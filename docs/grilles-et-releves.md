# Grilles et relevés — note de cadrage

*Validée par Hugo le 2026-10-14, avant la première ligne de code ; rédigée le même jour depuis
la session dédiée au mode d'annotation, après le calibrage et la maquette. Chantiers : `ANN-6` (le
relevé et son écran), `ANN-7` (les grilles). Cette note fixe le MODÈLE ; elle ne recopie pas la
discussion, qui vit dans les deux fiches.*

*Mise à jour le 2026-10-25, avec la tranche 1 : des décisions de la séance du 2026-10-22
(`ANN-7`, Q1 à Q9 ; `ANN-6`, la maquette v3) et du cadrage de la tranche
(`docs/ann7-tranche1-cadrage.md`, G1 à G20, « oui à tout »). Ce qui a changé depuis la
validation est dit sur place, daté. Le format du tableur, pour qui le remplit :
`docs/import-grille.md`.*

Le dépôt est public : aucune grille réelle n'y figure, ni ici, ni dans les tests, ni dans les
exemples. Les grilles citées sont fictives.

## 1. Ce que la note tranche, et dans quel ordre on construit

Quatre tranches, chacune vérifiée par sa revue et ses tests avant la suivante ; `COL-3` (sa
tranche 2) passe avant la première, et prend la migration v30 — le modèle des grilles prendra
la suivante.

1. **Le modèle, sans écran** — ce que décrit cette note : les tables, l'import du tableur avec
   son bilan, les routes et leurs gardes, le découpage des mots, les tests. Migration **v37**
   (après la v36 de la 3b de `COL-3`) ; seize tables neuves et `regions.nom`.
2. **La page Annotation**, écrite comme module montable (convention de `static/lib/qui-entre.js`),
   sur le modèle de la maquette.
3. **Le basculement** : les tags, la situation d'une case et le profil d'un personnage
   deviennent des grilles — NEUVES, sans conversion (Q3, 2026-10-22) : les tables d'aujourd'hui
   sont retirées, les Ctrl+Z d'avant le basculement sont coupés. Les stagiaires ne posent aucun
   tag d'ici là, et attendent la grille « Lieux » pour les lieux (Q9 ; G20 c, 2026-10-25).
4. **Ce qui compte et ce qui sort** : l'Exploration, la Recherche, les exports, la voie du
   dépôt — avec une relecture croisée.

Le catalogue (« Partager », dériver, proposer) n'est pas dans la tranche 1 : la grille y naît
pourtant avec ce qu'il lui faudra (un propriétaire, des versions, des identifiants stables),
pour que le catalogue n'oblige à rien migrer.

## 2. Les objets

| Objet | Ce que c'est | On y pose quelque chose ? |
|---|---|---|
| **Grille** | Un vocabulaire nommé, propriété d'un projet ; ouverte ou fermée | non |
| **Version** | Un état daté de la grille, brouillon puis publié, alors figé | non |
| **Rubrique** | Range des entrées, s'imbrique, ordonnée (niveau, famille…) | non |
| **Entrée** | Ce qu'on pose : simple, à variantes, ou à qualificatifs | oui |
| **Variante** | L'une des formes d'une entrée à variantes (« une parmi ») | — (choisie) |
| **Liste de qualificatifs** | Une liste partagée par plusieurs entrées (les procédés, les indices…) | — (cochés) |
| **Activation** | Un projet emploie une grille, dans une version donnée | non |
| **Relevé** | Une entrée posée sur une cible, par quelqu'un, dans une version | — |
| **Doute** | Une demande de relecture sur UN relevé : un fil de messages, une levée | — |
| **Passe** | « Grille appliquée à cette zone » : regardée, même sans relevé | — |

Ce qui n'est PAS un objet de grille : le type de zone et le locuteur (le personnage qui parle)
sont « pris dans l'outil » ; le doute est fourni par l'outil à toute grille. **Depuis le
2026-10-22**, la SORTE de locuteur (identifié, collectif, narrateur…) est une entrée de la
grille des linguistes, posée sur toute la zone, et le LIEU d'une case aura sa propre grille
(« Lieux ») : ni l'un ni l'autre n'est plus « pris dans l'outil ».

## 3. Les trois formes, et ce que pose chacune

| Forme | Geste | Le relevé porte |
|---|---|---|
| **Simple** | une case à cocher | l'entrée |
| **À variantes** | « une parmi » ; en choisir une autre remplace | l'entrée et SA variante |
| **À qualificatifs** | le phénomène, puis zéro, un ou plusieurs choix de sa liste | l'entrée et SES qualificatifs |

- Une entrée peut demander une **précision libre** (« région à préciser ») : un texte court
  porté par le relevé.
- Une entrée peut demander un **lien vers une autre zone** (le chevauchement de paroles) : le
  relevé désigne la région — du MÊME album (G4) —, l'outil tient le lien ; la référence écrite
  dans une note deviendrait fausse quand l'ordre de lecture change. **Si la région désignée
  disparaît** (tranché le 2026-10-22), le relevé reste, passe « à revoir », garde le texte de
  la région qu'il désignait ; Ctrl+Z de la suppression le rattache.
- **Un relevé à qualificatifs compte UNE fois son phénomène.** Les linguistes ont répondu le
  2026-10-22 que « emphase par typographie et ponctuation » fait DEUX emphases ; Hugo a tranché
  le même jour que **le modèle ne change pas** : la grille est une donnée, et celle des
  linguistes écrira l'emphase par manière (deux entrées, ou une entrée à variantes posée deux
  fois). L'outil DIT comment chaque forme compte (`docs/import-grille.md`), pour que l'auteur
  d'une grille choisisse en connaissance de cause.
- **« À compléter »** a deux causes : une entrée dont la forme change entre deux versions
  (avec la montée de version) ; et, tranché sur la maquette v3 (2026-10-22), une précision ou
  un lien que l'entrée attend et que le relevé ne porte pas.
- Une forme nouvelle demande du code, une fois, pour toutes les grilles. Le contenu, lui, est
  libre.

## 4. La cible

Une version de grille DÉCLARE ce qu'elle vise (« Porte sur »), parmi neuf sortes : `mots` ·
`bulle` · `cartouche` · `texte` · `case` · `personnage` (la BOÎTE dessinée, une région) ·
`detail` · `planche` (la SURFACE, `IMG-2`, 2026-10-16 : pour une double page, la double page) ·
`entite` (le personnage du REGISTRE, Q4, 2026-10-22). Plusieurs types de zone se combinent
(`bulle | cartouche | texte` : toute la zone, l'une des trois) ; les mots, la planche et
l'entité vont seuls. **Une entrée peut déclarer SA cible** (colonne `cible`, tranché le
2026-10-22) : la sorte de locuteur se pose sur toute la zone dans une grille qui vise des mots ;
sans cible, l'entrée prend celle de sa version.

Un relevé porte sur exactement une de ces choses :

- **des mots d'une zone de texte** — une région, et un passage (§5) ;
- **une région entière** — case, bulle, cartouche, texte, personnage ou détail ;
- **la planche** ;
- **l'entité du registre** — qui attend l'étage de projet des personnages (tranche 4 de
  `COL-3`) : l'import accepte une entrée qui la vise, aucun relevé ne s'y pose encore (G3).

**La cardinalité se déclare dans le tableur** (Q6, 2026-10-22) : `une` ou `plusieurs` ; vide,
`plusieurs` sur des mots, `une` sur une région entière, la planche ou l'entité. Un second
relevé d'une entrée `une` sur la même cible est refusé ; à l'écran, en choisir une autre
remplace.

**Le détail devient un type de région** (`regions.type = 'detail'`), avec un nom libre
(`regions.nom`, née avec la v37, NULL pour les autres types ; le type lui-même vient avec
l'écran qui le trace, et la région `detail` restera hors des exports jusqu'à la tranche 4,
G17). Il se trace sur la page Annotation, quelle que soit
la grille active, et toute grille qui vise `detail` l'annote — c'est ce qui rend la zone
« agnostique ». Un **texte hors bulle** tracé au même endroit est une région `texte` : il reçoit
une transcription (`ocr_texte`, comme toute zone de texte), puis ses mots s'annotent. Une zone
tracée sur la page Annotation n'est jamais une case : le découpage reste à l'Atelier.

## 5. Les mots, et ce que devient un passage quand le texte change

**Un passage est une liste de mots**, continue ou non (« ne … pas » : Ctrl+clic, ou « Ajouter
un mot » au doigt). Le relevé stocke, pour chaque mot, son RANG et sa FORME.

**Le découpage en mots est celui de l'outil, pas celui du moteur de langue.** Un cœur pur
(`mots.py`) et sa table de cas (`tests/cas-mots.json`) ; **pas de jumeau navigateur** (G11,
2026-10-25) : la route `GET /api/regions/{id}/mots` rend le découpage, et la page Annotation
dessine depuis elle — un découpage, à un endroit. Trois raisons :

- le relevé doit exister **là où spaCy est absent** (il est optionnel) ;
- un mot désigné à l'écran doit être le mot stocké : un seul découpage, le même partout ;
- changer de modèle de langue (`sm` → `lg`) ne doit déplacer aucun relevé.

Règle : espaces, ponctuation à part (une suite d'un même signe, « !!! », ne fait qu'un mot),
clitiques élidés détachés (`j'`, `c'`, `qu'`…) ; « aujourd'hui », les mots à tiret, la coupure
de fin de ligne restent entiers — ces cas sont tranchés par la table, **à confirmer avec les
linguistes** (G11). Le croisement avec le lemme et la catégorie (tranche 4) se fait en
ALIGNANT ces mots sur les `tokens` du moteur, quand il est là.

**Ré-ancrage — le patron de `token_correction`** (`database._reancrer_corrections`). Quand la
transcription d'une zone change, chaque passage est réaligné (difflib) entre l'ancien et le
nouveau découpage :

- tous ses mots retrouvés, même déplacés → le passage suit ;
- un de ses mots disparu ou changé → le relevé passe **« à revoir »**, garde ses anciennes
  formes pour qu'on voie ce qu'il désignait, et n'est jamais perdu ni déplacé en silence.

L'ancien découpage n'est pas en base : chaque relevé garde le texte de son ancrage
(`releve.texte_ancre`). En tranche 1, un relevé dont un mot ne se retrouve pas n'est pas
réécrit : il reste ancré sur l'ancien texte, ce qui le dit « à revoir », l'écran lit où chacun
de ses mots est aujourd'hui, et un Ctrl+Z du texte le rend normal sans rien écrire. L'état
« à revoir » n'est pas une colonne : il se DÉRIVE (`releves_effectifs`, G2).

## 6. Versions et identifiants

- **Chaque objet de grille porte un identifiant stable et invisible** (`cle`), fourni par le
  tableur. Sans lui, un libellé renommé se lirait comme une suppression suivie d'un ajout.
- **Une version publiée est figée.** On prépare la suivante (brouillon), on la publie. Une
  version est un INSTANTANÉ COMPLET (rubriques, entrées, variantes, listes) : une lecture faite
  en v1 se relit en v1 quand la grille en est à la v5, sans reconstituer un état passé.
- **Un relevé dit dans quelle version il a été posé**, et un projet reste sur sa version jusqu'à
  ce qu'il décide d'en changer (`ANN-7`). Effet de chaque changement entre deux versions, par
  la `cle` : renommer ou retoucher une définition n'abîme rien ; déplacer change les comptes par
  rubrique, passé compris ; supprimer une entrée employée est interdit (elle devient
  « retirée ») ; fusionner reporte les relevés, tracé ; scinder met les relevés « à revoir » ;
  changer de forme met les relevés incomplets « à compléter ». **En tranche 1, la montée de
  version d'un projet n'existe pas** : une seule version publiée par grille suffit à commencer.
- **Une coquille** (définition, exemple, piège) se corrige sans nouvelle version, par un
  responsable, au journal (tranché le 2026-10-22 ; sa route dès la tranche 1, G15) : elle ne
  touche aucun relevé.
- **Une grille ouverte** (les tags libres) n'a qu'une version, vivante, qui s'enrichit en
  posant (G14) ; elle n'est pas partageable tant qu'on ne la fige pas en grille fermée.

## 7. Le tableur

Une grille s'écrit dans un tableur, BéDéditeur la vérifie et la garde (`ANN-7`). Le format
de la tranche 1 — deux CSV point-virgule, et ce que chaque colonne dit — est écrit pour qui
remplit le tableur dans `docs/import-grille.md` ; le résumé, une ligne par entrée ou par
variante :

| Colonne | Rôle |
|---|---|
| `cle` | identifiant stable de l'entrée (obligatoire) |
| `rubrique` | chemin, du plus large au plus fin : `3 Morphosyntaxe > Verbe` |
| `rubrique_cle` | identifiant stable de chaque étage du chemin |
| `forme` | `simple` · `variantes` · `qualificatifs` |
| `libelle` | ce qu'on lit à l'écran |
| `variante_cle`, `variante` | une ligne par variante, pour une entrée à variantes |
| `structure` | la structure, quand la grille en donne une (interrogatives) |
| `liste` | la liste de qualificatifs d'une entrée à qualificatifs |
| `definition`, `exemples`, `piege` | ce que montre la ligne du guide |
| `precision` | libellé d'une précision libre, vide sinon |
| `lien` | `oui` pour une entrée qui désigne une autre zone |
| `cible` | facultative : la cible propre de l'entrée (2026-10-22) |
| `cardinalite` | facultative : `une` · `plusieurs` (Q6, 2026-10-22) |

Les listes de qualificatifs tiennent dans un second fichier (`grille-listes-qualificatifs.csv`)
; la déclaration (nom, ouverte ou fermée, « Porte sur », note de version) passe en arguments de
l'outil (G13 : deux CSV, pas de classeur). Une anomalie de structure refuse le fichier ENTIER
(G12). **L'import rend un bilan avant de publier** — ajouts, renommages, et pour chaque
entrée disparue qui a des relevés : « retirer, ou fusionner dans… ». BéDéditeur réexporte la
grille au même format, identifiants compris, et en produit le guide (§ « Le guide découle de la
grille », `ANN-7`). L'exemple du dépôt est une grille fictive ; la grille des linguistes reste
sur le poste et en production.

## 8. Le doute

- Il porte sur **un relevé**, toujours avec un commentaire court ; on y répond (un fil de
  messages, signés et datés), puis on le **lève** en gardant, en changeant ou en retirant le
  relevé. La levée est un acte signé, elle aussi.
- N'importe qui peut lever un doute, et pas seulement un responsable (décision de Hugo) —
  c'est-à-dire quiconque ÉCRIT dans l'album (G20 a, 2026-10-25). Un seul doute OUVERT à la
  fois par relevé ; un second « ? » ajoute un message au fil.
- Une liste « À revoir » réunit les doutes ouverts d'une planche, et les relevés mis de côté par
  le ré-ancrage (§5), qui sont une autre sorte de « à revoir ».
- **Sous un compte collectif, on ne sait pas qui doute** : le login est partagé. Le fil le dit
  (`utilisateur.nature = 'collectif'`, `AUTH-6`), sans rien inventer.

## 9. La passe : « terminée »

Une ligne (zone, grille, rubrique ou toute la grille, qui, quand) dit que la zone a été
regardée avec cette grille. C'est ce qui distingue « 0 élision » de « pas encore regardé ». Elle
ne dépend d'aucun relevé, et se retire (« Rouvrir »). Le parcours « à faire seulement » de
« Suivante » la lit. Le mot est « terminée » (maquette v3, 2026-10-22).

**La passe est COMMUNE et signée** (Q7, 2026-10-22) : marquée par l'un, elle vaut pour tous et
dit qui, quand ; on se partage les zones. **Les valeurs uniques** — la variante choisie, les
qualificatifs, la précision, le lien, le passage, la levée d'un doute, la passe — refusent une
écriture périmée par le 409 de `CONC-3` : Q7 disait « une version de ligne » ; le mécanisme
retenu est la VALEUR vue (G1, 2026-10-25), qui donne le même refus sans colonne à incrémenter.

## 10. Qui voit, qui écrit

- **Une grille appartient à un projet** (`COL-3`) ; ses responsables la créent, l'importent et
  la publient (`peut_gerer_projet`), et l'administrateur passe outre. Aucune validation
  préalable : l'administrateur trie après coup (`ANN-7`).
- **Elle s'active sur un projet** : toutes les collections du projet comptent avec elle. Un
  album n'a qu'un projet (le rangement ne traverse pas, `COL-3`) : les grilles actives sur un
  album sont celles de son projet. **Une collection peut MASQUER une grille active** (Q1,
  2026-10-22) — un filtre d'ÉCRAN, pas une garde : aucun relevé ne porte de `collection_id`,
  le serveur n'en refuse aucun selon la collection d'où l'on vient, et ce qui est posé reste
  lisible. Le masque se règle par le propriétaire de la collection (G7). Désactiver une grille
  ne supprime aucun relevé : ils restent, en lecture.
- **Voir le plan d'une grille** : quiconque lit un album du projet où elle est active — sans
  quoi un annotateur qui a un accès de collection sans être membre du projet ne verrait pas la
  grille qu'il doit appliquer. **Tranché par Hugo le 2026-10-14** (§13), en connaissance du
  risque que portait la question d'`ANN-7` : le plan d'une grille réservée peut révéler une
  étude en cours, et il se voit ainsi hors du cercle des membres du projet. **Et aussi**
  (G5, 2026-10-25) : les membres du projet de la grille, même sans album lu, et quiconque lit
  un album portant un relevé de la grille, même désactivée (`Portee.clause_grille`). Le
  brouillon reste chez qui gère le projet.
- **Poser, modifier, retirer un relevé** : écrire dans l'album (`clause_album(ecriture=True)`,
  par l'accesseur gardé de la région). Lire un relevé : lire l'album.
- **Créer une zone `detail` ou `texte`** depuis la page Annotation : écrire dans l'album, comme
  tracer une région dans l'Atelier.
- Le cliquet de `tests/test_autorisation.py` s'applique à chaque route neuve, celui des sorties
  (`tests/test_sorties_identite.py`) aussi : un doute porte des logins.

## 11. Journal, annulation, suppression

- Chaque acte sur un relevé, un message de doute, une levée, une passe, une zone tracée est
  **journalisé** (A3, l'agent courant).
- **Ctrl+Z** annule poser, modifier et retirer un relevé, et tracer une zone ; un message de
  doute ne s'annule pas (il se lève ou se répond).
- **Supprimer une région supprime ses relevés** (CASCADE), et l'annuler les rend : l'instantané
  profond de l'annulation les emporte, avec leurs doutes et les passes de la région.
- **Jamais de CASCADE sur la planche** (Q5, 2026-10-22) : un relevé de surface fait échouer la
  suppression d'une planche par un chemin qui l'oublierait ; les chemins qui suppriment une
  planche le retirent d'abord. **À l'assemblage d'une double page** (`IMG-2`), les relevés de
  la planche absorbée seront REPORTÉS sur la surface, avec une trace : `IMG-2`, arrivant
  second, écrira ce report.
- La règle « personne d'autre n'y a travaillé » de la suppression directe compte les relevés,
  les doutes et les passes ; « repartir de zéro » les retire (tranché le 2026-10-22).

## 11 bis. Les relevés aux crans de copie (tranché le 2026-10-22)

Une copie sœur amorcée au cran `annotations` (`COL-3`, 3b) emporte les relevés de sa source
**si leur grille est active dans le projet d'arrivée**, quelle que soit la version ; sinon ils
sont COMPTÉS dans l'aperçu, jamais posés et invisibles. Les passes suivent, les doutes non
(une conversation de l'équipe source). Entre deux projets, l'auteur d'un relevé recopié
arrive vide (G9). En tranche 1 une grille n'est active que dans son projet : entre deux
projets, rien ne suit encore. Les zones `detail` et `texte`, des régions, partent au cran
`decoupage` ; le NOM d'un détail ne suit qu'au cran `annotations` (Hugo, 2026-10-30) : il dit ce
que l'image montre, ce qui est déjà de l'interprétation. Un détail sans nom reste valide.

## 12. Ce qui n'existe pas encore

La page Annotation (tranche 2 ; ses gestes : `guide-utilisateur.md`, § Annotation) pose, doute,
parcourt et relit. Restent à venir :

- Le bilan d'import à l'écran, et l'écran des grilles dans la fiche du projet : importer,
  publier et activer passent par l'outil en ligne de commande et par une route, comme
  `tools/importer_vocabulaire.py`.
- Ni le catalogue, ni la montée de version d'un projet, ni la dérivation.
- Ni le basculement des tags et des attributs, ni la conversion.
- Rien dans la Recherche, l'Exploration ou les exports : un relevé ne SORT par aucune voie avant
  la tranche 4, et le cliquet des sorties le vérifie.

## 13. Ce qui est tranché, et ce qui reste ouvert

Tranché par Hugo le 2026-10-14, à la lecture de cette note :

1. **Une version est un instantané complet** (§6), plutôt qu'une table de différences : plus de
   lignes, aucune reconstitution d'un état passé.
2. **Le découpage des mots est celui de l'outil** (§5), plutôt que les `tokens` du moteur de
   langue.
3. **Le plan d'une grille non partagée se voit de quiconque lit un album du projet où elle est
   active** (§10). L'autre voie fermait la grille à des annotateurs qui ont un accès de
   collection sans être membres du projet.
4. **L'ordre** : `COL-3` (fusion de sa tranche 1, puis sa tranche 2) passe d'abord ; la tranche
   1 du modèle suit, sur la migration d'après.

Tranchés depuis (2026-10-22) :

5. **Le compte d'un relevé à qualificatifs** (§3) : le modèle ne change pas, la grille des
   linguistes écrira l'emphase par manière.
6. **Le nom de la passe** : « terminée » (§9, maquette v3).
7. **Le premier projet de la production** : « Principal » ou « LingApp », choisi au
   déploiement, sa gestionnaire responsable (Q9 d'`ANN-7`).
