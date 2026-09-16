---
chantier: CONC-3
statut: à venir
---

# CONC-3 — deux personnes sur la même planche : ce qui se perd, et ce que l'écran en dit

**Point de départ** — 2026-09-16, une question de Hugo en tranchant le cache des dérivés
d'IMG-1 : « ça ne servirait pas d'avoir quelque part (niveau album ou collection) un moyen
d'actualiser s'il y a des changements ? » Pour les IMAGES, non : la route des dérivés rend
`no-cache` et un 304, donc le navigateur vérifie lui-même à chaque affichage. Or personne ne
saurait quand cliquer, puisqu'une régénération se fait sur le serveur, sans prévenir. La
question vise pourtant un vrai manque, qui touche les DONNÉES et non le cache. Aucun code
n'est écrit, et le chantier commence par une mesure.

## Reste

### Mesurer ce qui se perd, avant de choisir un remède
- [ ] Deux navigateurs sous deux comptes en écriture, sur la même bulle. A sélectionne la bulle ; B la sélectionne, lui AJOUTE un tag et attend l'enregistrement ; A modifie alors la note et attend l'enregistrement. Attendu : on sait si le tag de B survit. Le journal A3 (`evenement`, avant/après) sert de preuve, et le résultat est écrit ici
- [ ] Même décor, deux notes : A et B modifient la note de la même bulle à quelques secondes d'intervalle. Attendu : on sait laquelle reste, et si celle ou celui dont le texte a disparu en reçoit un signe à l'écran
- [ ] Même décor en Transcription : A et B corrigent le texte de la même bulle. Attendu : on sait ce que montre l'écran de A une fois que B a enregistré, y compris après un changement de bulle puis un retour sur celle-ci
- [ ] A supprime une case pendant que B la modifie. Attendu : on sait ce que B lit à l'écran quand son enregistrement tombe sur une case disparue (un 404 affiché tel quel, un message, ou rien)
- [ ] Les quatre mesures rejouées sous le compte COLLECTIF d'AUTH-6, deux navigateurs sous le même login. Attendu : on sait si Ctrl+Z chez l'une défait l'acte de l'autre dans la fenêtre de cinq minutes

### Trancher la forme, sur les pertes mesurées
- [ ] Écrit : le remède retenu, choisi parmi trois familles, ou « rien, et pourquoi ». Refuser un enregistrement fait sur une version périmée (409 qui nomme le conflit). Signaler que la planche a changé ailleurs, avec un geste pour actualiser. Réserver la bulle ou la planche à qui l'édite. Le choix s'appuie sur ce que la zone précédente a MESURÉ, pas sur l'hypothèse de départ
- [ ] Si l'écran change, la disposition se tranche sur une maquette interactive, pas sur de la prose

## Contexte

**Ce qui a été LU, pas mesuré, le 2026-09-16.** C'est une hypothèse, et la première zone
existe pour la trancher.

- `PUT /api/regions/{id}` est PARTIEL côté serveur (`model_dump(exclude_unset=True)`), et
  l'Atelier n'y envoie que ce qui change : `{ ocr_texte }` en Transcription, les champs
  édités ailleurs. Deux personnes qui touchent deux champs différents d'une même case ne
  devraient donc pas s'écraser ; sur le même champ, le dernier enregistrement gagne.
- `PUT /api/regions/{id}/annotation` REMPLACE la note ET la liste des tags ensemble, et
  l'Atelier envoie `state.currentTags`, chargé au moment où la bulle a été SÉLECTIONNÉE
  (`loadAnnotation`). Un tag ajouté ailleurs entre cette sélection et l'enregistrement
  serait donc effacé en silence. C'est la perte la plus probable, et la seule qui touche un
  AUTRE champ que celui qu'on modifie. La fenêtre est étroite, bornée par le temps passé
  sur une bulle, mais le mode d'échec est muet.
- Les corrections grammaticales : `UNIQUE(region_id, ordre)`, donc le dernier écrit gagne
  par token, jugé « suffisant pour une petite équipe » dans
  `docs/correction-grammaticale.md`.
- L'Atelier charge les régions à l'ouverture d'une planche et ne les recharge plus. Le
  verrou de planche (`verrouillee`, `verrou_par`) est INFORMATIF : il protège des passes
  automatiques, pas d'une autre personne.

**Pourquoi maintenant, et pourquoi pas tout de suite.** Des gens testent la production :
le travail à plusieurs cesse d'être théorique. Mais le cap du moment est la gestion des
comptes (AUTH-12), et ce chantier se place APRÈS lui dans `docs/roadmap.md`. La mesure, en
revanche, ne coûte qu'une demi-heure sur la pile de recette, qui a déjà plusieurs comptes :
elle peut se faire avant, et dire si l'attente est tenable.

**Voisinage.** IMG-1 (le cache des dérivés, où la question est née, réglé par HTTP et hors
de ce chantier). AUTH-6 (le compte collectif utilisé SIMULTANÉMENT, que l'application ne
distinguera jamais). UX-5 (la granularité de l'annulation : un enregistrement toutes les
500 ms n'est pas un geste). CONC-1 et CONC-2 portent sur les lots ML, pas sur les
personnes.
