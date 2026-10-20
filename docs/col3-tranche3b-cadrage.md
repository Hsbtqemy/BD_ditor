# COL-3, tranche 3b — en partir jusqu'à un cran, repartir de zéro : cadrage

Rendu le 2026-10-20, sur `main` à `16c6127` (schéma 31, la 3a fusionnée). Rien n'est codé ni
exécuté. Ce qui est marqué **lu** a été lu dans le code à ce commit ; ce qui est marqué
**supposé** ne l'a pas été, ou reste à mesurer. Les décisions sont numérotées **E1 à E10**
(la 3a avait D1 à D12) ; chacune dit la case de `pilotage/COL-3.md` qu'elle ferme. Ce
document prolonge `docs/col3-tranche3-cadrage.md` (§ « 3b — l'échelle des couches » et
§ « Les questions de la 3b ») et n'en répète pas le modèle.

---

## Ce que la 3b livre, en gestes

1. **En partir** — une copie à soi, amorcée avec le travail d'une autre copie jusqu'au cran
   choisi. Dans le projet comme entre deux ; entre deux, avec l'accord du RESPONSABLE du projet
   d'où l'on part (confirmé par Hugo le 2026-10-09). La copie dit d'où elle vient et jusqu'à
   quel cran ; le journal attribue toujours le travail copié à ceux qui l'ont fait.
2. **Repartir de zéro** — revenir à un cran de l'échelle sur un album, en gardant les images ;
   directement si personne d'autre n'y a travaillé, sinon une demande certifiée, comme
   supprimer.
3. **Le vocabulaire qui ne suit pas est dit** — avant de copier, et dans la trace de la copie.

Ce que la 3b ne livre pas (inchangé depuis le cadrage de la 3a) : la Recherche et
l'Exploration bornées au projet et le dédoublonnage des sœurs (tranche 4) ; un étage de projet
pour le vocabulaire et les personnages (tranche 4) ; `AUTH-13`.

---

## Ce qui existe déjà (lu)

- **`database.creer_copie`** (`database.py` l.2078-2150) fait le cran `images` : notice
  recopiée hors `ALBUM_HORS_NOTICE`, planches réduites à `PLANCHE_SCAN` (mêmes fichiers,
  `statut = 'importee'`), contributions, une ligne `copie`, le rangement dans la collection
  d'arrivée, un acte sous `document` (charge `copie: {cran, depuis_album_id, collection_id}`)
  et un `lien` sous `collection_album`. Tout autre cran lève `ValueError` (l.2116) — un test
  le verrouille (`tests/test_creer_copie.py`, cran `annotations` refusé). Appelant unique :
  `socle._nouvelle_copie`.
- **Aucune correspondance planche source → planche copiée n'est gardée** ; le rapprochement
  se fait par `numero`, unique par album (`idx_planches_album_numero`).
- **`copie.cran`** n'a pas de `CHECK` ; il n'est lu qu'à deux endroits : `GET /api/fonds`
  (`routes/fonds.py` l.664-673) et `static/administration.js` l.2201 (« copie vierge, images
  partagées »).
- **La prise** (`routes/fonds.py`, `prendre`, l.903-987) a trois réponses par document —
  `zero`, `rejoindre`, `reprendre` — et rend `fait` / `demande` / `refuse`. La 3b en ajoute une.
- **`_index_region(conn, region_id, payload, lemmes, tokens)`** (l.2634) écrit la ligne FTS
  et les `tokens` FOURNIS : on peut réindexer une région copiée **sans spaCy**, en lui passant
  les lemmes et les tokens de sa source.

### Les tables du travail (lu, `database.py`)

| Table | Tient à | Référence | À noter |
|---|---|---|---|
| `regions` | planche | `parent_id` → regions, `activite_id` → activite | ordre de lecture = `regions.ordre` ; `AUTOINCREMENT` |
| `annotations` | région (UNIQUE) | — | une par région |
| `annotation_tags` | annotation | tag | `tags.label` **UNIQUE dans toute l'instance** |
| `region_attribut` | région | `attribut_valeur` | `UNIQUE(cible, nom)` sur la dimension |
| `bulle_locuteur`, `personnage_presence` | région (PK) | personnage | `personnages` n'a AUCUNE portée stockée |
| `tokens` | région | — | régénérés à chaque réindexation |
| `token_correction` | région, `UNIQUE(region_id, ordre)` | — | `auteur` en colonne ; `modele_auto`, `auto_*` (NLP-2) |
| `planches.statut`, `date_segmentation`, `validee`, `verrouillee`, `verrou_par`, `relecture` | planche | — | non recopiés aujourd'hui |

Aucune autre table ne lie deux régions. La FTS `recherche` porte `region_id` sans clé.

---

## E1 — L'échelle : ce que chaque cran emporte

Ferme la case « Les couches s'empilent, donc se choisissent sur une ÉCHELLE ». Proposition —
la liste de la fiche, rendue table par table :

| Cran (`copie.cran`) | Emporte, en plus du cran d'en dessous |
|---|---|
| `images` (existe) | notice, contributions, planches (`PLANCHE_SCAN`) |
| `decoupage` | `regions` : type, géométrie, `parent_id` (renuméroté), `ordre`, `source`, `activite_id` ; `ocr_texte` à NULL, `touche` à 0 ; `planches.statut` et `date_segmentation` |
| `transcription` | `regions.ocr_texte`, `touche` ; `tokens` recopiés tels quels, FTS réécrite sans spaCy |
| `grammaire` | `token_correction` entières (`auteur`, `etat`, `obsolete`, `modele_auto`, `auto_*`) ; `planches.relecture` |
| `annotations` | `annotations` + `annotation_tags` (sous E5), `region_attribut` (sous E5), `bulle_locuteur`, `personnage_presence` (sous E6) |

Trois choix dans cette table, qui sont les questions du cadrage de la 3a :

- **Les attributs de case vont avec les annotations, pas avec le découpage.** Qualifier une
  case est interpréter (`comptes.traces` le compte comme du travail), et ils tiennent au
  vocabulaire, dont E5 dit qu'il ne suit pas toujours.
- **Les locuteurs vont avec les annotations, pas avec la transcription.** Dire qui parle est
  interpréter, et c'est par le locuteur qu'un personnage d'un projet entre dans un autre (E6).
- **Rien de la VALIDATION ne suit** : ni `validee`, ni `verrouillee`, ni `verrou_par`, à aucun
  cran. Valider une planche est un jugement de qui la relit, dans SA copie ; la copie n'a été
  relue par personne. `activite_id` suit, lui : il dit quel moteur a produit la région, et le
  perdre ferait passer un découpage Kumiko pour un découpage humain dans l'export PROV.

Le cran n'est pas au-dessus de ce que la source porte : copier « jusqu'aux annotations » une
source sans annotation donne une copie qui n'en a pas, et `copie.cran` dit le cran DEMANDÉ.
**Supposé** : ce que l'écran dira d'une source sans travail au cran choisi (proposé : le
proposer quand même, et dire ce qui est vide dans l'aperçu, E5).

## E2 — La provenance d'une région copiée : `region_origine`, sur une v32

Ferme la case « Ce qu'une copie garde de sa provenance ». La copie dit déjà de quel document
elle vient (`albums.document_id`), de quelle copie (`copie.depuis_album_id`), de quel projet
(`copie.depuis_projet_nom`) et jusqu'à quel cran (`copie.cran`). Il manque ce que la région
copiée doit à une région source. Proposition :

```
region_origine(
  region_id        INTEGER PRIMARY KEY REFERENCES regions(id) ON DELETE CASCADE,
  region_source_id INTEGER NOT NULL      -- sans clé : la source peut mourir
)
```

Elle ne tient que parce que les identifiants de région ne reviennent plus depuis la v30. Pas
de table pour les planches : `numero` suffit et ne change pas. Une copie de copie pointe vers
sa source DIRECTE ; la chaîne se remonte par une requête récursive (E3). Retenue de toute
sortie, comme `copie` (aucune route ne la rend ; le cliquet des colonnes la classe).

**La v32** porte aussi `demande.cran TEXT` (pour E7 et E8) et rien d'autre ; les genres neufs
vivent dans le code (`GENRES_DEMANDE`), pour la raison écrite sur la table. Elle se vérifie
sur une **vraie base v31** : `tools/fabriquer_base_de_version.py 16c6127
tests/bases/v31-16c6127.sql`, qui gagne une branche `SCHEMA_VERSION >= 31` posant ce que la
v32 doit traverser — deux copies sœurs, un `rejoindre` accepté, une copie gardée au fonds, un
retour en attente, des corrections grammaticales de deux auteurs (`tests/bases/` n'a encore
que v29 et v30, lu).

## E3 — Le travail copié reste celui de ses auteurs : PAS d'événements recopiés

Le cœur de la 3b, et là où une forme naïve casse quatre choses à la fois. Deux formes
s'offrent, et les deux premières se lisent fausses :

- **Copier sans rien écrire** (lu, `autorisation._sql_travail_d_autrui` l.729-772) : les
  sources 1 et 4 de la règle de suppression joignent les événements par `region_id` et
  `planche_id` VIVANTS — aucun ne porte les identifiants neufs, donc le travail des autres
  devient invisible et le copieur supprime seul une copie pleine du travail d'autrui. Pire, la
  source 2 (un attribut de case sans `lien` humain = un inconnu) fait l'inverse : tout
  attribut recopié compte comme d'autrui, et interdit au copieur de supprimer seul une copie
  dont il a TOUT fait.
- **Recopier les événements sous les identifiants neufs, au nom de leurs auteurs** : Ctrl+Z
  les remonterait (lu, `undo.derniere_action_annulable` : `agent IS ?`, `ORDER BY id DESC`) —
  le prochain Ctrl+Z de Léa défairait une région qu'elle n'a pas touchée depuis un mois, dans
  une copie qu'elle n'a pas faite ; `comptes.traces` gonflerait ses actes ; `accord_inter`
  compterait chaque révision deux fois ; et l'export PROV publierait deux fois le même acte.

**Proposition : aucun événement par région.** La copie s'écrit en UN acte sous `document`,
comme aujourd'hui (charge : `cran`, `depuis_album_id`, `collection_id`, et les comptes de ce
qui est copié et de ce qui est laissé, E5) — retenu de toute sortie, sans rang, non annulable
(lu : `CIBLES_RETENUES`, `CIBLES_SANS_RANG`, `undo._TABLES`). L'attribution passe par
`region_origine`, et la règle de suppression apprend à la lire :

- une **sixième source** dans `_sources_du_travail` : les événements humains dont `cible_id`
  est une région source de l'album, remontée par la chaîne de `region_origine`. Le journal
  survit à sa cible : la jointure tient même si la région source a été supprimée depuis — un
  écart assumé avec « on lit ce qui VIT encore » (l.735-738), à écrire sur la source : le
  travail copié vit, lui ;
- la **source 2** cherche le `lien` d'un attribut sous la région ET sous ses régions
  sources ;
- la **source 3** n'a rien à apprendre : `token_correction.auteur` est recopié avec la ligne.

`sql_actes_sur_album` en hérite (la même liste), donc ce que l'administrateur lit sous une
demande de suppression compte le travail copié — à dire à l'écran (« dont n gestes faits sur
la copie d'origine »). La naissance de la copie reste hors du travail d'autrui
(`_SQL_NAISSANCE_D_UNE_COPIE`, inchangé). Ce que cela coûte : `GET /api/albums` descend dans
le journal par une requête récursive pour chaque album — **à mesurer** sur une base au volume
de la maquette (un millier de documents) AVANT de figer la forme ; le repli serait une colonne
`region_origine.region_racine` qui court-circuite la chaîne quand aucune copie intermédiaire
n'a été travaillée (**supposé** : ce n'est vrai que si l'on accepte de perdre le travail des
intermédiaires, donc à éviter).

**Ce qui se perd, à écrire et non à réparer ici** : l'accord inter-annotateurs (`ANN-5`) ne
suit pas une correction recopiée — la première retouche sur la copie d'une correction faite
ailleurs n'est pas comptée comme révision (lu, `accord_inter.py` l.90-124, chaîne indexée par
`token_correction.id`). C'est la matière de la case « Deux copies du même document se savent
sœurs » (comparer deux travaux), donc de la tranche 4 ; d'ici là, `docs/accord-inter.md` le
dit.

## E4 — Dans un projet : qui consent à ce qu'on parte de son travail

Ferme « qui consent dans le projet même », laissée ouverte par la 3a (la première maquette :
personne). Partir du travail d'une copie de C1 pour une copie dans C2 le fait lire par les
lecteurs de C2 — c'est élargir le cercle, exactement ce que D4 a réservé au propriétaire pour
`rejoindre`. **Proposition : la règle de `rejoindre`, telle quelle.** Immédiat pour qui
ADMINISTRE chacune des collections où vit la copie source (`clause_rejoindre_directe`, réutilisée
sans changement) ou pour la portée totale ; sinon une DEMANDE au propriétaire — genre neuf
`amorcer`, `repondra` comme pour `rejoindre`, réponse dans le bloc ⚑ de l'onglet *Albums*.
L'alternative (personne ne consent dans le projet) est plus simple et fait d'« en partir » le
contournement de D4 : qui se voit refuser `rejoindre` copierait le travail à la place.

Le cran `images` reste la « copie vierge » de la 3a : ne demande rien de plus qu'aujourd'hui.

## E5 — Le vocabulaire qui ne suit pas

Ferme la case « Le vocabulaire ne suit pas une copie ». Lu : un tag local à C1 recopié sur une
région de C2 serait INVISIBLE aux lecteurs de C2 (`socle._annotation_for_region` filtre par
`clause_terme`), préservé à l'écriture (`_tags_caches`), exclu de l'export de C2
(`clause_appartenance`) — posé et invisible, le piège de `COL-1`. Le dupliquer n'est pas
possible : `tags.label` est UNIQUE dans l'instance, `attribut_dimension` l'est par
`(cible, nom)`. **Proposition : n'emporter que les termes VISIBLES depuis la collection
d'arrivée** (globaux, ou locaux à elle) ; laisser les autres, et le DIRE :

- avant de copier, un **aperçu** (`GET …/amorcer/apercu?cran=&collection=`) dit combien de
  régions, de corrections, de notes, de tags et d'attributs partent, et combien de tags et
  d'attributs restent, sans les nommer à qui ne les lit pas — sinon l'aperçu ferait lire le
  nom d'un axe privé, la fuite de la v24 ;
- la charge de l'acte de copie garde les deux comptes ;
- une annotation dont tous les tags restent et qui n'a pas de note ne naît pas.

Entre deux projets, la même règle : un terme local d'une collection de P1 n'est jamais visible
d'une collection de P2, donc ne suit jamais. Les termes globaux suivent — ce que la tranche 4
bornera au projet.

## E6 — Les personnages suivent, et c'est une fuite écrite

Lu : `personnages` n'a pas de portée stockée, sa visibilité dérive des apparitions
(`socle._clause_personnage`). Recopier un locuteur rend le personnage — son nom, sa série, ses
notes, ses alignements — visible des lecteurs de la copie. Dans un projet, c'est le comportement
d'aujourd'hui pour tout album partagé. **Entre deux projets, c'est le premier chemin par lequel
une fiche de personnage de P1 entre dans P2.** Deux propositions, à trancher :

- **(a) ils suivent** au cran `annotations`, et la fuite est écrite (le personnage EST le
  travail : sans lui, « qui parle » est perdu) ; la tranche 4 lui donne un étage de projet ;
- (b) ils ne suivent qu'à l'intérieur d'un projet ; entre deux, les locuteurs et présences
  restent, comptés dans l'aperçu comme le vocabulaire.

Proposé : **(a)**, parce que le responsable de P1 CONSENT à la copie (E7) et que l'aperçu le
lui dit (« n personnages deviennent visibles dans P2 »).

## E7 — Entre deux projets : ce que le demandeur sait, et à qui va la demande

La question que le cadrage de la 3a a laissée : partir du travail d'un autre projet suppose de
savoir qu'il existe, contre « ni qui l'emploie » (la notice ne dit que titre, série, auteur —
confirmé par Hugo le 2026-10-09). Trois formes :

- (a) la notice dit qu'une copie travaillée existe ailleurs, et jusqu'à quel cran — rompt la
  décision du 2026-10-09 ;
- (b) le demandeur nomme le projet source, qu'il connaît hors de l'application — l'outil
  valide un nom qu'on ne peut pas lire, un oracle (« ce projet a-t-il ce document ? ») ;
- **(c) proposée : la demande nomme le DOCUMENT et le CRAN, jamais la source.** Le serveur
  l'adresse au responsable de chaque projet qui tient une copie travaillée jusqu'à ce cran, et
  à un administrateur s'il n'y en a aucune. Le demandeur ne lit que « demandé », quoi qu'il
  arrive : aucun bit ne fuit. Le premier responsable qui accepte choisit SA copie source ; les
  autres voient la demande close. Ce que le responsable source apprend : qui demande, et le
  nom du projet d'arrivée — accepté par écrit, comme pour `rejoindre`.

Seul un RESPONSABLE (ou la portée totale) demande entre deux projets : c'est lui qui lit les
notices (`peut_lire_les_notices`). Genre `amorcer` aussi, `demande.projet_id` = projet
d'arrivée, `demande.cran` posé ; la réponse vit dans « Au fonds · n demandes » de la fiche du
projet du demandeur, et chez le responsable source dans… **à trancher sur maquette** (proposé :
la fiche de SON projet, Administration → Projets, à côté de « Au fonds » — il n'a pas de
collection d'arrivée à lui où poser le bloc ⚑). Une copie née d'une acceptation est
`creee_par` le DEMANDEUR (comme une entrée acceptée, D11).

## E8 — Repartir de zéro

Ferme la case « Tranche 3 — repartir de zéro ». Revenir à un cran sur une copie, en gardant les
images. Proposition :

- **La règle de la suppression directe, telle quelle** (`clause_suppression_directe`, avec la
  sixième source d'E3) : écrire dans toutes les collections, avoir créé la copie, compte non
  partagé, personne d'autre n'y a travaillé. Sinon une demande, genre `repartir`, motif et
  **certification** obligatoires (le patron de la suppression, décision du 2026-10-15), à
  laquelle répond un administrateur. On repart VERS un cran inférieur à celui que porte la
  copie ; `images` est le plus bas.
- **Ce qui part**, par cran d'arrivée, l'inverse d'E1 : vers `grammaire`, les annotations, tags,
  attributs, locuteurs, présences ; vers `transcription`, en plus les corrections et
  `relecture` ; vers `decoupage`, en plus le texte (`ocr_texte` NULL, `touche` 0, tokens et FTS
  retirés) ; vers `images`, toutes les régions, `statut = 'importee'`. `validee` part à tout
  cran (le travail validé a changé) ; `verrouillee` reste (il protège des passes ML, et
  repartir de zéro n'est pas en lancer une).
- **UN acte sous `document`**, pas des centaines de suppressions : charge `{repartir: {cran,
  depuis_cran, comptes}}`. Non annulable — c'est voulu, et l'écran le dit (« ne s'annule pas »).
- **Ctrl+Z après une remise à zéro** : les actes d'avant visent des régions qui n'existent plus ;
  aujourd'hui l'annulation les refuserait un à un (« ne s'annule plus ») avant de les écarter.
  Proposé : un cinquième témoin dans `undo._meme_objet` — une remise à zéro de l'album
  journalisée depuis l'acte — qui écarte l'acte d'un coup. À trancher en route.
- `copie.cran` ne change pas : il dit d'où la copie est NÉE. **Supposé** : faut-il dire à
  l'écran qu'une copie a été remise à zéro ? Le journal le sait.

## E9 — Synchrone, sous le verrou, sans spaCy

Une copie profonde est une suite d'`INSERT … SELECT` par table, régions renumérotées par une
table de correspondance temporaire. Ordre de grandeur supposé : 60 planches × 40 régions =
2 400 régions, une poignée de requêtes par table, quelques dixièmes de seconde — sans spaCy,
parce que `_index_region` accepte les lemmes et les tokens de la source (E1, cran
`transcription`). **Proposé : dans la requête, sous `conflit.verrouiller`, en une transaction**
— pas de lot de fond (`pipeline/jobs.py` est figé sur trois passes ML et sous `ML_LOCK`, lu).
À mesurer au premier commit sur l'album le plus gros de la recette ; s'il dépasse la seconde,
l'étendre en lot devient un commit de plus. Réserve : les tokens recopiés ont été produits par
le modèle de la SOURCE ; si l'instance a changé de modèle depuis, la copie hérite d'un index
ancien, comme la source elle-même — pas un défaut neuf.

## E10 — L'écran se tranche sur maquette

Le patron de la 3a : une maquette interactive, en session dédiée, avant le commit d'écran.
Ce qu'elle doit trancher : où se choisit le cran (proposé : « Copie vierge » de « + Prendre
dans le projet… » devient « Copie… » avec l'échelle en radios, `images` présélectionné) ;
l'aperçu d'E5/E6 ; « Repartir de zéro… » dans la fiche d'un album (à côté de « Supprimer… »,
mêmes mots de certification) ; où le responsable source répond (E7) ; ce que « À faire » montre
des deux genres neufs (une couleur de tranche chacun, leurs boutons). Puis 320 px et grande
police sur l'écran codé.

---

## Les règles d'autorisation

Aucune question neuve ; trois qui s'étendent, toutes dans `autorisation.py` :

- **`_sources_du_travail`** gagne la sixième source et la source 2 sa chaîne (E3) — donc
  `clause_suppression_directe`, `destructible`, et la règle de « repartir » (E8).
- **`clause_rejoindre_directe`** sert aussi « en partir » dans le projet (E4), sans changement.
- **`peut_repondre_a`** apprend deux genres : `amorcer` → le propriétaire de chaque collection
  de la source (dans le projet) ou le responsable du projet source (entre deux), ou la portée
  totale ; `repartir` → `peut_tenir_le_fonds()`.

### Ce qui fuit si l'on se trompe

- **L'aperçu qui nomme un terme** qu'on ne lit pas (E5) — mutant : la liste des libellés au
  lieu de leur nombre.
- **La demande entre projets qui dit « personne n'a ce travail »** (E7) — mutant : un 404 ou un
  `refuse` quand aucune source n'existe.
- **Une région copiée qui garde un tag invisible** — mutant : recopier `annotation_tags` sans
  le filtre `clause_terme` de la collection d'arrivée ; le test lit la table, pas l'écran (qui
  le masquerait, `_tags_caches`).
- **Le copieur qui supprime seul le travail d'autrui** — mutant : la règle sans la sixième
  source.
- **Ctrl+Z qui remonte une région copiée** — mutant : un événement `creation` par région.

---

## Le découpage en commits

0. **La v32 et sa vraie base** : `tests/bases/v31-16c6127.sql` fabriquée, `region_origine`,
   `demande.cran`, le test de migration (patron `tests/test_migration_v31.py`).
1. **Amorcer dans le projet** : `creer_copie` à tous les crans (E1, E5, E6, E9), la règle de
   suppression qui lit `region_origine` (E3), la réponse `amorcer` de la prise et son genre de
   demande (E4), l'aperçu.
2. **Entre deux projets** (E7) : l'adressage de la demande, la réponse du responsable source.
3. **Repartir de zéro** (E8), et le témoin de l'annulation.
4. **L'écran**, après la maquette (E10).
5. **La documentation** : `docs/modele-et-droits.md`, `docs/guide-utilisateur.md`,
   `docs/accord-inter.md` (E3), `docs/undo.md` (E8), `CLAUDE.md`.

Chaque commit de code cite `COL-3`. Relecture croisée obligatoire (la 3b touche la règle de
suppression et ouvre un chemin entre projets), par une session qui ne l'a pas écrite, sous les
sept identités de la 3a et une base qui porte trois copies d'un même document, dont une copie
de copie, dans deux projets.

### Les gardes à éprouver par mutants

- l'échelle : à chaque cran, ce qui doit suivre suit et RIEN d'au-dessus ; mutant : un cran
  décalé ;
- `validee` et `verrou_par` ne suivent jamais ; mutant : la ligne de planche entière ;
- la chaîne de `region_origine` : le travail d'une copie INTERMÉDIAIRE compte ; mutant : la
  source directe seule, ou la racine seule ;
- la source 2 : le copieur auteur de tous les attributs supprime seul ; mutant : la source 2
  d'aujourd'hui ;
- aucun événement par région, Ctrl+Z inchangé, pseudonymes inchangés ; mutant : les
  événements recopiés ;
- E4 : un écrivain non propriétaire reçoit une demande ; mutant : `peut_ecrire` ;
- E7 : le demandeur lit « demandé » qu'il existe une source ou non, au bit près (le JSON brut
  des deux réponses égal) ;
- E8 : repartir vers un cran supérieur est refusé ; la règle de suppression s'applique ;
  `verrouillee` reste ;
- la migration : `region_origine` vide, rien d'autre ne change sur la vraie base v31.

### Les passes de QA à écrire

Rédigées, jamais cochées par qui les écrit : **`en-partir-d-un-travail`**, neuve (amorcer à
chaque cran dans le projet, la demande au propriétaire, l'aperçu qui compte ce qui reste,
entre deux projets sous `proprio` et un second responsable, repartir de zéro direct et
demandé) ; `prendre-un-document` rejouée sur le bouton « Copie… » ; `petites-largeurs` et
`preference-de-police` sur l'échelle et l'aperçu.

---

## Les décisions qui restent à Hugo

| | Question | Proposé |
|---|---|---|
| E1 | L'échelle, table par table ; attributs et locuteurs avec les annotations ; la validation ne suit jamais | oui |
| E2 | `region_origine` sur une v32 | oui |
| E3 | Aucun événement recopié ; l'attribution par `region_origine` ; l'accord inter ne suit pas, d'ici la tranche 4 | oui |
| E4 | Dans un projet, en partir suit la règle de `rejoindre` | oui (sinon : personne ne consent) |
| E5 | N'emporter que les termes visibles depuis l'arrivée, et le compter | oui |
| E6 | Les personnages suivent, même entre deux projets | (a) oui |
| E7 | Entre deux projets, la demande ne nomme pas la source ; le serveur l'adresse | (c) |
| E8 | Repartir de zéro : la règle de la suppression, une demande certifiée sinon, un acte | oui |
| E9 | Synchrone, sans spaCy, mesuré au premier commit | oui |
| E10 | L'écran sur maquette, en session dédiée | oui |
