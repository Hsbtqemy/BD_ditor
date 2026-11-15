# ANN-7 — la montée de version d'une grille fermée, et « Passer dans une grille… » : cadrage

Rendu le 2026-11-15, sur `dev` à `e8451a6` (schéma **40**). Rien n'est codé. Comme les
cadrages précédents : ce qui est marqué **lu** a été lu dans le code à ce commit ; **mesuré**
sort d'un test lancé ; **hypothèse** ne l'a pas été, et dit ce qui trancherait. Les questions
qui restent à Hugo sont numérotées **M1 à M7**, en fin de note — la suite de G (tranche 1),
H (tranche 2), I (tranche 3) et J (mode libre).

**Pourquoi maintenant.** Hugo a décidé le 2026-11-15 (`pilotage/ANN-6.md`, zone « La grille
des linguistes en production ») que la grille des linguistes, relue le 2026-11-17, entrera dans
LingApp FERMÉE, en v1 publiée. Sa première correction après des relevés sera une v2, et
activer cette v2 répond aujourd'hui un 409 : la montée de version doit exister avant (case « La
montée de version existe avant le premier changement de la grille relue sous des relevés »).
Elle sort donc de « Peut attendre », où la fiche d'`ANN-7` la rangeait (zone « La séance de
conception »). Le geste « Passer dans une grille… » du mode libre (J8) bute sur la même
question : vers quelle version d'une grille fermée, et ce que devient un relevé qui y arrive.

Le dépôt est public : aucune grille réelle n'est citée ici. Les exemples sont fictifs.

---

## Ce qui est déjà tranché, et que cette note ne rediscute pas

- **Une version est un instantané complet, désigné par `cle`** (Hugo, 2026-10-14 ; note du
  modèle §6). Le cadrage de la tranche 1 en tirait que la montée serait « une affaire de
  `version_id` et de bilan » (R2).
- **Un projet reste sur sa version et choisit quand passer à la suivante** — « il voit qu'une
  version neuve existe, lit son bilan pour SES relevés, et décide ; sans son accord, rien ne
  bouge » (Hugo, 2026-10-22, `ANN-7`, zone « Le catalogue et le partage »). Le bilan est donc
  celui des relevés du projet, et la montée est un geste du projet.
- **L'effet de chaque changement entre deux versions** (`ANN-7`, case « Une version en usage
  ne se modifie pas en place », 2026-10-14) : renommer ou retoucher une définition n'abîme
  rien ; déplacer change les comptes par rubrique, passé compris ; une entrée employée ne se
  supprime pas, elle devient « retirée » ; fusionner reporte les relevés, tracé ; scinder met
  les relevés « à revoir » ; changer de forme met les relevés incomplets « à compléter ».
- **« Fusionner dans… » d'une grille fermée attend la montée** (choix 1 des routes
  d'écriture, Hugo, 2026-11-04) : dans le brouillon d'une fermée, une entrée employée ne peut
  que se retirer (`e52d70c`, gardé par Hugo le même soir).
- **Une variante ou une case employée ne se supprime pas, même dans le brouillon d'une
  fermée** (choix 3, 2026-11-04) ; et **la forme et la liste d'une entrée employée restent
  modifiables dans ce brouillon** (choix 4 du formulaire, confirmé le 2026-11-04).
- **Une région qui change de type : ses relevés passent « à revoir »** (G8 a, 2026-10-25).
- **Les relevés de la v1 se lisent sur la v2** après la montée — c'est l'attendu de la case
  d'`ANN-6`. Ils PASSENT dans la nouvelle version ; ils ne restent pas en lecture sur
  l'ancienne (cf. « Le principe »).
- **J8 est tranché dans ses règles** (Hugo, 2026-11-06, « toutes comme le cadrage les
  propose ») : une tranche à part, vers la version ACTIVE de la grille d'arrivée, les relevés
  qui ne conviennent pas restent, un bilan relevé par relevé, pas de Ctrl+Z du geste, à qui
  gère le projet (`docs/ann7-mode-libre-cadrage.md`, section « Structurer »).
- **Un acte de fusion n'est ni un travail sur l'album, ni ce qui fait d'un relevé « celui d'un
  autre »** (`4f0561a`, les trois choix confirmés par Hugo le 2026-11-15).
- **La grille d'essai** de LingApp est OUVERTE, et la grille relue entre comme une grille
  NEUVE ; « ses relevés restent sur elle » (case d'`ANN-6`, 2026-11-15). La montée ne la
  concerne pas : une grille ouverte n'a qu'une version.

---

## 1. Ce qui existe déjà (lu)

### Où vit le refus

`grille_import.activer` (le cœur que partagent la route
`PUT /api/projets/{id}/grilles/{gid}/activation` et `tools/importer_grille.py --activer`) :
après les refus du jeu, du catalogue absent et d'une grille retirée, il compare la version
demandée à l'activation en place, puis

```
SELECT 1 FROM releve WHERE grille_id = ? AND version_id <> ? LIMIT 1
```

et lève « Des relevés sont posés avec cette grille : changer de version est une montée de
version, qui n'existe pas encore. Rien n'est changé. » La même garde tient la porte de
derrière (désactiver, puis réactiver dans l'autre version) : `tests/test_grilles.py::
test_changer_la_version_d_une_activation_qui_porte_des_releves_est_refuse` (**mesuré** : vert
à `e8451a6`).

**Ce qu'il en découle (lu, déduit)** : tous les relevés d'une grille sont aujourd'hui dans UNE
seule version — celle de son activation, ou de sa dernière activation si on l'a désactivée.
Et ils vivent tous dans les albums de SON projet : un projet n'active que ses grilles (le
catalogue n'existe pas), une copie n'emporte un relevé que si sa grille est active à l'arrivée
(`database._copier_les_releves`), et une copie gardée au fonds garde son projet écrit
(`albums.projet_id`).

### Ce que portent un relevé, un doute, une passe

- **Le relevé** (`releve`) porte `grille_id`, `version_id`, `entree_cle`, `variante_cle`, ses
  qualificatifs (`releve_qualificatif`, par `cle`), sa précision, son lien, son passage
  (`releve_mot`), et `une` — la cardinalité FIGÉE à la pose, que lit l'index unique partiel
  `idx_releve_une`. Il ne s'ÉCRIT que si la grille est active dans SA version :
  `routes/releves.releve_a_ecrire` refuse sinon (409, « ses relevés se lisent, ils ne
  s'écrivent plus »), et `vues` rend `modifiable: false`. C'est pourquoi des relevés laissés
  sur la vN après la montée deviendraient tous en lecture seule.
- **La pose** exige que la version envoyée soit celle de l'activation (409 « votre écran
  montre la version N. Rechargez la page. »).
- **Le doute** (`doute`, `doute_message`) ne porte aucune version : il suit son relevé
  (`doute.releve_id`).
- **La passe** (`passe`) porte `version_id`, écrit à la marque, « pour que la montée de
  version sache quelles zones rouvrir » (commentaire du schéma). Mais elle est UNIQUE par
  zone, grille et rubrique, quelle que soit la version (`idx_passe_zone`), et l'écran la lit
  sans regarder sa version (`static/lib/annotation.js`, `passesSurLaCible`, `terminee`).
  Marquer une zone déjà marquée rend la passe existante sans toucher sa version.

### Ce que l'état dérivé sait dire, et ce qu'il ne sait pas

La vue `releves_effectifs` joint chaque relevé à l'entrée de SA version, par `cle`. Elle dit
déjà, sans rien écrire :

- **à revoir** — une entrée absente de la version, ou RETIRÉE (`entree_absente`) ; un type de
  région qui ne convient plus à la cible effective de l'entrée (`type_change`) ; un mot perdu,
  un texte changé, un lien perdu ;
- **à compléter** — une précision ou un lien attendus et absents.

Elle ne dit PAS (lu, dans la vue) :

- une **variante** qui n'existe plus dans la version, ou qui n'a plus de place (l'entrée n'est
  plus à variantes) ;
- une **variante manquante** (l'entrée est devenue à variantes) ;
- un **qualificatif** hors de la liste de l'entrée, ou une entrée qui n'est plus à
  qualificatifs ;
- un changement de **sorte de pose** : un relevé de zone entière sur une bulle dont l'entrée
  vise désormais des mots reste « normal » (la règle `mots` ne regarde que le type de la
  région) ; un relevé de PLANCHE dont l'entrée vise désormais une zone aussi (`type_change`
  exige une région).

Ces causes n'existent pas aujourd'hui sur une grille fermée, puisque la version ne change pas
sous des relevés. Elles naissent avec la montée — et la dernière existe déjà ailleurs (cf.
« Vu en passant »).

### Ce que la comparaison de deux versions sait déjà dire

`grille_import.bilan(conn, grille_id, avant, apres)` compare deux contenus par `cle` et rend
`nes`, `renommes`, `retouches` (définition, structure, piège, exemples), `deplaces` (rubrique),
`changes` (forme, cible, cardinalité, liste, précision, lien, « retirée », et « Porte sur »
de la version) et `disparus`, chaque disparu avec le nombre de relevés posés sur lui. C'est le
bilan de l'IMPORT : il compare le fichier à la dernière version PUBLIÉE, pas à celle que le
projet a active.

Autour de lui, déjà écrits pour une grille OUVERTE et réemployables :
`_vers_possibles` (où des relevés peuvent être fusionnés sans rien perdre), `vers_sans_double`
et `_fusion_en_double` (une fusion qui poserait deux fois une entrée « une seule fois », ou la
même valeur deux fois), `_cibles_en_double` (une entrée qui passerait à « une » alors qu'une
cible en porte deux — la faute `cardinalite_contredite`), `reporter_cardinalites` (le drapeau
`une` suit la cardinalité), `_fusionner` et `journaliser_fusion` (le report, et un acte
`ACTE_FUSION` par relevé), et le verdict `a_repondre` de l'import, avec « retirer » /
« fusionner dans… ».

### Ce que lisent les autres

- **Ctrl+Z** (`undo._activation_du_releve`) : un acte sur un relevé ne s'annule que si la
  grille est active DANS LA VERSION de l'instantané. Défaire une pose ou une retouche lit le
  relevé ACTUEL ; rétablir un relevé retiré, ou les relevés d'une région supprimée
  (`_rendre_releves`), lit la version de l'INSTANTANÉ.
- **L'empreinte** (`empreinte.py`) : celle des relevés porte `version_id`, celle des plans
  (`empreintes_plans`) ne porte que les grilles OUVERTES.
- **La copie amorcée** au cran `annotations` garde la version du relevé source, « quelle que
  soit sa version ».
- **La Recherche** reconnaît une entrée par sa `cle`, quelle que soit la version du relevé
  (`tests/test_recherche_releves.py::test_une_entree_se_reconnait_par_sa_cle_quelle_que_soit_la_version`).
  L'index plein texte ne porte que les libellés des grilles OUVERTES (J6).

---

## 2. Le principe

**Monter, c'est faire passer les relevés du projet de la vN à la vM** (M > N, une version
PUBLIÉE ; sauter une version est permis, la comparaison se fait entre les deux). Un relevé
garde toutes ses VALEURS — variante, qualificatifs, précision, lien, passage, auteur, dates :
la montée ne réécrit que sa version, son drapeau `une`, et son entrée quand on la fusionne.
Ce qui ne convient plus à la vM se DIT par l'état dérivé, au lieu d'être corrigé en silence ;
la personne qui a posé le relevé le reprend, ou un doute le fait reprendre.

Trois raisons à ce choix plutôt qu'à laisser les relevés en vN :

1. seule la version active s'écrit (`releve_a_ecrire`) : laissés en vN, tous les relevés
   d'une campagne deviendraient intouchables d'un coup ;
2. l'invariant d'aujourd'hui — tous les relevés d'une grille dans une version — tient encore
   après, et tout ce qui le suppose (le réimport, les comptes, la fusion) reste juste ;
3. un relevé qui garde ses valeurs garde ce que CONC-3 compare : aucun écran ouvert ne voit
   une valeur changer sous lui.

**Le périmètre est le projet**, écrit dès maintenant : les relevés dont l'album est du projet
(`database.sql_projet_d_album`, copies gardées au fonds comprises). Aujourd'hui c'est la
grille entière ; le jour du catalogue, deux projets tiendront la même grille dans deux
versions, et une montée écrite « par grille » déplacerait les relevés de l'autre.

---

## 3. Ce qui arrive à chaque relevé, cas par cas

La règle ne lit que les deux plans (vN, vM) et le relevé. **Passe** : le relevé passe en vM,
« normal » s'il l'était. **À revoir / à compléter** : il passe en vM, et la vue le dit, avec sa
cause en mots. **À décider** : la montée attend une réponse. **Refus** : la montée ne se fait
pas tant que la cause reste.

| Ce qui change de vN à vM | Ce qui arrive au relevé | Cause, en mots |
|---|---|---|
| Rien sur l'entrée | passe | — |
| Une coquille (définition, exemple, piège) | passe — une coquille se corrige d'ailleurs sans version | — |
| L'entrée est renommée (même `cle`) | passe | — |
| L'entrée change de rubrique | passe ; les comptes par rubrique suivent, passé compris | — |
| Une variante ou une case est renommée | passe | — |
| Une variante ou une case est AJOUTÉE | passe | — |
| L'entrée est RETIRÉE (elle était employée) | **à décider** : la laisser retirée — le relevé passe, à revoir — ou « fusionner dans… » une entrée de la vM (M2) | « l'entrée a été retirée de la grille » (lu, `entree_absente`) |
| L'entrée est fusionnée dans une autre | le relevé passe à l'entrée d'arrivée, aux règles de la fusion d'une ouverte (`_vers_possibles`, `_fusion_en_double`), un acte `fusion` au journal | — |
| L'entrée a disparu de la vM (cf. « Vu en passant » : une publication ne le revérifie pas) | à revoir, comme une entrée retirée | « l'entrée n'existe plus dans cette version » |
| Une variante employée a disparu de la vM (même voie) | à revoir | « cette valeur n'existe plus » (cause neuve) |
| Une case cochée a disparu de la vM (même voie) | à revoir | « une case cochée n'existe plus » (cause neuve) |
| Simple → à variantes | à compléter (tranché, note du modèle §6) | « choisissez une valeur » (cause neuve) |
| À variantes → autre forme | impossible tant qu'un relevé porte une variante : les variantes employées ne se suppriment pas (lu) | — |
| À qualificatifs → simple ou à variantes | à revoir : ses cases cochées n'ont plus de place | « l'entrée ne prend plus de cases » (cause neuve) |
| Simple → à qualificatifs | passe : zéro case cochée est un relevé valide | — |
| La liste de l'entrée change | à revoir si une case cochée n'est pas dans la nouvelle liste ; sinon passe | « une case cochée n'est pas dans la liste » (cause neuve) |
| Cardinalité « une » → « plusieurs » | passe ; `une` repasse à 0 (`reporter_cardinalites`) | — |
| Cardinalité « plusieurs » → « une », sans cible en double | passe ; `une` passe à 1 | — |
| Cardinalité « plusieurs » → « une », une cible en porte deux | **refus**, cible par cible, comme pour une grille ouverte (M1) | « deux relevés là où l'entrée n'en veut plus qu'un » |
| « Porte sur » change, le type de la région ne convient plus | à revoir (G8, déjà dérivé) | « l'entrée ne se pose plus sur ce type de zone » (lu, `type_change`) |
| « Porte sur » passe des mots à la zone, ou l'inverse | à revoir | « l'entrée se pose maintenant sur des mots » / « … sur toute la zone » (cause neuve) |
| « Porte sur » passe de la planche à une zone, ou l'inverse | à revoir | « l'entrée ne se pose plus sur la planche » (cause neuve) |
| Une précision devient attendue | à compléter (déjà dérivé) | « précision attendue » (lu) |
| Un lien devient attendu | à compléter (déjà dérivé) | « lien attendu » (lu) |
| La précision ou le lien ne sont plus demandés | passe ; la valeur reste sur le relevé, lisible | — |
| Une entrée NAÎT | aucun relevé n'est touché ; les passes, oui (§5) | — |
| On SCINDE une entrée | à revoir (tranché, note du modèle §6) — par quelle voie : M3 | selon M3 |

**Les causes neuves se DÉRIVENT** (G2 tient) : variante absente, variante sans place,
variante manquante, case absente, case sans place, sorte de pose changée. Elles s'ajoutent à
`releves_effectifs` et à `routes/releves._CAUSES` ; la vue se recrée au démarrage, **aucune
migration**. Elles valent hors de la montée aussi — c'est ce qui ferme la faille vue sur la
grille de travail (« Vu en passant »). La règle de la montée et la vue doivent dire la même
chose : un test les accorde, relevé par relevé, comme `tests/test_releves.py` accorde déjà la
règle du type et son écriture SQL.

---

## 4. Le bilan avant d'activer

**Ce que voit qui monte**, en données, sur le patron du bilan de l'import (un verdict, des
nombres, ce qui attend) — `GET /api/projets/{id}/grilles/{gid}/montee?version=M` :

- en tête, une phrase : « 412 relevés passent en version 3. 9 seront à revoir, 4 à compléter.
  2 entrées retirées attendent votre réponse. » ;
- ce qui change dans le plan, de la vN active à la vM — le `bilan()` d'aujourd'hui, appelé
  avec la version ACTIVE pour `avant` et non la dernière publiée ;
- les relevés, comptés par issue et par cause — « passent », « à revoir : la valeur n'existe
  plus (3) », « à compléter : choisissez une valeur (4) » — et, pour chaque cause, les zones
  concernées, cliquables, bornées aux albums que l'appelant lit (le responsable les lit tous
  depuis la tranche 3c ; une copie gardée au fonds n'est que comptée) ;
- **à répondre** : chaque entrée employée retirée, avec « laisser à revoir » et « fusionner
  dans… » et ses cibles possibles (`_vers_possibles` + `vers_sans_double`, sur la vM) ;
- **ce qui se refuse** : les cibles où une entrée passée à « une seule fois » porte deux
  relevés (M1), nommées zone par zone ; une version qui n'est pas publiée ; une version plus
  ancienne que l'active (M5) ;
- les passes qui se rouvriront (§5), comptées par zone.

**Monter**, ensuite : `PUT …/activation` avec la version, les réponses (`reponses`, le format
de l'import : `retirer` → ici « laisser », `fusionner:<cle>`) et `vu` — le condensé du bilan
que l'écran a lu. Sous le verrou d'écriture (`conflit.verrouiller`), tout se relit ; si le
bilan n'est plus celui qu'on a vu (un relevé posé entre-temps qui change un compte), 409 qui
le dit, « relisez le bilan ». Puis, dans une transaction : les fusions (`_fusionner`,
`journaliser_fusion`), le report des relevés (`UPDATE releve SET version_id = vM`, borné au
projet), le drapeau `une` (`reporter_cardinalites`, appelé sur les deux versions), les passes
(§5), l'activation, et un acte `lien` sous `grille` dont la charge dit la montée (de vN à vM,
les comptes, les fusions, les passes rouvertes). Une activation sans relevé reste ce qu'elle
est aujourd'hui, sans bilan exigé.

La montée elle-même ne prend pas de temps : un `UPDATE` par sorte de relevé, quelques
milliers de lignes (**hypothèse** sur le volume de LingApp ; à mesurer sur la base de recette
au commit 2).

---

## 5. Les passes « terminée »

« Terminée » dit qu'une zone a été REGARDÉE avec la grille (note du modèle §9). Après la
montée, ce qui reste vrai est ce qui a été regardé ; ce qui devient faux est ce que la vM
ajoute à regarder.

**Proposé (M4 c)** : une passe se ROUVRE quand la vM lui ajoute quelque chose à regarder sur
CETTE zone — une entrée née, ou déplacée dans sa rubrique, ou dont « Porte sur » s'élargit au
type de la zone. Le périmètre d'une passe est sa rubrique et ce qu'elle contient ; celui de
la passe « toute la grille » (`rubrique_cle = ''`), la grille entière. Une entrée née sous une
sous-rubrique rouvre donc la passe de la sous-rubrique, celles de ses rubriques parentes, et
celle de toute la grille ; sur une case, seulement si l'entrée se pose sur les cases. Toute
autre passe reste, sa version portée à vM. Une passe dont la rubrique n'existe plus dans la vM
ne dit plus rien : elle part.

Ce qui ne rouvre rien : une entrée retirée, renommée, retouchée ; un relevé qui devient à
revoir (la passe ne dépend d'aucun relevé, note du modèle §9 — il se lit dans « À revoir »).

**Le journal** : chaque passe rouverte s'écrit `passe_rouverte`, comme un « Rouvrir » — le 409
de CONC-3 sur une passe nomme qui l'a changée, et il doit pouvoir nommer la montée. Mais
elles sont marquées dans leur charge (`montee`) et écartées, comme l'acte `fusion`, de ce qui
lit le journal pour dire « qui a travaillé » (`autorisation`, `comptes.traces`) : sans quoi
qui monte la version figurerait dans « qui perd quoi » de chaque album du projet. La forme :
généraliser `grilles.sql_acte_de_fusion` en « acte qui range un vocabulaire ».

---

## 6. Qui monte une version

**Qui gère le projet** (`peut_gerer_projet` : ses responsables, l'administrateur qui passe
outre) — la règle d'aujourd'hui pour activer, et le patron de la fusion. Aucune raison d'en
décider autrement : la montée fixe le vocabulaire de tout le projet, réécrit la version des
relevés des autres et rouvre leurs passes. Dans un bac à sable, son propriétaire (il en est le
responsable) ; sur le jeu, refusé comme aujourd'hui (`_MOTIF_JEU`). L'aperçu est borné de
même : 404 sur un projet qu'on ne voit pas, 403 nommé sur un projet qu'on voit sans le gérer
(`_get_projet`). Le cliquet de `tests/test_autorisation.py` exige que la route neuve soit
tranchée.

---

## 7. Le reste

**Ctrl+Z.**
- *La montée elle-même* ne s'annule pas (M5) : un acte sous `grille`, hors des types de
  `undo._TYPES`, comme la fusion. Revenir se fait autrement — selon M5.
- *Les gestes d'avant la montée* (se tranche en route, cf. la fin du §10). Défaire une pose ou une retouche lit le relevé actuel :
  passé en vM, il se défait déjà. Rétablir un relevé RETIRÉ avant la montée, ou les relevés
  d'une région supprimée avant elle, lit l'instantané, en vN : aujourd'hui l'acte serait passé
  (« l'état d'avant ne peut plus être rétabli »). Proposé : l'instantané se rend dans la
  version ACTIVE si la règle du §3 le laisse passer (son entrée y existe et n'est pas
  retirée ; une variante et des cases qui y ont leur place), et le geste est passé sinon. UNE
  règle, écrite une fois, que la montée, Ctrl+Z et J8 appellent.
- *Une fusion faite à la montée* change `entree_cle`. Défaire ensuite la pose d'origine
  retirerait le relevé fusionné sans rien dire, comme après la fusion d'une ouverte
  aujourd'hui (lu : `_VALEURS_DU_RELEVE` ne compare pas l'entrée). Le cadrage du mode libre
  proposait d'y ajouter `grille_id` et `entree_cle` pour J8 ; la montée en a le même besoin.
  Se tranche en route : le 409 « Passer ce geste » nommerait l'acte de fusion.

**Le journal.** Un acte sous `grille` pour la montée ; un acte `fusion` par relevé fusionné
(le patron existant) ; un acte `passe_rouverte` par passe rouverte (§5). Pas d'acte par relevé
qui change seulement de version : la version n'est pas une valeur que CONC-3 garde, et l'acte
de grille, daté, dit qu'avant lui le relevé était en vN. Toutes ces cibles sont déjà RETENUES
de toute sortie (`tools/_commun.CIBLES_RETENUES` : `grille`, `releve`, `releve_planche`).

**Deux écrans pendant la montée (CONC-3).** La montée tient le verrou d'écriture ; une pose
qui part pendant elle attend, puis reçoit le 409 « votre écran montre la version N.
Rechargez la page. » Une retouche d'un relevé passé en vM réussit : ses valeurs n'ont pas
bougé. **À corriger avec la montée** : l'empreinte des plans ne porte que les grilles
ouvertes ; une planche qui ne porte aucun relevé de la grille ne montre donc pas
« ⟳ Actualiser » après une montée, et la page garde le plan de la vN jusqu'au premier 409.
Proposé : `empreintes_plans` porte aussi, pour chaque grille FERMÉE active, le numéro de sa
version ; et la phrase du 409 renvoie à « Actualiser » plutôt qu'à « Rechargez la page ».

**Les copies amorcées au cran `annotations`.** Une copie recopie la version de sa source. Une
copie faite APRÈS la montée recopie des relevés déjà en vM. Une copie faite PENDANT est
sérialisée par le verrou. Une copie au fonds du projet monte avec le projet (le périmètre du
§2). Entre deux projets, rien ne suit encore (une grille n'est active que chez elle). **Rien à
changer** (lu) — à revoir avec le catalogue, quand une grille sera active dans deux projets à
deux versions : la copie devra alors porter le relevé dans la version de l'ARRIVÉE, par la
règle du §3.

**Les sorties.** Un relevé ne sort par aucune voie avant la tranche 4
(`tests/test_releves_sorties.py`), et la montée n'ajoute aucune sortie : elle écrit dans des
tables et sous des cibles déjà retenues. L'index plein texte ne porte que les libellés des
grilles OUVERTES : une montée, qui ne concerne qu'une grille fermée, n'y touche pas. La
Recherche reconnaît une entrée par sa `cle`, quelle que soit sa version : son filtre
« Porte… » trouve les mêmes zones avant et après. L'aperçu et la montée sont des routes JSON
sans fichier : le cliquet de `tests/test_droit_export.py` n'en voit aucune ; celui des
sorties d'identité (`tests/test_sorties_identite.py`) balaie l'aperçu, qui ne porte aucun
login.

**Une grille dérivée** (v40). La montée ne lit ni n'écrit `derivee_de_*` : elle se fait dans
une grille, entre deux de ses versions. Une grille dérivée ne suit pas les versions de son
origine — c'est la dérivation allégée (Hugo, 2026-10-22) : pour reprendre la v3 d'une origine,
on réimporte son classeur comme version suivante de la dérivée, puis on monte. Le classeur
d'une version porte son numéro : rien à ajouter.

---

## 8. « Passer dans une grille… » (J8)

Une entrée de la grille de travail passe, avec ses relevés, dans une entrée d'une AUTRE grille
active du projet. Ses règles sont tranchées (J8, 2026-11-06). Ce que cette note y ajoute :

- **Vers quelle version d'une grille fermée** : l'ACTIVE, toujours — on y AJOUTE des relevés,
  le geste ordinaire. Jamais le brouillon : un relevé ne vit que dans une version active, et
  écrire l'entrée dans le brouillon, publier et monter en un seul geste ferait trois décisions
  d'une. Le geste ne fait donc naître aucune version. Si l'entrée d'arrivée manque, le bilan le
  dit : « écrivez-la dans le brouillon, publiez, montez la version, puis revenez » — c'est
  pourquoi la montée vient d'abord.
- **Ce que devient une variante** : la table de correspondance de J8, proposée par le libellé
  (`cle_tag`), corrigée à la main. Vers une entrée simple, la valeur n'a pas de place : le
  relevé RESTE (J8). Vers une entrée à variantes, une valeur sans correspondance : le relevé
  reste.
- **Le bilan, relevé par relevé**, est celui de la montée avec une différence : à la montée,
  un relevé qui ne convient plus passe et se dit « à revoir » ; en passant dans une autre
  grille, il RESTE dans le Mode libre, et le bilan dit pourquoi — mêmes causes, mêmes mots.

**Ce qu'ils partagent** : la règle « ce relevé convient-il à cette entrée de cette version »
(sorte de pose, type de zone, forme, variante, cases, cardinalité, doublon) ; le bilan en
données ; l'acte `fusion` par relevé déplacé — J8 en est une fusion qui change de grille, et
il suit la règle confirmée le 2026-11-15 (ni un travail sur l'album, ni « celui d'un autre ») —,
là où le cadrage du mode libre proposait un acte `releve` ordinaire ; la traduction de Ctrl+Z
(§7) ; l'empreinte des plans. **Ce qui lui est propre** : il change `grille_id`, il réindexe les
étiquettes des régions qu'il touche (la grille de travail est ouverte : ses libellés sont dans
l'index, ceux d'une fermée non), il ne rouvre aucune passe (on ajoute des relevés, on ne change
pas le plan), et l'étiquette vidée se propose au retrait.

**Proposé (M7)** : J8 vient dans la foulée de la montée, après le livrable des linguistes, en
commits à part. La règle partagée s'écrit une fois, au premier commit de la montée ; J8 coûte
alors deux jours au lieu des trois estimés le 2026-11-06.

---

## 9. Le découpage en commits

Chaque commit de code cite `ANN-7` ; la fiche se met à jour à part. Aucune migration, sauf si
M3 retient (b).

**Le livrable qui débloque la grille des linguistes — les commits 1 à 3, ≈ 3 jours.**

1. **La règle d'un relevé dans une version** (≈ 1 jour). Un cœur — « ce relevé, dans cette
   version : passe, à revoir (causes), à compléter, à décider, refusé » —, les six causes
   neuves dans `releves_effectifs` et `_CAUSES`, et le test qui accorde la règle et la vue,
   cas par cas (la table du §3). Utile seul : il ferme la faille de « Porte sur » de la grille
   de travail.
2. **La montée, côté serveur** (≈ 1½ jour). L'aperçu, `PUT …/activation` avec réponses et
   `vu`, le report borné au projet, les fusions, `une`, les passes (selon M4), l'acte de
   grille ; la garde `releve.version_id <> ?` d'`activer` remplacée par la montée ;
   `empreintes_plans` avec les grilles fermées ; `tools/importer_grille.py --activer` qui
   rend le bilan à blanc et monte avec `--reponses`. Tests : chaque ligne du §3, la course
   (une pose pendant la montée), le périmètre (une grille de deux projets, par SQL, pour le
   jour du catalogue), les deux cliquets. Mutants : la borne du projet, le refus de M1, le
   `vu` du bilan, l'exclusion des passes rouvertes de « qui perd quoi ».
3. **L'écran minimal** (≈ ½ jour, selon M6). Dans le bloc « Grilles » de la fiche du projet,
   « Activer » d'une version plus récente devient « Monter à la version M… », qui ouvre sous la
   ligne une confirmation avec la phrase et les nombres du bilan, les entrées « à répondre »
   comme le bilan de l'import les montre déjà, et les refus.

**Ensuite — ≈ 1 jour.**

4. **Ctrl+Z après une montée** : l'instantané rendu dans la version active par la règle
   du commit 1 ; `entree_cle` dans les valeurs que Ctrl+Z compare. ½ jour.
5. **La documentation** : `CLAUDE.md` (§ Données, les GRILLES ; § Annulation),
   `docs/grilles-et-releves.md` §6 et §12, `docs/guide-utilisateur.md`, `docs/undo.md`. ½ jour.

**Après la maquette.** L'écran entier du bilan — relevé par relevé, les zones cliquables, les
passes rouvertes — se dessine dans la séance dédiée que Hugo a fixée le 2026-11-11 pour le
bilan des changements de « Publier… » (case « Activer, masquer et publier ont leur écran ») :
c'est le même bilan, vu de l'autre côté.

**J8** : ≈ 2 jours, en commits à part, la règle du commit 1 réemployée.

**Relecture croisée** : oui, une fois le commit 4 posé — la montée réécrit les relevés des
autres, rouvre leurs passes et touche Ctrl+Z. Sous quatre identités : le responsable du projet,
un annotateur qui a posé des relevés, un administrateur, le propriétaire d'un bac à sable. Une
passe de QA, `pilotage/qa/montee-de-version.md`, s'écrit avec le commit 3 : sur la recette,
une v1 avec des relevés de chaque forme, une v2 qui renomme, retire, change une forme, ajoute
une entrée et passe une entrée à « une seule fois », l'aperçu lu, la montée, deux comptes
ouverts pendant.

---

## 10. Les questions pour Hugo

| | Question | Options | Proposé |
|---|---|---|---|
| M1 | Une entrée devient « une seule fois », mais une zone en porte déjà deux : que fait la montée ? | (a) elle attend qu'on en retire un ; (b) les deux passent « à revoir » | (a) — la règle déjà tenue pour une grille ouverte, et la base refuse deux relevés « une seule fois » |
| M2 | « Fusionner dans… » une entrée retirée, à la montée : dès le premier livrable ? | (a) oui ; (b) plus tard, ses relevés restent « à revoir » d'ici là | (a) — le serveur sait déjà fusionner, et l'écran du bilan d'import pose déjà la question |
| M3 | Comment dit-on qu'une entrée est scindée ? | (a) on la retire et on écrit les nouvelles ; (b) un choix « à revoir » à la montée, sur une entrée qui reste | (a) — rien de neuf : « l'entrée a été retirée » se lit déjà ; (b) demanderait une colonne et une migration |
| M4 | Après la montée, quelles passes « terminée » se rouvrent ? | (a) aucune ; (b) toutes ; (c) celles où la version ajoute quelque chose à regarder | (c) — ce qui a été regardé reste vrai, une entrée neuve n'a pas été regardée |
| M5 | Comment revient-on en arrière après une montée ? | (a) Ctrl+Z ; (b) réactiver l'ancienne version, avec le même bilan ; (c) publier une version qui reprend l'ancienne, puis monter | (c) — une seule direction à tester ; (b) laisserait à revoir les relevés posés entre-temps sur les entrées neuves |
| M6 | Avant la maquette, l'écran de la montée : | (a) une confirmation sous la ligne, avec les nombres ; (b) l'outil seul, en ligne de commande ; (c) rien avant la maquette | (a) — le patron de « Publier », accepté « pour l'instant » le 2026-11-04 |
| M7 | « Passer dans une grille… » : quand ? | (a) dans la foulée, après le livrable des linguistes ; (b) plus tard | (a) — il réemploie la règle de la montée, et coûte alors deux jours |

**Se tranchent en route**, sans Hugo sauf avis contraire (le plus prudent à chaque fois) : une
montée vers une version plus RÉCENTE seulement (selon M5) ; le relevé garde une précision ou
un lien que l'entrée ne demande plus ; `entree_cle` entre dans les valeurs que Ctrl+Z compare ;
les passes rouvertes par la montée ne comptent pas dans « qui perd quoi » ; un geste d'avant la
montée se défait dans la nouvelle version quand la règle du §3 l'y laisse passer, et il est
passé sinon (§7) ; le périmètre est le
projet, écrit dès maintenant ; J8 écrit des actes `fusion` et non des actes `releve`.

---

## Vu en passant

- **Le « Porte sur » d'une étiquette employée de la grille de travail change sans rien dire**
  (**lu**, non rejoué). `reconcilier_ouverte` refuse sous des relevés un changement de forme,
  de liste et de cardinalité contradictoire, pas de cible ; et la vue ne voit pas un relevé de
  zone entière quand l'entrée vise désormais des mots, ni un relevé de planche quand elle vise
  une zone. Un responsable qui passe l'étiquette « ironie » de « toute la zone » à « des mots »
  laisse ses relevés de bulle « normaux ». Le commit 1 le ferme par la cause « sorte de pose
  changée ».
- **Une version publiée peut perdre une entrée, une variante ou une case employée**
  (**hypothèse**, lu dans `publier_version` qui ne le revérifie pas) : un brouillon ouvert
  quand la v1 ne portait pas encore de relevé sur une entrée, l'entrée supprimée du brouillon,
  puis un relevé posé en v1 sur elle, puis la publication. Le réimport et le formulaire le
  refusent au moment du geste, pas à la publication. Un test le trancherait ; la montée le
  tient de toute façon (« l'entrée n'existe plus dans cette version »).
- **Activer une autre version d'une grille fermée qui ne porte que des PASSES se fait sans
  rien dire** (**lu**, `activer` ne regarde que `releve`) : les passes gardent leur version et,
  le cas échéant, une rubrique qui n'existe plus dans la nouvelle. Le commit 2 y applique la
  règle des passes.
- **Une activation changée ne se signale pas aux pages ouvertes** (**lu**,
  `empreintes_plans` ne porte que les grilles ouvertes) : déjà vrai aujourd'hui pour une
  grille fermée sans relevé dont on active la v2 — la page garde la v1 jusqu'au 409 de la
  première pose. Le commit 2 le ferme.

---

## Ce que cette note n'a pas pu établir

- **Le volume de LingApp** au moment de la première montée : non mesuré ; la montée est
  supposée tenir en une transaction courte.
- **Ce que l'écran montre d'une précision qu'une entrée ne demande plus** : non lu dans
  `static/lib/annotation.js` ; supposé lisible, à vérifier au commit 3.
- **Le texte exact des causes neuves** : proposé ici, à confirmer à l'écran (« Écran stable,
  sans phrases » : la cause se lit sur la ligne du relevé, l'aide en infobulle).
