---
chantier: ANN-7
statut: à venir
---

# ANN-7 — les grilles d'annotation : un seul modèle, plusieurs vocabulaires, un catalogue

**Point de départ** — 2026-10-14. La grille des linguistes (cf. `ANN-6`) a posé une question
plus large qu'elle-même : l'outil annote-t-il avec CE vocabulaire, ou avec des vocabulaires ?
Discutée avec Hugo le même jour, sans rien coder : l'outil sera agnostique, accueillera
plusieurs grilles côte à côte, les partagera dans un catalogue où chacune entre si ses
responsables le décident, et n'aura qu'UN modèle — les tags et les attributs d'aujourd'hui y
entreront. Rien n'est écrit ; cette fiche garde ce qui est tranché et ce qui reste à cadrer.

## Reste

### Tranché par Hugo — 2026-10-14

- [x] **L'outil est agnostique** — attendu : tranché. Le code ne connaît aucun vocabulaire —
  ni un tag, ni un niveau, ni le mot « linguistique » — ; tout ce qui fait une grille est une
  donnée importée. Plusieurs grilles vivent côte à côte, et une même bulle reçoit des relevés
  de plusieurs. Le contenu est libre, les FORMES sont bornées : trois (simple, à variantes, à
  qualificatifs), et une forme nouvelle demande du code, une fois, pour toutes les grilles.
  Chaque grille est fermée (elle se coche, ses responsables seuls l'enrichissent) ou ouverte
  (elle s'enrichit pendant l'annotation, comme les tags libres). Hugo : « Je suis d'accord sur
  ce que tu décris pour le caractère agnostique »
- [x] **Un catalogue, où une grille entre par une case « Partager »** — attendu : tranché.
  Hugo : « il faut que les utilisateurs puissent choisir si leur grille entre dans le pot
  commun (une case à cocher sur le mode du "Partager", avec du versioning) », avec la crainte
  qui fonde les versions : « si on commence à utiliser un vocabulaire issu d'une autre
  personne, mais qu'elle fait évoluer la grille et modifie toute la lecture des images, ce
  serait compliqué »
- [x] **Une grille s'écrit dans un tableur, BD_ditor la vérifie et la garde** — attendu :
  tranché. Hugo : « Je vais suivre ta recommandation je pense ». Pas d'éditeur d'arborescence
  dans l'outil ; un écran de BILAN à l'import, cf. « Le modèle »
- [x] **Les responsables du projet publient les versions et cochent « Partager »** —
  attendu : tranché. Aucune validation préalable par un administrateur : il trie après coup.
  Hugo : « Quitte à ce qu'il y ait plein de proposition de vocabulaire, mais que je fasse le
  tri parfois. ça me parait plus simple »
- [x] **Une grille s'active sur le projet** — attendu : tranché. Toutes les collections d'un
  projet comptent avec les mêmes grilles. Hugo : « Sur le projet également je pense »
- [x] **Un seul modèle : les tags et les attributs d'aujourd'hui deviennent des grilles** —
  attendu : tranché. Hugo : « ok pour un seul modèle ». Le basculement a lieu quand le nouveau
  mode d'annotation remplace le panneau actuel, cf. « Un seul modèle »

### Le modèle — à écrire avant tout code

- [ ] **Les quatre objets sont définis** — attendu : écrit, avec leurs champs. La GRILLE (un
  nom, ses responsables, son projet, son état : brouillon, en usage, retirée) ; la VERSION (un
  état daté et figé, sa note de changement) ; la RUBRIQUE (range, s'imbrique, ordonnée ; on
  n'y pose rien) ; l'ENTRÉE (ce qu'on pose), avec un identifiant stable et invisible, un
  libellé, une définition, une structure, des exemples, une cible, un état
  **Posés le 2026-10-14** dans `docs/grilles-et-releves.md` (§2), avec leur rôle : grille, version, rubrique, entrée, variante, liste de qualificatifs, activation, relevé, doute, passe. Leurs champs s'écrivent avec la migration de la tranche 1 : la case se coche là
- [x] **Les trois formes d'entrée sont définies** — attendu : écrit, chacune avec son geste.
  Simple (posée ou non) ; à variantes (un phénomène, puis UNE variante des siennes) ; à
  qualificatifs (un phénomène, plus un ou plusieurs choix dans une liste PARTAGÉE entre
  plusieurs entrées). Une précision libre peut s'ajouter à une entrée. La grille des
  linguistes s'y range entière : à vérifier en l'important
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§3), avec la précision libre et le lien vers une autre zone
- [x] **La cible d'une grille est une donnée** — attendu : écrit. Des mots d'une zone, une
  zone entière, une case, un personnage, une planche : c'est ce qui laisse entrer dans le même
  modèle une grille d'oralité, des émotions de personnages et la situation d'une case
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§4) : une version déclare ce qu'elle vise, parmi huit sortes ; le détail devient un type de région
- [x] **Le doute n'est pas une entrée** — attendu : écrit. C'est une propriété de tout relevé,
  fournie par l'outil quelle que soit la grille, avec son commentaire. Le guide des
  linguistes le range comme un tag transversal
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§2, §8)
- [x] **Ce qu'une grille ne redéfinit pas se déclare « pris dans l'outil »** — attendu :
  écrit. Le premier niveau de la grille des linguistes (type de zone, locuteur, lieu) existe
  déjà dans l'outil
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§2)
- [ ] **Un exemple peut désigner un relevé du corpus** — attendu : tranché. Un exemple est du
  texte, ou un renvoi à un vrai relevé, qui s'ouvre en un clic ; le guide laisse plusieurs
  « [exemple du corpus] » vides
- [x] **Une version en usage ne se modifie pas en place** — attendu : écrit. On prépare la
  suivante, on la publie ; un relevé dit dans quelle version il a été posé. Effet de chaque
  changement : ajouter, renommer (l'identifiant tient), retoucher une définition (le sens
  bouge, la note de version le dit) n'abîment aucun relevé ; déplacer une entrée change les
  comptes par rubrique, passé compris ; supprimer une entrée employée est interdit, elle
  devient « retirée » ; fusionner reporte les relevés, tracé ; scinder met les relevés « à
  revoir » ; changer de forme met les relevés incomplets « à compléter »
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§6) : une version est un instantané complet, tranché par Hugo ; la montée de version d'un projet attend une tranche ultérieure
- [x] **Le tableur porte une colonne d'identifiants, et l'import rend un bilan** — attendu :
  écrit, sur le format d'import existant (`lexique_import.py`, `tools/vocabulaire-modele.csv`).
  Sans identifiant, un libellé renommé se lit comme une suppression suivie d'un ajout.
  L'écran de bilan prend les décisions du tableau des changements avant de publier :
  ajouts, renommages, et pour chaque entrée disparue qui a des relevés, « retirer, ou fusionner
  dans… ». BD_ditor réexporte la grille vers le tableur, identifiants compris
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§7) : les colonnes, le bilan avant publication, le réexport
- [ ] **Une coquille se corrige à l'écran** — attendu : tranché. Seule exception au tableur
  envisagée : une définition ou un exemple, qui ne touchent aucun relevé
- [ ] **Le guide des linguistes découle de la grille** — attendu : tranché. BD_ditor peut en
  produire les pages (rubriques, entrées, structures, exemples), pour qu'il ne soit plus tenu
  à côté

### Le catalogue et le partage

- [ ] **Seules les versions publiées se partagent** — attendu : écrit. Décochée par défaut, la
  case « Partager » laisse la grille à son projet, invisible des autres ; cochée, elle entre au
  catalogue et tout projet peut l'activer. Le brouillon reste chez ses auteurs
- [ ] **Un projet reste sur sa version et choisit quand passer à la suivante** — attendu :
  écrit. Il voit qu'une version neuve existe, lit son bilan pour SES relevés, et décide ;
  sans son accord, rien ne bouge — l'écran d'annotation montre les entrées et les définitions
  de sa version. Une campagne en cours ne voit pas sa grille changer sous elle
- [ ] **Décocher « Partager » ne retire rien à personne** — attendu : écrit. La grille sort
  du catalogue pour les nouveaux venus ; les projets qui l'emploient la gardent
- [ ] **Adapter une grille commune, c'est proposer ou dériver** — attendu : écrit. Proposer
  aux responsables, pour la version suivante ; ou dériver une grille neuve qui garde la trace
  de son origine et les identifiants des entrées héritées, donc comparable sur ce qu'elles
  partagent. Jamais modifier une grille commune pour son seul projet
- [ ] **La suppression suit l'emploi** — attendu : écrit. Une grille que nul autre projet
  n'emploie, son responsable la supprime ; employée ailleurs, elle ne peut que sortir du
  catalogue, et la supprimer se DEMANDE à un administrateur. Le tri de l'administrateur suit la
  même règle
- [ ] **Désactiver une grille dans un projet ne supprime aucun relevé** — attendu : écrit.
  Ils restent, en lecture
- [ ] **Les relevés sortent avec leur grille et sa version** — attendu : cadré. Une lecture
  faite en v1 reste interprétable quand la grille en est à la v5 ; la grille sort dans un
  format standard (SKOS, comme le lexique aujourd'hui), et une grille venue d'ailleurs peut
  entrer au catalogue. Ce pan touche ce qui SORT : relecture croisée
- [x] **Qui voit le plan d'une grille réservée** — attendu : tranché. Une grille non partagée
  est un travail de recherche, et son seul plan peut révéler une étude en cours : la même
  question qu'aux termes d'une collection, un étage plus haut (`clause_terme`)
  **Tranché par Hugo le 2026-10-14** : quiconque lit un album du projet où la grille est active (`docs/grilles-et-releves.md`, §10). Être membre du projet n'est pas exigé, pas plus que pour annoter

### Un seul modèle : ce qui existe y entre

- [ ] **Les trois vocabulaires d'aujourd'hui ont leur place de grille** — attendu : écrit.
  Les tags libres : une grille ouverte, de forme simple, sur la zone. La situation d'une
  case : une grille à variantes sur la case. Le profil d'un personnage : une grille à
  variantes sur le personnage. Le vocabulaire d'étude proposé dans `ANN-1` : une grille de
  plus. Le lexique situé (définition, note de portée, état) devient ce que porte une entrée
- [ ] **Le coût de la réécriture est mesuré** — attendu : chaque lecteur des tags et des
  attributs relevé, avec un ordre de grandeur. Le coût n'est pas dans les données mais dans
  le code : Recherche et index plein texte, Exploration (distribution, croisement,
  concordance), exports (CSV, JSON, TEI, SKOS), lexique et import du tableur, annulation,
  cloisonnement des termes, registre des personnages. Une lecture du code, sans passe de
  tests
- [ ] **Ce que la production porte déjà est compté** — attendu : nombres de tags, de tags
  posés, d'attributs et d'affectations, sur la production. Des utilisateurs en ont posé ; peu,
  sans doute. Commande à préparer pour Hugo, qui seul a la main sur le serveur
- [ ] **Ce que les stagiaires poseront en attendant se convertit** — attendu : la règle est
  écrite avant leur premier jour. Ils commencent dans quelques semaines, sans doute avant le
  nouveau mode : ce qu'ils poseront sera des tags, à convertir au basculement (cf. `ANN-6`)
- [ ] **La réindexation plein texte se paie une fois** — attendu : tranché. L'index agrège
  les tags d'une région (`tags_concat`), et la limite écrite sous `AUTH-11` attend la
  prochaine migration forcée de l'index pour être reprise : le basculement en est une

### L'ordre

- [x] **Sa place face à `ANN-6` et `COL-3` est décidée** — attendu : tranché par Hugo. Le
  relevé d'`ANN-6` se pose avec une entrée de grille, donc après le modèle ; le catalogue
  et le fonds de `COL-3` partagent le patron du pot commun, et gagnent à être conçus ensemble
  **Tranché par Hugo le 2026-10-14** : `COL-3` d'abord (fusion de sa tranche 1, puis sa tranche 2), puis le modèle des grilles, en quatre tranches (`docs/grilles-et-releves.md`, §1). Commits sur `dev`, sans push, chacun après revue
- [x] **La cible « planche » attend le modèle d'`IMG-2`, ou le tranche** — attendu : avant que la tranche 1 fige « la planche » comme cible d'une entrée, dit si c'est la PAGE (unité imprimée, numérotée, citée) ou la SURFACE (le repère où vivent les régions). Ouvert le 2026-10-16 : `docs/images-pages-surfaces.md` propose de séparer image, page et surface, que la planche confond aujourd'hui ; les régions changeraient alors de repère **Tranché par Hugo le 2026-10-16, dans `IMG-2` : la cible « planche » est la SURFACE** — pour une double page, la double page entière, que l'écran nomme « la planche (ou la double page) » ; une cible « page » viendra si une grille en a besoin

## Contexte

### D'où cela vient

Le 2026-10-13, une maquette du mode d'annotation faite depuis la session de pilotage n'a
pas convaincu Hugo (cf. `ANN-6`). En y repensant, il a posé la question de fond : la grille
des linguistes est un vocabulaire conçu en amont ; est-ce LE vocabulaire de l'outil, une
nomenclature partagée partout, un vocabulaire qu'on change, qu'on choisit à l'entrée d'un
projet ? Peut-on en ajouter un autre, d'un tout autre système ? Puis : ajouter un niveau,
des tags, en supprimer, sont des actions à penser en amont — et passent-elles par l'outil ou
par le tableur qu'on lui fait lire ?

La discussion a avancé par six réponses, dans l'ordre : agnostique ; un catalogue où l'on
entre par « Partager », versionné ; le tableur pour écrire ; les responsables publient,
l'administrateur trie après coup ; activation sur le projet ; un seul modèle.

### Ce que l'outil a, lu le 2026-10-14

Trois vocabulaires, câblés partout : les tags (un libellé libre, unique dans l'instance, à
plat), les attributs de situation (une case) et de profil (un personnage), rangés en domaine,
dimension et valeur. Tous portent une portée — globale, ou propre à une collection — et le
lexique situé : définition, note de portée, état. Un vocabulaire s'importe d'un tableur,
collection par collection, en préremplissant sans écraser. Il n'existe aucun objet
« grille » : une grille importée se dissout dans ce pot commun. Le projet, depuis `COL-3`,
se nomme et se règle, et ne porte aucun vocabulaire.

### Ce qui a été écarté, et pourquoi

Un vocabulaire unique pour l'instance : elle accueille plusieurs projets, qui n'annotent pas
avec la même grille. Un vocabulaire par collection : une étude couvre souvent plusieurs
collections, la grille y serait recopiée et les comptes ne s'additionneraient plus. Un
éditeur de grilles complet dans l'outil : un vrai chantier, et deux sources à tenir alignées
avec le guide. Des formes libres : ce serait un éditeur d'ontologies, sans fond. Suivre
automatiquement la dernière version d'une grille partagée : la crainte de Hugo, une lecture
changée sous les pieds d'une équipe.
