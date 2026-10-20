-- Base v31 faite par le code de 16c6127 (ses routes, sous trois comptes), vidée par
-- `sqlite3.Connection.iterdump` (la table plein texte recréée par son CREATE).
-- Refaite par : python tools/fabriquer_base_de_version.py 16c6127 tests/bases/v31-16c6127.sql
-- Ce qu'elle contient :
--   albums_vivants : [1, 2, 3, 5, 6, 7, 8, 10, 11, 12]
--   album_detruit : 4
--   planche_detruite : 8
--   region_detruite : 16
--   personnage_detruit : 3
--   projet_repli : 1
--   projet_etude : 2
--   collection_b : 6
--   album_sans_collection : 5
--   album_garde_au_fonds : 6
--   album_rendu : 7
--   album_detruit_sur_demande : 9
--   demandes : {"en_attente": 1, "refusee": 2, "acceptee": 3, "projet_en_attente": 4, "projet_acceptee": 5}
--   projets_supprimes : [3, 4]
--   base_etude : 5
--   collection_c : 7
--   album_source_des_soeurs : 10
--   album_soeur : 11
--   collection_de_lea : 8
--   demandes_v31 : {"rejoindre_acceptee": 6, "rejoindre_refusee": 7, "retour": 8}
--   max : {"albums": 12, "planches": 12, "regions": 18, "personnages": 2, "projet": 2, "collection": 8, "document": 11, "demande": 8}
--   comptes : {"albums": 10, "planches": 9, "regions": 14, "personnages": 2, "evenement": 133, "activite": 1, "tokens": 0, "annotations": 4, "recherche": 7, "projet": 2, "projet_acces": 6, "collection": 8, "document": 9, "demande": 8, "demande_document": 6, "copie": 10}
--   activites : [["ocr", "{\"planche_id\": 8}"]]
--   demandes_par_genre : {"rejoindre": 2, "rendre_copie": 1, "suppression_document": 3, "suppression_projet": 2}
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
INSERT INTO "activite" VALUES(1,'ocr','easyocr','moteur',NULL,NULL,'{"planche_id": 8}','{"crees": 0, "modifies": 0, "remplaces": 0}','2026-10-20 11:58:38','2026-10-20 11:58:38');
CREATE TABLE albums (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
INSERT INTO "albums" VALUES(1,'Album 1',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:38',1,1);
INSERT INTO "albums" VALUES(2,'Album 2',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:38',2,1);
INSERT INTO "albums" VALUES(3,'Album 3',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:38',3,1);
INSERT INTO "albums" VALUES(5,'Album sans collection',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',5,1);
INSERT INTO "albums" VALUES(6,'Gardée au fonds',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',6,2);
INSERT INTO "albums" VALUES(7,'Importé au fonds',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',7,1);
INSERT INTO "albums" VALUES(8,'Demande refusée',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',8,1);
INSERT INTO "albums" VALUES(10,'Source des sœurs',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',10,2);
INSERT INTO "albums" VALUES(11,'Source des sœurs',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',10,2);
INSERT INTO "albums" VALUES(12,'Rejoindre refusé',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',11,1);
CREATE TABLE annotation_tags (
    annotation_id  INTEGER REFERENCES annotations(id) ON DELETE CASCADE,
    tag_id         INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_id, tag_id)
);
INSERT INTO "annotation_tags" VALUES(1,1);
INSERT INTO "annotation_tags" VALUES(2,1);
INSERT INTO "annotation_tags" VALUES(3,1);
INSERT INTO "annotation_tags" VALUES(4,1);
CREATE TABLE annotations (
    id                 INTEGER PRIMARY KEY,
    region_id          INTEGER UNIQUE REFERENCES regions(id) ON DELETE CASCADE,
    note               TEXT,
    date_creation      TEXT DEFAULT (datetime('now')),
    date_modification  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "annotations" VALUES(1,2,'vu','2026-10-20 11:58:38','2026-10-20 11:58:38');
INSERT INTO "annotations" VALUES(2,6,'vu','2026-10-20 11:58:38','2026-10-20 11:58:38');
INSERT INTO "annotations" VALUES(3,10,'vu','2026-10-20 11:58:38','2026-10-20 11:58:38');
INSERT INTO "annotations" VALUES(4,18,'source','2026-10-20 11:58:39','2026-10-20 11:58:39');
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
INSERT INTO "attribut_dimension" VALUES(1,'case','cadrage',NULL,NULL,NULL,'provisoire',NULL,'2026-10-20 11:58:38');
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
INSERT INTO "attribut_valeur" VALUES(1,1,'gros plan',NULL,NULL,'provisoire',NULL,'2026-10-20 11:58:38');
CREATE TABLE bulle_locuteur (
    region_id      INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "bulle_locuteur" VALUES(2,1,'2026-10-20 11:58:38');
INSERT INTO "bulle_locuteur" VALUES(6,1,'2026-10-20 11:58:38');
INSERT INTO "bulle_locuteur" VALUES(10,1,'2026-10-20 11:58:38');
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
INSERT INTO "collection" VALUES(1,'Projet principal','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:37',1,1,NULL);
INSERT INTO "collection" VALUES(2,'Corpus principal',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:37',1,0,NULL);
INSERT INTO "collection" VALUES(3,'Incubateur',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:37',1,0,NULL);
INSERT INTO "collection" VALUES(4,'Collection par défaut','Créée automatiquement : tout album doit appartenir à une collection, qui est l''unité de cloisonnement des accès. Renommez-la et décrivez-la, ou déplacez ses albums vers des collections d''étude.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',1,0,NULL);
INSERT INTO "collection" VALUES(5,'Étude B','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',2,1,'ecriture');
INSERT INTO "collection" VALUES(6,'Collection B',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',2,0,NULL);
INSERT INTO "collection" VALUES(7,'Collection C',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',2,0,NULL);
INSERT INTO "collection" VALUES(8,'Collection de Léa',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-20 11:58:39',1,0,NULL);
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
INSERT INTO "collection_acces" VALUES(2,'utilisateur','lea','ecriture',0,'2026-10-20 11:58:37');
INSERT INTO "collection_acces" VALUES(3,'utilisateur','lea','ecriture',0,'2026-10-20 11:58:38');
INSERT INTO "collection_acces" VALUES(2,'utilisateur','sam','ecriture',0,'2026-10-20 11:58:38');
INSERT INTO "collection_acces" VALUES(6,'utilisateur','lea','proprietaire',0,'2026-10-20 11:58:39');
INSERT INTO "collection_acces" VALUES(7,'utilisateur','lea','proprietaire',0,'2026-10-20 11:58:39');
INSERT INTO "collection_acces" VALUES(8,'utilisateur','lea','proprietaire',0,'2026-10-20 11:58:39');
CREATE TABLE collection_album (
    collection_id  INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    album_id       INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    rang           INTEGER,
    PRIMARY KEY (collection_id, album_id)
);
INSERT INTO "collection_album" VALUES(2,1,NULL);
INSERT INTO "collection_album" VALUES(2,2,NULL);
INSERT INTO "collection_album" VALUES(3,3,NULL);
INSERT INTO "collection_album" VALUES(4,5,NULL);
INSERT INTO "collection_album" VALUES(2,7,NULL);
INSERT INTO "collection_album" VALUES(2,8,NULL);
INSERT INTO "collection_album" VALUES(6,10,NULL);
INSERT INTO "collection_album" VALUES(7,11,NULL);
INSERT INTO "collection_album" VALUES(8,2,NULL);
INSERT INTO "collection_album" VALUES(2,12,NULL);
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
INSERT INTO "contribution_role" VALUES(1,'scénariste','creator','aut','2026-10-20 11:58:37');
INSERT INTO "contribution_role" VALUES(2,'dessinateur','creator','art','2026-10-20 11:58:37');
INSERT INTO "contribution_role" VALUES(3,'coloriste','contributor','clr','2026-10-20 11:58:37');
INSERT INTO "contribution_role" VALUES(4,'encreur','contributor',NULL,'2026-10-20 11:58:37');
INSERT INTO "contribution_role" VALUES(5,'lettreur','contributor',NULL,'2026-10-20 11:58:37');
INSERT INTO "contribution_role" VALUES(6,'traducteur','contributor','trl','2026-10-20 11:58:37');
INSERT INTO "contribution_role" VALUES(7,'préfacier','contributor','aui','2026-10-20 11:58:37');
CREATE TABLE copie (
    album_id           INTEGER PRIMARY KEY REFERENCES albums(id) ON DELETE CASCADE,
    creee_par          TEXT,
    creee_le           TEXT DEFAULT (datetime('now')),
    depuis_album_id    INTEGER,
    cran               TEXT NOT NULL DEFAULT 'origine',
    depuis_projet_nom  TEXT
);
INSERT INTO "copie" VALUES(1,'lea','2026-10-20 11:58:38',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(2,'sam','2026-10-20 11:58:38',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(3,'lea','2026-10-20 11:58:38',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(5,'hugo','2026-10-20 11:58:39',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(6,'lea','2026-10-20 11:58:39',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(7,'hugo','2026-10-20 11:58:39',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(8,'lea','2026-10-20 11:58:39',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(10,'lea','2026-10-20 11:58:39',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(11,'lea','2026-10-20 11:58:39',10,'images','Étude B');
INSERT INTO "copie" VALUES(12,'sam','2026-10-20 11:58:39',NULL,'origine',NULL);
CREATE TABLE demande (
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
    collection_nom TEXT
);
INSERT INTO "demande" VALUES(1,'suppression_document','sam','Importé par erreur.','2026-10-20 11:58:39',1,'Projet principal','2026-10-20 11:58:39',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "demande" VALUES(2,'suppression_document','sam','Importé par erreur.','2026-10-20 11:58:39',1,'Projet principal','2026-10-20 11:58:39','refusee','hugo','2026-10-20 11:58:39',NULL,NULL);
INSERT INTO "demande" VALUES(3,'suppression_document','sam','Importé par erreur.','2026-10-20 11:58:39',1,'Projet principal','2026-10-20 11:58:39','acceptee','hugo','2026-10-20 11:58:39',NULL,NULL);
INSERT INTO "demande" VALUES(4,'suppression_projet','lea','Étude terminée.',NULL,2,'Étude B','2026-10-20 11:58:39',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "demande" VALUES(5,'suppression_projet','sam','Créé par erreur.',NULL,4,'Éphémère 2','2026-10-20 11:58:39','acceptee','hugo','2026-10-20 11:58:39',NULL,NULL);
INSERT INTO "demande" VALUES(6,'rejoindre','lea',NULL,NULL,1,'Projet principal','2026-10-20 11:58:39','acceptee','hugo','2026-10-20 11:58:39',8,'Collection de Léa');
INSERT INTO "demande" VALUES(7,'rejoindre','lea',NULL,NULL,1,'Projet principal','2026-10-20 11:58:39','refusee','hugo','2026-10-20 11:58:39',8,'Collection de Léa');
INSERT INTO "demande" VALUES(8,'rendre_copie','lea','On y retravaille.',NULL,2,'Étude B','2026-10-20 11:58:39',NULL,NULL,NULL,5,'Étude B');
CREATE TABLE demande_document (
    demande_id   INTEGER NOT NULL REFERENCES demande(id) ON DELETE CASCADE,
    document_id  INTEGER NOT NULL,
    album_id     INTEGER,
    titre        TEXT,
    reponse      TEXT,
    copie_id     INTEGER,
    PRIMARY KEY (demande_id, document_id)
);
INSERT INTO "demande_document" VALUES(1,1,1,'Album 1',NULL,NULL);
INSERT INTO "demande_document" VALUES(2,8,8,'Demande refusée','refusee',NULL);
INSERT INTO "demande_document" VALUES(3,9,9,'Demande acceptée','acceptee',NULL);
INSERT INTO "demande_document" VALUES(6,2,2,'Album 2','acceptee',2);
INSERT INTO "demande_document" VALUES(7,11,12,'Rejoindre refusé','refusee',NULL);
INSERT INTO "demande_document" VALUES(8,6,6,'Gardée au fonds',NULL,NULL);
CREATE TABLE document (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    importe_par        TEXT,
    importe_le         TEXT DEFAULT (datetime('now')),
    projet_origine_id  INTEGER,
    projet_origine_nom TEXT
);
INSERT INTO "document" VALUES(1,'lea','2026-10-20 11:58:38',1,'Projet principal');
INSERT INTO "document" VALUES(2,'sam','2026-10-20 11:58:38',1,'Projet principal');
INSERT INTO "document" VALUES(3,'lea','2026-10-20 11:58:38',1,'Projet principal');
INSERT INTO "document" VALUES(5,'hugo','2026-10-20 11:58:39',1,'Projet principal');
INSERT INTO "document" VALUES(6,'lea','2026-10-20 11:58:39',2,'Étude B');
INSERT INTO "document" VALUES(7,'hugo','2026-10-20 11:58:39',NULL,NULL);
INSERT INTO "document" VALUES(8,'lea','2026-10-20 11:58:39',1,'Projet principal');
INSERT INTO "document" VALUES(10,'lea','2026-10-20 11:58:39',2,'Étude B');
INSERT INTO "document" VALUES(11,'sam','2026-10-20 11:58:39',1,'Projet principal');
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
INSERT INTO "evenement" VALUES(1,NULL,'creation','hugo','humain','collection',2,NULL,'{"nom": "Corpus principal", "proprietaire": "hugo"}','2026-10-20 11:58:37');
INSERT INTO "evenement" VALUES(2,NULL,'creation','hugo','humain','collection',3,NULL,'{"nom": "Incubateur", "proprietaire": "hugo"}','2026-10-20 11:58:37');
INSERT INTO "evenement" VALUES(3,NULL,'lien','hugo','humain','collection_acces',2,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "lea"}','2026-10-20 11:58:37');
INSERT INTO "evenement" VALUES(4,NULL,'lien','hugo','humain','collection_acces',3,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "lea"}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(5,NULL,'lien','hugo','humain','collection_acces',2,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "sam"}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(6,NULL,'creation','lea','humain','document',1,NULL,'{"album_id": 1, "titre": "Album 1"}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(7,NULL,'lien','lea','humain','collection_album',1,NULL,'{"album_id": 1, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(8,NULL,'modification','lea','humain','document',1,NULL,'{"album_id": 1, "planche": {"id": 1, "numero": 1}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(9,NULL,'creation','lea','humain','regions',1,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 1, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(10,NULL,'creation','lea','humain','regions',2,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(11,NULL,'modification','lea','humain','regions',2,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 0 0", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(12,NULL,'creation','lea','humain','annotations',2,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(13,NULL,'lien','lea','humain','bulle_locuteur',2,NULL,'{"personnage_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(14,NULL,'lien','lea','humain','personnage_presence',1,NULL,'{"personnage_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(15,NULL,'lien','lea','humain','region_attribut',1,NULL,'{"valeur_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(16,NULL,'validation','lea','humain','planches',1,NULL,'{"validee": true}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(17,NULL,'modification','lea','humain','document',1,NULL,'{"album_id": 1, "planche": {"id": 2, "numero": 2}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(18,NULL,'creation','lea','humain','regions',3,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 2, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(19,NULL,'creation','lea','humain','regions',4,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 3, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(20,NULL,'modification','lea','humain','regions',4,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 3, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 0 1", "ordre": 1, "parent_id": 3, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(21,NULL,'creation','sam','humain','document',2,NULL,'{"album_id": 2, "titre": "Album 2"}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(22,NULL,'lien','sam','humain','collection_album',2,NULL,'{"album_id": 2, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(23,NULL,'modification','sam','humain','document',2,NULL,'{"album_id": 2, "planche": {"id": 3, "numero": 1}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(24,NULL,'creation','sam','humain','regions',5,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 3, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(25,NULL,'creation','sam','humain','regions',6,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 5, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(26,NULL,'modification','sam','humain','regions',6,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 5, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 1 0", "ordre": 1, "parent_id": 5, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(27,NULL,'creation','sam','humain','annotations',6,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(28,NULL,'lien','sam','humain','bulle_locuteur',6,NULL,'{"personnage_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(29,NULL,'lien','sam','humain','personnage_presence',5,NULL,'{"personnage_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(30,NULL,'lien','sam','humain','region_attribut',5,NULL,'{"valeur_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(31,NULL,'validation','sam','humain','planches',3,NULL,'{"validee": true}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(32,NULL,'modification','sam','humain','document',2,NULL,'{"album_id": 2, "planche": {"id": 4, "numero": 2}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(33,NULL,'creation','sam','humain','regions',7,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 4, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(34,NULL,'creation','sam','humain','regions',8,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 7, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(35,NULL,'modification','sam','humain','regions',8,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 7, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 1 1", "ordre": 1, "parent_id": 7, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(36,NULL,'creation','lea','humain','document',3,NULL,'{"album_id": 3, "titre": "Album 3"}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(37,NULL,'lien','lea','humain','collection_album',3,NULL,'{"album_id": 3, "collection": "Incubateur", "collection_id": 3}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(38,NULL,'modification','lea','humain','document',3,NULL,'{"album_id": 3, "planche": {"id": 5, "numero": 1}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(39,NULL,'creation','lea','humain','regions',9,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 5, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(40,NULL,'creation','lea','humain','regions',10,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 9, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(41,NULL,'modification','lea','humain','regions',10,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 9, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 2 0", "ordre": 1, "parent_id": 9, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(42,NULL,'creation','lea','humain','annotations',10,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(43,NULL,'lien','lea','humain','bulle_locuteur',10,NULL,'{"personnage_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(44,NULL,'lien','lea','humain','personnage_presence',9,NULL,'{"personnage_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(45,NULL,'lien','lea','humain','region_attribut',9,NULL,'{"valeur_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(46,NULL,'validation','lea','humain','planches',5,NULL,'{"validee": true}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(47,NULL,'modification','lea','humain','document',3,NULL,'{"album_id": 3, "planche": {"id": 6, "numero": 2}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(48,NULL,'creation','lea','humain','regions',11,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 6, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(49,NULL,'creation','lea','humain','regions',12,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 11, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(50,NULL,'modification','lea','humain','regions',12,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 11, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 2 1", "ordre": 1, "parent_id": 11, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(51,NULL,'creation','lea','humain','document',4,NULL,'{"album_id": 4, "titre": "Album 4"}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(52,NULL,'lien','lea','humain','collection_album',4,NULL,'{"album_id": 4, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(53,NULL,'modification','lea','humain','document',4,NULL,'{"album_id": 4, "planche": {"id": 7, "numero": 1}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(54,NULL,'creation','lea','humain','regions',13,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 7, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(55,NULL,'creation','lea','humain','regions',14,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 13, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(56,NULL,'modification','lea','humain','regions',14,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 13, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 3 0", "ordre": 1, "parent_id": 13, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(57,NULL,'creation','lea','humain','annotations',14,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(58,NULL,'lien','lea','humain','bulle_locuteur',14,NULL,'{"personnage_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(59,NULL,'lien','lea','humain','personnage_presence',13,NULL,'{"personnage_id": 2}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(60,NULL,'lien','lea','humain','region_attribut',13,NULL,'{"valeur_id": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(61,NULL,'validation','lea','humain','planches',7,NULL,'{"validee": true}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(62,NULL,'modification','lea','humain','document',4,NULL,'{"album_id": 4, "planche": {"id": 8, "numero": 2}}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(63,NULL,'creation','lea','humain','regions',15,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 8, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(64,NULL,'creation','lea','humain','regions',16,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(65,NULL,'modification','lea','humain','regions',16,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 3 1", "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(66,NULL,'modification','lea','humain','regions',2,'{"h": 9, "ocr_texte": "TINTIN ET LE OTAGE 0 0", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "AVANT ANNULER", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(67,NULL,'annulation','lea','humain','evenement',66,'{"acte": "modification", "cible_id": 2, "cible_table": "regions"}',NULL,'2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(68,NULL,'suppression','lea','humain','regions',16,'{"h": 9, "id": 16, "ocr_texte": "TINTIN ET LE OTAGE 3 1", "ordre": 1, "parent_id": 15, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}',NULL,'2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(69,NULL,'modification','hugo','humain','document',4,'{"album_id": 4, "planche": {"id": 8, "numero": 2}}',NULL,'2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(70,NULL,'delien','hugo','humain','collection_album',4,'{"album_id": 4, "collection": "Corpus principal", "collection_id": 2}',NULL,'2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(71,NULL,'suppression','hugo','humain','document',4,'{"album_id": 4, "planches": 1, "titre": "Album 4"}',NULL,'2026-10-20 11:58:38');
INSERT INTO "evenement" VALUES(72,NULL,'lien','lea','humain','bulle_locuteur',2,'{"personnage_id": 1}','{"personnage_id": 3}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(73,NULL,'lien','lea','humain','bulle_locuteur',2,'{"personnage_id": 3}','{"personnage_id": 1}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(74,NULL,'creation','hugo','humain','document',5,NULL,'{"album_id": 5, "titre": "Album sans collection"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(75,NULL,'lien','hugo','humain','collection_album',5,NULL,'{"album_id": 5, "collection": "Collection par défaut", "collection_id": 4}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(76,NULL,'lien','hugo','humain','projet_acces',1,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "membre"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(77,NULL,'lien','hugo','humain','projet_acces',1,NULL,'{"genre": "utilisateur", "principal": "rita", "role": "responsable"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(78,NULL,'lien','hugo','humain','projet_acces',1,NULL,'{"genre": "groupe", "principal": "chefs", "role": "responsable"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(79,NULL,'creation','hugo','humain','projet',2,NULL,'{"nom": "Étude B"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(80,NULL,'creation','hugo','humain','collection',5,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Étude B", "projet_id": 2, "proprietaire": null}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(81,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "utilisateur", "principal": "lea", "role": "responsable"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(82,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "membre"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(83,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "groupe", "principal": "etudiants", "role": "membre"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(84,NULL,'creation','lea','humain','collection',6,NULL,'{"nom": "Collection B", "proprietaire": "lea"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(85,NULL,'creation','lea','humain','document',6,NULL,'{"album_id": 6, "titre": "Gardée au fonds"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(86,NULL,'lien','lea','humain','collection_album',6,NULL,'{"album_id": 6, "collection": "Collection B", "collection_id": 6}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(87,NULL,'modification','lea','humain','document',6,NULL,'{"album_id": 6, "planche": {"id": 9, "numero": 1}}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(88,NULL,'delien','lea','humain','collection_album',6,'{"album_id": 6, "collection": "Collection B", "collection_id": 6}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(89,NULL,'creation','hugo','humain','document',7,NULL,'{"album_id": 7, "titre": "Importé au fonds"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(90,NULL,'lien','hugo','humain','collection_album',7,NULL,'{"album_id": 7, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(91,NULL,'creation','sam','humain','demande',1,NULL,'{"album_id": 1, "document_id": 1, "genre": "suppression_document"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(92,NULL,'creation','lea','humain','document',8,NULL,'{"album_id": 8, "titre": "Demande refusée"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(93,NULL,'lien','lea','humain','collection_album',8,NULL,'{"album_id": 8, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(94,NULL,'creation','sam','humain','demande',2,NULL,'{"album_id": 8, "document_id": 8, "genre": "suppression_document"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(95,NULL,'modification','hugo','humain','demande',2,'{"reponse": null}','{"reponse": "refusee"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(96,NULL,'creation','lea','humain','document',9,NULL,'{"album_id": 9, "titre": "Demande acceptée"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(97,NULL,'lien','lea','humain','collection_album',9,NULL,'{"album_id": 9, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(98,NULL,'modification','lea','humain','document',9,NULL,'{"album_id": 9, "planche": {"id": 10, "numero": 1}}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(99,NULL,'creation','sam','humain','demande',3,NULL,'{"album_id": 9, "document_id": 9, "genre": "suppression_document"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(100,NULL,'delien','hugo','humain','collection_album',9,'{"album_id": 9, "collection": "Corpus principal", "collection_id": 2}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(101,NULL,'suppression','hugo','humain','document',9,'{"album_id": 9, "planches": 1, "titre": "Demande acceptée"}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(102,NULL,'modification','hugo','humain','demande',3,'{"reponse": null}','{"reponse": "acceptee"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(103,NULL,'creation','lea','humain','demande',4,NULL,'{"genre": "suppression_projet", "projet_id": 2}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(104,NULL,'creation','hugo','humain','projet',3,NULL,'{"nom": "Éphémère"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(105,NULL,'creation','hugo','humain','collection',7,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Éphémère", "projet_id": 3, "proprietaire": null}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(106,NULL,'suppression','hugo','humain','collection',7,'{"base": true, "nom": "Éphémère"}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(107,NULL,'suppression','hugo','humain','projet',3,'{"nom": "Éphémère"}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(108,NULL,'creation','hugo','humain','projet',4,NULL,'{"nom": "Éphémère 2"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(109,NULL,'creation','hugo','humain','collection',7,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Éphémère 2", "projet_id": 4, "proprietaire": null}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(110,NULL,'lien','hugo','humain','projet_acces',4,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "responsable"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(111,NULL,'creation','sam','humain','demande',5,NULL,'{"genre": "suppression_projet", "projet_id": 4}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(112,NULL,'modification','hugo','humain','demande',5,'{"reponse": null}','{"reponse": "acceptee"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(113,NULL,'suppression','hugo','humain','collection',7,'{"base": true, "nom": "Éphémère 2"}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(114,NULL,'suppression','hugo','humain','projet',4,'{"nom": "Éphémère 2"}',NULL,'2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(115,NULL,'creation','lea','humain','collection',7,NULL,'{"nom": "Collection C", "proprietaire": "lea"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(116,NULL,'creation','lea','humain','document',10,NULL,'{"album_id": 10, "titre": "Source des sœurs"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(117,NULL,'lien','lea','humain','collection_album',10,NULL,'{"album_id": 10, "collection": "Collection B", "collection_id": 6}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(118,NULL,'modification','lea','humain','document',10,NULL,'{"album_id": 10, "planche": {"id": 11, "numero": 1}}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(119,NULL,'creation','lea','humain','regions',17,NULL,'{"h": 20, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 11, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(120,NULL,'creation','lea','humain','regions',18,NULL,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 17, "planche_id": 11, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(121,NULL,'modification','lea','humain','regions',18,'{"h": 9, "ocr_texte": null, "ordre": 1, "parent_id": 17, "planche_id": 11, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "ocr_texte": "LE OTAGE SOEUR", "ordre": 1, "parent_id": 17, "planche_id": 11, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(122,NULL,'creation','lea','humain','annotations',18,NULL,'{"note": "source", "tags": ["dialogue"]}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(123,NULL,'modification','lea','humain','document',10,NULL,'{"album_id": 11, "copie": {"collection_id": 7, "cran": "images", "depuis_album_id": 10}}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(124,NULL,'lien','lea','humain','collection_album',10,NULL,'{"album_id": 11, "collection": "Collection C", "collection_id": 7}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(125,NULL,'creation','lea','humain','collection',8,NULL,'{"nom": "Collection de Léa", "proprietaire": "lea"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(126,NULL,'creation','lea','humain','demande',6,NULL,'{"collection_id": 8, "documents": [2], "genre": "rejoindre"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(127,NULL,'lien','hugo','humain','collection_album',2,NULL,'{"album_id": 2, "collection": "Collection de Léa", "collection_id": 8}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(128,NULL,'modification','hugo','humain','demande',6,'{"reponse": null}','{"reponse": "acceptee"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(129,NULL,'creation','sam','humain','document',11,NULL,'{"album_id": 12, "titre": "Rejoindre refusé"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(130,NULL,'lien','sam','humain','collection_album',11,NULL,'{"album_id": 12, "collection": "Corpus principal", "collection_id": 2}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(131,NULL,'creation','lea','humain','demande',7,NULL,'{"collection_id": 8, "documents": [11], "genre": "rejoindre"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(132,NULL,'modification','hugo','humain','demande',7,'{"reponse": null}','{"reponse": "refusee"}','2026-10-20 11:58:39');
INSERT INTO "evenement" VALUES(133,NULL,'creation','lea','humain','demande',8,NULL,'{"collection_id": 5, "documents": [6], "genre": "rendre_copie"}','2026-10-20 11:58:39');
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
INSERT INTO "personnage_presence" VALUES(1,2,'2026-10-20 11:58:38');
INSERT INTO "personnage_presence" VALUES(5,2,'2026-10-20 11:58:38');
INSERT INTO "personnage_presence" VALUES(9,2,'2026-10-20 11:58:38');
CREATE TABLE personnages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    serie          TEXT,
    notes          TEXT,
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "personnages" VALUES(1,'Tintin',NULL,NULL,'2026-10-20 11:58:38');
INSERT INTO "personnages" VALUES(2,'Haddock',NULL,NULL,'2026-10-20 11:58:38');
CREATE TABLE planches (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
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
INSERT INTO "planches" VALUES(1,1,1,'recit','corpus/album_1/planche_0001.png','derivatives/album_1/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,'2026-10-20 11:58:38',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(2,1,2,'recit','corpus/album_1/planche_0002.png','derivatives/album_1/planche_0002.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(3,2,1,'recit','corpus/album_2/planche_0001.png','derivatives/album_2/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,'2026-10-20 11:58:38',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(4,2,2,'recit','corpus/album_2/planche_0002.png','derivatives/album_2/planche_0002.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(5,3,1,'recit','corpus/album_3/planche_0001.png','derivatives/album_3/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,'2026-10-20 11:58:38',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(6,3,2,'recit','corpus/album_3/planche_0002.png','derivatives/album_3/planche_0002.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(9,6,1,'recit','corpus/album_6/planche_0001.png','derivatives/album_6/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(11,10,1,'recit','corpus/album_10/planche_0001.png','derivatives/album_10/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(12,11,1,'recit','corpus/album_10/planche_0001.png','derivatives/album_10/planche_0001.jpg',40,50,NULL,NULL,'RGB','importee',NULL,NULL,NULL,NULL,NULL);
CREATE TABLE projet (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    description    TEXT,
    justification  TEXT,
    repli          INTEGER NOT NULL DEFAULT 0,     -- 1 = le projet de repli
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "projet" VALUES(1,'Projet principal','Créé automatiquement : toute collection appartient à un projet. Renommez-le, et décrivez-le.',NULL,1,'2026-10-20 11:58:37');
INSERT INTO "projet" VALUES(2,'Étude B',NULL,NULL,0,'2026-10-20 11:58:39');
CREATE TABLE projet_acces (
    projet_id      INTEGER NOT NULL REFERENCES projet(id) ON DELETE CASCADE,
    genre          TEXT NOT NULL,       -- 'utilisateur' | 'groupe'
    principal      TEXT NOT NULL,       -- login, ou nom de groupe Remote-Groups
    role           TEXT NOT NULL,       -- 'membre' | 'responsable'
    date_creation  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (projet_id, genre, principal)
);
INSERT INTO "projet_acces" VALUES(1,'utilisateur','sam','membre','2026-10-20 11:58:39');
INSERT INTO "projet_acces" VALUES(1,'utilisateur','rita','responsable','2026-10-20 11:58:39');
INSERT INTO "projet_acces" VALUES(1,'groupe','chefs','responsable','2026-10-20 11:58:39');
INSERT INTO "projet_acces" VALUES(2,'utilisateur','lea','responsable','2026-10-20 11:58:39');
INSERT INTO "projet_acces" VALUES(2,'utilisateur','sam','membre','2026-10-20 11:58:39');
INSERT INTO "projet_acces" VALUES(2,'groupe','etudiants','membre','2026-10-20 11:58:39');
CREATE VIRTUAL TABLE recherche USING fts5(
    region_id UNINDEXED,
    ocr_texte,
    note,
    tags_concat,
    lemmes,
    tokenize = 'unicode61 remove_diacritics 2'
);
INSERT INTO "recherche" VALUES(4,'TINTIN ET LE OTAGE 0 1','','','');
INSERT INTO "recherche" VALUES(6,'TINTIN ET LE OTAGE 1 0','vu','dialogue','');
INSERT INTO "recherche" VALUES(8,'TINTIN ET LE OTAGE 1 1','','','');
INSERT INTO "recherche" VALUES(10,'TINTIN ET LE OTAGE 2 0','vu','dialogue','');
INSERT INTO "recherche" VALUES(12,'TINTIN ET LE OTAGE 2 1','','','');
INSERT INTO "recherche" VALUES(2,'TINTIN ET LE OTAGE 0 0','vu','dialogue','');
INSERT INTO "recherche" VALUES(18,'LE OTAGE SOEUR','source','dialogue','');
CREATE TABLE region_attribut (
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    valeur_id      INTEGER NOT NULL REFERENCES attribut_valeur(id) ON DELETE CASCADE,
    PRIMARY KEY (region_id, valeur_id)
);
INSERT INTO "region_attribut" VALUES(1,1);
INSERT INTO "region_attribut" VALUES(5,1);
INSERT INTO "region_attribut" VALUES(9,1);
CREATE TABLE regions (
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
INSERT INTO "regions" VALUES(1,1,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:38',NULL,0,NULL);
INSERT INTO "regions" VALUES(2,1,1,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 0 0','manuel','2026-10-20 11:58:38',NULL,1,'2026-10-20 11:58:38');
INSERT INTO "regions" VALUES(3,2,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:38',NULL,0,NULL);
INSERT INTO "regions" VALUES(4,2,3,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 0 1','manuel','2026-10-20 11:58:38',NULL,1,'2026-10-20 11:58:38');
INSERT INTO "regions" VALUES(5,3,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:38',NULL,0,NULL);
INSERT INTO "regions" VALUES(6,3,5,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 1 0','manuel','2026-10-20 11:58:38',NULL,1,'2026-10-20 11:58:38');
INSERT INTO "regions" VALUES(7,4,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:38',NULL,0,NULL);
INSERT INTO "regions" VALUES(8,4,7,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 1 1','manuel','2026-10-20 11:58:38',NULL,1,'2026-10-20 11:58:38');
INSERT INTO "regions" VALUES(9,5,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:38',NULL,0,NULL);
INSERT INTO "regions" VALUES(10,5,9,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 2 0','manuel','2026-10-20 11:58:38',NULL,1,'2026-10-20 11:58:38');
INSERT INTO "regions" VALUES(11,6,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:38',NULL,0,NULL);
INSERT INTO "regions" VALUES(12,6,11,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 2 1','manuel','2026-10-20 11:58:38',NULL,1,'2026-10-20 11:58:38');
INSERT INTO "regions" VALUES(17,11,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-20 11:58:39',NULL,0,NULL);
INSERT INTO "regions" VALUES(18,11,17,'bulle',1,1,9,9,1,'LE OTAGE SOEUR','manuel','2026-10-20 11:58:39',NULL,1,'2026-10-20 11:58:39');
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
INSERT INTO "tags" VALUES(1,'dialogue','#1a4a8a',NULL,NULL,'provisoire',NULL,'2026-10-20 11:58:38');
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
INSERT INTO "utilisateur" VALUES('hugo','Hugo',NULL,'2026-10-20 11:58:37','2026-10-20 11:58:37','nominatif');
INSERT INTO "utilisateur" VALUES('lea','Lea',NULL,'2026-10-20 11:58:37','2026-10-20 11:58:37','nominatif');
INSERT INTO "utilisateur" VALUES('sam','Sam',NULL,'2026-10-20 11:58:37','2026-10-20 11:58:37','nominatif');
CREATE INDEX idx_projet_acces_principal ON projet_acces(genre, principal);
CREATE INDEX idx_demande_document_document ON demande_document(document_id);
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
CREATE INDEX idx_albums_document ON albums(document_id);
CREATE INDEX idx_albums_projet ON albums(projet_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('projet',4);
INSERT INTO "sqlite_sequence" VALUES('personnages',3);
INSERT INTO "sqlite_sequence" VALUES('albums',12);
INSERT INTO "sqlite_sequence" VALUES('document',11);
INSERT INTO "sqlite_sequence" VALUES('planches',12);
INSERT INTO "sqlite_sequence" VALUES('regions',18);
INSERT INTO "sqlite_sequence" VALUES('demande',8);
COMMIT;
PRAGMA user_version = 31;
