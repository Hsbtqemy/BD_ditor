# ANN-6 — une zone nomme plusieurs locuteurs : cadrage

Rendu le 2026-11-02, sur `dev` à `55da317` (schéma **38**). Rien n'est codé ni exécuté :
aucun test n'a été lancé, aucune base n'a été ouverte. Ce qui est marqué **lu** a été lu
dans le code à ce commit ; ce qui est marqué **supposé** ne l'a pas été, ou reste à mesurer.

La décision qui PRIME est celle de Hugo du 2026-11-02 (`pilotage/ANN-6.md`, case « Une zone
nomme plusieurs locuteurs ») : *« une zone peut avoir plusieurs locuteurs »* — deux
personnages qui parlent dans la même bulle, le même cartouche ou le même texte se désignent
tous deux dans le registre, et la grille des linguistes y pose deux relevés « personnage
identifié » (la cardinalité de l'entrée « locuteur » passe à `plusieurs` dans le brouillon).
Cette note ne la rediscute pas : elle dit ce qu'elle fait au code. Ce qu'elle laisse ouvert
est numéroté **L1 à L13**, en fin de note, chaque fois avec la proposition la plus simple et
la plus fermée. La case du narrateur, juste au-dessus dans la fiche (« Le narrateur d'un
récitatif a sa place dans le registre… »), reste aux linguistes : rien ici ne la tranche, et
rien ne l'empêche — un narrateur qui est un personnage de l'histoire sera un locuteur parmi
d'autres, un narrateur anonyme laissera la liste vide.

Ce que la fiche demande de GARDER, et qui tient : un même personnage désigné depuis une
bulle, un cartouche, un texte hors bulle (locuteur, `config.TYPES_LOCUTEUR`) et une boîte
personnage (personnage montré) reste UNE fiche du registre, comptée une fois. Rien de ce qui
suit ne touche à `personnages` ni à `personnage_presence`.

---

## Ce que le changement livre, en gestes

1. **Une zone de texte porte zéro, un ou plusieurs locuteurs** — chacun une fiche du
   registre, sans doublon (un personnage ne parle qu'une fois dans une zone).
2. **On AJOUTE un locuteur, on en RETIRE UN** — depuis l'Atelier et depuis le Contexte de la
   page Annotation. Remplacer n'est plus un geste du serveur : c'est un retrait puis un ajout.
3. **Chaque sortie dit tous les locuteurs d'une zone, et ne la duplique pas** — analyses de
   l'Exploration, exports du dépôt, IIIF.
4. **Ctrl+Z défait un locuteur à la fois** — celui que le geste a ajouté ou retiré.
5. **Une zone à deux locuteurs se copie, se remet à zéro, se fusionne et se supprime comme
   une zone à un** — copies amorcées, repartir de zéro, fusion de personnages, suppression
   rétablie par Ctrl+Z.

Ce que le changement ne livre pas : un lien entre un relevé de la grille et une fiche du
registre (§ La grille et le registre) ; plusieurs personnages MONTRÉS dans une boîte (L9) ;
la forme d'écran du champ « Locuteur », qui se tranche sur maquette.

---

## Ce qui existe (lu)

### La table

`bulle_locuteur` (`database.SCHEMA_SQL`) : `region_id INTEGER PRIMARY KEY REFERENCES
regions(id) ON DELETE CASCADE`, `personnage_id INTEGER NOT NULL REFERENCES personnages(id)
ON DELETE CASCADE`, `date_creation`, `recopiee` (v36, posée par `copier_le_travail`). Son
commentaire dit « au plus une → region_id PK ». Un index `idx_locuteur_perso` sur
`personnage_id`. Aucune vue ne la lit (`_VIEWS_SQL`, lu). Le nom date d'avant ANN-6 et le
commentaire le dit ; `personnage_presence` a exactement la même forme.

### Les routes (`routes/personnages.py`, lu)

- `GET /api/regions/{id}/locuteur` → `{"locuteur": {id, nom, serie} | null}` par
  `_locuteur_for` (un `fetchone` implicite : `_row`).
- `PUT /api/regions/{id}/locuteur` (`set_locuteur`, corps `socle.LocuteurIn` :
  `personnage_id`, `personnage_vu` facultatif) : verrou (`conflit.verrouiller`), accesseur
  gardé en écriture, 422 hors `TYPES_LOCUTEUR`, `_get_personnage`,
  `_exiger_le_personnage_ici` (la rive d'un bac à sable), garde CONC-4 si `personnage_vu` est
  envoyé (`_garder_le_lien` → `conflit.verifier`), puis
  `INSERT … ON CONFLICT(region_id) DO UPDATE SET personnage_id = excluded.personnage_id` —
  c'est-à-dire un REMPLACEMENT — et un acte `lien` sous `bulle_locuteur`, `cible_id` = la
  région, `avant` = `{"personnage_id": ancien}` ou NULL, `apres` = `{"personnage_id": neuf}`.
- `DELETE /api/regions/{id}/locuteur?personnage_vu=` (`clear_locuteur`) : supprime la ligne
  de la région, acte `delien` avec `avant` = `{"personnage_id": ancien}`.
- `POST /api/personnages/{id}/fusion` (`fusionner_personnage`) :
  `UPDATE bulle_locuteur SET personnage_id = cible WHERE personnage_id = doublon` — le
  commentaire dit « une zone a au plus un locuteur (region_id PK) → réaffectation directe ».
  Rien n'est journalisé (`docs/undo.md` le dit assumé).
- `GET /api/personnages` : `nb_bulles` = `COUNT(*)` des lignes du personnage, bornées par
  `clause_album`.

### Les autres écrivains (lu)

- **Le changement de type** (`main.py`, la route `PUT /api/regions/{id}`) :
  `database.liens_vus` photographie `{"locuteur": id | None, …}` dans `avant["liens_vus"]`,
  `database.retirer_liens_caches` supprime le locuteur d'un type muet et rend
  `{"locuteur": id}`, rangé dans `avant` ; la réponse rend `locuteur_retire` (un personnage).
- **`database.retirer_locuteur_muet`** et **`tools/retirer_locuteurs_muets.py`** : lisent
  `_SQL_LOCUTEURS_MUETS`, suppriment par région, rendent `rows[0]["personnage_id"]`.
- **`copier_le_travail`** (copies amorcées, cran `annotations`) : `_par_region` recopie
  chaque ligne avec sa `date_creation` et `recopiee = 1`.
- **`repartir_de_zero`** : `retirer("bulle_locuteur")`, par région.
- **`undo._poser_lien`** : `INSERT … ON CONFLICT(region_id) DO UPDATE`, partagé avec
  `personnage_presence` ; **`undo._retirer_lien`** : `DELETE … WHERE region_id = ?`.
- **`socle._effacer_bac_a_sable`** : ne lit `bulle_locuteur` que par `EXISTS`.

### L'écran (lu)

- **Atelier** (`static/viewer.js`) : `loadLocuteur`, `renderLocuteur` (UNE puce, son ×, ou
  « Aucun locuteur »), `setLocuteur`/`envoyerLocuteur` (PUT, `personnage_vu` = `state.locVu`),
  `clearLocuteur`/`retirerLocuteur` (DELETE), `conflitDeLien` et le bandeau (lieu
  `locuteur`). La puce porte aussi le **profil** du personnage (`persoAttrWidget`) et son
  **alignement d'autorité** (`locAlignWidget`, A5) : l'un et l'autre se chargent pour LE
  locuteur. `messageRetraits` dit « Locuteur « X » retiré » après un changement de type.
- **Page Annotation** (`static/annotation.js`) : `rendreContexte` lit
  `GET …/locuteur`, `montrerLocuteur` (une puce `#an-loc-nom` et `#an-loc-retirer`),
  `choisirLocuteur`/`envoyerLocuteur`, `retirerLocuteur`/`envoyerRetraitLocuteur`, la valeur
  vue `S.loc.vu`, `refusDuContexte` (le bandeau dans la boîte du guide), `RETENUES` et le
  conflit en vol. `static/lib/annotation.js` : `contexte` rend une ligne « Locuteur » à UNE
  valeur (`nom(d.locuteur)`), `gestesDuContexte` l'offre sur une zone de texte.
- **Le champ commun** (`static/lib/champ-personnage.js`) ne fait que la liste et le choix
  (`onPick(personnageId, zone, nom)`) : il ne sait pas ce qu'on fait du choix, et n'a pas à
  changer.
- **`static/lib/conflit.js`** : `AUCUN.locuteur = "Aucun locuteur"`, `texteLienNonEnregistre`,
  `nomPersonnage` — un personnage, pas une liste.
- **Exploration** (`static/exploration.js`) : `kwicMeta` affiche `r.locuteur` (une chaîne) ;
  l'axe `locuteur` du croisement ; le filtre par personnage.

`config.TYPES_LOCUTEUR = ("bulle", "cartouche", "texte")` ne change pas.

---

## Les lecteurs de `bulle_locuteur`, un par un

Recensés par recherche sur tout le dépôt (`bulle_locuteur`, `locuteur`, `ON CONFLICT
(region_id)`), `tools/` compris, tests exclus. Trois formes de lecture, et seule la
troisième est en danger :

- **`EXISTS`** (« la zone a-t-elle ce locuteur ? ») : juste avec N lignes, sans changement ;
- **`COUNT`** par personnage, ou par lignes : juste, mais un compte de LIENS n'est plus un
  compte de ZONES ;
- **`fetchone`, `dict(...)`, `LEFT JOIN`, `ON CONFLICT(region_id)`** : faux ou en panne avec
  N lignes — et presque toujours EN SILENCE.

### En panne dès la migration (le `ON CONFLICT(region_id)` et la clé primaire)

| Lecteur | Ce qui se passe avec la clé `(region_id, personnage_id)` |
|---|---|
| `routes/personnages.set_locuteur` | `ON CONFLICT(region_id)` ne désigne plus aucune contrainte : SQLite refuse la requête. **Supposé** : `sqlite3.OperationalError` (« ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint »), que le gestionnaire de `main.py` ne change en 409 que pour « locked/busy » → un 500 |
| `undo._poser_lien` | même requête, partagée avec `personnage_presence` : Ctrl+Z en panne sur le locuteur. Et `_inverser` ne rattrape que `IntegrityError` : l'erreur ne devient pas un « passé » |
| `routes/personnages.fusionner_personnage` | `UPDATE … SET personnage_id = cible` sur une zone qui porte DÉJÀ la cible : violation de clé primaire, `IntegrityError` non rattrapée → 500, rien de fusionné. À réécrire `INSERT OR IGNORE … SELECT` puis `DELETE` |

Ces trois-là doivent changer dans le MÊME commit que la migration.

### Faux en silence avec N locuteurs

| Lecteur | Forme | Ce qui se perd |
|---|---|---|
| `_locuteur_for` (GET, réponses du PUT, `_LIENS_GARDES`) | `_row` : la première ligne | les autres locuteurs, à l'écran |
| `empreinte.empreintes` | `dict(SELECT region_id, personnage_id …)` | le dict garde UNE ligne par région : ajouter un second locuteur peut ne pas changer l'empreinte, et « ⟳ Actualiser » ne paraît pas chez l'autre (CONC-4). À passer en `defaultdict(list)` trié, comme `tags` et `situations` juste au-dessus |
| `journal.snapshot_region_profond` | `fetchone` → `base["locuteur"] = id` | l'instantané d'une région supprimée ne garde qu'un locuteur ; Ctrl+Z de la suppression n'en rend qu'un |
| `database.liens_vus` | `fetchone` | la photographie d'un changement de type n'en voit qu'un ; `undo._garder_liens_du_type` compare alors à un ensemble faux |
| `database.retirer_liens_caches`, `retirer_locuteur_muet` | supprime TOUT par région, rend UN id | le changement de type retire tous les locuteurs mais n'en range qu'un dans `avant` : Ctrl+Z n'en rend qu'un ; la réponse `locuteur_retire` n'en nomme qu'un |
| `tools/retirer_locuteurs_muets.py` | boucle sur `locuteurs_muets` (N lignes par région), mais `retirer_locuteur_muet` supprime tout au premier tour et rend None aux suivants | les `delien` des locuteurs suivants ne sont pas journalisés |
| `routes/analyse._concordance_rows` | `LEFT JOIN bulle_locuteur blc … LEFT JOIN personnages loc` | **chaque token d'une zone à deux locuteurs sort deux fois** — à l'écran, dans `concordance.csv`, et le `LIMIT` se remplit de doublons. Ordre de grandeur : une ligne de plus par token et par locuteur au-delà du premier |
| `routes/analyse._axe_croisement`, axe `locuteur` | `LEFT JOIN` par axe | le token compte dans CHAQUE locuteur — c'est la règle « fan-out » déjà écrite pour les tags et les dimensions (la docstring d'`analyse_croisement` le dit), donc juste, et le `total` dépasse le nombre de tokens. À DIRE (L2) |
| `_axe_croisement`, axe `locuteur` × axe `dim:<id>` de cible `personnage` | DEUX jointures indépendantes de `bulle_locuteur` (`blx_x`, `bld_y`) | **un produit cartésien** : dans une bulle où parlent A (enfant) et B (adulte), la cellule « A × adulte » reçoit les tokens de la zone. Même faute pour deux axes de profil (`dim:âge` × `dim:sexe`) : l'âge de A croisé au sexe de B. Faux, pas discutable : les deux axes doivent partager UNE jointure du locuteur quand ils passent tous deux par lui |
| `tools/metadonnees_collection.py` (`_contexte` : `"locuteur": {region_id: nom}`) | `dict` | **le dépôt ne garde qu'un locuteur par zone**, le dernier lu : JSON (`"locuteur": c["locuteur"].get(id)`), table CSV `regions` (colonne `locuteur`), onglet XLSX `arbre` (« locuteur / présence ») |
| `tools/iiif_manifest.py` (`_region_anno`) | lit le `locuteur` de l'arbre de `metadonnees_collection` | un seul corps `identifying` « locuteur : … » |
| `static/viewer.js`, `static/annotation.js`, `static/lib/annotation.js`, `static/lib/conflit.js`, `static/exploration.js` | une valeur | cf. § L'écran |

### Juste, mais dont le sens bouge

| Lecteur | Forme | Avec N locuteurs |
|---|---|---|
| `routes/analyse._analyse_filtres`, filtre `personnage` | `EXISTS` | juste : la zone où A parle, seul ou avec B. Distribution, comparaison A/B (`_distribution`), concordance, croisement en dépendent. **Une zone où A et B parlent compte dans le sous-corpus A ET dans le sous-corpus B** de la comparaison (L2) |
| `_analyse_filtres`, filtre `attributs` (profil du locuteur) | un `EXISTS` par valeur, ET entre eux | « un enfant ET une femme » est satisfait par une bulle où parlent un garçon et une adulte : chaque valeur est portée par UN des locuteurs, pas forcément le même (L4) |
| `routes/recherche.py` (facettes `personnage`, `attributs`) | `EXISTS`, même forme | même remarque que les deux lignes ci-dessus ; rien n'est dupliqué, le texte cherché n'indexe pas le locuteur (`reindex_region` ne le lit pas, lu) |
| `routes/personnages.list_personnages` (`nb_bulles`) | `COUNT(*)` par personnage | une zone compte une fois PAR personnage qui y parle : juste, la clé dit des prises de parole |
| `socle._clause_personnage` (portée d'un personnage par ses apparitions) | `EXISTS` | inchangé |
| `socle._effacer_bac_a_sable` | `EXISTS` | inchangé |
| `database.niveau_de_travail` | `EXISTS` | inchangé |
| `database.copier_le_travail` (`_par_region`) et l'aperçu `compter_le_travail` | ligne par ligne ; `COUNT(*)` ; `UNION` des personnages | recopie juste ; `copies["locuteurs"]` compte des liens ; le compte de personnages rendus lisibles (E6) est un `UNION`, donc dédoublonné |
| `database.repartir_de_zero`, `compter_repartir` | `DELETE`/`COUNT(*)` par région | juste ; « Part » compte des liens (`static/lib/echelle.js` dit « locuteurs ») |
| `tools/description_collection.py` | `COUNT(*)` (« liens ») et `COUNT(DISTINCT personnage_id)` | juste ; « liens » cesse d'être le nombre de zones attribuées. Ajouter `COUNT(DISTINCT region_id)` si la fiche du corpus veut ce nombre-là (L12) |
| `autorisation._sources_du_travail` (source 1 : les actes sous `bulle_locuteur` par `cible_id` = la région) | un acte par geste | juste ; « qui perd quoi » compte des gestes |
| `autorisation._SQL_COUCHE_VIT` (la sixième source : la couche recopiée vit-elle ?) | `EXISTS … WHERE region_id = d AND recopiee = 1` | par RÉGION, pas par personnage : un acte sur A à la source « vit » tant qu'UN locuteur recopié vit sur la région, même si A a été retiré de la copie. Compte trop plutôt que trop peu, la doctrine de la forme fermée déjà écrite pour les relevés (L11) |
| `comptes.traces` | `COUNT(*)` des actes par agent | juste ; remplacer devient deux actes au lieu d'un |
| `journal.CIBLES_PAR_REGION`, `tools/_commun.CIBLES_CORPUS`, `tools/provenance_export.py` | `cible_table`/`cible_id`/`type`, jamais la charge | juste : l'entité publiée reste `bd:bulle_locuteur/<région>`, plusieurs actes sur elle. La charge ne sort pas, son changement de forme ne se voit pas au dépôt |
| `database._sql_acte_isole_direct`, `_AUTOINCREMENT` (v30) | `cible_table` | inchangé |
| `conflit.auteur_des_champs` (sources `(bulle_locuteur, personnage_id)`, `(regions, locuteur)`) | compare `apres[champ]` à une VALEUR | à revoir avec la garde (L6, L7) : la clé `locuteur` d'un acte `regions` deviendra une liste |

### Ctrl+Z (`undo.py`, lu) — le lecteur le plus touché

`_LIENS = ("bulle_locuteur", "personnage_presence")`, commenté « region_id UNIQUE ». Tout le
code des liens suppose UN personnage par région, et le partage entre les deux tables :

- `_inverser`, branche `_LIENS` : un `lien` sans `avant` → `_retirer_lien` (supprime TOUT par
  région) ; un `lien` avec `avant` (un remplacement) ou un `delien` → `_poser_lien(avant)`.
- `_garder_lien` : `actuel` = UNE ligne ; `admis = {laisse, rendu}` ;
  `_laisse_par_un_geste_passe` lit `personnage_id` d'un seul geste.
- `_personnage_rendu` : `avant.personnage_id` — pour les nouveaux actes, la forme ne change
  pas (cf. § L'API : un ajout est un `lien` sans `avant`, un retrait un `delien`).
- `_LIENS_DE_CREATION` / `_garder_liens_de_creation` : boucle déjà sur les valeurs portées
  (`portes`), mais lève avec `d_autrui[0]` seul pour le locuteur.
- `_LIENS_INSTANTANE`, `_liens_de_l_instantane`, `_rendre_liens` : `n[cle]` est UN id.
- `_LIENS_DU_TYPE` / `_garder_liens_du_type` : la logique est DÉJÀ ensembliste
  (`_en_liste`, `actuel <= admis`) ; seule la situation (`region_attribut`) prend la branche
  « ensemble, par différence, sans garde ».
- `_TYPES_QUI_MONTRENT`, `_montre` : inchangés.
- `_DESCRIPTIONS` : « attribution d'un locuteur », « retrait d'un locuteur » — justes pour un
  ajout et un retrait.

Ordre de grandeur : `tests/test_undo.py` a 48 tests qui touchent le locuteur,
`test_undo_cloisonnement.py` 14, `test_undo_liens.py` et `test_undo_miroir.py` 6 chacun
(comptés par recherche, pas par une passe). La moitié environ s'en sert comme décor (un
`PUT …/locuteur`) ; le reste éprouve le remplacement, qui change de sens.

**Le journal est append-only, et c'est la contrainte qui décide de tout ici** : les actes
d'avant la v39 restent écrits dans leur forme — un `lien` avec `avant` est un REMPLACEMENT ;
un instantané porte `"locuteur": <id>`. Le code de la v39 doit les lire tels quels, à côté
des formes neuves. `_en_liste` (« un personnage (ou None) devient [id] (ou []), une
situation est déjà une liste ») lit déjà les deux : c'est le patron à étendre aux
instantanés, plutôt que de renommer la clé.

---

## La migration v39

### La forme

```sql
CREATE TABLE IF NOT EXISTS bulle_locuteur (
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    personnage_id  INTEGER NOT NULL REFERENCES personnages(id) ON DELETE CASCADE,
    date_creation  TEXT DEFAULT (datetime('now')),
    recopiee       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (region_id, personnage_id)
    -- v39 (ANN-6, Hugo, 2026-11-02) : une zone a ZÉRO, UN OU PLUSIEURS locuteurs, chacun
    -- une fois. Commentaire SOUS la dernière ligne (cf. `collection.projet_id`).
);
```

- **Le nom reste `bulle_locuteur`.** Le reconstruire serait l'occasion de le renommer, et
  c'est à écarter : le journal append-only le porte en `cible_table` sur tous les actes
  passés, `tools/_commun.CIBLES_CORPUS` le publie, `undo._TABLES` et
  `autorisation._CIBLES_DE_REGION` le lisent. Renommer couperait les actes d'hier de ceux de
  demain.
- **Aucune colonne d'ordre** si L1 est tranchée comme proposé ; sinon un `rang INTEGER NOT
  NULL`, et la migration pose 1 sur l'existant.
- **`recopiee` et `date_creation` restent par LIGNE**, donc par locuteur : un locuteur
  recopié reste marqué tant qu'il vit, un locuteur ajouté ensuite naît à 0 — la règle de
  `COUCHES_RECOPIEES` (« elle vit avec la ligne ») sans rien à changer.
  **Lu en passant** : aujourd'hui, REMPLACER un locuteur recopié (`set_locuteur`, UPSERT qui
  ne réécrit que `personnage_id`) garde `recopiee = 1` et la `date_creation` d'origine — le
  nouveau locuteur passe pour recopié. Le modèle à ajouts et retraits ferme ce trou par
  construction : retirer emporte la ligne marquée, ajouter en pose une neuve à 0. Non
  éprouvé par un test aujourd'hui (**supposé** : aucun test lu ne remplace un locuteur
  recopié).
- `idx_locuteur_perso` (sur `personnage_id`) est recréé ; la clé primaire couvre la lecture
  par région.
- La clé primaire composite garde le `rowid` (pas de `WITHOUT ROWID`) : rien ne le lit, et la
  forme reste celle des autres tables de liaison.

### La reconstruction

SQLite ne change pas une clé primaire par `ALTER` : la forme de la v35
(`database._tags_par_espace`, elle-même celle de la v30, `_reconstruire_avec_autoincrement`)
— table neuve tirée de `SCHEMA_SQL` par expression régulière, `PRAGMA foreign_keys = OFF`
hors transaction (la transaction en cours validée d'abord), `BEGIN IMMEDIATE`, relevé des
fautes de clés étrangères d'AVANT (`PRAGMA foreign_key_check`), lignes copiées colonne par
colonne, ancienne table détruite, neuve renommée, index recréés, fautes NEUVES → tout est
défait, `COMMIT`, clés réactivées. Les vues n'ont pas à être détruites (aucune ne lit
`bulle_locuteur`) ; les recréer par `_VIEWS_SQL` ne coûte rien et garde le patron.

- **Gardée par la forme, pas par la version** : `PRAGMA table_info(bulle_locuteur)` —
  `personnage_id` avec `pk = 2` dit que c'est fait. Idempotente, comme `_tags_par_espace`.
- Rien à dédoublonner : l'ancienne clé garantit au plus une ligne par région.
- Rien à réécrire dans le journal, ni dans les instantanés.
- **La forme de `SCHEMA_SQL` change** : une base NEUVE naît dans la forme v39 ; une base
  ancienne garde l'ancienne par `IF NOT EXISTS`, jusqu'à la reconstruction.
- **Les bases « défaites » des tests** (`_ramener_en_v28`, `_ramener_en_v29`…) : elles
  retirent des colonnes et des tables d'une base neuve ; elles hériteront de la clé
  composite d'une base neuve et ne la remettront pas d'elles-mêmes à l'ancienne. **Supposé** :
  sans effet sur leurs assertions (aucune ne lit la clé de `bulle_locuteur`) ; à vérifier par
  la suite entière.

### La vraie base de la version précédente

La règle de CLAUDE.md (Hugo, 2026-10-16) : la v39 se vérifie sur une VRAIE base v38, faite
par `tools/fabriquer_base_de_version.py <commit> tests/bases/v38-<commit>.sql`, le commit étant
la tête de `dev` avant la migration. Elle n'existe pas encore (`tests/bases/` s'arrête à
`v37-f6f53ed.sql`, lu). Le parcours pose déjà, depuis la v29, ce que la v39 doit traverser :
un locuteur posé, un locuteur REMPLACÉ (`regions[1]` : Rastapopoulos puis Tintin — un acte
`lien` avec `avant`) et un personnage détruit qui l'avait été ; depuis la v36, une copie
amorcée au cran `annotations` (un locuteur `recopiee = 1`). Un `_parcours_v38` doit ajouter :

- un changement de type qui RETIRE un locuteur (l'acte `regions` porte `locuteur` et
  `liens_vus`) ;
- la suppression d'une région qui porte un locuteur (l'instantané profond porte
  `"locuteur": <id>`) ;
- une fusion de personnages où le doublon parle dans une zone ;
- un locuteur sur un cartouche et sur un texte (ANN-6).

Et l'outil gagne une **branche sur `database.SCHEMA_VERSION >= 39`** : son parcours emploie
`PUT /api/regions/{id}/locuteur` (lu) et dépend du REMPLACEMENT pour la séquence
Rastapopoulos → Tintin ; « chaque fichier de `tests/bases/` doit rester refabricable »
(sa docstring). Le test de la migration (`tests/test_migration_v39.py`, patron de
`test_migration_v38.py`) charge la v38, migre, et vérifie : chaque ligne là, avec sa date et
sa marque ; la clé composite ; un second locuteur s'ajoute ; le Ctrl+Z des actes d'avant
(remplacement, retrait par changement de type, suppression rétablie) rend ce qu'il rendait.

---

## L'API (ce que le serveur doit permettre)

Proposé (L8), la forme la plus fermée qui sert les deux écrans :

- **`GET /api/regions/{id}/locuteurs`** → `{"locuteurs": [{id, nom, serie}, …]}`, dans
  l'ordre de L1. Accesseur gardé en lecture, comme aujourd'hui.
- **`POST /api/regions/{id}/locuteurs`** `{personnage_id}` → AJOUTE un locuteur, rend la
  liste entière. Toutes les gardes de `set_locuteur`, dans le même ordre (verrou, accesseur en
  écriture, 422 de type — l'ordre est tenu par
  `test_poser_un_locuteur_sans_ecrire_la_region_repond_introuvable` —, personnage visible, rive
  du bac à sable). Déjà présent : 200, rien d'écrit, rien de journalisé. Sinon un acte `lien`
  **sans `avant`**, `apres` = `{"personnage_id": X}` — la forme exacte d'aujourd'hui pour une
  première attribution, si bien que `undo._personnage_rendu`, `conflit.auteur_des_champs`,
  `autorisation._sources_du_travail` et la provenance la lisent sans changer.
- **`DELETE /api/regions/{id}/locuteurs/{personnage_id}`** → RETIRE CE locuteur, 204. Absent :
  204 sans acte (le retrait commute, L6). Un acte `delien`, `avant` = `{"personnage_id": X}` —
  la forme d'aujourd'hui.
- **Les routes au singulier** (`GET/PUT/DELETE …/locuteur`) : gardées telles quelles pendant
  la transition (le PUT REMPLACE tous les locuteurs par un, le DELETE les retire tous, chacun
  journalisant un acte par locuteur touché), pour que l'écran marche entre deux commits ;
  retirées avec l'écran (commit 4). Elles ne servent plus qu'à `tools/semer_demo.py` et au
  parcours des bases d'avant la v39.
- **Remplacer** n'est plus un geste du serveur. Un remplacement à l'écran (s'il existe sur la
  maquette) = un `DELETE` puis un `POST`, deux actes, deux Ctrl+Z.
- **La valeur vue de CONC-4** (L6) : proposé, AUCUNE sur ces deux routes. Ajouter A et
  ajouter B commutent ; retirer A deux fois ne perd rien ; chaque réponse rend (ou fait relire)
  la liste entière, et l'écran se redessine d'elle : ce que l'autre a fait se VOIT. C'est la
  règle des tags (« leurs différences commutent », § Deux écrans) appliquée à un ensemble de
  personnages. Le scénario mesuré le 2026-10-25 (« Bob pose Yann, la base garde Yann, aucun
  écran n'en dit rien ») n'existe plus : la base garde Zed ET Yann, et chaque écran le montre
  au geste suivant ou à « ⟳ Actualiser ». `personnage_vu` reste pour la présence.
- **Le changement de type** : `retirer_liens_caches` rend `{"locuteur": [ids]}` (une liste,
  rangée dans `avant` sous la MÊME clé), `liens_vus` de même, et la réponse rend
  `locuteurs_retires` (une liste) — ou garde `locuteur_retire` en ne le posant qu'à un seul ;
  à trancher avec l'écran.
- **La fusion** : `INSERT OR IGNORE INTO bulle_locuteur (region_id, personnage_id,
  date_creation, recopiee) SELECT region_id, cible, date_creation, recopiee FROM
  bulle_locuteur WHERE personnage_id = doublon`, puis le `DELETE` du doublon emporte ses lignes
  par cascade. Une zone où parlaient le doublon ET la cible garde UN locuteur — la fiche
  « comptée une fois » de la case.
- **Plafond** : aucun (L13).

### Ctrl+Z, dans ce modèle

Proposé (L7) : un geste = un locuteur. L'inverse d'un ajout retire CE personnage ; l'inverse
d'un retrait le remet ; l'ancien remplacement (un `lien` avec `avant`, actes d'avant la v39)
s'inverse en retirant le nouveau et en remettant l'ancien. La garde se fait **par
personnage** : refus nommé (le 409 de CONC-3, « Passer ce geste ») si un AUTRE a touché CE
personnage sur cette zone depuis l'acte — `conflit.auteur_des_champs` sait déjà filtrer par
`objet=(clé, valeur)` (ANN-7, pour les relevés d'une même région) ; ici `("personnage_id",
X)`. Les autres locuteurs de la zone ne bougent pas, quel qu'en soit l'auteur — comme les
tags (`_inverser_annotation`, par différence). L'acte dont le personnage a été supprimé
depuis : rien à retirer, l'acte est passé (seconde phrase d'AUTH-14), comme aujourd'hui un
lien vers un personnage disparu.

Les sites à changer : `_retirer_lien` et `_poser_lien` prennent le personnage (et se
SÉPARENT de la présence, qui garde l'UPSERT) ; `_garder_lien` compare un ensemble ;
`_laisse_par_un_geste_passe` filtre par personnage ; `_rendre_liens` et
`_liens_de_l_instantane` lisent `_en_liste(n["locuteur"])` ; `_garder_liens_du_type` range le
locuteur dans la branche « ensemble, par différence » (L7) ; `_garder_liens_de_creation`
rend la liste dans `valeur_actuelle` et nomme l'auteur du premier locuteur d'autrui. La
description du geste ne change pas.

---

## L'écran (ce que le serveur doit permettre, sans trancher la forme)

La forme se tranche sur maquette, en séance dédiée (la règle de la mémoire « forme sur
maquettes interactives »). Ce qu'elle devra résoudre, et que le serveur rend possible :

- **Le champ « Locuteur »** devient une LISTE de puces, chacune avec son ×, et le champ
  « Attribuer un personnage… » AJOUTE (le module `champ-personnage.js` ne change pas : seul
  `onPick` de chaque hôte passe du PUT au POST). Atelier (`renderLocuteur`) et Contexte de la
  page Annotation (`montrerLocuteur`) ; la hauteur de la ligne du Contexte doit rester
  stable pendant le travail (« écran stable, sans phrases »).
- **Le profil et l'alignement d'autorité** de l'Atelier sont aujourd'hui CEUX du locuteur
  (`persoAttrWidget`, `locAlignWidget`). Avec deux locuteurs : celui de la puce qu'on
  choisit ? Une question d'écran (L10), aucune route ne change.
- **Le bandeau de conflit** du locuteur disparaît si L6 est tranchée comme proposé ; il reste
  pour la présence. `RETENUES`, `S.conflit.saisie` et le lieu `locuteur` de `conflit.js` se
  simplifient d'autant — ou se généralisent si L6 garde une valeur vue.
- **« Locuteur « X » retiré »** (`messageRetraits`) nomme une liste.
- **La concordance** affiche `locuteurs` (« A · B ») au lieu de `locuteur`.
- **Petites largeurs et police agrandie** : deux noms longs dans le Contexte, à 320 px.

---

## La grille et le registre

La grille des linguistes pose l'entrée « locuteur » — niveau 1, à variantes (personnage
identifié, non identifié, collectif, narrateur·ice), sur TOUTE la zone (une entrée peut
déclarer sa cible, `docs/grilles-et-releves.md` § 4) — désormais plusieurs fois par zone
(cardinalité `plusieurs` : `routes/releves.py` ne refuse un second relevé que sous `une`,
`_existant_une`, lu). Le registre, lui, nomme QUI. **Rien ne relie aujourd'hui un relevé
« personnage identifié » à une fiche du registre** : un relevé porte une variante, des
qualificatifs, une précision (texte) et un lien vers une RÉGION du même album
(`lien_region_id`), jamais un personnage ; la cible `entite` attend l'étage de projet des
personnages (G3, tranche 4 de `COL-3`) : l'import l'accepte, aucun relevé ne s'y pose.

Trois manières de les relier, pour mémoire (L11) :

1. **Aucune, dans ce chantier** — deux couches qui se répondent par l'humain : la grille dit
   COMBIEN et de quelle SORTE, le registre dit QUI. Coût nul. Rien ne signale une zone qui
   porte deux relevés « identifié » et un seul locuteur.
2. **Un signal de cohérence, sans lien** — une cause de plus dans « à revoir » de la vue
   `releves_effectifs` (« 2 relevés « personnage identifié », 1 locuteur nommé »). Coût
   estimé (**supposé**) : une demi-journée, mais il faut que la vue sache QUELLE entrée et
   QUELLE variante veulent dire « identifié » — une convention sur une grille qui n'est pas
   dans le code (« rien d'une grille n'est dans le code ») : il faudrait une colonne de plus
   au tableur. C'est là que le coût se cache.
3. **Le lien porté par le relevé** — une attente de plus (`attend: personnage`, comme une
   précision ou un lien), un `releve.personnage_id`, l'état « à compléter » s'il manque, le
   `vu` de CONC-3, Ctrl+Z, la recopie (E6), le décompte, le travail d'autrui. Coût estimé
   (**supposé**) : deux à trois journées. Et deux sources de vérité pour la même chose —
   `bulle_locuteur` et `releve.personnage_id` — qui divergeront dès qu'un geste n'écrit que
   l'une. Ce serait l'endroit, en revanche, où G3 se poserait naturellement.

Proposé : la première, la question rouverte par G3 (tranche 4 de `COL-3`), avec le renvoi
posé chez elle.

---

## Le découpage en commits

0. **La vraie base v38** : `_parcours_v38` et la branche `>= 39` dans
   `tools/fabriquer_base_de_version.py`, `tests/bases/v38-<sha>.sql` fabriquée sur la tête de
   `dev`. Aucun comportement.
1. **La v39 et tous les ÉCRIVAINS** : la migration et son test ; les routes au pluriel
   (`POST`, `DELETE …/{personnage_id}`, `GET`) et les singulières ramenées au « remplacer
   tous » ; la fusion ; `liens_vus`, `retirer_liens_caches`, `retirer_locuteur_muet` et
   l'outil de rattrapage ; l'instantané profond en liste ; `empreinte.empreintes` ; tout
   Ctrl+Z (lecture des deux formes du journal, garde par personnage) ; `conflit.
   auteur_des_champs` sur une clé à liste. Dans UN commit : la clé composite casse
   `ON CONFLICT(region_id)` à l'instant de la migration, et « une recette migrée entre deux
   commits ne repasserait pas une étape ajoutée ensuite » (la leçon de la 3c).
2. **Les LECTEURS et les SORTIES** : la concordance sans doublon (les locuteurs agrégés par
   ligne, lus à part comme `_joindre_tags`, une requête pour tout le jeu) ; le croisement à
   jointure du locuteur PARTAGÉE entre deux axes qui passent par lui ; `metadonnees_collection`
   (JSON `locuteurs` en liste, CSV joint par `|`, XLSX), `iiif_manifest` (un corps par
   locuteur), `description_collection` (L12). Un fichier de test au patron de
   `tests/test_locuteur_zones_de_texte.py` : **une zone à deux locuteurs, une bulle témoin à
   un, et pour chaque sortie « les deux y sont, et la zone une fois »**, un test par sortie,
   chacun joué contre SON mutant.
3. **L'écran**, après la maquette : Atelier, Contexte de la page Annotation,
   `lib/annotation.js`, `lib/conflit.js`, la concordance de l'Exploration ; les e2e.
4. **Le retrait des routes au singulier**, `tools/semer_demo.py` ; la documentation —
   `CLAUDE.md` (§ Deux écrans, § Annulation, la ligne `/annotation` du tableau),
   `docs/personnages-et-attribution.md` (§ 6 dit « une bulle a au plus un locuteur »),
   `docs/undo.md`, `docs/dictionnaire-metadonnees.md`, `docs/export-metadonnees.md` (le
   format du dépôt change, daté), `docs/modele-et-droits.md`, `docs/guide-utilisateur.md`.

Chaque commit de code cite `ANN-6`. Rien ne part vers `main` avant le commit 3 : entre 1 et
3, l'écran ne montre que le premier locuteur d'une zone qui en a deux (la route singulière
rend le premier).

**Estimation** (supposée, au rythme de la 3c) : commit 0, une demi-journée ; commit 1, deux
journées et demie (Ctrl+Z en est la moitié : environ 75 tests de `test_undo*.py` à relire, une
partie à réécrire) ; commit 2, une journée ; commit 3, une journée et demie à deux après la
maquette ; commit 4, une demi-journée ; mutants et relecture des sorties, une journée.
**Environ sept journées de session**, plus la séance de maquette. Ordre de grandeur des tests
qui touchent le locuteur : environ 190 fonctions Python dans 31 fichiers, et 7 fichiers
`tests/js/` (comptés par recherche) ; beaucoup ne s'en servent que comme décor.

**Relecture croisée** : sur les SORTIES (le commit 2 change le format du dépôt) — « réservée
aux gardes et à ce qui sort » ; `autorisation.py` n'est pas touché.

### Ce qui doit être éprouvé par mutants

- la migration : chaque ligne copiée avec sa date et sa marque ; la clé composite ; une faute
  de clé étrangère NEUVE défait tout ; idempotente sur une base déjà migrée ;
- `empreinte.empreintes` : revenir au `dict` → un second locuteur ne change plus l'empreinte ;
- `snapshot_region_profond` et `liens_vus` : revenir au `fetchone` → Ctrl+Z d'une suppression
  ou d'un changement de type ne rend qu'un locuteur ;
- `undo._retirer_lien` qui retire tout → l'annulation d'un ajout emporte l'autre locuteur ;
- la garde par personnage : sans le filtre `objet`, le geste d'un autre sur B bloque le
  Ctrl+Z de A (refus faux) — et sans garde, l'annulation emporte le A qu'un autre a remis ;
- un ancien acte de remplacement (journal v38) : retirer le nouveau ET remettre l'ancien ;
- la fusion : une zone où parlent doublon et cible → une ligne, pas un 500 ;
- la concordance : remettre le `LEFT JOIN` → un token sort deux fois ;
- le croisement : deux jointures indépendantes → la cellule croisée de A et du profil de B
  n'est plus vide ;
- `metadonnees_collection` : revenir au `dict` → un locuteur manque au dépôt ;
- `retirer_locuteurs_muets.py` : chaque locuteur retiré a son `delien` ;
- la présence reste à UN : un second `PUT …/personnage` remplace toujours.

### Les passes de QA que le changement périme

Rédigées ou réécrites, jamais cochées par qui les écrit, relues ensemble avant d'être rendues :

- **`conflit-du-locuteur`** — RÉÉCRITE : ses zones « Le locuteur posé de part et d'autre »
  éprouvent le refus d'un locuteur posé sur une valeur périmée, qui n'existe plus si L6 est
  tranchée comme proposé ; « ⟳ Actualiser » et le personnage montré restent ;
- **`lot-1-suite`** — ses cases « remplacer le locuteur par « Yann QA » » puis Ctrl+Z refusé :
  le remplacement devient retrait + ajout ;
- **`lot-1`** — les cases « Zed QA » (le locuteur qui part avec le type et revient au Ctrl+Z) :
  à relire, elles tiennent si le changement de type rend la liste ;
- **`page-annotation-jalon-3`** — « une puce « Abdou » avec son × remplace le « — » » et le
  Ctrl+Z « attribution d'un locuteur » : à relire contre la maquette ;
- **`page-annotation-correctifs-j3`** — la case « rien de vide entre la ligne Locuteur et la
  ligne Note » : à rejouer avec deux puces ;
- une passe **neuve**, « deux locuteurs » : Atelier et Contexte (ajouter, retirer l'un, Ctrl+Z
  de chacun, deux comptes), concordance et croisement de l'Exploration, une zone à deux
  locuteurs dans l'export du dépôt ; `petites-largeurs` et `preference-de-police` sur la liste.

---

## Les questions à Hugo

| | Question | Proposé (le plus simple, le plus fermé) |
|---|---|---|
| L1 | L'ordre des locuteurs d'une zone a-t-il un sens (qui parle d'abord) ? | Non : aucun ordre stocké ; l'affichage les range par nom. Un ordre qu'on pourrait lire comme « qui parle d'abord » serait une affirmation que personne n'a faite |
| L2 | Un comptage « par locuteur » compte-t-il la zone une fois par locuteur ? | Oui : dans `nb_bulles`, le filtre par personnage, la comparaison A/B et l'axe `locuteur` du croisement, la zone compte pour CHACUN — la règle « fan-out » des tags, déjà écrite ; le total du croisement dépasse alors le nombre de tokens, et l'écran le dit comme pour les tags |
| L3 | La concordance : une ligne par token, ses locuteurs réunis ? | Oui : « A · B » sur la ligne, jamais deux lignes ; le CSV porte `locuteurs` joints par `|` |
| L4 | Deux valeurs de profil filtrées ensemble (« enfant » ET « femme ») : le même locuteur, ou chacune par l'un d'eux ? | Chacune par l'un d'eux, comme le calcul le fait déjà (un `EXISTS` par valeur) ; écrit dans la docstring et le guide. Exiger le même locuteur est une règle neuve, à ouvrir si les linguistes la demandent |
| L5 | Le croisement locuteur × profil (ou profil × profil) | Corrélé au MÊME locuteur — ce n'est pas un choix : le produit cartésien est faux. Posé ici pour que la correction soit vue |
| L6 | La garde de CONC-4 sur le locuteur | Aucune valeur vue sur l'ajout et le retrait : ils commutent, comme les tags ; chaque réponse rend la liste, l'écran se redessine d'elle. La présence garde la sienne. Alternative : une liste vue, 409 dès qu'elle diffère — plus fermée, mais elle refuserait des gestes qui ne perdent rien |
| L7 | Que fait Ctrl+Z ? | Un geste = un locuteur : l'annulation défait celui-là seul ; refus nommé (« Passer ce geste ») si un autre a touché CE personnage sur la zone depuis ; les autres locuteurs ne bougent pas. Les anciens remplacements s'annulent en deux temps sous la même garde. Le changement de type rend ses locuteurs par différence |
| L8 | Les routes | Au pluriel (`GET`, `POST`, `DELETE …/locuteurs/{personnage_id}`) ; les routes au singulier gardées pendant la transition, puis retirées |
| L9 | Une boîte personnage peut-elle MONTRER plusieurs personnages ? | Non : `personnage_presence` reste à un ; plusieurs personnages, plusieurs boîtes. Le code partagé des liens (`undo._LIENS`) se sépare |
| L10 | Le profil et l'alignement d'autorité de l'Atelier, avec deux locuteurs | À la maquette : le serveur ne change pas (le profil est celui d'une fiche) |
| L11 | Le lien entre un relevé « personnage identifié » et une fiche du registre ; et la granularité de `_SQL_COUCHE_VIT` | Aucun lien dans ce chantier, la question rouverte par G3 ; `_SQL_COUCHE_VIT` reste par région (compte trop plutôt que trop peu) |
| L12 | Le dépôt : `locuteur` (chaîne) devient `locuteurs` (liste) ? La fiche du corpus compte-t-elle les zones attribuées ? | Oui, la clé au pluriel, une liste, le changement daté dans `docs/export-metadonnees.md` — garder la clé au singulier avec une chaîne jointe mentirait sur la forme ; et `description_collection` ajoute le nombre de zones à côté de celui des liens |
| L13 | Un plafond de locuteurs par zone ? | Aucun |

---

## Ce que cette note n'a pas pu établir

- **Combien de zones auront plusieurs locuteurs**, ni le volume actuel de `bulle_locuteur` en
  production : aucune base n'a été ouverte. Les ordres de grandeur ci-dessus sont de
  construction (une zone à N locuteurs = N lignes ; un token d'une telle zone sort N fois de
  la concordance actuelle), pas mesurés.
- **L'exception exacte levée par `ON CONFLICT(region_id)`** sur la clé composite : supposée
  `sqlite3.OperationalError` d'après le comportement connu de SQLite, non jouée ici. La
  conclusion (un 500, et un Ctrl+Z qui ne passe pas l'acte) en dépend ; le commit 1 la rend
  sans objet en réécrivant les trois requêtes.
- **Que les bases « défaites » des tests** ne lisent pas la clé de `bulle_locuteur` : supposé
  par lecture de leurs noms, à vérifier par la suite entière au commit 1.
- **Que remplacer un locuteur recopié le laisse marqué recopié** : lu dans l'UPSERT de
  `set_locuteur`, non éprouvé ; aucun test lu ne le joue. Sans objet après la v39.
- **Le nombre de tests qui changent de sort** : compté par recherche (fonctions qui
  mentionnent « locuteur »), pas par une passe ; le commit 1 le mesure par la suite entière.
- **Ce que la grille des linguistes appelle « personnage identifié »** dans le brouillon
  (clé d'entrée, clé de variante) : la grille n'est pas dans le dépôt, et l'option 2 de § La
  grille et le registre en dépend.
- **La forme d'écran** : rien ici ne la tranche ; L1, L6 et L10 se rejouent sur la maquette.
