---
chantier: ANA-4
statut: à venir
---

# ANA-4 — keyness (log-vraisemblance) dans la comparaison A/B

**Point de départ** — la comparaison A/B existe et fonctionne ; elle classe par écart de
fréquence relative, ce qui favorise mécaniquement les mots fréquents.

## Reste

- [ ] La métrique de classement est sélectionnable dans la vue Comparaison (écart de fréquence relative ou log-vraisemblance)
- [ ] Sur un corpus réel, le classement par keyness fait remonter au moins un mot rare-mais-distinctif que l'écart de fréquence relative enterrait
- [ ] Le choix de métrique passe dans l'URL, comme le reste de l'état d'Exploration (partageable)
- [ ] Un test verrouille le calcul de log-vraisemblance sur un jeu de comptes connu

## Contexte

Effort S au backlog : le calcul est une formule sur des comptes déjà disponibles côté
serveur, l'essentiel du travail est le sélecteur et le passage dans l'URL.

C'est le raffinement le moins cher des quatre vues d'Exploration, et celui qui change le
plus ce qu'on voit — la comparaison actuelle dit surtout que « le » est fréquent des deux
côtés.
