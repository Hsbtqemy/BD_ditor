# Importer une grille d'annotation — le tableur

*ANN-7, tranche 1. Le format que lit l'outil d'import (`tools/importer_grille.py`) et la route
`POST /api/projets/{id}/grilles/import`. Le cœur est `grille_import.py`. Ce document dit le
format tel qu'il est lu ; un gabarit fait pour une personne qui n'a jamais vu l'outil reste
à concevoir (case « Un gabarit de tableur qui ne perd personne » d'`ANN-7`).*

Une grille s'écrit dans un tableur ; BéDéditeur la vérifie ENTIÈRE, rend un bilan, et la
garde en brouillon jusqu'à ce qu'on la publie. Rien de la grille n'est dans le code : tout ce
qui la fait est dans ces deux fichiers.

## Les deux fichiers

Deux CSV, **séparateur `;`**, **UTF-8** — avec BOM (ce que pose un tableur pour lire les
accents) ou sans —, **en-tête obligatoire**, colonnes lues par leur NOM (l'ordre est libre,
une colonne en trop est ignorée).

1. **Les rubriques et les entrées** (`grille-rubriques-entrees.csv`) — la grille elle-même.
2. **Les listes de qualificatifs** (`grille-listes-qualificatifs.csv`) — facultatif, seulement
   si une entrée est à qualificatifs.

Un modèle FICTIF, qui fait jouer toutes les possibilités : `tools/grille-modele.csv` et
`tools/grille-modele-listes-qualificatifs.csv`.

## Le fichier des entrées

Une ligne par **entrée** (ce qu'on pose), et, sous une entrée à variantes, une ligne par
**variante**.

| Colonne | Ce qu'elle dit |
|---|---|
| `cle` | l'identifiant FIXE de l'entrée, invisible à l'écran (obligatoire). **Il ne change pas quand on renomme** : c'est grâce à lui qu'un renommage reste un renommage, et pas une entrée supprimée puis une autre ajoutée. Texte libre, comparé à l'identique |
| `rubrique` | où l'entrée se range, du plus large au plus fin, séparé par `>` : `Niveau 3. Morphosyntaxe > Verbe`. Vide : l'entrée n'est dans aucune rubrique |
| `rubrique_cle` | l'identifiant fixe de chaque étage, autant d'étages, même séparateur : `niveau-3 > verbe` |
| `forme` | `simple` · `variantes` · `qualificatifs` (obligatoire, cf. plus bas) |
| `libelle` | ce qu'on lit à l'écran (obligatoire) |
| `variante_cle`, `variante` | sur une ligne de variante : son identifiant fixe et son libellé |
| `structure`, `definition`, `exemples`, `piege` | ce que dira le guide — de l'entrée, ou de la variante sur sa ligne. Plusieurs exemples : séparés par ` \| ` |
| `liste` | pour une entrée à qualificatifs : la `liste_cle` de la liste où l'on coche |
| `precision` | le libellé d'un petit champ libre à remplir (« région ») ; vide, aucun |
| `lien` | `oui` quand l'entrée désigne une autre zone (un chevauchement) ; vide (ou `non`) sinon |
| `cible` | facultative : sur quoi CETTE entrée se pose, quand ce n'est pas ce que dit « Porte sur » |
| `cardinalite` | facultative : `une` (une seule fois par cible) ou `plusieurs` ; vide, la règle ordinaire |

Obligatoires dans l'en-tête : `cle`, `forme`, `libelle`.

### Une ligne de variante

Elle **répète la `cle` de son entrée**, porte `variante_cle` et `variante`, et laisse **vides**
les colonnes propres à l'entrée (`rubrique`, `rubrique_cle`, `forme`, `libelle`, `liste`,
`precision`, `lien`, `cible`, `cardinalite`). Si l'on y a recopié ces colonnes à l'identique —
en tirant une cellule vers le bas dans le tableur —, l'import l'accepte ; une valeur
DIFFÉRENTE de celle de l'entrée est une anomalie. Elle peut porter sa propre `definition`, sa
`structure`, ses `exemples`, son `piege`. Elle peut être n'importe où dans le fichier ; on
l'écrit d'ordinaire sous son entrée.

### Les cibles

| Cible | Ce qu'on désigne |
|---|---|
| `mots` | des mots d'une bulle, d'un cartouche ou d'une zone de texte — le découpage de l'outil |
| `bulle`, `cartouche`, `texte`, `case`, `personnage`, `detail` | une région ENTIÈRE de ce type (`personnage` : la boîte dessinée) |
| `planche` | la planche entière (la surface ; pour une double page, la double page) |
| `entite` | le personnage du registre — **aucun relevé ne s'y pose encore** (elle attend l'étage de projet des personnages) |

**Plusieurs cibles** s'écrivent séparées par ` | ` — `bulle | cartouche | texte` : toute la
zone, l'une des trois. Seuls des types de zone se combinent entre eux : `mots | case` ne veut
rien dire, et `planche` comme `entite` vont seules. Un `detail` se trace dans une case, sur la
page Annotation (« Détail d'image ») ; il ne sort d'aucun export avant la tranche 4.

« **Porte sur** » est la cible des entrées qui ne disent pas la leur ; elle se déclare à
l'import (ci-dessous), pas dans le fichier.

### La cardinalité

Vide, elle prend la règle ordinaire : **plusieurs** sur des mots (deux élisions dans une
bulle), **une** sur une région entière ou la planche (un seul registre par bulle). `une`
refuse un second relevé de la même entrée sur la même cible : à l'écran, en choisir une autre
remplace.

## Les trois formes, et ce que chacune compte

| Forme | Le geste | Ce que compte un relevé |
|---|---|---|
| `simple` | on pose l'entrée, ou non | une occurrence de l'entrée |
| `variantes` | on pose l'entrée et on choisit **UNE** de ses variantes | une occurrence de l'entrée, et de sa variante |
| `qualificatifs` | on pose l'entrée et on coche **zéro, un ou plusieurs** choix d'une liste PARTAGÉE | **UNE** occurrence de l'entrée, quel que soit le nombre de qualificatifs cochés |

Le dernier point décide de la forme. Un mot coché « lexique » et « graphie » sous une entrée à
qualificatifs fait UNE occurrence, pas deux. Si deux choix doivent compter pour deux, la
grille écrit deux entrées (« emphase par typographie », « emphase par ponctuation »), ou une
entrée à variantes posée deux fois. Le modèle ne change pas selon la grille : c'est l'auteur
de la grille qui choisit, en connaissant cette règle (tranché par Hugo le 2026-10-22).

## Le fichier des listes

Une ligne par qualificatif.

| Colonne | Ce qu'elle dit |
|---|---|
| `liste_cle` | l'identifiant fixe de la liste — ce que nomme la colonne `liste` d'une entrée (obligatoire) |
| `liste` | le libellé de la liste |
| `cle` | l'identifiant fixe du qualificatif (obligatoire) |
| `libelle` | son libellé (obligatoire) |
| `definition` | sa définition |

Une liste sert à plusieurs entrées : c'est ce qui la rend PARTAGÉE.

## La déclaration

Ce que le fichier ne dit pas passe en arguments de l'outil (ou en champs du formulaire de la
route) :

- `--nom` : le nom d'une grille NEUVE (unique dans son projet) ;
- `--grille N` : pour une version SUIVANTE d'une grille existante ;
- `--ouverte` : une grille OUVERTE (une seule version, vivante, qui s'enrichit en posant ;
  on ne la réimporte pas avec un autre contenu) ; sans lui, une grille FERMÉE ;
- `--porte-sur` : « Porte sur » (`mots`, `case`, `bulle | cartouche | texte`…) — exigé pour
  une grille neuve ; pour une version suivante, celui de la version précédente si on ne le dit
  pas ;
- `--note` : la note de version ;
- `--activer` : active la grille sur SON projet — la version vivante d'une grille ouverte, la
  version qu'on publie (`--publier N --activer`), ou la dernière publiée (`--grille N
  --activer`, sans fichier). Une grille fermée qu'on importe naît en brouillon : l'importer
  avec `--activer` est refusé, rien n'est écrit, et l'outil dit de publier d'abord ;
- `--masquer COLLECTION` (à répéter) : la masque dans ces collections de son projet, où elle
  doit être active.

Activer et masquer suivent les règles des routes, dans la même transaction que l'import ou
la publication : un refus n'écrit rien. Ils ne se jouent pas `--a-blanc`. C'est la voie
d'activation tant que la fiche du projet n'a pas son écran des grilles.

```
python tools/importer_grille.py entrees.csv --listes listes.csv --projet 2 \
    --nom "Oralité" --porte-sur mots --a-blanc      # le bilan, rien d'écrit
python tools/importer_grille.py entrees.csv --listes listes.csv --projet 2 \
    --nom "Oralité" --porte-sur mots                # le brouillon
python tools/importer_grille.py --publier 7         # la version 1 publiée
python tools/importer_grille.py --publier 7 --activer --masquer 12   # publiée, active, masquée
python tools/importer_grille.py --grille 7 --activer                 # active, sans rien importer
```

## Ce que l'import refuse, et ce qu'il dit

**Une anomalie de structure refuse le fichier ENTIER**, et l'import les dit TOUTES, avec leur
ligne : rien n'est écrit. Une ligne écartée se lirait, dans le bilan, comme une entrée
disparue. Les anomalies : une `cle` vide ou déjà prise par une autre entrée ; une forme
inconnue ; un libellé vide ; une variante qui nomme une entrée absente, ou une entrée qui
n'est pas à variantes ; une variante en double ; une entrée à variantes sans variante ; une
ligne de variante qui remplit autrement une colonne de son entrée ; une liste inconnue, ou
absente d'une entrée à qualificatifs, ou présente sur une autre forme ; un qualificatif sans
liste ; une cible ou une cardinalité inconnue, des cibles qui ne se combinent pas ; un `lien`
qui n'est ni `oui` ni vide ; une rubrique dont le chemin et les identifiants n'ont pas les
mêmes étages, qui a deux libellés, deux identifiants, deux parents, ou qui est son propre
ancêtre ; « Porte sur » absent ou inconnu.

**Ce qui ne casse rien avertit** — une liste qui a deux libellés (le premier est gardé), une
liste que personne ne nomme, une entrée qui vise l'entité ou un détail — et l'import se fait.

## Le bilan

Avant d'écrire, l'import compare au plus récent état PUBLIÉ de la grille, par `cle` : ce qui
NAÎT, ce qui est RENOMMÉ (même `cle`, autre libellé), RETOUCHÉ (définition, structure,
exemples, piège), DÉPLACÉ (une autre rubrique), CHANGÉ (forme, cible, cardinalité, liste,
précision, lien), ce qui DISPARAÎT — avec, pour chaque disparu, le nombre de relevés posés sur
lui. `--a-blanc` rend ce bilan sans rien écrire.

**Réimporter le même fichier ne change rien** : l'empreinte du contenu (les cellules
nettoyées, les lignes rangées par `cle`) est celle de la version en place. Réordonner les
lignes ne fait donc pas une version. Une grille fermée a au plus un brouillon : réimporter un
autre contenu le REMPLACE ; après une publication, un brouillon neuf naît au numéro suivant.

## Le réexport

`GET /api/grilles/{id}/versions/{numero}/tableur` rend les deux fichiers d'une version, dans ce
format, identifiants compris (un zip, UTF-8 avec BOM) — réimportés, ils rendent la même
empreinte. C'est le chemin pour DÉRIVER une grille dans son projet (réexporter, réimporter) :
les `cle` héritées la gardent comparable. Une cellule qui commencerait par `=`, `+`, `-` ou
`@` serait exécutée comme une formule par un tableur : le réexport la préfixe d'une
apostrophe, que l'import retire.
