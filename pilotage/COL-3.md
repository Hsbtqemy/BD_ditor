---
chantier: COL-3
statut: interrompu
---

# COL-3 — le fonds et les projets : un album appartient à l'instance, un travail à ceux qui le font

**Arrêté sur** — 2026-10-17, `3205426` : **le cadrage de la tranche 3 est entièrement tranché**
(D1 à D12 ; D10 contre la proposition d'abord écrite : la collection de base), et le serveur de la
3a a commencé — la v31 et la collection de base sont sur `dev`, relues et corrigées. Reste le
commit 2 (prendre au fonds, les demandes d'entrée, rejoindre consenti), puis l'écran, sans lequel
la 3a ne part pas en production. La passe `administration-a-l-echelle` attend Hugo.

**Plus tôt le 2026-10-16** — `bd5dff1` : **la tranche 2 est en production depuis le
2026-10-16** (`main` avancé de `b387080` à `5e7f56b`, déployé par Hugo) : schéma 30, cinq
albums et cinq documents, aucun album sans document, `AUTOINCREMENT` sur les quatre tables ;
le timer relancé répond « rien à faire ». Avant : les passes `supprimer-n-est-pas-sortir`
(71/71) et `collections-bibliotheque` (32/32) jouées par Hugo sur la recette, la suite (1 780)
et la passe navigateur (517) vertes dans l'image sur `5e7f56b`. Deux retouches d'écran
relevées pendant la passe sont parties avec (↗ sous `UX-3`, la pastille `bd5dff1`). Ce qui
vient ensuite : l'Administration à l'échelle, sur maquette, AVANT la tranche 3.

**Plus tôt le 2026-10-16** — arrêté sur `99eae43` : la tranche 2 sur `dev`, poussée, la
suite par défaut verte (1 869) ; restaient sa documentation, ses passes réécrites, la
recette, les passes de Hugo et les passes dans l'image.

**Plus tôt le 2026-10-11** — arrêté sur `79da8c4` : la tranche 1 est codée, et trois retouches de ses écrans aussi
(`79da8c4`, décrites dans les cases qu'elles ferment). Ses trois commits de code sont sur
`dev` — le projet EXISTE (`6c3e19f` : modèle, règle, routes, schéma v29), il se VOIT
(`9eec56e` : la bande du haut des cinq surfaces, la Bibliothèque bornée au projet courant,
le bloc « Projets » de l'Administration), et sa finition est faite (`7eabeb7` : les deux
listes de la Bibliothèque suivent le projet, la description et la justification se
modifient). Le plafond du nom, que la mesure a ramené de
24 à 21 caractères, est confirmé par Hugo, et les documents sont écrits. Restent : les
passes de QA, reportées par Hugo le soir du 2026-10-10 pour poursuivre sur le code — la recette les attend, arrêtée, sa base migrée ; et, avant la fusion vers `main`, la suite et la passe
navigateur DANS l'image. Ce que chaque commit a mesuré est en Contexte.

**D'où part le chantier** — 2026-10-09, en conversation, à partir du veto qu'`AUTH-10` venait de
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
- [x] **La création d'un projet se DEMANDE, et la demande porte sa justification** — *« La demande de création de projet est aussi une demande qui doit pouvoir accueillir une justification, notamment scientifique. N'importe qui ne doit pas pouvoir y accéder je pense »*. Un projet ne naît donc pas seulement du geste d'un administrateur : il se demande, par un texte libre qui dit pourquoi ~~, et cette demande n'est pas ouverte à tout compte. Ce que « y accéder » borne — déposer la demande, lire la justification, ou les deux — et à qui, reste à trancher dans la même case~~ **Lecture de la session, démentie par Hugo le même jour** : *« Non, ce n'était pas ce que j'entendais par là. Depuis l'extérieur, si on n'a pas de compte, on peut demander la création d'un compte et la création d'un projet. Mais ça doit être justifié de fait. »* « Y accéder » parlait de l'INSTANCE : on n'y entre pas sans avoir dit pourquoi, et c'est la justification qui filtre, pas une liste de qui a le droit de demander
- [x] **Sans compte, on peut demander un compte ET un projet, et la demande est justifiée** — Hugo, le 2026-10-10 (phrase ci-dessus). C'est la première chose de l'instance qu'atteindrait quelqu'un qui n'y a pas de compte : ce qu'elle coûte et sa forme sont la case « La demande venue de l'extérieur », zone « Le projet »

### La forme — à confirmer

- [x] **La COPIE DE TRAVAIL est l'unité, et une collection choisit en prenant un document** — attendu : confirmé ou écarté par Hugo. Trois réponses, posées au moment du geste et jamais par défaut : *rejoindre* le travail d'une collection du projet (une seule copie, rangée dans les deux — le modèle d'aujourd'hui) ; *en partir* (une copie à soi, amorcée jusqu'au cran choisi) ; *partir de zéro*. Écartées, avec leur raison, en Contexte : une copie par collection OU par projet imposée à tous, les couches vivantes sur un même album, et le mi-chemin **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [x] **Rejoindre un travail demande l'accord de qui le tient** — attendu : tranché, et c'est la réponse au veto d'`AUTH-10`. Aujourd'hui ranger chez soi ne demande que d'écrire dans l'album : quiconque le fait s'invite dans le travail, et retire aux autres le droit de le détruire. Si le partage est un CHOIX, il se consent des deux côtés **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [ ] **Ce que la séparation abandonne est accepté par écrit** — attendu : dit. Une correction faite dans une copie n'arrive pas dans l'autre : c'est le prix de « pas d'interférence », et c'est pourquoi le partage reste possible
- [x] **Quand le projet se construit** — **tranché par Hugo le 2026-10-09 : le plus tôt possible**, sans attendre qu'un second projet existe — *« pour éviter les malentendus, et permettre aussi l'interfaçage rapide de cette nouvelle notion »*. La session avait proposé de n'ouvrir l'étage qu'à l'arrivée d'un deuxième projet ; c'est écarté. Le code attend seulement la fusion vers `main`, pour ne pas y embarquer un changement de modèle ; la conception et la maquette n'attendent rien

### L'ordre — le projet d'abord visible, puis ce qu'il permet

- [x] **La forme se tranche sur une maquette interactive, avant la première ligne de code** — attendu : Hugo a manipulé, et dit ce qu'il garde, de quatre écrans : le projet courant dans la Bibliothèque ; « prendre un document » avec ses trois réponses et l'échelle des couches ; les deux réponses à « supprimer » ; le fonds et les projets vus de l'administrateur. Première version publiée le 2026-10-09, jouable sous trois identités (administrateur, responsable de projet, membre) : https://claude.ai/artifact/9TPyMWof747CBYGCty4sNv — privée, à partager depuis la page pour qu'un autre que Hugo l'ouvre **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [x] **Tranche 1 — le projet existe et se VOIT, et rien d'autre ne change** — attendu : tout l'existant est rangé dans un premier projet, nommé par Hugo ; son nom se lit sur les cinq surfaces ; un administrateur en crée un second et y fait entrer un compte ou un groupe ; une collection appartient à UN projet. Aucun test de comportement n'a eu à être retouché : c'est la preuve que la tranche n'a rien déplacé **Premier commit fait le 2026-10-10, `6c3e19f` : le modèle, la règle et les routes ; la preuve tient pour lui (un seul fichier de test existant modifié, le cliquet des sorties d'identité, sans une ligne retirée). La case reste ouverte jusqu'au second commit, qui fait VOIR le projet.** **Second commit fait le 2026-10-10, `9eec56e`, et la case se ferme sur sa preuve** : sur les deux commits, les seuls fichiers de test existants modifiés sont les deux cliquets attendus — `tests/test_sorties_identite.py` et `tests/test_e2e_masquage.py` —, 33 lignes ajoutées, aucune retirée, aucune vérification touchée. Suite par défaut : 1 536 passés avant la tranche, 1 593 après, dans l'arbre partagé. Passe navigateur entière sous Chromium, dans la copie : 381 passés. Ce que la preuve ne dit pas : ce que l'écran DIT à qui le regarde — c'est la passe `projet-visible`, à jouer par Hugo
- [x] **La description et la justification d'un projet ne se modifient par aucun écran** — attendu : tranché. Relevé le 2026-10-10 en écrivant le guide : la fiche d'un projet n'offre que « Renommer » et « Supprimer le projet », alors que la route les accepte toutes deux et que la description de naissance du premier projet dit « Renommez-le, et décrivez-le ». Une justification se saisit donc à la création, et ne se corrige plus. Proposition : deux champs de plus dans « Ce projet », pour qui décide des projets — dans le même petit commit que les deux listes de la Bibliothèque **Fait le 2026-10-10, `7eabeb7`.** Deux champs et un « Enregistrer » dans « Ce projet », pour qui décide des projets ; le responsable n'en reçoit aucun. La requête ne porte que ce qui a changé, un champ vidé efface son texte, et « Rien n'a changé. » se dit sans requête
- [x] **Tranche 1 — deux listes de la Bibliothèque proposent encore les collections de TOUS les projets** — attendu : tranché. Le sélecteur « Collection » de la modale « Nouvel album » et « + Ranger ici » ne sont pas bornés par le projet courant : la décision ne nommait que la liste des collections et le projet où l'on crée. Ranger à travers deux projets répond le 409 nommé du serveur, pas un silence — mais c'est offrir un choix dont on connaît le refus, le défaut qu'`AUTH-12` a déjà fermé pour les collections où l'on n'écrit pas. Sans effet tant qu'il n'existe qu'un projet. Proposition : les borner au projet courant, dans un petit commit avant la tranche 2 **Fait le 2026-10-10, `7eabeb7`, sur le « oui » de Hugo.** « Collection », dans « + Nouvel album », suit le projet COURANT ; « + Ranger ici » suit le projet de l'ALBUM, lu dans ses collections — la liste des albums n'est pas bornée par le projet, on peut ouvrir la fiche d'un album d'un autre. Chacune DIT ce qu'elle écarte, et ne dit rien quand rien n'est écarté. Un projet où l'on n'écrit dans aucune collection n'a pas de liste vide mais une phrase, et « Enregistrer » y est arrêté par l'écran : la requête partirait sinon sans collection, et le serveur rangerait l'album dans la collection de repli, donc dans un AUTRE projet que celui affiché. Un album dont les collections seraient de deux projets (base retouchée à la main) ne se voit rien proposer, et l'écran dit par quels ✕ en sortir. Aucun changement de serveur. Suite par défaut : 1 600 passés dans l'arbre partagé ; passe navigateur entière sous Chromium, dans la copie : 397 passés ; Firefox, les tests de la tranche, aux polices 16 et 24 ; quarante-cinq mutants, tous tombés. Aucun fichier de test antérieur à la tranche n'est modifié
- [x] **La phrase du responsable ne dit pas tout ce qu'il ne peut pas** — attendu : tranché. « Le renommer ou le supprimer se demande à un administrateur de l'instance » ne dit pas à qui demander de corriger la description ou la justification, qu'il lit et ne modifie pas. Laissée telle quelle au commit de finition : le guide et la passe `projet-visible` la citent **Fait le 2026-10-11, `79da8c4`.** Elle dit maintenant : « Vous réglez qui entre dans ce projet. Le renommer, corriger sa description ou sa justification, ou le supprimer se demande à un administrateur de l'instance. » Le guide et la passe la citent telle quelle
- [x] **La confirmation d'« Enregistrer » se lit loin de son bouton** — attendu : jugé à l'écran par Hugo. Vu sur une capture du commit de finition : la ligne de message de « Ce projet » est sous « Supprimer le projet » et sa note, quatre lignes plus bas que le bouton qu'on vient d'actionner. Une case de la passe `projet-visible` le fait regarder **Fait le 2026-10-11, `79da8c4`.** Mesuré d'abord : à 1 280 px, le message de « Renommer » commençait 292 px sous son bouton. Chaque geste de « Ce projet » a désormais SA ligne, rendue avec la fiche — sous « Renommer », sur la rangée d'« Enregistrer », sous « Supprimer le projet » — ; « un seul message à la fois » tient toujours. La case de la passe qui demandait d'en juger est réécrite
- [x] **Tranche 1 — les documents disent le projet** — attendu : écrits après le second commit de code, dans un commit à eux. `CLAUDE.md` (schéma 29, les questions d'autorisation qui passent de dix à quatorze, le tableau des surfaces, les modules de `static/lib/`), `docs/modele-et-droits.md`, `docs/guide-utilisateur.md` (la phrase de tête confirmée par Hugo), `docs/hebergement-securite.md`. D'ici là `CLAUDE.md` annonce encore le schéma 28, et c'est faux sur `dev` depuis `6c3e19f` **Fait le 2026-10-10, `50c22c1`** : `CLAUDE.md`, `docs/modele-et-droits.md`, `docs/guide-utilisateur.md` et `docs/hebergement-securite.md`, écrits par un agent neuf sur une copie, relus, et la suite par défaut entière rejouée avec eux (1 593 passés). Les questions d'autorisation sont bien quatorze, et le client en reçoit SIX : `gerable` est la seule réponse neuve. Deux phrases devenues fausses sont corrigées avec leur trace datée — « créer une collection n'exige qu'une identité », vrai dans le seul projet de repli ; et « une seule route lit l'annuaire », qui en compte trois, la dernière ouvrant les NOMS des groupes à un responsable de projet. Laissé, parce que la dérive n'est pas de ce chantier : `CLAUDE.md` annonce `main.py` à 1 811 lignes, il en fait 2 398 ; et les chiffres du cliquet des sorties d'identité n'ont pas été recomptés
- [x] **La tranche 1 se voit et se fusionne AVANT que le code de la tranche 2 n'arrive sur `dev`** — attendu : les passes jouées par Hugo, la suite et la passe navigateur jouées dans l'image, la fusion vers `main` faite, PUIS le premier commit de code de la tranche 2. Proposé par la session et accepté par Hugo le 2026-10-11 (« ok »), pour deux raisons : le projet devait se voir « le plus tôt possible » — sur `dev`, personne ne le voit — ; et la tranche 2 change le schéma une seconde fois, deux migrations enchaînées en production sans qu'aucune ait été vue à l'écran étant le risque à éviter. Le CADRAGE de la tranche 2 et ses décisions n'attendent pas : ils se font pendant ce temps, en lecture seule — **Fait le 2026-10-15** : les passes jouées par Hugo (`projet-visible` 33/33, et cinq autres du lot), la suite et la passe navigateur dans l'image vertes sur `b387080` (1 616 et 502 passés), `main` avancé de `68edccd` à `b387080`, déployé par Hugo : schéma 29, un projet, aucune collection sans projet, cinq membres. Le code de la tranche 2 peut maintenant arriver sur `dev`
- [ ] **Tranche 2 — le fonds** — attendu : un document a une identité distincte de ses copies de travail, son origine et ses emplois sont écrits à partir de ce jour, « supprimer » a ses deux réponses, et l'administrateur a l'écran du fonds avec les demandes en attente
- [ ] **Tranche 3 — prendre un document** — attendu : rejoindre (consenti), en partir (amorcé jusqu'à un cran), partir de zéro ; dans un projet et entre deux
- [x] **Tranche 3 — les albums que montrent la Bibliothèque et l'Atelier sont ceux du projet
  courant** — attendu : écrit dans le cadrage de la tranche 3, puis fait. Relevé par Hugo le
  2026-10-15 en jouant `projet-visible` : dans un projet neuf, la Bibliothèque montre Esther v1,
  qu'on ne peut pourtant ranger dans aucune de ses collections (le rangement ne traverse pas
  les projets). Aucune tranche ne nommait ces deux listes : la tranche 4 borne la Recherche et
  l'Exploration, pas elles. Placé en tranche 3 sur le mot de Hugo, parce que c'est elle qui
  donne un sens à « les albums de ce projet » — avant elle, un projet neuf n'a presque rien à
  montrer. À dire avec : le lot, qui ne connaît pas non plus le projet
  **Écrit dans le cadrage** (`docs/col3-tranche3-cadrage.md`, commit « 0 ») **puis fait par `2d80473`** (2026-10-17, sur copie, relu et vérifié par-dessus `dev`) : `GET /api/albums` publie le projet LU de chaque album (`sql_projet_d_album`) ; la Bibliothèque, son lot et l'Atelier ne montrent que les albums du projet courant, par une fonction pure de `static/lib/projet.js` sous table de vérité ; un lien de l'Atelier vers un album d'un autre projet qu'on lit fait basculer le projet courant, comme `/corpus?collection=`. Filtre d'écran, pas garde. Onze mutants tués ; une course dans un test existant de l'autre onglet, rendue plus probable, corrigée par `2e9db0b`
- [ ] **Tranche 3 — « repartir de zéro » sur un album** — attendu : cadré avec la tranche 3.
  Hugo, le 2026-10-15 : on a pu poser des choses sur des planches « uniquement pour tester »,
  et vouloir repartir de zéro. C'est le geste inverse de « partir de zéro » : revenir à un cran
  de l'échelle des couches (images seules, découpage, transcription, annotations) en gardant
  les images. Même protection que supprimer : directement si personne d'autre n'y a travaillé,
  sinon une demande, avec la même certification
- [ ] **Tranche 4 — ce qui parasite encore** — attendu : le vocabulaire et les personnages ont leur étage de projet, et la Recherche comme l'Exploration sont bornées au projet courant et ne comptent pas deux fois deux copies sœurs

### Tranche 1 — ce qui se tranche avant le code (propositions de la session, 2026-10-10)

- [x] **Le nom du premier projet** — attendu : donné par Hugo. Proposition : la migration le fait naître « Projet principal », et Hugo le renomme à l'écran ; ce nom n'est écrit en dur nulle part ailleurs **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Qui est membre du premier projet au départ** — attendu : tranché. Proposition : tout compte ou groupe qui a déjà un accès à une collection, recopié par la migration ; personne ne perd l'écran qu'il avait **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Ce que peut le responsable d'un projet en tranche 1** — attendu : tranché, et « Qui gère un projet » fermée pour cette tranche. Proposition : faire entrer, faire sortir, nommer un autre responsable ; créer, renommer et supprimer restent à l'administrateur, et la fiche du projet dit au responsable que sa suppression se demande à lui **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Ce que borne le projet courant en tranche 1** — attendu : tranché. Proposition : la Bibliothèque seule ; la Recherche et l'Exploration attendent la tranche 4 **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Une collection ne change pas de projet** — attendu : tranché. Proposition : aucun geste ne la déplace en tranche 1 **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Ranger un album dans une collection d'un AUTRE projet est refusé** — attendu : tranché. Proposition : refusé dès la tranche 1, par un refus qui le nomme ; c'est ce qui garantit qu'à l'arrivée du fonds chaque copie de travail n'a qu'un projet **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Le nom d'un projet a un plafond court** — attendu : la longueur, mesurée sur la barre du haut à 320 px et à grande police. Proposition : 22 à 24 caractères **Le principe est confirmé par Hugo le 2026-10-10 (« ok pour les 10 ») : un plafond, 24 caractères en attendant.** La case reste ouverte jusqu'à la MESURE, qui fixe la valeur au second commit de code. **MESURÉ le 2026-10-10, au second commit : 24 ne tient pas, la constante vaut 21.** Le pire coin est 320 px de large, une préférence de police de 24, deux projets visibles (le nom est alors dans un sélecteur, qui prend 26 à 29 px) et la police de l'image, DejaVu Sans : la bande laisse 249 px au texte du nom. Vingt et une capitales de français courant en demandent 238 — 12 px de marge sous Chromium, 14 sous Firefox ; vingt-deux tombent à 0 ; vingt-quatre sortent de 20 à 23 px. Il a fallu pour cela rendre le nom à la taille des petits textes sous 28em. Ce que 21 coûte : « Séminaire émotions 2026 » (23) est refusé, « Corpus franco-belge » (19) et « Projet principal » (16) passent. Ce qu'il ne garantit pas, et aucun plafond en caractères ne le ferait : un nom chargé de m, de M ou de W sort encore de ce coin-là. Reste ouvert jusqu'au mot de Hugo sur 21 **Confirmé par Hugo le 2026-10-10 : 21 caractères.** Sa réponse, à la question « tu le gardes ? » posée avec la mesure : « deux oui »
- [x] **Où se gèrent les projets** — attendu : tranché. Proposition : un bloc « Projets » dans l'Administration, sans onglets **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Le projet porte sa justification dès la tranche 1** — attendu : tranché. Proposition : une colonne de `projet` dès le schéma v29, saisie par l'administrateur qui crée le projet, lue des administrateurs et des responsables ; la DEMANDE qui la portera arrive avec le mécanisme de la tranche 2, et trouve la colonne déjà là — une migration de moins **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**
- [x] **Ce que le guide en dit** — attendu : tranché. Proposition : une phrase en tête de `docs/guide-utilisateur.md` ; le reste s'écrit avec la tranche qui donne au projet un effet **Confirmé par Hugo le 2026-10-10 : « ok pour les 10 ».**

### Tranche 2 — ce qui bloque le code (propositions du cadrage, 2026-10-11)

- [x] **Où s'arrête la tranche : faire ENTRER des documents, maintenant ou à la suivante** — attendu : tranché par Hugo. Étroite : le fonds de l'administrateur, les deux réponses à « supprimer », les demandes de suppression ; tout ce qui fait entrer — la notice ouverte aux responsables, la demande de plusieurs albums, la demande à la création d'un projet — part avec « prendre un document ». Large : s'y ajoutent la notice, la demande groupée et l'admission, environ la moitié en plus, et un document « admis » ne pourrait encore être pris par aucune collection pendant toute une tranche. Proposition : étroite, le mécanisme de demande étant construit pour recevoir plusieurs documents **Tranché par Hugo le 2026-10-11 : la proposition, telle quelle (« Oui pour les 5 »).**
- [x] **Quand « Supprimer définitivement » efface sans rien demander** — attendu : tranché par Hugo. Ses mots : aucun autre projet n'emploie le document, et personne d'autre que celui qui l'a importé n'y a travaillé. La maquette était plus stricte sans le dire : elle exigeait aussi qu'il ne soit rangé que dans UNE collection. Le cas qui les sépare : importé par moi, rangé dans deux de mes collections, personne d'autre n'y a touché. Proposition : ses mots, la règle d'aujourd'hui (écrire dans toutes ses collections) étant gardée. « Y a travaillé » se lit dans le journal : un travail supprimé depuis ne compte plus, une reconnaissance automatique lancée par un collègue ne compte pas **Tranché par Hugo le 2026-10-11 : la proposition, telle quelle (« Oui pour les 5 »).**
- [x] **Les albums déjà là, dont personne ne sait qui les a importés** — attendu : tranché par Hugo. Ce n'est écrit nulle part et ne se reconstitue pas. Inconnu veut dire « demander » : sur tout l'existant, seul un administrateur détruit ; ou l'ancienne règle pour les anciens albums, travail des autres compris ; ou un importateur désigné album par album, un geste de plus à construire. Proposition : la première **Tranché par Hugo le 2026-10-11 : la proposition, telle quelle (« Oui pour les 5 »).**
- [x] **Supprimer une planche** — attendu : tranché par Hugo. La maquette n'en dit rien ; aujourd'hui cela efface son scan pour tout le monde. Proposition : la règle du document, sans demande — on supprime une planche là où l'on pourrait supprimer le document, sinon l'écran dit de s'adresser à un administrateur ; « retirer la planche de sa copie en gardant le scan » suppose deux copies, donc la tranche 3 **Tranché par Hugo le 2026-10-11 : la proposition, telle quelle (« Oui pour les 5 »).**
- [x] **La demande de suppression d'un projet par son responsable, dans cette tranche** — attendu : tranché par Hugo ; ferme aussi la case « Un responsable DEMANDE la suppression de son projet ». Proposition : oui, ici — un bouton dans la fiche, un motif, une ligne dans « À regarder » ; l'administrateur accepte ou refuse, et le projet n'est supprimé que vide. Un projet qui garde des documents au fonds ne se supprime pas **Tranché par Hugo le 2026-10-11 : la proposition, telle quelle (« Oui pour les 5 »).**

### Tranche 2 — une question de Hugo qui ouvre une décision — 2026-10-11

- [x] **Comment un administrateur fait entrer un album au fonds sans passer par une collection** — attendu : tranché par Hugo. Sa question, en confirmant les cinq décisions : *« comment les administrateurs font pour ajouter des albums au pot commun ? »* Relevé dans le cadrage : RIEN ne le permet. Un album entre au fonds parce qu'on l'importe dans une collection, administrateur compris ; il n'y est « appelé par personne » qu'après avoir été retiré de toutes. Charger d'avance un corpus pour des projets à venir demanderait donc une collection d'attente, puis un retrait album par album. Proposition : un geste « Importer au fonds » sur l'écran du fonds, réservé aux administrateurs — l'album naît sans collection ni projet, « appelé par personne », et le geste « Rendre à… » du même écran le range ensuite dans une collection. Ce que cela coûte : la création d'un album sans collection, que le serveur n'accepte pas aujourd'hui (il retombe sur la collection de repli), et la règle qui dit de quel projet est une copie qui n'en a jamais eu. À chiffrer avant de l'ajouter à la tranche ; l'import en nombre, lui, est le chantier `UX-11` **Tranché par Hugo le 2026-10-11 : « Oui, on ajoute ce bouton. »** « Importer au fonds » entre dans la tranche 2, sur l'écran du fonds, pour les administrateurs ; avec « Rendre à… », il donne dès cette tranche un chemin entier — charger le corpus, puis le distribuer. Le cadrage ne le chiffrait pas : l'agent qui codera le deuxième commit le mesure d'abord, et dit ce que devient la règle « de quel projet est une copie » pour celle qui n'en a jamais eu

### Tranche 2 — ce qui peut se trancher en route (propositions du cadrage, 2026-10-11)

- [ ] **Le fonds dans l'Administration : un bloc de plus, ou des onglets** — proposition : un bloc, sous « Projets »
- [ ] **Le nom de qui demande se lit par tous ceux qui lisent la collection** — proposition : oui, comme la maquette (« suppression demandée par … ») : on a besoin de savoir à qui parler
- [ ] **Le « pourquoi » d'une demande est obligatoire** — proposition : oui ; la maquette acceptait une demande vide
- [ ] **Après « Garder », ce que voit celui qui avait demandé** — proposition : sa pastille disparaît, il peut redemander, et l'administrateur voit qu'une demande a déjà été refusée
- [ ] **Retirer sa propre demande** — proposition : pas dans cette tranche
- [ ] **Supprimer une collection dont certains albums ne sont que là** — proposition : garder le refus d'aujourd'hui et corriger sa phrase, plutôt que d'envoyer ces albums au fonds d'un coup
- [ ] **Un compte partagé qui importe** — proposition : il ne supprime jamais définitivement tout seul, « celui qui l'a importé » n'y désignant personne
- [x] **L'Atelier crée ses albums dans la collection de repli, pas dans le projet où l'on travaille** — proposition : il demande dans quelle collection, comme la Bibliothèque ; sans quoi l'origine écrite est fausse pour qui travaille dans un second projet
  Fermée avec la case du même nom de la zone « relevé par son premier commit » : l'Atelier ne crée plus d'albums (`250799a`, `1c72ecd`)
- [ ] **Importer compte-t-il comme du travail laissé quand un compte s'en va** — proposition : non pour l'instant ; l'importateur reste lisible dans le fonds
- [ ] **La phrase d'avertissement de « Qui entre »** — « Supprimer un album efface ses images et ne se rattrape pas » n'est plus vraie que pour « Supprimer définitivement » : à reformuler
- [ ] **L'administrateur et le mono-poste voient encore le texte d'un document retiré** dans la Recherche et l'Exploration, jusqu'à la tranche 4 — proposition : l'accepter, et l'écrire

### Tranche 1 — trouvé par la passe navigateur dans l'image (2026-10-11)

- [x] **Le formulaire « Nouveau projet » déborde de son bloc à 320 px sous une préférence de 24, sous une police plus large que Segoe UI** — attendu : `#pj-creer` tient dans `#projets-bloc`. Mesuré dans l'image, où la page rend DejaVu Sans : 268 px de contenu pour 260 de boîte (244 sur le poste, qui tenait). La piste implicite de la grille ne descendait pas sous la largeur propre du champ du nom ; le `min-width: 0` du champ ne pouvait rien tant que sa piste ne rétrécissait pas. **Fermée par `9e1f768`** (`minmax(0, 1fr)`), mutant rejoué dans l'image : piste remise à `auto`, 268 / 260. Non expliqué : sous la même police servie au poste, le champ fait 306 px et non 268. Preuve : passe navigateur entière dans une image reconstruite depuis le dernier des trois commits, sans montage : 434 passés, 5 ignorés, 0 échec ; la même sur le poste (Chromium) : 434 passés
- [x] **`test_nommer_un_responsable_puis_le_faire_sortir` tombe une fois sur quatre dans l'image** — attendu : il passe à chaque rejeu, sans rien cesser de vérifier. Ce n'était ni un tri ni une mise en page : rejoué SEUL dans l'image sur `869726c`, 25 fois, 19 verts et 6 rouges (quatre sur « lectrice » en première ligne, deux sur « membre » lu au serveur) ; 25 verts sur 25 sur le poste. Trois lectures s'enchaînaient sans rien attendre : la valeur de la liste déroulante vaut « responsable » dès le clic, l'attente de la requête rend la main quand elle PART, et la liste ne se redessine qu'après l'écriture puis sa relecture. **Fermée par `9e1f768`** : le test attend d'abord la liste redessinée ; 25 verts sur 25 dans l'image finale, et il tombe encore si la liste n'est pas redessinée après le geste (mutant rejoué). Non cherché : la même course dans d'autres tests

### Tranche 2 — relevé par son premier commit et sa relecture croisée, sur copie (2026-10-11)

- [x] **La tranche 2 ne part en production qu'une fois son deuxième commit écrit** — attendu : tranché par Hugo. Le cadrage disait que le premier commit, qui porte la migration v30, pouvait partir seul : « plus tôt il est déployé, plus tôt les origines s'écrivent ». La relecture croisée objecte qu'il fige deux tables, celles des demandes, qu'aucun code n'a encore écrites : tout regret trouvé en écrivant leurs routes coûterait une seconde migration. Elle en a trouvé un tout de suite — une demande ne gardait pas le NOM de son projet, dont l'identifiant se réattribue —, corrigé sur la copie avant que le schéma ne parte. Proposition : attendre le deuxième commit
  Sans objet : la tranche entière, ses trois commits et les décisions du 15, est sur `dev` depuis le 2026-10-16 (`99eae43`), et partira d'un bloc
- [x] **L'Atelier crée ses albums dans la collection de repli : dès la v30, leur origine écrite est celle du projet de repli** — attendu : tranché AVANT le déploiement de la v30, et non en route. C'est le point « L'Atelier crée ses albums dans la collection de repli » de la zone du dessus, que le premier commit rend pressant : l'origine d'un document s'écrit une fois, à sa naissance, et renverser la décision plus tard ne corrige pas les origines déjà écrites
  **Tranché par Hugo le 2026-10-15 : l'Atelier ne crée plus d'albums.** Un album se crée dans la Bibliothèque, avec sa collection ; l'Atelier y importe ses planches (`250799a`), et le serveur refuse toute création par l'import ShareDocs (`1c72ecd`)
- [ ] **Un import depuis ShareDocs dont l'écriture au journal échoue laisse ses images sur le disque** — attendu : dit, ou fermé. Provoqué artificiellement par la relecture : la route répond 500, la transaction est défaite, et les fichiers de l'album restent dans `corpus/` et `derivatives/` sans album. Aucun déclencheur réaliste trouvé, la transaction tenant déjà le verrou d'écriture à cet instant ; l'auteur suppose, sans l'avoir mesuré, qu'un `commit` qui lève au même endroit laisse le même état depuis toujours
- [ ] **Le projet d'ORIGINE d'un document ne garde pas son nom** — attendu : posé par la migration de la tranche 3, avant le premier projet supprimé sous un document vivant. Une demande garde le nom de son projet ; l'origine d'un document, non, par décision écrite sur la colonne : dans la tranche 2 un document n'a qu'une copie, elle porte ce même projet, et un projet que des copies désignent ne se supprime pas — le document part donc avant lui. C'est un raisonnement, pas un test

### Tranche 2 — relevé par son deuxième commit et sa relecture croisée, sur copie (2026-10-14)

- [x] **Qui lit le nom de qui demande une suppression** — attendu : tranché par Hugo. La
  proposition « en route » disait « lu par tous ceux qui lisent la collection » ; le code le
  rend à quiconque lit l'ALBUM, par n'importe laquelle de ses collections. Mesuré par la
  relecture : une personne qui n'écrit que dans l'Incubateur, et y demande la suppression d'un
  album partagé, est nommée aux lectrices du corpus principal — plus qu'« une autre collection,
  jamais laquelle », seule révélation qu'`AUTH-10` acceptait. Proposition : tout lecteur voit
  qu'une suppression est demandée ; seuls un administrateur et la personne elle-même voient
  qui l'a demandée
  **Tranché par Hugo le 2026-10-15 : la troisième voie** — tout lecteur voit qu'une suppression est demandée, seuls un administrateur et la personne elle-même voient qui. **Fait par `5bbb65f`** (`Portee.peut_nommer_le_demandeur`, comparaison sur le login), vérifié par la relecture sur toutes les routes GET et sept identités
- [x] **Un compte partagé ne supprime jamais définitivement seul** — attendu : tranché par Hugo.
  Suivi « en route » dans le code, et c'est une doctrine écrite qui bouge : « la nature d'un
  compte ne borde aucun droit, `autorisation.py` n'en sait rien ». Elle borde désormais un
  GESTE, et toujours aucun accès : « celui qui l'a importé » ne désigne personne derrière un
  compte partagé. Proposition : oui
  **Tranché par Hugo le 2026-10-15 : oui.** Déjà dans le code ; derrière un compte partagé, le détail montré à l'administrateur le dit (`46c9cee`)
- [x] **Qualifier une case compte comme « laisser des actes » au départ d'un compte** — attendu :
  tranché par Hugo. La pose d'un attribut de case s'écrit désormais au journal, pour que la
  règle de suppression la voie ; elle compte donc aussi dans « Comptes et groupes », et un
  compte qui n'a fait que qualifier des cases passe de « rien à orpheliner » à « laisse des
  actes ». Proposition : oui, c'est du travail
  **Tranché par Hugo le 2026-10-15 : oui**, avec en plus ce que les autres ont fait, montré à l'administrateur sous chaque demande, et une certification obligatoire de qui demande (`03c075b`)
- [x] **Les identifiants des régions et des planches ne se réutilisent plus, dès la v30** —
  attendu : tranché par Hugo. Sans `AUTOINCREMENT`, la région créée après la suppression de la
  dernière reprend son identifiant, n'importe où : la règle de suppression, qui lit le journal
  par identifiant, refusait alors à tort (un acte d'un ancien album attribué à une région
  neuve), et Ctrl+Z traversait le cloisonnement (corrigé à part, sans attendre la v30).
  Mesuré sur un prototype non commité : environ soixante lignes de migration, 0,30 s sur
  80 000 régions, la suite entière verte sans un test modifié ; le compteur s'amorce sur le
  plus grand identifiant que le journal ait jamais nommé, sans quoi les identifiants détruits
  avant la migration seraient rendus une dernière fois. L'autre voie — ne compter que les
  actes postérieurs à la création de la région — coûte à chaque affichage, garde un trou et ne
  règle pas Ctrl+Z. Proposition : la v30, tant qu'elle n'est pas déployée
  **Tranché par Hugo le 2026-10-15 : oui**, étendu aux albums et aux personnages. **Fait par `c56c4f4`**, le compteur amorcé sur `evenement` ET `activite`, et pour les albums sur les dossiers d'images du disque (`f54626f`, décision de Hugo du 2026-10-16) ; un dossier trouvé au numéro d'un album neuf est mis de côté (`0630486`), ou fait sauter le numéro (`99eae43`). Mesuré sur une vraie base v29 : 1,2 s sur 80 000 régions
- [ ] **Quatre choix de l'auteur sont vus par Hugo** — attendu : vus. Une demande en attente
  vient en tête d'« À regarder » ; les réponses se nomment « acceptée » et « refusée » quel que
  soit le genre de demande ; la liste des projets ne nomme pas qui a demandé ; « Importer au
  fonds » est une option de la création d'album, pas une route à part
- [ ] **Une copie sortie de sa dernière collection se reprend, ou se signale** — attendu : dit,
  ou fermé. Conforme aux décisions : tout membre en écriture l'envoie au fonds, même s'il ne
  l'a pas importée. Mais le propriétaire de la collection ne peut pas la reprendre (404), le
  geste ne s'annule pas, et rien ne remonte dans « À regarder » ; seul un administrateur la
  rend
- [ ] **Le message d'un geste fait dans « Supprimer… » ne tombe pas sur la colonne d'actions** —
  attendu : il se lit contre son contrôle, comme les autres messages de la tranche. Vu sur les
  captures de l'écran : « Votre demande est partie… » part en message flottant en bas à droite,
  et y couvre la colonne d'actions des planches. Le refus de la corbeille d'une planche, lui,
  a été ramené contre son bouton
- [ ] **La liste des albums reste rapide avec un gros journal** — attendu : mesuré. La règle
  de suppression directe descend dans le journal, région par région, pour chaque album de
  `GET /api/albums` ; aucune mesure n'a été faite sur un corpus réel
- [x] **`CLAUDE.md` dit ce que la tranche renverse** — attendu : réécrit au commit de
  documentation, chaque phrase avec sa date de renversement. Relevé par la relecture : sortir
  un album de sa dernière collection n'est plus refusé ; un album peut exister hors
  collection (au fonds) ; un album d'une seule collection ne se détruit plus par quiconque y
  écrit ; la phrase du refus de destruction a changé ; `destructible` change de sens et trois
  clés s'ajoutent ; « quatorze questions » devient seize ; le projet a un quatrième 409 et
  `routes/` un dixième module ; la nature d'un compte borde un geste ; et le journal A3, couche
  de provenance, devient une entrée d'autorisation
  **Fait par `6f73675`** (2026-10-16) : chaque renversement porte sa date et la décision de Hugo qui le fonde ; les questions du serveur sont DIX-SEPT et non seize — la relecture en comptait une de moins que le code (`peut_nommer_le_demandeur`). S'y ajoute la règle de Hugo du 2026-10-16 : chaque migration se vérifie sur une vraie base de la version précédente, fabriquée par `tools/fabriquer_base_de_version.py` (`c1c0817`). Le reste de la documentation d'usage et d'exploitation suit dans `90b5835`

### Tranche 3 — les décisions du cadrage (`docs/col3-tranche3-cadrage.md`, 2026-10-17)

- [x] **D1 — La tranche en deux temps : 3a (prendre, rejoindre, les albums du projet), puis 3b (en partir jusqu'à un cran, repartir de zéro)** — attendu : tranché par Hugo. **Tranché par Hugo le 2026-10-17 : oui.** La 3a ne copie aucun travail (une copie VIERGE, un rangement consenti) ; la 3b copie huit tables, le vocabulaire et le journal, sur une v32
- [x] **D2 — Être admis dans un projet n'est pas un état : un document entre dans un projet quand une de ses collections le prend** — attendu : tranché par Hugo. **Tranché par Hugo le 2026-10-17 : oui.** Pas de table « admis » ; la demande d'entrée nomme sa collection d'arrivée ; « le projet a ce document » se lit à l'existence d'une copie. Un projet vide doit donc avoir une collection avant de recevoir un document (D10)
- [x] **D12 — L'ordre** — attendu : tranché. **Laissé par Hugo à la session de pilotage le 2026-10-17 (« c'est toi qui sais le mieux »), qui retient la proposition du cadrage** : les albums du projet courant d'abord (faits, `2d80473`) ; le serveur de la 3a ensuite, la refonte de l'Administration étant sur `dev` ; son écran après la Bibliothèque en calque (`UX-18`) ; la 3a part en production sans attendre la tranche 4, le double compte de la Recherche et de l'Exploration écrit dans le guide
- [x] **D3 — Qui puise au fonds : le responsable par les notices, l'écrivain par ce qu'il lit déjà** — attendu : tranché par Hugo. Proposition et raisons dans `docs/col3-tranche3-cadrage.md` ; la maquette v8, non commentée, montrait « + Prendre du fonds… » à tout écrivain d'une collection, ce qui contredirait la décision du 2026-10-09. **Tranché par Hugo le 2026-10-17 : oui** — la règle du 2026-10-09 tient, la maquette se corrige
- [x] **D4 — Rejoindre : immédiat pour qui administre toutes les collections de la copie, sinon le propriétaire consent, dans tous les projets** — attendu : tranché par Hugo (cadrage). **Tranché par Hugo le 2026-10-17 : la règle stricte.** Rejoindre ne se fait que DANS un projet (le rangement ne traverse pas) ; c'est moins libre qu'aujourd'hui, où écrire des deux côtés suffit, et c'est voulu : ranger chez soi retire aux autres la suppression directe (`AUTH-10`). Écartée : « immédiat pour qui écrit dans toutes », plus fluide, qui laisse un écrivain élargir le cercle sans le propriétaire
- [x] **D5 — « Supprimer définitivement » détruit la COPIE ; le document part avec sa dernière** — attendu : tranché par Hugo (cadrage). Aujourd'hui, accepter une demande détruit toutes les copies d'un document (`repondre_demande`) : à réécrire avant la première sœur. **Tranché par Hugo le 2026-10-17 : oui**
- [x] **D6 — Les images appartiennent au DOCUMENT, les copies partagent les fichiers, et la 3a passe avant `IMG-2`** — attendu : tranché par Hugo (cadrage). Risque irréversible — une image effacée sous une sœur — : garde dans les mutants obligatoires. **Tranché par Hugo le 2026-10-17 : oui**
- [x] **D7 — La notice reste sur la copie** — attendu : tranché par Hugo (cadrage). **Tranché par Hugo le 2026-10-17 : oui.** Recopiée à la prise, libre de diverger ; le fonds montre celle de la plus ancienne copie vivante. La notice au document reste le modèle juste, pour quand deux copies ne seront plus rares
- [x] **D8 — Le projet d'origine garde son nom, et `projet` reçoit `AUTOINCREMENT`** — attendu : tranché par Hugo (cadrage). **Tranché par Hugo le 2026-10-17 : oui.**
- [x] **D9 — Répondre document par document, « tout accepter », un état « acceptée en partie »** — attendu : tranché par Hugo (cadrage). **Tranché par Hugo le 2026-10-17 : oui.**
- [x] **D10 — Un projet naît avec sa collection de base, et ses documents y entrent avant qu'on ait pensé ses collections** — attendu : tranché par Hugo. **Tranché par Hugo le 2026-10-17, contre la proposition du cadrage** (« le responsable dépose ses demandes une fois une collection créée ») : « le fonds commence avec le projet », la collection peut advenir après — penser collection avant d'avoir eu accès aux œuvres est difficile à concevoir pour un nouvel utilisateur, on n'aurait que des collections « Test » ; et un utilisateur peut ne jamais puiser au fonds. **Retenu** : une collection de base par projet (drapeau, renommable, non supprimable) ; ses responsables en sont propriétaires et ses membres y entrent selon une position choisie à la création — écriture (présélectionnée), lecture, ou aucun (« protégée ») —, les deux DÉRIVÉS de `projet_acces`, modifiables par qui gère le projet ; rien ne s'ouvre au déploiement (bases de l'existant protégées). Premier cas où être d'un projet ouvre une collection : mutants et relecture croisée. Détail dans `docs/col3-tranche3-cadrage.md`, section D10
- [x] **D11 — Les consentements se répondent là où vit qui les donne** — attendu : tranché par Hugo (cadrage). **Tranché par Hugo le 2026-10-17 : oui.** L'emplacement exact se tranche sur maquette

### Tranche 3a — relevé par ses commits 1 et 1b et leur relecture croisée, sur copie (2026-10-17)

- [x] **La v31 et la collection de base sont sur `dev`** — attendu : suite par défaut entière verte, mutants du cadrage tombés, relecture croisée faite. Écrits sur copie par un agent neuf (`4af3fbd` la v31 sans comportement — table `copie`, `projet_origine_nom`, `AUTOINCREMENT` sur `projet`, les sites qui supposaient une copie réécrits, images effacées par référence ; `593b296` la collection de base, D10), relus par une autre session, qui a prouvé deux défauts par des tests rouges : la « Collection par défaut », habitée, donnée aux responsables du repli au déploiement, et un réimport qui écrasait l'image d'une copie sœur. Corrigés par `aeefec2` (un import n'écrit jamais sur un fichier pris, une destruction n'efface que des images), `dab89e5` (une base qui porte du vocabulaire retient son projet) et `3205426` (aucune collection existante ne devient une base, décision de Hugo) ; les deux tests de la relecture passent sur l'état final, rejoués par la session de pilotage
- [ ] **« + Nouveau projet » pose la question de la position des membres, et la fiche du projet la règle** — attendu : écran du commit 3. Le serveur crée une base OUVERTE quand la création ne dit rien (la présélection de D10) et l'écran d'aujourd'hui n'envoie pas la question : **la 3a ne part pas en production sans elle**
- [ ] **L'accès tenu par le projet se lit là où l'on regarde qui entre** — attendu : « Qui entre » de la base et « Comptes et groupes » montrent la propriété des responsables et l'entrée des membres ; le 409 « dernier propriétaire » en tient compte. Aujourd'hui ils ne montrent que les lignes explicites : un propriétaire de la base croit son cercle restreint alors que tous les membres y écrivent (relecture, constat 6 ; l'esprit d'`AUTH-4`, « inévitable, mais pas invisible »)
- [ ] **Les images s'effacent sous le verrou d'écriture** — attendu : avant `creer_copie` (commit 2). L'effacement se fait après la validation, hors verrou : une sœur née entre la lecture de ce qu'il faut garder et l'effacement perdrait ses fichiers (relecture, constat 4)
- [ ] **Une demande montre qui a créé SA copie, et le fonds la rattache à sa copie** — attendu : commit 2. La vue d'une demande montre `importe_par` du document quand la règle lit `copie.creee_par`, et `lire_le_fonds` rattache la demande au document (la première trouvée) : identiques tant qu'il n'y a qu'une copie
- [ ] **L'import présélectionne la base, et la note morte de « + Nouvel album » part** — attendu : écran du commit 3. La note « l'album entrera dans une collection par défaut » ne peut plus s'afficher depuis que le repli naît avec sa base
- [x] **Le défaut de la base du repli aurait frappé en production** — attendu : la réponse de Hugo. **Hugo, 2026-10-17 : le projet de départ a un responsable en production, `chercheur`.** Avec la lecture d'abord écrite (la « Collection par défaut » base du repli), il en devenait propriétaire au déploiement de la v31, avec tout ce qu'elle porte ; avec la décision du jour (`3205426`), il ne reçoit qu'une base neuve et vide
- [x] **Qui « a créé » une copie entrée sur demande** — attendu : tranché par Hugo. **Hugo, 2026-10-17 : le DEMANDEUR**, pas l'administrateur qui accepte — il retire seul un document demandé par erreur, si personne d'autre n'y a travaillé ; la naissance de la copie, écrite par l'administrateur, ne compte pas comme travail d'autrui. Une prise directe par l'administrateur reste à son nom
- [x] **Une copie partagée entre plusieurs propriétaires se rejoint par un administrateur** — attendu : tranché par Hugo. **Hugo, 2026-10-17 : pour la 3a, oui** — seul un compte qui administre TOUTES les collections de la copie, ou un administrateur, répond à un `rejoindre` ; pas de consentements multiples, cas rare. Les messages le disent au lieu d'annoncer « son propriétaire »
- [ ] **Les consentements à plusieurs signatures, si le cas se présente** — attendu : une copie partagée entre deux propriétaires distincts se rejoint avec l'accord de chacun, sans passer par un administrateur. Écarté pour la 3a (décision ci-dessus) ; rouvert par un usage réel
- [ ] **Les genres neufs (entrée de documents, rejoindre) ont leur écran avant la production** — attendu : commit 3. La relecture croisée du commit 2 (sur copie, 2026-10-17) a trouvé « À faire » présentant ces demandes comme des suppressions définitives, son bouton « Détruire » les acceptant ; en correction, elles n'y paraissent plus, et aucun écran ne les lit encore — ni la fiche de la collection pour le propriétaire, ni celle du projet pour le responsable
- [ ] **L'adresse d'image d'une copie sœur nomme la copie source** — attendu : levée par `IMG-2` (fichiers nommés par image). Accepté par écrit pour la 3a : qui lit la sœur apprend que le document a ou a eu une copie ailleurs, et son identifiant (relecture croisée du commit 2)

### Le projet

- [ ] **Qui est dans un projet** — attendu : tranché. Proposition : le patron de `collection_acces`, un étage plus haut — un accès de projet se donne à un COMPTE ou à un GROUPE de l'annuaire, et l'on ne stocke toujours qu'une référence, jamais une appartenance (invariant d'`AUTH-1`). « Intégrer quelqu'un à son arrivée » est alors un geste de l'application, et un groupe d'étudiants entre d'un seul coup
- [ ] **Qui gère un projet** — attendu : nommé, avec ce qu'il peut. Un rôle entre l'administrateur de l'instance et le propriétaire d'une collection : admettre des documents, décider quelles collections existent, autoriser qu'on amorce depuis son travail ?
- [ ] **Une personne dans deux projets choisit dans lequel elle travaille** — attendu : dit, écran par écran. Un projet courant, lisible partout ; la Recherche et l'Exploration bornées à lui par défaut
- [ ] **Le vocabulaire et les personnages ont un étage de projet** — attendu : tranché. Un terme « global » est aujourd'hui visible de toute l'instance, et un personnage traverse les albums : c'est par là que deux projets se parasiteraient d'abord — ce qui fuit n'est pas un mot, c'est une grille d'analyse (`AUTH-2`, v24). Global à l'instance, au projet, ou local à une collection ?
- [ ] **Ce qui ne peut PAS entrer dans un projet** — attendu : qui le décide, et sur quoi. Un refus par document (ses droits, sa base légale) ou par projet ?
- [x] **La demande venue de l'extérieur — un compte et un projet, justifiés** — **DIFFÉRÉE par Hugo le 2026-10-10, et sortie de ce chantier : `AUTH-13`.** *« On peut garder ce projet pour plus tard. Je pense surtout à une page de présentation. Mais on garde ça pour quand tout sera à peu près construit et abouti. »* Ce qui la rouvre vit ici : la tranche 2 livrée, son mécanisme de demande est celui qu'`AUTH-13` réemploie — le dire chez lui en la fermant. Ce qui suit est le relevé qui a motivé le report. Attendu d'origine : sa forme tranchée par Hugo, et son chantier nommé. Relevé le 2026-10-10 : RIEN de l'application ne se joint aujourd'hui sans compte (`default_policy: 'deny'` dans la configuration d'Authelia, `forward_auth` sur tout le domaine), et `AUTH-7` a déjà écrit ce que vaut ce pas — « ce n'est pas un degré, c'est un régime ». Quatre choses neuves : une page et une écriture ouvertes à l'internet entier (abus, volume, donc plafonds et frein) ; des données personnelles de gens qui ne sont pas des utilisateurs — nom, courriel, rattachement, justification — et ce qu'on en garde après un refus (le corps « PERSONNES » de `docs/dossier-base-legale.md`) ; la RÉPONSE, l'application n'envoyant aucun courriel et la fiche ayant écarté toute messagerie ; et la création du compte, que l'application ne fait pas — le compte de service de l'annuaire ne fait que lire (`AUTH-6`), c'est un administrateur qui crée dans l'annuaire. Proposition : un chantier à part, relu en croisé comme tout ce qui touche une garde, APRÈS la tranche 2 dont il réemploie le mécanisme de demande ; d'ici là une demande arrive par le contact du référent et l'administrateur la saisit, justification comprise
- [x] **Un responsable DEMANDE la suppression de son projet** — attendu : confirmé par Hugo. Sa phrase du 2026-10-10 : *« D3 : demande de suppression possible aussi par les responsables des projets, non ? »* — lue par la session comme la suppression du PROJET (c'est d'elle que parlait la décision qu'il commentait), et rendue ainsi à Hugo, qui a poursuivi sans la reprendre. La demande passe par le mécanisme de la tranche 2 (case « Une demande est UN mécanisme ») **Confirmé par Hugo le 2026-10-11**, avec les cinq décisions qui bloquaient le code de la tranche 2 : la lecture était la bonne, et la demande se construit dans cette tranche
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
- [x] **La pastille « suppression demandée » reste un état à l'étroit** — attendu : sur la ligne d'un album, à 375 px, un cadre net sous le titre. Relevé par Hugo le 2026-10-16 pendant `supprimer-n-est-pas-sortir` : à côté du titre, dans une colonne étroite, elle se coupait sur trois lignes, et ses coins en gélule faisaient de sa bordure une ellipse — un trait de feutre, pas un état. **Fait par `bd5dff1`** : sous le titre, coins à peine arrondis ; vu en capture dans les deux thèmes, à l'étroit et au large

### Le fonds

- [ ] **L'origine et les emplois sont ÉCRITS** — attendu : qui a importé, quand, dans quel projet d'abord ; chaque admission et chaque retrait, datés et attribués. Relevé le 2026-10-09 : `albums` ne porte que `date_import` ; `collection_album` n'a ni date ni auteur ; ni créer, ni ranger, ni sortir, ni supprimer un album n'est journalisé. L'existant ne se reconstitue pas
- [ ] **Le fonds a un écran, pour l'administrateur** — attendu : les documents, d'où ils viennent, quels projets les emploient, lesquels ne sont appelés par personne, les demandes de suppression en attente
- [ ] **L'Administration tient à l'échelle, AVANT la tranche 3** — attendu : une forme tranchée par Hugo sur une maquette interactive, en session dédiée, puis écrite. Relevé par Hugo le 2026-10-16, sous `admin-bd` sur la recette : *« si on a une quarantaine de participants, dans plein de projets, avec un fonds de plus en plus grand, la page ne sera pas du tout adaptée »*. Lu dans le code le même jour : « 🗄️ Le fonds » rend chaque document EN ENTIER, l'un sous l'autre, par ordre d'arrivée, sans filtre, recherche, regroupement ni pagination, et `GET /api/fonds` rend tout d'un coup ; six blocs s'empilent, et « 👥 Comptes et groupes », le plus servi, descend SOUS le fonds à mesure qu'il grossit ; « 🗂️ Projets » a une liste et une fiche, mais une liste plate sans filtre. « 👥 Comptes et groupes » tient déjà (liste et fiche, filtre, axes, tri, « À regarder ») : c'est le patron. **Orientation acceptée par Hugo le 2026-10-16** : une page dont la VUE change selon son adresse — *Projets* · *Fonds* · *Comptes et groupes* · *Instance* (version, référent, moteurs) —, ouverte sur un tableau de bord court (demandes en attente, « À regarder ») ; le fonds en liste et fiche, une ligne par document, filtre et états (demandé, appelé par personne, copie gardée, projet) ; les projets de même. Avant la tranche 3, parce qu'elle ajoute « prendre un document » au fonds : posé sur la page d'aujourd'hui, il faudrait le déménager. La tranche 2 part en production telle quelle. Restent à calibrer, dans la session de maquettes : les ordres de grandeur visés, ce qu'un administrateur y vient faire le plus souvent, et par quoi il cherche un document
  **Tranché par Hugo le 2026-10-16 sur la maquette** (https://claude.ai/artifact/Hpj64m3EvgYfxJGqgZithX, version 8, ce qui est retenu y porte ✓) : des volumes « larges » d'ici un an — ~25 projets, ~1 000 documents au fonds, jusqu'à 10 collections par projet, ~40 comptes ; aucun geste dominant (« ça dépend des jours ») ; UNE page à vues adressables (`/administration?vue=…`), pas des pages séparées ; au fonds, on cherche par titre, série ou auteur, par projet, par qui l'a importé, par état ; l'ouverture est une vue « À faire » — « Tout ce qui est nécessaire. Là, tout est partout et c'est illisible, on ne parvient pas à se repérer sur les tâches à effectuer » — demandes, puis accès à régler, puis instance, le plus ancien d'abord ; quand rien n'attend, la page s'ouvre sur la dernière vue consultée ; on répond à une demande SUR PLACE dans « À faire » (Détruire / Garder), pas dans la fiche du fonds ; l'Administration TRAVERSE les projets — elle ne suit pas le projet courant, et le filtre « Projet » du fonds reste à la main ; un seul gabarit liste-et-fiche avec la Bibliothèque (`UX-18`). NON commentés par Hugo, donc ouverts : la forme des vues Fonds, Projets, Comptes et groupes et Instance ; l'emplacement des gestes de la tranche 3 ; le retour « ← Retour »
  **Écrite en partie par `73241cc`** (2026-10-17, sur copie, pendant que Hugo avait laissé l'ordinateur allumé ; portée sur `dev`, non poussée) : cinq vues adressables (`?vue=afaire|fonds|projets|comptes|instance`, les anciennes adresses `?compte=`, `?axe=`, `?document=` tenues) ; l'ouverture sur « À faire » dès que quelque chose attend, sinon la dernière vue ; « À faire » — les demandes, la plus ancienne d'abord, auxquelles on répond sur place, puis les accès à régler, puis l'instance ; le fonds en liste et fiche, filtres texte · état · projet · importé par, 400 lignes à la fois ; le gabarit `lf-` tiré des règles `cg-`. Chaque lien de vue ne se lève que si un bloc de sa vue a répondu : la garde reste celle des routes. **La vue Projets suit par `ec56a73`** : la liste filtrable par nom, l'état de chaque projet (« sans responsable » — jamais pour le projet de repli, né ainsi —, « suppression demandée »), « + Nouveau projet » au geste, la fiche dans l'adresse (`?projet=…`), une colonne à la fois sous 40em ; côté serveur, une seule clé neuve, `sans_responsable`, rendue comme la justification à qui GÈRE le projet (relue par la session de pilotage : absente pour un simple membre et pour qui ne lit qu'une collection, testé). **Reste** : Instance en blocs empilés, rien pour « ← Retour », ni filtre par état ni tri dans la liste des projets. **À faire valider par Hugo sur la recette** : la forme du fonds (le sens de « copie gardée » — sans collection mais avec un projet ; un import au fonds est « appelé par personne » —, le tri « récents d'abord ») ; la forme de « À faire » (« Répondre » qui déplie ; les comptes jamais venus repliés « à titre d'information », pour que la page ne s'ouvre pas toujours sur « À faire ») ; « À regarder », gardé aussi dans « Comptes et groupes » ; le menu des vues ; « Comptes et groupes » comme vue par défaut quand rien n'attend et qu'aucune n'a été retenue
- [ ] **Deux copies du même document se savent sœurs** — attendu : un identifiant de document, que la Recherche et l'Exploration lisent. Sans lui, qui lit deux collections dont chacune a sa copie compte deux fois le même texte ; avec lui, on dédoublonne, ou on COMPARE — deux travaux indépendants sur les mêmes bulles sont la matière d'un vrai accord inter-annotateurs, là où `ANN-5` ne mesure aujourd'hui que des révisions. À éprouver, pas à promettre
- [x] **La consultation du fonds est tranchée contre le cloisonnement** — attendu : qui consulte, et ce qu'il voit. « 404, jamais 403 » existe pour que personne n'apprenne ce que le corpus contient hors de sa portée. Proposition : un gestionnaire de projet voit la NOTICE seule (titre, série, auteur) — ni images, ni travail, ni qui l'emploie **Confirmé par Hugo le 2026-10-09, sur la maquette : « Tout me semble bien. »**
- [ ] **Une demande est UN mécanisme, pour trois usages** — attendu : tranché. Proposition : faire entrer des documents dans un projet, supprimer un document, supprimer un projet — le même état (qui demande, quand, pourquoi), la même place dans « À regarder », construit une fois, en tranche 2
- [ ] **Qui dépose la demande de départ d'un projet** — attendu : tranché par Hugo. Deux lectures de « à la création d'un projet ». (a) L'administrateur crée le projet et nomme son responsable ; celui-ci trouve, à sa première ouverture d'un projet encore vide, « quels documents du fonds voulez-vous ? », et dépose UNE demande ; l'administrateur qui crée peut aussi en admettre lui-même, dans le même geste. (b) Quelqu'un qui n'a pas encore de projet demande d'un seul coup le projet ET ses documents — ce qui lui ouvre les notices du fonds, que la case « La consultation du fonds » réserve aux responsables. ~~Proposition : (a)~~ **Hugo, le 2026-10-10 : le projet lui-même se demande, avec une justification, et pas par n'importe qui** — c'est (b), ~~bornée,~~ et la proposition de la session est écartée. ~~Restent : QUI peut déposer (proposition : qui porte déjà une responsabilité dans l'instance — responsable d'un projet ou propriétaire d'une collection ; un nouveau venu passe par un administrateur, qui crée le projet et saisit la justification pour lui) ;~~ **Corrigé le même jour : Hugo ne borne pas QUI demande — on demande même sans compte —, il exige que la demande soit justifiée.** Restent : QUI lit la justification (proposition : les administrateurs et les responsables du projet, pas ses membres) ; et les ALBUMS — qui demande de l'extérieur ne voit pas le fonds, donc ne peut pas y cocher : proposition, la demande de projet dit en clair sur quel corpus on veut travailler, et la demande groupée de documents se dépose à la première ouverture du projet accepté, par son responsable (c'est la lecture (a), qui redevient la seconde moitié du geste)
- [ ] **Comment l'administrateur répond à une demande de plusieurs documents** — attendu : tranché. Proposition : document par document, avec un « tout accepter » ; une demande peut finir acceptée en partie, et le dit à qui l'a déposée

### Les passes de QA que chaque tranche périme

- [ ] **Tranche 1 — la barre du haut est rejouée à l'étroit et à grande police** — attendu : `petites-largeurs` et `preference-de-police` rejouées sur leurs cases de barre, une fois le nom du projet (ou son sélecteur) posé sur les cinq surfaces. À 320 et 375 px, et à grande police, il ne fait sortir de la fenêtre ni la navigation, ni le menu « Aa », ni la pastille d'identité : c'est la bande où il reste le moins de place, et un nom de projet ne se coupe pas
- [ ] **Tranche 1 — `projet-visible` est écrite, puis jouée par Hugo** — attendu : une passe neuve et courte, sur une recette qui porte `9eec56e` — le nom sur les cinq surfaces, créer un second projet et y faire entrer un compte et un groupe, ce que voient un responsable et un simple membre, la Bibliothèque bornée au projet choisi. Monter cette recette MIGRE sa base en v29, sans retour sous le code de `main` : à faire sur le mot de Hugo **La recette est montée le 2026-10-10, sur l'accord de Hugo, et sert `bd89fe4`** : la passe peut se jouer. Les comptes y sont comme elle les suppose, lu dans l'application : `proprio` possède « Collection Test » et « Étude B », `stagiaire` écrit dans la première, `lectrice` la lit par le groupe `annotateurs`, et l'annuaire a des groupes à proposer **REPORTÉE par Hugo le 2026-10-10, le soir même** : « On peut repousser les passes et poursuivre sur le code ? » La recette est arrêtée proprement, sa base en v29, prête à repartir sur `bd89fe4` ou plus récent. Ce que le report laisse : la tranche 1 est sur `dev` gardée par ses tests et NON vue à l'écran par un humain, et ce qui se code ensuite s'empile dessus. Ce qui rouvre, au plus tard : la fusion vers `main` — la passe se joue avant, ou Hugo décide par écrit qu'elle n'en est pas un préalable. Si un chantier suivant change un écran qu'elle décrit, ses cases sont réécrites avant d'être jouées, jamais après
- [ ] **Tranche 1 — la carte d'accueil dit le projet, ou dit pourquoi non** — attendu : tranché, et `accueil-par-ou-commencer` rejouée si son texte change. Un arrivant entre désormais dans un projet avant d'entrer dans une collection
- [x] **Tranche 2 — `supprimer-n-est-pas-sortir` est RÉÉCRITE, pas rejouée** — attendu : une passe neuve pour les deux réponses à « supprimer ». La corbeille et le ✕ qu'elle vérifie aujourd'hui sont ce que la tranche remplace
  **Réécrite par `c3eee63`** (2026-10-16) : 19 zones, 71 cases, environ une heure ; elle part de l'état de base de la recette, pose son décor dans ses premières cases, et remet la recette en état à sa dernière zone. À jouer par Hugo, non cochée ici
- [ ] **Tranches 2 et 3 — `collections-bibliotheque` est rejouée sur ses gestes d'album** — attendu : rejouée. « Ranger ici » devient « prendre un document », et sortir un album de sa dernière collection cesse d'être refusé
- [ ] **Tranche 3 — le projet a SA passe** — attendu : écrite, non cochée. Qui entre dans un projet, ce qu'il admet, ses trois réponses ; `qui-entre` et `comptes-et-groupes` restent vraies pour la collection, mais ne disent rien de l'étage au-dessus
- [ ] **Tranche 4 — `import-bilan-refus` et `termes-illisibles` sont rejouées** — attendu : rejouées. Le menu « Portée » et « Importer dans » gagnent le projet, et « global » ne veut plus dire toute l'instance

### Ce que le chantier fait aux autres

- [ ] **`AUTH-10` garde sa règle pour une copie PARTAGÉE** — attendu : dit chez lui. Une copie rangée dans deux collections reste possible, donc « détruire demande d'écrire dans toutes » reste vrai pour elle ; ce que le fonds change est QUI détruit pour de bon, et le partage consenti ferme le veto de qui range chez soi
- [ ] **`UX-18` dessine la Bibliothèque d'UN projet** — attendu : dit chez lui. Ses décisions tiennent ; s'y ajoutent le projet courant, l'entrée « piocher dans ce que le projet a admis », et les deux réponses à « supprimer »
- [ ] **La règle du projet courant dans la Bibliothèque est réécrite pour la forme en calque** — attendu : dit, puis écrit dans `CLAUDE.md`. Rouvert le 2026-10-16 par la maquette : la Bibliothèque y montre les ALBUMS du projet, chacun nommant ses collections, et ses collections en calque ; la règle d'aujourd'hui — la Bibliothèque ne liste que les collections du projet courant, et « la liste des albums et le lot ne connaissent pas le projet » — ne le dit plus. Décision d'écran (`UX-18`) ; le modèle reste en réflexion (`docs/collections-niveau-ou-calque.md`)
- [ ] **L'export garde son titre** — attendu : vérifié. La collection reste l'unité de dépôt et le titre d'un export (`AUTH-11`) ; le projet n'en est pas un

### Ce que `ANN-7` ouvre ici — 2026-10-14

- [ ] **Le fonds et le catalogue des grilles suivent les mêmes règles** — attendu : tranché ensemble. `ANN-7` donne au projet un rôle neuf : il ACTIVE des grilles d'annotation, prises dans un catalogue où chacune entre par une case « Partager ». C'est le patron du fonds — un pot commun, des projets qui y prennent, des droits pour voir et pour prendre — et les deux gestes gagnent à se comporter pareil, à l'écran comme dans les droits

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

Rendu par un agent en lecture seule, sur `3cac8aa`. ~~Rien n'en est codé~~ (vrai à
l'écriture : le premier commit a suivi le même jour, section suivante), et les décisions
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

### Le premier commit de la tranche 1 — `6c3e19f`, 2026-10-10

Écrit par un agent neuf sur une copie, relu par la session de pilotage qui ne l'a pas écrit,
puis porté dans l'arbre partagé. Onze fichiers, dont deux neufs : `routes/projets.py` et
`tests/test_projets.py` (38 tests).

**Ce qui a été mesuré.** La suite par défaut : 1 536 passés sur le commit d'avant, 1 574
sur celui-ci, dans la copie puis dans l'arbre partagé — l'écart est exactement les 38
tests neufs, et aucun identifiant de test n'a disparu. La passe navigateur entière, dans la
copie : 333 passés, sous Chromium, sur le poste. Quarante-cinq mutants joués un par un,
quarante-cinq tombés. Et la preuve de la tranche : le seul fichier de test existant modifié
est `tests/test_sorties_identite.py` — deux déclarations et le semis de sa sentinelle, 24
lignes ajoutées, aucune retirée, aucune vérification touchée. Sur SQLite 3.49, celui du
poste : une colonne `NOT NULL` qui porte une clé étrangère ne s'ajoute pas par `ALTER`, avec
ou sans défaut — les deux règles que le cadrage citait de mémoire sont confirmées.

**Ce qui n'a pas été joué.** La suite DANS l'image : elle se joue sur le poste avant la
fusion vers `main`, et sa cible navigateur aussi, la barre dépendant de la police. La base
de production n'a pas été lue ; sa migration sera un déploiement manuel, sauvegarde faite —
la veille de déploiement refuse un changement de schéma, et une base v29 ne redémarre pas
sous du code v28.

**Quatre écarts au cadrage, acceptés à la relecture.** La route qui propose au responsable
les groupes de l'annuaire (`…/membres/choix`) vit dans `routes/collections.py` et non avec
les autres routes du projet : un test exige par égalité que les routes qui lisent l'annuaire
tiennent dans ce module, et le desserrer pour un rangement aurait été retoucher une garde.
Créer une collection dans un projet dont on n'est pas répond 404 si l'on ne voit pas le
projet, et un 403 NOMMÉ si l'on en voit le nom — la distinction des collections, là où le
cadrage disait 404 dans les deux cas. La règle « sans projet nommé, la collection est du
projet de repli » est une expression SQL écrite une fois dans `database.py`, que
`autorisation.py` importe. Et le refus de ranger un album à travers deux projets vaut aussi
pour l'outil en ligne de commande, pas seulement pour la route.

**Où vit chaque décision**, pour qui devra en changer une : le nom de naissance du premier
projet et le plafond d'un nom sont deux constantes de `database.py` ; les membres de départ,
une requête de l'étape v29 de la migration ; ce que peut le responsable, deux questions de
la `Portee` (régler les membres, décider des projets) ; la justification, une colonne de
`projet` rendue à un seul endroit de `routes/projets.py`, à qui gère le projet — les autres
ne reçoivent pas la clé.

**Trois conséquences à connaître.** Qui lit une collection lit le nom ET la description de
son projet, sans en être membre. Une justification modifiée s'écrit au journal, avant et
après : elle y survit à la suppression du projet, et le journal de ces deux tables est
retenu de tout dépôt. Et un projet qui a reçu un album ne se vide plus que par la
destruction de l'album — aucune collection ne change de projet, aucun rangement ne traverse :
« un projet ne se supprime que vide » est donc, d'ici la tranche 3, presque « ne se supprime
pas ».

**Ce que le second commit doit savoir.** `GET /api/projets` rend une liste VIDE à un compte
identifié qui n'a ni projet ni collection : la barre doit tenir ce cas. Ni le plafond du nom
ni la liste des rôles ne sont servis par une route. Et la clé de la réponse de
`…/membres/choix` est `membres`.

### Le second commit de la tranche 1 — `9eec56e`, 2026-10-10

Écrit par un second agent neuf sur une copie, relu — diff et captures d'écran — par la
session de pilotage, puis porté dans l'arbre partagé. Dix-huit fichiers, dont six neufs :
`static/lib/projet.js` (le projet courant, logique pure), `static/lib/membres-projet.js`
(« Qui y entre », module montable frère de « Qui entre »), leurs tests sous Node,
`tests/test_e2e_projets.py` (48 tests navigateur), `tests/test_membres_projet_module.py` (le
cliquet du module) et `tests/test_projet_ecran.py` (l'accord entre l'écran et le serveur).

**Ce qui a été mesuré.** La suite par défaut : 1 574 passés avant, 1 593 après, dans la
copie puis dans l'arbre partagé. La passe navigateur entière sous Chromium, dans la copie :
381 passés, dont les 48 neufs. Sous Firefox, à des préférences de police de 16, 20 et 24 :
les tests neufs passent aux trois ; la mesure de reflow passe à 16 et à 20, et laisse à 24
cinq échecs IDENTIQUES sur le commit d'avant — antérieurs à la tranche, rangés chez `UX-7`.
Soixante-cinq mutants joués un par un, soixante-cinq tombés — après que trois ont d'abord
survécu : un test qui comptait des titres et non des écouteurs, un `to_have_text` qui lit
aussi un élément caché, et un test qui dépendait de l'ordre d'arrivée de deux réponses.
Les trois sont corrigés, rejoués, tombés. Et le plafond du nom, cf. sa case.

**Ce qui n'a pas été joué.** L'image : ni sa suite, ni sa passe navigateur, ni le rendu de
ses polices — les mesures de largeur forcent DejaVu Sans, installée sur le poste : la même
famille que l'image, pas l'image. La passe navigateur ENTIÈRE sous Firefox. Un lecteur
d'écran. Et la phrase du simple membre de trois projets ou plus : seule la forme à deux est
jouée.

**Les écarts à la maquette et au cadrage, acceptés à la relecture.** La ligne qui nomme le
projet des collections est AU-DESSUS du bloc et non sous son titre : un test interdit le mot
« principal » dans ce bloc — c'est un terme du modèle —, et le premier projet naît « Projet
principal ». Tout nom de projet qui porterait « genre », « principal » ou « utilisateur »
l'aurait fait tomber de même. Le nom n'est pas en gras : le gras de l'image est 12 % plus
large, deux caractères de plafond. La phrase du simple membre ne parle pas du fonds, qui
n'existe pas encore, et ne dit pas « rien de cette page ne vous est ouvert » — les moteurs
le sont à tous. Le bloc ne liste que les projets qu'on RÈGLE. « Décider des projets » se lit
dans ce que `GET /api/moi` publie déjà, sans rien y ajouter, et un test exige que le serveur
réponde comme l'écran le suppose. Enfin le plafond et la liste des rôles sont recopiés dans
l'écran, et un test fait tomber la suite si les deux s'écartent.

**Ce que la tranche fait à la bande du haut**, mesuré à 320 px de large sur l'Atelier, avant
et après. À la police par défaut, la bande prend une rangée de plus : 73 px, puis 106. Sous
une préférence de 24, dans le cas ordinaire, elle demande la même hauteur qu'avant, 235 px ;
dans le pire cas — nom le plus long, deux projets — 347 px au lieu de 284. La dette ouverte
chez `UX-7` s'aggrave donc : la hauteur de fenêtre sous laquelle la bande est écrasée passe
d'environ 553 à 610 px dans ce pire cas. C'est écrit chez elle.

### Le commit de finition — `7eabeb7`, 2026-10-10

Troisième agent neuf, même méthode : une copie, la preuve rendue, le diff et les captures
relus avant de porter. Ce qu'il fait est dans les deux cases qu'il ferme. Deux choses qu'il
a trouvées sans les toucher, antérieures à ce chantier ou non vérifiées. Dans la fiche d'un
album, si la lecture de ses collections échoue, la liste et les ✕ de l'album PRÉCÉDENT
restent affichés sous la fiche du suivant, et ces ✕ agiraient sur le précédent — lu dans
`loadAppartenance`, non reproduit. Et sur une capture à 320 px, la grille « Série / Auteur »
de la modale d'album dépasse la boîte à droite — non vérifié sur le commit d'avant, donc ni
attribué ni écarté. Les deux relèvent de la Bibliothèque à l'étroit, pas du projet.

**Les deux sont fermés le 2026-10-11 (`79da8c4`), après avoir été reproduits.** Le premier était pire
que lu : depuis la fiche du second album, le ✕ resté affiché sortait le PREMIER de sa
collection, et « + Ranger ici » rangeait le second dans une collection choisie pour le
premier. La fiche dit maintenant qu'elle n'a pas pu lire, et n'offre aucun geste. Le second
est réel et ANCIEN : mesuré identique sur le commit du 2026-09-05, la règle datant de
l'origine de la page — 70 px de dépassement à 320 px. La grille passe sur une colonne quand
deux n'y tiennent plus. Vu et laissé, dans la même modale : à 320 px sous une préférence de
police de 24, le message du pied n'a aucune largeur, la rangée des boutons ne passant pas à
la ligne.

### La migration v29 sur une base réelle — la recette, 2026-10-10

Jusque-là la migration n'avait tourné que dans des tests, sur des bases ramenées en v28 par
chirurgie. La recette lui a donné une base qui a vécu : trois collections, trois albums,
cinq accès tenus par quatre principaux. Avant : une copie cohérente de la base, faite dans
le conteneur encore sous l'ancien code (`VACUUM INTO`), rangée à côté d'elle dans le volume
— `avant-v29-20261010-184017.sqlite`, version 28, intégrité vérifiée. C'est par elle qu'on
reviendrait sous le code de `main`, la migration étant à sens unique.

Après le redémarrage sur `bd89fe4`, lu dans la base et par l'application : version 29,
intégrité intacte ; un projet, « Projet principal », drapeau de repli posé ; les trois
collections dedans, aucune sans projet ; quatre membres pour quatre principaux — deux
groupes, deux comptes —, aucun responsable. `GET /api/projets` rend ce projet à chacun des
comptes de la passe avec le rôle « membre », y compris à `lectrice`, qui n'en est que par
son groupe ; à l'administrateur avec un rôle nul et `gerable`. Aucune erreur au journal de
l'application. C'est une répétition du déploiement, pas le déploiement : la base de
production n'a pas été lue, et l'image de la recette n'a joué ni la suite ni la passe
navigateur.

### Le cadrage de la tranche 2 — 2026-10-11, lu dans le code et non éprouvé

Rendu par un agent en lecture seule, sur `d1c85d3`. Rien n'en est codé, rien n'a été
exécuté, et son code attend les passes et la fusion de la tranche 1 (zone « L'ordre »).
Ses décisions sont les deux zones « Tranche 2 » du Reste.

**Ce que le code impose, et qu'on ne supposerait pas.** Aucun acte sur un album n'est
journalisé — ni créer, ni modifier, ni supprimer, ni importer une planche, ni ranger, ni
sortir : l'origine de l'existant ne se reconstitue pas. Une colonne neuve sur `albums` sort
par trois réponses de l'API qui lisent la ligne entière, et le cliquet des colonnes
exportables n'a pas de liste de retenues pour cette table : l'identité de qui importe ne peut
donc pas y vivre. Le 409 « dernière collection » garde plus que l'accès : il garde le PROJET
de l'album — une copie sans collection n'en a plus, et rien ne refuserait de la ranger dans
un autre. Les fichiers d'images portent l'identifiant de la ligne `albums`, qui se
réattribue : le dernier album détruit rend son numéro au suivant, donc son dossier et ses
lignes de journal. Ctrl+Z ignore la suppression d'un album et s'y coince sur les actes de
ses régions ; il atteint aussi une copie qu'on ne lit plus. « À regarder » vit dans une
route réservée aux administrateurs et composée avec l'annuaire. Et l'Atelier crée ses albums
dans la collection de repli, hors du projet courant.

**Le modèle proposé.** La ligne `albums` reste la copie de travail, comme la piste de la
fiche le disait. S'y ajoutent une table `document` — l'identité, qui a importé, quand, dans
quel projet d'abord — et deux attaches sur `albums` : son document, son projet. La notice
reste par copie, les fichiers ne bougent pas ; ce qui change est QUI les efface — la
destruction du document, et elle seule. Deux tables pour les demandes, bâties pour porter
plusieurs documents dès maintenant. Écartées : tout poser sur `albums` sans table, qui perd
« une identité distincte de ses copies » ; et remonter la notice sur le document, le modèle
juste, hors de proportion tant qu'un document n'a qu'une copie — trente sites de requêtes
dans onze fichiers. La migration fait de chaque album l'unique copie d'un document neuf,
importateur inconnu.

**Trois commits de code**, plus gros ensemble que la tranche 1 entière. Le document existe
et ses emplois s'écrivent, sans qu'aucun comportement change — il peut partir seul, et plus
tôt il part, plus tôt les origines s'écrivent. Puis la règle, la demande et le fonds côté
serveur, qui ne part PAS seul : l'écran d'avant y mentirait. Puis l'écran. Ici le
comportement change, et des tests existants seront réécrits : la preuve de la tranche 1 ne
vaut que pour le premier commit.

**Ce que le plan ne règle pas.** Ctrl+Z reste coincé sur les actes d'un document détruit —
le défaut existe aujourd'hui, la tranche le rend plus fréquent et il touche désormais des
tiers. Modifier la notice d'un album n'est toujours pas journalisé. Une demande répondue
reste en base, avec un login et un motif, sans durée de conservation. Et la base de
production n'a pas été lue : combien d'albums, combien rangés dans plusieurs collections.

### Le premier commit de la tranche 2, écrit et relu sur une copie — 2026-10-11

Deux commits sur la copie `fonds-c1` du scratchpad de la session de pilotage, partis de
`869726c`, NON portés : l'ordre arrêté veut que la tranche 1 soit fusionnée avant que le code
de la tranche 2 n'arrive sur `dev`. Ils ne se citent donc pas ici par leur identifiant, que
ce dépôt ne connaît pas.

**Ce qu'ils font.** Tout album devient la copie de travail d'un DOCUMENT : une table
`document`, première du dépôt à porter `AUTOINCREMENT` (sans lui SQLite rend au suivant
l'identifiant du dernier détruit, mesuré), qui dit qui a importé, quand, et dans quel projet
d'abord ; `albums.document_id` et `albums.projet_id`, nullables et à clé sans action ; deux
tables de demande, vides. La migration donne un document à chaque album d'hier sans inventer
d'importateur. Créer un album, y ajouter ou en retirer un scan, le ranger, le sortir, le
détruire s'écrivent désormais au journal, sous deux cibles retenues de toute sortie et
absentes de l'annulation. Aucune garde ne change.

**Ce que le cadrage n'avait pas vu.** Les pseudonymes de sortie numérotent sur le journal
entier : les deux cibles neuves auraient donné le rang 1 à qui monte un album, et décalé tous
ceux qui annotent après lui dans les artefacts déposés — un test existant est tombé dessus.
Elles sont donc écartées de la numérotation dès leur naissance, ce qui ne renumérote rien de
déposé ; la condition est tenue par un test, une cible sans rang ne pouvant pas être publiée.
Et la règle de lecture du projet d'une copie ne retombe PAS sur le repli : NULL sans
collection veut dire « n'a jamais eu de projet », ce qui porte « Importer au fonds » sans
colonne de plus.

**Ce que la relecture croisée a mesuré.** La migration sur la base de recette par deux
chemins (v28 → v30 d'un trait ; v28 → v29 par le code d'avant, puis v30), au résultat
identique, et sur dix bases faites pour la faire mentir ou lever : aucune ne lève. Une
trentaine de gestes rejoués avant et après : seuls écarts, deux clés de plus sur trois
réponses d'album (`document_id`, `projet_id`) et les lignes neuves du journal. Aucune des
deux clés ne sort par un export ; le login d'un compte qui n'a fait qu'importer ne sort
d'aucun artefact. Quatre de ses mutants survivaient à la suite ENTIÈRE, tous par un décor de
test trop mince : fermés dans le second commit, avec le nom du projet sur une demande, un
refus nommé à la suppression d'un projet qu'un album désigne encore (c'était une erreur
brute, sur une base retouchée seulement), et la fin des emplois écrite quand on détruit un
album. Suite par défaut entière sur la copie : 1 643 passés.

**Ce qui n'est pas fait.** Ni passe navigateur, ni suite dans l'image, ni recette, ni
lecture de la base de production. Le second commit n'a pas été relu par une autre session
que la session de pilotage. `CLAUDE.md` et la documentation d'usage ne disent rien de tout
cela : ils suivront le portage.

### Le deuxième commit de la tranche 2, écrit, relu et corrigé sur une copie — 2026-10-14

Sur la copie `fonds-c2` du scratchpad de la session de pilotage, partie de `5311ccc` : les
deux commits du premier y sont repris (un seul conflit, dans le test des colonnes classées,
où `AUTH-11` avait ajouté son contrôle ; les deux intentions sont gardées), puis le deuxième,
et quatre correctifs. NON portés, pour la même raison que le premier ; ils ne se citent donc
pas ici par leur identifiant.

**Ce qu'il fait.** Supprimer a deux réponses. Supprimer définitivement sans rien demander
suppose quatre conditions : écrire dans toutes les collections de l'album (la règle
d'`AUTH-10`), l'avoir importé, ne pas être un compte partagé, et que personne d'autre n'y ait
travaillé — lu dans le journal, sur ce qui vit encore : actes sur les régions, corrections
de grammaire, validations, scans ajoutés ou retirés, attributs de case, notice, paternité,
relecture forcée ; une passe automatique ne compte pas, un travail d'auteur inconnu compte
comme celui d'un autre. Sinon, une demande, que l'administrateur accepte ou garde. Les albums
d'avant la v30, d'importateur inconnu, se demandent tous. Une planche suit la règle du
document. Sortir un album de sa dernière collection aboutit : la copie part au fonds avec son
projet. Quatre routes neuves (le fonds, les demandes, en déposer, y répondre), réservées à la
portée totale sauf le dépôt d'une demande. La garde, la destruction et la réponse se font
sous le même verrou d'écriture.

**Ce que la relecture croisée a trouvé** — verdict « à corriger avant de porter », les gardes
posées tenant (32 de ses 33 mutants tombés). Un attribut de case posé par un autre ne comptait
pas comme travail : l'importateur détruisait sans demander, seul chemin sans administrateur
trouvé. La garde se lisait hors transaction : un travail validé entre elle et la destruction
partait avec l'album. `partage` se publiait à toute lectrice. Un test manquait sur le nom du
projet d'une demande. Tout cela est corrigé, chaque correctif tenu par un mutant tombé. Restent
ouverts, dans la zone du `Reste` : le nom du demandeur lu à travers les collections, la
réutilisation des identifiants, la copie au fonds que son propriétaire ne reprend pas. Elle a
trouvé aussi un défaut ANTÉRIEUR, présent en production et rejoué sur `5311ccc` : Ctrl+Z, sur
une région dont l'identifiant a été repris par une autre, efface un locuteur dans une
collection qu'on ne lit pas, ou rend dans son refus le texte de cette région et le login de
son auteur — sans qu'aucune destruction d'album soit nécessaire. Il est corrigé à part, dans
le lot en cours.

**Preuves.** Suite par défaut sur la copie : 1 759 passés. Mutants de l'auteur : 58 sur le
commit (56 tombés, 2 équivalents, expliqués), 18 sur ses correctifs (17 tombés, 1 équivalent).
Deux tests navigateur tombent, comme le cadrage l'annonçait : l'écran d'avant ment avec ce
seul commit, et c'est pourquoi il ne partira pas sans le troisième.

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
