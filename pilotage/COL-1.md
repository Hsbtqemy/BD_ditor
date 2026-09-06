---
chantier: COL-1
statut: à venir
---

# COL-1 — l'incubateur : promouvoir le travail d'une collection fermée vers le corpus

**Point de départ** — 2026-09-06, demandé en propres termes : *« avoir éventuellement un
groupe petit, fermé, qui est celui dans lequel opèrent les stagiaires et les étudiants,
qu'on puisse après migrer vers un autre espace, afin de le rendre accessible avec d'autres
sources. Un peu comme un cluster, qu'on intégrerait ensuite dans le corpus principal. »*

**Le patron existe déjà dans ce projet, une échelle plus bas.** Le lexique situé (A4) fait
exactement cela pour les TERMES : `collection_id` local, puis promotion en global —
*patron mentions→entités*, écrit dans la docstring de `LexiqueIn`. COL-1 applique le même
mouvement au CONTENU. Ce n'est donc pas une idée neuve à valider, c'est une doctrine
existante à étendre.

**Et la moitié marche déjà sans qu'on ait rien à écrire** : un album vit dans 0..N
collections, les deux gestes de rattachement sont exposés et câblés à l'écran. C'est
l'autre moitié — le vocabulaire — qui ne suit pas, et personne ne le verrait échouer.

## Reste

### Ce qui marche déjà, et qu'il faut éprouver plutôt que construire
- [ ] Un album rattaché à une seconde collection y emporte ses régions, annotations, tokens et personnages — à ÉPROUVER, pas à déduire. Attendu : aucun de ces objets n'est cloisonné par collection, leur visibilité se dérivant par album → collection ; un lecteur de la collection cible voit donc le travail sans qu'aucune de ces lignes n'ait bougé
- [ ] **La provenance survit intacte au déplacement** — `evenement` référence des identifiants de région, jamais des collections. Attendu : après promotion, le journal attribue toujours le travail aux personnes qui l'ont fait. C'est la propriété qui rend l'incubateur HONNÊTE : le travail est promu, la paternité n'est pas blanchie, et c'est exactement ce qu'un projet de recherche doit garantir à des stagiaires
- [ ] **La promotion se fait sans trou** : rattacher à la cible, vérifier, détacher de l'incubateur — dans cet ordre. Un album vivant dans plusieurs collections à la fois, il n'y a aucun instant où il n'est nulle part ; et le 409 « zéro collection pour un album » interdit l'ordre inverse, donc la garde existante suffit

### Le vocabulaire ne suit pas, et c'est le piège
- [ ] **Le constat est reproduit** : un tag créé dans l'incubateur reste invisible depuis la collection cible une fois l'album déplacé. Attendu : `/api/tags` filtre par `clause_terme` (`main.py:1148`), le tag est donc POSÉ sur l'annotation et ABSENT de la liste. Rien ne casse — le nuage de tags est amputé et le « % défini » se calcule sur un vocabulaire partiel. C'est une dégradation ANALYTIQUE, la pire sorte : elle ne lève aucune erreur
- [ ] La promotion d'un terme fonctionne par l'API existante — `PATCH /api/tags/{id}/lexique` (et ses équivalents dimension / valeur / domaine) avec `collection_id: null`. `LexiqueIn` l'accepte et sa docstring le déclare : « `collection_id: null` explicite = promotion en GLOBAL ». À éprouver de bout en bout, y compris la contrainte v24 — une valeur ne peut pas devenir plus globale que sa dimension
- [ ] **L'ORDRE est écrit là où on le cherchera** : promouvoir le vocabulaire d'abord, déplacer les albums ensuite. L'inverse ouvre une fenêtre pendant laquelle le corpus principal porte des annotations dont le vocabulaire est invisible — et cette fenêtre ne se signale nulle part, donc elle peut durer des mois

### Ce qu'il faut réellement construire
- [ ] **Une requête dit quels termes LOCAUX sont employés par les albums qu'on s'apprête à déplacer.** C'est le seul renseignement qui manque vraiment : rien ne le donne aujourd'hui, et promouvoir « tout le vocabulaire de l'incubateur » promouvrait aussi ce qui devait rester local. Attendu : la liste des tags / dimensions / valeurs / domaines dont `collection_id` = l'incubateur ET qui sont employés par au moins une région des albums concernés
- [ ] Un geste « promouvoir cette collection » enchaîne les deux temps dans le bon ordre et rend compte — N termes promus, M albums rattachés, et ce qui a été laissé. Sans lui, la manœuvre est N patches plus M rattachements à la main, et une erreur d'ordre ne se voit pas
- [ ] **Le geste est réversible, ou son irréversibilité est écrite.** Détacher un album se refait ; promouvoir un terme en global ne se défait pas tout seul — `collection_id` passé à NULL, la collection d'origine n'est plus référencée nulle part. Si le retour arrière est impossible, la promotion doit le DIRE avant, pas après

### Le réglage d'incubation
- [ ] Le groupe fermé reçoit `ecriture` sur l'incubateur **et `lecture` sur la collection principale**. Attendu : les stagiaires réemploient le vocabulaire de référence au lieu d'en réinventer un, et ne créent en local que ce qui est neuf — c'est-à-dire exactement ce qu'il faudra promouvoir. Une seule ligne d'accès, qui divise le travail de promotion à venir
- [ ] Ce que voit un incubateur de la mesure INTER-annotateurs est tranché : `GET /api/analyse/accord-inter` porte sur les albums où l'on ÉCRIT, donc un groupe fermé mesure son propre accord — ce qui est probablement souhaitable en contexte pédagogique. À confirmer plutôt qu'à découvrir : la règle d'AUTH-1 est *ceux qui voient la mesure sont ceux qu'elle mesure*

## Contexte

**Ce que l'incubateur est, exactement.** Une collection ordinaire, avec un groupe qui n'a
d'accès que sur elle. Rien à inventer côté cloisonnement : AUTH-2 et AUTH-3 ont fait de la
collection l'unité, et un tiers ne voit rien (404). Le neuf n'est pas l'enfermement, c'est
la SORTIE.

**Pourquoi la question « migrer ce qu'un groupe a produit » n'avait pas d'objet.** Un
groupe n'apparaît qu'à un seul endroit du modèle : comme `principal` dans
`collection_acces`. C'est une clé qui ouvre une porte, jamais un propriétaire de contenu —
et le journal A3 nomme des personnes, jamais des groupes, ce qui est juste : un groupe
n'est pas un auteur. Ce qui se déplace n'est donc pas « la production d'un groupe », c'est
un ALBUM, et son travail voyage avec lui parce qu'il pend à ses planches et non à sa
collection.

**Ce que ce chantier N'EST PAS.** La conversation du 2026-09-06 a d'abord exploré une
duplication d'album sans ses annotations — « la promo suivante repart à zéro sur les mêmes
planches ». Besoin distinct, écarté ce jour-là comme n'étant pas celui-ci : ce serait un
FORK, pas une promotion. Il vaut d'être noté parce que sa ligne de coupe serait
remarquablement nette — garder la segmentation et l'OCR, mécaniques et redérivables ;
laisser les annotations, tags et personnages, qui SONT l'exercice. C'est exactement la
frontière ML / humain que le projet trace déjà. Rien n'existe pour le faire aujourd'hui,
vérifié.

**Indépendance.** COL-1 ne dépend d'aucune décision d'`AUTH-7` : le patron marche avec le
fichier de comptes actuel, avec LLDAP, ou avec Authentik. Il ne touche pas non plus
`autorisation.py` — la portée d'un terme et celle d'un album sont déjà écrites, on ne fait
que les faire jouer ensemble. Le seul lien est de sens : si l'inscription en nombre
devient réelle (`AUTH-7`), l'incubateur devient le lieu naturel où ces arrivants
travaillent.
