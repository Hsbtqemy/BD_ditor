"""Lexique situé SKOS (A4, niveau 7) — tests.

Vérifie la couche définitionnelle posée sur le vocabulaire ÉMERGENT (dimensions, valeurs
ET tags) : schéma v17 + migration, édition par l'API (definition/note_portee/etat/portée),
indicateur « % défini », promotion local→global (SET NULL), et propagation dans les exports
(records SKOS + paradonnée). L'UI (panneau Lexique) est auditée à part (e2e/axe).
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402


def _lire(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- #
# Schéma & migration
# --------------------------------------------------------------------------- #
def test_schema_v17(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 17
    for t in ("attribut_dimension", "attribut_valeur"):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
        assert {"definition", "note_portee", "etat", "collection_id"} <= cols
    tcols = {r["name"] for r in conn.execute("PRAGMA table_info(tags)")}
    assert {"note_portee", "etat", "collection_id"} <= tcols   # description EST la définition


def test_migration_v16_vers_v17(tmp_path):
    """Depuis un schéma pré-v17 (vocabulaire sans couche définitionnelle, `collection`
    présente pour la FK), `_migrate` ajoute les colonnes et passe en v17."""
    db = tmp_path / "v16.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INT);"
        "CREATE TABLE regions (id INTEGER PRIMARY KEY, planche_id INT, type TEXT,"
        "  activite_id INT, touche INT, date_modification TEXT);"
        "CREATE TABLE activite (id INTEGER PRIMARY KEY);"
        "CREATE TABLE collection (id INTEGER PRIMARY KEY, nom TEXT);"
        "CREATE TABLE tags (id INTEGER PRIMARY KEY, label TEXT, description TEXT);"
        "CREATE TABLE attribut_dimension (id INTEGER PRIMARY KEY, cible TEXT, nom TEXT);"
        "CREATE TABLE attribut_valeur (id INTEGER PRIMARY KEY, dimension_id INT, valeur TEXT);"
        "PRAGMA user_version = 16;")
    database._migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    for t in ("attribut_dimension", "attribut_valeur"):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
        assert {"definition", "note_portee", "etat", "collection_id"} <= cols
    conn.close()


# --------------------------------------------------------------------------- #
# API — édition de la couche définitionnelle
# --------------------------------------------------------------------------- #
def _dim_val_tag(client, db_path):
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "registre"}).json()
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": "argot"}).json()
    conn = _lire(db_path)
    conn.execute("INSERT INTO tags (label, description) VALUES ('colere', 'glose')")
    conn.commit()
    tag_id = conn.execute("SELECT id FROM tags WHERE label='colere'").fetchone()["id"]
    conn.close()
    return dim, val, tag_id


def test_documenter_dimension_valeur_tag(client, db_path):
    dim, val, tag_id = _dim_val_tag(client, db_path)
    r = client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                     json={"definition": "niveau de langue", "note_portee": "oral",
                           "etat": "defini"})
    assert r.status_code == 200 and r.json()["definition"] == "niveau de langue"
    assert r.json()["etat"] == "defini" and r.json()["note_portee"] == "oral"
    client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                 json={"definition": "familier"})
    # Tag : la définition va dans `description` (sa glose EST la definition SKOS).
    rt = client.patch(f"/api/tags/{tag_id}/lexique",
                      json={"definition": "émotion", "etat": "defini"})
    assert rt.status_code == 200 and rt.json()["description"] == "émotion"

    lex = client.get("/api/lexique").json()
    assert lex["resume"]["definis"] == 2 and lex["resume"]["total"] == 3    # dim + tag définis
    assert lex["resume"]["pct_defini"] == round(2 / 3, 4)
    d0 = lex["dimensions"][0]
    assert d0["definition"] == "niveau de langue" and d0["valeurs"][0]["definition"] == "familier"


def test_etat_et_collection_valides(client, db_path):
    dim, val, tag_id = _dim_val_tag(client, db_path)
    assert client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                        json={"etat": "n'importe quoi"}).status_code == 422
    assert client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                        json={"collection_id": 99999}).status_code == 404


def test_portee_promotion_globale(client, db_path):
    """`collection_id` = portée d'appartenance ; supprimer la collection PROMEUT le terme en
    global (ON DELETE SET NULL), au lieu de perdre le vocabulaire (patron mentions→entités)."""
    dim, val, tag_id = _dim_val_tag(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('Étude X')")
    cid = conn.execute("SELECT id FROM collection WHERE nom='Étude X'").fetchone()["id"]
    conn.commit()
    conn.close()
    r = client.patch(f"/api/attributs/valeurs/{val['id']}/lexique", json={"collection_id": cid})
    assert r.json()["collection_id"] == cid
    # suppression de la collection → portée NULL (global), la valeur survit
    conn = _lire(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("DELETE FROM collection WHERE id = ?", (cid,))
    conn.commit()
    got = conn.execute("SELECT collection_id FROM attribut_valeur WHERE id = ?",
                       (val["id"],)).fetchone()
    conn.close()
    assert got["collection_id"] is None


def test_pct_defini_scope_collection(client, db_path):
    """L'indicateur % défini est scopable par APPARTENANCE (global ⊕ local à la collection)."""
    dim, val, tag_id = _dim_val_tag(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('C')")
    cid = conn.execute("SELECT id FROM collection WHERE nom='C'").fetchone()["id"]
    conn.commit()
    conn.close()
    # un terme local défini + les globaux non définis
    client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                 json={"collection_id": cid, "etat": "defini"})
    conn = _lire(db_path)
    glob = database.lexique_resume(conn)
    scoped = database.lexique_resume(conn, cid)
    conn.close()
    assert glob["total"] == 3                      # dim + val + tag
    assert scoped["total"] == 3 and scoped["definis"] == 1   # global (val,tag) ⊕ local défini (dim)


# --------------------------------------------------------------------------- #
# Export — colonnes SKOS + % défini
# --------------------------------------------------------------------------- #
def test_export_porte_le_lexique(client, db_path):
    dim, val, tag_id = _dim_val_tag(client, db_path)
    client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                 json={"definition": "niveau", "note_portee": "oral", "etat": "defini"})
    import metadonnees_collection as mc
    conn = _lire(db_path)
    doc = mc.collecter(conn)["metadonnees_collection"]
    v0 = doc["vocabulaire"][0]
    assert v0["definition"] == "niveau" and v0["note_portee"] == "oral" and v0["etat"] == "defini"
    assert "definition" in v0["valeurs"][0]                     # SKOS aussi au niveau valeur
    assert doc["paradonnee"]["lexique"]["definis"] == 1
    cols = mc.tables(conn)["vocabulaire"][0]
    conn.close()
    assert {"definition", "note_portee", "etat", "collection_id",
            "dim_definition", "dim_etat"} <= set(cols)
