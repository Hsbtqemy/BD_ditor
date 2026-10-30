---
passe: Page Annotation, jalon 1 — lire la grille, désigner, poser, terminer, parcourir, annuler
chantier: ANN-7
duree: 40 min
derniere:
---

# QA — la page Annotation, premier jalon de la tranche 2

**Écrite le 2026-10-28 sur la recette reconstruite sur `312e8a5`**, décor de l'état `avant-ann7-j1`
(`C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-ann7-j1`) : le décor `avant-3b` migré en
schéma 38, plus la grille FICTIVE du dépôt (`tools/grille-modele.csv`), importée, publiée et
activée sur le « Projet principal » sous le nom « Sons et images (fictive) ». Aucun relevé n'est
posé. Elle porte sur les cinq commits du jalon 1 (`fa820e4` à `c7369b8`) et sur le cadrage
`docs/ann7-tranche2-cadrage.md`.

**Les comptes** : `stagiaire` (écrit dans « Collection Test », lit seulement « Carnet
d'arrivant ») et `proprio` (propriétaire de « Collection Test »). Une fenêtre privée par compte.
L'album est « esther v1 », planche 1, celui de « Collection Test » : sa planche 1 porte le texte
transcrit, les planches 2 à 4 n'en ont pas.

**Ce que la passe ne juge pas** : le doute, la Synthèse et « ⟳ Actualiser » (jalon 2) ; le
Contexte modifiable, tracer une zone et les écrans étroits (jalon 3) ; 320 px, grande police et
contraste (mesurés par les tests). Une case qui dit faux alors que l'écran a raison se corrige
SUR PLACE et se signale.

## Reste

### Ouvrir la page — `stagiaire`

- [x] La navigation porte « 🖍️ Annotation » entre l'Atelier et la Bibliothèque ; un clic ouvre une page en trois colonnes : la planche à gauche, la case au milieu, la grille à droite
- [x] Collection « Collection Test », Album « esther v1 », Planche 1 : la minicarte montre les cases de la planche, et la colonne de droite porte un onglet « Sons et images (fictive) »
- [x] Clic, sur la minicarte, dans la case de la bulle « HEY TouCHE-Moi PAS L' CUL SALE PÉDÉ 1 » (en haut à droite) : la case s'agrandit au milieu, l'en-tête dit « Case c1 » ; clic sur la bulle DANS la case agrandie : l'en-tête dit « bulle b2 », et sous « Mots de la bulle b2 » son texte s'écrit tel qu'il a été transcrit (« L' CUL » avec son espace)
- [x] L'adresse porte `collection=`, `album=`, `planche=` et `region=` ; F5 rouvre la même bulle

### Lire la grille — `stagiaire`, même bulle

- [x] Les rubriques se replient et se déplient ; « A. Sons » dépliée montre « Voix » et « Bruits »
- [x] « Afficher » choisit toute la grille ou une seule rubrique de tête ; « B. Provenance » seule ne montre plus que « origine du son » et « écho »
- [x] Revenir à toute la grille, survoler « onomatopée de choc » : la ligne du guide, en bas de la colonne, dit « un mot qui imite le bruit d'un choc » puis « Exemples : bang : BANG ! · bang : PAN ! · crac : CRAC · splash : PLOUF · splash : SPLASH », sans que la colonne change de hauteur
- [x] Clic sur un fond neutre (hors d'un champ ou d'une liste : « Afficher » garde sinon le curseur), puis la TOUCHE « / » du clavier (Maj + « : » sur un clavier français) : le curseur est dans « Chercher dans la grille… » ; taper « echo » ne laisse que « écho » (B. Provenance) ; Échap vide le champ
- [x] « Guide complet ▸ » ouvre une fenêtre qui reprend toute la grille ; Échap la ferme et rend le focus au bouton

### Désigner des mots et poser — `stagiaire`, même bulle

- [x] Clic sur « TouCHE-Moi », puis Maj+clic sur « CUL » : « TouCHE-Moi PAS L' CUL » est surligné, et la liste en bas s'intitule « Sur « TouCHE-Moi PAS L ' CUL » » ; « Porte sur » propose « des mots », « toute la bulle », « la case » et « la planche », enfoncé sur « des mots »
- [x] Cocher « cri » : un trait apparaît sous les quatre mots, et « cri » s'inscrit dans la liste de ce qui est posé, en bas de la colonne ; la rubrique « A. Sons » dit « 1 ici »
- [x] Recocher « cri » sur le même passage : le relevé part, le trait et la ligne de la liste aussi
- [x] Désigner « HEY » seul, cocher la variante « bang » d'« onomatopée de choc », puis cocher « crac » : il n'y a toujours qu'UN relevé sous « HEY », et la liste dit « crac »
- [x] Sur « HEY », cocher le qualificatif « taille » d'« intensité graphique », puis « couleur » : un seul relevé « intensité graphique », dont la ligne dit les deux qualificatifs
- [x] Sur « HEY », poser « origine du son » (un qualificatif au choix) : sa ligne dit « à compléter » ; taper un lieu dans sa précision, sortir du champ : « à compléter » disparaît
- [x] « Porte sur » : « toute la bulle », cocher « crié » de « ton de voix », puis « chuchoté » : dans la grille, seul « chuchoté » reste enfoncé et « ton de voix » compte 1 ; clic sur « b2 · bulle » (rangée des zones, ce qui ne désigne plus aucun mot) : la liste, « Dans la bulle b2 », dit « ton de voix · chuchoté » et « toute la zone »
- [x] Toujours sur la bulle b2, aucun mot désigné, poser « réponse à une autre bulle » : sa ligne dit « à compléter » et offre « Désigner sur la planche » ; ce bouton, clic sur la case de « Pédé ! » dans la minicarte (case c2), puis sur la bulle « Pédé ! » dans la case agrandie ; revenu sur la bulle b2 de la case c1 : la ligne n'a plus « à compléter » et offre « Changer le lien »
- [x] ✕ sur la ligne « intensité graphique » de la liste (posée plus haut sur « HEY ») : le relevé part, la ligne aussi, et son trait sous « HEY »
- [x] Sur la bulle b2, cocher « regard caméra » puis « ambiance sonore de la planche », quel que soit « Porte sur » : la liste dit « regard caméra · la case » ; « ‹ Précédente » depuis « La case c1 » (zone 1 / 41) mène à « La planche » (zone 41 / 41), dont la liste dit « ambiance sonore de la planche · la planche » ; revenir ensuite sur la bulle b2

### Deux écrans sur le même relevé — `stagiaire` et `proprio`, planche 1, bulle « HEY TouCHE-Moi… »

- [x] `proprio` ouvre la même bulle : il voit les relevés posés par `stagiaire`, avec leurs traits
- [x] `proprio` tape « le préau » dans la précision d'« origine du son » et sort du champ ; puis `stagiaire`, SANS recharger, tape un AUTRE texte, « la cour », dans la même précision et sort du champ : un bandeau prend la place de la ligne du guide, nomme `proprio`, et offre « Remplacer par la mienne » et « Garder l'autre » (le même texte des deux côtés ne fait pas de conflit : rien ne se perd)
- [x] Tant que le bandeau est ouvert, cliquer une entrée de la grille ne change rien : un message dit « Réglez d'abord le conflit, en bas de la grille. » ; « Garder l'autre » ferme le bandeau et la précision dit celle de proprio

### Terminer et parcourir — `stagiaire`

- [x] Sur une bulle de la planche 1, le pied de la colonne du milieu dit « Sons et images (fictive) : à faire », et l'en-tête dit « zone i / n de « Sons et images (fictive) » »
- [x] « Terminée, suivante › » passe à la zone suivante ; « ‹ Précédente » y revient : le pied dit « ✓ Sons et images (fictive) : terminée », et l'onglet de la grille porte ✓
- [x] « Rouvrir » : le pied redit « … : à faire », le ✓ de l'onglet part
- [x] Clic sur « b1 · bulle » de la case c1 (zone 2 / 41), « Terminée, suivante › » deux fois (b1 puis b2 terminées), « Parcours » : « à faire seulement », clic sur la case c1 dans la minicarte (zone 1 / 41), puis « Suivante › » : l'en-tête dit « zone 4 / 41 » (Case c2), b1 et b2 sautées
- [x] « Parcours » toujours sur « à faire seulement », sur la case c2 (zone 4 / 41) : Ctrl+Entrée mène à la zone 5 / 41, dont le pied dit encore « … : à faire » ; Ctrl+Maj+Entrée revient à la zone 4, puis à la zone 1 (b1 et b2 sautées)
- [x] Clic sur la case c1 dans la minicarte, « Afficher » sur « A. Sons » : le pied dit « Sons et images (fictive) › A. Sons : à faire » ; « Terminée, suivante › », puis de nouveau clic sur la case c1 dans la minicarte : le pied dit « ✓ Sons et images (fictive) › A. Sons : terminée · stagiaire » ; « Afficher » sur « Toute la grille » : le pied redit « Sons et images (fictive) : à faire »

### Annuler — `stagiaire`

- [x] Poser « cri » sur un mot, puis Ctrl+Z (focus hors d'un champ de saisie) : un message « Annulé : … » s'affiche, le trait et la ligne de la liste disparaissent
- [x] Atelier (/), même planche, mode « Édition » : déplacer la bulle « HEY… » à la souris, puis Ctrl+Z : un message « Annulé : modification d'une région » s'affiche, et X / Y de « Coordonnées » reviennent à leurs valeurs d'avant

### Lire sans écrire — `stagiaire`, « Carnet d'arrivant »

- [ ] Collection « Carnet d'arrivant », Album « esther v1 », Planche 1, bulle b2 de la case c1, « HEY » désigné : la grille est là, ses entrées se VOIENT éteintes ; cliquer « cri » ou « crac » ne pose rien (la liste « Sur « HEY » » dit « — ») et un message dit qu'on lit cet album
- [x] « Terminée, suivante › » est éteint, et son infobulle dit qu'on lit cet album

### Le lien avec l'Atelier — `stagiaire`

- [x] « Ouvrir dans l'Atelier ↗ » ouvre l'Atelier sur la même bulle ; son retour ramène à la page Annotation, sur la même bulle
