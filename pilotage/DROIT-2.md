---
chantier: DROIT-2
statut: à venir
---

# DROIT-2 — exporter est un droit à part, accordé par collection

**Arrêté sur** — 2026-09-11, `6d08b87` : le droit d'exporter est posé de bout en bout — la case et la Portee, les quinze portes sous leur cliquet, et l'écran qui ne propose un export qu'à qui peut le faire. Ce qui reste ouvert est la famille des termes qu'on ne lit pas, dont deux cases reportées par l'équipe. L'avertissement de déploiement tombe avec l'écran : la case se pose désormais dans le panneau des accès.

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
- [x] **Une colonne booléenne `exporter` sur `collection_acces`**, schéma v27, défaut faux et AUCUN rattrapage — la migration ferme l'export à qui lisait, et c'est écrit comme un changement de comportement. `704b98a` ; `test_la_migration_v27_ferme_l_export_a_qui_lisait`
- [x] **`Portee` gagne un ensemble `export` et une question `peut_exporter(collection_id)`** — la case plus la propriété, réduite à la lecture par ceinture, et tout en portée totale. `704b98a` ; `test_exporter_est_une_case_a_cote_du_niveau_pas_un_palier`, `test_on_n_exporte_pas_ce_qu_on_ne_lit_pas`, `test_la_case_se_lit_en_base_par_login_et_par_groupe`
- [x] **Accorder ou retirer le droit est un geste de PROPRIÉTAIRE** — même route que le niveau, même garde ; absent de la requête, le droit n'est pas touché. `704b98a` ; `test_accorder_la_case_est_un_geste_de_proprietaire_et_se_trace`
- [x] **Le changement est tracé au journal A3**, dans le même événement que le niveau, avec l'état d'avant. `704b98a` ; même test

### Les portes
- [x] **Les portes exigent `peut_exporter`, sauf la sauvegarde** — mesurées à QUINZE routes et non dix : le tableau comptait par familles. Le dépôt ShareDocs garde la propriété en plus, et son message cesse de promettre un téléchargement. `4b1d530` ; `test_une_porte_refuse_qui_lit_sans_la_case` et sa contre-épreuve `test_la_meme_porte_s_ouvre_avec_la_case`, joués sur chaque porte
- [x] **Un export qui traverse plusieurs collections filtre par droit d'EXPORTER, pas par droit de LIRE** — non par une clause de plus, comme la case l'envisageait, mais par une PORTEE de plus (`Portee.pour_export()`), que les deux cœurs partagés consomment sans rien apprendre. `4b1d530` ; `test_la_case_sur_a_n_emporte_pas_b`, et `test_ce_qui_sort_suit_la_portee_d_export_pas_celle_de_lecture` pour le contenu
- [x] **L'export d'un ALBUM se fait au titre d'une collection NOMMÉE** (`socle._collection_d_export`) : nommée, elle doit contenir l'album (404) et s'exporter (403) ; non nommée, la seule exportable, et un 422 qui NOMME les candidates s'il y en a plusieurs. L'export le dit — `exporte_au_titre_de` dans le JSON, `availability` dans le TEI, le nom du fichier CSV. Tranché le 2026-09-11 par l'équipe. `4b1d530` ; `test_un_album_sort_au_titre_d_une_collection_nommee`
- [x] **Le panier de figures en fait partie** — chaque région doit appartenir à un album qu'on peut exporter, et la légende ne crédite qu'une collection exportable ; le régime ne bloque toujours pas la citation. `4b1d530`
- [x] **Un cliquet énumère les portes, parce que l'oubli d'une garde échoue ici OUVERT** — toute route qui produit un fichier, repérée par son source ET son chemin (l'export JSON d'un album ne pose aucun en-tête de pièce jointe), est une porte déclarée ou déclarée hors du droit ; une déclaration sans route échoue aussi ; plancher dérivé du source. `4b1d530` ; `test_toute_route_qui_sort_un_fichier_est_une_porte_declaree`, et deux mutations sur le cliquet lui-même parmi les treize

### L'écran
- [x] **Une case « peut exporter » dans le panneau des accès**, sur chaque accès et dans le formulaire d'ajout, libellée par l'acte ; chez un propriétaire, cochée et non modifiable, avec la raison à côté. `6d08b87` ; `test_la_case_cochee_dans_les_acces_rend_l_export_a_l_ecran`, audité par `test_a11y_la_case_et_le_choix_d_export`
- [x] **`GET /api/collections` porte `exportable`, et les boutons d'export se cachent pour qui n'a pas le droit** — Bibliothèque, Atelier, Recherche et Exploration, ces deux dernières par `acces.exporter` de `/api/moi`, qui dit « tout », « partiel » ou « rien » ; sans le droit, une note DIT ce qui manque. Un piège trouvé en route : `.dropdown-menu button { display: block }` l'emportait sur `hidden`. `6d08b87` ; `test_sans_la_case_aucune_surface_ne_propose_d_exporter`
- [x] **Un refus d'export est un 403 NOMMÉ, pas un 404** — le serveur le rend sur chaque porte, avec ce qui manque (`socle._MOTIF_EXPORT`). `4b1d530` ; `test_une_porte_refuse_qui_lit_sans_la_case` vérifie le code ET le mot

- [x] **Un album qu'on peut exporter au titre de plusieurs collections propose de CHOISIR** — une fenêtre dans l'Atelier, et l'export part au titre de la collection choisie. `6d08b87` ; `test_un_album_exportable_au_titre_de_deux_collections_fait_choisir`

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
- [x] Un compte en écriture, sans la case, n'exporte rien : ni le TEI de l'Atelier, ni une concordance, ni une figure — éprouvé sous son identité, porte par porte (`test_une_porte_refuse_qui_lit_sans_la_case`, quinze cas)
- [x] Le même compte, case cochée sur la collection A, exporte A et pas B, y compris dans une concordance qui traverse les deux (`test_la_case_sur_a_n_emporte_pas_b`)
- [x] Un propriétaire exporte sa collection sans avoir rien à cocher — éprouvé au MODÈLE et par la résolution réelle derrière le proxy (`test_un_proprietaire_exporte_sans_rien_cocher`, `test_exporter_est_une_case_a_cote_du_niveau_pas_un_palier`), et non porte par porte : les portes consultent la même `Portee`
- [x] Le mono-poste est inchangé : sans proxy, la portée est totale, export compris, et rien n'est à nommer (`test_le_mono_poste_exporte_sans_rien_nommer`, `test_la_portee_totale_exporte_tout`)

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
