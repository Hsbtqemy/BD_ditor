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

### Données personnelles — angle mort du projet
- [ ] Le sort des données personnelles d'annotateurs (`utilisateur.nom`, `utilisateur.email`) est tranché et écrit : combien de temps on les garde, ce qu'on en fait, comment on efface quelqu'un qui quitte l'équipe
- [ ] La conséquence sur les sauvegardes est traitée : `VACUUM INTO` (`pipeline/backup.py:28`) emporte la base ENTIÈRE, donc ces emails, et `pipeline/sharedocs.py` sait déposer ce zip sur ShareDocs — donc hors de la machine

## Contexte

**C'est la fiche la moins chère du lot et elle débloque tout le reste** : sans notion
d'utilisateur en base, ni AUTH-2 (autorisation), ni AUTH-3 (espaces), ni INFRA-3
(identifiants ShareDocs par personne) ne peuvent s'écrire.

La doctrine du dépôt reste intacte : **pas d'authentification dans le code**. Authelia
authentifie, l'application se contente de croire l'en-tête que le proxy pose — ce qu'elle
fait déjà depuis INFRA-2. On n'ajoute pas un système de comptes, on branche celui qui
existe : `deploy/authelia/users_database.yml` porte déjà un compte `chercheur` dans un
groupe `annotateurs`, et Authelia est en `default_policy: deny` avec 2FA.

**Angle mort découvert le 2026-08-27 en relisant ce chantier.** Le dépôt documente
minutieusement les droits du CORPUS — `base_legale`, `statut_diffusion`, tiering,
exception TDM — et ne dit **rien**, nulle part, des données personnelles des personnes
qui l'utilisent : aucune occurrence de « données personnelles », « RGPD » ou
« anonymisation » dans `docs/` ni dans `AUDIT.md`. AUTH-1 est le premier chantier à en
stocker (nom, email), et il le fait sans que rien n'encadre cette catégorie. Le volume est
minime et l'équipe petite ; ce n'est pas un blocage. C'est une lacune de doctrine, à
combler pendant qu'elle est petite plutôt qu'après. Recoupe DEPOT-1, qui porte l'autre
moitié de la question juridique.

Vérifié au passage : les exports (records, CSV, IIIF, crosswalk) n'énumèrent pas les
tables et ne laissent fuir aucun email — la seule voie de sortie est la sauvegarde.

Conséquence de sûreté, traitée : ces en-têtes ne sont dignes de confiance **que** derrière
le proxy. C'était vrai depuis INFRA-2 sans être garanti — la docstring affirmait « l'app
n'est jamais exposée en direct », ce qui est une hypothèse sur le déploiement, pas une
propriété du code. `BD_AUTH_PROXY` en fait une propriété du code (`247c145`), et le
compose pose le drapeau. Inoffensif tant que rien n'est autorisé sur cette base ; c'eût
été une escalade de privilège en une ligne de `curl` dès AUTH-2.
