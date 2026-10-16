-- Base v29 faite par le code de 10a3a90 (ses routes, sous trois comptes), vidée par
-- `sqlite3.Connection.iterdump` (la table plein texte recréée par son CREATE).
-- Refaite par : python tools/fabriquer_base_de_version.py 10a3a90 tests/bases/v29-10a3a90.sql
-- Ce qu'elle contient :
--   albums_vivants : [1, 2, 3]
--   album_detruit : 4
--   planche_detruite : 8
--   region_detruite : 16
--   personnage_detruit : 3
--   max : {"albums": 3, "planches": 6, "regions": 12, "personnages": 2}
--   comptes : {"albums": 3, "planches": 6, "regions": 12, "personnages": 2, "evenement": 50, "activite": 1, "tokens": 36, "annotations": 3, "recherche": 6}
--   activites : [["ocr", "{\"planche_id\": 8}"]]
BEGIN TRANSACTION;
CREATE TABLE activite (
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
INSERT INTO "activite" VALUES(1,'ocr','easyocr','moteur',NULL,NULL,'{"planche_id": 8}','{"crees": 0, "modifies": 0, "remplaces": 0}','2026-10-15 15:07:51','2026-10-15 15:07:51');
CREATE TABLE albums (
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
INSERT INTO "albums" VALUES(1,'Album 1',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-15 15:07:45');
INSERT INTO "albums" VALUES(2,'Album 2',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-15 15:07:51');
INSERT INTO "albums" VALUES(3,'Album 3',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-15 15:07:51');
CREATE TABLE annotation_tags (
    annotation_id  INTEGER REFERENCES annotations(id) ON DELETE CASCADE,
    tag_id         INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_id, tag_id)
);
INSERT INTO "annotation_tags" VALUES(1,1);
INSERT INTO "annotation_tags" VALUES(2,1);
INSERT INTO "annotation_tags" VALUES(3,1);
CREATE TABLE annotations (
    id                 INTEGER PRIMARY KEY,
    region_id          INTEGER UNIQUE REFERENCES regions(id) ON DELETE CASCADE,
    note               TEXT,
    date_creation      TEXT DEFAULT (datetime('now')),
    date_modification  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "annotations" VALUES(1,2,'vu','2026-10-15 15:07:50','2026-10-15 15:07:50');
INSERT INTO "annotations" VALUES(2,6,'vu','2026-10-15 15:07:51','2026-10-15 15:07:51');
INSERT INTO "annotations" VALUES(3,10,'vu','2026-10-15 15:07:51','2026-10-15 15:07:51');
CREATE TABLE attribut_dimension (
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
INSERT INTO "attribut_dimension" VALUES(1,'case','cadrage',NULL,NULL,NULL,'provisoire',NULL,'2026-10-15 15:07:45');
CREATE TABLE attribut_valeur (
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
INSERT INTO "attribut_valeur" VALUES(1,1,'gros plan',NULL,NULL,'provisoire',NULL,'2026-10-15 15:07:45');
CREATE TABLE bulle_locuteur (
    region_id      INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "bulle_locuteur" VALUES(2,1,'2026-10-15 15:07:50');
INSERT INTO "bulle_locuteur" VALUES(6,1,'2026-10-15 15:07:51');
INSERT INTO "bulle_locuteur" VALUES(10,1,'2026-10-15 15:07:51');
CREATE TABLE collection (
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
    projet_id         INTEGER REFERENCES projet(id)
    -- v29 (COL-3) : le PROJET auquel la collection appartient. NULLABLE, et NULL se lit
    -- « le projet de repli » — à un seul endroit, `sql_projet_de`. Deux raisons, mesurées :
    -- SQLite refuse d'AJOUTER une colonne `NOT NULL` qui porte une clé étrangère (un défaut
    -- non nul est exigé par l'un, interdit par l'autre), si bien qu'une base migrée ne
    -- pourrait pas porter la contrainte qu'une base neuve porterait ; et deux schémas qui
    -- divergent sur une garde valent moins qu'une règle unique dans le code (même doctrine
    -- que `utilisateur.nature`). Clé SANS action : ni `SET NULL` — supprimer un projet
    -- reverserait ses collections dans le repli sans que personne l'ait décidé —, ni
    -- `CASCADE`, qui laisserait des albums hors de toute collection.
    --
    -- Ce commentaire est SOUS la colonne, et il doit y rester : pour retirer la dernière
    -- colonne d'une table, SQLite remonte jusqu'à la première virgule qu'il trouve — celles
    -- d'un commentaire comprises — et rend alors un schéma tronqué (« incomplete input »,
    -- mesuré sur 3.49 par le test de migration, qui défait la v29 de cette façon).
);
INSERT INTO "collection" VALUES(1,'Corpus principal',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-15 15:07:45',1);
INSERT INTO "collection" VALUES(2,'Incubateur',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-15 15:07:45',1);
CREATE TABLE collection_acces (
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
INSERT INTO "collection_acces" VALUES(1,'utilisateur','lea','ecriture',0,'2026-10-15 15:07:45');
INSERT INTO "collection_acces" VALUES(2,'utilisateur','lea','ecriture',0,'2026-10-15 15:07:45');
INSERT INTO "collection_acces" VALUES(1,'utilisateur','sam','ecriture',0,'2026-10-15 15:07:45');
CREATE TABLE collection_album (
    collection_id  INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    album_id       INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    rang           INTEGER,
    PRIMARY KEY (collection_id, album_id)
);
INSERT INTO "collection_album" VALUES(1,1,NULL);
INSERT INTO "collection_album" VALUES(1,2,NULL);
INSERT INTO "collection_album" VALUES(2,3,NULL);
CREATE TABLE contribution (
    id             INTEGER PRIMARY KEY,
    album_id       INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    nom            TEXT NOT NULL,
    role_id        INTEGER REFERENCES contribution_role(id) ON DELETE SET NULL,
    rang           INTEGER,
    date_creation  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE contribution_role (
    id             INTEGER PRIMARY KEY,
    label          TEXT UNIQUE NOT NULL,          -- ex. « scénariste », « dessinateur »
    bucket         TEXT NOT NULL DEFAULT 'contributor',  -- DCterms : 'creator' | 'contributor'
    marc           TEXT,                          -- code MARC Relators (ex. 'aut', 'art'), optionnel
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "contribution_role" VALUES(1,'scénariste','creator','aut','2026-10-15 15:07:45');
INSERT INTO "contribution_role" VALUES(2,'dessinateur','creator','art','2026-10-15 15:07:45');
INSERT INTO "contribution_role" VALUES(3,'coloriste','contributor','clr','2026-10-15 15:07:45');
INSERT INTO "contribution_role" VALUES(4,'encreur','contributor',NULL,'2026-10-15 15:07:45');
INSERT INTO "contribution_role" VALUES(5,'lettreur','contributor',NULL,'2026-10-15 15:07:45');
INSERT INTO "contribution_role" VALUES(6,'traducteur','contributor','trl','2026-10-15 15:07:45');
INSERT INTO "contribution_role" VALUES(7,'préfacier','contributor','aui','2026-10-15 15:07:45');
CREATE TABLE domaine (
    id             INTEGER PRIMARY KEY,
    nom            TEXT NOT NULL UNIQUE,
    -- Lexique situé (A4) — SKOS : même couche définitionnelle que dimensions/valeurs/tags.
    definition     TEXT,
    note_portee    TEXT,
    etat           TEXT NOT NULL DEFAULT 'provisoire',   -- 'provisoire' | 'defini'
    collection_id  INTEGER REFERENCES collection(id) ON DELETE SET NULL,
    date_creation  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE evenement (
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
INSERT INTO "evenement" VALUES(1,NULL,'creation','hugo','humain','collection',1,NULL,'{"nom": "Corpus principal", "proprietaire": "hugo"}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(2,NULL,'creation','hugo','humain','collection',2,NULL,'{"nom": "Incubateur", "proprietaire": "hugo"}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(3,NULL,'lien','hugo','humain','collection_acces',1,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "lea"}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(4,NULL,'lien','hugo','humain','collection_acces',2,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "lea"}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(5,NULL,'lien','hugo','humain','collection_acces',1,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "sam"}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(6,NULL,'creation','lea','humain','regions',1,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 1, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(7,NULL,'creation','lea','humain','regions',2,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:45');
INSERT INTO "evenement" VALUES(8,NULL,'modification','lea','humain','regions',2,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 0 0", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(9,NULL,'creation','lea','humain','annotations',2,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(10,NULL,'lien','lea','humain','bulle_locuteur',2,NULL,'{"personnage_id": 1}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(11,NULL,'lien','lea','humain','personnage_presence',1,NULL,'{"personnage_id": 2}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(12,NULL,'validation','lea','humain','planches',1,NULL,'{"validee": true}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(13,NULL,'creation','lea','humain','regions',3,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 2, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(14,NULL,'creation','lea','humain','regions',4,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 3, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:50');
INSERT INTO "evenement" VALUES(15,NULL,'modification','lea','humain','regions',4,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 3, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 0 1", "ordre": 1, "parent_id": 3, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(16,NULL,'creation','sam','humain','regions',5,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 3, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(17,NULL,'creation','sam','humain','regions',6,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 5, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(18,NULL,'modification','sam','humain','regions',6,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 5, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 1 0", "ordre": 1, "parent_id": 5, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(19,NULL,'creation','sam','humain','annotations',6,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(20,NULL,'lien','sam','humain','bulle_locuteur',6,NULL,'{"personnage_id": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(21,NULL,'lien','sam','humain','personnage_presence',5,NULL,'{"personnage_id": 2}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(22,NULL,'validation','sam','humain','planches',3,NULL,'{"validee": true}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(23,NULL,'creation','sam','humain','regions',7,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 4, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(24,NULL,'creation','sam','humain','regions',8,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 7, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(25,NULL,'modification','sam','humain','regions',8,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 7, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 1 1", "ordre": 1, "parent_id": 7, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(26,NULL,'creation','lea','humain','regions',9,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 5, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(27,NULL,'creation','lea','humain','regions',10,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 9, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(28,NULL,'modification','lea','humain','regions',10,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 9, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 2 0", "ordre": 1, "parent_id": 9, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(29,NULL,'creation','lea','humain','annotations',10,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(30,NULL,'lien','lea','humain','bulle_locuteur',10,NULL,'{"personnage_id": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(31,NULL,'lien','lea','humain','personnage_presence',9,NULL,'{"personnage_id": 2}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(32,NULL,'validation','lea','humain','planches',5,NULL,'{"validee": true}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(33,NULL,'creation','lea','humain','regions',11,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 6, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(34,NULL,'creation','lea','humain','regions',12,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 11, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(35,NULL,'modification','lea','humain','regions',12,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 11, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 2 1", "ordre": 1, "parent_id": 11, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(36,NULL,'creation','lea','humain','regions',13,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 7, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(37,NULL,'creation','lea','humain','regions',14,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 13, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(38,NULL,'modification','lea','humain','regions',14,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 13, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 3 0", "ordre": 1, "parent_id": 13, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(39,NULL,'creation','lea','humain','annotations',14,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(40,NULL,'lien','lea','humain','bulle_locuteur',14,NULL,'{"personnage_id": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(41,NULL,'lien','lea','humain','personnage_presence',13,NULL,'{"personnage_id": 2}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(42,NULL,'validation','lea','humain','planches',7,NULL,'{"validee": true}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(43,NULL,'creation','lea','humain','regions',15,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 8, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(44,NULL,'creation','lea','humain','regions',16,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(45,NULL,'modification','lea','humain','regions',16,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 3 1", "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(46,NULL,'modification','lea','humain','regions',2,'{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 0 0", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "AVANT ANNULER", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(47,NULL,'annulation','lea','humain','evenement',46,'{"acte": "modification", "cible_id": 2, "cible_table": "regions"}',NULL,'2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(48,NULL,'suppression','lea','humain','regions',16,'{"h": 9, "id": 16, "ocr_texte": "TINTIN ET LE OTAGE 3 1", "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}',NULL,'2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(49,NULL,'lien','lea','humain','bulle_locuteur',2,'{"personnage_id": 1}','{"personnage_id": 3}','2026-10-15 15:07:51');
INSERT INTO "evenement" VALUES(50,NULL,'lien','lea','humain','bulle_locuteur',2,'{"personnage_id": 3}','{"personnage_id": 1}','2026-10-15 15:07:51');
CREATE TABLE meta (
    cle      TEXT PRIMARY KEY,
    valeur   TEXT
);
CREATE TABLE personnage_alignement (
    id             INTEGER PRIMARY KEY,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    source         TEXT,                          -- 'wikidata' | 'viaf' | 'idref' | … (auto)
    uri            TEXT NOT NULL,
    date_creation  TEXT DEFAULT (datetime('now')),
    UNIQUE(personnage_id, uri)
);
CREATE TABLE personnage_attribut (
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    valeur_id      INTEGER NOT NULL REFERENCES attribut_valeur(id) ON DELETE CASCADE,
    PRIMARY KEY (personnage_id, valeur_id)
);
CREATE TABLE personnage_presence (
    region_id      INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "personnage_presence" VALUES(1,2,'2026-10-15 15:07:50');
INSERT INTO "personnage_presence" VALUES(5,2,'2026-10-15 15:07:51');
INSERT INTO "personnage_presence" VALUES(9,2,'2026-10-15 15:07:51');
CREATE TABLE personnages (
    id             INTEGER PRIMARY KEY,
    nom            TEXT NOT NULL,
    serie          TEXT,
    notes          TEXT,
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "personnages" VALUES(1,'Tintin',NULL,NULL,'2026-10-15 15:07:45');
INSERT INTO "personnages" VALUES(2,'Haddock',NULL,NULL,'2026-10-15 15:07:45');
CREATE TABLE planches (
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
INSERT INTO "planches" VALUES(1,1,1,'recit','corpus/album_1/planche_0001.png','derivatives/album_1/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,'2026-10-15 15:07:50',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(2,1,2,'recit','corpus/album_1/planche_0002.png','derivatives/album_1/planche_0002.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(3,2,1,'recit','corpus/album_2/planche_0001.png','derivatives/album_2/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,'2026-10-15 15:07:51',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(4,2,2,'recit','corpus/album_2/planche_0002.png','derivatives/album_2/planche_0002.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(5,3,1,'recit','corpus/album_3/planche_0001.png','derivatives/album_3/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,'2026-10-15 15:07:51',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(6,3,2,'recit','corpus/album_3/planche_0002.png','derivatives/album_3/planche_0002.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
CREATE TABLE projet (
    id             INTEGER PRIMARY KEY,
    nom            TEXT NOT NULL,
    description    TEXT,
    justification  TEXT,
    repli          INTEGER NOT NULL DEFAULT 0,     -- 1 = le projet de repli
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "projet" VALUES(1,'Projet principal','Créé automatiquement : toute collection appartient à un projet. Renommez-le, et décrivez-le.',NULL,1,'2026-10-15 15:07:45');
CREATE TABLE projet_acces (
    projet_id      INTEGER NOT NULL REFERENCES projet(id) ON DELETE CASCADE,
    genre          TEXT NOT NULL,       -- 'utilisateur' | 'groupe'
    principal      TEXT NOT NULL,       -- login, ou nom de groupe Remote-Groups
    role           TEXT NOT NULL,       -- 'membre' | 'responsable'
    date_creation  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (projet_id, genre, principal)
);
CREATE VIRTUAL TABLE recherche USING fts5(
    region_id UNINDEXED,
    ocr_texte,
    note,
    tags_concat,
    lemmes,
    tokenize = 'unicode61 remove_diacritics 2'
);
INSERT INTO "recherche" VALUES(4,'TINTIN ET LE OTAGE 0 1','','','tintin otage');
INSERT INTO "recherche" VALUES(6,'TINTIN ET LE OTAGE 1 0','vu','dialogue','tintin otage');
INSERT INTO "recherche" VALUES(8,'TINTIN ET LE OTAGE 1 1','','','tintin otage');
INSERT INTO "recherche" VALUES(10,'TINTIN ET LE OTAGE 2 0','vu','dialogue','tintin otage');
INSERT INTO "recherche" VALUES(12,'TINTIN ET LE OTAGE 2 1','','','tintin otage');
INSERT INTO "recherche" VALUES(2,'TINTIN ET LE OTAGE 0 0','vu','dialogue','tintin otage');
CREATE TABLE region_attribut (
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    valeur_id      INTEGER NOT NULL REFERENCES attribut_valeur(id) ON DELETE CASCADE,
    PRIMARY KEY (region_id, valeur_id)
);
INSERT INTO "region_attribut" VALUES(1,1);
INSERT INTO "region_attribut" VALUES(5,1);
INSERT INTO "region_attribut" VALUES(9,1);
CREATE TABLE regions (
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
INSERT INTO "regions" VALUES(1,1,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-15 15:07:45',NULL,0,NULL);
INSERT INTO "regions" VALUES(2,1,1,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 0 0','manuel','2026-10-15 15:07:45',NULL,1,'2026-10-15 15:07:51');
INSERT INTO "regions" VALUES(3,2,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-15 15:07:50',NULL,0,NULL);
INSERT INTO "regions" VALUES(4,2,3,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 0 1','manuel','2026-10-15 15:07:50',NULL,1,'2026-10-15 15:07:51');
INSERT INTO "regions" VALUES(5,3,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-15 15:07:51',NULL,0,NULL);
INSERT INTO "regions" VALUES(6,3,5,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 1 0','manuel','2026-10-15 15:07:51',NULL,1,'2026-10-15 15:07:51');
INSERT INTO "regions" VALUES(7,4,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-15 15:07:51',NULL,0,NULL);
INSERT INTO "regions" VALUES(8,4,7,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 1 1','manuel','2026-10-15 15:07:51',NULL,1,'2026-10-15 15:07:51');
INSERT INTO "regions" VALUES(9,5,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-15 15:07:51',NULL,0,NULL);
INSERT INTO "regions" VALUES(10,5,9,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 2 0','manuel','2026-10-15 15:07:51',NULL,1,'2026-10-15 15:07:51');
INSERT INTO "regions" VALUES(11,6,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-15 15:07:51',NULL,0,NULL);
INSERT INTO "regions" VALUES(12,6,11,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 2 1','manuel','2026-10-15 15:07:51',NULL,1,'2026-10-15 15:07:51');
CREATE TABLE tags (
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
INSERT INTO "tags" VALUES(1,'dialogue','#1a4a8a',NULL,NULL,'provisoire',NULL,'2026-10-15 15:07:50');
CREATE TABLE token_correction (
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
CREATE TABLE tokens (
    id          INTEGER PRIMARY KEY,
    region_id   INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    ordre       INTEGER,
    texte       TEXT,
    lemme       TEXT,
    pos         TEXT,
    morph       TEXT
);
INSERT INTO "tokens" VALUES(7,4,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(8,4,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(9,4,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(10,4,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(11,4,4,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(12,4,5,'1','1','DET','');
INSERT INTO "tokens" VALUES(13,6,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(14,6,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(15,6,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(16,6,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(17,6,4,'1','1','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(18,6,5,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(19,8,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(20,8,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(21,8,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(22,8,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(23,8,4,'1','1','DET','');
INSERT INTO "tokens" VALUES(24,8,5,'1','1','DET','');
INSERT INTO "tokens" VALUES(25,10,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(26,10,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(27,10,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(28,10,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(29,10,4,'2','2','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(30,10,5,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(31,12,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(32,12,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(33,12,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(34,12,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(35,12,4,'2','2','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(36,12,5,'1','1','DET','');
INSERT INTO "tokens" VALUES(49,2,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(50,2,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(51,2,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(52,2,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(53,2,4,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(54,2,5,'0','0','NUM','NumType=Card');
CREATE TABLE utilisateur (
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
INSERT INTO "utilisateur" VALUES('hugo','Hugo',NULL,'2026-10-15 15:07:45','2026-10-15 15:07:45','nominatif');
INSERT INTO "utilisateur" VALUES('lea','Lea',NULL,'2026-10-15 15:07:45','2026-10-15 15:07:45','nominatif');
INSERT INTO "utilisateur" VALUES('sam','Sam',NULL,'2026-10-15 15:07:45','2026-10-15 15:07:45','nominatif');
CREATE INDEX idx_projet_acces_principal ON projet_acces(genre, principal);
CREATE INDEX idx_acces_principal ON collection_acces(genre, principal);
CREATE INDEX idx_planches_album   ON planches(album_id);
CREATE INDEX idx_regions_planche  ON regions(planche_id);
CREATE INDEX idx_regions_parent   ON regions(parent_id);
CREATE INDEX idx_anntags_tag      ON annotation_tags(tag_id);
CREATE INDEX idx_tokens_region    ON tokens(region_id);
CREATE INDEX idx_tokens_lemme     ON tokens(lemme);
CREATE INDEX idx_tokens_pos       ON tokens(pos);
CREATE INDEX idx_tcorr_region     ON token_correction(region_id);
CREATE INDEX idx_tcorr_etat       ON token_correction(etat);
CREATE INDEX idx_locuteur_perso   ON bulle_locuteur(personnage_id);
CREATE INDEX idx_presence_perso   ON personnage_presence(personnage_id);
CREATE INDEX idx_attrval_dim      ON attribut_valeur(dimension_id);
CREATE INDEX idx_persoattr_val    ON personnage_attribut(valeur_id);
CREATE INDEX idx_regattr_val      ON region_attribut(valeur_id);
CREATE INDEX idx_colalbum_album   ON collection_album(album_id);
CREATE INDEX idx_contribution_album ON contribution(album_id);
CREATE INDEX idx_contribution_role  ON contribution(role_id);
CREATE INDEX idx_evenement_cible    ON evenement(cible_table, cible_id);
CREATE INDEX idx_evenement_activite ON evenement(activite_id);
CREATE INDEX idx_evenement_date     ON evenement(date);
CREATE INDEX idx_alignement_perso   ON personnage_alignement(personnage_id);
CREATE INDEX idx_domaine_collection ON domaine(collection_id);
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
CREATE UNIQUE INDEX idx_planches_album_numero ON planches(album_id, numero);
CREATE INDEX idx_regions_activite ON regions(activite_id);
CREATE INDEX idx_dim_collection ON attribut_dimension(collection_id);
CREATE INDEX idx_val_collection ON attribut_valeur(collection_id);
CREATE INDEX idx_tags_collection ON tags(collection_id);
CREATE INDEX idx_dim_domaine ON attribut_dimension(domaine_id);
CREATE INDEX idx_collection_projet ON collection(projet_id);
COMMIT;
PRAGMA user_version = 29;
