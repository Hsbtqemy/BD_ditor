---
chantier: ARCH-1
statut: livré
---

# ARCH-1 — décider du sort de main.py avant qu'il ne soit illisible

**Arrêté sur** — 2026-09-03, `2e849bc` : le découpage est FAIT. `main.py` passe de
**4 483 à 1 811 lignes** — l'arrivée visée était « vers 1 800 ». `socle.py` porte le socle
commun (711 lignes), `routes/` **sept** domaines, et sept gardes tiennent le tout. Le seuil
de 3 200 n'est plus approché ; la veille cesse d'être en alerte.

**Point de départ** — `main.py` portait toutes les routes : 2 897 lignes au 2026-08-27,
4 483 quand le seuil de 3 200 a été franchi et la décision prise.

## Reste

### Arbitrage
- [x] **Le choix est tranché et écrit** (2026-09-02) : découpage par DOMAINE vers des routeurs FastAPI, par étapes, chacune vérifiée par la suite entière avant la suivante. Décidé sur mesure et non à vue — chaque bloc n'utilise que 5 à 20 noms définis ailleurs, presque toujours les mêmes, ce qui rend les coutures réelles
- [x] **Le découpage ne casse ni les chemins ni le contrat d'API** : table de routage identique à chaque étape (131 entrées au départ, 127 aujourd'hui — l'écart vient d'un décompte plus strict, pas d'une route perdue : chaque comparaison avant/après donne « aucune perdue, aucune gagnée »), aucun test réécrit. Ce dernier point tient par le RÉ-EXPORT — deux cliquets interrogent ces noms SUR `main` — et par le choix des blocs : ceux dont un nom est remplacé par `monkeypatch.setattr(main, …)` restent en place, faute de quoi le remplacement cesserait d'agir en silence
- [x] Diff ligne à ligne à chaque étape : **aucune ligne de code perdue**, hors les décorateurs rebranchés sur le routeur, les bannières de section et les listes d'imports repliées
- [x] Ce que ce diff ne disait PAS : il compte les lignes PERDUES, jamais celles devenues INUTILES. Le découpage a tué **vingt** imports au total — treize dans `main.py`, puis cinq et deux aux extractions suivantes. J'avais annoncé « une seule ligne perdue, un import mort retiré exprès » : exact, et muet sur les onze que la coupe venait de créer le même jour

### Ce que le découpage a cassé, et qui n'a été vu que de biais
- [x] **L'attribution du journal A3 disparaissait sur trois domaines.** `include_router` FIGE les dépendances de chaque route au moment de l'inclusion ; mes trois inclusions précédaient `app.router.dependencies.append(Depends(_capter_agent))`. Les routes sorties n'ont jamais capté l'utilisateur connecté — tout acte leur était attribué `NULL`. Rien ne cassait : les fonctionnalités marchaient, seule l'ATTRIBUTION manquait
- [x] Ce qui ne l'a pas vu : 646 tests unitaires verts, table de routage intacte, diff propre, quatre gardes silencieuses. Ce qui l'a vu : l'audit E2E de l'accord inter-annotateurs, et INDIRECTEMENT — alice et bob devenaient tous deux anonymes. Ce test avait été durci contre « la vacuité par l'amont » : sans ce durcissement, la modale vide aurait été parfaitement accessible et le test parfaitement vert

### Ce qui garde le découpage — `tests/test_decoupage_api.py`
- [x] Aucun **nom libre** dans un module, des DEUX côtés de la coupe. Un module aux noms libres s'importe sans broncher : le `NameError` n'arrive qu'à l'APPEL, et ressemble alors à un bug métier. La première extraction a produit 49 tests rouges pour cette seule raison
- [x] Aucune remontée vers `main`, ni du socle ni d'un module de routes. La mutation qui compte n'est pas l'import direct — Python le refuse bruyamment — mais l'import DIFFÉRÉ, qu'il accepte sans un mot
- [x] Tout routeur présent dans `routes/` est réellement INCLUS. Un `include_router` oublié ne casse rien : l'app démarre, le module s'importe, un domaine entier répond 404
- [x] Aucune route ne dépend de son RANG. Le découpage a déplacé 96 routes ; sans effet tant qu'aucune littérale n'est captable par une paramétrée — mesuré, 0 paire sur 127
- [x] Toute route capte l'agent courant, y compris celles arrivées par `include_router`
- [x] Les cinq gardes sont éprouvées par MUTATION, chacune la sienne

### Les trois dernières étapes (2026-09-03)
- [x] Sept noms descendent dans le socle — `_clause_personnage`, `_get_personnage`, `_get_dimension`, `_get_valeur`, `_attributs_de`, `_ETATS_LEXIQUE`, `_patch_lexique`. Ils étaient à CHEVAL sur la coupe : définis dans Personnages, utilisés par Collections. Sans cette descente, `routes/collections.py` aurait dû remonter vers `main`, ce qu'une garde interdit
- [x] **Personnages & attribution** devient `routes/personnages.py` (656 lignes)
- [x] **Collections** devient `routes/collections.py` (406) et **Lexique** `routes/lexique.py` (156)
- [x] `main.py` repasse sous le seuil de 3 200 — il est à **1 811**

### Ce que la relecture a trouvé, et qu'aucun test ne demandait
- [x] **Un module nommé d'après le registre des entités servait `/api/undo`.** Les deux routes de l'annulation (Ctrl+Z, D1) dormaient au milieu du bloc Personnages ; l'extraction les y a suivies. Aucun test ne demande dans QUEL module vit une route, et l'application répondait juste. Elles sont devenues `routes/annulation.py` — pas `undo.py`, qui importerait `undo`, la confusion pour laquelle `routes/figure.py` avait déjà été renommé
- [x] Deux autres désordres d'accrétion remis en place AVANT la coupe : l'affectation d'attributs, posée après le lexique alors qu'elle est l'« attribution » de Personnages ; et la bannière du lexique, loin de ses routes. Déplacements purs, vérifiés par diff
- [x] **Le ré-export rétrécissait tout seul.** Il était dérivé de ce que `main.py` utilise encore, alors que la règle écrite porte sur ce qui a DÉMÉNAGÉ — deux ensembles qui coïncidaient par chance. Trois noms manquaient déjà sans qu'aucun test ne bronche, parce qu'aucun ne les demandait ENCORE : muet à la création, bruyant des mois plus tard

### Deux gardes de plus, qui surveillent la COUTURE et non la coupe
- [x] `main.py` ré-exporte tout ce que `socle.py` définit — et l'IDENTITÉ est vérifiée, `main.X is socle.X` : un homonyme redéfini plus bas n'écraserait pas l'import bruyamment, les deux versions vivraient côte à côte
- [x] Aucun import mort des deux côtés de la coupe, l'exception du ré-export se DÉCLARANT par `# noqa: F401` — que le test lit, au lieu de connaître le cas par cœur
- [x] Elle a attrapé sa première victime à sa première exécution (`import undo` resté dans `personnages.py`), puis parlé aux DEUX extractions suivantes sans qu'on la sollicite. La dérive n'était pas un accident : c'est une propriété du geste

## Contexte

Cette fiche est la **cible de la veille à seuil** déclarée dans
`pilotage/journal.config.mjs` : `main.py`, seuil 3 200 lignes. Sans elle, le chiffre
monterait sur le tableau de bord sans que personne sache où la décision se prend.

Elle ne vient pas du backlog ni de l'audit — c'est un ajout de la mise en place du
journal, et le seul de la série.

**Ce que la méthode a coûté d'apprendre** (2026-09-02). L'ordre d'extraction ne se décide
pas au jugé : deux critères le fixent, et le second est invisible. Le COUPLAGE se mesure
(5 à 20 noms par bloc). Les noms remplacés PAR `main` dans les tests, eux, ne se voient
qu'en cherchant `monkeypatch.setattr(main, …)` — Segmentation, ShareDocs, Sauvegarde,
Jobs et Santé sont épinglés par là et restent en place.

**Un troisième critère est apparu en route, et il ne se mesure pas** : le DOMAINE réel du
bloc. Les deux premiers disent ce qu'on PEUT extraire ; celui-ci, ce qu'on extrait
ENSEMBLE. Le fichier unique tolérait l'accrétion sans conséquence — une fois la coupe
faite, elle devient le contenu d'un module, c'est-à-dire une affirmation.

L'outillage refuse de DEVINER : les imports d'un module produit sont calculés depuis ses
noms libres, et un nom sans origine connue ARRÊTE l'extraction en nommant ce qui doit
descendre d'abord. C'est venu d'un échec — la première liste d'imports, dressée à l'œil, a
coûté 49 tests rouges.

Le dépôt n'a **aucune étape de build** et c'est un principe, pas un manque : on ouvre les
fichiers et on les lit. Un fichier de 3 000 lignes est en tension directe avec ce
principe — c'est ce qui rend le seuil réel plutôt qu'esthétique. Le second candidat est
`static/viewer.js` (2 500 lignes), non surveillé pour l'instant : un seul chiffre à
limite réelle, sinon la veille devient un tableau de bord de plus.
