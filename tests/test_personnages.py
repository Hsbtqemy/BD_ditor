"""ANN-2 (lot mince) — schéma personnages / locuteur / attributs facettés.

Teste la STRUCTURE et les contraintes (cascade, canonicité des valeurs) ; l'API et
l'UI viennent dans les incréments suivants. Cf. docs/personnages-et-attribution.md §13.
"""
import sqlite3

import database
from conftest import direct_query


def test_schema_version_14(data_dir, db_path):
    assert database.SCHEMA_VERSION == 14
    assert direct_query(db_path, "PRAGMA user_version")[0]["user_version"] == 14


def test_tables_ann2_existent(data_dir):
    with database.connect() as conn:
        noms = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"personnages", "bulle_locuteur", "personnage_presence", "attribut_dimension",
            "attribut_valeur", "personnage_attribut", "region_attribut"} <= noms


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


def test_valeur_attribut_canonique(data_dir):
    """Une valeur est CANONIQUE par dimension : un doublon est rejeté (agrégabilité)."""
    with database.connect() as conn:
        d = conn.execute(
            "INSERT INTO attribut_dimension (cible, nom) VALUES ('personnage', 'origine')").lastrowid
        conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, 'rural')", (d,))
    with database.connect() as conn:
        rejete = False
        try:
            conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, 'rural')", (d,))
        except sqlite3.IntegrityError:
            rejete = True
        assert rejete


def test_affectation_attribut(region):
    """Affecter une valeur à un personnage ET à une région-case ; supprimer la valeur
    détache les affectations (CASCADE)."""
    with database.connect() as conn:
        d = conn.execute(
            "INSERT INTO attribut_dimension (cible, nom) VALUES ('case', 'formalite')").lastrowid
        v = conn.execute("INSERT INTO attribut_valeur (dimension_id, valeur) VALUES (?, 'soutenu')", (d,)).lastrowid
        p = conn.execute("INSERT INTO personnages (nom) VALUES ('X')").lastrowid
        conn.execute("INSERT INTO personnage_attribut (personnage_id, valeur_id) VALUES (?, ?)", (p, v))
        conn.execute("INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)", (region["id"], v))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM personnage_attribut").fetchone()["n"] == 1
        assert conn.execute("SELECT COUNT(*) n FROM region_attribut").fetchone()["n"] == 1
        conn.execute("DELETE FROM attribut_valeur WHERE id = ?", (v,))
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) n FROM personnage_attribut").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) n FROM region_attribut").fetchone()["n"] == 0


# --------------------------------------------------------------------------- #
# API (2a) : CRUD personnages, lien locuteur, fusion
# --------------------------------------------------------------------------- #
def test_personnage_crud(client):
    r = client.post("/api/personnages", json={"nom": "Haddock", "serie": "Tintin"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["nom"] == "Haddock"
    assert any(x["id"] == pid for x in client.get("/api/personnages").json())
    assert client.get("/api/personnages", params={"q": "Hadd"}).json()[0]["id"] == pid   # autocomplétion
    assert client.get("/api/personnages", params={"q": "zzz"}).json() == []
    client.put(f"/api/personnages/{pid}", json={"nom": "Capitaine Haddock"})
    assert client.get("/api/personnages").json()[0]["nom"] == "Capitaine Haddock"
    assert client.delete(f"/api/personnages/{pid}").status_code == 204
    assert client.get("/api/personnages").json() == []


def test_nom_vide_rejete(client):
    assert client.post("/api/personnages", json={"nom": "   "}).status_code == 422


def test_locuteur(client, region):
    rid = region["id"]
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


def test_locuteur_personnage_inconnu(client, region):
    assert client.put(f"/api/regions/{region['id']}/locuteur",
                      json={"personnage_id": 9999}).status_code == 404


def test_fusion(client, region):
    rid = region["id"]
    a = client.post("/api/personnages", json={"nom": "le capitaine"}).json()["id"]
    b = client.post("/api/personnages", json={"nom": "Capitaine Haddock"}).json()["id"]
    client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": a})
    client.post(f"/api/personnages/{a}/fusion", json={"cible_id": b})
    assert all(x["id"] != a for x in client.get("/api/personnages").json())            # doublon parti
    assert client.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]["id"] == b    # bulle réaffectée
    assert client.post(f"/api/personnages/{b}/fusion", json={"cible_id": b}).status_code == 422


# --------------------------------------------------------------------------- #
# API (2b) : dimensions / valeurs (émergentes, normalisées) / affectations
# --------------------------------------------------------------------------- #
def test_dimensions_et_valeurs(client):
    d = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "Origine"})
    assert d.status_code == 201 and d.json()["nom"] == "origine"   # normalisé (minuscules)
    did = d.json()["id"]
    # idempotent (find-or-create)
    assert client.post("/api/attributs/dimensions",
                       json={"cible": "personnage", "nom": "origine"}).json()["id"] == did
    assert client.post("/api/attributs/dimensions", json={"cible": "x", "nom": "y"}).status_code == 422
    # valeurs canoniques
    v = client.post(f"/api/attributs/dimensions/{did}/valeurs", json={"valeur": "Rural"})
    assert v.status_code == 201 and v.json()["valeur"] == "rural"
    vid = v.json()["id"]
    assert client.post(f"/api/attributs/dimensions/{did}/valeurs",
                       json={"valeur": "rural"}).json()["id"] == vid   # pas de doublon
    assert [x["id"] for x in client.get(f"/api/attributs/dimensions/{did}/valeurs").json()] == [vid]


def test_affectation_personnage(client):
    did = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    vid = client.post(f"/api/attributs/dimensions/{did}/valeurs", json={"valeur": "rural"}).json()["id"]
    pid = client.post("/api/personnages", json={"nom": "X"}).json()["id"]
    client.put(f"/api/personnages/{pid}/attributs", json={"valeur_id": vid})
    attrs = client.get(f"/api/personnages/{pid}/attributs").json()
    assert len(attrs) == 1 and attrs[0]["valeur"] == "rural" and attrs[0]["dimension"] == "origine"
    client.put(f"/api/personnages/{pid}/attributs", json={"valeur_id": vid})   # idempotent
    assert len(client.get(f"/api/personnages/{pid}/attributs").json()) == 1
    assert client.delete(f"/api/personnages/{pid}/attributs/{vid}").status_code == 204
    assert client.get(f"/api/personnages/{pid}/attributs").json() == []


def test_cible_incoherente(client, region):
    """Une valeur de dimension 'case' ne peut aller sur un personnage (et réciproquement)."""
    dc = client.post("/api/attributs/dimensions", json={"cible": "case", "nom": "formalite"}).json()["id"]
    vc = client.post(f"/api/attributs/dimensions/{dc}/valeurs", json={"valeur": "soutenu"}).json()["id"]
    pid = client.post("/api/personnages", json={"nom": "X"}).json()["id"]
    assert client.put(f"/api/personnages/{pid}/attributs", json={"valeur_id": vc}).status_code == 422
    assert client.put(f"/api/regions/{region['id']}/attributs", json={"valeur_id": vc}).status_code == 200
    assert len(client.get(f"/api/regions/{region['id']}/attributs").json()) == 1


def test_suppr_dimension_cascade(client):
    did = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    vid = client.post(f"/api/attributs/dimensions/{did}/valeurs", json={"valeur": "rural"}).json()["id"]
    pid = client.post("/api/personnages", json={"nom": "X"}).json()["id"]
    client.put(f"/api/personnages/{pid}/attributs", json={"valeur_id": vid})
    assert client.delete(f"/api/attributs/dimensions/{did}").status_code == 204
    assert client.get(f"/api/personnages/{pid}/attributs").json() == []   # affectation partie (CASCADE)


# --------------------------------------------------------------------------- #
# Revue ANN-2 : autocomplétion sans accents (#5), valeurs à plat (#3),
# renommage / fusion de valeurs (#2)
# --------------------------------------------------------------------------- #
def test_autocomplete_sans_accents(client):
    client.post("/api/personnages", json={"nom": "Étienne"})
    assert client.get("/api/personnages", params={"q": "etienne"}).json()[0]["nom"] == "Étienne"
    assert client.get("/api/personnages", params={"q": "ÉTI"}).json()[0]["nom"] == "Étienne"


def test_valeurs_a_plat(client):
    dp = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    client.post(f"/api/attributs/dimensions/{dp}/valeurs", json={"valeur": "rural"})
    dc = client.post("/api/attributs/dimensions", json={"cible": "case", "nom": "formalite"}).json()["id"]
    client.post(f"/api/attributs/dimensions/{dc}/valeurs", json={"valeur": "soutenu"})
    tout = client.get("/api/attributs/valeurs").json()
    assert {(x["dimension"], x["valeur"]) for x in tout} == {("origine", "rural"), ("formalite", "soutenu")}
    assert [x["valeur"] for x in client.get("/api/attributs/valeurs", params={"cible": "personnage"}).json()] == ["rural"]


def test_renommer_valeur(client):
    d = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "rural"}).json()["id"]
    r = client.put(f"/api/attributs/valeurs/{v}", json={"valeur": "Campagne"})
    assert r.status_code == 200 and r.json()["valeur"] == "campagne"
    client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "ville"})
    assert client.put(f"/api/attributs/valeurs/{v}", json={"valeur": "ville"}).status_code == 409   # conflit


def test_fusionner_valeur(client):
    d = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    va = client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "rural"}).json()["id"]
    vb = client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": "campagnard"}).json()["id"]
    p = client.post("/api/personnages", json={"nom": "X"}).json()["id"]
    client.put(f"/api/personnages/{p}/attributs", json={"valeur_id": va})
    client.post(f"/api/attributs/valeurs/{va}/fusion", json={"cible_id": vb})
    assert [a["valeur"] for a in client.get(f"/api/personnages/{p}/attributs").json()] == ["campagnard"]
    assert all(x["id"] != va for x in client.get(f"/api/attributs/dimensions/{d}/valeurs").json())
    d2 = client.post("/api/attributs/dimensions", json={"cible": "case", "nom": "lieu"}).json()["id"]
    vc = client.post(f"/api/attributs/dimensions/{d2}/valeurs", json={"valeur": "rue"}).json()["id"]
    assert client.post(f"/api/attributs/valeurs/{vb}/fusion", json={"cible_id": vc}).status_code == 422


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


def test_personnage_muet_profile_depuis_la_boite(client, planche):
    """§14 (a) — clé de voûte : un personnage qui ne parle JAMAIS (aucune bulle) est
    identifié sur une boîte et reçoit son profil, sans passer par une bulle."""
    rid = _boite_perso(client, planche)
    pid = client.post("/api/personnages", json={"nom": "Figurant muet"}).json()["id"]
    client.put(f"/api/regions/{rid}/personnage", json={"personnage_id": pid})
    did = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "origine"}).json()["id"]
    vid = client.post(f"/api/attributs/dimensions/{did}/valeurs", json={"valeur": "rural"}).json()["id"]
    client.put(f"/api/personnages/{pid}/attributs", json={"valeur_id": vid})
    attrs = client.get(f"/api/personnages/{pid}/attributs").json()
    assert [(a["dimension"], a["valeur"]) for a in attrs] == [("origine", "rural")]
    # muet : aucune bulle attribuée — le profil n'est PAS passé par la parole
    assert [x for x in client.get("/api/personnages").json() if x["id"] == pid][0]["nb_bulles"] == 0


def test_presence_et_locuteur_meme_entite(client, planche):
    """Le « moyeu » du §14 : une entité atteignable comme présence (boîte) ET comme
    locuteur (bulle) est la MÊME — profil partagé, parole et image agrégées."""
    boite = _boite_perso(client, planche)
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 20, "h": 20}).json()["id"]
    pid = client.post("/api/personnages", json={"nom": "Tournesol"}).json()["id"]
    client.put(f"/api/regions/{boite}/personnage", json={"personnage_id": pid})
    client.put(f"/api/regions/{bulle}/locuteur", json={"personnage_id": pid})
    assert client.get(f"/api/regions/{boite}/personnage").json()["personnage"]["id"] == pid
    assert client.get(f"/api/regions/{bulle}/locuteur").json()["locuteur"]["id"] == pid
    # profil posé une fois, partagé ; nb_bulles ne compte QUE la parole (1 bulle, 1 boîte)
    did = client.post("/api/attributs/dimensions", json={"cible": "personnage", "nom": "role"}).json()["id"]
    vid = client.post(f"/api/attributs/dimensions/{did}/valeurs", json={"valeur": "savant"}).json()["id"]
    client.put(f"/api/personnages/{pid}/attributs", json={"valeur_id": vid})
    ent = [x for x in client.get("/api/personnages").json() if x["id"] == pid][0]
    assert ent["nb_bulles"] == 1
    assert [(a["dimension"], a["valeur"]) for a in
            client.get(f"/api/personnages/{pid}/attributs").json()] == [("role", "savant")]
