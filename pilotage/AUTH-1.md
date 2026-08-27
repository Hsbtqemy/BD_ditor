---
chantier: AUTH-1
statut: à venir
---

# AUTH-1 — faire entrer l'identité dans l'application

**Point de départ** — le proxy transmet déjà quatre en-têtes d'identité ; l'application
n'en lit qu'un seul, et n'a aucune notion d'utilisateur en base.

## Reste

### Lire ce qui arrive déjà
- [ ] `Remote-Groups` est lu à côté de `Remote-User` (`main.py:2857`) et exposé par `GET /api/moi` : Caddy le transmet depuis `deploy/Caddyfile:26`, l'application le jette aujourd'hui
- [ ] `Remote-Name` et `Remote-Email` sont lus ou explicitement écartés par écrit, pas ignorés par omission

### Une identité en base, sans second système d'auth
- [ ] Une table `utilisateur` existe, dont la clé est le login Authelia, et une ligne est créée **à la première requête vue** — aucun formulaire d'inscription, aucun mot de passe en base : Authelia reste seul détenteur des secrets
- [ ] Les groupes reçus sont reflétés à chaque requête, de sorte qu'un changement dans `users_database.yml` prend effet sans intervention en base
- [ ] Le mode mono-poste local, sans proxy et donc sans en-tête, continue de fonctionner exactement comme aujourd'hui (agent NULL, acte anonyme)

### Ce que l'identité débloque immédiatement
- [ ] Le verrou de planche porte QUI l'a posé (`main.py:402` ne stocke qu'un booléen sans propriétaire) et l'affiche

## Contexte

**C'est la fiche la moins chère du lot et elle débloque tout le reste** : sans notion
d'utilisateur en base, ni AUTH-2 (autorisation), ni AUTH-3 (espaces), ni INFRA-3
(identifiants ShareDocs par personne) ne peuvent s'écrire.

La doctrine du dépôt reste intacte : **pas d'authentification dans le code**. Authelia
authentifie, l'application se contente de croire l'en-tête que le proxy pose — ce qu'elle
fait déjà depuis INFRA-2. On n'ajoute pas un système de comptes, on branche celui qui
existe : `deploy/authelia/users_database.yml` porte déjà un compte `chercheur` dans un
groupe `annotateurs`, et Authelia est en `default_policy: deny` avec 2FA.

Conséquence de sûreté à ne pas manquer : ces en-têtes ne sont dignes de confiance **que**
derrière le proxy. Exposer l'application directement rendrait `Remote-User` falsifiable
par n'importe qui. C'est vrai depuis INFRA-2 et ça le reste — à écrire noir sur blanc au
moment du déploiement.
