# Annulation (undo) — D1

> **But.** Rendre RÉVERSIBLE le geste d'annotation le plus dangereux — la **suppression
> cascade** (une case emporte ses bulles + annotations + tags), aujourd'hui irréversible sans
> restaurer une sauvegarde complète. Filet **fin**, complément de la sauvegarde (« gros grain »).
> Débloqué par le journal A3 (v16). Cadre : backlog **UX-5**.

## Le journal EST l'historique

Pas de pile client, pas de nouvelle table : le journal `evenement` (A3) porte déjà tout ce
qu'il faut — append-only, état **`avant`/`apres`**, **instantané profond** capturé à la
suppression, et un `cible_id` qui **survit** à la destruction de sa cible (pas une FK). Annuler,
c'est **remonter** ce journal en appliquant l'inverse de chaque acte.

## Pile via événements d'annulation (append-only préservé)

Un événement n'est **jamais** modifié. Annuler un acte `E` = exécuter son inverse **+ ajouter**
un événement `annulation` (`cible_table='evenement'`, `cible_id = E.id`). La **dernière action
annulable** est l'événement **humain** le plus récent, d'un type annulable, **non déjà
référencé** par une annulation. `Ctrl+Z` répété remonte ainsi l'historique — une **pile**, sans
état mutable. (Le **redo** — annuler une annulation — est hors périmètre de ce cran.)

## Inversions (`undo.py`)

Mutations **brutes** + réindex FTS, **sans repasser par les routes** (sinon elles
rejournaliseraient → bruit + boucle). Un **seul** événement `annulation` est ajouté par undo.
L'ensemble (inverse + journal) est **atomique** : la route commite, la dépendance `db` fait
rollback en cas d'échec.

| Acte journalisé | Inverse |
|---|---|
| `creation` région | supprimer la région (+ sous-arbre, désindexé) |
| `modification` région (géométrie / OCR / déplacement) | réécrire les colonnes métier depuis `avant` |
| `suppression` région | **recréer le sous-arbre** depuis l'instantané profond (région + annotation + enfants, **mêmes `id`**) |
| `creation` annotation | supprimer l'annotation |
| `modification` / `suppression` annotation | (re)poser note + tags depuis `avant` |
| `lien` locuteur/présence (avant ∅) | retirer le lien |
| `lien` (avant présent) / `delien` | rétablir l'ancien lien |

**Recréation à l'identique** : l'instantané profond porte les `id` d'origine → citations,
deep-links et références restent valides. Si un `id` a été **réattribué** depuis (une nouvelle
région a pris la place libérée), l'annulation échoue proprement en **409** plutôt que d'écraser.

## Ajustement A3 : les annotations ciblent `region_id`

Les événements d'annotation ciblaient l'`ann_id` (id d'annotation), **détruit** à la
suppression → une annotation supprimée aurait été irrécupérable. Ils ciblent désormais le
**`region_id`** (stable, `region_id` est UNIQUE dans `annotations`), comme locuteur/présence.
Additif : l'export PROV keye simplement l'entité annotation par sa région.

## Périmètre

**Inclus** : région (créer / modifier / supprimer+cascade), annotation (note + tags), locuteur,
présence — les gestes d'annotation, dont le plus destructeur. **Actes MACHINE non annulables**
par l'utilisateur (`agent_type='moteur'` filtré : une passe ML se rejoue, elle ne s'annule pas
au clavier). **Hors périmètre (dormant)** : correction grammaticale (tokens), validation
planche/région, et le **redo**.

## Boucle

- **API** : `GET /api/undo/prochain` (aperçu : `{evenement_id, description}` ou `null`) ·
  `POST /api/undo` (exécute ; renvoie `{description, acte, cible_table, region_id, planche_id}` ;
  **404** si rien à annuler, **409** si l'inverse est impossible).
- **UI** : **Ctrl/⌘+Z** dans la Visionneuse (hors champ de saisie — dans un champ, l'undo natif
  du navigateur s'applique) → toast « Annulé : … » + rafraîchissement de la planche/région
  touchée. Une sauvegarde d'annotation différée en attente est **annulée** (pas flushée) avant
  l'undo, pour ne pas ré-appliquer un buffer périmé.
