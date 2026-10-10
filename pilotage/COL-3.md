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

### Précisé par Hugo — 2026-10-10

- [x] **Importer soi-même dans son projet ne demande rien, et le document rejoint le fonds** — Hugo, devant « faire entrer un document dans son projet se demande à un administrateur » : *« à part si ce sont les personnes qui intègrent directement dans leur projet, on est d'accord ? et ça rejoint le pot commun ? »* La demande ne porte donc que sur un document DÉJÀ au fonds, que le projet n'a pas. Un import entre dans le projet de qui importe sans attendre personne, et appartient à l'instance dès cet instant : sa notice devient lisible des responsables des autres projets, qui peuvent le demander
- [x] **Une entrée de documents porte PLUSIEURS albums à la fois** — *« que l'ajout soit possible avec plusieurs albums à chaque fois »*. On en coche plusieurs dans le fonds, et la demande — ou l'admission, quand c'est un administrateur qui agit — part en une fois
- [x] **La demande se dépose aussi à la CRÉATION d'un projet** — *« histoire qu'on ait une demande unique avec plein d'albums potentiellement »*. Qui la dépose, et à quel instant, reste à trancher : case « Qui dépose la demande de départ d'un projet », zone « Le fonds »
- [x] **La création d'un projet se DEMANDE, et la demande porte sa justification** — *« La demande de création de projet est aussi une demande qui doit pouvoir accueillir une justification, notamment scientifique. N'importe qui ne doit pas pouvoir y accéder je pense »*. Un projet ne naît donc pas seulement du geste d'un administrateur : il se demande, par un texte libre qui dit pourquoi, et cette demande n'est pas ouverte à tout compte. Ce que « y accéder » borne — déposer la demande, lire la justification, ou les deux — et à qui, reste à trancher dans la même case

### La forme — à confirmer

- [x] **La COPIE DE TRAVAIL est l'unité, et une collection choisit en prenant un document** — attendu : confirmé ou écarté par Hugo. Trois réponses, posées au moment du geste et jamais par défaut : *rejoindre* le travail d'une collection du projet (une seule copie, rangée dans les deux — le modèle d'aujourd'hui) ; *en partir* (une copie à soi, amorcée jusqu'au cran choisi) ; *partir de zéro*. Écartées, avec leur raison, en Contexte : une copie par collection OU par projet imposée à tous, les couches vivantes sur un même album, et le mi-chemin **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [x] **Rejoindre un travail demande l'accord de qui le tient** — attendu : tranché, et c'est la réponse au veto d'`AUTH-10`. Aujourd'hui ranger chez soi ne demande que d'écrire dans l'album : quiconque le fait s'invite dans le travail, et retire aux autres le droit de le détruire. Si le partage est un CHOIX, il se consent des deux côtés **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [ ] **Ce que la séparation abandonne est accepté par écrit** — attendu : dit. Une correction faite dans une copie n'arrive pas dans l'autre : c'est le prix de « pas d'interférence », et c'est pourquoi le partage reste possible
- [x] **Quand le projet se construit** — **tranché par Hugo le 2026-10-09 : le plus tôt possible**, sans attendre qu'un second projet existe — *« pour éviter les malentendus, et permettre aussi l'interfaçage rapide de cette nouvelle notion »*. La session avait proposé de n'ouvrir l'étage qu'à l'arrivée d'un deuxième projet ; c'est écarté. Le code attend seulement la fusion vers `main`, pour ne pas y embarquer un changement de modèle ; la conception et la maquette n'attendent rien

### L'ordre — le projet d'abord visible, puis ce qu'il permet

- [x] **La forme se tranche sur une maquette interactive, avant la première ligne de code** — attendu : Hugo a manipulé, et dit ce qu'il garde, de quatre écrans : le projet courant dans la Bibliothèque ; « prendre un document » avec ses trois réponses et l'échelle des couches ; les deux réponses à « supprimer » ; le fonds et les projets vus de l'administrateur. Première version publiée le 2026-10-09, jouable sous trois identités (administrateur, responsable de projet, membre) : https://claude.ai/artifact/9TPyMWof747CBYGCty4sNv — privée, à partager depuis la page pour qu'un autre que Hugo l'ouvre **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [ ] **Tranche 1 — le projet existe et se VOIT, et rien d'autre ne change** — attendu : tout l'existant est rangé dans un premier projet, nommé par Hugo ; son nom se lit sur les cinq surfaces ; un administrateur en crée un second et y fait entrer un compte ou un groupe ; une collection appartient à UN projet. Aucun test de comportement n'a eu à être retouché : c'est la preuve que la tranche n'a rien déplacé
- [ ] **Tranche 2 — le fonds** — attendu : un document a une identité distincte de ses copies de travail, son origine et ses emplois sont écrits à partir de ce jour, « supprimer » a ses deux réponses, et l'administrateur a l'écran du fonds avec les demandes en attente
- [ ] **Tranche 3 — prendre un document** — attendu : rejoindre (consenti), en partir (amorcé jusqu'à un cran), partir de zéro ; dans un projet et entre deux
- [ ] **Tranche 4 — ce qui parasite encore** — attendu : le vocabulaire et les personnages ont leur étage de projet, et la Recherche comme l'Exploration sont bornées au projet courant et ne comptent pas deux fois deux copies sœurs

### Tranche 1 — ce qui se tranche avant le code (propositions de la session, 2026-10-10)

- [ ] **Le nom du premier projet** — attendu : donné par Hugo. Proposition : la migration le fait naître « Projet principal », et Hugo le renomme à l'écran ; ce nom n'est écrit en dur nulle part ailleurs
- [ ] **Qui est membre du premier projet au départ** — attendu : tranché. Proposition : tout compte ou groupe qui a déjà un accès à une collection, recopié par la migration ; personne ne perd l'écran qu'il avait
- [ ] **Ce que peut le responsable d'un projet en tranche 1** — attendu : tranché, et « Qui gère un projet » fermée pour cette tranche. Proposition : faire entrer, faire sortir, nommer un autre responsable ; créer, renommer et supprimer restent à l'administrateur, et la fiche du projet dit au responsable que sa suppression se demande à lui
- [ ] **Ce que borne le projet courant en tranche 1** — attendu : tranché. Proposition : la Bibliothèque seule ; la Recherche et l'Exploration attendent la tranche 4
- [ ] **Une collection ne change pas de projet** — attendu : tranché. Proposition : aucun geste ne la déplace en tranche 1
- [ ] **Ranger un album dans une collection d'un AUTRE projet est refusé** — attendu : tranché. Proposition : refusé dès la tranche 1, par un refus qui le nomme ; c'est ce qui garantit qu'à l'arrivée du fonds chaque copie de travail n'a qu'un projet
- [ ] **Le nom d'un projet a un plafond court** — attendu : la longueur, mesurée sur la barre du haut à 320 px et à grande police. Proposition : 22 à 24 caractères
- [ ] **Où se gèrent les projets** — attendu : tranché. Proposition : un bloc « Projets » dans l'Administration, sans onglets
- [ ] **Le projet porte sa justification dès la tranche 1** — attendu : tranché. Proposition : une colonne de `projet` dès le schéma v29, saisie par l'administrateur qui crée le projet, lue des administrateurs et des responsables ; la DEMANDE qui la portera arrive avec le mécanisme de la tranche 2, et trouve la colonne déjà là — une migration de moins
- [ ] **Ce que le guide en dit** — attendu : tranché. Proposition : une phrase en tête de `docs/guide-utilisateur.md` ; le reste s'écrit avec la tranche qui donne au projet un effet

### Le projet

- [ ] **Qui est dans un projet** — attendu : tranché. Proposition : le patron de `collection_acces`, un étage plus haut — un accès de projet se donne à un COMPTE ou à un GROUPE de l'annuaire, et l'on ne stocke toujours qu'une référence, jamais une appartenance (invariant d'`AUTH-1`). « Intégrer quelqu'un à son arrivée » est alors un geste de l'application, et un groupe d'étudiants entre d'un seul coup
- [ ] **Qui gère un projet** — attendu : nommé, avec ce qu'il peut. Un rôle entre l'administrateur de l'instance et le propriétaire d'une collection : admettre des documents, décider quelles collections existent, autoriser qu'on amorce depuis son travail ?
- [ ] **Une personne dans deux projets choisit dans lequel elle travaille** — attendu : dit, écran par écran. Un projet courant, lisible partout ; la Recherche et l'Exploration bornées à lui par défaut
- [ ] **Le vocabulaire et les personnages ont un étage de projet** — attendu : tranché. Un terme « global » est aujourd'hui visible de toute l'instance, et un personnage traverse les albums : c'est par là que deux projets se parasiteraient d'abord — ce qui fuit n'est pas un mot, c'est une grille d'analyse (`AUTH-2`, v24). Global à l'instance, au projet, ou local à une collection ?
- [ ] **Ce qui ne peut PAS entrer dans un projet** — attendu : qui le décide, et sur quoi. Un refus par document (ses droits, sa base légale) ou par projet ?
- [ ] **Un responsable DEMANDE la suppression de son projet** — attendu : confirmé par Hugo. Sa phrase du 2026-10-10 : *« D3 : demande de suppression possible aussi par les responsables des projets, non ? »* — lue par la session comme la suppression du PROJET (c'est d'elle que parlait la décision qu'il commentait), et rendue ainsi à Hugo, qui a poursuivi sans la reprendre. La demande passe par le mécanisme de la tranche 2 (case « Une demande est UN mécanisme »)
- [x] **Les accès par collection restent, à l'intérieur du projet** — attendu : confirmé. Être dans un projet n'ouvre pas toutes ses collections : l'incubateur de `COL-1` est une collection fermée DANS un projet **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**

### Les couches qu'on emporte en intégrant

- [ ] **Les couches s'empilent, donc se choisissent sur une ÉCHELLE** — attendu : la liste arrêtée. Proposition : les images seules · + le découpage (cases, bulles, ordre de lecture) · + la transcription · + la grammaire relue · + les annotations (notes, tags, attributs, locuteurs). Chaque cran suppose ceux d'en dessous — une note tient à une bulle
- [x] **Qui autorise qu'on amorce depuis son travail** — attendu : tranché. Copier le travail d'un projet vers un autre le fait SORTIR du premier, comme un export : une décision du gestionnaire du projet, sur le patron de `DROIT-2` ? **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »** Retenu : le RESPONSABLE du projet d'où l'on part donne son accord
- [ ] **Ce qu'une copie garde de sa provenance** — attendu : la copie dit de quel document elle vient, de quel projet elle a été amorcée, et jusqu'à quel cran ; le journal attribue toujours le travail copié à ceux qui l'ont fait
- [ ] **Le vocabulaire ne suit pas une copie** — attendu : dit, et son effet montré. Des tags d'un autre projet arriveraient posés et invisibles : le piège déjà décrit dans `COL-1`

### Supprimer

- [x] **Quand « Supprimer définitivement » efface directement** — attendu : la règle. Proposition : quand personne d'autre ne dépend du document — aucun autre projet ne l'emploie, et personne d'autre que celui qui l'a importé n'y a travaillé. C'est l'import par erreur, et il ne doit pas attendre un administrateur **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [x] **Sinon, c'est une DEMANDE, et une demande est un état** — attendu : le document porte qui demande, quand et pourquoi ; l'administrateur la voit dans le fonds et dans « À regarder », et répond par « détruire » ou « garder ». Aucune messagerie **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [x] **Ce que devient le travail d'un projet qui retire un document** — attendu : tranché. Gardé au fonds (rattrapable, et l'instance grossit) ou détruit avec la copie ? **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »** Retenu : gardé au fonds avec son travail, et un administrateur peut le rendre
- [ ] **Une planche** — attendu : dit. Retirer une planche d'une copie de travail ne touche que ce projet ; le scan reste au fonds

### Le fonds

- [ ] **L'origine et les emplois sont ÉCRITS** — attendu : qui a importé, quand, dans quel projet d'abord ; chaque admission et chaque retrait, datés et attribués. Relevé le 2026-10-09 : `albums` ne porte que `date_import` ; `collection_album` n'a ni date ni auteur ; ni créer, ni ranger, ni sortir, ni supprimer un album n'est journalisé. L'existant ne se reconstitue pas
- [ ] **Le fonds a un écran, pour l'administrateur** — attendu : les documents, d'où ils viennent, quels projets les emploient, lesquels ne sont appelés par personne, les demandes de suppression en attente
- [ ] **Deux copies du même document se savent sœurs** — attendu : un identifiant de document, que la Recherche et l'Exploration lisent. Sans lui, qui lit deux collections dont chacune a sa copie compte deux fois le même texte ; avec lui, on dédoublonne, ou on COMPARE — deux travaux indépendants sur les mêmes bulles sont la matière d'un vrai accord inter-annotateurs, là où `ANN-5` ne mesure aujourd'hui que des révisions. À éprouver, pas à promettre
- [x] **La consultation du fonds est tranchée contre le cloisonnement** — attendu : qui consulte, et ce qu'il voit. « 404, jamais 403 » existe pour que personne n'apprenne ce que le corpus contient hors de sa portée. Proposition : un gestionnaire de projet voit la NOTICE seule (titre, série, auteur) — ni images, ni travail, ni qui l'emploie **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [ ] **Une demande est UN mécanisme, pour trois usages** — attendu : tranché. Proposition : faire entrer des documents dans un projet, supprimer un document, supprimer un projet — le même état (qui demande, quand, pourquoi), la même place dans « À regarder », construit une fois, en tranche 2
- [ ] **Qui dépose la demande de départ d'un projet** — attendu : tranché par Hugo. Deux lectures de « à la création d'un projet ». (a) L'administrateur crée le projet et nomme son responsable ; celui-ci trouve, à sa première ouverture d'un projet encore vide, « quels documents du fonds voulez-vous ? », et dépose UNE demande ; l'administrateur qui crée peut aussi en admettre lui-même, dans le même geste. (b) Quelqu'un qui n'a pas encore de projet demande d'un seul coup le projet ET ses documents — ce qui lui ouvre les notices du fonds, que la case « La consultation du fonds » réserve aux responsables. ~~Proposition : (a)~~ **Hugo, le 2026-10-10 : le projet lui-même se demande, avec une justification, et pas par n'importe qui** — c'est (b), bornée, et la proposition de la session est écartée. Restent : QUI peut déposer (proposition : qui porte déjà une responsabilité dans l'instance — responsable d'un projet ou propriétaire d'une collection ; un nouveau venu passe par un administrateur, qui crée le projet et saisit la justification pour lui) ; QUI lit la justification (proposition : les administrateurs et les responsables du projet, pas ses membres) ; et si la demande de projet emporte ses albums ou si ceux-ci se demandent une fois le projet accepté — seul un responsable voit aujourd'hui les notices où les choisir
- [ ] **Comment l'administrateur répond à une demande de plusieurs documents** — attendu : tranché. Proposition : document par document, avec un « tout accepter » ; une demande peut finir acceptée en partie, et le dit à qui l'a déposée

### Les passes de QA que chaque tranche périme

- [ ] **Tranche 1 — la barre du haut est rejouée à l'étroit et à grande police** — attendu : `petites-largeurs` et `preference-de-police` rejouées sur leurs cases de barre, une fois le nom du projet (ou son sélecteur) posé sur les cinq surfaces. À 320 et 375 px, et à grande police, il ne fait sortir de la fenêtre ni la navigation, ni le menu « Aa », ni la pastille d'identité : c'est la bande où il reste le moins de place, et un nom de projet ne se coupe pas
- [ ] **Tranche 1 — la carte d'accueil dit le projet, ou dit pourquoi non** — attendu : tranché, et `accueil-par-ou-commencer` rejouée si son texte change. Un arrivant entre désormais dans un projet avant d'entrer dans une collection
- [ ] **Tranche 2 — `supprimer-n-est-pas-sortir` est RÉÉCRITE, pas rejouée** — attendu : une passe neuve pour les deux réponses à « supprimer ». La corbeille et le ✕ qu'elle vérifie aujourd'hui sont ce que la tranche remplace
- [ ] **Tranches 2 et 3 — `collections-bibliotheque` est rejouée sur ses gestes d'album** — attendu : rejouée. « Ranger ici » devient « prendre un document », et sortir un album de sa dernière collection cesse d'être refusé
- [ ] **Tranche 3 — le projet a SA passe** — attendu : écrite, non cochée. Qui entre dans un projet, ce qu'il admet, ses trois réponses ; `qui-entre` et `comptes-et-groupes` restent vraies pour la collection, mais ne disent rien de l'étage au-dessus
- [ ] **Tranche 4 — `import-bilan-refus` et `termes-illisibles` sont rejouées** — attendu : rejouées. Le menu « Portée » et « Importer dans » gagnent le projet, et « global » ne veut plus dire toute l'instance

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

### Ce que le chantier fait aux passes qui restent à jouer — relevé le 2026-10-09

Demandé par Hugo, au moment où il joue les passes d'avant la fusion. **Aucune n'est touchée
aujourd'hui** : rien de ce chantier n'est codé, et rien ne le sera avant la fusion. Les sept
passes qui ont encore des cases ouvertes — `accueil-par-ou-commencer`, `import-bilan-refus`,
`petites-largeurs`, `preference-de-police`, `supprimer-n-est-pas-sortir`, et les reliquats
d'`export-depot` et de `referent-instance` — vérifient le code tel qu'il part en production,
et se jouent telles qu'elles sont écrites.

Ce qui change vient APRÈS, tranche par tranche, et la zone « Les passes de QA que chaque
tranche périme » le range. Deux choses à savoir en les jouant maintenant. `petites-largeurs`
et `preference-de-police` seront à rejouer en partie dès la première tranche — sur la barre
du haut seulement, le reste tient. Et `supprimer-n-est-pas-sortir` a une durée de vie
courte : elle garde une règle qui part en production à la fusion, donc elle se joue, mais la
deuxième tranche remplacera les gestes qu'elle vérifie. `export-depot`, `droit-export` et
`referent-instance` ne sont pas concernées : la collection reste l'unité de dépôt et le
titre d'un export.

### Une piste de construction, lue dans le code et non éprouvée

La ligne `albums` d'aujourd'hui EST une copie de travail : tout le travail y tient par ses
planches. Il suffirait donc de lui donner deux attaches — le document dont elle vient, le
projet où elle vit — et d'interdire qu'une collection range la copie d'un autre projet.
« Rejoindre » est alors le rangement d'aujourd'hui, sans une ligne à changer ; « en partir »
et « partir de zéro » créent une nouvelle ligne pour le même document, amorcée ou vierge,
dans le projet comme entre deux. Les fichiers d'images seraient partagés entre copies, et ne
se détruiraient plus qu'au fonds.

### Le cadrage de la tranche 1 — 2026-10-10, lu dans le code et non éprouvé

Rendu par un agent en lecture seule, sur `3cac8aa`. Rien n'en est codé, et les décisions
qu'il suppose sont les cases de la zone « Tranche 1 — ce qui se tranche avant le code ».

**Le modèle** (schéma v29). Deux tables neuves : `projet` (`id`, `nom`, `description`,
`repli`, `date_creation`) et `projet_acces` (`projet_id`, `genre`, `principal`, `role`,
`date_creation`), sur le patron de `collection_acces`. `collection.projet_id` reste
NULLABLE, et `NULL` se lit « le projet de repli » — une fonction à écrire à côté de
`database.collection_par_defaut`, sur un drapeau `repli = 1`. Deux raisons, relevées : SQLite
n'ajoute pas une colonne `NOT NULL` par `ALTER`, et dix-neuf tests créent une collection par
un `INSERT` brut.

**La règle** vit dans `autorisation.py` et nulle part ailleurs : deux rôles (membre,
responsable), ce que la `Portee` sait des projets où l'on est et de ceux qu'on gère, et les
questions qui vont avec. Être d'un projet n'ouvre ni ne ferme aucune collection — c'est la
case « Les accès par collection restent, à l'intérieur du projet ».

**Les routes** : un module `routes/projets.py` — lister, créer, renommer, supprimer un
projet ; lire et régler ses membres — et un accesseur gardé de plus dans `socle.py`.
`GET /api/moi` ne gagne rien : un test y compare la réponse entière. `projet` et
`projet_acces` rejoignent `CIBLES_RETENUES` dans `tools/_commun.py` : rien d'elles ne sort de
l'instance.

**L'écran** : le nom du projet dans la barre commune aux cinq surfaces (`static/theme.js`) —
le nom seul quand on n'en a qu'un, un `<select>` natif dès deux ; le projet courant gardé par
navigateur, en stockage local ; un bloc « Projets » dans l'Administration ; les membres par
un module montable, sur la convention de `qui-entre.js`.

**Deux commits de code** — le modèle, la règle et les routes ; puis l'écran. **La preuve de
la tranche** se mesure : `git diff --diff-filter=M --name-only` sur `tests/` ne doit rendre
que `tests/test_sorties_identite.py` et `tests/test_e2e_masquage.py`, deux cliquets qui
DÉCLARENT ce qui est neuf. Un test de comportement modifié voudrait dire que la tranche a
déplacé quelque chose.

**Ce que les précisions de Hugo du 2026-10-10 n'y changent pas** : la demande groupée, le
choix de plusieurs albums et l'import qui rejoint le fonds supposent le fonds, donc les
tranches 2 et 3. En tranche 1 un projet neuf naît vide, et un album y entre comme
aujourd'hui, par l'import dans une de ses collections.

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
