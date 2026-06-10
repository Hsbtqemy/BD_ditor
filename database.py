"""Initialisation SQLite, schéma, migrations et helpers de recherche.

La base est volontairement simple : un seul fichier SQLite, FTS5 pour la
recherche plein texte. La table FTS `recherche` est dénormalisée (elle agrège
le texte OCR, la note d'annotation et les tags) ; elle est maintenue
explicitement via `reindex_region()` / `unindex_region()` appelés depuis l'API,
plutôt que par des triggers (la relation N-N tags rend les triggers fragiles).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import DB_PATH

# Version du schéma — incrémenter et ajouter une étape dans `_migrate()` à
# chaque changement structurel.
SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Connexion
# --------------------------------------------------------------------------- #
def get_connection() -> sqlite3.Connection:
    """Ouvre une connexion configurée (Row factory, clés étrangères, WAL)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Context manager : commit en sortie normale, rollback sur exception."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Schéma
# --------------------------------------------------------------------------- #
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS albums (
    id           INTEGER PRIMARY KEY,
    titre        TEXT NOT NULL,
    auteur       TEXT,
    annee        INTEGER,
    editeur      TEXT,
    serie        TEXT,
    date_import  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS planches (
    id                 INTEGER PRIMARY KEY,
    album_id           INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    numero             INTEGER NOT NULL,
    chemin_tiff        TEXT,
    chemin_web         TEXT NOT NULL,
    largeur_px         INTEGER,
    hauteur_px         INTEGER,
    statut             TEXT DEFAULT 'importee',
    date_segmentation  TEXT
);

CREATE TABLE IF NOT EXISTS regions (
    id             INTEGER PRIMARY KEY,
    planche_id     INTEGER REFERENCES planches(id) ON DELETE CASCADE,
    parent_id      INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,
    x INTEGER, y INTEGER, w INTEGER, h INTEGER,   -- pixels MASTER
    ordre          INTEGER,
    ocr_texte      TEXT,
    source         TEXT DEFAULT 'kumiko',
    date_creation  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id             INTEGER PRIMARY KEY,
    label          TEXT UNIQUE NOT NULL,
    couleur        TEXT DEFAULT '#1a4a8a',
    description    TEXT,
    date_creation  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS annotations (
    id                 INTEGER PRIMARY KEY,
    region_id          INTEGER UNIQUE REFERENCES regions(id) ON DELETE CASCADE,
    note               TEXT,
    date_creation      TEXT DEFAULT (datetime('now')),
    date_modification  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS annotation_tags (
    annotation_id  INTEGER REFERENCES annotations(id) ON DELETE CASCADE,
    tag_id         INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_planches_album   ON planches(album_id);
CREATE INDEX IF NOT EXISTS idx_regions_planche  ON regions(planche_id);
CREATE INDEX IF NOT EXISTS idx_regions_parent   ON regions(parent_id);
CREATE INDEX IF NOT EXISTS idx_anntags_tag      ON annotation_tags(tag_id);

CREATE VIRTUAL TABLE IF NOT EXISTS recherche USING fts5(
    region_id UNINDEXED,
    ocr_texte,
    note,
    tags_concat
);
"""


def init_db() -> None:
    """Crée le schéma s'il n'existe pas et applique les migrations."""
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Point d'extension pour les futures migrations (PRAGMA user_version)."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    # current < N : appliquer les étapes manquantes ici.
    if current < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


# --------------------------------------------------------------------------- #
# Maintenance de l'index FTS5
# --------------------------------------------------------------------------- #
def _region_index_payload(conn: sqlite3.Connection, region_id: int):
    """Récupère (ocr_texte, note, tags_concat) pour une région donnée."""
    region = conn.execute(
        "SELECT ocr_texte FROM regions WHERE id = ?", (region_id,)
    ).fetchone()
    if region is None:
        return None

    annotation = conn.execute(
        "SELECT id, note FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()

    note = annotation["note"] if annotation else None
    tags_concat = ""
    if annotation:
        rows = conn.execute(
            """
            SELECT t.label
            FROM annotation_tags at
            JOIN tags t ON t.id = at.tag_id
            WHERE at.annotation_id = ?
            ORDER BY t.label
            """,
            (annotation["id"],),
        ).fetchall()
        tags_concat = " ".join(r["label"] for r in rows)

    return region["ocr_texte"] or "", note or "", tags_concat


def reindex_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Recalcule la ligne FTS d'une région (texte OCR + note + tags)."""
    payload = _region_index_payload(conn, region_id)
    conn.execute("DELETE FROM recherche WHERE region_id = ?", (region_id,))
    if payload is None:
        return
    ocr_texte, note, tags_concat = payload
    # N'indexe que s'il y a quelque chose de cherchable.
    if ocr_texte or note or tags_concat:
        conn.execute(
            "INSERT INTO recherche (region_id, ocr_texte, note, tags_concat) "
            "VALUES (?, ?, ?, ?)",
            (region_id, ocr_texte, note, tags_concat),
        )


def unindex_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Retire une région de l'index FTS (suppression de région)."""
    conn.execute("DELETE FROM recherche WHERE region_id = ?", (region_id,))


if __name__ == "__main__":
    init_db()
    print(f"Base initialisée : {DB_PATH} (schéma v{SCHEMA_VERSION})")
