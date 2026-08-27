---
chantier: AUTH-1
statut: interrompu
---

# AUTH-1 — faire entrer l'identité dans l'application

**Arrêté sur** — 2026-08-27, `247c145` : garde de confiance, groupes, miroir
`utilisateur` (v22) et verrou attribué sont livrés et vérifiés dans l'image. Reste
l'exposition dans l'UI.

## Reste

### Lire ce qui arrive déjà
- [x] `Remote-Groups` est lu et exposé par `GET /api/moi` (liste découpée sur les virgules ; `[]` en l'absence d'en-tête, contrat stable pour l'UI)
- [x] `Remote-Name` était déjà lu ; `Remote-Email` l'est désormais et alimente le miroir

### Une identité en base, sans second système d'auth
- [x] Table `utilisateur` (v22), clé = login Authelia, ligne créée à la première visite via `/api/moi` ; aucun secret en base, vérifié par un test qui refuse toute colonne password/hash/token
- [x] Les groupes ne sont PAS stockés : relus à chaque requête, donc un retrait dans `users_database.yml` prend effet immédiatement. Un test refuse toute colonne `groupes`/`role`
- [x] Le mono-poste local reste identique (agent NULL, acte anonyme) — et va plus loin : sans `BD_AUTH_PROXY`, une en-tête FORGÉE est ignorée, vérifié dans l'image

### Ce que l'identité débloque immédiatement
- [x] Le verrou de planche consigne qui l'a posé (`planches.verrou_par`, v22)
- [ ] L'UI **affiche** qui a verrouillé une planche, et le nom lisible plutôt que le login — le miroir `utilisateur` existe pour ça, rien ne s'en sert encore
- [ ] L'UI affiche l'appartenance aux groupes là où c'est utile (aujourd'hui `/api/moi` les renvoie, aucune surface ne les lit)

## Contexte

**C'est la fiche la moins chère du lot et elle débloque tout le reste** : sans notion
d'utilisateur en base, ni AUTH-2 (autorisation), ni AUTH-3 (espaces), ni INFRA-3
(identifiants ShareDocs par personne) ne peuvent s'écrire.

La doctrine du dépôt reste intacte : **pas d'authentification dans le code**. Authelia
authentifie, l'application se contente de croire l'en-tête que le proxy pose — ce qu'elle
fait déjà depuis INFRA-2. On n'ajoute pas un système de comptes, on branche celui qui
existe : `deploy/authelia/users_database.yml` porte déjà un compte `chercheur` dans un
groupe `annotateurs`, et Authelia est en `default_policy: deny` avec 2FA.

Conséquence de sûreté, traitée : ces en-têtes ne sont dignes de confiance **que** derrière
le proxy. C'était vrai depuis INFRA-2 sans être garanti — la docstring affirmait « l'app
n'est jamais exposée en direct », ce qui est une hypothèse sur le déploiement, pas une
propriété du code. `BD_AUTH_PROXY` en fait une propriété du code (`247c145`), et le
compose pose le drapeau. Inoffensif tant que rien n'est autorisé sur cette base ; c'eût
été une escalade de privilège en une ligne de `curl` dès AUTH-2.
