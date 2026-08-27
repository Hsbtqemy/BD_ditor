---
chantier: SANTE-1
statut: interrompu
---

# SANTE-1 — /api/sante annonce vivants des moteurs morts

**Arrêté sur** — 2026-08-27, `ed17b32` : cœur `sante.py`, `/api/sante?profond=1`,
contrat d'image dans le Dockerfile. Éprouvé sur trois images cassées à dessein, 3/3
rejetées. Reste l'exposition à l'opérateur.

## Reste

### Le défaut
- [x] Un contrôle PROFOND existe à côté du rapide : `sante.profond()` importe réellement le moteur au lieu de le localiser
- [x] `/api/sante?profond=1` reflète le fait qu'un moteur **s'importe** ; la route sans paramètre garde son contrat historique, et un test vérifie qu'elle ne déclenche AUCUN import
- [x] Le coût reste tenable : voie profonde SÉPARÉE et mémoïsée par moteur — torch n'est chargé qu'une fois par process

### Ce qui doit être attrapé
- [x] Une pile où `import ultralytics` lève `torchvision::nms` est rapportée EN PANNE — build rejeté, `PANNE bulles, ocr`
- [x] Un Kumiko cassé par OpenCV 5 est rapporté en panne : Kumiko étant un SCRIPT et non une bibliothèque, on vérifie son point d'entrée ET la majeure d'OpenCV — build rejeté, `PANNE kumiko`
- [x] La cause est lisible : `{ok, erreur}` porte le type et le message de l'exception, borné à 300 caractères
- [x] Le moteur ABSENT est attrapé, ce que la suite ne sait pas faire : contrat d'image `tools/verifier_moteurs.py --exiger`, lancé au build — image sans modèle spaCy rejetée, `PANNE nlp`
- [ ] L'UI expose l'état profond : aujourd'hui il faut appeler `/api/sante?profond=1` à la main. Un opérateur sans shell ne le découvrira pas tout seul
- [ ] `docs/deploiement-docker.md` explique quoi faire d'un `PANNE` — la route dit ce qui ne va pas, pas encore quoi en faire

## Contexte

**Trois mensonges le même jour**, tous découverts en construisant l'image de déploiement :

1. spaCy absent de l'image — `lemmes` aurait dit `false`, donc celui-là était honnête ;
   mais rien ne signalait que la table `tokens` resterait vide.
2. `torchvision` incompatible avec le torch CPU — `bulles: true` annoncé sur une pile où
   le premier `import ultralytics` levait une exception.
3. OpenCV 5 écrasant OpenCV 4 — `kumiko: true` annoncé alors que la passe 1 renvoyait 500.

Dans les trois cas, `find_spec` a trouvé un module et en a conclu qu'il fonctionnait.

**Le raccourci est défendable en mono-poste** : le chercheur est devant sa machine, il
clique, il voit l'erreur, il comprend. C'est le DÉPLOIEMENT qui le rend nuisible — la
route de santé devient l'unique fenêtre sur l'état des moteurs, pour quelqu'un qui n'a
plus d'accès shell, et elle affiche vert sur une machine en panne. Un vert qui ne mesure
rien est pire que pas de contrôle.

Ne pas surcorriger : importer les trois moteurs à chaque appel rendrait `/api/sante`
inutilisable (plusieurs secondes, et le chargement de torch en mémoire). C'est l'objet de
la troisième case — le contrôle profond doit être distinct du contrôle rapide.

Lié à INFRA-1 : c'est le déploiement qui transforme ce raccourci en angle mort.
