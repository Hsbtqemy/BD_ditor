# Crosswalk de dépôt — Dublin Core & DataCite

> **But (A2).** Sérialiser la description d'une collection vers les schémas d'entrepôt —
> **Dublin Core** (dcterms, pour Nakala) et **DataCite 4.x** (pour le DOI, réutilisé par
> Nakala/HAL) — afin qu'un dépôt soit *machine-ready*. **Additif** : une sérialisation de
> plus sur le modèle interne existant (cf. `docs/export-metadonnees.md`), lecture seule,
> hors-app (`tools/`), scopable par `--collection`. Ne touche ni au schéma ni aux exports
> existants. Cadre : `docs/dictionnaire-metadonnees.md`.

## Cadrage : un dépôt éditorial, paternité « à la Zotero »

Ce qu'on dépose est un **corpus de BD annoté** (cadrage éditorial), pas un jeu de données
anonyme. Conséquence, décidée le 2026-07-17 : **l'auteur reste l'auteur de l'œuvre**
(dessinateur, scénariste…), et **l'annotateur a son propre rôle** (créateur de la notice).
C'est le modèle Zotero : chaque contribution a un *type* ; « auteur » n'est qu'un type parmi
d'autres.

## Les trois résolutions (validées 2026-07-17)

1. **`publisher` DataCite ≠ éditeur BD.** Au sens DataCite, `publisher` = qui *diffuse le
   dépôt* (l'entrepôt / l'institution), pas Casterman. → l'éditeur BD va en `dc:publisher`
   **au niveau album** (bibliographique) et en `relatedItem` (source) ; `publisher` DataCite
   = l'entrepôt (paramètre `--publisher`, défaut l'institution).
2. **Rôles fins conservés en Dublin Core, pas en DataCite.** La liste `contributorType` de
   DataCite est courte (pas de « coloriste »). → le rôle fin est porté **en DC** via les
   **relators MARC** (le code `contribution_role.marc` est déjà là, ex. `art`, `aut`,
   `clr`) ; en DataCite il retombe en `creator` ou `contributor` (type `Other`). **DC est la
   cible riche pour la paternité.**
3. **Deux granularités.** Une **notice par album** (Zotero pur : `creators` = les auteurs de
   *cet* album) **et** une **notice de collection** (le dépôt lui-même). La collection
   agrège : `creators` = union **dédupliquée** des auteurs d'albums, `contributors` = union
   des contributeurs + annotateurs. `resourceTypeGeneral` : **`Text`** par album (contenu
   langagier ; `Image` possible), **`Collection`** pour la notice de collection. La notice
   collection relie ses albums par `relatedIdentifier` `HasPart`.

## Créateurs & contributeurs — le cœur du mapping

Le `bucket` de `contribution_role` (déjà en base) pilote la répartition ; le `marc` porte le
rôle fin.

| Source interne | Dublin Core | DataCite |
|---|---|---|
| `contribution` où `role.bucket = 'creator'` (scénariste, dessinateur) | `dc:creator` + relator MARC | `creators/creator` |
| `contribution` où `role.bucket = 'contributor'` (coloriste, encreur, lettreur, traducteur, préfacier) | `dc:contributor` + relator MARC | `contributors/contributor` (`contributorType = Other`) |
| **Annotateurs** (`collection.responsables`, puis compte connecté via l'auth) | `dc:contributor` (rôle « annotateur / curateur ») | `contributors/contributor` (`contributorType = DataCurator`) |

- **ORCID** (présent dans `responsables` JSON, ou à terme le compte) → `nameIdentifier`
  (`nameIdentifierScheme = ORCID`) côté DataCite ; `foaf`/URI côté DC.
- **Relators MARC** : sérialisés en DC via les URI LoC (`http://id.loc.gov/vocabulary/relators/{code}`).
- L'annotateur est **auto-alimenté depuis l'auth plus tard** (INFRA-1/2 ; recoupe le
  `auteur` des corrections) ; pour l'instant, depuis `collection.responsables`.

## Crosswalk — niveau album (une notice par œuvre)

| Interne | Dublin Core (dcterms) | DataCite 4.x | Obl. DataCite |
|---|---|---|---|
| `album.titre` | `dc:title` | `titles/title` | ✅ |
| contributions (cf. ci-dessus) | `dc:creator` / `dc:contributor` (+ marcrel) | `creators` / `contributors` | ✅ (≥1 creator) |
| `album.date_edition` | `dcterms:issued` | `dates/date[dateType=Issued]` | — |
| `album.date_originale` | `dcterms:created` | `dates/date[dateType=Created]` | — |
| `album.editeur` (éditeur BD) | `dc:publisher` | `relatedItem` (source) — **pas** `publisher` | — |
| `album.langue` | `dc:language` | `language` | — |
| `album.type_oeuvre` | `dc:type` | `resourceType` (texte) ; `resourceTypeGeneral = Text` | ✅ |
| `album.lieu_edition` | `dcterms:spatial` | `geoLocation` (place) — optionnel | — |
| `album.isbn` | `dc:identifier` | `relatedIdentifier[relatedIdentifierType=ISBN]` | — |
| `album.edition_tirage` | `dcterms:hasVersion` (mention) | `version` (ou description) | — |
| `album.format_physique` | `dcterms:extent` | `sizes` / `formats` | — |
| vocabulaire facetté + tags (liés au périmètre) | `dc:subject` | `subjects/subject` | — |
| `collection.licence_defaut` | `dcterms:license` | `rightsList` (+ `rightsURI` SPDX) | recommandé |
| — (l'entrepôt) | `dc:publisher` (dépôt) | `publisher` | ✅ |
| — (année de dépôt) | `dcterms:issued` (dépôt) | `publicationYear` | ✅ |

## Crosswalk — niveau collection (la notice de dépôt)

| Interne | Dublin Core | DataCite |
|---|---|---|
| `collection.nom` | `dc:title` | `titles/title` |
| `collection.description` | `dc:description` | `descriptions/description[Abstract]` |
| union dédupliquée des `creators`/`contributors` d'albums + annotateurs | `dc:creator` / `dc:contributor` | `creators` / `contributors` |
| chaque album du périmètre | — | `relatedIdentifier[relationType=HasPart]` → notice album |
| `collection.date_debut` / `date_fin` | `dcterms:temporal` | `dates/date[dateType=Collected]` |
| `collection.licence_defaut` | `dcterms:license` | `rightsList` (+ URI SPDX) |
| `collection.base_legale` | `dc:rights` (mention) | `rightsList` (mention libre) |
| `collection.statut_diffusion` (+ `date_embargo`) | `dcterms:accessRights` | `rightsList` / `dates[Available]` (embargo) |
| couverture / provenance (roll-up existant) | `dcterms:extent` · `dc:description[Methods]` | `sizes` · `descriptions[Methods/TechnicalInfo]` |
| — (le dépôt) | `dc:type` = `Collection` | `resourceTypeGeneral = Collection` |
| — (l'entrepôt / année de dépôt) | `dc:publisher` · `dcterms:issued` | `publisher` · `publicationYear` |

## Droits

- `licence_defaut` (ex. `CC-BY-4.0`) → `rightsList/rights` avec **`rightsURI` SPDX**
  (`https://spdx.org/licenses/CC-BY-4.0.html`) ; `dcterms:license` en DC.
- `base_legale` → mention libre (`dc:rights` / `rightsList`) — reste un **prérequis
  hors-code** (décrire, pas imposer).
- `statut_diffusion` (`public` | `embargo` | `restreint` | `prive`) → `dcterms:accessRights`
  et, si `embargo`, `dates/date[dateType=Available]` = `date_embargo`. L'**enforcement**
  reste à l'entrepôt (Nakala gère public/embargo/privé).
- Rappel tiers de droits : l'**OCR verbatim** n'entre **jamais** dans ces notices (contenu
  restreint) ; le crosswalk ne porte que des métadonnées `ouvert`.

## Champs obligatoires par cible (garde-fous)

- **DataCite 4.x** : `Identifier` (DOI — **laissé à l'entrepôt**, cf. hors périmètre),
  `Creators` (≥1), `Titles` (≥1), `Publisher`, `PublicationYear`, `ResourceType`. Le
  générateur **vérifie leur présence** et refuse d'émettre une notice incomplète (ou marque
  le champ manquant, honnête sur la couverture — cf. principe du dictionnaire).
- **Nakala (DC)** : `title`, `type`, `creator`, `created`, `license` (obligatoires). Tous
  couverts par le mapping ci-dessus.

## Sérialisations produites

- `dublin_core.jsonld` — dcterms + relators MARC (JSON-LD, `@context` DCMI/LoC).
- `datacite.xml` — DataCite Metadata Schema 4.x (namespace `http://datacite.org/schema/kernel-4`).
- `datacite.json` — même contenu, DataCite JSON (pour les API REST d'entrepôt).
- Une notice **par album** + une notice **de collection** (avec `--collection`; sinon corpus
  entier = collection implicite, notice collection seule).

## Hors périmètre

- **Le DOI** : c'est l'entrepôt qui le frappe ; on produit la notice **sans** identifiant
  résolu (placeholder / champ laissé à l'entrepôt).
- **La validation officielle** : au dépôt (schéma DataCite de l'entrepôt ; Nakala). En local,
  on peut valider la **conformité structurelle** au schéma DataCite (XSD) si souhaité, comme
  pour l'IIIF (`tools/valider_iiif.py`).

## Où ça se branche

Nouvelle sérialisation `tools/` (extension de `description_collection.py`, qui porte déjà le
roll-up identité/couverture/provenance/droits, **ou** `tools/crosswalk_depot.py` dédié).
Lecture seule ; réutilise le **modèle interne** (mêmes dérivations : citation, contributions
avec `bucket`/`marc`, vocabulaire, droits). `--collection <id>` scope le périmètre ;
`--publisher`, `--annee-depot` paramètrent les champs propres au dépôt.
