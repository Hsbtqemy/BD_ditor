---
passe: L'écran du mode libre — page Annotation et Recherche
chantier: ANN-7
duree: 70 min
---

# QA — le Mode libre sur la page Annotation, et ses étiquettes dans la Recherche

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur `a509448` ou après
(branche `ann7-sur-dev` : la branche d'ANN-7 rejouée au-dessus de `dev`, PAS encore sur `dev`),
état `apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`).
Au démarrage, l'application migre la base en v39 : le vocabulaire d'hier (tags, attributs de case)
disparaît, et chaque projet reçoit sa grille de travail, « Travail en cours », que l'écran appelle
« Mode libre ». Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`, hors dépôt. Fenêtre
privée à 1 280 px, sauf mention contraire ; une fenêtre par compte, chaque zone dit laquelle. Les
onglets de la grille portent un compteur entre parenthèses (« Mode libre (2) ») : les cases les
nomment sans lui.

**Les comptes** — `stagiaire` : annotateur du « Projet principal » (il écrit dans « Collection
Test », et lit « Carnet d'arrivant »). `proprio` : responsable du « Projet principal ». `invite` :
responsable de « Projet QA », un projet qui n'a aucune grille. Les zones s'enchaînent dans l'ordre :
chacune part de l'état laissé par la précédente.

**Le décor.** « Projet principal » a une grille FERMÉE, « Sons et images (fictive) », v1 active ;
sur esther v1, planche 1, la bulle « HEY TouCHE-Moi PAS L' CUL… » porte « cri » et « réponse à une
autre bulle », et le texte « ÉCOLE PRIMAIRE » porte « cri ». Le Mode libre est vide partout. Sur
esther v1, planche 1, la bulle « Haha coucou Esther » est la bulle b2 de la case c5 (son texte se lit
en infobulle sur « b2 · bulle »), la case c1 est celle d'« ÉCOLE PRIMAIRE », et la case c7 n'a ni
bulle ni texte.

**Ce que la passe éprouve** — l'écran tranché sur maquette par Hugo le 2026-11-06 : sur la page
Annotation, l'onglet « Mode libre » en premier, son champ « + Nouvelle étiquette… », les puces,
« ✎ » et ses gestes rares, « ↕ Ranger », « + » et « / » ; dans la Recherche, les relevés de
chaque résultat en ligne, le clic qui isole et la liste « Porte… ». Les choix à confirmer sont dans
`pilotage/ANN-7.md`, case « Les choix de l'écran du mode libre sont confirmés » : la passe les
montre, elle ne les tranche pas.

**Rejouée sans écran avant d'être rendue**, le 2026-11-06, sous ces trois identités, sur une copie du
décor migrée en v39 : toutes les cases sauf celle d'un vrai appareil ; quatre cases réécrites d'après
ce rejeu. Ce qu'il a relevé sans en faire une case — le « — » qui reste dans la liste de ce qui est
posé quand rien ne l'est, l'absence de trace visible d'une étiquette créée depuis une grille
fermée, « (J8) » lisible à l'écran — est dans `pilotage/ANN-7.md`.

**Ce qu'elle ne juge pas** — la tablette et le téléphone (une case pour un vrai appareil, en
fin) ; 320 px, grande police et contraste, mesurés par les tests ; la migration v39 elle-même.
En fin de passe, `restaurer apres-moustache` avant toute autre passe qui part de ce décor.

## Reste

### Un projet sans grille — fenêtre `invite`, page Annotation, projet « Projet QA »

- [ ] Bande du haut : projet « Projet QA ». Page Annotation, Album « Lot JP2 QA », planche 1, clic sur une case dans la minicarte : la grille n'a qu'un onglet, « Mode libre », et sous lui le champ « + Nouvelle étiquette… » ; la liste des étiquettes, sous le champ, est vide — ni « — », ni intitulé « Sans rubrique »
- [ ] Taper « ironie » dans « + Nouvelle étiquette… » : une ligne flotte sous le champ, « nouvelle étiquette · Entrée », « Créer « ironie » et poser » ; Entrée : « ironie » paraît dans la liste, cochée, et ni le titre de la colonne ni la rangée « Ordre » au-dessus de la liste ne bougent

### Créer et poser — fenêtre `stagiaire`, page Annotation, Collection Test, esther v1, planche 1

- [ ] Collection « Collection Test », Album « esther v1 », Planche « planche 1 ». L'onglet ouvert est « Sons et images (fictive) » ; « Mode libre » est le premier onglet, à sa gauche
- [ ] Choisir la case c5 dans la minicarte, puis « b2 · bulle » dans la rangée des zones (« Haha coucou Esther »). Onglet « Mode libre », taper « sentiment : perte ; tristesse » : la ligne sous le champ dit « Créer « sentiment : perte, tristesse » et poser » ; Entrée : « sentiment » porte deux puces teintées, « perte » et « tristesse »
- [ ] Cliquer la puce « perte » : elle seule perd sa teinte, « tristesse » reste posée. Recliquer « perte » : elle redevient teintée
- [ ] Clic sur le titre de la case (hors d'un champ), Ctrl+Z : un message « Annulé : pose d'un relevé », et « perte » perd sa teinte ; « tristesse » reste posée
- [ ] Choisir la case c1 elle-même (celle d'« ÉCOLE PRIMAIRE » : clic sur son fond dans la case agrandie, ou sa ligne « La case c1 » dans la rangée des zones). Mode libre, taper « lieu : école », Entrée : « lieu » porte la puce « école », teintée
- [ ] Choisir la case c7 (ni bulle ni texte : sa rangée des zones ne montre qu'elle-même). Taper « silence », Entrée : « silence » paraît cochée

### Depuis une grille fermée — même fenêtre, même planche

- [ ] Onglet « Sons et images (fictive) », case c5, bulle b2. Taper « rire » dans le filtre de l'onglet : la grille dit « Rien pour « rire » », puis offre « Créer « rire » dans Mode libre » ; Entrée : l'onglet reste « Sons et images (fictive) », et le compteur de l'onglet « Mode libre » augmente d'un ; ouvrir l'onglet « Mode libre » : « rire » y est posé sur la bulle
- [ ] Retour à « Sons et images (fictive) », taper « cri » dans le filtre : « cri » se lit dans la liste, et rien ne propose de créer dans le Mode libre
- [ ] Hors d'un champ (clic sur le titre de la case), taper « + » : l'onglet « Mode libre » s'ouvre, le focus dans « + Nouvelle étiquette… ». Clic sur l'onglet « Sons et images (fictive) », puis hors d'un champ, taper « / » : le focus est dans le filtre de cet onglet

### Ranger — même fenêtre, onglet « Mode libre »

- [ ] La rangée au-dessus des étiquettes dit « Ordre : À la main », et les étiquettes sont dans l'ordre où elles sont nées (sentiment, lieu, silence, rire). Choisir « A → Z » : lieu, rire, sentiment, silence ; « ↕ Ranger » est éteint, et son clic dit « On range dans l'ordre « À la main » »
- [ ] Recharger la page (F5) : la même zone revient, et l'ordre est toujours « A → Z ». Revenir à « À la main », cliquer « ↕ Ranger » : chaque étiquette porte une poignée ⠿ et ↑ ↓, le bouton dit « Fini »
- [ ] Au clavier : Tab jusqu'au ↓ de « sentiment », Entrée : « sentiment » passe sous « lieu », et le focus reste sur son ↓. Clic sur « Fini », puis hors d'un champ, Ctrl+Z : « Annulé : déplacement d'une étiquette », et « sentiment » revient en tête

### Deux écrans — fenêtres `proprio` et `stagiaire`, même planche

- [ ] Fenêtre `proprio` : page Annotation, Collection Test, esther v1, planche 1, onglet « Mode libre » : les quatre étiquettes de `stagiaire` y sont, dans le même ordre. « ↕ Ranger », monter « silence » en tête, « Fini »
- [ ] Fenêtre `stagiaire`, sans recharger : dans les trente secondes, « ⟳ Actualiser » paraît dans la bande de la planche ; le cliquer : « silence » est en tête, et la zone choisie, ses puces et l'onglet n'ont pas changé

### ✎ et les gestes rares — fenêtre `proprio`, onglet « Mode libre »

- [ ] Choisir la case c5, bulle b2. Sur « rire », « ✎ » : le nom devient un champ, à côté l'état « provisoire » ; dessous, « Définir », « Fusionner dans… », « Passer dans une grille… », « Retirer… ». Renommer en « rire nerveux », Entrée : l'étiquette s'appelle « rire nerveux », dans la liste et posée sur la bulle
- [ ] Toujours dans « ✎ », « Définir » : l'état dit « ✓ définie » dans ✎, et nulle part ailleurs dans la grille ; « Remettre provisoire » paraît à la place de « Définir »
- [ ] « Passer dans une grille… » : la confirmation montre « Voir le bilan… » éteint ; son clic dit sur place « Le bilan, relevé par relevé : une tranche à part (J8) », sans rien faire
- [ ] Sur « silence », « ✎ », « Fusionner dans… » : la liste propose « rire nerveux » ; le choisir : la phrase dit « 1 relevé passe à « rire nerveux ». » ; « Fusionner » : « silence » disparaît, et la case c7 porte maintenant « rire nerveux »
- [ ] Choisir la case c1. Sur « lieu », « ✎ », « + valeur », taper « cour », Entrée : « lieu » a deux valeurs, « école » et « cour », toutes deux posées sur la case c1

### Ce qu'un annotateur ne fait pas — fenêtre `stagiaire`, onglet « Mode libre »

- [ ] « ⟳ Actualiser » s'il paraît. Sur « rire nerveux » (définie par `proprio`), « ✎ » est éteint mais se focalise ; son clic dit « « rire nerveux » est définie : seuls les responsables la changent »
- [ ] Sur « sentiment » (provisoire), « ✎ » s'ouvre : renommer en « émotion », Entrée, marche ; « Fusionner dans… », « Retirer… » et « Définir » sont éteints, et leur clic dit « Fusionner, retirer et définir : les responsables du projet »
- [ ] Case c5, bulle b2, taper « rire nerveux : jaune » dans « + Nouvelle étiquette… » : la ligne sous le champ est éteinte et dit « « rire nerveux » n'a pas de valeurs », et Entrée ne pose rien

### La Recherche — fenêtre `stagiaire`, page Recherche

- [ ] Le champ dit « Rechercher dans les dialogues, notes, étiquettes… ». Taper « coucou », Entrée : la bulle « Haha coucou Esther » de « Collection Test » sort ; sous son texte, une ligne « Mode libre : émotion : tristesse, rire nerveux » (le nom de la grille en encre discrète), « Mode libre » en premier. La copie de « Carnet d'arrivant » sort aussi, sans relevé
- [ ] Taper « ecole » (sans accent), Entrée : le texte « ÉCOLE PRIMAIRE » sort avec « ÉCOLE » surligné et la ligne « Sons et images (fictive) : cri » ; la case c1 sort aussi, dite « Case c1, sans texte », avec « Mode libre : lieu : école, lieu : cour », « école » surligné dans l'étiquette
- [ ] Taper « nerveux », Entrée : la case c7 sort, dite « Case c7, sans texte », avec « Mode libre : rire nerveux », et la bulle « Haha coucou Esther » aussi
- [ ] Sur le résultat de la bulle, cliquer « rire nerveux » dans sa ligne : une puce « porte · Mode libre › rire nerveux ✕ » paraît au-dessus des résultats, et seules les zones qui la portent restent ; l'adresse de la page porte `porte=`
- [ ] Vider le champ, liste « Porte… » à côté des filtres d'album et de type : elle propose « Mode libre » d'abord, avec ses étiquettes et leurs valeurs, puis « Sons et images (fictive) », ses rubriques et ses entrées (une grille FERMÉE) ; choisir « cri » : une seconde puce, reliée à la première par « et », et aucun résultat (aucune zone ne porte les deux)
- [ ] ✕ de la puce « rire nerveux » : les zones qui portent « cri » restent ; F5 : la puce « cri » est toujours là, et l'adresse aussi. Pas de bouton « ⤓ Export CSV » : une phrase dit qu'exporter demande un droit que le propriétaire d'une collection accorde
- [ ] ✕ de la dernière puce : plus aucune puce, la liste « Porte… » revient à « Porte… » ; nulle part sur la page un nuage de tags ni le mot « tag »
- [ ] Fenêtre `proprio`, page Recherche, liste « Porte… », choisir « cri », « ⤓ Export CSV » : le fichier a deux lignes, la bulle « HEY TouCHE-Moi PAS L' CUL… » et « ÉCOLE PRIMAIRE »

### L'étroit et le doigt

- [ ] Fenêtre `stagiaire`, page Annotation, fenêtre à 390 px de large, une bulle choisie : « Poser… ▴ » en bas ; hors d'un champ, « + » fait monter la feuille, ouverte sur « Mode libre » avec le focus dans « + Nouvelle étiquette… »
- [ ] Sur une tablette ou un téléphone (un bac à sable de la production, une fois la branche intégrée) : ✎, ↑ ↓, les puces et le champ se touchent sans viser, et rien ne passe par le survol

### L'Administration — fenêtre `proprio`, Administration, vue Projets, « Projet principal »

- [ ] Bloc « Grilles » : la grille de travail y figure sous son nom, « Travail en cours » ; son « Désactiver » est éteint mais se focalise, et son clic dit, sans rien changer, « C'est la grille de travail du projet, qui porte son mode libre : elle ne se désactive, ne se retire ni ne se supprime. » ; « Désactiver » de « Sons et images (fictive) » est offert (ne pas le cliquer)
