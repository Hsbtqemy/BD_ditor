---
chantier: INFRA-9
statut: à venir
---

# INFRA-9 — Authelia tourne sur une mineure qui ne reçoit plus de correctifs

**Arrêté sur** — 2026-09-06, `11c82a3` : **l'instance tourne en 4.39.22, `healthy`.**
Le `git pull` est passé du premier coup — le premier depuis trois échecs —, et le dossier
appartient à `ubuntu` APRÈS le démarrage : le correctif `PUID`/`PGID` tient sur la nouvelle
base *chisel*. Aucun avertissement de dépréciation, le journal entier faisant sept lignes.
Reste ce qui se vérifie dans un navigateur, et le repli à rejouer.

**Et la montée laisse une règle durable** : le schéma de stockage a migré de 15 à 28, et
Authelia refuse de tourner contre un schéma plus récent que lui. **L'étiquette n'est plus
un retour arrière** — pour ce service, et pour toutes les montées à venir, le seul chemin
retour est la restauration de la sauvegarde. Ce n'était pas connu avant : aucune des quatre
sources lues le matin ne le disait.

**Point de départ** — 2026-09-06, trouvé de biais. La case la moins chère d'`AUTH-7`
demandait si une version plus récente d'Authelia administrait les comptes ; la réponse est
non, mais la recherche a rendu autre chose : **l'instance est en 4.38.19 quand la dernière
publiée est 4.39.22**, du 2026-09-03. Le compose épingle `authelia/authelia:4.38`, une
étiquette de mineure FLOTTANTE — elle suit fidèlement une branche qui ne bouge plus.

## Reste

### Ce qu'il faut savoir avant de monter
- [x] **Les notes de version de 4.39 sont lues, et AUCUNE rupture ne touche cette configuration** — 2026-09-06. Quatre sources : le billet 4.39, la publication GitHub v4.39.0, le guide de migration et l'entrypoint de l'image. **Le guide de migration n'a aucune entrée pour 4.39** — il s'arrête à 4.38 —, donc aucune clé renommée ni retirée. Le seul changement de comportement NOMMÉ porte sur les revendications des jetons ID d'OpenID Connect, que ce déploiement n'utilise pas : il est en forward-auth. Les dépréciations sont des AVERTISSEMENTS, dont la suppression vise v5.0.0. Rien sur `access_control`, le backend `file`, le filtre `template`, `default_2fa_method`, `disable_startup_check`, `jwt_lifespan` ni le notifier SMTP
- [x] **Les avertissements de dépréciation sont lus : il n'y en a AUCUN** — 2026-09-06, journal entier de sept lignes après la montée. C'était l'occasion gratuite d'apprendre ce que v5.0.0 retirera ; la réponse est que cette configuration n'emploie rien de déprécié. Un « aucun » se consigne comme un autre résultat, sans quoi on rejouera la vérification
- [ ] Le sort des appareils TOTP déjà enrôlés lors d'une montée de mineure est établi, par la documentation ou par un essai. **C'est la même question qu'`AUTH-7` se pose** pour la migration `file` → `ldap` : une seule réponse sert aux deux, et la chercher deux fois serait du gaspillage
- [x] **Le sort de `db.sqlite3` est établi, et la réponse est NON RÉVERSIBLE** — 2026-09-06 : « Storage schema migration from 15 to 28 is being attempted », puis « is complete ». Treize versions de schéma en une seconde. Authelia refuse de tourner contre un schéma plus récent que lui, donc **redescendre l'étiquette ne suffit plus** : le seul chemin retour est la restauration de la sauvegarde. Aucune des quatre sources lues le matin ne le disait — cela ne se mesurait que sur l'instance, et c'est pourquoi la sauvegarde n'était pas une précaution de forme

### Le geste
- [x] **La sauvegarde a précédé la montée** — `~/authelia-avant-4.39-20260906.tgz`, 20 Ko, posée avant tout `pull`. C'est le seul état que `git checkout` ne restaure pas, n'étant pas versionné : les secrets TOTP de tout le monde vivent là. Et depuis la migration de schéma ci-dessus, elle n'est plus une précaution mais **le seul retour arrière qui existe** — à conserver tant qu'on n'a pas éprouvé la 4.39 en usage réel
- [x] **L'étiquette est `authelia/authelia:4.39.22`, version EXACTE**, et la raison est écrite dans le compose lui-même — 2026-09-06, `11c82a3`. La flottante prend bien les correctifs de sa branche, mais elle a laissé l'instance vieillir en silence : `docker compose pull` réussissait et tirait fidèlement la dernière image d'une branche abandonnée. Le coût est assumé : plus rien n'arrive tout seul, pas même un correctif de sécurité, et monter devient un GESTE — le bon régime pour le seul point d'entrée de l'instance, où l'écart doit se voir plutôt que se creuser
- [ ] Après la montée, quatre choses répondent : le portail s'ouvre, un compte se connecte avec son TOTP **déjà enrôlé**, `bd-admins` est toujours élevé en `two_factor`, et un compte sans accès voit le bandeau de portée vide avec ses trois cas distingués (AUTH-1)
- [ ] `verifier_deploiement.py` passe, et notamment son contrôle BLOQUANT de cohérence des groupes admin. S'il tombe, c'est que 4.39 a changé la forme d'`access_control` — et l'apprendre par une garde plutôt que par un administrateur qui s'authentifie plus faiblement en silence est exactement ce pour quoi elle a été écrite

### Ce que la montée ne doit pas emporter
- [ ] Le repli `filesystem` fonctionne ENCORE après la montée : `SMTP_ADRESSE` vidée seule, Authelia démarre, et un « Mot de passe oublié ? » fait grossir `/config/notification.txt`. INFRA-8 l'a éprouvé sur 4.38 ; une montée de mineure est précisément ce qui peut le défaire, et le défaire en silence
- [x] **Le `chown -R ${PUID}:${PGID} /config` se comporte pareil en 4.39** — vérifié le 2026-09-06 sur l'état d'APRÈS le démarrage : `drwxrwxr-x ubuntu ubuntu`. Et la preuve la plus parlante est ailleurs, dans le `git pull` qui l'a précédé : **il est passé du premier coup**, le premier depuis trois échecs consécutifs. Le mécanisme qui les causait vit dans l'image, l'image vient de changer de base, et il se comporte identiquement. C'est le mécanisme qui a coûté trois réparations annulées le 2026-09-05/06, et il vit dans l'image, donc il change avec elle. **La lecture du 2026-09-06 est rassurante sans être une preuve** : l'image change de base (Alpine → *chisel*, « no package manager, some common tools removed »), mais l'entrypoint de `master` fait toujours le `chown` et réclame `/bin/sh`, `id`, `chown` et `su-exec` — s'ils manquaient, il échouerait, donc ils sont là. Reste à le voir vrai plutôt que déduit

## La montée, faite — 2026-09-06

Sept lignes de journal, et trois d'entre elles répondent à des cases.

**« Storage schema migration from 15 to 28 »**, en une seconde. C'est le résultat que la
documentation ne donnait pas, et il change une règle plutôt qu'un fait : Authelia refusant
de tourner contre un schéma plus récent que lui, **redescendre l'étiquette n'est plus un
retour arrière** — ni pour cette montée, ni pour aucune des suivantes. Le seul chemin
retour est la restauration de la sauvegarde, ce qui vaut d'être su AVANT d'en avoir besoin.

**Aucun avertissement de dépréciation.** Le journal entier fait sept lignes. C'était la
seule occasion gratuite d'apprendre ce que v5.0.0 retirera ; la réponse est que cette
configuration n'emploie rien de déprécié, et un « aucun » se consigne comme un autre
résultat — sans quoi on rejouera la vérification en croyant ne pas l'avoir faite.

**Et le `git pull` est passé du premier coup.** C'est la preuve la plus parlante de la
journée, et elle est indirecte : le mécanisme qui a causé trois échecs consécutifs les 5 et
6 vit dans l'entrypoint de l'image, l'image vient de changer de base — Alpine vers
*chisel* —, et le correctif `PUID`/`PGID` tient. Le dossier appartient à `ubuntu` après le
démarrage, pas entre deux.

## Ce que la lecture des notes a écarté, et ce qu'elle a trouvé — 2026-09-06

**Écarté, mesuré plutôt que supposé.** Un piège documenté veut que `PUID`/`PGID` non nuls
empêchent Authelia de lire des secrets montés dans `/run/secrets/`, ce dossier appartenant
à root. Il ne s'applique pas ici : **aucun secret Docker n'est employé**, les trois secrets
d'Authelia et les quatre valeurs SMTP passant tous par l'environnement depuis `.env`.

**Trouvé, et c'était le seul vrai risque.** L'image quitte Alpine pour une base *chisel*
minimale — « there is no package manager, and some unnecessary but common tools have been
removed ». Deux choses de ce déploiement en dépendent. L'entrypoint, d'abord, qui porte le
`chown` sans lequel `deploy/authelia/` repasse à root et casse le `git pull` suivant : il
est intact sur `master` et réclame quatre binaires, qui existent donc dans la nouvelle
base. Et les commandes de runbook qui entrent dans le conteneur, ensuite — inventoriées :
`docker compose run --rm --entrypoint authelia … validate-config` appelle le binaire sans
shell, `deployer.sh` n'entre que dans le conteneur de l'APPLICATION, et le seul
`sh -c` du dépôt (fiche `AUTH-7`, export des TOTP) survit puisque l'entrypoint prouve la
présence de `/bin/sh`.

Le `VOLUME` retiré des images ne change rien ici — tout est en montage lié. Les unités
Systemd non plus : ce déploiement est en Docker.

**Ce qu'il reste d'inconnu tient en une ligne**, et c'est la seule à traiter avec méfiance :
personne ne dit si la migration du stockage propre d'Authelia est réversible. La sauvegarde
de `db.sqlite3` n'est donc pas une précaution de forme.

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
