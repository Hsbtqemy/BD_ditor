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
SCHEMA_VERSION = 24


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
    auteur       TEXT,                       -- legacy (responsabilité à plat) → voir `contribution`
    annee        INTEGER,                    -- legacy (ambigu) → précisé par date_edition/date_originale
    editeur      TEXT,
    serie        TEXT,
    description  TEXT,
    -- Enrichissement descriptif N0 (v15) : édition détenue. Cf. docs/dictionnaire-metadonnees.md.
    date_edition     TEXT,                   -- publication de l'édition détenue (l'ANCRE)
    date_originale   TEXT,                   -- 1re parution de l'œuvre (optionnel, secondaire)
    langue           TEXT,                   -- langue de l'expression (code, ex. 'fr')
    type_oeuvre      TEXT,                   -- BD / roman graphique / strip… (contrôlé-ouvert)
    lieu_edition     TEXT,                   -- ville de publication
    edition_tirage   TEXT,                   -- mention d'édition / tirage
    isbn             TEXT,                   -- ISBN / dépôt légal
    format_physique  TEXT,                   -- dimensions (cm) / reliure de l'ŒUVRE
    -- Matériel de numérisation (v19, A6, N1) : appareil / conditions de scan (PREMIS,
    -- humain). Album-level = une campagne de scan par album. Cf. docs/materiel-numerisation.md.
    source_numerisation TEXT,
    date_import  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS planches (
    id                 INTEGER PRIMARY KEY,
    album_id           INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    numero             INTEGER NOT NULL,             -- ordre d'import (clé de tri, peut avoir des trous)
    role               TEXT NOT NULL DEFAULT 'recit', -- 'recit' = narratif (numéroté) ; autre = paratexte (écarté)
    chemin_tiff        TEXT,
    chemin_web         TEXT NOT NULL,
    largeur_px         INTEGER,
    hauteur_px         INTEGER,
    -- Matériel de numérisation (v19, A6, N1) : résolution + mode colorimétrique CAPTÉS à
    -- l'ingest depuis le fichier (Pillow), NULL si le fichier ne les porte pas. Les dimensions
    -- physiques (cm) en DÉRIVENT (px÷dpi), jamais stockées. Cf. docs/materiel-numerisation.md.
    dpi_x              INTEGER,       -- résolution horizontale (points/pouce)
    dpi_y              INTEGER,       -- résolution verticale
    mode               TEXT,          -- espace colorimétrique Pillow : 'RGB' | 'CMYK' | 'L' | …
    statut             TEXT DEFAULT 'importee',
    date_segmentation  TEXT,
    validee            TEXT,          -- horodatage de validation humaine (NULL = non validée)
    verrouillee        TEXT,          -- horodatage de verrou (NULL = déverrouillée) : protège des passes ML auto
    verrou_par         TEXT,          -- AUTH-1 (v22) : QUI a posé le verrou (login Authelia ; NULL = local/anonyme)
    -- Statut de RELECTURE grammaticale (ANN-4, v21) : DÉRIVÉ des provenances de tokens par défaut
    -- (cf. database.relecture_planches, jamais stocké), cette colonne = OVERRIDE humain
    -- ('a_faire'|'en_cours'|'faite') ; NULL = suivre le dérivé.
    relecture          TEXT
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
    date_creation  TEXT DEFAULT (datetime('now')),
    -- Provenance / audit (v16, A3) : run qui a GÉNÉRÉ la zone (PROV wasGeneratedBy) et
    -- surface DÉNORMALISÉE de retouche humaine (drapeau + date), lue à moindre coût par
    -- les indicateurs de dérive sans rejouer le journal. Cf. `activite`/`evenement`.
    activite_id       INTEGER REFERENCES activite(id) ON DELETE SET NULL,
    touche            INTEGER NOT NULL DEFAULT 0,     -- pré-remplissage machine retouché par un humain
    date_modification TEXT                            -- horodatage de la dernière retouche humaine
);

CREATE TABLE IF NOT EXISTS tags (
    id             INTEGER PRIMARY KEY,
    label          TEXT UNIQUE NOT NULL,
    couleur        TEXT DEFAULT '#1a4a8a',
    description    TEXT,                          -- glose du tag = SKOS definition (A4 : déjà là)
    -- Lexique situé (v17, A4) — couche définitionnelle SKOS partagée avec le vocabulaire
    -- facetté. `note_portee` = SKOS scopeNote (le « situé ») ; `etat` = maturité
    -- provisoire→défini (miroir auto→validé) ; `collection_id` = portée d'appartenance
    -- (NULL = global, sinon local à une collection ; promotion → NULL, patron mentions→entités).
    note_portee    TEXT,
    etat           TEXT NOT NULL DEFAULT 'provisoire',   -- 'provisoire' | 'defini'
    collection_id  INTEGER REFERENCES collection(id) ON DELETE SET NULL,
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


-- Métadonnées clé/valeur (documentation/reproductibilité) : p.ex. quel modèle NLP
-- a produit l'index linguistique, et quand. Utile quand le corpus devient citable.
CREATE TABLE IF NOT EXISTS meta (
    cle      TEXT PRIMARY KEY,
    valeur   TEXT
);

-- ANN-2 (lot mince) : personnages + attribution du locuteur + attributs facettés &
-- ÉMERGENTS. Cf. docs/personnages-et-attribution.md (§13). Le vocabulaire n'est PAS
-- figé : dimensions et valeurs sont des DONNÉES créées au fil de l'eau.

-- Entité personnage RÉCURRENTE au niveau corpus (≠ type de région 'personnage', qui
-- n'est qu'une boîte dessinée). `serie` facultative → désambiguïse les homonymes.
CREATE TABLE IF NOT EXISTS personnages (
    id             INTEGER PRIMARY KEY,
    nom            TEXT NOT NULL,
    serie          TEXT,
    notes          TEXT,
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- Lien LOCUTEUR : quelle entité parle dans cette bulle (au plus une → region_id PK).
-- ON DELETE CASCADE des DEUX côtés = on détache la liaison quand la région OU le
-- personnage disparaît ; aucun des deux n'est supprimé par l'autre.
CREATE TABLE IF NOT EXISTS bulle_locuteur (
    region_id      INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- Lien PRÉSENCE : quelle entité est MONTRÉE dans cette boîte personnage (au plus une
-- → region_id PK ; region.type = 'personnage'). Miroir du locuteur, mais pour l'image :
-- la boîte porte l'identité, l'entité reste le moyeu où parole et image convergent
-- (cf. docs/personnages-et-attribution.md §14, brique (a)). Même CASCADE des deux côtés.
CREATE TABLE IF NOT EXISTS personnage_presence (
    region_id      INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- ALIGNEMENT D'AUTORITÉ (v18, A5, N6) — relie une entité personnage à des référentiels
-- externes (Wikidata / VIAF / IdRef…) : un personnage → 0..N URI, chacune un
-- `skos:exactMatch`. `source` = l'autorité (auto-détectée depuis l'URI, contrôlé-ouvert).
-- Rend les entités interopérables (réconciliation, réutilisation FAIR). Cf.
-- docs/alignement-autorite.md.
CREATE TABLE IF NOT EXISTS personnage_alignement (
    id             INTEGER PRIMARY KEY,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    source         TEXT,                          -- 'wikidata' | 'viaf' | 'idref' | … (auto)
    uri            TEXT NOT NULL,
    date_creation  TEXT DEFAULT (datetime('now')),
    UNIQUE(personnage_id, uri)
);

-- DOMAINE (v20, piste B) — champ analytique ÉMERGENT qui REGROUPE des dimensions
-- (« émotions », « représentation », « style visuel »…). ORTHOGONAL à `cible` : un domaine
-- peut grouper des dimensions personnage ET case. Même patron contrôlé-ouvert + lexique SKOS
-- que les dimensions. Les émotions ne sont qu'un domaine parmi d'autres. Cf. docs/domaines.md.
CREATE TABLE IF NOT EXISTS domaine (
    id             INTEGER PRIMARY KEY,
    nom            TEXT NOT NULL UNIQUE,
    -- Lexique situé (A4) — SKOS : même couche définitionnelle que dimensions/valeurs/tags.
    definition     TEXT,
    note_portee    TEXT,
    etat           TEXT NOT NULL DEFAULT 'provisoire',   -- 'provisoire' | 'defini'
    collection_id  INTEGER REFERENCES collection(id) ON DELETE SET NULL,
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- Dimension d'attribut (un AXE émergent). `cible` = à quoi elle s'applique :
-- 'personnage' (profil sociolinguistique du locuteur) ou 'case' (situation de scène).
-- `domaine_id` = champ analytique de rattachement (v20, NULL = hors domaine ; suppression du
-- domaine → NULL, la dimension survit — soupape *promotion* comme collection_id).
CREATE TABLE IF NOT EXISTS attribut_dimension (
    id             INTEGER PRIMARY KEY,
    cible          TEXT NOT NULL,              -- 'personnage' | 'case'
    nom            TEXT NOT NULL,
    domaine_id     INTEGER REFERENCES domaine(id) ON DELETE SET NULL,
    -- Lexique situé (v17, A4) — SKOS : definition (sens de l'axe) · note_portee (scopeNote,
    -- cadre d'emploi = le « situé ») · etat (provisoire→défini) · collection_id (portée
    -- d'appartenance : NULL = global, sinon local à une collection ; promotion → NULL).
    definition     TEXT,
    note_portee    TEXT,
    etat           TEXT NOT NULL DEFAULT 'provisoire',   -- 'provisoire' | 'defini'
    collection_id  INTEGER REFERENCES collection(id) ON DELETE SET NULL,
    date_creation  TEXT DEFAULT (datetime('now')),
    UNIQUE(cible, nom)
);

-- Valeur CANONIQUE d'une dimension (agrégabilité : « rural » = une entrée, pas trois
-- orthographes). Émergente, mais contrôlée en forme.
CREATE TABLE IF NOT EXISTS attribut_valeur (
    id             INTEGER PRIMARY KEY,
    dimension_id   INTEGER NOT NULL REFERENCES attribut_dimension(id) ON DELETE CASCADE,
    valeur         TEXT NOT NULL,
    -- Lexique situé (v17, A4) — SKOS : definition (sens de la valeur) · note_portee
    -- (scopeNote) · etat (provisoire→défini) · collection_id (portée d'appartenance).
    definition     TEXT,
    note_portee    TEXT,
    etat           TEXT NOT NULL DEFAULT 'provisoire',   -- 'provisoire' | 'defini'
    collection_id  INTEGER REFERENCES collection(id) ON DELETE SET NULL,
    date_creation  TEXT DEFAULT (datetime('now')),
    UNIQUE(dimension_id, valeur)
);

-- Affectation d'une valeur à un personnage (profil) — N-N.
CREATE TABLE IF NOT EXISTS personnage_attribut (
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    valeur_id      INTEGER NOT NULL REFERENCES attribut_valeur(id) ON DELETE CASCADE,
    PRIMARY KEY (personnage_id, valeur_id)
);

-- Affectation d'une valeur à une région-case (situation de scène) — N-N. La dimension
-- ('case') restreint l'usage côté UI ; au schéma, la cible est une région quelconque.
CREATE TABLE IF NOT EXISTS region_attribut (
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    valeur_id      INTEGER NOT NULL REFERENCES attribut_valeur(id) ON DELETE CASCADE,
    PRIMARY KEY (region_id, valeur_id)
);

-- COLLECTION (v14) — palier supérieur : décrit le JEU DE DONNÉES lui-même (une sélection
-- constituée pour une étude), unité de dépôt (1 collection = 1 dépôt Nakala/HAL = 1 DOI).
-- Cf. docs/dictionnaire-metadonnees.md (palier « Collection »). L'appartenance est N-N,
-- STATIQUE (composition figée → citable). Les descripteurs DÉCRIVENT le régime de droits ;
-- ils ne l'IMPOSENT pas (l'accès est géré par l'auth / l'entrepôt). `responsables` est un
-- JSON [{nom, role, orcid?}] — même forme que la future `contribution` (N0), pour converger.
CREATE TABLE IF NOT EXISTS collection (
    id                INTEGER PRIMARY KEY,
    nom               TEXT NOT NULL,
    description       TEXT,
    licence_defaut    TEXT,                         -- ex. « CC-BY-4.0 » (tier ouvert)
    base_legale       TEXT,                         -- à quel titre on détient/exploite les données (à établir, hors code)
    statut_diffusion  TEXT,                         -- 'public' | 'embargo' | 'restreint' | 'prive'
    date_embargo      TEXT,                          -- levée d'embargo (si statut_diffusion='embargo')
    responsables      TEXT,                          -- JSON : [{"nom":…, "role":…, "orcid":…}]
    date_debut        TEXT,                          -- période de constitution / couverture
    date_fin          TEXT,
    date_creation     TEXT DEFAULT (datetime('now'))
);

-- Appartenance album ↔ collection (N-N, statique). `rang` = ordre citable stable dans la
-- collection. CASCADE des deux côtés : on détache la liaison si l'album OU la collection
-- disparaît. Un album peut vivre dans 0..N collections.
CREATE TABLE IF NOT EXISTS collection_album (
    collection_id  INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    album_id       INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    rang           INTEGER,
    PRIMARY KEY (collection_id, album_id)
);

-- DROIT D'ACCÈS à une collection (v23, AUTH-2). La collection est l'unité de cloisonnement :
-- on n'autorise jamais un album directement, toujours la collection qui le contient.
--
-- `principal` est un NOM — un login, ou un nom de groupe tel qu'il apparaît dans l'en-tête
-- `Remote-Groups` posé par Authelia. Rien ici n'est un secret et rien n'est une
-- APPARTENANCE : on ne stocke pas « Alice est dans bd-lettrage », on stocke « bd-lettrage
-- ouvre la collection 3 ». La composition des groupes reste chez Authelia et se relit à
-- chaque requête (invariant AUTH-1, cf. docs/hebergement-securite.md).
--
-- `genre` est EXPLICITE plutôt que déduit : un login et un groupe peuvent porter le même
-- nom, et une ambiguïté silencieuse sur un contrôle d'accès n'est pas une hypothèse qu'on
-- se permet.
CREATE TABLE IF NOT EXISTS collection_acces (
    collection_id  INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    genre          TEXT NOT NULL,       -- 'utilisateur' | 'groupe'
    principal      TEXT NOT NULL,       -- login, ou nom de groupe Remote-Groups
    niveau         TEXT NOT NULL,       -- 'lecture' | 'ecriture'
    date_creation  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, genre, principal)
);
-- On interroge « quelles collections pour CE principal » à chaque requête : l'index porte
-- donc sur le principal, la clé primaire couvrant déjà le sens inverse.
CREATE INDEX IF NOT EXISTS idx_acces_principal ON collection_acces(genre, principal);

-- CONTRIBUTION (v15, N0) — paternité en modèle Zotero-like : (nom, rôle) par album.
-- Le rôle est un vocabulaire CONTRÔLÉ-MAIS-OUVERT (même forme que tags/attributs), curé
-- depuis MARC Relators et mappé aux buckets DCterms `creator`/`contributor`. Le `nom` reste
-- une chaîne, aliasable vers une entité (VIAF/IdRef) plus tard — dormant. `auteur` (albums)
-- reste en legacy. Cf. docs/dictionnaire-metadonnees.md (Niveau 0).
CREATE TABLE IF NOT EXISTS contribution_role (
    id             INTEGER PRIMARY KEY,
    label          TEXT UNIQUE NOT NULL,          -- ex. « scénariste », « dessinateur »
    bucket         TEXT NOT NULL DEFAULT 'contributor',  -- DCterms : 'creator' | 'contributor'
    marc           TEXT,                          -- code MARC Relators (ex. 'aut', 'art'), optionnel
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- Contributeur d'un album (N-N via lignes ; `rang` = ordre citable). Rôle NULL toléré
-- (ON DELETE SET NULL : supprimer un rôle du vocabulaire ne perd pas la contribution).
CREATE TABLE IF NOT EXISTS contribution (
    id             INTEGER PRIMARY KEY,
    album_id       INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    nom            TEXT NOT NULL,
    role_id        INTEGER REFERENCES contribution_role(id) ON DELETE SET NULL,
    rang           INTEGER,
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- JOURNAL DE PROVENANCE / AUDIT (v16, N8, A3) — couche APPEND-ONLY qui QUALIFIE le
-- travail sans inverser la base : les tables métier restent la source de vérité ; ici on
-- enregistre EN PLUS chaque acte, machine ou humain. Cf. docs/provenance-audit.md.
--   • `activite` = un RUN (PROV Activity) : une passe ML en lot, ou une session d'édition.
--     Porte l'agent (moteur+version, OU humain), les paramètres, la portée, le bilan.
--   • `evenement` = un ACTE atomique IMMUABLE (PROV / TEI change) rattaché à son activité,
--     portant l'état AVANT/APRÈS → substrat de l'undo (D1) et du signal de dérive.
-- Le journal SURVIT à la suppression de sa cible : `cible_id` n'est PAS une clé étrangère
-- (un CASCADE effacerait l'historique de ce qu'on veut justement pouvoir restaurer).
CREATE TABLE IF NOT EXISTS activite (
    id          INTEGER PRIMARY KEY,
    type        TEXT NOT NULL,                       -- 'segmentation'|'bulles'|'ocr'|'reindex_nlp'|'edition'…
    agent       TEXT,                                -- identité humaine (auth) OU nom du moteur
    agent_type  TEXT NOT NULL DEFAULT 'humain',      -- 'humain' | 'moteur'
    version     TEXT,                                -- version moteur/modèle (NULL si humain)
    params      TEXT,                                -- JSON des paramètres du run
    portee      TEXT,                                -- JSON : {planche_id, album_id…}
    comptes     TEXT,                                -- JSON : bilan {crees, modifies…}
    date_debut  TEXT DEFAULT (datetime('now')),
    date_fin    TEXT
);

CREATE TABLE IF NOT EXISTS evenement (
    id           INTEGER PRIMARY KEY,
    activite_id  INTEGER REFERENCES activite(id) ON DELETE SET NULL,
    type         TEXT NOT NULL,                      -- 'creation'|'modification'|'suppression'|'validation'|'lien'|'delien'|'annulation' (undo, D1)
    agent        TEXT,
    agent_type   TEXT NOT NULL DEFAULT 'humain',     -- 'humain' | 'moteur'
    cible_table  TEXT NOT NULL,                      -- 'regions'|'annotations'|'token_correction'|'planches'…
    cible_id     INTEGER,                            -- id de la cible (PAS une FK : le journal lui survit)
    avant        TEXT,                               -- JSON état avant (NULL si création)
    apres        TEXT,                               -- JSON état après (NULL si suppression)
    date         TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_planches_album   ON planches(album_id);
CREATE INDEX IF NOT EXISTS idx_regions_planche  ON regions(planche_id);
-- Utilisateur connu de l'application (AUTH-1, v22). MIROIR de ce qu'Authelia envoie :
-- l'app n'authentifie personne et ne stocke AUCUN secret — pas de mot de passe, pas de
-- hash, pas de jeton. La clé est le login du proxy (`Remote-User`) ; `nom` et `email`
-- ne servent qu'à l'affichage, et sont rafraîchis à chaque fois qu'on revoit la personne.
--
-- Les GROUPES ne sont volontairement PAS stockés : ils vivent dans
-- `deploy/authelia/users_database.yml` et sont relus dans `Remote-Groups` à chaque
-- requête. Les figer en base créerait une seconde source de vérité, et retirer quelqu'un
-- d'un groupe n'aurait aucun effet tant qu'on n'aurait pas aussi touché la base.
--
-- La ligne existe pour que d'autres chantiers aient une identité STABLE à référencer :
-- les identifiants WebDAV chiffrés par personne (INFRA-3) et le propriétaire d'une
-- collection (AUTH-3). Elle n'est PAS une table de droits.
CREATE TABLE IF NOT EXISTS utilisateur (
    login          TEXT PRIMARY KEY,               -- identifiant Authelia (en-tête Remote-User)
    nom            TEXT,                           -- Remote-Name : nom affiché
    email          TEXT,                           -- Remote-Email
    premiere_vue   TEXT DEFAULT (datetime('now')), -- première requête vue de cette personne
    derniere_vue   TEXT                            -- dernière requête vue
);

CREATE INDEX IF NOT EXISTS idx_regions_parent   ON regions(parent_id);
CREATE INDEX IF NOT EXISTS idx_anntags_tag      ON annotation_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_tokens_region    ON tokens(region_id);
CREATE INDEX IF NOT EXISTS idx_tokens_lemme     ON tokens(lemme);
CREATE INDEX IF NOT EXISTS idx_tokens_pos       ON tokens(pos);
CREATE INDEX IF NOT EXISTS idx_tcorr_region     ON token_correction(region_id);
CREATE INDEX IF NOT EXISTS idx_tcorr_etat       ON token_correction(etat);
CREATE INDEX IF NOT EXISTS idx_locuteur_perso   ON bulle_locuteur(personnage_id);
CREATE INDEX IF NOT EXISTS idx_presence_perso   ON personnage_presence(personnage_id);
CREATE INDEX IF NOT EXISTS idx_attrval_dim      ON attribut_valeur(dimension_id);
CREATE INDEX IF NOT EXISTS idx_persoattr_val    ON personnage_attribut(valeur_id);
CREATE INDEX IF NOT EXISTS idx_regattr_val      ON region_attribut(valeur_id);
CREATE INDEX IF NOT EXISTS idx_colalbum_album   ON collection_album(album_id);
CREATE INDEX IF NOT EXISTS idx_contribution_album ON contribution(album_id);
CREATE INDEX IF NOT EXISTS idx_contribution_role  ON contribution(role_id);
CREATE INDEX IF NOT EXISTS idx_evenement_cible    ON evenement(cible_table, cible_id);
CREATE INDEX IF NOT EXISTS idx_evenement_activite ON evenement(activite_id);
CREATE INDEX IF NOT EXISTS idx_evenement_date     ON evenement(date);
CREATE INDEX IF NOT EXISTS idx_alignement_perso   ON personnage_alignement(personnage_id);
CREATE INDEX IF NOT EXISTS idx_domaine_collection ON domaine(collection_id);
-- NB : l'unicité (album_id, numero) des planches (DB-1) est posée en MIGRATION
-- (idx_planches_album_numero), pas ici : sa création doit suivre un dédoublonnage
-- d'éventuelles données préexistantes, qui ne peut avoir lieu qu'après SCHEMA_SQL.
-- NB (v20) : les index portant sur des colonnes AJOUTÉES PAR MIGRATION (activite_id des regions
-- — v16 ; collection_id des dimensions/valeurs/tags — v17 ; domaine_id — v20) sont créés DANS
-- `_migrate` (après l'ALTER), PAS ici : un CREATE INDEX dans SCHEMA_SQL tournerait AVANT l'ALTER
-- lors d'un upgrade → crash « no such column ». Cf. idx_regions_activite / idx_dim_collection /
-- idx_val_collection / idx_tags_collection / idx_dim_domaine.
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

# Vues — TOUJOURS recréées au démarrage (DROP+CREATE) : une vue ne porte pas de
# données, donc faire évoluer sa définition est gratuit et sans migration.
# `tokens_effectifs` = read model canonique : valeur effective (correction vivante
# ⊕ auto) + provenance + `a_revoir` (une correction existe mais a dérivé → à
# revérifier). Toutes les surfaces d'analyse lisent CECI, jamais `tokens` brut.
_VIEWS_SQL = """
DROP VIEW IF EXISTS tokens_effectifs;
CREATE VIEW tokens_effectifs AS
SELECT t.region_id, t.ordre, t.texte,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.lemme END, t.lemme) AS lemme,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.pos   END, t.pos)   AS pos,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.morph END, t.morph) AS morph,
       CASE WHEN c.id IS NULL OR c.obsolete = 1 THEN 'auto'
            ELSE c.etat END                                          AS provenance,
       CASE WHEN c.id IS NOT NULL AND c.obsolete = 1 THEN 1 ELSE 0 END AS a_revoir,
       c.lemme AS corr_lemme, c.pos AS corr_pos, c.morph AS corr_morph,
       c.auteur AS corr_auteur          -- INFRA-2 : qui a corrigé/validé (NULL = auto / local)
FROM tokens t
LEFT JOIN token_correction c
       ON c.region_id = t.region_id AND c.ordre = t.ordre;
"""


def init_db() -> None:
    """Crée le schéma s'il n'existe pas et applique les migrations."""
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(_FTS_SQL)
        conn.executescript(_VIEWS_SQL)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Migrations idempotentes, GATÉES PAR `user_version` (cf. AUDIT B5).

    Deux garde-fous : (1) on REFUSE de rétrograder une base plus récente que le code
    (sinon corruption silencieuse) ; (2) on COURT-CIRCUITE si la base est déjà au schéma
    courant (aucune étape ne rejoue). Convention pour toute étape future : la garder par
    `if version < N` — INDISPENSABLE dès qu'une migration n'est pas détectable par le
    schéma lui-même (backfill, `UPDATE` de données), sinon elle rejouerait à chaque
    démarrage. Les étapes historiques gardées par présence de colonne restent valables
    (elles ne s'appliquent qu'aux bases pré-`user_version`)."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Base au schéma v{version}, plus récent que ce code (v{SCHEMA_VERSION}). "
            "Refus de rétrograder la base — mettez BéDéditeur à jour, ou restaurez une "
            "sauvegarde compatible.")
    if version == SCHEMA_VERSION:
        return                          # déjà à jour : aucune étape à rejouer

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

    # v9 → v10 : rôle éditorial de la planche (récit / paratexte). Le numéro éditorial
    # et le décompte de cases citables se dérivent des planches 'recit' (cf.
    # docs/numerotation-et-citation.md). Défaut 'recit' → tout l'existant reste
    # narratif, comportement inchangé jusqu'au marquage manuel d'un paratexte.
    if pcols and "role" not in pcols:
        conn.execute("ALTER TABLE planches ADD COLUMN role TEXT NOT NULL DEFAULT 'recit'")

    # v10 → v11 : ANN-2 (lot mince) — personnages, attribution du locuteur, attributs
    # facettés (personnages + tables `attribut_*`). NOUVELLES tables créées par
    # SCHEMA_SQL (CREATE … IF NOT EXISTS) → rien à migrer ici, juste acter la version.
    # Cf. docs/personnages-et-attribution.md §13.

    # v11 → v12 : brique (a) du §14 — lien PRÉSENCE (boîte personnage → entité), miroir
    # du locuteur pour l'image. NOUVELLE table créée par SCHEMA_SQL (CREATE … IF NOT
    # EXISTS) → rien à migrer, juste acter la version. Cf. docs/personnages-et-attribution.md §14.

    # v12 → v13 : DB-1 — unicité (album_id, numero) des planches. On dédoublonne D'ABORD
    # d'éventuels numéros en double (sinon CREATE UNIQUE INDEX échouerait), PUIS on pose
    # l'index. Idempotent (IF NOT EXISTS + version) ; sûr sur base neuve (aucune ligne).
    if version < 13:
        has_planches = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='planches'").fetchone()
        if has_planches:            # _migrate peut tourner avant SCHEMA_SQL (tests isolés)
            _dedup_numeros_planches(conn)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_planches_album_numero "
                         "ON planches(album_id, numero)")

    # v13 → v14 : palier COLLECTION — tables `collection` + `collection_album` (N-N statique),
    # unité de dépôt (1 collection = 1 DOI). NOUVELLES tables créées par SCHEMA_SQL
    # (CREATE … IF NOT EXISTS) → rien à migrer (aucune donnée existante), juste acter la
    # version. Cf. docs/dictionnaire-metadonnees.md (palier « Collection »).

    # v14 → v15 : enrichissement descriptif N0 — `contribution` (Zotero-like) +
    # `contribution_role` (vocabulaire ; créés par SCHEMA_SQL) et 8 colonnes d'édition sur
    # `albums`. Les colonnes se gardent par PRÉSENCE (no-op sur base neuve créée par
    # SCHEMA_SQL ; ALTER sur base ancienne). Le SEED du vocabulaire de rôles est un backfill
    # de DONNÉES → gaté par VERSION (idempotent en plus via INSERT OR IGNORE).
    if cols:                                        # table albums présente (peut manquer en test isolé)
        for col in ("date_edition", "date_originale", "langue", "type_oeuvre",
                    "lieu_edition", "edition_tirage", "isbn", "format_physique"):
            if col not in cols:
                conn.execute(f"ALTER TABLE albums ADD COLUMN {col} TEXT")
    if version < 15 and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='contribution_role'"
    ).fetchone():                                   # _migrate peut tourner avant SCHEMA_SQL
        _seed_roles(conn)

    # v15 → v16 : journal de provenance / audit (A3, N8). Tables `activite`/`evenement`
    # créées par SCHEMA_SQL (CREATE … IF NOT EXISTS). Sur `regions`, trois colonnes posées
    # par PRÉSENCE : lien wasGeneratedBy (`activite_id`) + surface dénormalisée de retouche
    # (`touche`/`date_modification`). L'ALTER de la FK exige que `activite` existe déjà
    # (SCHEMA_SQL tourne avant `_migrate` en init_db ; gardé au cas des tests isolés).
    rcols = {r["name"] for r in conn.execute("PRAGMA table_info(regions)")}
    a_activite = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='activite'").fetchone()
    if rcols:
        if a_activite and "activite_id" not in rcols:
            conn.execute("ALTER TABLE regions ADD COLUMN activite_id INTEGER "
                         "REFERENCES activite(id) ON DELETE SET NULL")
        # Index sur la colonne migrée : créé ICI (après l'ALTER), pas dans SCHEMA_SQL, qui
        # tournerait AVANT sur un upgrade pré-v16 → « no such column: activite_id ».
        if a_activite:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_regions_activite "
                         "ON regions(activite_id)")
        if "touche" not in rcols:
            conn.execute("ALTER TABLE regions ADD COLUMN touche INTEGER NOT NULL DEFAULT 0")
        if "date_modification" not in rcols:
            conn.execute("ALTER TABLE regions ADD COLUMN date_modification TEXT")

    # v16 → v17 : lexique situé (A4, N7) — couche définitionnelle SKOS sur le vocabulaire
    # émergent. `attribut_dimension`/`attribut_valeur` gagnent `definition` + `note_portee` +
    # `etat` + `collection_id` ; `tags` gagne `note_portee` + `etat` + `collection_id` (sa
    # `description` EST déjà la definition). Colonnes posées par PRÉSENCE ; la FK `collection_id`
    # exige que `collection` existe (SCHEMA_SQL tourne avant `_migrate` ; gardé pour les tests
    # isolés). `etat` NOT NULL exige un défaut (fourni : 'provisoire').
    a_collection = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection'").fetchone()
    _idx_collection = {"attribut_dimension": "idx_dim_collection",
                       "attribut_valeur": "idx_val_collection", "tags": "idx_tags_collection"}
    for table, defs in (
            ("attribut_dimension", (("definition", "TEXT"), ("note_portee", "TEXT"),
                                    ("etat", "TEXT NOT NULL DEFAULT 'provisoire'"))),
            ("attribut_valeur", (("definition", "TEXT"), ("note_portee", "TEXT"),
                                 ("etat", "TEXT NOT NULL DEFAULT 'provisoire'"))),
            ("tags", (("note_portee", "TEXT"),
                      ("etat", "TEXT NOT NULL DEFAULT 'provisoire'")))):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not cols:                                    # table absente (test isolé) → rien à faire
            continue
        for nom, typ in defs:
            if nom not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {typ}")
        if a_collection and "collection_id" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN collection_id INTEGER "
                         "REFERENCES collection(id) ON DELETE SET NULL")
        # Index sur collection_id créé ICI (pas dans SCHEMA_SQL) : la colonne vient peut-être
        # d'être posée → un CREATE INDEX dans SCHEMA_SQL tournerait AVANT l'ALTER (crash upgrade).
        if "collection_id" in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {_idx_collection[table]} "
                         f"ON {table}(collection_id)")

    # v17 → v18 : alignement d'autorité (A5, N6) — table `personnage_alignement` (NOUVELLE,
    # créée par SCHEMA_SQL CREATE … IF NOT EXISTS) → aucune donnée à migrer, juste acter la
    # version. Cf. docs/alignement-autorite.md.

    # v18 → v19 : matériel de numérisation (A6, N1). Sur `planches`, la résolution (`dpi_x`,
    # `dpi_y`) et le `mode` colorimétrique — CAPTÉS à l'ingest depuis le fichier (lus puis
    # jetés jusqu'ici). Sur `albums`, `source_numerisation` (appareil/conditions, humain).
    # Colonnes posées par PRÉSENCE (no-op sur base neuve créée par SCHEMA_SQL). Les dimensions
    # physiques (cm) sont DÉRIVÉES (px÷dpi), jamais stockées. Cf. docs/materiel-numerisation.md.
    pcols_mat = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    if pcols_mat:
        for col, typ in (("dpi_x", "INTEGER"), ("dpi_y", "INTEGER"), ("mode", "TEXT")):
            if col not in pcols_mat:
                conn.execute(f"ALTER TABLE planches ADD COLUMN {col} {typ}")
    acols_mat = {r["name"] for r in conn.execute("PRAGMA table_info(albums)")}
    if acols_mat and "source_numerisation" not in acols_mat:
        conn.execute("ALTER TABLE albums ADD COLUMN source_numerisation TEXT")

    # v19 → v20 : palier DOMAINE (piste B) — regroupe les dimensions facettées par champ
    # analytique (émotions, représentation…). Table `domaine` NOUVELLE (SCHEMA_SQL) ;
    # `attribut_dimension.domaine_id` posé par PRÉSENCE. L'ALTER de la FK exige que `domaine`
    # existe (SCHEMA_SQL tourne avant `_migrate` ; gardé pour les tests isolés). Orthogonal à
    # `cible`. Cf. docs/domaines.md.
    dcols = {r["name"] for r in conn.execute("PRAGMA table_info(attribut_dimension)")}
    a_domaine = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='domaine'").fetchone()
    if dcols and a_domaine and "domaine_id" not in dcols:
        conn.execute("ALTER TABLE attribut_dimension ADD COLUMN domaine_id INTEGER "
                     "REFERENCES domaine(id) ON DELETE SET NULL")
    # Index sur domaine_id créé ICI (pas dans SCHEMA_SQL, cf. NB ci-dessus) : la colonne vient
    # peut-être d'être ajoutée. Gardé par présence de la colonne (base neuve : posée par SCHEMA_SQL).
    if "domaine_id" in {r["name"] for r in conn.execute("PRAGMA table_info(attribut_dimension)")}:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dim_domaine ON attribut_dimension(domaine_id)")

    # v20 → v21 : statut de RELECTURE grammaticale (ANN-4). Colonne OVERRIDE ; le statut effectif
    # est DÉRIVÉ des provenances de tokens (jamais stocké). ALTER simple, pas d'index.
    pcols = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    if pcols and "relecture" not in pcols:
        conn.execute("ALTER TABLE planches ADD COLUMN relecture TEXT")

    # v21 → v22 : identité applicative (AUTH-1). Table `utilisateur` NOUVELLE (créée par
    # SCHEMA_SQL en `IF NOT EXISTS`) → rien à migrer. Sur `planches`, `verrou_par` posé par
    # PRÉSENCE : le verrou existait sans propriétaire, ce qui suffisait à un seul utilisateur
    # et devient ambigu à plusieurs. Aucun index : la table se lit par clé primaire, et
    # `verrou_par` ne sert qu'à l'affichage.
    pcols_auth = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    if pcols_auth and "verrou_par" not in pcols_auth:
        conn.execute("ALTER TABLE planches ADD COLUMN verrou_par TEXT")

    # v22 → v23 : cloisonnement par collection (AUTH-2). Table `collection_acces` NOUVELLE
    # (créée par SCHEMA_SQL en `IF NOT EXISTS`) → rien à migrer de ce côté. Ce qui suit est
    # une migration de DONNÉES, donc GATÉE par la version : elle rejouerait sinon à chaque
    # démarrage et recréerait la collection de repli après chaque rangement manuel.
    #
    # L'autorisation se décide par collection ; un album hors de toute collection ne
    # correspondrait à aucune règle. Plutôt que d'inventer une politique pour ce cas, on
    # supprime le cas : les orphelins existants entrent dans la collection de repli.
    # Mesuré le 2026-08-27 sur la base de travail : 3 albums, 0 collection.
    a_collections = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_album'"
    ).fetchone()
    if version < 23 and a_collections:      # garde de table : les tests de migration
        orphelins = albums_orphelins(conn)  # montent un schéma minimal, sans collections
        if orphelins:
            cid = collection_par_defaut(conn)
            conn.executemany(
                "INSERT OR IGNORE INTO collection_album (collection_id, album_id) "
                "VALUES (?, ?)", [(cid, a) for a in orphelins])

    # --- v24 : un terme ne peut pas être plus GLOBAL que celui dont il dépend ---------
    # Les routes de création n'ont jamais posé de `collection_id` : une dimension rattachée
    # à un domaine privé, et toute valeur créée sous un axe privé, naissaient GLOBALES.
    # Elles se montraient donc à tout le monde — en nommant au passage le domaine ou l'axe
    # d'à côté, c'est-à-dire une grille d'analyse et non un mot. Les routes héritent
    # désormais du parent ; cette étape recolle l'existant, sans quoi le cloisonnement ne
    # vaudrait que pour les bases neuves et le « % défini » resterait faux (il compte par
    # appartenance, et compterait donc un terme que les listes masquent).
    #
    # L'ordre compte : le domaine descend d'abord vers ses dimensions, qui descendent
    # ensuite vers leurs valeurs. On ne touche QUE les termes sans portée — un terme déjà
    # local à une autre collection est un fait délibéré, pas une omission.
    # Garde par COLONNES et non par table : les tests de migration montent des schémas
    # minimaux où `domaine` existe sans sa portée, et les ALTER qui la posent sont eux-mêmes
    # gardés par présence. Une garde de table suffisante en apparence casse donc là.
    def _cols(table):
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    portees_presentes = all(
        "collection_id" in _cols(t)
        for t in ("domaine", "attribut_dimension", "attribut_valeur")
    ) and "domaine_id" in _cols("attribut_dimension")
    if version < 24 and portees_presentes:
        conn.execute(
            """UPDATE attribut_dimension SET collection_id =
                   (SELECT d.collection_id FROM domaine d WHERE d.id = domaine_id)
               WHERE collection_id IS NULL AND domaine_id IS NOT NULL
                 AND (SELECT d.collection_id FROM domaine d
                       WHERE d.id = domaine_id) IS NOT NULL""")
        conn.execute(
            """UPDATE attribut_valeur SET collection_id =
                   (SELECT x.collection_id FROM attribut_dimension x
                     WHERE x.id = dimension_id)
               WHERE collection_id IS NULL
                 AND (SELECT x.collection_id FROM attribut_dimension x
                       WHERE x.id = dimension_id) IS NOT NULL""")

    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _dedup_numeros_planches(conn: sqlite3.Connection) -> None:
    """Réattribue un numéro libre aux planches partageant un (album_id, numero) — rare
    (seul un `numero` explicite a pu collisionner avant DB-1). Garde la plus ancienne
    (id min) ; les suivantes prennent MAX(numero)+1 de leur album. Prépare l'unicité.
    Note : ne renomme PAS les fichiers (un doublon préexistant les a déjà écrasés) ;
    rend seulement la base cohérente pour poser la contrainte."""
    dups = conn.execute(
        "SELECT album_id, numero FROM planches "
        "GROUP BY album_id, numero HAVING COUNT(*) > 1").fetchall()
    for d in dups:
        rows = conn.execute(
            "SELECT id FROM planches WHERE album_id = ? AND numero = ? ORDER BY id",
            (d["album_id"], d["numero"])).fetchall()
        for extra in rows[1:]:                      # on conserve la première
            n = conn.execute(
                "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches WHERE album_id = ?",
                (d["album_id"],)).fetchone()["n"]
            conn.execute("UPDATE planches SET numero = ? WHERE id = ?", (n, extra["id"]))


# Vocabulaire de rôles de contribution — SEED curé (contrôlé-mais-ouvert), source MARC
# Relators, mappé aux buckets DCterms. Étendu librement par l'utilisateur ensuite.
_ROLES_SEED = (
    ("scénariste", "creator", "aut"),
    ("dessinateur", "creator", "art"),
    ("coloriste", "contributor", "clr"),
    ("encreur", "contributor", None),
    ("lettreur", "contributor", None),
    ("traducteur", "contributor", "trl"),
    ("préfacier", "contributor", "aui"),
)


def _seed_roles(conn: sqlite3.Connection) -> None:
    """Insère le vocabulaire de rôles curé (idempotent : INSERT OR IGNORE sur `label`
    unique). N'écrase JAMAIS un rôle existant (bucket/marc édités à la main restent)."""
    conn.executemany(
        "INSERT OR IGNORE INTO contribution_role (label, bucket, marc) VALUES (?, ?, ?)",
        _ROLES_SEED)


# --------------------------------------------------------------------------- #
# Numérotation éditoriale des planches (dérivée — cf. docs/numerotation-et-citation.md)
# --------------------------------------------------------------------------- #
def numeros_editoriaux(conn: sqlite3.Connection, album_id: int) -> dict[int, int | None]:
    """Numéro éditorial de chaque planche d'un album, DÉRIVÉ (jamais stocké).

    Rang 1..N parmi les seules planches `role='recit'`, triées par `numero` (ordre
    d'import) — robuste aux trous de `numero` et aux suppressions. Une planche
    paratexte (couverture, liminaire, pub…) renvoie None : elle est citée par son
    libellé, hors de la numérotation du récit.

    Renvoie {planche_id: numero_editorial | None}.
    """
    rows = conn.execute(
        "SELECT id, role FROM planches WHERE album_id = ? ORDER BY numero, id",
        (album_id,),
    ).fetchall()
    out: dict[int, int | None] = {}
    n = 0
    for r in rows:
        if r["role"] == "recit":
            n += 1
            out[r["id"]] = n
        else:
            out[r["id"]] = None
    return out


def dimensions_cm(largeur_px, hauteur_px, dpi_x, dpi_y) -> dict | None:
    """Dimensions physiques (cm) du scan, DÉRIVÉES des pixels master et de la résolution
    (v19, A6) — jamais stockées, même doctrine que le numéro éditorial. None si la
    résolution manque (indérivable) ; arrondi au dixième de cm (1 pouce = 2,54 cm).

    Renvoie {"largeur": float, "hauteur": float} | None.
    """
    if not (dpi_x and dpi_y and largeur_px and hauteur_px):
        return None
    return {"largeur": round(largeur_px / dpi_x * 2.54, 1),
            "hauteur": round(hauteur_px / dpi_y * 2.54, 1)}


def relecture_planches(conn: sqlite3.Connection, planche_ids) -> dict:
    """Statut de RELECTURE grammaticale par planche (ANN-4, v21). DÉRIVÉ des provenances de
    tokens (relus = corrigé|validé) — jamais stocké —, OVERRIDÉ par `planches.relecture` si
    non NULL. Dérivé : 'faite' (tous relus, ≥1 token), 'en_cours' (partiel), sinon 'a_faire'
    (dont 0 token). Renvoie {planche_id: {statut (effectif), derive, force (bool), tokens, relus}}.
    """
    ids = list(dict.fromkeys(planche_ids))
    if not ids:
        return {}
    qm = ",".join("?" * len(ids))
    comptes = {pid: (0, 0) for pid in ids}          # planche_id → (tokens, relus)
    for r in conn.execute(
            f"SELECT reg.planche_id AS pid, COUNT(*) AS tokens, "
            f"       SUM(te.provenance IN ('corrige', 'valide')) AS relus "
            f"FROM tokens_effectifs te JOIN regions reg ON reg.id = te.region_id "
            f"WHERE reg.planche_id IN ({qm}) GROUP BY reg.planche_id", ids):
        comptes[r["pid"]] = (r["tokens"], r["relus"] or 0)
    overrides = {r["id"]: r["relecture"] for r in conn.execute(
        f"SELECT id, relecture FROM planches WHERE id IN ({qm})", ids)}
    out = {}
    for pid in ids:
        tokens, relus = comptes[pid]
        derive = ("faite" if tokens and relus >= tokens
                  else "en_cours" if relus else "a_faire")
        force = overrides.get(pid)
        out[pid] = {"statut": force or derive, "derive": derive,
                    "force": force is not None, "tokens": tokens, "relus": relus}
    return out


# Régions de texte (citées au niveau bulle « pl·c·b ») — cf. ordre de lecture.
_TYPES_TEXTE = ("bulle", "cartouche", "texte")


def citations_regions(conn: sqlite3.Connection,
                      region_ids: list[int]) -> dict[int, dict]:
    """Citation éditoriale de régions, DÉRIVÉE (cf. docs/numerotation-et-citation.md).

    Clé de citation STABLE ancrée sur la planche, plus un repère GLOBAL (confort) :
      • case        → {'texte': 'pl.3 · c2', 'planche', 'case', 'global', 'total'} ;
      • bulle/texte rattachée à une case → ajoute 'bulle' et 'texte' 'pl.3 · c2 · b1' ;
      • bulle hors case (parent NULL)    → 'texte' 'pl.3 · hors-case' ;
      • planche paratexte                → {'planche': None, 'texte': 'Paratexte'}.

    Tout est calculé à la volée (jamais stocké). Batch : un nombre fixe de requêtes
    par planches / albums concernés, pas une par région. Renvoie {region_id: dict}.
    """
    ids = list(dict.fromkeys(region_ids))
    if not ids:
        return {}
    qm = ",".join("?" * len(ids))
    regs = {r["id"]: dict(r) for r in conn.execute(
        f"SELECT id, type, planche_id, parent_id FROM regions WHERE id IN ({qm})", ids)}
    if not regs:
        return {}

    planche_ids = sorted({r["planche_id"] for r in regs.values() if r["planche_id"]})
    if not planche_ids:                       # régions sans planche (cas dégénéré)
        return {}
    pm = ",".join("?" * len(planche_ids))
    planches = {p["id"]: dict(p) for p in conn.execute(
        f"SELECT id, album_id FROM planches WHERE id IN ({pm})", planche_ids)}
    album_ids = sorted({p["album_id"] for p in planches.values()})

    # Numéro éditorial par planche (par album) + ordre éditorial pour l'offset global.
    ed_by_album = {aid: numeros_editoriaux(conn, aid) for aid in album_ids}
    editorial = {pid: ed for m in ed_by_album.values() for pid, ed in m.items()}

    # Rang de case (cases seules, ordre de lecture) + rang de bulle (entre frères
    # d'une même case) + nb de cases par planche, sur les planches concernées.
    case_rang: dict[int, int] = {}
    bulle_rang: dict[int, int] = {}
    seen_case: dict[int, int] = {}
    seen_child: dict[int, int] = {}
    for r in conn.execute(
            f"SELECT id, planche_id, parent_id, type FROM regions "
            f"WHERE planche_id IN ({pm}) ORDER BY ordre, id", planche_ids):
        if r["type"] == "case":
            seen_case[r["planche_id"]] = seen_case.get(r["planche_id"], 0) + 1
            case_rang[r["id"]] = seen_case[r["planche_id"]]
        # Rang de bulle : compté sur les SEULES régions de texte (une région
        # 'personnage' enfant d'une case ne décale pas la numérotation des bulles).
        elif r["type"] in _TYPES_TEXTE and r["parent_id"] is not None:
            seen_child[r["parent_id"]] = seen_child.get(r["parent_id"], 0) + 1
            bulle_rang[r["id"]] = seen_child[r["parent_id"]]

    # Offsets globaux + totaux par album : cases cumulées sur les planches RÉCIT,
    # en ordre éditorial (toutes les planches récit, pas seulement celles ciblées).
    global_offset: dict[int, int] = {}
    album_total: dict[int, int] = {}
    for aid, ed_map in ed_by_album.items():
        counts = {row["planche_id"]: row["n"] for row in conn.execute(
            "SELECT p.id AS planche_id, "
            "  (SELECT COUNT(*) FROM regions r WHERE r.planche_id = p.id "
            "   AND r.type = 'case') AS n "
            "FROM planches p WHERE p.album_id = ? AND p.role = 'recit'", (aid,))}
        recit = sorted((pid for pid, ed in ed_map.items() if ed is not None),
                       key=lambda pid: ed_map[pid])
        running = 0
        for pid in recit:
            global_offset[pid] = running
            running += counts.get(pid, 0)
        album_total[aid] = running

    out: dict[int, dict] = {}
    for rid in ids:
        r = regs.get(rid)
        if r is None or r["planche_id"] not in planches:
            continue
        ed = editorial.get(r["planche_id"])
        if ed is None:                                   # planche paratexte
            out[rid] = {"planche": None, "texte": "Paratexte"}
            continue
        aid = planches[r["planche_id"]]["album_id"]
        if r["type"] == "case":
            cr = case_rang.get(rid)
            out[rid] = {"planche": ed, "case": cr,
                        "global": global_offset.get(r["planche_id"], 0) + (cr or 0),
                        "total": album_total.get(aid),
                        "texte": f"pl.{ed} · c{cr}"}
        elif r["type"] in _TYPES_TEXTE and r["parent_id"] in case_rang:
            cr = case_rang[r["parent_id"]]
            br = bulle_rang.get(rid)
            out[rid] = {"planche": ed, "case": cr, "bulle": br,
                        "global": global_offset.get(r["planche_id"], 0) + cr,
                        "total": album_total.get(aid),
                        "texte": f"pl.{ed} · c{cr} · b{br}"}
        elif r["type"] in _TYPES_TEXTE:                  # bulle hors case
            out[rid] = {"planche": ed, "texte": f"pl.{ed} · hors-case"}
        else:
            out[rid] = {"planche": ed, "texte": f"pl.{ed}"}
    return out


# --------------------------------------------------------------------------- #
# Collections (palier supérieur — v14 ; cf. docs/dictionnaire-metadonnees.md)
# --------------------------------------------------------------------------- #
def collections(conn: sqlite3.Connection) -> list[dict]:
    """Toutes les collections, avec leur nombre d'albums. Ordre d'id (stable)."""
    return [dict(r) for r in conn.execute(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM collection_album ca WHERE ca.collection_id = c.id) "
        "AS nb_albums FROM collection c ORDER BY c.id")]


# Nom de la collection de repli (AUTH-2). L'identifier par son NOM plutôt que par une
# colonne ou un id figé est un choix de MODE D'ÉCHEC : si quelqu'un la renomme, le repli
# recrée une collection de repli — un seau visible et vide, sans conséquence. Une
# désignation par « plus petit id » aurait, elle, déversé des albums dans la collection
# d'étude de quelqu'un d'autre, silencieusement.
NOM_COLLECTION_DEFAUT = "Collection par défaut"


def nom_reserve(nom: str) -> bool:
    """Ce nom est-il celui de la collection de repli ?

    Il est LOAD-BEARING : `collection_par_defaut` désigne le repli PAR SON NOM. Tant que
    seul un accès shell permettait de renommer une collection, le seul mode d'échec était
    « quelqu'un renomme le repli », dont la conséquence est bénigne (un nouveau seau vide
    se recrée). AUTH-3 a ouvert le renommage à tout propriétaire, et rendu possible
    l'inverse : renommer SA collection avec ce nom-là capture les albums créés sans
    collection explicite — mesuré, un album d'administrateur y atterrit et devient visible
    de qui a fait le renommage. C'est précisément ce que le choix du nom voulait éviter.
    """
    return nom.strip().casefold() == NOM_COLLECTION_DEFAUT.casefold()


def collection_par_defaut(conn: sqlite3.Connection) -> int:
    """Id de la collection de repli, CRÉÉE si elle n'existe pas.

    Garantit l'invariant d'AUTH-2 : aucun album ne peut se retrouver hors de toute
    collection. La collection étant l'unité de cloisonnement, un album orphelin ne
    correspondrait à AUCUNE règle d'accès — il faudrait alors inventer une politique
    dans le code, à un endroit qu'on oublierait de relire. Ici, la question ne se pose
    jamais : il y a toujours une règle, quitte à ce qu'elle n'ouvre à personne.
    """
    r = conn.execute("SELECT id FROM collection WHERE nom = ?",
                     (NOM_COLLECTION_DEFAUT,)).fetchone()
    if r:
        return r[0]
    cur = conn.execute(
        "INSERT INTO collection (nom, description) VALUES (?, ?)",
        (NOM_COLLECTION_DEFAUT,
         "Créée automatiquement : tout album doit appartenir à une collection, qui est "
         "l'unité de cloisonnement des accès. Renommez-la et décrivez-la, ou déplacez "
         "ses albums vers des collections d'étude."))
    return cur.lastrowid


def albums_orphelins(conn: sqlite3.Connection) -> list[int]:
    """Albums n'appartenant à AUCUNE collection. Doit toujours être vide (AUTH-2) —
    c'est la formulation exécutable de l'invariant, utilisée par la migration et par
    le test qui le verrouille."""
    return [r[0] for r in conn.execute(
        "SELECT id FROM albums WHERE id NOT IN "
        "(SELECT album_id FROM collection_album)")]


def collection_row(conn: sqlite3.Connection, collection_id: int) -> dict | None:
    """Ligne descriptive d'une collection (dict), ou None si absente."""
    r = conn.execute("SELECT * FROM collection WHERE id = ?", (collection_id,)).fetchone()
    return dict(r) if r else None


def lexique_resume(conn: sqlite3.Connection, collection_id: int | None = None,
                   *, clause: tuple[str, list] | None = None) -> dict:
    """Indicateur « % défini » du lexique situé (A4, N7) : part des termes du vocabulaire
    ÉMERGENT (domaines + dimensions + valeurs + tags) à l'état `defini`. Scopé par APPARTENANCE
    si `collection_id` (global ⊕ local à la collection). Nourrit la qualité de la Collection.

    `clause` — AUTH-2 : fragment SQL de portée `(sql, params)` sur la colonne nue
    `collection_id`, fourni par l'appelant (`Portee.clause_terme`). Il généralise
    `collection_id` à PLUSIEURS collections lisibles. Ce module reçoit un fragment plutôt
    qu'une `Portee` pour ne pas dépendre de `autorisation` : la règle reste écrite à un
    seul endroit, et c'est là-bas.
    """
    if clause is not None:
        sql_scope, params = clause
        scope = f" AND ({sql_scope})"
        params = list(params)
    elif collection_id is None:
        scope, params = "", []
    else:
        scope, params = " AND (collection_id IS NULL OR collection_id = ?)", [collection_id]
    par_type, total, definis = {}, 0, 0
    for table, cle in (("domaine", "domaines"), ("attribut_dimension", "dimensions"),
                       ("attribut_valeur", "valeurs"), ("tags", "tags")):
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE 1=1{scope}", params).fetchone()[0]
        d = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE etat='defini'{scope}",
                         params).fetchone()[0]
        par_type[cle] = {"total": n, "definis": d}
        total += n
        definis += d
    return {"total": total, "definis": definis,
            "pct_defini": round(definis / total, 4) if total else None,
            "par_type": par_type}


def collection_album_ids(conn: sqlite3.Connection, collection_id: int) -> list[int]:
    """Ids des albums d'une collection, dans l'ordre de `rang` (composition citable)."""
    return [r[0] for r in conn.execute(
        "SELECT album_id FROM collection_album WHERE collection_id = ? "
        "ORDER BY rang, album_id", (collection_id,))]


def contributions_album(conn: sqlite3.Connection, album_id: int) -> list[dict]:
    """Contributions d'un album (nom + rôle résolu : label/bucket/marc), ordre de `rang`
    (N0, v15). Le rôle peut être NULL (contribution sans rôle attribué)."""
    return [dict(r) for r in conn.execute(
        "SELECT c.id, c.nom, c.rang, c.role_id, r.label AS role, r.bucket, r.marc "
        "FROM contribution c LEFT JOIN contribution_role r ON r.id = c.role_id "
        "WHERE c.album_id = ? ORDER BY c.rang, c.id", (album_id,))]


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


def _reancrer_corrections(conn: sqlite3.Connection, region_id: int, new_tokens: list) -> None:
    """Ré-ancre les corrections humaines après régénération des tokens auto, par
    ALIGNEMENT de séquences (difflib) entre l'ANCIENNE tokenisation (encore en base à
    cet instant) et la NOUVELLE (`new_tokens`). Cf. docs/correction-grammaticale.md §4.

    - un mot INCHANGÉ qui a seulement bougé de position → sa correction est re-mappée à
      son nouvel `ordre` (préservée, obsolete=0) ;
    - un mot réellement modifié/supprimé → sa correction devient orpheline (mise de
      côté à un `ordre` négatif, obsolete=1 ; conservée mais inerte — jamais perdue).

    → éditer le texte ne casse QUE les corrections des mots réellement touchés, pas
    toute la suite (fini la cascade)."""
    import difflib
    old = conn.execute("SELECT ordre, texte FROM tokens WHERE region_id = ? ORDER BY ordre",
                       (region_id,)).fetchall()
    old_ord = [r["ordre"] for r in old]
    new_ord = [t["ordre"] for t in new_tokens]
    new_forme = {t["ordre"]: t["texte"] for t in new_tokens}
    remap = {}                                  # ancien ordre -> nouvel ordre (mots alignés)
    sm = difflib.SequenceMatcher(a=[r["texte"] for r in old],
                                 b=[t["texte"] for t in new_tokens], autojunk=False)
    for a0, b0, size in sm.get_matching_blocks():
        for k in range(size):
            remap[old_ord[a0 + k]] = new_ord[b0 + k]

    corr = conn.execute("SELECT * FROM token_correction WHERE region_id = ?",
                        (region_id,)).fetchall()
    survivors, orphans, pris = [], [], set()
    for c in corr:
        no = remap.get(c["ordre"])
        if no is not None and no not in pris and new_forme.get(no) == c["forme"]:
            survivors.append((c, no)); pris.add(no)
        else:
            orphans.append(c)
    # réécriture propre (DELETE + réinsertion) → aucune collision d'UNIQUE possible
    conn.execute("DELETE FROM token_correction WHERE region_id = ?", (region_id,))
    ins = ("INSERT INTO token_correction "
           "(region_id, ordre, forme, lemme, pos, morph, etat, auteur, date_modif, obsolete) "
           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    for c, no in survivors:
        conn.execute(ins, (region_id, no, new_forme[no], c["lemme"], c["pos"], c["morph"],
                           c["etat"], c["auteur"], c["date_modif"], 0))
    park = -1                                   # ordres négatifs : ne rejoignent aucun token
    for c in orphans:
        conn.execute(ins, (region_id, park, c["forme"], c["lemme"], c["pos"], c["morph"],
                           c["etat"], c["auteur"], c["date_modif"], 1))
        park -= 1


def _appliquer_corrections(conn: sqlite3.Connection, region_id: int,
                           tokens: list, lemmes: str, reancrer: bool = True) -> str:
    """Couche de correction HUMAINE (cf. docs/correction-grammaticale.md §4-5). Si la
    région a des corrections, les ré-ancre par alignement (`_reancrer_corrections`) puis
    renvoie les lemmes FTS ENRICHIS des lemmes corrigés VIVANTS (→ la recherche reflète
    les corrections).

    `reancrer=False` quand la tokenisation auto n'est PAS fiable (moteur spaCy absent ou
    analyse échouée sur un texte non vide) : on ne ré-ancre alors PAS, pour ne jamais
    déplacer/invalider une correction sur la seule absence du moteur. L'ajout des lemmes
    corrigés au FTS reste fait (corrections cherchables même sans spaCy). Sans correction :
    `lemmes` inchangé (coût ≈ nul, cas courant)."""
    n = conn.execute("SELECT COUNT(*) AS n FROM token_correction WHERE region_id = ?",
                     (region_id,)).fetchone()["n"]
    if not n:
        return lemmes
    if reancrer:
        _reancrer_corrections(conn, region_id, tokens)
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
    import journal
    aid = journal.ouvrir_activite(conn, "reindex_nlp", agent="spacy", agent_type="moteur",
                                  version=(model_info().get("model") or None),
                                  params={"chunk": chunk})
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
    journal.cloturer_activite(conn, aid, comptes={"regions": n})
    conn.commit()
    return n


def unindex_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Retire une région de l'index FTS (suppression de région)."""
    conn.execute("DELETE FROM recherche WHERE region_id = ?", (region_id,))


if __name__ == "__main__":
    init_db()
    print(f"Base initialisée : {DB_PATH} (schéma v{SCHEMA_VERSION})")
