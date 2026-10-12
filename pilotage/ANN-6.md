---
chantier: ANN-6
statut: à venir
---

# ANN-6 — le relevé : annoter des mots et des passages, pas seulement des bulles

**Point de départ** — 2026-10-12. Hugo rapporte cinq retours d'usage de la production, puis
transmet la grille d'annotation des linguistes (extrait d'un guide, treize pages : sept
niveaux et un tag transversal « doute »). Lue contre l'outil, elle demande ce qu'il n'a pas :
poser un phénomène sur des MOTS précis d'une zone, plusieurs fois par zone, et compter des
occurrences. Rien n'est codé, rien n'est maquetté ; cette fiche garde la discussion et ce
qu'elle laisse à trancher. Les stagiaires doivent commencer à annoter « dans les prochaines
semaines » (Hugo, le même jour).

## Reste

### À confirmer avec les linguistes

- [ ] **On compte des OCCURRENCES, pas des bulles** — attendu : confirmé par les linguistes.
  Lecture de Hugo le 2026-10-12 : « je pense qu'ils souhaitent compter les occurrences. Vu
  qu'il peut y avoir plusieurs occurrences par bulle ». Tout le reste de la fiche en dépend :
  avec un tag posé sur la bulle, trois élisions comptent pour une, et deux clivages dans la
  même bulle ne peuvent pas se dire du tout — un tag est présent ou absent
- [x] **Une même famille peut recevoir plusieurs relevés dans une zone** — attendu : tranché.
  Hugo, le 2026-10-12 : oui — « si on a une phrase longue, avec plusieurs interrogatives par
  exemple, on pourrait avoir une antéposition dans un cas, puis un clivage, puis une
  inversion »
- [ ] **La couleur se pose sur les mots** — attendu : confirmé, et le chevauchement tranché
  sur maquette. Lecture de Hugo le 2026-10-12 : « ce serait au niveau des mots ». Dans
  « j'sais pas », une élision porte sur un mot et une négation courte sur deux : avec sept
  niveaux, il faut choisir entre un niveau affiché à la fois et des soulignements empilés.
  La couleur ne porte jamais l'information seule : une légende et la liste des relevés
  l'accompagnent
- [ ] **Un passage est continu, ou peut sauter des mots** — attendu : tranché. « Ne … pas »
  est discontinu ; proposition : du premier au dernier mot, sans trou, ce qui couvre le cas
  sans compliquer le geste
- [ ] **Le « doute » porte sur UN relevé, avec son commentaire, et se retrouve d'un coup** —
  attendu : tranché. Le guide dit « à utiliser dès que vous hésitez, toujours avec un
  commentaire court » ; Hugo, le 2026-10-12 : il sert au travail collectif — des stagiaires
  hésitent, des professeurs repassent derrière. C'est donc une demande de relecture, pas une
  catégorie : il lui faut dire sur quoi elle porte, une liste « à revoir », et une levée. Posé
  comme un tag de plus sur une bulle qui en porte trois, il ne dit pas duquel on doute. Sous
  un compte partagé, on ne sait pas non plus QUI doute
- [ ] **On compte aussi par niveau et par famille, ou seulement tag par tag** — attendu :
  tranché. Hugo, le 2026-10-12 : « je ne sais pas, il faut qu'on réfléchisse » ; toutes les
  familles ne serviront pas à chaque zone

### Avant que les stagiaires commencent

- [ ] **Ce qu'ils font en attendant le relevé est choisi** — attendu : tranché par Hugo. (a)
  Annoter tout de suite en tags à plat, en acceptant de repasser sur chaque bulle pour
  montrer les mots. (b) Les occuper d'abord à ce qui ne se reprend pas : découpage,
  transcription relue, locuteurs, lieux. (c) Les deux, dans cet ordre. Proposition : (c) —
  la transcription doit de toute façon être stable avant qu'on accroche quoi que ce soit à
  ses mots
- [ ] **Le guide ne donne qu'UNE forme par tag** — attendu : ses tableaux et son index
  s'accordent. Six écarts relevés le 2026-10-12, dont chacun ferait deux tags, donc deux
  compteurs : « élision » et « élision notée » ; « il / ils réduit à i ou y » et « il réduit à
  i ou y » ; « impersonnel present » sans accent et « impersonnel présent » ; « insulte » et
  « juron ou insulte » ; « indirecte standard », présente dans l'index seul, et
  l'interrogative indirecte rangée sous le titre « Exclamation » ; la ligne « intensifieur »,
  qui donne un tag dans une colonne et trois dans l'autre
- [ ] **Les tags du guide existent avant le premier stagiaire** — attendu : chacun est créé
  d'avance, avec sa définition et son exemple, pour que personne ne le tape de mémoire ;
  l'autocomplétion fait le reste. Environ soixante-cinq tags simples, plus une centaine de
  combinaisons aux niveaux 6 et 7. Lu le 2026-10-12 : l'import de vocabulaire
  (`lexique_import.py`) ne charge que domaines, dimensions et valeurs — rien ne charge des
  tags en lot
- [ ] **Une apostrophe ou un accent ne font pas deux tags** — attendu : « c’est pluriel »
  tapé avec l'apostrophe typographique ou avec la droite désigne le même tag. Lu le
  2026-10-12 : `socle._norm_tag` ne normalise que la casse et les espaces, et le libellé est
  unique à l'octet. Le guide écrit ses tags avec l'apostrophe typographique ; un clavier
  tape la droite
- [ ] **La référence d'une autre bulle écrite dans la Note ne devient pas fausse en silence**
  — attendu : dit aux annotateurs, ou remplacé par un lien que l'outil tient. Pour un
  chevauchement, le guide demande d'écrire dans la Note la référence de l'autre bulle telle
  que le logiciel l'affiche. Cette référence est DÉRIVÉE de l'ordre de lecture
  (`database.citations_regions`), jamais stockée : une case ajoutée ou réordonnée, et la même
  référence désigne une autre bulle
- [ ] **Une planche est transcrite et relue avant qu'on y pose des relevés** — attendu : écrit
  dans l'ordre de travail donné aux stagiaires. Un relevé accroché à des mots dépend du
  texte ; le statut de relecture par planche existe déjà et peut servir de feu vert

### Retours d'usage du même jour, indépendants du relevé

- [ ] **Un cartouche et une zone de texte reçoivent un locuteur** — attendu : le bloc
  « Locuteur » s'offre pour ces deux types, et la question de fond est tranchée. Retour
  d'usage : « une fois une nouvelle zone de texte créée, on ne peut pas lui attribuer un
  locuteur (de même pour les cartouches) ». Lu le 2026-10-12 : l'Atelier ne montre ce bloc
  que pour une bulle, alors que la route accepte n'importe quelle zone. La grille des
  linguistes range d'ailleurs le locuteur en quatre sortes — personnage identifié, non
  identifié, collectif, narrateur — : à trancher, si le narrateur d'un récitatif est un
  personnage du registre comme les autres, et si ces quatre sortes sont un attribut du
  personnage. Le gazetteer d'`ANN-3` n'y change rien : il SUGGÈRE un locuteur là où l'entrée
  existe
- [ ] **Taper un lieu seul dans « Situation » dit ce qui manque** — attendu : sur une case,
  « falaise » puis Entrée ne reste pas sans effet et sans message. Retour d'usage : « j'ai
  l'impression que je peux, au niveau de la case, ajouter une situation qui correspondrait
  au lieu. Mais finalement ça ne s'enregistre pas ». LU dans `static/viewer.js` le
  2026-10-12, pas rejoué à l'écran : le champ attend « dimension : valeur » ; sans les deux
  points, Entrée ne fait rien, sauf si une seule valeur existante correspond. HYPOTHÈSE sur
  la cause du retour ; l'autre possible : « falaise » et « cabane » créés comme tags, ou sous
  un axe prévu pour les personnages, donc non proposés sur une case. Ce qui trancherait :
  taper « lieu : falaise » en production, et regarder dans le Lexique si un axe « lieu »
  vise les cases
- [ ] **Le bouton de verrou dit ce qu'il protège** — attendu : son libellé ne laisse plus
  croire qu'il faut verrouiller avant d'annoter. Retour d'usage : « faut-il verrouiller la
  planche avant de l'annoter ? À quoi sert le verrouillage ? ». Il protège une planche des
  traitements automatiques et n'empêche aucune annotation humaine ; « Verrouiller la
  planche » se lit comme une réservation

### La maquette

- [ ] **Une maquette interactive du mode d'annotation est montrée aux linguistes** —
  attendu : hors de l'application, avec la grille réelle. Demande rapportée par Hugo :
  « l'annotation est l'élément le plus important […] pourrait-elle se faire dans un format
  similaire à celle de la transcription ? pour que ce soit présenté dans un format agrandi »,
  et, de lui : avoir la grille sous la main quand on annote. Elle fait jouer : la zone
  agrandie ; les niveaux repliables, chaque tag avec sa structure et son exemple ; un relevé
  posé sur des mots ; une paire des niveaux 6 et 7 en deux choix liés ; le doute et son
  commentaire sur la ligne concernée ; les deux rendus de couleur. Une forme d'écran se
  tranche là, pas sur une description

### Le modèle — à cadrer avant tout code

- [ ] **Le relevé est un objet à lui** — attendu : cadré. Une zone, une entrée de la grille,
  le premier et le dernier mot concernés (facultatifs : un contour de bulle n'en vise
  aucun), un doute, un commentaire ; plusieurs par zone, le même deux fois. Ni un tag, qui
  est présent ou absent, ni une ligne de `region_attribut`, dont la clé est le couple zone
  et valeur
- [ ] **L'ancrage suit le patron des corrections de grammaire** — attendu : quand la
  transcription est corrigée, un relevé suit son mot s'il existe encore, sinon il est mis de
  côté et signalé à revoir — jamais perdu, jamais déplacé en silence. Le mécanisme existe
  pour `token_correction` (la forme visée, le drapeau d'obsolescence,
  `database._reancrer_corrections`). À dire aussi : ce que devient un relevé là où le moteur
  de langue est absent, donc sans mots à viser
- [ ] **La grille entre dans le vocabulaire existant, ou dit ce qui lui manque** — attendu :
  tranché, la grille posée dans le format d'import. Les variables à variantes du niveau 3
  ont la forme exacte d'un axe et de ses valeurs ; mais le niveau 3 a QUATRE étages (niveau,
  famille, phénomène, variante) pour trois dans l'outil. Les paires des niveaux 6 et 7
  entrent avec le phénomène en axe et le procédé en valeur, ce qui garde la paire — et
  laisse à décider comment compter un même procédé à travers tous les phénomènes
- [ ] **Ce qui aura été annoté en tags se convertit** — attendu : la règle est écrite avant
  la première conversion. Un tag devient un relevé SANS passage, à compléter à la main ; le
  phénomène est gardé, les mots restent à montrer
- [ ] **L'Exploration compte des relevés** — attendu : cadré. Distribution et croisement par
  entrée de grille, par famille et par niveau ; croisement avec le locuteur, et avec le
  lemme et la catégorie des mots visés ; concordance centrée sur le passage
- [ ] **Le relevé sort, et ne sort que ce qu'on a le droit de sortir** — attendu : cadré. Sa
  place dans les exports d'album et dans la voie du dépôt ; la portée du vocabulaire, qui
  suit le titre de l'export ; les cliquets des sorties. Tout ce pan passe par une relecture
  croisée
- [ ] **Sa place dans l'ordre des chantiers est décidée** — attendu : tranché par Hugo. De la
  taille de `COL-3`, à mener en tranches ; `COL-3` attend la fusion de sa tranche 1, et le
  premier des trois commits de sa tranche 2 est écrit, sur copie

## Contexte

### D'où cela vient

Cinq retours d'utilisateurs de la production, rapportés par Hugo le 2026-10-12, avec la
consigne de ne lancer aucune modification : y a-t-il une limite aux tags et faut-il un
vocabulaire fermé, hiérarchisé dès le départ ; une zone de texte et un cartouche ne reçoivent
pas de locuteur ; un lieu posé sur une case ne s'enregistre pas ; faut-il verrouiller avant
d'annoter ; et l'annotation, « l'élément le plus important », pourrait-elle avoir un écran
agrandi comme la transcription. Une « légère insatisfaction » visait le « tag combiné ».

### Ce que la grille est

Le dépôt est public et la grille est le travail des linguistes : elle n'est pas recopiée
ici, seulement décrite. Sept niveaux — informations sur la bulle, marques graphiques et
phonographiques, morphosyntaxe, lexique, marqueurs discursifs et termes d'adresse,
phénomènes interactionnels et procédés de représentation, variétés régionales et de la
francophonie — et un tag transversal, le doute. Elle prend trois formes, et c'est ce qui
compte pour l'outil.

Des tags SIMPLES aux niveaux 2, 4 et 5, presque tous au mot : une élision, un mot familier,
une interjection. Des VARIABLES À VARIANTES au niveau 3, rangées en sept familles : un
phénomène et le choix d'une forme, comme « négation longue / négation courte » ou les dix
structures de l'interrogative partielle. Des PAIRES aux niveaux 6 et 7 : le « tag combiné »
se construit « phénomène + par + procédé » — sept phénomènes, neuf procédés —, et une variété
se dit avec son type de phénomène. Le niveau 1, lui, décrit ce que l'outil sait déjà : le
type de zone se choisit en la traçant, le lieu est la « Situation » de la case.

Le guide sent lui-même la fragilité des tags tapés : « utilisez toujours la même forme, sans
abréviation ni pluriel, sinon les comptages ne seront pas fiables ».

### Ce que l'outil a déjà, lu le 2026-10-12

Un tag est un libellé libre, mis en minuscules, unique dans l'instance, à plat ; aucune
limite de nombre. Il porte une définition, une note de portée, un état — et une couleur,
qu'aucun écran n'emploie. Les attributs ont trois étages (domaine, dimension, valeur) et
s'importent d'un tableur ; l'écran ne les offre que sur un personnage ou sur une case, mais
`region_attribut` accepte n'importe quelle zone, le commentaire du schéma le dit. Les mots
d'une zone existent (`tokens`, régénérés à chaque réindexation), et les corrections humaines
de grammaire s'y accrochent en survivant aux corrections de transcription. Le « combiné »
n'est donc le nom d'aucun objet de l'outil : c'est une chaîne de caractères dans un tag.

### Ce qui n'est pas établi

Rien de ceci n'a été rejoué à l'écran ni mesuré en production : ce sont des lectures du
code de `dev`, où `static/viewer.js` est identique à celui de la production. Les réponses
des linguistes sont, pour l'instant, celles que Hugo leur prête. La taille du chantier est
une estimation de discussion, pas un cadrage.
