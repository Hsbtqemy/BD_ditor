"""COL-4 — « Mon bac à sable » : le créer, et le borner.

Les identités de la relecture (cadrage, « Le découpage en commits ») : un ARRIVANT qui n'a
QUE son bac à sable (`lea`), son INVITÉ (`sam`), un ADMINISTRATEUR qui a le sien (`hugo`), un
INCONNU (`rita`), et une RESPONSABLE d'un vrai projet qui a aussi son bac à sable
(`resp`). Le jeu est synthétique (`test_jeu.ecrire_jeu`).

Ce que ces tests tiennent, en une phrase par bloc :
- la question neuve (`peut_ouvrir_un_bac_a_sable`) et ses refus nommés ;
- un bac à sable par login, relu sous le verrou ;
- S2 : être responsable de son bac à sable ne donne RIEN ailleurs — la même réponse que
  sans bac à sable, joué question par question et route par route ;
- S3 : rien n'en sort, rien n'y entre, aucune demande n'atteint l'administrateur ;
- S5 : son propriétaire y détruit tout album ; un invité garde la règle commune ;
- S9 : le plafond d'import ; S11 : l'invitation.
"""
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import autorisation
import conflit
import database
import main
import socle
from conftest import ADMIN, make_png
from test_jeu import DOC_EXEMPLE, DOC_PARCOURS, DOC_STOCK_SERVEUR, ecrire_jeu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import preparer_jeu  # noqa: E402

LEA = {"Remote-User": "lea", "Remote-Groups": ""}
SAM = {"Remote-User": "sam", "Remote-Groups": ""}
RITA = {"Remote-User": "rita", "Remote-Groups": ""}
RESP = {"Remote-User": "resp", "Remote-Groups": ""}
HUGO = {"Remote-User": "hugo", "Remote-Groups": "bd-admins"}

# Un document au cran `grammaire`, dont la correction n'a pas d'auteur : le travail du jeu
# n'est à personne, donc « d'autrui » pour la règle commune de suppression.
DOC_GRAMMAIRE = {"cle": "grammaire", "titre": "La grammaire", "role": "exemple", "rang": 2,
                 "cran": "grammaire",
                 "planches": [{"fichier": "p3.png", "regions": [
                     {"type": "bulle", "x": 1, "y": 1, "w": 50, "h": 20, "texte": "OTAGE",
                      "corrections": [{"ordre": 0, "forme": "otage", "lemme": "otage",
                                       "pos": "NOUN"}]}]}]}


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


@pytest.fixture
def jeu(client, tmp_path):
    depot = ecrire_jeu(tmp_path / "jeu-depot", [DOC_PARCOURS, DOC_EXEMPLE, DOC_GRAMMAIRE],
                       images=("p1.png", "p2.png", "p3.png"))
    serveur = ecrire_jeu(tmp_path / "jeu-serveur", [DOC_STOCK_SERVEUR], images=("s1.png",))
    conn = database.get_connection()
    try:
        preparer_jeu.preparer(conn, depot=depot, serveur=serveur, appliquer_=True,
                              dire=lambda _l: None)
    finally:
        conn.close()
    return {r["cle"]: r for r in _sql(database.DB_PATH, "SELECT * FROM jeu_document")}


@pytest.fixture
def decor(client, db_path, jeu, derriere_proxy):
    """Un vrai projet (« Étude ») dont `resp` est responsable, une collection où elle écrit,
    un album réel ; et le bac à sable de `lea`, où `sam` est invité."""
    for qui in (LEA, SAM, RITA, RESP, HUGO):
        client.get("/api/moi", headers=qui)
    etude = client.post("/api/projets", json={"nom": "Étude"}, headers=ADMIN).json()["id"]
    client.put(f"/api/projets/{etude}/membres", headers=ADMIN,
               json={"genre": "utilisateur", "principal": "resp", "role": "responsable"})
    col = client.post("/api/collections", headers=RESP,
                      json={"nom": "Corpus", "projet_id": etude}).json()["id"]
    reel = client.post("/api/albums", headers=RESP,
                       json={"titre": "Réel", "collection_id": col}).json()["id"]
    r = client.post("/api/bac-a-sable", headers=LEA)
    assert r.status_code == 201, r.text
    bac = r.json()
    assert client.put(f"/api/projets/{bac['id']}/membres", headers=LEA,
                      json={"genre": "utilisateur", "principal": "sam",
                            "role": "membre"}).status_code == 200
    copies = {j["role"] + ":" + str(j["rang"]): j for j in bac["jeu"]}
    return {"etude": etude, "col": col, "reel": reel, "bac": bac, "copies": copies,
            "base": bac["base"]["id"], "db": db_path}


def _copie(decor, cle):
    """La copie, dans le bac à sable de lea, du document du jeu de cette clé."""
    return next(j for j in decor["bac"]["jeu"]
                if j["document_id"] == _sql(decor["db"], "SELECT document_id FROM jeu_document "
                                                         "WHERE cle = ?", (cle,))[0]["document_id"])


# --------------------------------------------------------------------------- #
# Créer
# --------------------------------------------------------------------------- #
def test_un_clic_cree_le_bac_a_sable_rempli_du_jeu(client, decor):
    bac, db = decor["bac"], decor["db"]
    p = _sql(db, "SELECT * FROM projet WHERE id = ?", (bac["id"],))[0]
    assert (p["nom"], p["bac_a_sable_de"], p["jeu"]) == ("Bac à sable", "lea", 0)
    assert bac["nom"] == "Mon bac à sable" and bac["efface_le"] == p["efface_le"]
    assert _sql(db, "SELECT genre, principal, role FROM projet_acces WHERE projet_id = ? "
                    "ORDER BY role DESC", (bac["id"],)) == [
        {"genre": "utilisateur", "principal": "lea", "role": "responsable"},
        {"genre": "utilisateur", "principal": "sam", "role": "membre"}]
    assert _sql(db, "SELECT acces_membres, base FROM collection WHERE id = ?",
                (decor["base"],)) == [{"acces_membres": "ecriture", "base": 1}]
    # Une copie par document du jeu, à son cran, créée par lea ; aucune image copiée.
    assert sorted((j["role"], j["cran"]) for j in bac["jeu"]) == [
        ("exemple", "grammaire"), ("exemple", "transcription"), ("pas-a-pas", "images"),
        ("stock", "images")]
    assert bac["jeu"][0]["role"] == "pas-a-pas" and bac["jeu"][0]["planche_ids"]
    for j in bac["jeu"]:
        c = _sql(db, "SELECT creee_par, cran FROM copie WHERE album_id = ?", (j["album_id"],))
        assert c == [{"creee_par": "lea", "cran": j["cran"]}]
    assert bac["planches_importees"] == 0 and bac["plafond_planches"] == 50
    # La copie au cran transcription porte le texte de la référence.
    ex = _copie(decor, "exemple")
    assert _sql(db, "SELECT r.ocr_texte FROM regions r JOIN planches p ON p.id = r.planche_id "
                    "WHERE p.album_id = ? AND r.ocr_texte IS NOT NULL",
                (ex["album_id"],)) == [{"ocr_texte": "LE OTAGE"}]


def test_recliquer_y_ramene(client, decor):
    r = client.post("/api/bac-a-sable", headers=LEA)
    assert r.status_code == 200 and r.json()["id"] == decor["bac"]["id"]
    assert client.get("/api/bac-a-sable", headers=LEA).json()["id"] == decor["bac"]["id"]
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de = 'lea'"
                ) == [{"n": 1}]


def test_un_par_login_relu_sous_le_verrou(client, decor, monkeypatch):
    """Deux clics simultanés : un second bac à sable naît entre la lecture et le verrou. La
    route relit SOUS le verrou, et rend celui qui vient de naître."""
    import routes.bac_a_sable as module
    vrai = conflit.verrouiller

    def concurrent(conn):
        if not getattr(concurrent, "fait", False):
            concurrent.fait = True
            autre = database.get_connection()
            try:
                vrai(autre)
                socle._creer_bac_a_sable(autre, "rita")
                autre.commit()
            finally:
                autre.close()
        return vrai(conn)

    monkeypatch.setattr(module.conflit, "verrouiller", concurrent)
    r = client.post("/api/bac-a-sable", headers=RITA)
    assert r.status_code == 200, r.text
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de = 'rita'"
                ) == [{"n": 1}]


def test_l_administrateur_a_le_sien(client, decor):
    r = client.post("/api/bac-a-sable", headers=HUGO)
    assert r.status_code == 201
    vus = {p["id"]: p for p in client.get("/api/projets", headers=HUGO).json()}
    assert vus[r.json()["id"]]["bac_a_sable"]["mien"] is True
    assert vus[r.json()["id"]]["nom"] == "Mon bac à sable"


def test_sans_identite_pas_de_bac_a_sable(client, decor):
    assert client.post("/api/bac-a-sable").status_code == 403
    assert client.get("/api/bac-a-sable").json() is None


def test_le_mono_poste_n_a_pas_de_bac_a_sable(client, jeu):
    r = client.post("/api/bac-a-sable")
    assert r.status_code == 403 and "compte nommé" in r.json()["detail"]
    assert client.get("/api/bac-a-sable").json() is None


def test_un_compte_partage_n_a_pas_de_bac_a_sable(client, decor):
    client.get("/api/moi", headers={"Remote-User": "groupe-tp"})
    assert client.patch("/api/comptes/groupe-tp/nature", headers=ADMIN,
                        json={"nature": "collectif"}).status_code == 200
    r = client.post("/api/bac-a-sable", headers={"Remote-User": "groupe-tp"})
    assert r.status_code == 403 and "partagé" in r.json()["detail"]


def test_la_date_d_effacement_est_le_lundi_a_4h_de_paris(client, decor):
    efface = datetime.strptime(decor["bac"]["efface_le"], "%Y-%m-%d %H:%M:%S")
    local = efface + database.decalage_de_paris(efface)
    assert (local.weekday(), local.hour, local.minute) == (0, 4, 0)
    assert timedelta(0) < efface - datetime.utcnow() <= timedelta(days=7)


@pytest.mark.parametrize("maintenant, attendu", [
    # Un dimanche soir d'hiver : le lendemain 4 h, heure de Paris = 3 h UTC — sans
    # exception, même ouvert la veille (Hugo, 2026-10-22).
    ("2026-11-01 22:00:00", "2026-11-02 03:00:00"),
    # Un lundi 3 h 59 de Paris (hiver) : dans la minute.
    ("2026-11-02 02:59:00", "2026-11-02 03:00:00"),
    # Le lundi 4 h passé : la semaine suivante.
    ("2026-11-02 03:00:00", "2026-11-09 03:00:00"),
    # En été, 4 h de Paris = 2 h UTC.
    ("2026-07-01 12:00:00", "2026-07-06 02:00:00"),
    # Le changement d'heure d'octobre a lieu le dimanche : le lundi d'après est en hiver.
    ("2026-10-24 12:00:00", "2026-10-26 03:00:00"),
    # Celui de mars : le lundi d'après est en été.
    ("2026-03-28 12:00:00", "2026-03-30 02:00:00"),
])
def test_prochain_effacement(maintenant, attendu):
    assert database.prochain_effacement(
        datetime.strptime(maintenant, "%Y-%m-%d %H:%M:%S")) == attendu


def test_l_invite_lit_de_qui_est_le_bac_a_sable(client, decor):
    vus = {p["id"]: p for p in client.get("/api/projets", headers=SAM).json()}
    vue = vus[decor["bac"]["id"]]
    assert vue["nom"] == "Bac à sable · lea" and vue["gerable"] is False
    assert vue["bac_a_sable"] == {"mien": False, "efface_le": decor["bac"]["efface_le"],
                                  "proprietaire": "lea"}
    # Un inconnu ne le voit pas, ni dans la liste ni par son identifiant.
    assert decor["bac"]["id"] not in {p["id"] for p in
                                      client.get("/api/projets", headers=RITA).json()}
    assert client.get(f"/api/projets/{decor['bac']['id']}/membres",
                      headers=RITA).status_code == 404


def test_un_login_long_se_coupe_a_la_source(client, decor):
    long = {"Remote-User": "une-personne-au-tres-long-login"}
    assert client.post("/api/bac-a-sable", headers=long).status_code == 201
    vus = client.get("/api/projets", headers=HUGO).json()
    # La portée totale ne voit pas les bacs à sable des autres sans le demander (S6) ;
    # l'invitée, si.
    pid = _sql(decor["db"], "SELECT id FROM projet WHERE bac_a_sable_de = ?",
               (long["Remote-User"],))[0]["id"]
    client.put(f"/api/projets/{pid}/membres", headers=long,
               json={"genre": "utilisateur", "principal": "sam", "role": "membre"})
    vue = {p["id"]: p for p in client.get("/api/projets", headers=SAM).json()}[pid]
    assert len(vue["nom"]) == database.LONGUEUR_NOM_PROJET
    assert vue["nom"].startswith("Bac à sable · une-")


# --------------------------------------------------------------------------- #
# S2 — ce qu'il ne donne pas ailleurs
# --------------------------------------------------------------------------- #
def _portee(db, qui):
    class R:
        headers = {k: v for k, v in qui.items()}
    conn = database.get_connection()
    try:
        return autorisation.resoudre(conn, R)
    finally:
        conn.close()


QUESTIONS_TRANSVERSES = ("peut_ecrire_quelque_part", "peut_lire_les_notices",
                         "peut_decider_des_projets", "peut_tenir_le_fonds",
                         "peut_exporter_quelque_part")


def test_l_arrivant_ne_gagne_rien_hors_de_son_bac_a_sable(client, decor):
    """Le patron de `test_projet_ecran` : chaque question transverse de `Portee`, sous
    l'arrivant qui n'a QUE son bac à sable, et sous l'invité, répond comme sans bac à
    sable — c'est-à-dire non."""
    for qui in (LEA, SAM):
        p = _portee(decor["db"], qui)
        assert p.lecture, "le bac à sable est bien lu"
        for q in QUESTIONS_TRANSVERSES:
            assert getattr(p, q)() is False, (qui, q)
        assert p.peut_ecrire_terme(None) is False, qui
        # Mais dans le bac à sable, on travaille comme ailleurs.
        assert p.peut_ecrire(decor["base"]), qui
    # La responsable d'un vrai projet garde ce qu'elle avait, son bac à sable en plus.
    client.post("/api/bac-a-sable", headers=RESP)
    p = _portee(decor["db"], RESP)
    assert p.peut_lire_les_notices() and p.peut_ecrire_quelque_part()


@pytest.mark.parametrize("methode, chemin, corps", [
    ("get", "/api/fonds/notices", None),
    ("post", "/api/tags", {"label": "global-neuf"}),
    ("post", "/api/personnages", {"nom": "Inventé"}),
    ("post", "/api/domaines", {"nom": "émotions"}),
    ("post", "/api/attributs/dimensions", {"cible": "case", "nom": "cadrage"}),
    ("post", "/api/contribution-roles", {"label": "lettreur"}),
    ("get", "/api/analyse/accord-inter", None),
    ("get", "/api/recherche/export.csv?q=otage", None),
])
def test_les_routes_transverses_repondent_comme_sans_bac_a_sable(client, decor, methode,
                                                                 chemin, corps):
    r = getattr(client, methode)(chemin, headers=LEA,
                                 **({"json": corps} if corps is not None else {}))
    assert r.status_code == 403, (chemin, r.status_code, r.text)


def test_le_bandeau_de_portee_vide_reste_allume(client, decor):
    acces = client.get("/api/moi", headers=LEA).json()["acces"]
    assert (acces["collections"], acces["ecriture"], acces["exporter"]) == (0, 0, "rien")
    acces = client.get("/api/moi", headers=RESP).json()["acces"]
    assert acces["collections"] >= 1


def test_un_tag_tape_dans_un_bac_a_sable_y_nait_local(client, decor):
    planche = _copie(decor, "exemple")["planche_ids"][0]
    region = client.get(f"/api/planches/{planche}/regions", headers=LEA).json()[0]["id"]
    r = client.put(f"/api/regions/{region}/annotation", headers=LEA,
                   json={"note": "n", "tags": ["mot-du-bac"]})
    assert r.status_code == 200 and [t["label"] for t in r.json()["tags"]] == ["mot-du-bac"]
    assert _sql(decor["db"], "SELECT collection_id FROM tags WHERE label = 'mot-du-bac'") == [
        {"collection_id": decor["base"]}]
    # Hors d'un bac à sable, rien ne change : un libellé libre naît global.
    pl = client.post(f"/api/albums/{decor['reel']}/import", headers=RESP,
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    reg = client.post(f"/api/planches/{pl}/regions", headers=RESP,
                      json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    client.put(f"/api/regions/{reg}/annotation", headers=RESP,
               json={"note": "n", "tags": ["mot-du-corpus"]})
    assert _sql(decor["db"], "SELECT collection_id FROM tags WHERE label = 'mot-du-corpus'"
                ) == [{"collection_id": None}]


def test_l_annuaire_ne_se_lit_pas_dans_un_bac_a_sable(client, decor):
    pid = decor["bac"]["id"]
    for qui in (LEA, HUGO):
        r = client.get(f"/api/projets/{pid}/membres/choix", headers=qui)
        assert r.status_code == 403 and "annuaire" in r.json()["detail"], (qui, r.text)
    r = client.get(f"/api/collections/{decor['base']}/annuaire", headers=LEA)
    assert r.status_code == 403
    # Et le miroir `utilisateur` ne dit pas si un login tapé est venu.
    membres = client.get(f"/api/projets/{pid}/membres", headers=LEA).json()
    assert membres and all("jamais_vu" not in m for m in membres)
    cid = client.post("/api/collections", headers=LEA,
                      json={"nom": "La mienne", "projet_id": pid}).json()
    assert cid["acces"] and all("jamais_vu" not in a for a in cid["acces"])
    assert all("jamais_vu" not in a for a in
               client.get(f"/api/collections/{cid['id']}/acces", headers=LEA).json())


def test_aucun_acces_ne_se_pose_collection_par_collection(client, decor):
    r = client.put(f"/api/collections/{decor['base']}/acces", headers=LEA,
                   json={"genre": "groupe", "principal": "etudiants", "niveau": "ecriture"})
    assert r.status_code == 409 and "membre" in r.json()["detail"], r.text
    r = client.put(f"/api/collections/{decor['base']}/acces", headers=HUGO,
                   json={"genre": "utilisateur", "principal": "rita", "niveau": "lecture"})
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# S11 — l'invitation
# --------------------------------------------------------------------------- #
def test_l_invitation_est_bornee(client, decor):
    pid = decor["bac"]["id"]

    def poser(qui, **corps):
        return client.put(f"/api/projets/{pid}/membres", headers=qui,
                          json={"genre": "utilisateur", "principal": "rita",
                                "role": "membre", **corps})

    assert poser(LEA, genre="groupe", principal="etudiants").status_code == 409
    assert poser(LEA, role="responsable").status_code == 409
    # La ligne du propriétaire ne se touche pas — refusé par SON motif, pas seulement par
    # celui du dernier responsable, qui ne tiendrait plus le jour où il y en aurait deux.
    r = poser(LEA, principal="lea")
    assert r.status_code == 409 and "propriétaire de ce bac" in r.json()["detail"], r.text
    # L'invité ne règle rien ; l'administrateur non plus : la portée totale n'y ouvre rien.
    assert poser(SAM).status_code == 403
    # Et la liste le dit à l'administrateur : il ne règle pas ce bac à sable.
    vue = {p["id"]: p for p in client.get("/api/projets?bacs_a_sable=1", headers=HUGO).json()}
    assert vue[pid]["gerable"] is False and "justification" not in vue[pid]
    r = poser(HUGO)
    assert r.status_code == 403 and "propriétaire" in r.json()["detail"]
    assert client.put(f"/api/projets/{pid}/acces-membres", headers=HUGO,
                      json={"acces_membres": None}).status_code == 403
    # Le propriétaire ne se retire pas ; l'invité, si, par le propriétaire.
    r = client.delete(f"/api/projets/{pid}/membres/utilisateur/lea", headers=LEA)
    assert r.status_code == 409 and "propriétaire de ce bac" in r.json()["detail"], r.text
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/sam",
                         headers=HUGO).status_code == 403
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/sam",
                         headers=LEA).status_code == 204
    assert poser(LEA).status_code == 200


def test_l_invite_travaille_dans_le_jeu(client, decor):
    planche = _copie(decor, "exemple")["planche_ids"][0]
    r = client.post(f"/api/planches/{planche}/regions", headers=SAM,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 201


def test_un_bac_a_sable_ne_se_renomme_ni_ne_se_supprime(client, decor):
    pid = decor["bac"]["id"]
    assert client.patch(f"/api/projets/{pid}", json={"nom": "Autre"},
                        headers=HUGO).status_code == 409
    assert client.delete(f"/api/projets/{pid}", headers=HUGO).status_code == 409


# --------------------------------------------------------------------------- #
# S3 — rien n'en sort, rien n'y entre
# --------------------------------------------------------------------------- #
def test_une_copie_du_bac_a_sable_n_est_la_source_de_rien_ailleurs(client, decor):
    """Pour la responsable qui a son bac à sable, et pour la portée totale."""
    client.post("/api/bac-a-sable", headers=RESP)
    bac_resp = client.get("/api/bac-a-sable", headers=RESP).json()
    source = bac_resp["jeu"][0]
    for qui in (RESP, HUGO):
        for reponse, extra in (("zero", {}), ("amorcer", {"cran": "decoupage"})):
            r = client.post(f"/api/collections/{decor['col']}/prendre", headers=qui,
                            json={"documents": [{"document_id": source["document_id"],
                                                 "reponse": reponse,
                                                 "album_id": source["album_id"], **extra}],
                                  "motif": "x"})
            ligne = r.json()["documents"][0]
            assert ligne["etat"] == "refuse" and "cul-de-sac" in ligne["motif"], (qui, r.text)
    # Sans nommer la copie, le document du jeu n'existe pas pour un vrai projet.
    r = client.post(f"/api/collections/{decor['col']}/prendre", headers=RESP,
                    json={"documents": [{"document_id": source["document_id"],
                                         "reponse": "zero"}], "motif": "x"})
    assert r.status_code == 404
    r = client.get(f"/api/albums/{source['album_id']}/amorcer/apercu", headers=HUGO,
                   params={"collection": decor["col"], "cran": "decoupage"})
    assert r.status_code == 409


def test_rien_n_entre_dans_un_bac_a_sable(client, decor):
    doc = _sql(decor["db"], "SELECT document_id FROM albums WHERE id = ?",
               (decor["reel"],))[0]["document_id"]
    corps = {"documents": [{"document_id": doc, "reponse": "zero"}], "motif": "x"}
    # La propriétaire du bac à sable ne nomme pas un document du fonds…
    assert client.post(f"/api/collections/{decor['base']}/prendre", headers=LEA,
                       json=corps).status_code == 404
    # … et la portée totale se voit refuser, par la nature du projet.
    hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    r = client.post(f"/api/collections/{hugo['base']['id']}/prendre", headers=HUGO, json=corps)
    assert r.json()["documents"][0]["etat"] == "refuse", r.text
    # Le rangement ne traverse pas les projets (déjà tenu).
    assert client.put(f"/api/albums/{decor['reel']}/collections/{hugo['base']['id']}",
                      headers=HUGO).status_code == 409


def test_la_proprietaire_ne_nomme_pas_ce_qu_elle_ne_lit_pas(client, decor):
    """Un document importé par l'invité dans SA collection du bac à sable : la propriétaire
    ne le lit pas, donc ne le nomme pas — être responsable de son bac à sable n'ouvre rien
    (S2). Sans cela, la prise en ferait une demande d'entrée… à un administrateur."""
    pid = decor["bac"]["id"]
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    a = client.post("/api/albums", headers=SAM,
                    json={"titre": "À sam", "collection_id": chez_sam}).json()["id"]
    doc = _sql(decor["db"], "SELECT document_id FROM albums WHERE id = ?",
               (a,))[0]["document_id"]
    r = client.post(f"/api/collections/{decor['base']}/prendre", headers=LEA,
                    json={"documents": [{"document_id": doc, "reponse": "zero"}],
                          "motif": "x"})
    assert r.status_code == 404, r.text
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM demande") == [{"n": 0}]


def test_un_document_ne_dans_un_bac_a_sable_n_a_pas_de_notice(client, decor):
    a = client.post("/api/albums", headers=LEA,
                    json={"titre": "Importé au bac", "collection_id": decor["base"]})
    assert a.status_code == 201
    titres = {n["titre"] for n in client.get("/api/fonds/notices", headers=HUGO,
                                             params={"limit": 200}).json()["notices"]}
    assert "Importé au bac" not in titres and "Réel" in titres
    assert not {"Le parcours", "Un exemple", "Sous droits"} & titres


def test_aucune_demande_n_atteint_l_administrateur(client, decor):
    copie = _copie(decor, "grammaire")["album_id"]
    r = client.post("/api/demandes", headers=SAM,
                    json={"genre": "suppression_document", "album_id": copie,
                          "motif": "x", "certifie": True})
    assert r.status_code == 403 and "propriétaire" in r.json()["detail"], r.text
    r = client.post("/api/demandes", headers=LEA,
                    json={"genre": "suppression_projet", "projet_id": decor["bac"]["id"],
                          "motif": "x"})
    assert r.status_code == 409
    # La propriétaire, elle, n'a rien à demander : elle le fait.
    r = client.post("/api/demandes", headers=LEA,
                    json={"genre": "suppression_document", "album_id": copie,
                          "motif": "x", "certifie": True})
    assert r.status_code == 409 and "vous-même" in r.json()["detail"]
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM demande") == [{"n": 0}]


def test_un_rejoindre_que_seul_l_administrateur_consentirait_est_refuse(client, decor):
    """Une collection de sam dans le bac à sable, une copie qui vit dans la base ET chez
    lui : aucun propriétaire ne les tient toutes — la demande irait à un administrateur."""
    pid = decor["bac"]["id"]
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    copie = _copie(decor, "exemple")["album_id"]
    # sam range la copie chez lui : il faudrait le consentement de lea (base) — demande.
    r = client.put(f"/api/albums/{copie}/collections/{chez_sam}", headers=SAM)
    assert r.status_code == 202 and r.json()["repondra"] == "proprietaire"
    client.post(f"/api/demandes/{r.json()['demande_id']}/reponse", headers=LEA,
                json={"reponse": "acceptee"})
    a_lea = client.post("/api/collections", headers=LEA,
                        json={"nom": "Chez Léa", "projet_id": pid}).json()["id"]
    r = client.put(f"/api/albums/{copie}/collections/{a_lea}", headers=LEA)
    assert r.status_code == 403 and "propriétaire" in r.json()["detail"], r.text
    # Et par la prise : en partir, que seul un administrateur consentirait, est refusé.
    doc = _sql(decor["db"], "SELECT document_id FROM albums WHERE id = ?",
               (copie,))[0]["document_id"]
    r = client.post(f"/api/collections/{a_lea}/prendre", headers=LEA,
                    json={"documents": [{"document_id": doc, "reponse": "amorcer",
                                         "album_id": copie, "cran": "decoupage"}]})
    ligne = r.json()["documents"][0]
    assert ligne["etat"] == "refuse" and "propriétaire" in ligne["motif"], r.text
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM demande WHERE genre = 'amorcer'"
                ) == [{"n": 0}]


def test_la_proprietaire_rend_elle_meme_une_copie_gardee(client, decor):
    copie = _copie(decor, "exemple")
    assert client.delete(f"/api/albums/{copie['album_id']}/collections/{decor['base']}",
                         headers=LEA).status_code == 204
    corps = {"documents": [{"document_id": copie["document_id"], "reponse": "reprendre",
                            "album_id": copie["album_id"]}]}
    # L'invité ne lit pas la copie gardée : il ne la nomme pas (404, comme ailleurs), et
    # rien ne se demande.
    r = client.post(f"/api/projets/{decor['bac']['id']}/prendre", headers=SAM, json=corps)
    assert r.status_code == 404
    r = client.post(f"/api/projets/{decor['bac']['id']}/prendre", headers=LEA, json=corps)
    assert r.json()["documents"][0]["etat"] == "fait", r.text
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM demande") == [{"n": 0}]


# --------------------------------------------------------------------------- #
# S5 — la règle de destruction dans un bac à sable
# --------------------------------------------------------------------------- #
def test_la_proprietaire_detruit_tout_album_de_son_bac_a_sable(client, decor):
    """La copie au cran grammaire porte une correction sans auteur — « d'autrui » pour la
    règle commune — et une case posée par l'invité : sa propriétaire la détruit seule."""
    copie = _copie(decor, "grammaire")
    client.post(f"/api/planches/{copie['planche_ids'][0]}/regions", headers=SAM,
                json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
    vu = {a["id"]: a for a in client.get("/api/albums", headers=LEA).json()}
    assert vu[copie["album_id"]]["destructible"] is True
    assert {a["id"]: a for a in client.get("/api/albums", headers=SAM).json()
            }[copie["album_id"]]["destructible"] is False
    assert client.delete(f"/api/albums/{copie['album_id']}", headers=SAM).status_code == 403
    assert client.delete(f"/api/albums/{copie['album_id']}", headers=LEA).status_code == 204
    # Les images du jeu restent : la référence les désigne.
    ref = _sql(decor["db"], "SELECT chemin_web FROM planches p JOIN jeu_document jd "
                            "ON jd.album_reference = p.album_id WHERE jd.cle = 'grammaire'")
    assert ref and (decor["db"].parent / ref[0]["chemin_web"]).is_file()


def test_l_invite_garde_la_regle_commune_sur_sa_copie(client, decor):
    a = client.post("/api/albums", headers=SAM,
                    json={"titre": "À sam", "collection_id": decor["base"]}).json()["id"]
    assert client.delete(f"/api/albums/{a}", headers=SAM).status_code == 204


def test_le_proprietaire_d_un_autre_bac_n_y_detruit_rien(client, decor):
    client.post("/api/bac-a-sable", headers=RITA)
    copie = _copie(decor, "grammaire")["album_id"]
    assert client.delete(f"/api/albums/{copie}", headers=RITA).status_code == 404


# --------------------------------------------------------------------------- #
# L'export, document par document ; S9 — le plafond d'import
# --------------------------------------------------------------------------- #
def test_l_export_se_decide_document_par_document(client, decor):
    depot = _copie(decor, "exemple")["album_id"]
    serveur = _copie(decor, "stock-serveur")["album_id"]
    importe = client.post("/api/albums", headers=LEA,
                          json={"titre": "À moi", "collection_id": decor["base"]}).json()["id"]
    assert client.get("/api/export/json", headers=LEA,
                      params={"album_id": depot}).status_code == 200
    for a in (serveur, importe):
        r = client.get("/api/export/json", headers=LEA, params={"album_id": a})
        assert r.status_code == 403 and "dépôt" in r.json()["detail"], r.text
        # Pour la portée totale aussi : c'est le document qui décide.
        assert client.get("/api/export/csv", headers=HUGO,
                          params={"album_id": a}).status_code == 403
    r = client.get(f"/api/collections/{decor['base']}/depot/description", headers=LEA)
    assert r.status_code == 409


def test_le_plafond_d_import(client, decor, monkeypatch):
    monkeypatch.setattr(socle, "BAC_A_SABLE_PLAFOND_PLANCHES", 2)
    a = client.post("/api/albums", headers=LEA,
                    json={"titre": "Import", "collection_id": decor["base"]}).json()["id"]

    def importer():
        return client.post(f"/api/albums/{a}/import", headers=LEA,
                           files={"file": ("p.png", make_png(), "image/png")})

    assert importer().status_code == 201 and importer().status_code == 201
    r = importer()
    assert r.status_code == 409 and "2 planches" in r.json()["detail"], r.text
    assert client.get("/api/bac-a-sable", headers=LEA).json()["planches_importees"] == 2
    # Hors d'un bac à sable, aucun plafond.
    for _ in range(3):
        assert client.post(f"/api/albums/{decor['reel']}/import", headers=RESP,
                           files={"file": ("p.png", make_png(), "image/png")}
                           ).status_code == 201


def test_sharedocs_dans_un_bac_a_sable_sous_son_propre_compte(client, decor):
    a = client.post("/api/albums", headers=LEA,
                    json={"titre": "Import", "collection_id": decor["base"]}).json()["id"]
    for compte in (None, "instance"):
        r = client.post("/api/sharedocs/importer", headers=LEA,
                        json={"album_id": a, "chemins": ["x/p.png"], "compte": compte})
        assert r.status_code == 403 and "propre compte" in r.json()["detail"], r.text
