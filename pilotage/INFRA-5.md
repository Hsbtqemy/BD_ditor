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
- [ ] **`test_sans_stockage_de_session_la_page_repart_vide_sans_erreur` ne dépend plus de la charge du poste** — attendu : vert dans une passe navigateur entière lancée pendant qu'une autre suite tourne. Relevé le 2026-10-26 (chaîne de `8a38bb9`, et déjà le 2026-10-24 sur `0602f03`) : il attend 15 s « Aucun résultat. » après une PREMIÈRE recherche, qui charge à froid le modèle de langue ; sous charge, la requête `/api/recherche` dépasse le délai — tracé, elle reste en attente, quelle que soit la feuille de style (une bissection par fichier avait d'abord accusé `style.css` : c'était la charge qui variait). Seul et au repos, vert trois fois sur trois en 20 s. Remède à choisir : préchauffer le modèle dans la fixture (`nlp.prewarm()`), ou allonger ce délai-là

## Contexte

Effort S, priorité P3 — pur confort. Le point de conception est la troisième case : la
mémorisation ne doit jamais gagner contre une URL explicite, sinon les deep-links de
concordance vers la Visionneuse (livrés en B2) deviendraient imprévisibles.

`static/lib/nav.js` est déjà le point unique de la navigation transverse et sa logique
pure est testée sous Node — c'est là que ça se branche.
