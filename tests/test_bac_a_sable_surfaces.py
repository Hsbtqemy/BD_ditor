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
