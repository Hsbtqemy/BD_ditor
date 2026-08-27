---
chantier: QA-4
statut: à venir
---

# QA-4 — le verrou ne couvre que 15 paquets sur 91

**Point de départ** — QA-1 a livré `requirements.lock` en juin 2026, en épinglant
délibérément les seules dépendances DIRECTES. Le premier build d'image, le 2026-08-27, a
montré ce que cette limite laisse passer.

## Reste

### Refermer le trou
- [ ] Un verrou TRANSITIF complet existe pour l'image de déploiement, produit **depuis l'image Linux construite** (`pip freeze`) et non sur la machine de dev
- [ ] Le Dockerfile installe ce verrou complet, et deux constructions à un mois d'écart donnent le même jeu de versions
- [ ] La procédure de régénération est écrite : quand et comment refaire le gel, et comment vérifier que la suite reste verte après

### Un conflit déjà ouvert entre deux fichiers épinglés
- [ ] `requirements-export.txt` et `requirements.lock` cessent d'être mutuellement exclusifs : `iiif-prezi3==3.1.1` exige `Pillow<=12.0.0` (dépendance OBLIGATOIRE, pas un extra) quand le verrou épingle `pillow==12.1.0` — pip répond `ResolutionImpossible`
- [ ] Le test de conformance IIIF (`tests/test_export_metadonnees.py:246`) s'exécute quelque part : aujourd'hui il se skippe dans l'image ET sur la machine de dev, donc **nulle part**, alors que `docs/roadmap.md` donne l'IIIF pour « validé via iiif-prezi3 »
- [ ] `docs/roadmap.md` dit ce qui est réellement vérifié aujourd'hui, ou la vérification est rétablie — les deux conviennent, la situation actuelle non

### Cohérence
- [ ] `torch` et `torchvision` ne sont plus épinglés dans le Dockerfile pendant que `requirements.lock` prétend être « LE verrou » : soit ils y entrent, soit son en-tête dit où ils vivent
- [ ] Le cas des paquets JUMEAUX est traité explicitement — deux distributions fournissant le même paquet d'import, dont une seule est épinglée

## Contexte

**L'objection d'origine de QA-1 était juste, et elle ne tient plus.** Son en-tête dit :
« verrou des DIRECTES seulement, PAS un pip-compile transitif — les wheels ML sont
spécifiques à la plateforme ; figer les transitifs sur des wheels Windows casserait un
déploiement Linux ». C'était exact tant que le gel se faisait sur la machine de dev.
Depuis le 2026-08-27, l'image Linux se construit ici : un `pip freeze` produit DANS cette
image est par construction sur la bonne plateforme, et l'objection tombe.

Mesuré le 2026-08-27 dans `bdediteur:cpu3` : **91 paquets installés, 15 épinglés** (13 par
le verrou, 2 par le Dockerfile), donc **76 flottants**. Les 13 pins du verrou sont tous
respectés — ce n'est pas eux le problème.

Le problème est ce qui flotte à côté, et le couplage. `thinc 8.3.13` est le cœur natif de
spaCy, lié à son ABI — le même genre de couple que torch/torchvision, qui a précisément
cassé ce jour-là. `pydantic 2.13.4` et `starlette 1.6.0` flottent sous une `fastapi`
épinglée. Un jour, l'un d'eux bougera, et l'image se construira sans erreur en livrant une
application cassée.

**Le conflit Pillow est de la même famille et déjà actif.** Le verrou a été établi en
juin 2026 avec « les versions connues-bonnes du moment » ; `pillow` y est passé à 12.1.0,
ce qui a rendu `iiif-prezi3` ininstallable à côté. Personne ne l'a vu parce que le test
concerné ne CASSE pas : il se SKIPPE, et un skip se lit comme un succès. Piste de
résolution la moins risquée : redescendre `pillow` à 12.0.0 — rien n'indique que 12.1.0
soit requis par quoi que ce soit — puis relancer la suite pour le vérifier plutôt que le
supposer.

**L'incident opencv est le symptôme, pas l'exception.** Un pin sur
`opencv-python-headless` ne servait à rien tant que son jumeau `opencv-python`, tiré en
transitif par `ultralytics`, pouvait l'écraser dans le même dossier `cv2/` — et casser
Kumiko en silence. Corrigé en épinglant le jumeau (`4b02d79`), mais ce correctif est
ponctuel : rien ne dit qu'un autre couple ne se présentera pas.
