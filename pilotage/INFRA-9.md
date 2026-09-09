---
chantier: INFRA-9
statut: livré
---

# INFRA-9 — Authelia tourne sur une mineure qui ne reçoit plus de correctifs

**Arrêté sur** — 2026-09-09, chantier TERMINÉ par la mesure, **sans commit de code** (le
dernier reste `a0b0927`, qui vit sur `origin/main`) : les trois cases ouvertes sont faites,
et deux d'entre elles ont rapporté autre chose que ce qu'on venait chercher.

`verifier_deploiement.py` passe des deux côtés — **4.39 n'a pas changé la forme
d'`access_control`**, et son contrôle BLOQUANT de cohérence des groupes admin le dit.

Le bandeau de portée vide a été revu sur l'instance, sous un compte jetable créé dans
LLDAP : `<details>` replié, moitié humaine juste, et **le référent d'AUTH-4 s'affiche enfin
avec un nom et un contact réels** — l'oubli du 2026-09-06 est fermé sur l'écran qu'un
arrivant voit en premier. Mais sa ligne technique ACCUSE À TORT, et ce défaut appartient à
AUTH-8, où il est écrit : un compte sans groupe ne reçoit pas `Remote-Groups` vide, il ne le
reçoit pas du tout.

**Le repli `filesystem` survit à la montée, et l'éprouver a corrigé son propre attendu** :
le fichier de notifications a RÉTRÉCI, le notifier écrasant au lieu d'ajouter. Retour
arrière fait dans la foulée et vérifié des DEUX côtés — le courriel repart par SMTP ET le
fichier reste figé, ce qui distingue « le SMTP est revenu » de « les deux notifiers
tournent », la panne du 2026-09-05.

**Ce que cette journée dit d'une montée de mineure**, et c'est la leçon transposable :
aucune des trois cases n'a trouvé ce qu'elle cherchait. La montée n'avait rien cassé — ni
`access_control`, ni la recopie des en-têtes, ni le repli. Ce que la vérification a rapporté,
ce sont deux ATTENDUS faux et un diagnostic d'écran qui accuse à tort, tous trois antérieurs
à la montée. Vérifier après coup ne sert pas seulement à trouver ce que le changement a
défait ; c'est l'occasion où l'on regarde enfin des choses qu'on n'avait jamais regardées.

**État antérieur — 2026-09-06, `a0b0927`** : **`deployer.sh` déployait la politique d'accès
sans jamais l'appliquer.** Authelia lit sa configuration au démarrage du PROCESSUS, et le
script ne relançait que le service `app` : l'arbitrage du second facteur a été poussé à
11:16, tiré à 11:20, et n'a pris effet qu'à 18:58, au premier redémarrage fait pour une
autre raison. Sept heures pendant lesquelles le dépôt et l'instance disaient deux choses
différentes sur la POLITIQUE D'ACCÈS, sans un signal. Le sens était bénin — l'instance
restait plus stricte que voulu ; le même silence tairait un durcissement. Corrigé le jour
même : le script compare `deploy/authelia/` entre les deux commits et redémarre si elle a
changé. **Trouvé en allant vérifier autre chose**, et c'est la seule raison qu'on le sache.

Plus tôt le même jour, `11c82a3` : **l'instance tourne en 4.39.22, `healthy`.**
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
- [x] **Les appareils TOTP déjà enrôlés SURVIVENT à une montée de mineure** — éprouvé le 2026-09-06 par le geste réel, et le contexte rend la preuve forte : le stockage venait de migrer de TREIZE versions de schéma, et le code de `chercheur` a été accepté sans réenrôlement. **C'est la même propriété qu'`AUTH-7` interroge** pour la migration `file` → `ldap` : les appareils vivent dans le stockage propre d'Authelia, indexés par nom d'utilisateur, indépendamment du reste. Une seule mesure, deux cases
- [x] **Le sort de `db.sqlite3` est établi, et la réponse est NON RÉVERSIBLE** — 2026-09-06 : « Storage schema migration from 15 to 28 is being attempted », puis « is complete ». Treize versions de schéma en une seconde. Authelia refuse de tourner contre un schéma plus récent que lui, donc **redescendre l'étiquette ne suffit plus** : le seul chemin retour est la restauration de la sauvegarde. Aucune des quatre sources lues le matin ne le disait — cela ne se mesurait que sur l'instance, et c'est pourquoi la sauvegarde n'était pas une précaution de forme

### Le geste
- [x] **La sauvegarde a précédé la montée** — `~/authelia-avant-4.39-20260906.tgz`, 20 Ko, posée avant tout `pull`. C'est le seul état que `git checkout` ne restaure pas, n'étant pas versionné : les secrets TOTP de tout le monde vivent là. Et depuis la migration de schéma ci-dessus, elle n'est plus une précaution mais **le seul retour arrière qui existe** — à conserver tant qu'on n'a pas éprouvé la 4.39 en usage réel
- [x] **L'étiquette est `authelia/authelia:4.39.22`, version EXACTE**, et la raison est écrite dans le compose lui-même — 2026-09-06, `11c82a3`. La flottante prend bien les correctifs de sa branche, mais elle a laissé l'instance vieillir en silence : `docker compose pull` réussissait et tirait fidèlement la dernière image d'une branche abandonnée. Le coût est assumé : plus rien n'arrive tout seul, pas même un correctif de sécurité, et monter devient un GESTE — le bon régime pour le seul point d'entrée de l'instance, où l'écart doit se voir plutôt que se creuser
- [x] **Après la montée, la politique d'accès se comporte comme écrit** — 2026-09-06, éprouvé sur les DEUX versants, ce qui est le seul moyen de le savoir. `chercheur` (groupe `bd-admins`) se voit demander son second facteur : « https://bd.edito-revue.fr/ requires 2FA », règle 1. `stagiaire` entre au mot de passe SEUL et arrive directement dans l'application : règle 3, `one_factor`. Éprouver un seul des deux n'aurait rien prouvé — un refus universel et une politique juste se ressemblent d'un côté, une ouverture universelle et une politique juste se ressemblent de l'autre
- [x] **Le bandeau de portée vide est revu après la montée, et le revoir a rapporté un défaut** — 2026-09-09. Deux corrections à la case elle-même avant de la lire : les cas sont QUATRE et non trois depuis AUTH-8 (2026-09-07), et `stagiaire` ne pouvait plus servir, ayant reçu des accès entre-temps — la prémisse d'une case vieillit comme le reste. Mesuré sur un compte jetable créé dans LLDAP, sans groupe ni accès. **Ce qui marche** : `<details>` replié comme voulu, moitié humaine juste, et le référent d'AUTH-4 nommé avec un contact réel. **Ce qui ne marche pas** : `entete_groupes: false` pour un compte sans groupe, si bien que la ligne technique annonce « les accès par groupe sont sans effet — à vérifier côté proxy » à quelqu'un dont le proxy va bien. Le défaut est écrit dans AUTH-8 et ne rouvre pas cette fiche
- [x] **`verifier_deploiement.py` passe, contrôle BLOQUANT compris** — 2026-09-09, et il a fallu le lancer DEUX fois : `--url` seul n'exécute que les contrôles réseau, la cohérence des groupes admin vivant dans `controle_config`, donc sous `--config`. Une invocation partielle rendait 0 sans avoir regardé la garde que cette case vise, ce qui est la forme d'ARCH-2 en miniature — un vert qui n'a rien vu. DEHORS : les dix chemins refusés en anonyme, `/static` et `/api/sauvegarde` compris. DEDANS : les quatre moteurs importés pour de bon par la voie profonde. AVANT : `groupes admin  bd-admins — élevés au second facteur des deux côtés`, donc **4.39 n'a pas changé la forme d'`access_control`**. Une ligne à ne pas lire de travers : `ok comptes` porte sur `users_database.yml`, qui ne gouverne plus rien depuis LLDAP — l'instrument approuve un fichier sans effet, et c'est une case ouverte d'AUTH-7

### Ce que la montée ne doit pas emporter
- [x] **Le repli `filesystem` fonctionne ENCORE après la montée, et l'attendu de cette case était FAUX** — 2026-09-09. `SMTP_ADRESSE` vidée seule (les trois autres valeurs laissées : c'est le cas qui avait échoué le 2026-09-05), `validate-config` sur un conteneur JETABLE, puis `up -d --force-recreate` — `healthy`, `Startup complete`, aucun « only one of 'smtp' or 'filesystem' ». **Le geste qui prouve la remise a démenti la case** : `/config/notification.txt` a RÉTRÉCI, 3 492 → 1 918 octets, le notifier `filesystem` ÉCRASANT au lieu d'ajouter. INFRA-8 avait relevé « de 0 à 3 492 » sur un fichier qui partait vide — un cas particulier pris pour une règle, et « le fichier doit avoir grossi » aurait fait conclure à une panne un jour où tout marche. La preuve est le CONTENU : jeton portant `"username":"essai-sansgroupe"`, émis à 21:34:48 UTC contre un `Startup complete` à 21:33:01, durée de vie de 15 minutes — ce qui confirme au passage le `jwt_lifespan` relevé de 5 à 15 par INFRA-8. Retour arrière vérifié des DEUX côtés, courriel reçu ET fichier figé à 1 918 : un fichier immobile seul ne distinguerait pas « le SMTP est revenu » de « rien ne part »
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

## Trouvé de biais, et ce n'est pas d'ici — 2026-09-09

La notification écrite par le repli dit « This email was intended for **.** » — destinataire
VIDE. Ce n'est pas un défaut du repli, et c'est cohérent avec ce que `GET /api/moi` avait
rendu une heure plus tôt : `nom` retombe sur le login pour `essai-sansgroupe` **comme pour
`stagiaire`**, c'est-à-dire pour un compte réel.

Deux causes possibles, non départagées : l'annuaire n'a pas de nom d'affichage pour ces
comptes, ou `Remote-Name` ne parvient pas jusqu'à l'application. C'est la même famille de
question que `Remote-Groups`, et elle se mesure de la même façon — sauf qu'ici l'effet est
visible PARTOUT : tous les écrans montrent un login là où ils devraient montrer un nom.

Écrit ici parce que c'est ici qu'on l'a vu ; le sujet est celui d'**AUTH-7**, qui devrait
lui ouvrir une case. L'y inscrire le jour même aurait été le bon endroit au mauvais moment,
une autre session travaillant ces fiches.

## Un bruit identifié, pour ne pas le rechercher trois fois — 2026-09-06

Le journal de 4.39 porte des lignes qui alarment sans être un défaut :

    level=error msg="Request timeout occurred while handling request from client."
    error="read tcp 172.18.0.4:9091->172.18.0.5:53956: i/o timeout"
    method=GET path=/ status_code=408

`172.18.0.5` est **`bd-caddy`**, vérifié par `docker network inspect` : ce n'est pas un
client externe mais le proxy de la pile. Le motif — connexions ouvertes vers le portail,
jamais complétées, refermées après délai — est celui de connexions PERSISTANTES laissées
inactives que Caddy garde en réserve et qu'Authelia récolte.

**Ce qui est établi** : la source, le chemin, et l'absence d'effet — conteneur `healthy`,
connexions qui passent, occurrences pendant la navigation. **Ce qui ne l'est pas** :
pourquoi cela apparaît maintenant. Le plus probable est que 4.39 journalise en `error` ce
que 4.38 taisait. C'est écrit ici parce qu'un bruit non identifié se recherche à chaque
lecture de journal, et qu'il ressemble à une panne le jour où l'on en cherche une.

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
annuaire pour une mineure qu'on va quitter serait le pire ordre.** Cette fiche devait donc
passer AVANT la décision d'AUTH-7, ou avec elle, jamais après.

**L'ordre a été tenu, et il a servi** : la montée en 4.39.22 est du 2026-09-06, la bascule
vers LLDAP du 2026-09-07. Le bénéfice n'est pas théorique — AUTH-7 a dû vérifier que son
bloc `ldap:`, écrit AVANT la montée, était encore valide en 4.39, et il l'était. Écrit dans
l'autre ordre, cette vérification aurait porté sur une configuration déjà en service.

**Ce qui a rendu la dette invisible**, et c'est la leçon transposable : une étiquette de
mineure flottante donne toutes les apparences d'un déploiement à jour. `docker compose
pull` réussit, il tire bien la dernière image de la branche, et rien nulle part ne dit que
la branche est abandonnée. Le déploiement ne ment pas — il répond exactement à ce qu'on lui
a demandé, et ce qu'on lui a demandé a vieilli. C'est la même forme que les gardes
d'ARCH-2 qui approuvaient en ne regardant plus que la moitié des routes : pas une panne, un
silence.
