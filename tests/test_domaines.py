"""Domaines analytiques (piste B, v20) — tests.

Vérifie le schéma v20 et sa migration (ADD COLUMN domaine_id). Les routes des domaines et
leur panneau sont partis avec le basculement d'ANN-7 ; leurs tests avec eux. Les tables
restent jusqu'à la migration qui les retire.
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
def test_schema_v20(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
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
