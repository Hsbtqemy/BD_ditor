# Image de l'application BéDéditeur (FastAPI + moteurs ML + Kumiko).
#
# TROIS étapes (QA-5) :
#   base     — dépendances d'exécution, partagées ; jamais lancée telle quelle
#   test     — base + outils de test, pour exécuter la suite DANS l'image
#   runtime  — base + code, l'image LIVRÉE, sans aucun outil de test  (défaut)
#
# Pourquoi : jusqu'au 2026-08-27 le dépôt n'avait pas d'artefact, et sa vérification
# reposait sur une hypothèse alors vraie — ce qu'on teste EST ce qu'on exécute. Le premier
# build l'a rompue : 451 tests verts sur la machine de dev, et TROIS moteurs morts dans
# l'image (spaCy absent, torchvision incompatible, OpenCV 5 cassant Kumiko). Aucun n'était
# visible depuis le venv local. L'étape `test` existe pour que ça ne se reproduise pas ;
# `runtime` reste indemne, donc à 3,5 Go et sans navigateur embarqué.
#
#   docker build -f deploy/Dockerfile -t bdediteur .                      # runtime
#   docker build -f deploy/Dockerfile --target test -t bdediteur:test .   # suite
#   docker run --rm bdediteur:test                                        # lance pytest
#
# Python 3.12 : wheels torch/easyocr matures, conforme au README.

# --------------------------------------------------------------------------- #
# base — tout ce dont l'application a besoin pour TOURNER
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS base

# Dépendances système :
#   git           -> cloner Kumiko (segmentation, passe 1)
#   libgl1/glib   -> requis par opencv (tiré par ultralytics) à l'import de cv2
RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Marqueur EXPLICITE, hérité par `test` comme par `runtime` : « cette pile EST l'image ».
# Il sert à une question qui n'a de sens que hors d'ici — `tests/test_ecart_venv_image.py`
# compare le poste de travail à l'artefact, et dans l'artefact la comparaison porterait
# sur lui-même. Un marqueur POSÉ plutôt que DEVINÉ : reconnaître l'image à son chemin, à
# sa plateforme ou à l'absence de `.git` marcherait aujourd'hui et mentirait le jour où un
# poste de dev sous Linux ressemblerait assez à l'image pour tromper la devinette.
ENV BD_IMAGE=1

# 1) Dépendances Python d'abord (couche de cache indépendante du code).
#    On installe des verrous TRANSITIFS (QA-4, `verrou-*.lock`), engendrés par
#    `pip freeze` DANS cette image et non depuis un venv de dev. `requirements.lock`
#    reste la liste des dépendances CHOISIES — 13 pins, chacun avec sa spec ou sa raison
#    écrite — mais il ne dit rien de ce qui SUIT : mesuré le 2026-09-09, l'image portait
#    91 paquets à l'exécution pour 13 épinglés, dont `uvicorn`, `starlette` et
#    `pydantic`. Deux constructions à un mois d'écart ne donnaient pas la même image.
#
#    CHAQUE VERROU EST COPIÉ JUSTE AVANT SON INSTALLATION. Auparavant un seul
#    `COPY requirements.lock` précédait les DEUX `RUN` : mesuré le 2026-09-07 dans le
#    log de build, changer le seul pin de `pillow` invalidait la couche torch, qui ne
#    dépend pas de ce fichier — une reconstruction complète pour rien.

#    1a) torch en variante CPU, AVANT le reste. Mesuré le 2026-08-27 : la roue torch
#    par défaut de PyPI est compilée pour CUDA 13 et traîne 2 196 Mo de wheels GPU
#    (cublas 423, cudnn 366, cufft 214, nccl 206, cusolver 201, triton 198…) — pour
#    une image de 10 Go dont le conteneur répond `torch.cuda.is_available() == False`.
#    Les specs du projet disent « CPU suffit » (requirements-ocr.txt, requirements-nlp.txt)
#    et le déploiement ne prévoit aucun GPU. On installe donc torch d'abord depuis
#    l'index CPU ; `ultralytics` et `easyocr` le trouvent ensuite déjà satisfait.
#    Pour repasser au GPU : supprimer cette étape, rien d'autre.
#    torchvision DOIT venir du MÊME index : c'est une extension native compilée
#    contre torch. Mesuré le 2026-08-27 : `torch==2.13.0+cpu` (index CPU) avec
#    `torchvision==0.28.0` (PyPI, compilé pour le torch CUDA) donne un
#    « RuntimeError: operator torchvision::nms does not exist » au premier import
#    d'ultralytics — et `/api/sante` n'y voit RIEN, car il ne fait que localiser
#    le module (`find_spec`), jamais l'importer.
#
#    Le verrou porte la FERMETURE de torch — treize paquets, `numpy` et `pillow`
#    compris. Ces deux-là y sont pour une raison mesurée : sans eux, cette étape les
#    résolvait librement (numpy 2.5.2) et la suivante les DÉSINSTALLAIT pour poser les
#    versions du verrou (2.4.6). Un travail fait deux fois, à chaque construction.
COPY verrou-torch.lock ./
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        -r verrou-torch.lock

#    1b) le reste de l'exécution, depuis PyPI — modèle NLP français COMPRIS.
#    SANS ce modèle, `nlp_available()` est False et tout dégrade EN SILENCE : la table
#    `tokens` reste vide, donc l'Exploration ne montre rien, le statut de relecture
#    (ANN-4) reste « à faire » partout, les rapports d'accord (NLP-1, ANN-5) sortent
#    vides et la recherche perd les lemmes. Aucune erreur ne le signalerait.
#    Modèle surchargeable au runtime par BD_SPACY_MODEL (défaut : celui du verrou).
#
#    Il vient du verrou et non plus de `python -m spacy download`, qui prenait le plus
#    RÉCENT compatible : le gel le porte sous sa forme `fr_core_news_sm @ URL#sha256=…`,
#    donc épinglé par version ET par empreinte. Ce n'est pas un détail d'installation —
#    ce modèle produit les lemmes, donc l'index de recherche et le statut de relecture.
#    Le remplacer en silence changerait ce que l'application CALCULE.
COPY verrou-image.lock ./
RUN pip install --no-cache-dir -r verrou-image.lock

# 2) Kumiko (passe 1) dans lib/kumiko, à une RÉVISION FIXE (ses dépendances
#    opencv/numpy/requests viennent des verrous ci-dessus).
#    `git clone --depth 1` prenait la tête de la branche par défaut : un push amont
#    changeait la segmentation sans qu'aucun verrou ne bouge. Comme le modèle spaCy,
#    c'est une entrée qui décide de ce que l'outil CALCULE, et elle ne se voyait dans
#    aucune liste de dépendances. Pour avancer : changer ce SHA, reconstruire, relancer
#    la suite dans l'image.
ARG KUMIKO_REV=9d587ae9498bc84dfda06fc19c6ad89f421bec14
RUN git init -q lib/kumiko \
 && git -C lib/kumiko remote add origin https://github.com/njean42/kumiko.git \
 && git -C lib/kumiko fetch -q --depth 1 origin ${KUMIKO_REV} \
 && git -C lib/kumiko checkout -q --detach FETCH_HEAD

# --------------------------------------------------------------------------- #
# test — la suite s'exécute sur les MÊMES dépendances que la production
# --------------------------------------------------------------------------- #
# L'intérêt tient à ce partage : `test` hérite de `base`, donc du même torch, du même
# OpenCV et du même Kumiko que `runtime`. Un écart de version qui casse un moteur y est
# visible, alors qu'il ne l'est pas depuis le venv de dev.
#
# QUATRE exclusions ASSUMÉES, à connaître pour ne pas se croire couvert.
#
# DEUX CHIFFRES, et les confondre fait rater la démonstration. Mesuré le 2026-09-09 :
# l'image COLLECTE 920 tests contre 959 sur la machine de dev — 39 de moins, c'est-à-dire
# exactement les quatre modules `deploy` détaillés plus bas. Le BILAN, lui, en affiche
# 924 : un module sauté au niveau du MODULE est compté dans le total sans jamais être
# collecté, et ces 4 skips ramènent l'écart NET à 35. Les deux chiffres sont justes et ne
# se comparent pas l'un à l'autre. Cette page a d'abord écrit « la suite collecte 924 »,
# ce qui mélangeait les deux — et masquait que 959 − 920 tombe pile sur les 39 de `deploy`,
# la seule vérification qui rende cette liste crédible.
#   · e2e   — `pytest -m e2e` exige un navigateur, et l'étape `test` s'en passe pour
#             rester à la taille de `base`. Ils ne sont plus pour autant confinés à la
#             machine de dev : depuis le 2026-09-09 ils tournent dans l'étape `e2e`
#             ci-dessous, qui hérite de celle-ci et ajoute Chromium. (184 désélectionnés)
#   · JS    — `tests/test_js_unit.py` appelle `node`, absent de l'image : il se skippe
#             proprement, et sa logique est pure (aucun accès DOM), donc indépendante
#             de l'image. (1 skip)
#   · écart  — `test_ecart_venv_image.py::test_les_declarations_ne_survivent_pas_a_leur_objet`
#             se saute ici, et lui seul : il garde `ECARTS_ADMIS` de devenir un cimetière,
#             or ces déclarations décrivent un POSTE DE TRAVAIL. Dans l'image, où l'écart
#             est nul par construction, il les lirait toutes comme périmées. Les deux
#             autres tests du module TOURNENT et gardent quelque chose : que l'image ne
#             contredise aucune épingle délibérée. (1 skip)
#   · deploy — les scripts d'infrastructure ne sont pas dans l'image : `.dockerignore`
#             exclut `deploy/` en ENTIER, parce que `deploy/authelia/users_database.yml`
#             porte un hash de mot de passe qui n'a rien à faire là. Quatre modules
#             (`test_deployeur`, `test_veille_deploiement`, `test_verifier_comptes`,
#             `test_verifier_deploiement`) se sautent donc au niveau du MODULE : leurs
#             39 tests ne sont pas collectés et se réduisent à 4 skips, d'où l'écart net
#             de 35. Deux tests de `test_regressions` s'y ajoutent, skippés un par un
#             pour la même raison. Tous le disent à leur propre site — « son skip dans
#             l'image N'EST PAS une couverture ». Ils tournent sur la machine de dev.
#             (39 tests non collectés, 4 + 2 skips)
#
# Cette liste était INCOMPLÈTE jusqu'au 2026-09-09 : elle n'en nommait que deux, et la
# plus grosse — `deploy`, 39 tests — n'y était pas. C'est le mode d'échec que QA-5 dénonce
# retourné contre sa propre documentation : une suite qui ne dit pas ce qu'elle n'a pas
# mesuré laisse croire qu'elle a tout vu. Le compte des exclusions se relit donc à chaque
# fois qu'on en ajoute une : la quatrième est arrivée le matin même, et la mention
# « TROIS » lui a survécu jusqu'au soir.
FROM base AS test

# `openpyxl` et `iiif-prezi3` sont épinglés dans `requirements-dev.lock` (outils de test)
# et n'entrent donc pas dans `runtime` : l'application ne les importe jamais, seuls les
# scripts `tools/` s'en servent. Sans eux, des tests d'export se skippent.
#
# `iiif-prezi3` n'a PAS TOUJOURS PU y entrer, et la raison mérite d'être gardée :
# `iiif-prezi3==3.1.1` exige `Pillow<=12.0.0` (dépendance OBLIGATOIRE, pas un extra) quand
# `requirements.lock` épinglait `pillow==12.1.0` — mutuellement exclusifs, pip répondait
# `ResolutionImpossible`. Le test de conformance IIIF se skippait donc ici, alors que
# `docs/roadmap.md` donne l'IIIF pour « prouvé via iiif-prezi3 » : un skip se lit comme un
# succès. Réparé le 2026-09-07 (QA-4) en redescendant `pillow` à 12.0.0, ce que rien dans
# le dépôt ne contredit. Les deux pins se tiennent — remonter pillow refermerait cette
# validation en silence, et `tests/test_verrou_dependances.py` échoue désormais si on le
# fait.
COPY verrou-test.lock ./
RUN pip install --no-cache-dir -r verrou-test.lock

COPY . .

# Répertoires de travail ÉCRIVABLES et distincts de /data : la suite ne doit jamais
# écrire là où un volume de production serait monté. Les tests isolent de toute façon
# leurs données via BD_DATA_DIR/BD_DB_PATH (cf. tests/conftest.py), ceci ne sert qu'au
# `mkdir` fait par config.py à l'import.
ENV BD_DATA_DIR=/tmp/bd-test-data \
    HOME=/tmp/bd-test-home \
    PYTHONUNBUFFERED=1

# Le commit servi, comme dans `runtime` (INFRA-10). Ici il ne sert pas un panneau
# d'écran mais le bandeau d'identité ci-dessous : un journal de construction gardé trois
# semaines doit encore dire SUR QUOI la suite est passée.
ARG BD_COMMIT=inconnu
ENV BD_COMMIT=$BD_COMMIT

# `pytest` NU, sans `-q` : `pytest.ini` en porte déjà un dans `addopts`, et le second en
# ferait `-qq` — qui SUPPRIME la ligne de bilan. Mesuré le 2026-09-07 : `pytest -q` sort
# les points et rien d'autre, `pytest` nu sort « N passed ». L'image resterait donc muette
# sur le NOMBRE de tests exécutés, ce qui est précisément ce qu'on vient lui demander :
# QA-5 fait de cette image l'artefact de vérité, et « 833 verts » et « 12 verts, 821 non
# collectés » s'y affichaient à l'identique. Une suite qui ne dit pas ce qu'elle a mesuré
# approuve sans avoir rien vu (QA-4).
#
# L'IDENTITÉ EST IMPRIMÉE D'ABORD (QA-5). Un échec de suite dans l'image ne disait ni quel
# commit, ni quelle pile : il fallait reconstruire pour le savoir, c'est-à-dire remplacer
# la chose qu'on voulait examiner. Le bandeau pose le commit, la version de Python, les
# empreintes des trois verrous, dix versions clés et l'état des moteurs.
#
# `;` et non `&&` : le bandeau est un instrument de LECTURE, et un instrument cassé ne doit
# pas empêcher la mesure. S'il levait, `&&` supprimerait la suite entière au profit d'une
# erreur de mise en forme — l'inverse de ce qu'on lui demande. Le code de retour reste
# celui de pytest.
CMD ["sh", "-c", "python tools/identite_pile.py --identite; python -m pytest"]

# --------------------------------------------------------------------------- #
# e2e — les tests navigateur, dans un artefact eux aussi
# --------------------------------------------------------------------------- #
# Le dernier pan que l'artefact ne couvrait pas : les tests Playwright (184 au
# 2026-09-09) qui ne tournaient que sur la machine de dev. Ils exigent un navigateur, et l'étape `test` s'en passe
# délibérément — c'est ce qui la garde à la taille de `base`.
#
#   docker build -f deploy/Dockerfile --target e2e -t bdediteur:e2e .
#   docker run --rm bdediteur:e2e
#
# HÉRITE DE `test` ET NON DE `base` : le navigateur s'ajoute à la suite, il ne la
# remplace pas. `runtime` reste FROM `base` et n'hérite donc RIEN d'ici — la séparation
# des étapes est ce qui permet d'embarquer 400 Mo de navigateur sans toucher au livrable.
#
# PLACÉE AVANT `runtime`, et ce n'est pas cosmétique : l'étape par défaut d'un Dockerfile
# est la DERNIÈRE, et `runtime` doit le rester. Mettre celle-ci après ferait construire
# une image de test à qui lance `docker build -t bdediteur .` sans `--target`.
#
# La révision du navigateur n'est PAS épinglée par nos verrous, et elle n'a pas besoin de
# l'être : Playwright embarque une révision de Chromium par version, et `playwright` est
# épinglé dans `verrou-test.lock`. La chaîne tient donc — mais par une propriété de
# Playwright, pas par une décision de ce dépôt, et c'est écrit ici pour qu'on ne le
# découvre pas le jour où elle cesserait d'être vraie.
FROM test AS e2e

# `--with-deps` installe les bibliothèques système du navigateur (apt). Il refait son
# propre `apt-get update` : `base` a supprimé les listes pour ne pas les traîner.
RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Les polices — et la première rédaction de ce commentaire était FAUSSE. Elle affirmait
# que Chromium sur une `slim` n'en a aucune ; le journal de construction dit le contraire,
# `--with-deps` installant déjà liberation, freefont, ipafont et noto-color-emoji. Ce
# qu'il n'installe pas — mesuré en comparant les deux transactions apt, le 2026-09-09 —
# c'est DejaVu.
#
# On l'ajoute quand même, et pour une raison qui n'est pas « sinon rien ne s'affiche » :
# deux audits de ce dépôt MESURENT des rectangles — `test_e2e_reflow` compare la largeur
# de chaque élément à celle de la fenêtre, `test_e2e_police` fait varier la police par
# défaut du navigateur. DejaVu Sans est le sans-serif par défaut d'une Debian de bureau,
# donc ce qu'un poste Linux rend RÉELLEMENT ; on mesure contre lui pour cela, et pour
# rien d'autre. Ce qu'on n'a PAS mesuré, et qu'il ne faut donc pas déduire d'ici : lequel
# de DejaVu, Liberation (métriques d'Arial) ou FreeSans est le plus large. Le seul écart
# chiffré est DejaVu contre la police d'un poste Windows — cinq pixels, le 2026-09-09.
#
# Ce qui a changé le 2026-09-09 : la garde stricte de `/administration` ne DÉPEND plus de
# ce choix. Elle a trouvé son défaut ici et pas sur le poste — même chaîne, deux polices,
# cinq pixels — puis a gagné l'axe de la préférence de police, qui le reproduit partout.
# La fonte installée rend la mesure RÉALISTE ; elle ne la rend plus VALIDE.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Le marqueur d'image vaut ici aussi (hérité de `base`), et le bandeau d'identité précède
# la suite pour la même raison qu'à l'étape `test` : un journal doit rester lisible sans
# qu'on reconstruise ce qu'il décrit.
CMD ["sh", "-c", "python tools/identite_pile.py --identite; python -m pytest -m e2e"]

# --------------------------------------------------------------------------- #
# runtime — l'image LIVRÉE  (étape par défaut : la dernière du fichier)
# --------------------------------------------------------------------------- #
FROM base AS runtime

# Code de l'application (lib/kumiko, .venv, corpus… sont exclus via .dockerignore).
COPY . .

# Données ET caches de modèles (HOME) sous /data -> persistés par un volume,
# donc les modèles ML ne sont téléchargés qu'une seule fois.
ENV BD_DATA_DIR=/data \
    HOME=/data \
    PYTHONUNBUFFERED=1

# CONTRAT D'IMAGE (SANTE-1 / QA-5) : les quatre moteurs doivent être RÉELLEMENT
# utilisables, pas seulement présents. Le build ÉCHOUE sinon.
#
# Ce contrôle ne fait pas double emploi avec la suite de l'étape `test`, il couvre ce
# qu'elle ne peut pas couvrir. Mesuré le 2026-08-27 sur une image dont le modèle spaCy
# avait été retiré : 451 tests, ZÉRO échec — la couche NLP dégrade proprement et les tests
# encodent la même hypothèse, si bien qu'« absent » est un état qu'ils acceptent. Correct
# en développement local ; inacceptable pour un artefact, où l'absence de spaCy tue
# quatre chantiers livrés (Exploration, ANN-4, NLP-1, ANN-5) en silence.
RUN python tools/verifier_moteurs.py --exiger kumiko,bulles,ocr,nlp

# QUEL commit cette image sert-elle ? Sans cette étiquette, le déploiement ne peut
# comparer que des choses qui n'ont pas de rapport — `deployer.sh` regardait si SON
# `git pull` avait ramené quelque chose, ce qui n'est pas la même question que « l'image
# en service est-elle en retard ». Les deux se séparent dès que quelqu'un tire à la main,
# et c'est arrivé le 2026-09-06 : le dépôt était à jour, le conteneur d'avant-veille, et
# le script a répondu « rien de neuf ».
#
# Placé APRÈS tout ce qui coûte : changer de commit n'invalide que cette couche-ci.
ARG BD_COMMIT=inconnu
LABEL bd.commit=$BD_COMMIT
# DEUX fois, et pour deux lecteurs qui ne peuvent pas se remplacer. Le `LABEL` se lit de
# l'EXTÉRIEUR par `docker inspect` : c'est ce que `deployer.sh` interroge pour décider
# s'il y a à déployer. L'`ENV` se lit de l'INTÉRIEUR : un `ARG` ne survit pas au build,
# donc sans lui le processus qui tourne ignore quel commit il sert, et la page
# d'Administration n'aurait rien à afficher (INFRA-10).
ENV BD_COMMIT=$BD_COMMIT

EXPOSE 8000

# 1 SEUL worker : l'app garde des états en mémoire (jobs, session, modèles).
# L'app n'écoute qu'en interne ; elle n'est jamais exposée hors du réseau Docker.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
