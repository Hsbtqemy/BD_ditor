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
SCHEMA_VERSION = 9


# --------------------------------------------------------------------------- #
# Connexion
# --------------------------------------------------------------------------- #
def get_connection() -> sqlite3.Connection:
    """Ouvre une connexion configurée (Row factory, clés étrangères, WAL)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")   # job de fond + requêtes : écritures concurrentes
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
    description  TEXT,
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
    date_segmentation  TEXT,
    validee            TEXT,          -- horodatage de validation humaine (NULL = non validée)
    verrouillee        TEXT           -- horodatage de verrou (NULL = déverrouillée) : protège des passes ML auto
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

-- Analyse grammaticale (Palier B) : un mot du texte OCR d'une région, avec son
-- lemme, sa catégorie (POS) et ses traits morphologiques. Recalculé par spaCy à
-- chaque (ré)indexation. CASCADE → supprimé avec la région.
CREATE TABLE IF NOT EXISTS tokens (
    id          INTEGER PRIMARY KEY,
    region_id   INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    ordre       INTEGER,
    texte       TEXT,
    lemme       TEXT,
    pos         TEXT,
    morph       TEXT
);

-- Correction HUMAINE de l'étiquetage grammatical (cf. docs/correction-grammaticale.md).
-- Couche OVERLAY préservée : le reindex régénère `tokens` (auto) mais NE TOUCHE JAMAIS
-- cette table. `forme` = forme de surface visée (ancrage anti-dérive) ; `obsolete=1` =
-- le texte a changé → correction à revérifier (non appliquée). Champ NULL = auto accepté.
CREATE TABLE IF NOT EXISTS token_correction (
    id          INTEGER PRIMARY KEY,
    region_id   INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL,
    forme       TEXT NOT NULL,
    lemme       TEXT,
    pos         TEXT,
    morph       TEXT,
    etat        TEXT NOT NULL DEFAULT 'corrige',   -- 'corrige' | 'valide'
    auteur      TEXT,
    date_modif  TEXT DEFAULT (datetime('now')),
    obsolete    INTEGER NOT NULL DEFAULT 0,
    UNIQUE(region_id, ordre)
);

-- Vue de LECTURE : valeur effective (correction vivante ⊕ auto) + provenance unifiée.
-- Toutes les surfaces d'analyse lisent CECI, jamais `tokens` brut (invariant projet).
CREATE VIEW IF NOT EXISTS tokens_effectifs AS
SELECT t.region_id, t.ordre, t.texte,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.lemme END, t.lemme) AS lemme,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.pos   END, t.pos)   AS pos,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.morph END, t.morph) AS morph,
       CASE WHEN c.id IS NULL OR c.obsolete = 1 THEN 'auto'
            ELSE c.etat END                                          AS provenance
FROM tokens t
LEFT JOIN token_correction c
       ON c.region_id = t.region_id AND c.ordre = t.ordre;

-- Métadonnées clé/valeur (documentation/reproductibilité) : p.ex. quel modèle NLP
-- a produit l'index linguistique, et quand. Utile quand le corpus devient citable.
CREATE TABLE IF NOT EXISTS meta (
    cle      TEXT PRIMARY KEY,
    valeur   TEXT
);

CREATE INDEX IF NOT EXISTS idx_planches_album   ON planches(album_id);
CREATE INDEX IF NOT EXISTS idx_regions_planche  ON regions(planche_id);
CREATE INDEX IF NOT EXISTS idx_regions_parent   ON regions(parent_id);
CREATE INDEX IF NOT EXISTS idx_anntags_tag      ON annotation_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_tokens_region    ON tokens(region_id);
CREATE INDEX IF NOT EXISTS idx_tokens_lemme     ON tokens(lemme);
CREATE INDEX IF NOT EXISTS idx_tokens_pos       ON tokens(pos);
CREATE INDEX IF NOT EXISTS idx_tcorr_region     ON token_correction(region_id);
CREATE INDEX IF NOT EXISTS idx_tcorr_etat       ON token_correction(etat);
"""

# Index plein texte FTS5 — séparé du schéma pour pouvoir le RECRÉER en migration
# (le tokenizer est figé à la création de la table). `remove_diacritics 2` rend
# la recherche insensible aux accents (« eloignez » trouve « éloignez »).
_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS recherche USING fts5(
    region_id UNINDEXED,
    ocr_texte,
    note,
    tags_concat,
    lemmes,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def init_db() -> None:
    """Crée le schéma s'il n'existe pas et applique les migrations."""
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Migrations idempotentes (sûres sur base neuve comme existante)."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(albums)")}
    if "description" not in cols:                       # v1 → v2
        conn.execute("ALTER TABLE albums ADD COLUMN description TEXT")

    # FTS recréée si schéma < 5 (la structure FTS ne se modifie pas en place) :
    # v3 a introduit le tokenizer sans accents, v5 la colonne `lemmes`. Le
    # repeuplement est STRUCTUREL (ocr/note/tags, SANS spaCy) → démarrage instantané
    # et recherche jamais cassée (repli préfixe+accents). L'enrichissement NLP
    # (lemmes + tokens) est fait à part, à la demande, par `reindex_all()`.
    if version < 5:
        conn.execute("DROP TABLE IF EXISTS recherche")
        conn.executescript(_FTS_SQL)
        has_regions = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='regions'"
        ).fetchone()
        if has_regions:
            for r in conn.execute("SELECT id FROM regions").fetchall():
                _index_region(conn, r["id"],
                              _region_index_payload(conn, r["id"]), "", [])

    # v3 → v4 : validation humaine d'une planche (drapeau orthogonal au statut).
    pcols = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    if pcols and "validee" not in pcols:
        conn.execute("ALTER TABLE planches ADD COLUMN validee TEXT")

    # v7 → v8 : verrou de planche (protège des passes automatiques en lot ; cf.
    # docs/correction-grammaticale.md §6). Distinct de `validee`.
    if pcols and "verrouillee" not in pcols:
        conn.execute("ALTER TABLE planches ADD COLUMN verrouillee TEXT")

    # v8 → v9 : couche de correction grammaticale humaine (table token_correction +
    # vue tokens_effectifs) — créées par SCHEMA_SQL (CREATE … IF NOT EXISTS), donc
    # rien à faire ici sinon acter la version. Cf. docs/correction-grammaticale.md.
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


def _index_region(conn: sqlite3.Connection, region_id: int, payload,
                  lemmes: str, tokens: list) -> None:
    """Persistance partagée : écrit la ligne FTS (ocr/note/tags + `lemmes` fournis)
    et les `tokens` fournis. `lemmes=""` / `tokens=[]` ⇒ indexation STRUCTURELLE
    (sans NLP). Utilisé par `reindex_region` (unitaire), `reindex_all` (lot) et la
    migration (structurelle)."""
    conn.execute("DELETE FROM recherche WHERE region_id = ?", (region_id,))
    conn.execute("DELETE FROM tokens WHERE region_id = ?", (region_id,))
    if payload is None:
        return
    ocr_texte, note, tags_concat = payload
    if ocr_texte or note or tags_concat or lemmes:
        conn.execute(
            "INSERT INTO recherche (region_id, ocr_texte, note, tags_concat, lemmes) "
            "VALUES (?, ?, ?, ?, ?)",
            (region_id, ocr_texte, note, tags_concat, lemmes),
        )
    if tokens:
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(region_id, t["ordre"], t["texte"], t["lemme"], t["pos"], t["morph"])
             for t in tokens],
        )


def _appliquer_corrections(conn: sqlite3.Connection, region_id: int,
                           tokens: list, lemmes: str, reancrer: bool = True) -> str:
    """Couche de correction HUMAINE (cf. docs/correction-grammaticale.md §4-5). Après
    régénération des tokens auto, re-ancre les corrections de la région contre eux :
    `obsolete=1` si le mot à cette position a changé/disparu (texte édité). NE supprime
    ni ne modifie JAMAIS les valeurs humaines. Renvoie les lemmes FTS ENRICHIS des
    lemmes corrigés VIVANTS (→ la recherche reflète les corrections).

    `reancrer=False` quand la tokenisation auto n'est PAS fiable (moteur spaCy absent
    ou analyse échouée sur un texte non vide) : on ne recalcule alors PAS `obsolete`,
    pour ne jamais invalider une correction sur la seule absence du moteur. L'ajout
    des lemmes corrigés au FTS, lui, est toujours effectué (corrections cherchables
    même sans spaCy). Sans correction : `lemmes` inchangé (coût ≈ nul, cas courant)."""
    corr = conn.execute(
        "SELECT ordre, forme FROM token_correction WHERE region_id = ?",
        (region_id,)).fetchall()
    if not corr:
        return lemmes
    if reancrer:
        formes = {t["ordre"]: t["texte"] for t in tokens}   # tokens auto à jour
        for c in corr:
            vivante = formes.get(c["ordre"]) == c["forme"]
            conn.execute("UPDATE token_correction SET obsolete = ? "
                         "WHERE region_id = ? AND ordre = ?",
                         (0 if vivante else 1, region_id, c["ordre"]))
    # FTS : ajoute les lemmes corrigés VIVANTS (état `obsolete` courant) → cherchables
    extra = [r["lemme"] for r in conn.execute(
        "SELECT lemme FROM token_correction "
        "WHERE region_id = ? AND obsolete = 0 AND lemme IS NOT NULL AND lemme <> ''",
        (region_id,))]
    vus = set(lemmes.split())
    for l in extra:
        if l not in vus:
            vus.add(l)
            lemmes = (lemmes + " " + l).strip()
    return lemmes


def reindex_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Indexe une région AVEC enrichissement NLP (lemmes + tokens), à l'édition.
    Tokens = analyse du DIALOGUE (texte OCR) ; lemmes = OCR + note. Moteur optionnel :
    sans spaCy, lemmes vides + aucun token → repli propre (préfixe+accents).
    Les corrections humaines sont préservées et re-ancrées (cf. `_appliquer_corrections`)."""
    payload = _region_index_payload(conn, region_id)
    lemmes, tokens = "", []
    if payload and (payload[0] or payload[1]):
        from pipeline.nlp import analyse, lemmatise   # import paresseux (évite tout cycle)
        lemmes_ocr, tokens = analyse(payload[0])
        lemmes = (lemmes_ocr + " " + lemmatise(payload[1])).strip()
    # Re-ancrage fiable seulement si l'auto a été (re)calculé : des tokens, ou un texte
    # vraiment vide. Texte non vide + 0 token = analyse indispo → on préserve l'humain.
    ocr = payload[0] if payload else ""
    fiable = bool(tokens) or not (ocr or "").strip()
    lemmes = _appliquer_corrections(conn, region_id, tokens, lemmes, reancrer=fiable)
    _index_region(conn, region_id, payload, lemmes, tokens)


def reindex_all(conn: sqlite3.Connection, chunk: int = 500) -> int:
    """Réindexation NLP EN LOT (lemmes + tokens) de toutes les régions, via
    `nlp.pipe` (rapide). À lancer explicitement (commande `tools/reindex_nlp.py`) :
    après un changement de paramètre (Phase 1) ou pour figer l'index définitif avec
    un modèle plus riche, p.ex. `lg` hors ligne (transition vers la consultation).
    Commit par lots (transaction bornée, index mis à jour au fur et à mesure).
    Enregistre le modèle utilisé dans `meta` (reproductibilité). Renvoie le nombre
    de régions traitées. Sans spaCy : réindexation structurelle (repli propre)."""
    from pipeline.nlp import analyse_batch, model_info
    rows = conn.execute("SELECT id, ocr_texte FROM regions ORDER BY id").fetchall()
    notes = {r["region_id"]: (r["note"] or "")
             for r in conn.execute("SELECT region_id, note FROM annotations")}
    n = 0
    for start in range(0, len(rows), chunk):
        batch = rows[start:start + chunk]
        ocr_res = analyse_batch([r["ocr_texte"] or "" for r in batch])
        note_res = analyse_batch([notes.get(r["id"], "") for r in batch])
        for j, r in enumerate(batch):
            toks = ocr_res[j][1]
            lemmes = (ocr_res[j][0] + " " + note_res[j][0]).strip()
            fiable = bool(toks) or not (r["ocr_texte"] or "").strip()
            lemmes = _appliquer_corrections(conn, r["id"], toks, lemmes, reancrer=fiable)
            _index_region(conn, r["id"], _region_index_payload(conn, r["id"]),
                          lemmes, toks)
            n += 1
        conn.commit()
    info = model_info()
    meta = {"nlp_model": info.get("model", ""), "nlp_spacy": info.get("spacy", ""),
            "nlp_reindexed_count": str(n), "nlp_reindexed_at": "datetime"}
    for cle, val in meta.items():
        if val == "datetime":
            conn.execute("INSERT INTO meta (cle, valeur) VALUES (?, datetime('now')) "
                         "ON CONFLICT(cle) DO UPDATE SET valeur = datetime('now')", (cle,))
        else:
            conn.execute("INSERT INTO meta (cle, valeur) VALUES (?, ?) "
                         "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, val))
    conn.commit()
    return n


def unindex_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Retire une région de l'index FTS (suppression de région)."""
    conn.execute("DELETE FROM recherche WHERE region_id = ?", (region_id,))


if __name__ == "__main__":
    init_db()
    print(f"Base initialisée : {DB_PATH} (schéma v{SCHEMA_VERSION})")
