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
