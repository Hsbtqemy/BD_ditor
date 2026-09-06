---
chantier: INFRA-9
statut: à venir
---

# INFRA-9 — Authelia tourne sur une mineure qui ne reçoit plus de correctifs

**Point de départ** — 2026-09-06, trouvé de biais. La case la moins chère d'`AUTH-7`
demandait si une version plus récente d'Authelia administrait les comptes ; la réponse est
non, mais la recherche a rendu autre chose : **l'instance est en 4.38.19 quand la dernière
publiée est 4.39.22**, du 2026-09-03. Le compose épingle `authelia/authelia:4.38`, une
étiquette de mineure FLOTTANTE — elle suit fidèlement une branche qui ne bouge plus.

## Reste

### Ce qu'il faut savoir avant de monter
- [ ] Les notes de version de 4.39 sont lues, et les ruptures qui touchent CETTE configuration sont listées nommément : `access_control` ordonné, backend `file`, `X_AUTHELIA_CONFIG_FILTERS=template`, `default_2fa_method`, `disable_startup_check`, `jwt_lifespan`, `PUID`/`PGID`, notifier SMTP. Une rupture qui ne concerne pas ce déploiement n'a pas à figurer dans la liste — c'est ce qui la rend lisible
- [ ] Le sort des appareils TOTP déjà enrôlés lors d'une montée de mineure est établi, par la documentation ou par un essai. **C'est la même question qu'`AUTH-7` se pose** pour la migration `file` → `ldap` : une seule réponse sert aux deux, et la chercher deux fois serait du gaspillage
- [ ] Le sort de `db.sqlite3` est établi : Authelia migre-t-il son propre stockage au passage, et cette migration est-elle réversible ? Si elle ne l'est pas, le geste change de nature — ce n'est plus « changer une étiquette », c'est une bascule dont le retour arrière passe par une restauration

### Le geste
- [ ] La sauvegarde de `deploy/authelia/` PRÉCÈDE la montée, `db.sqlite3` compris. C'est le seul état que `git checkout` ne restaure pas, n'étant pas versionné — les secrets TOTP de tout le monde vivent là
- [ ] L'étiquette cesse d'être `authelia/authelia:4.38`, et le choix entre mineure flottante et version exacte est écrit avec sa raison. La flottante a laissé l'instance vieillir en silence pendant que le déploiement se croyait à jour ; une version exacte le dirait, au prix d'un geste à faire
- [ ] Après la montée, quatre choses répondent : le portail s'ouvre, un compte se connecte avec son TOTP **déjà enrôlé**, `bd-admins` est toujours élevé en `two_factor`, et un compte sans accès voit le bandeau de portée vide avec ses trois cas distingués (AUTH-1)
- [ ] `verifier_deploiement.py` passe, et notamment son contrôle BLOQUANT de cohérence des groupes admin. S'il tombe, c'est que 4.39 a changé la forme d'`access_control` — et l'apprendre par une garde plutôt que par un administrateur qui s'authentifie plus faiblement en silence est exactement ce pour quoi elle a été écrite

### Ce que la montée ne doit pas emporter
- [ ] Le repli `filesystem` fonctionne ENCORE après la montée : `SMTP_ADRESSE` vidée seule, Authelia démarre, et un « Mot de passe oublié ? » fait grossir `/config/notification.txt`. INFRA-8 l'a éprouvé sur 4.38 ; une montée de mineure est précisément ce qui peut le défaire, et le défaire en silence
- [ ] Le `chown -R ${PUID}:${PGID} /config` de l'entrypoint se comporte pareil en 4.39 — vérifié sur l'état d'APRÈS un démarrage, pas entre deux. C'est le mécanisme qui a coûté trois réparations annulées le 2026-09-05/06, et il vit dans l'image, donc il change avec elle

## Contexte

**La politique de versionnement d'Authelia est explicite, et ses deux moitiés ne disent pas
la même chose.** Les correctifs de bogue vont à la **dernière mineure seulement** : 4.38
n'en reçoit donc plus aucun, et l'étiquette flottante n'y peut rien. Les correctifs de
vulnérabilité couvrent les **trois dernières mineures, sur demande** : 4.38 est encore dans
la fenêtre — 4.39, 4.38, 4.37 — mais « sur demande » n'est pas « publié », et la sortie de
4.41 l'en fera sortir.

Ce n'est donc pas une urgence de sécurité aujourd'hui. C'est une dette qui se paie en
retard : plus on attend, plus la montée franchit de mineures d'un coup, et plus la lecture
des notes de version devient le vrai travail.

**Deux raisons de ne pas laisser dormir.** Ce service est le seul point d'entrée de
l'instance depuis INFRA-1 — personne n'atteint BDéditeur sans passer par lui. Et le
chemin 2 d'`AUTH-7`, ajouter un annuaire, se poserait sur cette version-là : **choisir un
annuaire pour une mineure qu'on va quitter serait le pire ordre.** Cette fiche passe donc
AVANT la décision d'AUTH-7, ou avec elle, jamais après.

**Ce qui a rendu la dette invisible**, et c'est la leçon transposable : une étiquette de
mineure flottante donne toutes les apparences d'un déploiement à jour. `docker compose
pull` réussit, il tire bien la dernière image de la branche, et rien nulle part ne dit que
la branche est abandonnée. Le déploiement ne ment pas — il répond exactement à ce qu'on lui
a demandé, et ce qu'on lui a demandé a vieilli. C'est la même forme que les gardes
d'ARCH-2 qui approuvaient en ne regardant plus que la moitié des routes : pas une panne, un
silence.
