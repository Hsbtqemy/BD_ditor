---
chantier: AUTH-3
statut: livré
---

# AUTH-3 — espaces de travail : ouvrir une collection, y être invité

**Arrêté sur** — le chantier entier, commit `ad24c1d`, 28 août : le modèle de propriété, les 9 routes, et
l'écran Collections de la Bibliothèque. `collection_acces` cesse de se remplir en SQL à la
main, ce qui était la seule chose entre le cloisonnement d'AUTH-2 et son usage réel.

La décision de forme : la propriété est un NIVEAU de plus dans `collection_acces`, pas une
colonne sur `collection`. Une seule source de vérité, la résolution d'AUTH-2 fonctionne
telle quelle, et un GROUPE peut posséder — un espace de travail survit rarement au départ
d'une personne. Contrepartie assumée et gardée : jamais zéro propriétaire.

Une passe de relecture, menée après coup sur du code entièrement vert, a trouvé cinq
écarts dont DEUX ouverts par le chantier lui-même : une écriture sans identité, et la
capture du nom de la collection de repli. Ils sont détaillés plus bas ; la leçon est celle
d'AUTH-2, redite — le vert dit qu'on n'a rien cassé, jamais qu'on n'a rien ouvert.

## Reste

### Propriété — le troisième palier
- [x] Une collection a un propriétaire, distinct de son champ descriptif `responsables` (JSON bibliographique nom/rôle/orcid, qui reste ce qu'il est : de la métadonnée de dépôt, pas un droit d'accès)
- [x] La propriété est un NIVEAU de plus dans `collection_acces` (`lecture` · `ecriture` · `proprietaire`) et non une colonne à part. Une seule source de vérité, la résolution d'AUTH-2 fonctionne telle quelle, et un GROUPE peut posséder — un espace de travail survit rarement au départ d'une personne
- [x] Les niveaux s'empilent DANS `Portee.__init__`, une fois : un `in portee.ecriture` qui oublierait les propriétaires serait un refus silencieux et parfaitement crédible
- [x] `peut_administrer()` est distinct de `peut_ecrire()` : écrire c'est annoter, posséder c'est décider qui d'autre entrera. Un membre en écriture n'hérite PAS du droit d'élargir le cercle — sinon il s'élargirait sans que le propriétaire le sache
- [x] L'administrateur (`bd-admins`) passe outre la propriété, et c'est écrit : c'est le recours quand quelqu'un quitte le projet. Le refuser fabriquerait des collections définitivement bloquées, dont la seule sortie serait un UPDATE en SQL — exactement ce que ce chantier supprime
- [x] Le refus d'administrer est un **403** et non un 404 : la collection vient d'être listée, on connaît son nom, un « introuvable » mentirait. Pour un tiers qui ne la voit pas, c'est bien un 404

### Les routes — `collection_acces` cesse de se remplir en SQL
- [x] `POST /api/collections` crée une collection et rend son créateur PROPRIÉTAIRE. Aucun droit préalable n'est exigé, délibérément : refuser la création à qui n'a encore rien rendrait l'application inutilisable au premier jour de chacun
- [x] Un administrateur qui crée ne s'inscrit PAS propriétaire (il possède déjà tout ; lui inventer un lien personnel fausserait la notion) ; hors proxy il n'y a personne à inscrire
- [x] `GET` / `PUT` / `DELETE /api/collections/{id}/acces…` accordent, changent et retirent. `PUT` est idempotent, ce qui fait de « promouvoir » et « rétrograder » le même geste
- [x] `PATCH` et `DELETE /api/collections/{id}` éditent les descripteurs et suppriment, réservés au propriétaire
- [x] `GET` / `PUT` / `DELETE /api/albums/{id}/collections…` gèrent l'appartenance N-N
- [x] Les 9 routes passent le cliquet d'AUTH-2 (109/120 cloisonnées, 0 à câbler)
- [x] Les 9 gardes sont vérifiées par MUTATION — une garde qu'aucun test ne fait tomber est décorative

### Appartenance des albums — N-N assumé
- [x] Un album peut vivre dans PLUSIEURS collections : le schéma est N-N depuis la v14, et c'est porteur de sens (un même album nourrit deux études). Dupliquer l'album casserait l'analyse inter-corpus, qui est la raison d'être du cloisonnement logique plutôt que physique
- [x] Ranger un album ailleurs demande d'écrire des DEUX côtés : sans le droit d'arrivée on déposerait son travail chez quelqu'un d'autre, sans le droit sur l'album on s'approprierait le travail d'un autre
- [x] La liste des collections d'un album partagé est PARTIELLE — même compromis que `_attributs_de` : mieux vaut ne pas montrer que révéler l'existence d'une étude voisine

### L'écran
- [x] La Bibliothèque a un écran Collections : créer, renommer, supprimer, voir qui a accès, accorder, retirer — c'est la case qui rend le reste utilisable, tout le travail ci-dessus restant sans elle du `curl`
- [x] Le formulaire d'accès dit clairement qu'un `principal` est un NOM et non une personne vérifiée : l'application n'a aucun annuaire (AUTH-1), et un login mal orthographié n'ouvre rien — silencieusement. C'est le mode d'échec à connaître avant d'exploiter une instance, donc il est écrit SOUS le formulaire et pas seulement dans la doc
- [x] L'écran distingue « propriétaire » de « administrateur qui passe outre » : afficher « propriétaire » à un administrateur lui ferait croire à un lien qu'il n'a pas
- [x] Un album se DÉPLACE depuis l'UI : AUTH-2 faisait choisir la collection à la création et cachait le champ à l'édition, faute de propriétaire pour dire qui a le droit de déplacer quoi. Le champ de création reste ce qu'il était ; l'édition montre l'appartenance N-N et permet d'ajouter ou de retirer
- [x] Les deux refus (dernier propriétaire, dernière collection) sont RENDUS et non avalés : ce sont des 409 qui nomment un état interdit, pas des droits manquants, et l'UI dit lequel. Le `<select>` de niveau se recharge même en cas d'échec, sinon l'écran afficherait un niveau que le serveur n'a pas accordé
- [x] L'écran est audité par axe (WCAG 2.1 AA), thèmes sombre et clair, à DEUX états : replié, puis déplié sur la liste des accès — c'est le seul écran du dépôt où l'on décide qui entre, on ne l'administre pas à l'aveugle
- [x] Deux comportements d'interface sont vérifiés par MUTATION : le rendu du refus 409, et l'affichage de l'appartenance à l'édition
- [x] `tools/gerer_collections.py` apprend `--proprietaire` / `--proprietaire-groupe`. Il n'est plus le SEUL outil d'écriture — c'était son défaut — mais il reste utile pour l'amorçage et les descripteurs de dépôt que l'écran ne couvre pas. Sans cette option il créait des collections que personne ne possède : un état valable (un shell n'a pas d'identité) mais rarement voulu, et il le DIT désormais dans son message de succès

### Ce que la relecture a trouvé — cinq écarts, sur une suite verte

> Passe de relecture du 2026-08-28, menée après coup sur du code entièrement vert. Aucun
> des cinq n'était rouge ; DEUX sont des trous que ce chantier a lui-même ouverts, et c'est
> ce qui rend la passe nécessaire : une suite verte dit qu'on n'a rien cassé, jamais qu'on
> n'a rien ouvert.

- [x] `POST /api/collections` ÉCRIVAIT sans identité derrière le proxy. « Aucun droit préalable » ne veut pas dire « aucune identité » — la première version confondait les deux, et c'était la seule écriture ouverte du dépôt, contredisant la fermeture par défaut d'AUTH-2. Refus en 403 qui NOMME la panne probable (forward_auth muet) plutôt qu'un 404 : ce n'est pas un objet qu'on cache, c'est une configuration à réparer
- [x] Le nom de la collection de REPLI est réservé. `collection_par_defaut` le désigne par son NOM ; tant que renommer exigeait un accès shell, le seul mode d'échec était bénin (« quelqu'un renomme le repli », un seau vide se recrée). Ce chantier a donné le renommage à tout propriétaire et rendu possible l'INVERSE — mesuré avant correction : un album d'administrateur créé sans collection atterrissait chez le renommeur, et lui devenait visible. C'est le mode d'échec que le choix du nom disait éviter. Garde à la création, au renommage, insensible à la casse, et dans l'outil headless
- [x] `statut_diffusion` n'était contrôlé que d'un côté : `gerer_collections.py` validait, la route non. Un champ à deux portes dont une seule contrôle n'est pas contrôlé — la liste vit désormais dans `config.py`, partagée
- [x] Les changements d'ACCÈS sont tracés dans le journal A3 (`lien` / `delien` sur `collection_acces`). L'écart venait de ma propre justification : `peut_administrer` se défend par le fait qu'un accès accordé par erreur doit rester traçable — sans trace, l'argument ne tenait pas. Non annulables : `undo._TABLES` est une liste blanche où `collection_acces` ne figure pas, défaire un partage par Ctrl+Z serait une surprise
- [x] Sortir un album d'une collection ÉTRANGÈRE répondait « c'est la dernière collection de cet album » — le garde-fou se déclenchait avant la vérification d'appartenance. Une phrase fausse sur une opération sans objet : un message d'erreur qui ment coûte plus cher que pas de message
- [x] Les huit gardes ajoutées par cette passe sont vérifiées par MUTATION

### Ce qui doit rester vrai
- [x] Retirer un accès ne détruit aucune donnée : les annotations faites par la personne restent, et le journal A3 continue de les lui attribuer
- [x] Supprimer une collection ne supprime pas ses albums (`collection_album` est une appartenance N-N ; le lien se défait, l'album survit). Refus tant qu'un album n'a qu'elle : supprimer par ricochet fabriquerait l'orphelin qu'AUTH-2 a retiré du modèle
- [x] Une collection sans aucun accès accordé reste accessible à son propriétaire — et JAMAIS zéro propriétaire : retirer ou rétrograder le dernier est un 409 qui nomme la contrainte
- [x] Le mono-poste local sans auth voit tout, comme aujourd'hui : la collection naît sans propriétaire, il n'y a personne à inscrire

## Contexte

**Reçu d'AUTH-2 le 2026-08-28.** Le cloisonnement est fait : `autorisation.py` tranche
« qui voit quoi », 99 routes sur 111 le consultent, et `collection_acces` est peuplée — mais
uniquement en SQL à la main. AUTH-2 avait dupliqué deux cases qui vivaient déjà ici (créer
une collection depuis l'UI, accorder un accès) ; elles lui ont été retirées, parce que la
version d'ici vient avec le PROPRIÉTAIRE, sans lequel « qui a le droit de partager » n'a
pas de réponse. Ce chantier est donc devenu le seul obstacle entre le cloisonnement et son
usage réel.

**C'est le modèle demandé le 2026-08-27 : « qu'un utilisateur puisse ouvrir une nouvelle
base, être ajouté à une qui existe ».** Le mot « base » y désigne un espace de travail,
pas un fichier SQLite — et c'est ce qui rend le chantier abordable.

Le conteneur est déjà là. `collection` (v14) porte `nom`, `description`, `licence_defaut`,
`base_legale`, `statut_diffusion`, `date_embargo`, `responsables`, une période de
couverture, et une appartenance N-N aux albums. Elle a été bâtie comme unité de DÉPÔT ;
c'est un espace de travail qui s'ignore. Il ne manque que la propriété et les accès.

**Un fichier SQLite par espace a été écarté** (arbitrage du 2026-08-27) : `BD_DB_PATH` est
certes configurable, mais toute l'application suppose une base unique via `Depends(db)`
(93 points), et l'isolation dure coûterait l'analyse inter-corpus — or l'Exploration,
l'accord inter-annotateurs et la recherche FTS n'ont d'intérêt que sur un corpus réuni.
Le cloisonnement est donc logique, pas physique, et sa solidité repose entièrement sur
AUTH-2. C'est le compromis à assumer les yeux ouverts : un bug d'ACL expose, là où des
fichiers séparés auraient protégé.
