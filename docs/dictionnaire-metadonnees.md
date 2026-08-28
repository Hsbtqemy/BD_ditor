# Dictionnaire de métadonnées

> **But.** Donner accès, de façon granulaire, à **toutes les informations disponibles à
> partir d'une planche scannée** — du jeu de données (collection) et de l'œuvre
> bibliographique jusqu'au mot analysé — en distinguant ce qui est *produit par la machine*, *ajouté par l'humain*,
> *dérivé*, ou *encore à prévoir*. Document de référence pour la réutilisation, la
> qualification du travail (paradonnée) et le futur dépôt (Nakala / HAL).
>
> **Périmètre.** Documente le **réel** (schéma v18) **et** les **champs à prévoir** qu'un
> dépôt de qualité bibliographique voudra. Ne fige aucun plan : c'est un inventaire, pas
> un PGD. Voir aussi `personnages-et-attribution.md`, `numerotation-et-citation.md`,
> `correction-grammaticale.md`.

## Conventions de lecture

Chaque niveau est une table dont les colonnes sont : **Élément · Qualifie · Forme &
valeurs · Provenance · Statut · Standard cible · Ouvrable ?**

**Provenance** — d'où vient la donnée :

| | |
|---|---|
| `descriptif` | saisi à la main pour décrire l'œuvre (bibliographique) |
| `machine`    | produit par un moteur (segmentation, détection, OCR, NLP), **éditable** |
| `humain`     | travail interprétatif ou correctif de l'annotateur |
| `dérivé`     | recalculé à la volée, **jamais stocké** |
| `matériel`   | décrit le support (physique / numérique) |
| `système`    | technique / administratif (identifiants, dates, versions) |

**Statut** — comment c'est stocké :

| | |
|---|---|
| `structuré`        | colonne typée, valeur atomique ou contrôlée |
| `libre`            | colonne texte libre |
| `dérivé`           | calculé à la demande, non persisté |
| `absent — à prévoir` | pas encore dans le modèle ; utile pour un dépôt qualité |

**Ouvrable ?** — régime de diffusion (cf. discussion droits ; à valider juridiquement) :

| | |
|---|---|
| `ouvert`   | fait ou dérivation → diffusable (CC-BY / CC0) |
| `restreint`| expression protégée (scan, **texte verbatim**) → non rediffusable |
| `agrégat`  | ouvert **sous forme agrégée** (fréquences), restreint en verbatim aligné |

**Standard cible** : `DC` Dublin Core · `TEI` TEI P5 · `UD` Universal Dependencies ·
`SKOS` thésaurus · `PROV` W3C PROV-O · `IIIF` IIIF / W3C Web Annotation.

## Trois axes transverses

- **Provenance & paradonnée.** Le modèle sépare partout *machine* (pré-remplissage
  éditable), *humain* (souverain, jamais écrasé) et *dérivé*. C'est ce qui **qualifie le
  travail** : qui a produit quoi, dans quel état de validation. À généraliser (versions
  des moteurs, provenance au niveau du *run*) pour un corpus pleinement réutilisable.
- **Droits.** La ligne ouvert / restreint traverse la couche de contenu : coordonnées,
  structure, abstractions linguistiques, annotations et entités sont **ouvrables** ; les
  scans et le **texte OCR verbatim** (expression protégée) restent **restreints**.
- **Standards.** La couche linguistique parle déjà **UD** ; deux exports sont déjà des
  standards (**TEI P5**, **JSON-LD**). Les cibles non encore atteintes (`IIIF`, `SKOS`,
  `PROV`) sont marquées champ par champ.

## Trois paliers de description

La description se lit à trois échelles emboîtées — la **collection** est le palier qui
manquait, et le plus haut :

| Palier | Décrit… | Niveaux | Cible |
|---|---|---|---|
| **Collection** | le *corpus / jeu de données* | *(v14)* | fiche de dépôt · description PGD |
| **Item — album** | chaque *œuvre* | 0 | Dublin Core |
| **Élément** | *planche · zone · token* (structure, contenu, langue) | 1–8 | TEI · IIIF · UD |

---

## Collection (corpus) — palier supérieur

Source : table `collection` + liaison `collection_album` (appartenance **N-N**,
album ∈ 0..N collections) — **réalisé (schéma v14)**. Palier qui décrit **le jeu de données
lui-même** — une sélection constituée pour une étude. **Transversal** (un album peut vivre
dans plusieurs collections) et **unité de dépôt** : une collection = un dépôt Nakala/HAL =
un DOI = la « description des données » d'un PGD. Gestion **hors-app** :
`tools/gerer_collections.py` (créer / ranger des albums / éditer) ; les exports acceptent
`--collection <id>` pour scoper leur périmètre. Restent *à prévoir* le gel versionné et le
PID (dormants).

Décisions de conception (2026-07-15) : entité nommée `collection` (« corpus » déjà pris par
`CORPUS_DIR` et la page bibliothèque) ; appartenance **statique et figeable** (composition
stable → citable), quitte à la **construire** depuis un filtre puis la geler ; outil
**nourricier** d'un PGD externe (dérive ce qu'il sait, pointe vers OPIDoR / Argos).

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `collection.nom` | nom du corpus / jeu | texte | descriptif | structuré (v14) | DC:title | ouvert |
| `collection.description` | objet, périmètre, critères de sélection | texte | descriptif | libre (v14) | DC:description | ouvert |
| `collection.licence_defaut` | régime de diffusion du **jeu enrichi** | licence / mention | descriptif | structuré (v14) | DC:rights / DataCite | ouvert |
| `collection.base_legale` | base légale d'accès/usage des **données** (scans, verbatim) — **à établir** (piste : exception TDM recherche, à valider) | mention + source + date | descriptif / paradonnée | libre (v14) | DC:rights / PROV | ouvert |
| `collection.statut_diffusion` | régime d'accès du jeu : `public` \| `embargo`(date) \| `restreint`(sur accord) \| `privé` | contrôlé | descriptif | structuré (v14) | DataCite / Nakala | ouvert |
| `collection.responsables` | qui constitue / gère le corpus | JSON `[{nom, rôle, orcid?}]` (forme `contribution`) | descriptif | structuré (v14) | DC:creator / PROV | ouvert |
| `collection.dates` | période de constitution / couverture (`date_debut`/`date_fin`) | dates | descriptif | structuré (v14) | DC:date · DC:coverage | ouvert |
| `collection_album` | appartenance album ↔ collection (statique, avec `rang`) | liaison N-N | humain | structuré (v14) | — | ouvert |
| `couverture / volume` | ampleur du jeu (nb albums/planches/régions/tokens) | agrégats | dérivé | dérivé (export) | DC:extent | ouvert |
| `provenance globale` | moteurs / modèles + versions ayant produit le jeu | agrégat paradonnée | dérivé | dérivé (export) | PROV | ouvert |
| `description PGD dérivée` | sections data-description / formats pour le dépôt | export dérivé | dérivé | absent — à prévoir | — | ouvert |
| *`version / gel`* | instantané citable (corpus v1, v2) | texte + horodatage | système | absent — à prévoir *(dormant)* | DataCite version / PROV | ouvert |
| *`PID`* | DOI du dépôt de la collection | URI résoluble | système | absent — à prévoir *(dormant)* | DataCite | ouvert |
| *`appartenance fine`* | sélection au niveau planche / région | liaison | humain | absent — à prévoir *(dormant)* | — | ouvert |

> **Casquette double.** Ce palier **porte** de la description (lignes ci-dessus) **et** sert
> d'**ancrage fonctionnel** — unité de dépôt / DOI, régime de droits par défaut, et **portée
> du lexique situé** (la « portée local » du Niveau 7 référencera `collection_id`).

> **Droits — décrire, et imposer À LA SORTIE (2026-07-16, précisée le 2026-08-28).** Ces
> champs *déclarent* le régime. Ils ne l'imposent pas **à l'intérieur de l'instance** :
> quiconque est admis sur une collection en reçoit tout, scans compris — le travail
> d'annotation REPOSE sur les images, et l'usage interne relève de la recherche. Le
> cloisonnement entre équipes est l'affaire d'AUTH-2/AUTH-3, pas du régime de diffusion.
>
> Ils l'imposent en revanche **là où la donnée quitte l'outil**, et c'est la précision
> qu'apporte DROIT-1 : une déclaration doit mordre au moment de la publication, sinon elle
> ne mord nulle part. Deux gestes s'y distinguent, et rien ne les rapproche :
>
> - **PUBLIER** — mettre un corpus à disposition (manifeste IIIF, paquet de dépôt). Porte
>   sur une collection entière et n'emporte d'images que si elle est déclarée `public`. La
>   règle est fail-closed : *publier suppose de nommer la collection qu'on publie*, ce qui
>   règle aussi le cas d'un album vivant dans plusieurs collections (AUTH-3) sans inventer
>   d'arbitrage. Un manifeste privé de ses scans le DÉCLARE (`requiredStatement`) — sans
>   quoi « retenir » et « oublier » se ressemblent.
> - **CITER** — extraire une case identifiée pour l'accompagner d'un discours (article,
>   communication). Jamais bloqué par le régime : c'est l'usage que la recherche revendique,
>   et un fonds sous droits est justement celui qu'on cite plutôt que de le diffuser. Le
>   régime ACCOMPAGNE l'extrait au lieu de l'interdire — la figure sort avec sa référence,
>   sa licence et sa base légale. Cf. `figure.py` et `docs/figure-citable.md`.
>
> L'enforcement de l'ACCÈS reste au portail d'auth (`docs/deploiement-docker.md`) et à
> l'entrepôt (Nakala gère public/embargo/privé, en séparant visibilité des métadonnées et
> accès aux fichiers). Ce qui change n'est pas là : c'est ce que l'outil accepte de
> FABRIQUER pour l'extérieur.
>
> **Deux services Huma-Num, deux côtés de la frontière** (2026-08-28). ShareDocs et Nakala
> ont le même opérateur, ce qui les fait confondre — ils ne sont pas du même côté de l'axe
> DEDANS / DEHORS, et c'est ce qui décide si le régime mord.
>
> - **ShareDocs est le stockage VIVANT** : modifiable, appelable à tout moment, un espace
>   de travail. C'est là que vivent les ressources (masters, PDF, sauvegardes), sans
>   question de droits : un disque distant de l'instance. Y déposer n'est donc pas PUBLIER,
>   et `statut_diffusion` n'y borde rien — pas plus qu'il ne borde à l'intérieur de
>   l'instance. Ce qui réserve `POST /api/sharedocs/deposer-sauvegarde` aux administrateurs
>   n'est pas le régime de diffusion mais deux autres raisons : sauvegarder est un geste
>   d'exploitation, et l'application ne contrôle pas le partage du dossier d'arrivée.
> - **Nakala est l'entrepôt du FIGÉ** : ce qu'on y dépose est traité, nettoyé, travaillé —
>   et ne bouge plus. Archivage, open science, DOI. C'est là que la déclaration mord. Et ce
>   qu'on y dépose est d'abord le **manifeste et ses Canvas** — la géométrie et
>   l'enrichissement — bien plus que les planches elles-mêmes. Le manifeste sans images
>   n'est donc pas un mode dégradé qu'on subit : c'est la forme NORMALE du dépôt, et c'est
>   la raison pour laquelle le Canvas devait survivre sans son image.
>
> **Ce que « figé » impose aux artefacts.** Un artefact qui ne bouge plus doit dire DE QUAND
> IL DATE, sans quoi deux dépôts du même album à un an d'intervalle sont indistinguables —
> et l'entrepôt ne remplace pas le premier, il garde les deux. Les notices posaient déjà
> `genere_le`, la figure citable `date_export` ; le manifeste, lui, ne datait rien (corrigé
> le 2026-08-28 : entrée `metadata` « Manifeste généré le »).
>
> Le cas est plus aigu pour la DÉCLARATION DE DROITS qu'il porte. « Les images de ce corpus
> ne sont pas diffusées (régime : restreint) », figé dans un entrepôt, l'affirmera encore le
> jour où la collection sera passée `public` : intemporelle, l'assertion devient fausse sans
> que personne mente. Datée — « Constat du 2026-08-28 » — elle redevient ce qu'elle est, un
> constat que son lecteur peut aller vérifier à la source.
>
> **`date_embargo` RETIENT, elle ne PROMEUT jamais** (2026-08-28). Une collection `public`
> dont l'embargo court encore ne fait pas sortir ses scans : la date est plus restrictive
> que le statut, donc la date gagne. Mais une échéance passée ne publie rien d'elle-même —
> parce que l'outil ignore POURQUOI l'embargo existe. Un délai qu'on s'est donné
> (soutenance, accord d'éditeur) se lève de soi-même ; un délai imposé par un ayant droit
> ne se lève pas, et son échéance dit que la contrainte a couru, pas que les droits sont à
> nous. Le champ qui trancherait, c'est `base_legale`, et il est vide par construction. La
> bascule appartient donc à l'entrepôt, à qui la date est transmise.
>
> Ne rien faire ne veut pas dire **se taire** : une échéance dépassée est SIGNALÉE (écran
> Collections, générateur de manifestes, `gerer_collections.py voir`). Un embargo échu que
> personne ne remarque garde un corpus fermé par inertie — ce qui trahit l'orientation
> open-science aussi sûrement qu'une fuite trahit les droits. Et une date qu'on ne sait pas
> lire retient elle aussi, en le disant : une faute de frappe ne doit pas ouvrir la porte,
> ni passer pour une décision.
>
> **`base_legale` est un prérequis au dépôt, hors code** (institution + source des scans) :
> tant qu'elle n'est pas établie, elle reste une **question ouverte, jamais une conclusion**
> — et la figure citable l'écrit telle quelle, « base légale non établie », plutôt que de
> laisser un blanc qui se lirait comme un problème réglé.
>
> **La surcharge par Album est ABANDONNÉE** (2026-08-28), après avoir été annoncée ici. La
> raison n'est plus la même qu'à l'écriture : depuis AUTH-3 un album vit dans PLUSIEURS
> collections, si bien qu'« un défaut Collection surchargeable par Album » n'a plus de
> défaut unique à surcharger. Le besoin réel — un corpus mêlant domaine public et œuvres
> sous droits — se traite en constituant deux collections, ce que l'appartenance N-N rend
> possible sans dupliquer les albums.

---

## Niveau 0 — Œuvre / album

Source : table `albums`. Couche **descriptive**, aujourd'hui **mince et surtout en texte
libre** — principal chantier pour une qualité bibliographique.

> **Décision (2026-07-15) — enrichissement descriptif.** Paternité en modèle **Zotero-like** :
> `contribution(nom, rôle)` par album, le **rôle** en vocabulaire **contrôlé-mais-ouvert** (jeu
> curé extensible — même forme que tags/attributs — de source **MARC Relators**, mappé aux
> buckets **DCterms** `creator`/`contributor`). Le nom reste une chaîne, **aliasable** vers un
> contributeur-entité alignable (VIAF/IdRef) plus tard — dormant (patron *mentions→entités*).
> Œuvre vs édition : **un seul niveau** = l'édition détenue ; `date_edition` est **l'ancre**,
> `date_originale` (1re parution) reste **optionnelle/secondaire** (on exploite le scanné).
> Les champs `auteur`/`annee` restent en *legacy*.
>
> **✅ Réalisé (schéma v15)** : tables `contribution` (N-N) + `contribution_role` (vocabulaire
> semé, ouvert), 8 colonnes d'édition sur `albums`. API (`/api/albums/{id}/contributions`,
> `/api/contribution-roles`, champs d'édition sur album), UI Bibliothèque (section Édition +
> éditeur de contributions), et câblage export (metadonnees/description/IIIF). Restent *à
> prévoir* : contributeur-**entité** alignable (VIAF/IdRef, dormant) et **PID**.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `id` | identifiant interne de l'œuvre | entier (PK) | système | structuré | — | ouvert |
| `titre` | titre de l'œuvre | texte | descriptif | structuré | DC:title | ouvert |
| `auteur` | responsabilité(s) — *champ legacy* | texte **libre, non décomposé** (→ voir `contribution`) | descriptif | libre | DC:creator | ouvert |
| `annee` | année — *legacy ambigu* | entier (→ précisé par `date_edition` / `date_originale`) | descriptif | structuré | DC:date | ouvert |
| `editeur` | maison d'édition | texte | descriptif | libre | DC:publisher | ouvert |
| `serie` | série d'appartenance | texte | descriptif | libre | DC:isPartOf | ouvert |
| `description` | note libre sur l'œuvre | texte | descriptif | libre | DC:description | ouvert |
| `date_import` | date d'entrée dans l'outil | horodatage | système | structuré | PROV | ouvert |
| `nombre de pages` | volume de l'album | entier | dérivé (compte des planches) | dérivé | DC:extent | ouvert |
| `contribution` | contributeur de l'album (**Zotero-like** : (nom, rôle)) | liaison N-N | descriptif | structuré (v15) | DCterms creator/contributor | ouvert |
| `contribution.role` | rôle du contributeur | vocabulaire **contrôlé-mais-ouvert** `contribution_role` (seed : scénariste · dessinateur · coloriste · encreur · lettreur · traducteur · préfacier) | descriptif | structuré (v15) | MARC Relators | ouvert |
| *`contributeur` (entité)* | alias du nom vers une personne canonique alignable | réf. entité + URI | descriptif | *absent — à prévoir (dormant)* | VIAF / IdRef / ISNI | ouvert |
| `date_edition` | publication de l'**édition détenue** (l'ancre) | date | descriptif | structuré (v15) | DC:issued | ouvert |
| `date_originale` | 1re parution de l'œuvre — *optionnel, secondaire* | date | descriptif | structuré (v15) | DC:created | ouvert |
| `type_oeuvre` | BD / roman graphique / strip… | contrôlé-ouvert | descriptif | structuré (v15) | DC:type | ouvert |
| `langue` | langue de l'expression (**traduction = autre texte**) | code (fr…) | descriptif | structuré (v15) | DC:language | ouvert |
| `lieu_edition` | ville de publication (édition détenue) | texte | descriptif | structuré (v15) | DC:coverage | ouvert |
| `edition_tirage` | mention d'édition | texte | descriptif | structuré (v15) | DC | ouvert |
| `isbn` | ISBN / dépôt légal (édition détenue) | code | descriptif | structuré (v15) | DC:identifier | ouvert |
| `format_physique` | dimensions du support (cm), reliure de l'œuvre | mesures | matériel | structuré (v15) | DC:format | ouvert |
| `source_numerisation` | appareil / conditions de scan (campagne = album) | texte | matériel | **structuré (v19)** | PREMIS | ouvert |
| *`PID`* | identifiant pérenne (DOI/ARK) | URI résoluble | système | *absent — à prévoir* | DataCite | ouvert |
| *`droits (surcharge)`* | `statut_diffusion` / `base_legale` propres à l'album (défaut = Collection) | idem Collection | descriptif | *absent — à prévoir* | DC:rights | ouvert |

## Niveau 1 — Planche

Source : table `planches`. Couche **éditoriale + technique + matérielle + cycle de vie**.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `id` | identifiant interne de la planche | entier (PK) | système | structuré | — | ouvert |
| `album_id` | rattachement à l'œuvre | entier (FK) | système | structuré | — | ouvert |
| `numero` | ordre d'import (page **physique**) | entier (unique/album) | système | structuré | — | ouvert |
| `role` | statut éditorial | contrôlé : `recit` \| paratexte | humain | structuré | — | ouvert |
| `numero_editorial` | rang cité parmi les planches `recit` | entier \| ∅ (paratexte) | dérivé | dérivé | — | ouvert |
| `chemin_tiff` | pointeur vers le master | chemin relatif POSIX | système | structuré | — | **restreint** |
| `chemin_web` | pointeur vers le dérivé web | chemin relatif POSIX | système | structuré | IIIF (image) | **restreint** |
| `largeur_px` / `hauteur_px` | dimensions **master** | entiers (px) | matériel | structuré | TEI `surface @lrx/@lry` | ouvert |
| `statut` | avancement de traitement | `importee` \| `segmentee` | système | structuré | — | ouvert |
| `date_segmentation` | date de la passe cases | horodatage | paradonnée | structuré | PROV | ouvert |
| `validee` | validation humaine de la planche | horodatage \| ∅ | humain | structuré | PROV | ouvert |
| `verrouillee` | protection contre les passes auto | horodatage \| ∅ | humain | structuré | — | ouvert |
| `dpi_x` / `dpi_y` | résolution du scan | paire d'entiers | matériel | **structuré (v19)** — capté à l'ingest | — | ouvert |
| `mode` | espace colorimétrique | `RGB`/`CMYK`/`L`… | matériel | **structuré (v19)** — capté à l'ingest | — | ouvert |
| `dimensions_physiques` | taille réelle (cm) | px ÷ dpi | dérivé | **dérivé (v19)** — jamais stocké | DC:format | ouvert |

> **`source de numérisation`** (appareil / conditions de scan) vit au niveau **album**
> (`albums.source_numerisation`, v19) : une campagne de scan = un album. Cf. le niveau 0 et
> `docs/materiel-numerisation.md`.

## Niveau 2 — Région / zone

Source : table `regions` (arbre par `parent_id`). Couche **géométrique + structurelle**.
Coordonnées **toujours en pixels master**.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `id` | identifiant interne de la zone | entier (PK) | système | structuré | — | ouvert |
| `planche_id` | rattachement à la planche | entier (FK) | système | structuré | — | ouvert |
| `parent_id` | contenance hiérarchique (bulle ∈ case) | entier (FK) \| ∅ | machine (géométrie) / humain | structuré | TEI (imbrication) | ouvert |
| `type` | nature de la zone | contrôlé `TYPES_REGION` : case · bulle · cartouche · texte · personnage | machine / humain | structuré | TEI `zone @type` | ouvert |
| `x` · `y` · `w` · `h` | boîte englobante | entiers, **px master** | machine → humain | structuré | TEI `zone @ulx…` · **IIIF `xywh`** | ouvert |
| `ordre` | rang de lecture entre frères | entier (1..N per-niveau) | machine → humain | structuré | — | ouvert |
| `source` | producteur de la géométrie | `kumiko` \| `auto` \| manuel | provenance | structuré | PROV | ouvert |
| `date_creation` | date de création de la zone | horodatage | paradonnée | structuré | PROV | ouvert |
| `citation` | repère éditorial cité | dérivé `pl·c·b` | dérivé | dérivé | — | ouvert |
| `activite_id` | run qui a **généré** la zone (→ moteur+version+params) | réf. activité | paradonnée | **structuré (v16)** | PROV `wasGeneratedBy` | ouvert |
| `touche` + `date_modification` | zone retouchée par l'humain, et quand (surface au-dessus du journal) | drapeau + horodatage | paradonnée | **structuré (v16)** | PROV / TEI `@resp` | ouvert |
| *`certitude`* | confiance sur la zone | score \| niveau | machine / humain | *absent — à prévoir* | TEI `@cert` | ouvert |

## Niveau 3 — Contenu textuel (OCR)

Source : `regions.ocr_texte`. **Le seul champ de contenu franchement restreint** : le
dialogue est de l'expression protégée.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `ocr_texte` | texte reconnu de la zone | texte libre | machine (pré-remplit, `only_empty`) → humain | libre | TEI `line` | **restreint** |

## Niveau 4 — Analyse linguistique

Sources : `tokens` (auto, régénéré), `token_correction` (overlay humaine préservée),
vue `tokens_effectifs` (**read model canonique** — toutes les analyses lisent ceci).

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `tokens.ordre` | position du mot | entier | machine | structuré (régénéré) | UD | ouvert |
| `tokens.texte` | forme de surface (mot exact) | texte | machine | structuré (régénéré) | UD `FORM` | **agrégat** |
| `tokens.lemme` | forme canonique | texte | machine | structuré (régénéré) | UD `LEMMA` | ouvert |
| `tokens.pos` | catégorie grammaticale | contrôlé **UPOS** | machine | structuré (régénéré) | UD `UPOS` | ouvert |
| `tokens.morph` | traits morphologiques | **UD FEATS** | machine | structuré (régénéré) | UD `FEATS` | ouvert |
| `token_correction.lemme/pos/morph` | correction humaine | idem UD | humain | structuré (overlay préservée) | UD | ouvert |
| `token_correction.forme` | forme visée (ancrage anti-dérive) | texte | humain | structuré | — | agrégat |
| `token_correction.etat` | état de la correction | `corrige` \| `valide` | humain | structuré | PROV | ouvert |
| `token_correction.auteur` | qui a corrigé / validé | texte (identité) | humain | structuré | PROV / TEI `@resp` | ouvert |
| `token_correction.date_modif` | quand | horodatage | paradonnée | structuré | PROV | ouvert |
| `token_correction.obsolete` | correction à revérifier (texte a changé) | 0/1 | système | structuré | — | ouvert |
| `tokens_effectifs.provenance` | valeur effective : `auto` \| `corrige` \| `valide` | contrôlé | dérivé | dérivé (vue) | PROV | ouvert |
| `tokens_effectifs.a_revoir` | une correction a dérivé | 0/1 | dérivé | dérivé (vue) | — | ouvert |

## Niveau 5 — Annotation interprétative

Sources : `annotations`, `tags`, `annotation_tags`. **Travail humain** — pleinement le
tien, donc ouvrable.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `annotations.note` | commentaire libre sur la zone | texte | humain | libre | TEI `note` | ouvert |
| `annotations.date_creation` / `date_modification` | vie de l'annotation | horodatages | paradonnée | structuré | PROV | ouvert |
| `tags.label` | étiquette (catégorie **émergente**) | texte unique | humain | structuré (contrôlé émergent) | SKOS `prefLabel` | ouvert |
| `tags.description` | glose du tag | texte | humain | libre | SKOS `definition` | ouvert |
| `tags.couleur` | présentation | code couleur | humain | structuré | — | ouvert |
| `annotation_tags` | pose d'un tag sur une annotation | liaison N-N | humain | structuré | — | ouvert |

## Niveau 6 — Entités personnages

Sources : `personnages` (entité canonique **corpus**), `bulle_locuteur` (qui parle),
`personnage_presence` (qui est montré), `personnage_alignement` (référentiels externes, v18).
Cf. `personnages-et-attribution.md`, `alignement-autorite.md`.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `personnages.nom` | identité récurrente | texte | humain | structuré | — | ouvert |
| `personnages.serie` | désambiguïsation (homonymes) | texte | humain | structuré | — | ouvert |
| `personnages.notes` | note libre sur l'entité | texte | humain | libre | — | ouvert |
| `bulle_locuteur` | **qui parle** dans la bulle | lien région ↔ personnage | humain | structuré | — | ouvert |
| `personnage_presence` | **qui est montré** dans la boîte | lien région ↔ personnage | humain | structuré | — | ouvert |
| `personnage_alignement` (source, uri) | **alignement d'autorité** : un personnage → 0..N URI de référentiel | table (source auto-détectée) | humain | **structuré (v18)** | SKOS `exactMatch` | ouvert |
| `% aligné` | part des personnages alignés (qualité Collection) | agrégat | dérivé | **dérivé (v18)** | — | ouvert |

## Niveau 7 — Vocabulaire facetté

Sources : `domaine` (champs analytiques), `attribut_dimension` (axes), `attribut_valeur`
(valeurs canoniques), `personnage_attribut` (profil du locuteur), `region_attribut`
(situation de scène). Vocabulaire **émergent** (données, pas code). Le **définitionnel + la
portée** sont le chantier « lexique agile mais défini ».

> **Décision (2026-07-18) — domaines analytiques. Livré v20 (piste B).** Palier `domaine`
> qui **regroupe les dimensions** par champ d'étude (émotions, représentation…) — les émotions
> ne sont **qu'un domaine**. Émergent + lexique SKOS comme le reste ; **`domaine_id` nullable**
> sur `attribut_dimension` (NULL = hors domaine ; suppression du domaine → NULL, promotion).
> **ORTHOGONAL à `cible`** (un domaine groupe des dimensions personnage ET case). Édité dans le
> panneau 📖 Lexique. **Dormant** : nouveaux types d'ancre (planche/album/scène). Cf.
> `docs/domaines.md`.

> **Décision (2026-07-15) — lexique situé (SKOS). Livré v17 (A4).** Couche définitionnelle **en
> paresseux** : `definition` + `note_portee` optionnelles sur dimensions **et** valeurs **et
> tags** (pour un tag, `description` EST la definition), avec un état `provisoire → défini`
> (miroir `auto→validé`). **Portée d'appartenance (A)** : `collection_id` nullable partout (NULL
> = global, sinon local à une collection) ; promotion local→global = passer à NULL (patron
> *mentions→entités* ; supprimer une collection PROMEUT ses termes via `ON DELETE SET NULL`).
> Édition par l'API (`PATCH …/lexique`) et l'UI (bouton **📖 Lexique** sur Exploration, modale
> accessible). Indicateur « **% défini** » (`database.lexique_resume`) dans les exports.
> **Définition contextuelle (B)** — glose d'un terme *par collection* (`valeur_definition`) —
> **dormante** ; version de concept **dormante** (gel au niveau Collection). Cf.
> `docs/lexique-situe.md`.

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `domaine` | champ analytique regroupant des dimensions (émotions, représentation…) | texte émergent | humain | **structuré (v20)** | SKOS | ouvert |
| `attribut_dimension.cible` | à quoi s'applique l'axe | `personnage` \| `case` | humain | structuré | — | ouvert |
| `attribut_dimension.domaine_id` | domaine analytique de rattachement (NULL = hors domaine) | réf. \| NULL | humain | **structuré (v20)** | SKOS | ouvert |
| `attribut_dimension.nom` | axe (origine, registre…) | texte émergent | humain | structuré | SKOS (schéma) | ouvert |
| `attribut_valeur.valeur` | valeur canonique de l'axe | texte émergent | humain | structuré | SKOS `concept` | ouvert |
| `personnage_attribut` | profil du personnage (inter-locuteur) | liaison N-N | humain | structuré | — | ouvert |
| `region_attribut` | situation de la case (intra-locuteur) | liaison N-N | humain | structuré | — | ouvert |
| `collection_id` (dimension · valeur · **tag**) | **portée d'appartenance** : NULL = global, sinon local à une collection ; promotion → NULL (*mentions→entités*) | réf. \| NULL | humain | **structuré (v17)** | SKOS | ouvert |
| `definition` | sens de la dimension / valeur (**tag** : `description`) | texte | humain | **structuré (v17)** | SKOS `definition` | ouvert |
| `note_portee` | cadre d'emploi (le « situé ») | texte | humain | **structuré (v17)** | SKOS `scopeNote` | ouvert |
| `etat` (définitionnel) | maturité : `provisoire` → `defini` (miroir `auto→validé`) | contrôlé | humain | **structuré (v17)** | — | ouvert |
| `% défini` | part du vocabulaire documenté (nourrit la qualité Collection) | agrégat | dérivé | **dérivé (v17)** | — | ouvert |
| *`valeur_definition` (B)* | **définition contextuelle** : glose d'un terme *par collection* | table (valeur_id, collection_id…) | humain | *absent — à prévoir (dormant)* | SKOS | ouvert |
| *`version`* | version du concept | texte | système | *absent — à prévoir (dormant)* | SKOS / PROV | ouvert |

## Niveau 8 — Paradonnée / système

Source : table `meta` (clé/valeur) **et**, depuis la **v16 (A3, livré 2026-07-17)**, une
**couche d'audit** (`activite`/`evenement`). Documente **le processus** — reproductibilité et
**qualification du travail**. Détail : `docs/provenance-audit.md`.

> **Décision (2026-07-15) — audit complet en journal *append-only* (lecture B). Livré v16.**
> Les tables restent la source de vérité ; un **journal d'événements immuable** enregistre en
> plus chaque acte de transformation/annotation, **sans inverser la base**. Portée : les
> *actes* (segmentation, bulles, OCR, NLP, édition de zone, correction, validation,
> annotation, lien d'entité) — **un événement par action**. Agent = identité humaine (auth,
> capté par contextvar) **ou** moteur + version + paramètres. Les passes en lot = une
> **activité (run)** parente de ses événements. La dérive machine↔humain est **récupérable
> depuis le journal** (avant/après) ; les entités ne portent qu'un `touché`/`date_modification`
> dénormalisés. Exporté **PROV-O** (`wasGeneratedBy` / `used` / `wasInvalidatedBy`) et **TEI
> `revisionDesc`/`change`** (`tools/provenance_export.py`). Les agrégats
> (`journal.indicateurs_provenance`) remontent nourrir la « provenance globale » de la
> **Collection**. Le journal **survit à la suppression** de sa cible → substrat de l'**undo
> (D1)**, désormais débloqué (l'endpoint/UI d'undo reste D1).

| Élément | Qualifie | Forme & valeurs | Provenance | Statut | Standard | Ouvrable ? |
|---|---|---|---|---|---|---|
| `meta.nlp_model` / `nlp_spacy` | modèle NLP ayant produit l'index | texte (nom+version) | paradonnée | structuré | PROV | ouvert |
| `meta.nlp_reindexed_count` / `_at` | ampleur & date de la réindexation | entier / horodatage | paradonnée | structuré | PROV | ouvert |
| `SCHEMA_VERSION` (`user_version`) | version du schéma | entier | système | structuré | — | ouvert |
| `activite` (run) | exécution de passe : type, agent+version, params, date, portée, comptes | table | paradonnée | **structuré (v16)** | PROV `Activity` | ouvert |
| `evenement` (journal) | acte atomique immuable : type, agent, cible, avant/après, date, `activite_id` | table **append-only** | paradonnée | **structuré (v16)** | PROV / TEI `change` | ouvert |
| `regions.activite_id` | lien entité → run producteur | référence | paradonnée | **structuré (v16)** | PROV `wasGeneratedBy` | ouvert |
| `regions.touche` / `date_modification` | surface dénormalisée (entité retouchée, quand) | drapeau + horodatage | paradonnée | **structuré (v16)** | PROV / TEI `@resp` | ouvert |
| `indicateurs de couverture` | % touché · dérive · runs · actes (machine/humain) | agrégats **dérivés du journal** | dérivé | **dérivé (v16)** | — | ouvert |
| *`licence & droits`* | régime de diffusion par jeu | licence / mention | descriptif | *absent — à prévoir* | DC:rights / DataCite | ouvert |

---

## Synthèse — ce qui part au dépôt

L'**unité de partage est la collection** (une collection = un dépôt = un DOI). Au sein de
cette unité, trois régimes de diffusion :

| Tier | Contenu | Régime |
|---|---|---|
| **Ouvert** (CC-BY / CC0) | descriptif · géométrie · structure · ordre · provenance/paradonnée · lemme/POS/morph · tags · notes · personnages · attributs · métriques matérielles | diffusable + DOI |
| **Agrégat** | formes de surface (`texte`/`forme`) sous forme de fréquences/distributions | diffusable agrégé, restreint en verbatim aligné |
| **Restreint** | scans (`chemin_*`) · **texte OCR verbatim** | détenu (exception TDM), non rediffusé — accès sur accord |

## Récapitulatif des champs « à prévoir »

Chantiers de FAIRisation dérivés de ce dictionnaire, par couche :

- **Collection (palier supérieur)** : **réalisé (v14)** — `collection` + `collection_album`
  (N-N statique avec `rang`), descripteurs de jeu (nom, description, licence, base légale,
  statut de diffusion, responsables, dates), agrégats dérivés à l'export (couverture,
  provenance globale). Gestion : `tools/gerer_collections.py` ; scope d'export : `--collection`.
  Restent *à prévoir* : gel versionné et PID (dormants), appartenance fine planche/région
  (dormant), description PGD dérivée.
- **Descriptif (N0)** : **✅ réalisé (v15)** — **contribution** Zotero-like (nom + rôle
  contrôlé-ouvert, DCterms / MARC Relators) · `date_edition` (ancre) + `date_originale` ·
  langue · type · lieu · tirage · ISBN · format. Restent *à prévoir* : contributeur-**entité**
  alignable (VIAF/IdRef, dormant) et **PID**.
- **Matériel (N1)** : **✅ réalisé (v19, A6)** — `dpi_x`/`dpi_y` · `mode` colorimétrique **captés
  à l'ingest** (lus du fichier, jetés jusque-là) · dimensions physiques (cm) **dérivées** (px÷dpi,
  jamais stockées) · `source_numerisation` (album, appareil/conditions — PREMIS). Backfill
  `tools/reindex_materiel.py` ; roll-up `% avec résolution` + modes ; UI Bibliothèque. Cf.
  `docs/materiel-numerisation.md`.
- **Provenance / audit (N2, N8)** : **✅ réalisé (v16, A3)** — **journal d'événements
  append-only** (`evenement`) + **activités (runs)** (`activite` : agent, versions moteurs,
  params, portée, bilan) + lien entité→run (`regions.activite_id`) + surface
  `touche`/`date_modification` + agrégats dérivés (`journal.indicateurs_provenance`) + export
  **PROV-O / TEI** (`tools/provenance_export.py`). Substrat de l'**undo (D1)**. Restent *à
  prévoir* : versionnement d'entités (`wasRevisionOf`) et **certitude** de zone (dormants).
  Cf. `docs/provenance-audit.md`.
- **Vocabulaire (N7)** : **✅ réalisé (v17, A4)** — lexique situé **SKOS** : `definition` ·
  `note_portee` · état `provisoire→défini` · **portée d'appartenance** (`collection_id`) sur
  dimensions · valeurs · **tags** ; édition API + **UI** (📖 Lexique / Exploration) ; indicateur
  « % défini ». Restent *dormants* : définition contextuelle (`valeur_definition`, B) et version.
  Cf. `docs/lexique-situe.md`.
- **Entités (N6)** : **✅ réalisé (v18, A5)** — alignement d'autorité `personnage_alignement`
  (personnage → 0..N URI Wikidata/VIAF/IdRef, `skos:exactMatch`, source auto-détectée) ; API +
  **UI** (panneau Personnage) + export (`alignements[]`, table CSV, indicateur % aligné).
  Dormant : alignement des **contributeurs** (requiert la promotion en entités d'abord).
  Cf. `docs/alignement-autorite.md`.
- **Droits (Collection / N0, N8)** : `licence_defaut` (tier ouvert) · **`base_legale`** (à quel
  titre on détient/exploite les données — *à établir, hors code*) · **`statut_diffusion`**
  (`public`/`embargo`/`restreint`/`privé`, mappe Nakala), défaut Collection **surchargeable par
  Album**. Principe : **décrire ≠ imposer** ; « à valider juridiquement ».
