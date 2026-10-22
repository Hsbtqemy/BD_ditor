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
n'est pas encore rejouée sur cet état : seuls les fichiers de l'Atelier le sont. Le 14, sans
code : l'outil d'annotation est calibré avec Hugo, et une seconde maquette est publiée (cf.
« Tranché par Hugo — 2026-10-14 » et « La maquette »). Puis la note de cadrage du modèle est
écrite et validée (`docs/grilles-et-releves.md`) ; la tranche 1 attend la fusion de `COL-3`.

**2026-10-21 — la fiche est découpée** (avec Hugo). Les quatorze défauts de l'annotation
ACTUELLE, qui ne dépendent ni du relevé ni des grilles — le verrou, le gel du premier Ctrl+Z,
le contraste élevé, le locuteur hérité et son annulation, les sept points laissés ouverts par
le correctif des champs, l'apostrophe des tags, la référence d'une bulle dans la Note —
partent vers `ANN-8`, pour être traités tôt. Reste ici ce qui attend le modèle d'`ANN-7` :
la page Annotation (son module, sa maquette), le relevé, ce qui se confirme avec les
linguistes, et l'organisation du travail des stagiaires.

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

### Tranché par Hugo — 2026-10-14, le calibrage de l'outil d'annotation

- [x] **Stagiaires et professeurs annotent à égalité** — attendu : tranché. L'écran sert
  autant qui découvre la grille que qui la sait. Le matériel des stagiaires n'est pas
  connu : l'écran tient sur un portable et profite d'un grand écran
- [x] **Zone par zone, sans empêcher une passe par niveau** — attendu : tranché. Hugo : « le
  zone par zone peut être plus judicieux, mais il ne faut pas que ça empêche la navigation
  niveau par niveau ». Un sélecteur n'affiche qu'une rubrique, et « Suivante » enchaîne
  les zones que la grille vise
- [x] **Une grille, trois lectures** — attendu : tranché. Les entrées se cochent, rangées par
  rubriques repliables ; un champ de frappe FILTRE la grille (accents, apostrophes et
  exemples compris) et Entrée pose le premier résultat ; la ligne du guide de l'entrée
  pointée s'affiche à un endroit fixe, piège compris ; le guide complet se déplie, produit
  depuis la grille. Hugo : « il faut tout rendre possible »
- [x] **Plusieurs grilles : une à la fois, par un sélecteur** — attendu : tranché. Les
  relevés des autres grilles restent visibles, en lecture
- [x] **La zone et son contexte** — attendu : tranché. Modifiables sur place : la situation
  de la case, le locuteur et sa sorte, la note. Hugo : « l'annotation ne concerne pas que
  le texte ». Placés d'abord en tête de la zone, puis, sur la première maquette, déplacés
  par Hugo dans la colonne de gauche, sous la planche
- [x] **La case au centre ; on choisit DANS la case où l'on annote** — attendu : tranché,
  sur la première maquette. Hugo : « il faut davantage recentrer autour de la case, et
  permettre de sélectionner à l'intérieur où on souhaite annoter ». La planche ne sert
  plus qu'à choisir une case ; dans la case agrandie, le fond désigne la case, un clic une
  bulle, un texte ou un personnage, un glissé trace un détail ; les mots de la zone
  choisie s'affichent dessous
- [x] **L'écran ne change ni de disposition ni de taille en cours de travail** — attendu :
  tranché. Hugo : « moins on change la disposition et les tailles au cours de
  l'annotation, mieux c'est, sinon on perd les utilisateurs ». Au centre, l'image de la
  case vit dans une boîte de hauteur constante, et les mots de la zone choisie dessous,
  toujours au même endroit, sans défiler. Une zone à la fois : afficher tous les textes de
  la case gênerait un travail qui ne veut pas tout annoter. Image et texte côte à côte :
  écarté, la lecture y perdrait
- [x] **La synthèse du travail est un onglet de la colonne de gauche** — attendu : tranché.
  Hugo : « Vue planche et vue synthèse du travail effectué ». « Planche » montre la planche
  et le contexte ; « Synthèse », les relevés, les doutes à revoir et le décompte
- [x] **Les phrases d'aide quittent l'écran** — attendu : tranché. Elles passent dans les
  infobulles et le nom accessible de l'image ; une case sans zone de texte choisie montre
  ses zones (b1, b2…) à la place des mots
- [x] **La ligne du guide a une hauteur fixe** — attendu : tranché. Hugo : la grille est
  « assez lisible », mais le bas « change de taille ». La ligne défile en elle-même, la
  grille au-dessus ne bouge plus
- [x] **Tablette et téléphone annotent aussi, sans urgence** — attendu : tranché. Hugo :
  « j'aimerais que les deux puissent annoter, mais on peut prendre notre temps »
- [x] **Sur l'image, un relevé porte sur une région ou sur un détail tracé** — attendu :
  tranché. Par défaut une région déjà tracée (case, personnage, planche) ; un détail se
  trace dans la vue agrandie, comme un passage se désigne dans le texte
- [x] **Un détail tracé est une zone à part entière, et le tracé peut faire un texte** —
  attendu : tranché. Sur la maquette, un détail n'existait que sous la grille qui l'avait
  tracé, et Hugo, voulant commenter un détail avec plusieurs grilles, s'est vu refuser le
  tracé sous Oralité. Glisser dans la case crée désormais une zone, quelle que soit la
  grille active : « Détail d'image », qui se nomme, se supprime, et que toute grille qui
  vise un détail annote, Tags libres compris ; ou « Texte hors bulle », qui reçoit une
  transcription puis s'annote avec Oralité. Les deux, choisis par Hugo le 2026-10-14.
  Une zone tracée ici n'est pas une case : le découpage reste à l'Atelier
- [x] **Le nom d'un personnage ou d'un détail s'écrit sur l'image, en petit** — attendu :
  tranché. L'Atelier n'étiquette une région que par son rang (« c2 », « b1 », et « 3·p »
  pour une boîte personnage, `regionLabel` dans `static/viewer.js`) ; la maquette y écrit
  le nom. Hugo : « ça peut être intéressant. Peut-être pas en aussi grand ». Dans la
  maquette, à taille d'écran constante (environ 12 px), quelle que soit la largeur de la
  case
- [x] **Le doute : un commentaire, des réponses, une levée** — attendu : tranché. Signé et
  daté ; on le lève en gardant, en changeant ou en retirant le relevé ; une liste « À
  revoir » les réunit
- [x] **Une zone se marque « faite » par grille, ou par rubrique** — attendu : tranché. C'est
  ce qui permet de compter 0 plutôt que « pas regardé ». Sur la maquette, « Faite pour
  Oralité · Sauter les faites », sous les mots, ne se comprenait pas (Hugo). Le marquage
  passe dans la colonne de la grille, que l'on applique : « Oralité appliquée à cette
  zone », un ✓ sur l'onglet de chaque grille appliquée, et « Parcours : toutes les zones |
  à faire seulement » pour « Suivante ». Le mot reste à trouver : Hugo hésite entre
  « appliquée », « effectuée » ou autre
- [x] **L'écran est un module, monté dans l'Atelier ET sur une page à part** — attendu :
  tranché. Qui prépare et qui annote : « tout. Les mêmes personnes et des personnes
  différentes ». Deux publics, donc deux montages d'un même module (la convention de
  `static/lib/qui-entre.js`) : dans l'Atelier en vue agrandie, comme la Transcription, et
  sur une page « Annotation » entre Atelier et Bibliothèque. La maquette montrait les deux ;
  Hugo, après les avoir vus : « il vaut mieux partir sur une page annotation ». La
  maquette n'a plus que ce cadre ; le module reste montable dans l'Atelier si l'usage le
  demande, comme second montage
- [x] **La planche et la grille peuvent figurer dans la maquette publiée** — attendu :
  tranché. Hugo : « Planche et grille », sur une page privée

### Tranché par Hugo — 2026-10-22, sur la maquette v3

- [x] **La liste de ce qui est posé est toujours visible, en bas de la colonne de la grille** —
  attendu : tranché. Sur la v3, cliquer « chais » ne montrait que ce qui porte EXACTEMENT sur
  ce mot ; la négation posée sur « chais pas » ne se voyait que dans la Synthèse. Hugo : « ça
  me semble très utile que ce soit toujours visible, comme le texte lui-même ». Une boîte à
  hauteur fixe liste les relevés qui touchent les mots désignés, toutes grilles, ou toute la
  zone si rien n'est désigné ; sur une case ou une boîte personnage, ce qui porte sur elle. Un
  clic désigne exactement le passage du relevé et bascule sur sa grille. Placée d'abord sous
  les mots (la page défilait dès que la fenêtre n'était pas très grande), puis au-dessus de
  la grille, puis, essayée dans les deux positions, en bas, au-dessus de la ligne du guide, en
  face de la boîte des mots. Hugo : « En bas, c'est pas mal du tout. j'aime bien »
- [x] **L'en-tête de la grille s'allège** — attendu : tranché. Hugo le trouvait « très
  bavard, entre le choix de grille de vocab et le début de la grille elle-même ». La
  description de la grille (version, cible, note) passe en infobulle sur son onglet ;
  « appliquée » et « Afficher » tiennent sur une ligne ; le parcours (« toutes les zones | à
  faire seulement ») descend à côté de « Suivante », qu'il gouverne
- [x] **Dans une collection qui masque des grilles, leurs onglets sont cachés** — attendu :
  tranché (`ANN-7`, Q1). Les relevés des grilles masquées restent dans les listes, en gris,
  sans geste ; l'infobulle de la liste Collection dit combien de grilles sont masquées.
  L'autre forme essayée, des onglets grisés, est écartée
- [x] **Un conflit sur une valeur unique s'affiche à la place de la ligne du guide** —
  attendu : tranché (`ANN-7`, Q7). Le bandeau de l'Atelier (`CONC-3`) : ce qui n'est pas
  enregistré, la version de l'autre, « Remplacer par la mienne » et « Garder l'autre » ; la
  colonne ne change pas de hauteur. Une écriture identique à celle de l'autre passe sans
  conflit
- [x] **La cardinalité ne se marque que là où elle surprend** — attendu : tranché (`ANN-7`,
  Q6). Une pastille « plusieurs » sur une entrée qui se pose plusieurs fois sur une cible
  ENTIÈRE ; sur des mots, plusieurs est la règle, et « une » sur une cible entière aussi,
  sans marque
- [x] **« À compléter » a deux causes** — attendu : tranché. Un changement de forme entre
  versions (note §6), et un relevé posé sans le lien ou la précision que son entrée attend (un
  chevauchement sans l'autre bulle, « France » sans sa région). Les deux se réunissent dans
  « À revoir », avec les doutes et les relevés « à revoir ». La note de `docs/grilles-et-releves.md`
  le dira au premier commit de la tranche 1 (case « La note est à jour » d'`ANN-7`)
- [x] **Par défaut, seuls les relevés de la grille active s'affichent** — attendu : tranché.
  Hugo : un corpus déjà annoté avec Oralité et Émotions, qu'on reprend avec Couleur et dessin
  — « Je n'ai pas spécialement envie que les annotations qui sont propres à d'autres
  vocabulaires viennent parasiter le nouveau travail d'annotation », et « pas de base toutes
  les grilles ». Un réglage d'AFFICHAGE, propre à chacun, dans l'en-tête de la liste de ce qui
  est posé : « Relevés : Oralité ▾ », des cases par grille du projet (la grille active toujours
  cochée, une grille masquée par la collection marquée « masquée ici »), « Toutes » et
  « … seule ». Il vaut pour les traits sous les mots, la liste, la Synthèse et les marques de
  doute sur la planche ; ni les nombres des onglets ni le Décompte. Retenu par personne et par
  projet, sur le poste, comme le filtre de collection de l'Atelier (`UX-19`) ; ni la collection
  ni l'adresse ne le portent. Hugo : « C'est bien ». Le cas d'un NOUVEAU projet sur le même
  corpus se règle avant l'écran : une copie sœur n'emporte que les relevés des grilles actives
  à l'arrivée, et aucun au cran « découpage » (`ANN-7`)
- [x] **« Terminée » se marque au pied de la zone, avec Suivante** — attendu : tranché. Hugo
  trouvait « Oralité appliquée », en tête de la grille, « un peu mal placé, et peut-être peu
  clair ». Le pied de la colonne du centre a deux lignes de hauteur fixe : l'état de la zone
  pour la grille active (« Oralité : à faire », ou « ✓ Oralité : terminée · Camille D. » et
  « Rouvrir » ; la date et le sens — un zéro compte comme un zéro — en infobulle) et le
  parcours ; puis « ‹ Précédente », « Suivante › », et le geste principal « Terminée,
  suivante › », qui marque et avance en un clic. Hugo : « On garde les deux boutons, c'est
  nécessaire » — on passe une zone sans la marquer. Le mot est « terminée », partout
  (légende, onglet, barre d'état, Décompte) : la question ouverte n°6 de la note
  (« appliquée » en attendant mieux) est tranchée. Hugo : « c'est très bien »
- [x] **La Synthèse › Relevés montre toute la planche, rangée par case** — attendu : tranché.
  Son ancien contenu (la zone et son contexte) faisait doublon avec la liste du bas. Une case
  par groupe dans l'ordre de lecture (« Case c3 · 9 »), puis la planche et les personnages
  partout ; une ligne compacte par relevé (libellé, zone, passage, états, grille) ; la case en
  cours marquée ; un clic ouvre le relevé, un clic sur la case l'ouvre. Hugo : « à l'échelle
  de la planche, c'est excellent »
- [x] **Douter et retirer se font sur la liste de ce qui est posé** — attendu : tranché. Deux
  petits boutons par ligne, « ? » et « ✕ », absents d'un relevé en lecture ; le doute s'écrit
  dans la boîte du guide, comme le conflit. Répondre à un doute et le lever restent dans
  « À revoir ». Hugo les a trouvés « trop discrets », avec une crainte : « que les utilisateurs
  aient l'impression qu'il faut qu'ils cliquent dessus obligatoirement ». Colorés, sans fond
  (l'ambre du doute, le rouge du retrait), « pour l'instant »
- [x] **On n'active pas une grille depuis la page Annotation** — attendu : tranché. Activer est
  un réglage du projet, rare, fait par son responsable ; la page Annotation est l'écran de
  tous les jours. Elle n'offre au responsable qu'un lien, « Gérer les grilles ↗ », vers la
  fiche du projet, où les grilles se règlent (cf. `ANN-7`, « Le catalogue et le partage »).
  Choisi par Hugo le 2026-10-22, parmi trois formes (là, ici, les deux pleinement) ; le volet
  de catalogue de la v3 quitte la page
- [x] **Le Contexte ne garde que ce qui n'est pas du vocabulaire** — attendu : tranché. La
  colonne de gauche de la v2 portait la « Situation » de la case (un attribut, qui part au
  basculement avec Q3) et une « sorte » de locuteur, que l'outil n'a pas : la maquette v2
  avait écrit EN DUR les quatre sortes de la grille des linguistes, ce que l'outil agnostique
  interdit (vérifié dans `static/viewer.js` le 2026-10-22). Restent le locuteur (un lien vers
  le registre), la note et le nom d'un détail ; le Contexte tient sans défiler
- [x] **Le lieu d'une case est une entrée de grille, sur la case** — attendu : tranché par
  Hugo le 2026-10-22, plutôt qu'un champ de l'outil dont les valeurs seraient un vocabulaire.
  Le niveau 1 des linguistes cesse d'être « pris dans l'outil » pour le lieu. Il vit dans une
  grille À PART, « Lieux », ouverte, sur la case — pas dans la grille des linguistes. Hugo :
  « je préfère que c'est en dehors de la grille Oralité »
- [x] **La sorte de locuteur est une entrée de la grille des linguistes** — attendu : tranché
  par Hugo le 2026-10-22. Niveau 1, à variantes (identifié, non identifié, collectif,
  narrateur·ice), sur la zone de texte, une fois par zone. La question du narrateur au
  registre (case « Le narrateur d'un récitatif… ») reste aux linguistes
- [ ] **La page Annotation atteint l'entité personnage par les deux chemins de l'Atelier** —
  attendu : à la tranche 2, une grille qui vise l'entité (`ANN-7`, Q4) se pose depuis une boîte
  personnage ET depuis le locuteur d'une zone de texte, comme le profil d'aujourd'hui dans le
  panneau Personnage de l'Atelier (`static/viewer.js`, « profil corpus ») ; et l'écran dit
  qu'un tel relevé vaut partout. La v3 ne fait jouer que la boîte, avec une grille fictive :
  ce n'est pas une décision de forme, c'est ne pas perdre un geste qui existe (constaté le
  2026-10-22, en revue de la maquette avec Hugo)
- [ ] **« ? » et « ✕ » colorés ne passent pas pour des gestes obligatoires** — attendu : à
  l'usage, avec les premiers stagiaires sur la page Annotation, personne ne clique « ? » sur
  chaque relevé « pour valider » ; sinon, revenir à des boutons sans couleur et chercher
  autre chose

### À confirmer avec les linguistes

- [x] **On compte des OCCURRENCES, pas des bulles** — attendu : confirmé par les linguistes.
  Lecture de Hugo le 2026-10-12 : « je pense qu'ils souhaitent compter les occurrences. Vu
  qu'il peut y avoir plusieurs occurrences par bulle ». Tout le reste de la fiche en dépend :
  avec un tag posé sur la bulle, trois élisions comptent pour une, et deux clivages dans la
  même bulle ne peuvent pas se dire du tout — un tag est présent ou absent **Confirmé par les linguistes le 2026-10-22**, rapporté par Hugo, sur la maquette v3
- [x] **Une même famille peut recevoir plusieurs relevés dans une zone** — attendu : tranché.
  Hugo, le 2026-10-12 : oui — « si on a une phrase longue, avec plusieurs interrogatives par
  exemple, on pourrait avoir une antéposition dans un cas, puis un clivage, puis une
  inversion »
- [x] **La couleur se pose sur les mots** — attendu : confirmé, et le chevauchement tranché
  sur maquette. Lecture de Hugo le 2026-10-12 : « ce serait au niveau des mots ». Dans
  « j'sais pas », une élision porte sur un mot et une négation courte sur deux : avec sept
  niveaux, il faut choisir entre un niveau affiché à la fois et des soulignements empilés.
  La couleur ne porte jamais l'information seule : une légende et la liste des relevés
  l'accompagnent **Confirmé par les linguistes le 2026-10-22**, rapporté par Hugo, sur la maquette v3 : une teinte par rubrique pour la grille active, les autres en gris
- [x] **Un passage est continu, ou peut sauter des mots** — attendu : tranché. « Ne … pas »
  est discontinu ; proposition : du premier au dernier mot, sans trou, ce qui couvre le cas
  sans compliquer le geste **Confirmé par les linguistes le 2026-10-22**, rapporté par Hugo, sur la maquette v3 : les deux se combinent (cf. « Un passage est continu ET peut sauter des mots »)
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
- [x] **La double annotation à l'aveugle est voulue, ou non** — attendu : réponse des
  linguistes. La passe est commune (`ANN-7`, Q7, 2026-10-22) : on se partage les zones. Deux
  personnes qui annotent la même zone sans voir l'autre, pour mesurer leur accord, demanderaient
  un mode de campagne aux passes séparées, à concevoir alors **Pas voulue** — réponse des linguistes rapportée par Hugo le 2026-10-22 : la passe commune leur suffit, aucun mode de campagne n'est à concevoir

### Avant que les stagiaires commencent

*Sorties vers `ANN-8` le 2026-10-21 : les défauts de l'annotation d'aujourd'hui, qui ne dépendent pas du relevé.*

- [x] **Ce qu'ils font en attendant le relevé est choisi** — attendu : tranché par Hugo. (a)
  Annoter tout de suite en tags à plat, en acceptant de repasser sur chaque bulle pour
  montrer les mots. (b) Les occuper d'abord à ce qui ne se reprend pas : découpage,
  transcription relue, locuteurs, lieux. (c) Les deux, dans cet ordre. Proposition : (c) —
  la transcription doit de toute façon être stable avant qu'on accroche quoi que ce soit à
  ses mots
  **Tranché par Hugo le 2026-10-22, à la séance de conception d'`ANN-7` (Q9) : (b)** —
  découpage, transcription relue, locuteurs, lieux, et aucun tag avant le basculement, ce qui
  laisse les grilles partir d'un vocabulaire neuf sans rien convertir
- [ ] **Le guide ne donne qu'UNE forme par tag** — attendu : ses tableaux et son index
  s'accordent. Six écarts relevés le 2026-10-12, dont chacun ferait deux tags, donc deux
  compteurs : « élision » et « élision notée » ; « il / ils réduit à i ou y » et « il réduit à
  i ou y » ; « impersonnel present » sans accent et « impersonnel présent » ; « insulte » et
  « juron ou insulte » ; « indirecte standard », présente dans l'index seul, et
  l'interrogative indirecte rangée sous le titre « Exclamation » ; la ligne « intensifieur »,
  qui donne un tag dans une colonne et trois dans l'autre
  **Hugo, le 2026-10-12** : ces écarts seront réglés, de son côté
- [x] **Les tags du guide existent avant le premier stagiaire** — attendu : chacun est créé
  d'avance, avec sa définition et son exemple, pour que personne ne le tape de mémoire ;
  l'autocomplétion fait le reste. Environ soixante-cinq tags simples, plus une centaine de
  combinaisons aux niveaux 6 et 7. Lu le 2026-10-12 : l'import de vocabulaire
  (`lexique_import.py`) ne charge que domaines, dimensions et valeurs — rien ne charge des
  tags en lot
  **Reporté par Hugo le 2026-10-12**, avec la vue d'annotation : cf. « Tranché par Hugo »
  **Sans objet depuis le 2026-10-22** : les stagiaires ne posent aucun tag avant le
  basculement (case ci-dessus), et la grille importée tient lieu de tags créés d'avance
- [ ] **Une planche est transcrite et relue avant qu'on y pose des relevés** — attendu : écrit
  dans l'ordre de travail donné aux stagiaires. Un relevé accroché à des mots dépend du
  texte ; le statut de relecture par planche existe déjà et peut servir de feu vert

### Retours d'usage du même jour, indépendants du relevé

*Sorties vers `ANN-8` le 2026-10-21 : les défauts de l'annotation d'aujourd'hui, qui ne dépendent pas du relevé.*

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

### Trouvé par la relecture croisée, antérieur aux deux correctifs — 2026-10-12

*Sorties vers `ANN-8` le 2026-10-21 : les défauts de l'annotation d'aujourd'hui, qui ne dépendent pas du relevé.*

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
- [x] **Le nom de la table du locuteur et la clé `nb_bulles` restent, ou changent** —
  attendu : tranché par Hugo. **Ils restent** (2026-10-13). La table s'appelle
  `bulle_locuteur` et la clé compte désormais des prises de parole, cartouches compris. Le
  nom de la table est une DONNÉE du journal et des exports de provenance déjà produits ; la
  clé n'est lue par aucun écran

### La maquette

- [x] **Une maquette interactive du mode d'annotation est montrée aux linguistes** —
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
  dépôt, dans `C:\temp\maquette-ann6` (la grille y est, le dépôt étant public)
  **Seconde maquette publiée le 2026-10-14**, depuis la session dédiée, après calibrage
  (cf. « Tranché par Hugo — 2026-10-14 ») : page privée
  `https://claude.ai/artifact/97Xznyg2dqkQ7bX9EYwhkU`, à partager depuis la page. Elle
  reprend les bandes et les jetons de l'Atelier, la planche 1 d'« esther v1 » et la
  planche 24 d'« Eau-terre », quatre grilles (celle des linguistes, les tags libres en
  grille ouverte, et deux grilles fictives qui portent sur l'image : émotions, couleur et
  dessin). Source hors du dépôt : `C:\temp\maquette-ann6\v2\releve.html`. Republiée le même
  jour à la même adresse après les retours de Hugo : case au centre, contexte à gauche,
  guide à hauteur fixe, gestes au doigt ; puis centre fixe et synthèse à gauche. Vingt-six
  gestes rejoués dans Chromium, sans
  erreur de console : à 1 440 px en sombre et en clair, sur une tablette tactile de
  1 024 px, sur un téléphone de 390 px ; non essayés : contraste élevé, lecteur d'écran,
  Firefox, un vrai appareil. La case reste ouverte : elle se coche quand les linguistes
  l'ont vue
  **Troisième maquette publiée le 2026-10-22**, en session dédiée, avec les décisions
  d'`ANN-7` du même jour : page privée `https://claude.ai/artifact/3EXqt485Dv7SwwTRVogLuQ`,
  à une adresse NEUVE — la v2 reste telle quelle pour qui a son lien. Source hors du dépôt :
  `C:\temp\maquette-ann6\v3\source.html`, construite par `construire.py` (qui réinjecte les
  deux planches). Elle fait jouer, depuis une bande de maquette : la collection qui masque des
  grilles, les quatre cibles (la boîte et l'entité d'un personnage, la planche comme surface),
  la cardinalité, la passe commune et signée, le conflit sur une variante, les trois états
  d'un relevé (une transcription corrigée, une bulle liée supprimée puis rétablie), le
  vocabulaire neuf des Tags libres, l'activation libre d'une grille du catalogue (retirée de
  la page en cours de séance). Republiée onze fois le même jour, sur les retours de Hugo :
  la liste de ce qui est posé, le réglage des relevés affichés, « terminée » au pied, la
  Synthèse à l'échelle de la planche, le Contexte allégé, la sorte de locuteur et la grille
  « Lieux » (cf. « Tranché par Hugo — 2026-10-22, sur la maquette v3 »). Vérifiée à 1 440 px
  de large, 900 et 768 de haut, dans Chromium ; le glissé sur les mots aussi dans Firefox. Non
  essayés : tablette, téléphone, contraste élevé, lecteur d'écran. Retenu pour la tranche 2 :
  pendant un glissé, ne rien redessiner sous le pointeur — la maquette le faisait, 61 fois par
  seconde, et le relâchement s'y perdait **Validée par les linguistes le 2026-10-22**, rapporté par Hugo : la maquette v3 (`https://claude.ai/artifact/3EXqt485Dv7SwwTRVogLuQ`). Leur réponse sur le relevé à qualificatifs, le même jour : deux tags (cf. sa case)

### À trancher sur la maquette, avec les linguistes

- [x] **Le rendu des relevés sur les mots est choisi** — attendu : tranché. Hugo, le
  2026-10-14 : « Rendu grille active en couleur » — une teinte par rubrique, les autres
  grilles en gris. L'autre rendu (toutes les grilles empilées) quitte la maquette
- [x] **Un passage est continu ET peut sauter des mots** — attendu : confirmé par Hugo puis
  par les linguistes. Hugo a demandé si les deux se combinaient : ils se combinent, et
  c'est ce que la maquette fait désormais, sans réglage. Clic, glissé ou Maj+clic désignent
  un passage continu ; Ctrl+clic, ou « Ajouter un mot » au doigt, ajoute ou retire un mot
  isolé (« ne … pas »). Un passage à trou se trace sans trait sous les mots sautés, et se
  lit « son … il » dans la liste **Confirmé par les linguistes le 2026-10-22**, rapporté par Hugo, sur la maquette v3
- [x] **Un relevé à qualificatifs compte UNE fois son phénomène** — attendu : confirmé par les
  linguistes. La maquette pose « emphase par typographie et ponctuation » comme un seul
  relevé : 1 emphase, 1 typographie, 1 ponctuation. Le guide en fait deux tags, donc deux
  emphases **Non — répondu par les linguistes le 2026-10-22**, rapporté par Hugo : « deux tags ». « Emphase par typographie et ponctuation » compte DEUX emphases, comme le guide ; ce que la maquette faisait (un seul relevé, une emphase) ne vaut pas. Le modèle ne change pas (Hugo, même jour, case d'`ANN-7`) : la grille des linguistes écrira l'emphase par manière, une entrée chacune
- [ ] **Le chevauchement désigne l'autre bulle d'un clic** — attendu : confirmé. Un lien que
  l'outil tient remplace la référence écrite dans la Note, qui change quand l'ordre de
  lecture change (cf. « Avant que les stagiaires commencent »)
- [ ] **Le décompte dans la vue, l'aperçu de l'Exploration, ou les deux** — attendu : tranché.
  Hugo, le 2026-10-14 : « à voir ce qui semble le plus utile » ; la maquette montre les deux
- [ ] **Au doigt, la tablette et le téléphone se jouent sur un vrai appareil** — attendu : les
  gestes de la maquette essayés sur une tablette et un téléphone, et ce qui gêne écrit. Ce
  que la maquette propose : toucher un mot, puis « Étendre » et toucher le dernier pour un
  passage ; « Un détail » à choisir avant de glisser, pour ne pas bloquer le défilement ;
  sur téléphone, la grille monte du bas par « Poser… ». Simulé dans Chromium seulement.
  Sans survol, la ligne du guide ne suit que le dernier geste

### Le modèle — à cadrer avant tout code

- [x] **Le relevé est un objet à lui** — attendu : cadré. Une zone, une entrée de la grille,
  le premier et le dernier mot concernés (facultatifs : un contour de bulle n'en vise
  aucun), un doute, un commentaire ; plusieurs par zone, le même deux fois. Ni un tag, qui
  est présent ou absent, ni une ligne de `region_attribut`, dont la clé est le couple zone
  et valeur
  **Cadré le 2026-10-14** dans `docs/grilles-et-releves.md` (§3, §4) : une entrée, une version, une cible — des mots, une région entière ou la planche —, une variante ou des qualificatifs, une précision, un lien
- [x] **L'ancrage suit le patron des corrections de grammaire** — attendu : quand la
  transcription est corrigée, un relevé suit son mot s'il existe encore, sinon il est mis de
  côté et signalé à revoir — jamais perdu, jamais déplacé en silence. Le mécanisme existe
  pour `token_correction` (la forme visée, le drapeau d'obsolescence,
  `database._reancrer_corrections`). À dire aussi : ce que devient un relevé là où le moteur
  de langue est absent, donc sans mots à viser
  **Cadré le 2026-10-14** dans `docs/grilles-et-releves.md` (§5) : le découpage des mots est celui de l'outil (tranché par Hugo), ce qui règle le cas du moteur de langue absent ; un mot disparu met le relevé « à revoir »
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
- [x] **Sa place dans l'ordre des chantiers est décidée** — attendu : tranché par Hugo. De la
  taille de `COL-3`, à mener en tranches ; `COL-3` attend la fusion de sa tranche 1, et le
  premier des trois commits de sa tranche 2 est écrit, sur copie
  **Tranché par Hugo le 2026-10-14** : après `COL-3`, en quatre tranches, à partir de `docs/grilles-et-releves.md`

### Ce que `ANN-7` tranche ici — 2026-10-14

- [x] **Le relevé se pose avec une entrée de grille, au sens d'`ANN-7`** — attendu : le modèle du relevé cite celui des grilles. Hugo a tranché le 2026-10-14 un outil agnostique, à plusieurs grilles versionnées, partagées dans un catalogue, et un seul modèle où les tags et les attributs entrent aussi. Deux cases de cette fiche y trouvent leur réponse : « La grille entre dans le vocabulaire existant » — elle devient la première grille, et c'est le vocabulaire existant qui y entre — et « Ce qui aura été annoté en tags se convertit », dont la règle s'écrit chez `ANN-7`
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md`, note commune aux deux chantiers

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
