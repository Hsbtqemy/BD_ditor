# Journal de provenance / audit (A3)

> **But.** Qualifier *qui a produit quoi, quand et comment* — le travail de transformation
> (passes ML) **et** d'annotation (humain) — sans jamais inverser la base. Condition d'un
> corpus **réutilisable** (reproductibilité, dérive machine↔humain) et substrat de l'**undo**
> (D1). Décision arrêtée le 2026-07-15, livrée en **v16** (2026-07-17). Cadre : niveau 8 du
> `docs/dictionnaire-metadonnees.md`.

## Principe : un journal *append-only*, la base reste la vérité

Les tables métier restent la **source de vérité**. À côté, un **journal immuable**
enregistre *en plus* chaque acte. On n'inverse jamais l'état (pas d'event-sourcing pur) :
l'historique est **récupérable** du journal (avant/après), mais l'app lit toujours les
tables. Deux grains (cf. `database.py`) :

| Grain | Table | PROV | Rôle |
|---|---|---|---|
| **Run** | `activite` | `Activity` | une passe ML en lot **ou** une session ; agent (moteur+version **ou** humain), paramètres, portée, bilan, dates |
| **Acte** | `evenement` | act / TEI `change` | un geste atomique **immuable** : type, agent, cible, **avant/après** (JSON), `activite_id` |

**Le journal survit à la suppression de sa cible.** `evenement.cible_id` n'est **pas** une
clé étrangère : un `ON DELETE CASCADE` effacerait justement l'historique de ce qu'on veut
pouvoir restaurer. C'est ce qui rend l'**undo (D1)** atteignable — l'événement `suppression`
porte un **instantané profond** (région + annotation + sous-arbre).

## L'agent

- **Humain** : l'utilisateur connecté (en-tête d'auth `Remote-User`, INFRA-2), capté par
  requête via un **contextvar** (`journal.agent_courant`) alimenté par une dépendance
  FastAPI globale — les routes n'ont pas à threader `request`. Hors requête (scripts,
  usage local mono-utilisateur), l'agent est **NULL** (honnête : acte anonyme).
- **Moteur** : le nom du moteur (`kumiko`, `yolov8-bulles`, `easyocr`, `spacy`) + sa
  **version** (best-effort, `importlib.metadata`). Posé explicitement par les passes ML.

### En base il est NOMMÉ, à la sortie il est PSEUDONYMISÉ (AUTH-1, 2026-08-31)

Le journal garde le login : c'est ce qui rend l'audit possible, et le cloisonnement
d'AUTH-2 borde déjà qui peut le lire. Mais **tout artefact qui QUITTE l'instance remplace
l'agent humain par un pseudonyme stable** — `annotateur-1`, `annotateur-2`… — via
`tools/_commun.pseudonymes()`, partagé par `provenance_export.py` (PROV-JSON **et** TEI) et
par les trois chemins de `metadonnees_collection.py` (JSON, CSV, XLSX).

**Les moteurs gardent leur nom**, et ce n'est pas un oubli : `kumiko`, `yolov8-bulles`,
`easyocr` sont des LOGICIELS, et les nommer EST l'auditabilité du pré-remplissage qu'on
revendique. Ils ne sont jamais collectés par `pseudonymes()`, si bien qu'un
`.get(nom, nom)` les laisse passer sans cas particulier.

**Pourquoi un pseudonyme plutôt que rien.** Le login ne sert bien aucun des deux buts de la
sortie : pour l'auditabilité, `agent_type` suffit — « machine, puis retouché par un
humain » ; pour l'attribution scientifique, le support propre est `contribution`, avec son
ORCID, et un login identifie sans créditer. Mais un graphe PROV où tous les humains se
confondraient perdrait les **chaînes de révision**, c'est-à-dire l'essentiel. Le pseudonyme
garde la structure et retire l'identité.

**Le mapping est partagé et corpus-entier.** Deux tables ou deux sérialisations du même
export qui nommeraient différemment la même personne se contrediraient sans que rien ne le
dise. L'ordre est celui de la **première trace** et non l'alphabet : un annotateur qui
rejoint l'équipe renumérote sinon tous ceux qui le suivent, et deux dépôts successifs du
même corpus décriraient des équipes différentes.

**Ce n'est pas de l'anonymisation, et c'est écrit dans le code** : dans une petite équipe,
l'ordre d'arrivée et le volume de travail réidentifient ; et un dépôt d'une petite
collection peut porter « annotateur-7 », donc révéler qu'il existe au moins sept
annotateurs. C'est une mesure de proportion — retirer le nom d'un artefact qui part et ne
bouge plus — pas une garantie.

**Deux surfaces nomment encore, délibérément** : `tools/rapport_accord_inter.py`, parce
qu'on ne peut pas réunir deux personnes pour arbitrer un désaccord si l'on ignore
lesquelles — et il se lit puis se jette, il ne se dépose pas ; et `GET /api/sauvegarde`,
qui est la base entière par construction. Le cliquet d'AUTH-5
(`tests/test_sorties_identite.py`) les tient déclarées, avec leur raison.

### À la sortie, les ACTES — sans leurs CHARGES (AUTH-11, 2026-09-24)

Le dépôt publie **qui a fait quoi, quand, sur quelle cible, sous quel run** ; il ne publie
plus `avant`/`apres`. Les colonnes qui partent sont nommées une fois, dans
`tools/_commun.COLONNES_EVENEMENT_PUBLIEES`, à côté de la liste blanche des cibles : deux
coupures pour deux questions — *quels actes* partent, et *quelles colonnes* de ces actes.

**Pourquoi.** Mesuré le 2026-09-23 : `journal._REGION_COLS` contient `ocr_texte` et les
charges étaient recopiées mot pour mot, si bien que l'export d'**une** collection emportait
le **texte des œuvres de toute l'instance** — y compris sans `--verbatim`. Deux
contournements d'un coup, celui du drapeau et celui du périmètre, et la promesse de DROIT-1
(« par défaut, présence et longueur ») franchie sans qu'aucune garde ne tombe. La charge
n'est pas ce qui fait la valeur du journal : **le contenu vit déjà dans les records**, qui
eux respectent le périmètre ET `--verbatim`, et la provenance d'un acte tient dans son
**attribution** et sa **date**, pas dans la recopie de ce qu'il a changé.

**Ce que le dépôt garde, et qui suffit à ce qu'on revendique** : l'agent pseudonymisé, sa
nature (`humain` / `moteur`), le type d'acte, la cible (`cible_table` + `cible_id`, stable
au point de survivre à la suppression), la date, et le run (`activite_id`). De quoi lire la
part machine et la part humaine, suivre une **chaîne de révision** sur une même cible, et
dater chaque geste — c'est exactement ce que `provenance_export.py` sérialisait déjà en
PROV-O et en TEI, qui **ne changent pas d'un iota**.

**Ce que le dépôt PERD, et il faut le savoir avant d'en avoir besoin** : on ne peut plus
reconstituer l'état d'une entité à une date, ni lire le **diff** d'un acte. Un audit sur
l'artefact déposé dira « cette région a été retouchée trois fois, par deux annotateurs, la
dernière le … » ; il ne dira pas « le texte disait ceci avant ». Pour cela il faut
l'instance, qui garde tout : **la table `evenement` n'est pas touchée**, et l'annulation
(D1) continue de lire ses charges — un test le verrouille, sans quoi « taire à la sortie »
pourrait dériver vers « cesser d'écrire », en silence.

**Reste au grain CORPUS, et ce n'est pas sous cette décision** : la table `activite` publie
`params`, `portee` et `comptes`, pour tous les runs de l'instance. Ce sont des réglages de
passe et des compteurs — aucun contenu de travail. `portee` désigne le périmètre du run
et vaut, mesuré : `{"planche_id": N}` pour une passe ML, `album_id`, `planche_id` ou
`{"corpus": true}` pour la normalisation de casse, et **rien du tout** pour la
réindexation NLP, qui n'en pose pas. `comptes` est **minimal par contrainte** (y verser
le message d'une exception enverrait des chemins serveur au dépôt). Les deux
sérialisations les portent, avant comme après cette décision.

## Ce qui est journalisé

**Passes ML** (`journal.passe_ml`, enveloppe les 3 routes directes + les 3 passes du worker
de lot — SIX appelants, et pas un de plus : le reindex NLP appelle `ouvrir_activite`
directement, dans `database.reindex_all`, et commit par lots. Corrigé le 2026-09-08 : cette
phrase l'y rangeait, et elle a failli faire croire que le correctif du jour le couvrait) — sans coupler le code pipeline : on **diffe** les régions de la planche avant/après.
Chaque passe = une `activite` ; les régions **créées** sont rattachées à leur run
(`regions.activite_id` = PROV `wasGeneratedBy`) et donnent un événement `creation` ; l'OCR
qui remplit une région donne un `modification`. Les régions machine *remplacées* par une
re-passe ne donnent pas d'événement individuel (bruit ; le travail humain, lui, est préservé
par SEG-1) mais sont **comptées** au bilan.

**Un run qui ne se termine pas laisse une trace lui aussi**, et il fallut un correctif pour
cela (2026-09-08). `passe_ml` clôturait bien l'activité sur `echec` — son commentaire disait
même « souvent rollback » — mais ce rollback, fait par l'appelant, emportait la ligne qu'on
venait d'écrire. Mesuré sur les deux chemins : **zéro** activité après une passe ratée, une
après un succès, en route directe comme en lot. Le journal ne gardait que ce qui avait
marché, c'est-à-dire exactement ce dont on a le moins besoin pour comprendre un corpus.

`passe_ml` défait donc la transaction LUI-MÊME, puis réinscrit une activité complète et la
valide seule. Une seconde connexion aurait été plus propre en théorie et fausse en pratique :
SQLite n'admet qu'un écrivain, elle aurait attendu le verrou que tient justement la
transaction qu'on veut défaire. Deux bilans : `{"echec": true}` et `{"interrompu": true}` —
une annulation demandée n'est pas une panne, et l'append-only ne se corrige pas.

Le bilan reste **minimal**, et c'est une contrainte et non un choix d'économie : `comptes`
SORT de l'instance (`metadonnees_collection`, `provenance_export`). Y verser le message de
l'exception enverrait des chemins serveur au dépôt — ce qu'AUTH-1 a fermé sur
`GET /api/export/json`. Un test le verrouille.

**Actes humains** (routes) — événement `creation`/`modification`/`suppression`/`validation`/
`lien`/`delien` avec **avant/après** : édition de zone (création, retouche, déplacement,
suppression **profonde**), annotation (note + tags), correction/validation grammaticale,
liens locuteur & présence, validation de planche. Une retouche d'un **pré-remplissage
machine** pose en plus la **surface dénormalisée** `regions.touche` + `date_modification`
(lue à moindre coût par l'indicateur de dérive, sans rejouer le journal).

## Indicateurs dérivés

`journal.indicateurs_provenance(conn, album_ids)` agrège :

- **régions** (scopé par album / `--collection`) : total, `machine` (généré par un run),
  `humaines`, `touchees`, **`derive`** (machine **puis** retouché), `taux_touche`,
  `taux_derive` ;
- **activités** / **événements** (grain **corpus** — un run/acte n'appartient pas à un album,
  et l'acte survit à la suppression de sa cible → non re-scopable) : comptes par type, par
  agent (humain vs moteur), bornes temporelles.

Branchés dans les exports : `metadonnees_collection.py` (`paradonnee.provenance` + tables
CSV `activite`/`evenement`) et `description_collection.py`
(`provenance_globale.audit`). Cf. `docs/export-metadonnees.md`.

## Export PROV-O / TEI

`tools/provenance_export.py` rejoue le journal (grain corpus, lecture seule) vers :

- **PROV-JSON** (W3C PROV) : activités, agents typés (`SoftwareAgent`/`Person`), entités et
  relations (`wasGeneratedBy` pour la création, `wasInvalidatedBy` pour la suppression,
  `used` pour les autres actes, `wasAssociatedWith`/`wasAttributedTo`, `wasInformedBy` pour
  acte ⟵ run parent). Modèle **pragmatique** : un *log d'actes* append-only, non un graphe à
  versionnement strict d'entités (le versionnement fin `wasRevisionOf` reste une extension) ;
- **TEI `<revisionDesc>`** : un `<change>` par acte (`who`/`when`/`type`/`target`),
  insérable dans un `<teiHeader>` d'export de contenu.

```bash
python tools/provenance_export.py                 # PROV-JSON + TEI (JSON) sur stdout
python tools/provenance_export.py --out-dir prov/  # provenance.json + revisionDesc.xml
```

## Périmètre & suites

- **Livré (v16)** : schéma + `journal.py` + câblage ML & routes humaines + indicateurs +
  export PROV-O/TEI. Tests : `tests/test_provenance_audit.py`.
- **D1 (undo) livré dessus** : `undo.py` **remonte** ce journal et rejoue l'inverse (pile via
  événements `annulation` — un type d'événement en plus ; append-only préservé). Ajustement :
  les actes d'annotation ciblent désormais le `region_id` (stable), pas l'id d'annotation
  (détruit à la suppression) → une annotation supprimée reste restaurable. Cf. `docs/undo.md`.
- **Extensions dormantes** : versionnement d'entités (`wasRevisionOf`), journalisation des
  changements de statut/verrou/rôle de planche, certitude de zone, export PROV-O *au fil de
  l'eau*.
