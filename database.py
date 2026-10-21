"""Initialisation SQLite, schéma, migrations et helpers de recherche.

La base est volontairement simple : un seul fichier SQLite, FTS5 pour la
recherche plein texte. La table FTS `recherche` est dénormalisée (elle agrège
le texte OCR, la note d'annotation et les tags) ; elle est maintenue
explicitement via `reindex_region()` / `unindex_region()` appelés depuis l'API,
plutôt que par des triggers (la relation N-N tags rend les triggers fragiles).
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import DB_PATH, STATUTS

# Version du schéma — incrémenter et ajouter une étape dans `_migrate()` à
# chaque changement structurel.
SCHEMA_VERSION = 34

# NLP-2 (v28) — ce que l'annotateur a VU en corrigeant : le modèle, et sa proposition.
# Une seule liste, lue par la migration ET par le ré-ancrage : celui-ci réinsère ses
# lignes colonne par colonne, et une colonne qu'il oublierait repartirait à NULL à chaque
# réindexation.
COLONNES_VU = ("modele_auto", "auto_lemme", "auto_pos", "auto_morph")

# AUTH-6 (2026-09-09) — les deux natures d'un compte, et la SEULE liste qui fasse foi.
# `nominatif` : une personne derrière un login, ce que suppose tout le raisonnement de
# provenance. `collectif` : un login partagé, décidé le 2026-09-09 pour les groupes
# d'étudiants, les stagiaires et les démos. La distinction ne borde AUCUN accès — un
# compte collectif écrit partout où ses accès le portent —, elle borde ce que les MESURES
# ont le droit d'affirmer ; et, depuis le fonds (COL-3, tranche 2), un seul GESTE : un
# compte collectif ne supprime jamais définitivement seul (`Portee.clause_suppression_directe`).
NATURE_NOMINATIF = "nominatif"
NATURE_COLLECTIF = "collectif"
NATURES = (NATURE_NOMINATIF, NATURE_COLLECTIF)


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
-- Des identifiants qui ne reviennent jamais (v30, COL-3 ; Hugo, 2026-10-15). `albums`,
-- `planches`, `regions` et `personnages` portent `AUTOINCREMENT` : sans lui SQLite REND
-- au suivant l'identifiant du dernier détruit, n'importe où dans le corpus. Le journal,
-- qui survit à sa cible et la désigne par son identifiant, mêlait alors deux objets : la
-- règle de suppression lisait l'acte d'un ancien album comme un travail sur une région
-- neuve, et Ctrl+Z écrivait à travers le cloisonnement (AUTH-14 l'a fermé à part). Une
-- base d'avant la v30 est reconstruite par `_reconstruire_avec_autoincrement`, compteur
-- amorcé au-dessus de tout identifiant que le journal a jamais nommé.
CREATE TABLE IF NOT EXISTS albums (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    titre        TEXT NOT NULL,
    auteur       TEXT,                       -- legacy (responsabilité à plat) → voir `contribution`
    annee        INTEGER,                    -- legacy (ambigu) → précisé par date_edition/date_originale
    editeur      TEXT,
    serie        TEXT,
    tome         TEXT,                       -- v33 : rang dans la série (« 1 », « HS », « Intégrale »), texte libre
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
    -- v34 (IMG-1, Hugo, 2026-10-21) : OÙ vivent les masters d'archive de l'album — ShareDocs,
    -- un disque local, des disques durs, « selon les projets et les personnes ». Champ libre,
    -- facultatif, humain : le serveur ne garde plus le scan reçu, seulement sa copie de
    -- travail, et n'impose aucun lieu. RETENU de toute sortie (`main._EXPORT_ALBUM_RETENUES`).
    lieu_masters TEXT,
    date_import  TEXT DEFAULT (datetime('now')),
    document_id  INTEGER REFERENCES document(id),
    projet_id    INTEGER REFERENCES projet(id)
    -- v30 (COL-3, tranche 2) — la ligne `albums` EST une COPIE DE TRAVAIL : tout le travail
    -- y pend par `planches`. Ces deux colonnes disent de QUOI elle est la copie, et OÙ.
    --
    -- `document_id` : le DOCUMENT dont elle est une copie (table `document`, plus bas) —
    -- ce qui appartient à l'instance et survit à ses copies. Depuis la tranche 3 un document
    -- peut avoir plusieurs copies SŒURS (`creer_copie`), et c'est par cette clé qu'elles se
    -- savent sœurs.
    --
    -- `projet_id` : le projet de la copie, ÉCRIT sur elle. Tant qu'elle est rangée, il se
    -- lit aussi dans ses collections — un rangement ne traverse pas les projets. Mais une
    -- copie retirée de toute collection n'aurait plus aucun projet à lire, et rien ne
    -- refuserait alors de la ranger dans un autre : c'est ce que la colonne garde. NULL se
    -- lit « celui de ses collections », à un seul endroit (`sql_projet_d_album`) ; NULL sans
    -- collection veut dire que la copie n'a JAMAIS eu de projet, pas qu'elle est du repli.
    --
    -- Toutes deux NULLABLES et à clé SANS action, pour les deux raisons de
    -- `collection.projet_id` : SQLite n'ajoute pas par ALTER une colonne NOT NULL qui porte
    -- une clé étrangère, et seize INSERT de huit fichiers de test posent un album sans rien
    -- nommer. Ni `SET NULL` — supprimer un projet détacherait ses copies gardées sans que
    -- personne l'ait décidé —, ni `CASCADE`, qui effacerait du travail par ricochet.
    --
    -- Ces commentaires sont SOUS les deux colonnes, et aucun ne les sépare : pour retirer
    -- la dernière colonne d'une table, SQLite remonte jusqu'à la première virgule qu'il
    -- trouve, celles d'un commentaire comprises (cf. `collection.projet_id`). Un
    -- commentaire posé ENTRE elles rend « incomplete input » au test qui défait la v30.
);

CREATE TABLE IF NOT EXISTS planches (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id           INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    numero             INTEGER NOT NULL,             -- ordre d'import (clé de tri, peut avoir des trous)
    role               TEXT NOT NULL DEFAULT 'recit', -- 'recit' = narratif (numéroté) ; autre = paratexte (écarté)
    -- `chemin_tiff` : la COPIE DE TRAVAIL depuis la v34 (IMG-1) — un JPEG à 300 dpi
    -- effectifs, à la géométrie du scan ; le nom de la colonne date d'avant, quand le
    -- serveur gardait le fichier reçu. Une planche importée avant la v34 et pas encore
    -- rattrapée (`tools/convertir_en_copies_de_travail.py`) y désigne encore son master.
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
    -- v34 (IMG-1) : ce que l'outil sait du master d'archive, qui ne vit plus sur le serveur
    -- — `sharedocs:<chemin distant>` pour un import ShareDocs, sinon le nom du fichier reçu.
    -- NON NULL veut aussi dire que `chemin_tiff` est une copie de travail et non le scan :
    -- NULL, la planche date d'avant la v34 et n'a pas été convertie. RETENU de toute sortie.
    master_origine     TEXT,
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
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
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
    -- v28 (NLP-2) : ce que l'annotateur a VU. `modele_auto` = le modèle chargé au moment
    -- du geste, même identifiant que `meta.nlp_model` (version comprise) ; `auto_*` = sa
    -- proposition telle qu'elle s'affichait, '' quand il n'en avait pas. Un champ de
    -- correction NULL veut dire « j'accepte CETTE proposition », pas celle du prochain
    -- modèle. Tout à NULL = correction antérieure à la v28, qui n'a rien gardé.
    modele_auto TEXT,
    auto_lemme  TEXT,
    auto_pos    TEXT,
    auto_morph  TEXT,
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
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    serie          TEXT,
    notes          TEXT,
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- Lien LOCUTEUR : quelle entité parle dans cette zone de texte (au plus une → region_id
-- PK). La table s'appelle `bulle_locuteur` parce qu'une bulle était seule à parler ;
-- depuis ANN-6 un cartouche et une zone de texte reçoivent un locuteur aussi
-- (`config.TYPES_LOCUTEUR`, tenu par la route — pas par une contrainte de schéma).
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
    -- Référent d'EXPLOITATION (v25, AUTH-4) : à qui s'adresser pour cette collection.
    -- DISTINCT de `responsables`, qui est SCIENTIFIQUE — il porte un ORCID et il part dans
    -- les notices DataCite/Nakala, où une adresse d'exploitation n'a rien à faire. Les
    -- mélanger obligerait à filtrer un rôle à CHAQUE export, et un filtre oublié quelque
    -- part est une fuite silencieuse.
    referent_nom      TEXT,                          -- nom lisible (pas un login : on écrit à une personne)
    referent_contact  TEXT,                          -- email ou URL — le moyen de LUI ÉCRIRE
    date_debut        TEXT,                          -- période de constitution / couverture
    date_fin          TEXT,
    date_creation     TEXT DEFAULT (datetime('now')),
    projet_id         INTEGER REFERENCES projet(id),
    base              INTEGER NOT NULL DEFAULT 0,
    acces_membres     TEXT
    -- v29 (COL-3) : `projet_id`, le PROJET auquel la collection appartient. NULLABLE, et NULL se lit
    -- « le projet de repli » — à un seul endroit, `sql_projet_de`. Deux raisons, mesurées :
    -- SQLite refuse d'AJOUTER une colonne `NOT NULL` qui porte une clé étrangère (un défaut
    -- non nul est exigé par l'un, interdit par l'autre), si bien qu'une base migrée ne
    -- pourrait pas porter la contrainte qu'une base neuve porterait ; et deux schémas qui
    -- divergent sur une garde valent moins qu'une règle unique dans le code (même doctrine
    -- que `utilisateur.nature`). Clé SANS action : ni `SET NULL` — supprimer un projet
    -- reverserait ses collections dans le repli sans que personne l'ait décidé —, ni
    -- `CASCADE`, qui laisserait des albums hors de toute collection.
    --
    -- v31 (COL-3, tranche 3, D10 — Hugo, 2026-10-17) : la COLLECTION DE BASE d'un projet.
    -- `base` = 1 désigne la seule collection de base de son projet : un DRAPEAU et jamais un
    -- nom, comme le projet de repli — elle se renomme, ne se supprime pas, ne change pas de
    -- projet, et aucune route ne pose ni n'ôte le drapeau. Tout projet naît avec elle,
    -- NEUVE et vide — le projet de repli comme les autres : aucune collection existante ne
    -- devient une base, ni la « Collection par défaut » (Hugo, 2026-10-17). Les RESPONSABLES du projet en sont propriétaires, et ses MEMBRES y entrent
    -- au niveau `acces_membres` — les deux DÉRIVÉS de `projet_acces` par
    -- `autorisation.Portee`, jamais recopiés dans `collection_acces`.
    -- `acces_membres` : un NIVEAU parmi ceux de `collection_acces` — 'ecriture' ou
    -- 'lecture' —, NULL = protégée (les membres n'y entrent pas). Sans `CHECK`, pour la
    -- raison écrite sur `utilisateur.nature` : la liste vit dans
    -- `autorisation.ACCES_MEMBRES`. Sans effet hors d'une base.
    -- Une seule base par projet : tenu par le code (`collection_de_base`) et non par un
    -- index partiel, qui nommerait `projet_id` et empêcherait de retirer la colonne — ce que
    -- des tests font pour rejouer la v29.
    --
    -- Ces commentaires sont SOUS la dernière colonne, et aucun ne s'intercale entre les
    -- trois dernières : pour retirer la dernière colonne d'une table, SQLite remonte jusqu'à
    -- la première virgule qu'il trouve — celles d'un commentaire comprises — et rend alors un
    -- schéma tronqué (« incomplete input », mesuré sur 3.49 par les tests de migration, qui
    -- défont des versions de cette façon).
);

-- PROJET (v29, COL-3) — l'étage AU-DESSUS des collections : le périmètre à l'intérieur
-- duquel un travail PEUT se partager. Une collection appartient à UN projet. Il n'ouvre ni
-- ne ferme aucune collection, que seule `collection_acces` règle — à une exception près
-- depuis la v31 (D10) : sa collection de BASE (`collection.base`), dont ses responsables
-- sont propriétaires et où ses membres entrent au niveau `collection.acces_membres`.
--
-- `repli` désigne LE projet où tombe une collection qui n'en nomme aucun — tout l'existant
-- au jour de la migration. Un drapeau et non un nom : ce projet-là est fait pour être
-- renommé, là où la collection de repli se désigne par un nom réservé. Mode d'échec choisi :
-- la ligne retirée à la main, un projet neutre et vide renaît au prochain besoin ; « le plus
-- petit id » aurait déversé des collections dans le projet de quelqu'un, sans bruit.
--
-- `justification` : pourquoi ce projet existe, en texte libre — scientifique d'abord. Elle
-- ne se rend qu'à qui gère le projet (`routes/projets.py`), jamais à ses simples membres.
--
-- `AUTOINCREMENT` depuis la v31 (COL-3, tranche 3, D8) : un projet d'origine pourra être
-- supprimé sous un document vivant, et un identifiant rendu au projet suivant ferait
-- désigner à `demande.projet_id`, à `document.projet_origine_id` et au journal un autre
-- projet que le leur. Une base v30 est reconstruite par `_reconstruire_avec_autoincrement`.
CREATE TABLE IF NOT EXISTS projet (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    description    TEXT,
    justification  TEXT,
    repli          INTEGER NOT NULL DEFAULT 0,     -- 1 = le projet de repli
    date_creation  TEXT DEFAULT (datetime('now'))
);

-- QUI EST D'UN PROJET (v29, COL-3) — le patron de `collection_acces`, un étage plus haut :
-- un NOM (login, ou groupe tel que `Remote-Groups` le pose) et un rôle. Toujours une
-- RÉFÉRENCE, jamais une appartenance (invariant AUTH-1). Pas de `CHECK` sur `role`, pour la
-- raison écrite sur `utilisateur.nature` : la liste vit dans `autorisation.ROLES_PROJET`,
-- et un rôle inconnu s'y lit `membre`.
CREATE TABLE IF NOT EXISTS projet_acces (
    projet_id      INTEGER NOT NULL REFERENCES projet(id) ON DELETE CASCADE,
    genre          TEXT NOT NULL,       -- 'utilisateur' | 'groupe'
    principal      TEXT NOT NULL,       -- login, ou nom de groupe Remote-Groups
    role           TEXT NOT NULL,       -- 'membre' | 'responsable'
    date_creation  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (projet_id, genre, principal)
);
-- « De quels projets est CE principal » se demande à chaque requête, comme pour les accès.
CREATE INDEX IF NOT EXISTS idx_projet_acces_principal ON projet_acces(genre, principal);

-- DOCUMENT (v30, COL-3, tranche 2) — ce qui appartient à l'INSTANCE et survit à ses copies
-- de travail : une identité, et une ORIGINE. Tout le reste vit ailleurs — la notice et le
-- travail sur la copie (`albums`), les scans par elle (`planches`), les emplois dans
-- `collection_album`. Le FONDS n'est pas une table : c'est l'ensemble de ces lignes, dont
-- certaines ne sont appelées par aucune collection.
--
-- `AUTOINCREMENT`, comme les copies, leurs planches, leurs régions et les personnages
-- (cf. la tête de ce schéma) : sans lui SQLite REND au suivant l'identifiant du dernier
-- détruit (mesuré), et le journal, qui survit à sa cible, mêlerait alors l'histoire de
-- deux documents.
--
-- `importe_par` : le LOGIN de qui a importé. NULL = on ne sait pas — tout album d'avant la
-- v30, dont l'import n'a été écrit nulle part, et tout import en mono-poste, où personne ne
-- s'annonce. La migration n'en invente aucun.
-- `projet_origine_id` : le projet où le document est entré d'abord. Un FAIT d'origine, donc
-- SANS clé étrangère, comme `evenement.cible_id` : il doit survivre au projet supprimé.
-- NULL = entré sans projet.
--
-- `projet_origine_nom` (v31, COL-3, tranche 3, D8) : le NOM de ce projet, écrit À
-- L'IMPORT. La tranche 3 fait naître des copies dans d'autres projets que celui d'origine,
-- qui pourra donc être supprimé sous un document vivant ; et `projet.id` se réattribuait
-- jusqu'à la v31. Le fonds dit l'origine par ce nom, plus par une jointure. Pour tout
-- document d'avant la v31, c'est le nom que portait le projet LE JOUR DE LA MIGRATION, pas
-- celui du jour de l'import, que rien n'avait gardé ; NULL si le projet n'existait plus.
CREATE TABLE IF NOT EXISTS document (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    importe_par        TEXT,
    importe_le         TEXT DEFAULT (datetime('now')),
    projet_origine_id  INTEGER,
    projet_origine_nom TEXT
);

-- COPIE (v31, COL-3, tranche 3) — la PROVENANCE de chaque copie de travail : qui l'a créée,
-- quand, d'où, et jusqu'à quel cran. Une ligne par album. Hors d'`albums`, et pas par
-- confort : trois réponses de l'API rendent `a.*` (`list_albums`, `create_album`,
-- `update_album`), et un login posé sur `albums` partirait à toute lectrice. Aucune route ne
-- la rend en entier.
--
-- `creee_par` : le LOGIN de qui a créé CETTE copie — c'est elle que lit la règle de
-- suppression directe (`autorisation.Portee.clause_suppression_directe`). NULL = on ne sait
-- pas : la copie d'origine d'un document d'avant la v30, et tout ce que crée le mono-poste.
-- Pour une copie d'ORIGINE, c'est l'importateur du document.
-- `cran` : 'origine' (la copie née avec son document), 'images' (une copie vierge, née d'un
-- document qui existait déjà) ; la 3b ajoutera les crans suivants. Pas de `CHECK`, pour la
-- raison écrite sur `utilisateur.nature`.
-- `depuis_album_id` : la copie dont celle-ci a été tirée — SANS clé étrangère, la source
-- peut mourir avant elle, comme `evenement.cible_id`. `depuis_projet_nom` : le nom de son
-- projet ce jour-là, pour la raison de `demande.projet_nom`.
CREATE TABLE IF NOT EXISTS copie (
    album_id           INTEGER PRIMARY KEY REFERENCES albums(id) ON DELETE CASCADE,
    creee_par          TEXT,
    creee_le           TEXT DEFAULT (datetime('now')),
    depuis_album_id    INTEGER,
    cran               TEXT NOT NULL DEFAULT 'origine',
    depuis_projet_nom  TEXT
);

-- REGION_ORIGINE (v32, COL-3, tranche 3b, E2) — ce qu'une région COPIÉE doit à une région
-- source : une copie amorcée jusqu'à un cran (« en partir ») recopie les régions de sa
-- source sous des identifiants neufs, et aucun événement du journal ne les nomme (E3 :
-- recopier les actes les ferait remonter par Ctrl+Z et compter deux fois). C'est par cette
-- table que le travail copié reste celui de ses auteurs. `region_source_id` est la source
-- DIRECTE, SANS clé étrangère — elle peut mourir avant la copie, et le journal qui la nomme
-- lui survit ; une copie de copie remonte la chaîne. Elle ne tient que parce que les
-- identifiants de région ne reviennent plus (v30). Aucune route ne la rend, rien ne la sort.
CREATE TABLE IF NOT EXISTS region_origine (
    region_id         INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    region_source_id  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_region_origine_source ON region_origine(region_source_id);

-- DEMANDE (v30, COL-3, tranche 2) — UN mécanisme pour ce qui ne se fait pas seul : qui
-- demande, quand, pourquoi ; puis qui répond, quand, quoi. Aucune messagerie. Les deux
-- tables naissent avec le document pour que le schéma ne change qu'UNE fois dans la
-- tranche ; AUCUNE ligne n'y est écrite tant que les routes de demande n'existent pas.
--
-- Pas de `CHECK` sur `genre` ni sur `reponse`, pour la raison écrite sur
-- `utilisateur.nature` : les listes vivent dans le code. `reponse` NULL = en attente. Une
-- demande répondue RESTE : c'est ce qui permet de dire qu'une demande a déjà été refusée.
-- `certifie_le` : quand le demandeur a certifié que les données posées sur le document ne
-- sont pas importantes — une case du formulaire, exigée par la route pour une suppression
-- de document (Hugo, 2026-10-15). NULL pour une demande qui ne la demande pas (un projet,
-- qui ne se supprime que vide). Qui a certifié est le demandeur : la colonne ne le recopie
-- pas.
-- `demandeur` est un login ; il est nullable pour qu'une demande venue de quelqu'un qui
-- n'a pas de compte puisse un jour s'y ranger sans reconstruire la table.
-- `projet_id` : le projet concerné — celui de la copie, ou celui qu'on demande de
-- supprimer. Sans clé étrangère : la demande survit à ce qu'elle a fait disparaître.
-- `projet_nom` : son NOM au jour de la demande. Il le faut, parce que `projet.id` se
-- réattribue (mesuré : un projet supprimé rend son identifiant au suivant) et qu'une
-- demande répondue reste : accepter la suppression d'un projet ferait désigner à sa propre
-- demande le projet créé ensuite. C'est la raison de `demande_document.titre`, un étage
-- plus haut. L'identifiant sert tant que le projet vit, le nom dit de quoi l'on parlait.
-- `collection_id`, `collection_nom` (v31, COL-3, tranche 3) : la collection d'ARRIVÉE d'une
-- entrée de documents ou d'un « rejoindre », sans clé étrangère ; le nom pour la raison de
-- `projet_nom` — l'identifiant d'une collection se réattribue (mesuré en tranche 2).
CREATE TABLE IF NOT EXISTS demande (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    genre          TEXT NOT NULL,
    demandeur      TEXT,
    motif          TEXT,
    certifie_le    TEXT,
    projet_id      INTEGER,
    projet_nom     TEXT,
    date_creation  TEXT DEFAULT (datetime('now')),
    reponse        TEXT,
    repondu_par    TEXT,
    date_reponse   TEXT,
    collection_id  INTEGER,
    collection_nom TEXT,
    cran           TEXT
    -- `cran` (v32, COL-3, tranche 3b) : le cran demandé d'une copie AMORCÉE (« en partir »)
    -- ou d'une remise à zéro (« repartir »), parmi ceux de `copie.cran` ; NULL pour tout
    -- autre genre. Commentaire SOUS la colonne : c'est la dernière de la table (cf. celui
    -- de `collection.projet_id`).
);

-- Les DOCUMENTS d'une demande — plusieurs dès maintenant, pour qu'une entrée de documents
-- en porte autant qu'on en coche. `document_id` SANS clé étrangère : la demande survit au
-- document détruit. `album_id` est la copie d'où le geste est parti et `titre` son titre
-- ce jour-là — l'album détruit ne se lit plus (et son identifiant se réattribuait avant la
-- v30) : sans le titre, une demande répondue ne dirait plus de quoi elle parlait. `reponse` : la réponse document par document, pour
-- une demande acceptée en partie. `copie_id` (v31) : la copie NÉE de l'acceptation d'une
-- entrée de documents, sans clé étrangère — ce qui dit, une fois la demande répondue, où le
-- document est entré.
CREATE TABLE IF NOT EXISTS demande_document (
    demande_id   INTEGER NOT NULL REFERENCES demande(id) ON DELETE CASCADE,
    document_id  INTEGER NOT NULL,
    album_id     INTEGER,
    titre        TEXT,
    reponse      TEXT,
    copie_id     INTEGER,
    PRIMARY KEY (demande_id, document_id)
);
-- « Ce document a-t-il une demande en attente » se pose album par album ; la clé primaire
-- ne couvre que l'autre sens.
CREATE INDEX IF NOT EXISTS idx_demande_document_document ON demande_document(document_id);

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
    niveau         TEXT NOT NULL,       -- 'lecture' | 'ecriture' | 'proprietaire'
    -- v27 (DROIT-2) : le droit de SORTIR le contenu, posé À CÔTÉ du niveau et non
    -- dedans, parce qu'exporter ne s'ordonne pas avec annoter. Faux par défaut ; un
    -- propriétaire exporte d'office, sans que la case soit posée (`autorisation.Portee`).
    exporter       INTEGER NOT NULL DEFAULT 0,
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
-- Les GROUPES ne sont volontairement PAS stockés : ils vivent dans l'annuaire LLDAP depuis
-- la bascule du 2026-09-07 (AUTH-7) — `deploy/authelia/users_database.yml` n'en est plus
-- que le REPLI — et sont relus dans `Remote-Groups` à chaque requête. Les figer en base
-- créerait une seconde source de vérité, et retirer quelqu'un d'un groupe n'aurait aucun
-- effet tant qu'on n'aurait pas aussi touché la base.
--
-- La ligne existe pour que d'autres chantiers aient une identité STABLE à référencer : le
-- propriétaire d'une collection (AUTH-3) et la nature du compte (AUTH-6, colonne
-- ci-dessous). INFRA-3 l'avait aussi prévue pour des identifiants WebDAV chiffrés par
-- personne, et a tranché le 2026-09-10 de ne rien persister. Elle n'est PAS une table de
-- droits.
CREATE TABLE IF NOT EXISTS utilisateur (
    login          TEXT PRIMARY KEY,               -- identifiant Authelia (en-tête Remote-User)
    nom            TEXT,                           -- Remote-Name : nom affiché
    email          TEXT,                           -- Remote-Email
    premiere_vue   TEXT DEFAULT (datetime('now')), -- première requête vue de cette personne
    derniere_vue   TEXT,                           -- dernière requête vue
    -- v26 (AUTH-6) — 'nominatif' | 'collectif'. Un login PARTAGÉ par plusieurs personnes
    -- est décidé le 2026-09-09, et il n'est pas un compte comme les autres : deux
    -- mécanismes cessent de dire vrai dessus, et tous deux échouent EN SILENCE. L'accord
    -- inter-annotateurs (ANN-5) ne voit pas deux personnes qui se relisent sous le même
    -- login — sa condition est `agent_précédent != agent` —, si bien que ces révisions
    -- disparaissent de l'échantillon au lieu d'être comptées ; et la pseudonymisation de
    -- sortie fondrait le groupe dans un `annotateur-N` que rien ne distingue d'une
    -- personne. La colonne existe pour que ces deux-là puissent REFUSER plutôt que rendre
    -- un chiffre.
    --
    -- Elle est POSÉE par un administrateur, jamais devinée : l'application ne peut pas
    -- savoir combien de personnes tapent derrière un login (elle ne voit que
    -- `Remote-User`), et une heuristique — « beaucoup d'actes », « connexions
    -- simultanées » — se tromperait un jour sans le dire.
    --
    -- Pas de contrainte CHECK, et c'est délibéré : SQLite ne sait pas en ajouter une par
    -- ALTER, donc une base MIGRÉE ne la porterait pas et une base NEUVE si. Deux schémas
    -- qui divergent sur une garde valent moins qu'une garde unique dans le code —
    -- `database.NATURES`, lu par la route ET par le test.
    nature         TEXT NOT NULL DEFAULT 'nominatif'
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
-- idx_val_collection / idx_tags_collection / idx_dim_domaine. Même règle pour
-- `collection.projet_id` (v29) : idx_collection_projet ; et pour `albums.document_id` et
-- `albums.projet_id` (v30) : idx_albums_document, idx_albums_projet.
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

    # --- v25 : le référent d'exploitation d'une collection (AUTH-4) -------------------
    # Deux colonnes plutôt qu'un JSON : il y a UN référent par collection, et un nom
    # lisible plus un moyen de contact se lisent et se modifient mieux à plat qu'en
    # sérialisé. Rien à recoller — le champ naît vide, et vide il signifie « aucun référent
    # déclaré », ce qui est la vérité de toute collection existante.
    # La garde porte sur la TABLE **et** sur la colonne. La v24 met en garde contre la
    # garde de table seule ; l'inverse est tout aussi faux — `PRAGMA table_info` sur une
    # table absente rend une liste vide, donc « colonne manquante », donc un ALTER sur
    # rien. Les tests de migration montent des schémas MINIMAUX où `collection` n'existe
    # pas : c'est là que ça casse, et nulle part ailleurs.
    _tables = {r["name"] for r in
               conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "collection" in _tables and "referent_nom" not in {
            r["name"] for r in conn.execute("PRAGMA table_info(collection)")}:
        conn.execute("ALTER TABLE collection ADD COLUMN referent_nom TEXT")
        conn.execute("ALTER TABLE collection ADD COLUMN referent_contact TEXT")

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

    # v25 → v26 : nature du compte (AUTH-6). ALTER simple, valeur par défaut `nominatif` —
    # c'est ce que toutes les lignes existantes SONT, l'instance n'ayant eu que des comptes
    # personnels jusqu'ici (mesuré le 2026-09-07 : `chercheur` et `stagiaire`). Défaut
    # RÉTROACTIF plutôt que NULL : une nature inconnue obligerait chaque lecteur à décider
    # quoi en faire, et le premier qui traiterait NULL comme « pas collectif » réintroduirait
    # exactement le silence que cette colonne ferme. Aucun index : la table se lit par clé
    # primaire, et la nature ne sert qu'en jointure sur des lots minuscules.
    ucols = {r["name"] for r in conn.execute("PRAGMA table_info(utilisateur)")}
    if ucols and "nature" not in ucols:
        conn.execute("ALTER TABLE utilisateur ADD COLUMN nature TEXT NOT NULL "
                     f"DEFAULT '{NATURE_NOMINATIF}'")

    # v26 → v27 : le droit d'exporter (DROIT-2), une colonne à côté du niveau. FAUX par
    # défaut, et c'est un changement de COMPORTEMENT autant que de schéma : jusqu'ici,
    # toute personne qui lisait une collection pouvait en sortir le contenu. Après la
    # migration, seuls ses propriétaires le peuvent, jusqu'à ce qu'ils cochent la case
    # pour d'autres — décidé le 2026-09-11 (« l'export reste quelque chose de
    # particulièrement sensible »). AUCUN rattrapage : ouvrir d'office à qui lisait
    # reconduirait exactement l'état que le chantier ferme.
    acols = {r["name"] for r in conn.execute("PRAGMA table_info(collection_acces)")}
    if acols and "exporter" not in acols:
        conn.execute("ALTER TABLE collection_acces ADD COLUMN exporter INTEGER NOT NULL "
                     "DEFAULT 0")

    # v27 → v28 : ce que l'annotateur a VU (NLP-2). Un champ de correction NULL veut dire
    # « j'accepte la proposition du modèle » — mais la proposition n'était pas gardée, et
    # le rapport d'accord la relisait dans `tokens`, que chaque réindexation régénère.
    # Après un passage à un autre modèle, un mot validé sous l'ancien comptait donc comme
    # un accord avec le nouveau, dont personne n'avait vu la proposition. Décidé le
    # 2026-09-11 : garder le modèle ET sa proposition, pas le nom seul. AUCUN rattrapage —
    # relire `tokens` aujourd'hui serait DEVINER ce qui s'affichait hier : retoucher le
    # texte ailleurs dans la bulle change l'étiquette d'un mot inchangé, et sa correction
    # survit au ré-ancrage. NULL dit « on ne sait pas », et le rapport retombe alors sur
    # sa lecture d'avant, pour ces seules lignes.
    tccols = {r["name"] for r in conn.execute("PRAGMA table_info(token_correction)")}
    for col in COLONNES_VU:
        if tccols and col not in tccols:
            conn.execute(f"ALTER TABLE token_correction ADD COLUMN {col} TEXT")

    # v28 → v29 : le PROJET, étage au-dessus des collections (COL-3, tranche 1). Tables
    # `projet` et `projet_acces` NOUVELLES (SCHEMA_SQL) ; `collection.projet_id` posée par
    # PRÉSENCE, nullable (cf. le commentaire de la colonne). Garde de TABLES : les tests de
    # migration montent des schémas minimaux, dont un `collection (id, nom)` sans rien autour.
    _tables = {r["name"] for r in
               conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if {"collection", "projet", "projet_acces"} <= _tables:
        if "projet_id" not in _cols("collection"):
            conn.execute("ALTER TABLE collection ADD COLUMN projet_id INTEGER "
                         "REFERENCES projet(id)")
        # Index créé ICI, après l'ALTER (cf. le NB de SCHEMA_SQL).
        conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_projet "
                     "ON collection(projet_id)")
        # Migration de DONNÉES, donc gatée par la VERSION : rejouée à chaque démarrage, elle
        # referait membre du premier projet quiconque en a été sorti. « L'instance d'hier
        # est, sans rien y changer, le premier projet » : toutes les collections y entrent,
        # et qui avait un accès à l'une d'elles — compte ou groupe — en devient MEMBRE.
        # Aucun responsable n'est désigné : c'est un choix, que la migration ne devine pas.
        # Une photographie du jour : un accès accordé plus tard ne fait pas entrer au projet.
        # Le rôle est écrit en LITTÉRAL : une migration est de l'histoire, elle ne doit pas
        # changer de sens le jour où `autorisation.ROLES_PROJET` change de mots.
        if version < 29:
            pid = projet_par_defaut(conn)
            conn.execute("UPDATE collection SET projet_id = ? WHERE projet_id IS NULL",
                         (pid,))
            if "collection_acces" in _tables:
                conn.execute(
                    "INSERT OR IGNORE INTO projet_acces (projet_id, genre, principal, role) "
                    "SELECT DISTINCT ?, genre, principal, 'membre' FROM collection_acces",
                    (pid,))

    # v29 → v30 : le DOCUMENT (COL-3, tranche 2). Tables `document`, `demande` et
    # `demande_document` NOUVELLES (SCHEMA_SQL) ; `albums.document_id` et `albums.projet_id`
    # posées par PRÉSENCE, nullables (cf. leur commentaire), dans l'ordre du schéma neuf.
    # Garde de TABLES : neuf fichiers de test montent un `albums (id, titre)` minimal avant
    # d'appeler `_migrate`, sans `document` ni `projet` autour.
    _tables = {r["name"] for r in
               conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if {"albums", "document", "projet"} <= _tables:
        for colonne, cible in (("document_id", "document"), ("projet_id", "projet")):
            if colonne not in _cols("albums"):
                conn.execute(f"ALTER TABLE albums ADD COLUMN {colonne} INTEGER "
                             f"REFERENCES {cible}(id)")
        # Index créés ICI, après les ALTER (cf. le NB de SCHEMA_SQL).
        conn.execute("CREATE INDEX IF NOT EXISTS idx_albums_document ON albums(document_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_albums_projet ON albums(projet_id)")
        # Migration de DONNÉES, donc gatée par la VERSION. Chaque album d'hier devient
        # l'unique copie d'un document neuf. Rejouée à l'upgrade suivant, elle donnerait un
        # document « d'avant le fonds » à un album né APRÈS sans le sien — c'est-à-dire
        # qu'elle maquillerait en origine inconnue la faute d'un chemin d'écriture, que
        # `albums_sans_document` est là pour dire.
        #
        # Elle est en plus IDEMPOTENTE, et il le faut : plusieurs tests ramènent
        # `user_version` en arrière sur une base au schéma courant pour rejouer un upgrade
        # réel, et l'étape repasse alors sur des albums qui ont déjà leur document. Elle ne
        # touche donc que ce qui est NULL.
        if version < 30:
            # Le projet d'abord, lu dans les collections. Il est exact pour un album dont
            # toutes les collections sont du même projet — ce que les routes garantissent
            # depuis la v29, aucun rangement ne traversant deux projets. Un album rangé nulle
            # part — base retouchée à la main — garde NULL : on ne lui en invente pas.
            #
            # Ce que la migration ne sait PAS trancher : un album rangé dans DEUX projets,
            # état interdit mais qu'une base retouchée peut porter. Elle lui écrit le projet
            # de sa collection de plus petit id, ce qui est un CHOIX et non un fait. L'écrire
            # vaut mieux que se taire : c'est cette écriture qui rend l'écart visible —
            # `albums_hors_de_leur_projet` le nomme dès le premier démarrage, là où un NULL
            # l'aurait laissé se lire « du projet de ses collections » sans dire lequel. À
            # contrôler après migration : la liste doit être vide, et sinon chaque album
            # nommé est à sortir à la main des collections qui ne sont pas de son projet.
            if ("collection_album" in _tables
                    and "projet_id" in _cols("collection")):
                conn.execute(
                    "UPDATE albums SET projet_id = "
                    f"({_sql_projet_des_collections('albums')}) WHERE projet_id IS NULL")
            # Puis l'origine, avec ce qu'on SAIT : la date d'import de l'album, et le projet
            # où il vit. QUI a importé n'a jamais été écrit, donc ne s'écrit pas ici — ni
            # deviné dans le journal, dont le premier acte sur une région est un indice et
            # pas un fait. Une date d'import absente reste absente : la valeur est passée
            # telle quelle, le défaut de la colonne ne la remplace pas.
            date = "date_import" if "date_import" in _cols("albums") else "NULL"
            for album_id, date_import, projet_id in conn.execute(
                    f"SELECT id, {date}, projet_id FROM albums "
                    "WHERE document_id IS NULL ORDER BY id").fetchall():
                cur = conn.execute(
                    "INSERT INTO document (importe_par, importe_le, projet_origine_id) "
                    "VALUES (NULL, ?, ?)", (date_import, projet_id))
                conn.execute("UPDATE albums SET document_id = ? WHERE id = ?",
                             (cur.lastrowid, album_id))

    # v29 → v30, suite : des identifiants qui ne reviennent jamais (Hugo, 2026-10-15). Gardée
    # par la VERSION — une reconstruction de table n'est pas une étape qu'on rejoue à chaque
    # démarrage — et IDEMPOTENTE, parce que des tests ramènent `user_version` en arrière sur
    # une base déjà au schéma courant : une table qui porte déjà `AUTOINCREMENT` n'est pas
    # touchée, et une base neuve, née du schéma courant, n'a donc rien à faire ici.
    if version < 30:
        _reconstruire_avec_autoincrement(conn)

    # v30 → v31 : prendre un document (COL-3, tranche 3). Table `copie` NOUVELLE
    # (SCHEMA_SQL) ; des colonnes posées par PRÉSENCE, dans l'ordre du schéma neuf, chacune
    # gardée par sa TABLE — des tests montent des schémas minimaux sans elles. Sans
    # comportement par elles-mêmes : `demande.collection_id`/`collection_nom` et
    # `demande_document.copie_id` attendent les demandes d'entrée et de « rejoindre », et
    # `collection.base`/`acces_membres` la collection de base (D10).
    _tables = {r["name"] for r in
               conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for table, colonnes in (
            ("collection", (("base", "INTEGER NOT NULL DEFAULT 0"), ("acces_membres", "TEXT"))),
            ("document", (("projet_origine_nom", "TEXT"),)),
            # v32 → v33 : `albums.tome`, le rang de l'album dans sa série. Texte libre (« 1 »,
            # « HS », « Intégrale ») ; NULL pour tout l'existant, aucune donnée à migrer.
            # v33 → v34 (IMG-1) : `albums.lieu_masters`, où vivent les masters d'archive
            # (libre, facultatif) ; `planches.master_origine`, ce que l'outil sait du master
            # d'une planche. NULL pour tout l'existant : rien n'est déduit, et une planche
            # d'avant garde son master jusqu'au rattrapage, qui écrit la colonne.
            ("albums", (("tome", "TEXT"), ("lieu_masters", "TEXT"))),
            ("planches", (("master_origine", "TEXT"),)),
            # v31 → v32 (COL-3, tranche 3b) : `demande.cran`, le cran d'une copie amorcée
            # ou d'une remise à zéro demandée. Table `region_origine` NOUVELLE (SCHEMA_SQL) ;
            # aucune migration de données — aucune copie d'avant la v32 n'a recopié de région.
            ("demande", (("collection_id", "INTEGER"), ("collection_nom", "TEXT"),
                         ("cran", "TEXT"))),
            ("demande_document", (("copie_id", "INTEGER"),))):
        if table not in _tables or (table == "collection" and "projet" not in _tables):
            continue
        for colonne, sorte in colonnes:
            if colonne not in _cols(table):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {sorte}")
    if version < 31:
        # Migrations de DONNÉES, donc gatées par la VERSION, et IDEMPOTENTES (des tests
        # ramènent `user_version` en arrière sur une base courante) : elles ne touchent que
        # ce qui manque.
        #
        # Le nom du projet d'origine : une PHOTOGRAPHIE du jour de la migration — le nom à
        # l'import n'a été gardé nulle part. NULL si le projet n'existe plus.
        if ({"document", "projet"} <= _tables
                and "projet_origine_id" in _cols("document")):
            conn.execute(
                "UPDATE document SET projet_origine_nom = "
                "(SELECT p.nom FROM projet p WHERE p.id = document.projet_origine_id) "
                "WHERE projet_origine_nom IS NULL AND projet_origine_id IS NOT NULL")
        # Chaque album d'hier est la copie d'ORIGINE de son document : créée par qui l'a
        # importé, quand il l'a importé. NULL quand on ne le sait pas (tout l'existant
        # d'avant la v30) — et « inconnu veut dire demander » (décision B3) tient pour lui.
        if ({"copie", "albums", "document"} <= _tables
                and "document_id" in _cols("albums")):
            conn.execute(
                "INSERT INTO copie (album_id, creee_par, creee_le, cran) "
                "SELECT a.id, d.importe_par, d.importe_le, ? FROM albums a "
                "LEFT JOIN document d ON d.id = a.document_id "
                "WHERE NOT EXISTS (SELECT 1 FROM copie c WHERE c.album_id = a.id)",
                (CRAN_ORIGINE,))
        # La collection de BASE de chaque projet (D10), PROTÉGÉE : rien ne s'ouvre au
        # déploiement — une mise à jour ne donne de droit à personne sans qu'on l'ait décidé.
        if {"collection", "projet"} <= _tables and "base" in _cols("collection"):
            _designer_les_bases(conn)
        # Et des identifiants de PROJET qui ne reviennent plus (D8) : la machinerie de la
        # v30, qui ne touche que les tables à qui `AUTOINCREMENT` manque encore — une base
        # migrée depuis la v29 l'a déjà reçu par l'étape du dessus.
        _reconstruire_avec_autoincrement(conn)

    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


# Les tables dont l'identifiant ne doit jamais revenir (v30), et, pour chacune, ce qui la
# désigne dans le JOURNAL : les `cible_table` dont `cible_id` est l'une de ses lignes, et
# les clés de charge (`avant`, `apres`) qui portent l'un de ses identifiants. Deux formes
# de plus, lues par `_jamais_nommes` : la clé `id` d'un instantané de région (une région
# supprimée, et ses enfants, sous `enfants`), et la clé `id` de l'objet `planche` d'un
# scan ajouté ou retiré (`main._journaliser_scan`).
#
# Le recensement est fait sur les écritures du journal au 2026-10-15. En dire TROP ne
# coûte qu'un saut dans la numérotation ; en dire trop peu rendrait une dernière fois un
# identifiant que le journal nomme encore. D'où `region_id` et `parent_id` lus dans
# TOUTES les charges, quelle que soit leur cible.
#
# v31 (COL-3, tranche 3, D8) : `projet` aussi. Le journal le nomme par deux cibles et par la
# clé `projet_id` des charges ; et deux colonnes HORS du journal, sans clé étrangère, le
# nomment encore après sa suppression — une demande, et l'origine d'un document
# (`_HORS_JOURNAL`).
_AUTOINCREMENT = {
    "albums": ((), ("album_id",)),
    "planches": (("planches",), ("planche_id",)),
    "regions": (("regions", "annotations", "bulle_locuteur", "personnage_presence",
                 "region_attribut"), ("region_id", "parent_id")),
    "personnages": ((), ("personnage_id",)),
    "projet": (("projet", "projet_acces"), ("projet_id",)),
}
# Ce qui nomme une ligne de ces tables HORS du journal, et lui survit faute de clé
# étrangère : (table, colonne). Lu par `_jamais_nommes` quand la colonne existe.
_HORS_JOURNAL = {
    "projet": (("demande", "projet_id"), ("document", "projet_origine_id")),
}


def _jamais_nommes(conn: sqlite3.Connection) -> dict:
    """{table: le plus grand identifiant de cette table que le journal ait jamais nommé},
    0 sans journal ou sans mention. Une lecture de tout le journal, une fois, à la
    migration : les charges sont du JSON, lu par `json_tree`, et une charge ILLISIBLE est
    sautée plutôt que de faire échouer la migration.

    Le journal A3, c'est `evenement` ET `activite` (relecture croisée de la tranche 2) :
    une passe automatique qui n'a rien changé — un OCR sans texte à poser — n'écrit aucun
    événement, et sa planche n'est nommée que par la PORTÉE de son activité. `portee` est
    lue, et `params` par prudence, avec les mêmes clés ; une activité n'a pas de cible."""
    resultat = {t: 0 for t in _AUTOINCREMENT}
    # Les colonnes PRÉSENTES, table par table : des tests de migration montent un journal
    # minimal — `activite (id)` seule — avant d'appeler `_migrate`.
    cols = {t: {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            for t in ("evenement", "activite")}
    charges = [("evenement", "e.cible_table" if "cible_table" in cols["evenement"]
                else "NULL", c) for c in ("avant", "apres") if c in cols["evenement"]]
    charges += [("activite", "NULL", c) for c in ("portee", "params")
                if c in cols["activite"]]
    for table, (cibles, _cles) in _AUTOINCREMENT.items():
        if cibles and {"cible_table", "cible_id"} <= cols["evenement"]:
            m = conn.execute(
                f"SELECT MAX(cible_id) FROM evenement WHERE cible_table IN "
                f"({', '.join('?' * len(cibles))})", cibles).fetchone()[0]
            resultat[table] = max(resultat[table], m or 0)
    for table, sources in _HORS_JOURNAL.items():
        for source, colonne in sources:
            if colonne in {r[1] for r in conn.execute(f"PRAGMA table_info({source})")}:
                m = conn.execute(f"SELECT MAX({colonne}) FROM {source}").fetchone()[0]
                resultat[table] = max(resultat[table], m or 0)
    return _max_des_charges(conn, charges, resultat)


def _plus_grand_dossier_d_album() -> int:
    """Le plus grand N d'un dossier `album_N` présent dans `corpus/` ou `derivatives/`, 0
    sans dossier (relecture croisée de la tranche 2). Une base v29 ne nomme AUCUN album
    dans son journal : sans cette lecture, l'album détruit en haut revenait à la migration,
    et l'album neuf retrouvait son dossier d'images. Seul un dossier nommé exactement
    `album_<nombre>` compte.

    Les chemins sont ceux qu'écrit l'import (`pipeline.ingest`), lus à l'appel et non au
    chargement : `database` n'importe pas le pipeline, et les tests les redirigent là."""
    from pipeline import ingest
    plus_grand = 0
    for racine in (ingest.CORPUS_DIR, ingest.DERIVATIVES_DIR):
        if not racine.is_dir():
            continue
        for d in racine.iterdir():
            m = re.fullmatch(r"album_(\d+)", d.name)
            if m and d.is_dir():
                plus_grand = max(plus_grand, int(m.group(1)))
    return plus_grand


def _max_des_charges(conn: sqlite3.Connection, charges: list, resultat: dict) -> dict:
    """Le plus grand identifiant que nomment des charges JSON, table par table, porté
    dans `resultat`. `charges` : (table du journal, expression de sa cible — NULL pour une
    activité —, colonne)."""
    for source, cible, charge in charges:
        colonnes = []
        params = []
        for table, (_cibles, cles) in _AUTOINCREMENT.items():
            cas = f"j.key IN ({', '.join('?' * len(cles))})"
            params.extend(cles)
            if table == "regions":
                cas = f"({cas} OR (j.key = 'id' AND {cible} = 'regions'))"
            elif table == "planches":
                cas = f"({cas} OR (j.key = 'id' AND j.path LIKE '%.planche'))"
            colonnes.append(f"MAX(CASE WHEN {cas} THEN CAST(j.atom AS INTEGER) END)")
        ligne = conn.execute(
            f"SELECT {', '.join(colonnes)} FROM {source} e, json_tree("
            f"CASE WHEN json_valid(e.{charge}) THEN e.{charge} ELSE '{{}}' END) j "
            f"WHERE e.{charge} IS NOT NULL AND j.type = 'integer'", params).fetchone()
        for table, m in zip(_AUTOINCREMENT, ligne):
            resultat[table] = max(resultat[table], m or 0)
    return resultat


def _copier_lignes(conn: sqlite3.Connection, table: str, colonnes: str) -> None:
    """Copie les lignes de `table` dans `<table>__v30`, identifiants compris. À part pour
    qu'un test puisse rendre la copie fautive, et mesurer que le contrôle des fautes de
    clé défait alors tout (`tests/test_identifiants_v30.py`)."""
    conn.execute(f'INSERT INTO "{table}__v30" ({colonnes}) SELECT {colonnes} FROM "{table}"')


def _reconstruire_avec_autoincrement(conn: sqlite3.Connection) -> None:
    """Pose `AUTOINCREMENT` sur les tables de `_AUTOINCREMENT` qui ne l'ont pas, par la
    reconstruction que SQLite prescrit — on ne peut pas le poser par `ALTER TABLE` : table
    neuve, copie des lignes avec leurs identifiants, ancienne détruite, neuve renommée,
    index recréés, vues recréées. Les clés étrangères sont SUSPENDUES le temps de la
    reconstruction : actives, détruire `albums` effacerait par cascade toutes les planches.
    Elles sont vérifiées à la fin (`PRAGMA foreign_key_check`), et la moindre faute NEUVE
    défait tout. La table FTS `recherche` et `tokens` ne sont pas reconstruites, et ne perdent rien :
    une table détruite sous des clés étrangères suspendues n'emporte pas ses dépendants.

    Le compteur de chaque table repart AU-DESSUS du plus grand identifiant que le journal
    ait jamais nommé (`_jamais_nommes`), pas seulement du plus grand qui survit : sans cela,
    les identifiants détruits avant la migration, au-dessus du dernier survivant, seraient
    rendus une dernière fois — et c'est précisément le mélange que la v30 ferme. Celui
    des albums part en plus au-dessus du plus grand dossier `album_N` présent sur le
    disque (`_plus_grand_dossier_d_album`) : le journal d'une base v29 n'en nomme aucun, et
    un album détruit laisse peut-être ses images. Un identifiant détruit que rien ne nomme
    plus — ni le journal, ni un dossier — peut revenir : rien ne le désigne.

    La transaction en cours est validée d'abord : `PRAGMA foreign_keys` ne change pas à
    l'intérieur d'une transaction. Ce qui précède dans `_migrate` est idempotent, et la
    version n'est écrite qu'après : une reconstruction qui échoue laisse la base en v29,
    prête à rejouer l'étape au démarrage suivant."""
    a_faire = []
    for table in _AUTOINCREMENT:
        r = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                         (table,)).fetchone()
        if r is None or "AUTOINCREMENT" in r[0].upper():
            continue
        neuf, n = re.subn(r"^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?\"?" + table + r"\"?\s*\(",
                          f"CREATE TABLE {table}__v30 (", r[0], count=1)
        neuf, m = re.subn(r"\bid\s+INTEGER\s+PRIMARY\s+KEY\b",
                          "id INTEGER PRIMARY KEY AUTOINCREMENT", neuf, count=1)
        if n != 1 or m != 1:
            raise RuntimeError(
                f"Migration v30 : la table `{table}` n'a pas la forme attendue "
                f"(« id INTEGER PRIMARY KEY ») ; elle ne peut pas recevoir AUTOINCREMENT. "
                "Aucune table n'a été modifiée.")
        a_faire.append((table, neuf))
    if not a_faire:
        return
    jamais = _jamais_nommes(conn)
    # Un album détruit laisse peut-être ses DOSSIERS d'images, et le journal d'une base v29
    # ne nomme aucun album : le compteur passe aussi au-dessus d'eux.
    jamais["albums"] = max(jamais["albums"], _plus_grand_dossier_d_album())
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            fautes_avant = {tuple(f) for f in conn.execute("PRAGMA foreign_key_check")}
            for (vue,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'view'").fetchall():
                conn.execute(f'DROP VIEW "{vue}"')
            for table, neuf in a_faire:
                index = [s for (s,) in conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? "
                    "AND sql IS NOT NULL", (table,))]
                colonnes = ", ".join(f'"{c[1]}"' for c in
                                     conn.execute(f'PRAGMA table_info("{table}")'))
                conn.execute(neuf)
                _copier_lignes(conn, table, colonnes)
                conn.execute(f'DROP TABLE "{table}"')
                conn.execute(f'ALTER TABLE "{table}__v30" RENAME TO "{table}"')
                for s in index:
                    conn.execute(s)
                # La copie a posé le compteur au plus grand identifiant survivant ; le
                # journal peut en nommer de plus grands.
                conn.execute("INSERT INTO sqlite_sequence (name, seq) "
                             "SELECT ?, 0 WHERE NOT EXISTS "
                             "(SELECT 1 FROM sqlite_sequence WHERE name = ?)", (table, table))
                conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?",
                             (jamais[table], table))
            # La reconstruction ne doit créer AUCUNE référence orpheline. Celles qu'une
            # base portait déjà (une ligne écrite clés étrangères coupées) ne sont pas les
            # siennes : refuser de démarrer pour elles fermerait l'instance sur une faute
            # que la migration n'a pas faite, et qu'elle ne saurait pas réparer.
            fautes = [f for f in map(tuple, conn.execute("PRAGMA foreign_key_check"))
                      if f not in fautes_avant]
            if fautes:
                raise RuntimeError(
                    "Migration v30 : la reconstruction laisse des clés étrangères "
                    f"orphelines ({fautes[:5]}) ; rien n'est modifié.")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_VIEWS_SQL)


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


def noms_lisibles(conn: sqlite3.Connection, logins) -> dict:
    """login → nom affichable, depuis le miroir `utilisateur` (v22).

    Le miroir existait depuis AUTH-1 sans qu'aucune surface ne le lise : les écrans
    montraient des logins là où une personne attend un nom. Il est alimenté à chaque
    passage par `Remote-Name`, donc il peut ne rien savoir — d'un compte qui n'a jamais
    ouvert l'application, ou d'un proxy qui ne pose pas l'en-tête. Dans ce cas le login est
    rendu TEL QUEL, et c'est la bonne réponse : un identifiant imparfait vaut mieux qu'un
    trou, et c'est ainsi que l'appelant n'a jamais à distinguer les deux cas.

    Aucun secret n'en sort : le miroir ne contient que ce qu'Authelia pose déjà dans ses
    en-têtes (AUTH-1), et le courriel n'est jamais lu ici.
    """
    voulus = {x for x in logins if x}
    if not voulus:
        return {}
    qm = ",".join("?" * len(voulus))
    connus = {r["login"]: (r["nom"] or "").strip()
              for r in conn.execute(
                  f"SELECT login, nom FROM utilisateur WHERE login IN ({qm})",
                  tuple(voulus))}
    return {login: (connus.get(login) or login) for login in voulus}


def avancer_statut(conn: sqlite3.Connection, planche_id: int, cible: str) -> str:
    """Fait AVANCER `planches.statut` vers `cible`, jamais reculer. Renvoie l'effectif.

    Une passe automatique n'a pas d'intention (B6, AUDIT-1). Re-segmenter une planche déjà
    `annotee` faisait retomber son statut à `segmentee` : le travail humain restait en base,
    mais sa DÉCLARATION d'avancement était effacée, et rien ne le signalait — `statut` ne
    commande rien, il ne nourrit que la barre d'avancement du corpus, de sorte que le seul
    symptôme est un tableau de bord qui régresse tout seul.

    L'ordre vient de `STATUTS` et de nulle part ailleurs : un `CASE WHEN` en SQL le
    recopierait, et deux copies d'un ordre finissent par diverger. Un statut inconnu en base
    (valeur héritée, migration future) est traité comme le PLUS BAS — on avance alors, ce
    qui est le comportement d'avant ce correctif, donc sans surprise.

    L'humain, lui, garde le droit de reculer : `PATCH /api/planches/{id}/statut` n'appelle
    PAS cette fonction. Corriger un clic est une intention ; une passe ML n'en a aucune.
    """
    rang = {st: i for i, st in enumerate(STATUTS)}
    if cible not in rang:
        raise ValueError(f"statut cible inconnu : {cible}")
    row = conn.execute("SELECT statut FROM planches WHERE id = ?", (planche_id,)).fetchone()
    if row is None:
        # Sans cette garde, l'UPDATE serait un no-op silencieux et la fonction renverrait
        # `cible` : elle ANNONCERAIT un avancement qui n'a pas eu lieu, ce qui est
        # exactement le mensonge que ce correctif supprime ailleurs. Une planche absente
        # est une erreur de programmation, pas un cas de bord à absorber.
        raise ValueError(f"planche inconnue : {planche_id}")
    actuel = row["statut"]
    if rang.get(actuel, -1) >= rang[cible]:
        return actuel                       # déjà aussi loin, ou plus loin : on ne touche pas
    conn.execute("UPDATE planches SET statut = ? WHERE id = ?", (cible, planche_id))
    return cible


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
    """Toutes les collections, avec leur nombre d'albums et leur PROJET. Ordre d'id (stable).

    `projet_id` est ici le projet LU (`sql_projet_de`) et non la colonne brute : une
    collection sans projet nommé se rend dans le projet de repli, avec son nom."""
    lignes = []
    for r in conn.execute(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM collection_album ca WHERE ca.collection_id = c.id) "
            "AS nb_albums, p.id AS projet_lu, p.nom AS projet_nom "
            f"FROM collection c LEFT JOIN projet p ON p.id = {sql_projet_de('c')} "
            "ORDER BY c.id"):
        c = dict(r)
        c["projet_id"] = c.pop("projet_lu")
        lignes.append(c)
    return lignes


# --------------------------------------------------------------------------- #
# Projets (l'étage au-dessus des collections — v29, COL-3)
# --------------------------------------------------------------------------- #
# Nom sous lequel NAÎT le projet de repli, sur toute instance, jusqu'à ce que quelqu'un le
# renomme. Il ne DÉSIGNE rien : le projet de repli se reconnaît à son drapeau `repli`, et
# ce nom n'est lu nulle part ailleurs que dans `projet_par_defaut`.
NOM_PROJET_DEFAUT = "Projet principal"

# Plafond du NOM d'un projet, en caractères. Court exprès : le nom se lit dans la bande du
# haut des cinq surfaces, où il ne doit ni se couper ni pousser la navigation hors de la
# fenêtre. Lu par les routes de `routes/projets.py`, et par elles seules ; l'écran en tient
# une copie pour l'annoncer sous son champ (`static/lib/projet.js`), et leur accord est
# mesuré (`tests/test_projet_ecran.py`).
#
# FIXÉ PAR LA MESURE le 2026-10-10 — il valait 24 en attendant, et 24 ne tient pas. Le pire
# cas est un coin précis : 320 px de large, une préférence de police de 24, DEUX projets
# visibles (le nom est alors dans un `<select>`, qui prend 26 à 29 px pour sa flèche et son
# cadre), et la police de l'image de production, DejaVu Sans, plus large que celle du poste.
# La bande y laisse 278 px, donc 249 au texte du nom. Vingt et une capitales de français
# courant en demandent 238 (« CORPUS FRANCO-BELGE 2 ») : 12 px de marge sous Chromium, 14
# sous Firefox. Vingt-quatre en demandent 272 et sortent de 20 à 23 px ; vingt-deux tombent
# à 0 px de marge.
#
# CE QUE LE PLAFOND NE GARANTIT PAS, et aucun plafond en CARACTÈRES ne le garantirait : la
# largeur d'un nom dépend de ses lettres. Un nom chargé de m ou de M sort encore de ce
# coin-là, de 2 px (« Hommage aux mammouths ») à 14 (« MAMMOUTHS ET HOMMAGES ») ; vingt et un
# W en sortent de 124, et dès une préférence de 20 — ils ne tiennent que sous 16. La borne
# vraie est en pixels ; celle-ci est sa traduction pour un nom ordinaire, capitales
# comprises.
LONGUEUR_NOM_PROJET = 21


def sql_projet_de(alias: str = "c") -> str:
    """Expression SQL du projet d'une collection — la règle de LECTURE, écrite une fois.

    `collection.projet_id` est nullable (cf. le schéma), et NULL se lit « le projet de
    repli ». Tout ce qui demande « de quel projet est cette collection » passe par ICI :
    la liste des collections, la visibilité d'un projet (`Portee.clause_projet`), le compte
    de ses collections, le refus de ranger un album à travers deux projets. Deux écritures
    de la règle finiraient par ne plus répondre pareil à une collection sans projet nommé —
    et c'est exactement l'état des collections que les tests et une base retouchée à la
    main créent par `INSERT`.

    `alias` est un morceau de SQL écrit par le code appelant, jamais une valeur du client.
    Sans projet de repli en base (ligne retirée à la main), l'expression rend NULL pour ces
    collections : elles ne se rattachent à aucun projet tant que `projet_par_defaut` n'en a
    pas refait un, ce que fait la première écriture qui en a besoin."""
    return (f"COALESCE({alias}.projet_id, "
            "(SELECT id FROM projet WHERE repli = 1 ORDER BY id LIMIT 1))")


def projet_par_defaut(conn: sqlite3.Connection) -> int:
    """Id du projet de repli, CRÉÉ s'il n'existe pas — le patron de `collection_par_defaut`.

    C'est le projet de toute collection qui n'en nomme aucun : l'instance d'avant la v29
    en entier, puis ce qui se crée sans préciser. Désigné par son DRAPEAU et non par son
    nom, parce qu'il est fait pour être renommé.

    v31 (COL-3, tranche 3, D10 ; Hugo, 2026-10-17) — il naît, comme tout projet, avec sa
    collection de BASE : NEUVE, vide et PROTÉGÉE. Ce n'est pas la collection de repli des
    albums sans collection (`collection_par_defaut`), qui reste ce qu'elle était. La garde
    de colonne vaut pour la migration : sur une base d'avant la v31, la colonne `base` n'est
    posée qu'après l'étape v29 qui fait naître le projet, et c'est `_designer_les_bases` qui
    lui donne sa base."""
    r = conn.execute("SELECT id FROM projet WHERE repli = 1 ORDER BY id LIMIT 1").fetchone()
    if r:
        return r[0]
    cur = conn.execute(
        "INSERT INTO projet (nom, description, repli) VALUES (?, ?, 1)",
        (NOM_PROJET_DEFAUT,
         "Créé automatiquement : toute collection appartient à un projet. Renommez-le, et "
         "décrivez-le."))
    if {"projet_id", "base", "acces_membres"} <= {
            c[1] for c in conn.execute("PRAGMA table_info(collection)")}:
        creer_collection_de_base(conn, cur.lastrowid, nom=NOM_PROJET_DEFAUT,
                                 acces_membres=None)
    return cur.lastrowid


def projet_de_collection(conn: sqlite3.Connection, collection_id: int) -> int | None:
    """Id du projet auquel cette collection appartient, par la règle de `sql_projet_de`.
    None si la collection n'existe pas."""
    r = conn.execute(f"SELECT {sql_projet_de('c')} FROM collection c WHERE c.id = ?",
                     (collection_id,)).fetchone()
    return r[0] if r else None


def rangement_traverse(conn: sqlite3.Connection, album_id: int, collection_id: int) -> bool:
    """Ranger cet album dans cette collection lui ferait-il TRAVERSER deux projets ?

    Vrai s'il vit déjà dans une collection d'un AUTRE projet que celui de la collection
    d'arrivée. Un album déjà rangé là ne traverse rien de plus : re-poser un rangement
    existant reste sans effet, quoi qu'une base retouchée à la main ait laissé.

    La question vit ici parce que ses appelants ne doivent pas diverger : ranger
    (`ranger_album`, « + Ranger ici »), la prise (`routes/fonds.py`), l'acceptation d'un
    `rejoindre` ou d'une reprise, et l'outil en ligne de commande (`gerer_collections.py`).
    Depuis la tranche 3 (D4) ranger est REJOINDRE : ce refus est la première question de
    `socle._plan_rejoindre`, avant celle de qui consent (`Portee.clause_rejoindre_directe`).

    COL-3, tranche 2 — une seconde moitié, et c'est elle qui garde une copie AU FONDS.
    Sortie de sa dernière collection, une copie n'a plus aucune collection où lire son
    projet ; la première moitié, qui ne lit que celles-là, la laisserait alors entrer dans
    n'importe quel projet. Le projet ÉCRIT sur la copie (`albums.projet_id`) doit donc
    être aussi celui de la collection d'arrivée. Une copie qui n'en a JAMAIS eu — importée
    au fonds — entre où l'on veut, et y prend son projet (`poser_projet_de_copie`)."""
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ? AND collection_id = ?",
                    (album_id, collection_id)).fetchone():
        return False
    arrivee = projet_de_collection(conn, collection_id)
    ecrit = conn.execute("SELECT projet_id FROM albums WHERE id = ?", (album_id,)).fetchone()
    if ecrit is not None and ecrit[0] is not None and ecrit[0] != arrivee:
        return True
    return conn.execute(
        "SELECT 1 FROM collection_album ca JOIN collection c ON c.id = ca.collection_id "
        f"WHERE ca.album_id = ? AND {sql_projet_de('c')} IS NOT ?",
        (album_id, arrivee)).fetchone() is not None


def poser_projet_de_copie(conn: sqlite3.Connection, album_id: int) -> None:
    """ÉCRIT sur la copie le projet qu'on lit pour elle (`sql_projet_d_album`), si la
    colonne est encore vide. À appeler juste APRÈS l'avoir rangée — une copie importée au
    fonds prend alors le projet de sa première collection — et juste AVANT de la sortir
    d'une collection, tant qu'on lit encore le projet dans celle-ci : une copie qui part au
    fonds doit l'emporter, sans quoi `rangement_traverse` la laisserait entrer ailleurs.

    Ne remplace jamais un projet déjà écrit : une copie n'en change pas. Deux appelants,
    la route et l'outil, pour la raison écrite sur `rangement_traverse`."""
    conn.execute(f"UPDATE albums SET projet_id = ({sql_projet_d_album('albums')}) "
                 "WHERE id = ? AND projet_id IS NULL", (album_id,))


def collections_sans_projet(conn: sqlite3.Connection) -> list[int]:
    """Collections dont la colonne `projet_id` est restée NULL. Les trois chemins d'écriture
    de l'application la posent (la route, la collection de repli, l'outil en ligne de
    commande) : c'est la formulation exécutable de « une collection appartient à UN
    projet », sur le modèle d'`albums_orphelins`. Une ligne ici n'est pas une panne — la
    règle de lecture la range au repli — mais dit qu'un chemin d'écriture l'a oubliée."""
    return [r[0] for r in conn.execute(
        "SELECT id FROM collection WHERE projet_id IS NULL ORDER BY id")]


# --------------------------------------------------------------------------- #
# La collection de BASE d'un projet (v31, COL-3, tranche 3, D10 — Hugo, 2026-10-17)
# --------------------------------------------------------------------------- #
# « Le fonds commence avec le projet » : tout projet naît avec UNE collection de base, où
# arrive ce qu'il prend au fonds et que l'import présélectionne. Désignée par un DRAPEAU
# (`collection.base`), jamais par son nom. Ce qu'elle ouvre — ses responsables
# propriétaires, ses membres au niveau `acces_membres` — est DÉRIVÉ par
# `autorisation.Portee`, et rien ici n'écrit dans `collection_acces`.
#
# Le nom qu'elle prend quand celui du projet est réservé à la collection de repli (« Collection
# par défaut » tient dans les 21 caractères d'un nom de projet).
NOM_BASE_DE_SECOURS = "Collection de base"
DESCRIPTION_BASE = ("Collection de base du projet : ce que le projet prend au fonds y arrive, "
                    "et l'import la propose d'abord. Ses responsables en sont propriétaires ; "
                    "elle se renomme, elle ne se supprime pas.")


def collection_de_base(conn: sqlite3.Connection, projet_id: int) -> int | None:
    """Id de la collection de base de ce projet, None s'il n'en a pas — une base retouchée à
    la main, ou une étape de migration pas encore jouée. La plus petite si une base retouchée
    en portait deux : l'unicité est tenue par le code, pas par un index (la raison est écrite
    sur la colonne)."""
    r = conn.execute(f"SELECT c.id FROM collection c WHERE c.base = 1 "
                     f"AND {sql_projet_de('c')} = ? ORDER BY c.id LIMIT 1",
                     (projet_id,)).fetchone()
    return r[0] if r else None


def creer_collection_de_base(conn: sqlite3.Connection, projet_id: int, *, nom: str,
                             acces_membres: str | None) -> int:
    """Fait naître la collection de base d'un projet qui n'en a pas, et rend son id.
    `acces_membres` est OBLIGATOIRE et sans défaut, comme les arguments de
    `creer_document` : la position est une décision, et un défaut la prendrait pour
    l'appelant distrait. N'écrit rien au journal : c'est l'affaire de l'appelant."""
    if collection_de_base(conn, projet_id) is not None:
        raise ValueError(f"le projet {projet_id} a déjà sa collection de base")
    nom = (nom or "").strip()
    if not nom or nom_reserve(nom):
        nom = NOM_BASE_DE_SECOURS
    return conn.execute(
        "INSERT INTO collection (nom, description, projet_id, base, acces_membres) "
        "VALUES (?, ?, ?, 1, ?)", (nom, DESCRIPTION_BASE, projet_id, acces_membres)).lastrowid


def _designer_les_bases(conn: sqlite3.Connection) -> None:
    """Migration v31 : donne à chaque projet existant — le projet de repli compris — une
    collection de base NEUVE, vide et PROTÉGÉE, de son nom. AUCUNE collection existante ne
    devient une base (Hugo, 2026-10-17, sur le constat 1 de la relecture croisée) : la
    « Collection par défaut », habitée, aurait été ouverte au déploiement aux responsables
    du projet de repli, propriétaires de sa base par dérivation. Rien ne s'ouvre au
    déploiement : les responsables ne reçoivent qu'une collection vide. Idempotente : un
    projet qui a déjà sa base n'est pas touché."""
    for projet_id, nom in conn.execute(
            "SELECT id, nom FROM projet ORDER BY id").fetchall():
        if collection_de_base(conn, projet_id) is None:
            creer_collection_de_base(conn, projet_id, nom=nom, acces_membres=None)


# --------------------------------------------------------------------------- #
# Le fonds — documents et copies de travail (v30, COL-3, tranche 2)
# --------------------------------------------------------------------------- #
def _sql_projet_des_collections(alias: str) -> str:
    """Sous-requête : le projet qu'on LIT dans les collections de l'album `alias` — celui
    de sa collection de plus petit id, par la règle de `sql_projet_de` ; NULL s'il n'est
    rangé nulle part. Les alias internes portent un tiret bas pour ne heurter aucun de
    ceux du code appelant."""
    return (f"SELECT {sql_projet_de('_c')} FROM collection_album _ca "
            "JOIN collection _c ON _c.id = _ca.collection_id "
            f"WHERE _ca.album_id = {alias}.id ORDER BY _c.id LIMIT 1")


def sql_projet_d_album(alias: str = "a") -> str:
    """Expression SQL du projet d'une COPIE DE TRAVAIL — la règle de LECTURE, écrite une
    fois, pendant de `sql_projet_de` pour les collections.

    Le projet ÉCRIT sur la copie d'abord (`albums.projet_id`) : c'est lui qui tient quand
    elle n'est plus rangée nulle part. À défaut — un album posé par `INSERT`, ou qu'aucun
    chemin d'écriture n'a nommé —, celui qu'on lit dans ses collections. Et NULL quand il
    n'y a ni l'un ni l'autre : la copie n'a JAMAIS eu de projet. Ce NULL-là ne se lit PAS
    « le projet de repli », à la différence d'une collection : un document entré au fonds
    sans passer par un projet n'est d'aucun, jusqu'à ce qu'on le range.

    `alias` est un morceau de SQL écrit par le code appelant, jamais une valeur du client."""
    return f"COALESCE({alias}.projet_id, ({_sql_projet_des_collections(alias)}))"


def projet_d_album(conn: sqlite3.Connection, album_id: int) -> int | None:
    """Id du projet de cette copie, par la règle de `sql_projet_d_album`. None si elle
    n'existe pas, ou n'a jamais eu de projet."""
    r = conn.execute(f"SELECT {sql_projet_d_album('a')} FROM albums a WHERE a.id = ?",
                     (album_id,)).fetchone()
    return r[0] if r else None


def document_d_album(conn: sqlite3.Connection, album_id: int) -> int | None:
    """Id du document dont cet album est une copie. None s'il n'en a pas — un album posé
    par `INSERT` — ou s'il n'existe pas."""
    r = conn.execute("SELECT document_id FROM albums WHERE id = ?", (album_id,)).fetchone()
    return r[0] if r else None


# Les crans d'une copie (`copie.cran`, v31). `origine` : la copie née avec son document ;
# les autres sont l'ÉCHELLE des couches (COL-3, tranche 3b, E1, Hugo, 2026-10-20), dans
# l'ordre où elles s'empilent — chaque cran emporte ceux d'en dessous :
#   images         la notice, les contributions, les planches (`PLANCHE_SCAN`) — vierge ;
#   decoupage      + les régions (cases, bulles, ordre de lecture), sans texte, et
#                    l'avancée de la reconnaissance des planches ;
#   transcription  + le texte des régions, et leurs tokens ;
#   grammaire      + les corrections grammaticales, et la relecture forcée des planches ;
#   annotations    + notes et tags, attributs de case, locuteurs, présences.
# La VALIDATION ne suit à aucun cran (`validee`, `verrouillee`, `verrou_par`) : valider est
# le jugement de qui relit, dans SA copie.
CRAN_ORIGINE = "origine"
CRAN_IMAGES = "images"
CRAN_DECOUPAGE = "decoupage"
CRAN_TRANSCRIPTION = "transcription"
CRAN_GRAMMAIRE = "grammaire"
CRAN_ANNOTATIONS = "annotations"
CRANS = (CRAN_IMAGES, CRAN_DECOUPAGE, CRAN_TRANSCRIPTION, CRAN_GRAMMAIRE, CRAN_ANNOTATIONS)


def rang_du_cran(cran: str) -> int:
    """Le rang d'un cran sur l'échelle, `images` valant 0 ; -1 pour ce qui n'en est pas un
    (`origine` compris : la copie d'origine n'est tirée de rien)."""
    return CRANS.index(cran) if cran in CRANS else -1


def sql_rang_du_cran(expr: str) -> str:
    """`rang_du_cran`, écrit en SQL sur l'expression `expr` — la même liste, pour que la
    règle de suppression (`autorisation`) lise l'échelle sans la recopier."""
    cas = " ".join(f"WHEN '{c}' THEN {i}" for i, c in enumerate(CRANS))
    return f"(CASE {expr} {cas} ELSE -1 END)"


def creer_document(conn: sqlite3.Connection, album_id: int, *,
                   importe_par: str | None, projet_id: int | None) -> int:
    """Fait naître le DOCUMENT d'un album qu'on vient de créer, et attache l'un à l'autre :
    l'origine sur le document (qui, quand, dans quel projet d'abord, et le NOM de ce projet
    ce jour-là), le document et le projet sur la copie, et la provenance de la copie — sa
    ligne `copie`, cran `origine`, créée par qui a importé (v31). Renvoie l'id du document.

    Les deux arguments sont OBLIGATOIRES et sans défaut, comme `principal` pour ShareDocs :
    un défaut à None ferait naître un document « d'origine inconnue » chez un appelant
    distrait, ce qui marcherait parfaitement et se lirait ensuite comme un album d'avant le
    fonds. `importe_par` vaut None quand personne ne s'annonce (mono-poste), `projet_id`
    quand le document entre sans projet — et dans les deux cas l'appelant l'a ÉCRIT.

    N'écrit rien au journal : c'est l'affaire de l'appelant, qui sait ce qu'il fait naître."""
    nom = None
    if projet_id is not None:
        r = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()
        nom = r[0] if r else None
    cur = conn.execute(
        "INSERT INTO document (importe_par, projet_origine_id, projet_origine_nom) "
        "VALUES (?, ?, ?)", (importe_par, projet_id, nom))
    document_id = cur.lastrowid
    conn.execute("UPDATE albums SET document_id = ?, projet_id = ? WHERE id = ?",
                 (document_id, projet_id, album_id))
    conn.execute("INSERT INTO copie (album_id, creee_par, creee_le, cran) "
                 "SELECT ?, ?, importe_le, ? FROM document WHERE id = ?",
                 (album_id, importe_par, CRAN_ORIGINE, document_id))
    return document_id


# Les colonnes d'`albums` qui ne sont PAS la notice, et ne se recopient pas d'une copie à sa
# sœur : son identité, sa date d'import, et ses deux attaches, que `creer_copie` pose
# elle-même. Toute autre colonne EST la notice (D7, Hugo, 2026-10-17) et se recopie — une
# colonne descriptive ajoutée demain suit par défaut, ce qui est le bon défaut pour une
# notice ; une colonne qui ne serait PAS descriptive doit entrer ici, et
# `tests/test_prendre.py` exige que la liste soit relue à chaque colonne neuve.
ALBUM_HORS_NOTICE = frozenset({"id", "date_import", "document_id", "projet_id"})

# Ce qu'une planche d'une copie VIERGE reprend de la planche source : ce que le SCAN est —
# son rang, son rôle, ses fichiers (D6 : les MÊMES, aucune image n'est copiée), ses
# dimensions et son matériel, et ce qu'on sait de son master d'archive (`master_origine`,
# IMG-1 : les mêmes fichiers viennent du même master). Le reste est le travail de la copie source — l'avancée de la
# reconnaissance (`statut`, `date_segmentation`), la validation, le verrou et qui l'a posé,
# la relecture forcée — et une copie vierge n'en hérite pas : elle repart `importee`.
PLANCHE_SCAN = ("numero", "role", "chemin_tiff", "chemin_web", "largeur_px", "hauteur_px",
                "dpi_x", "dpi_y", "mode", "master_origine")


def creer_copie(conn: sqlite3.Connection, document_id: int, collection_id: int, *,
                par: str | None, depuis: int, cran: str) -> int:
    """Fait naître une COPIE de travail d'un document qui EXISTE déjà, rangée dans
    `collection_id`, et rend son id. COL-3, tranche 3 — la seconde voie de naissance d'un
    album, à côté de `creer_document` (un document qui naît avec sa seule copie).

    Les trois arguments nommés sont OBLIGATOIRES et sans défaut, le patron de
    `creer_document` : `par` (le login de qui la crée, None en mono-poste — et il l'a
    écrit), `depuis` (la copie dont elle est tirée, du même document), `cran` (jusqu'où la
    copie reprend le travail de sa source) — `CRAN_IMAGES`, une copie VIERGE (tranche 3a),
    ou un cran plus haut de l'échelle (`CRANS`, tranche 3b), dont le travail est recopié par
    `copier_le_travail`. Un cran inconnu lève, plutôt que de faire une copie sous un nom
    qui promet autre chose que ce qu'elle porte.

    Ce que la copie reçoit :
    - la NOTICE de sa source — toutes les colonnes d'`albums` hors `ALBUM_HORS_NOTICE` — et
      ses CONTRIBUTIONS, recopiées puis libres de diverger (D7) ;
    - une planche par planche de la source, `PLANCHE_SCAN` seulement : les mêmes FICHIERS
      (D6 — les images appartiennent au document, et un fichier ne quitte le disque que
      lorsque plus aucune planche ne le désigne, `socle._effacer_les_images_d_une_copie`) ;
    - le PROJET de la collection d'arrivée, écrit sur elle — jamais celui de sa source :
      une copie prise entre deux projets naît dans le projet qui la prend, et
      `albums_hors_de_leur_projet` reste vide ;
    - sa ligne `copie` : créée par `par`, au cran dit, depuis la source et le nom du projet
      de celle-ci ce jour-là ;
    - son rangement dans `collection_id`, et dans elle seule ;
    - au-dessus du cran `images`, le TRAVAIL de sa source jusqu'au cran dit, et ce qui en
      est laissé (`copier_le_travail`), écrits dans la charge de la naissance.

    Et elle S'ÉCRIT au journal, dans la même transaction et ici plutôt que chez chaque
    appelant — trois appelants (la prise directe, l'acceptation d'une entrée, et la 3b)
    finiraient par l'oublier : sous la cible `document` (retenue de toute sortie, sans rang,
    non annulable), `apres` seul comme un scan ajouté, la copie neuve dans la charge avec sa
    collection, son cran et sa source ; puis son EMPLOI (`journal.journaliser_emploi`).

    Les FICHIERS ne sont pas touchés, et aucun dossier n'est créé : la copie n'en écrit
    qu'à son premier import, sous un numéro dont les fichiers sont libres et qu'il réserve
    (`ingest.prochain_numero_libre`, `ingest._reserver`). Ne commite pas. Lève `ValueError` sur une source qui
    n'est pas une copie de ce document, une collection qui n'existe pas, un cran inconnu :
    des erreurs de l'appelant, que la route a refusées avant."""
    import journal                          # la naissance s'écrit ici (cf. ci-dessus)
    if cran not in CRANS:
        raise ValueError(f"cran inconnu : {cran!r}")
    source = conn.execute("SELECT document_id FROM albums WHERE id = ?", (depuis,)).fetchone()
    if source is None or source[0] != document_id:
        raise ValueError(f"l'album {depuis} n'est pas une copie du document {document_id}")
    projet = projet_de_collection(conn, collection_id)
    if projet is None:
        raise ValueError(f"collection {collection_id} introuvable")
    notice = [c[1] for c in conn.execute("PRAGMA table_info(albums)")
              if c[1] not in ALBUM_HORS_NOTICE]
    album_id = conn.execute(
        f"INSERT INTO albums ({', '.join(notice)}, document_id, projet_id) "
        f"SELECT {', '.join(notice)}, ?, ? FROM albums WHERE id = ?",
        (document_id, projet, depuis)).lastrowid
    conn.execute(
        f"INSERT INTO planches (album_id, {', '.join(PLANCHE_SCAN)}) "
        f"SELECT ?, {', '.join(PLANCHE_SCAN)} FROM planches WHERE album_id = ? "
        "ORDER BY numero", (album_id, depuis))
    conn.execute("INSERT INTO contribution (album_id, nom, role_id, rang) "
                 "SELECT ?, nom, role_id, rang FROM contribution WHERE album_id = ? "
                 "ORDER BY rang, id", (album_id, depuis))
    conn.execute(
        "INSERT INTO copie (album_id, creee_par, cran, depuis_album_id, depuis_projet_nom) "
        f"VALUES (?, ?, ?, ?, (SELECT p.nom FROM albums a JOIN projet p "
        f"                     ON p.id = {sql_projet_d_album('a')} WHERE a.id = ?))",
        (album_id, par, cran, depuis, depuis))
    conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                 (collection_id, album_id))
    charge = {"cran": cran, "depuis_album_id": depuis, "collection_id": collection_id}
    if cran != CRAN_IMAGES:
        charge.update(copier_le_travail(conn, depuis, album_id, cran, collection_id))
    journal.journaliser(conn, "modification", "document", document_id,
                        apres={"album_id": album_id, "copie": charge})
    journal.journaliser_emploi(conn, "lien", album_id, collection_id)
    return album_id


# Les colonnes d'une région qui portent son TEXTE (cran `transcription`) : sous ce cran, la
# région copiée n'a que sa géométrie. Toute autre colonne de `regions` suit dès le
# découpage — une colonne ajoutée demain suit par défaut, comme la notice.
REGION_TEXTE = {"ocr_texte": None, "touche": 0}
_REGION_HORS_COPIE = frozenset({"id", "planche_id", "parent_id"})


def copier_le_travail(conn: sqlite3.Connection, depuis: int, album_id: int, cran: str,
                      collection_id: int) -> dict:
    """Recopie le travail de la copie `depuis` dans la copie `album_id`, qui vient de
    naître avec les mêmes planches (même `numero`), jusqu'au `cran` dit (E1, COL-3, tranche
    3b). Rend ce qui est copié et ce qui est LAISSÉ, que `creer_copie` écrit dans la charge
    de la naissance : `{"copies": {…}, "laisses": {…}}`.

    Trois règles, chacune tranchée par Hugo le 2026-10-20 :

    - **Aucun événement n'est recopié** (E3). Chaque région copiée dit sa source dans
      `region_origine` ; c'est par elle que le travail reste celui de ses auteurs — la
      règle de suppression remonte la chaîne (`autorisation._sources_du_travail`) —, et ni
      Ctrl+Z, ni les pseudonymes, ni le départ d'un compte ne voient une copie. Les dates
      de création et de modification d'une région, son `activite_id` (le moteur qui l'a
      produite) et l'`auteur` d'une correction suivent avec elles : ils disent quand et
      par qui ce travail a été FAIT, pas copié.
    - **Seul le vocabulaire visible depuis la collection d'arrivée suit** (E5) : un tag, une
      valeur d'attribut et sa dimension globaux ou locaux à `collection_id`
      (`clause_appartenance`, la règle d'une collection et non d'une personne). Un terme
      local à une autre collection serait posé sur la copie et invisible de ses lecteurs ;
      il reste, et se COMPTE. Une annotation dont tous les tags restent et qui n'a pas de
      note ne naît pas.
    - **Les personnages suivent** (E6, forme (a)) : un locuteur, une présence, même entre
      deux projets — le personnage EST le travail. C'est un chemin par lequel une fiche de
      personnage devient visible d'un autre projet, écrit et accepté.

    L'index plein texte et les tokens se recopient SANS spaCy (E9) quand la copie dit ce
    que la source disait — cran `annotations`, ou une source sans note et, au cran
    `transcription`, sans correction. Sinon (une note ou des corrections qui ne suivent pas,
    et dont les lemmes sont mêlés à ceux du texte dans l'index), les LEMMES se recalculent
    par spaCy, les tokens suivant toujours tels quels : l'appelant charge spaCy AVANT sa
    transaction d'écriture (CLAUDE.md § Concurrence). Sans moteur, ces lemmes sont vides,
    comme ceux de la source.

    La validation ne suit pas (E1). Ne commite pas, n'écrit rien au journal."""
    rang = rang_du_cran(cran)
    if rang < 1:
        raise ValueError(f"cran sans travail à copier : {cran!r}")
    texte = rang >= rang_du_cran(CRAN_TRANSCRIPTION)
    grammaire = rang >= rang_du_cran(CRAN_GRAMMAIRE)
    annotations = rang >= rang_du_cran(CRAN_ANNOTATIONS)
    copies = {"regions": 0}
    laisses = {}

    planches = dict(conn.execute(
        "SELECT s.id, n.id FROM planches s JOIN planches n "
        "ON n.album_id = ? AND n.numero = s.numero WHERE s.album_id = ?",
        (album_id, depuis)).fetchall())
    for source, cible in planches.items():
        conn.execute(
            "UPDATE planches SET statut = (SELECT statut FROM planches WHERE id = :s), "
            "date_segmentation = (SELECT date_segmentation FROM planches WHERE id = :s)"
            + (", relecture = (SELECT relecture FROM planches WHERE id = :s)"
               if grammaire else "") + " WHERE id = :c", {"s": source, "c": cible})

    # Les régions : toutes d'abord sans parent, puis les parents recollés — un parent peut
    # porter un identifiant plus grand que son enfant (une région re-parentée).
    colonnes = [c[1] for c in conn.execute("PRAGMA table_info(regions)")
                if c[1] not in _REGION_HORS_COPIE]
    valeurs = [c if texte or c not in REGION_TEXTE else "?" for c in colonnes]
    params_texte = [] if texte else [REGION_TEXTE[c] for c in colonnes if c in REGION_TEXTE]
    regions = {}
    sources = conn.execute(
        "SELECT r.id, r.planche_id, r.parent_id FROM regions r "
        "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ? ORDER BY r.id",
        (depuis,)).fetchall()
    for r in sources:
        regions[r["id"]] = conn.execute(
            f"INSERT INTO regions (planche_id, {', '.join(colonnes)}) "
            f"SELECT ?, {', '.join(valeurs)} FROM regions WHERE id = ?",
            (planches[r["planche_id"]], *params_texte, r["id"])).lastrowid
    for r in sources:
        if r["parent_id"] is not None:
            conn.execute("UPDATE regions SET parent_id = ? WHERE id = ?",
                         (regions.get(r["parent_id"]), regions[r["id"]]))
    conn.executemany("INSERT INTO region_origine (region_id, region_source_id) VALUES (?, ?)",
                     [(n, s) for s, n in regions.items()])
    copies["regions"] = len(regions)

    def _par_region(sql_select, sql_insert):
        """Recopie, région par région, les lignes que `sql_select` lit sous la source."""
        n = 0
        for s, c in regions.items():
            lignes = conn.execute(sql_select, (s,)).fetchall()
            conn.executemany(sql_insert, [(c, *tuple(l)) for l in lignes])
            n += len(lignes)
        return n

    if texte:
        copies["textes"] = conn.execute(
            f"SELECT COUNT(*) FROM regions WHERE id IN ({','.join('?' * len(regions))}) "
            "AND ocr_texte IS NOT NULL AND ocr_texte <> ''",
            list(regions.values())).fetchone()[0] if regions else 0
    if grammaire:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(token_correction)")
                if c[1] not in ("id", "region_id")]
        copies["corrections"] = _par_region(
            f"SELECT {', '.join(cols)} FROM token_correction WHERE region_id = ? ORDER BY id",
            f"INSERT INTO token_correction (region_id, {', '.join(cols)}) "
            f"VALUES (?, {', '.join('?' * len(cols))})")
    if annotations:
        tag_vu, tag_p = clause_appartenance(collection_id, "t.collection_id")
        dim_vu, dim_p = clause_appartenance(collection_id, "d.collection_id")
        val_vu, val_p = clause_appartenance(collection_id, "v.collection_id")
        n_annot = n_tags = n_tags_laisses = 0
        for s, c in regions.items():
            a = conn.execute("SELECT id, note, date_creation, date_modification "
                             "FROM annotations WHERE region_id = ?", (s,)).fetchone()
            if a is None:
                continue
            tags = [t[0] for t in conn.execute(
                f"SELECT at.tag_id FROM annotation_tags at JOIN tags t ON t.id = at.tag_id "
                f"WHERE at.annotation_id = ? AND {tag_vu} ORDER BY at.tag_id",
                (a["id"], *tag_p))]
            total = conn.execute("SELECT COUNT(*) FROM annotation_tags "
                                 "WHERE annotation_id = ?", (a["id"],)).fetchone()[0]
            n_tags_laisses += total - len(tags)
            if not tags and not (a["note"] or "").strip():
                continue
            nid = conn.execute(
                "INSERT INTO annotations (region_id, note, date_creation, date_modification) "
                "VALUES (?, ?, ?, ?)",
                (c, a["note"], a["date_creation"], a["date_modification"])).lastrowid
            conn.executemany("INSERT INTO annotation_tags (annotation_id, tag_id) "
                             "VALUES (?, ?)", [(nid, t) for t in tags])
            n_annot += 1
            n_tags += len(tags)
        copies.update(annotations=n_annot, tags=n_tags)
        laisses["tags"] = n_tags_laisses
        n_attr = n_attr_total = 0
        for s, c in regions.items():
            n_attr_total += conn.execute("SELECT COUNT(*) FROM region_attribut "
                                         "WHERE region_id = ?", (s,)).fetchone()[0]
            n_attr += conn.execute(
                "INSERT INTO region_attribut (region_id, valeur_id) "
                "SELECT ?, ra.valeur_id FROM region_attribut ra "
                "JOIN attribut_valeur v ON v.id = ra.valeur_id "
                "JOIN attribut_dimension d ON d.id = v.dimension_id "
                f"WHERE ra.region_id = ? AND {val_vu} AND {dim_vu}",
                (c, s, *val_p, *dim_p)).rowcount
        copies["attributs"] = n_attr
        laisses["attributs"] = n_attr_total - n_attr
        copies["locuteurs"] = _par_region(
            "SELECT personnage_id, date_creation FROM bulle_locuteur WHERE region_id = ?",
            "INSERT INTO bulle_locuteur (region_id, personnage_id, date_creation) "
            "VALUES (?, ?, ?)")
        copies["presences"] = _par_region(
            "SELECT personnage_id, date_creation FROM personnage_presence WHERE region_id = ?",
            "INSERT INTO personnage_presence (region_id, personnage_id, date_creation) "
            "VALUES (?, ?, ?)")

    if texte:
        lemmes = _lemmes_indexes(conn, list(regions))
        for s, c in regions.items():
            _indexer_une_region_copiee(conn, s, c, lemmes.get(s, ""), grammaire=grammaire,
                                       annotations=annotations)
    return {"copies": copies, "laisses": laisses}


# Combien d'identifiants une lecture de l'index accepte à la fois : sous la limite de
# variables de SQLite, et assez pour qu'un album entier ne coûte qu'une poignée de lectures.
_LOT_INDEX = 500


def _lemmes_indexes(conn: sqlite3.Connection, region_ids: list) -> dict:
    """Les lemmes de l'index plein texte de ces régions, `{region_id: lemmes}`, par LOTS.

    `recherche.region_id` est `UNINDEXED` : la retrouver ligne par ligne parcourt l'index
    entier à chaque région, et copier un album de 2 400 régions prenait alors plusieurs
    secondes sur un index qui n'en portait que quelques milliers (E9, mesuré le
    2026-10-20). Par lots, un parcours par lot."""
    lemmes = {}
    for i in range(0, len(region_ids), _LOT_INDEX):
        lot = region_ids[i:i + _LOT_INDEX]
        for rid, l in conn.execute(
                f"SELECT region_id, lemmes FROM recherche "
                f"WHERE region_id IN ({', '.join('?' * len(lot))})", lot):
            lemmes[int(rid)] = l or ""
    return lemmes


def compter_le_travail(conn: sqlite3.Connection, depuis: int, cran: str,
                       collection_id: int) -> dict:
    """Ce que `copier_le_travail` copierait de la copie `depuis` vers une copie rangée dans
    `collection_id`, jusqu'au `cran` dit — et ce qu'il LAISSERAIT —, sans rien écrire.
    L'APERÇU d'« en partir » (E5, COL-3, tranche 3b) : la même forme que la charge de la
    naissance, `{"copies": {…}, "laisses": {…}}`, plus `personnages`, le nombre de fiches de
    personnage que les locuteurs et présences copiés rendent lisibles depuis la copie (E6).

    Des NOMBRES, jamais des libellés : un tag ou un attribut laissé l'est parce que la
    collection d'arrivée ne le voit pas, et le nommer ferait lire à qui ne le lit pas le nom
    d'un axe privé — la fuite de la v24. Les deux fonctions comptent pareil, et
    `tests/test_amorcer.py` exige que l'aperçu soit la charge, cran par cran."""
    rang = rang_du_cran(cran)
    if rang < 1:
        raise ValueError(f"cran sans travail à copier : {cran!r}")
    regions = [r[0] for r in conn.execute(
        "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id "
        "WHERE p.album_id = ? ORDER BY r.id", (depuis,))]
    copies = {"regions": len(regions)}
    laisses = {}
    personnages = 0
    # Sans région, chaque compte vaut 0 et aucune requête ne part : `IN ()` ne s'écrit pas.
    dans = f"IN ({', '.join('?' * len(regions))})"

    def n(sql, *params):
        return conn.execute(sql, (*regions, *params)).fetchone()[0] if regions else 0
    if rang >= rang_du_cran(CRAN_TRANSCRIPTION):
        copies["textes"] = n(f"SELECT COUNT(*) FROM regions WHERE id {dans} "
                             "AND ocr_texte IS NOT NULL AND ocr_texte <> ''")
    if rang >= rang_du_cran(CRAN_GRAMMAIRE):
        copies["corrections"] = n(f"SELECT COUNT(*) FROM token_correction WHERE region_id {dans}")
    if rang >= rang_du_cran(CRAN_ANNOTATIONS):
        tag_vu, tag_p = clause_appartenance(collection_id, "t.collection_id")
        dim_vu, dim_p = clause_appartenance(collection_id, "d.collection_id")
        val_vu, val_p = clause_appartenance(collection_id, "v.collection_id")
        n_annot = n_tags = n_tags_laisses = 0
        annotations = conn.execute(f"SELECT id, note FROM annotations WHERE region_id {dans}",
                                   regions).fetchall() if regions else []
        for a in annotations:
            total = conn.execute("SELECT COUNT(*) FROM annotation_tags "
                                 "WHERE annotation_id = ?", (a["id"],)).fetchone()[0]
            vus = conn.execute(
                "SELECT COUNT(*) FROM annotation_tags at JOIN tags t ON t.id = at.tag_id "
                f"WHERE at.annotation_id = ? AND {tag_vu}", (a["id"], *tag_p)).fetchone()[0]
            n_tags_laisses += total - vus
            # Une annotation dont tous les tags restent et qui n'a pas de note ne naît pas.
            if vus or (a["note"] or "").strip():
                n_annot += 1
                n_tags += vus
        copies.update(annotations=n_annot, tags=n_tags)
        laisses["tags"] = n_tags_laisses
        total = n(f"SELECT COUNT(*) FROM region_attribut WHERE region_id {dans}")
        copies["attributs"] = n(
            "SELECT COUNT(*) FROM region_attribut ra "
            "JOIN attribut_valeur v ON v.id = ra.valeur_id "
            "JOIN attribut_dimension d ON d.id = v.dimension_id "
            f"WHERE ra.region_id {dans} AND {val_vu} AND {dim_vu}", *val_p, *dim_p)
        laisses["attributs"] = total - copies["attributs"]
        copies["locuteurs"] = n(f"SELECT COUNT(*) FROM bulle_locuteur WHERE region_id {dans}")
        copies["presences"] = n(
            f"SELECT COUNT(*) FROM personnage_presence WHERE region_id {dans}")
        personnages = n(
            f"SELECT COUNT(*) FROM (SELECT personnage_id FROM bulle_locuteur "
            f"WHERE region_id {dans} UNION SELECT personnage_id FROM personnage_presence "
            f"WHERE region_id {dans})", *regions)
    return {"copies": copies, "laisses": laisses, "personnages": personnages}


def _indexer_une_region_copiee(conn, source: int, copie: int, lemmes_source: str, *,
                               grammaire: bool, annotations: bool) -> None:
    """L'index plein texte et les tokens d'une région copiée (cf. `copier_le_travail`) :
    recopiés de la source quand la copie dit tout ce que la source disait, réindexés
    sinon. Les tags laissés (E5) ne changent pas les lemmes — l'index les porte à part,
    dans `tags_concat`, que `_region_index_payload` relit sur la copie. `lemmes_source` :
    ceux que l'index porte pour la source, lus par lots (`_lemmes_indexes`)."""
    note = conn.execute("SELECT note FROM annotations WHERE region_id = ?",
                        (source,)).fetchone()
    a_une_note = note is not None and (note[0] or "").strip() != ""
    a_des_lemmes_corriges = conn.execute(
        "SELECT 1 FROM token_correction WHERE region_id = ? AND obsolete = 0 "
        "AND lemme IS NOT NULL AND lemme <> '' LIMIT 1", (source,)).fetchone() is not None
    fidele = annotations or (not a_une_note and (grammaire or not a_des_lemmes_corriges))
    # Les tokens sont l'analyse du TEXTE seul : ils suivent toujours tels quels.
    tokens = [dict(t) for t in conn.execute(
        "SELECT ordre, texte, lemme, pos, morph FROM tokens WHERE region_id = ? "
        "ORDER BY ordre", (source,))]
    payload = _region_index_payload(conn, copie)
    if fidele:
        lemmes = lemmes_source
    else:
        # Les lemmes de l'index mêlent ceux du texte, de la note et des corrections ; une
        # couche n'a pas suivi, ils se recalculent sur ce que la copie porte. Sans moteur,
        # ceux du texte et de la note sont vides, comme sur la source.
        from pipeline.nlp import analyse, lemmatise   # import paresseux (évite tout cycle)
        lemmes = (analyse(payload[0])[0] + " " + lemmatise(payload[1])).strip()
        lemmes = _appliquer_corrections(conn, copie, tokens, lemmes, reancrer=False)
    _index_region(conn, copie, payload, lemmes, tokens, neuve=True)

def ranger_copie(conn: sqlite3.Connection, album_id: int, collection_id: int, *,
                 rang: int | None = None) -> bool:
    """RANGE une copie dans une collection, et rend vrai si elle n'y était pas. COL-3,
    tranche 3 — un seul geste pour toutes les portes qui rangent : rejoindre (la route, la
    prise, l'acceptation d'un `rejoindre`), reprendre une copie gardée au fonds, et l'outil
    en ligne de commande. Trois écritures du même rangement finissaient par ne plus dire
    pareil.

    Il ne DÉCIDE rien : qui peut ranger quoi est à `autorisation.Portee`
    (`clause_rejoindre_directe`), le refus de traverser deux projets à
    `rangement_traverse`, et c'est à l'appelant de les avoir posés. Il écrit le
    rangement, son EMPLOI au journal (`journal.journaliser_emploi`) quand il est neuf — re-poser
    un rangement existant ne s'écrit pas, rien n'a changé —, et le projet de la copie si elle
    n'en avait pas encore (une copie importée au fonds prend celui de sa première
    collection, `poser_projet_de_copie`). Ne commite pas."""
    import journal                          # l'emploi s'écrit avec le rangement
    neuf = conn.execute("INSERT OR IGNORE INTO collection_album (collection_id, album_id, rang) "
                        "VALUES (?, ?, ?)", (collection_id, album_id, rang)).rowcount == 1
    if neuf:
        journal.journaliser_emploi(conn, "lien", album_id, collection_id)
        # Une copie qui quitte le fonds, PAR QUELQUE CHEMIN QUE CE SOIT — la réponse à son
        # retour, « Rendre » de la fiche du document, la reprise directe, l'acceptation d'un
        # `rejoindre` ou d'une entrée, l'outil en ligne de commande : le retour qui
        # l'attendait a reçu ce qu'il demandait (relecture croisée de l'écran de la 3a,
        # défaut 1 — la clôture vivait chez deux appelants sur cinq).
        clore_retours_d_une_copie_rangee(conn, album_id, collection_id)
        # Et le `rejoindre` qui demandait CE rangement-là : une portée totale qui range
        # directement y a répondu (relecture croisée de t3a-c4) — sans quoi la demande
        # resterait offerte au propriétaire, pour un geste déjà fait.
        clore_rejoindre_d_un_rangement(conn, album_id, collection_id)
    poser_projet_de_copie(conn, album_id)
    return neuf


def clore_rejoindre_d_un_rangement(conn: sqlite3.Connection, album_id: int,
                                   collection_id: int) -> list[int]:
    """Clôt ACCEPTÉS les `rejoindre` qui attendaient le rangement de cette copie dans CETTE
    collection, qu'on vient de faire, et rend leurs identifiants. COL-3, tranche 3a.

    Le rangement a été fait par un autre chemin que la réponse — une portée totale qui coche
    la case, la prise —, ou par la réponse elle-même, que `_clore_demandes` trouve alors déjà
    close et ne réécrit pas. `repondu_par` est l'agent de la requête. Ne commite pas."""
    import journal
    qui = journal.agent_courant.get()
    clos = []
    for (demande_id,) in conn.execute(
            "SELECT d.id FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.genre = ? AND dd.album_id = ? AND d.collection_id = ? "
            "AND d.reponse IS NULL ORDER BY d.id",
            (DEMANDE_REJOINDRE, album_id, collection_id)).fetchall():
        conn.execute("UPDATE demande_document SET reponse = ?, copie_id = ? "
                     "WHERE demande_id = ? AND reponse IS NULL",
                     (REPONSE_ACCEPTEE, album_id, demande_id))
        conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                     "date_reponse = datetime('now') WHERE id = ? AND reponse IS NULL",
                     (REPONSE_ACCEPTEE, qui, demande_id))
        journal.journaliser(conn, "modification", "demande", demande_id,
                            avant={"reponse": None}, apres={"reponse": REPONSE_ACCEPTEE})
        clos.append(demande_id)
    return clos


def clore_retours_d_une_copie_rangee(conn: sqlite3.Connection, album_id: int,
                                     collection_id: int) -> list[int]:
    """Clôt ACCEPTÉ le retour (`DEMANDE_RENDRE`) qui attendait sur une copie qu'on vient de
    ranger, et rend les identifiants clos. COL-3, écran de la 3a.

    La demande dit ensuite la collection où la copie est RÉELLEMENT revenue : ses colonnes
    `collection_id` / `collection_nom` sont réécrites (relecture croisée, défaut 2 — la fiche
    du projet lisait « Rendre … à « base » — acceptée » quand l'administrateur l'avait rangée
    ailleurs). Sur la demande et non sur sa ligne, parce qu'un retour n'a qu'UNE ligne et que
    sa collection est celle que la fiche lit ; sans changement de schéma, la ligne n'en a
    pas. La collection DEMANDÉE n'est pas perdue : l'événement du journal qui clôt la demande
    la porte en `avant`. Celle-ci dit aussi sa copie (`copie_id`).

    `repondu_par` est l'agent de la requête (`journal.agent_courant`) : qui a rangé ; NULL
    pour un geste sans agent (l'outil en ligne de commande). Ne commite pas ; ne décide
    rien — qui peut ranger est réglé avant."""
    import journal
    ligne = conn.execute("SELECT nom FROM collection WHERE id = ?", (collection_id,)).fetchone()
    nom = ligne[0] if ligne else None
    qui = journal.agent_courant.get()
    clos = []
    for demande_id, demandee, demandee_nom in conn.execute(
            "SELECT d.id, d.collection_id, d.collection_nom FROM demande d "
            "JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.genre = ? AND dd.album_id = ? AND d.reponse IS NULL ORDER BY d.id",
            (DEMANDE_RENDRE, album_id)).fetchall():
        conn.execute("UPDATE demande_document SET reponse = ?, copie_id = ? "
                     "WHERE demande_id = ? AND reponse IS NULL",
                     (REPONSE_ACCEPTEE, album_id, demande_id))
        conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                     "date_reponse = datetime('now'), collection_id = ?, collection_nom = ? "
                     "WHERE id = ? AND reponse IS NULL",
                     (REPONSE_ACCEPTEE, qui, collection_id, nom, demande_id))
        journal.journaliser(conn, "modification", "demande", demande_id,
                            avant={"reponse": None, "collection_id": demandee,
                                   "collection": demandee_nom},
                            apres={"reponse": REPONSE_ACCEPTEE, "collection_id": collection_id,
                                   "collection": nom, "copie_id": album_id})
        clos.append(demande_id)
    return clos


def clore_rejoindre_d_une_copie_au_fonds(conn: sqlite3.Connection, album_id: int) -> list[int]:
    """Une copie vient de partir AU FONDS (sortie de sa dernière collection) : les
    `rejoindre` qui la visaient se closent REFUSÉS, et l'on rend leurs identifiants. COL-3,
    écran de la 3a (relecture croisée, défaut 3 ; option fermée). Les demandes d'EN PARTIR
    (`DEMANDE_AMORCER`, tranche 3b) aussi : leur consentement était celui des propriétaires
    des collections que la copie vient de quitter, et une copie gardée ne se lit plus que
    par qui tient le fonds.

    Accepter un `rejoindre` sur une copie gardée la RENDRAIT — sans que son responsable l'ait
    demandé, et sous les mots « ranger aussi », qui supposent une copie déjà rangée. Reprendre
    une copie gardée relève du RETOUR (`DEMANDE_RENDRE`), comme une destruction clôt les
    demandes qui la visaient. `repondu_par` est qui l'a retirée (`journal.agent_courant`).
    Ne fait rien si la copie est encore rangée quelque part. Ne commite pas."""
    import journal
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ?",
                    (album_id,)).fetchone() is not None:
        return []
    qui = journal.agent_courant.get()
    clos = []
    for (demande_id,) in conn.execute(
            "SELECT d.id FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
            "WHERE d.genre IN (?, ?) AND dd.album_id = ? AND d.reponse IS NULL ORDER BY d.id",
            (*GENRES_CONSENTIS, album_id)).fetchall():
        conn.execute("UPDATE demande_document SET reponse = ? WHERE demande_id = ? "
                     "AND reponse IS NULL", (REPONSE_REFUSEE, demande_id))
        conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                     "date_reponse = datetime('now') WHERE id = ? AND reponse IS NULL",
                     (REPONSE_REFUSEE, qui, demande_id))
        journal.journaliser(conn, "modification", "demande", demande_id,
                            avant={"reponse": None},
                            apres={"reponse": REPONSE_REFUSEE, "copie_au_fonds": album_id})
        clos.append(demande_id)
    return clos


def retirer_document_sans_copie(conn: sqlite3.Connection, document_id: int | None) -> bool:
    """Efface la ligne d'un document qui n'a PLUS aucune copie de travail. Vrai si elle
    est partie.

    À appeler après avoir détruit un album. Depuis la tranche 3 un document peut avoir
    plusieurs copies SŒURS (`creer_copie`) : détruire l'une n'emporte pas l'identité des
    autres, et le document part avec sa DERNIÈRE copie (D5). C'est ici que cela se garde,
    pas chez chaque appelant."""
    if document_id is None:
        return False
    return conn.execute(
        "DELETE FROM document WHERE id = ? "
        "AND NOT EXISTS (SELECT 1 FROM albums WHERE document_id = ?)",
        (document_id, document_id)).rowcount == 1


def albums_sans_document(conn: sqlite3.Connection) -> list[int]:
    """Albums qui ne sont la copie d'AUCUN document. Les chemins d'écriture de
    l'application le posent tous (créer un album, en créer un en important depuis
    ShareDocs) et la migration v30 l'a posé sur l'existant : c'est la formulation
    exécutable de « tout album appartient à l'instance », sur le modèle
    d'`albums_orphelins`. Une ligne ici dit qu'un chemin d'écriture l'a oublié."""
    return [r[0] for r in conn.execute(
        "SELECT id FROM albums WHERE document_id IS NULL ORDER BY id")]


def albums_sans_copie(conn: sqlite3.Connection) -> list[int]:
    """Albums sans ligne `copie` (v31) — la provenance de la copie manque. Le chemin
    d'écriture la pose (`creer_document`) et la migration v31 l'a posée sur l'existant : une
    ligne ici dit qu'un chemin d'écriture l'a oubliée, ou qu'un album a été posé par
    `INSERT`. La règle de suppression directe y lit « a créé cette copie » : sans ligne,
    personne ne l'a créée, et elle se demande."""
    return [r[0] for r in conn.execute(
        "SELECT id FROM albums a WHERE NOT EXISTS "
        "(SELECT 1 FROM copie c WHERE c.album_id = a.id) ORDER BY id")]


def albums_hors_de_leur_projet(conn: sqlite3.Connection) -> list[int]:
    """Albums rangés dans une collection d'un AUTRE projet que le leur. Doit rester vide :
    le rangement ne traverse pas les projets, et une collection n'en change pas. C'est ce
    qui permet de lire le projet d'une copie sur elle sans consulter ses collections —
    une ligne ici dit que les deux lectures ne répondent plus pareil."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT a.id FROM albums a "
        "JOIN collection_album ca ON ca.album_id = a.id "
        "JOIN collection c ON c.id = ca.collection_id "
        f"WHERE a.projet_id IS NOT NULL AND {sql_projet_de('c')} IS NOT a.projet_id "
        "ORDER BY a.id")]


# Les DEMANDES (COL-3, tranche 2) — les listes vivent dans le code, pas dans un `CHECK` (la
# raison est écrite sur la table). Un genre par usage du mécanisme ; la tranche 2 en ouvre
# deux, la suivante y ajoutera l'entrée de documents dans un projet. Une réponse par
# demande, dite comme un ÉTAT et non comme un geste : `acceptee` ou `refusee`, quel que
# soit le genre — « détruire » et « garder » sont les mots de l'écran pour un document,
# pas ceux d'une admission.
DEMANDE_SUPPRESSION_DOCUMENT = "suppression_document"
DEMANDE_SUPPRESSION_PROJET = "suppression_projet"
# COL-3, tranche 3 — deux genres de plus. Une ENTRÉE de documents : un responsable demande
# qu'un ou plusieurs documents du fonds entrent dans une collection de son projet, et un
# administrateur répond document par document (D9). Un REJOINDRE : un écrivain demande à
# ranger dans sa collection une copie qu'il lit sans tenir toutes ses collections, et le
# propriétaire de celles-ci consent (D4 stricte, D11). Tous deux nomment leur collection
# d'ARRIVÉE (`demande.collection_id` et son nom).
DEMANDE_ENTREE_DOCUMENTS = "entree_documents"
DEMANDE_REJOINDRE = "rejoindre"
# COL-3, tranche 3a (écran tranché par Hugo sur maquette, 2026-10-17) — RENDRE une copie
# gardée au fonds : le responsable du projet de la copie demande qu'elle revienne dans une
# collection de ce projet, et un administrateur répond (« Rendre à … » / « Garder au
# fonds »). Un genre à lui, et non une ligne d'entrée de documents comme le serveur de la
# prise l'écrivait d'abord : une entrée fait NAÎTRE une copie vierge, un retour rend une
# copie qui existe avec tout son travail — l'écran leur donne deux mots et deux boutons, et
# un retour ne s'attend qu'une fois par COPIE, quelle que soit la collection nommée. Une
# demande par copie, qui nomme sa collection d'arrivée (`demande.collection_id`).
DEMANDE_RENDRE = "rendre_copie"
# COL-3, tranche 3b (E4, Hugo, 2026-10-20) — EN PARTIR d'un travail du projet : un écrivain
# demande une copie à lui, amorcée avec le travail d'une copie qu'il lit jusqu'au cran dit
# (`demande.cran`), sans tenir toutes les collections où ce travail vit. La règle de
# `rejoindre`, telle quelle — le propriétaire de chacune consent, ou un administrateur :
# copier un travail dans une autre collection le fait lire par d'autres, comme le partager.
# Une demande par copie SOURCE (`demande_document.album_id`), qui nomme sa collection
# d'arrivée ; acceptée, la copie neuve est dite par `copie_id`.
DEMANDE_AMORCER = "amorcer"
GENRES_DEMANDE = (DEMANDE_SUPPRESSION_DOCUMENT, DEMANDE_SUPPRESSION_PROJET,
                  DEMANDE_ENTREE_DOCUMENTS, DEMANDE_REJOINDRE, DEMANDE_RENDRE,
                  DEMANDE_AMORCER)
# Les genres qui attendent le CONSENTEMENT des propriétaires des collections où vit la
# copie visée — et non la réponse de qui tient le fonds (`Portee.peut_repondre_a`).
GENRES_CONSENTIS = (DEMANDE_REJOINDRE, DEMANDE_AMORCER)
REPONSE_ACCEPTEE = "acceptee"
REPONSE_REFUSEE = "refusee"
REPONSES_DEMANDE = (REPONSE_ACCEPTEE, REPONSE_REFUSEE)
# L'ÉTAT d'une demande de plusieurs documents dont les réponses sont mêlées (D9) — jamais
# une réponse qu'on envoie : on répond à chaque document `acceptee` ou `refusee`, et la
# demande se clôt sur cet état quand le dernier a la sienne.
REPONSE_PARTIELLE = "partielle"


def etat_des_reponses(reponses) -> str | None:
    """L'état d'une demande d'après les réponses de ses documents : `acceptee` ou `refusee`
    quand elles le sont toutes, `partielle` quand elles sont mêlées, None tant qu'un document
    attend (ou qu'il n'y en a aucun). La demande se clôt à la DERNIÈRE réponse, pas à la
    première."""
    reponses = list(reponses)
    if not reponses or None in reponses:
        return None
    if set(reponses) == {REPONSE_ACCEPTEE}:
        return REPONSE_ACCEPTEE
    if set(reponses) == {REPONSE_REFUSEE}:
        return REPONSE_REFUSEE
    return REPONSE_PARTIELLE


def un_proprietaire_tient_toute_la_copie(conn: sqlite3.Connection, album_id: int) -> bool:
    """Un même principal possède-t-il CHACUNE des collections où vit cette copie ? Un FAIT,
    pour dire juste qui répondra à une demande de la rejoindre (COL-3, tranche 3a, Hugo,
    2026-10-17) : un propriétaire qui les tient toutes, ou — personne ne les tenant, une
    collection sans propriétaire comprise — un administrateur seul. Les propriétaires sont
    ceux de `collection_acces` et, pour une collection de BASE, les responsables de son
    projet (la dérivation de D10, relue ici sans rien décider : `autorisation.Portee` reste
    seule à dire qui PEUT répondre). Une copie rangée nulle part : faux."""
    collections = [r[0] for r in conn.execute(
        "SELECT collection_id FROM collection_album WHERE album_id = ?", (album_id,))]
    communs = None
    for cid in collections:
        proprietaires = {(r[0], r[1]) for r in conn.execute(
            "SELECT genre, principal FROM collection_acces WHERE collection_id = ? "
            "AND niveau = 'proprietaire'", (cid,))}
        proprietaires |= {(r[0], r[1]) for r in conn.execute(
            f"SELECT pa.genre, pa.principal FROM collection c JOIN projet_acces pa "
            f"ON pa.projet_id = {sql_projet_de('c')} AND pa.role = 'responsable' "
            "WHERE c.id = ? AND c.base = 1", (cid,))}
        communs = proprietaires if communs is None else communs & proprietaires
    return bool(communs)


def demandes_vers_collection(conn: sqlite3.Connection, collection_id: int) -> list[int]:
    """Les demandes EN ATTENTE qui nomment cette collection comme ARRIVÉE — une entrée de
    documents, un rejoindre, un retour (`DEMANDE_RENDRE`). À clore quand la collection disparaît : son identifiant se
    réattribue (`collection` n'a pas d'`AUTOINCREMENT`), et une demande acceptée plus tard
    rangerait sinon dans la collection créée ensuite, une autre étude."""
    return [r[0] for r in conn.execute(
        "SELECT id FROM demande WHERE collection_id = ? AND reponse IS NULL ORDER BY id",
        (collection_id,))]
# Le « pourquoi » d'une demande est un texte libre ; borné pour qu'un champ de motif ne
# devienne pas un dépôt de documents.
LONGUEUR_MOTIF = 2000


# Une date d'embargo est censée être en ISO (AAAA-MM-JJ) ; le champ est du TEXTE libre, et
# rien ne l'impose à l'écriture. Ce qui n'est pas de cette forme est ILLISIBLE et se DIT :
# retenir sans le dire ferait passer une faute de frappe pour une décision.
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def etat_embargo(bloc, aujourdhui: str | None = None) -> str | None:
    """Où en est la date d'embargo d'une collection — DÉRIVÉ, jamais stocké (DROIT-1).

    `bloc` : une ligne/dict de `collection`. Renvoie `None` (aucune date déclarée),
    `'pendant'` (la date n'est pas atteinte), `'echu'` (elle l'est, le jour même compris)
    ou `'illisible'` (la date est là mais pas en ISO).

    Cette fonction dit seulement OÙ L'ON EN EST ; elle ne dit pas quoi en faire. Ce qu'on
    en fait est écrit à la SORTIE (`tools/iiif_manifest.py`), parce que le régime de
    diffusion n'est opposable que là. Mais l'état, lui, est défini ICI et une seule fois :
    l'écran Collections et le générateur de manifestes le lisent tous les deux, et deux
    lectures divergentes du même champ finiraient par se contredire à l'écran.
    """
    # `bloc` peut être un `sqlite3.Row` (pas de `.get`) autant qu'un dict : les deux
    # circulent dans le projet, et exiger l'un des deux ne ferait que déplacer la faute.
    date = ("" if bloc is None else
            (dict(bloc).get("date_embargo") or "")).strip()
    if not date:
        return None
    if not _ISO.match(date):
        return "illisible"
    # Comparaison de chaînes : en ISO, l'ordre du texte EST l'ordre du temps.
    return "echu" if date <= (aujourdhui or _dt.date.today().isoformat()) else "pendant"


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

    Elle n'est PAS la collection de base du projet de repli (v31 ; Hugo, 2026-10-17) : ce
    projet a la sienne, neuve, comme tout projet. Elle reste désignée par son NOM réservé.
    """
    r = conn.execute("SELECT id FROM collection WHERE nom = ?",
                     (NOM_COLLECTION_DEFAUT,)).fetchone()
    if r:
        return r[0]
    # v29 — elle naît dans le projet de repli, comme toute collection qui n'en nomme aucun.
    # La garde de table vaut pour la migration v23 rejouée sur un schéma minimal, où
    # `collection` existe sans `projet` autour (tests de migration).
    a_projet = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'projet'").fetchone()
    a_colonne = "projet_id" in {r[1] for r in conn.execute("PRAGMA table_info(collection)")}
    cur = conn.execute(
        "INSERT INTO collection (nom, description) VALUES (?, ?)",
        (NOM_COLLECTION_DEFAUT,
         "Créée automatiquement : tout album doit appartenir à une collection, qui est "
         "l'unité de cloisonnement des accès. Renommez-la et décrivez-la, ou déplacez "
         "ses albums vers des collections d'étude."))
    if a_projet and a_colonne:
        conn.execute("UPDATE collection SET projet_id = ? WHERE id = ?",
                     (projet_par_defaut(conn), cur.lastrowid))
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


def clause_appartenance(collection_id: int | None,
                        alias: str = "collection_id") -> tuple[str, list]:
    """Fragment SQL `(sql, params)` restreignant un TERME du vocabulaire (tag, domaine,
    dimension, valeur) à son APPARTENANCE : global ⊕ local à `collection_id`.

    C'est la règle d'AUTH-2 posée sur une COLLECTION et non sur une personne. Les deux
    questions se ressemblent sans se confondre : `Portee.clause_terme` dit ce qu'un
    LECTEUR voit (ses collections lisibles), celle-ci dit ce qu'une COLLECTION emporte
    quand elle sort de l'instance — « quel que soit qui exporte » (AUTH-11). Un export de
    dépôt est FIGÉ : le borner sur la portée de qui a cliqué rendrait deux exports de la
    même collection différents sans que rien ne le dise.

    `collection_id=None` vaut « corpus entier » et ne filtre rien : c'est le défaut des
    CLI, jamais celui d'une route — ni de dépôt (`routes/depot.py`, où la collection est
    un segment de chemin), ni d'export d'ALBUM, qui suit la même règle depuis le
    2026-10-07 (`socle._vocabulaire_d_export`) et sort toujours au titre d'une collection :
    `socle._collection_d_export` en rend une ou lève, portée totale comprise.

    La formule vivait déjà ici, dépliée dans `lexique_resume` — c'est-à-dire dans le
    calcul du « % défini », que la fiche d'AUTH-11 désigne comme la règle à suivre. La
    nommer évite d'en semer des copies dans chaque outil d'export.
    """
    if collection_id is None:
        return "1", []
    return f"({alias} IS NULL OR {alias} = ?)", [collection_id]


def lexique_resume(conn: sqlite3.Connection, collection_id: int | None = None,
                   *, clause: tuple[str, list] | None = None) -> dict:
    """Indicateur « % défini » du lexique situé (A4, N7) : part des termes du vocabulaire
    ÉMERGENT (domaines + dimensions + valeurs + tags) à l'état `defini`. Scopé par APPARTENANCE
    si `collection_id` (global ⊕ local à la collection). Nourrit la qualité de la Collection.

    `clause` — AUTH-2 : fragment SQL de portée `(sql, params)` sur la colonne nue
    `collection_id`, fourni par l'appelant (`Portee.clause_terme`). Il généralise
    `collection_id` à PLUSIEURS collections lisibles. Ce module reçoit un fragment plutôt
    qu'une `Portee` pour ne pas dépendre de `autorisation` : la règle reste écrite à un
    seul endroit, et c'est là-bas. Sans `clause`, le fragment est celui de
    `clause_appartenance` — la même formule, nommée.
    """
    if clause is None:
        clause = clause_appartenance(collection_id)
    sql_scope, params = clause
    scope = f" AND ({sql_scope})"
    params = list(params)
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
                  lemmes: str, tokens: list, *, neuve: bool = False) -> None:
    """Persistance partagée : écrit la ligne FTS (ocr/note/tags + `lemmes` fournis)
    et les `tokens` fournis. `lemmes=""` / `tokens=[]` ⇒ indexation STRUCTURELLE
    (sans NLP). Utilisé par `reindex_region` (unitaire), `reindex_all` (lot) et la
    migration (structurelle).

    `neuve` : la région vient de naître dans cette transaction (une région copiée, COL-3,
    tranche 3b) et l'index ne porte rien d'elle — ses identifiants ne reviennent jamais
    (v30). L'effacement préalable est alors sauté : `region_id` étant `UNINDEXED`, il
    parcourait l'index entier pour chaque région."""
    if not neuve:
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
    # NLP-2 : ce que l'annotateur a vu voyage avec sa correction, survivante ou orpheline.
    ins = ("INSERT INTO token_correction "
           "(region_id, ordre, forme, lemme, pos, morph, etat, auteur, date_modif, obsolete, "
           f" {', '.join(COLONNES_VU)}) "
           f"VALUES ({', '.join('?' * (10 + len(COLONNES_VU)))})")
    for c, no in survivors:
        conn.execute(ins, (region_id, no, new_forme[no], c["lemme"], c["pos"], c["morph"],
                           c["etat"], c["auteur"], c["date_modif"], 0,
                           *(c[k] for k in COLONNES_VU)))
    park = -1                                   # ordres négatifs : ne rejoignent aucun token
    for c in orphans:
        conn.execute(ins, (region_id, park, c["forme"], c["lemme"], c["pos"], c["morph"],
                           c["etat"], c["auteur"], c["date_modif"], 1,
                           *(c[k] for k in COLONNES_VU)))
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
    de régions traitées. Sans spaCy : réindexation structurelle (repli propre).

    Un run qui ÉCHOUE ou qu'on INTERROMPT (Ctrl+C) laisse lui aussi une activité
    CLOSE au journal (A3), avec son bilan partiel — sans quoi une réindexation ratée
    et une réindexation jamais lancée seraient indistinguables."""
    from pipeline.nlp import analyse_batch, model_info
    import journal
    aid = journal.ouvrir_activite(conn, "reindex_nlp", agent="spacy", agent_type="moteur",
                                  version=(model_info().get("model") or None),
                                  params={"chunk": chunk})
    # La trace du DÉPART est validée tout de suite, et c'est ce qui la fait survivre à
    # l'échec de ce qui suit. Sans ce commit, l'activité n'était persistée qu'en même temps
    # que le PREMIER lot : une panne avant lui — un `analyse_batch` qui lève sur le lot
    # initial, un « database is locked » sur l'un des deux SELECT ci-dessous — la faisait
    # partir avec le `rollback` de l'appelant. Le journal ne gardait alors que les
    # réindexations qui avaient marché, et une réindexation ratée ne se distinguait pas
    # d'une réindexation jamais lancée. C'est la panne réparée le 2026-09-08 dans
    # `journal.passe_ml`, sur l'autre chemin de la même famille.
    #
    # Ouvrir puis commiter plutôt qu'inscrire un run déjà clos (`inscrire_run_termine`) :
    # ici les lots SONT validés au fur et à mesure, si bien qu'une panne tardive laisse
    # une activité déjà persistée. Réinscrire en produirait une SECONDE, et le journal
    # compterait deux runs là où il y en a eu un.
    conn.commit()
    n = 0
    try:
        rows = conn.execute("SELECT id, ocr_texte FROM regions ORDER BY id").fetchall()
        notes = {r["region_id"]: (r["note"] or "")
                 for r in conn.execute("SELECT region_id, note FROM annotations")}
        for start in range(0, len(rows), chunk):
            batch = rows[start:start + chunk]
            ocr_res = analyse_batch([r["ocr_texte"] or "" for r in batch])
            note_res = analyse_batch([notes.get(r["id"], "") for r in batch])
            for j, r in enumerate(batch):
                toks = ocr_res[j][1]
                lemmes = (ocr_res[j][0] + " " + note_res[j][0]).strip()
                fiable = bool(toks) or not (r["ocr_texte"] or "").strip()
                lemmes = _appliquer_corrections(conn, r["id"], toks, lemmes,
                                                reancrer=fiable)
                _index_region(conn, r["id"], _region_index_payload(conn, r["id"]),
                              lemmes, toks)
                n += 1
            conn.commit()
        # L'ÉPILOGUE est DANS le `try`, et ce n'est pas de la symétrie : les deux
        # écritures de `meta` et la clôture peuvent lever un « database is locked » comme
        # n'importe quelle écriture SQLite. Hors du `try`, une panne ici laissait
        # l'activité ouverte alors que tout le travail était fait — le même mensonge, à
        # la dernière ligne près.
        info = model_info()
        meta = {"nlp_model": info.get("model", ""), "nlp_spacy": info.get("spacy", ""),
                "nlp_reindexed_count": str(n), "nlp_reindexed_at": "datetime"}
        for cle, val in meta.items():
            if val == "datetime":
                conn.execute(
                    "INSERT INTO meta (cle, valeur) VALUES (?, datetime('now')) "
                    "ON CONFLICT(cle) DO UPDATE SET valeur = datetime('now')", (cle,))
            else:
                conn.execute(
                    "INSERT INTO meta (cle, valeur) VALUES (?, ?) "
                    "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", (cle, val))
        journal.cloturer_activite(conn, aid, comptes={"regions": n})
        conn.commit()
    except BaseException as exc:
        # `BaseException` et non `Exception`, et c'est le seul appelant qui l'exige :
        # `tools/reindex_nlp.py` est une CLI qui tourne des MINUTES sur le fil principal,
        # donc Ctrl+C y est l'interruption réaliste — et `KeyboardInterrupt` n'est pas une
        # `Exception`. Sans cette largeur, une réindexation abandonnée à la main laissait
        # son activité OUVERTE pour toujours, et tout consommateur du journal la lisait
        # comme un run encore en cours. `journal.passe_ml` s'en tient à `Exception` sans
        # avoir ce défaut : il vit dans un fil de travail, où Ctrl+C n'arrive jamais.
        #
        # DEMANDÉE, donc pas une panne — la distinction est celle de `passe_ml`, et elle
        # compte dans une couche append-only où l'on ne se corrige plus.
        interrompu = isinstance(exc, (KeyboardInterrupt, SystemExit))
        bilan = {"regions": n, "interrompu" if interrompu else "echec": True}
        # Le bilan reste MINIMAL par contrainte : `comptes` SORT de l'instance
        # (`metadonnees_collection`, `provenance_export`), et y verser le message de
        # l'exception enverrait des chemins serveur au dépôt. `regions` dit ce qui a été
        # traité avant l'arrêt, ce qui est l'information utile pour reprendre.
        #
        # Le `try` interne existe parce que tenir le journal ne doit jamais changer
        # l'erreur que l'appelant voit : un `commit()` qui lèverait « database is locked »
        # transformerait ici une panne de modèle en 409 « réessayer ».
        try:
            conn.rollback()
            journal.cloturer_activite(conn, aid, comptes=bilan)
            conn.commit()
        except Exception:
            pass
        raise
    return n


def unindex_region(conn: sqlite3.Connection, region_id: int) -> None:
    """Retire une région de l'index FTS (suppression de région)."""
    conn.execute("DELETE FROM recherche WHERE region_id = ?", (region_id,))


if __name__ == "__main__":
    init_db()
    print(f"Base initialisée : {DB_PATH} (schéma v{SCHEMA_VERSION})")
