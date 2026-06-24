# Personnages, attribution & échelle d'analyse — exploration amont

> Exploration menée le 2026-06-23, en amont de toute implémentation.
> **Statut : exploration — rien n'est codé.** Ce document compare les modèles
> possibles pour l'axe « personnage » et fige la contrainte d'échelle
> (album **et** corpus entier) qui les départage. Il prépare les tickets
> **ANN-2** (entité personnage + lien bulle→personnage) et **ANA-1** (filtre par
> tag dans l'analyse) du `backlog.md`, sans les figer.
> **Approfondi puis arrêté le même jour** (§8–§11 : deux graphes, *mentions →
> entités*, analyse par attribut ; §12 : cadrage « variation multimodale » +
> structure d'attributs *facettée & émergente* ; **§13 : arbitrages clos —
> situation/scène dans le périmètre, granularité case, canonicalisation par
> primitives**). **Conception arrêtée** : prêt à dériver les lots d'implémentation
> (ANN-2 « mince » + ANA-1 substrat).

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

---

## 12. Résolution de session (2026-06-23) — variation multimodale & attributs émergents

**Cadrage retenu.** Le projet porte sur la **variation du français dans la BD
francophone** ; la contribution méthodologique est de **ne pas séparer texte et
image** — le reproche fait aux linguistes qui exploitent la BD comme du texte brut.
L'image entre donc comme **caractérisation de la parole**, pas comme comptage de
présence :

- **Parole = colonne vertébrale** (`bulle → locuteur`) : on étudie la variation *par
  profil de locuteur*. ✅ (arbitrage §11.1 tranché)
- **Présence** (qui est à l'image, muet compris) = **réservée au schéma, secondaire** ;
  son annotation n'est pas planifiée.
- La **consultation est déjà multimodale** (crops / vignettes : le texte n'est jamais
  vu détaché du dessin) ; ce qui manque, c'est la partie **requêtable** — d'où l'entité
  personnage et ses attributs.

**Structure d'attributs : *facettée ET émergente* (décidé).** Pas de vocabulaire en
dur. On fournit le **mécanisme** de fabrication du vocabulaire ; les catégories
**émergent**, comme pour les tags (« aucune taxonomie n'est imposée — les catégories
émergent du corpus »).

- Le chercheur **déclare des dimensions** (axes : « origine », « registre »…), qui sont
  des **données** créées au fil de l'eau — jamais du code.
- Sous chaque dimension, des **valeurs canoniques** (choisies dans l'existant ou créées),
  pour rester **agrégeables** : *ouvert à étendre, contrôlé en forme*.
- Les **personnages** reçoivent des affectations (dimension → valeur).

Esquisse du **mécanisme** (pas du contenu) :

- `personnage` — entité canonique (cf. §9)
- `attribut_dimension(nom)` — axes **émergents**
- `attribut_valeur(dimension_id, valeur)` — valeurs canoniques **émergentes**
- `personnage_attribut(personnage_id, valeur_id)` — affectation

**Conséquence — déblocage.** Le **contenu** du vocabulaire n'est **pas** à décider
maintenant : on construit le **contenant**, les linguistes le **remplissent** ensuite.
Plus de réunion-vocabulaire bloquante en amont. L'**émotion** n'est donc plus un objectif
figé : c'est *une facette émergente possible* parmi d'autres (le chercheur la crée s'il
veut, au niveau qu'il choisit — dimension de personnage, ou tag de situation).

**Encore ouvert (prochaine session) :**

1. Variation **entre** locuteurs (profil stable) seulement, ou **aussi intra**-locuteur
   par **situation / scène** (registre conditionné par la case) ? (cf. §8, axe B)
2. **Qui canonicalise** — à la volée (autocomplétion) vs passe de curation — pour
   l'**identité** des personnages *et* pour les **valeurs** d'attributs ? (cf. §9, §11.3)

---

## 13. Arbitrages clos (2026-06-23) — conception arrêtée

Les deux points ouverts au §12 sont tranchés.

### 13.1 Variation intra-locuteur (situation / scène) : **dans le périmètre**

- **Distinction** : la **situation/scène** (contexte dépeint qui conditionne le
  registre) est le **cœur de la variation**, à ne pas confondre avec la **présence**
  (visibilité — secondaire). Ce sont deux choses différentes.
- **Argument multimodal le plus fort** : l'image est **indispensable** à la situation
  — « Bonjour » ne dit pas le registre, *seul le dessin* le dit. C'est la meilleure
  démonstration de l'union texte-image.
- **Mécanisme d'attributs généralisé** : mêmes `attribut_dimension` /
  `attribut_valeur`, appliqués à **deux cibles** — le **personnage** (qui parle,
  axe A) et la **case** (la situation, axe B). (Recoupe et facette les tags de case
  existants.)
- **Alignement du modèle** : `bulle → locuteur` (*qui*) + texte (*quoi*) ; `case
  parente → situation` (*où / comment*). Contexte multimodal complet d'une bulle =
  **attributs du locuteur × attributs de la case parente**. Requête-thèse :
  **variation × profil × situation**.
- **Granularité : la case** (une case = une scène) d'abord. Pas de découpage en
  scènes spéculatif ; une vue « par scène » se reconstruit en regroupant les cases à
  attributs identiques, ou via une entité *scène* ajoutée **plus tard** si la
  répétition pèse (YAGNI).

### 13.2 Canonicalisation : **primitives, mode « à la volée » primaire**

- **Valeurs d'attributs** (dimensions + valeurs) : **à la volée** — autocomplétion sur
  l'existant + création si absent ; fusion ponctuelle si doublon. (Comme les tags.)
- **Identité des personnages** : le modèle *mentions → entités* permet, **au choix de
  l'annotateur**, l'**alias à la volée** (autocomplétion sur le registre) **ou** la
  **curation différée** (laisser en mention locale, relier plus tard). Dégradation
  gracieuse : avant aliasing, les mentions locales font déjà tourner l'analyse **par
  album** ; l'aliasing débloque le **corpus**.
- **À construire = 3 primitives** : (1) autocomplétion sur l'existant, (2) création à
  la volée, (3) **fusion de doublons**. Le mode « à la volée » suffit en
  **mono-utilisateur** (état actuel) ; la **curation** n'est qu'un *usage* de ces
  primitives, utile quand une **équipe** annote (post-INFRA-1). Pas de choix global
  « à la volée OU curation » à figer.

### 13.3 Suite

Conception **arrêtée**. Prochaine étape (hors de ce document) : **dériver les lots
d'implémentation** — **ANA-1** (filtre par tag, substrat sans regret, livrable
indépendamment) puis **ANN-2 « mince »** (entité canonique + mention locale +
lien locuteur + mécanisme d'attributs facetté sur personnage **et** case + facette
d'analyse). Présence, attributs riches et entité *scène* restent différés.
