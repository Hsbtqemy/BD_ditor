---
chantier: UX-4
statut: à venir
---

# UX-4 — cohérence visuelle inter-surfaces

**Point de départ** — l'Exploration a été soignée récemment et sert de référence ; les
QUATRE autres surfaces ne s'y sont jamais alignées. Elles étaient trois quand cette fiche
a été écrite : `/administration` est arrivée depuis (UX-10, 2026-09-07), et elle est la
plus jeune donc la moins alignée.

## Reste

- [ ] Les espacements et la typographie de Recherche, Bibliothèque, Atelier et Administration suivent ceux de l'Exploration, sans valeur en dur qui contourne les tokens de `static/style.css`
- [ ] Un même composant (bouton, champ, pastille, panneau) a la même apparence sur les cinq surfaces
- [ ] **L'Administration est reprise en priorité** : ses trois blocs ont été construits pour FONCTIONNER, l'un après l'autre et par des chantiers différents (INFRA-10, AUTH-3/AUTH-7, SANTE-1, EXP-1), sans qu'aucun ne réponde de l'ensemble. Attendu : les quatre panneaux se lisent comme une même page, et non comme quatre écrans empilés
- [ ] L'audit axe (`pytest -m e2e`) reste sans violation sérieuse ou critique sur les cinq surfaces et les deux thèmes après réalignement
- [ ] Aucun petit texte coloré n'utilise un accent brut : les tokens d'encre AA-sûrs sont respectés (règle d'accessibilité de CLAUDE.md)

## Contexte

Effort M, priorité P3. La troisième et la quatrième case sont là parce que c'est
exactement le genre de chantier qui casse l'accessibilité sans le vouloir : réaligner des
couleurs « pour que ce soit cohérent » est la manière la plus rapide de réintroduire un
accent brut sur du petit texte, ce que le dépôt a déjà corrigé une fois.

À traiter avec UX-3, mêmes fichiers.

**L'Administration entre dans le périmètre le 2026-09-08**, sur un constat d'usage énoncé
pendant EXP-1 : *« il faudra certainement reprendre l'esthétique de cette page à l'avenir,
mais pour l'instant, on vise le fonctionnel »*. C'est un arbitrage, pas un oubli, et il
mérite d'être écrit ici plutôt que de se perdre — une intention de ce genre s'évapore
exactement comme les fiches périmées se fabriquent.

La cause est structurelle et vaut d'être notée : cette page est la seule dont les blocs
ont été posés par des chantiers SÉPARÉS, chacun ajoutant le sien sans que personne ne
réponde de l'ensemble. La version servie (INFRA-10), les collections et la vue des comptes
(AUTH-3, AUTH-7), les moteurs (SANTE-1), l'export de dépôt (EXP-1) — cinq origines, cinq
mises en forme locales. Les autres surfaces ont été dessinées d'un tenant.
