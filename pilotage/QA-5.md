---
chantier: QA-5
statut: livré
---

# QA-5 — la suite ne s'exécute jamais dans l'artefact livré

**Arrêté sur** — le commit `a423f98`, 2026-09-09 : **tous les items sont clos.** La suite
tourne dans l'artefact, l'écart poste/image est mesuré et gardé, et les e2e ont rejoint
l'image — 184 passés, 4 ignorés, 0 échec en 26 min 08, sous un bandeau qui cite le commit servi.

**L'écart venv/image, enfin MESURÉ.** Ce chantier reposait depuis le 2026-08-27 sur une
anecdote — « 451 tests verts en local, trois moteurs morts dans l'image ». Le chiffre
existe maintenant : **51 paquets communs portent une version différente** entre le poste de
travail et l'artefact. Sur les 17 épingles délibérées, quatre problèmes :

| Paquet | Poste | Image | |
|---|---|---|---|
| `numpy` | 1.26.2 | **2.4.6** | saut de version MAJEURE, sous OpenCV, torch, scipy, scikit-image |
| `pillow` | 12.1.0 | 12.0.0 | le poste porte la version que QA-4 a dû écarter pour `iiif-prezi3` |
| `requests` | 2.31.0 | 2.32.5 | — |
| `iiif-prezi3` | ABSENT | 3.1.1 | `test_iiif_conformance_stricte` se skippe ici, ne tourne QUE dans l'image |

La suite passe donc au vert sur numpy 1.x et livre sur numpy 2.x. C'est la thèse du
chantier, cessée d'être une intuition.

**Ce qui a décidé de la forme de la garde.** Elle ne surveille PAS les 51, et ce n'est pas
une reculade : les transitifs flottent par construction, et ce Python est partagé avec
d'autres projets du poste. Une garde impossible à satisfaire s'apprend à ne plus se lire.
Elle surveille les 17 épingles DÉCIDÉES, où un écart se répare en une commande — les
quatre constatés sont DÉCLARÉS avec leur date et leur coût, et un troisième test interdit
à ces déclarations de survivre à leur objet.

**Et la suite dans l'image a trouvé ce que mes lancements locaux n'avaient pas vu**, ce qui
est précisément ce que ce chantier existe pour obtenir : le cliquet d'AUTH-5 exigeait que
le nouvel outil soit déclaré, et ma propre garde anti-cimetière échouait là-bas — un défaut
de conception, `ECARTS_ADMIS` décrivant un POSTE et l'image n'en étant pas un.

**Ce que le chantier a produit de plus utile n'est pas l'étape Docker, c'est ce qu'elle a
trouvé le jour même.** `/administration` à 320 px faisait défiler le CORPS de la page —
325 px de contenu pour 320 —, à cause de l'empreinte complète du commit affichée par le
panneau « Version servie » (INFRA-10) : 40 caractères sans un espace, insécables. Le poste
ne le voyait pas, l'image si. **La même chaîne, deux polices, cinq pixels.**

Et le défaut n'était pas propre à l'image : sur le poste il apparaît dès que la préférence
de police du navigateur passe à 20 px (350 px pour 320) — un réglage que
`test_e2e_police.CAS` audite DÉJÀ à cette largeur. Cet audit-là visitait donc la bonne page
au bon réglage, et posait l'AUTRE question, « le contenu est-il perdu ? », à laquelle un
`overflow-x` sur le corps de la page répond oui. La garde stricte, elle, ne s'exerçait qu'à
la police INSTALLÉE : verte ici, rouge là-bas. Elle a gagné l'axe de la police, et le
défaut se reproduit désormais partout.

**Trois affirmations fausses ont été corrigées dans les commentaires du chantier**, toutes
écrites par la session qui les a corrigées : « Chromium sur une `slim` n'a aucune police »
(`--with-deps` en installe quatre familles — pas DejaVu, ce qui sauve la ligne mais pas sa
raison) ; « DejaVu est le plus large des défauts courants » (jamais mesuré) ; et « la suite
collecte 924 tests dans l'image » — elle en COLLECTE 920, 924 étant le BILAN, qui compte
quatre modules sautés au niveau du MODULE sans jamais les collecter. Ce dernier chiffre
masquait la démonstration qu'il devait porter : `959 - 920 = 39`, exactement les tests
`deploy` que les exclusions déclarent.

**Trois limites restent, et aucune n'appartient à ce chantier.**

1. *Reproductible n'est pas automatique.* Rien ne lance cette image tout seul : deux
   commandes, à la main. L'item demandait un endroit reproductible, et c'est acquis ;
   l'exécution automatique est un sujet d'intégration continue, que ce dépôt n'a pas.
2. *Le navigateur s'installe en AVAL de la copie du code* — `e2e` hérite de `test`, qui
   fait `COPY . .`. Tout commit invalide donc la couche et redéclenche ~400 Mo de
   téléchargement, ce qui rend la construction dépendante du réseau : mesuré le
   2026-09-09, un `deb.debian.org` injoignable a fait échouer un build. La réparation
   existe — une étape intermédiaire sans code — mais elle duplique les variables
   d'environnement de `test`, donc crée un risque de divergence. ÉCARTÉE aujourd'hui,
   écrite ici.
3. *Les e2e coûtent 7,7 s par test* contre 0,29 s hors e2e, vingt-six fois plus. Aucune
   fixture de `conftest.py` ne déclare de portée : chacun des 184 tests lance son uvicorn
   et resème son décor, OCR compris. La répartition setup/call n'est PAS mesurée
   (`--durations` la donnerait), et l'explication qui vient à l'esprit — le chargement à
   froid de spaCy — ne tient pas telle quelle : 184 fois 10 s dépasserait le temps total.
   À ouvrir en fiche propre. Le remède évident, une portée `module`, s'achète avec de
   l'ISOLATION, et ce dépôt sait ce que coûte une garde qui cesse de voir.

## Reste

### Faire tourner la suite là où le code s'exécutera
- [x] La suite s'exécute DANS une image construite depuis `deploy/Dockerfile` (étape `test`, `CMD = pytest`) — verte, 2 skips
- [x] L'image de production reste dépourvue de `pytest`, `playwright` et `openpyxl` (vérifié par `find_spec` dans le conteneur) : **runtime 3,55 Go, inchangé** ; l'étape `test` pèse 3,76 Go et n'est jamais livrée
- [x] **Le résultat est lisible sans reconstruire.** `tools/identite_pile.py --identite` est lancé par le `CMD` de l'étape `test` AVANT la première ligne de pytest : il pose le commit servi (`BD_COMMIT`, désormais transmis à `test` comme il l'était à `runtime`), la version de Python, la plateforme, les empreintes des trois verrous, dix versions clés et l'état des moteurs. Un journal de construction gardé trois semaines reste donc lisible, là où il fallait RECONSTRUIRE pour savoir — c'est-à-dire remplacer la chose qu'on voulait examiner. `;` et non `&&` entre les deux commandes : le bandeau est un instrument de LECTURE, et un instrument cassé ne doit pas supprimer la mesure qu'il annote

### Ce que ça doit attraper
- [x] Les trois défauts du 2026-08-27 ont été RÉELLEMENT rejoués dans des images cassées à dessein. Verdict : **deux sur trois détectés**, le troisième NON — mesuré, pas raisonné
- [x] Le moteur ML manquant est détecté à la CONSTRUCTION : `tools/verifier_moteurs.py --exiger` tourne dans l'étape `runtime` (SANTE-1, `ed17b32`). Les trois défauts du jour y sont rejetés, 3/3 — là où la suite n'en voyait que 2
- [x] **Les E2E tournent dans un artefact** — étape `e2e` du Dockerfile, `FROM test` plus Chromium, placée AVANT `runtime` parce que l'étape par défaut d'un Dockerfile est la DERNIÈRE. 4,79 Go contre 3,76 pour `test` et 3,55 pour le livrable, qui n'en hérite RIEN. 184 passés, 4 ignorés, 0 échec en 26 min 08, bandeau d'identité en tête. Elle a rapporté dès sa première passe un défaut invisible sur le poste, ce qui est l'argument entier de ce chantier
- [x] **Un écart de version entre le venv local et l'image est SIGNALÉ.** `tests/test_ecart_venv_image.py` fait échouer la suite sur toute divergence NON DÉCLARÉE portant une épingle délibérée, et sur tout paquet épinglé mais absent — cette seconde forme étant la plus traître, puisqu'elle fait SKIPPER au lieu d'échouer, et qu'un skip se lit comme un succès (QA-6). Les quatre écarts constatés le 2026-09-09 sont déclarés avec leur date et leur coût ; un troisième test interdit à ces déclarations de survivre à leur objet, sans quoi la liste deviendrait un cimetière qui excuse d'avance
- [x] **Le marqueur d'image est POSÉ, jamais deviné** — `ENV BD_IMAGE=1` dans l'étape `base`. La garde anti-cimetière se saute là-bas, et lui seul du module : ses déclarations décrivent un POSTE DE TRAVAIL, or l'image porte exactement les versions des verrous, si bien qu'elle les lirait toutes comme périmées. Reconnaître l'image à son chemin, à sa plateforme ou à l'absence de `.git` marcherait aujourd'hui et mentirait le jour où un poste sous Linux ressemblerait assez à l'image pour tromper la devinette
- [x] **La liste des exclusions du Dockerfile est complète et CHIFFRÉE** — elle en annonçait deux, il y en a quatre. La manquante était la plus grosse : `.dockerignore` exclut `deploy/` en entier pour une raison de sécurité, donc quatre modules d'infrastructure ne sont pas collectés. l'image COLLECTE 920 tests contre 959 sur le poste — 39 de moins, exactement les quatre modules `deploy` —, et rien ne le disait. (Cette ligne a d'abord écrit 924, qui est le BILAN et non la collecte : un module sauté au niveau du MODULE y est compté sans être collecté. Corrigé le 2026-09-09 ; le chiffre faux masquait justement l'égalité qui rend la liste des exclusions vérifiable)

## Contexte

**Le dépôt n'avait pas d'artefact avant le 2026-08-27.** Toute sa culture de vérification
s'est construite sous une hypothèse qui était vraie : ce qu'on teste EST ce qu'on
exécute. Le principe « aucune étape de build » (CLAUDE.md) l'énonce même comme une
qualité, et c'en est une — on ouvre les fichiers, on les lit, on les lance.

Docker rompt cette hypothèse. Il crée pour la première fois un objet distinct de
l'environnement de dev, et tout raccourci de vérification qui était sûr sous l'ancienne
hypothèse cesse de l'être : 451 tests verts en local, trois moteurs morts dans l'image.

Mesuré le 2026-08-27 : `pytest` et `playwright` sont ABSENTS de l'image — par décision
délibérée (`3720f9f`), pour ne pas embarquer Playwright et son navigateur dans un
livrable. La décision était bonne pour le poids et **mauvaise pour la vérification** ;
les deux sont vrais, et la sortie n'est pas de remettre pytest en production mais de
séparer les étapes.

**Ce que la suite en image attrape, et ce qu'elle n'attrape pas — mesuré le 2026-08-27**
en construisant trois images délibérément cassées :

| Défaut rejoué | Suite dans l'image |
|---|---|
| OpenCV 5 écrasant OpenCV 4 (Kumiko) | **5 échecs**, exit 1 — détecté |
| `torchvision` de PyPI sur torch CPU | **3 échecs**, exit 1 — détecté |
| Modèle spaCy absent | **0 échec, exit 0** — **INVISIBLE** |

Le troisième cas est le plus instructif, et il limite ce chantier : la couche NLP est
conçue pour **dégrader proprement**, et les tests encodent la même hypothèse. La suite ne
peut pas signaler un moteur optionnel absent, parce que « moteur absent » est un état
qu'elle est écrite pour accepter — et c'est correct en développement local, où l'on
travaille couramment sans spaCy.

La conséquence est qu'une suite verte dans l'image **ne suffit pas**. Il faut un contrat
d'IMAGE distinct du contrat de test : l'artefact déclare les moteurs qu'il doit porter, et
un contrôle le vérifie à la construction. C'est le même geste que le contrôle profond de
SANTE-1, appliqué au build plutôt qu'au runtime.

Ce chantier est la racine commune de **SANTE-1** (la route de santé ne peut pas voir une
pile cassée), de **QA-4** (76 paquets flottants sous 15 épinglés) et du constat **T8**
(un test qui passe sur un état vide). Chacun est réparable seul ; aucun ne suffit tant
que rien ne s'exécute dans l'objet qu'on livre.
