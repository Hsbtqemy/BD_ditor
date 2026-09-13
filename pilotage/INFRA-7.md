---
chantier: INFRA-7
statut: interrompu
---

# INFRA-7 — la session est trop courte pour du travail d'annotation

**Arrêté sur** — 2026-09-10 : la zone de nomenclature est tranchée — cette fiche GARDE `INFRA-7`,
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
- [ ] **Le renvoi après réouverture, quand une cible EXISTE** : être renvoyé par l'application (barre d'adresse en `auth…/?rd=…`), saisir le mot de passe, et dire si l'on revient sur la page demandée ou si l'on reste sur le portail. Le 2026-09-13, les deux connexions de `proprio` portaient bien leur cible dans `authentication_logs` (`request_uri` renseignée) — ce que le renvoi a fait ensuite n'a pas été observé, et l'équipe ne s'en souvenait pas. C'est la moitié qui décide s'il y a un défaut ou seulement un portail ouvert à la main
- [ ] **Atteindre le portail SANS cible** — en tapant son adresse au lieu d'être renvoyé — puis se connecter : attendu, le repli `default_redirection_url` mène à l'application. Observé une fois le 2026-09-13 en sens CONTRAIRE, sans l'avoir cherché (section ci-dessous) ; une observation incidente n'est pas une mesure, et celle-ci est confondue avec la proposition d'enrôlement décrite plus bas
- [ ] **La réouverture sur un compte de `bd-admins`**, seule question que les comptes `one_factor` ne peuvent pas départager : le portail redemande-t-il le second facteur en plus du mot de passe ? **Bloquée par un préalable** — au 2026-09-13, `totp_configurations` et `webauthn_credentials` sont VIDES sur la pile de recette, donc aucun appareil n'est enrôlé et `admin-bd` n'atteint même pas l'application (règle 1, `two_factor`). Enrôler d'abord, mesurer ensuite

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
