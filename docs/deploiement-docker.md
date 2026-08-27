# Déploiement sur VPS — Docker Compose + authentification (Authelia)

Guide pas à pas, pensé pour quelqu'un qui débute sur Docker. La pile fournit :
**plusieurs comptes**, **déconnexion propre**, **2FA**, **HTTPS automatique**, et
gate **tout** l'accès (y compris images et sauvegarde) sans modifier le code de
l'app. Architecture retenue : *portail d'accès sur corpus partagé* (tous les
comptes voient le même corpus).

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

## 8. Ce que cette pile corrige (cf. docs/hebergement-securite.md)

- 🔴 Exfiltration non authentifiée (`/api/sauvegarde`, `/derivatives`) → **gatée**.
- 🟠 OOM upload → **plafond `request_body` 200 Mo** dans Caddy (penser à
  compléter par `MAX_IMAGE_PIXELS` côté code).
- 🔴 SSRF ShareDocs → **non couvert par le proxy** : reste à corriger côté code
  (allowlist d'hôte, refus des IP privées, `follow_redirects=False`).

## 9. Limites connues / à garder en tête

- **1 seul worker uvicorn** (état en mémoire) → ne pas scaler horizontalement
  l'app ; la 2FA/proxy, eux, encaissent la charge.
- Authelia connaît l'utilisateur (`Remote-User`), **mais l'app n'attribue pas
  encore le travail à un auteur** (corpus partagé). Si un jour tu veux de la
  propriété par utilisateur/des rôles, ce sera un chantier côté modèle de données.
- Test local sans domaine : possible en faisant écouter Caddy en HTTP simple,
  mais la 2FA/cookies se valident mieux directement sur le VPS avec le vrai domaine.
