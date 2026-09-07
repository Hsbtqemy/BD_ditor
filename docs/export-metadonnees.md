# Export de métadonnées (description du corpus)

> **But.** Produire, *à côté* des exports de contenu existants (JSON-LD / CSV / TEI,
> routes `/api/export/*`), une **description des métadonnées** que le corpus génère —
> en vue de la réutilisation et d'un futur dépôt (Nakala / HAL). Sortie **additive** :
> ces outils ne touchent ni aux exports existants ni au schéma, et lisent la base en
> **lecture seule**. Cadre conceptuel : `docs/dictionnaire-metadonnees.md`.

Tout passait par des **scripts hors-app** (`tools/`), pas par l'API — vrai tant que
l'outil tournait en mono-poste, et faux depuis **EXP-1** : les trois exports descriptifs
ont aussi une route (cf. § *Depuis l'application, sans shell*), sur les mêmes cœurs. Les
scripts restent la voie complète, et la seule pour le crosswalk et la provenance.
Périmètre par défaut **en CLI** : le **corpus entier** — les routes, elles, exigent une
collection nommée, pour la raison écrite plus bas. Depuis le schéma **v14**, l'entité `collection` existe en
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
| `tools/provenance_export.py` | **PROV-O** (PROV-JSON) + **TEI `<revisionDesc>`** du journal d'audit (cf. `docs/provenance-audit.md`) | `--out-dir prov/` |

`gerer_collections.py` est le **seul outil d'écriture** de ce lot (les autres lisent en
seule lecture) ; ses sous-commandes : `lister`, `montrer ID`, `creer`, `modifier ID`,
`ajouter ID --albums …`, `retirer ID --albums …`, `supprimer ID`. Les trois exports
prennent `--collection <id>` (défaut : corpus entier).

La base suit la config du projet (`BD_DB_PATH` / `BD_DATA_DIR`).

## Depuis l'application, sans shell (EXP-1)

La doctrine « scripts hors-app » supposait le **mono-poste** : le chercheur était *sur* la
machine de la base. Déployé derrière Authelia, plus personne n'a de shell — les trois
outils descriptifs deviennent hors d'atteinte de ceux à qui ils servent. Trois routes les
rendent, sur une **collection nommée** :

| Route (`GET`) | Formats | Équivalent CLI |
|---|---|---|
| `/api/collections/{id}/depot/description` | `json` · `csv` | `description_collection.py --collection {id}` |
| `/api/collections/{id}/depot/metadonnees` | `json` · `zip` · `xlsx` (+ `verbatim`) | `metadonnees_collection.py --collection {id}` |
| `/api/collections/{id}/depot/iiif` | `zip` (+ `base_url` *facultatif*, `verbatim`) | `iiif_manifest.py --collection {id} --out-dir …` |

**Les cœurs sont partagés, rien n'est réécrit côté serveur.** L'extraction a coûté trois
petits déplacements, tous dans le sens du partage : `zip_tables` / `xlsx_tables` sortent du
`main()` des métadonnées (la CLI passe désormais par elles, faute de quoi le chemin
partagé ne serait exercé par aucun test), et les constats de l'IIIF deviennent des
**données** — `diagnostic_base_url` et `diagnostic_regime` rendent une liste de
`Constat(gravite, code, message)`, la CLI ne gardant que la mise en forme.

Quatre points où une route ne peut pas se comporter comme une CLI :

- **La collection est un segment de CHEMIN, jamais un paramètre facultatif.** Les outils
  traitent `--collection` absent comme « corpus entier », sans consulter la moindre
  portée : c'est le bon défaut sur la machine de la base, et c'est exactement ce qu'une
  route ne doit jamais faire. En chemin, le cas cesse d'être joignable.
- **Lire la collection suffit.** Ces artefacts décrivent un périmètre auquel on est déjà
  admis (cf. `docs/hebergement-securite.md` §6). Le refus est un **404** et non un 403 —
  « existe mais pas pour vous » révèle la composition du corpus.
- **`base_url` n'a pas de défaut, et l'application ne peut pas le deviner.** Elle sert
  bien `/derivatives`, mais par une route cloisonnée depuis AUTH-2 : s'y désigner elle-même
  fabriquerait un manifeste dont chaque image répond 404 chez le destinataire. Ce n'est pas
  un service d'images qu'on attend là — le manifeste référence de simples JPEG — mais
  l'adresse publique sous laquelle le dossier `derivatives/` sera servi.
- **Il est FACULTATIF, et il a été obligatoire une demi-journée** (renversé le 2026-09-07).
  On ne peut pas nommer l'adresse d'images qu'on n'a pas encore publiées, ce qui est le cas
  de tout le monde avant le premier dépôt : l'exiger interdisait de simplement REGARDER son
  manifeste. Sans adresse, il sort en **aperçu** — identifiants sur le préfixe d'exemple,
  aucune image — et le fichier s'appelle `depot-iiif-apercu-…`. Le NOM porte la
  distinction parce qu'il survit au téléchargement, là où `AVERTISSEMENTS.txt` suppose
  qu'on ouvre l'archive : un aperçu déposé par mégarde serait un dépôt aux images mortes.
- **Les avertissements voyagent DANS l'archive IIIF** (`AVERTISSEMENTS.txt`). La CLI les
  écrit sur `stderr`, où un humain les lit en tapant la commande ; un téléchargement n'a
  personne devant lui. Les perdre effacerait ce qui distingue un dépôt qui *retient* ses
  scans d'un dépôt qui les a *oubliés* — la confusion même que `requiredStatement` existe
  pour empêcher.

Les refus gardent le message de l'outil, au mot près, et prennent le code qui dit la
nature de la panne : **422** pour un `base_url` inutilisable (erreur de saisie), **403**
pour un `verbatim` hors régime (la demande est bien formée, c'est le droit qui manque),
**503** pour un format dont l'extra n'est pas installé (`openpyxl`), en nommant le paquet.

**Ce qui n'est PAS exposé, et pourquoi.** Le **crosswalk** (`crosswalk_depot.py`) et la
**provenance** (`provenance_export.py`) restent en CLI seule. Ce n'est pas un oubli : ce
sont les deux artefacts que l'on produit au moment de DÉPOSER, geste rare, préparé, et qui
suppose déjà un accès à l'entrepôt — là où la fiche, les enregistrements et le manifeste se
consultent en cours de travail pour voir où en est la description. La condition de
réouverture est écrite : dès qu'un dépôt se fait sans que personne n'ait de shell, les deux
suivent par le même patron, qui ne demandera pas de nouvelle décision.

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
  du périmètre sont comptés/scopés. Depuis **A4 (v17)**, chaque terme de vocabulaire porte sa
  **portée d'appartenance** (`collection_id` : NULL = global, sinon local) ; l'indicateur
  **% défini** (`paradonnee.lexique`) est **scopé par appartenance** (global ⊕ local à la
  collection). Cf. `docs/lexique-situe.md`.

## Formats produits

- **Fiche — JSON roll-up** : identité (à prévoir) · **couverture** (nb albums/planches/
  régions/tokens, % validé, couverture OCR, distributions par type/POS) · **provenance**
  (moteurs, modèle NLP) · **qualité** (paradonnée dérivée : relecture, accords ; cf. plus bas)
  · **vocabulaire** facetté · **droits**.
- **Fiche — CSV catalogue** : une ligne = un *élément* de métadonnée (colonnes du
  dictionnaire : provenance, statut, standard, ouvrable) + sa valeur/agrégat. Les
  champs `absent — à prévoir` y figurent **vides** → la sortie est honnête sur la couverture.
- **Enregistrements — JSON arbre** : `collection → albums → planches → régions
  (case ⊃ bulle) → tokens` ; personnages et vocabulaire sortis une fois, référencés par nom.
- **Enregistrements — CSV par niveau** : `collection`, `albums` (avec les champs d'édition
  N0), `contributions`, `contribution_roles`, `planches`, `regions`, `tokens`,
  `annotations`, `tags`, `personnages`, `personnage_attributs`, **`personnage_alignements`**
  (alignement d'autorité A5), `region_attributs`,
  `vocabulaire`, `paradonnee`, **`activite`** + **`evenement`** (journal d'audit A3, grain
  corpus) — dump relationnel recollable par les clés (`album_id`, `planche_id`, `region_id`,
  `parent_id` ; `evenement.activite_id` → `activite.id`). Groupables en `.zip`. Écrits avec un **BOM
  UTF-8** (accents lisibles dans Excel, comme l'export de l'app). Les albums portent aussi
  leurs **contributions** (nom + rôle résolu : bucket DCterms + code MARC) et le catalogue
  **`contribution_roles`** (vocabulaire contrôlé-ouvert). Depuis **A4 (v17)**, `vocabulaire` et
  `tags` portent leur **couche SKOS** (`definition`, `note_portee`, `etat`, `collection_id` ;
  au niveau dimension `dim_*` et valeur) ; depuis **A5 (v18)**, chaque personnage porte ses
  **alignements d'autorité** (`alignements: [{source, uri}]`, chaque `uri` = un
  `skos:exactMatch`) et le roll-up expose `personnages.avec_alignement_autorite` + `pct_aligne`.
  Depuis **A6 (v19)**, les `planches` portent leur **matériel de numérisation** (`dpi_x`,
  `dpi_y`, `mode` + dimensions physiques **dérivées** `largeur_cm`/`hauteur_cm`), les `albums`
  leur `source_numerisation`, et le roll-up expose
  `couverture.planches.materiel` (`avec_resolution`, `pct_avec_resolution`, `par_mode`).
  Depuis **la v20 (piste B)**, une table `domaines` (champs analytiques regroupant les
  dimensions) sort à part, chaque `dimension` du `vocabulaire` porte son `domaine`, et le
  roll-up expose `vocabulaire.domaines` (les domaines comptent aussi dans le « % défini »).
  Depuis **la v21 (ANN-4/B5)**, chaque `planche` porte son **statut de relecture** grammaticale
  **dérivé** (`relecture_statut` : `a_faire`/`en_cours`/`faite`), à côté de `numero_editorial`.
- **Enregistrements — XLSX multi-feuilles** : un onglet par table (dont `tags` et
  `paradonnee`), plus **trois** onglets de confort — **`fiche`** (le roll-up aplati),
  **`qualite`** (tableau de bord relecture + accords, cf. plus bas) et **`arbre`** (hiérarchie
  **repliable** avec les boîtes `x,y,w,h` et un lien « voir » vers la ligne de détail).
  En-têtes gelés + filtres ; les valeurs commençant par `= + - @` sont forcées en texte
  (**anti-injection de formule**). Requiert `openpyxl` (`requirements-export.txt`) ; JSON/CSV
  n'en dépendent pas (import protégé).
- **Paradonnée (niveau 8)** dans les enregistrements : `schema_version`, table `meta`
  (modèle NLP + versions + dates de réindexation), **provenance de l'outil**
  (`outil = {nom, version, revision git}`), et — depuis **A3 (v16)** — le bloc
  **`provenance`** : indicateurs dérivés du journal d'audit
  (`journal.indicateurs_provenance` : part machine vs humaine, **dérive**, comptes de runs &
  d'actes), le détail vivant étant dans les tables `activite`/`evenement`. La fiche
  (`description_collection.py`) porte les mêmes indicateurs sous
  `provenance_globale.audit`. Export standardisé : `tools/provenance_export.py` (PROV-O + TEI).
  Depuis **A4 (v17)**, le bloc **`lexique`** (`database.lexique_resume`) y ajoute la maturité
  du lexique situé (**% défini**, scopé par appartenance) ; la fiche l'expose sous
  `vocabulaire.lexique`.
- **Qualité (paradonnée dérivée)** — bloc `qualite` de la fiche + onglet XLSX `qualite`. Rend
  la fiabilité du corpus lisible et l'IA-de-pré-remplissage **auditable** (valeur FAIR). Trois
  indicateurs, **tout dérivé**, réutilisant les cœurs des surfaces d'analyse (« un modèle,
  plusieurs sérialisations ») :
  - **`relecture`** — part du corpus relu grammaticalement (`a_faire`/`en_cours`/`faite` +
    `pct_faite`), agrégée depuis `database.relecture_planches` sur le périmètre (ANN-4/B5) ;
  - **`accord_modele`** — accord modèle↔humain sur l'échantillon relu, par champ (lemme/POS/
    morpho) + confusion POS, avec le modèle NLP et le nombre de tokens relus (`accord.rapport`,
    NLP-1). **Scopé par `--collection`** (le cœur accepte un filtre d'albums) ;
  - **`accord_inter`** — accord de révision inter-annotateurs (`accord_inter.rapport`, ANN-5),
    lu au **journal A3**. **Portée corpus** (`portee: "corpus"`) : la chaîne de révisions n'est
    pas re-scopée par album (disproportionné pour un bloc creux avant le multi-utilisateur,
    piste C). La fiche n'embarque que les compteurs ; le détail des divergences reste aux
    rapports (`/api/analyse/accord-inter`, `tools/rapport_accord_inter.py`).
  Tier de droits : `ouvert` (aucun verbatim ; simples agrégats de fiabilité).
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

**Ce qu'AUTH-2 a changé, et qui rend le point 1 impératif.** L'application servait
`/derivatives` par un montage statique : pointer `--base-url` vers elle « marchait », par
accident. Elle le sert désormais par une route **cloisonnée** — un manifeste pointant vers
l'application ne montrerait à son destinataire que des `404`, puisqu'il n'a pas de session
Authelia. L'outil pose donc deux garde-fous : il **refuse** d'écrire des manifests
(`--out-dir`) si `--base-url` est resté sur le placeholder, et **avertit** si l'hôte est
local. Aucun des deux ne peut prouver que l'URL désigne un serveur d'images ; ils attrapent
les deux méprises qui se voient.

Ce que ces images doivent devenir — publiques ou non — n'est pas une question d'AUTH-2 mais
de **tiering de droits** (DROIT-1), qui place scans et OCR verbatim dans le palier
RESTREINT, l'enrichissement seul étant ouvert.

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

# Provenance / audit → PROV-O (PROV-JSON) + TEI revisionDesc (cf. docs/provenance-audit.md)
python tools/provenance_export.py --out-dir prov/

# (Re)générer TOUT le jeu d'exemples de docs/exemples/ (corpus de démo jetable)
python tools/regenerer_exemples.py
```
