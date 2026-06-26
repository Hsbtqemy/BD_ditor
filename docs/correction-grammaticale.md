# Correction humaine de l'étiquetage grammatical — spécification (lot 1)

> Conception menée le 2026-06-14, en discussion de fond.
> **Statut : implémenté (lot 1) — màj 2026-06-23.** La correction humaine des tokens
> (lemme / POS / morph), la couche *overlay* `token_correction`, la vue
> `tokens_effectifs` (valeur effective + provenance + « à revérifier ») et l'UI
> (panneau **Grammaire** de la Visionneuse, routes `/api/regions/{id}/tokens…`) sont
> en place. **Différés** : ré-ancrage par alignement (§4), normalisation morphologique
> (§10), provenance modèle par correction (§8), colonne explicite de statut de
> relecture (§2). Ce fichier reste la référence de conception du chantier.

## 1. Pourquoi

Le corpus sera traité par des **linguistes universitaires**. L'étiquetage
grammatical produit par spaCy (POS, lemme, morphologie ; cf. [pipeline/nlp.py](../pipeline/nlp.py)
et la table `tokens`) est une **baseline machine**, faillible. Pour ces utilisateurs,
la couche grammaticale **corrigée à la main** *est* l'objet savant : un étiquetage
automatique non corrigeable serait inacceptable.

La correction doit donc exister **dès la v1**, et respecter la philosophie déjà en
place dans le projet pour la re-segmentation (cf. [pipeline/segmentation.py](../pipeline/segmentation.py)) :

> **L'auto est remplaçable, le travail humain est préservé.**

La colonne `regions.source` (`'kumiko'` = auto) et la logique de
`segment_planche`/`_transfer_case_annotations` incarnent déjà ce principe au niveau
des régions. On le décline ici au niveau du **token**.

## 2. Le modèle : deux couches, une valeur effective

Décision retenue (**A1**, après comparaison avec une variante « colonnes sur
`tokens` ») : une **couche overlay séparée**.

- **Couche AUTO** — la table `tokens` actuelle. Reste 100 % machine, régénérée
  librement (DELETE+INSERT) à chaque réindexation, comme aujourd'hui.
- **Couche CORRECTION** — une table `token_correction` distincte, qui porte les
  corrections et validations humaines. **Le reindex n'y écrit jamais** (il recalcule
  seulement un drapeau d'ancrage). C'est la garantie centrale : *une réindexation ne
  peut pas corrompre le travail humain.*
- **Valeur effective** = correction (si vivante) sinon auto, exposée par une **vue**
  SQL `tokens_effectifs`. Toutes les surfaces d'analyse liront cette vue → requêtes
  simples, sans gérer le `COALESCE` à la main.

### États (provenance), jamais bloquants

| État | Sens |
|------|------|
| `auto` | valeur spaCy, non touchée |
| `corrige` | un humain a imposé une valeur |
| `valide` | un humain a **confirmé correct** (avec ou sans changement) |

**Aucun traitement n'est gaté sur la validation.** Recherche, exploration et export
travaillent sur la valeur effective quel que soit l'état. `valide` n'est qu'une
**surcouche qualité** (filtre optionnel : « seulement le validé », « l'auto à
réviser »), jamais un prérequis. Un corpus à 0 % validé reste pleinement exploitable.

**Auteur (INFRA-2).** Chaque correction/validation enregistre l'utilisateur connecté
(en-tête `Remote-User` posé par le proxy d'auth) dans `token_correction.auteur` —
exposé en `corr_auteur` dans `tokens_effectifs`, affiché au token et **filtrable**
(paramètre `auteur` sur frequences / concordance / comparaison, symétrique de
`provenance`). Valider ne réécrit pas le correcteur d'origine (`COALESCE`). NULL en
local (pas de proxy) : l'action reste anonyme.

Le **statut de relecture d'une planche** (« à faire / en cours / faite », l'idée
d'« Attente ») est un axe *différent* — un statut de **travail**, au niveau planche,
distinct du statut épistémique d'un token. Il est **dérivé** des statistiques de
provenance de la planche ; pas de colonne dédiée en v1 (on ajoutera un override
explicite seulement si le besoin se confirme).

## 3. Schéma (migration `SCHEMA_VERSION → 9`)

> Mise à jour : la v8 a été prise par le verrou de planche (§6, livré à part) ; la
> couche de correction grammaticale est donc la **v9**. La table `token_correction`
> et la vue `tokens_effectifs` sont créées par `SCHEMA_SQL` (`CREATE … IF NOT EXISTS`),
> donc la migration ne fait qu'acter la version. **Tranche 1.1 implémentée** (schéma
> + vue + reindex préservant) ; endpoints (1.2) et UI (1.3) à suivre.

Migration **purement structurelle → instantanée, sans spaCy** (fidèle au principe de
[database.py](../database.py) `_migrate`). Les corrections n'existant pas encore, rien
à reconstruire.

```sql
-- COUCHE HUMAINE : préservée, jamais écrasée par un reindex
CREATE TABLE token_correction (
    id          INTEGER PRIMARY KEY,
    region_id   INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL,    -- position du token dans le doc spaCy de la région
    forme       TEXT NOT NULL,       -- forme de surface visée → ancrage anti-dérive
    lemme       TEXT,                -- valeur corrigée ; NULL = auto accepté pour ce champ
    pos         TEXT,                -- UPOS ; NULL = auto accepté
    morph       TEXT,                -- traits Universal Dependencies ; NULL = auto accepté
    etat        TEXT NOT NULL DEFAULT 'corrige',  -- 'corrige' | 'valide'
    auteur      TEXT,
    date_modif  TEXT DEFAULT (datetime('now')),
    obsolete    INTEGER NOT NULL DEFAULT 0,       -- 1 = texte dérivé → à revérifier
    UNIQUE(region_id, ordre)
);
CREATE INDEX idx_tcorr_region ON token_correction(region_id);
CREATE INDEX idx_tcorr_etat   ON token_correction(etat);

-- LECTURE : valeur effective (humain ⊕ auto) + provenance unifiée
CREATE VIEW tokens_effectifs AS
SELECT t.region_id, t.ordre, t.texte,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.lemme END, t.lemme) AS lemme,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.pos   END, t.pos)   AS pos,
       COALESCE(CASE WHEN c.obsolete = 0 THEN c.morph END, t.morph) AS morph,
       CASE WHEN c.id IS NULL OR c.obsolete = 1 THEN 'auto'
            ELSE c.etat END                                          AS provenance
FROM tokens t
LEFT JOIN token_correction c
       ON c.region_id = t.region_id AND c.ordre = t.ordre;

-- VERROU de planche (cf. §6), distinct de `validee`
ALTER TABLE planches ADD COLUMN verrouillee TEXT;   -- horodatage (NULL = déverrouillée)
```

Remarque : « valider sans changer » = une ligne `token_correction` avec `etat='valide'`
et `lemme/pos/morph` à NULL → la vue renvoie la valeur auto, mais avec
`provenance = 'valide'`. Un seul mécanisme couvre correction *et* validation.

## 4. Ancrage et dérive du texte

Une correction est ancrée sur `(region_id, ordre)` + la **`forme`** visée. L'`ordre`
est la position du token dans le doc spaCy ; il est **déterministe pour un texte +
modèle donnés**.

Au reindex (cf. §5), pour chaque correction de la région :
- token auto présent à `ordre` **et** sa forme == `forme` → `obsolete = 0` (vivante) ;
- sinon (texte modifié, position disparue, tokenisation différente) → `obsolete = 1` :
  la correction est **conservée mais signalée « à revérifier »**, et **n'est pas
  appliquée** à la valeur effective tant qu'un humain ne l'a pas re-confirmée.

**Conséquence — la cascade.** Insérer/supprimer un mot tôt dans une région décale
tous les `ordre` suivants → beaucoup de corrections passent `obsolete` alors que les
mots n'ont pas changé.

- **v1 : cascade acceptée**, neutralisée par l'**ordre de travail recommandé** :
  *stabiliser l'OCR d'abord, corriger la grammaire ensuite*. Sur texte stable, zéro
  cascade. À documenter comme bonne pratique côté UI.
- **Plus tard (si besoin avéré)** : ré-ancrage par **alignement de séquences** (LCS)
  pour suivre les tokens qui se décalent au lieu de les orpheliner.

## 5. Réindexation préservante

`reindex_region(conn, region_id)` devient :
1. régénérer `tokens` (auto) — DELETE+INSERT, inchangé ;
2. ré-ancrer : recalculer `obsolete` pour les `token_correction` de la région (§4) —
   **sans jamais supprimer ni modifier les valeurs humaines** ;
3. reconstruire la colonne FTS `lemmes` de la région à partir de **`tokens_effectifs`**
   (donc la recherche reflète les corrections vivantes).

`reindex_all(conn)` applique la même logique en lot (via `nlp.pipe`, commit par
chunks), comme l'actuel — seule l'étape 2/3 change.

Les corrections vivent dans une table que le reindex ne réécrit pas : leur intégrité
ne dépend pas de la correction de l'algorithme de merge.

## 6. Verrou de planche (cadenas)

Protection **préventive et déclarative**, complémentaire de la préservation
(curative) : « cette planche est finie, **ne lance aucun traitement automatique
dessus** ». Couvre précisément le risque « relancer l'OCR/segmentation en lot sans
faire attention ».

Comportement de `planches.verrouillee` (horodatage ; distinct de `validee`, car
verrou = protection ≠ validé = assertion de qualité) :
- **les jobs en lot** ([pipeline/jobs.py](../pipeline/jobs.py), passes segmenter /
  détecter-bulles / ocr) **sautent** les planches verrouillées et le **signalent**
  (jamais en silence) ;
- une **relance directe** depuis la Visionneuse sur une planche verrouillée **exige de
  déverrouiller** d'abord (le geste volontaire reste possible, l'accident est bloqué) ;
- le verrou cible **les passes automatiques** ; l'**édition manuelle** humaine
  (texte, tags, corrections grammaticales) **reste libre** ;
- toggle 🔒 dans la Visionneuse ; **badge visible dans la Bibliothèque**, là où on
  lance les lots.

## 7. Intégration avec la re-segmentation (exigence)

Aujourd'hui, `segment_planche` décide de **conserver ou supprimer** une région selon
qu'elle est « touchée par l'humain » — mais ce test ne regarde que la table
`annotations` et `source`. **Il ignore `token_correction`.**

→ Une bulle océrisée + corrigée grammaticalement, *sans note ni tag*, pourrait être
supprimée par une re-segmentation **délibérée** (et ses corrections avec, via
CASCADE). Le verrou (§6) protège le cas distrait ; ceci protège le cas
délibéré-mais-pas-vu.

**Le test « travail humain ? » de `segment_planche` doit inclure
« la région a-t-elle des `token_correction` ? ».** Exigence du lot, pas option.

## 8. Upgrade de modèle et rapport d'accord

Lors d'un re-tag avec un modèle plus riche (`fr_core_news_lg`, futur transformer) :
la couche `tokens` auto reflète le **nouveau** modèle ; les corrections humaines
restent (l'humain prime). Le ré-ancrage (§4) revérifie les formes — une correction
sur **texte stable reste vivante** même si le nouveau modèle « voit » autre chose.

Bénéfice mesurable, en une requête : *parmi les tokens où un humain a imposé un POS,
combien le nouveau modèle retrouve-t-il seul ?* (`tokens.pos` vs
`token_correction.pos`). Un **rapport d'accord modèle↔humain** qui objective le gain
d'un passage à `lg`. Le travail humain devient l'**étalon** d'évaluation des modèles.
*(Optionnel : `modele_auto` par correction pour une provenance fine ; le `meta` global
+ la date suffisent en v1.)*

## 9. Endpoints d'édition

- **Corriger un token** — `PUT /api/regions/{rid}/tokens/{ordre}`
  `{lemme?, pos?, morph?, etat}` → upsert dans `token_correction` (`forme` = texte du
  token auto courant), `obsolete = 0`, puis rebuild FTS de la région. Champ absent =
  NULL = « auto accepté pour ce champ ».
- **Valider une région d'un coup** (geste courant) —
  `POST /api/regions/{rid}/grammaire/valider` → une ligne `valide` par token.
  Évite la validation mot à mot.
- **Annuler** — `DELETE /api/regions/{rid}/tokens/{ordre}` → suppression de la ligne
  de correction → retour à l'auto pur.

Concurrence : `UNIQUE(region_id, ordre)` → dernier écrit gagne par token ; suffisant
pour une petite équipe (WAL gère déjà les courses écriture/lecture, cf.
[tests/test_live_race.py](../tests/test_live_race.py)).

## 10. Morphologie

Édition via un éditeur de **traits UD** (`Tense=Past`, `Mood=Ind`…), stockés en
**chaîne canonique triée** (égalité et requête stables). Requête d'un trait :
`morph LIKE '%Tense=Past%'` — acceptable à l'échelle du corpus. Normalisation dans
une table `token_trait` (un trait/ligne) **différée** jusqu'à preuve que l'analyse par
trait est centrale.

## 11. UI — panneau token (Visionneuse)

La modalité « texte annoté par token » devient **éditable**, par région :
- table mot / lemme / POS / morph, chaque champ éditable (sélecteurs **UPOS** + traits
  **UD**, lemme en texte libre) ;
- **indicateur de provenance** par token (auto / corrigé / validé) ;
- **drapeaux « à revérifier »** (`obsolete`) mis en évidence ;
- bouton « valider la région » ; annulation par token ;
- rappel de la **bonne pratique** : corriger l'OCR avant la grammaire (§4).

C'est ici qu'atterrira le « round-trip » des surfaces d'analyse (lot 3+) : *je vois
une erreur → j'ouvre la Visionneuse → je corrige → je reviens à ma place*.

## 12. Périmètre

**Dans le lot 1** : §3 (schéma + migration v8), §5 (reindex préservant), §7
(intégration re-seg), §6 (verrou), §9 (endpoints d'édition), §11 (panneau token).
Livrable et utile **isolément** : on peut corriger et valider la grammaire, et
protéger les planches finies, sans aucune autre surface.

**Hors lot 1 (feuille de route ultérieure)** :
- **Lot 2** — endpoint de **requête par token** sur `tokens_effectifs` (POS / lemme /
  trait morpho, filtre de provenance) : le socle commun aux deux surfaces.
- **Lot 3** — **Recherche+++** : état dans l'URL (liens profonds partageables,
  Retour sans perte), facettes grammaticales, aperçu en place (lecture seule), export.
- **Lot 4** — **Exploration** : distributions / croisements / comparaison de
  sous-corpus sur le même socle.
- **Lot 5** — transverse : nav persistante, round-trip Visionneuse, reprise d'état.
- **Différés** : ré-ancrage par alignement (§4), normalisation morpho (§10), override
  de provenance modèle par correction (§8), colonne explicite de statut de relecture (§2).

## 13. Récapitulatif des décisions

1. Modèle **A1** : overlay `token_correction` séparé + vue `tokens_effectifs`.
2. Trois états **auto / corrigé / validé**, **validation jamais bloquante**.
3. Le reindex **ne touche jamais** les corrections (seul `obsolete` est recalculé).
4. Ancrage `(region_id, ordre, forme)` ; dérive du texte → `obsolete` ; **cascade
   acceptée en v1** + bonne pratique « OCR d'abord ».
5. **Verrou planche** distinct de `validee` ; bloque l'auto, pas le manuel.
6. La re-segmentation **doit compter les corrections** comme travail humain.
7. Couche auto/humaine séparées → **rapport d'accord modèle↔humain** gratuit.
8. Morpho en chaîne UD + `LIKE` ; normalisation différée.
9. Statut de relecture **dérivé** (pas de colonne en v1).
