# Matériel de numérisation (A6)

> **But.** Consigner le **matériel de numérisation** d'une planche — résolution (`dpi`), espace
> colorimétrique (`mode`), dimensions physiques réelles, appareil/conditions de scan — pour la
> **complétude** du dépôt (PREMIS, `DC:format`) et la traçabilité technique. Livré en **v19**.
> Cadre : niveau 1 (« Planche ») du `docs/dictionnaire-metadonnees.md`.

## L'insight — capter ce que l'ingest lisait déjà

`pipeline/ingest.read_metadata()` ouvrait le master avec Pillow et lisait **déjà** `dpi`, `mode`
et les dimensions en pixels — mais l'INSERT n'en gardait que les pixels ; `dpi`/`mode` étaient
**lus puis jetés**. A6 se contente de **persister** ce qui existait, plus un champ humain
(`source_numerisation`) et une **dérivation** (dimensions cm).

## Modèle — trois provenances

| Donnée | Où | Provenance | Note |
|---|---|---|---|
| `planches.dpi_x` / `dpi_y` | planche | **auto** (ingest) | résolution captée du fichier ; NULL si absente |
| `planches.mode` | planche | **auto** (ingest) | `RGB` / `CMYK` / `L` / `I;16`… (mode Pillow **du master**, jamais celui du dérivé) |
| dimensions physiques (cm) | planche | **dérivé** | `px ÷ dpi × 2,54` — **jamais stocké** |
| `albums.source_numerisation` | **album** | **humain** | appareil / conditions de scan (PREMIS, libre) |

Deux choix de modélisation :

1. **`dpi`/`mode` en lecture seule** : ce sont des **faits matériels** du fichier (provenance
   auto), non des jugements éditoriaux — pas d'UI d'édition. Un `dpi` absent se corrige en
   ré-important, ou via le backfill après re-scan ; la correction manuelle par planche reste
   **dormante** (activable plus tard si un besoin réel émerge).
2. **`source_numerisation` au niveau ALBUM**, à côté de `format_physique` : une **campagne de
   scan = un album** (un appareil, une session) → saisie **une seule fois**, pas planche par
   planche. Le `docs/dictionnaire-metadonnees.md` le rangeait spéculativement en N1 ; le
   précédent A1 (`format_physique` sur l'album) tranche en faveur de l'album.

Les **dimensions physiques ne sont jamais stockées** — même doctrine que le **numéro éditorial**
(`database.dimensions_cm()` les dérive à la lecture : API, exports). Rien à réindexer si un `dpi`
est corrigé.

## Câblage

- **Ingest** : `pipeline/ingest.ingest_image()` éclate `meta["dpi"]` (paire ou None) en
  `dpi_x`/`dpi_y` et persiste `mode`. Le mode reste celui du master même quand le dérivé
  change de mode : un gris 16 bits (`I;16`) donne un dérivé `L`, et c'est `I;16` qui est
  stocké — le matériel décrit le fichier numérisé (IMG-1, `ingest.image_8_bits`). Un master
  en `I` ou `F` est refusé à l'import, faute de réduction juste en 8 bits.
- **Backfill** : `tools/reindex_materiel.py` **re-lit les masters** des planches importées avant
  la v19 (matériel NULL), `--force` pour toutes, `--dry-run` pour le bilan. Saute proprement les
  planches sans master (dérivé seul) ou illisibles. UTF-8 forcé (portabilité Windows). Depuis la
  v34, il saute aussi toute planche dont le fichier est une COPIE DE TRAVAIL (`master_origine`
  renseigné, cf. plus bas) : sa résolution et son mode ne sont plus ceux du scan.
- **API** : `AlbumIn`/`AlbumUpdate` portent `source_numerisation` ; les payloads planche
  (`GET /api/albums/{id}/planches`, export JSON) portent `dpi_x`/`dpi_y`/`mode` +
  `dimensions_cm` dérivé.
- **UI** (Bibliothèque) : champ **« Source de numérisation »** éditable dans le formulaire album ;
  résolution / mode / dimensions cm affichés **en lecture seule** sous chaque planche, et la
  source dans l'en-tête de l'album.
- **Export** : records planche (`dpi_x`, `dpi_y`, `mode`, `dimensions_cm`) + album
  (`source_numerisation`) ; tables CSV `planches` (colonnes `dpi_x`/`dpi_y`/`mode` +
  `largeur_cm`/`hauteur_cm` dérivées) et `albums` ; roll-up
  `couverture.planches.materiel` (`avec_resolution`, `pct_avec_resolution`, `par_mode`) ;
  dictionnaire N1 mis à « structuré (v19) ».

## Dérivation des cm

`database.dimensions_cm(largeur_px, hauteur_px, dpi_x, dpi_y)` → `{largeur, hauteur}` en cm
(arrondi au dixième, 1 pouce = 2,54 cm), ou **None** si la résolution manque (indérivable).
Exemple : 600×900 px à 300 dpi → **5,1 × 7,6 cm**.

## La copie de travail (IMG-1, v34)

Décidé par Hugo le 2026-10-21 : **le serveur ne garde plus le fichier reçu** (un TIFF de
~52 Mo, un JPEG 2000 de ~12 Mo, quand le VPS n'avait que 26 Go libres), mais une **copie de
travail** — un JPEG qualité 80 à **300 dpi effectifs**. Un scan plus fin est réduit jusque-là
(un 400 dpi → 75 %) ; un scan à 300 dpi ou moins est gardé à sa taille ; un scan **sans
résolution écrite** aussi — on ne réduit pas ce qu'on ne sait pas mesurer, et rien n'est
inventé. Le facteur est le même pour les deux axes, tiré de la plus basse des deux
résolutions (`ingest.facteur_de_travail`). Le dérivé web reste à 25 % des dimensions du scan.

**Le matériel décrit toujours le SCAN, pas la copie.** `largeur_px`/`hauteur_px`, `dpi_x`/
`dpi_y` et `mode` sont lus dans le fichier reçu et écrits tels quels : les **centimètres ne
changent pas**, et les coordonnées des régions restent en pixels du scan. La copie porte la
résolution qu'elle a effectivement (300 pour un 400 réduit), pour qui l'ouvre ailleurs. Qui
l'ouvre dans l'outil applique l'échelle `largeur ouverte / largeur_px` (`ocr._open_image`).

**Le master d'archive vit où le projet le met** (ShareDocs, un disque, des disques durs —
« selon les projets et les personnes ») : l'outil n'en impose aucun. Il note ce qu'il sait,
planche par planche, dans `planches.master_origine` — `sharedocs:<chemin distant>` pour un
import ShareDocs, sinon le nom du fichier reçu — et l'album porte un champ libre facultatif,
`albums.lieu_masters` (« Où vivent les masters », dans la modale d'album de la Bibliothèque,
à côté de la source de numérisation). Les deux colonnes sont RETENUES de toute sortie : ce
sont des lieux internes au projet, sans valeur descriptive de l'œuvre.

| | v33 et avant | v34 |
|---|---|---|
| `corpus/album_<N>/` | le fichier reçu, octet pour octet | la copie de travail, `planche_<n>.jpg` |
| `chemin_tiff` | le master | la copie de travail (la colonne garde son nom) |
| `master_origine` | — | ce que l'outil sait du master ; NULL = planche d'avant, fichier encore le scan |

**Le rattrapage** des planches importées avant la v34 : `tools/convertir_en_copies_de_travail.py`.
À blanc par défaut — il dit quels fichiers et quelles planches seraient convertis et ce que
cela libérerait, mesuré en encodant réellement la copie ; avec `--appliquer`, fichier par
fichier, il écrit la copie à côté du master, bascule sous le verrou d'écriture TOUTES les
planches qui le désignent (une copie sœur suit, un fichier partagé ne se convertit qu'une
fois), note le nom du fichier d'origine, recopie en base une résolution ou un mode qui y
manquaient, puis efface le master s'il n'est plus désigné. Idempotent, il s'arrête proprement
sur Ctrl+C ou un arrêt du conteneur, et sa première ligne dit que **convertir efface le
master du serveur**. En production, seulement sur le mot de Hugo, une fois chaque master
retrouvé hors du serveur :

    cd ~/BD_ditor/deploy
    docker compose exec app python tools/convertir_en_copies_de_travail.py              # à blanc
    docker compose exec app python tools/convertir_en_copies_de_travail.py --appliquer  # convertit

`--album <N>` (répétable) borne le passage à un album, ses copies sœurs suivant.

## Hors périmètre (dormant)

- **Correction manuelle** de `dpi`/`mode` (UI d'édition par planche) — non requise tant qu'un
  ré-import suffit.
- **Conditions de scan structurées** (opérateur, date de numérisation, profil ICC…) — pour
  l'instant repliées dans le texte libre `source_numerisation`.
