---
chantier: QA-5
statut: interrompu
---

# QA-5 — la suite ne s'exécute jamais dans l'artefact livré

**Arrêté sur** — le commit `7046a57`, 2026-09-09 : **deux des trois items restants sont clos**, le conflit IIIF
l'ayant été par QA-4. Reste UN item, et c'est le plus gros : faire tourner les e2e quelque
part de reproductible.

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

## Reste

### Faire tourner la suite là où le code s'exécutera
- [x] La suite s'exécute DANS une image construite depuis `deploy/Dockerfile` (étape `test`, `CMD = pytest`) — verte, 2 skips
- [x] L'image de production reste dépourvue de `pytest`, `playwright` et `openpyxl` (vérifié par `find_spec` dans le conteneur) : **runtime 3,55 Go, inchangé** ; l'étape `test` pèse 3,76 Go et n'est jamais livrée
- [x] **Le résultat est lisible sans reconstruire.** `tools/identite_pile.py --identite` est lancé par le `CMD` de l'étape `test` AVANT la première ligne de pytest : il pose le commit servi (`BD_COMMIT`, désormais transmis à `test` comme il l'était à `runtime`), la version de Python, la plateforme, les empreintes des trois verrous, dix versions clés et l'état des moteurs. Un journal de construction gardé trois semaines reste donc lisible, là où il fallait RECONSTRUIRE pour savoir — c'est-à-dire remplacer la chose qu'on voulait examiner. `;` et non `&&` entre les deux commandes : le bandeau est un instrument de LECTURE, et un instrument cassé ne doit pas supprimer la mesure qu'il annote

### Ce que ça doit attraper
- [x] Les trois défauts du 2026-08-27 ont été RÉELLEMENT rejoués dans des images cassées à dessein. Verdict : **deux sur trois détectés**, le troisième NON — mesuré, pas raisonné
- [x] Le moteur ML manquant est détecté à la CONSTRUCTION : `tools/verifier_moteurs.py --exiger` tourne dans l'étape `runtime` (SANTE-1, `ed17b32`). Les trois défauts du jour y sont rejetés, 3/3 — là où la suite n'en voyait que 2
- [ ] Les E2E tournent quelque part de reproductible : elles exigent un navigateur, restent sur la machine de dev, et sont donc le dernier morceau non couvert par l'artefact
- [x] **Un écart de version entre le venv local et l'image est SIGNALÉ.** `tests/test_ecart_venv_image.py` fait échouer la suite sur toute divergence NON DÉCLARÉE portant une épingle délibérée, et sur tout paquet épinglé mais absent — cette seconde forme étant la plus traître, puisqu'elle fait SKIPPER au lieu d'échouer, et qu'un skip se lit comme un succès (QA-6). Les quatre écarts constatés le 2026-09-09 sont déclarés avec leur date et leur coût ; un troisième test interdit à ces déclarations de survivre à leur objet, sans quoi la liste deviendrait un cimetière qui excuse d'avance
- [x] **Le marqueur d'image est POSÉ, jamais deviné** — `ENV BD_IMAGE=1` dans l'étape `base`. La garde anti-cimetière se saute là-bas, et lui seul du module : ses déclarations décrivent un POSTE DE TRAVAIL, or l'image porte exactement les versions des verrous, si bien qu'elle les lirait toutes comme périmées. Reconnaître l'image à son chemin, à sa plateforme ou à l'absence de `.git` marcherait aujourd'hui et mentirait le jour où un poste sous Linux ressemblerait assez à l'image pour tromper la devinette
- [x] **La liste des exclusions du Dockerfile est complète et CHIFFRÉE** — elle en annonçait deux, il y en a quatre. La manquante était la plus grosse : `.dockerignore` exclut `deploy/` en entier pour une raison de sécurité, donc quatre modules d'infrastructure ne sont pas collectés. 924 tests mesurés dans l'image contre 959 sur le poste, et rien ne le disait

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
