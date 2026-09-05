---
chantier: ARCH-2
statut: livré
---

# ARCH-2 — une montée de FastAPI a rendu les cliquets aveugles à 56 % des routes

**Arrêté sur** — inventaire de routes partagé, plancher dérivé du source appelé par les
quatre tests qui énumèrent, plafond `fastapi<0.137` et skip ciblé d'`openpyxl` ;
commit `1bceafe`, 5 septembre. Vérifié sous les DEUX formes d'`app.routes` — 683 tests
sous 0.137, 89 sous 0.133 dans un venv jetable, mêmes 116/122 routes cloisonnées. Le
travail vit sur la branche `arch-2-cliquets-aveugles` : le démenti « hors de origin/main,
origin/dev » est donc attendu, et c'est le merge qui le lève.

## Reste

### Faire échouer un inventaire qui rétrécit
- [x] Un cliquet dont l'inventaire tombe sous un seuil ÉCHOUE au lieu de passer : `inventaire_routes.exiger_plancher()` est appelée par les **quatre** tests qui énumèrent, et elle MORD — éprouvée en leur rendant l'ancien inventaire, 53/122, 23/51, 53/122
- [x] Ce plancher se dérive du code : `plancher_source()` compte les décorateurs de route par AST sur `main.py` + `routes/*.py`, et donne 122 / 51 GET — exactement ce que l'app sert
- [x] Un plancher unique et lointain ne suffit pas : les quatre l'appellent CHACUN, sans quoi la suite serait rouge pendant que le cliquet concerné resterait vert — et c'est cette lecture-là qui a laissé passer la panne
- [x] `exiger_plancher` est elle-même éprouvée (`test_l_exigence_de_plancher_mord`) : c'est le point unique dont le silence rendrait les quatre muets ensemble

### Rendre les cliquets capables de voir ce qu'ils prétendent inventorier
- [x] `test_autorisation` traverse la forme paresseuse et voit **122 routes**, dont 116 cloisonnées et 6 hors périmètre écrit — les 69 nouvellement visibles étaient toutes déjà tranchées, aucune dette cachée
- [x] `test_sorties_identite` balaie **51 routes GET** et non 23 ; il filtre désormais sur `dependant` et non sur `isinstance(r, APIRoute)`
- [x] `test_decoupage_api` compare toujours source et inventaire ; sa réparation ne l'a pas rendu complaisant, et `test_un_routeur_non_inclus_reste_invisible` le prouve — un routeur jamais inclus doit rester absent de l'inventaire, sinon le cliquet cesserait de voir un `include_router` manquant
- [x] L'aplatissement vit à UN endroit, `tests/inventaire_routes.py` ; la marche transitive des dépendances y a rejoint l'aplatissement — elle existait en **trois** exemplaires, deux récursifs et un itératif
- [x] Le balayage fonctionne sur les DEUX formes : reconnaissance par COMPORTEMENT (`effective_candidates`) et non par le nom privé `_IncludedRouter`, éprouvée sur doublures (`test_inventaire_routes.py`) puisqu'un environnement n'installe jamais qu'une des deux formes
- [x] Deux autres tests étaient aveugles aux mêmes 69 routes, non repérés à la rédaction de cette fiche : le contrôle de l'ORDRE de la table (`hasattr(r, "path")`) et surtout **la garde de `_capter_agent`** (`hasattr(r, "dependant")`, avec le commentaire « montages StaticFiles, non concernés ») — celle-là gardait donc exactement les sept routeurs dont elle est née

### Empêcher la dérive qui l'a causé
- [x] `requirements.txt` ne peut plus atteindre une version qui change la forme de `app.routes` : `fastapi>=0.133,<0.137`, avec la raison écrite au-dessus de la borne
- [x] La spec et le verrou ne peuvent plus se contredire (`tests/test_verrou_dependances.py`) : toute version épinglée doit satisfaire sa spec, et un pin sans spec doit porter sa raison au-dessus de lui — `opencv-python` est le seul, et il l'avait déjà
- [x] Le plafond est déclaré comme une RÈGLE et non comme un cas : `PLAFONNES` dit pourquoi ce paquet-là est borné, et un test exige que la borne existe tant que la raison vaut

### Faire grandir l'inventaire qui n'a pas rétréci
- [x] `test_csp` est examiné pour lui-même : il n'était PAS concerné, ses surfaces étant écrites à la main — immunité par accident, mode d'échec inverse. Il porte désormais son propre contrôle : toute route servant du HTML doit figurer dans `SURFACES_HTML`, dans les deux sens

### Un second constat qui n'était pas « sans rapport »
- [x] Quatre tests ÉCHOUAIENT sur `openpyxl` absent, ils skippent : trois en entier (`test_export_metadonnees`, dont le SUJET est l'onglet XLSX), et le cliquet AUTH-5 seulement sur ses deux invocations XLSX — il vaut par son exhaustivité, et le mettre en pause pour un tableur le rendrait muet sur dix autres surfaces
- [x] Le skip partiel n'est pas silencieux : le cliquet AFFICHE les surfaces qu'il n'a pas regardées, et une égalité (non une inclusion) interdit au skip d'en retirer une de plus
- [x] Le skip est éprouvé sans dépendre de la machine qui lance la suite : les deux réponses de `find_spec` sont simulées, parce qu'un skip vérifiable seulement par accident d'environnement n'est pas vérifié

## Contexte

**Ce qui s'est passé.** FastAPI 0.137 n'aplatit plus les routeurs inclus dans
`app.routes` : il y dépose sept objets `_IncludedRouter` qui délèguent à l'exécution. Les
routes RÉPONDENT — `/api/analyse/info` rend 200 avec sa charge utile, une route inventée
rend 404 — mais elles ne sont plus énumérables. `app.routes` contient 53 `APIRoute` et
7 `_IncludedRouter` là où le dépôt en attend 122.

**Pourquoi c'est grave, et pas seulement gênant.** DEUX cliquets tirent leur inventaire de
`app.routes` : l'autorisation (« toute route consulte la portée, ou figure sur
`HORS_PERIMETRE` avec sa raison ») en voyait 53 sur 122 ; les sorties d'identité balayaient
23 routes GET au lieu de 51, parce qu'ils filtrent sur `isinstance(r, APIRoute)` et que
l'objet paresseux n'en est pas un. Aucun des deux ne s'est mis à échouer : ils ont continué
de PASSER en ne regardant plus que la moitié du contrat. Une garde qui tombe est un
incident ; une garde qui approuve en n'ayant rien vu est un mensonge, et c'est celui-là
qu'on a eu.

**QUATRE tests étaient aveugles, pas deux.** Cette fiche en annonçait deux ; le compte
s'est fait en réparant. Les deux autres vivent dans `test_decoupage_api.py`, et le second
est le plus inquiétant du lot : **la garde de `_capter_agent`**, celle qui existe
précisément pour la panne du 2026-09-02, sautait tout objet sans `dependant` — commentaire
à l'appui, « montages StaticFiles, non concernés ». Elle gardait donc exactement les sept
routeurs inclus dont elle est née, en ne regardant que les routes restées dans `main.py`.
La panne d'attribution pouvait revenir à l'identique sous une suite verte.

Et elle a une propriété que les autres n'ont pas : **elle ne se protège pas elle-même**.
Elle cherche des routes NON conformes, donc un inventaire tronqué ne lui retire que des
routes conformes — elle devient plus verte à mesure qu'elle voit moins. Mesuré en rendant
aux quatre cliquets l'ancien inventaire : trois planchers ont tiré, celui-là n'a rien dit.
C'est pourquoi elle appelle `exiger_plancher` explicitement, et pourquoi un plancher
unique posé ailleurs n'aurait pas suffi.

**Les deux constats n'étaient PAS sans rapport, et c'est le plus intéressant de la
journée.** `test_le_semis_est_visible` portait déjà un plancher — `assert len(vus) >= 55`,
un chiffre recopié. Il visait la bonne chose et **il aurait tiré** : sous FastAPI 0.137 le
balayage tombait à 33 surfaces. Il n'a pas tiré parce qu'`openpyxl` manquait —
`_balayer_outils` mourait sur la quatrième invocation, bien avant cette ligne. Le second
constat a donc étouffé le seul plancher que le dépôt possédait déjà. **Un plancher ne
protège que ce qui le PRÉCÈDE**, et un échec dur sur un extra optionnel n'est pas un
inconfort : c'est un interrupteur qui coupe le courant en amont des gardes. Le plancher
est maintenant dérivé (toute route GET non déclarée hors balayage doit être balayée), et
il n'y a plus rien devant lui pour l'éteindre.

**Le troisième cliquet, la CSP, n'est PAS concerné** — contrairement à ce qu'affirmaient la
première rédaction de cette fiche, la docstring de `test_decoupage_api` et `CLAUDE.md`,
tous trois corrigés. Son inventaire est une liste ÉCRITE À LA MAIN (`SURFACES_HTML`,
`SURFACES_BALAYEES`), donc rien ne pouvait le rétrécir. C'est une immunité par accident,
pas par conception : une liste manuelle ne grandit pas avec l'application, et le mode
d'échec est simplement l'autre — elle oublie ce qu'on ajoute au lieu de perdre ce qu'elle
voyait. Les deux gardes échouent en sens contraire, et aucune ne le dit toute seule ; d'où
son contrôle propre, qui confronte la liste aux routes servant réellement du HTML.

**Ce qui a sauvé la mise.** `test_decoupage_api` est le seul à avoir bronché, parce qu'il
compare une source à un inventaire au lieu de parcourir l'inventaire seul. Sa docstring
disait déjà le risque mot pour mot : « c'est de là que les trois cliquets du dépôt tirent
leur inventaire ; si elle n'y était pas, ils passeraient au vert en ne regardant plus
rien. » Il a été écrit contre un `include_router` oublié ; il a attrapé une montée de
version. C'est l'argument entier du plancher dérivé.

**Le plafond, et ce qui a été écarté avec.** La production n'était pas touchée, et c'est le
verrou qui l'a protégée : `requirements.lock` pose `fastapi==0.133.0`, l'image livrée est
donc dans l'ancienne forme. Le `.venv` local, lui, avait dérivé — `requirements.txt` disait
`fastapi>=0.110`. L'écart entre l'environnement qui MESURE et l'image qui SERT est
précisément ce que QA-5 dénonçait dans l'autre sens (« 451 tests verts en local, trois
moteurs morts dans l'image ») ; ici il jouait à l'envers — c'est le local qui voyait juste,
et il voyait que la garde ne gardait plus rien.

**Faire converger EXACTEMENT la spec et le verrou a été écarté le 2026-09-05.** Un
`>=0.133,<0.134` fermerait l'écart au chiffre près, mais `requirements.txt` cesserait
d'être une spec pour devenir un doublon du verrou — et le modèle du dépôt est explicite
(« les requirements*.txt restent la spec lisible ; CE fichier est le verrou »). Le plafond
retenu s'arrête à la FRONTIÈRE DE FORME : un venv neuf peut encore prendre 0.136 quand
l'image sert 0.133, mais `app.routes` y a la même forme, donc plus la panne d'ARCH-2. Le
résidu est nommé : deux environnements peuvent toujours différer d'un patch. Ce qui le rend
tolérable n'est pas le plafond, c'est le plancher — une différence qui MESURERAIT autre
chose fait maintenant échouer les quatre cliquets, quelle qu'en soit la cause, y compris
une cause qu'on n'a pas prévue.

**Monter le verrou à 0.137 a été écarté aussi**, et pour une raison de calendrier : le code
d'aplatissement sait lire les deux formes, donc le dépôt POURRAIT suivre — mais embarquer
une montée de FastAPI en production dans un chantier de harnais de test, sur une instance
mise en service le 2026-09-05 (INFRA-1), échange un risque mesuré contre un risque non
mesuré.

**Un détail d'environnement, pour la prochaine lecture.** `openpyxl` est apparu dans le
`.venv` en cours de chantier : les quatre échecs ont cessé de se reproduire localement
avant d'être corrigés. Le correctif a donc été vérifié en SIMULANT l'absence
(`monkeypatch` sur `find_spec`), et non en constatant un vert — c'est ce que fait
`test_le_skip_d_extra_retire_exactement_les_surfaces_visees`, et c'est la seule forme de
vérification qui ne dépende pas de ce qui se trouve installé ce jour-là.
