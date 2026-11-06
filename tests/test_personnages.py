"""ANN-2 (lot mince) — schéma personnages / locuteur / attributs facettés.

Teste la STRUCTURE et les contraintes (cascade, canonicité des valeurs) ; l'API et
l'UI viennent dans les incréments suivants. Cf. docs/personnages-et-attribution.md §13.
"""
import sqlite3

import pytest

import config
import database
from conftest import TYPES_MUETS, TYPES_PARLANTS, direct_query


def test_schema_version(data_dir, db_path):
    # La base migre jusqu'à la version du code (robuste aux bumps ultérieurs).
    assert direct_query(db_path, "PRAGMA user_version")[0]["user_version"] == database.SCHEMA_VERSION


def test_tables_ann2_existent(data_dir):
    with database.connect() as conn:
        noms = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"personnages", "bulle_locuteur", "personnage_presence"} <= noms
    # ANN-7, la v39 : les attributs facettés (le profil, la situation) sont partis.
    assert not {"attribut_dimension", "attribut_valeur", "personnage_attribut",
                "region_attribut"} & noms


def test_locuteur_cascade(region):
    """Supprimer un personnage détache la liaison (CASCADE) mais NE supprime PAS la région."""
    rid = region["id"]
    with database.connect() as conn:
        pid = conn.execute("INSERT INTO personnages (nom) VALUES ('Haddock')").lastrowid
        conn.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)", (rid, pid))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM bulle_locuteur").fetchone()["n"] == 1
        conn.execute("DELETE FROM personnages WHERE id = ?", (pid,))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM bulle_locuteur").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) n FROM regions WHERE id = ?", (rid,)).fetchone()["n"] == 1


def test_nom_vide_rejete(client):
    assert client.post("/api/personnages", json={"nom": "   "}).status_code == 422


def test_locuteur(client, zone_de_texte):
    """Attribuer, changer, retirer — pour une bulle, un cartouche et une zone de texte
    (ANN-6). Le compteur du registre compte les trois : il compte des prises de parole."""
    rid = zone_de_texte["id"]
    pid = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"] is None
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": pid})
    loc = client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]
    assert loc["id"] == pid and loc["nom"] == "Tintin"
    assert [x for x in client.get("/api/personnages").json() if x["id"] == pid][0]["nb_bulles"] == 1
    pid2 = client.post("/api/personnages", json={"nom": "Milou"}).json()["id"]   # upsert : changer de locuteur
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": pid2})
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]["id"] == pid2
    assert client.delete(f"/api/regions/{rid}/locuteur").status_code == 204
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"] is None


def test_locuteur_personnage_inconnu(client, zone_de_texte):
    assert client.put(f"/api/regions/{zone_de_texte['id']}/locuteur",
                      json={"personnage_id": 9999}).status_code == 404


def test_fusion(client, zone_de_texte):
    rid = zone_de_texte["id"]
    a = client.post("/api/personnages", json={"nom": "le capitaine"}).json()["id"]
    b = client.post("/api/personnages", json={"nom": "Capitaine Haddock"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": a})
    client.post(f"/api/personnages/{a}/fusion", json={"cible_id": b})
    assert all(x["id"] != a for x in client.get("/api/personnages").json())            # doublon parti
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]["id"] == b    # zone réaffectée
    assert client.post(f"/api/personnages/{b}/fusion", json={"cible_id": b}).status_code == 422


# --------------------------------------------------------------------------- #
# ANN-6 — le serveur tient la règle de l'écran : un locuteur ne se pose que sur une
# zone de texte. Il ne la tenait pas (200 sur les cinq types, mesuré le 2026-10-12).
# --------------------------------------------------------------------------- #
def _zone(client, planche, type_zone):
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": type_zone, "x": 5, "y": 5, "w": 30, "h": 30}).json()["id"]


def test_les_types_parlants_sont_ceux_qu_on_a_decides():
    """La liste, écrite à la main des deux côtés. `conftest.TYPES_PARLANTS` est l'attendu
    de tous les tests ci-dessous ; si le serveur en change, c'est une décision, et elle
    passe par ici au lieu de traverser la suite en silence."""
    assert set(config.TYPES_LOCUTEUR) == set(TYPES_PARLANTS) == {"bulle", "cartouche", "texte"}
    assert set(TYPES_PARLANTS) | set(TYPES_MUETS) == set(config.TYPES_REGION), (
        "un type de région n'est rangé ni parmi ceux qui parlent ni parmi les muets : "
        "les tests paramétrés ci-dessous ne le joueraient pas")


@pytest.mark.parametrize("type_zone", TYPES_MUETS)
def test_un_locuteur_ne_se_pose_pas_sur_une_region_muette(client, planche, db_path, type_zone):
    """422, et rien n'est écrit — ni le lien, ni son événement au journal."""
    rid = _zone(client, planche, type_zone)
    pid = client.post("/api/personnages", json={"nom": "Narrateur"}).json()["id"]
    rep = client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": pid})
    assert rep.status_code == 422, rep.text
    # Le refus se NOMME : il dit le type qu'il a trouvé et ceux qu'il attend.
    detail = rep.json()["detail"]
    assert f"« {type_zone} »" in detail
    assert all(t in detail for t in TYPES_PARLANTS)
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"] is None
    assert direct_query(db_path, "SELECT COUNT(*) n FROM bulle_locuteur")[0]["n"] == 0
    assert direct_query(db_path, "SELECT COUNT(*) n FROM evenement "
                                 "WHERE cible_table = 'bulle_locuteur'")[0]["n"] == 0
    # Le registre ne compte rien non plus.
    assert [x for x in client.get("/api/personnages").json() if x["id"] == pid][0]["nb_bulles"] == 0


def test_le_refus_de_type_precede_la_lecture_du_personnage(client, region):
    """Sur une case, un personnage inconnu répond 422 comme un personnage connu : la
    question posée est celle de la région."""
    assert client.put(f"/api/regions/{region['id']}/locuteur",
                      json={"personnage_id": 9999}).status_code == 422


def test_un_locuteur_herite_d_avant_se_lit_et_se_retire(client, planche, db_path):
    """Une base d'avant ANN-8 porte des cases qui ont gardé le locuteur de la bulle qu'elles
    étaient : le changement de type ne l'emportait pas. La garde ne porte que sur
    l'attribution — ce qui existe déjà se lit et se retire, et la route ne le repose ni ne
    le change. (Depuis ANN-8, le changement de type l'emporte — cf. `test_undo.
    test_un_locuteur_part_avec_le_type` — et l'annulation ne le repose plus : le cas ne naît
    plus, d'où le locuteur posé ici à la main, comme une base d'avant le porte.)"""
    rid = _zone(client, planche, "case")
    pid = client.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)", (rid, pid))
    c.commit()
    c.close()
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]["id"] == pid   # se lit
    autre = client.post("/api/personnages", json={"nom": "Milou"}).json()["id"]
    assert client.put(f"/api/regions/{rid}/locuteur",
                      json={"personnage_id": autre}).status_code == 422                 # ne se change pas…
    assert client.put(f"/api/regions/{rid}/locuteur",
                      json={"personnage_id": pid}).status_code == 422                   # …ni ne se repose
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]["id"] == pid
    assert client.delete(f"/api/regions/{rid}/locuteur").status_code == 204             # se retire
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"] is None


# --------------------------------------------------------------------------- #
# Revue ANN-2 : autocomplétion sans accents (#5), valeurs à plat (#3),
# renommage / fusion de valeurs (#2)
# --------------------------------------------------------------------------- #
def test_autocomplete_sans_accents(client):
    client.post("/api/personnages", json={"nom": "Étienne"})
    assert client.get("/api/personnages", params={"q": "etienne"}).json()[0]["nom"] == "Étienne"
    assert client.get("/api/personnages", params={"q": "ÉTI"}).json()[0]["nom"] == "Étienne"


# --------------------------------------------------------------------------- #
# API (a) du §14 : PRÉSENCE — la boîte personnage porte l'identité (miroir du
# locuteur, côté image). Cf. docs/personnages-et-attribution.md §14.
# --------------------------------------------------------------------------- #
def _boite_perso(client, planche):
    """Crée une région de type 'personnage' (boîte) sur la planche, renvoie son id."""
    return client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "personnage", "x": 5, "y": 5, "w": 30, "h": 60}).json()["id"]


def test_presence(client, planche):
    """Identité d'une boîte personnage : GET vide → PUT → upsert → DELETE (miroir locuteur)."""
    rid = _boite_perso(client, planche)
    pid = client.post("/api/personnages", json={"nom": "Bianca"}).json()["id"]
    assert client.get(f"/api/regions/{rid}/personnage").json()["personnage"] is None
    client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": pid})
    p = client.get(f"/api/regions/{rid}/personnage").json()["personnage"]
    assert p["id"] == pid and p["nom"] == "Bianca"
    pid2 = client.post("/api/personnages", json={"nom": "Castafiore"}).json()["id"]   # upsert
    client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": pid2})
    assert client.get(f"/api/regions/{rid}/personnage").json()["personnage"]["id"] == pid2
    assert client.delete(f"/api/regions/{rid}/personnage").status_code == 204
    assert client.get(f"/api/regions/{rid}/personnage").json()["personnage"] is None


def test_presence_personnage_inconnu(client, planche):
    rid = _boite_perso(client, planche)
    assert client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": 9999}).status_code == 404


def test_presence_region_inconnue(client):
    assert client.get("/api/regions/9999/personnage").status_code == 404
    assert client.put("/api/regions/9999/personnage", json={"personnage_id": 1}).status_code == 404


def test_presence_cascade(client, planche):
    """Supprimer le personnage détache la présence ; la région, elle, survit (CASCADE une voie)."""
    rid = _boite_perso(client, planche)
    pid = client.post("/api/personnages", json={"nom": "Nestor"}).json()["id"]
    client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": pid})
    client.delete(f"/api/personnages/{pid}")
    assert client.get(f"/api/regions/{rid}/personnage").json()["personnage"] is None
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM regions WHERE id=?", (rid,)).fetchone()["n"] == 1


def test_personnage_muet_identifie_depuis_la_boite(client, planche):
    """§14 (a) — clé de voûte : un personnage qui ne parle JAMAIS (aucune bulle) est
    identifié sur une boîte, sans passer par une bulle. (Son PROFIL s'y posait aussi : il
    est parti avec le basculement d'ANN-7, et reviendra avec la cible « entité », I2.)"""
    rid = _boite_perso(client, planche)
    pid = client.post("/api/personnages", json={"nom": "Figurant muet"}).json()["id"]
    client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": pid})
    assert client.get(f"/api/regions/{rid}/personnage").json()["personnage"]["id"] == pid
    # muet : aucune bulle attribuée
    assert [x for x in client.get("/api/personnages").json() if x["id"] == pid][0]["nb_bulles"] == 0


def test_presence_et_locuteur_meme_entite(client, planche):
    """Le « moyeu » du §14 : une entité atteignable comme présence (boîte) ET comme
    locuteur (bulle) est la MÊME — parole et image agrégées."""
    boite = _boite_perso(client, planche)
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 20, "h": 20}).json()["id"]
    pid = client.post("/api/personnages", json={"nom": "Tournesol"}).json()["id"]
    client.put(f"/api/regions/{boite}/personnage", json={"personnage_id": pid})
    client.put(f"/api/regions/{bulle}/locuteur", json={"personnage_id": pid})
    assert client.get(f"/api/regions/{boite}/personnage").json()["personnage"]["id"] == pid
    assert client.get(f"/api/regions/{bulle}/locuteur").json()["locuteur"]["id"] == pid
    # nb_bulles ne compte QUE la parole (1 bulle, 1 boîte) — toute la parole depuis ANN-6,
    # cartouches et zones de texte compris (`test_locuteur`)
    ent = [x for x in client.get("/api/personnages").json() if x["id"] == pid][0]
    assert ent["nb_bulles"] == 1
