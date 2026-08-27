---
chantier: QA-5
statut: interrompu
---

# QA-5 — la suite ne s'exécute jamais dans l'artefact livré

**Arrêté sur** — 2026-08-27, `79d3c8d` : le Dockerfile est en trois étapes et la suite tourne
dans l'image (2 skips, tous deux documentés). Reste les E2E et le conflit IIIF.

## Reste

### Faire tourner la suite là où le code s'exécutera
- [x] La suite s'exécute DANS une image construite depuis `deploy/Dockerfile` (étape `test`, `CMD = pytest`) — verte, 2 skips
- [x] L'image de production reste dépourvue de `pytest`, `playwright` et `openpyxl` (vérifié par `find_spec` dans le conteneur) : **runtime 3,55 Go, inchangé** ; l'étape `test` pèse 3,76 Go et n'est jamais livrée
- [ ] Le résultat est lisible sans reconstruire : un échec dit quel test, dans quelle image, sur quelle version des dépendances

### Ce que ça doit attraper
- [x] Les trois défauts du 2026-08-27 ont été RÉELLEMENT rejoués dans des images cassées à dessein. Verdict : **deux sur trois détectés**, le troisième NON — mesuré, pas raisonné
- [ ] Le moteur ML manquant est détecté à la construction, ce que la suite ne peut PAS faire : l'image déclare les moteurs qu'elle DOIT avoir et un contrôle le vérifie. Sans ça, une image sans spaCy passe la suite à 100 % vert tout en tuant quatre chantiers livrés (Exploration, ANN-4, NLP-1, ANN-5)
- [ ] Les E2E tournent quelque part de reproductible : elles exigent un navigateur, restent sur la machine de dev, et sont donc le dernier morceau non couvert par l'artefact
- [ ] Un écart de version entre le venv local et l'image est signalé, au lieu d'être découvert par un utilisateur

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
