---
chantier: UX-4
statut: à venir
---

# UX-4 — cohérence visuelle inter-surfaces

**Point de départ** — l'Exploration a été soignée récemment et sert de référence ; les
trois autres surfaces ne s'y sont jamais alignées.

## Reste

- [ ] Les espacements et la typographie de Recherche, Bibliothèque et Visionneuse suivent ceux de l'Exploration, sans valeur en dur qui contourne les tokens de `static/style.css`
- [ ] Un même composant (bouton, champ, pastille, panneau) a la même apparence sur les quatre surfaces
- [ ] L'audit axe (`pytest -m e2e`) reste sans violation sérieuse ou critique sur les quatre surfaces et les deux thèmes après réalignement
- [ ] Aucun petit texte coloré n'utilise un accent brut : les tokens d'encre AA-sûrs sont respectés (règle d'accessibilité de CLAUDE.md)

## Contexte

Effort M, priorité P3. La troisième et la quatrième case sont là parce que c'est
exactement le genre de chantier qui casse l'accessibilité sans le vouloir : réaligner des
couleurs « pour que ce soit cohérent » est la manière la plus rapide de réintroduire un
accent brut sur du petit texte, ce que le dépôt a déjà corrigé une fois.

À traiter avec UX-3, mêmes fichiers.
