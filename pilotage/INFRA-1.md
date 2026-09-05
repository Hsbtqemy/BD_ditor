---
chantier: INFRA-1
statut: livré
---

# INFRA-1 — déploiement Docker réel sur le VPS

**Arrêté sur** — 2026-09-05, `64b063f` : l'instance SERT, en HTTPS, sur
`https://bd.edito-revue.fr` — derrière le nginx qui servait déjà un autre site. Dix
chemins anonymes refusés, quatre moteurs importés pour de bon, un compte connecté en 2FA,
une sauvegarde reprise sur une machine de dev. Le chantier se ferme sur ce qu'il a trouvé
en se fermant : le référent d'AUTH-4 ne s'activait qu'en éditant un fichier versionné.

## Ce que la préparation du 2026-09-05 a trouvé

Rien de tout cela n'était visible avant de vouloir déployer POUR DE BON.

**Le fichier des comptes ne pouvait aller que dans un dépôt public.**
`deploy/authelia/users_database.yml` était suivi par git, et son en-tête demandait d'y
coller un hash argon2id : suivre la procédure publiait le hash du mot de passe. Rien n'a
fuité — les deux commits du fichier portent encore le placeholder, vérifié un par un — mais
le chemin était ouvert et rien ne l'aurait signalé. Le patron existait déjà dans le dépôt
(`.env.example` versionné, `.env` ignoré) ; il n'avait pas été appliqué ici.

**Les trois fichiers de config étaient des gabarits qu'il fallait éditer sur place**, donc
un conflit garanti à chaque `git pull` du VPS, et douze substitutions à refaire au vrai
domaine. Les valeurs vivent maintenant dans `deploy/.env` : Caddy lit `{$VAR}` depuis son
propre environnement, Authelia `{{ env "…" }}` via `X_AUTHELIA_CONFIG_FILTERS=template`.

**Une erreur silencieuse et grave était possible, et aucun outil ne la voyait** :
`COOKIE_DOMAINE` écrit trop HAUT envoie le cookie de session à tout ce domaine — avec
sslip.io, `sslip.io` au lieu de `<ip>.sslip.io` le livrerait à toutes les instances du
service, et la connexion fonctionnerait parfaitement. `compose config` valide la syntaxe,
Caddy son fichier, Authelia le sien ; aucun ne connaît les deux autres. D'où
`verifier_deploiement.py --config`.

**Et le contrôle lui-même a failli mentir dans le pire sens.** Sa première version lisait
les 502 d'un proxy comme des refus et déclarait « aucun chemin ne répond à un anonyme » sur
une instance ÉTEINTE. Il classe désormais en trois états, et « injoignable » est un ÉCHEC.
Éprouvé dans les trois sens : cible morte → 1, cible vivante sans auth → 1, cible qui
redirige vers un portail → 0.

**Le DNS n'est pas prêt**, d'où `sslip.io` (résout tout nom contenant une IP vers cette IP)
et `tls internal` : `sslip.io` n'étant pas un suffixe public — vérifié sur la Public Suffix
List —, Let's Encrypt le compte comme UN domaine enregistré et sa limite hebdomadaire est
partagée avec tous ses utilisateurs.

## Reste

### Image — écrite, jamais construite
- [x] `deploy/Dockerfile` se construit jusqu'au bout et son poids est relevé : **3,56 Go** après bascule de torch/torchvision sur l'index CPU (10 Go avant — 2 196 Mo de wheels NVIDIA pour un conteneur sans GPU)
- [x] Le Dockerfile installe spaCy ET télécharge `fr_core_news_sm` — il n'installait que `requirements.txt` + `requirements-ocr.txt` + `requests`, donc aucun des deux
- [x] Le Dockerfile installe depuis `requirements.lock` (verrou QA-1) et non depuis des bornes `>=` ouvertes
- [x] Les outils de test n'entrent PAS dans l'image : le lock a été scindé en `requirements.lock` (runtime, 12 pins) et `requirements-dev.lock` — un lock unique aurait embarqué Playwright
- [x] Le conteneur démarre et sert l'application, volume monté sur `/data` : base créée en `/data/bd_annotator.sqlite`, `/api/sante` renvoie `kumiko`/`bulles`/`ocr`/`lemmes` tous à `true`
- [x] La base survit à la **destruction** du conteneur : album créé, conteneur supprimé, nouveau conteneur sur le même volume — l'album est toujours là
- [x] Les **caches de modèles ML** survivent : passes bulles et OCR lancées, modèles téléchargés dans `/data/.cache` (50 Mo) et `/data/.EasyOCR` (95 Mo) — donc sur le volume, réutilisés par les conteneurs suivants. `HOME=/data` fait son travail
- [x] Les trois passes ML tournent sur un **vrai master** (`corpus/album_2/planche_0002.tif`, 3748×4710, 400 dpi) : 12 cases, 24 bulles, 24 régions avec texte OCR — pic mémoire 1,216 Gio

### Déploiement — jamais lancé
- [x] Le VPS est en état de recevoir la pile : Ubuntu 24.04.4 LTS, **x86_64** (vérifié avant de lancer 3,56 Go de build), 51 Go libres, Docker 29.8.0 + Compose v5.5.1 installés par le dépôt APT signé, et **2 Go de swap ajoutés** — `swapon --show` était vide sur une machine de 3,9 Go, alors que le pic mesuré atteint 1,216 Gio et qu'un dépassement tue le process sans traceback
- [x] La configuration est PARAMÉTRABLE : plus aucune valeur d'instance dans un fichier versionné, et le contrôle de cohérence des trois domaines refuse un cookie posé trop haut
- [x] **La pile monte réellement sur le VPS** — mais pas dans l'architecture prévue : la machine hébergeait déjà `edito-revue.fr` derrière nginx, qui occupait 80 et 443. Caddy tournait, ses mappings déclarés mais jamais obtenus, et les requêtes tombaient sur nginx répondant 400 à un nom inconnu. Résolu par une VARIANTE versionnée (`docker-compose.derriere-proxy.yml` + `Caddyfile.derriere-proxy`) : Caddy passe sur `127.0.0.1:8080` sans TLS, nginx termine le TLS et proxifie. Le cas nominal du dépôt reste Caddy en frontal
- [x] **Le NLP est disponible en production**, vérifié par la voie PROFONDE et non par la voie rapide : `profond.nlp = {ok: true}`, donc spaCy et `fr_core_news_sm` ont réellement suivi. Les quatre moteurs répondent (`kumiko`, `bulles`, `ocr`, `nlp`)
- [x] **Une requête non authentifiée est refusée avant d'atteindre l'application** : dix chemins testés en anonyme, tous en 401 — `/api/sauvegarde` et `/static/style.css` compris, les deux que le `forward_auth` doit couvrir et qu'une garde posée au mauvais endroit laisserait passer sans rien signaler
- [x] La déconnexion fonctionne de bout en bout depuis l'UI, pas seulement via la route `/api/moi` : clic sur la pastille 👤 → portail, retour sur l'application → **mot de passe ET code TOTP redemandés**. C'est ce troisième temps qui mesure, et lui seul : une page « vous êtes déconnecté » laissant la session vivante dans Redis donne exactement la même impression au premier coup d'œil, et laisse rentrer sans rien saisir
- [x] Une sauvegarde prise sur le VPS se restaure sur une machine de dev : album témoin créé en ligne, `/api/sauvegarde` téléchargée — réservée aux administrateurs depuis DROIT-1 —, dézippée, servie par `BD_DB_PATH` sur le port 8001, l'album y est. Elle ne porte QUE la base : un corpus complet aux images absentes est le comportement attendu, pas un échec
- [x] **L'identité a fait le trajet, pas seulement la donnée** : la base restaurée porte `chercheur / Chercheur / …@example.fr` dans `utilisateur` (v22) — écrit côté serveur depuis les en-têtes par le MÊME `_auteur(request)` qui alimente `_capter_agent`. C'est ce qui exclut la panne d'attribution du 2026-09-02, qui ne se voit nulle part ailleurs
- [x] Le référent d'AUTH-4 s'active sans toucher un fichier versionné : `BD_REFERENT_NOM`/`_CONTACT` passent par `.env` comme les trois domaines, et `docker compose config` sur le VPS les rend en chaînes vides, sans avertissement de variable absente

## Le déploiement réel — 2026-09-05

Fait, en HTTPS, sur `https://bd.edito-revue.fr`. Ce que le premier `up` a révélé, et que la
fiche annonçait sans pouvoir le nommer.

**La machine n'était pas vierge.** Elle sert un autre site en production. Rien ne le
laissait prévoir, et la conséquence était silencieuse : Docker créait le conteneur avec ses
mappings, Caddy démarrait sans erreur, et c'est nginx qui répondait. Le contrôle de l'étape
0 — `ss -lntp | grep -E ':(80|443)'` — aurait donné la réponse en une seconde ; il avait été
sauté.

**Le nommage a coûté deux détours.** `main` était la branche par défaut du dépôt et datait
du 12 juin : le VPS a cloné une version sans `deploy/`. Et `sante.rapide()` annonce le NLP
sous `lemmes` quand `sante._CONTROLES` le contrôle sous `nlp`, ce qui a fait déclarer le
moteur cassé sur une instance où il tournait — alors que `static/lib/sante.js` porte ce
mapping, commenté, depuis SANTE-1.

**Trois faux positifs du contrôle, tous corrigés le jour même** : une instance ÉTEINTE
déclarée « protégée » (les 502 lus comme des refus), un `.env` valide rejeté pour cause de
guillemets, et le domaine de production refusé par une garde calibrée sur `<ip>.sslip.io`.

## La fermeture — 2026-09-05

Les deux dernières cases étaient hors de portée d'un script, et c'est en les fermant à la
main que le chantier a trouvé son dernier défaut.

**Le journal A3 était VIDE dans la base restaurée, et ce n'était PAS la panne** — c'était
un test mal choisi. `create_album` ne journalise pas : le journal couvre les actes
d'annotation, les passes ML, les accès de collection et ShareDocs. Le témoin utilisable
était ailleurs, dans `utilisateur`, écrit à chaque `/api/moi` depuis les en-têtes par le
même `_auteur(request)` que la dépendance de capture. Noté ici parce que le prochain qui
voudra vérifier l'attribution après une restauration fera exactement le même détour.

**Le référent d'AUTH-4 restait derrière un fichier versionné.** `GET /api/moi` répondait
`referent: null` sur l'instance réelle. Les deux variables existaient bien dans `deploy/`,
mais EN COMMENTAIRE dans `docker-compose.yml` : les activer aurait fait diverger un fichier
suivi par git — le conflit de `git pull` que cette fiche venait de fermer le matin même
pour les trois domaines. Le défaut n'était donc pas l'oubli d'une variable, c'était une
décision appliquée à moitié.

**Et le contrôle n'a délibérément PAS été élargi.** Faire signaler un référent vide par
`verifier_deploiement.py --config` le ferait sonner à chaque premier déploiement, au moment
précis où la valeur vide est la bonne réponse. Un avertissement qu'on a toujours raison
d'ignorer n'apprend plus rien — et il use la confiance accordée à tous les autres.

**Un reste sans conséquence aujourd'hui** : `users_database.yml` porte encore l'adresse du
gabarit, `chercheur@example.fr`. Le notifier écrit dans un fichier, aucun courriel ne part.
Elle devra être réelle le jour d'une bascule sur SMTP : réinitialisation de mot de passe et
récupération de 2FA en dépendent, et c'est le seul recours quand l'appareil TOTP est perdu.

## Contexte

**P1, effort L — et la fiche qui débloque le plus de choses** : INFRA-3 (credentials
WebDAV par utilisateur), SEC-2 (le volet CSRF, qui n'a de sens qu'avec des sessions) et
EXP-1 (exposer les exports de dépôt dans l'UI) en dépendent tous, et ANN-5 (accord
inter-annotateurs, livré) ne servira vraiment qu'une fois plusieurs annotateurs en ligne.

Le code applicatif est prêt depuis le 26 juin — **et l'infrastructure est écrite aussi** :
`deploy/` contient déjà le Dockerfile (36 lignes, moteurs ML + Kumiko, un seul worker
parce que l'app garde des états en mémoire), le `docker-compose.yml` à quatre services,
le `Caddyfile`, la config Authelia et un `.dockerignore` soigné. Vérifié le 2026-08-27 :
rien de tout cela n'est à écrire.

Ce qui manque est le geste, pas le fichier : **rien n'a jamais été construit ni lancé**.
C'est de l'infrastructure sur une machine qui n'est pas celle-ci — d'où l'arrêt net, et
d'où le fait que deux mois plus tard rien n'a bougé. Le risque n'est donc pas la
conception, c'est ce qu'un premier `docker compose up` révélera.

Attention au dimensionnement mémoire : CONC-2 documente un OOM observé en enchaînant
segmentation, bulles, OCR et NLP sur une vraie planche. Un VPS contraint reproduira ce
problème plus tôt qu'un poste de dev.

**Empreinte mémoire mesurée le 2026-08-27** (VM Docker à 8,17 Go, image CPU, planche
synthétique 1600×2200) : application seule **49,7 Mio** ; + spaCy préchargé **143,4 Mio** ;
+ YOLOv8 **826,4 Mio** ; + EasyOCR, les trois moteurs, **833,6 Mio** — soit ~10 % de la
mémoire disponible. `/api/sante` montrait alors `modeles_charges: {bulles: false, ocr:
true, nlp: true}` : l'orchestrateur de **CONC-2 v1 déchargeait bien YOLO** avant la passe
interactive. Ces chiffres remettent en cause la nécessité de CONC-2 v2 — cf. sa fiche.

**Le premier build a eu lieu le 2026-08-27, et il a tout appris.** Trois blocages en
cascade, dont aucun n'était prévu : le proxy universitaire invisible au démon Docker
(Windows n'en déclare aucun, seules les variables de shell l'ont) ; `docker-credential-desktop`
absent du PATH, Docker Desktop 4.88 s'installant par utilisateur hors de `Program Files` ;
et la pile CUDA embarquée par défaut. Aucun des trois ne se voyait sans construire.

Les trois secrets attendus par compose, Caddy et Authelia sont tous documentés dans
`deploy/.env.example` (vérifié) — ce n'est pas là que ça achoppera. Restent les domaines
`example.fr` à remplacer et le hash Authelia, encore à `REMPLACER_PAR_UN_VRAI_HASH`.

**Le trou du NLP était le plus coûteux, et il était silencieux.** Sans spaCy, `nlp_available()`
vaut False et tout dégrade *proprement* — aucune erreur, aucun log alarmant. Mais la table
`tokens` n'est jamais peuplée, donc `tokens_effectifs` est vide, donc : l'Exploration
(distribution, concordance, croisement, comparaison) ne montre rien, le statut de relecture
(ANN-4) reste « à faire » sur tout le corpus, les rapports d'accord (NLP-1) et inter-annotateurs
(ANN-5) sortent vides, et la recherche perd les lemmes. **Quatre chantiers livrés seraient
morts en production sans qu'aucun message ne le dise.** Vérifié le 2026-08-27 sur le
Dockerfile ; le lock, lui, prévoit déjà `spacy==3.8.14` et documente
`python -m spacy download fr_core_news_sm`.
