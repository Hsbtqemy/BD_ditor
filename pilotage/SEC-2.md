---
chantier: SEC-2
statut: à venir
---

# SEC-2 — CSP maintenant, CSRF avec les sessions

**Point de départ** — aucun en-tête Content-Security-Policy n'est servi, et les appels
`apiSend` POST/PUT/DELETE n'envoient ni jeton ni en-tête personnalisé. Risque faible en
mono-poste local, à traiter **avant** toute exposition réseau.

## Reste

### CSP — faisable tout de suite
- [ ] Un en-tête CSP est servi sur les quatre surfaces et ne casse aucune d'elles, vérifié console navigateur vide
- [ ] La politique interdit le script inline, ou les inlines restants sont recensés et justifiés
- [ ] L'audit e2e reste vert avec la CSP active

### CSRF — dépend d'INFRA-1
- [ ] Une protection CSRF est en place sur les routes mutantes, une fois que des sessions existent réellement

## Contexte

Fiche **scindée exprès en deux zones** : le backlog les traitait comme un seul ticket P3,
ce qui masquait que la moitié est faisable immédiatement. La CSP ne dépend de rien ; le
CSRF n'a aucun sens tant qu'il n'y a pas de session à voler, donc dépend d'INFRA-1.

La quatrième case restera ouverte tant qu'INFRA-1 n'aura pas abouti — c'est normal et
c'est l'information utile : la fiche ne se clora pas avant le déploiement.

L'ordre importe. `docs/deploiement-docker.md` et l'audit s'accordent : ceci se traite
avant l'exposition réseau, pas après.
