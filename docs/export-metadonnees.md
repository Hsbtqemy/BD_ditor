# Export de métadonnées (description du corpus)

> **But.** Produire, *à côté* des exports de contenu existants (JSON-LD / CSV / TEI,
> routes `/api/export/*`), une **description des métadonnées** que le corpus génère —
> en vue de la réutilisation et d'un futur dépôt (Nakala / HAL). Sortie **additive** :
> ces outils ne touchent ni aux exports existants ni au schéma, et lisent la base en
> **lecture seule**. Cadre conceptuel : `docs/dictionnaire-metadonnees.md`.

Tout passe par des **scripts hors-app** (`tools/`), pas par l'API. Périmètre par
défaut : le **corpus entier**. Depuis le schéma **v14**, l'entité `collection` existe en
base (palier supérieur du dictionnaire, unité de dépôt) : on la gère avec
`tools/gerer_collections.py`, et chaque export accepte `--collection <id>` pour se
restreindre à ses albums. Sans collection, le corpus entier tient lieu de collection implicite.

## Principe : un modèle, plusieurs sérialisations

Une seule lecture de la base alimente **un modèle interne** (mêmes dérivations que
l'app : citation `pl·c·b`, numéro éditorial, locuteur/présence par nom, attributs
facettés, tokens effectifs). Toutes les vues en découlent — CSV, XLSX et IIIF **ne
peuvent pas diverger**.

Deux registres, à ne pas confondre :

| Registre | Répond à | Outil |
|---|---|---|
| **Fiche descriptive** (méta-niveau) | *quels champs emploie-t-on, avec quelle couverture ?* | `description_collection.py` |
| **Enregistrements** (les métadonnées elles-mêmes) | *les valeurs réelles, entité par entité* | `metadonnees_collection.py` |

## Les outils

| Script | Sorties | Commande type |
|---|---|---|
| `tools/gerer_collections.py` | **écrit** : crée / édite une collection, y range des albums | `creer --nom "…" --albums 1,2` |
| `tools/description_collection.py` | roll-up **JSON** + catalogue **CSV** (le dictionnaire instancié) | `--json f.json --csv f.csv` |
| `tools/metadonnees_collection.py` | **JSON** arbre · **CSV** par niveau (`--csv-dir`/`--zip`) · **XLSX** multi-feuilles (`--xlsx`) | `--xlsx metadonnees.xlsx` |
| `tools/iiif_manifest.py` | **IIIF Presentation 3.0** : Manifest/album, Canvas/planche, Collection | `--base-url https://host --out-dir iiif/` |
| `tools/valider_iiif.py` | rapport de conformité IIIF (structurel, hors ligne) | `iiif/` |
| `tools/crosswalk_depot.py` | **Dublin Core** (JSON-LD) + **DataCite 4.x** (JSON/XML) : notices album + collection (cf. `docs/crosswalk-depot.md`) | `--collection 1 --out-dir depot/` |

`gerer_collections.py` est le **seul outil d'écriture** de ce lot (les autres lisent en
seule lecture) ; ses sous-commandes : `lister`, `montrer ID`, `creer`, `modifier ID`,
`ajouter ID --albums …`, `retirer ID --albums …`, `supprimer ID`. Les trois exports
prennent `--collection <id>` (défaut : corpus entier).

La base suit la config du projet (`BD_DB_PATH` / `BD_DATA_DIR`).

## Portée d'une collection (`--collection`)

Une collection est un **ensemble d'albums** (appartenance N-N, statique → citable). Quand
`--collection <id>` est passé :

- les **records** (`metadonnees_collection.py`) et l'**IIIF** ne portent que sur les albums
  de la collection ; l'arbre JSON gagne un bloc `collection` (descripteurs) et la Collection
  IIIF prend son nom ;
- la **fiche** (`description_collection.py`) renseigne son bloc `identite` depuis la ligne
  `collection` et **restreint la couverture** à ces albums ;
- les **catalogues de référence** — personnages, vocabulaire facetté, étiquettes (tags) —
  restent **globaux** (entités canoniques du corpus) ; seuls leurs **liens** vers des régions
  du périmètre sont comptés/scopés. Le rattachement d'un terme de vocabulaire à une collection
  (« portée d'appartenance ») reste *à prévoir* (cf. dictionnaire, N7).

## Formats produits

- **Fiche — JSON roll-up** : identité (à prévoir) · **couverture** (nb albums/planches/
  régions/tokens, % validé, couverture OCR, distributions par type/POS) · **provenance**
  (moteurs, modèle NLP) · **vocabulaire** facetté · **droits**.
- **Fiche — CSV catalogue** : une ligne = un *élément* de métadonnée (colonnes du
  dictionnaire : provenance, statut, standard, ouvrable) + sa valeur/agrégat. Les
  champs `absent — à prévoir` y figurent **vides** → la sortie est honnête sur la couverture.
- **Enregistrements — JSON arbre** : `collection → albums → planches → régions
  (case ⊃ bulle) → tokens` ; personnages et vocabulaire sortis une fois, référencés par nom.
- **Enregistrements — CSV par niveau** : `collection`, `albums` (avec les champs d'édition
  N0), `contributions`, `contribution_roles`, `planches`, `regions`, `tokens`,
  `annotations`, `tags`, `personnages`, `personnage_attributs`, `region_attributs`,
  `vocabulaire`, `paradonnee` — dump relationnel recollable par les clés (`album_id`,
  `planche_id`, `region_id`, `parent_id`). Groupables en `.zip`. Écrits avec un **BOM
  UTF-8** (accents lisibles dans Excel, comme l'export de l'app). Les albums portent aussi
  leurs **contributions** (nom + rôle résolu : bucket DCterms + code MARC) et le catalogue
  **`contribution_roles`** (vocabulaire contrôlé-ouvert).
- **Enregistrements — XLSX multi-feuilles** : un onglet par table (dont `tags` et
  `paradonnee`), plus deux onglets de confort — **`fiche`** (le roll-up aplati) et
  **`arbre`** (hiérarchie **repliable** avec les boîtes `x,y,w,h` et un lien « voir »
  vers la ligne de détail). En-têtes gelés + filtres ; les valeurs commençant par
  `= + - @` sont forcées en texte (**anti-injection de formule**). Requiert `openpyxl`
  (`requirements-export.txt`) ; JSON/CSV n'en dépendent pas (import protégé).
- **Paradonnée (niveau 8)** dans les enregistrements : `schema_version`, table `meta`
  (modèle NLP + versions + dates de réindexation), **provenance de l'outil**
  (`outil = {nom, version, revision git}`), et la liste `a_prevoir` (journal d'audit,
  activités/runs… absents en base).
- **IIIF Presentation 3.0** : Canvas aux dimensions **master**, image (dérivé web)
  peinte dessus, **une Annotation par région** ciblant `canvas#xywh=x,y,w,h`.

## Décisions de conception

- **Exports existants intacts** — la description est strictement additive.
- **OCR verbatim = contenu, pas métadonnée.** C'est de l'expression protégée
  (`restreint`) : par défaut on n'expose que présence + longueur ; `--verbatim` inclut
  le texte (export **détenu**, non rediffusable).
- **Tiers de droits** portés partout : `ouvert` (descriptif, géométrie, structure,
  provenance, lemme/POS/morph, tags, notes, personnages, attributs) · `agrégat` (formes
  de surface, en fréquences) · `restreint` (scans, OCR verbatim).
- **Coordonnées = coin supérieur gauche, pixels master** — exactement le repère
  **IIIF `xywh`** (et TEI `@ulx/@uly`). L'export IIIF est donc une *sérialisation*, sans
  aucune conversion (Canvas déclaré en dimensions master, image body plus petite).
- **DOI hors périmètre** : c'est l'entrepôt qui le frappe, au niveau qu'on lui soumet.

## Limites (état actuel)

- Les exemples de `docs/exemples/` (dossier **gitignoré** : artefacts locaux, non
  versionnés) sont **reproductibles** — `python tools/regenerer_exemples.py` sème un
  corpus de démonstration jetable (`tools/semer_demo.py`, versionné) puis réécrit tout le
  jeu (JSON + XLSX + ZIP + tables CSV + fiche + IIIF). Aucun corpus réel n'est requis.
- La couche **descriptive de la collection** (nom, responsables, licence, base légale,
  statut de diffusion, dates) est renseignée dès qu'une collection est créée
  (`gerer_collections.py`) et scopée par `--collection` ; **sans** collection, le périmètre
  reste le corpus entier et cette couche est vide (collection implicite).
- **Validation IIIF à trois niveaux** : (1) **structurelle hors ligne**
  (`tools/valider_iiif.py` : ids/URI uniques, Canvas → dimensions, cible `#xywh` dans les
  bornes du Canvas…) ; (2) **stricte** via **`iiif-prezi3`** (bibliothèque IIIF *officielle* —
  re-parse chaque document dans ses modèles typés ; validation **indépendante** de notre
  script, exécutée automatiquement si la lib est installée, cf. `requirements-export.txt`) ;
  (3) **validateur officiel** `validator.iiif.io`, au moment du dépôt (exige une **URL
  publique** ; ne récupère pas les images ni ne fait l'expansion JSON-LD en local).
- Une planche **sans dimensions master** ou une région **sans boîte** (coordonnées
  nulles) est **omise de l'IIIF** (un Canvas / un `xywh` exige des entiers positifs) —
  elle reste présente dans les CSV/JSON.

## Dépôt IIIF (moment T)

Le manifest est un livrable **ponctuel** (au dépôt), pas un service continu — BéDéditeur ne
sert PAS de manifests en direct. Au dépôt, c'est l'**entrepôt** (Nakala / HAL / hôte IIIF)
qui sert manifest + images (URL stable, CORS). En pratique :

1. **Générer** avec `--base-url` = l'**hôte cible** (là où le manifest et les `/derivatives`
   seront servis) : l'`id` du manifest doit pointer cet hôte, jamais `localhost`.
2. **Vérifier** en local : `python tools/valider_iiif.py iiif/` (structurel + strict
   `iiif-prezi3` si installé).
3. **Au dépôt** : soumettre l'URL publique au **validateur officiel** `validator.iiif.io`.

## Récapitulatif des commandes

```bash
# Collections (unité de dépôt) — création + rattachement d'albums
python tools/gerer_collections.py creer --nom "Corpus X" --licence CC-BY-4.0 \
    --statut public --responsable "Nom;chercheur;0000-0000-…" --albums 1,2,3
python tools/gerer_collections.py lister
python tools/gerer_collections.py montrer 1

# Fiche descriptive (--collection pour scoper ; sinon corpus entier)
python tools/description_collection.py --json fiche.json --csv fiche.csv

# Métadonnées réelles
python tools/metadonnees_collection.py --json arbre.json           # arbre
python tools/metadonnees_collection.py --csv-dir tables/           # tables CSV
python tools/metadonnees_collection.py --zip metadonnees.zip       # bundle
pip install -r requirements-export.txt
python tools/metadonnees_collection.py --xlsx metadonnees.xlsx     # classeur

# Scoper un export à une collection (idem pour description_collection / iiif_manifest)
python tools/metadonnees_collection.py --json arbre.json --collection 1

# IIIF + validation (structurelle ; + stricte iiif-prezi3 si installé)
python tools/iiif_manifest.py --base-url https://host/iiif --out-dir iiif/
python tools/valider_iiif.py iiif/

# Crosswalk de dépôt : Dublin Core + DataCite (cf. docs/crosswalk-depot.md)
python tools/crosswalk_depot.py --collection 1 --out-dir depot/
python tools/crosswalk_depot.py --publisher "Huma-Num (Nakala)" --annee-depot 2026

# (Re)générer TOUT le jeu d'exemples de docs/exemples/ (corpus de démo jetable)
python tools/regenerer_exemples.py
```
