---
passe: Page Annotation sur un vrai appareil — téléphone puis tablette, en production, dans un bac à sable
chantier: ANN-7
duree: 30 min
---

# QA — la page Annotation sur un vrai appareil

**Écrite le 2026-11-01**, sortie de la passe du jalon 3 (`page-annotation-jalon-3.md`), dont elle était la dernière zone : elle ne pouvait se jouer que sur la production, la recette n'écoutant que sur le poste. Elle porte sur les écrans étroits et le doigt (commit 12 de la tranche 2, `953531d`) et vise la production qui sert `51d70d1` ou un commit plus récent. Ce qui gêne s'écrit dans `ANN-6`.

**Où** : `https://bd.edito-revue.fr`, sous votre compte, dans VOTRE bac à sable. Rien n'y a de valeur, et il s'efface chaque lundi à 4 h (heure de Paris) : une passe commencée le dimanche soir et reprise le lundi repart de la première zone.

**Le décor** : la planche du parcours, *Bibi Fricotin chez les Chinois* (trois cases, quatre bulles), et la « Grille d'exemple », fictive, que le bac à sable reçoit à sa naissance. Un bac à sable ouvert avant ce déploiement n'a pas de grille : la première zone le remet à neuf. Deux bulles reçoivent d'abord, sur l'ordinateur, un texte connu dont les cases désignent les mots. Les cases s'enchaînent : chacune part de l'état laissé par la précédente.

**Rejouée sans écran avant d'être rendue**, le 2026-11-01, sur un serveur local à `51d70d1` : un bac à sable neuf, un jeu au même titre mais à l'image synthétique (la longue bulle et `HEY` y tombaient dans la case c1 ; dans le vrai Bibi, elles peuvent être ailleurs), en émulation tactile à 390 × 844, 667 × 375 et 1024 × 768. Toutes les cases conformes après correction de la deuxième (la remise à neuf lancée hors de l'Atelier reste sur sa page). Ce que l'émulation ne joue pas : le clavier virtuel, Safari, et les deux défauts qu'elle mesure (le toucher perdu après un tracé rapide, la grille de 8 px couchée), que les cases demandent de constater.

**Ce que la passe ne juge pas** : ce que le jalon 3 a joué sur ordinateur, le doute, la Synthèse, « ⟳ Actualiser ».

## Reste

### Sur l'ordinateur d'abord — 5 min, votre compte

- [x] Administration › Instance, « 🏷️ Version servie » : `51d70d1` ou un commit plus récent
- [x] Ouvrir ✏️ Atelier. « Mon bac à sable » dans la bande du haut — ou, si votre bac à sable existe déjà, le choisir dans la liste « Projet », puis « Remettre à neuf… » dans la ligne rayée et confirmer : l'Atelier s'ouvre sur *Bibi Fricotin chez les Chinois*, la planche du parcours
- [x] Atelier, mode « Transcription » : la première bulle s'affiche en grand ; remplacer son texte par `MAIS ENFIN BIBI TU NE VAS PAS ENCORE GRIMPER SUR CE TOIT POUR REGARDER PASSER LES NUAGES DU SOIR ALORS DESCENDS TOUT DE SUITE`, « Valider + Suivant › » ; dans la deuxième, taper `HEY`, « Valider + Suivant › » ; « ‹ Précédent » deux fois : la première porte le texte tapé. Retenir sur l'image où sont ces deux bulles, puis « Quitter (Échap) »
- [x] 🖍️ Annotation : les listes disent *Bibi Fricotin chez les Chinois* et sa planche, et la colonne de droite porte la « Grille d'exemple », ses rubriques « A. Sons » à « E. Image ». Cliquer sur la minicarte la case de la longue bulle, puis sa bulle « b1 » : ses mots sont ceux qu'on a tapés

### Téléphone — 15 min, debout sauf la dernière case

- [x] Page Annotation (un appareil neuf ouvre le « Projet principal » : choisir « Mon bac à sable » dans la liste « Projet »), *Bibi Fricotin chez les Chinois* : « ☰ Planche et contexte » en tête de la colonne, en bas une barre qui dit ce sur quoi on poserait, et « Poser… ▴ » ; rien ne dépasse à droite. Toucher ☰, puis sur la minicarte la case de la longue bulle : le tiroir se referme, la case s'agrandit
- [x] Toucher la bulle `HEY` (si elle est dans une autre case, ☰ et cette case d'abord), puis le mot « HEY » : il se surligne, et la barre dit « Sur « HEY » » ; le retoucher : plus aucun mot n'est désigné
- [x] Revenir à la longue bulle. Toucher « ENFIN », « Étendre » (le bouton reste enfoncé), toucher « GRIMPER » : le passage va de l'un à l'autre. « Ajouter un mot », toucher « NUAGES » : il entre ; toucher « BIBI » : il sort. Pendant tout cela, les deux boutons et le mot touché restent à l'écran, sans saut du défilement
- [x] « Ajouter un mot » pour l'éteindre, « Poser… ▴ » : la grille monte du bas ; cocher « cri » ; « Fermer ✕ » : la page revient, et le passage porte son trait
- [x] « Poser… ▴ », toucher « Chercher dans la grille… » : le clavier virtuel paraît, le champ reste visible au-dessus de lui ; taper « echo » : le champ et « écho » restent visibles au-dessus du clavier ; dire si le bas de la feuille passe sous lui (sa hauteur, 88 % de l'écran, ne rapetisse pas quand le clavier sort) ; « Fermer ✕ »
- [x] Dans la rangée des zones, toucher la case elle-même (« La case c… »), puis glisser le doigt dans la case agrandie SANS avoir touché « ✎ Tracer une zone » : la page défile ou rien ne bouge, mais aucun rectangle ne naît
- [x] Toucher « ✎ Tracer une zone » (il reste enfoncé), glisser le doigt lentement dans la case, l'arrêter, le lever : un rectangle suit le doigt, la page ne défile pas (sur un iPhone, dire si Safari défile quand même), puis « Détail d'image », « Texte hors bulle », « Annuler » paraissent ; toucher « Annuler »
- [x] Toucher « ✎ Tracer une zone », tracer VITE, le doigt levé en pleine course, puis toucher UNE fois « Détail d'image » : le détail naît à ce premier toucher, et le tiroir s'ouvre. Mesuré en émulation : ce toucher est perdu, il en faut un second ; dire ce que fait le vrai appareil
- [x] Le tiroir ouvert, le curseur dans Nom : le clavier virtuel laisse le champ visible ; taper un nom, valider, « Fermer ✕ » : le nom s'écrit sur l'image
- [ ] Téléphone couché, s'il fait moins de 760 px de large : « Poser… ▴ » : la grille se lit et ses entrées se cochent. Mesuré en émulation à 667 × 375 : la grille n'y reçoit que 8 px, la boîte de bas gardant sa hauteur ; dire ce que fait le vrai appareil (au-delà de 760 px, il n'y a pas de feuille : la grille reste en colonne à droite, et on regarde si elle se sert)

### Tablette — 5 min, moins de 1 200 px de large (en portrait si besoin)

- [x] La grille à droite, « ☰ Planche et contexte » en tête de la colonne. La case de la longue bulle, sa bulle « b1 », cocher « réponse à une autre bulle », « Désigner sur la planche » : le tiroir s'ouvre de lui-même, et la minicarte porte « Cliquez la zone liée · Échap annule » ; toucher une AUTRE bulle de la minicarte : le tiroir se referme, et la ligne nomme la zone liée (« ↔ b2 « … » ») ; dire si l'étiquette « Cliquez la zone liée », posée sur le haut de la minicarte, cache une bulle qu'on voudrait toucher
