---
chantier: QA-4
statut: livré
---

# QA-4 — le verrou ne couvre que 15 paquets sur 91

**Arrêté sur** — le commit `d2fb7ce`, 2026-09-09 : **les trois zones sont closes.** Le verrou transitif
existe, engendré DEPUIS l'image par `deploy/geler_verrous.py` ; le Dockerfile l'installe ;
une construction `--no-cache` est verte et `--verifier` confirme que les trois verrous
décrivent exactement l'image obtenue. Suite DANS l'image : **910 passés, 7 ignorés**.

**Le titre de cette fiche est faux depuis le premier jour où on l'a mesuré, et c'est
instructif.** « 15 paquets sur 91 » : au 2026-09-09 l'image porte **91 paquets à
l'exécution pour 13 épinglés**, et 105 avec les outils de test pour 17. Les chiffres
d'une fiche vieillissent dans le sens qui rassure — le dénominateur monte quand personne
ne regarde.

**Ce qui flottait n'était pas du feuillage.** Sous les treize épinglés : `uvicorn` (le
serveur), `starlette` (le socle de FastAPI), `pydantic` (toute la couche de validation).
Le verrou décrivait la façade d'une pile dont l'ossature était libre.

**Et deux entrées échappaient à TOUT verrou, même transitif** — la fiche ne les nommait
pas, et ce sont les plus conséquentes, parce qu'elles décident de ce que l'outil CALCULE
et non de ce qui est installé :

· le **modèle spaCy**, tiré par `python -m spacy download fr_core_news_sm` sans version —
  donc le plus récent compatible. Il produit les lemmes, donc l'index de recherche, le
  statut de relecture (ANN-4) et les rapports d'accord. Refermé sans mécanisme spécial :
  `pip freeze` le rend déjà sous la forme `fr_core_news_sm @ URL#sha256=…`, épinglé par
  version ET par empreinte.
· **Kumiko**, cloné en `--depth 1` sur la tête de branche. Un push amont changeait la
  segmentation. Épinglé par `ARG KUMIKO_REV` sur un SHA.

**Point de départ** — QA-1 a livré `requirements.lock` en juin 2026, en épinglant
délibérément les seules dépendances DIRECTES. Le premier build d'image, le 2026-08-27, a
montré ce que cette limite laisse passer.

## Reste

### Refermer le trou
- [x] **Un verrou TRANSITIF complet existe, produit DEPUIS l'image Linux construite.** `deploy/geler_verrous.py` construit les deux étapes, y lance `pip freeze` et écrit **trois** fichiers — la séparation n'est pas cosmétique, chacun s'installe autrement : `verrou-torch.lock` (13 paquets) vient de l'index CPU de PyTorch, ses versions portant un identifiant LOCAL `+cpu` qui n'existe pas sur PyPI ; `verrou-image.lock` (77) et `verrou-test.lock` (15) viennent de PyPI, à deux étapes différentes
- [x] **`requirements.lock` reste la liste des dépendances CHOISIES**, et c'est ce qui a décidé de la forme. Y verser 90 lignes transitives aurait noyé les 13 décisions **et tué le cliquet** de `test_verrou_dependances.py`, qui exige qu'un pin ait une spec ou une raison écrite. Deux questions distinctes — « qu'a-t-on décidé », « qu'est-ce qui en découle » — donc deux familles de fichiers, et un test qui leur interdit de se contredire
- [x] **Le Dockerfile installe ce verrou complet, et deux constructions donnent le même jeu de versions.** Construction `--no-cache` verte le 2026-09-09 ; `python deploy/geler_verrous.py --verifier` régèle depuis l'image obtenue et compare : « les trois verrous décrivent exactement l'image construite ». Ce n'est pas un mois d'écart — c'est le mécanisme qui rend l'écart d'un mois vérifiable en une commande
- [x] **La procédure de régénération est écrite, et elle est EXÉCUTABLE.** L'en-tête de `deploy/geler_verrous.py` dit quand refaire le gel (après un changement de `requirements*.lock`, de la ligne torch, ou de la base Python) et surtout quand NE PAS le refaire : un gel régénéré « pour voir » ramasse les publications du jour, ce qu'on vient précisément de fermer. Chaque fichier engendré porte son en-tête de provenance et l'interdiction de l'éditer à la main

### Un conflit déjà ouvert entre deux fichiers épinglés
- [x] `requirements-export.txt` et `requirements.lock` cessent d'être mutuellement exclusifs : `iiif-prezi3==3.1.1` exige `Pillow<=12.0.0` (dépendance OBLIGATOIRE, pas un extra) quand le verrou épingle `pillow==12.1.0` — pip répond `ResolutionImpossible`
- [x] Le test de conformance IIIF (`test_iiif_conformance_stricte`, dans `tests/test_export_metadonnees.py`) s'exécute quelque part : aujourd'hui il se skippe dans l'image ET sur la machine de dev, donc **nulle part**, alors que `docs/roadmap.md` donne l'IIIF pour « validé via iiif-prezi3 »
- [x] `docs/roadmap.md` dit ce qui est réellement vérifié aujourd'hui, ou la vérification est rétablie — les deux conviennent, la situation actuelle non
- [x] La construction de l'image confirme que `iiif-prezi3` s'y installe et que `test_iiif_conformance_stricte` y PASSE — c'est la réserve de QA-5, le venv local n'est pas l'artefact livré ; vérifié le 2026-09-07 sur une image construite depuis `2e70028`

### Cohérence
- [x] **`COPY` ne précède plus une installation qui n'en dépend PAS** : chaque verrou est copié juste avant le `RUN` qui le lit. Auparavant un seul `COPY requirements.lock` précédait les DEUX installations, si bien que changer le pin de `pillow` invalidait la couche torch — une reconstruction complète pour un fichier dont cette couche ne se sert pas
- [x] **Le double travail entre torch et le verrou est SUPPRIMÉ**, et il l'est par construction plutôt que constaté : `numpy` et `pillow` entrent dans `verrou-torch.lock`, donc l'étape torch les pose d'emblée à leur version finale. Mesuré dans le log `--no-cache` du 2026-09-09 : **zéro « Attempting uninstall »**, là où l'étape suivante désinstallait `numpy 2.5.2` pour poser `2.4.6` à chaque construction
- [x] **`torch` et `torchvision` ne sont plus épinglés dans le Dockerfile** : ils vivent dans `verrou-torch.lock` avec leur fermeture. Et un cliquet l'interdit désormais — `test_le_dockerfile_n_epingle_aucune_version_hors_verrou` joint les continuations `\` avant de balayer, parce que la version se trouve justement sur la SECONDE ligne d'un `RUN` continué et qu'un balayage naïf resterait vert
- [x] **Le cas des paquets JUMEAUX est traité ET gardé.** Le traitement existait — les deux OpenCV épinglés à la même version, avec la raison écrite dans le verrou. Ce qui manquait était la garde : rien n'obligeait les deux versions à rester égales. `JUMEAUX` déclare la famille AVEC sa raison (patron de `HORS_PERIMETRE`), et le test balaie les deux familles de verrous
- [x] **Une exclusion de la suite d'image manquait à la liste du Dockerfile**, trouvée en comptant : il annonçait « deux exclusions assumées » (e2e, JS) et il y en a **trois**. Les quatre modules qui éprouvent les scripts d'infrastructure ne sont pas collectés, `.dockerignore` excluant `deploy/` en entier pour une raison de sécurité — 39 tests réduits à 4 skips, plus 2 skips ailleurs. La suite d'image mesurait donc 917 tests contre 952 en local, sans que rien ne le dise. C'est le reproche de QA-5 retourné contre sa propre documentation : une suite qui ne dit pas ce qu'elle n'a PAS mesuré laisse croire qu'elle a tout vu
- [x] **Une recette de dépannage contournait l'épingle du modèle.** `docs/deploiement-docker.md` conseillait `docker exec … python -m spacy download` pour réparer un modèle manquant : la commande fonctionne, et c'est le problème — elle prend le plus RÉCENT compatible, donc pas celui de l'image. La réparation passe désormais par le verrou, avec l'interdiction et sa raison écrites. `docs/exploitation.md` nommait de son côté `requirements.lock` comme « la forme que l'image LIVRE », ce qui a cessé d'être vrai le jour où l'image a installé le verrou transitif

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

## La case de l'image est fermée, et par deux mesures distinctes — 2026-09-07

Docker lancé, image `test` construite depuis un `git archive` de `2e70028` — et non depuis
l'arbre de travail, qu'une session voisine modifiait : `COPY . .` y aurait fait entrer des
fichiers non commités, si bien qu'un rouge, ou pire un VERT, aurait pu venir d'un travail
qui n'est pas celui-ci. Contrôlé avant de construire : pins présents, fichiers de l'autre
chantier absents.

**(a) Ce que pip a résolu, constaté dans un conteneur et non lu dans le log du build.**
`pillow 12.0.0` et `iiif-prezi3 3.1.1` s'importent tous deux dans la même image. Un
`DONE` de pip aurait seulement dit qu'il avait réussi, pas ce qu'il avait résolu.

**(b) Le test s'EXÉCUTE.** `1 passed` sur le nom complet, `-rs` sans un seul skip. Le
premier essai, `-k "iiif"`, rendait « 6 passed » — six tests dont l'affichage compact ne
nommait aucun, donc une réponse qui n'en était pas une : c'est la vacuité par le filtre,
et il a fallu nommer le test pour que la mesure porte. Son vert vaut d'ailleurs plus
qu'une collecte réussie, puisqu'il assertionne lui-même « Conformité stricte
(iiif-prezi3) : exécutée » dans la sortie de l'outil.

**Et l'instrument était muet.** Le `CMD` de l'étape `test` passait `-q` quand `pytest.ini`
en porte déjà un : `-qq` supprime la ligne de bilan. Une image dont la suite ne dit pas
combien de tests ont tourné ne permet pas de distinguer 833 verts de 12 — dans l'artefact
même dont QA-5 fait la vérité contre le venv local. Corrigé (`c6b33a2`), puis ÉPROUVÉ : reconstruction sur
cache (9 couches reprises), l'image porte `["python","-m","pytest"]` quand le témoin
d'avant porte `[…,"-q"]`, et cette commande y sort bien « N passed ». Le premier contrôle
tenté ne valait rien et c'est instructif — passer la commande à `docker run` REMPLACE le
`CMD`, donc il éprouvait tout sauf ce qu'il prétendait.

Deux mesures de méthode valent d'être gardées, parce qu'elles se sont produites ici même.
La première mesure du `-qq` était FAUSSE : le filtre appliqué à la sortie contenait le mot
`warning`, donc il mangeait la ligne de bilan qu'il cherchait. Et la passe locale lancée
plus tôt avait été canalisée dans un `tail`, qui bufferise — sa sortie est restée vide
pendant sept minutes, invisible au moment exact où elle coûtait le processeur.
