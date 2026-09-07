---
chantier: QA-4
statut: interrompu
---

# QA-4 — le verrou ne couvre que 15 paquets sur 91

**Arrêté sur** — le conflit `pillow`/`iiif-prezi3` est fermé et la validation IIIF stricte
s'exécute de nouveau, commit `39d1f12`, 7 septembre. Restent le verrou TRANSITIF (zone 1,
entière, elle demande Docker) et la zone Cohérence.

**Point de départ** — QA-1 a livré `requirements.lock` en juin 2026, en épinglant
délibérément les seules dépendances DIRECTES. Le premier build d'image, le 2026-08-27, a
montré ce que cette limite laisse passer.

## Reste

### Refermer le trou
- [ ] Un verrou TRANSITIF complet existe pour l'image de déploiement, produit **depuis l'image Linux construite** (`pip freeze`) et non sur la machine de dev
- [ ] Le Dockerfile installe ce verrou complet, et deux constructions à un mois d'écart donnent le même jeu de versions
- [ ] La procédure de régénération est écrite : quand et comment refaire le gel, et comment vérifier que la suite reste verte après

### Un conflit déjà ouvert entre deux fichiers épinglés
- [x] `requirements-export.txt` et `requirements.lock` cessent d'être mutuellement exclusifs : `iiif-prezi3==3.1.1` exige `Pillow<=12.0.0` (dépendance OBLIGATOIRE, pas un extra) quand le verrou épingle `pillow==12.1.0` — pip répond `ResolutionImpossible`
- [x] Le test de conformance IIIF (`test_iiif_conformance_stricte`, dans `tests/test_export_metadonnees.py`) s'exécute quelque part : aujourd'hui il se skippe dans l'image ET sur la machine de dev, donc **nulle part**, alors que `docs/roadmap.md` donne l'IIIF pour « validé via iiif-prezi3 »
- [x] `docs/roadmap.md` dit ce qui est réellement vérifié aujourd'hui, ou la vérification est rétablie — les deux conviennent, la situation actuelle non
- [ ] La construction de l'image confirme que `iiif-prezi3` s'y installe et que `test_iiif_conformance_stricte` y PASSE : non vérifié le 2026-09-07, Docker n'étant pas lancé — et c'est exactement la réserve de QA-5, le venv local n'est pas l'artefact livré

### Cohérence
- [ ] `torch` et `torchvision` ne sont plus épinglés dans le Dockerfile pendant que `requirements.lock` prétend être « LE verrou » : soit ils y entrent, soit son en-tête dit où ils vivent
- [ ] Le cas des paquets JUMEAUX est traité explicitement — deux distributions fournissant le même paquet d'import, dont une seule est épinglée

## Un second verrou est apparu à côté, et il n'est pas celui-ci — 2026-09-07

Relevé en revérifiant les références de cette fiche. ARCH-2 a posé le 2026-09-05 un
dispositif qui RESSEMBLE à ce que la première zone demande, sans y répondre : `fastapi` est
plafonné dans `requirements.txt` (`>=0.133,<0.137`), `requirements-dev.lock` épingle la
version qui a protégé la production, et `tests/test_verrou_dependances.py` **interdit
désormais à une spec et à son verrou de se contredire**.

Ce qui est fermé et ce qui ne l'est pas : la contradiction entre deux fichiers du dépôt est
attrapée — donc le conflit `pillow` / `iiif-prezi3` de la zone suivante est exactement le
genre de chose que cette garde voit. Ce qui reste entier, c'est le TRANSITIF : 76 paquets
flottent toujours sous les épinglés, et aucun verrou produit depuis l'image Linux n'existe.
Une garde de cohérence entre deux listes ne dit rien de ce qui n'est sur aucune des deux.

À vérifier avant d'ouvrir le chantier : si `test_verrou_dependances` échoue déjà sur le
couple `pillow`/`iiif-prezi3`, la deuxième zone est plus avancée qu'écrit ici.

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

## Ce qui a été fait, et la seule chose qui ferme vraiment le trou — 2026-09-07

Zone 2 close, commit `39d1f12`. `pillow` redescendu à 12.0.0 (rien ne demandait 12.1),
`iiif-prezi3` entré dans `requirements-dev.lock` au même titre qu'`openpyxl`.

**Mais ce n'est pas le pin qui ferme le trou, c'est d'avoir REDIT la borne dans le dépôt.**
`Pillow<=12.0.0` ne vivait que dans les métadonnées d'`iiif-prezi3` : invisible à la
lecture, et invisible au cliquet d'ARCH-2, qui ne résout aucune dépendance — sa propre
docstring le dit. Écrite dans `requirements-export.txt`, elle devient une contradiction
entre deux fichiers du dépôt, que ce cliquet attrape hors ligne, partout, même sans le
paquet installé. Éprouvé dans les DEUX sens : la mutation `pillow==12.1.0` le fait rougir,
et sans la redite les trois gardes d'origine restent VERTES — le trou existait bien.

Une quatrième garde couvre le couple qu'on n'a PAS prévu (la leçon opencv, que la zone
Cohérence porte encore) : elle lit les métadonnées des paquets installés et les confronte
aux pins. 16 couples réellement comparés, portés par 9 paquets — mesuré par SOURCE et non
par total, sans quoi « ça marche » aurait voulu dire « iiif-prezi3 seul ».

**La réserve écrite en tête de cette fiche était fausse sur un point, et il faut le dire.**
« Le test se skippe dans l'image ET sur la machine de dev, donc nulle part » : la seconde
moitié ne tenait plus. Le `.venv` porte `pillow 12.0.0` avec `iiif-prezi3 3.1.1`, et
`test_iiif_conformance_stricte` y PASSAIT déjà — quelqu'un avait résolu le conflit dans le
venv, par la piste même que cette fiche propose, sans que `requirements.lock` en sache
rien. Ce qui était vrai reste vrai pour l'image, et c'est ce qui comptait.

**Et le venv a dérivé du verrou sur SEPT directes** — mesuré le 2026-09-07 : `fastapi`
0.137.0 (la version que le plafond d'ARCH-2 exclut), `pillow` 12.0.0, `uvicorn` 0.49.0 vs
0.41.0, `requests` 2.34.2 vs 2.32.5, `huggingface_hub` 1.19.0 vs 1.18.0, `ultralytics`
8.4.67 vs 8.4.65, `torch`/`torchvision` 2.12.0/0.27.0 vs les 2.13.0/0.28.0 du Dockerfile.
C'est la zone 1 vue depuis l'autre bout : l'environnement qui MESURE n'installe pas le
verrou. La quatrième garde le rapporte plutôt que de le taire — elle cite la version POSÉE
et non le pin, faute de quoi elle mentirait sur sa provenance dans le fichier même qui
traque cet écart.

**Un constat de sécurité est sorti de la passe de revue, et il part en fiche : SEC-3.**
Le plafond qu'on vient de poser retient `CVE-2026-25990`, corrigé dans Pillow 12.1.1.
