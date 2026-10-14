---
chantier: ANN-6
statut: interrompu
---

# ANN-6 — le relevé : annoter des mots et des passages, pas seulement des bulles

**Arrêté sur** — 2026-10-13, `2ab7911` : **deux retours d'usage sont corrigés, avec ce que leur
relecture avait trouvé dans les mêmes champs ; le relevé n'est pas commencé.** Le 12 : un cartouche et une zone de texte reçoivent un locuteur (`7a21dc1`), le
champ « Situation » dit sa syntaxe (`35e9b62`). Le 13, sur le mot de Hugo : dans les champs
« dimension : valeur », Entrée agit sur ce qui est tapé et répond quand elle ne fait rien
(`2a52e77`) ; un nom déjà au registre, tapé vite, ne crée plus d'homonyme (`d957a70`) ; les
deux champs de profil portent la phrase d'aide (`2ab7911`). La passe navigateur entière
n'est pas encore rejouée sur cet état : seuls les fichiers de l'Atelier le sont.

**Point de départ** — 2026-10-12. Hugo rapporte cinq retours d'usage de la production, puis
transmet la grille d'annotation des linguistes (extrait d'un guide, treize pages : sept
niveaux et un tag transversal « doute »). Lue contre l'outil, elle demande ce qu'il n'a pas :
poser un phénomène sur des MOTS précis d'une zone, plusieurs fois par zone, et compter des
occurrences. Rien n'est codé, rien n'est maquetté ; cette fiche garde la discussion et ce
qu'elle laisse à trancher. Les stagiaires doivent commencer à annoter « dans les prochaines
semaines » (Hugo, le même jour).

## Reste

### Tranché par Hugo — 2026-10-12

- [x] **Le locuteur s'ouvre aux cartouches et aux zones de texte** — attendu : tranché. Hugo :
  « oui pour l'ouverture du locuteur ». Fait le jour même, cf. « Retours d'usage »
- [x] **« Situation » reçoit une phrase sous le champ, pas un changement de saisie** —
  attendu : tranché. Hugo : « une phrase en dessous en mode : Respectez la syntaxe
  "dimension : valeur", ex. : lieu : falaise ». Fait le jour même
- [x] **Créer les tags d'avance attend la vue d'annotation** — attendu : tranché. Hugo : « on
  en reparle plus tard, si on confectionne une vue d'annotation plus complète »

### Tranché par Hugo — 2026-10-13

- [x] **Le champ « dimension : valeur » est corrigé** — attendu : tranché. Hugo : « on corrige
  le champ dimension : valeur ». Fait le jour même, avec le doublon du champ du locuteur :
  cf. « Trouvé par la relecture croisée »
- [x] **Les deux champs de profil reçoivent la même phrase** — attendu : tranché, avec
  l'exemple. Hugo : « oui », pour l'exemple proposé, « registre : familier »
- [x] **`bulle_locuteur` et `nb_bulles` gardent leur nom** — attendu : tranché. Hugo : « ok »
  à la proposition de les laisser

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
  **Hugo, le 2026-10-12** : ces écarts seront réglés, de son côté
- [ ] **Les tags du guide existent avant le premier stagiaire** — attendu : chacun est créé
  d'avance, avec sa définition et son exemple, pour que personne ne le tape de mémoire ;
  l'autocomplétion fait le reste. Environ soixante-cinq tags simples, plus une centaine de
  combinaisons aux niveaux 6 et 7. Lu le 2026-10-12 : l'import de vocabulaire
  (`lexique_import.py`) ne charge que domaines, dimensions et valeurs — rien ne charge des
  tags en lot
  **Reporté par Hugo le 2026-10-12**, avec la vue d'annotation : cf. « Tranché par Hugo »
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

- [x] **Un cartouche et une zone de texte reçoivent un locuteur** — attendu : le bloc
  « Locuteur » s'offre pour ces deux types. Retour d'usage : « une fois une nouvelle zone de
  texte créée, on ne peut pas lui attribuer un locuteur (de même pour les cartouches) ».
  Mesuré avant : le bloc ne se montrait que pour une bulle, et la route acceptait un locuteur
  sur les CINQ types, case comprise. **Fermée par `7a21dc1`** : le bloc s'offre à la bulle, au
  cartouche et au texte, à eux seuls ; la route refuse le reste par un 422 qui nomme le type
  (`config.TYPES_LOCUTEUR`). Relecture croisée : la garde est juste sous cinq types et huit
  situations d'accès — qui n'écrit pas la région reçoit le 404 de toute région introuvable,
  jamais le 422 — ; 522 sorties comparées avant et après, aucune ne change de forme, aucune
  porte neuve, le cloisonnement tient. **Ce que les premiers tests valaient** : onze mutants
  du relecteur leur survivaient, la suite entière verte — la garde posée avant l'accesseur,
  l'accesseur en lecture seule, huit lecteurs ramenés aux seules bulles. Fermés par `6271d56`
  (22 mutants serveur tombés, un par un) et, pour trois gardes de l'écran, par `14d4ead`.
  Preuves : suite par défaut 1 664 passés ; passe navigateur entière sur le poste, 447 passés
  et trois accrocs dus à une mise en veille (réseau suspendu, serveur de test hors délai),
  rejoués seuls et verts ; dans l'image, sous l'autre police, les fichiers de l'Atelier verts
- [ ] **Le narrateur d'un récitatif a sa place dans le registre, ou une place à lui** —
  attendu : tranché avec les linguistes. Leur grille range le locuteur en quatre sortes —
  personnage identifié, non identifié, collectif, narrateur. Aujourd'hui le locuteur d'un
  cartouche se choisit dans le registre des personnages, où l'on peut créer une entrée pour
  un narrateur ; rien ne dédoublonne, deux homonymes sont possibles, et sous cloisonnement
  une étude ne voit pas celui de l'autre. Le gazetteer d'`ANN-3` n'y change rien : il
  SUGGÈRE un locuteur là où l'entrée existe
- [x] **Le champ « Situation » dit la syntaxe qu'il attend** — attendu : une phrase sous le
  champ, lue aussi par un lecteur d'écran. Retour d'usage : « j'ai l'impression que je peux,
  au niveau de la case, ajouter une situation qui correspondrait au lieu. Mais finalement ça
  ne s'enregistre pas ». L'hypothèse de la fiche était exacte, mesurée : « falaise » puis
  Entrée ne déclenche ni requête ni message. **Fermée par `35e9b62`** : « Respectez la
  syntaxe « dimension : valeur ». Exemple : lieu : falaise ». La saisie n'a pas changé
  (quatorze gestes rejoués avant et après par la relecture, mêmes requêtes) ; la phrase tient
  à 320 px sous une préférence de 24, sur le poste et dans l'image ; contraste de 6,2 à 6,3
- [x] **Entrée ne reste plus sans effet et sans message** — attendu : sur une case, « falaise »
  puis Entrée dit ce qui manque. **Fermée par `2a52e77`** : champ rempli et rien à faire —
  un mot seul qui ne désigne pas UNE proposition, ou « lieu : » sans valeur —, l'écran
  répond « Rien n'est ajouté : écrivez « dimension : valeur », ou choisissez une
  proposition. », dans la région d'annonce de la page, quatre secondes. Jamais dans le champ
  vide. Preuve : `tests/test_e2e_atelier_propositions.py`, trois saisies sur deux montages ;
  le mutant qui retire le message fait tomber le test. Ce qu'un lecteur d'écran PRONONCE
  n'est pas mesuré : cf. « Laissé ouvert par le correctif des champs »
- [ ] **Le bouton de verrou dit ce qu'il protège** — attendu : son libellé ne laisse plus
  croire qu'il faut verrouiller avant d'annoter. Retour d'usage : « faut-il verrouiller la
  planche avant de l'annoter ? À quoi sert le verrouillage ? ». Il protège une planche des
  traitements automatiques et n'empêche aucune annotation humaine ; « Verrouiller la
  planche » se lit comme une réservation

### Trouvé par la relecture croisée, antérieur aux deux correctifs — 2026-10-12

- [x] **Entrée décide d'après une liste périmée, et peut poser une AUTRE valeur** — attendu :
  Entrée agit sur ce qui est tapé. Reproduit sur `33bc5ea` comme après : si une seule valeur
  existe (« lieu : falaise »), « grotte » tapé vite puis Entrée pose « lieu : falaise », et
  Entrée dans le champ VIDE la pose aussi ; « lieu : phare » tapé vite ne part pas, il faut
  une seconde Entrée. Le même champ sert au profil d'un personnage, où « argot » peut poser
  « registre : soutenu » — et ce profil vaut pour tout le corpus. Cause LUE : la liste est
  calculée 200 ms après la frappe, Entrée la consulte telle qu'elle est. **Fermée par
  `2a52e77`**, dans la fonction qui sert les trois champs. La lecture rendait déjà TOUT le
  vocabulaire : il est gardé, et la liste se recalcule à chaque frappe, sans attendre le
  réseau ; la forme complète aboutit en UNE Entrée sans consulter la liste ; le champ vide
  n'affecte rien ; une lecture arrivée après une plus récente est écartée. Trois défauts de
  la même fonction corrigés avec : « lieu:falaise » sans espaces ne faisait rien quand la
  valeur existait ; après un choix, ↓ rouvrait la liste de la saisie d'avant ; l'attribut
  partait vers la région sélectionnée ENTRE-TEMPS et non vers celle du geste. Preuves : la
  course est tenue par les tests — la lecture est retenue en vol, aucune vitesse de frappe
  n'entre en jeu — et mesurée sur la requête partie ; rejoués sur le code d'avant, 30 des 34
  premiers cas tombent, les quatre autres sont tenus par des mutants ; quinze mutants, tous
  tombés, un par un ; suite par défaut 1 669 passés ; 244 tests navigateur de l'Atelier verts sur
  le poste, 67 dans l'image sous l'autre police ; les quatorze gestes de la relecture
  rejoués — aucun geste lent ne change d'écriture. Non fermé, écrit dans le code : avant le
  retour de la toute première lecture, un mot seul reçoit le message là où, un instant plus
  tard, Entrée aurait pris l'unique résultat ; rien de faux n'est posé
- [x] **Un nom existant tapé vite crée un second personnage homonyme** — attendu : Entrée
  prend l'homonyme exact avant de créer. Reproduit avec quatorze personnages au registre :
  « Zed » existant, tapé vite puis Entrée, crée un second « Zed » et l'attribue. Même cause
  que la case du dessus, dans le champ du locuteur. **Fermée par `d957a70`**, pour le
  locuteur et la boîte personnage : si la liste ne vaut pas pour ce qui est tapé, le
  registre est RELU pour cette saisie avant de décider. Trois défauts de la même fonction
  corrigés avec : l'homonyme au-delà de la dixième proposition n'était pas trouvé, et
  Entrée créait un doublon même tapé lentement (mesuré sur le code d'avant) ; une lecture
  en échec valait un registre vide, donc Entrée créait ; le choix partait vers la zone
  sélectionnée entre-temps. Aucune unicité n'est posée côté serveur : la série distingue
  des homonymes légitimes. Preuves : douze mutants, tous tombés, un par un ; les tests
  jouent les deux champs, lecture en vol et avant la lecture
- [x] **La même phrase sous les deux champs de profil d'un personnage** — attendu : tranché
  par Hugo, avec son exemple. **Fermée par `2ab7911`** : « Respectez la syntaxe « dimension :
  valeur ». Exemple : registre : familier », sous chacun des deux champs, reliée au sien
  pour un lecteur d'écran. Mesuré à 320 px sous une préférence de 24 : trois lignes sur le
  poste, quatre dans l'image, jamais rognée, l'exemple d'un seul tenant. L'audit
  d'accessibilité voit désormais les deux blocs, sombre et clair — son décor n'avait ni
  locuteur ni boîte personnage. Dix mutants, tous tombés
- [ ] **Un locuteur hérité sur une région devenue case se voit, ou part avec le type** —
  attendu : tranché. Une bulle qui a un locuteur et devient case le garde : invisible à
  l'écran, il compte encore au registre, dans la Recherche et les exports. L'annulation peut
  aussi en reposer un sur une case, la garde ne tenant que la route — écrit dans son
  commentaire et décrit par un test. « Aucune case ne porte de locuteur » n'est pas un
  invariant de la base. Non su : si la production en porte déjà
- [ ] **Annuler la suppression d'une région rend aussi son locuteur** — attendu : Ctrl+Z
  d'une suppression rend ce qui a été supprimé. Reproduit, antérieur : une case avec une
  situation, dessous un cartouche avec locuteur, note et tag ; supprimer la case, puis
  Ctrl+Z : case, cartouche, note et tag reviennent, le locuteur du cartouche et la situation
  de la case non. Cause LUE : l'instantané d'une région n'emporte que ses colonnes et son
  annotation. À rapprocher d'`UX-5`
- [ ] **Le premier Ctrl+Z ou la première note après un redémarrage ne gèle plus l'écran** —
  attendu : dit, ou fermé. Mesuré : 9 à 17 secondes sans rien afficher, le temps de charger
  le moteur de langue ; 0,01 s ensuite. Le préchauffage existe (`BD_NLP_PREWARM`) et il est
  commenté dans `deploy/docker-compose.yml`. Annuler un lien de locuteur ne réindexe rien :
  ce chargement y est payé pour rien
- [ ] **Le contraste élevé est audité quelque part** — attendu : tranché. L'audit
  d'accessibilité du dépôt ne pose que le thème, clair ou sombre ; un mutant qui cache la
  phrase de « Situation » en contraste élevé passe toute la suite
- [x] **Le nom de la table du locuteur et la clé `nb_bulles` restent, ou changent** —
  attendu : tranché par Hugo. **Ils restent** (2026-10-13). La table s'appelle
  `bulle_locuteur` et la clé compte désormais des prises de parole, cartouches compris. Le
  nom de la table est une DONNÉE du journal et des exports de provenance déjà produits ; la
  clé n'est lue par aucun écran

### Laissé ouvert par le correctif des champs — 2026-10-13

- [ ] **La région des messages existe avant son premier message, sur les cinq surfaces** —
  attendu : le premier message d'une page est annoncé par un lecteur d'écran, mesuré avec
  l'un d'eux. Aujourd'hui la région naît AVEC son premier message, et ce premier message
  est désormais « Rien n'est ajouté… ». L'auteur du correctif l'avait posée d'avance dans le
  gabarit de l'Atelier seul : non porté — rien n'est mesuré, et une surface sur cinq
- [ ] **Pendant que la liste du registre se recharge, ↓ puis Entrée ne prend pas un nom de la
  liste d'avant** — attendu : tranché. Entre une frappe et le retour de sa liste, ↓ puis
  Entrée prend la proposition surlignée de la liste précédente : elle est à l'écran, le
  geste est explicite. La fermer rend les flèches inertes le temps de la lecture
- [ ] **Plusieurs personnages du même nom se départagent à l'écran** — attendu : tranché.
  Quand plusieurs homonymes exacts existent déjà, Entrée prend le premier dans l'ordre du
  registre — nom, puis série, celui sans série d'abord —, sans le dire (mesuré, inchangé).
  Le guide le dit ; aucun test ne fige ce choix
- [ ] **Les deux champs de personnage savent ce que l'autre vient de créer** — attendu : dit,
  ou fermé. « Zed » créé par la boîte personnage, puis tapé vite dans le champ du locuteur,
  se décide sur la liste de ce champ-là — périmée seulement si « Zed » y avait déjà été
  cherché. Rapporté par l'auteur du correctif, non rejoué
- [ ] **Après une validation, la première ↓ surligne une proposition** — attendu : une seule
  flèche suffit. Antérieur, dans les champs à propositions : la première rouvre la liste
  sans rien surligner, il en faut une seconde
- [ ] **À 320 px sous une police de 24, le champ ne dépasse pas du tiroir dans l'image** —
  attendu : aucun défilement en largeur du tiroir. Antérieur, mesuré dans l'image : le
  champ « dimension : valeur » va jusqu'à 326,6 px et le tiroir défile ; sur le poste il
  s'arrête à 318,6 px. Les phrases d'aide, elles, tiennent. À rapprocher d'`UX-7`
- [ ] **La règle d'Entrée du champ « dimension : valeur » vit dans un module pur** —
  attendu : tranché. Elle ne dépend plus de l'horloge : une table de vérité sous Node la
  couvrirait en millisecondes, là où chaque variante coûte un test navigateur de cinq à dix
  secondes. Recommandé par l'auteur du correctif, non fait : un script de plus au gabarit

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
  **Ajouté par Hugo le 2026-10-12** : au lieu de tags à taper, des cases à cocher rangées
  selon les niveaux de la grille, tags combinés compris — à établir dans ce nouvel espace
  **Un premier essai n'a pas convaincu Hugo (2026-10-14)**, fait depuis la session de
  pilotage : trois dispositions jouables, la grille réelle, une planche dessinée. Ses
  raisons : la maquette ne ressemble pas au site ; elle n'a pas suivi la façon habituelle
  de produire une page ; une planche du corpus aurait mieux servi qu'un dessin. La suite se
  fait dans une SESSION DÉDIÉE, qui commence par une série de questions pour calibrer
  l'outil d'annotation, avant toute maquette. L'essai et ses notes sont gardés hors du
  dépôt, dans `C:	emp\maquette-ann6` (la grille y est, le dépôt étant public)

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
