# COL-4 — « Mon bac à sable », sans wizard : cadrage

Rendu le 2026-10-21, sur `dev` à `361656d` (schéma **34** : v32 et v33 de la 3b et de
`tome`, v34 d'IMG-1 ; `main` est encore en v31). Rien n'est codé ni exécuté. Ce qui est
marqué **lu** a été lu dans le code à ce commit ; ce qui est marqué **supposé** ne l'a pas
été, ou reste à mesurer. Les propositions sont numérotées **S1 à S12** ; chacune dit
*proposé / pourquoi / ce que ça coûte / ce qui reste à trancher*. Le modèle de forme est
`docs/col3-tranche3b-cadrage.md`. Le wizard (`UX-6`) n'est PAS cadré ici : S10 dit seulement
la place qu'on lui garde.

---

## Ce que le lot 2 livre, en gestes

1. **« Mon bac à sable »** — un clic crée, pour CE compte, un projet à lui, dont il est
   responsable, rempli d'un jeu fixe. Recliquer y ramène.
2. **Inviter** — le propriétaire fait entrer un collègue pour essayer le travail à plusieurs.
3. **Remettre à neuf** — le propriétaire efface tout et retrouve le jeu de départ.
4. **L'effacement hebdomadaire** — tous les bacs à sable partent à un moment fixe ; on
   reclique pour en retrouver un neuf. La date se lit dans le bac à sable.

Ce qu'il ne livre pas : le wizard (lot 4) ; l'annotation dans le jeu (`ANN-7`) ; un chemin
pour faire sortir un travail d'un bac à sable (S3, question Q3).

---

## Ce qui existe déjà (lu)

- **Créer un projet** : `POST /api/projets` (`routes/projets.py`) exige
  `peut_decider_des_projets()` = `self.tout` (`autorisation.py`) — l'administrateur et le
  mono-poste seuls. Le nom passe par `_nom_valide` : 21 caractères au plus
  (`database.LONGUEUR_NOM_PROJET`, mesuré sur la bande à 320 px) et UNIQUE sans égard à la
  casse. Le projet naît sans membre, avec sa base (`creer_collection_de_base`, drapeau
  `collection.base`, `acces_membres` obligatoire).
- **Le drapeau voisin** : `projet.repli` (INTEGER, désigne le projet de repli) ; aucun autre
  drapeau sur `projet`. `projet` porte `AUTOINCREMENT` depuis la v31 ; `collection` NON (ses
  identifiants se réattribuent, d'où `demande.collection_nom`).
- **Ce que donne la responsabilité d'un projet** (`Portee.__init__`) : `projets_geres` ⊂
  `projets`, et la base du projet en `propriete` (donc `ecriture`, `lecture`, `export`
  d'office). Aucune clause de données ne connaît les projets : elles lisent les ensembles.
- **Supprimer un projet** : `socle._supprimer_projet` refuse (409) un projet de repli, un
  projet qui porte une collection hors base, une base habitée, une base qui porte du
  vocabulaire local, un projet qu'un album désigne (`albums.projet_id`, copies gardées au
  fonds). Il ne détruit RIEN : il n'accepte qu'un projet vide.
- **Détruire un album** : `socle._detruire_album` — seul chemin ; verrou d'écriture, garde
  `clause_suppression_directe` relue dessous, fin des emplois au journal, document parti
  avec sa dernière copie, demandes closes, commit, puis images effacées PAR RÉFÉRENCE sous
  le verrou repris (`_sous_le_verrou`) — un fichier qu'une autre planche désigne reste.
- **Copier** : `database.creer_copie(conn, document, collection, par=, depuis=, cran=)` fait
  les CINQ crans sur `dev` (`images` … `annotations`, via `copier_le_travail`, tranche 3b) :
  mêmes fichiers d'image (D6), `region_origine` par région copiée, UN acte sous `document`,
  aucun événement par région (E3). Ne crée aucun dossier.
- **Le rangement ne traverse pas les projets** : `database.rangement_traverse`, 409 pour
  TOUTE portée (route et outil), y compris une copie gardée au fonds, qui garde son projet
  écrit (`albums.projet_id`).
- **La minuterie** : `deploy/systemd/bd-deploiement.{service,timer}` — `Type=oneshot` (pas
  deux à la fois), `User=ubuntu`, `PATH` posé, `OnBootSec` + `OnUnitActiveSec`,
  `RandomizedDelaySec` ; le service lance un script du dépôt sur l'hôte. L'application vit
  dans le conteneur `bd-app` (`deploy/docker-compose.yml`).
- **Un outil qui écrit** : `tools/convertir_en_copies_de_travail.py` (IMG-1) — à blanc par
  défaut, `--appliquer`, verrou propre à l'outil (fichier créé en exclusif à la racine des
  données), verrou d'écriture de la base par geste, arrêt propre sur SIGTERM.
  `tools/gerer_collections.py` écrit au journal avec un agent vide (« un shell n'a pas
  d'identité »). `tools/semer_demo.py` passe par `TestClient` et meurt en 403 derrière le
  proxy (mémoire du projet) : ce n'est pas un patron pour la production.
- **La bande du projet** : `static/theme.js` (`dessinerProjet`) — le nom seul pour un projet,
  un `<select>` natif dès deux, alimenté par `GET /api/projets` (`window.BDProjets`) ; le
  projet courant vit dans le navigateur (`bd-projet`, `static/lib/projet.js` : retenu s'il
  est encore visible, sinon le repli, sinon le premier).

---

## S1 — Créer : une route à elle, et une exception écrite

**Proposé.**
- Deux routes dans un module neuf, `routes/bac_a_sable.py` :
  `GET /api/bac-a-sable` (le mien : id, date d'effacement, ce que le jeu y a posé — S10 —, ou
  `null`) et `POST /api/bac-a-sable` (le créer s'il n'existe pas, sinon rendre le même :
  le bouton est « y aller », idempotent). `POST /api/bac-a-sable/remise-a-neuf` en S5.
- **La garde est une question NEUVE**, pas un trou dans `peut_decider_des_projets`, qui
  reste `self.tout` et son sens (« décider quels projets existent »). Proposition :
  `Portee.peut_ouvrir_un_bac_a_sable()` = un login ET derrière le proxy — vrai pour un
  compte ordinaire comme pour un administrateur qui a un login ; faux en mono-poste (sans
  login : un poste seul n'a ni « mon » ni personne à inviter) et sans identité (portée vide).
  Le compte PARTAGÉ est refusé à la route (`utilisateur.nature = 'collectif'`, lu en base
  comme le fait déjà `clause_suppression_directe`) : un bac à sable est à une personne, et
  « remettre à neuf » y effacerait le travail d'un autre sans qu'il le sache. Refus : 403
  nommés, qui parlent de l'appelant et non d'un objet.
- **Un par login, tenu par le code sous le verrou d'écriture** (relire puis créer sous
  `conflit.verrouiller`) — pas par un index unique partiel, pour la raison écrite sur
  `collection.base` : un index nommant la colonne empêche les tests de défaire la version.
- **Le drapeau** : `projet.bac_a_sable_de TEXT` — le LOGIN du propriétaire, NULL pour un
  projet ordinaire. Une colonne suffit pour dire « c'est un bac à sable » ET « de qui »,
  sans `projet_acces` à relire. `projet.efface_le TEXT` à côté (S5). La règle de lecture
  vit à UN endroit (`database.est_bac_a_sable(conn, projet_id)` / un fragment SQL), comme
  `sql_projet_de`.
- **Le propriétaire est aussi écrit dans `projet_acces`** (responsable), pour que tout ce
  qui lit les membres — « Qui y entre », la dérivation de la base, `acces_derives` — marche
  sans branche. Mais il est INAMOVIBLE : dans un bac à sable, `PUT …/membres` refuse le rôle
  `responsable` à un invité et refuse de toucher la ligne du propriétaire, `DELETE` aussi
  (409 nommés). Sans cela un invité promu responsable retirerait le propriétaire, qui
  garderait `bac_a_sable_de` sans plus rien y voir.
- **Le nom** : stocké « Bac à sable » (11 caractères), hors de l'unicité de `_nom_valide`
  (75 projets du même nom) ; le PRÉFIXE est réservé aux projets ordinaires (un projet
  « Bac à sable de Léa » créé par un administrateur serait pris pour le sien). Ce que la
  bande AFFICHE est rendu par `_vue` : « Mon bac à sable » (15) au propriétaire,
  « Bac à sable · <login> » à un invité, borné à 21 — **à mesurer sur la bande** (320 px,
  grande police) ; un login long se coupe à la source, jamais à l'écran. Le renommer n'est
  pas offert.
- **Sa base** : naît avec lui (`creer_collection_de_base`), `acces_membres = 'ecriture'` —
  l'invité écrit là où est le jeu ; sinon inviter ne sert à rien. Le jeu y est copié (S4).

**Pourquoi.** « Qui décide des projets » est une phrase de la doctrine (CLAUDE.md § Le
PROJET) ; l'élargir à « tout le monde » pour un cas l'userait. Une question à part se teste
seule et se mute seule.

**Ce que ça coûte.** Un module de routes (le plancher de `tests/inventaire_routes.py` le
suit tout seul ; `test_autorisation` exige que chaque route consulte la portée) ; deux
colonnes ; trois refus dans `routes/projets.py`.

**Reste à trancher.** Un administrateur a-t-il un bac à sable ? Proposé : oui (Hugo y
éprouvera le wizard), en sachant que sa portée totale y garde ses pouvoirs — d'où S3, où
l'isolement est tenu par la NATURE du projet et jamais par la portée.

## S2 — Ce qu'il ne donne pas ailleurs (l'inventaire)

Le constat central du cadrage : **aujourd'hui un arrivant n'écrit nulle part ; avec son bac
à sable, il « écrit quelque part » et il « est responsable d'un projet ».** Tout ce qui
s'ouvre sur ces deux faits s'ouvre pour 75 comptes d'un coup. Inventaire (lu), avec ce qu'on
en fait :

| Ce qui s'ouvre | Par quoi (lu) | Proposé |
|---|---|---|
| Les NOTICES de tout le fonds (titre, série, auteur) | `peut_lire_les_notices` = `bool(projets_geres)` | **Fermer** : les bacs à sable ne comptent pas |
| NOMMER n'importe quel document dans une prise, et en DEMANDER l'entrée (une demande à l'administrateur par essai ; et un oracle d'existence par identifiant) | `_plan_d_une_ligne` : `gere` suffit à nommer | **Fermer** : dans un bac à sable, `gere` ne nomme pas ; on ne nomme que ce qu'on lit déjà (le jeu) |
| Le vocabulaire GLOBAL : créer, renommer, définir, supprimer tags, domaines, dimensions, valeurs ; l'import CSV en global | `peut_ecrire_terme(None)` = `bool(ecriture)` ; `peut_ecrire_quelque_part` ; `POST /api/lexique/importer` | **Fermer** pour qui n'écrit que dans des bacs à sable |
| Un TAG tapé dans une annotation naît GLOBAL (« un libellé libre se crée, global ») et reste après l'effacement | `socle._ensure_tags` | **Le faire naître LOCAL** à la base du bac à sable quand la région en est (l'appelant connaît la région) ; l'effacement le détruit (S5) |
| Le registre des PERSONNAGES : modifier, fusionner, aligner tout personnage visible — dont ceux « jamais apparus », visibles de tous | `_get_personnage(ecriture=True)` → `peut_ecrire_quelque_part` | **Fermer** l'écriture hors des personnages qui n'apparaissent QUE dans ses bacs à sable ; et S4 garde le jeu sous le cran `annotations`, sans personnage partagé |
| Lire l'ANNUAIRE : les noms de groupes, et la colonne « Signal » des membres posés — l'oracle d'existence de login fermé le 2026-09-18 pour les propriétaires | `GET /api/projets/{id}/membres/choix`, `GET /api/collections/{id}/annuaire` (`gerer`/`administrer`) | **Fermer** dans un bac à sable (403 nommé) : on invite un login tapé, sans liste ni vérification ; `jamais_vu` (miroir `utilisateur`) ne s'y rend pas non plus |
| `accord-inter` (des PERSONNES) | 403 à qui n'écrit nulle part ; périmètre = albums où l'on écrit | Laisser : borné au bac à sable, il ne mesure que ceux qu'on y a invités |
| Exporter (propriétaire d'office de sa base), figures, manifeste IIIF d'une collection déclarée `public` | DROIT-2 | **Dépend du jeu** (Q1) : jeu du domaine public → laisser (exporter s'apprend) ; sinon fermer l'export dans un bac à sable |
| Importer depuis ShareDocs sous le compte de l'INSTANCE dans un album où l'on écrit | `sharedocs_importer` (écrire dans l'album) ; la session de l'instance est le repli de chacun | **À trancher en route** — proposé : dans un bac à sable, sa session personnelle seulement |
| Lancer les passes ML (Kumiko, bulles, OCR) | `lots`, écriture | Laisser (c'est ce qu'on apprend) ; **supposé** : 75 comptes sur un `ML_LOCK` sérialisé — à surveiller, pas à borner d'avance |
| Le bandeau de PORTÉE VIDE disparaît : `acces.collections` compte la base | `GET /api/moi`, `len(portee.lecture)` | **Exclure** les bacs à sable du compte : l'arrivant qui n'a accès à rien d'autre doit encore lire pourquoi |
| « Comptes et groupes » : chaque compte a une entrée de projet ; le verdict de départ dit de le retirer du projet ; les bases sont « seul propriétaire par le projet » | `comptes.traces` (`entrees_projet`), `acces_derives` | **Exclure** les bacs à sable des signaux et du verdict ; les montrer à part dans la fiche d'un compte (« a un bac à sable ») |

**La forme proposée.** `Portee` reçoit un ensemble de plus, `bacs_a_sable` (les projets bacs
à sable dont on est), lu dans `projets_du_principal` (une jointure sur `projet`), et en
dérive `ecriture_hors_bac` (l'écriture sur les collections d'un projet qui n'en est pas un).
Les questions TRANSVERSES lisent celle-là : `peut_ecrire_quelque_part`,
`peut_ecrire_terme(None)`, `peut_lire_les_notices` (sur `projets_geres - bacs_a_sable`),
`peut_exporter_quelque_part` si Q1 ferme l'export. Les questions PONCTUELLES (`peut_lire`,
`peut_ecrire(c)`, `clause_album`, `clause_destruction`) ne changent pas : dans le bac à sable,
on y travaille comme ailleurs. Une portée totale n'est pas touchée (S3 tient l'isolement
pour elle).

**Pourquoi.** Ce sont des conséquences ordinaires de règles justes — exactement le constat
de la relecture croisée de la v31 sur la base ouverte (CLAUDE.md : « ce que la dérivation
emporte »). Multipliées par 75 et re-semées chaque semaine, elles deviennent une pollution
qui SURVIT à l'effacement (tags et personnages globaux) et un flot de demandes chez
l'administrateur.

**Ce que ça coûte.** Le cœur des droits : relecture croisée obligatoire, sous les identités
de la 3a plus « un compte qui n'a QUE son bac à sable » et « un invité ». La liste ci-dessus
est une énumération à la main : sa garde est un test qui joue, sous ce compte-là, CHAQUE
question de `Portee` et chaque route qui lit `peut_ecrire_quelque_part`, et exige la même
réponse que sans bac à sable (hors des routes du bac à sable lui-même) — le patron de
`test_projet_ecran.py` qui joue l'accord sous quatre identités.

**Reste à trancher.** Les personnages : **supposé** — « n'apparaissent que dans ses bacs à
sable » se calcule par les apparitions ; un personnage créé et jamais attribué n'a ni
apparition ni créateur écrit (sa création n'est pas journalisée, lu) : il reste visible de
tous et survit à l'effacement. Résiduel à écrire, le remède de fond étant l'étage de projet
de la tranche 4.

## S3 — L'isolement : rien n'entre, rien ne sort

**Proposé.** Un bac à sable est un cul-de-sac, et c'est la NATURE du projet qui le tient,
jamais la portée — une portée totale y travaille aussi (S1).
- **Ranger** : déjà tenu (`rangement_traverse`, lu) — une copie du bac à sable n'entre dans
  aucune collection d'un autre projet, pour personne. Rien à écrire.
- **Copier depuis** : une copie d'un bac à sable n'est la SOURCE d'aucune copie d'un autre
  projet — ni copie vierge par la portée totale (aujourd'hui permis : `_plan_d_une_ligne`,
  « sauf portée totale »), ni « en partir » (E4), ni demande entre projets (E7, à venir :
  son adressage saute les bacs à sable). Refus nommé.
- **Les documents NÉS dans un bac à sable** (`document.projet_origine_id` = un bac à sable :
  ce qu'on y importe) n'existent pour aucun autre projet : absents des notices, refusés à
  la prise, y compris pour la portée totale. Ils meurent avec leur dernière copie, à
  l'effacement.
- **Le fonds ne se remplit pas** : une copie sortie de sa dernière collection dans un bac à
  sable part au fonds comme ailleurs (apprendre le geste en vaut la peine) avec son projet
  écrit, et l'effacement la prend par `albums.projet_id` (S5). La vue « Fonds » de
  l'Administration masque les copies des bacs à sable par défaut (un filtre de plus).
- **Aucune demande n'atteint l'administrateur depuis un bac à sable.** Ce qui serait une
  demande à l'administrateur — supprimer définitivement, entrée de documents, rendre une
  copie gardée, supprimer le projet, et demain repartir de zéro — le PROPRIÉTAIRE le fait
  lui-même (S5 pour la règle de destruction), et un invité reçoit un refus nommé (« dans un
  bac à sable, c'est son propriétaire qui le fait »). Les demandes ENTRE comptes du bac à
  sable (rejoindre, en partir, adressées au propriétaire d'une collection) restent : c'est
  le travail à plusieurs qu'on vient essayer.

**Pourquoi.** 75 essais par semaine en demandes à l'administrateur rendraient « À faire »
illisible. Et un document importé dans un bac à sable n'a été choisi par personne pour
l'instance : le faire passer dans un vrai projet, c'est contourner l'entrée de documents.

**Ce que ça coûte.** Des refus en tête de quatre chemins (`_plan_d_une_ligne`,
`_plan_amorcer`, `POST /api/demandes`, `lire_les_notices`), chacun une ligne et un mutant ;
le filtre du fonds.

**Reste à trancher.** Q3 : un jour, faire sortir un travail de son bac à sable ? Proposé :
non, et l'écran le dit (« ce qui est fait ici s'efface »).

## S4 — Le jeu : des documents au fonds, des copies dans chaque bac à sable

**Proposé.**
- **Le jeu vit dans un PROJET DE JEU** caché — un seul, `projet.jeu = 1` (troisième drapeau,
  à côté de `repli` et `bac_a_sable_de`), sans membre, une collection : il porte les
  copies DE RÉFÉRENCE, une par document du jeu, chacune travaillée jusqu'à son cran. Les
  documents sont au fonds comme tous les autres (le fonds est l'ensemble des documents,
  lu). Pourquoi un projet et non des copies gardées au fonds sans collection : `creer_copie`
  range dans une collection, `copier_le_travail` lit une source vivante, et un projet
  caché se protège en une règle — on n'y range rien, on n'y détruit rien sinon par l'outil
  du jeu (409 nommé dans `_detruire_album` et `_supprimer_projet`), il n'apparaît dans
  aucune liste. Invisible de toute portée non totale (personne n'en est membre).
- **Une table du jeu**, `jeu_document(document_id PK, album_reference, cran, role, rang)` :
  `role` ∈ `pas-a-pas` (les une à trois planches où l'on suit toutes les étapes — copiées au
  cran `images`, vierges, puisque c'est l'apprenant qui fait), `exemple` (d'autres
  possibilités : copiées au cran où elles montrent quelque chose — `decoupage`,
  `transcription`, `grammaire`), `stock` (pour s'amuser, au cran `images`). Le wizard
  trouvera « la planche du pas-à-pas » par son rôle, jamais par un identifiant (S10).
- **Créer un bac à sable** = pour chaque ligne, `creer_copie(document, base, par=login,
  depuis=album_reference, cran=cran)`. Coût disque : zéro image copiée (D6, lu) ; des lignes
  `planches`, `regions`, index plein texte. **Supposé** : sous la seconde pour un jeu de
  dix documents de quelques planches (E9 mesurée : 0,05 à 0,4 s pour un album de 60
  planches × 40 régions).
- **Pas au-delà du cran `grammaire` dans le lot 2.** Au cran `annotations`, la copie
  emporte locuteurs et présences : les PERSONNAGES du jeu deviendraient communs aux 75 bacs à
  sable, et modifiables par chacun (S2) ; et les attributs de case sans `lien` humain
  comptent comme le travail d'un inconnu. L'annotation vient avec `ANN-7` (fiche COL-4), le
  cran `annotations` avec elle, et la question du personnage partagé à ce moment-là.
- **Sans spaCy à la création** : `copier_le_travail` recopie l'index sans spaCy quand la
  source n'a pas de note (lu, sa docstring) ; des sources de jeu SANS note le garantissent.
  **Supposé** au cran `grammaire` : à mesurer au commit, sinon `nlp.ensure_loaded()` avant
  le verrou, et dix secondes au premier clic d'une instance froide.
- **Préparer et changer le jeu** : un outil, `tools/preparer_jeu.py`, qui lit une
  DESCRIPTION déclarative (un dossier `jeu/` : `jeu.json` + les images) — notice, rôle,
  cran, et le travail en coordonnées master (régions, ordre, texte, corrections), comme
  `semer_demo.py` pose ses cases. Il écrit en base directement (verrou d'écriture, pas de
  `TestClient` — il mourrait en 403 derrière le proxy), à blanc par défaut,
  `--appliquer`. Changer le jeu = changer le dossier et relancer : l'outil crée le
  nouveau document, retire l'ancien de `jeu_document` (sa référence reste tant que des bacs
  à sable en tiennent des copies — ses images aussi, par référence — et part avec la
  dernière, au prochain effacement). Les bacs à sable existants gardent l'ancien jusqu'à
  leur remise à neuf. Les images passent par l'import ordinaire (`pipeline/ingest`) : la
  copie de travail d'IMG-1 (JPEG à 300 dpi, `master_origine`) s'applique d'elle-même.
- **Le travail du jeu n'est à personne** : écrit par l'outil, sans événement par région ;
  les corrections grammaticales ont `auteur` NULL. Conséquence lue dans
  `_sources_du_travail` : une correction d'auteur NULL compte comme « d'autrui » — le
  propriétaire ne supprimerait pas seul une copie au cran `grammaire`. C'est une raison de
  plus pour S5 (règle de destruction propre au bac à sable).

**Pourquoi.** La forme proposée par la fiche (« le jeu vit au fonds, chaque bac à sable en
prend des copies ») tient telle quelle avec les outils de la 3b ; la description
déclarative rend le jeu reproductible — les tests, la recette et la production fabriquent
le même.

**Ce que ça coûte.** Un drapeau, une table, un outil, un dossier `jeu/`. Le jeu de TEST
peut être synthétique (pages unies de `semer_demo`) ; celui de la production dépend de Q1.

**Reste à trancher.** Q1 (d'où viennent les images). Lu, pour la décider : la fiche demande
le DOMAINE PUBLIC « pour que le jeu vive dans le dépôt » — or **supposé** : la bande
franco-belge à bulles en français du domaine public est rare (Töpffer, Christophe, Forton,
Rabier, Pinchon/Caumery : surtout du texte sous l'image) ; et le domaine public de l'œuvre
ne dit rien de la licence du SCAN (Gallica a ses conditions de réutilisation).

## S5 — Remettre à neuf, effacer chaque semaine

**Proposé.**
- **Un chemin de destruction à lui**, `socle._effacer_bac_a_sable(conn, portee, projet_id)`,
  distinct de `_supprimer_projet` (qui n'accepte qu'un projet vide et doit le rester pour
  les vrais). Sa première garde, relue sous le verrou : `projet.bac_a_sable_de IS NOT NULL`
  — jamais un projet ordinaire, jamais le jeu, jamais le repli. Puis, dans l'ordre :
  1. relever les personnages qui apparaissent dans ses albums ;
  2. détruire chaque album dont le projet (écrit ou lu, `sql_projet_d_album`) est ce bac à
     sable — rangés ou gardés au fonds — par `_detruire_album` : fin des emplois au journal,
     demandes closes, document parti avec sa dernière copie (ce qu'on y a importé), images
     effacées par référence — celles du jeu restent, la référence et les autres bacs à
     sable les désignent ;
  3. supprimer le vocabulaire local à ses collections (ses tags d'abord : S2 les y fait
     naître), les accès (cascade), ses collections base comprise, en refusant les demandes
     qui les visent (`_clore_demandes_vers`) ;
  4. supprimer les personnages relevés en 1 qui n'apparaissent plus nulle part ;
  5. supprimer le projet (`projet_acces` en cascade), et l'écrire : `suppression` sous
     `projet`, charge `{bac_a_sable: true, motif: "remise à neuf" | "effacement"}`.
- **La règle de destruction dans un bac à sable** : son PROPRIÉTAIRE détruit tout album de
  son bac à sable, sans demande, quel que soit qui y a travaillé — un disjoint de plus dans
  `clause_suppression_directe` (le projet écrit de l'album ∈ ses bacs à sable), ce qui fait
  aussi offrir « Supprimer définitivement » à l'écran (`destructible`). Un invité garde la
  règle commune (sa copie, que personne n'a touchée). C'est la décision 3b de Hugo
  (« le responsable efface tout album de son projet ») en avance, bornée au bac à sable ;
  la clause « dernière copie → administrateur » ne s'y applique pas : un document né dans
  un bac à sable n'existe pour aucun autre projet (S3).
- **Remettre à neuf** : `POST /api/bac-a-sable/remise-a-neuf`, au propriétaire seul (403
  nommé à un invité), = effacer puis créer. `_detruire_album` commite par album : un arrêt au
  milieu laisse un bac à sable à moitié effacé, que la reprise finit (idempotent) ; la
  création n'a lieu qu'une fois la ligne `projet` partie. L'écran confirme et dit ce qui part
  (« le travail de vos invités aussi »).
- **L'effacement hebdomadaire — la date est en base, la minuterie n'est qu'un battement.**
  À la création, `projet.efface_le` reçoit le prochain moment d'effacement (un réglage :
  proposé lundi 4 h, heure de Paris, dans `config.py`) ; un outil,
  `tools/effacer_bacs_a_sable.py` (à blanc par défaut, `--appliquer`, verrou propre à
  l'outil, arrêt propre sur SIGTERM — le patron d'IMG-1), efface les bacs à sable dont
  `efface_le` est passé. Une minuterie sur l'hôte, `deploy/systemd/bd-bacs-a-sable.{service,timer}`
  (patron de `bd-deploiement` : `oneshot`, `User=ubuntu`, `PATH`), le lance TOUTES LES
  HEURES par `docker exec bd-app python tools/effacer_bacs_a_sable.py --appliquer`. Une
  seule source de la date — celle qu'on affiche est celle qu'on applique —, une minuterie
  manquée se rattrape à l'heure suivante, et la recette sans minuterie se lance à la main.
- **Le journal** : append-only, il garde tout — les actes des apprenants (`comptes.traces`
  les compte : ce sont des gestes réels), la naissance des copies, les destructions. Aucun
  identifiant ne revient pour les albums, planches, régions, personnages, projets (lu,
  `AUTOINCREMENT`). **Les collections, si** : 75 bacs à sable par semaine les font tourner
  vite, et le journal (`collection`, `collection_acces`, les emplois) en mêlerait deux. D'où
  S7.
- **Ce que voit qui travaille à l'instant** : sa prochaine requête répond 404 (l'album n'est
  plus) ou 409 (verrou, réessayer). L'écran, qui sait que le projet courant était un bac à
  sable (`BDProjets`), dit « Votre bac à sable a été effacé » et offre d'en recréer un ;
  le projet courant retombe par la règle de `projet.js`. À 4 h, c'est rare.
- **Ctrl+Z après un effacement** (lu, `undo.py`) : l'annulation est par AGENT, sur tout
  projet ; les actes faits dans le bac à sable effacé sont refusés un par un (« ne
  s'annule plus ») puis passés. Proposé : un témoin de plus dans `undo._meme_objet` —
  l'album de l'acte a été détruit depuis — et que `derniere_action_annulable` les saute en
  bloc. Le même besoin qu'E8 (le cinquième témoin d'une remise à zéro) : à écrire une fois.

**Pourquoi.** Réutiliser `_detruire_album` garde les gardes déjà relues (verrou, images par
référence, demandes closes) ; un chemin à part pour le projet évite d'affaiblir
`_supprimer_projet`, la protection des vrais projets.

**Ce que ça coûte.** Le chemin, l'outil, deux unités systemd, `docs/exploitation.md` (les
installer, les lister, les arrêter). **Supposé** : 75 bacs à sable × une dizaine d'albums =
750 destructions, chacune quelques dizaines de millisecondes — moins d'une minute, sous le
verrou album par album.

**Reste à trancher.** Q2 (le moment, et le bac à sable créé la veille).

## S6 — L'écran (se tranche sur maquette)

**Proposé, à poser sur la maquette** — une petite, en session dédiée, avant le commit
d'écran (mémoire du projet : une disposition se tranche sur maquette).
- **Où naît « Mon bac à sable »** : trois places candidates — (a) la bande du haut, à côté
  du projet ; (b) le bandeau de portée vide, là où l'arrivant de la vague atterrit (« Vous
  n'avez accès à aucune collection — en attendant : Mon bac à sable ») ; (c) le menu de la
  pastille d'identité. Proposé : (b) + (c), et dans la bande seulement le projet une fois
  créé (il entre dans le `<select>` comme les autres). La bande est déjà mesurée au pixel à
  320 px : y ajouter un bouton est le risque, d'où la maquette.
- **Dans le bac à sable** : une ligne sous la bande — « Bac à sable · effacé lundi
  27 octobre à 4 h · Remettre à neuf… » —, stable, une infobulle pour le reste (mémoire :
  écran stable, sans phrases). La date vient de `efface_le` (UTC, lu en heure locale comme
  les dates SQLite de `suppression.js`). Le propriétaire seul voit « Remettre à neuf… » ;
  l'invité lit de qui est le bac à sable. « Qui y entre » vit dans la fiche du projet
  d'aujourd'hui (Administration → Projets) : il faut un chemin plus court pour un arrivant
  — proposé : le module `membres-projet.js` MONTÉ une seconde fois sur la page du bac à
  sable (la convention des modules montables le prévoit ; `ajusterALaPlace` si colonne).
- **L'Administration et les 75 projets** : la vue « Projets » masque les bacs à sable par
  défaut, un filtre « Bacs à sable · n » les montre (avec propriétaire, date d'effacement, et
  « Effacer maintenant » pour l'administrateur — le même chemin) ; « Comptes et groupes »
  et « Fonds » les écartent de leurs signaux (S2, S3). `GET /api/projets` ne rend à une
  portée totale QUE son propre bac à sable et ceux dont elle est membre, sauf
  `?bacs_a_sable=1` (la vue Projets) : sinon le `<select>` de l'administrateur aurait 75
  entrées.
- **Le sélecteur de projet** d'un compte ordinaire : son bac à sable, ceux où il est invité,
  ses vrais projets. Aucun changement de forme.

**Reste à trancher.** La maquette ; le texte exact de la ligne de date.

## S7 — La migration et les règles

**Proposé.**
- **La v35** (hypothèse : v34 est IMG-1, sur `dev` ; la 3b est le lot 3 et son réglage « les
  membres peuvent créer des collections » prendra donc la v36 — à confirmer selon l'ordre
  réel des commits) : `projet.bac_a_sable_de TEXT`, `projet.efface_le TEXT`,
  `projet.jeu INTEGER NOT NULL DEFAULT 0` (commentaires SOUS la dernière colonne, la règle
  de SQLite 3.49), la table `jeu_document`. Aucune donnée à migrer : tout est NULL ou 0.
- **`collection` reçoit `AUTOINCREMENT`** dans la même migration, par la machinerie de la
  v30 (`_reconstruire_avec_autoincrement`, une entrée de plus dans `_AUTOINCREMENT` : les
  cibles `collection`, `collection_acces`, `collection_album` et la clé `collection_id` des
  charges ; `_HORS_JOURNAL` : `demande.collection_id`). C'est ce que le bac à sable rend
  urgent (S5) ; c'était un résiduel écrit. Coût : une reconstruction de table référencée
  par plusieurs autres (accès, emplois, les quatre tables du vocabulaire — **supposé**, à
  recenser), clés étrangères suspendues — la machinerie existe et a sa vraie base.
- **La vraie base de la v34 n'existe pas** (lu : `tests/bases/` s'arrête à
  `v33-e5d2e73.sql`). Commit 0 : `tools/fabriquer_base_de_version.py <commit v34>
  tests/bases/v34-<commit>.sql`, une branche `SCHEMA_VERSION >= 34` qui pose ce que la v35
  doit traverser — des collections détruites en haut de table (pour le compteur), des
  copies sœurs, une copie amorcée (`region_origine`), des planches converties
  (`master_origine`). Le commit est la tête de `dev` avant COL-4 : `main` n'a jamais porté la
  v34, et la règle « tête de `main` » ne s'applique pas telle quelle — à dire dans l'en-tête
  du fichier.
- **Les cliquets** : `test_autorisation` (les routes neuves tranchées),
  `test_sorties_identite` (`GET /api/bac-a-sable` et `GET /api/projets` ne rendent PAS
  `bac_a_sable_de` — un login — à un invité : `mien` et le nom affiché seulement ; sinon
  déclarer), `test_decoupage_api` (le module neuf, ses imports), `test_csrf` (les envois du
  front par `apiSend`), `CIBLES_RETENUES` (`projet` y est déjà ; rien du bac à sable ne sort
  au dépôt).

**Reste à trancher.** `collection` en `AUTOINCREMENT` maintenant (proposé) ou plus tard.

## S8 — Les surfaces qui traversent les projets

**Lu** : la Recherche, l'Exploration (distribution, concordance, croisement, comparaison),
l'accord modèle↔humain et l'accord inter filtrent par `clause_album`, qui vaut `"1"` pour une
portée totale. **Conséquence** : chez l'administrateur, 75 copies du jeu entrent dans
chaque concordance et chaque fréquence, et l'accord modèle↔humain (l'étalon de NLP-1)
compte 75 fois les corrections du jeu au cran `grammaire`. Pour un compte ordinaire, son bac
à sable se mêle à ses vrais projets.

**Proposé** : une `Portee` de plus, `pour_le_corpus()`, sur le patron de `pour_export()` —
la même personne sans les bacs à sable ni le jeu —, que reçoivent les cœurs transverses
(`_recherche_rows`, `_analyse_filtres`, `accord`, `accord_inter`) ; pour une portée totale,
une clause d'exclusion au lieu de `"1"`. La tranche 4 bornera tout cela au projet courant ;
d'ici là, un bac à sable ne s'interroge pas par la Recherche (le wizard du lot 4 en
tiendra compte).

**Ce que ça coûte.** Une méthode, quatre cœurs, un test par surface sous une portée totale.

**Reste à trancher.** Q4.

## S9 — Les ressources

**Supposé, à mesurer sur la recette** : l'import dans un bac à sable (apprendre à importer
fait partie du parcours) écrit de vraies images — IMG-1 les réduit à 300 dpi. 75 comptes
qui importent chacun un album de 50 planches, c'est quelques gigaoctets pour une semaine.
Proposé : autoriser, avec un plafond de planches IMPORTÉES par bac à sable (refus nommé au
dépassement) ; les copies du jeu ne comptent pas. Q5.

## S10 — La place du wizard

**Proposé**, sans rien en coder : `GET /api/bac-a-sable` rend, à côté de l'id et de la date,
la carte du jeu posé — `[{role, rang, album_id, planche_ids}]` — lue dans `jeu_document` et les
copies nées à la création (par `copie.depuis_album_id` = la référence). Le wizard (lot 4) y
trouve la planche du pas-à-pas et fabrique ses liens profonds vers l'Atelier ; la ligne de
S6 lui laisse sa place (un bouton « Par où commencer » y viendra). Le jeu de test garde au
moins un document de chaque rôle.

## S11 — L'invitation

**Proposé.** Dans un bac à sable, on fait entrer des LOGINS, au rôle `membre` seulement (S1),
sans lecture de l'annuaire (S2). Un GROUPE entier ferait entrer 30 étudiants dans le bac à
sable d'un enseignant — utile, mais effacé chaque semaine et remis à neuf par une seule
personne. Q6.

## S12 — Ce qui reste écrit à côté

- `CLAUDE.md` § Autorisation : la question neuve (S1), l'ensemble `bacs_a_sable` et ce qu'il
  ne donne pas (S2), l'isolement (S3), la règle de destruction dans un bac à sable (S5) ;
  § Données : le projet de jeu ; § Schéma : v35.
- `docs/modele-et-droits.md`, `docs/guide-utilisateur.md` (le bac à sable, sa date),
  `docs/exploitation.md` (la minuterie, l'outil du jeu, l'effacement à la main),
  `docs/undo.md` (le témoin de S5).

---

## Les règles d'autorisation

Une question neuve, `peut_ouvrir_un_bac_a_sable` ; un ensemble neuf dans `Portee`,
`bacs_a_sable`, et ses conséquences sur quatre questions transverses (S2) ; un disjoint dans
`clause_suppression_directe` (S5) ; une `Portee` dérivée, `pour_le_corpus` (S8). Inchangées :
`peut_decider_des_projets`, `clause_album`, `clause_destruction`, `rangement_traverse`.

### Ce qui fuit si l'on se trompe

- **Un projet ORDINAIRE effacé** par le chemin du bac à sable — mutant : la garde
  `bac_a_sable_de IS NOT NULL` retirée ; le test l'appelle sur le repli, un vrai projet, le
  projet de jeu.
- **Les images du jeu effacées** à l'effacement d'un bac à sable — mutant : effacer les
  dossiers de la copie sans lire les références ; le test vérifie les fichiers de la
  référence après l'effacement du dernier bac à sable.
- **Les notices du fonds lues par un arrivant** — mutant : `peut_lire_les_notices` sur
  `projets_geres` entier.
- **Le vocabulaire global modifié depuis un bac à sable** ; **un tag global né d'une
  annotation de bac à sable** — mutants : `peut_ecrire_quelque_part` sur `ecriture` entier ;
  `_ensure_tags` sans la collection.
- **Un invité qui retire le propriétaire, ou se fait responsable** — mutant : la garde de
  `PUT …/membres`.
- **Un second bac à sable pour le même login** (deux clics simultanés) — mutant : la
  relecture hors du verrou.
- **Une copie de bac à sable source d'une copie dans un vrai projet** — mutant : le refus de
  S3 sous une portée totale.
- **L'annuaire lu par un propriétaire de bac à sable** — mutant : la garde des deux routes de
  choix.
- **Une demande d'un bac à sable dans « À faire »** — mutant : le refus de `POST /api/demandes`.
- **Le bandeau de portée vide éteint par le bac à sable** — mutant : `acces.collections` sur
  `lecture` entière.

---

## Le découpage en commits

0. **La vraie base v34** (`tests/bases/v34-<commit>.sql`, branche `>= 34` de l'outil de
   fabrication), **puis la v35** : colonnes, `jeu_document`, `collection` en
   `AUTOINCREMENT` ; test de migration sur la vraie base (patron `test_migration_v31.py`).
   ½ jour.
1. **Le jeu** : le projet de jeu, `tools/preparer_jeu.py`, un jeu de test synthétique dans
   `tests/`, les refus qui protègent la référence. ½ à 1 jour (hors le choix des images, Q1).
2. **Créer et borner** : `routes/bac_a_sable.py` (`GET`/`POST`), la question neuve,
   l'ensemble `bacs_a_sable` et S2 entier, l'isolement S3, l'invitation S11. Le cœur : 1½ à
   2 jours, mutants compris.
3. **Effacer** : `_effacer_bac_a_sable`, la règle de destruction S5, la remise à neuf,
   `tools/effacer_bacs_a_sable.py`, les unités systemd, le témoin de l'annulation. 1 jour.
4. **Les surfaces transverses** (S8). ½ jour.
5. **L'écran**, après la maquette (S6) : la naissance, la ligne de date, la remise à neuf, le
   filtre de l'Administration, le message après effacement. 1 jour.
6. **La documentation** (S12).

**Estimation : 5 à 6½ jours**, au-dessus des 3 à 5 de la fiche — l'écart est S2 et S8 : la
fiche ne comptait pas que le bac à sable fait de chaque arrivant quelqu'un qui « écrit
quelque part » et « est responsable ». Si Hugo veut tenir 3 à 5 jours, ce qui se reporte
sans risque est S8 (les surfaces transverses de l'administrateur polluées une semaine, pas
une fuite) ; S2 ne se reporte pas.

Chaque commit de code cite `COL-4`. **Relecture croisée obligatoire** (le cœur des droits :
une exception à « qui crée un projet », un ensemble neuf dans `Portee`, un chemin de
destruction de projet), par une session qui ne l'a pas écrite, sous les identités de la 3a
plus trois : un arrivant qui n'a QUE son bac à sable, son invité, un administrateur qui a le
sien ; sur une base qui porte le jeu, trois bacs à sable dont un expiré, une copie gardée au
fonds dans l'un, un document importé dans un autre.

### Les passes de QA à écrire

Rédigées, jamais cochées par qui les écrit : **`bac-a-sable`**, neuve (le premier clic sous
un compte neuf, recliquer, inviter et travailler à deux, remettre à neuf, l'effacement lancé à
la main et ce qu'on voit à l'instant, la date, un compte partagé refusé) ; `projet-visible`
et `administration-a-l-echelle` rejouées (le sélecteur, la vue Projets avec 75 bacs à sable
semés) ; `petites-largeurs` et `preference-de-police` sur la ligne de date.

---

## Les questions qui restent à Hugo

| | Question | Options | Proposé |
|---|---|---|---|
| Q1 | **D'où viennent les images du jeu ?** | (a) des scans du DOMAINE PUBLIC (Gallica, Commons) — dans le dépôt, export permis dans le bac à sable ; mais surtout du texte sous l'image, et la licence du scan est à lire ; (b) des planches DESSINÉES pour l'outil, sous licence libre — dans le dépôt, avec de vraies bulles ; (c) des scans du corpus, sur le VPS hors dépôt — export fermé dans les bacs à sable | (b) si quelqu'un peut les dessiner, sinon (a) ; le jeu des tests reste synthétique dans tous les cas |
| Q2 | **Quand l'effacement ?** | (a) un moment fixe pour tous (lundi 4 h), un bac à sable créé moins de 24 h avant étant gardé jusqu'au suivant ; (b) un moment fixe, sans exception ; (c) sept jours après sa création, chacun le sien | (a) |
| Q3 | **Un travail peut-il sortir d'un bac à sable ?** | (a) jamais, et l'écran le dit ; (b) plus tard, par « en partir » entre deux projets (E7), comme n'importe quel projet ; (c) par un administrateur seulement | (a) |
| Q4 | **La Recherche et l'Exploration voient-elles les bacs à sable ?** | (a) non, pour personne, d'ici la tranche 4 (S8) ; (b) oui pour ceux qui en sont, non pour les autres et pour l'administrateur ; (c) rien maintenant, la tranche 4 le fera | (a) — le plus simple à garder, et (b) suppose le projet courant côté serveur, que la tranche 4 apportera |
| Q5 | **Importer dans un bac à sable ?** | (a) oui, avec un plafond de planches (S9) ; (b) oui, sans plafond ; (c) non, le jeu suffit | (a), plafond à fixer sur la recette (proposé : 50 planches) |
| Q6 | **Qui peut-on inviter ?** | (a) des comptes, membres seulement ; (b) des comptes et des groupes, membres seulement ; (c) comme dans un vrai projet, responsables compris | (a) |

Se tranchent en route, sans Hugo sauf avis contraire : le nom affiché mesuré sur la bande
(S1) ; `collection` en `AUTOINCREMENT` dans la v35 (S7) ; ShareDocs sous le compte de
l'instance (S2) ; le témoin de l'annulation partagé avec E8 (S5). Sur maquette : S6.
