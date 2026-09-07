# Hébergement & sécurité — notes d'analyse

> Analyse réalisée le 2026-06-13 sur la branche `main` (commit `ede51ad`).
> **État actuel : aucune authentification n'est en place.** C'est un choix
> assumé — l'app a été conçue pour un usage **local, mono-utilisateur**. Une
> couche d'**authentification (accès gated à tout)** est prévue *avant* toute
> exposition sur un VPS. Ce document liste ce qu'il faut savoir, dimensionner et
> corriger avant cette mise en ligne.

## 1. Modèle de concurrence (à comprendre avant tout)

Les routes sont des `def` **synchrones** → FastAPI les exécute dans un
threadpool (~40 threads). Donc, **même en un seul process uvicorn, plusieurs
requêtes s'exécutent réellement en parallèle**, chacune avec sa propre connexion
SQLite (`check_same_thread=False`, `main.py:51-65`).

- **État global au process** : `_jobs` (`pipeline/jobs.py:19`), `_session`
  ShareDocs (`pipeline/sharedocs.py:33`), `_model` YOLO (`pipeline/bulles.py:23`),
  `_reader` EasyOCR (`pipeline/ocr.py:24`), `_crop_cache` (`pipeline/ocr.py:123`).
  → **Mono-process obligatoire.** Interdit de lancer `uvicorn --workers N` /
  gunicorn multi-workers : l'état divergerait (jobs, session, modèles).

- **✅ Corrigé — thread-safety des routes ML directes.** Un verrou partagé
  `jobs.ML_LOCK` sérialise désormais TOUTE inférence ML (worker de lot ET routes
  `/ocr`, `/detecter-bulles`, `/segmenter`) → plus d'inférence concurrente (anti-OOM)
  ni de *check-then-set* de modèle non atomique. (Le cache de crop était déjà
  verrouillé via `_crop_lock`.)

- **Les inférences ML bloquent des threads du pool** pendant toute leur durée
  (lentes, CPU) → quelques appels ML concurrents peuvent affamer les requêtes
  normales (annotation, recherche).

- **✅ Atténué — contention d'écriture SQLite pendant un job.** Au-delà de
  `busy_timeout=5000`, `database is locked` reste possible, mais un **handler
  global** renvoie désormais **409** (« réessayez ») au lieu d'un 500 brut sur les
  routes d'écriture (la sérialisation ML réduit aussi la fenêtre de contention).

## 2. Sécurité — failles à corriger AVANT exposition

Relevées quand rien n'authentifiait, ce qui les amplifiait toutes. **L'instance sert
derrière Authelia depuis le 2026-09-05 (INFRA-1)** : la colonne Sévérité dit l'état
constaté au 2026-09-07, pas celui du relevé d'origine.

| Sévérité | Faille | Référence | Détail |
|---|---|---|---|
| ✅ **Corrigé** | **SSRF via ShareDocs** | `pipeline/sharedocs.py` (`_check_url`, `_client`) | Était : URL contrôlée par le client + `follow_redirects=True` → cible interne possible. **Corrigé** : allowlist d'hôte (`BD_SHAREDOCS_ALLOWED_HOSTS`, défaut `sharedocs.huma-num.fr`), refus des IP internes, `follow_redirects=False`. |
| ✅ **Corrigé** | **Exfiltration totale non authentifiée** | `main.py` (`_exiger_admin_sauvegarde`, route `/derivatives`) | Était : `GET /api/sauvegarde` → snapshot **complet** de la base en un GET, et `/derivatives/...` monté en `StaticFiles` → toutes les images, aux chemins parfaitement devinables. **Corrigé en DEUX temps, et les deux moitiés n'ont pas la même leçon.** Le montage est devenu une ROUTE cloisonnée (AUTH-2), la base servant d'allowlist — un montage n'a aucune dépendance, le cliquet ne le voyait donc pas, et c'est une relecture qui l'a trouvé ; `MONTAGES_AUTORISES` ne porte plus que `/static`. Les deux routes de sauvegarde sont réservées aux administrateurs (DROIT-1, cf. §6), leur raison écrite ayant porté sa propre condition de réouverture. |
| ✅ **Corrigé** (partiel) | **OOM upload + bombe de décompression** | `config.py` (`MAX_IMAGE_PIXELS`), `ingest.py`, `ocr.py` | **Corrigé** : garde Pillow réactivée (`MAX_IMAGE_PIXELS` borné, défaut 200 Mpx, `BD_MAX_IMAGE_PIXELS`) → plus d'OOM sur image-bombe ; limite de taille d'upload posée côté **proxy Caddy** (`request_body 200MB`). Restant (mineur) : `file.file.read()` en RAM + image ouverte deux fois. |
| ✅ **Corrigé** | **Pic RAM de la sauvegarde** | `pipeline/backup.py` | **Corrigé** : `make_backup` zippe désormais directement depuis le fichier snapshot (plus de `read_bytes()` complet en RAM) → pic ÷ ~2. |
| ✅ **Corrigé** | **Aucune Content-Security-Policy** | `main.py` (`_csp`) | Était : aucun en-tête, donc rien pour amortir un XSS qui passerait l'échappement, ni contre le clickjacking. **Corrigé (SEC-2)** : `script-src 'self'` sans `'unsafe-inline'` — les quatre surfaces n'ont aucun script inline, la politique ne coûte donc rien —, plus `object-src`/`base-uri`/`frame-ancestors` fermés. `/docs` et `/redoc` reçoivent une politique DISTINCTE (CDN autorisé, principes gardés) plutôt qu'une exemption. |
| 🟡 Faible | **Fuite d'info par messages d'erreur** | divers `HTTPException(…, str(exc))` | Chemins disque, erreurs SQL, URLs internes renvoyés au client. |

### La CSP est de la défense en profondeur, pas un colmatage (SEC-2, 2026-08-31)

L'audit passe 1 relevait deux `innerHTML` interpolant des labels de tags sans échapper, et
recommandait DEUX correctifs : « échapper systématiquement, ajouter une CSP ». Le premier
a été fait depuis — il ne reste aucune interpolation de donnée utilisateur hors `esc()`,
`textContent` ou `confirm()`. La CSP est le second, et sa valeur est d'être utile le jour
où l'échappement manquera quelque part : `script-src 'self'` bloque aussi bien un
`<script>` injecté qu'un attribut `onerror=`, qui est la forme qu'aurait prise ce défaut.

Trois faits qui expliquent pourquoi elle a coûté si peu :
- **Rien à réécrire.** Zéro `<script>` inline, zéro `<style>`, zéro `onclick=`, zéro
  `eval`, aucune ressource externe dans les quatre gabarits. La sévérité était déjà là,
  personne ne l'avait déclarée.
- **Une seule tolérance, et bornée.** Dix attributs `style="width:…%"` portent des valeurs
  CALCULÉES (barres, heatmap, jauges d'accord) qui ne peuvent pas rejoindre la feuille de
  style. `style-src-elem 'self'` reprend d'une main ce que `style-src 'unsafe-inline'`
  donne de l'autre : aucun `<style>` n'existe, donc le canal élément est strict
  gratuitement, et seul l'attribut reste ouvert.
- **La politique est EXÉCUTÉE par un test**, pas seulement servie (`tests/test_csp.py`) :
  un vrai Chromium charge les six surfaces et écoute `securitypolicyviolation`. C'est ce
  test qui a trouvé les deux choses qu'aucune lecture de source ne pouvait voir — le
  `<link rel="icon" href="data:,">` des gabarits, et le logo que ReDoc va chercher sur
  `cdn.redoc.ly` depuis l'intérieur de son bundle. Ce dernier reste BLOQUÉ et déclaré :
  on n'ouvre pas un hôte tiers pour une image décorative.

Reste ouvert dans SEC-2 : le CSRF, qui n'a pas de sens tant qu'il n'y a pas de session à
voler — il dépend d'INFRA-1.

### Points confirmés SAINS (ne pas sur-corriger)
- **Pas d'injection SQL** : recherche FTS5 avec tokens échappés + `MATCH` paramétré
  (`main.py:783-787`) ; ailleurs, valeurs liées et noms de colonnes statiques.
- **Pas de traversée de chemin** : fichiers nommés `planche_{numero:04d}`, seul le
  suffixe vient du client et ne peut contenir de `/` (`pipeline/ingest.py:153-157`) ;
  `_rel_posix` via `relative_to(DATA_DIR)`.
- Course écriture→lecture déjà traitée (commit explicite, `main.py:51-57`).
- Préservation du travail humain à la re-détection (CTE `doomed`, `bulles.py:107-122`).

## 3. Capacités VPS recommandées

| Usage | vCPU | RAM | Disque |
|---|---|---|---|
| Annotation + recherche seules (ML désactivé) | 1–2 | 1–2 Go | dominé par les TIFF |
| Avec les 3 passes ML (segmentation / bulles / OCR) | 4 | **8 Go** (4 Go = risque OOM) | + cache modèles ~1–2 Go |

- **Pilote mémoire = images décodées + modèles torch résidents** (`_model`/`_reader`
  restent chargés après le 1er appel). La base reste modeste (texte/métadonnées).
- **Disque dominé par les masters TIFF** (`corpus/`) : dizaines–centaines de Go.
- **Disque local uniquement** pour la base (WAL casse sur NFS/CIFS).
- **Modèles téléchargés au 1er appel** (`hf_hub_download`, `easyocr.Reader()`) →
  sur VPS sans egress, pré-charger au provisioning. Repo HF **non épinglé** à une
  révision → à fixer (reproductibilité / supply-chain).

## 4. Plan d'action (par priorité)

1. **Authentification + isolement réseau** (reverse proxy auth/TLS, ou VPN/firewall).
   Neutralise d'un coup l'exfiltration `/api/sauvegarde` + `/derivatives` et réduit
   SSRF/DoS. ← *la couche prévue.*
2. **Anti-SSRF ShareDocs** : allowlist du host (domaine Huma-Num), refus IP
   privées/loopback/link-local, `follow_redirects=False`.
3. **Garde-fous upload** : limite de taille (proxy + appli), `MAX_IMAGE_PIXELS`
   raisonnable, streaming vers disque, ouvrir l'image une seule fois.
4. **Verrouiller les routes ML directes** (Lock partagé avec le worker, ou les
   router vers la file de jobs) + rendre `_get_reader`/`_load_model` atomiques.
5. **1 worker uvicorn + systemd** (sans `--reload`), modèles pré-chargés,
   `/api/sante` en liveness probe.
6. **Figer les dépendances** (lockfile) + **épingler la révision du modèle HF** ;
   sauvegarde automatisée hors-site (en tenant compte du pic RAM de `make_backup`).
7. Attraper `OperationalError` sur les routes d'écriture (409/retry) et
   **assainir les messages d'erreur**.

## 5. Rappels d'exploitation

- Lancement prod : `uvicorn main:app --workers 1` (jamais `--reload`).
- Données configurables : `BD_DATA_DIR` (racine corpus/derivatives/base),
  `BD_DB_PATH` (base). ShareDocs : `BD_SHAREDOCS_URL/USER/PASS` (le mot de passe
  n'est jamais persisté ni renvoyé). **Depuis SHARE-1, ces trois variables déclarent
  le compte d'INSTANCE**, vivant dès le démarrage et servant de repli à qui n'a pas
  connecté le sien — à assumer : toute personne admise sur l'instance peut s'en servir.
  Le couper ou le remplacer est réservé aux administrateurs. Les sessions personnelles
  s'ajoutent, une par principal, et restent comme avant **en mémoire serveur
  uniquement** — deux magasins désormais, aucun sur disque.
- Auth (derrière proxy) : `BD_AUTH_LOGOUT_URL` = URL de déconnexion du portail
- Auth (derrière proxy) : **`BD_AUTH_PROXY`** = déclare qu'un proxy d'authentification
  est bien devant l'application (AUTH-1). **Sans ce drapeau, les en-têtes d'identité
  (`Remote-User`, `Remote-Groups`, `Remote-Name`, `Remote-Email`) sont IGNORÉS** et tout
  acte reste anonyme. Ne le poser QUE si le `forward_auth` est réellement en place :
  autrement, n'importe quel client atteignant l'app en direct pourrait se déclarer qui il
  veut — sans conséquence tant que rien n'est autorisé sur cette base, escalade de
  privilège dès qu'une autorisation en dépendra.
  (ex. `https://auth.example.fr/logout`), affichée dans l'UI avec l'utilisateur
  connecté (`Remote-User`). Vide en local → ni nom ni lien affichés.
- Auth (derrière proxy) : **`BD_AUTH_ADMIN_GROUPS`** = groupes dont les membres voient
  tout le corpus (défaut `bd-admins`). Comme les autres groupes, leur composition n'est
  jamais stockée : elle vit dans Authelia et est relue à chaque requête.
- Auth : **`BD_REFERENT_NOM`** / **`BD_REFERENT_CONTACT`** (AUTH-4) = à qui s'adresser
  quand on est bloqué. Ils vivent dans l'environnement et non en base pour une raison de
  PORTÉE : c'est le seul référent qu'une portée VIDE puisse lire, or c'est exactement la
  personne à qui le bandeau dit « demander un accès à un administrateur » sans nommer
  personne. La déclaration est DÉCLARATIVE et l'écran le dit : l'application ne connaît
  les groupes que de la personne qui frappe (AUTH-1), l'appartenance d'un TIERS lui est
  structurellement invérifiable — un référent parti reste affiché. Vides derrière le
  proxy → le bandeau retombe sur sa formule anonyme ; en mono-poste, ils ne s'affichent
  jamais, non plus que les noms de `BD_AUTH_ADMIN_GROUPS` : sans proxy aucun groupe n'est
  lu, donc nommer `bd-admins` distinguerait deux rôles là où une seule personne a déjà
  tout.
- Les jobs sont **éphémères** (threads daemon, registre RAM) : un redémarrage les
  perd. Le travail DB déjà committé par passe survit ; le suivi de job non.

## 6. Cloisonnement par collection (AUTH-2)

Jusqu'à AUTH-2, l'application faisait de l'**affichage seul** : Authelia disait qui entre,
et quiconque entrait voyait tout. Ce n'est plus vrai — et la phrase « l'autorisation est
entièrement assurée par Authelia », qui figurait ici, ne l'est plus non plus.

**La collection est l'unité de cloisonnement.** On n'autorise jamais un album directement :
on autorise une collection (`collection_acces` : collection × principal × niveau), et
l'album suit celle qui le contient. `principal` est un login OU un nom de groupe lu dans
`Remote-Groups` ; ce qui est stocké est une RÉFÉRENCE à un nom de groupe, jamais une
appartenance — celle-ci reste chez Authelia et se relit à chaque requête.

Corollaire : **aucun album ne peut être hors collection** (`database.collection_par_defaut`).
Un orphelin ne correspondrait à aucune règle, et il faudrait inventer une politique dans le
code, à un endroit qu'on oublierait de relire.

### Le regarder fonctionner sans monter Authelia (2026-09-03)

Tout ce qui suit est **inobservable en mono-poste**, et c'est structurel : sans
`BD_AUTH_PROXY`, l'application ignore les en-têtes d'identité et donne la portée totale.
Un navigateur, lui, n'envoie pas ces en-têtes — si bien qu'on ne peut voir qu'UN état,
celui où aucune identité ne parvient. Le cloisonnement, les trois niveaux d'AUTH-3, le
pouvoir déclaré de l'administrateur (AUTH-4) et le 404-jamais-403 restent entièrement
écrits, testés, et invisibles.

`tools/faux_proxy_auth.py` ferme cet angle mort. Il tient le rôle d'Authelia et rien
d'autre — il pose `Remote-User` / `Remote-Groups` / `Remote-Name` / `Remote-Email` et
relaie —, ce qui est précisément le partage des rôles d'AUTH-1 : **le proxy dit QUI,
l'application décide QUOI**. Cinq identités, choisies pour montrer chacune un état
différent, dont les trois pannes que le bandeau de portée vide distingue. Le mode
d'emploi est en tête du fichier.

C'est un outil de DÉVELOPPEMENT : il n'authentifie personne et pose l'identité qu'on lui
demande. Devant une instance réelle il donnerait à quiconque l'identité de son choix,
`bd-admins` compris.

Ce n'est pas un substitut à INFRA-1 : ce que le faux proxy montre, c'est le comportement
de l'APPLICATION derrière un proxy. Que le vrai proxy refuse bien une requête non
authentifiée avant de l'atteindre reste à vérifier sur le déploiement, et c'est une case
d'INFRA-1.
Trois comportements à connaître avant d'exploiter une instance.

**Le refus est un 404, jamais un 403.** Dire « cet album existe, mais pas pour vous »
révèle la composition du corpus. La contrepartie : qui perd un droit ne verra pas d'erreur,
ses objets auront simplement disparu.

**Sans `BD_AUTH_PROXY`, tout passe.** C'est le mono-poste, et le comportement est
exactement celui d'avant AUTH-2.

**Avec `BD_AUTH_PROXY` mais sans en-tête d'identité, rien ne passe.** Une requête qui n'a
pas traversé Authelia ne voit rien. Si le `forward_auth` est mal configuré, l'application
paraîtra VIDE pour tout le monde : c'est une panne bruyante et immédiate, préférée à une
fuite silencieuse. Si l'instance semble vide au premier démarrage, chercher là d'abord.

### Administrer une collection — AUTH-3

Le cloisonnement d'AUTH-2 ne s'administrait qu'en SQL : `tools/gerer_collections.py` était
le seul outil d'écriture, et il exige un accès shell. Ce n'est plus le cas — la Bibliothèque
a un écran **Collections** (créer, renommer, supprimer, accorder et retirer un accès), et
l'appartenance d'un album se gère depuis sa fiche.

**Trois niveaux, et le troisième n'est pas une gradation du deuxième.** `lecture` puis
`ecriture` (annoter) puis `proprietaire` (décider qui d'autre entre). Un membre en écriture
n'hérite PAS du droit de partager : sinon le cercle s'élargirait sans que le propriétaire le
sache, et un accès accordé par erreur deviendrait intraçable.

**Ce que « accorder un accès » veut dire exactement.** On ne désigne pas une personne
vérifiée : on déclare qu'un NOM — un login, ou un nom de groupe tel qu'Authelia le pose dans
`Remote-Groups` — ouvre une collection. L'application n'a aucun annuaire (invariant AUTH-1),
et **un nom mal orthographié n'ouvre rien, silencieusement**. C'est le mode d'échec à
connaître avant d'exploiter une instance : si quelqu'un ne voit toujours rien après un
partage, vérifier l'orthographe du login avant de chercher ailleurs.

**Deux états sont interdits, et refusés par un 409 qui les nomme** — pas par un 403 : ce
n'est pas un droit qui manque, c'est un état que le modèle n'admet pas.

- *Zéro propriétaire sur une collection.* Retirer ou rétrograder le dernier est refusé.
  Sans cela, seule une intervention d'administrateur pourrait rouvrir la collection — le
  SQL à la main que ce chantier existe pour supprimer.
- *Zéro collection pour un album.* Sortir un album de sa dernière collection est refusé, et
  supprimer une collection l'est aussi tant qu'un album n'a qu'elle. Un orphelin ne
  correspondrait à aucune règle d'accès (invariant AUTH-2). Déplacer, c'est donc ranger
  ailleurs PUIS sortir — l'ordre inverse se voit refuser plutôt que de déverser le travail
  dans un seau commun.

**Retirer un accès ne détruit AUCUNE donnée.** Les annotations faites par la personne
restent, et le journal A3 continue de les lui attribuer : le corpus perdrait sa provenance
à chaque départ. De même, supprimer une collection ne supprime pas ses albums — l'appartenance
est N-N, le lien se défait et l'œuvre reste ; ses termes de vocabulaire sont promus en
global plutôt que perdus.

**L'administrateur passe outre la propriété**, et c'est le recours prévu quand quelqu'un
quitte le projet en laissant une collection derrière lui. Il ne se déclare pas propriétaire
des collections qu'il crée : il possède déjà tout, et lui inventer un lien personnel avec
chacune fausserait la notion.

**Créer une collection exige une IDENTITÉ, pas un droit.** Quelqu'un qui n'a encore accès à
rien peut en ouvrir une — sinon l'application serait inutilisable au premier jour de
chacun. Mais derrière le proxy, une requête sans en-tête d'identité est refusée par un
**403 qui nomme la panne** : elle n'est pas passée par Authelia, et c'est une configuration
à réparer, pas un objet à cacher.

**Le nom « Collection par défaut » est RÉSERVÉ.** Le repli est désigné par son nom, et se
l'attribuer capturerait les albums créés sans collection explicite — y compris ceux d'un
administrateur, qui deviendraient visibles de qui a fait le renommage. La garde vaut à la
création, au renommage, et dans l'outil headless ; elle est insensible à la casse.

**Les changements d'accès sont TRACÉS** dans le journal de provenance (A3) : événements
`lien` / `delien` sur `collection_acces`, avec l'agent qui les a posés. C'est la contrepartie
de « seul le propriétaire partage » — un accès accordé par erreur doit pouvoir se retrouver.
Ils ne sont pas annulables : défaire un partage par Ctrl+Z serait une surprise.

### Le vocabulaire suit sa propre règle, et sa hiérarchie avec

Un terme (tag, domaine, dimension, valeur) n'est pas une donnée : il est visible s'il est
**global** ou local à une collection qu'on lit. C'est la portée d'appartenance du lexique
situé, pas celle du corpus — une personne sans aucune collection voit donc quand même le
vocabulaire global, et aucune donnée. Leurs COMPTEURS, en revanche, se filtrent comme des
données : un nuage de tags doit refléter le sous-corpus qu'on regarde.

Le vocabulaire est hiérarchique, et sa portée descend avec lui : **un terme n'est jamais
plus global que celui dont il dépend** (v24 ; cf. `docs/lexique-situe.md`). Ce que révélait
l'inverse n'était pas le mot mais le NOM de son parent — une dimension, un domaine,
c'est-à-dire une grille d'analyse. La relecture du 2026-08-28 l'a trouvé sur une suite
entièrement verte : les routes filtraient bien le terme demandé, pas son parent.

### Ce qui était ouvert à tous — décision du 2026-08-27, REJOUÉE le 2026-08-28

`GET /api/sauvegarde` et `POST /api/sharedocs/deposer-sauvegarde` déversent la base
**ENTIÈRE**, toutes collections confondues. Ils sont **réservés aux administrateurs**
depuis DROIT-1 (`main.py`, `_exiger_admin_sauvegarde`).

**La décision d'origine portait sa propre condition de réouverture, et c'est elle qui a
tiré.** Le 2026-08-27, ces routes restaient accessibles à tout compte authentifié, au motif
qu'une sauvegarde partielle ne restaure pas une instance et que le nom deviendrait
trompeur ; la condition écrite était « dès que l'instance accueille quelqu'un qui n'a pas
le droit de tout voir — un partenaire extérieur, **un tiering de droits effectif
(DROIT-1)**, un corpus sous embargo ». DROIT-1 est arrivé le lendemain.

**L'argument d'origine tient, et c'est pourquoi la route n'a PAS été cloisonnée** : la
sauvegarde reste ENTIÈRE et change de PUBLIC. Sauvegarder est un geste d'exploitation, pas
de recherche — le restreindre ne retire rien à personne qui en avait l'usage.

**Ce qui a rendu la bascule impossible à oublier** vaut d'être noté, parce que c'était le
but : la raison était écrite dans `HORS_PERIMETRE` (`tests/test_autorisation.py`), donc la
changer supposait de relire la liste. Les deux routes en sont SORTIES le 2026-08-28 et
consultent désormais la portée comme les autres. Leur comportement est verrouillé par
`test_la_sauvegarde_est_reservee_aux_administrateurs` — 403 pour un compte ordinaire, 200
pour un administrateur — et par `test_le_mono_poste_garde_sa_sauvegarde` : sans proxy, il
n'y a personne à qui refuser, et le comportement d'avant est strictement conservé.

**Cette page a pourtant affirmé le contraire pendant dix jours**, relevé le 2026-09-07. Le
sens de l'erreur mérite d'être nommé : elle décrivait l'instance comme plus OUVERTE qu'elle
n'est. Personne n'en tire donc un faux sentiment de sécurité — on refait un travail déjà
fait, ou l'on renonce à exposer une instance qui peut l'être. **Ce n'est pas la décision
qui a vieilli, c'est le verrou qui a bougé sans que la page le suive** : `HORS_PERIMETRE`
était nommée ici comme la garde, et elle a cessé de l'être le jour où les deux routes en
sont sorties.
