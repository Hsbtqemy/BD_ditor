# La collection : un niveau, ou un calque ?

> **Réflexion ouverte le 2026-10-16 avec Hugo. Aucune décision n'est prise** : Hugo a demandé
> de garder la réflexion sans trancher. Ce qui suit dit ce qu'on a constaté, les pistes
> examinées, et les orientations exprimées, chacune pour ce qu'elle est. Organigramme des
> couches : artefact « Les couches de BéDéditeur ».

## 1. Le constat : à quoi sert la collection aujourd'hui

Vérifié dans le code le 2026-10-16. **Comme cadre de travail, elle n'existe pas** : on ne voit
pas ses albums (la Bibliothèque n'en montre que le nombre ; on retrouve les collections d'un
album depuis sa fiche, dans l'autre sens), on ne filtre pas la liste des albums sur elle, et
ni l'Atelier, ni les lots, ni la Recherche, ni l'Exploration ne s'y bornent ; deux collections
ne se comparent pas.

**Ce qu'elle fait réellement** : (1) les **droits** — c'est l'unité d'accès, et toute la garde
d'`autorisation.py` repose sur elle ; (2) la **sortie** — description FAIR, métadonnées, IIIF,
dépôt ShareDocs, et le titre d'un export d'album, qui borne son vocabulaire ; (3) la **portée
d'un terme** local ; (4) de la tuyauterie — la choisir à la création d'un album, y ranger, la
règle de destruction. Des fonctions d'administration et de sortie, pas de recherche.

**D'où cela vient.** Née le 2026-07-16 (v14) comme le *jeu de données* — « objet, périmètre,
critères de sélection », une collection = un dépôt = un DOI (`docs/dictionnaire-metadonnees.md`)
—, elle est devenue l'unité d'accès le 2026-08-27 (AUTH-2), faute d'autre objet ; le
2026-10-10, le projet (COL-3) a repris le rôle d'objet scientifique. Le rôle de sous-corpus
n'a jamais été construit.

## 2. Ce que Hugo voudrait (orientations, non tranchées)

- **Le projet est l'entièreté du corpus, défini scientifiquement** : la constitution d'un
  objet scientifique.
- **La collection sert à créer des sous-corpus à l'intérieur du projet** — à condition de se
  rendre visible et que les actions puissent se faire à l'intérieur d'elle.
- **On garde le mot « collection »** : « chantier » désigne une tâche à effectuer, ce qui n'est
  pas le but de ce niveau.
- **Le partage des annotations** faites dans une collection sur un album rangé aussi ailleurs
  devrait être une **option**.
- Une remarque générale, pas une demande de transformer la collection : un regroupement peut
  être **par identité** (le corpus définit la collection : une série, un auteur, une période —
  il change à mesure que le fonds grandit) ou **en anthologie** (le chercheur définit son corpus
  : une liste fixe, argumentée, qui se cite).

## 3. La question de fond : dans la hiérarchie, ou posée dessus ?

**Les données disent déjà « calque ».** Depuis la v30, l'album porte lui-même son projet
(`albums.projet_id`) ; il est dans 0, 1 ou N collections du même projet — des ensembles qui se
chevauchent, pas des tiroirs. **Les droits disent « niveau »** : on n'atteint un album qu'à
travers une collection qu'on lit, et un album sans collection part au fonds. L'organigramme
projet › collection › album suit les droits, pas les données.

**Le niveau** (chaque album dans une seule collection, le projet découpé sans recouvrement) :
un arbre simple, des droits naturels ; mais pas de sous-corpus qui se recoupent, donc pas de
comparaison libre, et la question du partage des annotations disparaît.

**Le calque** (le projet contient tous ses albums ; les collections sont posées dessus et se
recoupent) : ce que la base est déjà ; des sous-corpus qui se comparent ; une collection qu'on
choisit comme cadre. Il reste à dire qui voit un album du projet qu'aucun calque ne porte — ce
qui ramène à la question des accès.

## 4. Les pistes examinées, et ce qu'elles coûtent

- **Une couche d'annotations propre à chaque calque** (la transcription commune à l'album, les
  annotations interprétatives propres à la collection ou partagées, selon l'option). Elle donne
  tout son sens à l'option de Hugo, mais elle est **très coûteuse** : toutes les tables
  d'annotation porteraient un calque (tags, notes, attributs, locuteurs, présences, relevés de
  grille), et chaque analyse, export, citation, Ctrl+Z et règle de suppression devrait dire
  quelle couche il compte. Rien ne dit encore que quelqu'un en ait besoin.
- **Les grilles d'annotation (ANN-7) couvrent peut-être l'essentiel du besoin** : deux équipes
  qui annotent le même album avec deux grilles ne se marchent pas dessus, leurs relevés étant
  distincts. L'option de Hugo pourrait alors s'obtenir à bas coût : une collection dit quelles
  grilles y sont actives, et n'affiche que leurs relevés — un filtre d'affichage, pas un
  stockage séparé. Ce qui rouvrirait la couche par calque : deux collections qui auraient
  besoin d'annotations DE MÊME NATURE et différentes sur le même album.
- **Déplacer les accès au projet** (rôles de projet, avec une restriction « réservée » en
  exception) : un modèle plus simple, mais la plus grosse refonte depuis AUTH-2, sur la garde
  dont tout dépend. Rien ne l'impose tant que les accès par collection fonctionnent.
- **Rendre la collection visible et en faire un cadre** : sans toucher aux données — la
  Bibliothèque (`UX-18`), une collection courante à côté du projet courant, l'Atelier, les lots,
  la Recherche et l'Exploration qui s'y bornent (la tranche 4 de `COL-3` prévoit déjà de les
  borner au projet), la comparaison de deux collections.

## 5. Ce que la session de pilotage en pense (2026-10-16)

Le calque est juste sur le fond ; la couche d'annotations par calque est à éviter tant qu'aucun
cas réel ne la demande ; les accès peuvent rester sur la collection. Et une mise en garde : le
modèle a beaucoup bougé en une journée, sans utilisateurs réels pour l'éprouver. L'étudiant de
master qui va annoter des albums à doubles pages en sera un ; ce qu'il fera dira mieux que la
conception ce dont les collections ont besoin.

## 6. Ce qui rouvrira la question

- la maquette de la Bibliothèque (`UX-18`), dont l'arbre dépend de la réponse ;
- la tranche 4 de `COL-3` (la Recherche et l'Exploration bornées) ;
- `ANN-7`, si une grille doit s'activer par collection et non seulement par projet ;
- un premier usage réel de sous-corpus.
