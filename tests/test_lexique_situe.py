"""Lexique situé SKOS (A4, niveau 7) — tests.

Vérifie le schéma v17 et sa migration. L'édition par l'API, le « % défini », la promotion et
le panneau 📖 Lexique sont partis avec le basculement d'ANN-7 (ni écran ni route) ; leurs
tests avec eux. Les tables restent jusqu'à la migration qui les retire.
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
def test_schema_lexique(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
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
