"""Domaines analytiques (piste B, v20) — tests.

Vérifie le palier `domaine` qui REGROUPE les dimensions facettées (émotions, représentation…) :
schéma v20 + migration (ADD COLUMN domaine_id), CRUD domaine, rattachement dimension→domaine
(orthogonal à `cible`), promotion à la suppression (domaine_id → NULL), couche lexique SKOS
(read model groupé + % défini incluant les domaines), et propagation dans les exports.
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402
from conftest import direct_query  # noqa: E402


def _lire(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- #
# Schéma & migration
# --------------------------------------------------------------------------- #
def test_schema_v20(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='domaine'").fetchone()
    dcols = {r["name"] for r in conn.execute("PRAGMA table_info(attribut_dimension)")}
    assert "domaine_id" in dcols
    conn.close()


def test_migration_v19_vers_v20_ajoute_domaine_id(tmp_path):
    """Depuis un schéma minimal « v19 » (table `domaine` présente, `attribut_dimension` SANS
    `domaine_id`), `_migrate` pose la colonne par ALTER (gardé par présence de la table)."""
    db = tmp_path / "pre20.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"   # requis par _migrate (v1→v2)
        "CREATE TABLE domaine (id INTEGER PRIMARY KEY, nom TEXT);"
        "CREATE TABLE attribut_dimension (id INTEGER PRIMARY KEY, cible TEXT, nom TEXT);"
        "PRAGMA user_version = 19;")
    conn.commit()
    database._migrate(conn)
    dcols = {r["name"] for r in conn.execute("PRAGMA table_info(attribut_dimension)")}
    assert "domaine_id" in dcols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    conn.close()


def test_upgrade_reel_recree_les_index_de_migration(tmp_path, monkeypatch):
    """Régression : les index sur des colonnes AJOUTÉES PAR MIGRATION (collection_id — v17 ;
    domaine_id — v20) sont créés DANS `_migrate` (après l'ALTER), pas dans SCHEMA_SQL — sinon un
    upgrade RÉEL (init_db sur une base ancienne, colonne absente) planterait « no such column »
    à la création de l'index. On simule une base pré-v17 puis on rejoue init_db (v16 → v20)."""
    db = tmp_path / "vieux.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()                                        # base neuve v20
    conn = sqlite3.connect(db)                                # foreign_keys OFF par défaut → surgery OK
    for i in ("idx_dim_domaine", "idx_dim_collection", "idx_val_collection", "idx_tags_collection"):
        conn.execute(f"DROP INDEX IF EXISTS {i}")
    conn.execute("ALTER TABLE attribut_dimension DROP COLUMN domaine_id")
    conn.execute("DROP TABLE domaine")
    for t in ("attribut_dimension", "attribut_valeur", "tags"):
        conn.execute(f"ALTER TABLE {t} DROP COLUMN collection_id")
    conn.execute("PRAGMA user_version = 16")
    conn.commit()
    conn.close()
    database.init_db()                                        # upgrade v16 → v20 : ne doit PAS lever
    conn = _lire(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    idx = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"idx_dim_domaine", "idx_dim_collection", "idx_val_collection",
            "idx_tags_collection"} <= idx                     # index de migration bien (re)créés
    conn.close()


# --------------------------------------------------------------------------- #
# CRUD + rattachement
# --------------------------------------------------------------------------- #
def test_crud_domaine_et_rattachement(client, db_path):
    dom = client.post("/api/domaines", json={"nom": "Émotions"}).json()
    assert dom["etat"] == "provisoire" and dom["nom"] == "émotions"      # normalisé (minuscule)
    # dimension créée directement dans le domaine
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "valence", "domaine_id": dom["id"]}).json()
    assert dim["domaine_id"] == dom["id"]
    # une autre dimension, rattachée APRÈS coup
    dim2 = client.post("/api/attributs/dimensions",
                       json={"cible": "case", "nom": "intensité"}).json()
    assert dim2["domaine_id"] is None
    r = client.patch(f"/api/attributs/dimensions/{dim2['id']}/domaine",
                     json={"domaine_id": dom["id"]}).json()
    assert r["domaine_id"] == dom["id"]
    # le domaine compte ses 2 dimensions
    d = next(x for x in client.get("/api/domaines").json() if x["id"] == dom["id"])
    assert d["nb_dimensions"] == 2
    # détacher une dimension (domaine_id: null)
    client.patch(f"/api/attributs/dimensions/{dim2['id']}/domaine", json={"domaine_id": None})
    d = next(x for x in client.get("/api/domaines").json() if x["id"] == dom["id"])
    assert d["nb_dimensions"] == 1
    # domaine inexistant → 404
    assert client.patch(f"/api/attributs/dimensions/{dim['id']}/domaine",
                        json={"domaine_id": 9999}).status_code == 404


def test_domaine_orthogonal_a_cible(client):
    """Un domaine peut regrouper une dimension PERSONNAGE et une dimension CASE."""
    dom = client.post("/api/domaines", json={"nom": "représentation"}).json()
    client.post("/api/attributs/dimensions",
                json={"cible": "personnage", "nom": "genre", "domaine_id": dom["id"]})
    client.post("/api/attributs/dimensions",
                json={"cible": "case", "nom": "scène minorisée", "domaine_id": dom["id"]})
    cibles = {x["cible"] for x in client.get("/api/attributs/dimensions").json()
              if x["domaine"] == "représentation"}
    assert cibles == {"personnage", "case"}


def test_suppression_domaine_promeut_les_dimensions(client, db_path):
    """Supprimer un domaine ne détruit PAS ses dimensions : `domaine_id` repasse à NULL."""
    dom = client.post("/api/domaines", json={"nom": "style"}).json()
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "cadrage", "domaine_id": dom["id"]}).json()
    assert client.delete(f"/api/domaines/{dom['id']}").status_code == 204
    row = direct_query(db_path, "SELECT domaine_id FROM attribut_dimension WHERE id = ?",
                       (dim["id"],))
    assert row[0]["domaine_id"] is None                                 # dimension survit, orpheline


def test_rename_domaine(client):
    dom = client.post("/api/domaines", json={"nom": "affects"}).json()
    r = client.patch(f"/api/domaines/{dom['id']}", json={"nom": "émotions"}).json()
    assert r["nom"] == "émotions"
    client.post("/api/domaines", json={"nom": "autre"})
    # renommer vers un nom déjà pris → 409
    autre = next(x for x in client.get("/api/domaines").json() if x["nom"] == "autre")
    assert client.patch(f"/api/domaines/{autre['id']}", json={"nom": "émotions"}).status_code == 409


# --------------------------------------------------------------------------- #
# Lexique (couche SKOS)
# --------------------------------------------------------------------------- #
def test_lexique_domaine_et_pct_defini(client):
    dom = client.post("/api/domaines", json={"nom": "émotions"}).json()
    # % défini AVANT : domaine provisoire → 0 défini sur ce type
    lex = client.get("/api/lexique").json()
    assert any(d["nom"] == "émotions" and d["etat"] == "provisoire" for d in lex["domaines"])
    assert lex["resume"]["par_type"]["domaines"] == {"total": 1, "definis": 0}
    # documenter → défini
    client.patch(f"/api/domaines/{dom['id']}/lexique",
                 json={"definition": "charge affective représentée", "etat": "defini"})
    lex = client.get("/api/lexique").json()
    dd = next(d for d in lex["domaines"] if d["nom"] == "émotions")
    assert dd["etat"] == "defini" and dd["definition"].startswith("charge")
    assert lex["resume"]["par_type"]["domaines"] == {"total": 1, "definis": 1}


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def test_export_porte_les_domaines(client, db_path):
    dom = client.post("/api/domaines", json={"nom": "émotions"}).json()
    client.patch(f"/api/domaines/{dom['id']}/lexique", json={"definition": "affects", "etat": "defini"})
    client.post("/api/attributs/dimensions",
                json={"cible": "case", "nom": "valence", "domaine_id": dom["id"]})
    import metadonnees_collection as mc
    import description_collection as dc
    conn = _lire(db_path)

    doc = mc.collecter(conn)["metadonnees_collection"]
    assert {"nom": "émotions", "definition": "affects", "note_portee": None,
            "etat": "defini", "collection_id": None} in doc["domaines"]
    dim = next(v for v in doc["vocabulaire"] if v["nom"] == "valence")
    assert dim["domaine"] == "émotions"                                 # rattachement dans le record

    cols, rows = mc.tables(conn)["domaines"]
    assert cols[0] == "nom" and len(rows) == 1
    voc_cols, _ = mc.tables(conn)["vocabulaire"]
    assert "domaine" in voc_cols                                        # colonne ajoutée

    fiche = dc.collecter(conn)[0]["description_collection"]["vocabulaire"]
    conn.close()
    assert {"nom": "émotions", "nb_dimensions": 1} in fiche["domaines"]
    assert fiche["lexique"]["par_type"]["domaines"]["definis"] == 1
