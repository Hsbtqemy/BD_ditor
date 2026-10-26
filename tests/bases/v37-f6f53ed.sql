-- Base v37 faite par le code de f6f53ed (ses routes, sous trois comptes), vidée par
-- `sqlite3.Connection.iterdump` (la table plein texte recréée par son CREATE).
-- Refaite par : python tools/fabriquer_base_de_version.py f6f53ed tests/bases/v37-f6f53ed.sql
-- Ce qu'elle contient :
--   albums_vivants : [1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
--   album_detruit : 4
--   planche_detruite : 8
--   region_detruite : 20
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
--   collection_c : 9
--   album_source_des_soeurs : 10
--   album_soeur : 11
--   collection_de_lea : 10
--   demandes_v31 : {"rejoindre_acceptee": 6, "rejoindre_refusee": 7, "retour": 8}
--   album_amorce : 13
--   collections_detruites : [11, 12]
--   projet_de_jeu : 5
--   bacs_a_sable : [6, 7]
--   collection_d_un_invite : 15
--   album_du_bac : 18
--   collection_d_un_membre : 17
--   album_cinq_types : 21
--   regions_cinq_types : {"bulle": 32, "cartouche": 33, "texte": 34, "case": 31, "personnage": 35}
--   album_amorce_annotations : 22
--   album_retire_du_projet : 23
--   planche_detruite_v36 : 24
--   region_detruite_v36 : 41
--   grille : 1
--   releve : 1
--   doute : 1
--   acces_hors_projet : [[6, "utilisateur", "nora"], [6, "groupe", "invites"], [10, "utilisateur", "omar"]]
--   album_carnet_d_arrivant : 24
--   copies_de_nora : [25, 26]
--   demandes_v37 : {"en_attente": {"suppression_avec_soeur": 10, "suppression_derniere_copie": 11, "repartir": 12}, "close": 13}
--   compte_partage_responsable : "atelier"
--   max : {"albums": 26, "planches": 27, "regions": 45, "personnages": 2, "projet": 7, "collection": 17, "document": 19, "demande": 13}
--   comptes : {"albums": 24, "planches": 23, "regions": 39, "personnages": 2, "evenement": 230, "activite": 1, "tokens": 98, "annotations": 6, "recherche": 21, "projet": 5, "projet_acces": 10, "collection": 13, "document": 17, "demande": 13, "demande_document": 11, "copie": 24, "region_origine": 11, "jeu_document": 2, "geste_sur_copie": 9, "retrait_vu": 0, "grille": 1, "grille_version": 1, "projet_grille": 1, "releve": 1, "passe": 1, "doute": 1, "collection_acces": 11}
--   activites : [["ocr", "{\"planche_id\": 8}"]]
--   demandes_par_genre : {"rejoindre": 3, "rendre_copie": 1, "repartir": 1, "suppression_document": 6, "suppression_projet": 2}
--   planches_avec_master_origine : 23
--   natures_de_projet : {"bac à sable": 2, "jeu": 1, "ordinaire": 1, "repli": 1}
--   regions_par_type : {"bulle": 17, "cartouche": 2, "case": 13, "personnage": 5, "texte": 2}
--   crans_des_copies : {"annotations": 1, "images": 3, "origine": 17, "transcription": 3}
--   demandes_par_reponse : {"acceptee": 3, "en attente": 6, "refusee": 4}
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
INSERT INTO "activite" VALUES(1,'ocr','easyocr','moteur',NULL,NULL,'{"planche_id": 8}','{"crees": 0, "modifies": 0, "remplaces": 0}','2026-10-26 16:30:08','2026-10-26 16:30:08');
CREATE TABLE albums (
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
INSERT INTO "albums" VALUES(1,'Album 1',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:01',1,1);
INSERT INTO "albums" VALUES(2,'Album 2',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:07',2,1);
INSERT INTO "albums" VALUES(3,'Album 3',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:07',3,1);
INSERT INTO "albums" VALUES(5,'Album sans collection',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',5,1);
INSERT INTO "albums" VALUES(6,'Gardée au fonds',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',6,2);
INSERT INTO "albums" VALUES(7,'Importé au fonds',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',7,1);
INSERT INTO "albums" VALUES(8,'Demande refusée',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',8,1);
INSERT INTO "albums" VALUES(10,'Source des sœurs',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',10,2);
INSERT INTO "albums" VALUES(11,'Source des sœurs',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',10,2);
INSERT INTO "albums" VALUES(12,'Rejoindre refusé',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',11,1);
INSERT INTO "albums" VALUES(13,'Source des sœurs',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',10,2);
INSERT INTO "albums" VALUES(14,'Le parcours',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',12,5);
INSERT INTO "albums" VALUES(15,'Un exemple',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',13,5);
INSERT INTO "albums" VALUES(16,'Un exemple',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',13,6);
INSERT INTO "albums" VALUES(17,'Le parcours',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',12,6);
INSERT INTO "albums" VALUES(18,'Importé au bac',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',14,6);
INSERT INTO "albums" VALUES(19,'Un exemple',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',13,7);
INSERT INTO "albums" VALUES(20,'Le parcours',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',12,7);
INSERT INTO "albums" VALUES(21,'Cinq types',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',15,2);
INSERT INTO "albums" VALUES(22,'Cinq types',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',15,2);
INSERT INTO "albums" VALUES(23,'Retiré du projet',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',16,2);
INSERT INTO "albums" VALUES(24,'Carnet d''arrivant',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',17,2);
INSERT INTO "albums" VALUES(25,'Carnet de Nora',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',18,2);
INSERT INTO "albums" VALUES(26,'Carnet de Nora 2',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',19,2);
CREATE TABLE annotation_tags (
    annotation_id  INTEGER REFERENCES annotations(id) ON DELETE CASCADE,
    tag_id         INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_id, tag_id)
);
INSERT INTO "annotation_tags" VALUES(1,1);
INSERT INTO "annotation_tags" VALUES(2,1);
INSERT INTO "annotation_tags" VALUES(3,1);
INSERT INTO "annotation_tags" VALUES(4,1);
INSERT INTO "annotation_tags" VALUES(5,1);
INSERT INTO "annotation_tags" VALUES(6,1);
CREATE TABLE annotations (
    id                 INTEGER PRIMARY KEY,
    region_id          INTEGER UNIQUE REFERENCES regions(id) ON DELETE CASCADE,
    note               TEXT,
    date_creation      TEXT DEFAULT (datetime('now')),
    date_modification  TEXT DEFAULT (datetime('now')),
    recopiee           INTEGER NOT NULL DEFAULT 0
    -- v36 (COL-3, tranche 3b) : 1 si la ligne est arrivée avec une copie amorcée
    -- (`copier_le_travail`), telle quelle ; cf. `COUCHES_RECOPIEES`.
);
INSERT INTO "annotations" VALUES(1,2,'vu','2026-10-26 16:30:07','2026-10-26 16:30:07',0);
INSERT INTO "annotations" VALUES(2,7,'vu','2026-10-26 16:30:07','2026-10-26 16:30:07',0);
INSERT INTO "annotations" VALUES(3,12,'vu','2026-10-26 16:30:07','2026-10-26 16:30:07',0);
INSERT INTO "annotations" VALUES(4,22,'source','2026-10-26 16:30:08','2026-10-26 16:30:08',0);
INSERT INTO "annotations" VALUES(5,32,'à relever','2026-10-26 16:30:09','2026-10-26 16:30:09',0);
INSERT INTO "annotations" VALUES(6,37,'à relever','2026-10-26 16:30:09','2026-10-26 16:30:09',1);
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
INSERT INTO "attribut_dimension" VALUES(1,'case','cadrage',NULL,NULL,NULL,'provisoire',NULL,'2026-10-26 16:30:01');
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
INSERT INTO "attribut_valeur" VALUES(1,1,'gros plan',NULL,NULL,'provisoire',NULL,'2026-10-26 16:30:01');
CREATE TABLE bulle_locuteur (
    region_id      INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now')),
    recopiee           INTEGER NOT NULL DEFAULT 0
    -- v36 (COL-3, tranche 3b) : 1 si la ligne est arrivée avec une copie amorcée
    -- (`copier_le_travail`), telle quelle ; cf. `COUCHES_RECOPIEES`.
);
INSERT INTO "bulle_locuteur" VALUES(2,1,'2026-10-26 16:30:07',0);
INSERT INTO "bulle_locuteur" VALUES(7,1,'2026-10-26 16:30:07',0);
INSERT INTO "bulle_locuteur" VALUES(12,1,'2026-10-26 16:30:07',0);
CREATE TABLE collection (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
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
INSERT INTO "collection" VALUES(1,'Projet principal','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:00',1,1,NULL);
INSERT INTO "collection" VALUES(2,'Corpus principal',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:01',1,0,NULL);
INSERT INTO "collection" VALUES(3,'Incubateur',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:01',1,0,NULL);
INSERT INTO "collection" VALUES(4,'Collection par défaut','Créée automatiquement : tout album doit appartenir à une collection, qui est l''unité de cloisonnement des accès. Renommez-la et décrivez-la, ou déplacez ses albums vers des collections d''étude.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',1,0,NULL);
INSERT INTO "collection" VALUES(5,'Étude B','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',2,1,'ecriture');
INSERT INTO "collection" VALUES(6,'Collection B',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',2,0,NULL);
INSERT INTO "collection" VALUES(9,'Collection C',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',2,0,NULL);
INSERT INTO "collection" VALUES(10,'Collection de Léa',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',1,0,NULL);
INSERT INTO "collection" VALUES(13,'Jeu des bacs à sable','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',5,1,NULL);
INSERT INTO "collection" VALUES(14,'Bac à sable','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',6,1,'ecriture');
INSERT INTO "collection" VALUES(15,'Chez Sam',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',6,0,NULL);
INSERT INTO "collection" VALUES(16,'Bac à sable','Collection de base du projet : ce que le projet prend au fonds y arrive, et l''import la propose d''abord. Ses responsables en sont propriétaires ; elle se renomme, elle ne se supprime pas.',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:08',7,1,'ecriture');
INSERT INTO "collection" VALUES(17,'Par un membre',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-26 16:30:09',2,0,NULL);
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
INSERT INTO "collection_acces" VALUES(2,'utilisateur','lea','ecriture',0,'2026-10-26 16:30:01');
INSERT INTO "collection_acces" VALUES(3,'utilisateur','lea','ecriture',0,'2026-10-26 16:30:01');
INSERT INTO "collection_acces" VALUES(2,'utilisateur','sam','ecriture',0,'2026-10-26 16:30:01');
INSERT INTO "collection_acces" VALUES(6,'utilisateur','lea','proprietaire',0,'2026-10-26 16:30:08');
INSERT INTO "collection_acces" VALUES(9,'utilisateur','lea','proprietaire',0,'2026-10-26 16:30:08');
INSERT INTO "collection_acces" VALUES(10,'utilisateur','lea','proprietaire',0,'2026-10-26 16:30:08');
INSERT INTO "collection_acces" VALUES(15,'utilisateur','sam','proprietaire',0,'2026-10-26 16:30:08');
INSERT INTO "collection_acces" VALUES(17,'utilisateur','sam','proprietaire',0,'2026-10-26 16:30:09');
INSERT INTO "collection_acces" VALUES(6,'utilisateur','nora','ecriture',0,'2026-10-26 16:30:09');
INSERT INTO "collection_acces" VALUES(6,'groupe','invites','ecriture',0,'2026-10-26 16:30:09');
INSERT INTO "collection_acces" VALUES(10,'utilisateur','omar','ecriture',0,'2026-10-26 16:30:09');
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
INSERT INTO "collection_album" VALUES(9,11,NULL);
INSERT INTO "collection_album" VALUES(10,2,NULL);
INSERT INTO "collection_album" VALUES(2,12,NULL);
INSERT INTO "collection_album" VALUES(9,13,NULL);
INSERT INTO "collection_album" VALUES(13,14,NULL);
INSERT INTO "collection_album" VALUES(13,15,NULL);
INSERT INTO "collection_album" VALUES(14,16,NULL);
INSERT INTO "collection_album" VALUES(14,17,NULL);
INSERT INTO "collection_album" VALUES(15,18,NULL);
INSERT INTO "collection_album" VALUES(16,19,NULL);
INSERT INTO "collection_album" VALUES(16,20,NULL);
INSERT INTO "collection_album" VALUES(6,21,NULL);
INSERT INTO "collection_album" VALUES(9,22,NULL);
INSERT INTO "collection_album" VALUES(17,24,NULL);
INSERT INTO "collection_album" VALUES(6,25,NULL);
INSERT INTO "collection_album" VALUES(6,26,NULL);
CREATE TABLE collection_grille_masquee (
    collection_id  INTEGER NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    grille_id      INTEGER NOT NULL REFERENCES grille(id) ON DELETE CASCADE,
    masque_par     TEXT,
    masque_le      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, grille_id)
);
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
INSERT INTO "contribution_role" VALUES(1,'scénariste','creator','aut','2026-10-26 16:30:00');
INSERT INTO "contribution_role" VALUES(2,'dessinateur','creator','art','2026-10-26 16:30:00');
INSERT INTO "contribution_role" VALUES(3,'coloriste','contributor','clr','2026-10-26 16:30:00');
INSERT INTO "contribution_role" VALUES(4,'encreur','contributor',NULL,'2026-10-26 16:30:00');
INSERT INTO "contribution_role" VALUES(5,'lettreur','contributor',NULL,'2026-10-26 16:30:00');
INSERT INTO "contribution_role" VALUES(6,'traducteur','contributor','trl','2026-10-26 16:30:00');
INSERT INTO "contribution_role" VALUES(7,'préfacier','contributor','aui','2026-10-26 16:30:00');
CREATE TABLE copie (
    album_id           INTEGER PRIMARY KEY REFERENCES albums(id) ON DELETE CASCADE,
    creee_par          TEXT,
    creee_le           TEXT DEFAULT (datetime('now')),
    depuis_album_id    INTEGER,
    cran               TEXT NOT NULL DEFAULT 'origine',
    depuis_projet_nom  TEXT
);
INSERT INTO "copie" VALUES(1,'lea','2026-10-26 16:30:01',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(2,'sam','2026-10-26 16:30:07',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(3,'lea','2026-10-26 16:30:07',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(5,'hugo','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(6,'lea','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(7,'hugo','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(8,'lea','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(10,'lea','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(11,'lea','2026-10-26 16:30:08',10,'images','Étude B');
INSERT INTO "copie" VALUES(12,'sam','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(13,'lea','2026-10-26 16:30:08',10,'transcription','Étude B');
INSERT INTO "copie" VALUES(14,NULL,'2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(15,NULL,'2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(16,'lea','2026-10-26 16:30:08',15,'transcription','Jeu des bacs à sable');
INSERT INTO "copie" VALUES(17,'lea','2026-10-26 16:30:08',14,'images','Jeu des bacs à sable');
INSERT INTO "copie" VALUES(18,'sam','2026-10-26 16:30:08',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(19,'hugo','2026-10-26 16:30:08',15,'transcription','Jeu des bacs à sable');
INSERT INTO "copie" VALUES(20,'hugo','2026-10-26 16:30:08',14,'images','Jeu des bacs à sable');
INSERT INTO "copie" VALUES(21,'lea','2026-10-26 16:30:09',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(22,'lea','2026-10-26 16:30:09',21,'annotations','Étude B');
INSERT INTO "copie" VALUES(23,'lea','2026-10-26 16:30:09',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(24,'sam','2026-10-26 16:30:09',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(25,'nora','2026-10-26 16:30:09',NULL,'origine',NULL);
INSERT INTO "copie" VALUES(26,'nora','2026-10-26 16:30:09',NULL,'origine',NULL);
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
    collection_nom TEXT,
    cran           TEXT
    -- `cran` (v32, COL-3, tranche 3b) : le cran demandé d'une copie AMORCÉE (« en partir »)
    -- ou d'une remise à zéro (« repartir »), parmi ceux de `copie.cran` ; NULL pour tout
    -- autre genre. Commentaire SOUS la colonne : c'est la dernière de la table (cf. celui
    -- de `collection.projet_id`).
);
INSERT INTO "demande" VALUES(1,'suppression_document','sam','Importé par erreur.','2026-10-26 16:30:08',1,'Projet principal','2026-10-26 16:30:08',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "demande" VALUES(2,'suppression_document','sam','Importé par erreur.','2026-10-26 16:30:08',1,'Projet principal','2026-10-26 16:30:08','refusee','hugo','2026-10-26 16:30:08',NULL,NULL,NULL);
INSERT INTO "demande" VALUES(3,'suppression_document','sam','Importé par erreur.','2026-10-26 16:30:08',1,'Projet principal','2026-10-26 16:30:08','acceptee','hugo','2026-10-26 16:30:08',NULL,NULL,NULL);
INSERT INTO "demande" VALUES(4,'suppression_projet','lea','Étude terminée.',NULL,2,'Étude B','2026-10-26 16:30:08',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "demande" VALUES(5,'suppression_projet','sam','Créé par erreur.',NULL,4,'Éphémère 2','2026-10-26 16:30:08','acceptee','hugo','2026-10-26 16:30:08',NULL,NULL,NULL);
INSERT INTO "demande" VALUES(6,'rejoindre','lea',NULL,NULL,1,'Projet principal','2026-10-26 16:30:08','acceptee','hugo','2026-10-26 16:30:08',10,'Collection de Léa',NULL);
INSERT INTO "demande" VALUES(7,'rejoindre','lea',NULL,NULL,1,'Projet principal','2026-10-26 16:30:08','refusee','hugo','2026-10-26 16:30:08',10,'Collection de Léa',NULL);
INSERT INTO "demande" VALUES(8,'rendre_copie','lea','On y retravaille.',NULL,2,'Étude B','2026-10-26 16:30:08',NULL,NULL,NULL,5,'Étude B',NULL);
INSERT INTO "demande" VALUES(9,'rejoindre','lea',NULL,NULL,1,'Projet principal','2026-10-26 16:30:08','refusee','lea','2026-10-26 16:30:08',11,'Arrivée détruite',NULL);
INSERT INTO "demande" VALUES(10,'suppression_document','nora','Plus utile.','2026-10-26 16:30:09',2,'Étude B','2026-10-26 16:30:09',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "demande" VALUES(11,'suppression_document','nora','Plus utile.','2026-10-26 16:30:09',2,'Étude B','2026-10-26 16:30:09',NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "demande" VALUES(12,'repartir','nora','Plus utile.','2026-10-26 16:30:09',2,'Étude B','2026-10-26 16:30:09',NULL,NULL,NULL,NULL,NULL,'images');
INSERT INTO "demande" VALUES(13,'suppression_document','nora','Plus utile.','2026-10-26 16:30:09',2,'Étude B','2026-10-26 16:30:09','refusee','hugo','2026-10-26 16:30:09',NULL,NULL,NULL);
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
INSERT INTO "demande_document" VALUES(9,2,2,'Album 2','refusee',NULL);
INSERT INTO "demande_document" VALUES(10,10,10,'Source des sœurs',NULL,NULL);
INSERT INTO "demande_document" VALUES(11,18,25,'Carnet de Nora',NULL,NULL);
INSERT INTO "demande_document" VALUES(12,19,26,'Carnet de Nora 2',NULL,NULL);
INSERT INTO "demande_document" VALUES(13,19,26,'Carnet de Nora 2','refusee',NULL);
CREATE TABLE document (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    importe_par        TEXT,
    importe_le         TEXT DEFAULT (datetime('now')),
    projet_origine_id  INTEGER,
    projet_origine_nom TEXT
);
INSERT INTO "document" VALUES(1,'lea','2026-10-26 16:30:01',1,'Projet principal');
INSERT INTO "document" VALUES(2,'sam','2026-10-26 16:30:07',1,'Projet principal');
INSERT INTO "document" VALUES(3,'lea','2026-10-26 16:30:07',1,'Projet principal');
INSERT INTO "document" VALUES(5,'hugo','2026-10-26 16:30:08',1,'Projet principal');
INSERT INTO "document" VALUES(6,'lea','2026-10-26 16:30:08',2,'Étude B');
INSERT INTO "document" VALUES(7,'hugo','2026-10-26 16:30:08',NULL,NULL);
INSERT INTO "document" VALUES(8,'lea','2026-10-26 16:30:08',1,'Projet principal');
INSERT INTO "document" VALUES(10,'lea','2026-10-26 16:30:08',2,'Étude B');
INSERT INTO "document" VALUES(11,'sam','2026-10-26 16:30:08',1,'Projet principal');
INSERT INTO "document" VALUES(12,NULL,'2026-10-26 16:30:08',5,'Jeu des bacs à sable');
INSERT INTO "document" VALUES(13,NULL,'2026-10-26 16:30:08',5,'Jeu des bacs à sable');
INSERT INTO "document" VALUES(14,'sam','2026-10-26 16:30:08',6,'Bac à sable');
INSERT INTO "document" VALUES(15,'lea','2026-10-26 16:30:09',2,'Étude B');
INSERT INTO "document" VALUES(16,'lea','2026-10-26 16:30:09',2,'Étude B');
INSERT INTO "document" VALUES(17,'sam','2026-10-26 16:30:09',2,'Étude B');
INSERT INTO "document" VALUES(18,'nora','2026-10-26 16:30:09',2,'Étude B');
INSERT INTO "document" VALUES(19,'nora','2026-10-26 16:30:09',2,'Étude B');
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
CREATE TABLE doute (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    releve_id  INTEGER NOT NULL REFERENCES releve(id) ON DELETE CASCADE,
    ouvert_par TEXT,
    ouvert_le  TEXT DEFAULT (datetime('now')),
    leve_par   TEXT,
    leve_le    TEXT,
    issue      TEXT
);
INSERT INTO "doute" VALUES(1,1,'lea','2026-10-26 16:30:09',NULL,NULL,NULL);
CREATE TABLE doute_message (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doute_id  INTEGER NOT NULL REFERENCES doute(id) ON DELETE CASCADE,
    auteur    TEXT,
    date      TEXT DEFAULT (datetime('now')),
    texte     TEXT NOT NULL
);
INSERT INTO "doute_message" VALUES(1,1,'lea','2026-10-26 16:30:09','Un cri, ou une onomatopée ?');
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
INSERT INTO "evenement" VALUES(1,NULL,'creation','hugo','humain','collection',2,NULL,'{"nom": "Corpus principal", "proprietaire": "hugo"}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(2,NULL,'creation','hugo','humain','collection',3,NULL,'{"nom": "Incubateur", "proprietaire": "hugo"}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(3,NULL,'lien','hugo','humain','collection_acces',2,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "lea"}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(4,NULL,'lien','hugo','humain','collection_acces',3,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "lea"}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(5,NULL,'lien','hugo','humain','collection_acces',2,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "sam"}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(6,NULL,'creation','lea','humain','document',1,NULL,'{"album_id": 1, "titre": "Album 1"}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(7,NULL,'lien','lea','humain','collection_album',1,NULL,'{"album_id": 1, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(8,NULL,'modification','lea','humain','document',1,NULL,'{"album_id": 1, "planche": {"id": 1, "numero": 1}}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(9,NULL,'creation','lea','humain','regions',1,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 1, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(10,NULL,'creation','lea','humain','regions',2,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:01');
INSERT INTO "evenement" VALUES(11,NULL,'modification','lea','humain','regions',2,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 0 0", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(12,NULL,'creation','lea','humain','annotations',2,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(13,NULL,'lien','lea','humain','bulle_locuteur',2,NULL,'{"personnage_id": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(14,NULL,'creation','lea','humain','regions',3,NULL,'{"h": 5, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "personnage", "w": 5, "x": 2, "y": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(15,NULL,'lien','lea','humain','personnage_presence',3,NULL,'{"personnage_id": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(16,NULL,'lien','lea','humain','region_attribut',1,NULL,'{"valeur_id": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(17,NULL,'validation','lea','humain','planches',1,NULL,'{"validee": true}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(18,NULL,'modification','lea','humain','document',1,NULL,'{"album_id": 1, "planche": {"id": 2, "numero": 2}}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(19,NULL,'creation','lea','humain','regions',4,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 2, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(20,NULL,'creation','lea','humain','regions',5,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 4, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(21,NULL,'modification','lea','humain','regions',5,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 4, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 0 1", "ordre": 1, "parent_id": 4, "planche_id": 2, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(22,NULL,'creation','sam','humain','document',2,NULL,'{"album_id": 2, "titre": "Album 2"}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(23,NULL,'lien','sam','humain','collection_album',2,NULL,'{"album_id": 2, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(24,NULL,'modification','sam','humain','document',2,NULL,'{"album_id": 2, "planche": {"id": 3, "numero": 1}}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(25,NULL,'creation','sam','humain','regions',6,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 3, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(26,NULL,'creation','sam','humain','regions',7,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 6, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(27,NULL,'modification','sam','humain','regions',7,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 6, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 1 0", "ordre": 1, "parent_id": 6, "planche_id": 3, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(28,NULL,'creation','sam','humain','annotations',7,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(29,NULL,'lien','sam','humain','bulle_locuteur',7,NULL,'{"personnage_id": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(30,NULL,'creation','sam','humain','regions',8,NULL,'{"h": 5, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": 6, "planche_id": 3, "source": "manuel", "type": "personnage", "w": 5, "x": 2, "y": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(31,NULL,'lien','sam','humain','personnage_presence',8,NULL,'{"personnage_id": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(32,NULL,'lien','sam','humain','region_attribut',6,NULL,'{"valeur_id": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(33,NULL,'validation','sam','humain','planches',3,NULL,'{"validee": true}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(34,NULL,'modification','sam','humain','document',2,NULL,'{"album_id": 2, "planche": {"id": 4, "numero": 2}}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(35,NULL,'creation','sam','humain','regions',9,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 4, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(36,NULL,'creation','sam','humain','regions',10,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 9, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(37,NULL,'modification','sam','humain','regions',10,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 9, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 1 1", "ordre": 1, "parent_id": 9, "planche_id": 4, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(38,NULL,'creation','lea','humain','document',3,NULL,'{"album_id": 3, "titre": "Album 3"}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(39,NULL,'lien','lea','humain','collection_album',3,NULL,'{"album_id": 3, "collection": "Incubateur", "collection_id": 3}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(40,NULL,'modification','lea','humain','document',3,NULL,'{"album_id": 3, "planche": {"id": 5, "numero": 1}}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(41,NULL,'creation','lea','humain','regions',11,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 5, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(42,NULL,'creation','lea','humain','regions',12,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 11, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(43,NULL,'modification','lea','humain','regions',12,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 11, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 2 0", "ordre": 1, "parent_id": 11, "planche_id": 5, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(44,NULL,'creation','lea','humain','annotations',12,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(45,NULL,'lien','lea','humain','bulle_locuteur',12,NULL,'{"personnage_id": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(46,NULL,'creation','lea','humain','regions',13,NULL,'{"h": 5, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": 11, "planche_id": 5, "source": "manuel", "type": "personnage", "w": 5, "x": 2, "y": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(47,NULL,'lien','lea','humain','personnage_presence',13,NULL,'{"personnage_id": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(48,NULL,'lien','lea','humain','region_attribut',11,NULL,'{"valeur_id": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(49,NULL,'validation','lea','humain','planches',5,NULL,'{"validee": true}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(50,NULL,'modification','lea','humain','document',3,NULL,'{"album_id": 3, "planche": {"id": 6, "numero": 2}}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(51,NULL,'creation','lea','humain','regions',14,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 6, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(52,NULL,'creation','lea','humain','regions',15,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 14, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(53,NULL,'modification','lea','humain','regions',15,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 14, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 2 1", "ordre": 1, "parent_id": 14, "planche_id": 6, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(54,NULL,'creation','lea','humain','document',4,NULL,'{"album_id": 4, "titre": "Album 4"}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(55,NULL,'lien','lea','humain','collection_album',4,NULL,'{"album_id": 4, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(56,NULL,'modification','lea','humain','document',4,NULL,'{"album_id": 4, "planche": {"id": 7, "numero": 1}}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(57,NULL,'creation','lea','humain','regions',16,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 7, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(58,NULL,'creation','lea','humain','regions',17,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 16, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(59,NULL,'modification','lea','humain','regions',17,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 16, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 3 0", "ordre": 1, "parent_id": 16, "planche_id": 7, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(60,NULL,'creation','lea','humain','annotations',17,NULL,'{"note": "vu", "tags": ["dialogue"]}','2026-10-26 16:30:07');
INSERT INTO "evenement" VALUES(61,NULL,'lien','lea','humain','bulle_locuteur',17,NULL,'{"personnage_id": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(62,NULL,'creation','lea','humain','regions',18,NULL,'{"h": 5, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": 16, "planche_id": 7, "source": "manuel", "type": "personnage", "w": 5, "x": 2, "y": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(63,NULL,'lien','lea','humain','personnage_presence',18,NULL,'{"personnage_id": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(64,NULL,'lien','lea','humain','region_attribut',16,NULL,'{"valeur_id": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(65,NULL,'validation','lea','humain','planches',7,NULL,'{"validee": true}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(66,NULL,'modification','lea','humain','document',4,NULL,'{"album_id": 4, "planche": {"id": 8, "numero": 2}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(67,NULL,'creation','lea','humain','regions',19,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 8, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(68,NULL,'creation','lea','humain','regions',20,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 19, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(69,NULL,'modification','lea','humain','regions',20,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 19, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 3 1", "ordre": 1, "parent_id": 19, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(70,NULL,'modification','lea','humain','regions',2,'{"h": 9, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 0 0", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "AVANT ANNULER", "ordre": 1, "parent_id": 1, "planche_id": 1, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(71,NULL,'annulation','lea','humain','evenement',70,'{"acte": "modification", "cible_id": 2, "cible_table": "regions"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(72,NULL,'suppression','lea','humain','regions',20,'{"h": 9, "id": 20, "nom": null, "ocr_texte": "TINTIN ET LE OTAGE 3 1", "ordre": 1, "parent_id": 19, "planche_id": 8, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(73,NULL,'modification','hugo','humain','document',4,'{"album_id": 4, "planche": {"id": 8, "numero": 2}}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(74,NULL,'delien','hugo','humain','collection_album',4,'{"album_id": 4, "collection": "Corpus principal", "collection_id": 2}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(75,NULL,'suppression','hugo','humain','document',4,'{"album_id": 4, "planches": 1, "titre": "Album 4"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(76,NULL,'lien','lea','humain','bulle_locuteur',2,'{"personnage_id": 1}','{"personnage_id": 3}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(77,NULL,'lien','lea','humain','bulle_locuteur',2,'{"personnage_id": 3}','{"personnage_id": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(78,NULL,'creation','hugo','humain','document',5,NULL,'{"album_id": 5, "titre": "Album sans collection"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(79,NULL,'lien','hugo','humain','collection_album',5,NULL,'{"album_id": 5, "collection": "Collection par défaut", "collection_id": 4}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(80,NULL,'lien','hugo','humain','projet_acces',1,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "membre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(81,NULL,'lien','hugo','humain','projet_acces',1,NULL,'{"genre": "utilisateur", "principal": "rita", "role": "responsable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(82,NULL,'lien','hugo','humain','projet_acces',1,NULL,'{"genre": "groupe", "principal": "chefs", "role": "responsable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(83,NULL,'creation','hugo','humain','projet',2,NULL,'{"nom": "Étude B"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(84,NULL,'creation','hugo','humain','collection',5,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Étude B", "projet_id": 2, "proprietaire": null}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(85,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "utilisateur", "principal": "lea", "role": "responsable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(86,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "membre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(87,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "groupe", "principal": "etudiants", "role": "membre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(88,NULL,'creation','lea','humain','collection',6,NULL,'{"nom": "Collection B", "proprietaire": "lea"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(89,NULL,'creation','lea','humain','document',6,NULL,'{"album_id": 6, "titre": "Gardée au fonds"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(90,NULL,'lien','lea','humain','collection_album',6,NULL,'{"album_id": 6, "collection": "Collection B", "collection_id": 6}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(91,NULL,'modification','lea','humain','document',6,NULL,'{"album_id": 6, "planche": {"id": 9, "numero": 1}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(92,NULL,'delien','lea','humain','collection_album',6,'{"album_id": 6, "collection": "Collection B", "collection_id": 6}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(93,NULL,'creation','hugo','humain','document',7,NULL,'{"album_id": 7, "titre": "Importé au fonds"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(94,NULL,'lien','hugo','humain','collection_album',7,NULL,'{"album_id": 7, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(95,NULL,'creation','sam','humain','demande',1,NULL,'{"album_id": 1, "document_id": 1, "genre": "suppression_document"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(96,NULL,'creation','lea','humain','document',8,NULL,'{"album_id": 8, "titre": "Demande refusée"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(97,NULL,'lien','lea','humain','collection_album',8,NULL,'{"album_id": 8, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(98,NULL,'creation','sam','humain','demande',2,NULL,'{"album_id": 8, "document_id": 8, "genre": "suppression_document"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(99,NULL,'modification','hugo','humain','demande',2,'{"reponse": null}','{"reponse": "refusee"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(100,NULL,'creation','lea','humain','document',9,NULL,'{"album_id": 9, "titre": "Demande acceptée"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(101,NULL,'lien','lea','humain','collection_album',9,NULL,'{"album_id": 9, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(102,NULL,'modification','lea','humain','document',9,NULL,'{"album_id": 9, "planche": {"id": 10, "numero": 1}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(103,NULL,'creation','sam','humain','demande',3,NULL,'{"album_id": 9, "document_id": 9, "genre": "suppression_document"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(104,NULL,'delien','hugo','humain','collection_album',9,'{"album_id": 9, "collection": "Corpus principal", "collection_id": 2}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(105,NULL,'suppression','hugo','humain','document',9,'{"album_id": 9, "planches": 1, "titre": "Demande acceptée"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(106,NULL,'modification','hugo','humain','demande',3,'{"reponse": null}','{"reponse": "acceptee"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(107,NULL,'creation','lea','humain','demande',4,NULL,'{"genre": "suppression_projet", "projet_id": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(108,NULL,'creation','hugo','humain','projet',3,NULL,'{"nom": "Éphémère"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(109,NULL,'creation','hugo','humain','collection',7,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Éphémère", "projet_id": 3, "proprietaire": null}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(110,NULL,'suppression','hugo','humain','collection',7,'{"base": true, "nom": "Éphémère"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(111,NULL,'suppression','hugo','humain','projet',3,'{"nom": "Éphémère"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(112,NULL,'creation','hugo','humain','projet',4,NULL,'{"nom": "Éphémère 2"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(113,NULL,'creation','hugo','humain','collection',8,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Éphémère 2", "projet_id": 4, "proprietaire": null}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(114,NULL,'lien','hugo','humain','projet_acces',4,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "responsable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(115,NULL,'creation','sam','humain','demande',5,NULL,'{"genre": "suppression_projet", "projet_id": 4}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(116,NULL,'modification','hugo','humain','demande',5,'{"reponse": null}','{"reponse": "acceptee"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(117,NULL,'suppression','hugo','humain','collection',8,'{"base": true, "nom": "Éphémère 2"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(118,NULL,'suppression','hugo','humain','projet',4,'{"nom": "Éphémère 2"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(119,NULL,'creation','lea','humain','collection',9,NULL,'{"nom": "Collection C", "proprietaire": "lea"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(120,NULL,'creation','lea','humain','document',10,NULL,'{"album_id": 10, "titre": "Source des sœurs"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(121,NULL,'lien','lea','humain','collection_album',10,NULL,'{"album_id": 10, "collection": "Collection B", "collection_id": 6}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(122,NULL,'modification','lea','humain','document',10,NULL,'{"album_id": 10, "planche": {"id": 11, "numero": 1}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(123,NULL,'creation','lea','humain','regions',21,NULL,'{"h": 20, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 11, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(124,NULL,'creation','lea','humain','regions',22,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 21, "planche_id": 11, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(125,NULL,'modification','lea','humain','regions',22,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 21, "planche_id": 11, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "LE OTAGE SOEUR", "ordre": 1, "parent_id": 21, "planche_id": 11, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(126,NULL,'creation','lea','humain','annotations',22,NULL,'{"note": "source", "tags": ["dialogue"]}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(127,NULL,'modification','lea','humain','document',10,NULL,'{"album_id": 11, "copie": {"collection_id": 9, "cran": "images", "depuis_album_id": 10}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(128,NULL,'lien','lea','humain','collection_album',10,NULL,'{"album_id": 11, "collection": "Collection C", "collection_id": 9}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(129,NULL,'creation','hugo','humain','collection',10,NULL,'{"nom": "Collection de Léa", "proprietaire": "hugo"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(130,NULL,'lien','hugo','humain','collection_acces',10,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "proprietaire", "principal": "lea"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(131,NULL,'creation','lea','humain','demande',6,NULL,'{"collection_id": 10, "documents": [2], "genre": "rejoindre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(132,NULL,'lien','hugo','humain','collection_album',2,NULL,'{"album_id": 2, "collection": "Collection de Léa", "collection_id": 10}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(133,NULL,'modification','hugo','humain','demande',6,'{"reponse": null}','{"reponse": "acceptee"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(134,NULL,'creation','sam','humain','document',11,NULL,'{"album_id": 12, "titre": "Rejoindre refusé"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(135,NULL,'lien','sam','humain','collection_album',11,NULL,'{"album_id": 12, "collection": "Corpus principal", "collection_id": 2}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(136,NULL,'creation','lea','humain','demande',7,NULL,'{"collection_id": 10, "documents": [11], "genre": "rejoindre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(137,NULL,'modification','hugo','humain','demande',7,'{"reponse": null}','{"reponse": "refusee"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(138,NULL,'creation','lea','humain','demande',8,NULL,'{"collection_id": 5, "documents": [6], "genre": "rendre_copie"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(139,NULL,'modification','lea','humain','document',10,NULL,'{"album_id": 13, "copie": {"collection_id": 9, "copies": {"regions": 2, "textes": 1}, "cran": "transcription", "depuis_album_id": 10, "laisses": {}}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(140,NULL,'lien','lea','humain','collection_album',10,NULL,'{"album_id": 13, "collection": "Collection C", "collection_id": 9}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(141,NULL,'creation','hugo','humain','collection',11,NULL,'{"nom": "Arrivée détruite", "proprietaire": "hugo"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(142,NULL,'lien','hugo','humain','collection_acces',11,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "proprietaire", "principal": "lea"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(143,NULL,'creation','hugo','humain','collection',12,NULL,'{"nom": "Éphémère", "proprietaire": "hugo"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(144,NULL,'lien','hugo','humain','collection_acces',12,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "proprietaire", "principal": "lea"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(145,NULL,'creation','lea','humain','demande',9,NULL,'{"collection_id": 11, "documents": [2], "genre": "rejoindre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(146,NULL,'modification','lea','humain','demande',9,'{"reponse": null}','{"reponse": "refusee"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(147,NULL,'suppression','lea','humain','collection',11,'{"nom": "Arrivée détruite"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(148,NULL,'suppression','lea','humain','collection',12,'{"nom": "Éphémère"}',NULL,'2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(149,NULL,'creation',NULL,'humain','document',12,NULL,'{"album_id": 14, "jeu": {"cle": "parcours", "part": "depot"}, "titre": "Le parcours"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(150,NULL,'lien',NULL,'humain','collection_album',12,NULL,'{"album_id": 14, "collection": "Jeu des bacs à sable", "collection_id": 13}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(151,NULL,'creation',NULL,'humain','document',13,NULL,'{"album_id": 15, "jeu": {"cle": "exemple", "part": "depot"}, "titre": "Un exemple"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(152,NULL,'lien',NULL,'humain','collection_album',13,NULL,'{"album_id": 15, "collection": "Jeu des bacs à sable", "collection_id": 13}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(153,NULL,'creation','lea','humain','projet',6,NULL,'{"bac_a_sable": true, "efface_le": "2026-11-02 03:00:00", "nom": "Bac à sable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(154,NULL,'lien','lea','humain','projet_acces',6,NULL,'{"genre": "utilisateur", "principal": "lea", "role": "responsable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(155,NULL,'creation','lea','humain','collection',14,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Bac à sable", "projet_id": 6, "proprietaire": null}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(156,NULL,'modification','lea','humain','document',13,NULL,'{"album_id": 16, "copie": {"collection_id": 14, "copies": {"regions": 2, "textes": 1}, "cran": "transcription", "depuis_album_id": 15, "laisses": {}}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(157,NULL,'lien','lea','humain','collection_album',13,NULL,'{"album_id": 16, "collection": "Bac à sable", "collection_id": 14}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(158,NULL,'modification','lea','humain','document',12,NULL,'{"album_id": 17, "copie": {"collection_id": 14, "cran": "images", "depuis_album_id": 14}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(159,NULL,'lien','lea','humain','collection_album',12,NULL,'{"album_id": 17, "collection": "Bac à sable", "collection_id": 14}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(160,NULL,'lien','lea','humain','projet_acces',6,NULL,'{"genre": "utilisateur", "principal": "sam", "role": "membre"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(161,NULL,'creation','sam','humain','collection',15,NULL,'{"nom": "Chez Sam", "proprietaire": "sam"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(162,NULL,'creation','sam','humain','document',14,NULL,'{"album_id": 18, "titre": "Importé au bac"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(163,NULL,'lien','sam','humain','collection_album',14,NULL,'{"album_id": 18, "collection": "Chez Sam", "collection_id": 15}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(164,NULL,'modification','sam','humain','document',14,NULL,'{"album_id": 18, "planche": {"id": 18, "numero": 1}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(165,NULL,'creation','hugo','humain','projet',7,NULL,'{"bac_a_sable": true, "efface_le": "2026-11-02 03:00:00", "nom": "Bac à sable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(166,NULL,'lien','hugo','humain','projet_acces',7,NULL,'{"genre": "utilisateur", "principal": "hugo", "role": "responsable"}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(167,NULL,'creation','hugo','humain','collection',16,NULL,'{"acces_membres": "ecriture", "base": true, "nom": "Bac à sable", "projet_id": 7, "proprietaire": null}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(168,NULL,'modification','hugo','humain','document',13,NULL,'{"album_id": 19, "copie": {"collection_id": 16, "copies": {"regions": 2, "textes": 1}, "cran": "transcription", "depuis_album_id": 15, "laisses": {}}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(169,NULL,'lien','hugo','humain','collection_album',13,NULL,'{"album_id": 19, "collection": "Bac à sable", "collection_id": 16}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(170,NULL,'modification','hugo','humain','document',12,NULL,'{"album_id": 20, "copie": {"collection_id": 16, "cran": "images", "depuis_album_id": 14}}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(171,NULL,'lien','hugo','humain','collection_album',12,NULL,'{"album_id": 20, "collection": "Bac à sable", "collection_id": 16}','2026-10-26 16:30:08');
INSERT INTO "evenement" VALUES(172,NULL,'modification','lea','humain','projet',2,'{"membres_creent_collections": false}','{"membres_creent_collections": true}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(173,NULL,'creation','sam','humain','collection',17,NULL,'{"nom": "Par un membre", "proprietaire": "sam"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(174,NULL,'creation','lea','humain','document',15,NULL,'{"album_id": 21, "titre": "Cinq types"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(175,NULL,'lien','lea','humain','collection_album',15,NULL,'{"album_id": 21, "collection": "Collection B", "collection_id": 6}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(176,NULL,'modification','lea','humain','document',15,NULL,'{"album_id": 21, "planche": {"id": 21, "numero": 1}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(177,NULL,'creation','lea','humain','regions',31,NULL,'{"h": 30, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 21, "source": "manuel", "type": "case", "w": 30, "x": 0, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(178,NULL,'creation','lea','humain','regions',32,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(179,NULL,'modification','lea','humain','regions',32,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!", "ordre": 1, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "bulle", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(180,NULL,'creation','lea','humain','regions',33,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "cartouche", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(181,NULL,'modification','lea','humain','regions',33,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "cartouche", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "— C''EST L''HISTOIRE D''UN OTAGE...", "ordre": 2, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "cartouche", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(182,NULL,'creation','lea','humain','regions',34,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 3, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "texte", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(183,NULL,'modification','lea','humain','regions',34,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 3, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "texte", "w": 9, "x": 1, "y": 1}','{"h": 9, "nom": null, "ocr_texte": "presqu''île, dis-moi : va-t-il por-\ntrait ?!", "ordre": 3, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "texte", "w": 9, "x": 1, "y": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(184,NULL,'creation','lea','humain','regions',35,NULL,'{"h": 5, "nom": null, "ocr_texte": null, "ordre": 4, "parent_id": 31, "planche_id": 21, "source": "manuel", "type": "personnage", "w": 5, "x": 2, "y": 2}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(185,NULL,'creation','lea','humain','annotations',32,NULL,'{"note": "à relever", "tags": ["dialogue"]}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(186,NULL,'modification','lea','humain','document',15,NULL,'{"album_id": 22, "copie": {"collection_id": 9, "copies": {"annotations": 1, "attributs": 0, "corrections": 0, "locuteurs": 0, "passes": 0, "presences": 0, "regions": 5, "releves": 0, "tags": 1, "textes": 3}, "cran": "annotations", "depuis_album_id": 21, "laisses": {"attributs": 0, "releves": 0, "tags": 0}}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(187,NULL,'lien','lea','humain','collection_album',15,NULL,'{"album_id": 22, "collection": "Collection C", "collection_id": 9}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(188,NULL,'creation','lea','humain','document',16,NULL,'{"album_id": 23, "titre": "Retiré du projet"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(189,NULL,'lien','lea','humain','collection_album',16,NULL,'{"album_id": 23, "collection": "Collection B", "collection_id": 6}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(190,NULL,'modification','lea','humain','document',16,NULL,'{"album_id": 23, "planche": {"id": 23, "numero": 1}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(191,NULL,'delien','lea','humain','collection_album',16,'{"album_id": 23, "collection": "Collection B", "collection_id": 6}',NULL,'2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(192,NULL,'modification','lea','humain','document',16,NULL,'{"album_id": 23, "retire_du_projet": {"collections": [{"id": 6, "nom": "Collection B", "proprietaires": [{"genre": "utilisateur", "principal": "lea"}]}], "motif": "Entré par erreur.", "projet_id": 2, "titre": "Retiré du projet"}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(193,NULL,'modification','lea','humain','document',15,NULL,'{"album_id": 21, "planche": {"id": 24, "numero": 2}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(194,NULL,'creation','lea','humain','regions',41,NULL,'{"h": 4, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": null, "planche_id": 21, "source": "manuel", "type": "bulle", "w": 4, "x": 3, "y": 3}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(195,NULL,'modification','hugo','humain','document',15,'{"album_id": 21, "planche": {"id": 24, "numero": 2}}',NULL,'2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(196,NULL,'suppression','lea','humain','regions',41,'{"h": 4, "id": 41, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": null, "planche_id": 21, "source": "manuel", "type": "bulle", "w": 4, "x": 3, "y": 3}',NULL,'2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(197,NULL,'creation','lea','humain','grille',1,NULL,'{"nom": "Signaux", "ouverte": false, "projet_id": 2}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(198,NULL,'modification','lea','humain','grille',1,NULL,'{"import": {"empreinte": "0f4b4676423449ee4a96bae2f53f55ef19e237eeed78cbae1cb43e6841ac3714", "etat": "brouillon", "numero": 1, "remplace": false}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(199,NULL,'modification','lea','humain','grille',1,'{"etat": "brouillon", "version": 1}','{"etat": "publiee", "version": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(200,NULL,'lien','lea','humain','grille',1,NULL,'{"projet_id": 2, "version": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(201,NULL,'creation','lea','humain','releve',32,NULL,'{"auteur": "lea", "cree_le": "2026-10-26 16:30:09", "entree_cle": "cri", "formes": ["J''"], "grille_id": 1, "lien_region_id": null, "lien_texte": null, "modifie_le": null, "modifie_par": null, "mots": [0], "origine_id": null, "planche_id": null, "precision": null, "qualificatifs": [], "region_id": 32, "releve_id": 1, "texte_ancre": "J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!", "une": 0, "variante_cle": null, "version_id": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(202,NULL,'passe','lea','humain','releve',32,'{"grille_id": 1, "passe": false, "passe_cle": "1:", "rubrique_cle": "", "version_id": 1}','{"grille_id": 1, "passe": true, "passe_cle": "1:", "rubrique_cle": "", "version_id": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(203,NULL,'doute','lea','humain','releve',32,NULL,'{"doute": "ouvert", "doute_id": 1, "message_id": 1, "releve_id": 1}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(204,NULL,'lien','lea','humain','collection_acces',6,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "nora"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(205,NULL,'lien','lea','humain','collection_acces',6,NULL,'{"exporter": false, "genre": "groupe", "niveau": "ecriture", "principal": "invites"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(206,NULL,'lien','lea','humain','collection_acces',10,NULL,'{"exporter": false, "genre": "utilisateur", "niveau": "ecriture", "principal": "omar"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(207,NULL,'creation','sam','humain','document',17,NULL,'{"album_id": 24, "titre": "Carnet d''arrivant"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(208,NULL,'lien','sam','humain','collection_album',17,NULL,'{"album_id": 24, "collection": "Par un membre", "collection_id": 17}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(209,NULL,'modification','sam','humain','document',17,NULL,'{"album_id": 24, "planche": {"id": 25, "numero": 1}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(210,NULL,'creation','nora','humain','document',18,NULL,'{"album_id": 25, "titre": "Carnet de Nora"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(211,NULL,'lien','nora','humain','collection_album',18,NULL,'{"album_id": 25, "collection": "Collection B", "collection_id": 6}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(212,NULL,'modification','nora','humain','document',18,NULL,'{"album_id": 25, "planche": {"id": 26, "numero": 1}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(213,NULL,'creation','nora','humain','regions',42,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 26, "source": "manuel", "type": "bulle", "w": 9, "x": 0, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(214,NULL,'modification','nora','humain','regions',42,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 26, "source": "manuel", "type": "bulle", "w": 9, "x": 0, "y": 0}','{"h": 9, "nom": null, "ocr_texte": "LE OTAGE", "ordre": 1, "parent_id": null, "planche_id": 26, "source": "manuel", "type": "bulle", "w": 9, "x": 0, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(215,NULL,'creation','lea','humain','regions',43,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": null, "planche_id": 26, "source": "manuel", "type": "bulle", "w": 9, "x": 10, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(216,NULL,'modification','lea','humain','regions',43,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": null, "planche_id": 26, "source": "manuel", "type": "bulle", "w": 9, "x": 10, "y": 0}','{"h": 9, "nom": null, "ocr_texte": "LE OTAGE", "ordre": 2, "parent_id": null, "planche_id": 26, "source": "manuel", "type": "bulle", "w": 9, "x": 10, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(217,NULL,'creation','nora','humain','document',19,NULL,'{"album_id": 26, "titre": "Carnet de Nora 2"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(218,NULL,'lien','nora','humain','collection_album',19,NULL,'{"album_id": 26, "collection": "Collection B", "collection_id": 6}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(219,NULL,'modification','nora','humain','document',19,NULL,'{"album_id": 26, "planche": {"id": 27, "numero": 1}}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(220,NULL,'creation','nora','humain','regions',44,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 27, "source": "manuel", "type": "bulle", "w": 9, "x": 0, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(221,NULL,'modification','nora','humain','regions',44,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 1, "parent_id": null, "planche_id": 27, "source": "manuel", "type": "bulle", "w": 9, "x": 0, "y": 0}','{"h": 9, "nom": null, "ocr_texte": "LE OTAGE", "ordre": 1, "parent_id": null, "planche_id": 27, "source": "manuel", "type": "bulle", "w": 9, "x": 0, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(222,NULL,'creation','lea','humain','regions',45,NULL,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": null, "planche_id": 27, "source": "manuel", "type": "bulle", "w": 9, "x": 10, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(223,NULL,'modification','lea','humain','regions',45,'{"h": 9, "nom": null, "ocr_texte": null, "ordre": 2, "parent_id": null, "planche_id": 27, "source": "manuel", "type": "bulle", "w": 9, "x": 10, "y": 0}','{"h": 9, "nom": null, "ocr_texte": "LE OTAGE", "ordre": 2, "parent_id": null, "planche_id": 27, "source": "manuel", "type": "bulle", "w": 9, "x": 10, "y": 0}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(224,NULL,'creation','nora','humain','demande',10,NULL,'{"album_id": 10, "document_id": 10, "genre": "suppression_document"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(225,NULL,'creation','nora','humain','demande',11,NULL,'{"album_id": 25, "document_id": 18, "genre": "suppression_document"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(226,NULL,'creation','nora','humain','demande',12,NULL,'{"album_id": 26, "cran": "images", "document_id": 19, "genre": "repartir"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(227,NULL,'creation','nora','humain','demande',13,NULL,'{"album_id": 26, "document_id": 19, "genre": "suppression_document"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(228,NULL,'modification','hugo','humain','demande',13,'{"reponse": null}','{"reponse": "refusee"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(229,NULL,'modification','hugo','humain','utilisateur_nature',NULL,'{"login": "atelier", "nature": "nominatif"}','{"login": "atelier", "nature": "collectif"}','2026-10-26 16:30:09');
INSERT INTO "evenement" VALUES(230,NULL,'lien','hugo','humain','projet_acces',2,NULL,'{"genre": "utilisateur", "principal": "atelier", "role": "responsable"}','2026-10-26 16:30:09');
CREATE TABLE geste_sur_copie (
    album_id   INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    agent      TEXT NOT NULL,
    PRIMARY KEY (album_id, agent)
);
INSERT INTO "geste_sur_copie" VALUES(1,'lea');
INSERT INTO "geste_sur_copie" VALUES(2,'sam');
INSERT INTO "geste_sur_copie" VALUES(3,'lea');
INSERT INTO "geste_sur_copie" VALUES(10,'lea');
INSERT INTO "geste_sur_copie" VALUES(21,'lea');
INSERT INTO "geste_sur_copie" VALUES(25,'nora');
INSERT INTO "geste_sur_copie" VALUES(25,'lea');
INSERT INTO "geste_sur_copie" VALUES(26,'nora');
INSERT INTO "geste_sur_copie" VALUES(26,'lea');
CREATE TABLE grille (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    projet_id      INTEGER NOT NULL REFERENCES projet(id),
    nom            TEXT NOT NULL,
    ouverte        INTEGER NOT NULL DEFAULT 0,
    retiree_le     TEXT,
    cree_par       TEXT,
    date_creation  TEXT DEFAULT (datetime('now'))
);
INSERT INTO "grille" VALUES(1,2,'Signaux',0,NULL,'lea','2026-10-26 16:30:09');
CREATE TABLE grille_entree (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id    INTEGER NOT NULL REFERENCES grille_version(id) ON DELETE CASCADE,
    cle           TEXT NOT NULL,
    rubrique_cle  TEXT,
    rang          INTEGER NOT NULL DEFAULT 0,
    forme         TEXT NOT NULL,
    libelle       TEXT NOT NULL,
    definition    TEXT,
    structure     TEXT,
    piege         TEXT,
    precision     TEXT,                       -- le libellé d'une précision libre, NULL sinon
    lien          INTEGER NOT NULL DEFAULT 0, -- 1 : l'entrée désigne une autre région
    cible         TEXT,                       -- NULL : celle de la version (« Porte sur »)
    cardinalite   TEXT,                       -- 'une' | 'plusieurs' ; NULL : le défaut (Q6)
    liste_cle     TEXT,                       -- la liste d'une entrée à qualificatifs
    retiree       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (version_id, cle)
);
INSERT INTO "grille_entree" VALUES(1,1,'cri','voix',0,'simple','cri','un cri poussé par un personnage, écrit en toutes lettres',NULL,'un cri n''est pas une onomatopée de choc : on le pose sur le cri, pas sur le bruit',NULL,0,NULL,NULL,NULL,0);
INSERT INTO "grille_entree" VALUES(2,1,'onomatopee','chocs',1,'variantes','onomatopée de choc','un mot qui imite le bruit d''un choc',NULL,NULL,NULL,0,NULL,NULL,NULL,0);
INSERT INTO "grille_entree" VALUES(3,1,'ton-de-voix','voix',2,'variantes','ton de voix','le ton de toute la zone, une fois par zone',NULL,NULL,NULL,0,'bulle|cartouche|texte','une',NULL,0);
INSERT INTO "grille_entree" VALUES(4,1,'origine-du-son','provenance',3,'qualificatifs','origine du son','d''où vient le son relevé',NULL,NULL,'lieu',0,NULL,NULL,'sources',0);
INSERT INTO "grille_entree" VALUES(5,1,'echo','provenance',4,'qualificatifs','écho','un son répété, plus faible',NULL,NULL,NULL,0,NULL,NULL,'sources',0);
INSERT INTO "grille_entree" VALUES(6,1,'intensite','graphisme',5,'qualificatifs','intensité graphique','comment le lettrage marque la force du son',NULL,NULL,NULL,0,NULL,NULL,'manieres',0);
INSERT INTO "grille_entree" VALUES(7,1,'geste-graphique','graphisme',6,'qualificatifs','geste graphique','un trait qui accompagne le son',NULL,NULL,NULL,0,NULL,NULL,'manieres',0);
INSERT INTO "grille_entree" VALUES(8,1,'reponse-a','echanges',7,'simple','réponse à une autre bulle','la zone répond à une autre, qu''on désigne',NULL,NULL,NULL,1,'bulle','plusieurs',NULL,0);
INSERT INTO "grille_entree" VALUES(9,1,'ambiance','echanges',8,'simple','ambiance sonore de la planche','le fond sonore de toute la planche',NULL,NULL,NULL,0,'planche',NULL,NULL,0);
INSERT INTO "grille_entree" VALUES(10,1,'regard-camera','image',9,'simple','regard caméra','le personnage regarde le lecteur',NULL,NULL,NULL,0,'case',NULL,NULL,0);
CREATE TABLE grille_exemple (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id    INTEGER NOT NULL REFERENCES grille_version(id) ON DELETE CASCADE,
    entree_cle    TEXT NOT NULL,
    variante_cle  TEXT,
    rang          INTEGER NOT NULL DEFAULT 0,
    texte         TEXT,
    releve_id     INTEGER
);
INSERT INTO "grille_exemple" VALUES(1,1,'cri',NULL,0,'AAAH !',NULL);
INSERT INTO "grille_exemple" VALUES(2,1,'cri',NULL,1,'OUILLE',NULL);
INSERT INTO "grille_exemple" VALUES(3,1,'onomatopee','bang',0,'BANG !',NULL);
INSERT INTO "grille_exemple" VALUES(4,1,'onomatopee','bang',1,'PAN !',NULL);
INSERT INTO "grille_exemple" VALUES(5,1,'onomatopee','crac',0,'CRAC',NULL);
INSERT INTO "grille_exemple" VALUES(6,1,'onomatopee','splash',0,'PLOUF',NULL);
INSERT INTO "grille_exemple" VALUES(7,1,'onomatopee','splash',1,'SPLASH',NULL);
INSERT INTO "grille_exemple" VALUES(8,1,'echo',NULL,0,'OH… OH… OH…',NULL);
CREATE TABLE grille_liste (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id  INTEGER NOT NULL REFERENCES grille_version(id) ON DELETE CASCADE,
    cle         TEXT NOT NULL,
    libelle     TEXT,
    UNIQUE (version_id, cle)
);
INSERT INTO "grille_liste" VALUES(1,1,'sources','source du son');
INSERT INTO "grille_liste" VALUES(2,1,'manieres','manière');
CREATE TABLE grille_qualificatif (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id  INTEGER NOT NULL REFERENCES grille_version(id) ON DELETE CASCADE,
    liste_cle   TEXT NOT NULL,
    cle         TEXT NOT NULL,
    libelle     TEXT NOT NULL,
    definition  TEXT,
    rang        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (version_id, liste_cle, cle)
);
INSERT INTO "grille_qualificatif" VALUES(1,1,'sources','personnage','personnage','un personnage de la case',0);
INSERT INTO "grille_qualificatif" VALUES(2,1,'sources','objet','objet','un objet de la case',1);
INSERT INTO "grille_qualificatif" VALUES(3,1,'sources','hors-champ','hors champ','une source qu''on ne voit pas',2);
INSERT INTO "grille_qualificatif" VALUES(4,1,'manieres','taille','taille','des lettres plus grandes',0);
INSERT INTO "grille_qualificatif" VALUES(5,1,'manieres','couleur','couleur','des lettres colorées',1);
INSERT INTO "grille_qualificatif" VALUES(6,1,'manieres','forme','forme des lettres','des lettres déformées',2);
CREATE TABLE grille_rubrique (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id  INTEGER NOT NULL REFERENCES grille_version(id) ON DELETE CASCADE,
    cle         TEXT NOT NULL,
    libelle     TEXT NOT NULL,
    parent_cle  TEXT,
    rang        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (version_id, cle)
);
INSERT INTO "grille_rubrique" VALUES(1,1,'sons','A. Sons',NULL,0);
INSERT INTO "grille_rubrique" VALUES(2,1,'voix','Voix','sons',1);
INSERT INTO "grille_rubrique" VALUES(3,1,'bruits','Bruits','sons',2);
INSERT INTO "grille_rubrique" VALUES(4,1,'chocs','Chocs','bruits',3);
INSERT INTO "grille_rubrique" VALUES(5,1,'provenance','B. Provenance',NULL,4);
INSERT INTO "grille_rubrique" VALUES(6,1,'graphisme','C. Graphisme',NULL,5);
INSERT INTO "grille_rubrique" VALUES(7,1,'echanges','D. Échanges',NULL,6);
INSERT INTO "grille_rubrique" VALUES(8,1,'image','E. Image',NULL,7);
CREATE TABLE grille_variante (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id  INTEGER NOT NULL REFERENCES grille_version(id) ON DELETE CASCADE,
    entree_cle  TEXT NOT NULL,
    cle         TEXT NOT NULL,
    libelle     TEXT NOT NULL,
    definition  TEXT,
    structure   TEXT,
    piege       TEXT,
    rang        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (version_id, entree_cle, cle)
);
INSERT INTO "grille_variante" VALUES(1,1,'onomatopee','bang','bang','un choc sec, une détonation',NULL,NULL,0);
INSERT INTO "grille_variante" VALUES(2,1,'onomatopee','crac','crac','une rupture, un craquement',NULL,NULL,1);
INSERT INTO "grille_variante" VALUES(3,1,'onomatopee','splash','splash','une chute dans un liquide','[liquide] + [chute]',NULL,2);
INSERT INTO "grille_variante" VALUES(4,1,'ton-de-voix','chuchote','chuchoté','écrit plus petit, ou dit à voix basse',NULL,NULL,0);
INSERT INTO "grille_variante" VALUES(5,1,'ton-de-voix','crie','crié','écrit en gros, ou dit à pleine voix',NULL,NULL,1);
CREATE TABLE grille_version (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    grille_id     INTEGER NOT NULL REFERENCES grille(id) ON DELETE CASCADE,
    numero        INTEGER NOT NULL,
    etat          TEXT NOT NULL,
    cible         TEXT,
    note          TEXT,
    empreinte     TEXT,
    importee_par  TEXT,
    importee_le   TEXT,
    publiee_par   TEXT,
    publiee_le    TEXT,
    UNIQUE (grille_id, numero)
);
INSERT INTO "grille_version" VALUES(1,1,1,'publiee','mots',NULL,'0f4b4676423449ee4a96bae2f53f55ef19e237eeed78cbae1cb43e6841ac3714','lea','2026-10-26 16:30:09','lea','2026-10-26 16:30:09');
CREATE TABLE jeu_document (
    document_id      INTEGER PRIMARY KEY,
    album_reference  INTEGER NOT NULL,
    cran             TEXT NOT NULL,
    role             TEXT NOT NULL,
    rang             INTEGER NOT NULL DEFAULT 0,
    cle              TEXT NOT NULL,
    empreinte        TEXT,
    part             TEXT NOT NULL,
    exportable       INTEGER NOT NULL DEFAULT 0,
    date_creation    TEXT DEFAULT (datetime('now'))
);
INSERT INTO "jeu_document" VALUES(12,14,'images','pas-a-pas',1,'parcours','1131d2d2796ee3cdc365f3b7146d71c4a482c29ab995038700b9d9f3cf2e33e3','depot',1,'2026-10-26 16:30:08');
INSERT INTO "jeu_document" VALUES(13,15,'transcription','exemple',0,'exemple','442e49efd99540dbd22e444f2560bb67000b69c2d69d426f378ee1d01cee86a8','depot',1,'2026-10-26 16:30:08');
CREATE TABLE meta (
    cle      TEXT PRIMARY KEY,
    valeur   TEXT
);
CREATE TABLE passe (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id     INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    planche_id    INTEGER REFERENCES planches(id),
    grille_id     INTEGER NOT NULL REFERENCES grille(id),
    version_id    INTEGER REFERENCES grille_version(id),
    rubrique_cle  TEXT NOT NULL DEFAULT '',
    par           TEXT,
    le            TEXT DEFAULT (datetime('now')),
    recopiee      INTEGER NOT NULL DEFAULT 0
    -- 1 si la passe est arrivée avec une copie amorcée (`copier_le_travail`), telle
    -- quelle : la règle de suppression la compte alors comme le travail de `par`, fait
    -- ailleurs (`autorisation._sources_du_travail`). Une marque EXPLICITE, comme celle des
    -- `COUCHES_RECOPIEES` (décision du pilotage du 2026-10-25 : une marque, jamais une
    -- date) : une passe RE-MARQUÉE — rouverte puis marquée — est une ligne neuve, à 0 ;
    -- la marquer quand elle l'est déjà ne change rien, comme valider une correction
    -- recopiée n'en fait pas l'auteur. Commentaire SOUS la dernière colonne (cf. celui de
    -- `collection.projet_id`).
);
INSERT INTO "passe" VALUES(1,32,NULL,1,1,'','lea','2026-10-26 16:30:09',0);
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
    date_creation  TEXT DEFAULT (datetime('now')),
    recopiee           INTEGER NOT NULL DEFAULT 0
    -- v36 (COL-3, tranche 3b) : 1 si la ligne est arrivée avec une copie amorcée
    -- (`copier_le_travail`), telle quelle ; cf. `COUCHES_RECOPIEES`.
);
INSERT INTO "personnage_presence" VALUES(3,2,'2026-10-26 16:30:07',0);
INSERT INTO "personnage_presence" VALUES(8,2,'2026-10-26 16:30:07',0);
INSERT INTO "personnage_presence" VALUES(13,2,'2026-10-26 16:30:07',0);
CREATE TABLE personnages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    serie          TEXT,
    notes          TEXT,
    date_creation  TEXT DEFAULT (datetime('now')),
    bac_a_sable_id INTEGER
    -- v35 (COL-4) — le BAC À SABLE où le personnage est NÉ (`projet.id`, qui ne revient
    -- jamais), NULL pour un personnage du registre. Un personnage né dans un bac à sable
    -- n'existe que pour ses membres, ne s'attribue que dans ce bac à sable, et part avec lui
    -- (Hugo, 2026-10-24) ; les apparitions dans un bac à sable ne comptent pas pour la
    -- visibilité d'un personnage du registre — ni pour le cacher, ni pour le montrer
    -- (`socle._clause_personnage`). Sans clé étrangère : le journal et les outils lisent
    -- encore l'identifiant d'un bac à sable effacé. Commentaire SOUS la dernière colonne
    -- (cf. celui de `collection.projet_id`).
);
INSERT INTO "personnages" VALUES(1,'Tintin',NULL,NULL,'2026-10-26 16:30:01',NULL);
INSERT INTO "personnages" VALUES(2,'Haddock',NULL,NULL,'2026-10-26 16:30:01',NULL);
CREATE TABLE planches (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id           INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    numero             INTEGER NOT NULL,             -- rang dans l'album (l'ordre d'import, puis UX-11) ; clé de tri, peut avoir des trous
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
INSERT INTO "planches" VALUES(1,1,1,'recit','corpus/album_1/planche_0001.jpg','derivatives/album_1/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,'2026-10-26 16:30:07',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(2,1,2,'recit','corpus/album_1/planche_0002.jpg','derivatives/album_1/planche_0002.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(3,2,1,'recit','corpus/album_2/planche_0001.jpg','derivatives/album_2/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,'2026-10-26 16:30:07',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(4,2,2,'recit','corpus/album_2/planche_0002.jpg','derivatives/album_2/planche_0002.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(5,3,1,'recit','corpus/album_3/planche_0001.jpg','derivatives/album_3/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,'2026-10-26 16:30:07',NULL,NULL,NULL);
INSERT INTO "planches" VALUES(6,3,2,'recit','corpus/album_3/planche_0002.jpg','derivatives/album_3/planche_0002.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(9,6,1,'recit','corpus/album_6/planche_0001.jpg','derivatives/album_6/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(11,10,1,'recit','corpus/album_10/planche_0001.jpg','derivatives/album_10/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(12,11,1,'recit','corpus/album_10/planche_0001.jpg','derivatives/album_10/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(13,13,1,'recit','corpus/album_10/planche_0001.jpg','derivatives/album_10/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(14,14,1,'recit','corpus/album_14/planche_0001.jpg','derivatives/album_14/planche_0001.jpg',40,50,NULL,NULL,'RGB','jeu:j1.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(15,15,1,'recit','corpus/album_15/planche_0001.jpg','derivatives/album_15/planche_0001.jpg',40,50,NULL,NULL,'RGB','jeu:j2.png','segmentee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(16,16,1,'recit','corpus/album_15/planche_0001.jpg','derivatives/album_15/planche_0001.jpg',40,50,NULL,NULL,'RGB','jeu:j2.png','segmentee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(17,17,1,'recit','corpus/album_14/planche_0001.jpg','derivatives/album_14/planche_0001.jpg',40,50,NULL,NULL,'RGB','jeu:j1.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(18,18,1,'recit','corpus/album_18/planche_0001.jpg','derivatives/album_18/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(19,19,1,'recit','corpus/album_15/planche_0001.jpg','derivatives/album_15/planche_0001.jpg',40,50,NULL,NULL,'RGB','jeu:j2.png','segmentee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(20,20,1,'recit','corpus/album_14/planche_0001.jpg','derivatives/album_14/planche_0001.jpg',40,50,NULL,NULL,'RGB','jeu:j1.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(21,21,1,'recit','corpus/album_21/planche_0001.jpg','derivatives/album_21/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(22,22,1,'recit','corpus/album_21/planche_0001.jpg','derivatives/album_21/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(23,23,1,'recit','corpus/album_23/planche_0001.jpg','derivatives/album_23/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(25,24,1,'recit','corpus/album_24/planche_0001.jpg','derivatives/album_24/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(26,25,1,'recit','corpus/album_25/planche_0001.jpg','derivatives/album_25/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
INSERT INTO "planches" VALUES(27,26,1,'recit','corpus/album_26/planche_0001.jpg','derivatives/album_26/planche_0001.jpg',40,50,NULL,NULL,'RGB','p.png','importee',NULL,NULL,NULL,NULL,NULL);
CREATE TABLE projet (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    description    TEXT,
    justification  TEXT,
    repli          INTEGER NOT NULL DEFAULT 0,     -- 1 = le projet de repli
    date_creation  TEXT DEFAULT (datetime('now')),
    bac_a_sable_de TEXT,
    efface_le      TEXT,
    jeu            INTEGER NOT NULL DEFAULT 0,
    membres_creent_collections INTEGER NOT NULL DEFAULT 0
    -- v36 (COL-3, tranche 3b ; Hugo, 2026-10-21) — `membres_creent_collections` : les
    -- MEMBRES du projet peuvent-ils y créer des collections ? NON par défaut, et pour tout
    -- l'existant ; les responsables et les administrateurs créent toujours
    -- (`autorisation.Portee.peut_creer_collection`). Un bac à sable ne le lit pas : ses
    -- invités y créent comme avant, son propriétaire en est responsable.
    -- v35 (COL-4) — deux natures de projet de plus, chacune un DRAPEAU comme `repli`.
    -- `bac_a_sable_de` : le LOGIN de qui l'a ouvert, NULL pour un projet ordinaire. Une
    -- colonne dit à la fois « c'est un bac à sable » et « de qui » ; la règle de lecture vit
    -- à UN endroit (`sql_est_bac_a_sable`). Un par login : tenu par la base (l'index
    -- partiel `idx_projet_bac_a_sable_de`, posé par `_migrate`) ET relu sous le verrou
    -- d'écriture par les routes. `efface_le` : le moment de son effacement (UTC, la forme des dates
    -- SQLite), posé à la naissance — celui qu'on affiche est celui qu'on applique.
    -- `jeu` = 1 désigne LE projet de jeu, caché : il porte les copies de RÉFÉRENCE dont
    -- chaque bac à sable prend les siennes (`jeu_document`). Personne n'en est membre.
    -- Commentaires SOUS la dernière colonne (cf. celui de `collection.projet_id`).
);
INSERT INTO "projet" VALUES(1,'Projet principal','Créé automatiquement : toute collection appartient à un projet. Renommez-le, et décrivez-le.',NULL,1,'2026-10-26 16:30:00',NULL,NULL,0,0);
INSERT INTO "projet" VALUES(2,'Étude B',NULL,NULL,0,'2026-10-26 16:30:08',NULL,NULL,0,1);
INSERT INTO "projet" VALUES(5,'Jeu des bacs à sable','Créé par l''outil du jeu : les copies de référence dont chaque bac à sable prend les siennes. Caché ; il ne se règle que par `tools/preparer_jeu.py`.',NULL,0,'2026-10-26 16:30:08',NULL,NULL,1,0);
INSERT INTO "projet" VALUES(6,'Bac à sable','Un bac à sable : on y apprend l''outil. Il s''efface chaque semaine.',NULL,0,'2026-10-26 16:30:08','lea','2026-11-02 03:00:00',0,0);
INSERT INTO "projet" VALUES(7,'Bac à sable','Un bac à sable : on y apprend l''outil. Il s''efface chaque semaine.',NULL,0,'2026-10-26 16:30:08','hugo','2026-11-02 03:00:00',0,0);
CREATE TABLE projet_acces (
    projet_id      INTEGER NOT NULL REFERENCES projet(id) ON DELETE CASCADE,
    genre          TEXT NOT NULL,       -- 'utilisateur' | 'groupe'
    principal      TEXT NOT NULL,       -- login, ou nom de groupe Remote-Groups
    role           TEXT NOT NULL,       -- 'membre' | 'responsable'
    date_creation  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (projet_id, genre, principal)
);
INSERT INTO "projet_acces" VALUES(1,'utilisateur','sam','membre','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(1,'utilisateur','rita','responsable','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(1,'groupe','chefs','responsable','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(2,'utilisateur','lea','responsable','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(2,'utilisateur','sam','membre','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(2,'groupe','etudiants','membre','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(6,'utilisateur','lea','responsable','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(6,'utilisateur','sam','membre','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(7,'utilisateur','hugo','responsable','2026-10-26 16:30:08');
INSERT INTO "projet_acces" VALUES(2,'utilisateur','atelier','responsable','2026-10-26 16:30:09');
CREATE TABLE projet_grille (
    projet_id   INTEGER NOT NULL REFERENCES projet(id) ON DELETE CASCADE,
    grille_id   INTEGER NOT NULL REFERENCES grille(id),
    version_id  INTEGER NOT NULL REFERENCES grille_version(id),
    active_par  TEXT,
    active_le   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (projet_id, grille_id)
);
INSERT INTO "projet_grille" VALUES(2,1,1,'lea','2026-10-26 16:30:09');
CREATE VIRTUAL TABLE recherche USING fts5(
    region_id UNINDEXED,
    ocr_texte,
    note,
    tags_concat,
    lemmes,
    tokenize = 'unicode61 remove_diacritics 2'
);
INSERT INTO "recherche" VALUES(5,'TINTIN ET LE OTAGE 0 1','','','tintin otage');
INSERT INTO "recherche" VALUES(7,'TINTIN ET LE OTAGE 1 0','vu','dialogue','tintin otage');
INSERT INTO "recherche" VALUES(10,'TINTIN ET LE OTAGE 1 1','','','tintin otage');
INSERT INTO "recherche" VALUES(12,'TINTIN ET LE OTAGE 2 0','vu','dialogue','tintin otage');
INSERT INTO "recherche" VALUES(15,'TINTIN ET LE OTAGE 2 1','','','tintin otage');
INSERT INTO "recherche" VALUES(2,'TINTIN ET LE OTAGE 0 0','vu','dialogue','tintin otage');
INSERT INTO "recherche" VALUES(22,'LE OTAGE SOEUR','source','dialogue','otage soeur source');
INSERT INTO "recherche" VALUES(24,'LE OTAGE SOEUR','','','otage soeur');
INSERT INTO "recherche" VALUES(26,'LE OTAGE','','','otage');
INSERT INTO "recherche" VALUES(28,'LE OTAGE','','','otage');
INSERT INTO "recherche" VALUES(30,'LE OTAGE','','','otage');
INSERT INTO "recherche" VALUES(33,'— C''EST L''HISTOIRE D''UN OTAGE...','','','histoire otage');
INSERT INTO "recherche" VALUES(34,'presqu''île, dis-moi : va-t-il por-
trait ?!','','','île di traire');
INSERT INTO "recherche" VALUES(32,'J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!','à relever','dialogue','savoir relever');
INSERT INTO "recherche" VALUES(37,'J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!','à relever','dialogue','savoir relever');
INSERT INTO "recherche" VALUES(38,'— C''EST L''HISTOIRE D''UN OTAGE...','','','histoire otage');
INSERT INTO "recherche" VALUES(39,'presqu''île, dis-moi : va-t-il por-
trait ?!','','','île di traire');
INSERT INTO "recherche" VALUES(42,'LE OTAGE','','','otage');
INSERT INTO "recherche" VALUES(43,'LE OTAGE','','','otage');
INSERT INTO "recherche" VALUES(44,'LE OTAGE','','','otage');
INSERT INTO "recherche" VALUES(45,'LE OTAGE','','','otage');
CREATE TABLE region_attribut (
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    valeur_id      INTEGER NOT NULL REFERENCES attribut_valeur(id) ON DELETE CASCADE,
    recopiee       INTEGER NOT NULL DEFAULT 0,  -- v36 : cf. `COUCHES_RECOPIEES`
    PRIMARY KEY (region_id, valeur_id)
);
INSERT INTO "region_attribut" VALUES(1,1,0);
INSERT INTO "region_attribut" VALUES(6,1,0);
INSERT INTO "region_attribut" VALUES(11,1,0);
CREATE TABLE region_origine (
    region_id         INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
    region_source_id  INTEGER NOT NULL
);
INSERT INTO "region_origine" VALUES(23,21);
INSERT INTO "region_origine" VALUES(24,22);
INSERT INTO "region_origine" VALUES(27,25);
INSERT INTO "region_origine" VALUES(28,26);
INSERT INTO "region_origine" VALUES(29,25);
INSERT INTO "region_origine" VALUES(30,26);
INSERT INTO "region_origine" VALUES(36,31);
INSERT INTO "region_origine" VALUES(37,32);
INSERT INTO "region_origine" VALUES(38,33);
INSERT INTO "region_origine" VALUES(39,34);
INSERT INTO "region_origine" VALUES(40,35);
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
    date_modification TEXT,                           -- horodatage de la dernière retouche humaine
    nom               TEXT
    -- v37 (ANN-7, tranche 1 ; G17, Hugo, 2026-10-25) : le NOM libre d'une zone de détail
    -- (« le téléphone », « l'affiche »), NULL pour tout autre type. Le type `detail` lui-même
    -- vient avec l'écran qui le trace (tranche 2) ; la colonne naît avec la migration de la
    -- tranche 1 pour qu'il n'en faille pas une seconde. Elle ne sort par aucun export :
    -- `_region_tree` et les outils de sortie nomment leurs champs un à un. Elle est en
    -- revanche PUBLIÉE par les routes de région de l'Atelier (leur `SELECT *`), et c'est une
    -- DÉCISION, pas un défaut (relecture croisée d'ANN-7, constat 5) : un champ de TRAVAIL
    -- interne, que l'écran de la tranche 2 lira et écrira, lisible de qui lit la région comme
    -- son texte. Ctrl+Z la rend avec la région (`journal._REGION_COLS`). Commentaire SOUS la
    -- dernière colonne (cf. celui de `collection.projet_id`).
);
INSERT INTO "regions" VALUES(1,1,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:01',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(2,1,1,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 0 0','manuel','2026-10-26 16:30:01',NULL,1,'2026-10-26 16:30:08',NULL);
INSERT INTO "regions" VALUES(3,1,1,'personnage',2,2,5,5,2,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(4,2,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(5,2,4,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 0 1','manuel','2026-10-26 16:30:07',NULL,1,'2026-10-26 16:30:07',NULL);
INSERT INTO "regions" VALUES(6,3,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(7,3,6,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 1 0','manuel','2026-10-26 16:30:07',NULL,1,'2026-10-26 16:30:07',NULL);
INSERT INTO "regions" VALUES(8,3,6,'personnage',2,2,5,5,2,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(9,4,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(10,4,9,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 1 1','manuel','2026-10-26 16:30:07',NULL,1,'2026-10-26 16:30:07',NULL);
INSERT INTO "regions" VALUES(11,5,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(12,5,11,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 2 0','manuel','2026-10-26 16:30:07',NULL,1,'2026-10-26 16:30:07',NULL);
INSERT INTO "regions" VALUES(13,5,11,'personnage',2,2,5,5,2,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(14,6,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:07',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(15,6,14,'bulle',1,1,9,9,1,'TINTIN ET LE OTAGE 2 1','manuel','2026-10-26 16:30:07',NULL,1,'2026-10-26 16:30:07',NULL);
INSERT INTO "regions" VALUES(21,11,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(22,11,21,'bulle',1,1,9,9,1,'LE OTAGE SOEUR','manuel','2026-10-26 16:30:08',NULL,1,'2026-10-26 16:30:08',NULL);
INSERT INTO "regions" VALUES(23,13,NULL,'case',0,0,30,20,1,NULL,'manuel','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(24,13,23,'bulle',1,1,9,9,1,'LE OTAGE SOEUR','manuel','2026-10-26 16:30:08',NULL,1,'2026-10-26 16:30:08',NULL);
INSERT INTO "regions" VALUES(25,15,NULL,'case',0,0,30,30,1,NULL,'jeu','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(26,15,25,'bulle',1,1,9,9,1,'LE OTAGE','jeu','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(27,16,NULL,'case',0,0,30,30,1,NULL,'jeu','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(28,16,27,'bulle',1,1,9,9,1,'LE OTAGE','jeu','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(29,19,NULL,'case',0,0,30,30,1,NULL,'jeu','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(30,19,29,'bulle',1,1,9,9,1,'LE OTAGE','jeu','2026-10-26 16:30:08',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(31,21,NULL,'case',0,0,30,30,1,NULL,'manuel','2026-10-26 16:30:09',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(32,21,31,'bulle',1,1,9,9,1,'J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(33,21,31,'cartouche',1,1,9,9,2,'— C''EST L''HISTOIRE D''UN OTAGE...','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(34,21,31,'texte',1,1,9,9,3,'presqu''île, dis-moi : va-t-il por-
trait ?!','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(35,21,31,'personnage',2,2,5,5,4,NULL,'manuel','2026-10-26 16:30:09',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(36,22,NULL,'case',0,0,30,30,1,NULL,'manuel','2026-10-26 16:30:09',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(37,22,36,'bulle',1,1,9,9,1,'J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(38,22,36,'cartouche',1,1,9,9,2,'— C''EST L''HISTOIRE D''UN OTAGE...','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(39,22,36,'texte',1,1,9,9,3,'presqu''île, dis-moi : va-t-il por-
trait ?!','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(40,22,36,'personnage',2,2,5,5,4,NULL,'manuel','2026-10-26 16:30:09',NULL,0,NULL,NULL);
INSERT INTO "regions" VALUES(42,26,NULL,'bulle',0,0,9,9,1,'LE OTAGE','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(43,26,NULL,'bulle',10,0,9,9,2,'LE OTAGE','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(44,27,NULL,'bulle',0,0,9,9,1,'LE OTAGE','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
INSERT INTO "regions" VALUES(45,27,NULL,'bulle',10,0,9,9,2,'LE OTAGE','manuel','2026-10-26 16:30:09',NULL,1,'2026-10-26 16:30:09',NULL);
CREATE TABLE releve (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id       INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    planche_id      INTEGER REFERENCES planches(id),
    grille_id       INTEGER NOT NULL REFERENCES grille(id),
    version_id      INTEGER NOT NULL REFERENCES grille_version(id),
    entree_cle      TEXT NOT NULL,
    variante_cle    TEXT,
    precision       TEXT,
    lien_region_id  INTEGER,
    lien_texte      TEXT,
    texte_ancre     TEXT,
    une             INTEGER NOT NULL DEFAULT 0,
    origine_id      INTEGER,
    auteur          TEXT,
    cree_le         TEXT DEFAULT (datetime('now')),
    modifie_par     TEXT,
    modifie_le      TEXT
);
INSERT INTO "releve" VALUES(1,32,NULL,1,1,'cri',NULL,NULL,NULL,NULL,'J''SAIS PAS… AUJOURD’HUI, PEUT-ÊTRE !!!',0,NULL,'lea','2026-10-26 16:30:09',NULL,NULL);
CREATE TABLE releve_mot (
    releve_id  INTEGER NOT NULL REFERENCES releve(id) ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    rang       INTEGER,
    forme      TEXT NOT NULL,
    PRIMARY KEY (releve_id, position)
);
INSERT INTO "releve_mot" VALUES(1,0,0,'J''');
CREATE TABLE releve_qualificatif (
    releve_id         INTEGER NOT NULL REFERENCES releve(id) ON DELETE CASCADE,
    qualificatif_cle  TEXT NOT NULL,
    PRIMARY KEY (releve_id, qualificatif_cle)
);
CREATE TABLE retrait_vu (
    evenement_id   INTEGER NOT NULL,
    login          TEXT NOT NULL,
    vu_le          TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (evenement_id, login)
);
CREATE TABLE tags (
    id             INTEGER PRIMARY KEY,
    label          TEXT NOT NULL,
    couleur        TEXT DEFAULT '#1a4a8a',
    description    TEXT,                          -- glose du tag = SKOS definition (A4 : déjà là)
    -- Lexique situé (v17, A4) — couche définitionnelle SKOS partagée avec le vocabulaire
    -- facetté. `note_portee` = SKOS scopeNote (le « situé ») ; `etat` = maturité
    -- provisoire→défini (miroir auto→validé) ; `collection_id` = portée d'appartenance
    -- (NULL = global, sinon local à une collection ; promotion → NULL, patron mentions→entités).
    note_portee    TEXT,
    etat           TEXT NOT NULL DEFAULT 'provisoire',   -- 'provisoire' | 'defini'
    collection_id  INTEGER REFERENCES collection(id) ON DELETE SET NULL,
    date_creation  TEXT DEFAULT (datetime('now')),
    espace         INTEGER NOT NULL DEFAULT 0
    -- v35 (COL-4) — l'ESPACE de libellés du tag : 0 pour l'instance, l'identifiant du BAC À
    -- SABLE (`projet.id`, qui ne revient jamais) pour un tag né dans l'un d'eux. Le libellé
    -- est UNIQUE PAR ESPACE (`idx_tags_espace_label`, posé par `_migrate`), et non plus dans
    -- toute l'instance (Hugo, 2026-10-24) : un libellé tapé dans un bac à sable ne bloque
    -- rien ailleurs, le vrai corpus peut avoir le même, et rien ne se voit d'un côté à
    -- l'autre. Un tag d'un bac à sable y est toujours LOCAL (`collection_id`, une de ses
    -- collections) ; l'espace se lit par `espace_d_album`. Commentaire SOUS la dernière
    -- colonne (cf. celui de `collection.projet_id`).
);
INSERT INTO "tags" VALUES(1,'dialogue','#1a4a8a',NULL,NULL,'provisoire',NULL,'2026-10-26 16:30:07',0);
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
    -- v36 (COL-3, tranche 3b) : 1 si la correction est arrivée avec une copie amorcée
    -- (`copier_le_travail`), et n'a été corrigée par personne depuis. Survit à la
    -- validation et au ré-ancrage ; cf. `COUCHES_RECOPIEES`.
    recopiee    INTEGER NOT NULL DEFAULT 0,
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
INSERT INTO "tokens" VALUES(7,5,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(8,5,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(9,5,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(10,5,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(11,5,4,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(12,5,5,'1','1','DET','');
INSERT INTO "tokens" VALUES(13,7,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(14,7,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(15,7,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(16,7,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(17,7,4,'1','1','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(18,7,5,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(19,10,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(20,10,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(21,10,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(22,10,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(23,10,4,'1','1','DET','');
INSERT INTO "tokens" VALUES(24,10,5,'1','1','DET','');
INSERT INTO "tokens" VALUES(25,12,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(26,12,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(27,12,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(28,12,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(29,12,4,'2','2','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(30,12,5,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(31,15,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(32,15,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(33,15,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(34,15,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(35,15,4,'2','2','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(36,15,5,'1','1','DET','');
INSERT INTO "tokens" VALUES(49,2,0,'tintin','tintin','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(50,2,1,'et','et','CCONJ','');
INSERT INTO "tokens" VALUES(51,2,2,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(52,2,3,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(53,2,4,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(54,2,5,'0','0','NUM','NumType=Card');
INSERT INTO "tokens" VALUES(55,22,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(56,22,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(57,22,2,'soeur','soeur','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(58,24,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(59,24,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(60,24,2,'soeur','soeur','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(61,26,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(62,26,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(63,28,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(64,28,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(65,30,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(66,30,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(72,33,1,'c''','ce','PRON','Number=Sing|Person=3');
INSERT INTO "tokens" VALUES(73,33,2,'est','être','AUX','Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin');
INSERT INTO "tokens" VALUES(74,33,3,'l''','le','DET','Definite=Def|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(75,33,4,'histoire','histoire','NOUN','Gender=Fem|Number=Sing');
INSERT INTO "tokens" VALUES(76,33,5,'d''','de','ADP','');
INSERT INTO "tokens" VALUES(77,33,6,'un','un','DET','Definite=Ind|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(78,33,7,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(79,34,0,'presqu''','presque','ADP','');
INSERT INTO "tokens" VALUES(80,34,1,'île','île','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(81,34,3,'dis','di','NOUN','');
INSERT INTO "tokens" VALUES(82,34,4,'-moi','moi','PRON','Number=Sing|Person=1');
INSERT INTO "tokens" VALUES(83,34,6,'va','aller','VERB','Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin');
INSERT INTO "tokens" VALUES(84,34,7,'-t','-t','PRON','Gender=Masc|Number=Sing|Person=3');
INSERT INTO "tokens" VALUES(85,34,8,'-il','il','PRON','Gender=Masc|Number=Sing|Person=3');
INSERT INTO "tokens" VALUES(86,34,9,'por-','por-','ADJ','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(87,34,11,'trait','traire','VERB','Mood=Ind|Number=Sing|Person=3|Tense=Imp|VerbForm=Fin');
INSERT INTO "tokens" VALUES(88,32,0,'j''','je','PRON','Number=Sing|Person=1');
INSERT INTO "tokens" VALUES(89,32,1,'sais','savoir','VERB','Mood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin');
INSERT INTO "tokens" VALUES(90,32,2,'pas','pas','ADV','Polarity=Neg');
INSERT INTO "tokens" VALUES(91,32,4,'aujourd’hui','aujourd’hui','ADV','');
INSERT INTO "tokens" VALUES(92,32,6,'peut-être','peut-être','ADV','');
INSERT INTO "tokens" VALUES(93,37,0,'j''','je','PRON','Number=Sing|Person=1');
INSERT INTO "tokens" VALUES(94,37,1,'sais','savoir','VERB','Mood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin');
INSERT INTO "tokens" VALUES(95,37,2,'pas','pas','ADV','Polarity=Neg');
INSERT INTO "tokens" VALUES(96,37,4,'aujourd’hui','aujourd’hui','ADV','');
INSERT INTO "tokens" VALUES(97,37,6,'peut-être','peut-être','ADV','');
INSERT INTO "tokens" VALUES(98,38,1,'c''','ce','PRON','Number=Sing|Person=3');
INSERT INTO "tokens" VALUES(99,38,2,'est','être','AUX','Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin');
INSERT INTO "tokens" VALUES(100,38,3,'l''','le','DET','Definite=Def|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(101,38,4,'histoire','histoire','NOUN','Gender=Fem|Number=Sing');
INSERT INTO "tokens" VALUES(102,38,5,'d''','de','ADP','');
INSERT INTO "tokens" VALUES(103,38,6,'un','un','DET','Definite=Ind|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(104,38,7,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(105,39,0,'presqu''','presque','ADP','');
INSERT INTO "tokens" VALUES(106,39,1,'île','île','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(107,39,3,'dis','di','NOUN','');
INSERT INTO "tokens" VALUES(108,39,4,'-moi','moi','PRON','Number=Sing|Person=1');
INSERT INTO "tokens" VALUES(109,39,6,'va','aller','VERB','Mood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin');
INSERT INTO "tokens" VALUES(110,39,7,'-t','-t','PRON','Gender=Masc|Number=Sing|Person=3');
INSERT INTO "tokens" VALUES(111,39,8,'-il','il','PRON','Gender=Masc|Number=Sing|Person=3');
INSERT INTO "tokens" VALUES(112,39,9,'por-','por-','ADJ','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(113,39,11,'trait','traire','VERB','Mood=Ind|Number=Sing|Person=3|Tense=Imp|VerbForm=Fin');
INSERT INTO "tokens" VALUES(114,42,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(115,42,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(116,43,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(117,43,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(118,44,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(119,44,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
INSERT INTO "tokens" VALUES(120,45,0,'le','le','DET','Definite=Def|Gender=Masc|Number=Sing|PronType=Art');
INSERT INTO "tokens" VALUES(121,45,1,'otage','otage','NOUN','Gender=Masc|Number=Sing');
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
INSERT INTO "utilisateur" VALUES('hugo','Hugo',NULL,'2026-10-26 16:30:00','2026-10-26 16:30:00','nominatif');
INSERT INTO "utilisateur" VALUES('lea','Lea',NULL,'2026-10-26 16:30:01','2026-10-26 16:30:01','nominatif');
INSERT INTO "utilisateur" VALUES('sam','Sam',NULL,'2026-10-26 16:30:01','2026-10-26 16:30:01','nominatif');
INSERT INTO "utilisateur" VALUES('nora','Nora',NULL,'2026-10-26 16:30:09','2026-10-26 16:30:09','nominatif');
INSERT INTO "utilisateur" VALUES('omar',NULL,NULL,'2026-10-26 16:30:09','2026-10-26 16:30:09','nominatif');
INSERT INTO "utilisateur" VALUES('atelier',NULL,NULL,'2026-10-26 16:30:09','2026-10-26 16:30:09','collectif');
CREATE INDEX idx_projet_acces_principal ON projet_acces(genre, principal);
CREATE INDEX idx_region_origine_source ON region_origine(region_source_id);
CREATE INDEX idx_grille_projet ON grille(projet_id);
CREATE INDEX idx_projet_grille_grille ON projet_grille(grille_id);
CREATE INDEX idx_releve_region ON releve(region_id);
CREATE INDEX idx_releve_planche ON releve(planche_id);
CREATE INDEX idx_releve_grille ON releve(grille_id);
CREATE INDEX idx_releve_lien ON releve(lien_region_id);
CREATE UNIQUE INDEX idx_releve_une
    ON releve(COALESCE(region_id, 0), COALESCE(planche_id, 0), grille_id, entree_cle)
    WHERE une = 1;
CREATE INDEX idx_doute_releve ON doute(releve_id);
CREATE UNIQUE INDEX idx_doute_ouvert ON doute(releve_id) WHERE leve_le IS NULL;
CREATE INDEX idx_doute_message_doute ON doute_message(doute_id);
CREATE INDEX idx_passe_region ON passe(region_id);
CREATE INDEX idx_passe_planche ON passe(planche_id);
CREATE UNIQUE INDEX idx_passe_zone
    ON passe(COALESCE(region_id, 0), COALESCE(planche_id, 0), grille_id, rubrique_cle);
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
CREATE VIEW releves_effectifs AS
SELECT x.*,
       CASE WHEN x.mot_perdu OR x.texte_change OR x.lien_perdu OR x.type_change
                 OR x.entree_absente THEN 'a_revoir'
            WHEN x.precision_manquante OR x.lien_manquant THEN 'a_completer'
            ELSE 'normal' END AS etat
FROM (
  SELECT r.*,
         COALESCE(e.cible, v.cible) AS cible_effective,
         EXISTS (SELECT 1 FROM releve_mot m WHERE m.releve_id = r.id AND m.rang IS NULL)
             AS mot_perdu,
         (r.texte_ancre IS NOT NULL AND r.texte_ancre IS NOT COALESCE(g.ocr_texte, ''))
             AS texte_change,
         (r.lien_region_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM regions l WHERE l.id = r.lien_region_id)) AS lien_perdu,
         (r.region_id IS NOT NULL AND e.cle IS NOT NULL AND NOT (
              CASE WHEN COALESCE(e.cible, v.cible) = 'mots'
                        THEN g.type IN ('bulle', 'cartouche', 'texte')
                   WHEN COALESCE(e.cible, v.cible) IN ('planche', 'entite') THEN 0
                   ELSE instr('|' || COALESCE(e.cible, v.cible) || '|',
                              '|' || g.type || '|') > 0 END)) AS type_change,
         (e.cle IS NULL) AS entree_absente,
         (e.precision IS NOT NULL AND TRIM(COALESCE(r.precision, '')) = '')
             AS precision_manquante,
         (e.lien = 1 AND r.lien_region_id IS NULL) AS lien_manquant
  FROM releve r
  JOIN grille_version v ON v.id = r.version_id
  LEFT JOIN grille_entree e ON e.version_id = r.version_id AND e.cle = r.entree_cle
  LEFT JOIN regions g ON g.id = r.region_id
) x;
CREATE UNIQUE INDEX idx_planches_album_numero ON planches(album_id, numero);
CREATE INDEX idx_regions_activite ON regions(activite_id);
CREATE INDEX idx_dim_collection ON attribut_dimension(collection_id);
CREATE INDEX idx_val_collection ON attribut_valeur(collection_id);
CREATE INDEX idx_tags_collection ON tags(collection_id);
CREATE INDEX idx_dim_domaine ON attribut_dimension(domaine_id);
CREATE INDEX idx_collection_projet ON collection(projet_id);
CREATE INDEX idx_albums_document ON albums(document_id);
CREATE INDEX idx_albums_projet ON albums(projet_id);
CREATE UNIQUE INDEX idx_projet_bac_a_sable_de ON projet(bac_a_sable_de) WHERE bac_a_sable_de IS NOT NULL;
CREATE UNIQUE INDEX idx_tags_espace_label ON tags(espace, label);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('projet',7);
INSERT INTO "sqlite_sequence" VALUES('collection',17);
INSERT INTO "sqlite_sequence" VALUES('personnages',3);
INSERT INTO "sqlite_sequence" VALUES('albums',26);
INSERT INTO "sqlite_sequence" VALUES('document',19);
INSERT INTO "sqlite_sequence" VALUES('planches',27);
INSERT INTO "sqlite_sequence" VALUES('regions',45);
INSERT INTO "sqlite_sequence" VALUES('demande',13);
INSERT INTO "sqlite_sequence" VALUES('grille',1);
INSERT INTO "sqlite_sequence" VALUES('grille_version',1);
INSERT INTO "sqlite_sequence" VALUES('grille_rubrique',8);
INSERT INTO "sqlite_sequence" VALUES('grille_entree',10);
INSERT INTO "sqlite_sequence" VALUES('grille_exemple',8);
INSERT INTO "sqlite_sequence" VALUES('grille_variante',5);
INSERT INTO "sqlite_sequence" VALUES('grille_liste',2);
INSERT INTO "sqlite_sequence" VALUES('grille_qualificatif',6);
INSERT INTO "sqlite_sequence" VALUES('releve',1);
INSERT INTO "sqlite_sequence" VALUES('passe',1);
INSERT INTO "sqlite_sequence" VALUES('doute',1);
INSERT INTO "sqlite_sequence" VALUES('doute_message',1);
COMMIT;
PRAGMA user_version = 37;
