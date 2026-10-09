---
chantier: COL-3
statut: à venir
---

# COL-3 — le fonds et les projets : un album appartient à l'instance, un travail à ceux qui le font

**Point de départ** — 2026-10-09, en conversation, à partir du veto qu'`AUTH-10` venait de
mettre au jour. Hugo : *« Pour moi, il doit y avoir une sorte de back où tous les albums sont
stockés. Avec leurs origines et leurs utilisations dans différentes collections. Quitte à ce
qu'on considère que tout ce qui est ajouté sur BéDéditeur appartient à BéDéditeur, et que
les gestionnaires de collection soient en mode "j'ai des droits dessus dans la limite où
j'intègre ceci dans ma collection". »* Puis, le même jour : *« je me demande si on ne devrait
pas instituer cette notion de projet de manière plus institutionnelle, ou en tout cas plus
cadrée. On intègre des gens dans un projet à l'arrivée. Ce projet, c'est une couche
supérieure aux collections. Et les travaux effectués sur les différents albums peuvent être
partagés à l'intérieur de ce projet. On peut aussi définir quels albums entrent dans ce
projet, ou ne peuvent pas entrer. Et donc piocher dans une base de données ce qu'on souhaite
ajouter à telle ou telle collection. »*

**Trois étages, là où il y en a un et demi.** Le FONDS garde les documents — les scans et
leur notice —, qui appartiennent à l'instance. Un PROJET admet des personnes et des
documents : c'est le périmètre à l'intérieur duquel un travail PEUT se partager. Une
COLLECTION reste ce qu'elle est : une étude, une unité de dépôt, un cercle d'accès — à
l'intérieur d'un projet.

**L'unité n'est ni le projet ni la collection : c'est la COPIE DE TRAVAIL.** Aujourd'hui un
album n'a qu'UN travail (les régions tiennent à la planche, `annotations.region_id` est
UNIQUE, la transcription est une colonne de la région), partagé d'office par toutes les
collections où il est rangé — voulu, arbitrage du 2026-08-27, `AUTH-3` : « dupliquer l'album
casserait l'analyse inter-corpus ». Ce que la demande change est le « d'office ». Une
collection qui prend un document choisit : REJOINDRE le travail d'une autre collection du
projet — c'est le rangement d'aujourd'hui —, en partir par une COPIE, ou partir de ZÉRO.
Entre deux projets, seules les deux dernières existent. L'instance d'aujourd'hui est, sans
rien y changer, « le premier projet », où tout est partagé.

## Reste

### Posé par Hugo — 2026-10-09

- [x] **Tout album appartient à l'instance** — il vit dans un FONDS, avec son origine et ses emplois. Le fonds n'est pas une collection de plus : c'est l'ensemble des documents, dont certains ne sont appelés par personne
- [x] **Le PROJET est un étage au-dessus des collections** — on y intègre les gens à leur arrivée ; on décide quels albums y entrent, ou ne peuvent pas y entrer ; les collections du projet piochent dans ce qu'il a admis
- [x] **Le travail PEUT se partager à l'intérieur d'un projet, jamais d'office ; et pas entre deux** — précisé par Hugo le même jour, devant une phrase qui le disait partagé : *« Le travail PEUT se partager entre collections, non ? Pas obligatoirement ? »* La raison est celle qu'il avait donnée : *« on peut très bien utiliser un album pour travailler sur un sujet, tandis que d'autres travaillent sur une problématique qui n'a rien à voir, et on n'a pas envie qu'il y ait des interférences entre les deux, du bruit et du parasitage »*
- [x] **Intégrer un album n'est pas en recevoir le travail** — il arrive VIERGE, ou avec les couches produites ailleurs qu'on choisit d'y ajouter ; et ces couches ont des droits : *« tout le monde ne peut pas faire ce qu'il souhaite avec n'importe quel travail préexistant »*
- [x] **« Supprimer » a deux réponses** — « Supprimer de la collection » et « Supprimer définitivement ». La seconde existe parce qu'on importe parfois ce qui n'a rien à faire dans l'instance ; elle efface directement, ou envoie une demande à un administrateur
- [x] **La Recherche et l'Exploration prennent le projet pour critère** — c'est ce qui empêche de compter deux fois le texte d'un document que deux projets travaillent. Il ne suffit pas seul : deux copies du même document peuvent exister DANS un projet (case « Deux copies du même document se savent sœurs »)
- [x] **Rien de l'existant n'est à séparer** — selon Hugo, aucun usage ne repose aujourd'hui sur un album rangé dans plusieurs collections ; et l'existant entier devient le premier projet, où ce rangement reste permis

### La forme — à confirmer

- [ ] **La COPIE DE TRAVAIL est l'unité, et une collection choisit en prenant un document** — attendu : confirmé ou écarté par Hugo. Trois réponses, posées au moment du geste et jamais par défaut : *rejoindre* le travail d'une collection du projet (une seule copie, rangée dans les deux — le modèle d'aujourd'hui) ; *en partir* (une copie à soi, amorcée jusqu'au cran choisi) ; *partir de zéro*. Écartées, avec leur raison, en Contexte : une copie par collection OU par projet imposée à tous, les couches vivantes sur un même album, et le mi-chemin
- [ ] **Rejoindre un travail demande l'accord de qui le tient** — attendu : tranché, et c'est la réponse au veto d'`AUTH-10`. Aujourd'hui ranger chez soi ne demande que d'écrire dans l'album : quiconque le fait s'invite dans le travail, et retire aux autres le droit de le détruire. Si le partage est un CHOIX, il se consent des deux côtés
- [ ] **Ce que la séparation abandonne est accepté par écrit** — attendu : dit. Une correction faite dans une copie n'arrive pas dans l'autre : c'est le prix de « pas d'interférence », et c'est pourquoi le partage reste possible
- [x] **Quand le projet se construit** — **tranché par Hugo le 2026-10-09 : le plus tôt possible**, sans attendre qu'un second projet existe — *« pour éviter les malentendus, et permettre aussi l'interfaçage rapide de cette nouvelle notion »*. La session avait proposé de n'ouvrir l'étage qu'à l'arrivée d'un deuxième projet ; c'est écarté. Le code attend seulement la fusion vers `main`, pour ne pas y embarquer un changement de modèle ; la conception et la maquette n'attendent rien

### L'ordre — le projet d'abord visible, puis ce qu'il permet

- [ ] **La forme se tranche sur une maquette interactive, avant la première ligne de code** — attendu : Hugo a manipulé, et dit ce qu'il garde, de quatre écrans : le projet courant dans la Bibliothèque ; « prendre un document » avec ses trois réponses et l'échelle des couches ; les deux réponses à « supprimer » ; le fonds et les projets vus de l'administrateur. Première version publiée le 2026-10-09, jouable sous trois identités (administrateur, responsable de projet, membre) : https://claude.ai/artifact/9TPyMWof747CBYGCty4sNv — privée, à partager depuis la page pour qu'un autre que Hugo l'ouvre
- [ ] **Tranche 1 — le projet existe et se VOIT, et rien d'autre ne change** — attendu : tout l'existant est rangé dans un premier projet, nommé par Hugo ; son nom se lit sur les cinq surfaces ; un administrateur en crée un second et y fait entrer un compte ou un groupe ; une collection appartient à UN projet. Aucun test de comportement n'a eu à être retouché : c'est la preuve que la tranche n'a rien déplacé
- [ ] **Tranche 2 — le fonds** — attendu : un document a une identité distincte de ses copies de travail, son origine et ses emplois sont écrits à partir de ce jour, « supprimer » a ses deux réponses, et l'administrateur a l'écran du fonds avec les demandes en attente
- [ ] **Tranche 3 — prendre un document** — attendu : rejoindre (consenti), en partir (amorcé jusqu'à un cran), partir de zéro ; dans un projet et entre deux
- [ ] **Tranche 4 — ce qui parasite encore** — attendu : le vocabulaire et les personnages ont leur étage de projet, et la Recherche comme l'Exploration sont bornées au projet courant et ne comptent pas deux fois deux copies sœurs

### Le projet

- [ ] **Qui est dans un projet** — attendu : tranché. Proposition : le patron de `collection_acces`, un étage plus haut — un accès de projet se donne à un COMPTE ou à un GROUPE de l'annuaire, et l'on ne stocke toujours qu'une référence, jamais une appartenance (invariant d'`AUTH-1`). « Intégrer quelqu'un à son arrivée » est alors un geste de l'application, et un groupe d'étudiants entre d'un seul coup
- [ ] **Qui gère un projet** — attendu : nommé, avec ce qu'il peut. Un rôle entre l'administrateur de l'instance et le propriétaire d'une collection : admettre des documents, décider quelles collections existent, autoriser qu'on amorce depuis son travail ?
- [ ] **Une personne dans deux projets choisit dans lequel elle travaille** — attendu : dit, écran par écran. Un projet courant, lisible partout ; la Recherche et l'Exploration bornées à lui par défaut
- [ ] **Le vocabulaire et les personnages ont un étage de projet** — attendu : tranché. Un terme « global » est aujourd'hui visible de toute l'instance, et un personnage traverse les albums : c'est par là que deux projets se parasiteraient d'abord — ce qui fuit n'est pas un mot, c'est une grille d'analyse (`AUTH-2`, v24). Global à l'instance, au projet, ou local à une collection ?
- [ ] **Ce qui ne peut PAS entrer dans un projet** — attendu : qui le décide, et sur quoi. Un refus par document (ses droits, sa base légale) ou par projet ?
- [ ] **Les accès par collection restent, à l'intérieur du projet** — attendu : confirmé. Être dans un projet n'ouvre pas toutes ses collections : l'incubateur de `COL-1` est une collection fermée DANS un projet

### Les couches qu'on emporte en intégrant

- [ ] **Les couches s'empilent, donc se choisissent sur une ÉCHELLE** — attendu : la liste arrêtée. Proposition : les images seules · + le découpage (cases, bulles, ordre de lecture) · + la transcription · + la grammaire relue · + les annotations (notes, tags, attributs, locuteurs). Chaque cran suppose ceux d'en dessous — une note tient à une bulle
- [ ] **Qui autorise qu'on amorce depuis son travail** — attendu : tranché. Copier le travail d'un projet vers un autre le fait SORTIR du premier, comme un export : une décision du gestionnaire du projet, sur le patron de `DROIT-2` ?
- [ ] **Ce qu'une copie garde de sa provenance** — attendu : la copie dit de quel document elle vient, de quel projet elle a été amorcée, et jusqu'à quel cran ; le journal attribue toujours le travail copié à ceux qui l'ont fait
- [ ] **Le vocabulaire ne suit pas une copie** — attendu : dit, et son effet montré. Des tags d'un autre projet arriveraient posés et invisibles : le piège déjà décrit dans `COL-1`

### Supprimer

- [ ] **Quand « Supprimer définitivement » efface directement** — attendu : la règle. Proposition : quand personne d'autre ne dépend du document — aucun autre projet ne l'emploie, et personne d'autre que celui qui l'a importé n'y a travaillé. C'est l'import par erreur, et il ne doit pas attendre un administrateur
- [ ] **Sinon, c'est une DEMANDE, et une demande est un état** — attendu : le document porte qui demande, quand et pourquoi ; l'administrateur la voit dans le fonds et dans « À regarder », et répond par « détruire » ou « garder ». Aucune messagerie
- [ ] **Ce que devient le travail d'un projet qui retire un document** — attendu : tranché. Gardé au fonds (rattrapable, et l'instance grossit) ou détruit avec la copie ?
- [ ] **Une planche** — attendu : dit. Retirer une planche d'une copie de travail ne touche que ce projet ; le scan reste au fonds

### Le fonds

- [ ] **L'origine et les emplois sont ÉCRITS** — attendu : qui a importé, quand, dans quel projet d'abord ; chaque admission et chaque retrait, datés et attribués. Relevé le 2026-10-09 : `albums` ne porte que `date_import` ; `collection_album` n'a ni date ni auteur ; ni créer, ni ranger, ni sortir, ni supprimer un album n'est journalisé. L'existant ne se reconstitue pas
- [ ] **Le fonds a un écran, pour l'administrateur** — attendu : les documents, d'où ils viennent, quels projets les emploient, lesquels ne sont appelés par personne, les demandes de suppression en attente
- [ ] **Deux copies du même document se savent sœurs** — attendu : un identifiant de document, que la Recherche et l'Exploration lisent. Sans lui, qui lit deux collections dont chacune a sa copie compte deux fois le même texte ; avec lui, on dédoublonne, ou on COMPARE — deux travaux indépendants sur les mêmes bulles sont la matière d'un vrai accord inter-annotateurs, là où `ANN-5` ne mesure aujourd'hui que des révisions. À éprouver, pas à promettre
- [ ] **La consultation du fonds est tranchée contre le cloisonnement** — attendu : qui consulte, et ce qu'il voit. « 404, jamais 403 » existe pour que personne n'apprenne ce que le corpus contient hors de sa portée. Proposition : un gestionnaire de projet voit la NOTICE seule (titre, série, auteur) — ni images, ni travail, ni qui l'emploie

### Ce que le chantier fait aux autres

- [ ] **`AUTH-10` garde sa règle pour une copie PARTAGÉE** — attendu : dit chez lui. Une copie rangée dans deux collections reste possible, donc « détruire demande d'écrire dans toutes » reste vrai pour elle ; ce que le fonds change est QUI détruit pour de bon, et le partage consenti ferme le veto de qui range chez soi
- [ ] **`UX-18` dessine la Bibliothèque d'UN projet** — attendu : dit chez lui. Ses décisions tiennent ; s'y ajoutent le projet courant, l'entrée « piocher dans ce que le projet a admis », et les deux réponses à « supprimer »
- [ ] **L'export garde son titre** — attendu : vérifié. La collection reste l'unité de dépôt et le titre d'un export (`AUTH-11`) ; le projet n'en est pas un

## Contexte

### Ce qu'un essai a montré — 2026-10-09

Joué sur `22cc644` par un essai jetable : un album dont on retire tous les rangements, à la
main en base, se comporte déjà comme un album « au fonds ». Celui qui le possédait ne le
voit plus, ses planches lui répondent 404, il ne peut ni y toucher ni le ranger de nouveau ;
l'administrateur le voit, planches intactes ; l'export le refuse (409) ; et un rangement par
l'administrateur le rend à qui le lisait. Une seule garde s'y oppose aujourd'hui : le 409
« dernière collection » de `sortir_album`.

### Une piste de construction, lue dans le code et non éprouvée

La ligne `albums` d'aujourd'hui EST une copie de travail : tout le travail y tient par ses
planches. Il suffirait donc de lui donner deux attaches — le document dont elle vient, le
projet où elle vit — et d'interdire qu'une collection range la copie d'un autre projet.
« Rejoindre » est alors le rangement d'aujourd'hui, sans une ligne à changer ; « en partir »
et « partir de zéro » créent une nouvelle ligne pour le même document, amorcée ou vierge,
dans le projet comme entre deux. Les fichiers d'images seraient partagés entre copies, et ne
se détruiraient plus qu'au fonds.

### Les formes écartées

**Une règle unique, imposée à tous** — proposée deux fois par la session, retirée deux fois
devant Hugo. D'abord « une copie par COLLECTION, la collection est le projet » : elle
supprimait le rangement d'un album dans plusieurs collections, donc l'analyse à travers les
études d'un même projet. Puis « une copie par PROJET, partagée d'office entre ses
collections » : elle réimposait dans le projet l'interférence que la demande voulait
éviter. Les deux décidaient à la place de ceux qui travaillent.

**Des couches vivantes sur un même album** — plusieurs travaux côte à côte, chacun avec ses
droits. La lecture la plus littérale de « plusieurs couches disponibles », et la plus
lourde : chaque lecture, écriture, recherche, export et annulation gagne une dimension, et
une couche de notes dépend du découpage au-dessous.

**Le mi-chemin** — découpage et transcription communs à tous, interprétation propre à
chacun. Mais Hugo compte la reconnaissance et l'OCR parmi les couches, et le projet tient
déjà que normaliser une transcription est une INTERPRÉTATION (`NLP-3`).

### D'où vient ce chantier

`AUTH-10` a fermé le 2026-10-08 la suppression d'un album partagé depuis une seule de ses
collections, et sa relecture a trouvé l'envers de la règle : quiconque range l'album chez
soi retire aux autres le droit de le détruire. Hugo a répondu par le fonds, puis par les
couches, puis par le projet. Tout ce qui précède est de la conception lue dans le code :
rien n'est prototypé, et rien ne se code avant la fusion vers `main`.
