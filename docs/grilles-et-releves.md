# Grilles et relevés — note de cadrage

*Validée par Hugo le 2026-10-14, avant la première ligne de code ; rédigée le même jour depuis
la session dédiée au mode d'annotation, après le calibrage et la maquette. Chantiers : `ANN-6` (le
relevé et son écran), `ANN-7` (les grilles). Cette note fixe le MODÈLE ; elle ne recopie pas la
discussion, qui vit dans les deux fiches.*

Le dépôt est public : aucune grille réelle n'y figure, ni ici, ni dans les tests, ni dans les
exemples. Les grilles citées sont fictives.

## 1. Ce que la note tranche, et dans quel ordre on construit

Quatre tranches, chacune vérifiée par sa revue et ses tests avant la suivante ; `COL-3` (sa
tranche 2) passe avant la première, et prend la migration v30 — le modèle des grilles prendra
la suivante.

1. **Le modèle, sans écran** — ce que décrit cette note : les tables, l'import du tableur avec
   son bilan, les routes et leurs gardes, le découpage des mots, les tests.
2. **La page Annotation**, écrite comme module montable (convention de `static/lib/qui-entre.js`),
   sur le modèle de la maquette.
3. **Le basculement** : les tags, la situation d'une case et le profil d'un personnage
   deviennent des grilles ; la règle de conversion de ce que les stagiaires auront posé en tags
   s'applique.
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

Ce qui n'est PAS un objet de grille : le type de zone, le locuteur et le lieu d'une case (le
premier niveau de la grille des linguistes) sont « pris dans l'outil » ; le doute est fourni
par l'outil à toute grille.

## 3. Les trois formes, et ce que pose chacune

| Forme | Geste | Le relevé porte |
|---|---|---|
| **Simple** | une case à cocher | l'entrée |
| **À variantes** | « une parmi » ; en choisir une autre remplace | l'entrée et SA variante |
| **À qualificatifs** | le phénomène, puis zéro, un ou plusieurs choix de sa liste | l'entrée et SES qualificatifs |

- Une entrée peut demander une **précision libre** (« région à préciser ») : un texte court
  porté par le relevé.
- Une entrée peut demander un **lien vers une autre zone** (le chevauchement de paroles) : le
  relevé désigne la région, l'outil tient le lien ; la référence écrite dans une note
  deviendrait fausse quand l'ordre de lecture change.
- **Un relevé à qualificatifs compte UNE fois son phénomène**, et une fois chacun de ses
  qualificatifs : « emphase par typographie et ponctuation » fait 1 emphase, 1 typographie, 1
  ponctuation. Le guide des linguistes en fait deux tags — **à confirmer par eux** ; le modèle
  sait rendre les deux comptes.
- Une forme nouvelle demande du code, une fois, pour toutes les grilles. Le contenu, lui, est
  libre.

## 4. La cible

Une version de grille DÉCLARE ce qu'elle vise, parmi : `mots` · `bulle` · `cartouche` ·
`texte` · `case` · `personnage` · `detail` · `planche`. L'écran ne propose que cela, depuis la
zone choisie et son contexte (sa case, les personnages et détails de sa case, la planche).

Un relevé porte sur exactement une de ces trois choses :

- **des mots d'une zone de texte** — une région, et un passage (§5) ;
- **une région entière** — case, bulle, cartouche, texte, personnage ou détail ;
- **la planche**.

**Le détail devient un type de région** (`regions.type = 'detail'`), avec un nom libre
(colonne neuve, NULL pour les autres types). Il se trace sur la page Annotation, quelle que soit
la grille active, et toute grille qui vise `detail` l'annote — c'est ce qui rend la zone
« agnostique ». Un **texte hors bulle** tracé au même endroit est une région `texte` : il reçoit
une transcription (`ocr_texte`, comme toute zone de texte), puis ses mots s'annotent. Une zone
tracée sur la page Annotation n'est jamais une case : le découpage reste à l'Atelier.

## 5. Les mots, et ce que devient un passage quand le texte change

**Un passage est une liste de mots**, continue ou non (« ne … pas » : Ctrl+clic, ou « Ajouter
un mot » au doigt). Le relevé stocke, pour chaque mot, son RANG et sa FORME.

**Le découpage en mots est celui de l'outil, pas celui du moteur de langue.** Un cœur pur
(`mots.py`) et son jumeau navigateur (`static/lib/mots.js`), accordés par une table de cas lue
des deux côtés — le patron de `casse.py` / `casse.js`. Trois raisons :

- le relevé doit exister **là où spaCy est absent** (il est optionnel) ;
- un mot désigné à l'écran doit être le mot stocké : un seul découpage, le même partout ;
- changer de modèle de langue (`sm` → `lg`) ne doit déplacer aucun relevé.

Règle : espaces, ponctuation à part, clitiques élidés détachés (`j'`, `c'`, `qu'`…). Le
croisement avec le lemme et la catégorie (tranche 4) se fait en ALIGNANT ces mots sur les
`tokens` du moteur, quand il est là.

**Ré-ancrage — le patron de `token_correction`** (`database._reancrer_corrections`). Quand la
transcription d'une zone change, chaque passage est réaligné (difflib) entre l'ancien et le
nouveau découpage :

- tous ses mots retrouvés, même déplacés → le passage suit ;
- un de ses mots disparu ou changé → le relevé passe **« à revoir »**, garde ses anciennes
  formes pour qu'on voie ce qu'il désignait, et n'est jamais perdu ni déplacé en silence.

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
- **Une coquille** (définition, exemple) se corrige à l'écran sans nouvelle version : elle ne
  touche aucun relevé.

## 7. Le tableur

Une grille s'écrit dans un tableur, BéDéditeur la vérifie et la garde (`ANN-7`). Format proposé,
CSV point-virgule comme `tools/vocabulaire-modele.csv`, une ligne par entrée ou par variante :

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

Les listes de qualificatifs et la déclaration de la cible tiennent dans deux petits onglets, ou
deux fichiers. **L'import rend un bilan avant de publier** — ajouts, renommages, et pour chaque
entrée disparue qui a des relevés : « retirer, ou fusionner dans… ». BéDéditeur réexporte la
grille au même format, identifiants compris, et en produit le guide (§ « Le guide découle de la
grille », `ANN-7`). L'exemple du dépôt est une grille fictive ; la grille des linguistes reste
sur le poste et en production.

## 8. Le doute

- Il porte sur **un relevé**, toujours avec un commentaire court ; on y répond (un fil de
  messages, signés et datés), puis on le **lève** en gardant, en changeant ou en retirant le
  relevé. La levée est un acte signé, elle aussi.
- N'importe qui peut lever un doute, et pas seulement un responsable (décision de Hugo).
- Une liste « À revoir » réunit les doutes ouverts d'une planche, et les relevés mis de côté par
  le ré-ancrage (§5), qui sont une autre sorte de « à revoir ».
- **Sous un compte collectif, on ne sait pas qui doute** : le login est partagé. Le fil le dit
  (`utilisateur.nature = 'collectif'`, `AUTH-6`), sans rien inventer.

## 9. La passe : « appliquée à cette zone »

Une ligne (zone, grille, rubrique ou toute la grille, qui, quand) dit que la zone a été
regardée avec cette grille. C'est ce qui distingue « 0 élision » de « pas encore regardé ». Elle
ne dépend d'aucun relevé, et se retire. Le parcours « à faire seulement » de « Suivante » la lit.

## 10. Qui voit, qui écrit

- **Une grille appartient à un projet** (`COL-3`) ; ses responsables la créent, l'importent et
  la publient (`peut_gerer_projet`), et l'administrateur passe outre. Aucune validation
  préalable : l'administrateur trie après coup (`ANN-7`).
- **Elle s'active sur un projet** : toutes les collections du projet comptent avec elle. Un
  album n'a qu'un projet (le rangement ne traverse pas, `COL-3`) : les grilles actives sur un
  album sont celles de son projet.
- **Voir le plan d'une grille** : quiconque lit un album du projet où elle est active — sans
  quoi un annotateur qui a un accès de collection sans être membre du projet ne verrait pas la
  grille qu'il doit appliquer. **À trancher** (question ouverte d'`ANN-7` : le plan d'une grille
  réservée peut révéler une étude en cours).
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
  profond de l'annulation doit les emporter — le défaut ouvert d'`ANN-6` sur le locuteur et la
  situation est de la même famille, et se ferme en même temps.

## 12. Ce que la tranche 1 ne fait pas

- Aucun écran : ni la page Annotation, ni le guide produit, ni le bilan d'import à l'écran
  (l'import se fait par l'outil en ligne de commande et par une route, comme
  `tools/importer_vocabulaire.py`).
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

Encore ouvert :

5. **Le compte d'un relevé à qualificatifs** (§3) : un phénomène, plus un par qualificatif — à
   confirmer par les linguistes, sans effet sur le modèle.
6. **Le nom de la passe** : « appliquée » à l'écran, en attendant mieux (§9).
7. **Le premier projet de la production** : celui où s'importe la grille des linguistes. Décidé
   au déploiement ; la tranche 1 se joue en local.
