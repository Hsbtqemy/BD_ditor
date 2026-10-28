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
- [x] Clic, sur la minicarte, dans la case de la bulle « HEY TouCHE-Moi PAS L' CUL SALE PÉDÉ 1 » : la case s'agrandit au milieu ; clic sur la bulle DANS la case agrandie : elle est choisie, et son texte s'écrit mot par mot sous « Texte », tel qu'il a été transcrit (« L' CUL » avec son espace)
- [x] L'adresse porte `collection=`, `album=`, `planche=` et `region=` ; F5 rouvre la même bulle

### Lire la grille — `stagiaire`, même bulle

- [x] Les rubriques se replient et se déplient ; « A. Sons » dépliée montre « Voix » et « Bruits »
- [x] « Afficher » choisit toute la grille ou une seule rubrique de tête ; « B. Provenance » seule ne montre plus que « origine du son » et « écho »
- [x] Revenir à toute la grille, survoler « onomatopée de choc » : la ligne du guide, en bas de la colonne, dit « un mot qui imite le bruit d'un choc » et ses variantes, sans que la colonne change de hauteur
- [x] Touche « / » : le curseur est dans le filtre ; taper « echo » trouve « écho » (sans accent) ; Échap vide le champ
- [x] « Guide complet ▸ » ouvre une fenêtre qui reprend toute la grille ; Échap la ferme et rend le focus au bouton

### Désigner des mots et poser — `stagiaire`, même bulle

- [x] Clic sur « TouCHE-Moi », puis Maj+clic sur « CUL » : les quatre mots sont désignés ; « Porte sur » propose « des mots », « toute la bulle », « la case » et « la planche », sur « des mots »
- [x] Cocher « cri » : un trait apparaît sous les quatre mots, et « cri » s'inscrit dans la liste de ce qui est posé, en bas de la colonne ; la rubrique « A. Sons » dit « 1 ici »
- [x] Recocher « cri » sur le même passage : le relevé part, le trait et la ligne de la liste aussi
- [x] Désigner « HEY » seul, cocher la variante « bang » d'« onomatopée de choc », puis cocher « crac » : il n'y a toujours qu'UN relevé sous « HEY », et la liste dit « crac »
- [x] Sur « HEY », cocher le qualificatif « taille » d'« intensité graphique », puis « couleur » : un seul relevé « intensité graphique », dont la ligne dit les deux qualificatifs
- [x] Sur « HEY », poser « origine du son » (un qualificatif au choix) : sa ligne dit « à compléter » ; taper un lieu dans sa précision, sortir du champ : « à compléter » disparaît
- [x] « Porte sur » : « toute la bulle », cocher « crié » de « ton de voix », puis « chuchoté » : un seul « ton de voix » sur la bulle, qui dit « chuchoté »
- [x] Toujours sur toute la bulle, poser « réponse à une autre bulle » : sa ligne dit « à compléter » ; « Désigner sur la planche », puis clic sur la bulle « Pédé ! » dans la minicarte : le lien est posé, « à compléter » disparaît
- [x] ✕ sur la ligne « intensité graphique » de la liste (posée plus haut sur « HEY ») : le relevé part, la ligne aussi, et son trait sous « HEY »
- [x] « regard caméra » se pose sur la case et « ambiance sonore de la planche » sur la planche, quel que soit « Porte sur » : la liste les dit sur « la case » et « la planche »

### Deux écrans sur le même relevé — `stagiaire` et `proprio`, planche 1, bulle « HEY TouCHE-Moi… »

- [ ] `proprio` ouvre la même bulle : il voit les relevés posés par `stagiaire`, avec leurs traits
- [ ] `proprio` change la précision d'« origine du son » (s'il a été retiré, `stagiaire` le repose avant) et sort du champ ; puis `stagiaire`, SANS recharger, change la même précision et sort du champ : un bandeau prend la place de la ligne du guide, nomme `proprio`, et offre « Remplacer par la mienne » et « Garder l'autre »
- [ ] Tant que le bandeau est ouvert, cocher une autre entrée ne pose rien ; « Garder l'autre » ferme le bandeau et la précision dit celle de `proprio`

### Terminer et parcourir — `stagiaire`

- [ ] Sur une bulle de la planche 1, le pied de la colonne du milieu dit « Sons et images (fictive) : à faire », et l'en-tête dit « zone i / n de « Sons et images (fictive) » »
- [ ] « Terminée, suivante › » passe à la zone suivante ; « ‹ Précédente » y revient : le pied dit « ✓ Sons et images (fictive) : terminée », et l'onglet de la grille porte ✓
- [ ] « Rouvrir » : le pied redit « … : à faire », le ✓ de l'onglet part
- [ ] Marquer deux zones terminées, choisir « à faire seulement », revenir à la première zone du parcours : « Suivante › » saute les deux zones terminées
- [ ] Ctrl+Entrée passe à la zone suivante, Ctrl+Maj+Entrée revient à la précédente, sans rien marquer
- [ ] « Afficher » sur « A. Sons », marquer la zone terminée : le pied nomme la rubrique, et revenir à toute la grille la dit encore « à faire »

### Annuler — `stagiaire`

- [ ] Poser « cri » sur un mot, puis Ctrl+Z (focus hors d'un champ de saisie) : un message « Annulé : … » s'affiche, le trait et la ligne de la liste disparaissent
- [ ] Ctrl+Z dans l'Atelier, sur une région qu'on vient de déplacer, s'annule toujours comme avant

### Lire sans écrire — `stagiaire`, « Carnet d'arrivant »

- [ ] Collection « Carnet d'arrivant », Album « esther v1 », Planche 1, une bulle : la grille est là, ses entrées éteintes ; cliquer une entrée ne pose rien
- [ ] « Terminée, suivante › » est éteint, et son infobulle dit qu'on lit cet album

### Le lien avec l'Atelier — `stagiaire`

- [ ] « Ouvrir dans l'Atelier ↗ » ouvre l'Atelier sur la même bulle ; son retour ramène à la page Annotation, sur la même bulle
