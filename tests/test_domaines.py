"""Domaines analytiques (piste B, v20) — tests.

Les routes des domaines et leur panneau sont partis avec le basculement d'ANN-7 ; la
migration v39 a détruit leurs tables (`domaine`, `attribut_dimension`, `attribut_valeur`).
Ce qui reste à vérifier : une base neuve ne les porte plus, et les étapes d'hier qui les
touchaient (v17, v20, v24) tolèrent leur absence, d'une base neuve comme d'une base
ancienne qu'on migre jusqu'au bout.
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402

_VOCABULAIRE = {"domaine", "attribut_dimension", "attribut_valeur", "tags"}


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_une_base_neuve_ne_porte_plus_les_domaines(db_path):
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
        assert not _VOCABULAIRE & _tables(conn)
    finally:
        conn.close()


def test_une_base_v19_minimale_migre_jusqu_au_bout_sans_ses_domaines(tmp_path):
    """Depuis un schéma minimal « v19 » (table `domaine` présente, `attribut_dimension` SANS
    `domaine_id`), `_migrate` passe l'étape v20 (l'ALTER, l'index) puis la v39 détruit les
    tables."""
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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    assert not _VOCABULAIRE & _tables(conn)
    conn.close()


def test_une_base_neuve_rejoue_les_etapes_d_hier_sans_leurs_tables(tmp_path, monkeypatch):
    """Une base neuve rejoue toutes les étapes de `_migrate` (sa version vaut 0) : celles qui
    touchaient le vocabulaire (v17, v20, v24, v35) tolèrent son absence, et rejouées (version
    ramenée en arrière), elles ne recréent rien."""
    db = tmp_path / "neuve.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA user_version = 16")
    conn.commit()
    conn.close()
    database.init_db()
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
        assert not _VOCABULAIRE & _tables(conn)
        idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert not {"idx_dim_domaine", "idx_dim_collection", "idx_val_collection",
                    "idx_tags_collection", "idx_tags_espace_label"} & idx
    finally:
        conn.close()
