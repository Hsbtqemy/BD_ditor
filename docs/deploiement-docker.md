# Déploiement sur VPS — Docker Compose + authentification (Authelia)

Guide pas à pas, pensé pour quelqu'un qui débute sur Docker. La pile fournit :
**plusieurs comptes**, **déconnexion propre**, **2FA**, **HTTPS automatique**, et
gate **tout** l'accès (y compris images et sauvegarde) sans modifier le code de
l'app. Architecture retenue : *portail d'accès*, Authelia disant **qui** est là.
Ce que chacun voit, en revanche, appartient à l'application depuis AUTH-2 : les
accès se donnent **par collection** (lecture / écriture / propriétaire), et un
album suit celles qui le contiennent. Cette page décrivait un « corpus partagé où
tous les comptes voient la même chose », ce qui n'est plus vrai — cf.
`docs/hebergement-securite.md`.

## 1. Ce que fait chaque conteneur

| Conteneur | Rôle | Exposé sur Internet ? |
|---|---|---|
| **caddy** | Reverse proxy : HTTPS auto (Let's Encrypt) + redirige vers Authelia/app | **Oui** (ports 80/443) |
| **authelia** | Portail de connexion : comptes, login/**logout**, **2FA**, anti-bruteforce | Non (interne) |
| **redis** | Mémorise les sessions (permet expiration + déconnexion propre) | Non (interne) |
| **app** | L'application FastAPI BéDéditeur | **Non** (jamais en direct) |

Principe clé : **seul Caddy est exposé**. Toute requête vers l'app passe d'abord
par Authelia (`forward_auth`). Non connecté → redirection vers le portail.

## 2. Prérequis

- Un **VPS** (Debian/Ubuntu récent conseillé) avec Docker + plugin Compose :
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```
- **4 Go de RAM** recommandés, et voici sur quoi repose ce chiffre plutôt que sur une
  habitude. MESURÉ le 2026-08-27, les trois passes enchaînées dans un seul conteneur sur
  un vrai master (3748 × 4710, 17,7 Mpx, 400 dpi) : application seule 49,7 Mio, + spaCy
  173, + segmentation 410, + bulles 779, + OCR 1,036 Gio — **pic observé 1,216 Gio**.
  DÉDUIT du reste : les quatre autres conteneurs (Caddy, Authelia, Redis, plus le système)
  sont petits mais pas nuls, et SQLite en WAL travaille mieux avec du cache disque libre.
  2 Go peuvent suffire à une instance qui n'enchaîne jamais les passes — ce cas-là n'a pas
  été mesuré, et l'OOM se manifeste par un process tué SANS traceback Python, donc sans
  rien à lire pour comprendre.
- Un **nom de domaine** avec **deux sous-domaines** pointant (enregistrement DNS
  **A**) vers l'IP du VPS :
  - `bd.example.fr`   → l'application
  - `auth.example.fr` → le portail Authelia
- Les **ports 80 et 443 ouverts** sur le VPS (Caddy en a besoin pour les certificats).

> Les deux sous-domaines doivent partager un **domaine parent commun**
> (`example.fr`) : c'est ce qui permet à la session de couvrir les deux.

## 3. Configuration (5 remplacements)

Récupère le dépôt sur le VPS, puis place-toi dans `deploy/`.

1. **Domaines** — remplace `example.fr` partout dans :
   - `deploy/Caddyfile` (les 2 blocs `auth.…` et `bd.…`)
   - `deploy/authelia/configuration.yml` (`totp.issuer`, `access_control`, `session.cookies`)
   - `deploy/docker-compose.yml` (`BD_AUTH_LOGOUT_URL` → lien de déconnexion dans l'UI)

2. **Secrets** — crée `deploy/.env` à partir du modèle et génère 3 valeurs :
   ```bash
   cp .env.example .env
   for k in AUTHELIA_SESSION_SECRET AUTHELIA_STORAGE_ENCRYPTION_KEY AUTHELIA_JWT_SECRET; do
     echo "$k=$(openssl rand -hex 32)" 
   done
   # colle les 3 lignes obtenues dans deploy/.env
   ```

3. **Mot de passe du 1er compte** — génère un hash et colle-le dans
   `deploy/authelia/users_database.yml` (champ `password`) :
   ```bash
   docker run --rm authelia/authelia:4.38 \
     authelia crypto hash generate argon2 --password 'TonMotDePasse'
   ```
   Ajuste aussi `displayname` / `email`. Pour d'autres comptes, duplique le bloc.

## 4. Démarrage

Depuis `deploy/` :
```bash
docker compose up -d --build      # construit l'app et lance les 4 conteneurs
docker compose logs -f            # suivre les logs (Ctrl+C pour quitter)
```
Le premier build est long (torch + modèles). Caddy obtient les certificats TLS
automatiquement dès que le DNS pointe bien sur le VPS.

## 5. Première connexion + activation de la 2FA

1. Ouvre `https://bd.example.fr` → tu es redirigé vers `https://auth.example.fr`.
2. Connecte-toi (identifiant `chercheur` + ton mot de passe).
3. Pour enregistrer la 2FA, Authelia génère un lien. Avec le notifier
   « filesystem » (par défaut), récupère-le ici :
   ```bash
   docker compose exec authelia cat /config/notification.txt
   ```
   Ouvre le lien, scanne le QR code avec une app TOTP (Aegis, Google
   Authenticator…). Ensuite la connexion demandera le code à 6 chiffres.

> Pour de vrais e-mails (liens reçus par mail au lieu d'un fichier), remplace le
> bloc `notifier:` de `configuration.yml` par un notifier **SMTP**.

## 6. Déconnexion

`https://auth.example.fr/logout` — détruit la session (côté Redis). L'interface
**affiche déjà ce lien** : la bande de navigation montre « 👤 *nom* · Déconnexion »
dès que l'app est derrière le proxy (en-tête `Remote-User`). Le lien pointe vers
`BD_AUTH_LOGOUT_URL` (réglé dans `docker-compose.yml`). En local, sans proxy, ni le
nom ni le lien n'apparaissent.

**`BD_AUTH_PROXY` (AUTH-1) — à ne pas oublier.** L'application n'exploite les en-têtes
d'identité que si ce drapeau est posé ; `docker-compose.yml` le pose à `1`. Sans lui, la
pile Authelia + Caddy tournerait normalement, les utilisateurs se connecteraient — et
l'application les traiterait tous comme anonymes, sans le moindre message. Symétriquement,
le poser sur une application joignable autrement que par Caddy revient à croire n'importe
quel `Remote-User` envoyé par n'importe qui.

**`BD_AUTH_ADMIN_GROUPS` (AUTH-2) — le premier réglage à faire après le déploiement.**
Depuis AUTH-2, l'application autorise : on ne voit que les collections ouvertes pour soi
dans `collection_acces`. Une instance neuve n'en ouvre AUCUNE. Concrètement, si personne
n'appartient à un groupe d'administration, **tout le monde se connecte correctement et
voit une application vide** — et rien n'indique pourquoi.

Le défaut est `bd-admins` : déclarez ce groupe dans `deploy/authelia/users_database.yml`
et mettez-y au moins une personne, ou changez le nom via cette variable. Ensuite seulement,
les accès des autres se donnent collection par collection.

C'est aussi le symptôme à connaître : **une instance qui paraît vide pour tout le monde**
n'est presque jamais une base perdue, c'est un droit manquant — ou un `forward_auth` qui
ne pose pas `Remote-User`, auquel cas la portée est vide par fermeture délibérée
(cf. `docs/hebergement-securite.md` §6).

## 7. Opérations courantes

```bash
docker compose ps                 # état des conteneurs
docker compose restart app        # redémarrer juste l'app
docker compose down               # tout arrêter (les données restent dans les volumes)
docker compose up -d --build      # rebuild + relance après une mise à jour du code
```

- **Données persistées** dans des volumes Docker (`bd-data` = corpus, dérivés,
  base, caches de modèles ; `caddy-data` = certificats ; sessions dans `redis`).
  Un `docker compose down` ne les efface pas (`down -v` le ferait — à éviter).
- **Sauvegarde** : la base reste accessible via `/api/sauvegarde` (désormais
  derrière l'auth). Pense aussi à sauvegarder le volume `bd-data` (masters TIFF).

## 8. Un moteur en panne

**« En panne » n'est pas « absent ».** Les quatre moteurs (Kumiko, bulles, OCR, spaCy)
sont OPTIONNELS : absent, un moteur ne casse rien — sa passe répond 503 et le reste de
l'outil fonctionne. Le cas grave est l'autre : un moteur **installé mais cassé**, que le
contrôle de présence annonce disponible. C'est arrivé trois fois le même jour en
construisant la première image, et rien ne le disait.

### Le voir

| Où | Comment | Pour qui |
|---|---|---|
| **Bibliothèque → 🩺 Moteurs** | bouton **Éprouver les moteurs** | l'opérateur sans accès shell — c'est la seule fenêtre dont il dispose |
| API | `GET /api/sante?profond=1` | script, supervision |
| Conteneur | `docker exec bd-app python tools/verifier_moteurs.py` | qui a le shell ; `--json` pour une sortie machine |

Le contrôle **rapide** — `/api/sante` sans paramètre, celui d'une sonde de conteneur et
celui qu'affiche le panneau à son ouverture — ne fait que LOCALISER les modules. Il ne voit aucune incompatibilité binaire, et c'est
délibéré : importer torch coûte plusieurs secondes et quelques centaines de mégaoctets,
qu'une route de santé ne peut pas payer. Le contrôle **profond** importe réellement, et
dit pourquoi quand ça rate.

> **Après une réparation, redémarrez l'app** : `docker compose restart app`. Le verdict
> profond est mémorisé **par processus** — un moteur réparé à chaud dans le conteneur
> continuerait d'être annoncé en panne, et re-cliquer « Éprouver » n'y changerait rien.
> Cette mémorisation est voulue (sans elle, un clic répété rechargerait torch autant de
> fois qu'on insiste) ; et le chemin normal — `docker compose up -d --build` — redémarre
> le processus, donc repose la question tout seul.

### Les trois pannes déjà rencontrées, et leur remède

**1. `RuntimeError: operator torchvision::nms does not exist`** — moteurs `bulles` et
`ocr`.
`torchvision` vient de PyPI, compilé contre le torch **CUDA**, et se retrouve posé sur
un torch **CPU**. Les deux doivent venir du **même index** :

```bash
pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.13.0 torchvision==0.28.0
```

C'est ce que fait `deploy/Dockerfile` avant tout le reste. Une installation qui
réinstallerait torch après coup (une dépendance transitive, par exemple) rejouerait la
panne : `pip list | grep -i torch`, les deux doivent porter le même suffixe.

**2. `OpenCV 5.x : Kumiko attend la 4.x`** — moteur `kumiko`.
`HoughLinesP` a changé de forme de retour en OpenCV 5 (`(N, 4)` au lieu de `(N, 1, 4)`)
et Kumiko indexe `dline[0][0]`. Le module s'importe parfaitement ; c'est la passe 1 qui
renvoie 500. `requirements.lock` épingle **les deux** paquets OpenCV en 4.13 pour cette
raison — `opencv-python-headless` ET `opencv-python`, que `ultralytics` tire en
transitif. Si la panne revient, c'est qu'une installation en a désépinglé un :
`pip list | grep -i opencv`.

**3. `OSError: [E050] Can't find model 'fr_core_news_sm'`** — moteur `nlp`.
Le modèle spaCy n'est pas un paquet ordinaire, il se télécharge :

```bash
docker exec bd-app python -m spacy download fr_core_news_sm
docker compose restart app
```

C'est la plus discrète des trois, parce qu'elle est **silencieuse à l'usage** : la
couche NLP est conçue pour dégrader proprement, donc rien ne casse. La table `tokens`
reste simplement vide, la recherche perd les lemmes, et l'Exploration comme la relecture
grammaticale n'ont plus rien à montrer — quatre chantiers livrés meurent sans un message
d'erreur. Le nom du modèle se configure (`BD_SPACY_MODEL`) : si vous en avez changé,
c'est CELUI-LÀ qu'il faut télécharger.

### L'empêcher d'arriver jusqu'ici

Le build refuse une image dont un moteur exigé ne s'importe pas :

```dockerfile
RUN python tools/verifier_moteurs.py --exiger kumiko,bulles,ocr,nlp
```

Ce contrôle ne fait pas double emploi avec la suite de tests, il couvre ce qu'elle ne
peut pas couvrir : mesuré sur une image privée de son modèle spaCy, **451 tests, zéro
échec**. « Moteur absent » est un état que les tests sont écrits pour accepter — correct
en développement local, inacceptable pour un artefact livré. Un contrat d'IMAGE dit
autre chose qu'un contrat de test : non pas « le code se comporte bien quand un moteur
manque », mais « cet artefact-ci DOIT porter ces moteurs-là ».

## 9. Ce que cette pile corrige (cf. docs/hebergement-securite.md)

- 🔴 Exfiltration non authentifiée (`/api/sauvegarde`, `/derivatives`) → **gatée**.
- 🟠 OOM upload → **plafond `request_body` 200 Mo** dans Caddy (penser à
  compléter par `MAX_IMAGE_PIXELS` côté code).
- 🔴 SSRF ShareDocs → **corrigée côté code**, et non par le proxy qui ne pouvait rien
  y faire : allowlist d'hôte (`BD_SHAREDOCS_ALLOWED_HOSTS`, défaut
  `sharedocs.huma-num.fr`), refus des IP privées, `follow_redirects=False`. La garde
  vaut pour TOUTES les sessions, y compris personnelles (SHARE-1).

## 10. Limites connues / à garder en tête

- **1 seul worker uvicorn** (état en mémoire) → ne pas scaler horizontalement
  l'app ; la 2FA/proxy, eux, encaissent la charge.
- L'app **attribue** le travail (journal de provenance A3) et **autorise** par
  collection (AUTH-2/AUTH-3) : `Remote-User` et `Remote-Groups` sont lus à chaque
  requête, jamais stockés. Ces lignes annonçaient l'inverse — elles dataient d'avant.
  Conséquence à connaître : sans `BD_AUTH_PROXY` l'app ne CROIT pas les en-têtes et
  tout reste anonyme ; avec le drapeau mais sans en-tête d'identité, la portée est
  VIDE et l'app paraît vide pour tout le monde (fermeture par défaut). Le bandeau qui
  l'explique distingue les trois pannes possibles.
- Test local sans domaine : possible en faisant écouter Caddy en HTTP simple,
  mais la 2FA/cookies se valident mieux directement sur le VPS avec le vrai domaine.
