"""Le cliquet des tables d'ANNOTATION (ANN-7, tranche 1 ; cadrage R11 ; « Deux gardes qui
échouent OUVERT couvrent les relevés, et un cliquet les tient », tranché le 2026-10-22).

Une table d'annotation neuve doit être lue par des chemins qui ne la connaissent pas, et la
plupart échouent OUVERT : « qui perd quoi » (l'écran tairait, avant d'effacer, le travail des
autres — la règle « travail d'autrui » jusqu'à la tranche 3c), « repartir de zéro » (une copie remise à zéro garderait ce
travail), la re-segmentation (une case qui ne porte que lui serait supprimée). Ce cliquet les
JOUE, table par table de `database.TABLES_D_ANNOTATION`, par le comportement — une table
semée par l'API, le chemin joué, l'effet vérifié — et non par la lecture du source. Et
l'inverse : toute table du schéma qui porte un `region_id` ou un `planche_id` est dans la
liste, ou déclarée hors d'elle avec sa raison — sans quoi la prochaine table d'annotation
passerait à côté, comme la situation d'une case passait à côté de la re-segmentation.
"""
import sqlite3

import pytest

import autorisation
import database
import pipeline.segmentation as seg
from grilles_decor import LEA, STAG, grille_active, monter, ok

# Les tables qui portent une région ou une planche, et ne sont PAS de l'annotation.
HORS_ANNOTATION = {
    "demande": "Une demande d'effacement qui vise une PLANCHE (`planche_id`, v38, COL-3, "
               "tranche 3c) : une requête adressée au responsable ou à l'administrateur, pas un "
               "travail posé sur la planche ; elle survit à la planche (sans clé étrangère).",
    "regions": "La région elle-même (sa planche) : c'est la cible, pas ce qu'on pose dessus.",
    "tokens": "L'analyse automatique du texte, régénérée à chaque réindexation : aucun "
              "travail humain.",
    "token_correction": "La correction grammaticale : le cran `grammaire`, au-dessous des "
                        "annotations — lue par la règle (son `auteur`) et retirée par "
                        "« repartir de zéro » à SON cran (`tests/test_repartir.py`).",
    "region_origine": "La provenance d'une région recopiée (E2) : elle part avec la région, "
                      "et la règle « travail d'autrui » la LIT pour remonter la chaîne.",
    "recherche": "L'index plein texte, dénormalisé, maintenu par `reindex_region`.",
}


def _tables_qui_portent(conn) -> set:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE 'recherche_%'")]
    return {t for t in tables
            if {"region_id", "planche_id"} & {c[1] for c in conn.execute(
                f'PRAGMA table_info("{t}")')}}


def test_toute_table_qui_porte_une_region_ou_une_planche_est_classee(db_path):
    c = sqlite3.connect(db_path)
    try:
        portent = _tables_qui_portent(c)
    finally:
        c.close()
    classees = set(database.TABLES_D_ANNOTATION) | set(HORS_ANNOTATION)
    assert portent - classees == set(), (
        f"tables ni d'annotation ni déclarées hors : {sorted(portent - classees)}")
    # Les tables de la liste qui pendent d'un PARENT (un relevé, un doute) n'ont pas de
    # colonne de région : elles sont dans la liste pour que le cliquet les joue aussi.
    enfants = set(database.TABLES_D_ANNOTATION) - portent
    assert enfants == {"releve_mot", "releve_qualificatif", "doute", "doute_message"}, enfants
    assert not set(HORS_ANNOTATION) - portent, "une exemption vise une table qui n'existe plus"


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    d = monter(client, db_path)
    d.update(grille_active(client, d["p"]))
    perso = ok(client.post("/api/personnages", headers=LEA, json={"nom": "Zed"}), 200, 201)
    d["perso"] = perso["id"]
    dim = ok(client.post("/api/attributs/dimensions", headers=LEA,
                         json={"cible": "case", "nom": "lieu"}), 201)["id"]
    d["valeur"] = ok(client.post(f"/api/attributs/dimensions/{dim}/valeurs", headers=LEA,
                                 json={"valeur": "cuisine"}), 201)["id"]
    return d


def _poser(client, d, qui, **champs):
    r = client.post("/api/releves", headers=qui,
                    json={"grille_id": d["grille_id"], "version": 1, **champs})
    assert r.status_code == 201, r.text
    return r.json()


def semer(client, d, table, qui=STAG):
    """Pose, sous `qui`, du travail qui rend `table` non vide pour l'album du décor. Rend la
    région qui le porte (une case, quand c'en est une)."""
    z = d["zones"]
    if table == "annotations":
        ok(client.put(f"/api/regions/{z['case']}/annotation", headers=qui,
                      json={"note": "vu"}))
        return z["case"]
    if table == "region_attribut":
        ok(client.put(f"/api/regions/{z['case']}/attributs", headers=qui,
                      json={"valeur_id": d["valeur"]}))
        return z["case"]
    if table == "bulle_locuteur":
        ok(client.put(f"/api/regions/{z['bulle']}/locuteur", headers=qui,
                      json={"personnage_id": d["perso"]}))
        return z["bulle"]
    if table == "personnage_presence":
        ok(client.put(f"/api/regions/{z['personnage']}/personnage", headers=qui,
                      json={"personnage_id": d["perso"]}))
        return z["personnage"]
    if table in ("releve", "releve_mot"):
        if table == "releve":
            _poser(client, d, qui, region_id=z["case"], entree_cle="regard-camera")
            return z["case"]
        _poser(client, d, qui, region_id=z["bulle"], entree_cle="cri", mots=[8])
        return z["bulle"]
    if table == "releve_qualificatif":
        _poser(client, d, qui, region_id=z["bulle"], entree_cle="echo", mots=[1],
               qualificatifs=["objet"])
        return z["bulle"]
    if table in ("doute", "doute_message"):
        r = _poser(client, d, LEA, region_id=z["case"], entree_cle="regard-camera")
        ok(client.post(f"/api/releves/{r['id']}/doutes", headers=qui, json={"texte": "?"}),
           201)
        return z["case"]
    if table == "passe":
        ok(client.put(f"/api/regions/{z['case']}/passes/{d['grille_id']}", headers=qui,
                      json={}))
        return z["case"]
    raise AssertionError(f"le cliquet ne sait pas semer `{table}` : apprenez-le-lui")


def _compte(conn, table, album) -> int:
    regions = ("SELECT g.id FROM regions g JOIN planches p ON p.id = g.planche_id "
               "WHERE p.album_id = ?")
    if table in ("releve_mot", "releve_qualificatif", "doute"):
        return conn.execute(f"SELECT COUNT(*) FROM {table} x JOIN releve r "
                            f"ON r.id = x.releve_id WHERE r.region_id IN ({regions})",
                            (album,)).fetchone()[0]
    if table == "doute_message":
        return conn.execute(f"SELECT COUNT(*) FROM doute_message m JOIN doute x "
                            f"ON x.id = m.doute_id JOIN releve r ON r.id = x.releve_id "
                            f"WHERE r.region_id IN ({regions})", (album,)).fetchone()[0]
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE region_id IN ({regions})",
                        (album,)).fetchone()[0]


def _travail_d_un_autre(conn, d) -> bool:
    """Un autre que la créatrice (`lea`) a-t-il travaillé sur l'album, selon « qui perd
    quoi » (`autorisation.sql_actes_sur_album`) ? Jusqu'à la tranche 3c, c'était la
    quatrième moitié du chemin du créateur ; depuis (F3), la mesure ne décide plus rien et
    sert à MONTRER, avant d'effacer, qui perd quoi."""
    return bool(conn.execute(
        f"SELECT EXISTS (SELECT 1 FROM "
        f"({autorisation.sql_actes_sur_album(str(int(d['album'])))}) "
        "WHERE agent IS NULL OR agent IS NOT 'lea')").fetchone()[0])


@pytest.mark.parametrize("table", database.TABLES_D_ANNOTATION)
def test_le_travail_d_un_autre_dans_cette_table_se_lit_avant_d_effacer(client, decor, table):
    """Tranche 3c (F3) — RÉÉCRIT : le travail d'un autre dans chaque table d'annotation se
    lit sous « qui perd quoi » (il retenait la suppression directe de la créatrice)."""
    c = database.get_connection()
    try:
        # Le décor : la responsable a tout fait, personne d'autre.
        assert not _travail_d_un_autre(c, decor), "le décor laisse déjà travailler un autre"
    finally:
        c.close()
    semer(client, decor, table)
    c = database.get_connection()
    try:
        assert _compte(c, table, decor["album"]) > 0, f"`{table}` n'a pas été semée"
        assert _travail_d_un_autre(c, decor), (
            f"le travail d'un autre dans `{table}` ne se lit pas sous « qui perd quoi »")
    finally:
        c.close()


@pytest.mark.parametrize("table", database.TABLES_D_ANNOTATION)
def test_repartir_de_zero_vide_cette_table(client, decor, table):
    semer(client, decor, table)
    c = database.get_connection()
    try:
        assert _compte(c, table, decor["album"]) > 0
        database.repartir_de_zero(c, decor["album"], "grammaire")
        assert _compte(c, table, decor["album"]) == 0, (
            f"« repartir de zéro » laisse `{table}` sous une copie qu'on a voulue vide")
    finally:
        c.rollback()
        c.close()


# Les tables qui peuvent porter du travail sur une CASE — celles que la re-segmentation
# doit lire pour la garder. Le locuteur vit sur une zone de texte, la présence sur une boîte
# personnage : la segmentation ne supprime que des cases.
SUR_UNE_CASE = ("annotations", "region_attribut", "releve", "doute", "doute_message", "passe")


@pytest.mark.parametrize("table", SUR_UNE_CASE)
def test_la_resegmentation_garde_une_case_qui_porte_cette_table(client, decor, monkeypatch,
                                                                db_path, table):
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 50, 50]]})
    pl = decor["planche"]
    ok(client.post(f"/api/planches/{pl}/segmenter", headers=LEA))
    case = next(x for x in ok(client.get(f"/api/planches/{pl}/regions", headers=LEA))
                if x["type"] == "case" and x["source"] == "kumiko")
    decor["zones"] = {**decor["zones"], "case": case["id"]}
    semer(client, decor, table)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[300, 400, 50, 50]]})
    ok(client.post(f"/api/planches/{pl}/segmenter", headers=LEA))
    assert any(x["id"] == case["id"] for x in ok(client.get(f"/api/planches/{pl}/regions",
                                                            headers=LEA))), table


def test_le_cliquet_couvre_toute_la_liste():
    """Mode d'échec du cliquet : une table de la liste que `semer` ne sait pas semer lève, et
    une table sur une case doit être dans `SUR_UNE_CASE` ou vivre ailleurs que sur une case."""
    assert set(SUR_UNE_CASE) <= set(database.TABLES_D_ANNOTATION)
    assert set(database.TABLES_D_ANNOTATION) - set(SUR_UNE_CASE) == {
        "bulle_locuteur", "personnage_presence", "releve_mot", "releve_qualificatif"}
