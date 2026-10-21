---
chantier: COL-4
statut: à venir
---

# COL-4 — « Mon bac à sable » : un projet de test à soi, remis à neuf chaque semaine, où l'on apprend l'outil

**Arrêté sur** — rien de codé. Fiche ouverte le 2026-10-21 sur une demande de Hugo et ses
réponses du même jour (Contexte). Avant tout code : une note de cadrage, puis la maquette du
wizard en session dédiée.

## Reste

### Tranché par Hugo — 2026-10-21
- [x] **Un bac à sable PAR COMPTE, pas un projet commun** — attendu : tranché. Le projet commun permettait de tester le travail à plusieurs, mais « 75 comptes, et un qui décide de virer tout le monde ? » : on apprend l'outil chez soi. Chacun est RESPONSABLE de son bac à sable, et peut y faire entrer un collègue pour essayer le collaboratif — c'est lui qui l'ouvre, à qui il veut
- [x] **Il naît au clic, et l'effacement automatique ne le recrée pas** — attendu : tranché. Un bouton « Mon bac à sable » le crée la première fois, rempli de son jeu ; chaque SEMAINE, tous les bacs à sable sont effacés, et l'on reclique pour en retrouver un neuf. Rien n'est créé pour les comptes qui ne viennent pas, et les projets ne s'accumulent pas
- [x] **Une remise à neuf à la demande, par son propriétaire** — attendu : tranché. Un bouton dans le bac à sable le remet à son jeu de départ, quand on veut
- [x] **Re-semé d'un jeu fixe, et le wizard y vit** — attendu : tranché. L'écran « par où commencer » (`UX-6`, décalé le même jour) prend place dans le bac à sable : on comprend les étapes sur pièce. Le jeu : une, deux ou trois planches sur lesquelles on suit TOUTES les étapes au même endroit (pas une planche par étape) ; d'autres planches pour montrer d'autres possibilités ; un stock pour tester et s'amuser. L'annotation, plus chargée (vocabulaires, modes, texte), viendra à part, avec `ANN-7`. Le détail se rediscute sur pièce

- [x] **Sa place dans la file** — attendu : tranché par Hugo. **Le 2026-10-21 : lot 3**, après le lot 1 (imports, copie de travail) et le lot 2 (la 3b de `COL-3`), AVANT `ANN-7` — la vague de nouveaux comptes arrive avant les annotateurs. Il ne dépend pas vraiment du lot 2 (remise à neuf et effacement hebdomadaire sont des gestes à lui ; chacun y crée ses copies) : si la vague devance la 3b, il peut passer en lot 2

### À cadrer avant le code
- [ ] **Une note de cadrage** — attendu : écrite et rendue à Hugo, lue dans le code : qui crée un projet aujourd'hui (`peut_decider_des_projets`, la portée totale seule) et l'exception écrite qu'est un bac à sable créé par son propre utilisateur ; comment on le reconnaît (un drapeau sur `projet`, à côté de `repli`) et ce qu'il NE donne PAS ailleurs ; comment l'effacement hebdomadaire détruit un projet et tout ce qu'il porte (albums, copies, collections, demandes, journal — append-only, donc il reste) sans toucher aux autres ; ce qui empêche un album du bac à sable de sortir vers un vrai projet (le rangement ne traverse pas les projets ; « en partir », E7, à décider) ; la minuterie (le patron de `bd-deploiement.timer`) ; et ce que la liste des projets de l'Administration fait de 75 bacs à sable
- [ ] **Le jeu ne coûte rien sur le disque** — attendu : décidé dans le cadrage. Proposé : le jeu vit au FONDS comme des documents, et chaque bac à sable en prend des COPIES (COL-3, D6 : une copie désigne les mêmes images que sa source) — 75 bacs à sable pour presque rien, et l'effacement ne détruit que les copies. Des images du DOMAINE PUBLIC, pour que le jeu puisse vivre dans le dépôt et se tester ; sinon sur le VPS, hors du dépôt public
- [ ] **Le bac à sable dit quand il sera effacé** — attendu : la date du prochain effacement se lit dans le bac à sable, pour que personne ne perde un essai par surprise
- [ ] **Le wizard se tranche sur maquette** — attendu : une maquette interactive en session dédiée, sur une vraie planche du jeu, avec Hugo ; elle reprend la moitié écran d'`UX-6` (étapes, liens profonds) et la passe `accueil-par-ou-commencer`

## Contexte

**La demande** (Hugo, 2026-10-21) : un projet « Pour tester », ouvert à tout le monde, remis à
zéro régulièrement. Le même jour, Hugo a précisé que le corpus actuellement en production est
lui-même un corpus de TEST ; et des testeurs ont demandé s'il était possible de réinitialiser
son projet, ou de tout effacer sur une planche, sur un album — ce qui a donné, chez `COL-3`
(tranche 3b, « qui efface, qui retire, qui crée »), E8 étendu à la planche et les droits
gradués d'effacement.

**Ce que la forme « un par compte » règle sans l'avoir cherché.** « Ouvert à tout le monde »
demandait soit un groupe de l'annuaire où mettre chaque compte, soit un drapeau « toute
personne connectée est membre », qui touche au cœur des droits. Un bac à sable dont on est
soi-même responsable n'a besoin d'aucun des deux.

**Voisinage.** `UX-6` (le wizard y prend place) ; `COL-3` (le fonds, les copies sœurs, D6 ;
E8 et les droits d'effacement ; le réglage « les membres peuvent créer des collections »,
sans effet ici puisqu'on est responsable de son bac à sable) ; `ANN-7` (l'annotation, à part) ;
`IMG-1` (la copie de travail : les images du jeu en suivent la règle).
