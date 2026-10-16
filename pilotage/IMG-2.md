---
chantier: IMG-2
statut: à venir
---

# IMG-2 — images, pages, surfaces : ce que l'outil accueille au-delà de la planche

**Point de départ** — 2026-10-16 : une note de conception, `docs/images-pages-surfaces.md`,
ouverte sur la demande de Hugo (« le modèle le plus pertinent pour toutes les situations à
venir »), et un inventaire du code. Aucun code. À approfondir avec Hugo avant de cadrer.

## Reste

### Le modèle — à approfondir avant tout code

- [ ] **Les trois notions sont confirmées ou écartées** — attendu : Hugo a tranché, sur la note, que la planche se sépare en IMAGE (un fichier), PAGE (une unité imprimée, numérotée, citée) et SURFACE (le repère où vivent les régions) ; ou il a dit pourquoi non
- [ ] **La planche DEVIENT la surface** — attendu : confirmé ou écarté. La proposition qui rend la migration mécanique : `planches` garde son nom et sa forme, chaque planche existante reçoit une image en (0, 0) et une page qui la couvre entière ; aucune coordonnée de région ne bouge, et le journal reste vrai
- [ ] **Les treize questions de la note ont leur réponse** — attendu : chacune tranchée ou renvoyée par écrit dans `docs/images-pages-surfaces.md` § 5 (une page sur une seule surface ; l'emprise d'une page ; une région à cheval, sa citation et son compte ; le rang de case par page ou par surface ; les statuts ; les moteurs par image ou par surface ; les fichiers nommés d'après l'image ; IIIF et TEI ; le journal ; assembler après coup ; le webtoon ; la cible « planche » d'ANN-7 ; les métadonnées)
- [ ] **La forme de l'Atelier sur une surface de plusieurs images se tranche sur une maquette interactive** — attendu : Hugo a manipulé une double page en deux cadres et un épisode de webtoon, en session dédiée, et dit ce qu'il garde
- [ ] **L'ordre face aux autres chantiers est décidé** — attendu : la place d'IMG-2 face à l'Administration à l'échelle et à la tranche 3 de `COL-3`, et à `ANN-7`, écrite avec sa raison

### Ce que le modèle ne doit pas casser

- [ ] **ANN-7 ne fige pas la cible « planche » avant ce modèle** — attendu : la tranche 1 des grilles d'annotation dit si « la planche » est la page ou la surface, ou attend que cette fiche le tranche. Une grille annote des régions, et les régions changeraient de repère
- [ ] **Les citations déjà produites restent lisibles** — attendu : une citation d'une planche ordinaire est identique avant et après le modèle, mesuré sur les exports JSON, CSV, TEI, IIIF et la figure citable
- [ ] **La migration se vérifie sur une vraie base de la version précédente** — attendu : fabriquée par `tools/fabriquer_base_de_version.py` sur la tête de `main` d'avant la migration (règle de Hugo du 2026-10-16), dans le test de la migration

### Les doubles pages — le premier usage

- [ ] **Les doubles pages scannées en deux cadres s'assemblent sans ressaisie** — attendu : un geste réunit deux planches consécutives en une surface ; les régions de la page de droite sont décalées de la largeur de la gauche ; la numérotation et les citations sont celles d'avant l'assemblage
- [ ] **Une case à cheval sur la pliure est UNE région, et se cite « 12-13 · c… »** — attendu : tracée sur la surface, elle se découpe pour la figure et l'OCR à travers les deux images
- [ ] **Une double page en un seul cadre se coupe en deux pages** — attendu : la ligne de pliure posée, la numérotation compte deux pages

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
