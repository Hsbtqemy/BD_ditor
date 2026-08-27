---
chantier: AUTH-2
statut: interrompu
---

# AUTH-2 — un point de passage unique pour l'autorisation

**Arrêté sur** — le socle et le premier tiers du câblage, commit `d36816c`, 27 août.
`autorisation.py` existe et répond une `Portee` ; 51 routes sur 111 la consultent, 48
restent nommées dans `A_CABLER`, 12 sont hors périmètre écrit. Reprendre par la famille
« vocabulaire », qui est la plus grosse et dont la question de fond (global ou par
collection ?) commande tout le reste.

## Reste

### Le modèle
- [x] Une table `collection_acces` (collection, principal, niveau) où `principal` est soit un login, soit un nom de groupe lu dans `Remote-Groups` : Authelia dit QUI, l'application décide ce que ça ouvre
- [x] Aucune appartenance de groupe n'est stockée — on référence un NOM de groupe, la liste vient de l'en-tête à chaque requête, comme en AUTH-1
- [x] Migration : une collection par défaut est créée et les albums existants y sont rangés ; après elle, `SELECT COUNT(*) FROM albums WHERE id NOT IN (SELECT album_id FROM collection_album)` vaut 0
- [x] Créer un album range TOUJOURS dans une collection (`collection_id` accepté, collection de repli sinon) : l'orphelin n'existe pas dans le modèle, donc aucune route n'a à trancher son sort
- [x] La raison de ne PAS poser cette garantie en contrainte SQL est écrite : `collection_album` est une jointure N-N, « au moins une » ne s'y exprime pas sans déclencheur, et le dépôt a déjà écarté les déclencheurs comme fragiles (cf. l'index FTS)

### Le passage obligé
- [x] Une dépendance unique répond « quelles collections cette requête a-t-elle le droit de voir, et en écriture ou en lecture », et c'est le SEUL endroit du code où cette question se tranche
- [x] Elle vit dans son propre module, pas dans `main.py` : le fichier fait près de 3 000 lignes, et mêler un découpage (ARCH-1) à la pose d'un contrôle d'accès rendrait indécidable lequel des deux a cassé quoi
- [x] Sans proxy d'auth (`BD_AUTH_PROXY` faux), le point de passage laisse TOUT passer : le mono-poste se comporte exactement comme avant, prouvé par un test
- [x] Un test échoue si une nouvelle route accède aux données sans passer par le point de passage — sinon l'oubli d'une seule route est une fuite silencieuse
- [x] Un test échoue aussi si un MONTAGE de fichiers statiques sert autre chose que les assets : un montage n'est pas une route et échappe à toute dépendance
- [ ] La liste `A_CABLER` de `tests/test_autorisation.py` atteint ZÉRO — 48 routes au 2026-08-27, sur 111 (51 cloisonnées, 12 hors périmètre écrit)

### Les routes qui ne prennent pas `Depends(db)`
- [x] `/api/jobs` et `/api/jobs/{id}` ne montrent que les travaux dont TOUTES les planches sont autorisées : la progression d'un lot cite des planches, donc des albums
- [x] `POST /api/jobs` ne lance un lot que sur les planches autorisées en ÉCRITURE, en filtrant plutôt qu'en refusant en bloc
- [x] `/api/ml/liberer` libère un verrou global : réservé aux administrateurs, en 403 (le refus parle des droits de l'appelant, pas du corpus)
- [ ] `POST /api/sharedocs/importer` écrit une planche dans un album : il lui faut le droit d'écrire sur cet album

### Les endroits où ça fuit
- [x] La recherche FTS ne renvoie que des régions de collections autorisées, en passant par la jointure `albums` et non par la table `recherche`, qui est dénormalisée et ne connaît ni album ni collection
- [x] `GET /api/recherche/export.csv` est scopé par le même cœur que `GET /api/recherche` — deux routes, une seule logique de requête
- [x] Les quatre surfaces d'analyse (distribution, concordance, croisement, comparaison) sont filtrées dans `_analyse_filtres`, le seul endroit qu'elles partagent, pas chacune à sa façon
- [x] Les trois exports (JSON-LD, CSV, TEI) n'exposent pas ce que l'UI cache
- [x] `/derivatives` n'est plus un montage `StaticFiles` mais une route cloisonnée : l'image web de toute planche était lisible à un chemin devinable, quelle que soit la rigueur des routes JSON
- [x] Le remplacement du montage ne perd PAS la protection contre la traversée de répertoire : la base sert d'allowlist (`planches.chemin_web`), donc `..` ne correspond à aucune ligne
- [ ] Le nuage de tags et le lexique ne révèlent pas le vocabulaire de collections non autorisées
- [ ] `GET /api/corpus` compte les tags sans filtre : tranché avec la question du vocabulaire, pas avant
- [ ] Le manifeste IIIF (`tools/iiif_manifest.py`, hors application) a son sort écrit : il ne passe par aucune route, donc par aucun contrôle

### Ce qu'il reste à câbler, par famille
- [ ] Vocabulaire : tags, personnages, domaines, dimensions, valeurs, lexique — une trentaine de routes, et la question de fond est la même pour toutes (le vocabulaire est-il global ou par collection ?)
- [ ] Correction grammaticale : `PUT`/`DELETE /api/regions/{id}/tokens/{ordre}` et `POST .../grammaire/valider` (la lecture `GET .../tokens` est faite)
- [ ] Annulation : `GET /api/undo/prochain` et `POST /api/undo` remontent le journal, qui n'a pas de notion de collection — annuler l'acte d'un autre sur un album qu'on ne voit pas doit être impossible
- [ ] Contributions d'album (3 routes) : elles portent sur un album, donc le filtre existe déjà, seul le câblage manque
- [ ] Rapports d'accord : `GET /api/analyse/accord` et `/accord-inter` agrègent les tokens de TOUT le corpus — un taux d'accord global révèle l'existence et le volume du travail des autres, sans en montrer le contenu
- [ ] `GET /api/analyse/info` dit ce que l'analyse a sous la main, donc combien de corpus il y a

### Ce qui reste ouvert, écrit noir sur blanc
- [x] `docs/hebergement-securite.md` (§6) énonce que `GET /api/sauvegarde` et le dépôt ShareDocs exportent la base ENTIÈRE et restent accessibles à tous : toute personne ayant accès à l'instance peut aspirer l'intégralité du corpus
- [x] La condition de réouverture est écrite avec : dès que l'instance accueille quelqu'un qui n'a pas le droit de tout voir, cette décision se rejoue

### L'interface
- [ ] La Bibliothèque demande explicitement une collection à la création d'un album — l'API accepte le défaut, mais laisser l'UI choisir à notre place ferait s'entasser tout le corpus dans la collection de repli, et le cloisonnement ne servirait jamais
- [ ] Une route de création de collection existe : `GET /api/collections` est aujourd'hui en lecture seule (l'écriture est headless, dans `tools/gerer_collections.py`), donc l'UI ne peut pas sortir d'un état à zéro collection
- [ ] Les accès d'une collection se lisent et se modifient depuis l'UI, sinon `collection_acces` ne se remplit qu'en SQL à la main

## Contexte

**C'est l'investissement architectural de toute la séquence, et l'ordre n'est pas
négociable** : AUTH-3 (espaces de travail) et DROIT-1 (tiering) se posent tous les deux
DESSUS. Les écrire avant reviendrait à auditer 94 points d'entrée deux fois, puis trois.

Le risque n'est pas la difficulté, c'est l'exhaustivité. Une ACL qui couvre 108 routes sur
109 ne cloisonne rien — et le trou ne se voit pas, puisque tout marche. D'où la case du
test qui refuse une route non scopée : c'est la seule vraie protection, et c'est la même
leçon que SANTE-1, où un vert mesurait l'absence de mesure.

**Reconnaissance du 2026-08-27** — 109 routes, 94 `Depends(db)`, **15 sans**. La version
précédente de cette fiche supposait des exclusions anodines (santé, statiques, `/api/moi`).
Elles ne le sont pas : `GET /api/sauvegarde` déverse toute la base, `deposer-sauvegarde`
la pousse sur WebDAV, `/api/jobs` liste des travaux tous albums confondus. Un contrôle
branché sur `Depends(db)` les manquerait TOUTES, et ce sont les fuites les plus larges.
D'où une zone entière de la fiche qui leur est consacrée.

**Trois arbitrages tranchés le 2026-08-27.**

1. *Le droit* — table `collection_acces` plutôt qu'une convention de nommage des groupes
   Authelia. La convention coûtait moins de code mais mettait le modèle hors de portée de
   l'application : ni affichage, ni modification, et un renommage de collection cassant
   l'accès en silence. AUTH-3 se pose sur la table, pas sur la convention.

2. *Les orphelins* — interdits. La base compte 3 albums et 0 collection : « visible par
   défaut » n'aurait été un moindre coût qu'en apparence, et c'est le seul des trois choix
   où un album oublié ne peut pas fuir, l'état n'existant pas. Migration mesurée : 3 lignes.

3. *La sauvegarde* — laissée OUVERTE, et écrite comme telle. C'est une décision assumée,
   pas un oubli : elle suppose que les membres de l'instance se font mutuellement
   confiance sur l'intégralité du corpus. Tant qu'elle tient, le cloisonnement du reste
   protège de l'accident et de la confusion, pas d'une exfiltration délibérée — et la
   distinction doit rester lisible dans la doc, sans quoi on se croira protégé.

Deux pièges propres à ce dépôt. La table FTS `recherche` **agrège OCR, note, tags et
lemmes** sans porter la moindre trace de collection : la scoper suppose de rejoindre le
résultat vers `regions → planches → albums → collection_album`, à chaque requête. Et
`main.py` fait 2 969 lignes : c'est là qu'ARCH-1 cesse d'être une coquetterie — mais on
ne découpe PAS pendant cette passe, on pose un module propre et `main.py` n'y gagne que
des lignes d'appel, de sorte qu'ARCH-1 reste entier après.

La session ShareDocs unique découverte pendant cette reconnaissance part dans SHARE-1 :
c'est un défaut réel, mais le corriger n'est pas autoriser.
