# Export de métadonnées (description du corpus)

> **But.** Produire, *à côté* des exports de contenu existants (JSON-LD / CSV / TEI,
> routes `/api/export/*`), une **description des métadonnées** que le corpus génère —
> en vue de la réutilisation et d'un futur dépôt (Nakala / HAL). Sortie **additive** :
> ces outils ne touchent ni aux exports existants ni au schéma, et lisent la base en
> **lecture seule**. Cadre conceptuel : `docs/dictionnaire-metadonnees.md`.

Tout passe par des **scripts hors-app** (`tools/`), pas par l'API. Périmètre par
défaut : le **corpus entier** (l'entité `collection` du dictionnaire est « à prévoir »
en base ; le corpus tient lieu de collection implicite).

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
| `tools/description_collection.py` | roll-up **JSON** + catalogue **CSV** (le dictionnaire instancié) | `--json f.json --csv f.csv` |
| `tools/metadonnees_collection.py` | **JSON** arbre · **CSV** par niveau (`--csv-dir`/`--zip`) · **XLSX** multi-feuilles (`--xlsx`) | `--xlsx metadonnees.xlsx` |
| `tools/iiif_manifest.py` | **IIIF Presentation 3.0** : Manifest/album, Canvas/planche, Collection | `--base-url https://host --out-dir iiif/` |
| `tools/valider_iiif.py` | rapport de conformité IIIF (structurel, hors ligne) | `iiif/` |

La base suit la config du projet (`BD_DB_PATH` / `BD_DATA_DIR`).

## Formats produits

- **Fiche — JSON roll-up** : identité (à prévoir) · **couverture** (nb albums/planches/
  régions/tokens, % validé, couverture OCR, distributions par type/POS) · **provenance**
  (moteurs, modèle NLP) · **vocabulaire** facetté · **droits**.
- **Fiche — CSV catalogue** : une ligne = un *élément* de métadonnée (colonnes du
  dictionnaire : provenance, statut, standard, ouvrable) + sa valeur/agrégat. Les
  champs `absent — à prévoir` y figurent **vides** → la sortie est honnête sur la couverture.
- **Enregistrements — JSON arbre** : `collection → albums → planches → régions
  (case ⊃ bulle) → tokens` ; personnages et vocabulaire sortis une fois, référencés par nom.
- **Enregistrements — CSV par niveau** : `albums`, `planches`, `regions`, `tokens`,
  `annotations`, `tags`, `personnages`, `personnage_attributs`, `region_attributs`,
  `vocabulaire`, `paradonnee` — dump relationnel recollable par les clés (`album_id`,
  `planche_id`, `region_id`, `parent_id`). Groupables en `.zip`. Écrits avec un **BOM
  UTF-8** (accents lisibles dans Excel, comme l'export de l'app).
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

- Les exemples de `docs/exemples/` sont produits sur un **corpus de démonstration semé**
  (aucun corpus réel n'est versionné).
- La couche **descriptive de la collection** (nom, responsables, licence…) reste vide
  tant que la table `collection` n'existe pas en base — champ « à prévoir » du dictionnaire.
- La validation IIIF est **structurelle et hors ligne** (le validateur officiel
  `validator.iiif.io` exige une URL publique). Elle ne récupère pas les images et ne
  fait pas l'expansion JSON-LD ; à compléter le jour d'un déploiement servi.
- Une planche **sans dimensions master** ou une région **sans boîte** (coordonnées
  nulles) est **omise de l'IIIF** (un Canvas / un `xywh` exige des entiers positifs) —
  elle reste présente dans les CSV/JSON.

## Récapitulatif des commandes

```bash
# Fiche descriptive
python tools/description_collection.py --json fiche.json --csv fiche.csv

# Métadonnées réelles
python tools/metadonnees_collection.py --json arbre.json           # arbre
python tools/metadonnees_collection.py --csv-dir tables/           # tables CSV
python tools/metadonnees_collection.py --zip metadonnees.zip       # bundle
pip install -r requirements-export.txt
python tools/metadonnees_collection.py --xlsx metadonnees.xlsx     # classeur

# IIIF + validation
python tools/iiif_manifest.py --base-url https://host/iiif --out-dir iiif/
python tools/valider_iiif.py iiif/
```
