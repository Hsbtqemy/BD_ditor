---
chantier: INFRA-5
statut: à venir
---

# INFRA-5 — reprise d'état via sessionStorage

**Point de départ** — l'URL couvre déjà le rechargement et le partage ; revenir sur
Recherche ou Exploration **par le menu** repart d'un état vide.

## Reste

- [ ] Revenir sur Recherche via la nav transverse restaure la dernière recherche, filtres compris
- [ ] Revenir sur Exploration via la nav restaure la dernière vue (distribution, concordance, croisement, comparaison) et ses filtres
- [ ] Arriver par une URL portant un état explicite l'emporte sur l'état mémorisé — l'URL reste la source de vérité
- [ ] Une navigation privée, ou un stockage de session indisponible, dégrade proprement vers l'état vide

## Contexte

Effort S, priorité P3 — pur confort. Le point de conception est la troisième case : la
mémorisation ne doit jamais gagner contre une URL explicite, sinon les deep-links de
concordance vers la Visionneuse (livrés en B2) deviendraient imprévisibles.

`static/lib/nav.js` est déjà le point unique de la navigation transverse et sa logique
pure est testée sous Node — c'est là que ça se branche.
