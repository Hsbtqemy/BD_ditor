---
chantier: INFRA-7
statut: interrompu
---

# INFRA-7 — la session est trop courte pour du travail d'annotation

**Arrêté sur** — 2026-09-15, `cac2a4b` : le portail atteint sans destination est TRANCHÉ — on
documente le geste (partir de l'application, jamais du portail) et le lien de déconnexion
porte désormais sa cible `rd`. **La déconnexion est mesurée le jour même sur la recette**, après
recréation de son seul conteneur `app` : elle ramène à l'application, au mot de passe seul.
Reste ouverte la mesure du « Mot de passe oublié ? », dans la zone « Le portail sans
destination ».

**État antérieur** — 2026-09-10 : la zone de nomenclature est tranchée — cette fiche GARDE `INFRA-7`,
et le contrôle de déploiement part sous `INFRA-12`, qui reçoit sa première fiche. Le dernier
commit de code reste `0914094` (2026-09-07), la durée de session n'ayant pas rouvert depuis.

**État antérieur** — 2026-09-07, `0914094` : **cette fiche a été DÉPASSÉE par les faits, et elle ne le
disait pas.** Elle annonce « rien n'est écrit » et cite `expiration: 1 hour` /
`inactivity: 15 minutes`. Les valeurs réelles sont `12 hours` et `1 hour` depuis le
2026-09-06, relevées à la demande de l'équipe (« 15 min, c'est trop peu ; minimum 30 min,
voire 1 h »), avec leur raison écrite dans `authelia/configuration.yml`. La moitié
« Décider » était donc faite pendant que la fiche la déclarait à venir.

**Trouvée en relisant le tableau de bord, pas en travaillant dessus** — et c'est le seul
mode de découverte qui existe pour ce défaut. `npm run verifier` contrôle la STRUCTURE
d'une fiche, jamais si ses affirmations sont encore vraies ; il le dit lui-même. Une fiche
qui décrit un problème résolu est pire qu'inutile : elle fait chercher une panne.

**Et elle portait DEUX références mortes**, ce qui est la moitié mécaniquement vérifiable
d'une fiche. Le bloc YAML de son Contexte citait des valeurs remplacées ; sa dernière case
visait « la ligne `# mets 'one_factor' si tu ne veux PAS imposer la 2FA` » de
`docs/deploiement-docker.md`, qui n'existe plus nulle part dans le dépôt — le seul endroit
où cette phrase subsiste était cette case.

**Point de départ** — 2026-09-05, à l'annonce de comptes stagiaires. Le constat venait de
la configuration livrée par INFRA-1, relue et non éprouvée.

## Reste

### Mesurer avant de changer — et les valeurs ont changé AVANT la mesure
- [ ] Ce que `inactivity: 1 hour` fait sur une session ORDINAIRE : connexion, une heure sans toucher l'onglet, retour — le portail redemande-t-il mot de passe ET second facteur, ou rien ? La case citait `15 minutes`, valeur remplacée le 2026-09-06 ; la mesure reste à faire, sur les valeurs qui tournent
- [ ] Ce que la case « se souvenir de moi » change vraiment : la même attente, case cochée à la connexion. La session survit-elle à l'inactivité, ou seulement jusqu'à `expiration` ? C'est la question qui décide si `remember_me: 1 month` rend les deux autres réglages sans objet
- [ ] Ce qu'une expiration fait à un LOT ML en cours : un lot lancé depuis la Bibliothèque tourne dans un thread serveur, donc l'expiration ne devrait pas l'interrompre — à vérifier, parce que « ne devrait pas » n'est pas une mesure
- [ ] La documentation d'Authelia ne dit pas si `expiration` est RAFRAÎCHIE à chaque requête ou si elle plafonne depuis la connexion. Le réglage du 2026-09-06 a levé les deux valeurs précisément pour être juste dans les deux cas — l'incertitude est contournée, pas levée, et une mesure la trancherait
- [ ] **Le renvoi après réouverture, quand une cible EXISTE** : être renvoyé par l'application (barre d'adresse en `auth…/?rd=…`), saisir le mot de passe, et dire si l'on revient sur la page demandée ou si l'on reste sur le portail. Le 2026-09-13, les deux connexions de `proprio` portaient bien leur cible dans `authentication_logs` (`request_uri` renseignée) — ce que le renvoi a fait ensuite n'a pas été observé, et l'équipe ne s'en souvenait pas. C'est la moitié qui décide s'il y a un défaut ou seulement un portail ouvert à la main. **Une trace y répond peut-être déjà** (relevée le 2026-09-15) : `INFRA-9` consigne le 2026-09-06 que `stagiaire` « entre au mot de passe SEUL et arrive directement dans l'application », alors que la règle `two_factor` des administrateurs existait — le second facteur était donc activé pour tous, et seule la branche AVEC cible mène là. C'était une première connexion et non une réouverture, d'où la case laissée ouverte ; la mesure de la déconnexion (zone « Le portail sans destination ») la tranche au passage. **La recette l'a montré le 2026-09-15**, sur une connexion qui n'était pas davantage une réouverture (visite anonyme, aucune session expirée au journal) : `stagiaire` réussit son premier facteur à 13:53:40.42 avec `request_uri` = la racine de l'application, et `bd-app` sert `GET /` puis `/api/moi` à 13:53:40.58 — le renvoi a eu lieu. Détail dans la section « Le retour avec destination, vu dans les journaux ». **Et de nouveau après déconnexion**, à 14:13:43 (case « La déconnexion ramène à l'application »). Ce qui manque encore est la seule variante qui donne son nom à la case, l'EXPIRATION : le journal d'Authelia montre à 11:40:40 qu'une session expirée redevient anonyme et reçoit la même redirection avec cible, lien profond compris (`?album=2&planche=123&region=41`), mais l'arrivée sur la page demandée n'y a pas été vue
- [ ] **La réouverture sur un compte de `bd-admins`**, seule question que les comptes `one_factor` ne peuvent pas départager : le portail redemande-t-il le second facteur en plus du mot de passe ? **Bloquée par un préalable** — au 2026-09-13, `totp_configurations` et `webauthn_credentials` sont VIDES sur la pile de recette, donc aucun appareil n'est enrôlé et `admin-bd` n'atteint même pas l'application (règle 1, `two_factor`). Enrôler d'abord, mesurer ensuite

### Le portail sans destination — tranché le 2026-09-15
- [x] **Décider ce qu'on fait du portail atteint SANS cible** — tranché le 2026-09-15 avec l'équipe, `cac2a4b`. **Retenu : documenter le geste ET poser la cible du lien de déconnexion.** Le geste (partir de l'application, jamais du portail) est écrit là où l'arrivant le reçoit — `docs/exploitation.md`, *Ajouter un compte*, où le message d'accueil donne désormais l'adresse de l'application, et `docs/modele-et-droits.md` — et le coût dans `docs/deploiement-docker.md`, *Durée de session, et second facteur*. **Ce qu'on accepte** : le « Mot de passe oublié ? » d'un arrivant mène toujours à « Enregistrez votre premier appareil », et seule la phrase du message l'en détourne. **Écarté** : « retirer la règle 1 », qui ne produisait RIEN telle qu'écrite (section « Décision » ci-dessous), et une redirection Caddy de la racine du portail, qui ne voit aucun des deux chemins réels. **Ce qui rouvre** : une réponse favorable à l'option demandée le 2026-09-14 sous `authelia/authelia#12853` (évaluer `default_redirection_url` pour une session à un facteur) — à regarder à chaque montée d'Authelia, avec les notes de version
- [x] **La déconnexion ramène à l'application** — mesuré le 2026-09-15 sur la recette par l'équipe, et recoupé dans trois journaux. Le SEUL conteneur `bd-app` a été recréé à 14:11 UTC, avec l'accord de l'équipe et la passe `termes-illisibles` finie : `--no-build --no-deps`, même image, `BD_COMMIT` inchangé, Authelia et Caddy intouchés ; son environnement porte `BD_AUTH_LOGOUT_URL=…/logout?rd=https://bd.127-0-0-1.sslip.io/`, que `/api/moi` relaie tel quel. Geste : `proprio` dans l'application, « Déconnexion ». Constaté : retour dans l'application au mot de passe seul, sans écran de second facteur. Recoupé : `bd-authelia` renvoie une visite ANONYME de l'application vers `auth…/?rd=…` à 14:13:22 — la trace que la déconnexion est repassée par l'application ; `authentication_logs` porte le premier facteur de `proprio` à 14:13:43.94 avec `request_uri` = la racine de l'application ; `bd-app` sert `GET /` et `/api/moi` à 14:13:44.05. Une connexion sans destination précède, à 14:13:07, suivie de l'application onze secondes plus tard : cohérente avec une adresse tapée à la main avant le geste, elle n'entre pas dans la mesure. **La contre-épreuve n'a pas été rejouée à part** : elle avait été observée une heure plus tôt sur l'ancien lien — `collectif`, 13:54:00, destination vide, resté sur les réglages du second facteur (section « Le retour avec destination, vu dans les journaux »)
- [ ] **Le « Mot de passe oublié ? » ramène au portail SANS destination** — c'est la prémisse de la phrase écrite dans `docs/exploitation.md`, lue dans le frontend d'Authelia (`ResetPasswordStep2` navigue vers l'accueil sans `rd`) et non mesurée. Pour un compte sans appareil enrôlé : partir de l'application, réinitialiser le mot de passe, puis se connecter sur l'écran où l'on est ramené. Attendu : la barre d'adresse est `auth…/` sans `rd`, et la connexion mène à « Enregistrez votre premier appareil ». Si elle mène à l'application, la phrase est fausse et se retire de la documentation

### Décider — fait le 2026-09-06, par un autre chemin que celui prévu ici
- [x] Les trois valeurs sont tranchées sur un attendu ÉCRIT (« une journée de travail sans ressaisir ») et non sur une intuition de confort : `12 hours` / `1 hour` / `1 month`, avec le raisonnement dans `authelia/configuration.yml` — dont l'argument le plus utile est que `remember_me: 1 month` accordait DÉJÀ un mois à qui coche la case, si bien que les quinze minutes ne bordaient que les prudents
- [x] La dérogation au second facteur est NOMMÉE, et par GROUPE : défaut `one_factor`, `two_factor` maintenu pour `bd-admins` partout et sur les deux routes de sauvegarde (`access_control`, règles 1 et 2). Le sens est délibéré — on renforce par appartenance plutôt que de dispenser, un groupe « dispensé » affaiblissant quelqu'un en silence le jour où on l'y oublie. Tranché sous INFRA-8 / AUTH-6, pas ici
- [x] Le choix est écrit dans `docs/deploiement-docker.md` avec sa raison — section « Durée de session, et second facteur », qui dit aussi CE QU'ON PERD (un mot de passe suffit désormais à atteindre les scans) et pourquoi on l'a accepté : `two_factor` partout poussait vers un compte partagé, dont le coût est invisible et bien pire. La case visait « la ligne `# mets 'one_factor' si tu ne veux PAS imposer la 2FA » qui n'existe plus dans le dépôt — référence morte, remplacée par l'attendu réel

### Le code INFRA-7 désignait DEUX chantiers — tranché le 2026-09-10
- [x] **Le code de cette fiche était employé ailleurs pour un tout autre sujet.** Mesuré le 2026-09-07, et RECOMPTÉ le 2026-09-10 avant de trancher : la fiche annonçait cinq emplois dont `deploy/deployer.sh`, qui n'en portait déjà plus aucun — un renvoi mort dans la case même qui dénonçait le désordre. Les emplois réels au moment de l'arbitrage étaient TROIS, tous du côté déploiement : les docstrings d'ouverture de `tests/test_verifier_deploiement.py` et de `tests/test_version_servie.py`, et le point de départ de `pilotage/INFRA-10.md`. Aucun ne parle de durée de session
- [x] **Ce que ça coûte, et pourquoi ça ne se rattrape pas tout seul** : l'outil date un chantier en cherchant son code dans les sujets de commit. **Et la symétrie est plus exacte que cette fiche ne le disait** — recomptée le 2026-09-10, chaque sujet a EXACTEMENT un commit de code sous `INFRA-7` : `0914094` pour la session (`docs/deploiement-docker.md`, `tests/test_sante.py`) et `87544ba` pour le déploiement. Les deux sont poussés, donc le sujet perdant garde une attribution fausse quoi qu'on choisisse. Ce n'était donc pas un critère de décision, c'était un coût égal des deux côtés — et le voir a évité de choisir pour une raison qui n'existait pas
- [x] **Tranché le 2026-09-10 : la session GARDE `INFRA-7`, le déploiement prend `INFRA-12`** et reçoit `pilotage/INFRA-12.md`, la première fiche qu'il ait jamais eue — `deployer.sh` était né sous `9ee9a98` sans code, `verifier_deploiement.py` sous INFRA-1, c'est-à-dire en passant. Les trois emplois vivants sont repointés dans le même geste. **Ce qui a fait pencher, les coûts étant symétriques** : aucun fichier de fiche n'est renommé, donc aucune référence extérieure au dépôt ne casse, et le sujet qui détenait le code depuis le 2026-09-05 le conserve. **Ce qu'on accepte en échange, par écrit** : `87544ba` continue de dater cette fiche-ci au 2026-09-07 pour du travail qui n'est pas le sien, indéfiniment — consigné dans `INFRA-12` plutôt que laissé silencieux, seule chose qui distingue une erreur portée d'une erreur subie

## La fresque redate cette fiche, et c'est le geste qui la corrigeait — 2026-09-10

**`dbb67d1` porte « INFRA-7 » dans son corps**, à l'endroit où il explique que la durée de
session GARDE ce code. Il touche `tests/`, donc il compte comme un commit de code ; et
l'outil cherche le code d'un chantier dans le SUJET **ou le CORPS**. La fresque montrera
donc INFRA-7 travaillée le 2026-09-10, alors que ce commit ne fait que repointer deux
docstrings vers `INFRA-12`.

**C'est exactement le défaut que cette zone décrivait, reproduit par sa réparation.** Il
n'est pas rattrapable — le commit est poussé, son sujet et son corps ne se réécrivent pas —
et le point d'arrêt ci-dessus n'est pas modifié pour l'absorber : citer `dbb67d1` ici
ferait dire à cette fiche qu'un travail de nomenclature est son dernier commit de code, ce
qui est faux dans l'autre sens.

**La leçon est transposable et ne concerne pas que cette fiche** : dans un commit de CODE,
nommer le code d'un autre chantier — même pour dire qu'on ne travaille pas dessus — le lui
attribue. Le renvoi appartient à la fiche, pas au message de commit.

## `inactivity` observé, sans l'avoir cherché — 2026-09-10

La première case de la première zone demande ce que `inactivity: 1 hour` fait sur une
session ordinaire. **La moitié serveur est mesurée**, relevée dans les journaux d'Authelia
pendant la passe `repli-annuaire` : une session de la veille, présentée le lendemain
matin, rend

    level=info msg="Session for user not marked as remembered has exceeded configured
    session inactivity" username=essai-sansgroupe

suivi d'un renvoi anonyme au portail. Donc : la session est bien expirée CÔTÉ SERVEUR,
Authelia le nomme explicitement, et le compte redevient `<anonymous>`.

**Ce qui n'est pas mesuré, et que cette observation ne peut pas rendre** : ce que le
portail redemande alors — mot de passe seul, ou mot de passe ET second facteur. Le compte
observé est en `one_factor` (règle 4 d'`access_control`), donc il ne peut pas départager.
Il faudrait la même attente sur un compte de `bd-admins`.

La case reste donc ouverte, mais son attendu a rétréci : la mécanique d'expiration est
établie, seul le parcours de réouverture ne l'est pas.

## Le parcours de réouverture, à moitié observé — 2026-09-13

**Signalé pendant la recette de `DROIT-2`**, sur la pile locale : « il n'y a pas de
redirection directe à la connexion 1 facteur. On reste dans auth, avec la proposition de
deux possibilités de connexion, alors qu'on est en réalité connecté. » La moitié CLIENT
que la section précédente déclarait manquante — et elle arrive mêlée à autre chose, ce qui
est précisément la raison de l'écrire ici plutôt que de la retenir.

**Ce que les artefacts établissent.** `authentication_logs` garde la cible attachée à
chaque connexion, et c'est elle qui départage les épisodes du jour : `proprio` à 09:25:43
(`request_uri` = la racine de l'application) et à 15:37:30 (`…/administration`) — cible
présente ; `lectrice` à 16:53:08 — **`request_uri` VIDE**. Les trois connexions ont
réussi. Le portail avait donc, pour `lectrice`, à se rabattre sur `default_redirection_url`
faute de cible, et non à « revenir » quelque part.

**Ce qui l'a retenue là est un SECOND fait, indépendant du renvoi.** `totp_configurations`
et `webauthn_credentials` sont à zéro ligne : personne n'a jamais enrôlé de second facteur
sur cette pile. Authelia 4.39 propose alors l'enregistrement d'un appareil, et les « deux
possibilités » sont l'application d'authentification et la clé de sécurité — non pas deux
façons de SE CONNECTER, mais deux façons de S'ÉQUIPER. Enregistrer un appareil est une
modification des paramètres de sécurité, d'où l'élévation de session et le code à usage
unique écrit dans `notification.txt` à 16:53:24. Ce code n'a pas été mal saisi :
`consumed` est nul et `revoked` porte 16:54:07 — il a été révoqué, jamais consommé.

**L'écran qui dit « connectez-vous » à quelqu'un qui l'est déjà est donc le mode d'échec,
et il n'a rien à voir avec la durée de session.** Les deux se ressemblent au point d'être
rapportés comme un seul défaut ; les séparer a demandé la table, pas le journal.

**Ce que cela rétrécit.** Pour un compte `one_factor`, la réouverture après expiration ne
redemande QUE le mot de passe — mesuré deux fois le 2026-09-13 (`proprio`, 1FA réussie
à 15:37:30, six secondes après l'expiration de 15:37:24). La première case de la première
zone est donc répondue pour ce cas, et ne reste ouverte que pour `bd-admins`, comme la
section précédente l'annonçait. Elle n'est pas cochée : son énoncé couvre les deux
populations.

**Ce que cela NE dit pas, et qu'il ne faut pas déduire** : ce que le renvoi fait quand une
cible existe. Les deux connexions de `proprio` en portaient une ; aucun journal ne consigne
le renvoi qui a suivi, et l'équipe ne s'en souvenait pas au moment de la question. Une
case neuve le demande, plutôt qu'une conclusion tirée du cas de `lectrice`, qui n'avait
pas de cible.

**Pourquoi cela vaut pour la PRODUCTION et pas seulement pour la recette** : les deux
`authelia/configuration.yml` sont identiques, `override.yml` ne touche pas au service
Authelia, et `authelia validate-config` passe sans erreur sur la 4.39.22 qui tourne — donc
aucune clé de la 4.38 n'y est ignorée en silence, et `default_redirection_url` est bien
prise en compte. Ce qui s'observe ici s'observera là-bas.

**Deux pistes écartées en chemin**, écrites pour ne pas les reprendre : les `status_code=408`
qui accompagnent chaque chargement du portail sont le bruit déjà identifié par `INFRA-9`
(§ « Un bruit identifié, pour ne pas le rechercher trois fois ») — connexions persistantes
que Caddy garde en réserve et qu'Authelia récolte ; et le portail se sert en `HTTP 200`
depuis l'intérieur de son conteneur, donc il n'est pas en panne.

## Le portail sans cible : la cause est en amont, et elle est VOULUE — 2026-09-13

La section précédente laissait le cas `proprio` ouvert faute d'observation. Une capture l'a
rendu, le même soir, et la cause est désormais établie **par les sources primaires** et non
par déduction.

**Ce que l'écran montre** : `auth…/2fa/one-time-password`, « Bonjour proprio », et la
phrase « La ressource à laquelle vous essayez d'accéder nécessite une authentification à
deux facteurs », suivie de « Enregistrez votre premier appareil ». Le lien « MÉTHODES »
offre les deux possibilités — mot de passe à usage unique, clé de sécurité.

**Ce que les artefacts établissent, et qui rend la phrase FAUSSE dans ses propres termes** :
la connexion de 17:47:48 a réussi avec une `request_uri` VIDE, et le journal ne porte
aucune décision `forward-auth` depuis 16:53:59. Aucune ressource n'était donc demandée.
L'écran nomme une ressource qui n'existe pas.

**Et ce n'est pas une affaire de groupe** : `proprio` n'apparaît nulle part dans la table
`memberships` de l'annuaire — il n'a AUCUN groupe. Seul `admin-bd` est dans `bd-admins`. La
documentation d'Authelia est explicite sur les deux points qui en découlent : *« Rules are
matched in sequential order. The first entry in the list where all criteria match is the
rule which is applied »* et *« Rules that have subject reliant elements require
authentication to determine if they match »*. Sur une vraie ressource, `proprio` saute donc
la règle 1 et relève de la règle 4, `one_factor`.

**Deux comportements amont se combinent, tous deux ouverts au 2026-09-13.**

- **`authelia/authelia` discussion #7873** — dès qu'une règle exige `two_factor` pour un
  SUJET, fût-il un groupe vide, le second facteur est activé **globalement** sur le portail
  pour tout le monde. **Inexact, corrigé le 2026-09-15** (section « Décision ») : ce n'est pas le SUJET qui déclenche, c'est n'importe quelle règle en `two_factor`. Le mainteneur le qualifie de voulu : *« as soon as any policy exists
  that may require it we enable it globally »*, au nom de la simplicité (*« complexity is
  the enemy of good design and security »*). **Aucun contournement de configuration.** C'est
  notre règle 1 qui le déclenche — et les règles 2 et 3 tout autant, même correction —, et elle n'est pas négociable : elle protège les
  administrateurs.
- **`authelia/authelia` issue #12853** (ouverte le 2026-08-24, branche 4.39.x, étiquetée
  *working-as-intended* / *type/feature*) — atteint à la racine sans `rd`, le portail
  récupère `default_redirection_url` mais ne l'évalue JAMAIS contre le contrôle d'accès
  avant de terminer le premier facteur. Rien ne ramène donc la session vers `one_factor`.

**Conséquence pratique, et elle est gratuite** : on entre en partant de l'APPLICATION et en
se laissant renvoyer — la cible est alors évaluée, la règle 4 s'applique, le mot de passe
suffit. On se bloque en partant du PORTAIL. Les deux connexions de `proprio` du matin
portaient une cible ; celles de 16:53 et 17:47 n'en portaient pas.

**Vaut pour la production**, qui tourne le même fichier et la même version.

**Trois hypothèses ont été écartées en chemin**, écrites pour ne pas les reprendre : une
clé de la 4.38 ignorée par la 4.39 (`validate-config` passe sans erreur) ; `proprio`
membre de `bd-admins` (la table `memberships` le réfute) ; et l'issue #9664, citée à tort
d'après un résumé de recherche — elle traite du cas INVERSE, l'impossibilité d'enrôler
quand aucune règle n'exige `two_factor`. La leçon est la même que celle d'`AUTH-8` :
lire la source, pas ce qu'on en dit.

## Décision — 2026-09-15 : aucune version ne change la donne, et l'une des trois issues n'existait pas

**Les versions d'abord, avant toute proposition.** Cinq sont sorties depuis la 4.39.22, de la
4.39.23 (2026-09-08) à la 4.39.27 (publiée le jour même). Leurs notes ne touchent ni la
redirection ni le premier facteur — et c'est le CODE qui l'établit, pas les notes :
`Handle1FAResponse` (`internal/handlers/response.go`) et `NewAuthorizer`
(`internal/authorization/authorizer.go`) sont identiques à la 4.39.22, à la 4.39.27 et sur
`master`, à un en-tête de licence près. Sous `#12853`, le mainteneur a répondu le 2026-08-24 :
*« This is working as intended. The default redirection URL intentionally only applies once
they've 2FA'd »*, au nom de qui voudrait gérer son compte plutôt qu'être renvoyé. Étiquetée
*type/feature* le 2026-09-10, assignée le 2026-09-13. Le 2026-09-14, un tiers y demande une
option à activer, correctif à l'appui ; seule sa question sur WebAuthn a reçu réponse (renvoi
à `#9664`), pas celle sur l'option.

**L'issue « retirer la règle 1 » ne produisait rien.** La section précédente tenait de `#7873`
que le second facteur s'active dès qu'une règle l'exige « pour un SUJET ». La source dit autre
chose : `NewAuthorizer` pose `mfa = true` dès que la politique par défaut OU n'importe quelle
règle est en `two_factor`, sans regarder le sujet. Or `access_control` en compte trois — les
administrateurs sur l'application, les deux routes de sauvegarde (sans sujet), les
administrateurs sur l'annuaire. Retirer la première laissait les deux autres activer le second
facteur pour tous. La seule forme qui marche est de les retirer TOUTES : plus de second facteur
nulle part, et, `ConfigurationGET` ne publiant ses méthodes que sous ce même interrupteur, plus
même d'enrôlement possible. **C'est la leçon d'`AUTH-8` une fois de plus** : on avait lu la
discussion, pas le code dont elle parle.

**Le portail sans destination n'était pas un accident d'usage : deux chemins y mènent
d'office.** Lus dans le frontend de la 4.39.22, non mesurés :

- **la réinitialisation** — `ResetPasswordStep2` navigue vers l'accueil sans `rd`. Or c'est le
  parcours que `docs/exploitation.md` prescrivait pour une arrivée nombreuse : qui suivait la
  procédure y passait. C'est aussi le parcours que l'auteur de `#12853` décrit dans son second
  commentaire — son rapport initial, lui, reproduit le chemin suivant ;
- **la déconnexion** — `BD_AUTH_LOGOUT_URL` valait `…/logout` nu ; la page de déconnexion lit
  `rd`, et sans lui revient à l'accueil.

Les connexions sans `request_uri` de `lectrice` et de `proprio` le 2026-09-13 sont COMPATIBLES
avec l'un ou l'autre chemin. Rien ne consigne comment elles y sont arrivées, et on ne
l'affirme pas.

**Une redirection Caddy de la racine du portail vers `/?rd=…` a été envisagée, et écartée.**
Les deux navigations ci-dessus sont INTERNES à la page : aucune requête ne part, Caddy ne les
voit jamais. Elle ne servirait que le portail ouvert depuis un favori, au prix d'une règle de
plus sur le seul point d'entrée.

**Ce qui est fait, `cac2a4b`** : la cible `rd` sur le lien de déconnexion — le seul des deux
chemins qui se corrige ici —, le geste écrit là où l'arrivant le reçoit, le coût écrit dans
`deploiement-docker.md`, et une garde, `test_la_deconnexion_renvoie_vers_l_application`,
éprouvée par deux mutations (cible retirée, cible pointée vers le portail). **Rien n'a changé
en service sur la recette** : elle lit le compose du dépôt, donc le lien changera à la
prochaine recréation de son conteneur `app` — pas avant, et pas pendant la passe de QA qui y
tournait.

## Le retour avec destination, vu dans les journaux — 2026-09-15

**Signalé le même jour, pendant la conception : « après le mot de passe, on ne revient pas
dans l'application », pour tous les comptes.** Le signalement a failli faire retirer
`cac2a4b` et bâtir un contournement — une page d'accueil publique ouvrant le portail dans une
fenêtre superposée, qui aurait détecté la session elle-même. Trois journaux de la recette,
lus sans rien toucher ni redémarrer, disent autre chose :

- `authentication_logs` : `stagiaire` réussit son premier facteur à 13:53:40.42 avec
  `request_uri` = `https://bd.127-0-0-1.sslip.io/` ; `collectif` réussit le sien à 13:54:00
  avec une `request_uri` VIDE ;
- `bd-app` sert `GET /`, puis `/api/moi`, les albums et les planches à 13:53:40.58, soit
  150 ms après la connexion de `stagiaire`, sans autre connexion à ce moment-là ;
- `bd-authelia` ne porte aucun « requires 2FA, cannot be redirected yet » après 11:46 —
  celui-là est `admin-bd`, dont la connexion avait une cible et a été traitée comme prévu :
  second facteur demandé, puis entrée à 11:47:19.

**Le renvoi avec destination fonctionne ; ce qui a bloqué `collectif`, c'est une connexion
sans destination.** L'écran `/settings/two-factor-authentication` où il est resté est celui
qu'ouvre le bouton d'enregistrement de l'écran du second facteur (`SecondFactorForm`,
`onRegisterClick`) — pas un mécanisme de plus. Entre les deux connexions, l'application n'a
reçu aucune requête : la forme d'un clic sur « Déconnexion », dont le lien est encore nu sur
la recette, et l'équipe confirme que ses changements de compte passent par là. **Ce n'est
pas un cas isolé** : sur les treize premiers facteurs réussis de la journée, douze sont
arrivés sans destination — la signature des changements de compte d'une passe de QA.

**En attendant la recréation du conteneur `app`**, le geste qui évite le blocage : après
« Déconnexion », ne pas se connecter sur l'écran du portail, taper d'abord l'adresse de
l'application, et se connecter sur l'écran où elle renvoie.

**La leçon vaut dans les deux sens.** Le signalement était exact sur l'écran et faux sur la
cause : l'enchaînement qui y menait ne se voyait pas depuis le navigateur. Et la réponse
« on revient dedans » était juste, mais affirmée d'après la source avant d'être montrée —
c'est ce qui l'a rendue discutable, au point de la retirer à tort une première fois. La
trace a tranché en une lecture ; elle aurait dû précéder les deux affirmations.

## Contexte

Trois lignes gouvernent le confort réel, et ce n'est PAS la politique 2FA. Telles qu'elles
étaient au 2026-09-05, à l'ouverture de cette fiche :

```yaml
expiration: '1 hour'      # → '12 hours' le 2026-09-06
inactivity: '15 minutes'  # → '1 hour'   le 2026-09-06
remember_me: '1 month'    # inchangé
```

La 2FA est demandée une fois par session. C'est `inactivity` qui mordait tous les jours —
l'annotation passe beaucoup de temps à regarder autre chose que l'écran : l'album papier,
un dictionnaire, une note. Quinze minutes est un réglage de banque, pas d'atelier.

**Le danger est d'assouplir du mauvais côté.** Passer en `one_factor` répond à l'agacement
en affaiblissant les comptes les plus nombreux et les moins surveillés ; allonger la
session répond au même agacement sans rien céder. Le second devrait être essayé d'abord —
et si la 2FA doit tomber, que ce soit une décision datée avec son motif, pas la ligne de
moindre résistance offerte par un commentaire du gabarit.

Les ordinateurs multiples ne sont PAS le problème : le secret TOTP appartient au compte et
non à la machine. Un stagiaire enrôle son téléphone une fois et se connecte de partout.
