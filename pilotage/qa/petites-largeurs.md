---
passe: Petites largeurs — ce que la mesure ne dit pas
chantier: UX-7
duree: 45 min
derniere: 2026-09-05
---

# QA — le repli tient-il à l'usage, et pas seulement au rectangle

UX-7 est livré avec vingt tests neufs, et ils mesurent tous la même chose : le contenu
est-il ATTEIGNABLE. C'est ce que demande le 1.4.10, et ils le demandent bien. Mais la
fiche elle-même a écrit, le 2026-09-05, que **« rien ne dépasse » n'est pas
« utilisable »** — et cette phrase reste vraie après le chantier. Un canevas qu'on atteint
peut être un canevas dans lequel on ne travaille pas.

Cette passe pose donc les questions qu'aucun `getBoundingClientRect` ne pose. Elle ne
rejoue pas les tests : ce qu'ils couvrent est écrit ci-dessous, en toutes lettres, pour
qu'on ne le refasse pas à la main.

**Elle exige un vrai appareil, et il doit être NOMMÉ.** L'émulation de Chromium donne la
géométrie et ment sur tout le reste : la taille réelle d'un doigt, la latence du défilement
inertiel, le clavier logiciel qui mange la moitié de l'écran, la barre d'URL qui apparaît
et disparaît en changeant la hauteur utile. « Ça marche sur tablette » sans machine
désignée est une affirmation invérifiable — c'est déjà la discipline qu'UX-8 s'impose.

**Où reportent les constats.** UX-7 est clos et son `Reste` est vide : un défaut trouvé ici
ne s'y recoche pas. Ce qui relève du GESTE (cible trop petite, pincement, poignée) part
dans `UX-8`. Ce qui condamne un SEUIL ou un repli rouvre une fiche à part, avec la largeur
et l'appareil en tête. Et si la passe se dément elle-même sur un point — c'est arrivé le
2026-09-04 sur le collage vertical —, c'est ce démenti qui compte, pas la case.

## Ce que les tests couvrent déjà — ne pas le refaire ici

- `test_e2e_reflow.py` : à 320 et 768 px, sur les quatre surfaces, aucun élément n'est hors
  champ sans cadre défilant ni bascule qui le ramène. Plus la démonstration que la garde
  naïve sur `scrollWidth` aurait été vacante, et les deux contrôles de l'exemption.
- `test_e2e_tiroirs.py` : le focus ne sort pas d'un tiroir ouvert, dans les deux sens et
  sur les deux tiroirs ; Échap referme et rend le focus à la bascule ; le piège se désarme
  quand la fenêtre s'élargit.
- `test_e2e_a11y.py` : aucune violation axe sérieuse ou critique — **à la largeur par
  défaut seulement**. C'est le trou que la zone *Ce qu'axe ne regarde pas* vient combler.
- `tools/mesurer_reflow.py` : sept largeurs balayées à la demande, pour explorer.

## Reste

### L'appareil

- [ ] La machine est nommée dans cette section avant de commencer : modèle, taille d'écran en pouces, résolution logique, navigateur et version — une passe rejouée sur une autre machine ne dit rien de la précédente
- [ ] La passe est jouée en PORTRAIT et en PAYSAGE, et les deux orientations sont notées séparément ; sur téléphone le paysage laisse moins de 400 px de hauteur, ce qu'aucune de nos mesures n'a regardé
- [ ] Le zoom du navigateur est à 100 % et la taille de police du système est celle par défaut — les modifier mesurerait A11Y-2, pas cette passe

### Le repli s'explique tout seul

- [ ] Sur la Visionneuse en largeur de téléphone, quelqu'un qui n'a pas construit l'outil trouve comment afficher la liste des planches, sans qu'on lui dise que ☰ existe
- [ ] Il trouve de même le panneau d'annotation (▤), et sait dire à quoi sert chacune des deux icônes après les avoir ouvertes une fois
- [ ] Refermer un tiroir se devine : la personne essaie au moins un des trois gestes prévus (retoucher la bascule, toucher hors du tiroir, Échap) sans qu'on l'oriente
- [ ] Un tiroir ouvert ne laisse pas croire que l'application est bloquée : le voile assombrit sans faire disparaître le canevas

### Annoter, et pas seulement consulter

L'arbitrage du 2026-09-05 a tranché « annotation tactile » : la Visionneuse n'est pas une
surface de consultation qu'on rendrait lisible faute de mieux. Ces cases jugent ce choix,
et peuvent le condamner.

- [ ] Sur la tablette nommée, les deux tiroirs fermés, une planche entière tient à l'écran et ses bulles se distinguent les unes des autres sans zoomer
- [ ] Sélectionner une bulle existante au doigt réussit du premier coup, trois fois de suite, sur trois bulles de tailles différentes
- [ ] Ouvrir le panneau d'annotation, saisir une note et la valider se fait sans que le clavier logiciel masque le champ qu'on remplit
- [ ] Après avoir refermé le panneau, la sélection est toujours la même — ouvrir un tiroir ne perd pas le travail en cours
- [ ] Le va-et-vient « je sélectionne une bulle, j'ouvre le panneau, j'annote, je referme, je passe à la suivante » s'enchaîne dix fois sans qu'on ait envie d'aller chercher une souris

### Ce qui a été retiré sous les seuils

Trois éléments disparaissent en petite largeur. Chacun a été retiré pour une raison
mesurée ; reste à savoir si son absence se paie.

- [ ] Le **fil d'Ariane** est masqué sous 659 px. Il servait aussi à DÉSÉLECTIONNER : vérifier qu'on sort d'une sélection sans lui, au doigt, sans clavier — la racine de l'arbre de structure est la voie prévue
- [ ] La **légende de la barre d'état** est masquée sous 659 px : vérifier qu'on distingue toujours une case d'une bulle d'un personnage à leurs seules couleurs de contour
- [ ] Les **libellés des modes** tombent sous 899 px, ne laissant que les lettres N/E/A/T : vérifier qu'on sait dans quel mode on est sans avoir à essayer, et qu'on retrouve celui qu'on veut

### Les cadres de défilement se laissent trouver

Quatre zones défilent maintenant dans leur propre cadre. Les tests prouvent qu'on PEUT y
accéder ; ils ne disent rien de savoir qu'on le peut.

- [ ] Le tableau du corpus (Bibliothèque) : on comprend qu'il se prolonge à droite sans avoir à le deviner en tâtonnant
- [ ] Le **tableau de croisement** défile maintenant dans un cadre borné à 70vh : sur un croisement d'au moins 40 lignes, les en-têtes de colonnes restent visibles pendant le défilement, et la molette ne donne pas l'impression de se battre entre deux barres
- [ ] Sur ce même croisement, atteindre la dernière colonne ET la dernière ligne se fait sans jamais perdre de vue à quelle ligne on est — le collage des deux axes tient ensemble
- [ ] Le tableau des panneaux 🎯 Accord et 👥 Inter déborde de 38 px à 320 px : vérifier sur un corpus AYANT des tokens relus que ce débordement se voit et se franchit, et qu'il ne fait pas défiler le titre de la modale avec lui

### Ce que la mesure a déclaré conforme sans le juger

- [ ] La vignette d'un résultat de recherche tombe à 72 px sur un téléphone : vérifier qu'elle sert encore à reconnaître une planche, ou qu'elle est devenue une décoration qu'il vaudrait mieux masquer
- [ ] À 320 px, un résultat de recherche laisse 174 px au texte : lire trois résultats de suite et dire si l'extrait reste exploitable ou s'il faut ouvrir la planche à chaque fois
- [ ] La barre d'état passe à deux lignes sous 659 px : vérifier qu'elle ne mange pas une part inacceptable de la hauteur sur un téléphone en paysage

### Ce qu'axe ne regarde pas

L'audit automatique tourne à la largeur par défaut. Ces cases couvrent, à la main, ce
qu'il ne voit pas en petite largeur — elles sont la contrepartie de la limite écrite dans
la fiche UX-7.

- [ ] Au clavier (clavier externe sur la tablette), le focus est VISIBLE à chaque arrêt en largeur de téléphone : aucun contour n'est coupé par un bord, masqué par une barre collante, ni posé sur un élément hors champ
- [ ] Le lien d'évitement apparaît au premier Tab et son cadre entier est visible — mesuré à `[8, 0, 121, 34]` en émulation, à confirmer sur l'appareil
- [ ] Aucun texte ne devient illisible par contraste une fois la police réduite par le repli — en particulier les lettres de mode et les libellés de la barre d'état
- [ ] Aucune cible n'en recouvre une autre partiellement : deux boutons voisins se touchent sans se chevaucher, ce qui est le mode d'échec qu'on obtient en resserrant une barre

### Ce que la passe ne peut pas juger

À laisser cochées vides et à écrire en clair si l'on constate quelque chose — ce sont les
angles morts CONNUS de cette passe, pas des vérifications.

- [ ] Le pincement, le glissement à deux doigts et la taille des cibles relèvent d'`UX-8` et ne se jugent pas ici : les rencontrer est normal, les traiter serait déborder
- [ ] Cette passe ne dit rien du 1.4.4 (zoom à 200 %), qui est le voisin d'`A11Y-2` : agrandir le texte à largeur constante est un autre critère, et le confondre avec celui-ci fausserait les deux
