# Backlog — déplacé dans `pilotage/`

> Établi le 2026-06-15, tenu en prose jusqu'au 2026-07-18, **retiré le 2026-08-27** :
> le suivi ticket-par-ticket vit désormais dans le **journal de bord** (`pilotage/`),
> lu par [`pilote`](https://github.com/Hsbtqemy/pilote). Ce fichier n'est plus qu'un
> renvoi — il n'est plus tenu à jour et ne doit plus servir de référence.

## Pourquoi

Deux listes à tenir en donnent une de fausse. Ce document en était l'illustration : des
notes de section déclaraient livré ce que la ligne du ticket ne marquait pas (A11Y-1→5,
ANA-1, UX-1/UX-2), un `✅` valait tantôt « fait », tantôt « la moitié », et l'ordre
conseillé en bas de page contredisait les statuts du haut.

Un journal confronte ce qu'on a écrit à ce que `git` montre, au lieu de demander qu'on
tienne les deux à la main.

## Où sont les tickets maintenant

| Ce que vous cherchez | Où |
|---|---|
| Un ticket **ouvert** (`ANN-3`, `SEC-2`, `INFRA-1`…) | `pilotage/<CODE>.md` — une fiche par ticket, avec son `Reste` |
| Un ticket **livré** (`QA-1`, `QA-2`, `QA-3`, `SEG-1`, `DB-1`, `ANN-2`, `ANA-1/2/3`, `NLP-1`, `ANN-4/5`, `UX-1/2/5`, `A11Y-1/3/4/5`, `INFRA-2`, `SEC-1`, `CONC-2 v1`) | [`roadmap.md`](roadmap.md), qui en garde le détail et le pointeur vers sa note de conception |
| Le **texte d'origine** d'un ticket, ouvert ou livré | `git show e411703:docs/backlog.md` (dernier état complet, 2026-07-18) |
| La **vue stratégique** par pistes, le cap, l'ordre conseillé | [`roadmap.md`](roadmap.md) — le journal ne la remplace pas |
| L'**audit technique** et ses constats | [`../AUDIT.md`](../AUDIT.md) ; les reliquats ouverts sont regroupés dans `pilotage/AUDIT-1.md` |

Les codes n'ont pas changé : un commentaire de code qui dit « cf. `docs/backlog.md`
(CONC-2) » désigne toujours CONC-2, à lire maintenant dans `pilotage/CONC-2.md`.

## Lire le journal

```bash
npm run journal      # http://localhost:4124
npm run verifier     # contrôle du dossier avant de clore une session
npm run arreter      # fermer
```

La convention d'écriture des fiches est dans `pilotage/_TEMPLATE.md`, et les règles que
l'agent doit respecter dans la section « Pilotage » de [`../CLAUDE.md`](../CLAUDE.md).
