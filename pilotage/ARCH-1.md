---
chantier: ARCH-1
statut: interrompu
---

# ARCH-1 — décider du sort de main.py avant qu'il ne soit illisible

**Arrêté sur** — 2026-09-02, `34d013c` : la décision est PRISE (découpage par domaine,
par étapes) et les deux tiers sont faits. `main.py` passe de **4 483 à 3 146 lignes** ;
`socle.py` porte le socle commun, `routes/` trois domaines, et six gardes neuves tiennent
le tout. Reste à sortir Personnages (718) et Collections (615), après six accesseurs à
faire descendre — arrivée visée vers 1 800 lignes.

**Point de départ** — `main.py` portait toutes les routes : 2 897 lignes au 2026-08-27,
4 483 quand le seuil de 3 200 a été franchi et la décision prise.

## Reste

### Arbitrage
- [x] **Le choix est tranché et écrit** (2026-09-02) : découpage par DOMAINE vers des routeurs FastAPI, par étapes, chacune vérifiée par la suite entière avant la suivante. Décidé sur mesure et non à vue — chaque bloc n'utilise que 5 à 20 noms définis ailleurs, presque toujours les mêmes, ce qui rend les coutures réelles
- [x] **Le découpage ne casse ni les chemins ni le contrat d'API** : table de routage identique (131 entrées, aucune perdue ni gagnée), aucun test réécrit. Ce dernier point tient par le RÉ-EXPORT — deux cliquets interrogent ces noms SUR `main` — et par le choix des blocs : ceux dont un nom est remplacé par `monkeypatch.setattr(main, …)` restent en place, faute de quoi le remplacement cesserait d'agir en silence
- [x] Diff ligne à ligne contre l'état d'origine : **une seule ligne de code perdue** sur les cinq fichiers, un import devenu mort et retiré exprès

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

### Reste à sortir
- [ ] Six noms descendent dans le socle : `_patch_lexique`, `_ETATS_LEXIQUE`, `_attributs_de`, `_clause_personnage`, `_get_dimension`, `_get_personnage`, `_get_valeur` — accesseurs gardés et helpers de lexique, définis aujourd'hui dans le bloc Personnages et utilisés par Collections
- [ ] **Personnages & attribution** (718 lignes) devient `routes/personnages.py`
- [ ] **Collections** (615 lignes) devient `routes/collections.py` — après les six, d'où l'ordre
- [ ] `main.py` repasse sous le seuil de 3 200 et la veille cesse d'être en alerte

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

L'outillage refuse de DEVINER : les imports d'un module produit sont calculés depuis ses
noms libres, et un nom sans origine connue ARRÊTE l'extraction en nommant ce qui doit
descendre d'abord. C'est venu d'un échec — la première liste d'imports, dressée à l'œil, a
coûté 49 tests rouges.

Le dépôt n'a **aucune étape de build** et c'est un principe, pas un manque : on ouvre les
fichiers et on les lit. Un fichier de 3 000 lignes est en tension directe avec ce
principe — c'est ce qui rend le seuil réel plutôt qu'esthétique. Le second candidat est
`static/viewer.js` (2 500 lignes), non surveillé pour l'instant : un seul chiffre à
limite réelle, sinon la veille devient un tableau de bord de plus.
