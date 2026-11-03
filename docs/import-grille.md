# Importer une grille d'annotation — le tableur

*ANN-7. Le format que lisent l'outil d'import (`tools/importer_grille.py`) et la route
`POST /api/projets/{id}/grilles/import`, et que rend `GET /api/grilles/{id}/versions/{n}/tableur`.
Les cœurs sont `grille_import.py` (la lecture, la validation, le bilan) et `grille_tableur.py`
(les deux formes, les mots, le classeur). Le gabarit en mots a été tranché par Hugo sur
maquette le 2026-11-03. Ce qu'une grille peut demander, et ce qu'elle ne peut pas :
[ce-qu-une-grille-peut-demander.md](ce-qu-une-grille-peut-demander.md).*

Une grille s'écrit dans un tableur ; BéDéditeur la vérifie ENTIÈRE, rend un bilan, et la
garde en brouillon jusqu'à ce qu'on la publie. Rien de la grille n'est dans le code : tout ce
qui la fait est dans le tableur.

## Deux formes, qui se lisent toutes deux

- **Le classeur `.xlsx`, en mots** — le gabarit fait pour une personne qui n'a jamais vu
  l'outil. Ses titres sont les QUESTIONS (« 4. Ce qu'on choisit »), ses cellules des réponses
  en mots (« une variante », « la case »), avec des listes déroulantes, l'aide de chaque
  colonne en commentaire sur son titre, et une mise en forme qui passe en rouge une réponse
  que l'import refuserait. On l'obtient en réexportant une grille (`GET …/tableur`), et on le
  renvoie tel quel à l'import.
- **Deux CSV, en mots machine** — la forme de l'outil en ligne de commande, du modèle fictif et
  des grilles écrites avant le gabarit : **séparateur `;`**, **UTF-8** avec ou sans BOM,
  en-tête obligatoire. `?format=csv` les rend, dans un zip.

Les deux se MÊLENT sans peine : une colonne se reconnaît à son nom machine (`forme`) comme à
son titre (« 4. Ce qu'on choisit », avec ou sans son numéro, accents et casse indifférents),
une valeur en mots machine (`variantes`) comme en mots (« une variante »). L'ordre des
colonnes est libre, une colonne en trop est ignorée. Une ligne qui commence par `#` est
ignorée partout, en-tête compris : on y écrit une consigne. Le `.ods` n'est pas lu.

Un modèle FICTIF, qui fait jouer toutes les possibilités : `tools/grille-modele.csv` et
`tools/grille-modele-listes-qualificatifs.csv`. C'est aussi la grille que chaque bac à sable
reçoit à sa naissance, sous le nom « Grille d'exemple », et la feuille « Exemple » du
classeur : le changer change celle des bacs à sable à venir, jamais celle de ceux qui
existent.

## Le classeur

| Feuille | Ce qu'elle porte |
|---|---|
| « 1. La grille » | la déclaration : en colonne A le libellé, en colonne B la réponse — « Nom de la grille », « Fermée ou ouverte » (`fermée` · `ouverte`), « Porte d'ordinaire sur », « Note de version » |
| « 2. Les entrées » | les entrées et leurs variantes (ci-dessous) |
| « 3. Listes à cocher » | les listes de qualificatifs : « Liste », « Case », « Définition (au survol) » |
| « Exemple » | le modèle fictif rempli ; l'import ne la lit pas |

Une feuille se reconnaît à un mot de son nom (« entrées », « liste », « grille ») ; une
feuille « Exemple… » et les feuilles inconnues sont ignorées. Une feuille cachée, « Choix »,
porte les valeurs des listes déroulantes.

## Le fichier des entrées

Une ligne par **entrée** (ce qu'on pose), et, sous une entrée à variantes, une ligne par
**variante**.

| Titre du classeur | Colonne machine | Ce qu'elle dit |
|---|---|---|
| « 1. Rubrique » | `rubrique` | où l'entrée se range, du plus large au plus fin, séparé par `>` : `Niveau 3. Morphosyntaxe > Verbe`. Vide : dans aucune rubrique |
| « Entrée » | `libelle` | ce qu'on lit à l'écran (obligatoire sur une ligne d'entrée) |
| « Variante » | `variante` | le libellé d'une variante, sur sa ligne |
| « 2. Se pose sur » | `cible` | facultative : sur quoi CETTE entrée se pose, quand ce n'est pas ce que dit « Porte sur » |
| « 3. Combien de fois » | `cardinalite` | facultative : « une seule » (`une`) ou « plusieurs » ; vide, la règle ordinaire |
| « 4. Ce qu'on choisit » | `forme` | « rien » (`simple`) · « une variante » (`variantes`) · « des cases d'une liste » (`qualificatifs`) — obligatoire |
| « Liste à cocher » | `liste` | pour une entrée à qualificatifs : la liste où l'on coche, par son nom ou son identifiant |
| « 5. Champ à écrire » | `precision` | le libellé d'un petit champ libre à remplir (« région ») ; vide, aucun |
| « 6. Autre zone » | `lien` | « oui » quand l'entrée désigne une autre zone (un chevauchement) ; vide ou « non » sinon |
| « Définition », « Structure », « Exemples », « Piège » | `definition`, `structure`, `exemples`, `piege` | ce que dira le guide — de l'entrée, ou de la variante sur sa ligne. Plusieurs exemples : un par ligne dans la cellule, ou séparés par ` \| ` |
| « Identifiant » | `cle` | l'identifiant FIXE de l'entrée, gris dans le classeur (ci-dessous) |
| « Identifiant de variante » | `variante_cle` | celui d'une variante, sur sa ligne |
| « Identifiant de rubrique » | `rubrique_cle` | celui de chaque étage de la rubrique, autant d'étages, même séparateur : `niveau-3 > verbe` |

Obligatoires dans l'en-tête : la forme et le libellé. L'identifiant ne l'est plus.

### Une ligne de variante

Elle porte le libellé de la variante, et laisse **vides** les colonnes propres à l'entrée
(rubrique, libellé, forme, liste, champ, autre zone, cible, combien de fois). Elle appartient à
l'entrée dont elle répète l'identifiant — ou, si elle n'en porte pas, à **l'entrée du dessus**
(la dernière ligne d'entrée avant elle) : c'est la forme du classeur, où l'on écrit les
variantes juste sous leur entrée. Si l'on y a recopié les colonnes de l'entrée à l'identique —
en tirant une cellule vers le bas —, l'import l'accepte ; une valeur DIFFÉRENTE de celle de
l'entrée est une anomalie. Elle peut porter sa propre définition, sa structure, ses exemples,
son piège.

### Les identifiants

L'identifiant d'une entrée — d'une variante, d'une rubrique, d'une liste, d'un qualificatif —
ne change pas quand on renomme : c'est grâce à lui qu'un renommage reste un renommage, et pas
une entrée supprimée puis une autre ajoutée. **Il est facultatif à la création** (tranché le
2026-11-03) : la colonne grise du classeur peut être vide. Ce qui en manque se reçoit du NOM,
dans cet ordre :

1. un identifiant ÉCRIT est gardé tel quel, et aucun autre objet ne le prend ;
2. sans identifiant, l'objet REPREND celui de l'objet de même nom dans la version à laquelle
   l'import compare (même libellé ; pour une rubrique, même chemin ; pour une variante ou une
   case, sous la même entrée ou la même liste) ;
3. sinon il est DÉRIVÉ du libellé : sans accents, en minuscules, lettres et chiffres gardés,
   tout le reste devenu un tiret, au plus 48 caractères — « Écho lointain » → `echo-lointain`,
   « cœur » → `coeur` —, suffixé `-2`, `-3`… s'il est déjà pris, par le fichier ou par la
   version de référence (un nouveau venu ne passe jamais pour un renommage).

Le même fichier, comparé à la même version, rend les mêmes identifiants. Le bilan dit ceux
qu'il a reçus (`identifiants_deduits`), et le réexport les écrit : un classeur réexporté ne
dérive plus rien. Une entrée née EN POSANT dans une grille ouverte a la clé de son libellé
(`database.cle_tag`), une autre règle — l'étape 2 la reprend quand le fichier porte son nom.

### Les cibles

| En mots | Machine | Ce qu'on désigne |
|---|---|---|
| « des mots » | `mots` | des mots d'une bulle, d'un cartouche ou d'une zone de texte — le découpage de l'outil |
| « bulle », « cartouche », « texte hors bulle », « la case », « boîte de personnage », « détail d'image » | `bulle`, `cartouche`, `texte`, `case`, `personnage`, `detail` | une région ENTIÈRE de ce type |
| « la planche » | `planche` | la planche entière (la surface ; pour une double page, la double page) |
| « l'entité du registre » | `entite` | le personnage du registre — **aucun relevé ne s'y pose encore** (il attend l'étage de projet des personnages) |

**Plusieurs cibles** s'écrivent séparées par une virgule, « ou », ou ` | ` — « bulle, cartouche
ou texte hors bulle », `bulle | cartouche | texte` : toute la zone, l'une des trois. Seuls des
types de zone se combinent entre eux : « des mots, la case » ne veut rien dire, et la planche
comme l'entité vont seules. Un détail se trace dans une case, sur la page Annotation
(« Détail d'image ») ; il ne sort d'aucun export avant la tranche 4.

« **Porte sur** » est la cible des entrées qui ne disent pas la leur ; elle se déclare (ci-dessous).

### La cardinalité

Vide, elle prend la règle ordinaire : **plusieurs** sur des mots (deux élisions dans une
bulle), **une** sur une région entière ou la planche (un seul registre par bulle). « une
seule » refuse un second relevé de la même entrée sur la même cible : à l'écran, en choisir
une autre remplace.

## Les trois formes, et ce que chacune compte

| Forme | Le geste | Ce que compte un relevé |
|---|---|---|
| « rien » (`simple`) | on pose l'entrée, ou non | une occurrence de l'entrée |
| « une variante » (`variantes`) | on pose l'entrée et on choisit **UNE** de ses variantes | une occurrence de l'entrée, et de sa variante |
| « des cases d'une liste » (`qualificatifs`) | on pose l'entrée et on coche **zéro, un ou plusieurs** choix d'une liste PARTAGÉE | **UNE** occurrence de l'entrée, quel que soit le nombre de qualificatifs cochés |

Le dernier point décide de la forme. Un mot coché « lexique » et « graphie » sous une entrée à
qualificatifs fait UNE occurrence, pas deux. Si deux choix doivent compter pour deux, la
grille écrit deux entrées (« emphase par typographie », « emphase par ponctuation »), ou une
entrée à variantes posée deux fois. Le modèle ne change pas selon la grille : c'est l'auteur
de la grille qui choisit, en connaissant cette règle (tranché par Hugo le 2026-10-22).

## Le fichier des listes

Une ligne par qualificatif.

| Titre du classeur | Colonne machine | Ce qu'elle dit |
|---|---|---|
| « Liste » | `liste` | le nom de la liste — ce que nomme la colonne « Liste à cocher » d'une entrée |
| « Case » | `libelle` | le libellé du qualificatif (obligatoire) |
| « Définition (au survol) » | `definition` | sa définition |
| « Identifiant de liste » | `liste_cle` | l'identifiant fixe de la liste |
| « Identifiant » | `cle` | l'identifiant fixe du qualificatif |

Il faut le nom de la liste ou son identifiant. Une liste sert à plusieurs entrées : c'est ce
qui la rend PARTAGÉE.

## La déclaration

Le nom, la nature (fermée ou ouverte), « Porte sur » et la note de version se disent dans la
feuille « 1. La grille » du classeur, ou en arguments de l'outil (en champs du formulaire de
la route) — les deux CSV n'ont pas de feuille pour eux. **La feuille remplit ce que les
arguments laissent vide ; un argument donné l'emporte sur elle** — on réimporte le classeur
d'une grille sous un autre nom pour la DÉRIVER —, et le bilan le dit (« À savoir »). Pour une
version suivante, le nom et la nature sont ceux de la grille : un autre nom dans la feuille
est dit et ignoré, une autre NATURE est une anomalie.

- `--nom` : le nom d'une grille NEUVE (unique dans son projet) ;
- `--grille N` : pour une version SUIVANTE d'une grille existante ;
- `--ouverte` : une grille OUVERTE (une seule version, vivante, qui s'enrichit en posant) ;
  sans lui et sans la feuille, une grille FERMÉE ;
- `--porte-sur` : « Porte sur » (`mots`, « la case », « bulle, cartouche ou texte hors
  bulle »…) — exigé pour une grille neuve ; pour une version suivante, celui de la version
  précédente si on ne le dit pas ;
- `--note` : la note de version ;
- `--activer` : active la grille sur SON projet — la version vivante d'une grille ouverte, la
  version qu'on publie (`--publier N --activer`), ou la dernière publiée (`--grille N
  --activer`, sans fichier). Une grille fermée qu'on importe naît en brouillon : l'importer
  avec `--activer` est refusé, rien n'est écrit, et l'outil dit de publier d'abord ;
- `--masquer COLLECTION` (à répéter) : la masque dans ces collections de son projet, où elle
  doit être active ;
- `--retirer CLE`, `--fusionner CLE=AUTRE` (à répéter) : les réponses d'un réimport de grille
  ouverte (ci-dessous).

Activer et masquer suivent les règles des routes, dans la même transaction que l'import ou
la publication : un refus n'écrit rien. Ils ne se jouent pas `--a-blanc`. C'est la voie
d'activation tant que la fiche du projet n'a pas son écran des grilles.

```
python tools/importer_grille.py Oralite.xlsx --projet 2 --a-blanc   # le bilan, rien d'écrit
python tools/importer_grille.py Oralite.xlsx --projet 2             # nom, nature, cible : la feuille
python tools/importer_grille.py entrees.csv --listes listes.csv --projet 2 \
    --nom "Oralité" --porte-sur mots                # les deux CSV, et leur déclaration
python tools/importer_grille.py --publier 7         # la version 1 publiée
python tools/importer_grille.py --publier 7 --activer --masquer 12   # publiée, active, masquée
python tools/importer_grille.py --grille 7 --activer                 # active, sans rien importer
```

## Ce que l'import refuse, et ce qu'il dit

**Une anomalie de structure refuse le fichier ENTIER**, et l'import les dit TOUTES : rien n'est
écrit. Une ligne écartée se lirait, dans le bilan, comme une entrée disparue. Les anomalies :
une entrée sans nom ni identifiant ; un identifiant déjà pris par une autre entrée ; une
réponse inconnue à l'une des questions (forme, cible, combien de fois, autre zone) ; une
variante écrite avant toute entrée, qui nomme une entrée absente, ou sous une entrée qui ne se
pose pas avec une variante ; une variante sans nom, ou en double ; une entrée à variantes sans
variante ; une ligne de variante qui remplit autrement une colonne de son entrée ; une liste
inconnue, ou absente d'une entrée à qualificatifs, ou présente sur une autre forme ; une case
sans liste ; des cibles qui ne se combinent pas ; une rubrique dont le chemin et les
identifiants n'ont pas les mêmes étages, qui a deux noms, deux identifiants, deux parents, ou
qui est son propre ancêtre ; « Porte sur » absent ou inconnu ; dans un classeur, une cellule
qui porte une FORMULE ou une erreur du tableur ; une feuille « 1. La grille » qui dit une autre
nature que la grille, ou une nature inconnue.

**Ce qui ne casse rien avertit** (« À savoir ») — une liste qui a deux noms (le premier est
gardé), une liste que personne ne nomme, une entrée qui vise l'entité, des identifiants reçus
du nom, une déclaration de la feuille remplacée par un argument, une cellule que le tableur
avait typée en date ou en nombre à virgule (elle est lue en texte, et on le dit) — et l'import
se fait.

**Chaque anomalie, chaque avertissement est une DONNÉE**, que l'écran dessine et que l'outil
imprime en une ligne :

| Clé | Ce qu'elle dit |
|---|---|
| `code` | la sorte de faute, stable (`forme_inconnue`, `variante_sans_entree`…) |
| `fichier`, `ligne` | où : la feuille ou le fichier, et la ligne |
| `cle` | l'entrée concernée, quand il y en a une |
| `colonne`, `question` | la colonne machine, et la question telle que le classeur la pose (« 4. Ce qu'on choisit ») |
| `probleme` | ce qui ne va pas, en mots |
| `a_faire` | ce qu'il faut faire, en mots (absent d'un avertissement qui n'appelle rien) |

## Le bilan

Avant d'écrire, l'import compare au plus récent état PUBLIÉ de la grille, par identifiant. Le
bilan porte :

- un **verdict** (`verdict`) : `refuse` (des fautes : rien n'est importé tant qu'il en reste
  une), `a_repondre` (une grille ouverte attend des réponses), `aucun_changement`,
  `importable` (à blanc, rien ne l'empêche), `importe` — et sa phrase ;
- **à corriger** : les anomalies (dans la réponse 422 de la route, `anomalies`) ;
- **à savoir** (`a_savoir`) : les avertissements ;
- **ce qui va naître** (`va_naitre`) : combien de rubriques, d'entrées, de variantes, de
  listes et de cases ;
- **ce qui change** (`bilan`) : ce qui NAÎT, ce qui est RENOMMÉ (même identifiant, autre
  libellé), RETOUCHÉ (définition, structure, exemples, piège), DÉPLACÉ (une autre rubrique),
  CHANGÉ (forme, cible, cardinalité, liste, précision, lien), ce qui DISPARAÎT — avec, pour
  chaque disparu, le nombre de relevés posés sur lui ;
- la **déclaration** retenue, et les identifiants reçus du nom.

`--a-blanc` (`a_blanc` pour la route) rend ce bilan sans rien écrire.

**Réimporter le même fichier ne change rien** : l'empreinte du contenu (les cellules
nettoyées, les lignes rangées par identifiant) est celle de la version en place. Réordonner
les lignes ne fait donc pas une version. Une grille fermée a au plus un brouillon :
réimporter un autre contenu le REMPLACE ; après une publication, un brouillon neuf naît au
numéro suivant.

## Réimporter une grille ouverte

Une grille ouverte n'a qu'une version, vivante, qui s'enrichit en posant. Elle **se
réimporte** (tranché par Hugo le 2026-11-03, qui renverse le refus d'avant) : la version est
récrite EN PLACE, à son numéro, et le bilan dit ce qui disparaît.

**Une entrée employée ne se supprime jamais.** Une entrée que le fichier ne porte plus :

- que personne n'emploie, part (`decision: part`) ;
- déjà RETIRÉE, le reste, sans question ;
- EMPLOYÉE (au moins un relevé), attend sa réponse — le bilan la met dans `a_repondre`, avec
  les entrées où ses relevés peuvent être fusionnés, et l'import est refusé (409) tant qu'elle
  n'en a pas :
  - **retirer** (`{"cle": "retirer"}`, `--retirer CLE`) : elle reste dans la version, ne se
    pose plus, et ses relevés restent, « à revoir » (« l'entrée n'est plus dans la grille ») ;
    un réimport suivant la garde retirée ; la remettre dans le fichier la remet en usage ;
  - **fusionner dans…** (`{"cle": "fusionner:autre"}`, `--fusionner CLE=AUTRE`) : ses relevés
    passent à une autre entrée du fichier, et l'entrée part. L'autre entrée doit avoir la même
    forme, se poser de la même façon (des mots, une zone, la planche), avoir la même liste, et
    porter toutes les variantes employées ; une entrée qui ne se pose qu'une fois et qu'un
    relevé porte déjà sur la même cible refuse la fusion. Le journal de la grille garde quels
    relevés sont passés de l'une à l'autre.

Dans une version vivante, les relevés lisent la version telle qu'elle sera : l'import refuse
aussi (409) qu'une entrée employée change de forme ou de liste, qu'une variante ou une case
employée disparaisse, et une réponse donnée pour une entrée qui ne disparaît pas.

Ce que la route reçoit : `reponses`, un objet JSON (`{"cri": "retirer", "echo":
"fusionner:souffle"}`).

## Le réexport

`GET /api/grilles/{id}/versions/{numero}/tableur` rend le **classeur** d'une version — sa
déclaration, ses entrées et ses listes en mots, identifiants compris, la feuille d'exemple —,
et `?format=csv` les deux CSV machine, dans un zip (UTF-8 avec BOM). L'un comme l'autre,
réimporté tel quel, rend la même empreinte. C'est le chemin pour DÉRIVER une grille dans son
projet (réexporter, réimporter sous un autre nom) : les identifiants hérités la gardent
comparable. Une entrée retirée n'y est pas : elle ne se pose plus, et un réimport de la grille
ouverte la garde retirée.

Il se lit avec le plan : à qui lit la version publiée ou vivante (`clause_grille`), et le
brouillon à qui gère le projet seulement. Il ne porte ni login, ni relevé, ni transcription.

## Ce que l'import ne fait pas, et pourquoi on peut lui donner un classeur

Un classeur est une archive zip de XML : on le reçoit comme une entrée hostile.

- **Il est borné** : 5 Mo reçus, et 25 Mo une fois déplié — chaque membre de l'archive est
  décompressé et compté AVANT qu'on l'ouvre, sans se fier aux tailles qu'elle déclare : une
  bombe zip s'arrête au plafond (413). Au plus 300 membres, 5 000 lignes et 40 colonnes par
  feuille. Les deux CSV sont bornés de même.
- **Son XML est lu par `defusedxml`** : aucune entité, aucune DTD n'est résolue. openpyxl le
  prend de lui-même ; s'il ne l'a pas pris, l'import refuse tout classeur.
- **Aucune formule n'est évaluée** : une cellule qui en porte une est une anomalie, jamais
  une valeur. Un nombre, une date, un booléen que le tableur a typés reviennent en texte.
- **À la sortie, une cellule qui commence par `=` est du TEXTE** : son type est forcé, et le
  préfixe de citation posé, pour qu'un tableur ne l'exécute pas, même quand on la retouche.
  Dans les CSV, elle est préfixée d'une apostrophe, que l'import retire.

Ce qui reste à vérifier : le classeur dans Excel, LibreOffice et Google Sheets — les listes
déroulantes, les commentaires et le rouge (case d'`ANN-7`).
