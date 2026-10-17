# COL-3, tranche 3 — prendre un document : cadrage

Rendu le 2026-10-16 par un agent en lecture seule, sur `dev` à `578ce99` (`main` à `5e7f56b`,
schéma 30 en production). Rien n'est codé ni exécuté. Ce qui est marqué **lu** a été lu dans le
code à ce commit ; ce qui est marqué **supposé** ne l'a pas été, ou reste à mesurer. Les
décisions qu'il suppose sont numérotées D1 à D12 plus bas ; chacune cite la case de
`pilotage/COL-3.md` qu'elle ferme au lieu d'en ouvrir une parallèle.

> **Toutes les décisions sont tranchées par Hugo le 2026-10-17.** D1 à D9, D11 et D12 retiennent
> la proposition écrite plus bas (D12 laissée par Hugo à la session de pilotage, qui a retenu la
> proposition ; D4 sous sa forme stricte). **D10 est tranchée CONTRE la proposition d'abord
> écrite** : un projet naît avec sa collection de base — la section D10 dit ce qui est retenu,
> et ce qu'elle change aux gestes 4 et 9, à la v31, aux règles et au découpage. Le commit « 0 —
> les albums du projet courant » est sur `dev` (`2d80473`).

---

## Ce que la tranche livre, en gestes

La fiche porte quatre cases « Tranche 3 » et trois cases du fonds qui en dépendent. Toutes ne
se valent pas en coût : prendre une copie VIERGE ou rejoindre un travail est un rangement de
plus ; EN PARTIR jusqu'à un cran est une copie profonde de huit tables, avec le vocabulaire et
le journal derrière elle. D'où la proposition D1 : deux temps, **3a** puis **3b**.

### 3a — prendre, rejoindre, et les albums du projet

1. **La Bibliothèque et l'Atelier ne montrent que les albums du projet courant** (case
   « Tranche 3 — les albums que montrent la Bibliothèque et l'Atelier… »). Dans un projet neuf,
   Esther v1 ne s'affiche plus. Le lot, qui part d'une sélection de la Bibliothèque, suit. Un
   lien de l'Atelier vers un album d'un autre projet fait basculer le projet courant, comme
   `/corpus?collection=…` le fait déjà.
2. **Un responsable de projet parcourt le fonds par ses NOTICES** — titre, série, auteur —, sans
   images, sans travail, sans savoir qui les emploie (case « La consultation du fonds est
   tranchée contre le cloisonnement », confirmée le 2026-10-09). Il cherche, coche plusieurs
   documents et les demande pour UNE collection de son projet : la demande part en une fois
   (case « Une entrée de documents porte PLUSIEURS albums à la fois »).
3. **L'administrateur répond document par document**, ou « tout accepter » ; une demande peut
   finir acceptée en partie, et le dit à qui l'a déposée (case « Comment l'administrateur répond
   à une demande de plusieurs documents »). Chaque document accepté entre dans la collection
   demandée avec une copie de travail VIERGE — « partir de zéro », la seule des trois réponses
   qui ne suppose le travail de personne.
4. **L'administrateur prend un document du fonds pour une collection**, directement, depuis la
   fiche du document (« Prendre dans… » de la maquette, qui nomme un PROJET : la copie entre
   alors dans sa collection de base, ou dans une collection qu'on nomme — D10 ; écrit d'abord
   « il faut nommer une collection », avant que Hugo tranche D10).
5. **Dans un projet, une collection prend un document que le projet a déjà** : *partir de zéro*
   (une seconde copie vierge, sans rien demander à personne), ou *rejoindre* le travail d'une
   collection du projet — c'est le « + Ranger ici » d'aujourd'hui, qui devient un geste
   CONSENTI (case « Rejoindre un travail demande l'accord de qui le tient », confirmée le
   2026-10-09). Immédiat quand on tient soi-même le travail, sinon une demande au propriétaire
   (D4).
6. **Reprendre une copie gardée au fonds** de son projet se demande depuis la même liste — ferme
   la case « Une copie sortie de sa dernière collection se reprend, ou se signale ».
7. **« Supprimer définitivement » ne détruit plus que SA copie** quand le document a une sœur ;
   les images restent tant qu'une copie les emploie, le document part avec sa dernière copie
   (D5).
8. **Le projet d'origine d'un document garde son nom** (case « Le projet d'ORIGINE d'un document
   ne garde pas son nom ») — nécessaire dès qu'une copie vit hors de son projet d'origine.
9. **Tout projet naît avec sa collection de base** (D10) : ce qu'il prend au fonds y arrive, ce
   qu'on importe la présélectionne, et ses membres y entrent selon ce que le projet a choisi —
   écriture, lecture, ou rien.

### 3b — l'échelle des couches

9. **En partir** : une copie à soi, amorcée avec le travail d'une autre copie jusqu'au cran
   choisi — images seules · + découpage · + transcription · + grammaire relue · + annotations
   (case « Les couches s'empilent, donc se choisissent sur une ÉCHELLE »). Dans le projet comme
   entre deux ; entre deux, avec l'accord du RESPONSABLE du projet d'où l'on part (case « Qui
   autorise qu'on amorce depuis son travail », confirmée le 2026-10-09). La copie dit d'où elle
   vient et jusqu'à quel cran, et le journal attribue toujours le travail copié à ceux qui l'ont
   fait (case « Ce qu'une copie garde de sa provenance »).
10. **Repartir de zéro sur un album** (case « Tranche 3 — repartir de zéro ») : revenir à un cran
    de l'échelle en gardant les images ; directement si personne d'autre n'y a travaillé, sinon
    une demande certifiée, comme supprimer.
11. **Le vocabulaire qui ne suit pas une copie est dit** (case « Le vocabulaire ne suit pas une
    copie »).

### Ce que la tranche ne livre PAS

- **La Recherche et l'Exploration ne sont pas bornées au projet, et ne dédoublonnent pas deux
  copies sœurs** : c'est la tranche 4 (case « Tranche 4 — ce qui parasite encore »). D'ici là,
  qui lit deux copies du même document compte son texte deux fois — l'administrateur, toujours.
  À écrire dans le guide (D12).
- **Le vocabulaire et les personnages n'ont pas d'étage de projet** (tranche 4).
- **La demande venue de l'extérieur** (compte + projet justifiés) : `AUTH-13`, différé. Son
  mécanisme de demande est celui que la 3a étend ; le dire chez lui en fermant la 3a.
- **« Ce qui ne peut PAS entrer dans un projet »** (refus par document ou par projet) : reste
  ouvert ; la proposition D2 ne lui donne pas d'état (c'est ce qu'elle coûte).
- **Le catalogue des grilles d'`ANN-7`** : la case « Le fonds et le catalogue des grilles suivent
  les mêmes règles » demande que les deux se comportent pareil ; la 3a pose le patron
  (notices lues par les responsables, demande groupée, réponse par élément), `ANN-7` s'y
  alignera. Rien n'est construit pour lui ici.
- **Une notice remontée au document** : écartée en tranche 2 (« trente sites de requêtes dans
  onze fichiers ») et proposée écartée encore (D7).

---

## Le modèle

### Ce qui reste vrai de la tranche 2 (lu)

- La ligne `albums` est la COPIE DE TRAVAIL ; tout son travail y pend par `planches`
  (`database.py`, tête de `SCHEMA_SQL`). Une copie a UN document (`albums.document_id`) et UN
  projet (`albums.projet_id`, lu par `sql_projet_d_album`).
- **Le rangement ne traverse pas les projets** (`database.rangement_traverse`, deux moitiés,
  route et outil). Une copie gardée au fonds emporte son projet (`poser_projet_de_copie`). Rien
  de la tranche 3 ne touche cette règle : « prendre entre deux projets » crée une copie NEUVE
  dans le projet d'arrivée, il ne déplace jamais une copie.
- Le fonds et les demandes restent à la portée totale (`Portee.peut_tenir_le_fonds`), à une
  exception près, voulue : la NOTICE, lue par les responsables.
- `document`, `albums`, `planches`, `regions`, `personnages`, `demande` portent `AUTOINCREMENT`
  depuis la v30 — et c'est ce qui rend sûre une pièce maîtresse de la 3a : un dossier
  `album_<id>` peut survivre à sa copie détruite (parce qu'une sœur emploie ses fichiers) sans
  qu'un album neuf ne vienne jamais le reprendre.

### Ce que la tranche 2 avait écrit pour UNE copie, et qui casse à deux (lu)

C'est la partie du cadrage qui compte le plus : ces sites marchent aujourd'hui parce qu'un
document n'a qu'une copie, et ils se tromperaient en silence à la première sœur.

| Site | Ce qu'il fait aujourd'hui | Ce qui se passe avec une sœur |
|---|---|---|
| `routes/fonds.repondre_demande` | accepter une suppression de document détruit TOUTES les copies du document (`SELECT a.id FROM albums a JOIN demande_document dd ON dd.document_id = a.document_id`) | la demande d'un membre du projet P1 détruirait, acceptée, la copie de P2 et tout son travail |
| `routes/fonds._en_attente`, `main.list_albums` (clé `demande`) | la demande en attente se cherche PAR DOCUMENT | la copie de P2 afficherait « suppression demandée » pour un geste fait dans P1 : une fuite entre projets, et un faux |
| `autorisation._sources_du_travail`, 5ᵉ source | les actes sous la cible `document` (`cible_id = document_id`) comptent comme travail sur l'album | une notice modifiée sur la copie A interdirait à la créatrice de la copie B de la supprimer seule — l'album est dans la charge (`apres.album_id`), il faut filtrer dessus |
| `Portee.clause_suppression_directe` | « l'avoir importé » = `document.importe_par` | personne d'autre que l'importatrice d'origine ne supprimerait jamais seul une copie qu'il a lui-même créée |
| `socle._detruire_album` | `remove_album_files(album_id)` efface `corpus/album_<id>` et `derivatives/album_<id>` | si les planches de la sœur pointent dans ces dossiers (D6), ses images partent |
| `main.delete_planche` | `remove_planche_files(chemin_tiff, chemin_web)` | même chose, planche par planche |
| `routes/fonds._vues_demandes` (`copie`) | la copie d'une demande = le plus petit album du document | désigne une copie au hasard ; `demande_document.album_id` porte déjà la bonne |
| `database.document_d_album` / `creer_document` | un document naît avec sa seule copie | il faut une seconde voie : une copie qui naît d'un document EXISTANT |

`retirer_document_sans_copie` est déjà écrit pour deux copies (lu : « La condition est écrite
quand même »), et la docstring de `clause_suppression_directe` l'annonçait (« Le jour où deux
copies seront sœurs, il faudra l'écrire ici »).

### Une seconde copie : ce qu'elle est (proposé)

Une nouvelle ligne `albums` pour le même `document_id`, dans le projet de la collection qui la
prend, rangée dans cette collection. Elle reçoit :

- **la notice de sa source** (colonnes descriptives d'`albums`, et ses lignes `contribution`) —
  recopiée, puis libre de diverger (D7) ;
- **ses planches** : une ligne `planches` par planche de la copie source, mêmes `numero`,
  `role`, `chemin_tiff`, `chemin_web`, dimensions, `dpi_*`, `mode` ; `statut = 'importee'`,
  `validee`, `verrouillee`, `verrou_par`, `relecture` à NULL. Les FICHIERS sont partagés (D6) ;
- en 3a rien d'autre ; en 3b, le travail jusqu'au cran.

La route qui sert les images s'en accommode sans changement (lu : `main.derivative` cherche une
planche LISIBLE dont `chemin_web` vaut le chemin demandé ; deux planches de deux copies au
même chemin passent si l'une des deux est lisible). Ce qu'elle laisse voir : l'adresse d'une
image d'une copie de P2 porte l'identifiant de la copie de P1 (`/derivatives/album_12/…`). Un
identifiant, pas un contenu — à accepter par écrit.

**Plusieurs copies dans le même projet sont permises.** C'est la forme confirmée le 2026-10-09
(les trois réponses valent « dans le projet comme entre deux ») et ce que dit la case « Deux
copies du même document se savent sœurs ». La tranche 2 n'avait aucune contrainte « une par
projet » ; la 3a n'en ajoute pas.

### La migration v31 (proposée)

Une seule migration pour les deux temps, si D1 est retenue ET que le schéma de la 3b est arrêté
avant le premier commit — sinon la 3b paiera une v32 (la leçon de la tranche 2 : deux tables
de demande figées avant que leurs routes n'existent, un regret trouvé le jour même). Proposition :
**v31 pour la 3a seule**, la 3b ajoute sa table quand elle arrive. Contenu :

1. **`copie`** — la provenance de chaque copie de travail, hors d'`albums` :
   `album_id INTEGER PRIMARY KEY REFERENCES albums(id) ON DELETE CASCADE`, `creee_par TEXT`
   (login), `creee_le TEXT`, `depuis_album_id INTEGER` (sans clé : la source peut mourir),
   `cran TEXT` (`origine` | `images` | en 3b les crans suivants), `depuis_projet_nom TEXT`.
   Hors d'`albums` et pas par confort : trois réponses de l'API rendent `a.*` (lu : `list_albums`,
   `create_album`, `update_album`), et le cadrage de la tranche 2 l'avait mesuré — un login posé
   sur `albums` partirait à toute lectrice. La migration écrit une ligne par album existant :
   `cran = 'origine'`, `creee_par = document.importe_par` (NULL pour tout l'existant d'avant la
   v30, qui reste « inconnu veut dire demander », décision B3), `creee_le = document.importe_le`.
   C'est désormais elle que lit la règle de suppression directe (« a créé CETTE copie »).
   À classer : `copie` dans `CIBLES_RETENUES` si le journal la vise, son login dans les deux
   cliquets de sortie (`test_sorties_identite`, colonnes classées). **Supposé** : aucune route ne
   la lit en entier ; à garder ainsi.
2. **`document.projet_origine_nom TEXT`** — le nom du projet d'origine, écrit à l'import. La
   migration le remplit avec le nom ACTUEL du projet (une photographie du jour de migration,
   pas le nom à l'import — à écrire sur la colonne) ; NULL si le projet n'existe plus, ce que le
   code v30 ne sait pas produire (un projet que des copies désignent ne se supprime pas, et
   aucune copie ne quitte son projet) mais qu'une base retouchée peut porter. Le fonds cesse de
   joindre `projet` par `projet_origine_id` pour dire l'origine (lu : `lire_le_fonds` fait
   `LEFT JOIN projet p ON p.id = d.projet_origine_id`, qui nommerait un autre projet après
   réattribution).
3. **`demande.collection_id`, `demande.collection_nom`** — la collection d'ARRIVÉE d'une entrée
   de documents ou d'un « rejoindre » ; le nom pour la raison de `demande.projet_nom` (les
   identifiants de collection se réattribuent, mesuré en tranche 2).
4. **`demande_document.copie_id INTEGER`** — la copie NÉE de l'acceptation (sans clé), pour
   qu'une demande répondue dise où le document est entré. `demande_document.reponse` existe déjà
   (lu) et porte la réponse document par document. Pas de `CHECK` sur les genres, pour la raison
   écrite sur la table : `GENRES_DEMANDE` gagne `entree_documents` et `rejoindre` dans le code.
5. **`AUTOINCREMENT` sur `projet`** (D8), par `_reconstruire_avec_autoincrement` — la machinerie
   de la v30 (clés suspendues, compteur amorcé sur ce que le journal a jamais nommé). Pour
   `projet` : `evenement` sous `projet`, `projet_acces`, plus `demande.projet_id` et
   `document.projet_origine_id`. **Lu** : la fonction parcourt `_AUTOINCREMENT`, une entrée par
   table avec les cibles du journal qui la désignent, et amorce par `_jamais_nommes`. **Non lu** :
   comment y faire entrer des sources hors journal (`demande.projet_id`,
   `document.projet_origine_id`) ; à lire avant de chiffrer.

La migration est gardée par la version et idempotente (le patron de la v30 : des tests ramènent
`user_version` en arrière sur une base courante).

**Comment elle se vérifie** (règle de Hugo du 2026-10-16, `CLAUDE.md` § Schéma & migrations).
Une vraie base v30, fabriquée par `tools/fabriquer_base_de_version.py <tête de main avant la
v31> tests/bases/v30-<sha>.sql`. L'outil ne connaît que le parcours v29 (lu : collections,
albums, régions, destructions en haut de table) ; il gagne une branche sur
`SCHEMA_VERSION >= 30` qui pose ce que la v31 doit traverser : un second projet et sa
collection ; une copie gardée au fonds (sortie de sa dernière collection) ; un album importé
au fonds par l'administrateur puis rendu ; un album importé par un compte nommé (pour que
`importe_par` ne soit pas NULL partout) ; une demande de suppression en attente, une refusée,
une acceptée ; une demande de suppression de projet ; un projet supprimé VIDE (pour que son
identifiant soit nommé par le journal et que le compteur de `projet` ait quelque chose à
dépasser). Le test charge le fichier, migre, et vérifie : version 31 ; une ligne `copie` par
album, `cran = 'origine'`, `creee_par = importe_par` ; `projet_origine_nom` égal au nom ;
`sqlite_sequence` de `projet` au-dessus du plus grand identifiant nommé ; `PRAGMA
foreign_key_check` vide ; idempotence (rejouer ne change rien) ; et une trentaine de gestes
rejoués avant et après sur la même base (le protocole de la relecture de la tranche 2), dont
les seuls écarts permis sont les clés neuves.

---

## Les règles d'autorisation, question par question

Le serveur distingue aujourd'hui dix-sept questions (lu, `autorisation.Portee`). Proposition :
trois neuves, une qui change de sens, une qui change de lecture. Toutes dans
`autorisation.py`, et nulle part ailleurs.

**`peut_lire_les_notices(self) -> bool`** — neuve. `self.tout or bool(self.projets_geres)`.
Voir les notices du fonds : titre, série, auteur, et rien d'autre. Ne prend pas d'identifiant :
une notice appartient à l'instance (case du 2026-10-10 : « appartient à l'instance dès cet
instant : sa notice devient lisible des responsables des autres projets »). Ce que la route ne
rend PAS, et qu'un test de sortie doit jouer : ni `importe_par`, ni les copies, ni leurs
projets ou collections, ni la demande en attente, ni le nombre de planches. Si elle dit d'un
document qu'il est « déjà dans ce projet », c'est pour un projet que l'appelant GÈRE, et sans
dire dans quelle collection — être responsable n'ouvre aucune collection du projet (lu :
`est_du_projet`, « entrer dans un projet n'ouvre aucune de ses collections »).

**`clause_rejoindre_directe(self, alias="a.id") -> (sql, params)`** — neuve. Rejoindre sans
rien demander : on LIT la copie (`clause_album`), on écrit dans la collection d'arrivée
(`peut_ecrire`, vérifié par la route), et l'on ADMINISTRE chacune des collections où la copie
vit (`peut_administrer` — le propriétaire, ou `bd-admins`). La forme de `clause_destruction`
(« toutes ses collections »), un palier plus haut, parce que partager un travail est élargir
le cercle de qui le voit : c'est la décision du propriétaire, pas de qui annote (AUTH-3,
« administrer n'est pas écrire »). Hors de là, une demande (D4).

**`peut_repondre_a(self, demande) -> bool`** — neuve. Par genre : une suppression (document ou
projet) et une entrée de documents → `peut_tenir_le_fonds()` ; un `rejoindre` →
`peut_administrer(c)` pour une collection `c` où la copie vit, ou la portée totale. C'est la
première demande à laquelle répond quelqu'un qui ne tient pas le fonds, et la garde des routes
de réponse change en conséquence : aujourd'hui `repondre_demande` commence par
`_exiger_le_fonds` (lu). Le refus reste un 403 nommé sur le DROIT, avant l'objet, pour les
genres réservés ; pour un `rejoindre`, 404 à qui ne lit pas la collection source (l'objet ne
lui est pas connu).

**`clause_suppression_directe`** — change de lecture. Ses quatre moitiés restent ; la deuxième
lit `copie.creee_par` (« a créé CETTE copie ») au lieu de `document.importe_par`, et la
cinquième source de `_sources_du_travail` ne compte plus que les actes sous `document` dont la
charge nomme CET album. En 3b, une sixième source : le travail RECOPIÉ dans la copie compte
comme celui de ses auteurs (cf. 3b).

**`destructible`** dans `GET /api/albums` — change de sens une seconde fois : « supprimer
définitivement CETTE copie sans rien demander ». Le document n'est détruit avec elle que si
c'est sa dernière.

Questions qui ne bougent pas, et qu'il faut dire : `est_du_projet`, `peut_gerer_projet`,
`peut_decider_des_projets`, `clause_projet`, `clause_album` (une copie se lit par ses
collections, rien de plus), `clause_destruction`, `peut_tenir_le_fonds` (le fonds entier,
l'origine, les demandes et leur détail restent à lui), `peut_nommer_le_demandeur`.

### Ce qui fuit si l'on se trompe

- **Une demande de P1 lisible dans P2** — la clé `demande` de `GET /api/albums` cherchée par
  document (ci-dessus). C'est le défaut le plus probable, parce que le code d'aujourd'hui le
  fait et qu'aucun test ne le voit tant qu'il n'y a qu'une copie.
- **La route des notices qui rend une colonne de trop.** Elle sera écrite à côté de
  `lire_le_fonds`, qui rend tout ; la tentation est d'en filtrer la sortie. Elle doit être une
  requête à elle, avec une liste de colonnes NOMMÉE (la leçon de `GET /api/export/json`, qui
  publiait par défaut). Cliquet : `test_sorties_identite` (la sentinelle importe un document,
  aucune trace de son login dans la réponse).
- **404, jamais 403, sur un document qu'on n'a pas le droit de nommer.** Un annotateur qui
  n'est responsable de rien et envoie un `document_id` arbitraire à la route de prise doit lire
  « Document introuvable », le même que l'identifiant existe ou non ; un responsable lit les
  notices, donc un 403 nommé ne lui révèle rien. Une collection d'arrivée où l'on n'écrit pas :
  404, comme `ranger_album` aujourd'hui (lu).
- **Ce que révèle une demande « rejoindre »** — à son destinataire, le propriétaire de la
  collection source : le nom de qui demande et celui de la collection d'arrivée, qu'il ne lit
  peut-être pas. Dans le même projet. Proposé accepté par écrit : on ne consent pas à partager
  avec une collection dont on ignore le nom.
- **« Déjà dans ce projet »** dit au responsable qu'une collection de SON projet, qu'il ne lit
  peut-être pas, emploie le document. Proposé accepté : c'est son projet.
- **En 3b, amorcer depuis un autre projet** suppose que le demandeur sache qu'une copie
  travaillée existe ailleurs — contre « ni qui l'emploie ». À trancher avec la 3b, pas
  maintenant (cf. ses questions).

---

## Les écrans touchés

Deux refontes sont en cours et la tranche se pose dessus : l'Administration à vues adressables
(« À faire », Fonds, Projets, Comptes et groupes, Instance — tranchée le 2026-10-16, écrite par
un autre agent sur une copie) et la Bibliothèque en calque (`UX-18`, orientée le 2026-10-16,
non codée). **Tout ce qui suit dépend de leur forme finale**, et la maquette marque « non
commenté par Hugo » l'emplacement des gestes de la tranche 3.

**Bibliothèque** (`static/corpus.js`, ou son successeur `UX-18`).
- La liste des albums filtrée par le projet courant (lu : `loadAlbums` filtre déjà `au_fonds`
  à l'écran ; il gagne le projet, par une fonction de `static/lib/projet.js` sous table de
  vérité Node — la place de `BDProjet.duProjet`). Le serveur publie le projet EFFECTIF de chaque
  album (`sql_projet_d_album`), pas seulement la colonne brute. Filtre d'écran, pas garde :
  la doctrine d'aujourd'hui, et la règle de `CLAUDE.md` (« la liste des albums et le lot ne
  connaissent pas le projet ») est à réécrire — c'est aussi la case « La règle du projet
  courant dans la Bibliothèque est réécrite pour la forme en calque ».
- « + Prendre du fonds… » dans l'onglet *Albums* d'une collection (maquette v8) : pour un
  responsable, la recherche dans les notices et la demande groupée ; pour tout écrivain de la
  collection, les documents du projet qu'il LIT déjà (rejoindre, zéro). Il remplace
  « + Ranger ici » (lu : `rangerAlbum`, `loadAppartenance`, `BDProjet.pourRanger`).
- Le panneau « Supprimer… » (lu : `ouvrirSuppression`, `spDefinitif`, mots dans
  `static/lib/suppression.js`) dit, pour une copie qui a une sœur, que les images restent.
  **Supposé** : sans dire où est la sœur — qui ne lit que P1 n'a pas à apprendre que P2 existe.
- Les demandes « rejoindre » reçues, chez le propriétaire, dans la fiche de la collection
  (D11).

**Atelier** (`static/viewer.js`). La liste des albums (lu : ligne 92, le même filtre
`au_fonds`) suit le projet courant ; le lien profond bascule le projet.

**Administration** (`static/administration.js`, en refonte).
- « À faire » : la demande d'entrée de documents, dépliée sur place, une ligne par document
  avec Accepter / Refuser et « Tout accepter » (maquette : `ligneDemande`, genre `documents`,
  montré sous « tranche 3 »). Les demandes « rejoindre » y figurent pour l'administrateur, qui
  peut y répondre comme recours.
- Fonds, fiche d'un document : « Prendre dans… » nomme une COLLECTION (groupée par projet), et
  la liste de ses copies devient une vraie liste (la fiche les rend déjà toutes, lu :
  `fdDocument`).
- Projets, fiche d'un projet : pour son responsable, ses demandes d'entrée et leur état ; pour
  un projet vide, la phrase qui mène à créer une collection puis à prendre au fonds (D10).

**Ce qui ne bouge pas** : la Recherche et l'Exploration (tranche 4), « Qui entre », la bande du
haut.

---

## Les décisions qui restent à Hugo

Les plus structurantes d'abord. Chacune : la proposition, ses raisons, ce que l'autre réponse
coûterait, et la case qu'elle ferme.

**D1 — La tranche en deux temps : 3a (prendre, rejoindre, les albums du projet), puis 3b
(l'échelle des couches).** *Cases « Tranche 3 — prendre un document » et « Tranche 3 —
repartir de zéro ».* Proposition : oui. « Partir de zéro » et « rejoindre » ne copient aucun
travail : une ligne `albums`, ses planches, un rangement. « En partir » copie huit tables
(régions avec leur arbre, annotations, tags, corrections grammaticales, attributs de case,
locuteurs, présences, et la réindexation de chaque région), doit dire ce que devient le
vocabulaire local d'une autre collection, attribuer au journal un travail fait par d'autres, et
entre deux projets faire savoir au demandeur qu'un travail existe ailleurs, ce que la notice
lui cache. La 3a rend utilisable tout de suite le fonds, que la tranche 2 a rempli sans que
personne d'autre que l'administrateur puisse y puiser. L'autre réponse — une seule tranche —
double la durée pendant laquelle le code reste sur `dev` sans être vu, et fige dans la v31 la
table de provenance du travail copié avant d'avoir écrit le code qui la remplit (le regret de
la tranche 2).

**D2 — Être admis dans un projet n'est pas un état : un document entre dans un projet quand
une de ses collections le prend.** *Cases « Le PROJET est un étage… les collections du projet
piochent dans ce qu'il a admis », « Ce qui ne peut PAS entrer dans un projet ».* Proposition :
pas de table « admis » ; la demande d'entrée NOMME sa collection d'arrivée (la forme de la
maquette v8, « Prendre du fonds pour « Étude B » »), et « le projet a ce document » se lit à
l'existence d'une copie de ce projet. Raisons : un document admis sans copie est un état où
personne ne travaille, invisible des écrans d'aujourd'hui, et que la règle de la tranche 2
confondrait avec une copie gardée au fonds (une copie avec un projet et sans collection, lu :
`au_fonds`). L'autre réponse — une table `projet_document`, la forme de la première maquette
(« Admis dans … : ses collections peuvent le prendre ») — ajoute une liste « admis, pas encore
pris » chez le responsable et un second geste, mais donne une place à un refus (« ne peut pas
entrer »). Conséquence de la proposition : un projet vide doit avoir une collection avant de
recevoir un document (D10).

**D3 — Qui puise au fonds : le responsable par les notices, l'écrivain par ce qu'il lit
déjà.** *Case « La consultation du fonds est tranchée contre le cloisonnement ».* Proposition :
les notices du fonds et la demande d'entrée au responsable du projet (et à l'administrateur,
qui prend directement) ; un écrivain d'une collection qui n'est responsable de rien ne se voit
proposer que les documents du projet dont il LIT une copie — rejoindre, ou partir de zéro.
Raison : c'est la décision du 2026-10-09 (« un gestionnaire de projet voit la NOTICE seule »).
La maquette v8, non commentée, montre « + Prendre du fonds… » à tout écrivain de la
collection, et sa propre note dit pourtant « le responsable » : la suivre ouvrirait les
notices de l'instance entière à chaque annotateur et étudiant, plus large que ce qui a été
confirmé.

**D4 — Rejoindre : immédiat pour qui tient le travail, sinon le propriétaire consent — dans
TOUS les projets, le premier compris.** *Cases « Rejoindre un travail demande l'accord de qui
le tient », « Rien de l'existant n'est à séparer ».* Proposition : rejoindre ne s'offre que sur
une copie qu'on LIT ; il est immédiat si l'on administre chacune des collections où elle vit
(`clause_rejoindre_directe`) ; sinon il se DEMANDE, et un propriétaire de chacune de ces
collections répond (une collection sans propriétaire : l'administrateur). Dans le premier
projet aussi : la phrase du 2026-10-09 dit que le rangement « reste permis » — il le reste,
consenti. Raisons : le veto d'`AUTH-10` (« quiconque range chez soi retire aux autres le droit
de détruire ») n'est fermé que si le partage se consent, et un propriétaire est celui qui
décide qui voit sa collection. Ce que l'autre réponse coûte : « immédiat pour qui écrit dans
toutes » (`clause_destruction`) est plus léger mais laisse un membre élargir le cercle sans le
propriétaire ; « l'ancienne règle dans le projet de repli » écrit deux règles selon le projet.
« Un propriétaire de CHAQUE collection » est strict ; « d'une seule » est plus simple et ne
couvre pas la copie déjà partagée entre deux études — rare aujourd'hui (Hugo : aucun usage n'y
repose). À dire avec : la case « Ce que la séparation abandonne est accepté par écrit » (une
correction faite dans une copie n'arrive pas dans l'autre), que la 3a rend réelle.

**D5 — « Supprimer définitivement » détruit la COPIE ; le document part avec sa dernière.**
*Case « Quand « Supprimer définitivement » efface directement » (« aucun autre projet ne
l'emploie »).* Proposition : sur une copie qui a une sœur, le geste efface son travail et ses
planches, jamais les images qu'une sœur emploie ; sans rien demander si l'on a CRÉÉ cette copie
et que les trois autres conditions tiennent sur ELLE ; sinon une demande sur cette copie, et
l'administrateur qui l'accepte ne détruit qu'elle. Détruire un document qui a encore des copies
reste un geste de l'administrateur, depuis le fonds. Raisons : les mots de Hugo — « aucun autre
projet ne l'emploie » — protègent l'autre projet ; détruire sa copie ne lui retire rien. L'autre
réponse (définitivement = le document) rendrait toute copie indestructible par quiconque dès
qu'une sœur existe, sauf par un administrateur, et `repondre_demande` détruirait aujourd'hui
exactement cela : toutes les copies.

**D6 — Les images appartiennent au DOCUMENT : les copies partagent les fichiers ; et la 3a passe
avant `IMG-2`.** *Case d'`IMG-2` « L'ordre face aux autres chantiers est décidé ».* Proposition :
une seconde copie pointe vers les mêmes fichiers (`planches.chemin_*`) ; un fichier ne quitte
le disque que lorsqu'aucune planche ne le désigne plus, et les dossiers vides sont élagués à la
destruction du document. `IMG-2`, qui sort les chemins de `planches` vers une table d'IMAGES
nommées d'après leur identifiant (sa question 7, tranchée), y accroche alors ses images au
document. Raisons : un master TIFF pèse lourd, et le dupliquer à chaque prise doublerait le
disque d'un projet qui reprend un corpus ; l'`AUTOINCREMENT` de la v30 garantit qu'un dossier
`album_<id>` survivant à sa copie n'est jamais repris. Ce que coûtent les autres : copier les
fichiers à la prise (simple, sûr, ×2 sur le disque) ; ou `IMG-2` d'abord (l'image appartient au
document dès sa naissance, propre, mais la tranche 3 attend un chantier « de la taille d'une
tranche de COL-3 », selon sa propre note). Le risque de la proposition est irréversible — une
image effacée sous une sœur — et c'est pourquoi sa garde est dans les mutants obligatoires.

**D7 — La notice reste sur la copie.** Proposition : recopiée à la prise (avec ses
contributions), libre de diverger ; le fonds et les notices montrent celle de la plus ancienne
copie vivante. Raison : remonter la notice au document est le modèle juste, mais le cadrage de
la tranche 2 l'a mesuré hors de proportion (trente sites de requêtes, onze fichiers) ; il le
reste tant que deux copies sont rares. L'autre réponse — la notice au document — fait un
chantier de plus que la 3a, et une migration de données sans retour. Ce que la proposition
laisse : deux copies peuvent dire deux titres ; l'administrateur le voit dans la fiche du
document.

**D8 — Le projet d'origine garde son nom, et `projet` reçoit `AUTOINCREMENT`.** *Case « Le
projet d'ORIGINE d'un document ne garde pas son nom ».* Proposition : `projet_origine_nom` écrit
à l'import (rempli par la migration avec le nom du jour, ce qui est dit sur la colonne) ; et
plus aucun identifiant de projet ne revient. Raison : un projet d'origine pourra désormais être
supprimé sous un document vivant (sa copie vivant ailleurs), et `projet.id` se réattribue
(mesuré en tranche 2) — le fonds nommerait alors l'origine d'après le projet créé ensuite. Le
nom seul suffit à l'affichage ; `AUTOINCREMENT` ferme la cause pour `demande.projet_id` et le
journal aussi, avec la machinerie de la v30. Ce que coûte le nom seul : la jointure du fonds
disparaît, et chaque nouvel usage d'un identifiant de projet devra recopier un nom à côté.
`collection` (bien plus de tables filles) n'est pas proposée ici.

**D9 — Répondre à une demande de plusieurs documents : document par document, « tout
accepter », et un état « acceptée en partie ».** *Case « Comment l'administrateur répond à une
demande de plusieurs documents ».* Proposition : la case telle qu'écrite, plus la forme : la
demande se clôt quand chaque document a sa réponse ; son état vaut `acceptee`, `refusee` ou
`partielle` (une valeur de plus, sans `CHECK`) ; chaque document accepté naît copie vierge dans
la collection demandée (`demande_document.copie_id`) ; qui l'a déposée lit l'état dans la fiche
de son projet. L'autre réponse — accepter ou refuser en bloc — oblige à redemander ce qui a été
refusé avec le reste.

**D10 — Un projet naît avec sa collection de base, et ses documents y entrent avant qu'on ait
pensé ses collections.** *Case « Qui dépose la demande de départ d'un projet ».* **Tranché par
Hugo le 2026-10-17, CONTRE la proposition d'abord écrite ici** (le responsable dépose ses
demandes une fois une collection créée ; un projet vide le lui dit). Ses raisons : « le fonds
commence avec le projet », la collection peut advenir après ; penser collection avant d'avoir
eu accès aux œuvres est difficile à concevoir pour un nouvel utilisateur — on n'aurait que des
collections « Test » ; et un utilisateur peut ne jamais puiser au fonds, seulement importer ses
planches. Ce qui est retenu, piste de Hugo mise en forme avec la session de pilotage :

- **Tout projet naît avec UNE collection de base**, désignée par un drapeau
  (`collection.base`) et jamais par son nom, comme le projet de repli : elle se renomme, ne se
  supprime pas, ne change pas de projet. Ce que le projet prend au fonds y arrive par défaut
  (geste 4), et l'import la présélectionne. D2 tient : un document entre par une collection.
- **Ses responsables en sont propriétaires**, par DÉRIVATION de `projet_acces` et non par une
  ligne recopiée dans `collection_acces` : un responsable remplacé cesse de l'être.
- **Ses membres y entrent selon une position choisie pour le projet**, trois au choix :
  *écriture* (« ouverte »), *lecture* (les membres voient le corpus et travaillent dans leurs
  propres collections — annoter ne demande d'écrire que dans UNE collection de l'album), *aucun*
  (« protégée » : le propriétaire seul, plus qui il fait entrer par « Qui entre »). Stockée comme
  un NIVEAU (`collection.acces_membres`, NULL = protégée), dérivée elle aussi : qui sort du projet
  sort de la collection. Posée à la création du projet — « ouverte » présélectionnée, c'est le
  cas du débutant, et c'est un administrateur qui crée et voit la question —, modifiable ensuite
  par qui GÈRE le projet (`peut_gerer_projet`) ; la resserrer n'efface aucun travail, et le geste
  le dit avant de s'appliquer.
- **Rien ne s'ouvre au déploiement, et AUCUNE collection existante ne devient une base** : la
  migration crée pour chaque projet existant, le repli compris, une base NEUVE, VIDE et
  PROTÉGÉE. Une mise à jour ne donne de droit à personne sans qu'on l'ait décidé. *Écrit
  d'abord : « la migration désigne la « Collection par défaut » comme base du projet de
  repli ». La relecture croisée l'a pris en défaut le 2026-10-17 : la Collection par défaut est
  HABITÉE, et les responsables du repli — qu'une route v30 pouvait nommer sans que cela ouvre
  rien — en devenaient propriétaires au déploiement (prouvé sur la vraie base v30) ; en nommer
  un plus tard la lui aurait donnée entière. Hugo a tranché le jour même pour la base neuve.* La
  Collection par défaut reste la collection de repli des albums sans collection, désignée par
  son nom réservé ; le projet de repli porte donc deux collections.
- **Le coût est un changement de principe** : c'est la première fois qu'être d'un projet ouvre
  une collection — celle-là seule, et seulement si on l'a choisi. `collections_du_principal`
  lit `projet_acces` pour les bases ; la phrase « être d'un projet n'ouvre ni ne ferme AUCUNE
  collection » (`CLAUDE.md`, `docs/modele-et-droits.md`) devient fausse pour elles et se
  réécrit. Le cumul se fait dans `Portee.__init__`, avec les niveaux ; garde à mutants et
  relecture croisée obligatoires (cf. plus bas).
- La demande « d'un seul coup, projet et documents » venue de l'extérieur reste `AUTH-13`.

**D11 — Les consentements qui ne vont pas à l'administrateur se répondent là où vit qui les
donne.** Proposition : un « rejoindre » s'adresse au propriétaire dans la fiche de SA
collection, dans la Bibliothèque (une marque sur la collection, la demande dans l'onglet
*Albums*) ; l'administrateur les voit aussi dans « À faire », en recours. En 3b, l'accord du
responsable source va dans la fiche de son projet. Raison : le principe d'`UX-16` (« un panneau
va là où la question se pose ») et la phrase de `CLAUDE.md` — un propriétaire qui n'administre
rien n'a aucune raison d'ouvrir l'Administration. L'autre réponse — un « À faire » pour tous dans
l'Administration — envoie chaque propriétaire sur une page qui ne lui est pas faite.

**D12 — L'ordre : le serveur de la 3a après la refonte de l'Administration, son écran après
`UX-18` ; et la 3a part en production sans attendre la tranche 4.** Proposition : les deux
premiers commits de serveur peuvent s'écrire dès la refonte de l'Administration portée ; le
commit d'écran attend la Bibliothèque en calque — l'argument que Hugo a retenu pour
l'Administration (« posé sur la page d'aujourd'hui, il faudrait le déménager ») vaut pour elle.
Le commit « les albums du projet courant », petit et sans migration, peut partir avant tout le
reste, dans l'écran d'aujourd'hui, si Hugo le veut tôt. La 3a part en production seule, le
double compte de la Recherche et de l'Exploration écrit dans le guide : les copies sœurs seront
rares avant la tranche 4. L'autre réponse — retenir la 3a jusqu'à la tranche 4 — empile deux
migrations et deux tranches non vues, le risque que l'ordre de la tranche 1 avait refusé.

### Ce qui peut se trancher en route (propositions)

- Le lien profond de l'Atelier vers un album d'un autre projet fait basculer le projet courant
  (comme `/corpus?collection=`).
- Reprendre une copie gardée au fonds se DEMANDE à l'administrateur (son geste « Rendre »),
  même par le responsable : la copie porte un travail fait dans une collection qu'il ne lit
  peut-être pas.
- Une demande d'entrée refusée peut être redéposée ; la règle des refus antérieurs
  (`refus_anterieurs`, lu) s'étend aux documents d'une entrée.
- Une copie neuve s'écrit au journal sous la cible `document` (déjà retenue, sans rang, non
  annulable), charge : album, collection, cran, copie source.
- La liste des notices est cherchée au serveur et paginée : un millier de documents visés d'ici
  un an (maquette v8).

### Les questions de la 3b, à cadrer avec elle (non tranchées ici)

Ce qui est copié à chaque cran (le découpage emporte-t-il les attributs de case ? les
locuteurs vont-ils avec la transcription ou les annotations ?) ; le vocabulaire local d'une
autre collection (proposition à venir : n'emporter que les termes visibles depuis la collection
d'arrivée, et dire combien sont laissés — sachant que `tags.label` est UNIQUE dans toute
l'instance, lu, donc qu'un tag local ne se duplique pas sous le même nom) ; ce que le demandeur
apprend d'une copie d'un autre projet pour en partir ; qui consent dans le projet même (la
première maquette : personne) ; une copie longue faite par un lot plutôt que dans la requête
(une réindexation par région, spaCy hors transaction d'écriture, `CLAUDE.md` § Concurrence) ;
la provenance (une table `region_origine`, région copiée → région source, qui ne tient que
parce que les identifiants de région ne reviennent plus depuis la v30) ; l'attribution au
journal (une activité `copie` de l'agent qui copie, sans événement par région, pour ne pas lui
attribuer le travail des autres — à vérifier contre `tools/_commun.pseudonymes`, qui numérote
aussi sur les activités, **supposé**) ; et « repartir de zéro » écrit comme UN acte sous
`document` plutôt que comme des centaines de suppressions que Ctrl+Z remonterait une à une.

---

## Le découpage en commits (3a)

Chaque commit vert seul, suite par défaut entière ; sur une copie, par un agent neuf, relu par
la session de pilotage, comme les tranches 1 et 2.

**0 — Les albums du projet courant** (sans migration, détachable — D12). Le serveur publie le
projet effectif d'un album dans `GET /api/albums` ; `static/lib/projet.js` gagne la fonction
qui filtre, sous table de vérité Node ; la Bibliothèque, l'Atelier et le lot l'emploient ; le
lien profond bascule. Tests : un album d'un autre projet absent des deux listes, sous une
identité qui lit les deux projets ; la bascule par adresse.

**1 — La v31, sans comportement** (la preuve de la tranche 1 : aucun test de comportement
modifié, seuls les cliquets qui DÉCLARENT ce qui est neuf). Les tables et colonnes ci-dessus ;
`copie` écrite par `create_album` et l'import ShareDocs ; `projet_origine_nom` écrit à l'import ;
`AUTOINCREMENT` sur `projet`. Le fichier `tests/bases/v30-<sha>.sql` et l'extension de l'outil
qui le fabrique, dans le même commit. Et, sans effet tant qu'un document n'a qu'une copie : les
sites du tableau « ce qui casse à deux » réécrits — demande cherchée par copie, 5ᵉ source filtrée
par album, suppression directe lue sur `copie.creee_par`, fichiers effacés par référence. Leur
preuve d'innocuité est la suite inchangée ; leur preuve d'utilité arrive au commit suivant.

**1b — La collection de base** (D10). `collection.base` et `collection.acces_membres` dans la
v31 ; la base créée avec tout projet (route et repli), désignée pour l'existant (protégée) ; la
dérivation dans `Portee.__init__` — responsables propriétaires, membres au niveau choisi — ; le
réglage par qui gère le projet ; les refus nommés (supprimer la base, la sortir de son projet) ;
la présélection à l'import. Tests de comportement sous les trois positions, et un membre sorti du
projet qui n'y lit plus rien.

**2 — Le serveur : sœurs, prise, demandes.** `database.creer_copie(conn, document_id,
collection_id, *, par, depuis, cran)` (arguments obligatoires sans défaut, le patron de
`creer_document`) ; les trois questions neuves de la `Portee` ; `GET /api/fonds/notices`
(cherchée, paginée) ; la prise (`POST /api/collections/{cid}/prendre`, une liste de documents
avec leur réponse `zero` | `rejoindre`, résultat document par document : fait, demandé, refusé) ;
les genres `entree_documents` et `rejoindre` ; la réponse document par document ; les lectures
de ses demandes par le responsable (fiche du projet) et des demandes reçues par le propriétaire
(fiche de la collection). `rangement_traverse` et l'outil `gerer_collections.py` (qui range
aussi) passent par la même règle de rejoindre. Comme le deuxième commit de la tranche 2, il ne
part pas seul : l'écran d'avant mentirait (« + Ranger ici » répondrait par une demande).

**3 — L'écran.** Sur la Bibliothèque en calque et l'Administration à vues (D12) : « + Prendre du
fonds… », rejoindre, le panneau « Supprimer… » pour une copie qui a une sœur, « À faire » et la
fiche du document, la fiche du projet, les demandes reçues du propriétaire.

**4 — La documentation**, à part : `CLAUDE.md` (schéma 31, les questions qui passent de dix-sept
à vingt, `destructible` qui change de sens, la règle du projet courant de la Bibliothèque, le
tableau des surfaces, « en créer une seconde est la tranche 3 » qui devient faux),
`docs/modele-et-droits.md`, `docs/guide-utilisateur.md` (le double compte jusqu'à la tranche 4,
ce que la séparation abandonne), `docs/exploitation.md` (les dossiers d'images qui survivent à
leur copie). Puis les fiches : `AUTH-13` (le mécanisme qu'il réemploie), `IMG-2` (D6), `AUTH-10`
(case « garde sa règle pour une copie PARTAGÉE »), `UX-18`.

Ordre de grandeur : la 3a fait cinq commits de code et de documentation, plus les correctifs de
la relecture — la tranche 2 en a demandé une demi-douzaine de plus que son plan. La 3b, trois à
quatre (amorcer ; repartir de zéro ; l'écran ; la documentation), sur une v32.

### Les gardes à éprouver par mutants (obligatoires)

Une suite verte dit qu'on n'a rien cassé, pas qu'on n'a rien ouvert. Chacune avec le mutant qui
doit tomber :

- **les fichiers d'une sœur** : détruire la copie A, l'image de la copie B répond encore 200 et
  son fichier existe ; mutant : effacer par dossier comme aujourd'hui ; idem pour une planche ;
- **la demande cherchée par copie** : la copie de P2 ne porte aucune clé `demande` quand P1 a
  demandé ; mutant : la jointure par document ;
- **accepter ne détruit que la copie demandée** ; mutant : la requête de `repondre_demande`
  d'aujourd'hui ;
- **la 5ᵉ source filtrée par album** ; mutant : sans le filtre, la créatrice d'une sœur ne peut
  plus supprimer seule ;
- **`creee_par` et non `importe_par`** ; mutant : l'ancienne moitié ;
- **les notices** : 403 sans responsabilité, droit avant objet ; aucune clé hors de la liste
  nommée ; mutant : `SELECT d.*` ou une clé de plus ;
- **404 sur un document non nommable** pour qui n'est responsable de rien ; mutant : un 403 ;
- **`clause_rejoindre_directe`** : un écrivain non propriétaire reçoit une demande, pas un
  rangement ; mutant : `peut_ecrire` à la place de `peut_administrer` ; une collection sans
  propriétaire n'est jamais « tenue » par personne d'autre que la portée totale ;
- **`peut_repondre_a`** : un propriétaire répond à un `rejoindre` de sa collection, pas à une
  entrée de documents ni à une suppression ; un propriétaire d'une AUTRE collection, 404 ;
  mutant : la garde d'aujourd'hui, ou l'inverse ;
- **la copie neuve naît dans le projet de la collection d'arrivée**, rangée dans elle seule, et
  `albums_hors_de_leur_projet` reste vide ; mutant : le projet de la source ;
- **l'état partiel** : une réponse par document, la demande close à la dernière ; mutant : close
  à la première ;
- **la migration** : compteur de `projet` au-dessus du plus grand identifiant nommé ; mutant :
  amorcé sur `MAX(projet.id)`.
- **la collection de base n'ouvre qu'elle-même** (D10) : un membre d'un projet à base ouverte
  ne lit aucune AUTRE collection du projet ; mutant : la dérivation appliquée à toute collection
  du projet ;
- **la position est respectée** : protégée, un membre n'y lit rien ; en lecture, il n'y écrit
  pas ; mutants : NULL lu comme `lecture`, `lecture` lu comme `ecriture` ;
- **la dérivation suit le projet** : un membre retiré du projet n'y lit plus rien, un responsable
  rétrogradé n'en est plus propriétaire ; mutant : une ligne recopiée dans `collection_acces` ;
- **rien ne s'ouvre à la migration** : sur la vraie base v30, aucune portée ne grandit ; mutant :
  la base de l'existant créée ouverte.

### La relecture croisée

Obligatoire : la tranche touche quatre gardes et une sortie. Par une session qui ne l'a pas
écrite, sur la copie, avec ses propres sondes — sept identités au moins (administrateur ;
responsable de P1 sans collection lue ; propriétaire d'une collection de P1 ; écrivain non
propriétaire ; lectrice ; membre de P2 ; compte partagé), toutes les routes GET rejouées sous
chacune avec une sentinelle dans chaque copie, et la question qu'aucun test ne pose : une
personne qui ne lit que P2 apprend-elle quoi que ce soit de P1, par une clé, un refus, une
adresse d'image ou un compte ?

### Les passes de QA à réécrire

Rédigées, jamais cochées par qui les écrit.

- **`prendre-un-document`**, neuve — la case « Tranche 3 — le projet a SA passe » : le
  responsable cherche au fonds et demande trois documents pour une collection, l'administrateur
  en accepte deux et en refuse un, le responsable le lit ; un écrivain rejoint un travail qu'il
  tient, puis demande à en rejoindre un qu'il ne tient pas, le propriétaire accepte ; une
  seconde copie vierge ; « Supprimer définitivement » sur une copie qui a une sœur, l'image de
  la sœur encore là. Sous les identités de la recette (`proprio`, `stagiaire`, `lectrice`,
  `admin-bd`).
- **`collections-bibliotheque`** — rejouée sur ses gestes d'album (case « Tranches 2 et 3 ») :
  « + Ranger ici » n'existe plus.
- **`supprimer-n-est-pas-sortir`** — une zone de plus : la copie qui a une sœur.
- **`projet-visible`** — ses cases de la Bibliothèque : les albums suivent le projet.
- **La passe d'« À faire »** que l'agent de la refonte écrira : ses cases de demandes gagnent
  l'entrée de documents et le « rejoindre ».
- **`petites-largeurs`** et **`preference-de-police`** — sur le panneau « + Prendre du fonds… »
  et la réponse document par document, à 320 et 375 px et à grande police.

---

## Les risques, et ce qui les mesurerait

- **Une image effacée sous une sœur** — irréversible. Mesuré par les mutants ci-dessus, et par un
  test qui détruit successivement toutes les copies d'un document et vérifie qu'à la dernière il
  ne reste plus un fichier, ni avant elle un seul de moins.
- **Les sites écrits pour une copie que ce cadrage n'a pas trouvés.** Le tableau en compte huit ;
  la règle « une copie » est aussi dans des phrases (`_MOTIF_DESTRUCTION`, les mots de
  `static/lib/suppression.js`) et peut-être dans des requêtes qui joignent par `document_id`.
  Mesuré par une recherche de `document_id` sur tout le dépôt au premier commit, et par la
  relecture croisée sous une base qui porte DEUX copies d'un même document dans deux projets.
- **Le double compte** dans la Recherche et l'Exploration d'ici la tranche 4 — accepté (D12) ;
  mesurable par un test qui le CONSTATE et qu'on retournera en tranche 4.
- **La liste des albums ralentit** : la règle de suppression descend déjà dans le journal pour
  chaque album, sans mesure sur un corpus réel (case de la tranche 2, ouverte) ; la 3a y ajoute
  la jointure de `copie`, la 3b `region_origine`. À mesurer sur une base fabriquée au volume de la
  maquette (un millier de documents) avant la 3b.
- **La notice qui diverge** (D7) : deux titres pour un document. Visible de l'administrateur
  seul ; à surveiller à l'usage.
- **Les refontes en cours** : l'Administration (sur une copie, en ce moment) et `UX-18` changent
  les ancres que les tests navigateur visent ; le commit d'écran se réécrit sur elles, pas avant.
- **`IMG-2` et la 3a dans le même schéma** : deux migrations qui toucheraient `planches` ; si
  `IMG-2` passait devant, D6 se rejoue (l'image au document dès sa table).
- **La base de production** compte cinq albums et cinq documents (fiche, 2026-10-16) : la v31 y
  est triviale ; c'est la base fabriquée qui porte l'exigence.
- **Ce que ce cadrage n'a pas lu** : `routes/projets.py` en entier, `undo.py` au-delà de sa liste
  de tables, `tools/gerer_collections.py`, `_reconstruire_avec_autoincrement` au-delà de sa
  docstring, et la dernière version de la refonte de l'Administration (sur une copie
  hors de cet arbre).
