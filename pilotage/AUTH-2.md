---
chantier: AUTH-2
statut: livré
---

# AUTH-2 — un point de passage unique pour l'autorisation

**Arrêté sur** — la relecture des filtres de lecture, commit `1ba0e1d`, 28 août. Elle a trouvé un défaut
sous trois formes, toutes vertes : un terme du vocabulaire pouvait être plus GLOBAL que
celui dont il dépend, et c'est le nom du parent qui fuyait — un axe d'analyse, pas un mot.
Corrigé par héritage à la création, filtre du parent à la lecture, et une migration v24 qui
recolle l'existant. Cinq gardes vérifiées par mutation.

Le chantier est LIVRÉ. AUTH-3 porte désormais tout ce qui manque à `collection_acces`
pour se remplir autrement qu'en SQL à la main.

## Reste

### Le modèle
- [x] Une table `collection_acces` (collection, principal, niveau) où `principal` est soit un login, soit un nom de groupe lu dans `Remote-Groups` : Authelia dit QUI, l'application décide ce que ça ouvre
- [x] Aucune appartenance de groupe n'est stockée — on référence un NOM de groupe, la liste vient de l'en-tête à chaque requête, comme en AUTH-1
- [x] Migration : une collection par défaut est créée et les albums existants y sont rangés ; après elle, `SELECT COUNT(*) FROM albums WHERE id NOT IN (SELECT album_id FROM collection_album)` vaut 0
- [x] Créer un album range TOUJOURS dans une collection (`collection_id` accepté, collection de repli sinon) : l'orphelin n'existe pas dans le modèle, donc aucune route n'a à trancher son sort
- [x] La raison de ne PAS poser cette garantie en contrainte SQL est écrite : `collection_album` est une jointure N-N, « au moins une » ne s'y exprime pas sans déclencheur, et le dépôt a déjà écarté les déclencheurs comme fragiles

### Le passage obligé
- [x] Une dépendance unique répond « quelles collections cette requête a-t-elle le droit de voir, et en écriture ou en lecture », et c'est le SEUL endroit du code où cette question se tranche
- [x] Elle vit dans son propre module, pas dans `main.py` : mêler un découpage (ARCH-1) à la pose d'un contrôle d'accès rendrait indécidable lequel des deux a cassé quoi
- [x] Sans proxy d'auth (`BD_AUTH_PROXY` faux), le point de passage laisse TOUT passer : le mono-poste se comporte exactement comme avant, prouvé par un test
- [x] Un test échoue si une nouvelle route accède aux données sans passer par le point de passage — sinon l'oubli d'une seule route est une fuite silencieuse
- [x] Un test échoue aussi si un MONTAGE de fichiers statiques sert autre chose que les assets : un montage n'est pas une route et échappe à toute dépendance
- [x] La liste `A_CABLER` de `tests/test_autorisation.py` atteint ZÉRO — 99 routes cloisonnées sur 111, 12 hors périmètre écrit

### Les routes qui ne prennent pas `Depends(db)`
- [x] `/api/jobs` et `/api/jobs/{id}` ne montrent que les travaux dont TOUTES les planches sont autorisées : la progression d'un lot cite des planches, donc des albums
- [x] `POST /api/jobs` ne lance un lot que sur les planches autorisées en ÉCRITURE, en filtrant plutôt qu'en refusant en bloc
- [x] `/api/ml/liberer` libère un verrou global : réservé aux administrateurs, en 403 (le refus parle des droits de l'appelant, pas du corpus)
- [x] `POST /api/sharedocs/importer` exige le droit d'écrire sur l'album cible, et range l'album qu'il crée dans une collection comme n'importe quelle création

### Les endroits où ça fuit
- [x] La recherche FTS ne renvoie que des régions de collections autorisées, en passant par la jointure `albums` et non par la table `recherche`, qui est dénormalisée et ne connaît ni album ni collection
- [x] `GET /api/recherche/export.csv` est scopé par le même cœur que `GET /api/recherche` — deux routes, une seule logique de requête
- [x] Les quatre surfaces d'analyse (distribution, concordance, croisement, comparaison) sont filtrées dans `_analyse_filtres`, le seul endroit qu'elles partagent, pas chacune à sa façon
- [x] Les trois exports (JSON-LD, CSV, TEI) n'exposent pas ce que l'UI cache
- [x] `/derivatives` n'est plus un montage `StaticFiles` mais une route cloisonnée : l'image web de toute planche était lisible à un chemin devinable, quelle que soit la rigueur des routes JSON
- [x] Le remplacement du montage ne perd PAS la protection contre la traversée de répertoire : la base sert d'allowlist (`planches.chemin_web`), donc `..` ne correspond à aucune ligne
- [x] Le nuage de tags et le lexique ne révèlent pas le vocabulaire de collections non autorisées, et leurs COMPTEURS (fréquence, usages) ne portent que sur le sous-corpus lisible
- [x] `GET /api/corpus` compte les tags selon la règle du vocabulaire (global, ou local à une collection lue), et non plus sans filtre
- [x] Le manifeste IIIF a son sort écrit (2026-08-28) : `--base-url` doit désigner le serveur qui servira les images au destinataire, jamais l'application — qui sert `/derivatives` par une route cloisonnée depuis AUTH-2. L'outil REFUSE d'écrire avec le placeholder et AVERTIT sur un hôte local ; ce que les images doivent devenir relève de DROIT-1, pas d'ici

### Les familles câblées
- [x] Vocabulaire (tags, domaines, dimensions, valeurs, lexique) : un terme est visible s'il est GLOBAL (`collection_id` NULL) ou local à une collection qu'on lit — la règle du lexique situé (A4), pas celle des données
- [x] Créer un terme (tag, domaine, rôle de contribution) ou importer du vocabulaire exige un droit d'écriture quelque part : sinon une personne en lecture seule pourrait polluer un vocabulaire partagé
- [x] Personnages : portée DÉRIVÉE de leurs apparitions, plus ceux qui n'apparaissent nulle part — sans cette exception, le personnage qu'on vient de créer disparaîtrait avant qu'on ait pu lui attribuer une bulle
- [x] Correction grammaticale : corriger, valider et annuler une correction passent par l'accès en écriture à la région
- [x] Annulation : Ctrl+Z est PERSONNEL (chacun n'annule que ses actes), et la raison de ne pas scoper par collection est écrite — la cible d'une suppression n'existe plus
- [x] Contributions d'album : autorisées par leur album, y compris la suppression, qui ne reçoit pourtant que l'id de la contribution
- [x] Rapports d'accord : scopés aux albums lisibles ; le cœur `accord_inter` a gagné le paramètre `album_ids` que `accord` avait déjà
- [x] `tools/description_collection.py` en profite : son bloc d'accord inter annonçait une portée « corpus » sous une rubrique de collection, il annonce désormais la bonne
- [x] `GET /api/analyse/info` : la volumétrie est filtrée, `meta` (modèle, date de réindexation) reste entier — c'est un fait d'exploitation, pas une donnée de corpus

### Ce qui reste ouvert, écrit noir sur blanc
- [x] `docs/hebergement-securite.md` (§6) énonce que `GET /api/sauvegarde` et le dépôt ShareDocs exportent la base ENTIÈRE et restent accessibles à tous : toute personne ayant accès à l'instance peut aspirer l'intégralité du corpus
- [x] La condition de réouverture est écrite avec : dès que l'instance accueille quelqu'un qui n'a pas le droit de tout voir, cette décision se rejoue

### Voir n'est pas changer
- [x] Les routes d'ÉCRITURE portent une garde d'écriture et non de lecture — 19 n'en avaient pas au premier jet : les accesseurs de vocabulaire et de personnage répondaient « peux-tu le voir », et la suite était verte
- [x] `Portee.peut_ecrire_terme(collection_id)` : un terme LOCAL s'édite si l'on écrit dans sa collection, un terme GLOBAL si l'on écrit quelque part (personne ne le possède en propre)
- [x] Changer la PORTÉE d'un terme exige d'écrire dans la collection VISÉE, pas seulement dans la sienne : sans quoi on rangerait son vocabulaire dans l'étude d'un autre
- [x] `POST /api/albums/{id}/contributions` n'avait AUCUNE garde d'écriture : on pouvait ajouter une paternité à l'album d'un autre
- [x] Annuler un lot (`POST /api/jobs/{id}/annuler`) interrompt un traitement : réservé à qui peut écrire sur ses planches
- [x] `POST /api/undo` exige un droit d'écriture — le filtre par agent ne suffisait pas : quelqu'un rétrogradé en lecture seule pouvait défaire ses anciens actes
- [x] Les gardes sont éprouvées par MUTATION, pas seulement écrites : retirer la garde fait échouer les tests (vérifié le 2026-08-27)
- [x] `_attributs_de` filtre les valeurs comme des TERMES : un objet PARTAGÉ (un personnage traverse les albums) exposait sinon la grille d'analyse d'une autre étude, alors que `GET /api/attributs/valeurs` la masquait déjà — on la retrouvait par la bande
- [x] Le résiduel d'`undo` est ASSUMÉ par écrit (`docs/undo.md`, 2026-08-28) : le fermer supposerait de lire l'album de la cible dans l'instantané journalisé, et un contrôle d'accès qui dépend de la forme d'un JSON est plus fragile que le trou qu'il bouche

### Ce que le cliquet ne prouve PAS
- [x] Les routes d'écriture ont été relues une à une pour vérifier la NATURE de leur garde (lecture ou écriture) — c'est cette passe qui a trouvé les 19
- [x] Les routes de LECTURE ont été passées en revue une fois : toutes portent un filtre (parfois délégué à `_recherche_rows`, `_analyse_filtres` ou `_agent_undo`), et la revue a sorti l'écart de `_attributs_de`
- [x] Les routes de LECTURE sont relues à leur tour pour vérifier que le filtre appliqué est le BON : le test statique prouve qu'une route consulte la portée, jamais qu'elle en tire la bonne conclusion
- [x] Les routes de LISTE passent en premier dans cette relecture : une lecture par identifiant qui se trompe renvoie un objet, une liste qui se trompe en renvoie mille

> **Ce que la relecture a trouvé (2026-08-28)** — un seul défaut, sous trois formes, et
> aucune des trois n'était rouge. Les routes filtraient bien le terme demandé ; elles ne
> filtraient pas celui dont il DÉPEND.
>
> `POST .../valeurs` et `POST /api/attributs/dimensions` n'ont jamais posé de
> `collection_id`. Une valeur créée sous un axe local à une étude naissait donc GLOBALE,
> une dimension rattachée à un domaine privé aussi. Ce qui fuit n'est pas le mot —
> « palpable » ne dit rien — mais ce que les routes à plat traînent avec lui : le NOM de
> l'axe, du domaine, c'est-à-dire une grille d'analyse. C'est exactement le dommage que
> `_attributs_de` nommait déjà, réapparu par une autre porte.
>
> Le `resume` de `GET /api/lexique` était le troisième cas, et le plus visible à l'usage :
> ses quatre listes étaient filtrées, son total ne l'était pas. Le panneau annonçait « 3
> définis sur 41 » à qui n'en voit que trois — le total DIT le volume de vocabulaire des
> autres, et le pourcentage devient faux pour la personne qui le lit.
- [x] La création fait HÉRITER la portée du parent (domaine → dimension → valeur) : un terme ne peut pas être plus global que celui dont il dépend
- [x] Les lectures à plat filtrent le terme PARENT en plus du terme — l'héritage ne vaut que pour les créations à venir, or toute base antérieure à v24 contient déjà la situation
- [x] La migration v24 RECOLLE l'existant plutôt que de seulement le masquer : sans elle, le « % défini » continuerait de compter un terme que les listes cachent. Deux témoins vérifient qu'elle ne déborde pas — un terme déjà local ailleurs est délibéré, un terme sous un parent global reste global
- [x] L'étape v24 est gardée par présence des COLONNES, pas de la table. Une garde de table passait les tests ciblés et cassait `test_migration_v19_vers_v20` : les schémas minimaux montent `domaine` sans sa portée, et les ALTER qui la posent sont eux-mêmes gardés. C'est la convention déjà écrite dans `_migrate`, retrouvée par la suite complète et non par la passe ciblée
- [x] `lexique_resume` se filtre comme ses listes. Il reçoit un FRAGMENT de portée, pas une `Portee` : `database.py` n'a pas à dépendre de `autorisation.py`, et la règle reste écrite à un seul endroit
- [x] Les cinq gardes sont vérifiées par MUTATION. La première passe a laissé l'une d'elles verte : le test prouvait la ceinture de lecture, pas l'héritage — les deux masquent le même symptôme. Corrigé en vérifiant la ligne STOCKÉE, seul endroit où l'héritage s'observe
- [x] Le tag d'une région lisible reste montré ENTIER, et l'écart avec `_attributs_de` est voulu : ce dernier masque une grille d'analyse, un tag n'est qu'un mot — la distinction était déjà écrite, la relecture n'a fait que la vérifier
- [x] Le panneau 📖 Lexique replie sur « Hors domaine » une dimension dont le domaine n'est PAS visible (locale à une collection qu'on lit, domaine à une autre). Sans ce repli elle n'était rendue nulle part — ni sous son domaine, absent de la liste, ni « hors domaine », son `domaine_id` n'étant pas nul : elle disparaissait de l'écran tout en restant éditable ailleurs. Le cloisonnement doit masquer ce qu'on n'a pas le droit de voir, jamais ce qu'on a le droit de modifier

### L'interface

> Deux cases ont quitté cette zone le 2026-08-28 : « créer une collection depuis l'UI » et
> « accorder / retirer un accès ». Elles étaient DÉJÀ écrites dans AUTH-3, et sa version
> est la bonne — elle vient avec la notion de PROPRIÉTAIRE, sans laquelle « qui a le droit
> de partager » n'a pas de réponse. Deux fiches revendiquant le même travail est exactement
> ce que le suivi est censé empêcher.
>
> Correction au passage, d'une affirmation d'hier faite avec trop d'aplomb : l'UI n'est PAS
> bloquée à zéro collection. `collection_par_defaut` en crée une au premier album. Ce qui
> manque, c'est d'en créer une SECONDE — et c'est AUTH-3.
- [x] La Bibliothèque demande explicitement une collection à la création d'un album — trois cas : plusieurs collections → choix à faire ; une seule → présélectionnée (poser une question à réponse unique serait de la cérémonie) ; aucune → pas de sélecteur, une note annonce le repli, ce qui évite l'impasse
- [x] Le champ n'apparaît PAS à l'édition : déplacer un album d'une collection à l'autre est un geste d'espace de travail, qui appartient à AUTH-3 — l'y montrer laisserait croire au déplacement
- [x] Un message dit POURQUOI on ne voit rien quand la portée est vide, sur les 4 surfaces, et il distingue DEUX pannes : « aucune collection ne vous est ouverte » (droit manquant) et « aucune identité ne parvient à l'application » (forward_auth muet) — la seconde n'a pas de pastille utilisateur, donc rien d'autre ne la signalerait
- [x] `GET /api/moi` renvoie un bloc `acces` (total / admin / nombre de collections lues et écrites). Il quitte `HORS_PERIMETRE` au passage : sa raison écrite disait « circulaire », ce qu'elle n'était pas — rapporter sa propre portée n'est pas s'y soumettre
- [x] Le bandeau est audité par axe sur les 4 surfaces × 2 thèmes, plus le cas sans identité : c'est le seul écran que verra une personne mal configurée, et il aurait été le seul que l'audit n'aurait jamais regardé

## Contexte

**C'est l'investissement architectural de toute la séquence, et l'ordre n'est pas
négociable** : AUTH-3 (espaces de travail) et DROIT-1 (tiering) se posent tous les deux
DESSUS. Les écrire avant reviendrait à auditer une centaine de points d'entrée deux fois,
puis trois.

Le risque n'est pas la difficulté, c'est l'exhaustivité. Une ACL qui couvre 110 routes sur
111 ne cloisonne rien — et le trou ne se voit pas, puisque tout marche. D'où le cliquet :
c'est la seule vraie protection, et c'est la même leçon que SANTE-1, où un vert mesurait
l'absence de mesure. Mais il faut savoir ce qu'il prouve et ce qu'il ne prouve pas : il
ferme la porte de l'OUBLI, pas celle de l'ERREUR. D'où une zone entière de la fiche qui
lui est consacrée, et qui reste ouverte.

**Reconnaissance du 2026-08-27** — 109 routes, 94 `Depends(db)`, **15 sans**. La version
initiale de cette fiche supposait des exclusions anodines (santé, statiques, `/api/moi`).
Elles ne l'étaient pas : `GET /api/sauvegarde` déverse toute la base, `deposer-sauvegarde`
la pousse sur WebDAV, `/api/jobs` liste des travaux tous albums confondus. Un contrôle
branché sur `Depends(db)` les aurait manquées TOUTES, et ce sont les fuites les plus larges.

**La plus large de toutes n'était même pas une route** : `/derivatives` était un montage
`StaticFiles`, servant l'image web de n'importe quelle planche à un chemin devinable. Un
montage échappe à toute dépendance ; le cliquet ne le voyait pas. Trouvé en relisant, pas
en testant — et le test regarde désormais aussi les montages.

**Une faille trouvée en relisant, après que tout fut vert.** Dix-neuf routes d'écriture ne
portaient qu'une garde de LECTURE : les accesseurs `_get_valeur`, `_get_dimension`,
`_get_domaine`, `_get_personnage` et la clause `clause_terme` répondent « peux-tu le
voir », pas « peux-tu le changer ». Une personne en lecture seule pouvait renommer ou
supprimer un tag, une dimension, un domaine, éditer n'importe quelle définition du lexique,
créer et fusionner des personnages — et ajouter une paternité à l'album d'un autre. La
suite était verte, le cliquet aussi. C'est le même motif que SANTE-1 sous une autre forme :
un contrôle bien réel, posé au mauvais niveau, ne mesure pas ce qu'on croit.

**Quatre arbitrages tranchés le 2026-08-27.**

1. *Le droit* — table `collection_acces` plutôt qu'une convention de nommage des groupes
   Authelia. La convention coûtait moins de code mais mettait le modèle hors de portée de
   l'application : ni affichage, ni modification, et un renommage de collection cassant
   l'accès en silence. AUTH-3 se pose sur la table, pas sur la convention.

2. *Les orphelins* — impossibles. La base comptait 3 albums et 0 collection : « visible
   par défaut » n'aurait été un moindre coût qu'en apparence, et c'est le seul des choix
   où un album oublié ne peut pas fuir, l'état n'existant pas. Une contrainte a nuancé
   l'exécution : il n'existe aucune route pour CRÉER une collection (l'écriture est
   headless), si bien qu'exiger une collection à la création d'album fermait l'API sur
   elle-même. L'invariant est donc tenu par construction — collection de repli à défaut —
   et c'est à l'UI d'exiger le choix explicite.

3. *La sauvegarde* — laissée OUVERTE, et écrite comme telle. Décision assumée, pas oubli :
   elle suppose que les membres de l'instance se font mutuellement confiance sur
   l'intégralité du corpus. Tant qu'elle tient, le cloisonnement protège de l'accident et
   de la confusion, pas d'une exfiltration délibérée — et la distinction doit rester
   lisible dans la doc, sans quoi on se croira protégé.

4. *Les personnages* — portée dérivée de leurs apparitions. Le premier cadrage présentait
   la question comme un enjeu de confidentialité ; c'était faux, et l'arbitrage 3 le
   montre : qui peut déjà télécharger la base entière n'apprend rien d'une liste de noms.
   Le vrai enjeu est d'USAGE — l'autocomplétion de locuteur puise dans le registre entier
   et grossirait avec l'instance au lieu de rester à la taille de l'étude.

Deux pièges propres à ce dépôt, désormais désamorcés. La table FTS `recherche` **agrège
OCR, note, tags et lemmes** sans porter la moindre trace de collection : elle se scope par
la jointure `albums`, jamais par elle-même. Et `main.py` frôle les 3 000 lignes : on n'a
PAS découpé pendant cette passe, le module d'autorisation est à part et `main.py` n'y a
gagné que des lignes d'appel, de sorte qu'ARCH-1 reste entier après.

La session ShareDocs unique, découverte pendant la reconnaissance, part dans SHARE-1 :
c'est un défaut réel, mais le corriger n'est pas autoriser.
