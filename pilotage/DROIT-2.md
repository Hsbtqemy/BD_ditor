---
chantier: DROIT-2
statut: à venir
---

# DROIT-2 — exporter est un droit à part, accordé par collection

**Arrêté sur** — 2026-09-11, `a2ed353` : les tags qu'on ne lit pas ne sortent plus des lectures ni de l'Atelier, et l'écriture les préserve. Le droit d'exporter lui-même n'est pas commencé : la migration (v27), la `Portee`, les portes et l'écran restent entiers.

**Point de départ** — 2026-09-11, pendant COL-2. À la question « le bloc d'export suit-il
les descripteurs vers la Bibliothèque ? », l'équipe a répondu : *« tout dépend de qui a
accès à cela. L'export reste quelque chose de particulièrement sensible, et il ne faut pas
que tout le monde y ait accès. »* Mesuré dans la foulée : **aujourd'hui, toute personne qui
peut LIRE une collection peut en exporter le contenu, texte relevé compris.**

Tranché le même jour, en deux temps : **exporter devient un droit à part** — ni un niveau,
ni un réglage de l'écran —, et il s'accorde **par collection**, par une case à côté du
niveau d'accès, **d'office pour les propriétaires**.

## Les dix portes, mesurées le 2026-09-11

| porte | où | ce qui sort | garde aujourd'hui |
|---|---|---|---|
| Export de dépôt — fiche, enregistrements, manifeste IIIF | bloc de collection | métadonnées, et le **texte relevé** si la case est cochée | lire |
| Dépôt ShareDocs de ces mêmes exports | idem | idem | propriétaire |
| JSON, CSV, TEI d'un album | menu de l'Atelier | l'album entier, texte relevé compris | lire |
| CSV de la Recherche | Recherche | résultats, texte relevé, notes, tags | lire |
| Six CSV de l'Exploration | Exploration | fréquences, **concordances** (du texte), comparaison, croisement, accords | lire — sauf l'accord inter-annotateurs, qui exige d'écrire |
| Panier de figures | Atelier | recadrages d'images, avec leur légende | lire |
| Sauvegarde | Administration | toute la base | administrateurs |

**Pourquoi c'était ouvert, et c'était écrit.** EXP-1 : *« décrire une collection qu'on lit
n'est pas la partager »* — la garde commune des trois exports de dépôt est LIRE. DROIT-1
(arbitrage du 2026-08-28) : à l'intérieur de l'instance, le régime de diffusion ne borde
rien, parce que l'annotation repose sur les images et que le travail interne relève de
l'usage savant. Ces deux décisions restent vraies de ce qu'elles décrivent : voir, annoter,
travailler.

**Pourquoi ça cesse.** Télécharger n'est pas travailler dans l'instance : c'est SORTIR. Le
fichier quitte l'instance pour un poste qu'elle ne contrôle plus, et la base légale du
corpus n'est toujours pas établie (`DEPOT-1`). C'est l'axe DEDANS / DEHORS de DROIT-1,
appliqué à une sortie qu'il n'avait pas nommée — pas un retour au classement des personnes
par niveau, que DROIT-1 a écarté.

**Pourquoi un droit à part, et pas un niveau.** Les stagiaires sont en écriture, et c'est
voulu : une règle « écriture et plus » ne les arrêterait pas. Exporter ne s'ordonne pas
avec annoter, et c'est exactement le cas qu'`AUTH-10` avait décrit — une capacité hors de
l'échelle `lecture ⊂ ecriture ⊂ proprietaire`. Sa conclusion structurelle était qu'une
telle capacité serait **un drapeau de plus, pas un changement de modèle** : ce chantier est
le premier à l'éprouver.

## Reste

### Le modèle
- [ ] **Une colonne booléenne `exporter` sur `collection_acces`**, par migration (incrément de `SCHEMA_VERSION` et étape de `_migrate()`), défaut faux. Le niveau reste une seule valeur ordonnée : la case s'y ajoute sans y entrer, et le cumul des niveaux reste dérivé à un seul endroit
- [ ] **`Portee` gagne un ensemble `export` et une question `peut_exporter(collection_id)`** : les propriétaires, les lignes cochées, et tout pour un administrateur comme en mono-poste. `autorisation.py` reste le seul endroit qui tranche — une deuxième règle dans une route serait la divergence à venir
- [ ] **Accorder ou retirer le droit est un geste de PROPRIÉTAIRE** (`peut_administrer`). Décider ce qui sort engage la collection autant que décider qui entre
- [ ] **Le changement est tracé au journal A3**, comme les autres changements d'accès

### Les portes
- [ ] **Les dix portes exigent `peut_exporter`, sauf la sauvegarde**, qui reste aux administrateurs. Le dépôt ShareDocs garde son exigence de propriétaire EN PLUS : envoyer dans un dossier partagé que l'application ne contrôle pas n'est pas le même geste que télécharger pour soi
- [ ] **Un export qui traverse plusieurs collections filtre par droit d'EXPORTER, pas par droit de LIRE.** La Recherche et l'Exploration portent sur tout ce qu'on lit ; sans ce filtre, qui exporte la collection A emporterait le texte de B dans une concordance qui couvre les deux. `Portee` doit donc offrir une clause d'export, analogue à `clause_album`, et les deux cœurs partagés (`_recherche_rows`, `_analyse_filtres`) doivent pouvoir la recevoir
- [ ] **L'export d'un ALBUM se fait au titre d'une collection NOMMÉE**, choisie quand l'album en a plusieurs — tranché le 2026-09-11 par l'équipe, après avoir vu ce qu'un export d'album contient : métadonnées, découpage, texte relevé, notes et tags, et aucune image (le TEI ne porte qu'un lien vers le dérivé web). Un album vit dans plusieurs collections depuis AUTH-3, et le droit peut être accordé sur l'une et pas sur l'autre : « au moins une » était permissif, « toutes » fermait un album dès son second rangement. C'est le patron du manifeste IIIF de DROIT-1 : un droit sur UNE collection suffit, et l'export dit sous quel droit il est parti
- [ ] **Le panier de figures en fait partie.** DROIT-1 dit que citer n'est jamais bloqué par le RÉGIME de diffusion, et ça reste vrai : qui a le droit d'exporter cite, même depuis une collection sous embargo. Ce qui change est QUI peut exporter, pas ce que le régime retient
- [ ] **Un cliquet énumère les portes, parce que l'oubli d'une garde échoue ici OUVERT.** Toute route qui produit un fichier téléchargeable doit consulter `peut_exporter`, ou être déclarée avec sa raison. Une porte oubliée continuerait de laisser sortir — c'est précisément l'état d'aujourd'hui, et il ne ferait tomber aucun test. Même forme que le cliquet des sorties d'identité d'AUTH-5, et même exigence d'un plancher dérivé du source (ARCH-2)

### L'écran
- [ ] **Une case « peut exporter » dans le panneau des accès**, à côté du niveau, libellée par l'ACTE et non par un nom de niveau — c'est l'exigence qu'AUTH-10 a posée pour ses cases. Chez un propriétaire, elle apparaît cochée et non modifiable, avec la raison écrite à côté
- [ ] **`GET /api/collections` porte `exportable`**, comme il porte `administrable`. Les boutons d'export se cachent pour qui n'a pas le droit ; la garde reste celle du serveur, et l'écran ne fait qu'éviter de proposer un geste qu'il refusera
- [ ] **Un refus d'export est un 403 NOMMÉ, pas un 404** : l'objet est lisible — on vient de l'afficher —, donc un 404 mentirait. C'est la précision qu'AUTH-10 a écrite pour les refus d'écriture sur un objet visible

### Les tags qu'on ne lit pas
- [x] **Les lectures qui ont leur propre requête taisent un tag local à une collection qu'on ne lit pas** — la Recherche et son CSV, le CSV d'un album, l'axe « tag » du croisement (JSON et CSV), et les deux filtres par nom de tag, qui étaient des ORACLES : ils n'affichaient rien, mais chercher le nom disait quelles régions le portent. `df20d3d` ; quatre tests dans `test_autorisation.py`, cinq mutants tués
- [x] **L'Atelier et les exports JSON et TEI d'un album le taisent, et l'écriture le PRÉSERVE** — `_annotation_for_region` reçoit la portée ; le PUT relit les tags cachés (`_tags_caches`) et les remet ; vider ce qu'on voit ne supprime plus une annotation qui en porte encore ; le journal garde l'annotation ENTIÈRE, sans quoi Ctrl+Z effacerait ce qu'on a caché — piège signalé par la session voisine avant l'écriture. `a2ed353` ; trois tests, quatre mutants tués
- [ ] **Les exports de dépôt d'une collection emportent les termes des AUTRES collections** — le catalogue de tous les tags de l'instance avec leur définition et leur `collection_id` (`metadonnees_collection`, clé `tags_cat` : JSON et onglet « tags ») ; les tags posés, sans portée des termes (`ann_tags`) ; les valeurs d'attribut des personnages (`perso_attr`) ; les sujets DataCite et Dublin Core, qui prennent tous les tags et toutes les valeurs (`crosswalk_depot._sujets`). Ces artefacts QUITTENT l'instance. Attendu : l'export de A ne porte que le vocabulaire de A — global ⊕ local à A, la règle que suit déjà le « % défini » —, quel que soit qui exporte ; et `docs/export-metadonnees.md`, qui dit « les catalogues de référence restent globaux », réécrit avec. **Reporté le 2026-09-11 par l'équipe, à traiter avec la garde de ces mêmes portes**
- [ ] **L'axe « dimension » du croisement lit une dimension par son identifiant, sans portée** — `dim:<id>` d'une collection qu'on ne lit pas rend son NOM (le libellé de l'axe) et ses valeurs. Attendu : un 404, comme pour un terme absent, et une valeur illisible ne fait pas de ligne (la portée posée sur la liaison, comme sur l'axe des tags). **Reporté le 2026-09-11 par l'équipe**
- [ ] **Le filtre par valeur d'attribut (`attributs=<id>`) ne vérifie que l'EXISTENCE de la valeur** (`_valider_facette`) — un oracle par énumération d'identifiants, sans nom. Attendu : la même règle que le filtre par tag
- [ ] **L'index plein texte contient le nom des tags** : une recherche par mot trouve une région par un tag qu'on ne lit pas, sans l'afficher. Un oracle — il faut connaître le mot. Attendu : décider si l'index garde les tags, l'oracle étant alors écrit comme une limite, ou s'il les perd au profit du seul filtre par tag
- [ ] **Taper le nom d'un tag caché l'attache** : le libellé est unique dans toute l'instance (`_ensure_tags`, `ON CONFLICT(label)`), donc qui tape le nom d'un tag local à une collection qu'il ne lit pas s'attache CE tag — qui disparaît aussitôt de son écran. Un oracle par l'écriture. Attendu : il se ferme par une unicité (libellé, collection), c'est-à-dire un changement de schéma, pas par une garde
- [ ] **Une région dont il ne reste que des tags cachés reste marquée « annotée »** — `annotee`, `nb_annotees` et le compteur de la Recherche lisent l'existence de la ligne `annotations` : l'écran montre une région annotée sans rien d'annoté. Un indice mineur. Attendu : le marqueur suit ce qu'on voit, ou la limite est écrite

### Ce qui devra être vrai
- [ ] Un compte en écriture, sans la case, n'exporte rien : ni le TEI de l'Atelier, ni une concordance, ni une figure — éprouvé sous son identité, porte par porte
- [ ] Le même compte, case cochée sur la collection A, exporte A et pas B, y compris dans une concordance qui traverse les deux
- [ ] Un propriétaire exporte sa collection sans avoir rien à cocher
- [ ] Le mono-poste est inchangé : sans proxy, la portée est totale, export compris

## Contexte

**Ordre imposé par la session voisine.** Ce chantier touche `routes/analyse.py`,
`routes/recherche.py` et probablement `socle.py`, que `ANA-6` modifie au même moment. Il
passe donc après les commits d'ANA-6 sur ces fichiers ; la session concernée est prévenue,
et son export de concordance — qui existe depuis ANA-7, ANA-6 n'y ajoutant que deux colonnes,
les tags et la note — suit la règle commune plutôt qu'une garde à part.

**La voie est libre depuis le 2026-09-11.** ANA-6 a commité ses trois lots sur les fichiers
communs (`1a1bc8a`, `15d1785`, `efeb0bf`) et les a libérés. Un fait qu'il a signalé et qui
compte ici : `_concordance_rows` joint désormais les tags de chaque ligne par
`_joindre_tags(conn, portee, lignes)`, qui les filtre par `portee.clause_terme`. Elle
REÇOIT la `Portee` : faire passer la concordance d'une portée de lecture à une portée
d'export n'aura rien à recâbler, à condition de lui passer l'objet adapté plutôt que de
filtrer à côté.

**Un trou ANTÉRIEUR sur la même jointure, mesuré par la session d'ANA-6 le 2026-09-11 et
remonté à l'équipe.** `_recherche_rows` joint les tags de chaque résultat SANS
`portee.clause_terme` : un tag local à une collection que le lecteur ne lit pas lui est
montré — dans `/api/recherche` comme dans son export CSV —, alors que `/api/tags` le lui
masque. Ce n'est pas ce chantier, et il n'est corrigé ni ici ni ailleurs en passant :
c'est à l'équipe de dire qui le prend. Mais DROIT-2 touchera cette jointure pour la
clause d'export ; il faut savoir qu'elle a déjà ce trou, pour ne pas le conserver par
recopie. La concordance, elle, filtre ses tags par `clause_terme` depuis `efeb0bf`.

**Pris par ce chantier le 2026-09-11, en tête, à la demande de l'équipe** — et il n'était pas seul. La même lecture sans portée des termes se trouvait à sept endroits où un nom de tag s'affiche, plus deux filtres qui servaient d'oracle ; la passe de revue en a trouvé d'autres, sur les dimensions et les valeurs et dans les exports de dépôt. Fermés en deux commits pour les tags ; ce qui reste est dans la zone « Les tags qu'on ne lit pas », avec ce que l'équipe a reporté.

**Ce que COL-2 en fait.** Le bloc d'export de collection déménage TEL QUEL dans la
Bibliothèque ; ce chantier-ci pose ensuite sa garde au serveur et `exportable` à l'écran,
à un seul endroit. Faire l'inverse — restreindre le bloc pendant le déménagement — aurait
laissé les neuf autres portes ouvertes en donnant l'impression d'avoir fermé.

**Voisinage.** `DROIT-1` (DEDANS / DEHORS, et le patron « nommer la collection »), `EXP-1`
(la décision « décrire n'est pas partager », rouverte ici pour la sortie), `AUTH-10` (la
capacité hors de l'échelle, dont ceci est le premier cas réel), `AUTH-2` / `AUTH-3` (la
portée et ses deux cœurs partagés), `AUTH-5` (le patron du cliquet des sorties),
`DEPOT-1` (la base légale non établie, qui rend la question pressante), `ANA-6` (l'export
de concordance, en cours), `COL-2` (le déménagement du bloc).
