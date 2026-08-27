---
chantier: ANA-6
statut: à venir
---

# ANA-6 — détails de recherche laissés de côté par B2/B3

**Point de départ** — les vues Concordance (B2) et Croisement (B3) sont livrées ; trois
raffinements ont été explicitement différés à leur livraison.

## Reste

- [ ] La recherche de lemme accepte un préfixe (aujourd'hui : correspondance exacte uniquement)
- [ ] Une ligne de concordance affiche les tags et la note de la région, sans second aller-retour serveur
- [ ] La concordance a un export dédié, cohérent avec les autres exports (`_csv_safe` appliqué)

## Contexte

Ces trois points sont les « différés » notés en toutes lettres au moment de livrer ANA-3
et ANA-2 — ils ne viennent pas d'un audit mais de la revue de livraison.

Priorité P3, effort S. Le premier (préfixe) est celui qui manque le plus vite à l'usage :
sans lui, chercher « otage » ne trouve pas « otages » dès que le lemme n'est pas résolu,
ce qui arrive quand spaCy est absent.
