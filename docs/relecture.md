# Statut de relecture par planche (ANN-4)

> **But.** Suivre **quelles planches restent à relire** (coordination d'équipe) : un statut de
> relecture grammaticale **dérivé** de l'avancement réel des corrections, **forçable** si besoin.
> Livré en **v21**. Badge + filtre dans la Bibliothèque.

## Trois concepts distincts (à ne pas confondre)

Une planche porte déjà deux drapeaux ; la relecture est un **troisième**, orthogonal :

| Champ | Sens |
|---|---|
| `statut` | avancement du **pipeline ML** (`importee → segmentee → …`) |
| `validee` | **validation** humaine binaire (horodatage ; « finalisée ») |
| **`relecture`** | **relecture grammaticale** : `à faire` / `en cours` / `faite` (ANN-4) |

## Dérivé, jamais stocké — sauf l'override

Le statut effectif est **DÉRIVÉ** des provenances de tokens (`database.relecture_planches`,
même doctrine que le numéro éditorial) :

```
relus = tokens dont la provenance est « corrigé » ou « validé »   (via tokens_effectifs)
à faire   : 0 relu (dont planche sans texte — pas encore travaillée)
en cours  : quelques-uns relus (partiel)
faite     : tous relus (≥ 1 token)
```

Seul l'**override** est stocké : la colonne `planches.relecture` (`a_faire`|`en_cours`|`faite`,
ou **NULL = suivre le dérivé**). Le statut effectif = override si présent, sinon dérivé.

## API & UI

- `GET /api/albums/{id}/planches` → chaque planche porte `relecture_statut` :
  `{statut (effectif), derive, force (bool), tokens, relus}`.
- `PATCH /api/planches/{id}/relecture` `{"relecture": "faite" | "en_cours" | "a_faire" | null}` —
  force un statut, ou `null` pour **revenir au dérivé**.
- **Bibliothèque** : colonne *Relecture* = **pastille** du statut effectif (couleur *renforçante*,
  le libellé porte l'info → accessible daltoniens ; italique si forcé) + **sélecteur** d'override
  (3 états | *auto*). **Filtre** au-dessus du tableau (n'afficher qu'un statut).

## Périmètre

- **Couvert** : dérivation, override 3 états + auto, badge, filtre par album. Migration v21
  (colonne `relecture`, ALTER simple sans index).
- **Différé** : roll-up **corpus** du reste-à-relire (bande de synthèse) ; relecture **par
  annotateur** ; statut de relecture au niveau **album**.
