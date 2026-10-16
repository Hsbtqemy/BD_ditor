# Images, pages, surfaces — ce que la « planche » confond

> Note de conception ouverte le 2026-10-16 et approfondie le même jour avec Hugo : le modèle
> et ses quatorze questions sont tranchés (§ 5). Aucun code ; restent la maquette de
> l'Atelier et la place du chantier dans la file. Fiche : `pilotage/IMG-2.md`.

## 1. D'où vient la question

Deux situations, l'une réelle et l'autre de principe.

- **Les doubles pages.** Un étudiant de master va scanner des albums qui en comptent
  beaucoup, pour les annoter et produire son mémoire. Certaines s'annotent à la pliure — une
  case, une composition, à cheval sur les deux pages. Le scanner de l'équipe restitue bien la
  jonction, et sait rendre au choix un seul cadre étalé sur la double page ou deux cadres,
  page gauche et page droite.
- **Les supports qui ne sont pas des pages** : le webtoon (une bande verticale continue par
  épisode), le leporello et la frise, la toile infinie, le turbomédia. Une réflexion générale
  sur ce que l'outil est capable d'accueillir et d'annoter.

**Ce qui a tranché la manière de poser la question** (Hugo, 2026-10-16) : un seul cadre pour
une double page fait d'elle UNE planche, donc décale de un toutes les pages suivantes — les
numéros, et avec eux **les citations et les références** produites. Un correctif « cette
planche couvre deux pages » effacerait le décalage, mais ferait de la double page une
exception que tous les exports, toutes les citations et toutes les analyses par planche
devraient connaître pour toujours. Hugo ne veut pas traiter la chose au cas par cas : il veut
**le modèle le plus pertinent pour toutes les situations à venir**.

## 2. Le modèle proposé : trois notions au lieu d'une

Aujourd'hui une ligne de `planches` est trois choses à la fois.

| Notion | Ce que c'est | Ce qui en dépend |
|---|---|---|
| **Image** | un fichier, scanné ou récupéré | la résolution, le matériel (dpi, mode), le dérivé web |
| **Page** | une unité imprimée, numérotée | la numérotation, les citations, les références, récit ou paratexte |
| **Surface** | le repère où l'on annote | les régions et leurs coordonnées, l'ordre de lecture, les moteurs |

Pour une planche scannée ordinaire, les trois coïncident — c'est pourquoi le modèle a tenu
jusqu'ici. Séparées, chaque situation s'écrit sans exception :

| Situation | Images | Pages | Surface |
|---|---|---|---|
| Planche ordinaire (tout l'existant) | 1 | 1 | 1 |
| Double page, un seul cadre | 1 | 2, séparées par la pliure | 1 |
| Double page, deux cadres | 2, côte à côte | 2 | 1 |
| Webtoon | N tranches, empilées | aucune page imprimée | 1 par épisode |
| Leporello, frise | N, alignées | selon l'objet | 1 |
| Toile infinie | N, placées librement | — | 1 |
| Turbomédia | 1 par écran | — | 1 par écran |

**Ce que cela rend aux numéros et aux citations.** La numérotation compte des PAGES, jamais
des surfaces : plus aucun décalage, nulle part. Une région trouve sa page par sa position sur
la surface — une bulle de la page de droite se cite « 13 · … » ; une case réellement à cheval
se cite par la page où elle commence dans l'ordre de lecture, et son débordement se dit à côté
de la citation (§ 5, question 3). Les comptes par page restent justes, puisqu'une double page
est deux pages.

**Ce que cela rend à IIIF.** Une surface est un *Canvas* ; IIIF Presentation 3 permet d'y
peindre plusieurs images, chacune à sa place (`xywh`). C'est la forme native d'une double page
en deux cadres et d'un webtoon en tranches.

## 3. Ce qui ne change pas pour l'existant

La proposition qui rend la migration mécanique : **la table `planches` DEVIENT la surface**,
sans changer de nom ni de forme, et deux tables neuves s'y accrochent — ses images (chacune
avec sa position sur la surface) et ses pages (chacune avec son emprise). Toute planche
existante reçoit UNE image posée en (0, 0) et UNE page qui la couvre entière.

Pour une surface d'une seule image, pixels de surface = pixels du master : **les coordonnées
des régions ne bougent pas d'un pixel**, le journal reste vrai (ses `planche_id` désignent
une surface, ce qu'ils désignaient déjà), et rien ne change à l'écran tant qu'on n'assemble
rien. L'invariant « tout en pixels MASTER » de `CLAUDE.md` devient « tout en pixels de
SURFACE », qui lui est identique sur tout l'existant.

## 4. Ce que l'inventaire du code a trouvé (2026-10-16)

Un inventaire en lecture seule a relevé chaque endroit qui s'appuie sur l'une des trois
facettes. L'essentiel :

- **Image et surface sont les plus entremêlées.** Les coordonnées n'ont de sens que dans les
  pixels d'UN master, et toute la chaîne en dépend : `largeur_px`/`hauteur_px` servent de
  `viewBox` à l'Atelier et à la Recherche, de `@lrx/@lry` à la TEI, de dimensions au Canvas
  IIIF ; `webScale = naturalWidth / largeur_px` suppose un seul dérivé.
- **Page et image sont liées par un seul fil, mais structurant** : les fichiers master et
  dérivé sont nommés d'après `numero`, l'ordre d'import (`pipeline/ingest.py`) — d'où
  `_allouer_numero`, qui alloue le numéro avant d'écrire le fichier.
- **Environ 60 % des sites sont mécaniques** : une quarantaine de jointures région → album
  pour la portée, dans une quinzaine de fichiers ; `numeros_editoriaux` et ses consommateurs
  (exports, recherche, concordance, écrans), qui ne lisent que `id`, `role` et `numero` ; les
  colonnes de matériel et de chemin, qui iraient à l'image ; les outils de dérivés.
- **Ce qui est délicat** :
  - **la découpe d'une région qui traverse deux images** — `region_crop_png`, `ocr_planche`
    et leur cache supposent un fichier par planche ;
  - **les moteurs** (Kumiko, bulles, OCR) : un fichier en entrée, des régions sur la même clé
    en sortie, ramenées au master par un seul facteur d'échelle ;
  - **IIIF et TEI** : l'identifiant de Canvas `canvas/p{planche_id}` doit rester stable, et
    la taille de l'image peinte est aujourd'hui CALCULÉE par `WEB_SCALE`, non lue ;
  - **la citation** : le rang d'une case se compte par `planche_id` (la surface) mais se
    numérote par page — `citations_regions` change de nature ;
  - **les statuts** : `statut`, `relecture` et le verrou décrivent le travail sur des régions,
    donc une surface ; `validee` est ambigu, et compte aussi comme « travail d'un autre »
    dans la règle de suppression de COL-3 ;
  - **le cliquet des colonnes exportables** obligera à classer chaque colonne neuve, et c'est
    voulu.
- **Des incohérences qui existent déjà**, à régler en passant : l'Atelier affiche l'ordre
  d'import (`numero`) dans l'arbre, le fil d'Ariane et la navigation de transcription, mais le
  numéro éditorial dans la liste ; l'Exploration affiche l'ordre d'import sous l'étiquette
  « pl. » quand la citation manque ; `nombre_pages` compte des planches ; `dimensions_cm`
  présente la taille d'un scan comme la taille d'une page.

Ordre de grandeur : une vingtaine de fichiers par facette, une centaine de fonctions en tout,
dont la moitié de simples jointures. Un chantier de fond, de la taille d'une tranche de COL-3.

## 5. Les questions, et ce qui a été tranché

Les quatorze questions sont **tranchées par Hugo le 2026-10-16**. Ce qui reste avant de
cadrer le code : la maquette de l'Atelier sur une surface de plusieurs images (une double
page en deux cadres, un épisode de webtoon), et la place du chantier dans la file.

1. **Une page appartient à une seule surface — tranché : oui.** Une surface porte une ou
   plusieurs pages ; une page n'est jamais partagée entre deux surfaces, sans quoi elle aurait
   deux repères et une région ne saurait plus où elle vit.
2. **L'emprise d'une page est un rectangle, en pixels de la surface — tranché.** Deux cadres
   sont RECOMMANDÉS à la numérisation : chaque rectangle est alors l'emprise de son image, il
   n'y a rien à poser. Un cadre unique reste ACCEPTÉ — un fichier d'éditeur, un PDF arrivent
   souvent ainsi — et l'on y pose une fois la ligne de pliure, qui coupe la surface en deux
   rectangles.
3. **Une région à cheval sur deux pages se cite par la page où elle COMMENCE dans l'ordre de
   lecture, et compte pour elle seule — tranché.** « 12 · c5 », pas « 12-13 · c5 » : une
   troisième forme de citation que tous les exports et les outils qui les lisent devraient
   reconnaître. « Où elle commence » et non « la page de gauche » : un manga commence à
   droite (question 14). Elle compte pour cette page seule dans les analyses par page, pour
   que la somme des pages fasse l'album. Ce qu'on perd — la chercher sous la page 13, livre
   ouvert — se compense À CÔTÉ de la citation : l'Atelier montre qu'elle déborde, et les
   exports portent « s'étend jusqu'à la page 13 ».
4. **Le rang d'une case se compte par PAGE — tranché.** Une case de la page 13 reste
   « 13 · c2 » qu'on ait assemblé la double page ou non : l'assemblage ne renumérote rien, et
   une citation écrite dans un mémoire reste vraie. Par surface, chaque assemblage aurait
   décalé les numéros de case de la page de droite.
5. **Les statuts vont à la SURFACE — tranché.** Le statut du pipeline, la relecture et le
   verrou décrivent un travail sur des régions ou le passage d'un moteur ; la validation les
   suit, pour rester simple : une double page se valide d'un bloc. Sur une page ordinaire,
   surface et page coïncident, et rien ne change.
6. **Les moteurs travaillent sur la SURFACE — tranché.** Une image de la surface entière se
   compose à la volée, en cache, et la segmentation, les bulles et l'OCR la lisent comme un
   scan aujourd'hui : Kumiko voit toute la double page, et la découpe d'une case à cheval
   traverse les deux images sans code à part. Pour une surface d'une seule image, l'image
   composée EST le scan.
7. **Les fichiers neufs se nomment d'après l'identifiant de l'IMAGE — tranché.** Les fichiers
   existants gardent leur nom, sans renommage sur le disque ; le numéro d'une page ne décide
   plus rien sur le disque.
8. **IIIF et TEI — tranché.** IIIF : un Canvas par surface, à l'identifiant d'aujourd'hui,
   une image peinte par image à sa place (`xywh`), et les pages en *Ranges* dans
   `structures`, chacune avec son numéro et sa portion du Canvas. TEI : une `<surface>` par
   surface, chaque page en `<zone type="page">` avec son numéro. Pour une page ordinaire, les
   deux exports restent ceux d'aujourd'hui, une *Range* par page en plus — que les
   visionneuses IIIF lisent comme une table des matières.
9. **Le journal — tranché.** Ses `planche_id` historiques désignent des surfaces, ce qu'ils
   désignaient déjà, et cela reste vrai. Les actes neufs — assembler, poser une pliure — se
   journalisent sous la planche ; ce sont des gestes d'ORGANISATION et non d'annotation :
   Ctrl+Z ne les annule pas, un geste inverse explicite (« désassembler ») les défait.
10. **Assembler après coup — tranché.** Dans la Bibliothèque, sur deux planches consécutives
    du même album : celle qui commence la lecture (la gauche, ou la droite pour un manga)
    garde son identifiant et DEVIENT la surface ; les régions de l'autre y passent, décalées
    de la largeur de la première — un calcul exact ; l'autre cesse d'être une planche, son
    image et sa page restent. Réunir les deux moitiés d'une case coupée en attendant est un
    geste à la main, « fusionner deux régions ». Le prix : si l'album a déjà été publié en
    IIIF, le Canvas de la page absorbée quitte le manifeste — d'où la règle **assembler
    avant de publier**, que l'écran rappelle sur un album déjà exporté. C'est ce geste qui
    permet de commencer à annoter AVANT que le modèle existe.
11. **Le webtoon — tranché : rien maintenant**, on le traite quand un corpus réel arrive. Ce
    qui est déjà posé : un épisode est une surface SANS page, cité « ép. 3 · c12 » ; le
    dérivé web se réduira vers une LARGEUR MINIMALE à garder et non d'un facteur fixe — un
    épisode fait ~800 px de large, et le dérivé à 25 % en ferait 200 ; la règle vaut pour
    toute petite image, pas pour le seul webtoon. Un Atelier qui défile verticalement reste à
    dessiner ; la segmentation automatique sur un webtoon reste une HYPOTHÈSE à éprouver.
12. **La cible « planche » d'ANN-7 est la SURFACE — tranché.** Annoter « la planche »
    (composition, mise en page), c'est annoter ce qu'on voit d'un tenant : pour une double
    page, la double page entière, que l'écran nomme « la planche (ou la double page) ». Une
    cible « page » viendra si une grille en a besoin.
13. **Les métadonnées — tranché.** `nombre_pages` compte des pages. Les dimensions physiques
    se calculent PAR PAGE, de son emprise et de la résolution de son image : une double page
    d'un seul cadre donne à chaque page sa taille, pas la largeur des deux.
14. **Le sens de lecture est une propriété de l'ALBUM — tranché, 2026-10-16.** Trois
    valeurs : de gauche à droite (la BD franco-belge, par défaut), de droite à gauche (le
    manga), de haut en bas (le webtoon). Il se choisit à la création, dans « + Nouvel
    album », et se change dans la fiche de l'album ; sur un album déjà segmenté, le changer
    recalcule l'ordre de lecture de ses planches, ce qui efface les réordonnancements faits à
    la main — l'écran le dit et le fait confirmer, et sur un album vierge ne demande rien.
    Il sert l'ordre des cases et des bulles, la page où commence une case à cheval (question
    3), et l'ordre des deux images d'une double page. Aujourd'hui `pipeline/ordering.py` est
    écrit pour le seul sens occidental (rangées haut → bas, puis gauche → droite), et le dit
    en tête : sur un manga, tous les rangs de case d'une rangée — donc les citations — et
    l'ordre de transcription seraient faux. Le manga n'a en revanche rien à numéroter à
    l'envers : on le numérise dans l'ordre de lecture, et la première page lue devient la
    page 1. Le sens de lecture ne dépend pas du découpage image / page / surface : c'est un
    petit chantier qui peut le précéder. Un album qui mêlerait les deux sens (une
    anthologie) ne se traite pas sans un exemple réel. L'OCR, réglé pour le français, lit un
    manga traduit, pas un manga en japonais.

## 6. En attendant le modèle

Conseil donné le 2026-10-16 pour les doubles pages : **scanner en deux cadres**, page gauche
et page droite. La frontière entre les pages reste celle que donne le scanner ; l'outil les
accepte aujourd'hui comme deux planches, la numérotation est juste, et l'annotation peut
commencer. Les cases à cheval se coupent en deux en attendant (question 10). Un seul cadre,
lui, ferait de la double page une planche, avec le décalage de numéros qui a motivé cette
note — et revenir en arrière demanderait de rescanner.
