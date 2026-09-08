# Import en lot du vocabulaire (piste B)

> **But.** Laisser des chercheurs **pré-remplir la taxonomie** (domaines → dimensions → valeurs
> + définitions) depuis un **tableur**, plutôt que de la saisir terme à terme dans l'app. C'est
> un **amorçage** : additif, rejouable, et **compatible avec l'émergent** — les annotateurs
> continuent de créer des dimensions/valeurs au fil de l'annotation. Outil : `tools/importer_vocabulaire.py`.

## Ce que ça n'est pas

Ce n'est **pas** un nouveau modèle de données : l'import écrit dans les tables existantes
(`domaine`, `attribut_dimension`, `attribut_valeur` + couche lexique A4). Ce n'est **pas** un
figement : rien n'empêche d'ajouter ensuite des termes à la main. Ce n'est **pas** une validation :
tout entre à l'état `provisoire` ; la promotion `provisoire → defini` reste un acte **humain**
dans le panneau 📖 Lexique (là où on a le contexte pour juger). Cf. [lexique-situe.md](lexique-situe.md).

## Le tableur

Séparateur **point-virgule** (défaut d'Excel FR ; les virgules dans le texte ne demandent alors
aucun guillemet), en-tête **obligatoire**, encodage UTF-8 (avec ou sans BOM). Modèle livré :
[`tools/vocabulaire-modele.csv`](../tools/vocabulaire-modele.csv).

Deux fichiers, à ne pas confondre : `vocabulaire-modele.csv` montre le **format** (colonnes,
conventions) avec des termes jetables ; [`tools/vocabulaire-etude-propose.csv`](../tools/vocabulaire-etude-propose.csv)
est une **proposition de contenu** pour l'étude — deux domaines, neuf axes, quarante et une
valeurs, chaque dimension avec sa `definition` et sa `note_portee`. Elle est faite pour être
**amendée en séance** (ANN-1), et n'a encore été importée nulle part.

| Colonne | Rôle |
|---|---|
| `domaine` | champ analytique de rattachement (**vide = dimension hors domaine**) |
| `domaine_definition` | glose du domaine (SKOS `definition`) |
| `cible` | à quoi la dimension s'accroche : `personnage` \| `case` |
| `dimension` | l'axe (ex. `valence`, `genre`) |
| `dimension_definition` | glose de l'axe |
| `dimension_note_portee` | le « **situé** » (SKOS `scopeNote`) : comment lire cet axe **dans cette étude** |
| `valeur` | une valeur de l'axe (**vide = déclarer la dimension sans énumérer ses valeurs**) |
| `valeur_definition` | glose de la valeur |

### Deux conventions, pour que ce soit robuste au tableur

1. **Une ligne = une valeur.** Les colonnes d'**identité** (`domaine`, `cible`, `dimension`,
   `valeur`) sont remplies sur **chaque** ligne. C'est volontairement redondant : un chercheur
   qui **trie ou filtre** son tableur ne casse jamais le rattachement (chaque ligne est
   autonome).
2. **Les définitions ne se mettent qu'une fois**, sur la première ligne de leur domaine/dimension,
   puis restent vides. On ne répète que les noms courts, pas les longues gloses (pas de risque
   d'en corriger une et pas l'autre). L'ordre des lignes n'a **aucune** importance.

> La `note_portee` du tableur porte sur la **dimension** (le cas le plus utile : cadrer tout un
> axe). Une note propre à une *valeur* ou à un *domaine* se pose ensuite dans le panneau Lexique.

## Doctrine : pré-remplir, jamais écraser

Exactement comme l'OCR (`pipeline/ocr.py`, `only_empty=True`), l'import **ne remplace jamais**
une saisie humaine :

- un terme **déjà présent** est **réutilisé** (jamais dupliqué) — l'import est **idempotent** ;
- sa `definition` / `note_portee` n'est renseignée **que si elle est encore vide** ; une glose
  saisie dans l'app est intouchable ;
- le **rattachement au domaine** ne se pose que si la dimension était *orpheline* (jamais déplacée) ;
- la **portée** (`collection_id`) n'est fixée qu'à la **création** du terme (réimporter dans une
  collection ne déménage pas un terme déjà global — l'appartenance est une décision humaine).

Deux définitions **différentes** pour un même terme dans le fichier → **avertissement** (faute de
saisie typique) ; la première fait foi (cohérent avec le « ne jamais écraser »).

## Arbitrage (ANN-1) — amorcer par le tableur, finir dans l'app

**La question s'est posée pour de bon** en préparant la séance de vocabulaire d'ANN-1 :
saisir les termes d'étude un par un dans le panneau 📖 Lexique, ou les amorcer depuis un
tableur ? Tranché le **2026-09-08** — *le tableur pour l'amorçage, l'app pour tout ce qui
vient après*, et la frontière n'est pas une préférence : elle est **imposée par la
doctrine ci-dessus**.

Ce qui décide n'est pas le volume : neuf dimensions et quarante et une valeurs se
saisiraient à la main sans drame. C'est la **trace**. Un vocabulaire d'étude est une
décision collective : il s'amende, il se discute, et il faut pouvoir dire six mois plus
tard qui a changé quoi et pourquoi. Un fichier versionné donne un diff lisible ; cinquante
gestes dans une modale ne laissent que leur résultat.

### Ce qui a été mesuré

Sur [`tools/vocabulaire-etude-propose.csv`](../tools/vocabulaire-etude-propose.csv), le
2026-09-08, base jetable :

- **L'import est idempotent.** Rejoué tel quel : `0 créé`, 2 domaines / 9 dimensions /
  41 valeurs `déjà présents`. Un tableur se rejoue sans jamais dupliquer.
- **Le tableur ne porte pas tout.** Aucune colonne pour la `note_portee` d'un **domaine**
  ni d'une **valeur** — seule celle des *dimensions* y tient — et l'`etat`
  (`provisoire`→`defini`) en est exclu **exprès**. Ces trois-là sont des gestes d'app, et
  c'est le bon endroit : ce sont ceux qui demandent le contexte.

### Le piège, et c'est lui qui fixe l'ordre des opérations

**Un tableur CORRIGÉ ne corrige pas ce que le tableur a lui-même créé** — et il ne le dit
pas. Mesuré : définition importée, définition changée dans le fichier, import rejoué → la
base garde l'ancienne, et le bilan annonce paisiblement « 0 créé, 9 déjà présents ». C'est
la conséquence exacte du *« renseignée que si elle est encore vide »* ; l'avertissement
« deux définitions divergentes » ne joue qu'**à l'intérieur** d'un fichier, jamais entre le
fichier et la base.

Donc l'import n'est pas un aller-retour, c'est un **amorçage à un coup, par terme** :

1. **Les amendements de la séance se portent dans le CSV AVANT le premier import.** Après,
   le fichier est doublé par la base sans qu'aucun signal ne le dise.
2. Une fois importé, **une correction se fait dans l'app** — c'est le seul chemin qui
   écrit par-dessus.
3. Le CSV reste alors la trace **datée de l'amorçage**, pas l'état courant du vocabulaire.
   Le lire comme la source de vérité serait l'erreur que ce paragraphe ferme.

> Rattraper un import prématuré ne demande pas de vider la base : un terme dont la glose
> est encore **vide** est toujours renseignable par un réimport. Ce sont les termes déjà
> glosés qu'il faut reprendre à la main.

## Utilisation

```bash
# Vocabulaire GLOBAL (partagé par tout le corpus)
python tools/importer_vocabulaire.py mon_vocabulaire.csv

# Vocabulaire LOCAL à une collection (portée d'appartenance A4)
python tools/importer_vocabulaire.py mon_vocabulaire.csv --collection 3

# Aperçu : compte ce qui serait créé, n'écrit RIEN
python tools/importer_vocabulaire.py mon_vocabulaire.csv --dry-run
```

`--collection` prend un **id** de collection **existante** (à créer d'abord avec
[`tools/gerer_collections.py`](../tools/gerer_collections.py) — seul outil d'écriture des
collections) ; absent = global. La base suit `BD_DB_PATH` / `BD_DATA_DIR` (cf. `config.py`).

Le bilan (sur stderr) distingue **créés / déjà présents** par palier et liste les anomalies
(cible inconnue, dimension vide → ligne ignorée) et avertissements (définitions divergentes).

### Dans l'app (panneau 📖 Lexique)

Le même import est accessible sans terminal : dans **Exploration → 📖 Lexique**, le bouton
**« Importer un tableur… »** ouvre un sélecteur de fichier, avec un menu **« Importer dans »**
(portée : *Global* ou une collection). Le bilan s'affiche en notifications et la modale se
recharge. Route : `POST /api/lexique/importer` (multipart : `file` + `collection_id` optionnel).

Le **cœur** (parsing + upsert) vit dans `lexique_import.py` ; l'outil CLI comme la route en
sont de **minces enveloppes** — une seule logique, testée en un seul endroit.

## Périmètre

- **Couvert** : domaines, dimensions (les deux `cible`), valeurs, et leur `definition` /
  `note_portee` / portée `collection_id`.
- **Hors périmètre** (volontaire, se fait dans l'app) : l'`etat` (`provisoire`→`defini`), les
  **tags** (vocabulaire d'un autre patron, glosé dans le Lexique), l'affectation des valeurs aux
  personnages/cases (acte d'**annotation**, pas de taxonomie).
