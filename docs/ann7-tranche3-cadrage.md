# ANN-7, tranche 3 — le basculement : cadrage

Rendu le 2026-11-05, sur `dev` à `9ef3143` (schéma **38** : les tranches 1 et 2 d'`ANN-7`, la
3c de `COL-3`, le formulaire et le classeur des grilles). Rien n'est codé. Ce qui est marqué
**lu** a été lu dans le code à ce commit ; ce qui est marqué **mesuré** sort d'une commande
citée dans l'annexe ; ce qui est marqué **hypothèse** ne l'a pas été, et dit ce qui
trancherait. Les questions qui restent à Hugo sont numérotées **I1 à I9** — la suite de G1 à
G20 (tranche 1) et de H1 à H7 (tranche 2) — et viennent EN TÊTE, chacune avec une
proposition et son coût.

Le basculement est décidé dans son principe depuis le 2026-10-22 : les tags, la situation
d'une case et le profil d'un personnage cessent d'exister comme vocabulaires à part, et
l'annotation n'a plus qu'un modèle, la grille. Cette note ne rediscute pas ce principe ; elle
dit ce qu'il retire du code, ligne de compte à l'appui, ce qu'il laisse en place, ce que la
tranche 4 attend de lui, et dans quel ordre le faire sans casser ce qui marche.

Le dépôt est public : aucune grille réelle n'est citée ici.

---

## Les questions pour Hugo

1. **I1 — Livrer la tranche 3 seule, ou avec la tranche 4 ?** Entre les deux, la Recherche et
   l'Exploration ne liront plus AUCUNE annotation structurée : ni les tags (retirés), ni les
   relevés (qu'elles ne lisent pas encore). Elles gardent le texte, la note, la grammaire, le
   locuteur et le personnage (section « Entre la tranche 3 et la tranche 4 »). (a) La tranche 3
   seule, puis la tranche 4. (b) Les deux dans le même lot. *Proposé : (a).* Ce qu'on perd
   dans l'intervalle est un corpus de TEST (Hugo, 2026-10-21) que personne ne filtre ; les
   relevés, le seul travail réel, ne sont déjà pas cherchables aujourd'hui ; et la tranche 4
   touche ce qui SORT, donc demande sa relecture croisée — la lier au basculement retarderait
   le retrait du mode Annotation de l'Atelier, que le wizard et l'écran mobile attendent.
   Coût de (a) : quelques semaines où l'on ne filtre l'Exploration par aucune annotation.

2. **I2 — Le profil d'un personnage, d'ici l'étage de projet des personnages.** Le profil
   devient une grille sur l'ENTITÉ du registre (Q4), et cette cible est refusée tant que les
   personnages n'ont pas leur étage de projet (G3, tranche 4 de `COL-3`). Retirer
   `personnage_attribut` au basculement laisse donc un intervalle où AUCUN profil ne se pose.
   (a) Le profil part avec le reste et revient avec la cible `entite`. (b) On garde
   `personnage_attribut`, ses dimensions et ses valeurs jusque-là — c'est-à-dire la moitié du
   modèle d'aujourd'hui (termes, portée, lexique, routes, écran) pour une table. (c) Une grille
   provisoire sur la BOÎTE personnage. *Proposé : (a).* La production porte 3 attributs de
   personnage, de test (2026-10-21) ; (b) coûterait l'essentiel de ce que la tranche retire ;
   (c) pose « ce personnage dans cette case », que Q4 a justement distingué du profil.

3. **I3 — Qui écrit les grilles « tags libres » et « situation » ?** Le basculement ne
   convertit rien (Q3) ; reste à dire s'il CRÉE quelque chose. (a) Rien : chaque projet écrit
   les grilles dont il a besoin, par le formulaire ou le tableur — la grille « Lieux », ouverte,
   sur la case, tient lieu de situation pour les stagiaires (case ouverte « Le contenu de
   « Lieux » est écrit »). (b) La migration pose dans chaque projet ordinaire une grille
   ouverte et vide, « sur la zone », tirée d'un fichier de données comme la grille du bac à
   sable (H4). *Proposé : (a).* « Rien d'une grille n'est dans le code » ; une grille vide
   nommée par la migration serait un vocabulaire écrit par l'outil, et chaque projet devrait
   ensuite la supprimer ou la renommer. Coût : une phrase du guide qui dit comment recréer des
   tags libres (une grille ouverte, forme simple, sur la zone).

4. **I4 — Ce que veut dire « annotée ».** La coche ✓ de l'arbre de l'Atelier, `nb_annotees`
   des listes de planches et le compteur « annotées » de la Recherche lisent aujourd'hui « une
   note non vide, ou un tag dont on lit le terme » (`socle._sql_a_montrer`, **lu**). (a) Une
   note non vide, ou au moins un relevé sur la région. (b) Une note non vide seulement.
   *Proposé : (a)* — sans quoi une bulle relevée par les linguistes se dit « non annotée ».
   Coût : une sous-requête de plus, sans question de portée (lire un relevé, c'est lire
   l'album).

5. **I5 — Comment couper les Ctrl+Z d'avant le basculement.** Q3 les veut « passés, comme un
   acte d'`AUTH-14` ». (a) Un PLANCHER : la migration note dans `meta` le dernier acte du
   journal, et `undo.derniere_action_annulable` ne remonte pas au-dessous — tous les actes
   d'avant, de toute sorte, relevés compris, cessent d'être offerts ; Ctrl+Z dit « rien à
   annuler ». (b) Ne couper que les actes dont l'inverse toucherait le vocabulaire (une
   annotation qui portait des tags, une suppression de région dont l'instantané porte une
   situation…), les autres restant annulables. (c) Écrire à la migration une trace `abandon`
   pour chaque acte annulable. *Proposé : (a).* C'est la lettre de Q3, et le moins de code :
   (b) oblige chaque inversion à trier ses instantanés, là où un oubli réécrirait dans une table
   morte (une erreur 500, pas une fuite) ; (c) écrit des milliers de lignes pour dire ce qu'un
   seul nombre dit. Coût de (a) : un geste fait juste avant le déploiement ne se défait plus —
   personne ne travaille pendant une migration.

6. **I6 — La réindexation plein texte.** Retirer `tags_concat` impose de recréer la table FTS
   (le schéma d'une table FTS5 ne se modifie pas). (a) Recréer l'index en RECOPIANT ses lignes
   sans la colonne : le texte, la note et les lemmes déjà calculés suivent, sans moteur de
   langue — **mesuré** à 6 ms pour 330 régions, 112 ms pour 20 000, 757 ms pour 100 000 ; un mot
   qui n'était qu'un tag ne trouve plus rien. (b) Une réindexation complète par le moteur
   (`database.reindex_all`, spaCy), qui recalcule aussi tous les tokens. *Proposé : (a)* :
   c'est l'index entier reconstruit une fois, ce que la décision du 2026-10-22 demandait
   (« une seule réindexation complète, au basculement ») ; (b) ne change ni le texte ni les
   lemmes et coûte le temps du moteur (non mesuré sur la recette). Coût de (a) : aucun ; les
   tokens restent ceux de la dernière analyse.

7. **I7 — Les anciens chemins.** Ce qui menait au vocabulaire existe encore dans des liens et
   des écrans d'hier : `/?…&mode=annotation` (UX-12), la touche `A` de l'Atelier, les
   paramètres `tags`, `tag_scope` et `attributs` de la Recherche et de l'Exploration (dans les
   liens « drill » enregistrés), les champs `tags`, `tags_ajoutes`, `tags_retires` de
   `PUT /api/regions/{id}/annotation`. (a) `mode=annotation` et `A` mènent à la page Annotation
   sur la zone courante (le chemin d'« Annoter ↗ ») ; l'API refuse les anciens paramètres et
   champs par un 422 qui le dit (« les tags n'existent plus »). (b) Tout est ignoré en silence.
   *Proposé : (a).* FastAPI ignore un paramètre inconnu : un lien filtré par tag rendrait le
   corpus entier en ayant l'air filtré — un filtre qui se tait, le défaut qu'`AUTH-11` a déjà
   corrigé ailleurs. Coût : un test par route, et une ligne dans `entrerDansLeModeDeLAdresse`.

8. **I8 — Regarder la production avant de migrer.** Q3 tient « à condition que personne ne
   pose de vrai travail en tags d'ici là ». La dernière mesure date du 2026-10-21 (13 tags posés
   31 fois, 11 attributs de case, 3 de personnage). (a) Avant le déploiement, Hugo lance en
   lecture seule la commande de l'annexe ; toute affectation postérieure au 2026-10-21 est
   listée et relue avec lui avant de migrer. (b) On migre sans regarder. *Proposé : (a)*, cinq
   minutes ; la migration détruit sans retour (une sauvegarde en garde la trace).

9. **I9 — La vraie base v38 vient du commit qui PRÉCÈDE la tranche.** La règle de Hugo
   (2026-10-16) veut la base de la version précédente fabriquée par « le dernier état » de
   cette version. Ici, le dernier état v38 sera le commit qui retire les routes du vocabulaire
   (commits 1 à 4 du découpage) : le parcours de `tools/fabriquer_base_de_version.py` ne
   pourrait plus y poser un tag. *Proposé : fabriquer la base depuis le commit qui précède la
   tranche* — même schéma, mêmes tables, vocabulaire posé par les vraies routes. C'est un écart
   à la lettre de la règle, pas à son but (une base qui a vécu). Coût : aucun.

**Se tranchent en route**, sans Hugo sauf avis contraire (le choix le plus prudent à chaque
fois) : la colonne `tags` du CSV d'export est retirée et non laissée vide ; « aucun export sans
titre » (`AUTH-11`) reste, bien que sa raison — borner le vocabulaire — attende la tranche 4 ;
les actes passés sur `region_attribut` ne comptent plus dans « qui perd quoi » (ce qu'ils ont
posé n'existe plus), mais restent dans ce qu'un compte laisse en partant (`comptes.traces` :
le travail a été fait) ; les tags d'un bac à sable partent avec la table, comme tout ce qu'un
lundi efface ; `tools/vocabulaire-etude-propose.csv` reste tel quel jusqu'à ce qu'`ANN-1`
décide de sa grille ; les classes CSS `.tag-input-wrap` et `.tag-suggest` restent, la page
Annotation les emploie pour le locuteur (**lu**, `templates/annotation.html`) ; `cle_tag`
reste, les grilles et les relevés s'en servent (**lu**, `grille_import.py`, `routes/releves.py`,
`mots.py`).

---

## Ce qui est déjà tranché (cité)

- **Le vocabulaire neuf, sans conversion** — Q3, Hugo, 2026-10-22 (`pilotage/ANN-7.md`,
  « Tranché par Hugo — 2026-10-22 ») : les tags, dimensions, valeurs et leurs affectations ne
  deviennent pas des grilles ; leurs tables sont retirées ; les Ctrl+Z d'avant sont coupés,
  « passés, comme un acte d'`AUTH-14` », au lieu de réécrire dans des tables mortes
  (la fiche cite `undo._ensure_tag` ; c'est aujourd'hui `undo._tag_a_rendre`, qui ne crée plus
  de tag depuis `ANN-8` mais en repose). Aucun terme local ne devient visible du projet
  entier : la question de portée d'`AUTH-11` ne se pose pas. Condition : que personne ne pose
  de vrai travail en tags d'ici là (I8).
- **Le corpus de production est un corpus de test** — Hugo, 2026-10-21, écrit sous Q3 et dans
  le Contexte de la fiche (« Mesuré en production le 2026-10-21 »). Toujours écrit au
  2026-11-05 ; non remesuré depuis (I8).
- **Les stagiaires ne posent aucun tag avant le basculement** — Q9, 2026-10-22 ; et les lieux
  attendent la grille « Lieux » (G20 c, 2026-10-25). Rien n'est donc à convertir de leur
  travail : découpage, transcription, locuteurs restent.
- **La place de chaque vocabulaire dans les grilles** — 2026-10-14, tenu le 2026-10-22 (« Un
  seul modèle : ce qui existe y entre ») : les tags libres, une grille ouverte de forme simple
  sur la zone ; la situation d'une case, une grille à variantes sur la case ; le profil d'un
  personnage, une grille à variantes sur l'ENTITÉ (Q4), qui attend l'étage de projet des
  personnages (G3) ; le lexique situé, ce que porte une entrée. Le LIEU d'une case vit dans
  une grille à part, « Lieux », ouverte, sur la case (`ANN-6`, 2026-10-22).
- **L'index plein texte perd les tags** — Hugo, 2026-10-22 (« La réindexation plein texte se
  paie une fois ») : le basculement retire `tags_concat`, ne met pas les relevés dans l'index,
  paie une seule réindexation complète ; la Recherche gagne en tranche 4 un filtre « porte le
  relevé… », et le champ promet « dialogues, notes ». La limite écrite sous `AUTH-11` se ferme.
- **Le mode Annotation de l'Atelier disparaît, le bouton avec lui** — Hugo, 2026-11-02 : on
  annote dans la page Annotation. Deux conditions, cases ouvertes de la fiche : l'identité
  d'une boîte personnage s'écrit dans la page Annotation, et le panneau Personnage
  (alignements A5) s'ouvre depuis elle.
- **Le wizard passe de quatre modes à trois** — `UX-6`, 2026-11-02, et la zone « Au
  basculement — le texte du wizard » de la fiche ; `UX-3` suit ; sur téléphone, les modes en
  bas de l'Atelier passent de quatre à trois (`UX-7`, case ouverte).
- **L'ordre** — `UX-20`, 2026-11-02 : le catalogue, puis le wizard, puis le basculement « une
  fois les linguistes revenus ».
- **Les grilles sont le vocabulaire au niveau du projet** — Q2, 2026-10-22 : la tranche 4 de
  `COL-3` ne garde que les personnages, la Recherche et l'Exploration bornées au projet, et le
  double compte des copies sœurs.
- **Renommer, fusionner, retirer une entrée d'une grille ouverte** — tranché le 2026-10-22
  (« Supprimer, fusionner, renommer un terme a sa règle ») et prévu pour la tranche 3 par G14 :
  **déjà codé** le 2026-11-04 (`f2c78cc`, `edc9ae7` : `PATCH`, `…/retrait`, `…/fusion` d'une
  entrée dans `routes/grilles.py`, à qui gère le projet). La tranche 3 n'a rien à y ajouter.
- **La note reste** — `ANN-6`, 2026-10-22, « Le Contexte ne garde que ce qui n'est pas du
  vocabulaire » : le locuteur, la note, le nom d'un détail. La page Annotation écrit la note
  depuis le jalon 3 (`cd17dd2`, avec `note_vue`). Le locuteur, la présence, les personnages et
  leurs alignements restent aussi : ce sont le registre, pas un vocabulaire.

---

## Ce que la tranche 3 livre, en gestes

1. L'Atelier a trois modes : Navigation, Édition, Transcription. « Annoter ↗ » mène à la
   page Annotation, qui écrit le locuteur, la note, le nom d'un détail, l'identité d'une boîte
   et ouvre le panneau Personnage.
2. Plus aucun écran ne montre, ne pose ni ne documente un tag, une situation, un profil, un
   domaine : ni le panneau 📖 Lexique de l'Exploration, ni son import de vocabulaire, ni le
   nuage de tags de la Recherche, ni les facettes « tag » et « attribut ».
3. Un projet qui veut des tags libres ou une situation écrit une grille (I3).
4. La recherche plein texte porte sur les dialogues, les notes et les lemmes.
5. Ctrl+Z ne remonte pas au-delà du basculement (I5).
6. Les exports ne portent plus de vocabulaire ; ce que les relevés y deviennent est la
   tranche 4.

---

## L'inventaire mesuré

### La méthode

Trois comptes, tous rejouables (annexe) : les motifs SQL et les noms de route, par `git grep`,
fichier par fichier ; les fonctions Python touchées, par l'arbre syntaxique (`ast`) ; les
tests, par fonction `test_*` dont le corps touche l'un des motifs. Un motif large compte
trop : les chiffres des tests sont des MAJORANTS (le mot « attributs » ou une clé JSON `"tags"`
y entrent aussi dans des tests qui n'ont rien à voir). Les comptes du 2026-10-21 (Contexte de
la fiche : `annotation_tags` 10 fichiers, `region_attribut` 10, `attribut_valeur` 10,
`personnage_attribut` 7) ne sont pas comparables terme à terme : leur méthode n'est pas
écrite.

### Les tables, colonnes, index

**Sept tables disparaissent** (**lu**, `database.SCHEMA_SQL`) : `tags`, `annotation_tags`,
`domaine`, `attribut_dimension`, `attribut_valeur`, `personnage_attribut`, `region_attribut`.
Avec elles **dix index** : cinq dans le schéma (`idx_anntags_tag`, `idx_attrval_dim`,
`idx_persoattr_val`, `idx_regattr_val`, `idx_domaine_collection`) et cinq posés par
`_migrate` (`idx_dim_domaine`, `idx_dim_collection`, `idx_val_collection`,
`idx_tags_collection`, `idx_tags_espace_label`). **Une colonne de l'index FTS**,
`recherche.tags_concat`. Aucune vue ne les lit (`tokens_effectifs`, `releves_effectifs` :
**lu**). Aucune autre table ne les référence (**lu** : les seules clés vers elles sont entre
elles).

**Une table reste, amputée de son rôle** : `annotations`, qui ne porte plus que la note (et
`recopiee`). Son nom reste — le journal la nomme (`cible_table = 'annotations'`), Ctrl+Z aussi.

Lecteurs, hors tests et docs (**mesuré**, `git grep -l` / `-h | wc -l`) :

| Motif | Fichiers de code | Lignes | Fichiers de test | Lignes |
|---|---:|---:|---:|---:|
| `annotation_tags` | 12 | 46 | 12 | 21 |
| `region_attribut` | 19 | 74 | 20 | 47 |
| `personnage_attribut` | 8 | 24 | 3 | 6 |
| `attribut_valeur` | 14 | 58 | 19 | 112 |
| `attribut_dimension` | 10 | 56 | 19 | 116 |
| `tags` (FROM / JOIN / INTO / UPDATE) | 14 | 50 | 16 | 63 |
| `domaine` (FROM / JOIN, `domaine_id`) | 8 | 76 | 10 | 112 |
| `tags_concat` | 3 | 20 | 3 | 6 |

Tous motifs confondus (une liste plus large : les tables, les routes, les fonctions de portée
des termes), **mesuré** en lignes uniques : serveur 22 fichiers, 670 lignes ; écrans 8
fichiers JS, 55 lignes ; outils 9 fichiers, 79 lignes ; tests 53 fichiers, 917 lignes. Ce sont
les lignes qui NOMMENT le vocabulaire ; les fonctions et fichiers entiers qui partent sont
plus gros (ci-dessous).

### Les routes

**31 routes disparaissent sur 231** (**mesuré**) :

- `main.py` : `GET /api/tags`, `POST /api/tags` (2).
- `routes/lexique.py`, le fichier entier (497 lignes) : `GET /api/lexique`,
  `POST /api/lexique/importer`, `PATCH …/dimensions/{id}/lexique`, `PATCH …/valeurs/{id}/lexique`,
  `PATCH /api/tags/{id}/lexique`, `PUT`, `DELETE` et `POST …/fusion` d'un tag (8).
- `routes/personnages.py`, toute sa seconde moitié (de `GET /api/domaines` à la fin, environ 500 lignes sur 1 038) : les domaines (5), les
  dimensions (4), les valeurs (6), les attributs d'un personnage (3) et d'une région (3) (21).

**Une vingtaine changent de forme** (**lu**) — c'est là que se loge le travail fin :

| Route | Ce qui part |
|---|---|
| `GET` / `PUT /api/regions/{id}/annotation` | `tags` de la réponse ; `tags`, `tags_ajoutes`, `tags_retires` du corps (I7) |
| les neuf routes d'analyse (`frequences`, `lemmes`, `concordance`, `comparaison`, `croisement` et leurs `.csv`) | paramètres `tags`, `tag_scope`, `attributs` (et `a_` / `b_` de la comparaison) ; axes `tag` et `dim:<id>` du croisement ; colonne `tags` de la concordance |
| `GET /api/recherche`, `GET /api/recherche/export.csv` | les mêmes paramètres ; `tags` de chaque résultat et du CSV |
| `GET /api/corpus` | le compte `tags` ; « annotées » (I4) |
| `GET /api/albums/{id}/planches`, `GET /api/planches/{id}/regions` | `nb_annotees`, `annotee` (I4) |
| `GET /api/export/json`, `/csv`, `/tei` | les tags d'une annotation (`<note type="tags">` du TEI, colonne du CSV) |
| `PUT /api/regions/{id}` | `situation_retiree` quand le type change |
| `GET /api/planches/{id}/empreinte` | tags et attributs dans l'empreinte d'une région |
| les aperçus d'« en partir », de « repartir de zéro », « qui perd quoi » | tags, attributs, `region_attribut` dans leurs comptes |
| les routes du dépôt (`routes/depot.py`, par `tools/metadonnees_collection.py`) | le catalogue SKOS et les tables du vocabulaire |

### Le serveur, fichier par fichier

| Fichier | Ce qui part ou change (**lu**) |
|---|---|
| `database.py` | les sept tables du schéma ; `tags_concat` dans `_FTS_SQL`, `_region_index_payload`, `_index_region` ; `reindex_tags_regions` ; `clause_appartenance`, `lexique_resume` ; la part « situation » de `liens_vus`, `retirer_liens_caches`, `situations_cachees` ; tags et attributs dans `copier_le_travail`, `compter_le_travail`, `_marquer_les_couches_recopiees`, `niveau_de_travail`, `repartir_de_zero`, `compter_repartir` ; `region_attribut` de `TABLES_D_ANNOTATION` et de `COUCHES_RECOPIEES` ; 30 lignes de `_migrate` (cf. la migration) |
| `socle.py` | `_norm_tag`, `_ensure_tags`, `_annotation_selon` (la note seule), `_tags_caches`, `_sql_a_montrer` (I4), `_rive_d_un_terme`, `_exiger_une_rive` pour les termes, `_supprimer_le_vocabulaire_du_bac`, `_vocabulaire_d_export`, `_get_dimension`, `_get_valeur`, `_attributs_de`, `_ancetres_terme`, `_patch_lexique`, les modèles `TagIn`, `DomaineIn`, `DimensionIn`, `ValeurIn`, `LexiqueIn`, `AttributIn`, `DimensionDomaineIn` ; la clause « vocabulaire propre » de la suppression d'un projet |
| `autorisation.py` | **trois questions retirées** : `clause_terme`, `peut_ecrire_terme`, `peut_remanier_tag` (trois de moins au décompte de `CLAUDE.md`, § Autorisation, et la clé `remaniable` de `GET /api/lexique` part avec sa route) ; la source « attributs sans lien humain » de `_sources_du_travail` |
| `main.py` | les deux routes des tags ; `put_annotation` (la note seule) ; les tags des trois exports ; `situation_retiree` |
| `routes/analyse.py` | `_analyse_filtres` (tags, attributs), `_valider_facette` (attributs), `_joindre_tags`, `_axe_croisement` (axes `tag` et `dim`) ; le personnage-locuteur reste |
| `routes/recherche.py` | `_recherche_rows` (tags, attributs) ; le compte `tags` de `GET /api/corpus` |
| `routes/collections.py` | les termes d'une collection supprimée (`_rive_d_un_terme`) |
| `lexique_import.py` | le fichier entier (382 lignes) |
| `undo.py` | `_contexte_tags`, `_tag_a_rendre`, la part tags de `_poser_annotation` et `_inverser_annotation`, la part situation de `_rendre_liens`, `_liens_rendables`, `_garder_liens_du_type`, `_garder_liens_de_creation`, `_valeur_nee_apres`, `meme_dimension` ; et le plancher (I5) |
| `journal.py` | les tags de `snapshot_annotation`, les attributs de `snapshot_region_profond` |
| `empreinte.py` | tags et attributs de l'empreinte |
| `pipeline/segmentation.py`, `pipeline/bulles.py` | `region_attribut` dans le critère qui garde une case ou une bulle (les relevés et passes y sont déjà) |
| `config.py` | `TYPES_SITUATION` |

### Les écrans

| Fichier | Ce qui part (**lu** ; découpage des fonctions approximatif) |
|---|---|
| `templates/index.html`, `static/viewer.js` | le mode Annotation : le bouton, `#panel-annotation` (une centaine de lignes du gabarit), `loadAnnotation`, `chargerBlocsDuType`, `renderTagChips`, `addTag`, `removeTag`, `saveAnnotation`, `refreshTagVocab`, `setupTagInput`, `makeAttributsWidget`, `setupAttributs`, `loadSituation`, les champs locuteur et personnage de l'Atelier et leur conflit de note ; le mode dans `MODES_ATELIER` et la touche `A` (I7) ; le message `situation_retiree` de `patchRegion` |
| `templates/exploration.html`, `static/exploration.js` | le panneau 📖 Lexique et son import (d'`openLexique` à `importerTableur`, environ 390 lignes), les facettes « tag » et « attribut » des deux sous-corpus, la case « herite », les axes `tag` et `dim`, les puces de tags de la concordance |
| `templates/recherche.html`, `static/recherche.js` | le nuage, les tags actifs, le filtre par tag, les tags d'un résultat ; « dialogues, notes, tags » devient « dialogues, notes » |
| `static/lib/gestes-tag.js` (108 lignes), `static/lib/bilan-import.js` (131 lignes) | les deux fichiers, que seule l'Exploration charge |
| `static/lib/echelle.js`, `static/lib/suppression.js` | « notes, tags, attributs de case… » au cran des annotations ; les tags et attributs qui « restent » ; le libellé `region_attribut` (gardé pour les actes passés, cf. « se tranchent en route ») |
| `static/lib/resultats.js` | le compte `tags` |
| `static/lib/wizard.js` | **cinq zones**, et pas seulement les modes (cf. « Vu en passant ») |
| `static/style.css` | 315 lignes nomment `tag-`, `lexique`, `attr-`, `sit-`… (**mesuré**) ; `.tag-input-wrap` et `.tag-suggest` restent |

La page Annotation elle-même ne lit aucun tag (**lu** : `static/annotation.js` n'emploie
« tag » que dans ses aides DOM, et ne lit de l'annotation que la note).

### Les outils

`tools/importer_vocabulaire.py` (158 lignes), `tools/tags_hors_collection.py` (115) et
`tools/vocabulaire-modele.csv` partent. `tools/metadonnees_collection.py` (42 lignes
touchées : le catalogue SKOS des tags, des domaines, des dimensions et des valeurs, les tables
CSV `tags`, `personnage_attributs`, `region_attributs`, `domaines`, le résumé « % défini »),
`tools/description_collection.py` (39), `tools/crosswalk_depot.py` (les sujets DataCite tirés
des valeurs et des tags), `tools/iiif_manifest.py` (les tags en `purpose: tagging`),
`tools/retirer_liens_caches.py` (sa part situation), `tools/semer_demo.py`,
`tools/fabriquer_base_de_version.py` (cf. la migration) changent. `tools/_commun.py` GARDE la
classification des cibles `tags` et `region_attribut` (`CIBLES_RETENUES`, `CIBLES_SANS_RANG`) :
le journal est append-only, ses actes d'avant restent, et le cliquet
`test_journal_publie_par_decision` exige que toute cible présente soit classée.

### Les tests

**Mesuré** (majorant, cf. la méthode) : **368 fonctions de test dans 65 fichiers** touchent le
vocabulaire, sur 3 386 comptées. Les fichiers qui partent presque entiers :
`test_tags_remaniement.py` (35 sur 37), `test_import_vocabulaire.py` (28 / 29),
`test_lexique_situe.py` (24 / 24), `test_domaines.py` (9 / 9), `test_e2e_import_vocabulaire.py`
(10 / 11), `test_e2e_tags_par_album.py` (2 / 2), `tests/js/gestes-tag.test.js`,
`tests/js/bilan-import.test.js`. Ceux qui se réécrivent en partie : `test_autorisation.py`
(49 / 105, dont les déclarations de routes), `test_bac_a_sable.py` (20 / 66),
`test_undo_miroir.py` (19 / 33), `test_amorcer.py` (16 / 44), `test_analyse.py` (15 / 32),
`test_api.py` (12 / 69), `test_personnages.py` (12 / 28), `test_annotation_partielle.py`
(8 / 8, dont la moitié porte sur la note et reste), `test_cle_tag.py` (7 / 9 : `cle_tag`
reste, ses cas sur les tags partent). Le détail est dans l'annexe.

**Le mode Annotation à lui seul : 76 tests navigateur dans 12 fichiers** (**mesuré** : ceux
qui touchent ses champs, ou passent par une aide qui l'ouvre). `test_e2e_atelier_propositions.py`
(26 / 26), `test_e2e_atelier_annotation.py` (19 / 19), `test_e2e_conflit_a_deux.py` (15 / 19),
`test_e2e_a11y.py` (4), `test_e2e_a11y_contraste.py` (2), `test_e2e_navigation.py` (2),
`test_e2e_planche_changee.py` (2), `test_e2e_tags_par_album.py` (2), et un dans
`annotation_a_deux`, `transcription_promesses`, `undo_rafraichit`, `verrou_et_annulation`.
Ils se TRIENT : ceux des tags, de la situation et du profil partent ; ceux du locuteur, des
propositions de personnages, de la note et du bandeau de CONC-3 déménagent vers la page
Annotation (où beaucoup ont déjà leur jumeau, à vérifier un par un) ou se rejouent sur la
transcription, qui a le même bandeau. `test_e2e_conflit_a_deux.py` éprouve la MACHINERIE du
conflit de l'Atelier (partir pendant l'envoi, attente vaine, 409 tardif) en passant par la
note : ces gardes ne doivent pas disparaître avec le champ qui servait à les provoquer.

### Ce que les docs disent

`CLAUDE.md` (48 lignes : § Lexique situé, § Domaines analytiques, le paragraphe `tags_concat`
de § Recherche FTS5, § Autorisation — le vocabulaire, `remaniable`, le nombre de questions —,
§ Annulation, § Schéma, la ligne de l'Atelier dans le tableau des surfaces) ;
`docs/modele-et-droits.md` (84), `docs/personnages-et-attribution.md` (78),
`docs/lexique-situe.md` (70), `docs/import-vocabulaire.md` (48), `docs/undo.md` (47),
`docs/dictionnaire-metadonnees.md` (41), `docs/guide-utilisateur.md` (37 : « Quatre modes »,
l'étape 7, la Recherche, l'Exploration), `docs/export-metadonnees.md` (28), `README.md` (28),
`docs/domaines.md` (27) — **mesuré**, mots « tag », « attribut », « situation », « profil »,
« lexique »… ; un majorant. Les notes de conception (`lexique-situe`, `domaines`,
`import-vocabulaire`, `personnages-et-attribution`) sont des traces datées : elles se marquent
« retiré par le basculement, le … » en tête, elles ne se réécrivent pas.

### Ce qui devient une grille, ce qui reste

| Aujourd'hui | Au basculement |
|---|---|
| Les tags libres | Une grille ouverte, forme simple, sur la zone — écrite par le projet qui la veut (I3) |
| La situation d'une case | Une grille à variantes sur la case ; pour les lieux, la grille « Lieux » (à écrire) |
| Le profil d'un personnage | Une grille à variantes sur l'entité — après l'étage de projet des personnages (I2) |
| Les domaines | Les rubriques d'une grille |
| Le lexique situé | Ce que porte une entrée : définition, structure, exemples, piège — la note de portée et l'état n'ont pas d'équivalent (cf. « Ce que cette note n'a pas pu établir ») |
| L'import de vocabulaire | L'import d'une grille (classeur ou CSV), et le formulaire |
| Le panneau 📖 Lexique | Le bloc « Grilles » de la fiche d'un projet et son formulaire |
| Remanier un tag (ANN-8) | Renommer, retirer, fusionner une entrée d'une grille ouverte — déjà codé |
| **Restent** | la note, le locuteur, la présence, le registre des personnages et leurs alignements, le nom d'un détail, la grammaire, les relevés, `cle_tag`, le journal entier |

---

## Entre la tranche 3 et la tranche 4

**Ce que la tranche 4 attend** (`docs/grilles-et-releves.md`, §1 et §5 ; fiche, « La
réindexation plein texte se paie une fois » et « Les relevés sortent avec leur grille et sa
version ») : l'Exploration compte les relevés (grille, rubrique, entrée, variante,
qualificatif) et croise les mots d'un passage avec les tokens du moteur en les ALIGNANT ; la
Recherche filtre « porte le relevé… » ; les exports et la voie du dépôt portent les relevés
avec leur grille et sa version (SKOS) ; le type `detail` sort. La tranche 3 ne doit casser
aucun de ces appuis : `mots.py`, les tokens et leurs corrections, le journal des relevés, les
rangs des pseudonymes (les relevés en ont depuis G10 : rien ne se renumérote), la règle
« aucun export sans titre ». Elle n'en touche aucun (**lu**).

**Une sémantique à reconstruire** : un tag posé sur une CASE comptait pour ses bulles
(`tag_scope = herite`, dans l'analyse et dans la Recherche). La grille « Lieux » vise la case ;
pour que « les bulles d'un lieu » se comptent, la tranche 4 devra redonner cette héritance aux
relevés d'une case. La tranche 3 retire le paramètre ; l'ancien code reste lisible dans
l'historique.

**Ce que montrent les deux surfaces dans l'intervalle** (si I1 est (a)) :

- **La Recherche** cherche dans les dialogues, les notes et les lemmes ; filtre par album, type
  de zone, catégorie, lemme, trait, provenance, personnage. Le nuage de tags disparaît sans
  rien à sa place (un bloc vide ne se montre pas).
- **L'Exploration** garde ses quatre vues sur les facettes grammaticales, le type, la
  provenance, l'auteur et le locuteur ; le croisement garde les axes `pos`, `morph`, `type`,
  `provenance`, `auteur`, `locuteur`. Le bouton 📖 Lexique disparaît ; 🎯 Accord et 👥 Inter
  restent.
- **Les exports** (JSON, CSV, TEI, IIIF, dépôt) portent la note, le locuteur, la présence, le
  texte — plus aucun vocabulaire. Rien ne se dépose d'ici là (`DEPOT-1` est différé).

---

## La migration v39

### Ce qu'elle fait, dans l'ordre

0. **Une vraie base v38 d'abord** (règle de Hugo du 2026-10-16 ; I9). **Mesuré** : l'outil ne
   la fabrique PAS aujourd'hui. `python tools/fabriquer_base_de_version.py 9ef3143 …` s'arrête
   à la troisième requête : `PUT /api/collections/2/acces` répond 409, « lea n'est pas du
   projet » — la règle F2 de la 3c de `COL-3` (on n'entre dans une collection que si l'on est du
   projet), née avec la v38. Le parcours gagne une branche `>= 38` (faire entrer les comptes
   dans le projet avant de leur donner un accès), et un `_parcours_v38` qui pose le vocabulaire
   partout où la migration doit le retirer : un tag global, un tag local, un tag dans un bac à
   sable (`tags.espace`), un tag renommé et un fusionné (journal `tags`), un domaine, une
   dimension de case et une de personnage, leurs valeurs, une situation, un profil, une
   annotation qui ne porte QUE des tags, une qui porte une note et un tag, un relevé, des actes
   annulables. Tout appel au vocabulaire du parcours est gardé `_VERSION < 39`, pour que le
   fichier reste refabricable après la tranche.
1. **Valider la transaction en cours** (le patron de la v30 : le pragma des clés étrangères ne
   change pas dans une transaction ; une migration qui échoue laisse la base en v38, prête à
   rejouer).
2. **Retirer les annotations vides** : `DELETE FROM annotations WHERE TRIM(COALESCE(note, ''))
   = ''` — une ligne qui ne portait que des tags. `put_annotation` supprime déjà une annotation
   sans note ni tag ; la règle reste vraie après.
3. **Détruire les tables, enfants d'abord** : `annotation_tags`, `region_attribut`,
   `personnage_attribut`, puis `attribut_valeur`, `attribut_dimension`, `domaine`, `tags`.
   Dans cet ordre, aucune destruction implicite ne rencontre une clé qui la refuse, et les
   clés peuvent rester actives (**hypothèse** à éprouver sur la vraie base : qu'aucune table
   hors de ces sept ne les référence est **lu**).
4. **Recréer l'index FTS par recopie** (I6) : une table neuve sans `tags_concat`, les lignes
   recopiées (`region_id`, `ocr_texte`, `note`, `lemmes`) sauf celles qui deviennent vides,
   l'ancienne détruite, la neuve renommée (FTS5 accepte `ALTER TABLE … RENAME`, **mesuré**).
   `_FTS_SQL` perd la colonne pour les bases neuves.
5. **Poser le plancher de Ctrl+Z** (I5) : `meta.plancher_annulation` = le plus grand
   identifiant d'`evenement` au moment de la migration ; `undo.derniere_action_annulable`
   ajoute `AND id > ?`.
6. **`PRAGMA user_version = 39`.**

Le journal n'est pas touché : append-only, il garde ses actes sur `tags`, `region_attribut`,
`annotations` (leurs charges nomment des libellés de tags), et le plancher les sort de la pile
sans rien écrire.

### Ce que la migration doit tolérer

**Une base neuve rejoue toutes les étapes de `_migrate`** (sa version vaut 0) : une étape qui
touche une table retirée doit tolérer son absence. Les étapes v17, v20, v24, v35 et v36 la
tolèrent (**lu** : `PRAGMA table_info` rend une liste vide et l'étape s'arrête, ou
`"region_attribut" in tables`).

**Une base ANTÉRIEURE à la v35, elle, planterait.** Sa table `tags` existe encore, sans
`espace` ; `_tags_par_espace` la reconstruit d'après la définition de `tags` qu'il relit dans
`SCHEMA_SQL` par une expression régulière (`re.search(r"CREATE TABLE IF NOT EXISTS tags
\((.*?)\n\);", …)`, **lu**) — qui ne trouvera plus rien une fois `tags` retirée du schéma.
Six vraies bases sont dans ce cas (v29 à v34), lues par huit fichiers de test
(`test_identifiants_v30.py`, `test_migration_v31.py` à `test_migration_v35.py`,
`test_collection_de_base.py`, `test_convertir_copies_de_travail.py`), qui migrent jusqu'à la
version courante. Deux remèdes : garder la forme v35 de `tags` dans une constante à part ; ou
sauter la reconstruction quand la table sera détruite plus loin. Le second change ce que
`test_migration_v35.py` peut vérifier (il ne verra plus `tags.espace`) : à décider au commit,
ces huit fichiers à l'appui.

### Les tests de la migration

Sur la vraie base v38 : les sept tables et leurs index ont disparu ; les identifiants
d'albums, planches, régions, personnages sont inchangés ; les notes, locuteurs, présences,
relevés, passes, doutes et grilles sont intacts, compte pour compte ; l'annotation qui ne
portait que des tags a disparu, celle qui portait une note est là, sans tags ; une recherche
par un mot du texte, par un lemme et par un mot de la note trouve ce qu'elle trouvait, un mot
qui n'était qu'un tag ne trouve plus rien ; Ctrl+Z ne rend aucun acte d'avant, et rend un acte
fait après ; la migration rejouée ne fait rien ; une base neuve s'initialise. Mutants : le
plancher retiré (le test du Ctrl+Z rougit) ; la recopie sans `lemmes` (le test du lemme
rougit) ; le `DELETE` des annotations sans sa condition (le test de la note rougit).

### Les bacs à sable et le jeu

Les tags d'un bac à sable partent avec la table ; sa grille d'exemple (H4) reste, et revient
neuve à la remise à neuf. `personnages.bac_a_sable_id` reste. Le jeu ne porte aucune
annotation (**lu** : `tools/preparer_jeu.CRANS_DU_JEU` s'arrête à la grammaire). Le vocabulaire
« à la frontière » d'un projet isolé (`_rive_d_un_terme`, la 409 de la frontière,
`_supprimer_le_vocabulaire_du_bac`) disparaît avec lui ; la frontière des personnages
(`_rive_d_un_personnage`) reste.

### La production

Au 2026-10-21 (Hugo, lecture seule) : 13 tags dont 6 locaux, posés 31 fois ; 4 dimensions,
10 valeurs, aucun domaine ; 11 attributs de case, 3 de personnage ; 330 régions. La recopie de
l'index y est instantanée. Le contrôle d'avant (I8) est dans l'annexe.

---

## Le mode Annotation de l'Atelier

Il porte aujourd'hui (**lu**, `#panel-annotation`) : le locuteur d'une zone de texte, avec le
profil et les alignements du personnage ; l'identité d'une boîte personnage, avec son profil
et ses alignements ; la situation d'une case ; les tags ; la note. Au basculement :

- le profil, la situation, les tags partent avec leurs tables ;
- le locuteur, la note et le nom d'un détail s'écrivent déjà dans la page Annotation ;
- l'identité d'une boîte et le panneau Personnage doivent s'y écrire AVANT (les deux cases
  ouvertes de la fiche) — sans quoi le retrait du mode retire le seul écran qui les écrit.

Ce que le retrait emporte aussi : le bouton du mode et sa touche (I7) ; `MODES_ATELIER` et
`?mode=annotation` (I7) ; le conflit de note de l'Atelier (le bandeau reste pour le texte) ;
le texte du wizard (« Trois modes ») et les modes en bas sur téléphone (`UX-7`) ;
`test_promesses_atelier.py` (« les quatre modes ») ; `docs/guide-utilisateur.md`, « Quatre
modes ». Le `beforeunload` de l'Atelier reste : il vaut pour tout conflit, celui du texte
compris.

---

## Les tests et les passes à prévoir

- **Les cliquets qui doivent tenir** : `test_autorisation.py` (les routes retirées sortent de
  ses listes) ; `test_sorties_identite.py` (les surfaces retirées sortent des déclarations) ;
  `test_decoupage_api.py` (le plancher des routes se dérive du source : il suit seul) ;
  `test_tables_d_annotation.py` (`region_attribut` sort de la liste) ;
  `test_journal_publie_par_decision` (les cibles d'hier restent classées) ;
  `test_echelle_ecran.py` (les mots du cran des annotations) ; `test_csp.py` (aucune surface
  ne change) ; le test du wizard (ses zones existent sur leurs surfaces).
- **Les tests neufs** : la migration (ci-dessus) ; le plancher de Ctrl+Z ; les 422 des anciens
  paramètres et champs (I7), un par route ; « annotée » (I4) ; `?mode=annotation` et la touche
  `A` qui mènent à la page Annotation.
- **Relecture croisée** : sur la migration (elle détruit sans retour) et sur le commit des
  coutures (il retire trois questions d'autorisation et une source de « qui perd quoi ») — par
  une session qui ne les a pas écrits, sur la vraie base v38. Le reste RETIRE de ce qui sort :
  il ne peut rien ouvrir, et les cliquets des sorties le tiennent.
- **Les passes longues** : navigateur entier et suite dans l'image une fois, avant la fusion.
- **Une passe de QA** à écrire dans `pilotage/qa/` au basculement livré (l'Atelier à trois
  modes, la page Annotation qui écrit l'identité d'une boîte, la Recherche et l'Exploration
  sans vocabulaire, Ctrl+Z au plancher) ; et les passes que le basculement rend sans objet
  sont à relire par le pilotage : `import-bilan-refus`, `termes-illisibles`,
  `concordance-tags`, une partie de `lot-1` et `lot-1-suite` (**mesuré** : plus de dix
  mentions du vocabulaire chacune).

---

## Le découpage

Les tables ne partent qu'en DERNIER : chaque commit retire des lecteurs pendant que les tables
existent encore, et garde la suite verte ; la migration vient quand plus rien ne les lit.
Estimations tests compris, sur le patron des deux cadrages précédents.

0. **La vraie base v38** (I9) : la branche `>= 38` et `_parcours_v38` de
   `tools/fabriquer_base_de_version.py`, les appels au vocabulaire gardés `< 39`,
   `tests/bases/v38-<commit>.sql` fabriqué depuis le commit qui précède la tranche. ½ jour.
1. **Le mode Annotation de l'Atelier** — après les deux cases du personnage dans la page
   Annotation. Le gabarit, `viewer.js`, la touche et l'adresse (I7), le wizard (« Trois
   modes »), les modes sur téléphone, le guide ; les 76 tests navigateur triés (partir,
   déménager, rejouer sur la transcription). 2 jours.
2. **Le vocabulaire hors des écrans et des routes** : les 31 routes, `lexique_import.py`,
   `routes/lexique.py`, la moitié de `routes/personnages.py`, les deux outils et le modèle CSV ;
   📖 Lexique, les facettes et les axes de l'Exploration, le nuage et le filtre de la Recherche,
   leur texte et leurs zones du wizard ; `PUT …/annotation` sans tags et les 422 (I7) ;
   « annotée » (I4) ; `gestes-tag.js`, `bilan-import.js`, le CSS. 2½ jours.
3. **Les coutures du serveur** : copies, aperçus, repartir et leurs mots (`echelle.js`) ;
   `autorisation.py` (trois questions, une source) ; `journal.py`, `undo.py` (sans le plancher),
   `empreinte.py`, la re-segmentation ; le bac à sable, la suppression d'une collection et d'un
   projet ; `TABLES_D_ANNOTATION`, `COUCHES_RECOPIEES`. Relecture croisée. 2 jours.
4. **Les sorties** : les trois exports, le manifeste IIIF, `metadonnees_collection`,
   `description_collection`, `crosswalk_depot`, `_vocabulaire_d_export` ; les cliquets des
   sorties. 1 jour.
5. **La migration v39** : les étapes ci-dessus, le plancher de Ctrl+Z, l'index recopié,
   `SCHEMA_SQL` et `_FTS_SQL` sans le vocabulaire, la v35 qui ne relit plus `tags` dans
   `SCHEMA_SQL` (les six vraies bases v29 à v34), la base neuve ; ses tests et ses mutants sur la vraie base. Relecture croisée. 1½ jour.
6. **La documentation** : `CLAUDE.md`, `docs/guide-utilisateur.md`,
   `docs/modele-et-droits.md`, `docs/undo.md`, `docs/grilles-et-releves.md` (§1, §12),
   `docs/export-metadonnees.md`, `docs/dictionnaire-metadonnees.md`, `README.md` ; les notes
   de conception marquées « retiré par le basculement ». 1 jour.

**Total : ≈ 10½ jours**, plus la demi-journée des passes longues. Préalable hors de ce
décompte : les deux cases du personnage dans la page Annotation. Ce qui ne se reporte pas : le
plancher de Ctrl+Z dans le même commit que la migration (sans lui, un Ctrl+Z d'avant écrirait
dans une table détruite : une erreur 500), et la vraie base avant la migration.

Chaque commit de code cite `ANN-7` ; la fiche se met à jour à part.

---

## Vu en passant

- **Le wizard parle du vocabulaire en cinq endroits, pas seulement des modes** (**lu**,
  `static/lib/wizard.js`) : « Quatre modes » (`atelier-modes`), « Dialogues, notes et tags »
  (`recherche-champ`), « Le nuage de tags » (`recherche-tags`, dont l'élément porte
  `data-parcours` et disparaît), « catégorie, tag, locuteur » (`exploration-sous-corpus`),
  « Les définitions du vocabulaire » (`exploration-lexique`, dont le bouton 📖 Lexique porte
  l'attribut avec les deux boutons d'accord). La case d'`UX-6` et celle de la fiche ne nomment
  que les modes.
- **`tools/fabriquer_base_de_version.py` ne fabrique plus une base de la version courante**
  (**mesuré**, ci-dessus) : la v38 a fermé les accès de collection aux comptes hors projet, et
  le parcours de la v29 en donne d'abord.
- **Le piège de la v35** (`_tags_par_espace` qui relit `SCHEMA_SQL`), ci-dessus : il tomberait
  sur toute migration d'une base antérieure à la v35, dans huit fichiers de test qui n'ont
  rien à voir avec le vocabulaire — loin de la faute.
- **Le lexique situé ne passe qu'à moitié dans une entrée** : la fiche (2026-10-14) dit que
  « le lexique situé (définition, note de portée, état) devient ce que porte une entrée » ;
  `grille_entree` porte une définition, une structure, un piège et des exemples, ni note de
  portée ni état (**lu**). La note de portée est le « situé » de SKOS ; son export (tranche 4,
  SKOS) dira s'il manque.

---

## Ce que cette note n'a pas pu établir

- **La durée d'une réindexation par le moteur** (`reindex_all`) sur la recette : non mesurée,
  et inutile si I6 est (a).
- **Que les sept tables se détruisent clés actives sur une vraie base** : lu, pas joué.
- **Le tri des 76 tests navigateur** : combien partent, combien ont déjà leur jumeau dans la
  page Annotation — non fait test par test.
- **Le coût exact d'`exploration.js`** : le découpage par fonctions est approximatif (une
  fonction va de sa déclaration à la suivante).
- **L'état de la production au 2026-11-05** : rien n'a été remesuré depuis le 2026-10-21 (I8).

---

## Annexe : les commandes de mesure

Toutes lancées dans la copie à `9ef3143`, sous Git Bash avec `MSYS_NO_PATHCONV=1`,
interpréteur `C:\Dev\BD_ditor\.venv\Scripts\python` (SQLite 3.49.1).

```sh
# Les 31 routes (32 lignes, dont une docstring de routes/personnages.py), sur 231
git grep -n -E '@(app|router)\.(get|post|put|patch|delete)\("/api/(tags|attributs|domaines|lexique)|/attributs"|/attributs/' -- main.py routes/
git grep -c -E '@(app|router)\.(get|post|put|patch|delete)\(' -- main.py routes/

# Lecteurs d'une table, hors tests et docs, puis dans les tests
T='region_attribut'   # puis annotation_tags, personnage_attribut, attribut_valeur, …
git grep -l -E "$T" -- '*.py' '*.js' ':!tests' ':!docs' ':!spike' | wc -l
git grep -h -E "$T" -- '*.py' '*.js' ':!tests' ':!docs' ':!spike' | wc -l
git grep -l -E "$T" -- 'tests/*.py' 'tests/js/*.js' | wc -l

# La vraie base v38 : l'outil s'arrête sur le 409 de la règle F2
python tools/fabriquer_base_de_version.py 9ef3143 <scratchpad>/v38.sql
```

Les tests touchés : pour chaque `tests/test_*.py`, les fonctions `test_*` (de module et de
classe) dont les lignes contiennent l'un des motifs — tables, routes, `tags_ajoutes`,
`tag_scope`, sélecteurs `#tag-input`, `#sit-input`, `#perso-attr`, mot `attributs`, fonctions
de portée des termes, `lexique` — comptées par `ast`. Le mode Annotation : les mêmes, avec les
motifs `data-mode="annotation"`, `#panel-annotation`, `#note-input`, `#loc-input`,
`#perso-input`, `setMode`, et toute aide du fichier qui en contient un (`_ouvrir`), suivie
jusqu'aux tests qui l'appellent. L'index : une table FTS5 de cinq colonnes remplie de N lignes
synthétiques, recopiée dans une table de quatre colonnes, l'ancienne détruite, la neuve
renommée, puis interrogée sur un mot du texte (trouvé N fois) et sur un ancien tag (0 fois).

Le contrôle de la production (I8), en lecture seule :

```sh
sqlite3 'file:/chemin/de/la/base.sqlite?mode=ro' "
SELECT (SELECT COUNT(*) FROM tags)                AS tags,
       (SELECT COUNT(*) FROM annotation_tags)     AS tags_poses,
       (SELECT COUNT(*) FROM region_attribut)     AS situations,
       (SELECT COUNT(*) FROM personnage_attribut) AS profils,
       (SELECT COUNT(*) FROM attribut_valeur)     AS valeurs,
       (SELECT COUNT(*) FROM domaine)             AS domaines,
       (SELECT MAX(date) FROM evenement
         WHERE agent_type = 'humain'
           AND cible_table IN ('tags', 'region_attribut')) AS dernier_geste,
       (SELECT COUNT(*) FROM annotations a
         WHERE a.date_modification > '2026-10-21'
           AND EXISTS (SELECT 1 FROM annotation_tags t
                        WHERE t.annotation_id = a.id))    AS taguees_depuis;"
```

Une pose de tag s'écrit au journal sous `annotations`, avec la note, d'où la dernière colonne ;
un profil n'est pas journalisé (`personnage_attribut`, **lu**) : seul son compte le dit.
