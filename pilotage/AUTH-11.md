---
chantier: AUTH-11
statut: interrompu
---

# AUTH-11 — un terme qu'on ne lit pas ne se montre pas, ne sort pas, ne se devine pas

**Arrêté sur** — 2026-09-23, `9446d68` : **l'export d'une collection ne porte plus que son vocabulaire, et une région dont il ne reste qu'un tag caché n'est plus dite « annotée ».** Deux cases fermées, deux OUVERTES par la passe de revue — le journal A3, qui emporte le texte verbatim des œuvres de toute l'instance, et le contrôle des sorties, qui est une liste écrite à la main se présentant comme un inventaire. Restent les deux décisions de Hugo, l'index plein texte et l'unicité du libellé, chacune désormais chiffrée dans sa case.

Avant lui, `b206d41` (2026-09-11) : les deux cases qui ne demandaient aucune décision sont fermées — l'axe « dimension » du croisement, et le filtre par facette, locuteur compris, dans l'analyse puis dans la Recherche, qui avait le sien et que la passe de revue a trouvé resté ouvert. Les quatre qui restent attendent chacune autre chose qu'une clause : une décision sur l'index plein texte, un changement de schéma qui croise COL-1, le premier dépôt, et un indice mineur à fermer ou à écrire comme limite.

**Point de départ** — 2026-09-11, détaché de `DROIT-2` le jour même. La session d'ANA-6
avait mesuré que `_recherche_rows` montrait un tag local à une collection que le lecteur ne
lit pas ; l'équipe l'a confié à DROIT-2, en tête. La moitié « tags » s'y est fermée en deux
commits : les lectures qui ont leur propre requête (`df20d3d`), puis l'Atelier et les
exports d'un album, où l'écriture PRÉSERVE ce qu'elle cache (`a2ed353`). La passe de revue a
trouvé les six cases ci-dessous, et elles ne portent pas sur le droit d'exporter : elles
portent sur ce qu'on VOIT d'un terme. Laissées dans DROIT-2, elles auraient tenu ouvert un
chantier livré ; elles ont déménagé ici telles quelles, sauf la queue de la première, qui
avait vieilli dans la journée.

**La règle est déjà écrite, et ce chantier ne la change pas** : un tag, un domaine, une
dimension ou une valeur se voit s'il est GLOBAL ou local à une collection qu'on lit
(`portee.clause_terme`, AUTH-2 ; CLAUDE.md, § Autorisation par collection). Ce qui reste,
ce sont des lectures qui ne la consultent pas — et trois d'entre elles ne MONTRENT rien :
ce sont des oracles, où le terme se devine à la réponse.

## Reste

### Ce qui sort de l'instance
- [x] **Les exports de dépôt d'une collection emportent les termes des AUTRES collections** — le catalogue de tous les tags de l'instance avec leur définition et leur `collection_id` (`metadonnees_collection`, clé `tags_cat` : JSON et onglet « tags ») ; les tags posés, sans portée des termes (`ann_tags`) ; les valeurs d'attribut des personnages (`perso_attr`) ; les sujets DataCite et Dublin Core, qui prennent tous les tags et toutes les valeurs (`crosswalk_depot._sujets`). Ces artefacts QUITTENT l'instance. Attendu : l'export de A ne porte que le vocabulaire de A — global ⊕ local à A, la règle que suit déjà le « % défini » —, quel que soit qui exporte ; et `docs/export-metadonnees.md`, qui dit « les catalogues de référence restent globaux », réécrit avec. **Reporté le 2026-09-11 par l'équipe, « avec les portes, plus tard »** — et les portes ont reçu leur garde le même jour sans lui (`4b1d530`) : le report n'attend donc plus rien qui le rouvrira de lui-même. C'est le premier dépôt qui le rend pressant, et le renvoi est posé dans `DEPOT-1` — **fermé le 2026-09-23, `9446d68`.** Le vocabulaire suit l'APPARTENANCE du terme, catalogues ET liaisons, dans l'arbre JSON, les tables CSV, le classeur, la notice DataCite et la route du dépôt ; la règle est nommée une fois (`database.clause_appartenance`) au lieu d'être recopiée, et posée sur la COLLECTION et non sur la personne — un export figé qui varierait selon la portée de qui clique rendrait deux dépôts différents sans le dire. 19 mutants posés, 19 tués ; suite entière verte (1389). **Deux endroits restent hors périmètre et sont désormais ÉCRITS** plutôt que découverts : le journal A3 (case ci-dessus) et le bloc `vocabulaire` de la fiche de description, qui compte une COUVERTURE — décider si ces chiffres portent sur l'instance ou sur le dépôt change ce que la fiche FAIR affirme, et c'est une question de modèle, pas une clause à poser

- [ ] **Par le journal A3, un export de dépôt emporte l'OCR VERBATIM de TOUTE l'instance — et `--verbatim` n'y peut rien** — mesuré le 2026-09-23 par la passe de revue, sur les tables `activite` et `evenement` de `metadonnees_collection` (CSV, onglet XLSX, zip, et donc `POST …/depot/deposer` vers ShareDocs). `journal._REGION_COLS` contient `ocr_texte` et les charges `avant`/`apres` sont publiées mot pour mot : le texte de l'œuvre sort dans le mode PAR DÉFAUT, alors que `docs/export-metadonnees.md` promet « par défaut on n'expose que présence + longueur ». Et ce texte n'est pas celui de la collection déposée : c'est celui de toutes. Deux règles franchies, pas une — `DROIT-1` (le régime de diffusion, opposable à la SORTIE) et celle-ci. **Ce n'est pas un défaut de ce chantier** : le bloc n'a jamais été touché, et `evenements_publiables` sort au grain CORPUS par une décision ÉCRITE (« un acte n'appartient pas à un album, et il survit à la suppression de sa cible »). C'est cette décision qu'il faut rouvrir, et elle est plus large qu'AUTH-11. Attendu : la décision de Hugo entre filtrer le journal par collection, taire les charges dans un export, ou faire respecter `--verbatim` à cette table — et la limite réécrite en attendant. Le renvoi est posé dans `DEPOT-1`, que le premier dépôt rend opposable
- [ ] **Le contrôle « tout ce qu'une collection fait sortir » est une liste écrite à la main** — `tests/test_depot_export.py:_textes_de_depot` se présente comme exhaustif et couvre quatre sorties sur une dizaine : ni le zip, ni le XLSX, ni la fiche de description, ni le dépôt ShareDocs. Rien ne fuit en silence aujourd'hui (mesuré), mais c'est le mode d'échec que `CLAUDE.md` impute à `test_csp` : une liste manuelle **oublie ce qu'on ajoute** au lieu de perdre ce qu'elle voyait. Attendu : un CLIQUET qui énumère les routes `/depot/*` depuis l'inventaire des routes, joue chaque format, et exige de chaque artefact qu'il soit propre OU DÉCLARÉ avec sa raison — les deux limites d'aujourd'hui devenant deux entrées écrites plutôt que deux absences

### Ce qui se montre
- [x] **L'axe « dimension » du croisement lisait une dimension par son identifiant, sans portée** — `dim:<id>` d'une collection qu'on ne lit pas rendait son NOM (le libellé de l'axe) et ses valeurs. Il passe par l'accesseur gardé et répond 404 au mot près comme pour une dimension absente ; une valeur illisible ne fait pas de ligne, la portée étant posée sur la liaison comme pour l'axe des tags. Reporté puis levé par l'équipe le 2026-09-11. `e906810` ; `test_l_axe_dimension_du_croisement_tait_ce_qu_on_ne_lit_pas`, deux mutants tués
- [x] **Une région dont il ne reste que des tags cachés reste marquée « annotée »** — `annotee`, `nb_annotees` et le compteur de la Recherche lisent l'existence de la ligne `annotations` : l'écran montre une région annotée sans rien d'annoté. Un indice mineur. Attendu : le marqueur suit ce qu'on voit, ou la limite est écrite — **fermé le 2026-09-23, `9446d68`** : `socle._sql_a_montrer` dit « cette annotation a quelque chose à MONTRER » — une note non vide, ou un tag dont on lit le terme —, et les trois compteurs le consultent. Rien ne change pour qui lit tout : la ligne vide n'existe pas en base. C'est aussi la définition que l'ÉCRAN appliquait déjà de son côté, et qui divergeait de celle du serveur

### Ce qui se devine sans se montrer
- [x] **Le filtre par valeur d'attribut (`attributs=<id>`) ne vérifiait que l'EXISTENCE de la valeur** (`_valider_facette`) — un oracle par énumération d'identifiants, sans nom. Il passe par `_get_valeur`, et le filtre par locuteur (`personnage=<id>`), qui avait le même défaut dans la même fonction, par `_get_personnage` : ce qu'on ne voit pas répond exactement comme ce qui n'existe pas, sur les quatre cœurs d'analyse et leurs exports. `e906810` ; `test_une_facette_qu_on_ne_lit_pas_repond_comme_une_facette_absente`, quatre mutants tués. **Et la Recherche avait son PROPRE filtre**, écrit à part, resté ouvert après ce commit alors que cette case se disait cochée — trouvé en repassant : une valeur qu'on ne lit pas, posée sur une région qu'on lit, la faisait sortir, et chercher l'identifiant disait quelles régions la portent. Elle n'y filtre plus rien, comme un tag, et répond ce qu'elle répond à un identifiant libre. `b206d41` ; `test_la_recherche_ne_filtre_pas_par_une_valeur_qu_on_ne_lit_pas`, un mutant tué
- [ ] **L'index plein texte contient le nom des tags** : une recherche par mot trouve une région par un tag qu'on ne lit pas, sans l'afficher. Un oracle — il faut connaître le mot. Attendu : décider si l'index garde les tags, l'oracle étant alors écrit comme une limite, ou s'il les perd au profit du seul filtre par tag **Mesuré le 2026-09-23, et l'oracle est plus étroit que cette case ne le laissait croire** : il ne joue que sur des régions qu'on LIT déjà, il faut avoir deviné le mot, et le libellé n'est jamais rendu — la Recherche ne produit aucun extrait depuis l'index et joint les tags par une requête déjà bornée. C'est un canal de CONFIRMATION, un bit par mot deviné, pas une énumération. Options chiffrées : **(A)** garder et écrire la limite, 0 ligne ; **(B)** retirer les tags de l'index — migration de schéma (la table FTS se recrée, son tokenizer étant figé à la création) **plus une réindexation complète du corpus**, trois sites de code, et la promesse du champ de recherche à réécrire, qui dit « dialogues, notes, tags » ; **(C)** post-filtrer à la requête, **à écarter** — FTS5 ne dit pas quelle colonne a répondu, le correctif aurait l'air complet sans l'être ; **(E)** n'indexer que les tags GLOBAUX, même coût que (B) plus un couplage neuf — promouvoir un tag devrait réindexer toutes ses régions, et l'oublier laisserait l'index périmé en silence. **Recommandation : (A)**, et si le vocabulaire d'étude d'`ANN-1` naît LOCAL, alors (B) à la prochaine migration FTS forcée, pour ne payer la réindexation qu'une fois
- [ ] **Taper le nom d'un tag caché l'attache** : le libellé est unique dans toute l'instance (`_ensure_tags`, `ON CONFLICT(label)`), donc qui tape le nom d'un tag local à une collection qu'il ne lit pas s'attache CE tag — qui disparaît aussitôt de son écran. Un oracle par l'écriture. Attendu : il se ferme par une unicité (libellé, collection), c'est-à-dire un changement de schéma, pas par une garde **Mesuré le 2026-09-23 : il y a DEUX dommages, et cette case n'en nommait qu'un.** Outre l'oracle, l'annotatrice se retrouve avec un tag d'une autre collection attaché à sa région — qu'elle ne voit pas, et qu'elle ne peut pas RETIRER, une garde refusant de retirer un tag caché. Le dommage de données est celui qui coûte aujourd'hui. L'unicité (libellé, collection) reste la bonne fin, et elle porte trois pièges : SQLite traite les NULL comme DISTINCTS dans un index unique, donc deux tags GLOBAUX homonymes passeraient sans erreur ; le journal A3 nomme les tags par LIBELLÉ et il est append-only, donc l'annulation ne saurait plus lequel rattacher — c'est le coût caché le plus lourd, il touche le substrat de Ctrl+Z ; et il faut décider à quelle collection appartient un tag TAPÉ (aujourd'hui : toujours global, et si cela reste vrai, l'oracle se ferme du même coup). Ce n'est pas un chantier serveur seul : le nuage de tags et l'autocomplétion montreraient deux libellés identiques. **Recommandation : séquencer cette fin AVEC `COL-1`**, qui doit de toute façon trancher la collision à la promotion ; et, en attendant, une demi-mesure de cinq lignes sans migration — ce qu'on ne lit pas ne s'attache pas, ni ne se crée. Elle ferme le dommage de données, ne ferme pas l'oracle, et n'ajoute aucun mode de panne : le silence existe déjà

## Contexte

**Pourquoi un chantier et pas six commits.** Les six n'ont pas le même remède. Deux sont
une clause de portée à poser (l'axe dimension, le filtre par valeur). Une est la réécriture
d'un export et de sa documentation (le dépôt). Une est une DÉCISION : garder l'oracle de
l'index plein texte en l'écrivant comme limite, ou retirer les tags de l'index. Une est un
changement de SCHÉMA (l'unicité du libellé). La dernière est un indice mineur, qui peut
aussi s'écrire comme limite. Ce qui les réunit est la question qu'elles posent, pas le code
qu'elles touchent.

**Le patron à suivre existe, en deux moitiés.** Pour LIRE, l'axe « tag » du croisement
(`df20d3d`) : la portée se pose sur la LIAISON et pas seulement sur le terme nommé, sans
quoi un axe lisible compterait des valeurs illisibles. Pour ÉCRIRE, l'annotation
(`a2ed353`) : une route qui réécrit ce qu'elle voit doit remettre ce qu'elle cache
(`_tags_caches`), sinon enregistrer efface le travail d'une autre collection — et le
journal doit garder la ligne ENTIÈRE, sans quoi Ctrl+Z l'efface à son tour. Toute
fermeture sur les dimensions et les valeurs devra se poser la même question avant d'écrire
la clause : les attributs d'une région ou d'un personnage se réécrivent-ils en bloc ?

**L'unicité du libellé croise COL-1.** Fermer la collision par une unicité (libellé,
collection) permet deux tags « X », l'un global, l'autre local. Promouvoir le local en
global — le geste central de COL-1 — rencontre alors son homonyme, et il faudra choisir :
fusionner, refuser, renommer. Aujourd'hui la question ne se pose pas parce que le libellé
est unique partout ; c'est exactement ce qui fait l'oracle. Renvoi posé dans COL-1.

**Voisinage.** `DROIT-2` (d'où ces cases viennent, et les deux commits qui ont fermé la
moitié « tags »), `AUTH-2` (la règle `clause_terme`), `COL-1` (la promotion des termes, et
l'unicité), `DEPOT-1` (le premier dépôt, qui rend pressante la case des exports), `ANN-1`
(le vocabulaire d'étude : s'il naît LOCAL, l'axe dimension du croisement cesse d'être une
hypothèse).
