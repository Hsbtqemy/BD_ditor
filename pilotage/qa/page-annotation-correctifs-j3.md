---
passe: Page Annotation, correctifs de la passe du jalon 3
chantier: ANN-7
duree: 25 min
---

# QA — les correctifs de la passe du jalon 3 sur la page Annotation

**Écrite le 2026-10-31 sur la recette reconstruite sur le commit 16 de la tranche** (les commits 14, 15 et 16 : `6574c04`, `dcd8a7e` et `bc6295d`), décor de l'état `avant-ann7-j1` (`C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-ann7-j1`) : la grille FICTIVE « Sons et images (fictive) » active sur le « Projet principal », aucun relevé posé. Elle porte sur les relevés de la passe du jalon 3 et sur la saisie en conflit, dans `pilotage/ANN-7.md`.

**Les comptes** : `stagiaire` et `proprio`, tous deux écrivent dans « Collection Test ». Une fenêtre privée par compte, chaque zone dit laquelle. Les cases s'enchaînent dans l'ordre : chacune part de l'état laissé par la précédente.

**Où se lit quoi** : sur écran large, à gauche la minicarte, et sous elle le Contexte ; au milieu la case agrandie, la rangée « Zones de la case », puis « Porte sur » et les mots de la zone ; à droite la grille, sous elle la liste de ce qui est posé, et en bas la boîte du guide.

**Rejouée sans écran avant d'être rendue**, sous ces deux identités, sur une copie du décor : quatre cases y ont été réécrites. Celle qui suit « Remplacer par la mienne » et le clic sur le petit « / », nés de défauts trouvés à ce rejeu, n'ont été joués que par leurs tests e2e. Les couleurs ne se jugent qu'à l'écran : le rejeu en a mesuré la présence et le contraste, pas l'effet.

**Ce que la passe ne juge pas** : les autres voies de perte, ouvertes dans la fiche (changer de projet, quitter la page, une précision retenue) ; le focus au doigt. En fin de passe, la recette porte une zone tracée et des relevés : `restaurer avant-ann7-j1` avant toute autre passe qui part de ce décor.

## Reste

### Le conflit se voit depuis le champ — fenêtres `stagiaire` et `proprio`, page Annotation, Collection Test, esther v1, planche 1

- [ ] Fenêtre `stagiaire` : clic sur la case c1 dans la minicarte — en HAUT À DROITE, cadre bleu, l'en-tête du milieu dit « Case c1 » —, puis sur « b2 · bulle » dans la rangée des zones. Taper « relire ce cri » dans Note (Contexte), attendre « Enregistrée » sous le champ. Fenêtre `proprio` : même planche, même bulle, remplacer la note par « à vérifier », clic sur le titre « Case c1 », attendre « Enregistrée ». Fenêtre `stagiaire`, SANS recharger — ni F5, ni « ⟳ Actualiser » s'il paraît dans la bande — : ajouter « vite » à la fin de la note, clic sur le titre « Case c1 ». Dans le Contexte : le champ Note a un cadre rouge, et « En attente de votre choix » s'écrit en rouge sous lui
- [ ] Même écran, dans la boîte du guide, en bas à droite : le bandeau a un filet rouge à gauche, et son titre « ⚠ Note modifiée par proprio à … » est en rouge. En regardant le Contexte à gauche, le conflit se voit sans chercher
- [ ] Rien n'a bougé à l'arrivée du bandeau : mêmes colonnes, même hauteur de la case agrandie, la rangée des zones au même endroit
- [ ] Sans répondre, clic sur « b1 · bulle » : dans le Contexte, le champ Note de b1 est vide et sans cadre rouge ; le bandeau reste, et sa deuxième ligne finit par « (la bulle b2) », la zone où la saisie attend
- [ ] Clic sur « b2 · bulle » : le champ Note redit « relire ce cri vite », cadre rouge revenu
- [ ] Ajouter « encore » à la fin, puis clic sur « Remplacer par la mienne » dans le bandeau : le bandeau part, le cadre rouge aussi, et « Enregistrée » s'écrit sous Note. Fenêtre `proprio`, F5 : sa note dit « relire ce cri vite encore »
- [ ] Fenêtre `proprio` : remplacer la note par « à revoir », clic sur le titre « Case c1 », attendre « Enregistrée ». Fenêtre `stagiaire`, sans recharger : ajouter « ici » à la fin de la note, s'arrêter de taper jusqu'à ce que le bandeau paraisse (une à deux secondes), puis continuer : taper « et là ». Dans le Contexte, le curseur est resté dans Note, qui finit par « ici et là » ; le bandeau est toujours ouvert, rien n'a été remplacé
- [ ] Clic sur « Garder l'autre » dans le bandeau : le bandeau part, et Note dit « à revoir »
- [ ] Fenêtre `stagiaire` : clic sur « La case c1 » dans la rangée des zones, puis glisser dans le coin bas gauche de la case agrandie, sous le « ? », sans passer le milieu de la case. « Détail d'image », taper « le cartable » dans Nom, Entrée. Fenêtre `proprio`, F5, clic sur « d1 · détail », remplacer le Nom par « la lampe », clic sur le titre « Case c1 ». Fenêtre `stagiaire`, sans recharger (ni F5, ni « ⟳ Actualiser ») : remplacer le Nom par « le sac », clic sur le titre « Case c1 » : dans la boîte du guide, le bandeau dit « Votre nom n'est pas enregistré » ; dans le Contexte, le champ Nom a son cadre rouge, avec « En attente de votre choix » au-dessus de lui
- [ ] Clic sur « b1 · bulle », puis sur « d1 · détail » : le champ Nom redit « le sac ». « Remplacer par la mienne » : le bandeau part. Fenêtre `proprio`, F5 : le Nom du détail dit « le sac », et l'étiquette du détail sur la case agrandie aussi

### La grille porte ses couleurs — fenêtre `stagiaire`, même planche

- [ ] Clic sur « b2 · bulle ». Dans la grille, à droite, en la faisant défiler de A. Sons à E. Image : chaque rubrique de tête a un filet de couleur à gauche, sur toute sa hauteur, sous-rubriques comprises, et une pastille de la même couleur dans son titre. D'un coup d'œil, on repère où finit une partie et où commence la suivante
- [ ] Clic sur le mot « HEY » dans « Mots de la bulle b2 », sous « Porte sur » (l'image ne désigne pas un mot), puis clic sur « bang » dans la grille (A. Sons, Bruits, Chocs) : dans « Mots de la bulle b2 », un trait paraît sous « HEY » ; sous la grille, la liste « Sur « HEY » » montre « onomatopée de choc · bang », et sa pastille, comme le trait, a la couleur du filet de A. Sons
- [ ] Clic sur le titre « A. Sons » pour la replier : réduite à son titre, elle garde son filet et sa pastille. La redéplier. « Aa », dans la bande du haut : bouton « Clair », puis « Sombre », puis case « Contraste élevé » : dans la grille, le filet et la pastille restent lisibles dans chacun. Revenir à « Clair », décocher « Contraste élevé », clic hors du menu

### Au clavier — fenêtre `stagiaire`, même bulle, mot « HEY » toujours désigné

- [ ] Clic sur le petit « / » à droite du champ « Chercher dans la grille… » : le curseur est dans le champ. Tab trois fois — « A. Sons », « Voix », « cri » : un contour se voit sur « cri », entrée sans variante. Entrée : elle se coche, une ligne « cri » s'ajoute sous la grille, et le contour reste sur elle
- [ ] Entrée de nouveau : « cri » se décoche, sa ligne part, le contour y reste. Tab : le contour passe à « ton de voix », l'entrée suivante, sans repartir du haut de la page
- [ ] Onglet « Synthèse », au-dessus de la minicarte, puis clic sur « Relevés ». Tab trois fois, jusqu'au bouton « Case c1 · 1 », Entrée : « La case c1 » s'ouvre au milieu, et le contour reste sur ce bouton. Revenir à l'onglet « Planche », faire défiler la grille, cliquer « regard caméra » (E. Image) à la souris : elle se coche, sans contour sur elle ; recliquer pour la décocher

### Les finitions — fenêtre `stagiaire`

- [ ] Clic sur « b2 · bulle » : dans le Contexte, rien de vide entre la ligne Locuteur et la ligne Note. Clic sur « La case c1 », glisser dans le bas de la case agrandie, à droite du détail, « Texte hors bulle », taper « ÉCOLE », clic sur le titre « Case c1 » : « b3 · texte » s'ajoute à la rangée des zones, et « Porte sur », sous cette rangée, dit « tout le texte » et non « toute le texte »
- [ ] Clic sur « Atelier » dans la navigation : pl.1 s'ouvre sur la dernière zone. Dans l'arbre, à droite, sous « Case #43 », la première : la ligne du détail dit « Détail », avec son accent. Clic sur « Case #43 » dans l'arbre, « Type » sur « bulle », sous l'arbre : un message en bas à droite dit « Cette case porte un détail, qui se range dans une case… », et la liste « Type » redit « case », sans qu'on la resélectionne