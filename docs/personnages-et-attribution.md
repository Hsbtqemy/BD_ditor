# Personnages, attribution & échelle d'analyse — exploration amont

> Exploration menée le 2026-06-23, en amont de toute implémentation.
> **Statut : exploration — rien n'est codé.** Ce document compare les modèles
> possibles pour l'axe « personnage » et fige la contrainte d'échelle
> (album **et** corpus entier) qui les départage. Il prépare les tickets
> **ANN-2** (entité personnage + lien bulle→personnage) et **ANA-1** (filtre par
> tag dans l'analyse) du `backlog.md`, sans les figer.
> **Approfondi le même jour** (cf. §8–§11 : deux graphes, modèle *mentions →
> entités*, analyse par attribut) — **à reprendre en session suivante** sur les
> trois arbitrages du §11.

## 1. Le besoin

L'étude porte sur **les émotions et la représentation des minorités**. Deux axes :

- **Qui parle** — idiolectes, registres *par personnage* (analyse linguistique de
  la parole attribuée).
- **Qui est représenté** — présence/visibilité à l'image, attributs de
  représentation.

Contrainte transverse (posée le 2026-06-23) : la **sélection doit fonctionner à
deux échelles** — au niveau d'un **album**, *et* au niveau du **corpus entier**
(toutes œuvres confondues).

## 2. État actuel (ce sur quoi on construit)

- `personnage` n'est qu'un **type de région** (`TYPES_REGION`) — une boîte
  dessinée sur l'image. **Aucune identité récurrente**, aucun lien locuteur.
- Les **tags** s'appliquent à n'importe quel niveau de la hiérarchie
  (`region → annotation → annotation_tags → tags`), sans taxonomie imposée.
- L'**analyse est déjà album-ou-corpus** : `/api/analyse/{frequences,concordance,
  comparaison}` prennent un paramètre `album` **optionnel**. Omis ⇒ **corpus
  entier** ; fourni ⇒ album. Les valeurs analysées sortent de `tokens_effectifs`
  (correction humaine ⊕ auto), jointe à `regions` puis `planches`.

**Conséquence clé** : pour les filtres *linguistiques et par tag*, l'échelle
album/corpus est **déjà gratuite** (présence ou non du filtre `album`). C'est
seulement l'axe **identité de personnage** qui demande un choix de modèle.

## 3. La contrainte qui départage : « corpus entier »

Analyser l'idiolecte d'un personnage **à travers tout le corpus** exige une
**identité de personnage qui traverse les albums**. Cela élimine le modèle
intermédiaire :

| Modèle | Album | Corpus entier | Coût | Verdict |
|---|---|---|---|---|
| **A — Bulle / tag** (pas d'entité personnage) | ✅ natif | ✅ natif | **S** | Substrat immédiat |
| **B — Entité personnage par album** | ✅ | ❌ « Tintin »(A) ≠ « Tintin »(B) | M–L | **À éviter** (casse la contrainte) |
| **C — Registre de personnages corpus/série** (identité récurrente) | ✅ | ✅ | **L** | Cible pour l'axe « qui » |

Lecture : on reste au niveau **bulle/tag** (A, suffisant aux deux échelles
aujourd'hui), **ou** on s'engage sur un **registre de personnages au niveau
corpus** (C). **On saute B** : le faire par album obligerait à tout refaire pour
satisfaire le corpus.

## 4. Recommandation phasée

1. **Maintenant — A / ANA-1 (effort S).** Filtre par **tag** dans les trois routes
   d'analyse (étendre `_analyse_filtres` d'un `EXISTS` sur `annotation_tags`),
   facette tag dans Exploration. Marche **album et corpus** d'emblée. Livre tout
   de suite « distribution des lemmes parmi les bulles taguées *colère* », à
   n'importe quelle échelle. *Portée hiérarchique des tags* (bulle seule vs
   héritée de la case) : paramètre `tag_scope`, défaut hérité (cf. discussion
   ANA-1) — **mais ne rattrape pas un tag posé sur un personnage**, car ce lien
   n'existe pas encore (c'est précisément l'objet de C).
2. **Désigné ensuite — C / ANN-2 (effort L, décision requise).** Registre de
   personnages au niveau **corpus** (ou série), lien **bulle → locuteur**, facette
   « par personnage » dans recherche/exploration/comparaison. À spécifier
   sérieusement avant code.
3. **ANA-1 monte par-dessus** : une fois C en place, l'analyse se filtre **par tag
   ET par personnage**, aux deux échelles, sans retoucher A.

Cette séquence ne jette rien : A reste le substrat, C ajoute l'axe « qui ».

## 5. Décisions à valider avec l'équipe (avant de coder C)

1. **Locuteur seul, ou locuteur + représenté ?**
   - *Qui parle* : lien **bulle → personnage** (nécessaire aux idiolectes).
   - *Qui est représenté* : lien **région `personnage` (boîte) → personnage**
     (présence à l'image). Les deux sont utiles mais distincts ; commencer par le
     locuteur, garder le représenté ouvert.
2. **Granularité de l'identité : corpus, ou série ?** Un registre **corpus** est
   le plus simple à requêter (« toute la parole de X ») ; un découpage **série**
   évite les homonymes entre univers. Recommandation : identité **corpus**, avec
   un champ `serie`/`oeuvre` facultatif pour désambiguïser.
3. **Attributs de personnage = même décision qu'ANN-1.** Genre, origine, rôle…
   pour « représentation des minorités » sont un **vocabulaire contrôlé** — la
   *même* décision que le schéma d'annotation contrôlé (ANN-1). À prendre **une
   fois**, partagée. ⇒ **Différer les attributs riches** du lot mince ; ne livrer
   d'abord que l'**identité + le lien locuteur**.
4. **Désambiguïsation à la saisie** : comment l'annotateur choisit « ce
   personnage » (autocomplétion sur le registre, création à la volée, fusion de
   doublons) ? UI à esquisser ; impacte la qualité de l'agrégation corpus.

## 6. Esquisse technique (indicatif, non arrêté)

- **Schéma** (lot mince) : table `personnages(id, nom, serie?, …)` au niveau
  corpus ; table de liaison `bulle_locuteur(region_id UNIQUE → regions,
  personnage_id → personnages)` (une bulle a au plus un locuteur).
  `ON DELETE` : détacher la liaison, **jamais** supprimer le personnage avec une
  région. Migration via `SCHEMA_VERSION` + `_migrate()`.
- **Analyse** : ajouter `personnage` (et `a_personnage`/`b_personnage`) à
  `_analyse_filtres` → un `EXISTS`/join `bulle_locuteur`, **orthogonal** au filtre
  `album` ⇒ l'échelle corpus/album reste pilotée par `album`, sans effort
  supplémentaire.
- **Attribution** : route `PUT /api/regions/{id}/locuteur`, panneau d'attribution
  côté Visionneuse (mode Annotation), autocomplétion sur `/api/personnages`.
- **Tests** : attribution + filtre d'analyse par personnage aux deux échelles
  (album et corpus) ; non-régression sur les routes d'analyse existantes.

## 7. Ce que ce document ne tranche pas

Le **périmètre exact du lot mince** (attributs inclus ou non), la **granularité**
(corpus vs série) et le **« représenté » vs « locuteur seul »** restent à
valider. Tant que ce n'est pas figé, **A / ANA-1** est livrable sans risque et
sans dette : il n'anticipe aucune de ces décisions.

---

## 8. Approfondissement — deux graphes, pas un lien

Le modèle A/B/C écrase une distinction qui structure tout : la représentation se
mesure sur **deux relations différentes vers la même entité personnage**.

- **Qui parle** : `bulle → personnage` (locuteur). Sert l'**idiolecte / le registre**.
- **Qui est à l'image** : `région personnage (boîte) → personnage` (présence). Sert
  la **visibilité**.

La métrique de représentation la plus parlante les **croise** : *présence vs
parole* — « tel groupe apparaît dans N cases mais ne parle que dans M bulles »
(qui est **vu mais pas entendu**). Elle est incalculable avec un seul lien. Le
schéma doit donc **prévoir les deux liens** vers l'entité, même si on n'implémente
que le locuteur d'abord.

## 9. Modèle d'identité retenu en exploration — *mentions → entités* (deux niveaux)

« Personnage par album » (option B) était mal posé. La bonne réponse au dilemme
*album vs corpus* est le patron de **résolution d'entités / coréférence**, à deux
niveaux :

- **Mention locale** (dans l'album) : l'annotateur marque « cette bulle = *le
  capitaine* » — un libellé **local**, rapide, **sans recherche globale** pendant
  l'annotation.
- **Entité canonique** (corpus) : registre de personnages ; chaque mention locale
  est **aliasée** vers une entité canonique.
- L'analyse passe par l'alias : filtrer par entité = agréger **toutes ses mentions,
  tous albums** ; restreindre à un album = ses mentions là.

Pourquoi c'est supérieur à B :
- **Ergonomie album** *et* **agrégation corpus**, sans choisir.
- **Dégradation gracieuse** : avant canonicalisation, les mentions locales font déjà
  tourner l'analyse **par album** ; la canonicalisation **débloque le corpus**
  ensuite, **sans rien re-saisir**.
- L'**autocomplétion** à la saisie (suggérer une entité existante) canonicalise *à
  la volée* la plupart des cas ; il ne reste qu'une **passe de curation** pour les
  ambigus / doublons.

C'est le seul modèle qui livre « corpus entier » sans imposer une saisie globale
coûteuse dès le départ. (B « plat » reste écarté ; ici le *local* n'est qu'une
**mention**, pas une identité concurrente.)

## 10. Analyse par attribut, pas (que) par individu

Question de recherche réelle : rarement « la parole de Tintin », mais « la parole
des personnages marqués **[genre=F / origine=X / rôle=secondaire]** », à l'échelle
du corpus. Conséquences :

- Les **attributs** vivent sur l'**entité canonique** (stables, partagés par toutes
  ses mentions).
- La facette d'analyse qui compte le plus est l'**attribut de classe**, pas
  l'individu. L'entité personnage est le **porteur** ; l'attribut contrôlé est
  l'**analysable**.
- Donc le **vrai chemin critique de la finalité est le vocabulaire contrôlé** de ces
  attributs — c'est-à-dire **ANN-1** (schéma d'annotation contrôlé), *plus* que
  l'identité individuelle. À décider **une seule fois**, partagée ANN-1 ⇄ attributs
  personnage.

## 11. Cible affinée & arbitrages pour la prochaine session

**Lot mince visé** : mention locale `bulle → locuteur` + entité canonique + alias +
facette d'analyse par personnage / attribut (album et corpus). **Différés** : le
2ᵉ graphe (présence) et les attributs riches. **ANA-1** reste le substrat sans
regret, livrable indépendamment.

**À trancher avec l'équipe :**
1. **Parole seule, ou parole + présence ?** (décide si on prévoit le 2ᵉ graphe au
   schéma dès maintenant, même non implémenté).
2. **Unité d'analyse de la représentation** : attribut de classe (genre/origine/
   rôle) seul, ou **aussi l'individu** comme objet d'étude ?
3. **Qui canonicalise** : l'annotateur *à la volée* (autocomplétion), ou une **passe
   de curation** dédiée par un référent ? (impacte l'UI et la qualité corpus).
