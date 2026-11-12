---
passe: Le guide pas à pas du bac à sable
chantier: UX-6
duree: 50 min
---

# QA — le guide pas à pas : chaque étape montre son foyer, et la fenêtre ne le cache jamais

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`ce90237` ou après, état `apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1
restaurer apres-moustache`), puis le jeu repréparé, qui y manque de sa planche d'essai (`docker exec bd-app python tools/preparer_jeu.py --depot /data/jeu-depot --serveur /data/jeu-serveur --appliquer`). Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`,
hors dépôt. Sous `arrivant`, qui n'a pas encore de bac à sable dans cet état, dans une fenêtre
privée à 1 280 px de large, police ordinaire, sauf mention contraire.

**La planche du parcours** est celle du rôle `pas-a-pas` du jeu des bacs à sable : dans l'état
restauré, *Moustache et Trottinette* (Calvo), sa dernière rangée découpée sauf la case du
milieu — à gauche une case et ses deux bulles, à droite une case. *Bibi Fricotin chez les
Chinois* reste au jeu pour s'exercer, hors du parcours (`pilotage/UX-6.md`, à valider).

**Ce que la passe éprouve** — la tranche 3 d'`UX-6` et sa reprise (`8729427`, `977c833`) :
chaque étape éclaire un FOYER précis, le reste assombri ; la fenêtre du guide se pose à droite
du foyer, sinon à gauche, dessous, dessus, et devient la feuille du bas quand rien ne tient ;
une étape faite se voit sur la planche, sans coche à déclarer. « Recouvrir » veut dire : une
partie du foyer éclairé passe sous la fenêtre.

**L'ordre est celui de l'écran** (réécrite le 2026-11-05) : l'album, la visite, puis les
étapes, chacune avec ce que la tranche 4 y a changé. Les choix à confirmer sont dans
`pilotage/UX-6.md` : la passe les montre, elle ne les tranche pas. Une remarque de contenu va dans le fil.

### Prélude, sous `arrivant`
- [x] Dans la bande du haut, « Mon bac à sable » : l'Atelier s'ouvre sur la planche du parcours, et l'album « Bienvenue dans BéDéditeur » s'ouvre par-dessus
- [x] Tourner les pages jusqu'à « Essayez sur une vraie planche », choisir « Parcours complet », aller au bout de la visite des pages : la carte « Par où commencer » liste les neuf étapes, numérotées, « Pré-remplir » marqué « facultatif » (ou « optionnel ici : moteur absent » si l'OCR manque)

### L'album de présentation, page par page, sous `arrivant`
- [x] « Par où commencer » (ligne du bac à sable, ou « ☰ » d'une étape) ouvre la carte → « Revoir la présentation » : l'album rouvre à sa page 1 « Interrogez le texte et l'image », cinq planches du jeu en éventail à gauche, le texte à droite, « 1 / 8 » en bas
- [x] Page 2 « Constituez votre corpus » : deux cadres, « Collection « Récits d'aventure » » (trois planches de comics) puis « Collection « Humour » » (*Moustache*, *Saint-Cyr*), sans titre sous les images ; le survol d'une image montre son titre
- [x] Page 3 « Repérez, segmentez, organisez » : une case de *Moustache* recadrée, quatre zones dessinées, chacune nommée près d'elle — « case 1 », « bulle 1 », « bulle 2 », « détail : la coccinelle »
- [x] Page 4 « Automatisez la reconnaissance » : au-dessus, « Trouvé automatiquement : 3 cases, 3 bulles, 2 cartouches » ; une rangée de *Moustache* et ses cadres ; dessous, quatre lectures, « Pas Trop tat » et « reconnail » surlignées et marquées « à corriger », une autre « ✓ corrigé » ; le texte dit que les moteurs « se trompent parfois, surtout sur un lettrage manuscrit », sans nommer la planche du parcours ni donner de chiffre
- [x] Page 5 « Analysez et annotez » : une bulle de *Moustache* recadrée, et « Votre vocabulaire » — Forme, Registre, Adresse —, « ✓ familier » seul coché
- [x] Page 6 « Travaillez à plusieurs » : trois membres, chacun avec son initiale et son rôle (« responsable du projet », « annote et exporte », « annote »), puis un doute sur « familier » que deux d'entre eux discutent
- [x] D'une page à l'autre (←, « Suivant → », les points du bas), la boîte garde sa hauteur : les boutons du bas ne sautent pas
- [x] Page 8 « Essayez sur une vraie planche » : « Parcours rapide » (4 gestes, 5 minutes) et « Parcours complet » (les 9 étapes, 15 minutes), et « Ne plus afficher »
- [x] « Aa » → thème sombre, pages 1 à 7 : les images, les cadres et leurs étiquettes se lisent
- [x] Page 7 « Recherchez, exportez et partagez » : « forêt », « 3 occurrences », trois lignes de concordance — une vignette, le mot encadré dessus et sa citation dessous, le contexte gauche, « forêt », le contexte droit —, puis « Vos données, aux formats de la recherche » : TEI, CSV, JSON-LD, IIIF
- [x] Page 1 : l'éventail est fait de cinq pages chevauchées en arc, aux teintes alternées — *Radar* (noir et blanc), *Lightning*, *Modern Comics* (couleur), *Moustache* (noir et blanc), *Saint-Cyr* (sépia)
- [x] « Suivant → » : la page qui arrive glisse de la droite ; ← : elle glisse de la gauche ; à l'ouverture de l'album, rien ne glisse
- [x] Page 8 : à gauche, un aperçu de la carte « Par où commencer » (ses neuf étapes, la première marquée) ; à droite, « 8 », le titre, le texte, puis deux cartes — « Parcours rapide » « 5 min », les pastilles 4 à 7, « tracer → annoter » ; « Parcours complet » « 15 min », 1 à 9, « corpus → exporter » —, chacune avec « Commencer → » ; « Ne plus afficher » dans la barre du bas, à droite (demande `1c860d3` ou après)

### La visite des pages, sous `arrivant`
- [x] Carte → « Revoir les pages » : « Visite 1 / 7 », « La barre du haut » ; la barre en clair, le reste assombri, six pastilles numérotées sur ses zones et six lignes dans la liste de la fenêtre
- [x] Survoler une ligne de la liste : sa zone reste seule en clair, cernée, les autres repassent sous l'assombri en gardant leur pastille ; quitter la liste : toutes reviennent en clair ; la fenêtre ne bouge pas
- [x] Survoler une zone de la page : sa ligne se surligne dans la liste ; au clavier, Tab sur une ligne fait ce que fait le survol
- [x] « Suivant → » : « Visite 2 / 7 · 1 / 2 », l'Atelier, la fenêtre à droite ; « Suivant → » : « 2 / 2 », la fenêtre passe à gauche, et sa première zone est d'emblée seule en clair
- [x] Au second temps de l'Atelier, la ligne « Traitement, Import / Export » dit « Lancer les moteurs, ajouter des planches. Sortir un album, hors d'un bac à sable. »
- [x] « Suivant → » jusqu'au bout : Annotation, Bibliothèque, Recherche, Exploration, Administration, chacune ouverte sur sa page ; la Recherche et l'Exploration disent que le bac à sable n'y paraît pas
- [x] « Visite 7 / 7 », « Commencer → » : le guide s'ouvre sur la première étape du parcours choisi, sur sa page (parcours complet : « Constituer le corpus », dans la Bibliothèque)
- [x] Pendant la visite de la barre du haut, cliquer « Annotation » dans la barre : rien ne change de page, la zone « Les six pages » est choisie (seule en clair, cernée), et la visite reste à « Visite 1 / 7 »
- [x] Toujours à « Visite 1 / 7 », cliquer « ? », puis « Par où commencer », puis « Remettre à neuf… » : aucun ne remplace ni ne ferme la visite ; chacun choisit sa zone
- [x] Choisir « Aa » dans la liste (clic ou Entrée) : son menu s'ouvre, en clair, et le focus reste sur la ligne ; changer le thème y marche ; choisir une autre ligne le referme ; le survol d'une ligne n'ouvre rien
- [x] « Visite 2 / 7 · 2 / 2 » (l'Atelier, second temps) : à l'arrivée, « Structure » ET « Traitement, Import / Export » sont en clair, aucune ligne pressée
- [x] Choisir « Traitement, Import / Export » : le menu « Traitement » s'ouvre ; ses entrées se lisent mais sont éteintes, l'infobulle dit « Le guide pas à pas vous le fera faire. », et un clic sur « OCR des bulles » ne lance rien
- [x] Au premier temps de l'Atelier, changer d'album dans la liste *Album* ; « Suivant → » : la planche de *Moustache* revient, « Visite 2 / 7 · 2 / 2 », et la Structure montre ses cases et ses bulles
- [x] Hors visite, les repères du « ? » de la page Annotation : « Ouvrir dans l'Atelier ↗ » ne quitte pas la page, il choisit sa zone ; Échap ferme les repères

### Le parcours complet, étape par étape, sous `arrivant`
- [x] Étape 1 « Constituer le corpus » : la Bibliothèque, seule la carte de l'album du parcours est éclairée, le reste assombri, et la fenêtre est posée à côté d'elle sans la recouvrir ; la tête de la fenêtre dit « 1 / 9 »
- [x] Ouvrir l'album du parcours (clic sur sa carte) : la fenêtre dit « ✓ Fait », et le bouton de droite passe de « Passer → » à « Suivant → »
- [x] Les gestes de la fenêtre se lisent dans cet ordre : « ✓ Fait » (quand l'étape l'est), ←, le geste principal poussé à droite, ☰, ✕
- [x] « Suivant → », étape 2 « Décrire l'album » : la tête de la fiche de l'album est éclairée et la fenêtre à côté d'elle ; « ✎ Modifier » dans la fiche : la notice est presque remplie (série, numéro 11, date 1959-04, type « périodique (mensuel) ») ; y écrire la langue « fr », enregistrer : « ✓ Fait » (la notice n'arrive que dans un bac à sable né ou remis à neuf après `7e20116`)
- [x] « Pré-remplir », désormais l'étape 6 (après « Transcrire et relire ») : l'Atelier s'ouvre sur la PLANCHE D'ESSAI (planche 2, sans zone), « Traitement » ET la planche sont éclairés, la fenêtre à côté ; ses trois entrées sont actives ; lancer « Segmenter les cases », « Détecter les bulles », puis « OCR des bulles » : les cadres et le texte apparaissent sur la planche d'essai ; « ✓ Fait » une fois l'OCR passé
- [x] Étape 4 « Tracer une zone » : la planche et sa barre sont éclairées, la fenêtre à côté ; « ✎ Tracer » est dans la barre du canevas. Tracer la case du milieu sur le fond, puis, dans elle, sa bulle (Maj + glisser, ou « ✎ Tracer ») : « ✓ Fait » ne vient qu'une fois les DEUX tracées, et le guide ne passe pas seul à l'étape suivante
- [x] Les deux tracées, la fenêtre dit « Une zone tracée se range en dernier : ↻, en tête de la structure, remet l'ordre de lecture. » ; un clic sur ↻ (Structure de la planche), puis la Transcription : la bulle de la case du milieu se cite `c2 · b1`, et plus `c3 · b1`
- [x] Étape 5 « Corriger le découpage » : en y entrant, la planche se rapproche d'une bulle, qui se voit EN ENTIER à côté de la fenêtre, jamais dessous ; la bulle et le panneau de droite sont éclairés
- [x] Agrandir cette bulle par une poignée (la poignée répond, même si elle dépasse un peu du trou) : « ✓ Fait » ; « Suivant → » : la planche revient entière
- [x] Étape 6 « Transcrire et relire » : le mode Transcription s'ouvre, sa colonne du texte est éclairée et la fenêtre à côté ; recopier le texte d'une bulle, Tab passe à la suivante ; « ✓ Fait » ne vient qu'une fois TOUTES les zones de texte de la planche transcrites (parcours complet)
- [x] Étape 7 « Annoter » : la page Annotation s'ouvre, la case agrandie et la grille sont éclairées, la fenêtre à côté et sans les recouvrir ; cliquer un mot puis une entrée de la grille : « ✓ Fait »
- [x] Étape 8 « Chercher et explorer » : la Recherche s'ouvre, sa barre de recherche et la phrase sur le bac à sable sont éclairées, la fenêtre à côté ; le bouton dit « Suivant → » sans geste à faire
- [x] Étape 9 « Exporter » : la fiche de l'album s'ouvre dans la Bibliothèque, la liste de ses actes est éclairée, la fenêtre à côté ; le bouton dit « Terminer »
- [x] Étape 9 « Exporter » : la fenêtre dit d'ABORD « Vos données sortent aux formats de la recherche : une collection en fiche, en enregistrements et en manifeste IIIF, un album en JSON, CSV ou TEI. », PUIS « Vous êtes dans votre bac à sable, une zone pour vous exercer : ici, seuls … peuvent être exportés… » en nommant les albums du jeu de la part du dépôt (sur la recette : *L'École de Saint-Cyr*, les deux *Comics*, *Bibi Fricotin*), jamais *Moustache et Trottinette*
- [x] À l'étape 9, dans « Vos droits ici » de la fiche de *Moustache et Trottinette*, « exporter » est éteint ; dans la Bibliothèque du bac à sable, la fiche de *L'École de Saint-Cyr* le montre allumé
- [x] « Terminer » : la fenêtre dit « Parcours terminé », et montre les autres planches du jeu en vignettes ; une vignette ouvre sa planche dans l'Atelier, sans guide

### La carte et le retour, sous `arrivant`
- [x] « Par où commencer » (ligne du bac à sable, ou « ☰ » d'une étape) : les étapes faites portent « ✓ » au lieu de leur numéro ; un lecteur d'écran y lit « (fait) »
- [x] Sous les étapes, la carte propose « Revoir la présentation » puis « Revoir les pages »
- [x] Pendant une étape, ✕ : la fenêtre se ferme en disant « « Par où commencer » le rouvre, à la même étape. » ; rouvrir la carte et reprendre : on revient à l'étape quittée
- [x] Pendant une étape, Échap fait ce que fait ✕
- [x] Pendant une étape, recharger la page (F5) : le guide reprend à la même étape, dans cet onglet ; un nouvel onglet où l'on TAPE l'adresse de l'Atelier ne rouvre pas le guide de lui-même ; « Par où commencer » l'y rouvre
- [x] « ☰ » ouvre la carte depuis la fenêtre ; ← revient à l'étape d'avant, et est éteint sur la première

### Le parcours rapide, sous `arrivant`
- [x] Carte, « Passer au parcours rapide » (ou le choix de parcours) : quatre étapes, « Tracer une zone », « Corriger le découpage », « Transcrire et relire », « Annoter », comptées « n / 4 »
- [x] « Transcrire et relire » y est faite dès qu'UNE zone de texte est transcrite

### Petits écrans et grande police, sous `arrivant`
- Abandonnée le 2026-11-06 (Hugo : à 200 %, inutile de tester) — Fenêtre à 768 px, « Aa » → la plus grande police (200 %), « Revoir les pages » jusqu'à la Recherche puis l'Exploration : la fenêtre de la visite est une feuille en bas, son texte défile dedans, rien ne défile de côté ; la feuille repliée sur une ligne, le message des résultats se lit en entier
- Abandonnée le 2026-11-06 (Hugo : à 200 %, inutile de tester) — Fenêtre à 768 px, plus grande police, rejouer « Constituer », « Tracer », « Corriger », « Transcrire » et « Annoter » (← et « Suivant → ») : à chacune, la fenêtre du guide est une feuille en bas et la page réserve sa hauteur ; replier la feuille sur une ligne dégage le foyer, qu'on atteint en entier en faisant défiler la page ; la rouvrir rend la consigne
- [x] Dans ces conditions, à « Constituer le corpus », la carte de l'album du parcours peut être amenée au-dessus de la feuille en faisant défiler la page jusqu'en bas
- Abandonnée le 2026-11-06 (Hugo : le guide vise un écran de bureau) — Fenêtre à 600 px de large : la fenêtre du guide est une feuille en bas, pleine largeur, et la page réserve sa hauteur (le bas de la planche n'est pas caché sous elle)
- [x] À « Tracer une zone », zoomer la planche à la main, puis changer la largeur de la fenêtre : noter si le zoom est perdu (la planche se réajuste quand la feuille réserve sa place, choix confirmé par Hugo le 2026-11-05)

### Clavier et lecteur d'écran, sous `arrivant`
- [x] Pendant une étape, Tab passe des zones jouables de l'étape aux gestes de la fenêtre et revient, sans s'arrêter sur ce qui est assombri et sans piège ; aucun `role="dialog"` modal n'enferme le focus
- [x] Quand une étape devient faite, un lecteur d'écran l'annonce une fois (« … : fait. »), sans répéter à chaque redessin
- [x] En thème clair puis sombre, le texte de la fenêtre, « ✓ Fait » et la marque « optionnel ici » se lisent sur l'assombri

### Le lot du 5 novembre au soir, sous `arrivant`, dans un bac à sable remis à neuf
- [x] « Remettre à neuf… », puis « Par où commencer » : la carte du parcours complet liste, dans cet ordre, « Constituer le corpus », « Décrire l'album », « Tracer une zone », « Corriger le découpage », « Transcrire et relire », « Pré-remplir », « Annoter », « Chercher et explorer », « Exporter » ; la page 8 de l'album montre le même ordre
- [x] « Tracer une zone » : en y entrant, la planche se rapproche seule de la dernière rangée, ses deux cases ET le vide du milieu entiers à côté de la fenêtre, jamais dessous ; ✕ : la planche revient entière
- [x] « Corriger le découpage » : en y entrant, la planche cadre la CASE de la bulle à corriger — la bulle, sa voisine et la case entières, la bulle choisie avec ses poignées — et non la bulle seule grossie
- [x] « Chercher et explorer » : la fenêtre dit d'abord à quoi servent la Recherche et l'Exploration (« La Recherche retrouve un mot… L'Exploration met le corpus en chiffres… »), puis que le bac à sable n'y paraît pas
- [x] « Terminer » : « Parcours terminé » s'ouvre au milieu de l'écran, de la taille de l'album, les autres planches du jeu en vignettes titrées, « Revoir la présentation » et « Fermer ✕ » ; une vignette ouvre sa planche dans l'Atelier, sans guide
- [x] Visite, page Recherche : la ligne « Facettes grammaticales » dit « Chercher par la grammaire : la catégorie d'un mot (verbe, nom…), son lemme (« aller » trouve « va » et « irons »), un trait (le temps, le nombre). », et la choisir ouvre le dépliant
- Abandonnée le 2026-11-06 (Hugo : à 200 %, inutile de tester) — Fenêtre d'environ 790 px, « Aa » → zoom à 200 %, parcours rapide jusqu'à « Transcrire et relire » : à chaque étape, la fenêtre du guide tient dans l'écran, en feuille en bas, jamais hors de l'écran ; repliée, elle ne garde qu'une ligne, et rien ne défile de côté
- [x] Mode Transcription, sur un grand écran : la bulle grandit jusqu'à remplir son cadre (au plus ×3), sans se déformer

### Les retouches du 6 novembre, sous `arrivant`, sur la recette reconstruite sur `43c0ce7`
Recette reconstruite sur `dev` le 2026-11-06 (`98c0e26`…`06d9d51`), état `apres-moustache` restauré et le jeu repréparé avec sa planche d'essai. Un bac à sable neuf (« Mon bac à sable »), « Par où commencer », parcours complet, fenêtre à 1 280 px sauf mention contraire.
- [x] « Tracer une zone », l'Atelier en Navigation : la barre des modes est éclairée, et la fenêtre dit « La Navigation déplace et agrandit la planche. Pour tracer, passez en mode Édition, dans la barre des modes. » ; la planche n'est pas encore éclairée
- [x] Toujours à « Tracer une zone », cliquer « Édition » dans la barre des modes : l'éclairage passe à la planche et à la structure, la dernière rangée est cadrée, la fenêtre redonne la consigne du tracé (« Glissez sur le fond pour tracer une case… »)
- [x] Toujours à « Tracer une zone », repasser en « Navigation » puis revenir en « Édition » : à chaque passage, la fenêtre et l'éclairage suivent sans recharger la page, et rien n'empêche de revenir en Navigation
- [x] Tracer la case, « Suivant → » jusqu'à « Corriger le découpage », passer en Navigation : la fenêtre dit « La Navigation déplace et agrandit la planche. Pour corriger le découpage, passez en mode Édition, dans la barre des modes. » ; en Édition, la case de la bulle à corriger est cadrée, la bulle avec ses poignées
- [x] « Transcrire et relire » (l'Atelier en Transcription), puis « Suivant → » jusqu'à « Pré-remplir » : l'Atelier passe de lui-même en mode Édition, sur la planche d'essai, visible et sans zone
- [x] À « Pré-remplir », la fenêtre dit « Précédemment, vous avez découpé et transcrit à la main. Voyons maintenant comment automatiser ce travail grâce aux moteurs embarqués. Cliquez sur « Traitement », et lancez dans l'ordre « Segmenter les cases », « Détecter les bulles », puis « OCR des bulles », et regardez ce que chacun produit. »
- [x] À « Pré-remplir », le bouton « Traitement » porte un cadre ambre épais, plus marqué que le reste éclairé, et il saute aux yeux sans qu'on le cherche ; ouvrir son menu efface le cadre, le refermer le rend, tant que l'OCR n'a pas été lancé
- [x] Même chose en thème clair (« Aa » → thème) : le cadre de « Traitement » se voit aussi nettement qu'en sombre
- [x] « Annoter », fenêtre à 1 440 px : la fenêtre du guide est posée à côté, son haut à la hauteur du bloc du texte (les mots), et non en face de la case agrandie ; elle ne couvre ni les mots ni la grille
- [x] « Annoter » : la fenêtre dit « Cliquez un mot du texte, sous l'image, puis une entrée de la grille : c'est le vocabulaire du projet. », et le texte est bien sous l'image
- [x] « Annoter », fenêtre à 1 280 px (la fenêtre devient une feuille en bas) : le bloc des mots remonte au-dessus de la feuille, les mots entiers visibles
