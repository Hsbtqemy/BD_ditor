---
chantier: IMG-2
statut: à venir
---

# IMG-2 — images, pages, surfaces : ce que l'outil accueille au-delà de la planche

**Point de départ** — 2026-10-16 : une note de conception, `docs/images-pages-surfaces.md`,
ouverte sur la demande de Hugo (« le modèle le plus pertinent pour toutes les situations à
venir »), un inventaire du code, puis le modèle et ses quatorze questions tranchés avec lui
le même jour. Aucun code. Restent la maquette de l'Atelier et la place du chantier dans la
file.

**2026-10-21 — la pratique de numérisation est tranchée, avant le code.** Rien n'est encore
scanné en double page : l'équipe attendait de savoir ce que l'outil en ferait pour choisir
comment scanner. Hugo retient **une page par image**, y compris pour l'avenir : une double page
se scanne en deux fichiers, chacun une planche dès aujourd'hui, réunis ensuite par le geste
d'assemblage. La pliure lui importe peu ; le vrai souci est de **caler** les deux pages l'une
contre l'autre, qui peuvent présenter un léger décalage de hauteur — d'où la case « Les deux
pages se calent l'une contre l'autre », zone des doubles pages. « Couper une double page en
un seul cadre » perd donc son usage premier, sans être retiré : un fonds déjà scanné ainsi
peut encore se présenter.

## Reste

### Le modèle — à approfondir avant tout code

- [x] **Les trois notions sont confirmées ou écartées** — attendu : Hugo a tranché, sur la note, que la planche se sépare en IMAGE (un fichier), PAGE (une unité imprimée, numérotée, citée) et SURFACE (le repère où vivent les régions) ; ou il a dit pourquoi non **Confirmées par Hugo le 2026-10-16**, en tranchant les quatorze questions qui les supposent
- [x] **La planche DEVIENT la surface** — attendu : confirmé ou écarté. La proposition qui rend la migration mécanique : `planches` garde son nom et sa forme, chaque planche existante reçoit une image en (0, 0) et une page qui la couvre entière ; aucune coordonnée de région ne bouge, et le journal reste vrai **Confirmé le 2026-10-16** (question 10 : à l'assemblage, la planche qui commence la lecture garde son identifiant et devient la surface)
- [x] **Les quatorze questions de la note ont leur réponse** — attendu : chacune tranchée ou renvoyée par écrit dans `docs/images-pages-surfaces.md` § 5 (une page sur une seule surface ; l'emprise d'une page ; une région à cheval, sa citation et son compte ; le rang de case par page ou par surface ; les statuts ; les moteurs par image ou par surface ; les fichiers nommés d'après l'image ; IIIF et TEI ; le journal ; assembler après coup ; le webtoon ; la cible « planche » d'ANN-7 ; les métadonnées ; le sens de lecture) **Toutes tranchées par Hugo le 2026-10-16** — une page sur une seule surface ; l'emprise d'une page est un rectangle, deux cadres recommandés et un cadre unique accepté avec sa ligne de pliure ; une case à cheval se cite par la page où elle commence dans l'ordre de lecture et compte pour elle seule ; le rang de case se compte par page ; le sens de lecture est une propriété de l'album ; les statuts, les moteurs (sur une image composée de la surface), les fichiers neufs nommés d'après l'image, IIIF et TEI (Canvas et `<surface>` par surface, les pages en Ranges et en zones) ; le journal (organiser n'est pas annoter : Ctrl+Z ne défait pas un assemblage) ; assembler AVANT de publier ; le webtoon attend un corpus réel ; la cible « planche » d'ANN-7 est la surface ; les dimensions physiques se calculent par page
- [ ] **La forme de l'Atelier sur une surface de plusieurs images se tranche sur une maquette interactive** — attendu : Hugo a manipulé une double page en deux cadres et un épisode de webtoon, en session dédiée, et dit ce qu'il garde
- [ ] **L'ordre face aux autres chantiers est décidé** — attendu : la place d'IMG-2 face à l'Administration à l'échelle et à la tranche 3 de `COL-3`, et à `ANN-7`, écrite avec sa raison

### Ce que le modèle ne doit pas casser

- [x] **ANN-7 ne fige pas la cible « planche » avant ce modèle** — attendu : la tranche 1 des grilles d'annotation dit si « la planche » est la page ou la surface, ou attend que cette fiche le tranche. Une grille annote des régions, et les régions changeraient de repère **Tranché par Hugo le 2026-10-16 : la cible « planche » est la SURFACE** — ce qu'on voit d'un tenant, la double page entière ; une cible « page » viendra si une grille en a besoin (question 12 de la note)
- [ ] **Les citations déjà produites restent lisibles** — attendu : une citation d'une planche ordinaire est identique avant et après le modèle, mesuré sur les exports JSON, CSV, TEI, IIIF et la figure citable
- [ ] **La migration se vérifie sur une vraie base de la version précédente** — attendu : fabriquée par `tools/fabriquer_base_de_version.py` sur la tête de `main` d'avant la migration (règle de Hugo du 2026-10-16), dans le test de la migration

### Les doubles pages — le premier usage

- [ ] **Les doubles pages scannées en deux cadres s'assemblent sans ressaisie** — attendu : un geste réunit deux planches consécutives en une surface ; les régions de la page de droite sont décalées de la largeur de la gauche ; la numérotation et les citations sont celles d'avant l'assemblage
- [ ] **Les deux pages se calent l'une contre l'autre** — attendu : à l'assemblage, la page de droite se déplace au pixel près, au moins en hauteur, jusqu'à ce que les deux pages se raccordent à l'œil ; le calage est la POSITION de l'image sur la surface, jamais une retouche du master (les coordonnées restent en pixels master) ; les régions de la page de droite suivent le même déplacement, et le calage se reprend plus tard sans rien ressaisir. Dit par Hugo le 2026-10-21 : c'est LE souci de l'assemblage, plus que la pliure. Une légère rotation ou une différence d'échelle entre les deux scans se tranche sur la maquette
- [ ] **Une case à cheval sur la pliure est UNE région, et se cite par la page où elle commence** — attendu : tracée sur la surface, elle se cite « 12 · c5 » (ou « 13 · … » pour un manga, qui commence à droite), compte pour cette page seule, et son débordement se lit à côté de la citation — dans l'Atelier, et dans les exports (« s'étend jusqu'à la page 13 ») ; elle se découpe pour la figure et l'OCR à travers les deux images
- [ ] **Une double page en un seul cadre se coupe en deux pages** — attendu : la ligne de pliure posée, la numérotation compte deux pages

### Le sens de lecture — peut précéder le reste

- [ ] **Un album a un sens de lecture, choisi à sa création** — attendu : dans « + Nouvel album », trois valeurs — de gauche à droite (par défaut), de droite à gauche (manga), de haut en bas (webtoon) ; modifiable dans la fiche de l'album. Tranché par Hugo le 2026-10-16
- [ ] **L'ordre de lecture des cases et des bulles suit le sens de l'album** — attendu : sur une planche de manga segmentée, la case du haut à DROITE est « c1 », et la transcription bulle à bulle suit le même sens. Aujourd'hui `pipeline/ordering.py` ne connaît que le sens occidental, et le dit en tête
- [ ] **Changer le sens d'un album déjà segmenté se fait confirmer** — attendu : l'écran dit combien de planches seront recalculées, et que les réordonnancements faits à la main seront perdus ; sur un album vierge, rien n'est demandé

### Les supports continus — une réflexion, pas un engagement

- [ ] **Le webtoon a sa réponse écrite** — attendu : dans la note, ce que demandent un dérivé non réduit, une lecture qui défile, une citation sans page ; et si on l'accueille, quand
- [ ] **La segmentation automatique est ÉPROUVÉE sur un épisode de webtoon** — attendu : Kumiko sur une bande verticale réelle, ce qu'il trouve et ce qu'il manque ; jusque-là, « il devrait bien couper » reste une hypothèse

## Contexte

**Ouvert le 2026-10-16**, pendant la mise en production de la tranche 2 de `COL-3`, à partir
d'une discussion de Hugo avec un futur utilisateur : un étudiant de master qui va scanner des
albums riches en doubles pages, pour les annoter et produire son mémoire. Pas de question de
droits dans ce cas-là ; certaines doubles pages s'annotent à la pliure ; le scanner de
l'équipe restitue bien la jonction, et rend au choix un cadre étalé ou deux cadres.

**Le chemin de la discussion**, pour ne pas le refaire. Première proposition : un seul scan
par double page, et un correctif « cette planche couvre deux pages » pour la numérotation —
écarté par Hugo : le décalage des numéros, donc des citations et des références, ferait de la
double page une exception perpétuelle. Deuxième : deux cadres, et la double page comme une
VUE, avec un lien « même case » pour une case coupée à la pliure — meilleure, mais encore
pensée pour un seul cas. Hugo ne veut pas traiter les situations au cas par cas, d'où la
troisième, celle de la note : séparer image, page et surface, dont les deux premières ne sont
que des cas particuliers.

**Conseil donné en attendant** : scanner en deux cadres. L'outil les accepte dès aujourd'hui
comme deux planches, la numérotation est juste, l'annotation peut commencer, et l'assemblage
viendra sans ressaisie.

**Les webtoons et la continuité** sont une réflexion générale de Hugo sur ce que l'outil peut
accueillir, sans corpus derrière elle aujourd'hui. Ce qui la rouvrirait : un corpus réel.

**La récupération depuis les applications** a été écartée de cette fiche : c'est une
question de base légale (exception de fouille pour la recherche, accès licite, mesures
techniques de protection), qui relève du dossier de `DEPOT-1`, pas du modèle.

**L'inventaire du code** (lecture seule, 2026-10-16) est résumé dans la note, § 4.
