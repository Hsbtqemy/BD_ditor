---
passe: Le guide pas à pas du bac à sable
chantier: UX-6
duree: 50 min
---

# QA — le guide pas à pas : chaque étape montre son foyer, et la fenêtre ne le cache jamais

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`b09a916` ou après, état `apres-ann7-j3` restauré (`C:\temp\bd-recette\etat-de-base.ps1
restaurer apres-ann7-j3`). Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`,
hors dépôt. Sous `arrivant`, qui n'a pas encore de bac à sable dans cet état, dans une fenêtre
privée à 1 280 px de large, police ordinaire, sauf mention contraire.

**La planche du parcours** est celle du rôle `pas-a-pas` du jeu des bacs à sable. Dans l'état
restauré, c'est encore *Bibi Fricotin chez les Chinois*, que Hugo a retirée du parcours
(représentation raciste) : la passe se joue après que le jeu de la recette a reçu *Moustache
et Trottinette* découpée à ce rôle — un préalable à trancher, écrit dans `pilotage/UX-6.md`.

**Ce que la passe éprouve** — la tranche 3 d'`UX-6` et sa reprise (`8729427`, `977c833`) :
chaque étape éclaire un FOYER précis, le reste assombri ; la fenêtre du guide se pose à droite
du foyer, sinon à gauche, dessous, dessus, et devient la feuille du bas quand rien ne tient ;
une étape faite se voit sur la planche, sans coche à déclarer. « Recouvrir » veut dire : une
partie du foyer éclairé passe sous la fenêtre.

**Ce que la passe ne joue pas.** L'album de présentation et la visite des pages : la tranche 2,
déjà jouée. Les textes « Automatisez » et « Exporter » : la tranche 4. Les choix à confirmer
sont dans `pilotage/UX-6.md` : la passe les montre, elle ne les tranche pas.

### Prélude, sous `arrivant`
- [ ] Dans la bande du haut, « Mon bac à sable » : l'Atelier s'ouvre sur la planche du parcours, et l'album « Bienvenue dans BéDéditeur » s'ouvre par-dessus
- [ ] Tourner les pages jusqu'à « Essayez sur une vraie planche », choisir « Parcours complet », aller au bout de la visite des pages : la carte « Par où commencer » liste les neuf étapes, numérotées, « Pré-remplir » marqué « facultatif » (ou « optionnel ici : moteur absent » si l'OCR manque)

### Le parcours complet, étape par étape, sous `arrivant`
- [ ] Carte, étape 1 « Constituer le corpus » : la Bibliothèque s'ouvre, seule la carte de l'album du parcours est éclairée, le reste assombri, et la fenêtre est posée à côté d'elle sans la recouvrir ; la tête de la fenêtre dit « 1 / 9 »
- [ ] Ouvrir l'album du parcours (clic sur sa carte) : la fenêtre dit « ✓ Fait », et le bouton de droite passe de « Passer → » à « Suivant → »
- [ ] Les gestes de la fenêtre se lisent dans cet ordre : « ✓ Fait » (quand l'étape l'est), ←, le geste principal poussé à droite, ☰, ✕
- [ ] « Suivant → », étape 2 « Décrire l'album » : la tête de la fiche de l'album est éclairée et la fenêtre à côté d'elle ; ouvrir la notice de l'album (✎ de sa fiche), y écrire une source de numérisation, enregistrer : « ✓ Fait »
- [ ] Étape 3 « Pré-remplir » : l'Atelier s'ouvre, « Traitement » est éclairé et la fenêtre à côté ; l'ouvrir : sa liste se lit en clair, jamais sous l'assombri, et la fenêtre ne la recouvre pas ; sans OCR, le titre porte « optionnel ici » et le bouton dit « Suivant → » sans rien lancer
- [ ] Étape 4 « Tracer une zone » : la planche et sa barre sont éclairées, la fenêtre à côté ; « ✎ Tracer » est dans la barre du canevas. Tracer une case sur le fond, puis, dans elle, une bulle (Maj + glisser, ou « ✎ Tracer ») : « ✓ Fait » ne vient qu'une fois les DEUX tracées, et le guide ne passe pas seul à l'étape suivante
- [ ] Étape 5 « Corriger le découpage » : en y entrant, la planche se rapproche d'une bulle, qui se voit EN ENTIER à côté de la fenêtre, jamais dessous ; la bulle et le panneau de droite sont éclairés
- [ ] Agrandir cette bulle par une poignée (la poignée répond, même si elle dépasse un peu du trou) : « ✓ Fait » ; « Suivant → » : la planche revient entière
- [ ] Étape 6 « Transcrire et relire » : le mode Transcription s'ouvre, sa colonne du texte est éclairée et la fenêtre à côté ; recopier le texte d'une bulle, Tab passe à la suivante ; « ✓ Fait » ne vient qu'une fois TOUTES les zones de texte de la planche transcrites (parcours complet)
- [ ] Étape 7 « Annoter » : la page Annotation s'ouvre, la case agrandie et la grille sont éclairées, la fenêtre à côté et sans les recouvrir ; cliquer un mot puis une entrée de la grille : « ✓ Fait »
- [ ] Étape 8 « Chercher et explorer » : la Recherche s'ouvre, sa barre de recherche et la phrase sur le bac à sable sont éclairées, la fenêtre à côté ; le bouton dit « Suivant → » sans geste à faire
- [ ] Étape 9 « Exporter » : la fiche de l'album s'ouvre dans la Bibliothèque, la liste de ses actes est éclairée, la fenêtre à côté ; le bouton dit « Terminer »
- [ ] « Terminer » : la fenêtre dit « Parcours terminé », et montre les autres planches du jeu en vignettes ; une vignette ouvre sa planche dans l'Atelier, sans guide

### La carte et le retour, sous `arrivant`
- [ ] « Par où commencer » (rouvert par le « ? » ou la carte) : les étapes faites portent « ✓ » au lieu de leur numéro ; un lecteur d'écran y lit « (fait) »
- [ ] Sous les étapes, la carte propose « Revoir la présentation » puis « Revoir les pages »
- [ ] Pendant une étape, ✕ : la fenêtre se ferme en disant « « Par où commencer » le rouvre, à la même étape. » ; rouvrir la carte et reprendre : on revient à l'étape quittée
- [ ] Pendant une étape, Échap fait ce que fait ✕
- [ ] Pendant une étape, recharger la page (F5) : le guide reprend à la même étape, dans cet onglet ; un nouvel onglet où l'on TAPE l'adresse de l'Atelier ne rouvre pas le guide de lui-même ; « Par où commencer » l'y rouvre
- [ ] « ☰ » ouvre la carte depuis la fenêtre ; ← revient à l'étape d'avant, et est éteint sur la première

### Le parcours rapide, sous `arrivant`
- [ ] Carte, « Passer au parcours rapide » (ou le choix de parcours) : quatre étapes, « Tracer une zone », « Corriger le découpage », « Transcrire et relire », « Annoter », comptées « n / 4 »
- [ ] « Transcrire et relire » y est faite dès qu'UNE zone de texte est transcrite

### Petits écrans et grande police, sous `arrivant`
- [ ] Fenêtre à 768 px, « Aa » → la plus grande police, rejouer les étapes 1, 4, 5, 6 et 7 (← et « Suivant → ») : à chacune, le foyer éclairé se voit en entier, la fenêtre à côté de lui ou en feuille en bas, jamais par-dessus
- [ ] Dans ces conditions, à l'étape 1, la carte de l'album du parcours peut être amenée au-dessus de la feuille en faisant défiler la page jusqu'en bas
- [ ] Fenêtre à 600 px de large : la fenêtre du guide est une feuille en bas, pleine largeur, et la page réserve sa hauteur (le bas de la planche n'est pas caché sous elle)
- [ ] À l'étape 4, zoomer la planche à la main, puis changer la largeur de la fenêtre : noter si le zoom est perdu (la planche se réajuste quand la feuille réserve sa place, un choix à confirmer)

### Clavier et lecteur d'écran, sous `arrivant`
- [ ] Pendant une étape, Tab passe des zones jouables de l'étape aux gestes de la fenêtre et revient, sans s'arrêter sur ce qui est assombri et sans piège ; aucun `role="dialog"` modal n'enferme le focus
- [ ] Quand une étape devient faite, un lecteur d'écran l'annonce une fois (« … : fait. »), sans répéter à chaque redessin
- [ ] En thème clair puis sombre, le texte de la fenêtre, « ✓ Fait » et la marque « optionnel ici » se lisent sur l'assombri
