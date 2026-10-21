---
chantier: INFRA-5
statut: interrompu
---

# INFRA-5 — reprise d'état via sessionStorage

**Arrêté sur** — 2026-10-21, `6ccd8cb` : les quatre cases sont codées, dans le lot 1, sur `dev`
en local. Restent la passe de QA du lot et le push. D'où `interrompu`.

**Point de départ** — l'URL couvre déjà le rechargement et le partage ; revenir sur
Recherche ou Exploration **par le menu** repart d'un état vide.

## Reste

- [x] Revenir sur Recherche via la nav transverse restaure la dernière recherche, filtres compris **Fait le 2026-10-21, `6ccd8cb`** : chaque page mémorise son état dans `sessionStorage` (clé `bd-etat:<page>`, propre à l'onglet) à chaque écriture de son adresse ; joué au navigateur
- [x] Revenir sur Exploration via la nav restaure la dernière vue (distribution, concordance, croisement, comparaison) et ses filtres **Fait le 2026-10-21, `6ccd8cb`**, joué au navigateur
- [x] Arriver par une URL portant un état explicite l'emporte sur l'état mémorisé — l'URL reste la source de vérité **Fait le 2026-10-21, `6ccd8cb`** (`Nav.etatDeDepart`) : une adresse qui porte un état gagne toujours ; `retour` seul est un contexte et non un état, il ne se mémorise jamais. Trois mutants de la logique pure tués sous Node
- [x] Une navigation privée, ou un stockage de session indisponible, dégrade proprement vers l'état vide **Fait le 2026-10-21, `6ccd8cb`** : toute lecture et toute écriture sous try/catch ; sans stockage, les pages repartent vides sans erreur de script (joué au navigateur)
- [ ] La passe de QA du lot 1 joue le retour par le menu sur la Recherche et l'Exploration — attendu : cochée par Hugo

## Contexte

Effort S, priorité P3 — pur confort. Le point de conception est la troisième case : la
mémorisation ne doit jamais gagner contre une URL explicite, sinon les deep-links de
concordance vers la Visionneuse (livrés en B2) deviendraient imprévisibles.

`static/lib/nav.js` est déjà le point unique de la navigation transverse et sa logique
pure est testée sous Node — c'est là que ça se branche.
