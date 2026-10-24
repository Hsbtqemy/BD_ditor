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
    r = client.get(f"/api/projets/{pid}/membres/choix", headers=LEA)
    assert r.status_code == 403 and "annuaire" in r.json()["detail"], r.text
    # L'administrateur ne voit pas le bac à sable d'un autre ; dans le sien, la même règle.
    assert client.get(f"/api/projets/{pid}/membres/choix", headers=HUGO).status_code == 404
    a_hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    r = client.get(f"/api/projets/{a_hugo['id']}/membres/choix", headers=HUGO)
    assert r.status_code == 403 and "annuaire" in r.json()["detail"], r.text
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
    assert r.status_code == 404                 # le bac à sable d'un autre : rien
    a_hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    r = client.put(f"/api/collections/{a_hugo['base']['id']}/acces", headers=HUGO,
                   json={"genre": "utilisateur", "principal": "rita", "niveau": "lecture"})
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# L'administrateur dans le bac à sable d'un autre : RIEN (Hugo, 2026-10-24)
# --------------------------------------------------------------------------- #
QUESTIONS_DE_COLLECTION = ("peut_lire", "peut_ecrire", "peut_administrer", "peut_exporter",
                           "peut_ecrire_terme", "peut_remanier_tag")
QUESTIONS_DE_PROJET = ("est_du_projet", "peut_gerer_projet")
CLAUSES_D_ALBUM = ("clause_album", "clause_destruction", "clause_suppression_directe",
                   "clause_rejoindre_directe")


def _albums_ouverts(db, portee, clause, album_id):
    ou, params = getattr(portee, clause)("a.id")
    c = database.get_connection()
    try:
        return c.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                         (album_id, *params)).fetchone() is not None
    finally:
        c.close()


def test_la_portee_totale_ne_passe_dans_aucun_bac_d_autrui(client, decor):
    """Question par question de `Portee`, le patron de `test_projet_ecran` : sur la base et
    le projet du bac à sable de lea, l'administrateur répond comme un non-membre (rita) —
    non partout. Sur le vrai corpus, sa portée totale reste entière."""
    copie = _copie(decor, "exemple")["album_id"]
    for qui in (HUGO, RITA):
        p = _portee(decor["db"], qui)
        for q in QUESTIONS_DE_COLLECTION:
            assert getattr(p, q)(decor["base"]) is False, (qui, q)
        for q in QUESTIONS_DE_PROJET:
            assert getattr(p, q)(decor["bac"]["id"]) is False, (qui, q)
        for q in CLAUSES_D_ALBUM:
            assert not _albums_ouverts(decor["db"], p, q, copie), (qui, q)
        o, prm = p.clause_projet("p.id")
        c = database.get_connection()
        try:
            assert c.execute(f"SELECT 1 FROM projet p WHERE p.id = ? AND {o}",
                             (decor["bac"]["id"], *prm)).fetchone() is None, qui
            assert c.execute(f"SELECT 1 FROM collection c WHERE c.id = ? AND "
                             f"{p.clause_terme('c.id')[0]}",
                             (decor["base"], *p.clause_terme("c.id")[1])).fetchone() is None
        finally:
            c.close()
    h = _portee(decor["db"], HUGO)
    assert h.tout and h.bornee
    assert all(getattr(h, q)(decor["col"]) for q in QUESTIONS_DE_COLLECTION)
    assert h.peut_gerer_projet(decor["etude"]) and h.est_du_projet(decor["etude"])
    for q in CLAUSES_D_ALBUM:
        assert _albums_ouverts(decor["db"], h, q, decor["reel"]), q


def test_les_lots_de_l_administrateur_ne_touchent_pas_le_bac_d_un_autre(client, decor):
    """Un lot (passes automatiques) ne porte que sur des planches où l'on écrit, et un lot
    n'est visible qu'à qui les lit toutes (`main._planches_autorisees`) : celles du bac à
    sable de lea n'y sont pas pour l'administrateur — matérialisées, pas `None`."""
    planche_bac = _copie(decor, "exemple")["planche_ids"][0]
    pl = client.post(f"/api/albums/{decor['reel']}/import", headers=RESP,
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    conn = database.get_connection()
    try:
        for ecriture in (False, True):
            ok = main._planches_autorisees(conn, _portee(decor["db"], HUGO),
                                           ecriture=ecriture)
            assert ok is not None and pl in ok and planche_bac not in ok, ecriture
    finally:
        conn.close()


@pytest.mark.parametrize("geste", [
    "lire l'album", "lire ses planches", "lire une région", "écrire une région",
    "annoter", "créer une région", "lire ses collections", "lire les membres",
    "créer une collection", "inviter", "détruire l'album", "lire les accès", "exporter",
    "prendre", "ranger", "proposer les tags", "régler la base", "décrire la base"])
def test_l_administrateur_n_a_rien_dans_le_bac_d_un_autre(client, decor, geste):
    """Route par route : la portée totale ne passe pas dans le bac à sable de lea — 404,
    comme pour qui n'en est pas (rita, qui joue le même geste). Rien n'y est écrit."""
    copie = _copie(decor, "exemple")
    planche = copie["planche_ids"][0]
    region = _sql(decor["db"], "SELECT id FROM regions WHERE planche_id = ? ORDER BY id",
                  (planche,))[0]["id"]
    pid, base = decor["bac"]["id"], decor["base"]
    gestes = {
        "lire l'album": ("get", f"/api/albums/{copie['album_id']}/contributions", None),
        "lire ses planches": ("get", f"/api/albums/{copie['album_id']}/planches", None),
        "lire une région": ("get", f"/api/regions/{region}/annotation", None),
        "écrire une région": ("put", f"/api/regions/{region}", {"ocr_texte": "ADMIN"}),
        "annoter": ("put", f"/api/regions/{region}/annotation", {"note": "x", "tags": []}),
        "créer une région": ("post", f"/api/planches/{planche}/regions",
                             {"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}),
        "lire ses collections": ("get", f"/api/albums/{copie['album_id']}/collections", None),
        "lire les membres": ("get", f"/api/projets/{pid}/membres", None),
        "créer une collection": ("post", "/api/collections",
                                 {"nom": "Ici", "projet_id": pid}),
        "inviter": ("put", f"/api/projets/{pid}/membres",
                    {"genre": "utilisateur", "principal": "rita", "role": "membre"}),
        "détruire l'album": ("delete", f"/api/albums/{copie['album_id']}", None),
        "lire les accès": ("get", f"/api/collections/{base}/acces", None),
        "exporter": ("get", f"/api/export/json?album_id={copie['album_id']}", None),
        "prendre": ("post", f"/api/collections/{base}/prendre",
                    {"documents": [{"document_id": copie["document_id"], "reponse": "zero"}],
                     "motif": "x"}),
        "ranger": ("put", f"/api/albums/{decor['reel']}/collections/{base}", None),
        "proposer les tags": ("get", f"/api/tags?album={copie['album_id']}", None),
        "régler la base": ("put", f"/api/projets/{pid}/acces-membres",
                           {"acces_membres": None}),
        "décrire la base": ("patch", f"/api/collections/{base}", {"description": "x"}),
    }
    methode, chemin, corps = gestes[geste]
    avant = _sql(decor["db"], "SELECT COUNT(*) AS n FROM evenement")[0]["n"]
    for qui in (RITA, HUGO):
        r = getattr(client, methode)(chemin, headers=qui,
                                     **({"json": corps} if corps is not None else {}))
        assert r.status_code == 404, (qui, geste, r.status_code, r.text)
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM evenement")[0]["n"] == avant


def test_dans_le_sien_l_administrateur_est_un_arrivant(client, decor):
    """Son bac à sable : il en est propriétaire de la base, il y détruit tout album (la
    règle du propriétaire), il est propriétaire de la collection qu'il y crée ; mais la
    collection qu'un invité y a créée, il ne la lit pas — pas plus que lea la sienne."""
    bac = client.post("/api/bac-a-sable", headers=HUGO).json()
    pid, base = bac["id"], bac["base"]["id"]
    assert client.put(f"/api/projets/{pid}/membres", headers=HUGO,
                      json={"genre": "utilisateur", "principal": "sam",
                            "role": "membre"}).status_code == 200
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    a_sam = client.post("/api/albums", headers=SAM,
                        json={"titre": "À sam", "collection_id": chez_sam}).json()["id"]
    assert client.get(f"/api/albums/{a_sam}/planches", headers=HUGO).status_code == 404
    assert client.get(f"/api/collections/{chez_sam}/acces", headers=HUGO).status_code == 404
    niveaux = {c["id"]: c["mon_niveau"] for c in
               client.get("/api/collections", headers=HUGO).json()}
    assert niveaux[base] == "proprietaire" and chez_sam not in niveaux
    assert niveaux[decor["col"]] is None            # hors des bacs : sa portée totale
    sienne = client.post("/api/collections", headers=HUGO,
                         json={"nom": "La mienne", "projet_id": pid}).json()["id"]
    assert _sql(decor["db"], "SELECT principal, niveau FROM collection_acces "
                             "WHERE collection_id = ?", (sienne,)) == [
        {"principal": "hugo", "niveau": "proprietaire"}]
    roles = {p["id"]: p["mon_role"] for p in client.get("/api/projets", headers=HUGO).json()}
    assert roles[pid] == "responsable"
    copie = next(j for j in bac["jeu"] if j["role"] == "exemple")
    # Une copie rangée aussi chez sam (posé en base : le geste se demanderait) : pour lui
    # comme pour un arrivant, elle est « partagée » — elle vit dans une collection qu'il
    # ne lit pas.
    _sql(decor["db"], "INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
         (chez_sam, copie["album_id"]))
    vus = {a["id"]: a for a in client.get("/api/albums", headers=HUGO).json()}
    assert vus[copie["album_id"]]["partage"] is True
    assert vus[decor["reel"]]["partage"] is False
    client.post(f"/api/planches/{copie['planche_ids'][0]}/regions", headers=SAM,
                json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
    assert client.delete(f"/api/albums/{copie['album_id']}", headers=HUGO).status_code == 204


def test_l_administrateur_ne_remanie_pas_un_tag_pose_dans_le_bac_d_un_autre(client, decor):
    """Un tag GLOBAL posé (base retouchée : le geste ne se fait plus depuis l'écran) sur une
    région du bac à sable de lea : l'administrateur ne le retire pas « partout » — il
    n'écrit pas là (`routes/lexique._exiger_tout_ecrit`)."""
    region = _sql(decor["db"], "SELECT id FROM regions WHERE planche_id = ? ORDER BY id",
                  (_copie(decor, "exemple")["planche_ids"][0],))[0]["id"]
    c = sqlite3.connect(decor["db"])
    try:
        tag = c.execute("INSERT INTO tags (label) VALUES ('global-pose')").lastrowid
        an = c.execute("INSERT INTO annotations (region_id, note) VALUES (?, '')",
                       (region,)).lastrowid
        c.execute("INSERT INTO annotation_tags (annotation_id, tag_id) VALUES (?, ?)",
                  (an, tag))
        c.commit()
    finally:
        c.close()
    r = client.delete(f"/api/tags/{tag}", headers=HUGO)
    assert r.status_code == 403 and "administrateur" in r.json()["detail"], r.text
    assert _sql(decor["db"], "SELECT label FROM tags WHERE id = ?", (tag,)) == [
        {"label": "global-pose"}]


def test_invite_ailleurs_l_administrateur_est_un_invite(client, decor):
    client.put(f"/api/projets/{decor['bac']['id']}/membres", headers=LEA,
               json={"genre": "utilisateur", "principal": "hugo", "role": "membre"})
    copie = _copie(decor, "exemple")
    assert client.get(f"/api/albums/{copie['album_id']}/planches",
                      headers=HUGO).status_code == 200
    planche = copie["planche_ids"][0]
    assert client.post(f"/api/planches/{planche}/regions", headers=HUGO,
                       json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}
                       ).status_code == 201
    # Un invité ne règle rien, ne détruit pas la copie d'une autre.
    assert client.put(f"/api/projets/{decor['bac']['id']}/membres", headers=HUGO,
                      json={"genre": "utilisateur", "principal": "rita",
                            "role": "membre"}).status_code == 403
    assert client.delete(f"/api/albums/{copie['album_id']}", headers=HUGO).status_code == 403


# --------------------------------------------------------------------------- #
# Le vocabulaire et la frontière d'un bac à sable (relecture croisée)
# --------------------------------------------------------------------------- #
def _region_reelle(client, decor, type_="bulle"):
    pl = client.post(f"/api/albums/{decor['reel']}/import", headers=RESP,
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    return client.post(f"/api/planches/{pl}/regions", headers=RESP,
                       json={"type": type_, "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]


def _region_du_bac(client, decor, qui=LEA):
    planche = _copie(decor, "exemple")["planche_ids"][0]
    return client.get(f"/api/planches/{planche}/regions", headers=qui).json()[0]["id"]


def test_un_terme_ne_passe_pas_la_frontiere(client, decor):
    """resp écrit dans « Corpus » ET a son bac à sable : elle ne range pas un tag du corpus
    dans la base de son bac (qui partait avec lui, et la région du corpus le perdait), ni
    une dimension locale à « Corpus » ; et un tag né dans un bac à sable n'en sort pas —
    ni vers le global, ni vers le corpus. Entre deux collections du même bac à sable, si."""
    reg = _region_reelle(client, decor)
    client.put(f"/api/regions/{reg}/annotation", headers=RESP,
               json={"note": "n", "tags": ["colere"]})
    tag = _sql(decor["db"], "SELECT id FROM tags WHERE label = 'colere'")[0]["id"]
    bac = client.post("/api/bac-a-sable", headers=RESP).json()
    r = client.patch(f"/api/tags/{tag}/lexique", headers=RESP,
                     json={"collection_id": bac["base"]["id"]})
    assert r.status_code == 409 and "frontière" in r.json()["detail"], r.text
    d = client.post("/api/attributs/dimensions", headers=RESP,
                    json={"cible": "case", "nom": "cadrage"}).json()
    assert client.patch(f"/api/attributs/dimensions/{d['id']}/lexique", headers=RESP,
                        json={"collection_id": decor["col"]}).status_code == 200
    r = client.patch(f"/api/attributs/dimensions/{d['id']}/lexique", headers=RESP,
                     json={"collection_id": bac["base"]["id"]})
    assert r.status_code == 409 and "frontière" in r.json()["detail"], r.text
    # Un tag né dans le bac de resp n'en sort pas.
    planche = next(j for j in bac["jeu"] if j["role"] == "exemple")["planche_ids"][0]
    breg = client.get(f"/api/planches/{planche}/regions", headers=RESP).json()[0]["id"]
    client.put(f"/api/regions/{breg}/annotation", headers=RESP,
               json={"note": "", "tags": ["du-bac"]})
    du_bac = _sql(decor["db"], "SELECT id FROM tags WHERE label = 'du-bac'")[0]["id"]
    for cible in (None, decor["col"]):
        r = client.patch(f"/api/tags/{du_bac}/lexique", headers=RESP,
                         json={"collection_id": cible})
        assert r.status_code == 409 and "frontière" in r.json()["detail"], (cible, r.text)
    autre = client.post("/api/collections", headers=RESP,
                        json={"nom": "Ailleurs", "projet_id": bac["id"]}).json()["id"]
    assert client.patch(f"/api/tags/{du_bac}/lexique", headers=RESP,
                        json={"collection_id": autre}).status_code == 200
    # Ni par une fusion, dans un sens ou dans l'autre.
    r = client.post(f"/api/tags/{du_bac}/fusion", headers=RESP, json={"cible_id": tag})
    assert r.status_code == 409 and "frontière" in r.json()["detail"], r.text
    # Rien n'a bougé : la remise à neuf n'emporte que ce qui est né dans le bac à sable.
    assert client.post("/api/bac-a-sable/remise-a-neuf", headers=RESP).status_code == 200
    tags = client.get(f"/api/regions/{reg}/annotation", headers=RESP).json()["tags"]
    assert [t["label"] for t in tags] == ["colere"]
    assert _sql(decor["db"], "SELECT id FROM tags WHERE label = 'du-bac'") == []


def test_l_effacement_garde_le_vocabulaire_employe_hors_du_bac(client, decor):
    """L'état qu'aurait laissé une base retouchée : un tag et une dimension du corpus,
    rangés dans la base du bac à sable de lea et employés dans le corpus. L'effacement ne
    les emporte pas (ils deviennent globaux, leur collection partie) ; ce qui n'est employé
    que dans le bac à sable part."""
    reg, case = _region_reelle(client, decor), _region_reelle(client, decor, "case")
    client.put(f"/api/regions/{reg}/annotation", headers=RESP,
               json={"note": "", "tags": ["dehors"]})
    d = client.post("/api/attributs/dimensions", headers=RESP,
                    json={"cible": "case", "nom": "cadrage"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", headers=RESP,
                    json={"valeur": "gros plan"}).json()["id"]
    assert client.put(f"/api/regions/{case}/attributs", headers=RESP,
                      json={"valeur_id": v}).status_code in (200, 201)
    base = decor["base"]
    for q in ("UPDATE tags SET collection_id = ? WHERE label = 'dehors'",
              "UPDATE attribut_dimension SET collection_id = ? WHERE nom = 'cadrage'",
              "UPDATE attribut_valeur SET collection_id = ? WHERE valeur = 'gros plan'"):
        _sql(decor["db"], q, (base,))
    _sql(decor["db"], "INSERT INTO tags (label, collection_id) VALUES ('seul-ici', ?)",
         (base,))
    assert client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA).status_code == 200
    assert _sql(decor["db"], "SELECT collection_id FROM tags WHERE label = 'dehors'") == [
        {"collection_id": None}]
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM region_attribut WHERE region_id = ?",
                (case,)) == [{"n": 1}]
    assert _sql(decor["db"], "SELECT id FROM tags WHERE label = 'seul-ici'") == []


def test_chacun_voit_le_vocabulaire_de_ses_bacs_a_sable(client, decor):
    """Le 📖 Lexique (Hugo, 2026-10-24) : lea et son invité y lisent le tag né dans le bac
    à sable — l'administrateur et resp, non. Il se remanie comme ailleurs : par la
    propriétaire de sa collection. Ses chiffres restent ceux du vrai corpus (0 emploi)."""
    client.put(f"/api/regions/{_region_du_bac(client, decor)}/annotation", headers=LEA,
               json={"note": "", "tags": ["du-bac"]})
    for qui, voit, remanie in ((LEA, True, True), (SAM, True, False), (HUGO, False, None),
                               (RESP, False, None)):
        tags = {t["label"]: t for t in client.get("/api/lexique", headers=qui).json()["tags"]}
        assert ("du-bac" in tags) is voit, qui
        if voit:
            assert tags["du-bac"]["remaniable"] is remanie and tags["du-bac"]["frequence"] == 0
    tag = _sql(decor["db"], "SELECT id FROM tags WHERE label = 'du-bac'")[0]["id"]
    assert client.put(f"/api/tags/{tag}", headers=LEA,
                      json={"label": "renomme"}).status_code == 200
    assert client.put(f"/api/tags/{tag}", headers=SAM,
                      json={"label": "autre"}).status_code == 403


def test_une_collection_supprimee_dans_un_bac_y_garde_ses_termes(client, decor):
    """Ses termes ne deviennent pas globaux (`ON DELETE SET NULL`) : ils rejoignent la base."""
    pid = decor["bac"]["id"]
    chez_lea = client.post("/api/collections", headers=LEA,
                           json={"nom": "Chez Léa", "projet_id": pid}).json()["id"]
    _sql(decor["db"], "INSERT INTO tags (label, collection_id) VALUES ('a-moi', ?)",
         (chez_lea,))
    assert client.delete(f"/api/collections/{chez_lea}", headers=LEA).status_code == 204
    assert _sql(decor["db"], "SELECT collection_id FROM tags WHERE label = 'a-moi'") == [
        {"collection_id": decor["base"]}]


def test_on_n_importe_pas_de_vocabulaire_dans_un_bac_a_sable(client, decor):
    csv = "domaine;dimension;cible;valeur\nemotions;humeur;case;joie\n".encode("utf-8")
    r = client.post("/api/lexique/importer", headers=LEA,
                    data={"collection_id": str(decor["base"])},
                    files={"file": ("v.csv", csv, "text/csv")})
    assert r.status_code == 409 and "bac à sable" in r.json()["detail"], r.text
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM domaine") == [{"n": 0}]


def test_une_valeur_d_un_bac_ne_se_pose_pas_dans_le_corpus(client, decor):
    """Posée en base (une valeur locale au bac à sable, sous une dimension du corpus) : elle
    ne se pose pas sur une case du corpus, ni sous un domaine de l'autre rive."""
    case = _region_reelle(client, decor, "case")
    d = client.post("/api/attributs/dimensions", headers=RESP,
                    json={"cible": "case", "nom": "cadrage"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", headers=RESP,
                    json={"valeur": "gros plan"}).json()["id"]
    _sql(decor["db"], "UPDATE attribut_valeur SET collection_id = ? WHERE id = ?",
         (decor["base"], v))
    client.put(f"/api/projets/{decor['bac']['id']}/membres", headers=LEA,
               json={"genre": "utilisateur", "principal": "resp", "role": "membre"})
    r = client.put(f"/api/regions/{case}/attributs", headers=RESP, json={"valeur_id": v})
    assert r.status_code == 409 and "frontière" in r.json()["detail"], r.text
    # Ni fondue dans une valeur du corpus, de la même dimension.
    w = client.post(f"/api/attributs/dimensions/{d}/valeurs", headers=RESP,
                    json={"valeur": "plan large"}).json()["id"]
    r = client.post(f"/api/attributs/valeurs/{v}/fusion", headers=RESP, json={"cible_id": w})
    assert r.status_code == 409 and "frontière" in r.json()["detail"], r.text
    dom = client.post("/api/domaines", headers=RESP, json={"nom": "regard"}).json()["id"]
    _sql(decor["db"], "UPDATE domaine SET collection_id = ? WHERE id = ?", (decor["base"], dom))
    r = client.patch(f"/api/attributs/dimensions/{d}/domaine", headers=RESP,
                     json={"domaine_id": dom})
    assert r.status_code == 409 and "frontière" in r.json()["detail"], r.text


def _tags_de(db, label):
    return _sql(db, "SELECT id, espace, collection_id FROM tags WHERE label = ? ORDER BY id",
                (label,))


def test_les_libelles_d_un_bac_a_sable_sont_a_part(client, decor):
    """Hugo, 2026-10-24 : un libellé né dans un bac à sable ne bloque rien ailleurs ; le
    vrai corpus peut avoir le même, et rien ne se voit d'un côté à l'autre (relecture
    croisée : resp posait « peur » sur le corpus et recevait 200 avec `tags: []`)."""
    bac_region = _region_du_bac(client, decor)
    r = client.put(f"/api/regions/{bac_region}/annotation", headers=LEA,
                   json={"note": "", "tags": ["peur"]})
    assert [t["label"] for t in r.json()["tags"]] == ["peur"]
    reg = _region_reelle(client, decor)
    r = client.put(f"/api/regions/{reg}/annotation", headers=RESP,
                   json={"note": "", "tags": ["peur"]})
    assert r.status_code == 200 and [t["label"] for t in r.json()["tags"]] == ["peur"], r.text
    assert [t["espace"] for t in _tags_de(decor["db"], "peur")] == [decor["bac"]["id"], 0]
    # Dans l'autre sens : un libellé du corpus ne se pose pas dans le bac à sable — le bac
    # à sable a le sien.
    client.put(f"/api/regions/{reg}/annotation", headers=RESP,
               json={"note": "", "tags": ["peur", "colere"]})
    r = client.put(f"/api/regions/{bac_region}/annotation", headers=LEA,
                   json={"note": "", "tags": ["peur", "colere"]})
    bac_ids = {t["id"] for t in r.json()["tags"]}
    assert bac_ids == {t["id"] for t in _sql(decor["db"], "SELECT id FROM tags WHERE "
                                                          "espace = ?", (decor["bac"]["id"],))}
    # Rien ne se voit d'un côté à l'autre : ni ce que l'Atelier propose, ni le nuage.
    album_bac = _copie(decor, "exemple")["album_id"]
    proposes = client.get("/api/tags", headers=LEA, params={"album": album_bac}).json()
    assert {t["id"] for t in proposes} == bac_ids
    # Le vocabulaire de l'instance se crée sans rien voir du bac à sable.
    r = client.post("/api/tags", headers=RESP, json={"label": "peur", "description": "d"})
    assert r.status_code == 201 and r.json()["espace"] == 0, r.text
    client.put(f"/api/projets/{decor['bac']['id']}/membres", headers=LEA,
               json={"genre": "utilisateur", "principal": "resp", "role": "membre"})
    corpus = {t["id"] for t in client.get("/api/tags", headers=RESP,
                                          params={"album": decor["reel"]}).json()}
    assert not corpus & bac_ids
    assert not {t["id"] for t in client.get("/api/tags", headers=RESP).json()} & bac_ids


def test_dans_un_bac_un_libelle_pris_se_refuse_par_son_nom(client, decor):
    """Pris dans CE bac à sable par une collection qu'on ne lit pas : un refus nommé, et non
    un 200 qui ne pose rien (Hugo, 2026-10-24)."""
    pid = decor["bac"]["id"]
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    _sql(decor["db"], "INSERT INTO tags (label, collection_id, espace) VALUES "
                      "('secret', ?, ?)", (chez_sam, pid))
    r = client.put(f"/api/regions/{_region_du_bac(client, decor)}/annotation", headers=LEA,
                   json={"note": "", "tags": ["secret"]})
    assert r.status_code == 409 and "déjà pris dans ce bac à sable" in r.json()["detail"], \
        r.text


def test_un_tag_se_renomme_dans_son_espace(client, decor):
    """L'unicité vaut dans l'espace : un tag du bac à sable prend un libellé du corpus, pas
    celui d'un autre tag du même bac à sable."""
    client.put(f"/api/regions/{_region_reelle(client, decor)}/annotation", headers=RESP,
               json={"note": "", "tags": ["corpus"]})
    client.put(f"/api/regions/{_region_du_bac(client, decor)}/annotation", headers=LEA,
               json={"note": "", "tags": ["un", "deux"]})
    un = next(t["id"] for t in _tags_de(decor["db"], "un"))
    assert client.put(f"/api/tags/{un}", headers=LEA, json={"label": "corpus"}).status_code \
        == 200
    r = client.put(f"/api/tags/{un}", headers=LEA, json={"label": "deux"})
    assert r.status_code == 409 and "fusion" in r.json()["detail"], r.text


def test_un_tag_du_bac_employe_dehors_rejoint_l_instance(client, decor):
    """L'état d'une base retouchée : le « peur » du bac à sable posé sur une région du
    corpus. L'effacement ne l'emporte pas : il se fond dans le « peur » de l'instance."""
    client.put(f"/api/regions/{_region_du_bac(client, decor)}/annotation", headers=LEA,
               json={"note": "", "tags": ["peur"]})
    r1, r2 = _region_reelle(client, decor), _region_reelle(client, decor)
    client.put(f"/api/regions/{r1}/annotation", headers=RESP,
               json={"note": "", "tags": ["peur"]})
    client.put(f"/api/regions/{r2}/annotation", headers=RESP, json={"note": "x", "tags": []})
    du_bac, de_l_instance = (t["id"] for t in _tags_de(decor["db"], "peur"))
    _sql(decor["db"], "INSERT INTO annotation_tags (annotation_id, tag_id) SELECT id, ? "
                      "FROM annotations WHERE region_id = ?", (du_bac, r2))
    assert client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA).status_code == 200
    assert _tags_de(decor["db"], "peur") == [
        {"id": de_l_instance, "espace": 0, "collection_id": None}]
    tags = client.get(f"/api/regions/{r2}/annotation", headers=RESP).json()["tags"]
    assert [t["id"] for t in tags] == [de_l_instance]


def test_ctrl_z_rend_le_tag_de_son_espace(client, decor):
    """L'annulation retrouve un libellé DANS l'espace de la région (`undo._tag_a_rendre`) :
    le « mot » du bac à sable, pas celui du corpus, plus ancien."""
    client.put(f"/api/regions/{_region_reelle(client, decor)}/annotation", headers=RESP,
               json={"note": "", "tags": ["mot"]})
    region = _region_du_bac(client, decor)
    client.put(f"/api/regions/{region}/annotation", headers=LEA,
               json={"note": "n", "tags": ["mot"]})
    du_bac = next(t["id"] for t in _tags_de(decor["db"], "mot") if t["espace"])
    client.put(f"/api/regions/{region}/annotation", headers=LEA, json={"note": "n", "tags": []})
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 200, r.text
    tags = client.get(f"/api/regions/{region}/annotation", headers=LEA).json()["tags"]
    assert [t["id"] for t in tags] == [du_bac]


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
    # L'invité ne règle rien ; l'administrateur non plus : le bac à sable d'un autre lui est
    # introuvable (Hugo, 2026-10-24 : « rien, comme un non-membre »).
    assert poser(SAM).status_code == 403
    # La liste de l'Administration le lui montre, sans rien lui en ouvrir.
    vue = {p["id"]: p for p in client.get("/api/projets?bacs_a_sable=1", headers=HUGO).json()}
    assert vue[pid]["gerable"] is False and "justification" not in vue[pid]
    assert vue[pid]["nb_collections"] == 0 and vue[pid]["mon_role"] is None
    assert poser(HUGO).status_code == 404
    assert client.put(f"/api/projets/{pid}/acces-membres", headers=HUGO,
                      json={"acces_membres": None}).status_code == 404
    # Le propriétaire ne se retire pas ; l'invité, si, par le propriétaire.
    r = client.delete(f"/api/projets/{pid}/membres/utilisateur/lea", headers=LEA)
    assert r.status_code == 409 and "propriétaire de ce bac" in r.json()["detail"], r.text
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/sam",
                         headers=HUGO).status_code == 404
    assert client.delete(f"/api/projets/{pid}/membres/utilisateur/sam",
                         headers=LEA).status_code == 204
    assert poser(LEA).status_code == 200


def test_l_invite_travaille_dans_le_jeu(client, decor):
    planche = _copie(decor, "exemple")["planche_ids"][0]
    r = client.post(f"/api/planches/{planche}/regions", headers=SAM,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 201


def test_un_bac_a_sable_ne_se_renomme_ni_ne_se_supprime(client, decor):
    pid = client.post("/api/bac-a-sable", headers=HUGO).json()["id"]
    assert client.patch(f"/api/projets/{pid}", json={"nom": "Autre"},
                        headers=HUGO).status_code == 409
    assert client.delete(f"/api/projets/{pid}", headers=HUGO).status_code == 409
    # Celui d'un autre, l'administrateur ne le voit pas.
    assert client.delete(f"/api/projets/{decor['bac']['id']}",
                         headers=HUGO).status_code == 404


# --------------------------------------------------------------------------- #
# S3 — rien n'en sort, rien n'y entre
# --------------------------------------------------------------------------- #
def test_une_copie_du_bac_a_sable_n_est_la_source_de_rien_ailleurs(client, decor):
    """Pour la responsable qui a son bac à sable, et pour la portée totale (le sien)."""
    for qui in (RESP, HUGO):
        source = client.post("/api/bac-a-sable", headers=qui).json()["jeu"][0]
        for reponse, extra in (("zero", {}), ("amorcer", {"cran": "decoupage"})):
            r = client.post(f"/api/collections/{decor['col']}/prendre", headers=qui,
                            json={"documents": [{"document_id": source["document_id"],
                                                 "reponse": reponse,
                                                 "album_id": source["album_id"], **extra}],
                                  "motif": "x"})
            ligne = r.json()["documents"][0]
            assert ligne["etat"] == "refuse" and "cul-de-sac" in ligne["motif"], (qui, r.text)
    source = client.get("/api/bac-a-sable", headers=RESP).json()["jeu"][0]
    # Sans nommer la copie, le document du jeu n'existe pas pour un vrai projet.
    r = client.post(f"/api/collections/{decor['col']}/prendre", headers=RESP,
                    json={"documents": [{"document_id": source["document_id"],
                                         "reponse": "zero"}], "motif": "x"})
    assert r.status_code == 404
    source = client.get("/api/bac-a-sable", headers=HUGO).json()["jeu"][0]
    r = client.get(f"/api/albums/{source['album_id']}/amorcer/apercu", headers=HUGO,
                   params={"collection": decor["col"], "cran": "decoupage"})
    assert r.status_code == 409
    # Et un document qui ne vit que dans le bac à sable d'un AUTRE, l'administrateur ne le
    # nomme même pas : le refus « cul-de-sac » dirait qu'il existe.
    a = client.post("/api/albums", headers=LEA,
                    json={"titre": "À lea", "collection_id": decor["base"]}).json()["id"]
    doc = _sql(decor["db"], "SELECT document_id FROM albums WHERE id = ?",
               (a,))[0]["document_id"]
    for ligne in ({"document_id": doc, "reponse": "zero", "album_id": a},
                  {"document_id": doc, "reponse": "zero"}):
        r = client.post(f"/api/collections/{decor['col']}/prendre", headers=HUGO,
                        json={"documents": [ligne], "motif": "x"})
        assert r.status_code == 404, r.text


def test_rien_n_entre_dans_un_bac_a_sable(client, decor):
    doc = _sql(decor["db"], "SELECT document_id FROM albums WHERE id = ?",
               (decor["reel"],))[0]["document_id"]
    corps = {"documents": [{"document_id": doc, "reponse": "zero"}], "motif": "x"}
    # La propriétaire du bac à sable ne nomme pas un document du fonds…
    assert client.post(f"/api/collections/{decor['base']}/prendre", headers=LEA,
                       json=corps).status_code == 404
    # … ni la portée totale dans le sien : elle y est une arrivante, qui ne nomme que ce
    # qu'elle lit dans son bac à sable (Hugo, 2026-10-24).
    hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    r = client.post(f"/api/collections/{hugo['base']['id']}/prendre", headers=HUGO, json=corps)
    assert r.status_code == 404, r.text
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


def test_rien_ne_se_demande_dans_un_bac_a_sable(client, decor):
    """Aucune demande, d'aucun genre, ne naît d'un bac à sable (relecture croisée) — ni à un
    administrateur, ni à son propriétaire. Ce qui demanderait un consentement est refusé, et
    dit pourquoi ; ce que le propriétaire peut faire lui-même, il le fait."""
    pid = decor["bac"]["id"]
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    copie = _copie(decor, "exemple")["album_id"]
    # sam range la copie chez lui : il faudrait le consentement de lea (la base) — refusé.
    r = client.put(f"/api/albums/{copie}/collections/{chez_sam}", headers=SAM)
    assert r.status_code == 403 and "rien ne se demande" in r.json()["detail"], r.text
    # Par la prise : en partir, que lea devrait consentir, aussi.
    doc = _sql(decor["db"], "SELECT document_id FROM albums WHERE id = ?",
               (copie,))[0]["document_id"]
    r = client.post(f"/api/collections/{chez_sam}/prendre", headers=SAM,
                    json={"documents": [{"document_id": doc, "reponse": "amorcer",
                                         "album_id": copie, "cran": "decoupage"}]})
    ligne = r.json()["documents"][0]
    assert ligne["etat"] == "refuse" and "rien ne se demande" in ligne["motif"], r.text
    # lea, qui tient la base, range elle-même — sans rien demander.
    chez_lea = client.post("/api/collections", headers=LEA,
                           json={"nom": "Chez Léa", "projet_id": pid}).json()["id"]
    assert client.put(f"/api/albums/{copie}/collections/{chez_lea}",
                      headers=LEA).status_code == 201
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM demande") == [{"n": 0}]


def test_aucune_demande_ne_s_ecrit_depuis_un_bac_a_sable(client, decor):
    """Le dernier mot (`socle._deposer`), là où toute demande de prise ou de rejoindre
    s'écrit : 403 si son projet, ou celui de sa collection d'arrivée, est un bac à sable."""
    conn = database.get_connection()
    try:
        col = database.collection_row(conn, decor["base"])
        for projet in (decor["bac"]["id"], decor["etude"]):
            with pytest.raises(socle.HTTPException) as e:
                socle._deposer(conn, _portee(decor["db"], LEA), database.DEMANDE_REJOINDRE,
                               col, projet, None, [{"document_id": 1}])
            assert e.value.status_code == 403, projet
        conn.rollback()
    finally:
        conn.close()


def test_rien_ne_part_au_fonds_depuis_un_bac_a_sable(client, decor):
    """Sortir une copie de sa DERNIÈRE collection l'enverrait au fonds — d'où la prise en
    redemandait l'entrée à un administrateur (relecture croisée). Dans un bac à sable, c'est
    refusé : elle se supprime définitivement, ou part avec le bac à sable. Sortir d'une
    collection reste permis tant qu'une autre la garde."""
    copie = _copie(decor, "exemple")
    pid, base = decor["bac"]["id"], decor["base"]
    r = client.delete(f"/api/albums/{copie['album_id']}/collections/{base}", headers=LEA)
    assert r.status_code == 409 and "fonds" in r.json()["detail"], r.text
    chez_lea = client.post("/api/collections", headers=LEA,
                           json={"nom": "Chez Léa", "projet_id": pid}).json()["id"]
    assert client.put(f"/api/albums/{copie['album_id']}/collections/{chez_lea}",
                      headers=LEA).status_code == 201
    assert client.delete(f"/api/albums/{copie['album_id']}/collections/{base}",
                         headers=LEA).status_code == 204
    r = client.delete(f"/api/albums/{copie['album_id']}/collections/{chez_lea}", headers=LEA)
    assert r.status_code == 409, r.text
    # Et il n'y a rien à reprendre : la prise le dit, sans rien demander.
    r = client.post(f"/api/projets/{pid}/prendre", headers=LEA,
                    json={"documents": [{"document_id": copie["document_id"],
                                         "reponse": "reprendre",
                                         "album_id": copie["album_id"]}]})
    ligne = r.json()["documents"][0]
    assert ligne["etat"] == "refuse" and "rien n'est gardé" in ligne["motif"], r.text
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM demande") == [{"n": 0}]


def test_rien_n_entre_dans_un_bac_a_sable_depuis_le_fonds(client, decor):
    """Un document importé au fonds n'a jamais eu de projet : il entre où l'on veut —
    sauf dans un bac à sable, pour toute portée (relecture croisée : une portée totale le
    rangeait dans le bac de lea ; et dans le sien, elle est une arrivante)."""
    a = client.post("/api/albums", headers=HUGO, json={"titre": "Au fonds", "au_fonds": True})
    assert a.status_code == 201, a.text
    a = a.json()["id"]
    bac_hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    r = client.put(f"/api/albums/{a}/collections/{bac_hugo['base']['id']}", headers=HUGO)
    assert r.status_code == 409 and "traverse" in r.json()["detail"], r.text
    assert client.put(f"/api/albums/{a}/collections/{decor['base']}",
                      headers=HUGO).status_code == 404
    # La règle vit dans `database.rangement_traverse`, que l'outil lit aussi.
    conn = database.get_connection()
    try:
        assert database.rangement_traverse(conn, a, decor["base"]) is True
        assert database.rangement_traverse(conn, a, decor["col"]) is False
    finally:
        conn.close()
    # Ailleurs, il entre comme avant.
    assert client.put(f"/api/albums/{a}/collections/{decor['col']}",
                      headers=HUGO).status_code == 201


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
        # L'administrateur ne lit pas le bac à sable d'un autre.
        assert client.get("/api/export/csv", headers=HUGO,
                          params={"album_id": a}).status_code == 404
    # Dans le sien, c'est le document qui décide, comme pour tout arrivant.
    a_hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    serveur_h = next(j["album_id"] for j in a_hugo["jeu"] if not j["exportable"])
    assert client.get("/api/export/csv", headers=HUGO,
                      params={"album_id": serveur_h}).status_code == 403
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


def test_le_plafond_vaut_aussi_dans_une_copie_du_jeu(client, decor, monkeypatch):
    """Toute planche importée par quelqu'un compte, quel que soit l'album (Hugo,
    2026-10-24) : importer dans une copie du jeu ne contourne pas le plafond — et ce qu'on
    importe chez soi s'y ajoute."""
    monkeypatch.setattr(socle, "BAC_A_SABLE_PLAFOND_PLANCHES", 2)
    copie = _copie(decor, "exemple")["album_id"]

    def importer(album):
        return client.post(f"/api/albums/{album}/import", headers=LEA,
                           files={"file": ("p.png", make_png(), "image/png")})

    assert importer(copie).status_code == 201
    assert client.get("/api/bac-a-sable", headers=LEA).json()["planches_importees"] == 1
    a = client.post("/api/albums", headers=LEA,
                    json={"titre": "Import", "collection_id": decor["base"]}).json()["id"]
    assert importer(a).status_code == 201
    r = importer(copie)
    assert r.status_code == 409 and "2 planches" in r.json()["detail"], r.text
    assert importer(a).status_code == 409


def test_une_planche_importee_ne_sort_jamais(client, decor):
    """Importée dans la copie d'un document EXPORTABLE du jeu, une image n'en devient pas
    exportable : ni l'album entier, ni une figure tirée d'elle. Les images du jeu de la
    même copie, si (la contre-épreuve)."""
    copie = _copie(decor, "exemple")
    jeu_region = _sql(decor["db"], "SELECT id FROM regions WHERE planche_id = ? ORDER BY id",
                      (copie["planche_ids"][0],))[0]["id"]
    assert client.post("/api/figures", headers=LEA,
                       json={"regions": [jeu_region]}).status_code == 200
    assert client.get("/api/export/json", headers=LEA,
                      params={"album_id": copie["album_id"]}).status_code == 200
    pl = client.post(f"/api/albums/{copie['album_id']}/import", headers=LEA,
                     files={"file": ("moi.png", make_png(), "image/png")}).json()["id"]
    reg = client.post(f"/api/planches/{pl}/regions", headers=LEA,
                      json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    r = client.post("/api/figures", headers=LEA, json={"regions": [reg]})
    assert r.status_code == 403 and "importée" in r.json()["detail"], r.text
    for chemin in ("/api/export/json", "/api/export/csv", "/api/export/tei"):
        r = client.get(chemin, headers=LEA, params={"album_id": copie["album_id"]})
        assert r.status_code == 403 and "importée" in r.json()["detail"], (chemin, r.text)
    # Une figure tirée d'une image du jeu, dans la même copie, sort toujours.
    assert client.post("/api/figures", headers=LEA,
                       json={"regions": [jeu_region]}).status_code == 200


def test_sharedocs_dans_un_bac_a_sable_sous_son_propre_compte(client, decor):
    a = client.post("/api/albums", headers=LEA,
                    json={"titre": "Import", "collection_id": decor["base"]}).json()["id"]
    for compte in (None, "instance"):
        r = client.post("/api/sharedocs/importer", headers=LEA,
                        json={"album_id": a, "chemins": ["x/p.png"], "compte": compte})
        assert r.status_code == 403 and "propre compte" in r.json()["detail"], r.text
