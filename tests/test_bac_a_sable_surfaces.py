"""COL-4 — les surfaces qui traversent les projets (S8) et celles de l'administrateur (S6).

La Recherche et l'Exploration ne voient les bacs à sable POUR PERSONNE, ni l'administrateur
ni leur propriétaire (Q4, Hugo, 2026-10-21) : les mesures du corpus restent celles du vrai
corpus. Et une portée totale ne reçoit, de soixante-quinze bacs à sable, que le sien et ceux
où elle est invitée : elle est BORNÉE (Hugo, 2026-10-24) — la vue Projets de
l'Administration (`bacs_a_sable=1`) lui dit seulement qu'ils existent.
"""
import csv
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter

import pytest

import database
import journal
from conftest import ADMIN, REPO_ROOT, make_png
from test_bac_a_sable import HUGO, LEA, RESP, SAM, _copie, _sql, decor, jeu  # noqa: F401


@pytest.fixture
def corpus(client, decor):
    """Une bulle « LE OTAGE » dans le vrai projet, à côté de celles du jeu."""
    pl = client.post(f"/api/albums/{decor['reel']}/import", headers=RESP,
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    reg = client.post(f"/api/planches/{pl}/regions", headers=RESP,
                      json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    client.put(f"/api/regions/{reg}", headers=RESP, json={"ocr_texte": "LE OTAGE"})
    client.put(f"/api/regions/{reg}/annotation", headers=RESP,
               json={"note": "n", "tags": ["vrai-tag"]})
    planche = _copie(decor, "exemple")["planche_ids"][0]
    breg = client.get(f"/api/planches/{planche}/regions", headers=LEA).json()[-1]["id"]
    client.put(f"/api/regions/{breg}/annotation", headers=LEA,
               json={"note": "n", "tags": ["tag-du-bac", "vrai-tag"]})
    hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    return {**decor, "region_reelle": reg, "region_du_bac": breg, "bac_hugo": hugo}


def _regions_trouvees(client, qui, q="otage"):
    return {r["region_id"] for r in client.get("/api/recherche", headers=qui,
                                               params={"q": q}).json()["results"]}


def test_la_recherche_ne_voit_aucun_bac_a_sable(client, corpus):
    assert corpus["region_du_bac"] not in _regions_trouvees(client, LEA)
    trouvees = _regions_trouvees(client, HUGO)
    assert corpus["region_reelle"] in trouvees
    # Ni les copies des bacs à sable, ni la référence du jeu : la seule bulle est la vraie.
    assert trouvees == {corpus["region_reelle"]}
    assert client.get("/api/corpus", headers=LEA).json()["regions"] == 0
    stats = client.get("/api/corpus", headers=HUGO).json()
    assert stats["albums"] == _sql(corpus["db"], "SELECT COUNT(*) AS n FROM albums a JOIN "
                                                 "projet p ON p.id = a.projet_id WHERE "
                                                 "p.bac_a_sable_de IS NULL AND p.jeu = 0"
                                   )[0]["n"]


def test_l_exploration_ne_compte_aucun_bac_a_sable(client, corpus):
    """La concordance et les fréquences : ni la copie du jeu dans le bac à sable de lea, ni
    sa référence. Le vrai corpus porte UNE bulle « LE OTAGE » ; le jeu en porte deux de
    plus (la référence, la copie)."""
    r = client.get("/api/analyse/concordance", headers=HUGO,
                   params={"tags": "vrai-tag"}).json()
    regions = {x["region_id"] for x in r["results"]}
    assert corpus["region_du_bac"] not in regions
    assert client.get("/api/analyse/concordance", headers=LEA,
                      params={"tags": "vrai-tag"}).json()["results"] == []
    freq = client.get("/api/analyse/frequences", headers=HUGO,
                      params={"champ": "lemme"}).json()["results"]
    otage = sum(x["freq"] for x in freq if (x.get("lemme") or "").lower() == "otage")
    assert otage <= 1, freq


def test_le_nuage_et_le_lexique_ne_comptent_pas_les_bacs_a_sable(client, corpus):
    nuage = {t["label"]: t["frequence"] for t in client.get("/api/tags", headers=HUGO).json()}
    assert nuage.get("vrai-tag") == 1 and "tag-du-bac" not in nuage
    lexique = {t["label"]: t for t in client.get("/api/lexique", headers=HUGO).json()["tags"]}
    assert "tag-du-bac" not in lexique
    # L'Atelier, lui, propose sur l'album qu'il ouvre ce qui s'y pose.
    album = _copie(corpus, "exemple")["album_id"]
    assert "tag-du-bac" in {t["label"] for t in client.get(
        "/api/tags", headers=LEA, params={"album": album}).json()}


def test_l_accord_modele_humain_ne_compte_pas_le_jeu(client, corpus):
    """La référence au cran grammaire et ses copies portent une correction ; aucune ne
    compte : le vrai corpus n'en a pas."""
    assert _sql(corpus["db"], "SELECT COUNT(*) AS n FROM token_correction")[0]["n"] >= 2
    assert client.get("/api/analyse/accord", headers=HUGO).json()["revus"] == 0


def test_l_administrateur_ne_voit_que_ses_bacs_a_sable_sans_le_demander(client, corpus):
    vus = {p["id"] for p in client.get("/api/projets", headers=HUGO).json()}
    assert corpus["bac_hugo"]["id"] in vus and corpus["bac"]["id"] not in vus
    tous = {p["id"] for p in client.get("/api/projets?bacs_a_sable=1", headers=HUGO).json()}
    assert corpus["bac"]["id"] in tous
    # Rien de ce qu'il porte, même en le demandant : le paramètre n'existe que pour la liste
    # des projets.
    for chemin in ("/api/collections", "/api/collections?bacs_a_sable=1"):
        assert corpus["base"] not in {c["id"] for c in
                                      client.get(chemin, headers=HUGO).json()}
    copie = _copie(corpus, "exemple")["album_id"]
    for chemin in ("/api/albums", "/api/albums?bacs_a_sable=1"):
        assert copie not in {a["id"] for a in client.get(chemin, headers=HUGO).json()}
    # Un compte ordinaire ne reçoit pas les bacs à sable des autres en le demandant.
    assert corpus["bac"]["id"] not in {
        p["id"] for p in client.get("/api/projets?bacs_a_sable=1", headers=RESP).json()}
    # Invité dans un bac à sable, il le voit.
    client.put(f"/api/projets/{corpus['bac']['id']}/membres", headers=LEA,
               json={"genre": "utilisateur", "principal": "hugo", "role": "membre"})
    assert corpus["bac"]["id"] in {p["id"] for p in
                                   client.get("/api/projets", headers=HUGO).json()}


def test_un_compte_ordinaire_voit_ses_bacs_a_sable(client, corpus):
    assert corpus["bac"]["id"] in {p["id"] for p in
                                   client.get("/api/projets", headers=SAM).json()}
    assert corpus["bac"]["id"] in {p["id"] for p in
                                   client.get("/api/projets", headers=LEA).json()}


def test_comptes_et_groupes_ecarte_les_bacs_a_sable(client, corpus):
    vue = client.get("/api/comptes-et-groupes", headers=HUGO).json()
    comptes = {c["login"]: c for c in vue["comptes"]}
    assert comptes["lea"]["bac_a_sable"] is True and comptes["sam"]["bac_a_sable"] is False
    assert comptes["lea"]["entrees_projet"] == 0 and comptes["sam"]["entrees_projet"] == 0
    assert "collection de base" not in comptes["lea"]["verdict"]
    assert not any(c["par"] == "projet" for c in comptes["lea"]["collections"])
    ids = {c["id"] for c in vue["collections"]}
    assert corpus["base"] not in ids


def test_aucune_demande_d_un_bac_a_sable_dans_a_faire(client, corpus):
    """Aucune n'y naît plus (`test_bac_a_sable.test_rien_ne_se_demande_dans_un_bac_a_sable`).
    Une demande posée en base — d'avant ce refus, ou retouchée — ne paraît ni dans « À
    faire » ni dans la liste de l'administrateur ; et pas davantage une fois le bac à sable
    EFFACÉ, quand plus aucune ligne de `projet` ne dit qu'il en était un (relecture
    croisée : elle y reparaissait)."""
    pid = corpus["bac"]["id"]
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    copie = _copie(corpus, "exemple")["album_id"]
    assert client.put(f"/api/albums/{copie}/collections/{chez_sam}",
                      headers=SAM).status_code == 403
    demande = _sql(corpus["db"], "INSERT INTO demande (genre, demandeur, projet_id, "
                                 "projet_nom, collection_id, collection_nom) VALUES "
                                 "('rejoindre', 'sam', ?, 'Bac à sable', NULL, NULL) "
                                 "RETURNING id", (pid,))[0]["id"]

    def visible():
        vue = client.get("/api/comptes-et-groupes", headers=HUGO).json()
        return (demande in {l.get("demande") for l in vue["a_regarder"]}
                or demande in {d["id"] for d in
                               client.get("/api/demandes", headers=HUGO).json()})

    assert not visible()
    assert client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA).status_code == 200
    assert _sql(corpus["db"], "SELECT COUNT(*) AS n FROM projet WHERE id = ?",
                (pid,)) == [{"n": 0}]
    assert not visible()


def test_le_fonds_masque_les_bacs_a_sable_et_le_jeu(client, corpus):
    titres = {c["titre"] for d in client.get("/api/fonds", headers=HUGO).json()["documents"]
              for c in d["copies"]}
    assert "Réel" in titres and not {"Le parcours", "Un exemple", "Sous droits"} & titres
    # Et l'administrateur ne les lit pas en le demandant : il n'y a rien à demander.
    tout = {c["titre"] for d in client.get("/api/fonds?bacs_a_sable=1",
                                           headers=HUGO).json()["documents"]
            for c in d["copies"]}
    assert not {"Le parcours", "Un exemple", "Sous droits"} & tout


# --------------------------------------------------------------------------- #
# Le résumé de provenance compte ce que le journal publie (relevé par la relecture d'ANN-7)
# --------------------------------------------------------------------------- #
def _outil(db_path, outil, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(db_path.parent)}
    c = sqlite3.connect(db_path)
    try:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        c.close()
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / outil), *args],
                       cwd=str(REPO_ROOT), env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-600:]
    return r.stdout.decode("utf-8")


def _lignes(fichier):
    with open(fichier, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _publies(db_path):
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import _commun
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(e) for e in _commun.evenements_publiables(c)]
    finally:
        c.close()


def test_le_resume_de_provenance_ne_compte_pas_un_bac_a_sable(client, corpus, tmp_path):
    """De VRAIS actes dans le bac à sable de lea — une région posée, son texte retouché, sa
    note — et un run sur sa planche : ni la table publiée ni le résumé des deux artefacts ne
    les comptent. Des NOMBRES, comparés à ce que le même artefact publie ; le témoin, ce sont
    les actes du bac à sable d'abord lus au journal, et ceux du vrai corpus comptés."""
    db = corpus["db"]
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import _commun
    planche = _copie(corpus, "exemple")["planche_ids"][0]
    reg = client.post(f"/api/planches/{planche}/regions", headers=LEA,
                      json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    client.put(f"/api/regions/{reg}", headers=LEA, json={"ocr_texte": "DANS LE BAC"})
    client.put(f"/api/regions/{reg}/annotation", headers=LEA, json={"note": "n", "tags": []})
    conn = database.get_connection()
    try:
        journal.inscrire_run_termine(conn, "segmentation", agent="kumiko", agent_type="moteur",
                                     version=None, params=None,
                                     portee={"planche_id": planche},
                                     debut="2026-10-30 10:00:00", comptes={})
        cibles = sorted(_commun.CIBLES_CORPUS)
        du_bac = conn.execute(
            f"SELECT COUNT(*) FROM evenement WHERE cible_table IN ({','.join('?' * len(cibles))}) "
            "AND cible_id = ?", (*cibles, reg)).fetchone()[0]
        tous = conn.execute(
            f"SELECT COUNT(*) FROM evenement WHERE cible_table IN ({','.join('?' * len(cibles))})",
            cibles).fetchone()[0]
    finally:
        conn.close()
    publies = _publies(db)
    assert du_bac >= 2 and publies, "le semis ne mesure rien"
    assert len(publies) <= tous - du_bac
    assert any(e["cible_id"] == corpus["region_reelle"] for e in publies), "le témoin"
    assert not any(e["cible_id"] == reg for e in publies)

    meta = json.loads(_outil(db, "metadonnees_collection.py", "--json", "-"))
    prov = meta["metadonnees_collection"]["paradonnee"]["provenance"]
    _outil(db, "metadonnees_collection.py", "--csv-dir", str(tmp_path / "t"))
    evenements = _lignes(tmp_path / "t" / "evenement.csv")
    activites = _lignes(tmp_path / "t" / "activite.csv")
    audit = json.loads(_outil(db, "description_collection.py", "--json", "-"))
    audit = audit["description_collection"]["provenance_globale"]["audit"]
    for nom, resume in (("métadonnées", prov), ("description", audit)):
        ev = resume["evenements"]
        assert ev["total"] == len(publies) == len(evenements), (nom, ev["total"], len(publies))
        assert ev["par_type"] == dict(Counter(e["type"] for e in publies)), nom
        assert ev["par_agent"] == dict(Counter(e["agent_type"] for e in publies)), nom
        assert (ev["premier"], ev["dernier"]) == (min(e["date"] for e in publies),
                                                  max(e["date"] for e in publies)), nom
        assert resume["activites"]["total"] == len(activites) == 0, (nom, resume["activites"])


# --------------------------------------------------------------------------- #
# Une collection sans album n'a rien à résumer (relecture de `5adfd60`)
# --------------------------------------------------------------------------- #
def _resumes(db, *args):
    """Le résumé de provenance des deux artefacts, sortis par leurs outils."""
    meta = json.loads(_outil(db, "metadonnees_collection.py", "--json", "-", *args))
    audit = json.loads(_outil(db, "description_collection.py", "--json", "-", *args))
    return (("métadonnées", meta["metadonnees_collection"]["paradonnee"]["provenance"]),
            ("description", audit["description_collection"]["provenance_globale"]["audit"]))


def _seme_un_run(planche):
    conn = database.get_connection()
    try:
        journal.inscrire_run_termine(conn, "segmentation", agent="kumiko", agent_type="moteur",
                                     version=None, params=None, portee={"planche_id": planche},
                                     debut="2026-10-30 10:00:00", comptes={})
    finally:
        conn.close()


def test_une_collection_sans_album_ne_compte_rien(client, corpus, tmp_path):
    """Les vraies sorties d'une collection VIDE, à côté d'une instance qui a du travail : le
    témoin est la collection voisine, dont le même résumé n'est pas à zéro."""
    db = corpus["db"]
    pl = client.get(f"/api/albums/{corpus['reel']}/planches", headers=RESP).json()[0]["id"]
    _seme_un_run(pl)
    vide = client.post("/api/collections", headers=RESP,
                       json={"nom": "Vide", "projet_id": corpus["etude"]}).json()["id"]

    for nom, resume in _resumes(db, "--collection", str(corpus["col"])):
        assert resume["regions"]["total"] >= 1, nom
        assert resume["evenements"]["total"] >= 1 and resume["activites"]["total"] >= 1, nom

    def a_zero(nom, resume):
        assert resume["portee_regions"] == "collection", nom
        assert resume["regions"] == {"total": 0, "machine": 0, "humaines": 0, "touchees": 0,
                                     "derive": 0, "taux_touche": None, "taux_derive": None}, nom
        assert resume["activites"] == {"total": 0, "par_type": {}}, nom
        assert resume["evenements"] == {"total": 0, "par_type": {}, "par_agent": {},
                                        "premier": None, "dernier": None}, nom

    for nom, resume in _resumes(db, "--collection", str(vide)):
        a_zero(nom, resume)
    # … par la voie du dépôt comme par l'outil.
    r = client.get(f"/api/collections/{vide}/depot/description", headers=RESP)
    assert r.status_code == 200, r.text
    a_zero("route description",
           r.json()["description_collection"]["provenance_globale"]["audit"])
    r = client.get(f"/api/collections/{vide}/depot/metadonnees", headers=RESP)
    assert r.status_code == 200, r.text
    a_zero("route métadonnées", r.json()["metadonnees_collection"]["paradonnee"]["provenance"])
    # Le résumé dit ce que le même artefact publie : ses tables du journal aussi sont vides,
    # et celles d'une collection qui a un album ne le sont pas.
    _outil(db, "metadonnees_collection.py", "--collection", str(vide),
           "--csv-dir", str(tmp_path / "vide"))
    assert _lignes(tmp_path / "vide" / "evenement.csv") == []
    assert _lignes(tmp_path / "vide" / "activite.csv") == []
    _outil(db, "metadonnees_collection.py", "--collection", str(corpus["col"]),
           "--csv-dir", str(tmp_path / "pleine"))
    assert _lignes(tmp_path / "pleine" / "evenement.csv")
    assert _lignes(tmp_path / "pleine" / "activite.csv")


def test_le_corpus_ne_compte_pas_les_bacs_a_sable_meme_sans_autre_album(client, corpus,
                                                                        tmp_path):
    """Le corpus entier, quand TOUT album vivant est d'un projet isolé :
    `_commun.albums_du_corpus` rend une liste vide, et non `None`. Ses régions ne se comptent
    pas ; le journal reste au grain du corpus, celui que publie le même artefact."""
    db = corpus["db"]
    assert client.delete(f"/api/albums/{corpus['reel']}", headers=HUGO).status_code == 204
    assert _sql(db, "SELECT COUNT(*) AS n FROM regions")[0]["n"] >= 1, "le semis"
    _outil(db, "metadonnees_collection.py", "--csv-dir", str(tmp_path / "t"))
    evenements = _lignes(tmp_path / "t" / "evenement.csv")
    assert evenements, "le témoin : il reste un journal à résumer"
    for nom, resume in _resumes(db):
        assert resume["regions"]["total"] == 0, (nom, resume["regions"])
        assert resume["portee_regions"] == "corpus", nom
        assert resume["evenements"]["total"] == len(evenements), nom


def test_le_corpus_se_dit_corpus_a_cote_d_un_bac_a_sable(client, corpus):
    """`albums_du_corpus` rend la liste des albums dès qu'un bac à sable existe : le résumé
    d'un corpus entier ne se dit pas pour autant celui d'une collection."""
    for nom, resume in _resumes(corpus["db"]):
        assert resume["regions"]["total"] >= 1, nom
        assert resume["portee_regions"] == "corpus", nom
    for nom, resume in _resumes(corpus["db"], "--collection", str(corpus["col"])):
        assert resume["portee_regions"] == "collection", nom


# --------------------------------------------------------------------------- #
# Un projet isolé ne donne aucun rang dans les pseudonymes
# --------------------------------------------------------------------------- #
RITA = {"Remote-User": "rita", "Remote-Groups": ""}


def _rangs():
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import _commun
    conn = database.get_connection()
    try:
        return _commun.pseudonymes(conn)
    finally:
        conn.close()


def _faire_annoter(client, corpus, qui):
    """`qui` écrit dans la collection du vrai projet, et annote la bulle du corpus."""
    login = qui["Remote-User"]
    assert client.put(f"/api/projets/{corpus['etude']}/membres", headers=RESP,
                      json={"genre": "utilisateur", "principal": login,
                            "role": "membre"}).status_code == 200
    assert client.put(f"/api/collections/{corpus['col']}/acces", headers=RESP,
                      json={"genre": "utilisateur", "principal": login,
                            "niveau": "ecriture"}).status_code == 200
    r = client.put(f"/api/regions/{corpus['region_reelle']}/annotation", headers=qui,
                   json={"note": f"note de {login}", "tags": []})
    assert r.status_code == 200, r.text


def _dater(db, login, date, ou="1"):
    assert _sql(db, f"UPDATE evenement SET date = ? WHERE agent = ? AND {ou} RETURNING id",
                (date, login)), f"aucun acte de {login} à dater"


def _agents_publies(db, tmp_path):
    """Les agents que sortent réellement les tables du journal et le graphe PROV."""
    _outil(db, "metadonnees_collection.py", "--csv-dir", str(tmp_path / "agents"))
    _outil(db, "provenance_export.py", "--out-dir", str(tmp_path / "prov"))
    prov = "".join(f.read_text(encoding="utf-8") for f in (tmp_path / "prov").iterdir())
    return ({e["agent"] for e in _lignes(tmp_path / "agents" / "evenement.csv")}
            | {a["agent"] for a in _lignes(tmp_path / "agents" / "activite.csv")},
            prov)


def test_ouvrir_un_bac_a_sable_ne_donne_aucun_rang(client, corpus):
    """Deux comptes n'ont fait qu'ouvrir un bac à sable, AVANT que rita n'annote : elle sort
    au rang qu'elle aurait sans eux. Le témoin : leurs actes `projet` et `collection` sont
    bien au journal, aux dates les plus anciennes."""
    db = corpus["db"]
    _faire_annoter(client, corpus, RITA)
    _dater(db, "lea", "2026-01-01 08:00:00")
    _dater(db, "hugo", "2026-01-02 08:00:00")
    _dater(db, "decor", "2026-01-03 08:00:00")
    _dater(db, "resp", "2026-02-01 08:00:00")
    _dater(db, "rita", "2026-03-01 08:00:00")
    for login in ("lea", "hugo"):
        assert {"projet", "collection"} <= {e["cible_table"] for e in _sql(
            db, "SELECT cible_table FROM evenement WHERE agent = ?", (login,))}, login
    assert _rangs() == {"decor": "annotateur-1", "resp": "annotateur-2", "rita": "annotateur-3"}


def test_le_rang_d_un_compte_se_lit_hors_de_son_bac_a_sable(client, corpus, tmp_path):
    """lea travaille dans son bac à sable, puis annote le corpus après rita : ni son rang ni
    celui de rita ne doivent rien au bac, et elle sort sous pseudonyme."""
    db = corpus["db"]
    _dater(db, "lea", "2026-01-01 08:00:00")
    _faire_annoter(client, corpus, RITA)
    _dater(db, "decor", "2026-01-03 08:00:00")
    _dater(db, "resp", "2026-02-01 08:00:00")
    _dater(db, "rita", "2026-03-01 08:00:00")
    _faire_annoter(client, corpus, LEA)
    _dater(db, "lea", "2026-04-01 08:00:00",
           ou=f"cible_table = 'annotations' AND cible_id = {corpus['region_reelle']}")
    rangs = _rangs()
    assert list(rangs) == ["decor", "resp", "rita", "lea"]
    assert rangs["lea"] == "annotateur-4"
    agents, prov = _agents_publies(db, tmp_path)
    assert "annotateur-4" in agents and "annotateur-4" in prov
    assert not agents & {"lea", "rita", "resp", "hugo", "sam"}
    assert '"lea"' not in prov and "agent:lea" not in prov


def test_rien_ne_redonne_un_rang_une_fois_le_bac_a_sable_efface(client, corpus, tmp_path):
    """Le travail de comptes qui ne sont passés que par un bac à sable : une note, une région
    retirée après avoir été annotée, une collection créée puis supprimée par une invitée.
    Vivant ou remis à neuf, rien de cela ne donne de rang, et rien ne sort sous un login :
    un acte publié sans rang sortirait EN CLAIR (`pseudonymes(...).get(nom, nom)`)."""
    db = corpus["db"]
    planche = _copie(corpus, "exemple")["planche_ids"][0]
    reg = client.post(f"/api/planches/{planche}/regions", headers=LEA,
                      json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    assert client.put(f"/api/regions/{reg}/annotation", headers=LEA,
                      json={"note": "n", "tags": []}).status_code == 200
    assert client.delete(f"/api/regions/{reg}", headers=LEA).status_code == 204
    assert client.put(f"/api/regions/{corpus['region_du_bac']}/annotation", headers=LEA,
                      json={"note": "gardée", "tags": []}).status_code == 200
    # Une région RECOPIÉE n'a aucun acte de création : validée, son premier acte ne nomme
    # pas sa planche, et seule sa suppression le dit.
    recopiee = client.get(f"/api/planches/{_copie(corpus, 'grammaire')['planche_ids'][0]}"
                          "/regions", headers=LEA).json()[-1]["id"]
    assert client.put(f"/api/regions/{recopiee}/annotation", headers=LEA,
                      json={"note": "n", "tags": []}).status_code == 200
    r = client.post(f"/api/regions/{recopiee}/grammaire/valider", headers=LEA)
    assert r.status_code == 200, r.text
    assert client.delete(f"/api/regions/{recopiee}", headers=LEA).status_code == 204
    assert _sql(db, "SELECT type FROM evenement WHERE cible_table = 'regions' AND cible_id = ? "
                    "ORDER BY id", (recopiee,)) == [{"type": "validation"},
                                                    {"type": "suppression"}]
    col = client.post("/api/collections", headers=SAM,
                      json={"nom": "Essai", "projet_id": corpus["bac"]["id"]})
    assert col.status_code == 201, col.text
    assert client.delete(f"/api/collections/{col.json()['id']}",
                         headers=SAM).status_code == 204
    assert _sql(db, "SELECT COUNT(*) AS n FROM evenement WHERE agent = 'sam'")[0]["n"] >= 2

    temoin = {"decor", "resp"}
    assert set(_rangs()) == temoin
    assert client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA).status_code == 200
    assert _sql(db, "SELECT COUNT(*) AS n FROM evenement WHERE agent = 'lea' "
                    "AND type = 'abandon'")[0]["n"] >= 1, "le semis : un geste passé par elle"
    assert set(_rangs()) == temoin
    agents, prov = _agents_publies(db, tmp_path)
    assert not agents & {"lea", "sam", "hugo"}
    assert not any(a in prov for a in ('"lea"', "agent:lea", '"sam"', "agent:sam"))


def test_ni_correction_ni_run_d_un_projet_isole_ne_donnent_un_rang(client, corpus):
    """Les deux autres sources du rang, hors du journal d'actes : une correction grammaticale
    et un run humain dans le bac à sable ne comptent pas ; les mêmes dans le corpus comptent."""
    db = corpus["db"]
    grammaire = _copie(corpus, "grammaire")["planche_ids"][0]
    assert _sql(db, "UPDATE token_correction SET auteur = 'lea' WHERE region_id IN "
                    "(SELECT id FROM regions WHERE planche_id = ?) RETURNING id", (grammaire,))
    _sql(db, "INSERT INTO token_correction (region_id, ordre, forme, auteur) "
             "VALUES (?, 0, 'otage', 'tok')", (corpus["region_reelle"],))
    reelle = _sql(db, "SELECT planche_id AS p FROM regions WHERE id = ?",
                  (corpus["region_reelle"],))[0]["p"]
    conn = database.get_connection()
    try:
        for agent, planche in (("sam", grammaire), ("run", reelle)):
            journal.inscrire_run_termine(conn, "session", agent=agent, agent_type="humain",
                                         version=None, params=None,
                                         portee={"planche_id": planche},
                                         debut="2026-10-30 10:00:00", comptes={})
    finally:
        conn.close()
    rangs = _rangs()
    assert "lea" not in rangs and "sam" not in rangs
    assert {"tok", "run"} <= set(rangs)
