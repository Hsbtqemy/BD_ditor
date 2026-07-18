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
| `planches.mode` | planche | **auto** (ingest) | `RGB` / `CMYK` / `L`… (mode Pillow) |
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
  `dpi_x`/`dpi_y` et persiste `mode`.
- **Backfill** : `tools/reindex_materiel.py` **re-lit les masters** des planches importées avant
  la v19 (matériel NULL), `--force` pour toutes, `--dry-run` pour le bilan. Saute proprement les
  planches sans master (dérivé seul) ou illisibles. UTF-8 forcé (portabilité Windows).
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

## Hors périmètre (dormant)

- **Correction manuelle** de `dpi`/`mode` (UI d'édition par planche) — non requise tant qu'un
  ré-import suffit.
- **Conditions de scan structurées** (opérateur, date de numérisation, profil ICC…) — pour
  l'instant repliées dans le texte libre `source_numerisation`.
