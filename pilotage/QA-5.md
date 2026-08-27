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
- [ ] Les trois défauts du 2026-08-27 sont RÉELLEMENT rejoués et détectés : construire une image avec OpenCV 5 (ou sans spaCy) doit faire échouer la suite. Raisonné, jamais éprouvé — et c'est exactement le genre d'affirmation que ce chantier existe pour refuser sur parole
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

Ce chantier est la racine commune de **SANTE-1** (la route de santé ne peut pas voir une
pile cassée), de **QA-4** (76 paquets flottants sous 15 épinglés) et du constat **T8**
(un test qui passe sur un état vide). Chacun est réparable seul ; aucun ne suffit tant
que rien ne s'exécute dans l'objet qu'on livre.
