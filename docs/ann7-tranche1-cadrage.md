# ANN-7, tranche 1 — le modèle des grilles, sans écran : cadrage

Rendu le 2026-10-25, sur la copie d'intégration `integ` à `e0afc86` (`dev` + la 3b de
`COL-3` : schéma **36** — v35 de `COL-4`, v36 de la 3b). Rien n'est codé ni exécuté. Ce qui
est marqué **lu** a été lu dans le code à ce commit ; ce qui est marqué **supposé** ne l'a
pas été, ou reste à mesurer. Les propositions sont numérotées **R1 à R13** ; chacune dit
*proposé / pourquoi / ce que ça coûte / ce qui reste à trancher*. Les décisions qui restent à
Hugo sont numérotées **G1 à G20**, en fin de note.

Cette note RÉCONCILIE deux sources qui ne se citent pas encore : `docs/grilles-et-releves.md`
(la note du modèle, validée le 2026-10-14) et les décisions prises depuis — la séance de
conception du 2026-10-22 (`pilotage/ANN-7.md`, zone « Tranché par Hugo — 2026-10-22, la
séance de conception », Q1 à Q9) et la revue de la maquette v3 (`pilotage/ANN-6.md`, zone
« Tranché par Hugo — 2026-10-22, sur la maquette v3 »). Quand la note du 2026-10-14 et une
décision du 2026-10-22 divergent, c'est la décision qui est suivie, et l'écart est dit. La
note du modèle sera mise à jour au premier commit de la tranche (case « La note est à jour
des décisions du 2026-10-22 » d'`ANN-7`) ; celle-ci ne la remplace pas, elle descend jusqu'aux
tables, aux routes et aux gardes.

Le dépôt est public : aucune grille réelle n'est citée ici. Les exemples sont fictifs.

---

## Ce que la tranche 1 livre, en gestes

Sans écran : par l'outil en ligne de commande et par des routes, que la tranche 2 (la page
Annotation) consommera.

1. **Importer une grille** — un responsable de projet donne un tableur ; BD_ditor le vérifie
   entier, rend un BILAN (ce qui naît, ce qui change, ce qui disparaît depuis la dernière
   version publiée) et le garde en BROUILLON. À blanc d'abord, pour lire le bilan sans rien
   écrire. Réimporter le même fichier ne change rien.
2. **Publier une version** — le brouillon devient une version figée, numérotée.
3. **Activer une grille sur le projet**, dans une version publiée ; la désactiver. Une
   collection du projet peut MASQUER une grille active (un réglage d'affichage, Q1).
4. **Poser un relevé** sur une cible — des mots d'une zone de texte, une région entière, la
   planche (la surface) — avec sa variante ou ses qualificatifs, une précision, un lien vers
   une autre région ; le modifier ; le retirer ; Ctrl+Z.
5. **Douter** d'un relevé, répondre, lever le doute.
6. **Marquer une zone « terminée »** pour une grille, ou une rubrique ; la rouvrir.
7. **Réexporter** une version au format du tableur, identifiants compris.

Ce que la tranche 1 ne livre pas : aucun écran (ni la page Annotation, ni le bilan à l'écran,
ni le guide produit depuis la grille) ; ni le catalogue (« Partager », activer une grille d'un
autre projet), ni la montée de version d'un projet, ni la dérivation ; ni le basculement des
tags et des attributs (tranche 3, Q3 : vocabulaire neuf, sans conversion) ; rien dans la
Recherche, l'Exploration ou les exports (tranche 4) ; la cible `entite` reste refusée tant
que les personnages n'ont pas leur étage de projet (Q4, G3) ; le type de région `detail` vient
avec l'écran qui le trace (G17).

---

## Ce qui existe déjà (lu)

### Le vocabulaire d'aujourd'hui, et comment il coexiste

- **Les tags** (`tags`, `annotation_tags` par `annotations`, une par région) : un libellé
  libre, unique PAR ESPACE depuis la v35 (`tags.espace` : 0 pour l'instance, l'id d'un bac à
  sable sinon ; `idx_tags_espace_label`), une portée (`collection_id`, NULL = global), la
  couche du lexique situé (définition, note de portée, état). Posés par
  `socle._ensure_tags`, qui refuse un tag local hors des albums de sa collection (ANN-8).
  Remaniés par `routes/lexique.py` (`peut_remanier_tag`).
- **Les attributs** : `domaine` → `attribut_dimension` (`cible` = `personnage` | `case`,
  `UNIQUE(cible, nom)` dans toute l'instance) → `attribut_valeur` ; posés sur une région par
  `region_attribut` (journalisés en `lien` sous `region_attribut`, `routes/personnages._affecter`)
  et sur un personnage par `personnage_attribut` (non journalisés).
- **L'import du vocabulaire** (`lexique_import.py`, `tools/importer_vocabulaire.py`,
  `POST /api/lexique/importer`) : un CSV point-virgule, une ligne par valeur, idempotent,
  « pré-remplir sans écraser », une ligne fautive ÉCARTÉE et signalée, une portée obligatoire
  (`_refus`, trois passes). Refusé dans un bac à sable (409 nommé : les noms de domaines et de
  dimensions sont uniques dans l'instance).
- **Les personnages** : `personnages` (registre, `bac_a_sable_id` depuis la v35), visibles par
  leurs apparitions (`socle._clause_personnage`) ; `bulle_locuteur`, `personnage_presence`.
- **Les mots** : `tokens` (spaCy, régénérés à chaque réindexation, absents sans moteur) ;
  `token_correction`, couche humaine qui survit aux réindexations par
  `database._reancrer_corrections` (difflib entre l'ANCIENNE tokenisation, encore en base, et
  la nouvelle ; un mot disparu part à un `ordre` négatif, `obsolete = 1`) ; la vue
  `tokens_effectifs`, read model canonique.

**Aucun objet « grille » n'existe** (lu : ni table, ni route). La tranche 1 ne touche à RIEN
de ce qui précède : une région peut porter, en même temps, une annotation (note, tags), des
attributs, un locuteur et des relevés. Les tags et attributs continuent de vivre jusqu'au
basculement (tranche 3), qui les retire sans les convertir (Q3) ; d'ici là, les stagiaires
n'en posent pas (Q9). Ctrl+Z remonte indifféremment les deux sortes d'actes, dans l'ordre du
journal.

### Les mécanismes sur lesquels la tranche s'appuie

- **Le conflit nommé** (`conflit.py`, CONC-3) : l'écran envoie la VALEUR qu'il a vue
  (`vu`) ; sous `conflit.verrouiller` (`BEGIN IMMEDIATE`), `conflit.verifier` lève `Perime`
  si la base porte autre chose, et le 409 nomme l'auteur lu au journal. **Le module refuse
  explicitement une colonne de version** — « chaque écrivain doit l'incrémenter, un oubli
  reste muet » (sa docstring). Cf. G1.
- **L'annulation** (`undo.py`) : liste blanche `_TABLES` (`regions`, `annotations`,
  `bulle_locuteur`, `personnage_presence`) et `_TYPES` ; gardes d'AUTH-14 (`_meme_objet`, qui
  suppose que `cible_id` est une RÉGION pour tout acte autre qu'une suppression de région ;
  `lieux` + `ecrivable` obligatoire) ; cinquième témoin de la 3b
  (`planches_remises_a_zero`) ; un acte qui ne s'annule plus est PASSÉ (`ecarter`, trace
  `abandon` sous `annulation`) ; ANN-8 : l'annulation ne crée jamais de terme
  (`_tag_a_rendre`) et ne réécrase pas un lien posé depuis (`_garder_liens_du_type`).
- **L'instantané profond** (`journal.snapshot_region_profond`) : colonnes, annotation, liens
  (locuteur, présence, attributs), enfants — le substrat de Ctrl+Z après une suppression.
- **Le journal et la sortie** : `evenement.avant` / `apres` sont RETENUS de tout export
  (`tools/_commun.COLONNES_JOURNAL_RETENUES`) ; toute `cible_table` est classée publiée ou
  retenue (`CIBLES_CORPUS` / `CIBLES_RETENUES`, cliquet `test_journal_publie_par_decision`) ;
  `CIBLES_SANS_RANG` (aujourd'hui `document`, `collection_album`, `demande`,
  `region_attribut`, `tags`).
- **« Personne d'autre n'y a travaillé »** (`autorisation._sources_du_travail`) : six sources
  — le journal des régions de l'album sous `_CIBLES_DE_REGION`, les attributs sans `lien`
  humain, les corrections (`auteur`), les validations de planches (`cible_table = 'planches'`),
  les actes sur le document, et le travail RECOPIÉ par la chaîne de `region_origine` (une
  couche d'annotation n'y compte qu'au cran `annotations` et si elle VIT, `_SQL_COUCHE_VIT`).
  Lue par `clause_suppression_directe`, `clause_repartir_directe`, `sql_actes_sur_album`, et
  par `destructible` de `GET /api/albums`.
- **Les copies** (`database.copier_le_travail`, 3b) : cinq crans ; au cran `annotations`,
  annotations, tags visibles depuis l'arrivée (E5, les autres comptés dans `laisses`),
  attributs, locuteurs, présences ; l'auteur d'une correction NE SUIT PAS entre deux projets
  (Hugo, 2026-10-25, constat 3 de la relecture de la 3b) ; `compter_le_travail` pour l'aperçu.
- **Repartir de zéro** (`database.repartir_de_zero`, `socle._repartir`) : retire table par
  table ce qui est au-dessus du cran d'arrivée.
- **Détruire** (`socle._detruire_album`) : seul chemin, garde sous le verrou,
  `DELETE FROM albums` en CASCADE sur planches et régions.
- **Les passes ML qui remplacent** : `segmentation.segment_planche(replace=True)` supprime une
  ancienne case Kumiko qui ne porte ni annotation ni correction (le critère `preserved`) ;
  `bulles` supprime une bulle `auto` vide et sans annotation. **Ni l'un ni l'autre ne regarde
  `region_attribut`** : une case Kumiko qui ne porte qu'une situation est supprimée à la
  re-segmentation, et sa situation avec elle (lu, non rejoué ; cf. G20).
- **Le bac à sable** (COL-4) : la « rive » d'un terme (`socle._rive_d_un_terme`), aucune
  question transverse ouverte par un bac (`_ecriture_hors_bac`), `sql_acte_isole` (ce qui vit
  ou a vécu dans un projet isolé ne compte pas dans `comptes.traces`), la portée totale
  BORNÉE (`couvre`, `couvre_projet`), `socle._effacer_bac_a_sable`.

### Ce qui n'existe pas (lu)

Aucune route ne FUSIONNE deux régions (les seules fusions sont celles des tags, des
personnages et des valeurs) ; l'ASSEMBLAGE d'une double page (`IMG-2`) n'est pas codé ; le type
`detail` n'est pas dans `config.TYPES_REGION`. Les décisions qui les concernent (« la fusion de
deux régions réunit leurs relevés », Q5) n'ont donc pas de site dans la tranche 1 : elles
s'écrivent ici pour le chantier qui créera ces gestes.

---

## R1 — La migration v37 : seize tables neuves, une colonne

**Proposé.** La v37, additive : aucune donnée existante n'est touchée. Toute table neuve porte
`AUTOINCREMENT` (la règle de la v30 : le journal les nommera, et un identifiant rendu au
suivant mêlerait deux objets), et les commentaires de la dernière colonne s'écrivent SOUS elle
(la règle de SQLite 3.49). Aucun `CHECK` : les listes vivent dans le code, pour la raison
écrite sur `utilisateur.nature`.

```
-- Le vocabulaire : une grille, ses versions, et l'instantané complet de chaque version.
grille(id, projet_id NOT NULL → projet (sans action), nom NOT NULL, ouverte INTEGER
       NOT NULL DEFAULT 0, retiree_le, cree_par, date_creation)
grille_version(id, grille_id NOT NULL → grille ON DELETE CASCADE, numero NOT NULL,
       etat NOT NULL,          -- 'brouillon' | 'publiee' | 'vivante' (grille ouverte)
       cible,                  -- « Porte sur » : la cible par défaut de ses entrées
       note, empreinte, importee_par, importee_le, publiee_par, publiee_le,
       UNIQUE(grille_id, numero))
grille_rubrique(id, version_id → grille_version CASCADE, cle, libelle, parent_cle, rang,
       UNIQUE(version_id, cle))
grille_entree(id, version_id CASCADE, cle, rubrique_cle, rang, forme, libelle, definition,
       structure, piege, precision, lien INTEGER, cible, cardinalite, liste_cle,
       retiree INTEGER NOT NULL DEFAULT 0, UNIQUE(version_id, cle))
grille_variante(id, version_id CASCADE, entree_cle, cle, libelle, definition, structure,
       piege, rang, UNIQUE(version_id, entree_cle, cle))
grille_liste(id, version_id CASCADE, cle, libelle, UNIQUE(version_id, cle))
grille_qualificatif(id, version_id CASCADE, liste_cle, cle, libelle, definition, rang,
       UNIQUE(version_id, liste_cle, cle))
grille_exemple(id, version_id CASCADE, entree_cle, variante_cle, rang, texte, releve_id)

-- Où elle sert.
projet_grille(projet_id → projet CASCADE, grille_id → grille, version_id → grille_version,
       active_par, active_le, PRIMARY KEY(projet_id, grille_id))
collection_grille_masquee(collection_id → collection CASCADE, grille_id → grille CASCADE,
       masque_par, masque_le, PRIMARY KEY(collection_id, grille_id))

-- Ce qu'on pose.
releve(id, region_id → regions ON DELETE CASCADE, planche_id → planches (SANS action),
       grille_id NOT NULL → grille, version_id NOT NULL → grille_version,
       entree_cle NOT NULL, variante_cle, precision, lien_region_id, lien_texte,
       texte_ancre, une INTEGER NOT NULL DEFAULT 0, origine_id,
       auteur, cree_le, modifie_par, modifie_le)
releve_mot(releve_id → releve CASCADE, position, rang, forme NOT NULL,
       PRIMARY KEY(releve_id, position))
releve_qualificatif(releve_id → releve CASCADE, qualificatif_cle,
       PRIMARY KEY(releve_id, qualificatif_cle))
doute(id, releve_id → releve CASCADE, ouvert_par, ouvert_le, leve_par, leve_le, issue)
doute_message(id, doute_id → doute CASCADE, auteur, date, texte NOT NULL)
passe(id, region_id → regions CASCADE, planche_id → planches (SANS action),
       grille_id NOT NULL → grille, version_id, rubrique_cle NOT NULL DEFAULT '', par, le)

-- Et une colonne : regions.nom (le nom libre d'un détail, NULL pour les autres types, G17).
```

Les index : `releve(region_id)`, `releve(planche_id)`, `releve(grille_id)`, `passe(region_id)`,
`passe(planche_id)`, et deux index UNIQUES partiels — `releve(COALESCE(region_id, 0),
COALESCE(planche_id, 0), grille_id, entree_cle) WHERE une = 1` (la cardinalité, R5) et
`passe(COALESCE(region_id, 0), COALESCE(planche_id, 0), grille_id, rubrique_cle)` (une passe
par zone, grille et rubrique ; `rubrique_cle` vaut `''` pour toute la grille, parce qu'un
`NULL` n'entre pas dans une unicité SQLite).

**Ce que chaque clé fait à la suppression de sa cible :**

| Clé | À la suppression de la cible | Pourquoi |
|---|---|---|
| `releve.region_id`, `passe.region_id` | CASCADE | « Supprimer une région supprime ses relevés, Ctrl+Z les rend » (note §11, case « Les champs d'un relevé ») |
| `releve.planche_id`, `passe.planche_id` | AUCUNE action : la suppression d'une planche qui en porte ÉCHOUE | Q5 : jamais de CASCADE sur la planche. Une FK sans action fait échouer BRUYAMMENT tout chemin qui oublierait les relevés de surface (une `IntegrityError`, un 500) — l'erreur se ferme au lieu d'effacer en silence. Les chemins qui suppriment une planche les retirent d'abord (R11) |
| `releve.grille_id`, `releve.version_id` | AUCUNE action | Une grille qui porte des relevés ne se supprime pas (« la suppression suit l'emploi ») ; le refus est nommé avant la FK |
| `releve.lien_region_id` | PAS de clé étrangère | Le relevé reste quand la région désignée disparaît, et Ctrl+Z de la suppression le rattache (case « Un lien dont la région désignée disparaît ») ; les identifiants de région ne reviennent plus depuis la v30, donc l'identifiant gardé ne désignera jamais une autre région |
| `releve.origine_id`, `grille_exemple.releve_id` | PAS de clé étrangère | Le patron de `region_origine` et de `evenement.cible_id` : la source peut mourir avant |
| `grille.projet_id` | AUCUNE action | Un projet qui possède une grille ne se supprime pas sans qu'on le décide (G18) |
| `releve` → `doute` → `doute_message` | CASCADE | Le doute porte sur UN relevé (note §8) ; le journal garde le fil |

**Aucun `collection_id` sur un relevé ni sur une passe** (Q1 : le relevé tient à sa cible).
**Aucune colonne neuve sur `albums` ni `planches`** : le cliquet des colonnes de ces deux tables
n'a rien à classer. `regions.nom` est la seule colonne ajoutée à une table existante.

**La vraie base.** La v37 se vérifie sur une VRAIE base v36 (la règle du 2026-10-16) :
`tools/fabriquer_base_de_version.py <tête de dev après la 3b> tests/bases/v36-<commit>.sql`,
qui gagne une branche `SCHEMA_VERSION >= 36` posant ce que la v37 doit traverser — des régions
des cinq types, des textes à apostrophes et à tirets, deux copies sœurs dont une amorcée au cran
`annotations`, un bac à sable, une planche détruite en haut de table. **Supposé** : la 3b
fusionnée avant ANN-7 ; si l'ordre change, ce numéro et celui de la version précédente
suivent. Le test de migration (patron `tests/test_migration_v31.py`) exige que les tables neuves
soient vides et que RIEN d'autre ne change.

**Pourquoi.** Les champs du relevé sont ceux que Hugo a arrêtés le 2026-10-22 (case « Les
champs d'un relevé »), avec trois écarts dits : le doute et la passe sont des tables à part
(un relevé peut avoir un fil ; une passe ne tient à aucun relevé) ; l'état n'est pas une
colonne (R5, G2) ; la version de ligne non plus (R9, G1).

**Ce que ça coûte.** Seize tables, deux index partiels, une colonne ; une vraie base à
fabriquer ; un test de migration. Aucune reconstruction de table.

**Reste à trancher.** G1, G2, G3, G17, G18.

## R2 — La grille, ses versions, son plan

**Proposé.**
- **La grille** appartient à un projet (`grille.projet_id`), porte un nom UNIQUE DANS SON
  PROJET (tenu par le code sous le verrou : pas d'unicité d'instance, donc aucun oracle
  « ce nom est pris ailleurs » — l'écueil des domaines et des dimensions), est ouverte ou
  fermée. « Brouillon / en usage » se DÉRIVE (une version publiée existe ou non) ; seule la
  retraite est écrite (`retiree_le`).
- **Une version est un INSTANTANÉ COMPLET** (note §6, tranché le 2026-10-14) : ses rubriques,
  entrées, variantes, listes, qualificatifs et exemples sont des lignes à elle, désignées
  entre elles par leur `cle` et jamais par leur `id` — copier une version, c'est recopier des
  lignes sans renuméroter de références. Une version `publiee` ne se modifie plus, sauf la
  coquille (définition, exemples, piège : « Une coquille se corrige à l'écran », tranché le
  2026-10-22), par un responsable, sans nouvelle version, au journal.
- **Une grille FERMÉE** : au plus un brouillon à la fois ; le publier lui donne le numéro
  suivant. Réimporter sur un brouillon le remplace ; réimporter quand la dernière version est
  publiée crée un brouillon neuf — sauf si son empreinte est celle de la version publiée
  (« aucun changement », rien n'est créé).
- **Une grille OUVERTE** (« propre à son projet, sans version publiée, NON partageable tant
  qu'on ne la fige pas », tranché le 2026-10-22) : UNE version, `vivante`, qui s'enrichit en
  place. On y ajoute une entrée EN LA POSANT (R5, G14), comme un tag libre aujourd'hui ;
  renommer, fusionner, supprimer une entrée (les gestes d'ANN-8, « par les responsables du
  projet ») viennent avec le basculement des tags libres (tranche 3), seul usage qui les
  demande.
- **Les cibles** qu'une version ou une entrée déclare : `mots` · `bulle` · `cartouche` ·
  `texte` · `case` · `personnage` (la BOÎTE, une région) · `detail` · `planche` (la SURFACE,
  `IMG-2`, 2026-10-16) · `entite` (le registre, Q4). Neuf sortes ; la note §4 en avait huit
  avant Q4. Une entrée sans `cible` prend celle de sa version (« Porte sur ») ; une entrée qui
  déclare la sienne se pose d'elle-même sur elle (case « Une entrée peut déclarer sa propre
  cible »). `detail` et `entite` s'importent (ce sont des données) mais aucun relevé ne s'y
  pose en tranche 1 (G3, G17).
- **Les formes** : `simple` · `variantes` · `qualificatifs`, et ce que chacune COMPTE est
  écrit dans le modèle du tableur et sa documentation — un relevé à qualificatifs compte UNE
  fois son phénomène (case « Une entrée à qualificatifs compte comme les linguistes
  comptent » : le modèle ne change pas, la grille des linguistes écrira l'emphase par
  manière).

**Pourquoi.** L'instantané par `cle` est ce qui rend la montée de version (tranche ultérieure)
une affaire de `version_id` et de bilan, sans reconstituer un état passé. Le nom unique par
projet évite le défaut connu du vocabulaire actuel (des noms uniques dans l'instance, d'où le
refus de l'import dans un bac à sable).

**Ce que ça coûte.** Le cœur `grilles.py` (lecture du plan, empreinte, copie d'une version) ;
huit tables de plan.

**Reste à trancher.** G14 (l'entrée d'une grille ouverte), G15 (la coquille dès la tranche 1).

## R3 — Le tableur, l'import, le bilan

**Proposé.**
- **Le format** — celui de la note §7, plus les deux colonnes nées le 2026-10-22. Un CSV
  point-virgule, UTF-8 avec ou sans BOM, en-tête obligatoire, lecture par nom de colonne (le
  patron de `lexique_import.lire`). Une ligne par entrée, une ligne par variante :

  | Colonne | Rôle |
  |---|---|
  | `cle` | identifiant stable de l'entrée (obligatoire) |
  | `rubrique` | chemin, du plus large au plus fin : `3 Morphosyntaxe > Verbe` |
  | `rubrique_cle` | identifiants des étages du chemin, même nombre d'étages, même séparateur |
  | `forme` | `simple` · `variantes` · `qualificatifs` |
  | `libelle` | ce qu'on lit |
  | `variante_cle`, `variante` | une ligne par variante, sous la ligne de son entrée |
  | `structure`, `definition`, `exemples`, `piege` | la ligne du guide — de l'entrée, ou de la variante sur sa ligne |
  | `liste` | la `cle` de la liste de qualificatifs d'une entrée à qualificatifs |
  | `precision` | le libellé d'une précision libre, vide sinon |
  | `lien` | `oui` pour une entrée qui désigne une autre région |
  | `cible` | facultative : la cible propre de l'entrée (tranché le 2026-10-22) |
  | `cardinalite` | facultative : `une` · `plusieurs` ; vide, le défaut de la cible (Q6) |

  Un second CSV, facultatif, pour les **listes de qualificatifs** : `liste_cle` ; `liste` ;
  `cle` ; `libelle` ; `definition`. La **déclaration** de la grille (nom, ouverte ou fermée,
  « Porte sur », note de version) passe en arguments de l'outil et en champs du formulaire de
  la route : quatre valeurs ne justifient pas un troisième fichier. `exemples` : plusieurs
  exemples séparés par ` | ` dans la cellule. Pas de XLSX : `openpyxl` n'est que dans
  `requirements-export.txt`, hors du noyau (lu) — G13.
- **La validation refuse le fichier ENTIER** à la première anomalie de structure, et les
  liste toutes : `cle` vide ou dupliquée, forme inconnue, variante sans entrée à variantes
  au-dessus, entrée à variantes sans variante, `liste` inconnue, qualificatif sans liste,
  cible ou cardinalité inconnue, chemin de rubrique et `rubrique_cle` incohérents (deux
  libellés pour une même `cle` de rubrique, ou l'inverse), `parent_cle` circulaire. C'est
  l'inverse de `lexique_import`, qui ÉCARTE une ligne fautive : une version est un tout figé, et
  une ligne écartée se lirait dans le bilan comme une entrée DISPARUE (G12). Les divergences
  qui ne cassent rien (deux définitions pour une même rubrique) sont des avertissements, la
  première retenue — le patron de `lexique_import._divergence`.
- **Le bilan** compare au plus récent état publié de la grille, par `cle` : entrées, rubriques,
  variantes et qualificatifs NÉS ; RENOMMÉS (même `cle`, autre libellé) ; définitions,
  structures, exemples et pièges retouchés ; DÉPLACÉS (autre rubrique) ; formes, cibles et
  cardinalités CHANGÉES ; DISPARUS, chacun avec le nombre de relevés posés sur lui dans le
  projet. Sans relevé sur la grille (le cas de toute la tranche 1 avant les premiers
  stagiaires), les disparitions ne coûtent rien ; avec, le bilan les nomme, et la décision
  « retirer, ou fusionner dans… » attend la montée de version, qui n'existe pas en tranche 1
  (note §6) : les relevés restent sur la version où ils ont été posés.
- **L'idempotence** : l'empreinte d'une version (SHA-256 du contenu normalisé : lignes triées
  par `cle`, cellules nettoyées) ; même empreinte, aucun changement écrit.
- **Deux enveloppes d'un même cœur** (le patron de `lexique_import`) : `grille_import.py`
  (lire, valider, comparer, écrire ; reçoit un flux et une connexion, aucune I/O),
  `tools/importer_grille.py` (`--projet`, `--grille` pour une version suivante, `--nom`,
  `--ouverte`, `--porte-sur`, `--note`, `--a-blanc` ; codes de retour 0 / 1 / 2 du patron
  `importer_vocabulaire`) et `POST /api/projets/{id}/grilles/import` (multipart ; `a_blanc`
  rend le bilan sans écrire). L'outil passe `autorisation.TOTALE` et un agent vide au journal
  (« un shell n'a pas d'identité », le patron de `gerer_collections.py`).
- **Le réexport** : `GET /api/grilles/{id}/versions/{numero}/tableur` rend les deux CSV
  (un zip), identifiants compris — le chemin de la DÉRIVATION allégée (réexporter, réimporter
  comme grille de son projet, tranché le 2026-10-22). Réservé à qui gère le projet de la
  grille. C'est un fichier qui sort : le cliquet de `tests/test_droit_export.py` exige de le
  DÉCLARER — hors du droit d'export (DROIT-2 borne le CORPUS ; une grille est un vocabulaire,
  et son plan ne porte aucune transcription) — G16.
- **La grille de test est SYNTHÉTIQUE** : `tools/grille-modele.csv` (+ sa liste), fictive,
  le pendant de `tools/vocabulaire-modele.csv`, qui fait jouer les trois formes, deux listes
  partagées, une entrée à cible propre, les deux cardinalités, une précision, un lien, trois
  étages de rubriques ; les tests lisent des variantes de ce fichier dans `tests/grilles/`.
  **La grille réelle n'entre jamais dans le dépôt.**
- **Où vit la vraie grille — à demander.** Lu : elle n'existe aujourd'hui qu'en PDF, extrait
  du guide des linguistes, hors du dépôt (`C:\temp\maquette-ann6\guide-pages-6-18.pdf`, dossier
  de la première maquette) ; AUCUN tableur n'existe. Le constituer est une tâche : transcrire
  les sept niveaux dans le format ci-dessus, AVEC les `cle` dès la première importation —
  sans elles, chaque renommage ultérieur se lirait comme une suppression suivie d'un ajout
  (« ce qui coûterait cher à défaire », `ANN-7`). Qui le fait, où il vit (un dossier du poste
  hors dépôt, et la production), qui le relit avec les linguistes : G19. Les six écarts du
  guide relevés le 2026-10-12 (case « Le guide ne donne qu'UNE forme par tag » d'`ANN-6`)
  sont à régler AVANT, sinon ils deviennent six paires d'entrées.

**Pourquoi.** Le refus entier et le bilan avant publication sont ce que la note §7 demande, et
ce qui protège une grille qu'on ne peut plus modifier en place une fois publiée.

**Ce que ça coûte.** Un cœur pur et sa table de tests, un outil, une route, deux fichiers
modèles. **Supposé** : l'import de la vraie grille (une centaine d'entrées, deux cents
variantes et combinaisons) se fait sous la seconde.

**Reste à trancher.** G12, G13, G16, G19.

## R4 — L'activation, et le masque par collection

**Proposé.**
- **L'activation** (`projet_grille`) : une grille active une fois par projet, dans UNE version
  (`publiee` pour une grille fermée, `vivante` pour une ouverte). `PUT
  /api/projets/{id}/grilles/{gid}/activation {version}` / `DELETE`. Dans la tranche 1, un
  projet n'active que SES grilles (le catalogue n'existe pas) ; changer la version d'une
  activation qui porte des relevés est la montée de version, refusée (409 nommé) jusqu'à la
  tranche qui l'écrit. **Désactiver ne retire rien** : les relevés restent, en LECTURE (case
  « Désactiver une grille dans un projet ne supprime aucun relevé ») — le serveur refuse
  alors toute écriture sur eux (409 nommé : « cette grille n'est plus active dans le
  projet ») ; Ctrl+Z aussi (R10).
- **Le masque** (`collection_grille_masquee`) : une collection du projet MASQUE une grille
  active (Q1, « Paratexte n'affiche que les tags libres »). On stocke le masque et non la
  liste des grilles montrées : une grille activée ensuite se montre partout par défaut. **Un
  filtre d'écran, pas une garde** : aucune route de relevé ne le lit ; `GET` de la collection
  le rend, la page Annotation l'applique (onglets cachés, relevés des grilles masquées en
  gris, ANN-6 2026-10-22). `PUT` / `DELETE /api/collections/{id}/grilles-masquees/{gid}`, au
  propriétaire de la collection (G7).

**Pourquoi.** Q1 : le projet stocke, la collection restreint l'affichage. Un relevé posé sur un
album rangé dans deux collections du projet se voit par l'une et par l'autre, masque ou non.

**Ce que ça coûte.** Deux tables, quatre routes.

**Reste à trancher.** G7.

## R5 — Le relevé

**Proposé.**
- **UNE cible parmi trois en tranche 1** — `region_id` (une région entière, ou des mots d'une
  zone de texte, alors avec ses `releve_mot`) ou `planche_id` (la surface) ; exactement une des
  deux colonnes est remplie, tenu par le code (pas de `CHECK`). L'entité (Q4) prendra une
  troisième colonne, ajoutée par `ALTER` avec son étage de projet (G3).
- **Les gardes de la pose**, dans cet ordre : la cible s'atteint EN ÉCRITURE par l'accesseur
  gardé (`_get_region` / `_get_planche`, `ecriture=True` : 404 sinon) ; la grille est ACTIVE
  dans le projet de l'album (`sql_projet_d_album`) — 409 nommé sinon ; la version envoyée est
  celle de l'activation — 409 nommé sinon (l'écran a vu une autre version) ; l'entrée existe
  dans cette version et n'est pas retirée — 422 ; la cible convient à l'entrée (le type de la
  région est dans la cible déclarée, `mots` demande une zone `bulle` · `cartouche` · `texte`
  et au moins un mot) — 422 nommé ; la forme est respectée (une variante de cette entrée pour
  une entrée à variantes, des qualificatifs de SA liste, rien de cela pour une simple) — 422 ;
  le lien désigne une région du MÊME ALBUM (G4) qu'on lit — 404 sinon, qui ne dit pas si elle
  existe ailleurs.
- **La cardinalité** (Q6) : `une` ou `plusieurs`, déclarée par l'entrée ; vide, `plusieurs`
  sur des mots, `une` sur une région entière, la planche ou l'entité. Elle est FIGÉE sur le
  relevé à la pose (`releve.une`) — c'est ce que lit l'index unique partiel. Un second relevé
  d'une entrée `une` sur la même cible est refusé par un 409 qui rend le relevé existant (son
  identifiant, sa variante, son auteur) : c'est la forme du conflit que l'écran montre
  (« Remplacer par la mienne » = modifier CE relevé, avec `vu`, R9). La relecture se fait sous
  `conflit.verrouiller` ET l'index la tient (le patron du bac à sable : un par login, index
  partiel et relecture sous le verrou) : deux poses simultanées n'en font jamais deux.
- **Le lien** : `lien_region_id` + `lien_texte` (le texte de la région désignée AU MOMENT DU
  LIEN, gardé pour le jour où elle disparaît : « garde le texte de la région qu'il désignait »).
- **La précision** : un texte court (`precision`), offert seulement si l'entrée le déclare.
- **L'état n'est pas une colonne : il se DÉRIVE** (G2), à un seul endroit — une vue
  `releves_effectifs`, recréée au démarrage comme `tokens_effectifs`, read model canonique de
  toutes les routes :
  - **à revoir** si un mot du passage a disparu (`releve_mot.rang IS NULL`, R6) ; si la région
    liée n'existe plus (`lien_region_id` non nul sans région) ; si le texte de la région n'est
    plus celui de l'ancrage (`texte_ancre` différent de `ocr_texte` : une réindexation
    manquée, détectée au lieu d'être crue) ; si le type de la région ne convient plus à
    l'entrée (G8) ;
  - **à compléter** si l'entrée attend une précision ou un lien et que le relevé n'en porte
    pas (la seconde cause tranchée sur la maquette v3) ; la première cause, un changement de
    forme entre versions, n'existe pas avant la montée de version ;
  - **normal** sinon.
  Chaque cause se répare par un geste qui la supprime : redésigner le passage, choisir un
  autre lien ou le retirer, remplir la précision, repasser la région à son type. Ctrl+Z d'une
  suppression de région rend la région liée, et le relevé redevient normal sans rien écrire —
  ce que la décision du lien demande.
- **La provenance** : `auteur`, `cree_le`, `modifie_par`, `modifie_le` (« l'auteur, les dates
  de création et de modification ») ; `origine_id` : le relevé source d'un relevé recopié
  (R11), le patron de `region_origine` — c'est par lui que la tranche 4 comparera deux sœurs.
- **Ajouter une entrée à une grille OUVERTE** se fait en posant : `POST /api/releves` avec
  `nouvelle_entree: {libelle}` au lieu d'`entree_cle` — la `cle` est dérivée du libellé (le
  patron de `database.cle_tag`), l'entrée naît dans la version `vivante`, journalisée sous la
  grille (G14). Sans région à écrire, pas d'entrée neuve : c'est ce qui borne qui enrichit.

**Pourquoi l'état dérivé.** Les causes sont toutes lisibles dans les données : les stocker
demanderait de les poser sur CHAQUE chemin qui supprime une région, change un texte ou un type
(une dizaine, R11) — l'oubli d'un seul laisserait un relevé « normal » qui désigne autre
chose, en silence. Dérivé, il ne peut pas mentir, et s'efface tout seul quand la cause
disparaît. C'est la doctrine du numéro éditorial et de la relecture (« dérivé, jamais
stocké »). La fiche dit « un état (normal · à revoir · à compléter) » : c'est ce que la vue
rend, champ compris.

**Ce que ça coûte.** `routes/releves.py` (un module neuf : le plancher de
`tests/inventaire_routes.py` le suit seul, `test_decoupage_api` exige ses imports) ; la vue ;
les gardes et leurs tests.

**Reste à trancher.** G2, G3, G4, G8, G14.

## R6 — Les mots : le découpage de l'outil, et le ré-ancrage

**Proposé.**
- **Un cœur pur, `mots.py`** (tranché le 2026-10-14 : le découpage est celui de l'outil, pas
  des `tokens` de spaCy, note §5) et une **table de cas**, `tests/cas-mots.json` — le patron de
  `casse.py` et de `tests/cas-casse.json`. La règle : séparation aux espaces et aux retours à la
  ligne ; la ponctuation forme des mots à elle (et une suite de ponctuations identiques —
  « !!! », « ... » — un seul : « emphase par ponctuation » doit pouvoir la désigner) ; les
  clitiques élidés se détachent avec leur apostrophe (`j'`, `c'`, `qu'`, `l'`, `d'`, `n'`,
  `s'`, `t'`, `m'`), l'apostrophe typographique comprise (la table `_APOSTROPHES` de
  `database.cle_tag`, pour la COMPARAISON ; la forme stockée reste verbatim). Le rang est
  l'indice dans ce découpage. Les cas que la table doit trancher AVANT le premier relevé, et
  que la note ne tranche pas : « aujourd'hui », « presqu'île » (une apostrophe qui n'élide
  pas) ; les mots à tiret (« peut-être », « dis-moi », « -t-il ») ; la coupure de fin de ligne
  du lettrage (« por-↵trait ») ; les nombres et les sigles pointés (G11).
- **Le passage** : `releve_mot`, une ligne par mot désigné, dans l'ordre (`position`), avec son
  RANG et sa FORME (note §5) — continu ou non (« ne … pas », confirmé par les linguistes le
  2026-10-22).
- **Le ré-ancrage** — le patron de `token_correction`, avec une différence : l'ancien découpage
  n'est pas en base. Chaque relevé sur des mots garde donc le texte de son ancrage
  (`texte_ancre`, le texte de la région quand le passage a été désigné). Quand le texte change,
  `reancrer_releves(conn, region_id)` aligne (difflib) `mots(texte_ancre)` sur
  `mots(ocr_texte)` : tous les mots retrouvés, même déplacés → le passage suit, ses rangs sont
  réécrits, `texte_ancre` aussi ; un mot disparu ou changé → son `rang` passe à NULL, sa forme
  reste (« garde ses anciennes formes pour qu'on voie ce qu'il désignait »), le relevé est
  « à revoir » (dérivé, R5). Jamais perdu, jamais déplacé en silence.
- **Le point d'appel unique : `database.reindex_region`**, qui porte déjà le ré-ancrage des
  corrections. Tout chemin qui change un texte y passe (lu) : `PUT /api/regions/{id}`,
  l'annulation (`undo._inverser_modification_region` et la recréation profonde),
  `tools/normaliser_casse.py`, l'OCR (qui ne remplit que du vide — aucun relevé sur des mots
  n'y est possible). `repartir_de_zero` efface les relevés avant d'effacer les textes (R11).
  Et le jour où un écrivain oublierait `reindex_region`, l'écart `texte_ancre` ≠ `ocr_texte`
  rend le relevé « à revoir » au lieu de le laisser désigner un autre mot.
- **Sans spaCy** : rien ne change, le découpage n'en dépend pas (c'est la raison de la
  décision du 2026-10-14).
- **Le jumeau navigateur** : la note §5 prévoyait `static/lib/mots.js`, accordé par la table de
  cas. Proposé : la route `GET /api/regions/{id}/mots` rend les mots (rang, forme, début et fin
  dans le texte), et la page Annotation dessine depuis elle — UN découpage, à un endroit. La
  page Annotation ne modifie pas le texte (la Transcription le fait) : elle n'a jamais à
  découper elle-même. Le jumeau ne viendrait que si la tranche 2 en montre le besoin (G11).

**Pourquoi.** Le relevé doit exister sans moteur de langue, désigner le mot montré, et ne pas
bouger quand le modèle change (note §5). `texte_ancre` est le seul moyen de rejouer
l'alignement sans réintroduire une table de mots régénérée.

**Ce que ça coûte.** Un cœur, une table de cas, un ré-ancrage, une route ; le coût en place
d'un `texte_ancre` par relevé sur des mots (le texte d'une bulle).

**Reste à trancher.** G11, et la table de cas avec les linguistes.

## R7 — Le doute et la passe

**Proposé.**
- **Le doute** (note §8 ; ANN-6, 2026-10-14) : il porte sur UN relevé ; un seul OUVERT à la
  fois par relevé (un second « ? » ajoute un message au fil ouvert) ; il s'ouvre avec un
  commentaire obligatoire ; on y répond (`doute_message`, signé et daté) ; on le LÈVE en
  gardant, en changeant (la modification du relevé est un acte à part, avant la levée) ou en
  retirant le relevé (`issue` = `garde` · `change` · `retire`). N'importe qui le lève (décision
  de Hugo, note §8) — c'est-à-dire, ici, quiconque ÉCRIT dans l'album (G20). Sous un compte
  COLLECTIF, chaque message le dit (`collectif`, lu sur `utilisateur.nature`, AUTH-6), sans
  rien inventer. Routes : `POST /api/releves/{id}/doutes`, `POST /api/doutes/{id}/messages`,
  `POST /api/doutes/{id}/levee`.
- **La passe** (Q7 : « commune et signée ») : une ligne par zone, grille et rubrique (`''` =
  toute la grille) ; marquer « terminée » écrit `par` et `le`, et une passe déjà marquée par un
  autre reste (une écriture identique passe sans conflit, ANN-6 2026-10-22) ; « Rouvrir » la
  retire. Elle porte `version_id`, pour que la montée de version sache plus tard quelles zones
  rouvrir. `PUT` / `DELETE /api/regions/{id}/passes/{grille_id}` et leur pendant sur la
  planche. Le mot est « terminée » (tranché sur la maquette v3), la question ouverte n°6 de la
  note est close.

**Pourquoi.** La passe distingue « 0 élision » de « pas regardé » (note §9) ; elle ne tient à
aucun relevé, donc pas à la table des relevés.

**Ce que ça coûte.** Trois tables, cinq routes ; les messages sont des LOGINS et du texte libre
— le cliquet des sorties les voit (R12).

**Reste à trancher.** G20.

## R8 — Qui voit, qui écrit

**Proposé.** Une seule question neuve dans `Portee`, et des réponses tirées de celles qui
existent.

| Geste | Question | Refus |
|---|---|---|
| Importer, publier, retirer une grille, réexporter, corriger une coquille | `peut_gerer_projet(projet de la grille)` — le responsable, l'administrateur qui passe outre (note §10) | 404 sur une grille qu'on ne voit pas, 403 nommé sur une grille qu'on voit sans gérer son projet (le patron de `_get_projet`) |
| Activer, désactiver | `peut_gerer_projet(projet)` | idem |
| Masquer dans une collection | `peut_administrer(collection)` (G7) | 404 / 403 nommé, le patron de `_get_collection` |
| Lire le plan d'une version publiée (ou vivante) | **`clause_grille(alias)`**, neuve (ci-dessous) | 404 |
| Lire un brouillon | `peut_gerer_projet` | 404 (« le brouillon reste chez ses auteurs ») |
| Poser, modifier, retirer un relevé ; douter, répondre, lever ; marquer une passe | écrire dans l'album : l'accesseur gardé en écriture (`clause_album(ecriture=True)`) — note §10 | 404 |
| Lire un relevé, un doute, une passe | lire l'album | 404 |

**`Portee.clause_grille(alias)`** — une question neuve, écrite dans `autorisation.py`
(« un seul endroit tranche qui voit quoi »), un fragment SQL comme `clause_terme`. Une grille
est lisible :
- (a) de quiconque est MEMBRE de son projet ;
- (b) de quiconque LIT un album d'un projet où elle est active — la décision du 2026-10-14
  (§10 de la note, `ANN-7` zone « Le catalogue et le partage ») : un annotateur qui a un accès
  de collection sans être du projet doit voir la grille qu'il applique ;
- (c) de quiconque lit un album qui porte un relevé de cette grille — sans quoi désactiver une
  grille rendrait illisible le sens des relevés qui restent « en lecture ».
(a) et (c) ne sont pas tranchés : G5. Une portée totale lit tout, BORNÉE hors des bacs à sable
des autres (`couvre_projet`, le patron de `clause_projet`).

**Le bac à sable** (COL-4). Son propriétaire, responsable de son bac, y importe et y active
des grilles : c'est un projet comme un autre, et l'annotation est ce qu'on viendra y essayer.
Une grille née dans un bac n'existe que dans ce bac (sa rive, au sens de
`socle._rive_d_un_terme`) : elle ne se partagera jamais au catalogue, et part avec lui
(`_effacer_bac_a_sable`, R11). Ses entrées vivent dans sa version, sans unicité d'instance :
aucun nom n'y est « pris pour toute l'instance », l'écueil qui a fait refuser l'import de
vocabulaire dans un bac. Rien de ce que la tranche 1 ajoute n'est une question TRANSVERSE
(aucune ne lit `ecriture` entière) : l'inventaire S2 de COL-4 n'a rien à gagner. Les relevés du
JEU (le cran `annotations` des copies de référence, S4 de COL-4) ne viennent pas en tranche 1
(G6).

**Le jeu de la cible.** Le relevé s'autorise par l'ALBUM de sa cible ; l'entité (Q4) n'a ni
album ni portée, d'où son attente (G3).

**Pourquoi.** Toutes les décisions d'accès d'une grille sont celles du projet, sauf la
lecture du plan, qui est la seule chose neuve à trancher — et qui doit vivre dans
`autorisation.py`, pas dans une route.

**Ce que ça coûte.** Une méthode de `Portee`, et le cliquet `test_autorisation` sur chaque
route neuve. Relecture croisée : la lecture du plan est une question de droits neuve.

**Reste à trancher.** G5, G6, G7, G20.

## R9 — La concurrence : le 409 de CONC-3 sur les valeurs uniques

**Proposé.** Chaque écriture d'une VALEUR UNIQUE d'un relevé, d'un doute ou d'une passe porte
`vu` — la valeur que l'écran avait vue —, et passe par `conflit.verifier` sous
`conflit.verrouiller` :
- d'un relevé : la variante, les qualificatifs (comme UN ensemble : deux personnes qui en
  cochent des différents se voient refusées l'une l'autre, plutôt que fusionnées sans le
  savoir), la précision, le lien, le passage ;
- d'un doute : sa levée (`vu` = ouvert) ;
- d'une passe : sa présence (`vu` = marquée ou non).
Le 409 est celui de CONC-3, mot pour mot (`Perime.detail()` : message, champ, valeur actuelle,
auteur lu au journal) — c'est ce que le bandeau de l'Atelier sait déjà afficher, et ce que la
page Annotation montre à la place de la ligne du guide (ANN-6, 2026-10-22). Une écriture
identique à la valeur actuelle passe (`conflit.verifier` le fait déjà). `LIBELLES` gagne les
champs neufs (« la variante », « les qualificatifs », « la précision », « le lien », « le
passage », « le doute », « la passe »). `vu` reste facultatif pour l'API, comme pour une région
(Q8 de CONC-3) ; la page Annotation l'enverra toujours.

**L'écart avec la fiche, à trancher (G1).** Q7 dit que ces valeurs « portent une version de
ligne dès la tranche 1 ». CONC-3 a refusé la colonne de version le 2026-09-17, et sa docstring
dit pourquoi : chaque écrivain doit l'incrémenter, un oubli reste muet, et elle vaut pour la
ligne entière (poser une précision périmerait la variante de l'autre). La valeur vue donne
EXACTEMENT ce que Q7 demande — le 409 sur une valeur périmée, dès la tranche 1, la réponse au
renvoi de CONC-4 — sans ces deux défauts. Proposé : la valeur, sans colonne ; la décision de
Hugo a fixé le but, et ce mécanisme le tient.

**Pourquoi.** Les relevés commutent comme des tags (en poser deux n'en perd aucun), mais une
variante, une levée, une passe sont des valeurs qu'un second écrivain écrase (Q7).

**Ce que ça coûte.** Les sources de `conflit.auteur_des_champs` pour chaque champ (la cible
`releve`, la clé de charge) ; un test de course par valeur gardée (le patron de
`test_conflit_version`).

**Reste à trancher.** G1.

## R10 — Le journal et l'annulation

**Proposé — le journal.**
- **Deux cibles neuves, sur le patron des annotations** (« les actes d'annotation ciblent le
  `region_id`, stable ») : `releve`, dont `cible_id` est la RÉGION du relevé, et
  `releve_planche`, dont `cible_id` est la PLANCHE. L'identifiant du relevé voyage dans la
  charge. Les doutes et les passes s'écrivent sous la même cible que leur relevé ou leur zone,
  par des TYPES à eux (`doute`, `doute_reponse`, `doute_levee`, `passe`, `passe_rouverte`) —
  hors de `undo._TYPES`, donc jamais remontés par Ctrl+Z, sans une ligne de code de plus.
- **Pourquoi la région et non le relevé** : quatre lecteurs du journal raisonnent déjà par
  région et s'appuient sur l'index `idx_evenement_cible` — la règle « travail d'autrui » (ses
  sources 1 et 6, la chaîne de `region_origine` comprise), `sql_acte_isole`, et les gardes de
  `undo._meme_objet` et `lieux`. Ajouter `releve` à `_CIBLES_DE_REGION` les fait lire les
  relevés tels quels ; un `cible_id` de relevé les obligerait à chercher la région dans la
  charge, par `json_extract`, sans index — sur le chemin de `destructible`, calculé album par
  album dans `GET /api/albums` (le constat de COL-4 : 186 ms au lieu de 22 pour un `OR` mal
  placé). C'est le patron de `token_correction` qu'on écarte ici, et la raison en est la
  mesure, pas le goût.
- **La grille** s'écrit sous `grille` (`cible_id` = la grille) : import d'un brouillon,
  publication, retraite, coquille, entrée ajoutée à une grille ouverte, activation et
  désactivation (charge : le projet, la version), masque (charge : la collection).
- **Toutes les trois sont RETENUES de toute sortie** en tranche 1 (`CIBLES_RETENUES`, avec leur
  raison : « rien du relevé ne sort avant la tranche 4 »), et `grille` est SANS RANG
  (administrer un vocabulaire n'est pas annoter, la raison de `tags`). Pour `releve` et
  `releve_planche`, G10 : les compter dès maintenant dans les rangs des pseudonymes, pour que
  leur sortie en tranche 4 ne renumérote pas tous ceux qui annotent.
- **`comptes.traces`** : les actes sur les relevés COMPTENT (qualifier une zone est du travail,
  la raison de `region_attribut`) ; ceux sous `grille` non (la raison de `tags`).
  `sql_acte_isole` apprend les deux cibles neuves (la région pour `releve`, la planche pour
  `releve_planche`) — sans quoi les relevés d'un bac à sable effacé compteraient chez
  l'administrateur.

**Proposé — l'annulation.**
- **Ctrl+Z défait poser, modifier, retirer un relevé** (note §11). `_TABLES` gagne `releve`
  et `releve_planche` ; `_DESCRIPTIONS` leurs phrases (« pose d'un relevé », « modification
  d'un relevé », « retrait d'un relevé »). Un message de doute, une levée, une passe ne
  s'annulent pas (note §11 ; ils se répondent, se rouvrent).
- **Les gardes, chacune déjà écrite pour une autre table** :
  - AUTH-14 — `lieux` rend la région (ou la planche pour `releve_planche`), que la route
    éprouve en écriture ; `_meme_objet` vaut tel quel pour `releve` (la région est l'objet),
    et gagne une branche pour `releve_planche` (la planche présente, l'album né avant l'acte) ;
    le relevé d'une pose à défaire doit exister encore (sinon : passé), celui d'un retrait à
    rétablir ne doit pas (son identifiant ne revient jamais : il n'existe que s'il a été
    rétabli) ;
  - le cinquième témoin de la 3b (`planches_remises_a_zero`) s'applique sans changement ;
  - CONC-3 — défaire une modification ou un retrait dont la valeur a changé depuis lève
    `Perime` (`depuis` = l'acte), et l'écran offre « Passer ce geste » (ANN-8) ;
  - ANN-8 — le relevé se rétablit par sa `cle` d'entrée et de variante, jamais par un libellé
    (case « Supprimer, fusionner, renommer un terme a sa règle dans le modèle ») ; une entrée
    qui n'existe plus dans la version (une grille ouverte remaniée) rend l'acte
    irrétablissable (seconde phrase) ;
  - la grille n'est plus active dans le projet : passé, seconde phrase — l'agent lit la
    région, la phrase ne lui apprend rien.
- **Supprimer une région supprime ses relevés, et Ctrl+Z les rend** : l'instantané profond
  (`journal.snapshot_region_profond`) gagne une clé `releves` — chaque relevé de la région avec
  ses mots, ses qualificatifs, ses doutes et leurs messages —, et une clé `passes`.
  `_recreer_region_profond` les rend sous leurs identifiants, après `_rendre_liens` ; ceux dont
  la grille n'est plus active ou dont l'entrée a disparu ne reviennent pas, comptés dans la
  réponse (le patron de `liens_non_rendus`). La charge porte du texte (précision, messages) :
  elle est retenue, comme `ocr_texte` aujourd'hui (`COLONNES_JOURNAL_RETENUES`).
- **Le relevé dont la région LIÉE disparaît** n'est pas touché : il devient « à revoir » par
  dérivation, et Ctrl+Z de la suppression de cette région le rattache sans rien écrire (R5).

**Pourquoi.** Tout ce que Ctrl+Z doit tenir pour un relevé, il le tient déjà pour une région
ou une annotation ; la forme des cibles est choisie pour hériter de ces gardes.

**Ce que ça coûte.** Deux tables dans `_TABLES`, deux inversions, une branche de
`_meme_objet`, l'instantané. `docs/undo.md` le dit.

**Reste à trancher.** G10.

## R11 — Les coutures : ce que les relevés obligent à toucher ailleurs

Le constat central de ce cadrage. Une table d'annotation neuve doit être lue par une dizaine
de chemins qui ne la connaissent pas, et la plupart échouent OUVERT : un oubli ne fait tomber
aucun test existant (`pilotage/ANN-7.md`, case « Deux gardes qui échouent OUVERT couvrent les
relevés, et un cliquet les tient »). Inventaire (lu), avec ce qu'on en fait :

| Chemin | Ce qui casserait sans lui | Proposé |
|---|---|---|
| **« Travail d'autrui »** (`autorisation._sources_du_travail`) | L'importatrice supprimerait SEULE un album annoté par d'autres en relevés — échoue OUVERT | `releve` dans `_CIBLES_DE_REGION` (sources 1 et 6), `releve_planche` à côté de `planches` (source 4) ; une source sur les COLONNES (`releve.auteur`, `doute_message.auteur`, `passe.par`) comme celle des corrections, pour le travail recopié au niveau de la planche que la chaîne de `region_origine` ne remonte pas ; `_SQL_COUCHE_VIT` apprend `releve` |
| **Repartir de zéro** (`database.repartir_de_zero`) | Une copie remise sous le cran `annotations` garderait ses relevés — échoue OUVERT | Retirer relevés (régions ET planche), passes, doutes à tout cran inférieur à `annotations`, comptés dans `comptes` |
| **Copier au cran `annotations`** (`copier_le_travail`, `compter_le_travail`) | Sans eux, les relevés ne suivraient jamais ; mal faits, ils suivraient posés et invisibles (le piège de `COL-1`) | Le patron d'E5, tranché le 2026-10-22 : un relevé suit si sa grille est ACTIVE dans le projet d'arrivée, quelle que soit la version ; sinon il est COMPTÉ dans `laisses` (l'aperçu le dit). En tranche 1, une grille n'est active que dans son projet : entre deux projets, rien ne suit encore. Les passes suivent (de ces grilles-là), les doutes non (tranché le 2026-10-22). `lien_region_id` est renuméroté par la table des régions copiées, `origine_id` posé. **L'auteur entre deux projets** : G9 |
| **Détruire un album** (`socle._detruire_album`), **supprimer une planche** (`DELETE /api/planches/{id}`) | La FK sans action fait échouer la suppression (R1) : bruyant, pas une fuite | Retirer les relevés et passes de SURFACE des planches avant le `DELETE` ; ceux des régions partent par CASCADE |
| **Re-segmenter, re-détecter les bulles** (`segmentation.segment_planche`, `bulles`) | Une case qui ne porte que des relevés (« Lieux », sur la case) serait supprimée par une re-segmentation, ses relevés avec elle — échoue OUVERT, et c'est déjà le cas des situations (lu, G20) | Le critère de préservation lit les relevés et les passes (« porte du travail humain ») ; aucun transfert de relevé vers la nouvelle case (le transfert d'annotation refuse déjà l'ambiguïté) |
| **Changer le type d'une région** (`PUT /api/regions/{id}`) | Un relevé de bulle sur une région devenue case | Rien n'est retiré : « à revoir » dérivé (G8) ; Ctrl+Z du type le fait redevenir normal |
| **Effacer un bac à sable** (`socle._effacer_bac_a_sable`) | La ligne `projet` ne partirait pas (FK sans action de `grille.projet_id`) : bruyant | Supprimer ses grilles (leurs relevés sont partis avec ses albums) avant le projet ; le compter dans la charge de l'effacement |
| **Supprimer un projet** (`socle._supprimer_projet`) | idem | Un 409 de plus qui se nomme : « ce projet possède n grilles » (G18) |
| **`sql_acte_isole`**, `comptes.traces` | Les actes d'un bac effacé compteraient chez l'administrateur | Les deux cibles neuves (R10) |
| **L'instantané profond, Ctrl+Z** | Ctrl+Z d'une suppression de région rendrait la région sans ses relevés | R10 |
| **Assembler une double page** (`IMG-2`, pas codé) | — | Q5 : « le chantier qui arrive second écrit le report ». ANN-7 arrive premier : `IMG-2` reportera les relevés de surface et la FK sans action fera échouer bruyamment un assemblage qui les oublierait |
| **Fusionner deux régions** (aucune route, lu) | — | Quand le geste naîtra, il réunira les relevés, et deux relevés d'une entrée `une` contradictoires passeront « à revoir » (tranché le 2026-10-22) — l'index unique partiel le forcera à y penser |

**Le cliquet.** La décision demande « un test qui exige que toute table de l'annotation soit
lue par l'une et par l'autre » (la règle de suppression et repartir de zéro). Proposé : une
liste déclarée, `database.TABLES_D_ANNOTATION` (`releve`, `releve_mot`,
`releve_qualificatif`, `doute`, `doute_message`, `passe`, et celles d'aujourd'hui qui y
appartiennent), et un test qui exige, pour chaque table de la liste, qu'elle soit lue par
CHACUN des chemins de la table ci-dessus qui échouent ouvert — par comportement (une table
semée, le chemin joué, l'effet vérifié) et non par lecture du source. Et l'inverse : toute
table neuve du schéma qui porte un `region_id` ou un `planche_id` est dans la liste ou
déclarée hors d'elle, avec sa raison — sans quoi la prochaine table d'annotation passerait à
côté du cliquet comme la situation passe aujourd'hui à côté de la re-segmentation.

**Ce que ça coûte.** C'est le commit le plus lourd (cf. découpage) : neuf chemins à apprendre,
et le cliquet.

## R12 — Ce qui sort : rien, et les cliquets le vérifient

**Proposé.** En tranche 1, aucun relevé, aucune grille, aucun doute ne sort par aucune voie
(note §12).
- Les exports (`/api/export/json` nomme ses colonnes, CSV, TEI, IIIF, les outils
  `metadonnees_collection`, `description_collection`, `provenance_export`, le crosswalk) ne
  lisent aucune table neuve. Un test JOUE l'absence — le patron de
  `test_le_projet_ne_sort_d_aucun_artefact` : une base semée de relevés à précision
  sentinelle, chaque artefact produit, la sentinelle absente.
- Le journal : les trois cibles retenues (R10) ; `test_journal_publie_par_decision` échoue tant
  qu'elles ne sont pas classées.
- `tests/test_sorties_identite.py` : les routes GET neuves qui rendent un login (`auteur`,
  `modifie_par`, `ouvert_par`, `leve_par`, l'auteur d'un message, `par` d'une passe,
  `importee_par` / `publiee_par` d'une version, `active_par`) sont DÉCLARÉES, avec la sorte
  émise et sa raison. **Son mode d'échec est le semis** : la sentinelle doit être semée dans
  chacune de ces colonnes, sinon une route qui ne lit qu'elles paraît propre
  (`test_le_semis_est_visible`).
- `tests/test_droit_export.py` : le réexport du tableur est une porte DÉCLARÉE hors du droit
  (G16).
- La sauvegarde, entière et réservée aux administrateurs, emporte tout — elle a changé de
  public, pas de portée (DROIT-1).

## R13 — Ce que la tranche 2 attendra des routes

La page Annotation (un module montable, sur la maquette v3,
`https://claude.ai/artifact/3EXqt485Dv7SwwTRVogLuQ`) consommera, sans route à ajouter :

- `GET /api/projets/{id}/grilles` : les grilles ACTIVES du projet (version, ouverte ou non, le
  masque de chaque collection), et — à qui gère — les siennes en brouillon ; `gerable` existe
  déjà dans `GET /api/projets` pour le lien « Gérer les grilles ↗ ».
- `GET /api/grilles/{id}/versions/{numero}` : le plan entier — rubriques imbriquées, entrées,
  variantes, listes, définitions, structures, exemples, pièges, cible effective, cardinalité
  effective, précision et lien attendus — de quoi filtrer côté écran (accents, apostrophes et
  exemples compris) sans aller-retour.
- `GET /api/planches/{id}/releves` : tous les relevés de la planche, régions et surface, avec
  mots, qualificatifs, lien (et son texte s'il est perdu), état dérivé et ses causes, doute
  ouvert et son fil, auteur et nom lisible, `collectif`, `modifiable` (la grille active et
  l'album écrit) ; plus les passes de la planche. C'est ce que lisent la liste du bas, la
  Synthèse rangée par case, « À revoir », les nombres des onglets et le Décompte.
- `GET /api/regions/{id}/mots` : le découpage (R6).
- `POST /api/releves`, `PUT` / `DELETE /api/releves/{id}` avec `vu` ; les trois routes du
  doute ; les deux de la passe ; `POST /api/undo` tel qu'il est.
- Les corps d'erreur nommés (409 cardinalité avec le relevé existant, 409 CONC-3 au format
  `Perime.detail()`, 409 grille inactive, 422 forme et cible) : l'écran n'a rien à deviner.

Ce que la tranche 2 ajoutera elle-même : le type `detail` et `regions.nom` à l'écran (G17) ;
les deux chemins vers l'entité (case ouverte d'`ANN-6`, avec G3) ; le guide produit depuis la
grille.

---

## Les règles d'autorisation

Une question neuve, `Portee.clause_grille` (R8). Réutilisées sans changement :
`peut_gerer_projet` (gérer les grilles d'un projet, les activer), `peut_administrer` (masquer
dans une collection), `clause_album` par les accesseurs gardés (poser, lire). Étendues sans
changer de sens : `_sources_du_travail` (R11), `sql_acte_isole` (R10). Inchangées :
`clause_terme`, `peut_ecrire_terme`, `peut_remanier_tag` — le vocabulaire d'aujourd'hui garde
ses règles jusqu'au basculement.

### Ce qui fuit si l'on se trompe

- **Le plan d'une grille réservée lu hors de son cercle** — une étude en cours révélée
  (`ANN-7`, case « Qui voit le plan d'une grille réservée ») — mutant : `clause_grille` à `"1"`,
  ou sans la condition de lecture d'album.
- **Un brouillon lu par un non-gérant** — mutant : la version lue sans regarder son état.
- **Un relevé posé sur un album qu'on ne fait que lire** — mutant : l'accesseur sans
  `ecriture=True`.
- **L'importatrice qui supprime seule un album annoté en relevés par d'autres** — mutant :
  `releve` hors de `_CIBLES_DE_REGION` ; et `releve_planche` hors de la source 4.
- **Repartir de zéro qui laisse des relevés** sous une copie qu'on a voulue vide — mutant :
  la ligne de `repartir_de_zero` retirée.
- **Un relevé recopié dans un projet où sa grille n'est pas active**, posé et invisible ; **un
  doute recopié**, qui nomme l'équipe source — mutants : le filtre d'activation, la ligne des
  doutes.
- **Un relevé de bac à sable compté chez l'administrateur** (`comptes.traces`) — mutant :
  `sql_acte_isole` sans les cibles neuves.
- **Une case porteuse de relevés supprimée par une re-segmentation** — mutant : le critère
  `preserved` d'aujourd'hui.
- **Un relevé qui désigne un AUTRE mot après une correction du texte** — mutant : le
  ré-ancrage retiré de `reindex_region` ; le test vérifie aussi que la vue dit « à revoir »
  quand `texte_ancre` diverge.
- **Le lien vers une région d'un autre album**, qu'on ne lit peut-être pas — mutant : la
  vérification du même album.
- **Ctrl+Z qui rend un relevé dans une région qu'on n'écrit plus** — mutant : `lieux` sans la
  cible du relevé.
- **Une précision, un message de doute dans un export** — mutant : une table neuve lue par un
  outil de sortie.

---

## Le découpage en commits

0. **La vraie base v36 et la v37** : `tests/bases/v36-<commit>.sql` (branche `>= 36` de
   l'outil de fabrication), les seize tables et `regions.nom`, le test de migration. ½ jour.
1. **Les mots** : `mots.py`, `tests/cas-mots.json` (les cas tranchés avec Hugo et les
   linguistes, G11), `GET /api/regions/{id}/mots`. ½ jour.
2. **Les grilles** : `grille_import.py`, `tools/importer_grille.py`, la grille modèle fictive,
   `routes/grilles.py` (import, bilan à blanc, publier, supprimer un brouillon, retirer,
   coquille, plan, réexport, activation, masque), `Portee.clause_grille`, le journal sous
   `grille`. 2 jours, mutants compris.
3. **Les relevés** : `routes/releves.py` (poser, modifier, retirer ; les gardes de R5 ; la
   cardinalité sous verrou et l'index ; le lien), la vue `releves_effectifs`, CONC-3 (R9), les
   cibles `releve` / `releve_planche` au journal et retenues. 1½ jour.
4. **Les doutes et les passes** (R7). 1 jour.
5. **Les coutures** (R11) et **l'annulation** (R10) : le ré-ancrage dans `reindex_region`,
   repartir, copier et compter, détruire et supprimer une planche, la re-segmentation, le bac
   et le projet, `_sources_du_travail` et `sql_acte_isole`, l'instantané profond et Ctrl+Z, le
   cliquet des tables d'annotation. 2 à 2½ jours.
6. **La documentation** : `docs/grilles-et-releves.md` à jour des décisions du 2026-10-22
   (la case « La note est à jour » ; idéalement AVANT le commit 2, puisqu'elle « fixe ce qui se
   code »), `CLAUDE.md` (§ Données, § Autorisation, § Schéma, § Journal, § Annulation),
   `docs/modele-et-droits.md`, `docs/undo.md`, `docs/provenance-audit.md`, et un
   `docs/import-grille.md` (le format du tableur et ce que chaque forme COMPTE — la case
   « Une entrée à qualificatifs compte comme les linguistes comptent »). ½ jour.

**Estimation : 8 à 9 jours.** Ce qui se reporterait sans risque si Hugo veut moins : le
réexport (G16) et la coquille (G15), une demi-journée à eux deux. Rien de R11 ne se reporte :
ce sont les gardes qui échouent ouvert.

Chaque commit de code cite `ANN-7`. **Relecture croisée obligatoire** — une question de droits
neuve (`clause_grille`), la règle de suppression étendue, les copies et Ctrl+Z —, par une
session qui ne l'a pas écrite, sous les identités de la 3a plus trois : un annotateur qui a un
accès de collection SANS être membre du projet (la lecture du plan, §10), un membre du projet
dont la base est protégée (G5), un compte qui n'a que son bac à sable ; sur une base qui porte
deux projets, une grille active et une désactivée portant des relevés, une copie sœur amorcée
au cran `annotations`, un bac à sable avec sa grille.

### Les gardes à éprouver par mutants

- la lecture du plan, sous les quatre identités de G5 : (a), (b), (c), et un lecteur d'un autre
  projet ; mutant : chaque disjoint retiré tour à tour ;
- le brouillon invisible des non-gérants ;
- la pose : écriture requise ; grille active ; version de l'activation ; entrée non retirée ;
  cible et type ; forme ; lien du même album — un mutant par garde, un par un ;
- la cardinalité : le second relevé `une` refusé ; deux poses simultanées n'en font qu'un
  (test de course ; mutant : la relecture hors du verrou ET l'index retiré, séparément) ;
- CONC-3 : chaque valeur gardée de R9 refusée périmée, acceptée identique ; mutant : `vu`
  ignoré ;
- l'état dérivé : chacune des cinq causes produit son état, et disparaît avec elle ;
- le ré-ancrage : un mot déplacé suit, un mot changé met « à revoir », le texte d'ancrage
  divergent aussi ;
- chaque ligne de R11 (le cliquet joue la liste) ; et la FK de surface : supprimer une planche
  qui porte un relevé de surface sans passer par le chemin échoue ;
- Ctrl+Z : poser, modifier, retirer ; hors de portée → passé ; grille désactivée → passé ;
  valeur changée depuis → 409 « Passer ce geste » ; suppression de région → relevés rendus ;
- l'import : une anomalie refuse tout (mutant : ligne écartée) ; même empreinte, rien d'écrit ;
- les sorties : la sentinelle de précision et de message absente de chaque artefact.

### Les passes de QA à écrire

La tranche 1 n'a pas d'écran : aucune passe VISUELLE. Une passe de RECETTE est à écrire —
rédigée, jamais cochée par qui l'écrit — dans `pilotage/qa/import-grille.md` : sur la pile de
recette, l'outil d'import à blanc puis pour de bon avec la VRAIE grille (hors dépôt), le bilan
lu, le réimport sans changement, une version 2 en brouillon avec un renommage et une
disparition, la publication, l'activation, puis par l'API un relevé de chaque forme et chaque
cible, un conflit de variante entre deux comptes, un doute à deux, Ctrl+Z. Chaque case dit sa
commande et son attendu. C'est aussi la mesure demandée « sans Hugo » (`ANN-7`, Contexte) :
l'import de la vraie grille dans les trois formes. Les passes visuelles viennent avec la
tranche 2.

---

## Les décisions qui restent à Hugo

Ce que la fiche ou la note tranchent est cité dans le texte et n'est pas repris ici. Chaque
ligne ci-dessous est une question qu'elles ne tranchent pas, ou un écart proposé à une de
leurs formulations.

| | Question | Options | Proposé |
|---|---|---|---|
| G1 | **La « version de ligne » de Q7** | (a) une colonne `version` incrémentée par chaque écrivain ; (b) la VALEUR vue, le mécanisme de CONC-3 | (b) — le 409 de Q7 dès la tranche 1, sans les deux défauts que CONC-3 a écrits contre la colonne (R9) |
| G2 | **L'état d'un relevé** | (a) une colonne, posée par chaque chemin qui change un texte, un type ou supprime une région ; (b) DÉRIVÉ par une vue, comme la relecture | (b) en tranche 1 ; une colonne ne viendrait qu'avec une cause qui ne se lit pas dans les données (la scission d'une entrée, à la montée de version) |
| G3 | **La cible `entite` en tranche 1** | (a) la colonne dès la v37, les routes la refusent ; (b) rien avant l'étage de projet des personnages (tranche 4 de `COL-3`), une colonne ajoutée alors par `ALTER` | (b) — l'import accepte des entrées qui la visent, aucun relevé ne s'y pose, et le refus est nommé |
| G4 | **Où peut pointer un lien** | (a) une région du même album ; (b) de la même planche ; (c) n'importe où | (a) — un chevauchement est presque toujours sur la planche, un renvoi peut traverser l'album ; hors de l'album, le lecteur du relevé ne lit peut-être pas la cible |
| G5 | **Qui lit le plan d'une grille, au-delà du §10** | (a) les membres du projet propriétaire, même sans album lu ; (c) qui lit un album portant un relevé de la grille, même désactivée | (a) et (c), en plus de la règle tranchée (lire un album d'un projet où elle est active) |
| G6 | **Les grilles dans un bac à sable** | (a) importer et activer, jamais partager, effacées avec lui ; (b) aucune grille dans un bac en tranche 1 ; et le cran `annotations` du JEU | (a) ; le jeu (relevés de référence) attend la tranche 2, avec un exemple d'annotation à montrer |
| G7 | **Qui masque une grille dans une collection** | (a) le propriétaire de la collection ; (b) le responsable du projet | (a) — c'est un réglage d'affichage de la collection, comme sa description |
| G8 | **Une région qui change de type** | (a) ses relevés passent « à revoir » ; (b) ils sont retirés dans le même geste, comme les liens d'ANN-8 | (a) — jamais perdu ; Ctrl+Z du type les rend normaux sans rien écrire |
| G9 | **L'auteur d'un relevé recopié ENTRE deux projets** | (a) il suit (la décision du 2026-10-22, « avec leur auteur ») ; (b) NULL, « recopié », comme une correction depuis le 2026-10-25 | (b) — la raison du constat 3 vaut mot pour mot (un login nommé à des gens qui ne le connaissent pas) ; sans effet en tranche 1, où rien ne suit entre projets |
| G10 | **Les relevés dans les rangs des pseudonymes** | (a) comptés dès la tranche 1 ; (b) sans rang jusqu'à leur sortie | (a) — sinon la tranche 4 renumérote tous ceux qui annotent, ce que l'ordre par première trace existe pour empêcher |
| G11 | **Le découpage : la route ou un jumeau JS ; et ses cas** | (a) la route rend les mots ; (b) `static/lib/mots.js` accordé par la table de cas | (a) ; et à trancher avec les linguistes : « aujourd'hui », les mots à tiret, « -t-il », la coupure de fin de ligne, « !!! » et « ... » comme un seul mot |
| G12 | **Une anomalie dans le tableur** | (a) refuse tout le fichier ; (b) écarte la ligne, comme l'import de vocabulaire | (a) — une ligne écartée se lirait comme une entrée disparue |
| G13 | **Le format du fichier** | (a) deux CSV (entrées, listes), la déclaration en arguments ; (b) un XLSX à onglets | (a) — `openpyxl` est hors du noyau |
| G14 | **Enrichir une grille ouverte** | (a) une entrée naît en la posant, par qui écrit dans l'album ; (b) seuls les responsables ajoutent ; et quand viennent renommer / fusionner / supprimer | (a), comme les tags libres ; les trois gestes d'ANN-8 avec le basculement (tranche 3) |
| G15 | **La coquille corrigée sans nouvelle version** | (a) sa route dès la tranche 1 ; (b) avec l'écran (tranche 2) | (a) — un quart de jour, et la vraie grille en aura besoin dès son import |
| G16 | **Le réexport du tableur** | (a) dès la tranche 1, aux gérants, déclaré hors du droit d'export ; (b) plus tard | (a) — c'est le chemin de la dérivation allégée, et la seule façon de vérifier les `cle` par aller-retour |
| G17 | **Le détail, type de région** | (a) `regions.nom` en v37, le type `detail` en tranche 2, EXCLU des exports jusqu'à la tranche 4 ; (b) le type en tranche 1 | (a) — une région SORT par les exports dès qu'elle existe (TEI, CSV, IIIF) : sans exclusion, le détail sortirait avant que la tranche 4 en décide |
| G18 | **Supprimer un projet qui possède des grilles** | (a) 409 nommé ; (b) les grilles partent avec lui | (a), le patron du vocabulaire propre d'une base ; un bac à sable les efface avec lui |
| G19 | **La vraie grille** | Qui transcrit le PDF en tableur, avec ses `cle` ; où il vit (hors dépôt) ; qui le relit avec les linguistes ; les six écarts du guide réglés avant | à décider par Hugo — proposé : une session prépare le tableur sur le poste depuis le PDF, hors dépôt, Hugo et la gestionnaire le relisent, puis il s'importe dans le projet retenu au déploiement (Q9) |
| G20 | **Trois points de bord** | (a) douter, répondre, lever : qui ÉCRIT dans l'album (pas un simple lecteur) ; (b) la re-segmentation perd aujourd'hui la situation d'une case (lu) : corriger dans le commit 5, qui pose le même critère pour les relevés, ou le renvoyer à `ANN-8` ; (c) les lieux posés par les stagiaires AVANT le basculement (Q9) : en attributs, que Q3 retirera sans conversion, ou dans la grille « Lieux », qui suppose les tranches 1 et 2 d'abord | (a) oui ; (b) dans le commit 5 ; (c) **à trancher**, la tension entre Q9 et Q3 n'est écrite nulle part |

Se tranchent en route, sans Hugo sauf avis contraire : les noms des types d'événement (R10) ;
le format des `cle` (texte libre, comparé exactement) ; la table `grille_exemple` dès la v37
(le renvoi à un relevé s'y posera sans migration) ; un seul doute ouvert par relevé (R7).

---

## Ce que cette note n'a pas pu établir

- **La vraie grille dans les trois formes** : non lue (le PDF est le travail des linguistes, et
  aucun tableur n'existe). Que ses sept niveaux tiennent dans le format de R3, cardinalité
  comprise, reste à mesurer à son import.
- **Le coût de la règle « travail d'autrui » avec les relevés** : non mesuré. Elle est calculée
  album par album dans `GET /api/albums` ; une source de plus et une cible de plus dans la
  chaîne récursive de `region_origine` s'y ajoutent. À mesurer au commit 5 sur une base au
  volume de la maquette, avant de figer la forme.
- **Le semis de `tests/test_sorties_identite.py`** : non lu dans le détail ; qu'il sache semer
  des sentinelles dans les tables neuves est supposé.
- **La place de la 3b dans `dev`** : la note suppose la 3b fusionnée avant ANN-7, d'où la v37 ;
  sinon les numéros de version glissent.
- **Le coût de la réécriture au basculement** (case ouverte « Le coût de la réécriture est
  mesuré ») : hors du périmètre de la tranche 1, non refait ici.
- **La re-segmentation qui perd une situation** : lu dans le code (`segment_planche`, critère
  `preserved`), non rejoué.
