---
chantier: INFRA-8
statut: interrompu
---

# INFRA-8 — l'enrôlement 2FA passe par un fichier sur le serveur

**Arrêté sur** — 2026-09-06, `cee43ec` : deux cases d'hygiène fermées, et **le
durcissement a cassé un outil** — le fichier des comptes a deux lecteurs qui n'ont pas les
mêmes droits, et je n'en avais considéré qu'un. Le dossier, lui, était redevenu
`root:root` : le piège du `git pull` était réarmé et dormait. Réparé et éprouvé. Restent
six cases, dont les deux qui comptent — le parcours d'un compte neuf, et le remplacement
d'un appareil TOTP perdu.

**État antérieur — 2026-09-05, `4b6761d` : la bascule est FAITE et le courriel arrive**.
Relais Infomaniak, dont le SPF du domaine autorisait déjà le relais ; boîte d'expédition
PARTAGÉE avec l'autre site du serveur, une adresse dédiée étant payante — c'est cette
contrainte qui a fait désactiver le contrôle SMTP au démarrage, et la soirée a montré que
c'était le bon arbitrage. Reste à éprouver le repli, et les adresses des futurs comptes.
`SMTP_ADRESSE` tranche depuis `.env` — renseignée, le courriel ; vide, le fichier —, donc
le repli ne se reconstruit pas. Reste l'instance : quel relais, quelles adresses, et
l'éprouver pour de bon.

## Reste

### Le mécanisme
- [x] La bascule se décide depuis `.env` SEUL, dans les deux sens : aucun fichier versionné à éditer pour l'activer, aucun à restaurer pour revenir en arrière
- [x] `verifier_deploiement.py --config` refuse une configuration SMTP PARTIELLE — éprouvé dans ses quatre cas (absent, incomplet, sans schéma, complet) et non supposé bon. C'est le seul cas où l'avertissement se justifie : vide est légitime pour un référent, jamais pour un SMTP à moitié écrit
- [x] Une panne de courriel ne peut plus fermer l'atelier : `disable_startup_check` est posé, et l'arbitrage est écrit — le contrôle au boot vérifie la connexion et jamais la remise, donc un envoi d'essai prouve strictement plus, tandis qu'il faisait dépendre l'accès de TOUT LE MONDE d'un serveur de courriel. Contrepartie assumée : un SMTP cassé devient SILENCIEUX, et le diagnostic passe par `docker compose logs authelia`
- [x] `jwt_lifespan` passe de 5 à 15 minutes : le délai de remise d'un courriel s'ajoute à celui de la personne qui relève sa boîte, et un lien expiré ressemble à une panne plutôt qu'à un retard

### La bascule
- [x] Le compte `chercheur` porte une adresse RÉELLE — le gabarit posait `chercheur@example.fr`, vers quoi un notifier SMTP aurait expédié dans le vide sans rien dire
- [x] Le notifier bascule sur SMTP, ses identifiants dans `deploy/.env` et non dans un fichier versionné, comme les trois secrets d'Authelia
- [x] **Le courriel part et arrive** : « Mot de passe oublié ? » sur le portail, message reçu. Il a fallu un mot de passe d'APPLICATION Infomaniak — le mot de passe ordinaire de la boîte est refusé pour du SMTP externe, `535 5.7.0 Invalid login or password`
- [ ] Un compte neuf reçoit son lien d'enrôlement 2FA PAR COURRIEL et va au bout sans intervention sur le serveur — vérifié pour la réinitialisation, pas encore pour l'enrôlement d'un compte qui n'existe pas encore
- [ ] Un appareil TOTP perdu se remplace sans SSH : c'est le seul recours quand le second facteur disparaît, et le chemin n'a pas été parcouru

### La conséquence qu'on n'attend pas
- [ ] Des adresses RÉELLES ne changent rien à ce que les artefacts publient : rejouer `tests/test_sorties_identite.py` après la bascule. Le courriel devient une donnée personnelle là où le gabarit n'en était pas une, et il entre dans la base par `Remote-Email` → `utilisateur`, donc dans toute sauvegarde

### Ce que la bascule a laissé ouvert
- [ ] Le mot de passe d'application est nommé `bdediteur` chez l'hébergeur, donc révocable seul, sans toucher à l'autre site qui partage la boîte
- [x] `deploy/authelia/users_database.yml` n'est plus en `664` : il porte un hash de mot de passe et reste lisible par tout compte de la machine, quand `.env` est en `600`. Deux fichiers de secrets, deux traitements, et rien ne l'avait jamais signalé. **Fait le 2026-09-06 — et le `chmod` seul a cassé un outil** (ci-dessous) : le mode final est `600 ubuntu:ubuntu`, pas `600 root:root`
- [x] Le dossier `deploy/authelia/` appartient de nouveau à `ubuntu` — et il ne l'était PLUS le 2026-09-06, `root:root` en 775, le piège du `pull` réarmé sans que rien ne le dise. Réparé, et **prouvé par une réécriture réelle** (`git checkout --` sur un fichier suivi de ce dossier), pas par un raisonnement sur les permissions. L'autre moitié est **observée** depuis le 2026-09-06 08:56 : l'enrôlement TOTP du premier compte d'essai a écrit dans `db.sqlite3`, qui appartient toujours à `root` dans un dossier appartenant à `ubuntu`. Ce n'est plus le raisonnement « root ignore les permissions », c'est un horodatage

### Ne pas fermer l'instance en croyant régler les notifications
- [x] `docker compose exec authelia authelia validate-config --config /config/configuration.yml` passe AVANT tout redémarrage : le contrôle de connexion est désactivé, mais une configuration structurellement invalide — `sender` manquant — empêche toujours Authelia de démarrer. **Et il NE LIT PAS le fichier des comptes**, mesuré le 2026-09-06 en y glissant une tabulation illégale : « successfully », code 0. Cette case, telle qu'elle était écrite, laissait croire à une garde avant redémarrage qui ne couvre pas ce qu'on modifie le plus souvent
- [x] Le fichier des COMPTES a son propre contrôle avant redémarrage, puisque `validate-config` l'ignore : `python3 -c "import yaml; yaml.safe_load(open('users_database.yml'))"`, PyYAML étant déjà présent sur Ubuntu. Éprouvé dans les DEUX sens le 2026-09-06 — il accepte le fichier correct et refuse une copie contenant une tabulation. Écrit dans `docs/exploitation.md`, avec la copie de sauvegarde qui doit le précéder
- [ ] Le repli est éprouvé pour de vrai, pas seulement écrit : vider `SMTP_ADRESSE`, redémarrer, et retrouver une instance qui laisse entrer

## Le parcours d'un compte neuf, emprunté pour de vrai — 2026-09-06

Un compte `stagiaire` a été créé, sans droit sur aucune collection, avec une adresse en
sous-adressage Gmail (`+stagiaire`) — distincte pour Authelia, livrée dans la même boîte,
sans avoir à payer une adresse de plus chez l'hébergeur.

**Ce qui a marché du premier coup.** Le courriel d'enrôlement part et arrive. Le mot de
passe est accepté (`requires 2FA, cannot be redirected yet`). L'appareil TOTP s'enregistre.
Et le bandeau de portée vide dit exactement ce qu'AUTH-1 lui demandait : *« Groupes reçus :
stagiaires. Aucun n'a reçu d'accès sur une collection — il n'y a donc rien de cassé,
seulement un accès à demander. »* Le troisième cas, celui qui ne se répare pas côté proxy,
distingué en conditions réelles pour la première fois.

**Ce qui a bloqué, et personne ne l'avait conçu.** Après l'enrôlement, le portail propose
une CLÉ DE SÉCURITÉ et affiche « Enregistrez votre premier appareil ». Le message est exact
— aucun WebAuthn n'est enregistré — et parfaitement trompeur pour qui vient de terminer une
inscription TOTP : il se lit comme « rien n'est enregistré ». Il a fallu lire les journaux
d'Authelia pour comprendre, c'est-à-dire exactement l'« intervention sur le serveur » que
cette case interdit. `default_2fa_method: 'totp'` n'était pas déclaré.

**Le bandeau ne disait pas QUI, et c'est réparé le jour même.** Il renvoyait vers « un
administrateur de l'instance », sans nom. Le mécanisme d'AUTH-4 était pourtant complet de
bout en bout — `config.py` lit l'environnement, Compose le transmet, `theme.js` rend la
ligne — mais `BD_REFERENT_NOM` et `BD_REFERENT_CONTACT` n'avaient jamais été posés dans
`deploy/.env`. **Une fonctionnalité livrée depuis des jours, jamais configurée**, sur
l'écran qu'un arrivant voit en premier. La ligne apparaît désormais, avec sa réserve :
« l'application ne peut pas vérifier qu'il fait toujours partie de l'équipe ».

`.env.example` l'annonçait déjà — « cela devient un cul-de-sac dès le deuxième compte ».
L'oubli n'était donc pas documentaire mais opérationnel : rien ne le signalait **au moment
où c'est devenu vrai**. `verifier_deploiement.py` le dit maintenant, et seulement quand la
condition est remplie — au moins deux comptes, aucun référent. Volontairement NON
bloquant : `deployer.sh` appelle ce contrôle avant chaque mise en service, et refuser un
déploiement pour un nom manquant serait disproportionné quand c'est justement le
déploiement qui permet de le poser. Un test verrouille cette propriété-là, pas
l'avertissement.

## Le durcissement a cassé un outil — 2026-09-06

`users_database.yml` était bien en `664`, `root:root`. Le passer en `600` a fermé
l'exposition et **cassé `verifier_deploiement.py`**, qui s'est écrasé sur une
`PermissionError` en pleine trace Python — donc avant tous les contrôles suivants, et
avant le déploiement.

La cause tient en une phrase : **ce fichier a deux lecteurs, et ils n'ont pas les mêmes
droits.** Authelia le lit parce que son conteneur tourne en root ; le script de contrôle,
non — il s'exécute sous le compte de l'opérateur. Le raisonnement qui a mené au `chmod`
n'avait considéré que le premier.

Deux réparations, et elles ne se remplacent pas.

Le mode final est **`600 ubuntu:ubuntu`** et non `600 root:root` : la propriété de
sécurité est la même — illisible aux autres comptes de la machine — et les deux lecteurs
retrouvent leur accès. `chown` plutôt que de relâcher le `chmod`.

Et le contrôle DIT désormais qu'il n'a pas pu lire, au lieu de tomber (`caf4baa`). Un
durcissement légitime ne doit pas ressembler à une panne, ni se comporter en interrupteur
placé en amont des autres gardes — c'est la famille qu'ARCH-2 a nommée avec `openpyxl` et
que QA-6 a retrouvée avec le modèle spaCy. Un test de non-régression éprouve les trois
branches par substitution de `read_text` ; il se skippe dans l'image, `deploy/` étant
exclu du contexte de build, et son message le dit — ce skip n'est pas une couverture.

**Le dossier, lui, était redevenu `root:root`.** Le `chown` du 2026-09-05 n'a pas tenu, ou
n'a jamais été appliqué ; le journal ne permet pas de trancher, et peu importe : ce qui
compte est qu'il l'était le 6, donc que le piège du `git pull` était réarmé et dormait,
faute d'un commit touchant ce dossier depuis. Réparé, puis ÉPROUVÉ — `git checkout --` sur
un fichier suivi de ce dossier réécrit de nouveau. Le premier essai que j'avais proposé,
un `touch` suivi d'un `checkout`, ne prouvait rien : `touch` ne change que la date, git
compare le contenu, le trouve identique et ne réécrit pas.

## La bascule réelle — 2026-09-05

Six pannes en une soirée. Aucune n'était celle qu'on croyait, et **la première a rendu
toutes les autres illisibles**. Le repli percé n'en est pas une septième : c'est une
conséquence de la deuxième, et c'est précisément ce qui le rendait inutilisable.

**Le code n'était jamais arrivé sur la machine.** `deploy/authelia/` appartenait à `root`,
si bien que `git pull` ne pouvait pas remplacer `configuration.yml` : il mettait à jour
tous les autres fichiers, butait sur celui-là, et **abandonnait sans déplacer `HEAD`**.
L'arbre de travail portait donc le contenu neuf pendant que la référence restait neuf
commits en arrière, et les fiches nouvelles apparaissaient « non suivies ». L'erreur
tenait en une ligne — `unable to unlink old … Permission denied` — noyée dans le
défilement d'un `pull`. Tout ce qui a suivi consistait à chercher pourquoi une bascule ne
marchait pas alors que son code n'était pas là. Correctif : rendre le DOSSIER écrivable,
pas les fichiers — supprimer un fichier demande le droit d'écriture sur le répertoire, et
les secrets gardent leur propriétaire.

**Une chose configurée à deux endroits ferme l'instance.** Le gabarit posait `smtp` ou
`filesystem` selon `SMTP_ADRESSE`, mais le compose passait
`AUTHELIA_NOTIFIER_SMTP_PASSWORD` inconditionnellement — or cette variable instancie le
notifier SMTP à elle seule. Résultat : `filesystem` par le gabarit ET `smtp` par
l'environnement, Authelia refuse les deux, boucle de redémarrage, plus personne n'entre.
**Et le repli avait le même angle mort**, ne retirant que l'adresse : il ne pouvait pas
réparer ce qu'il avait lui-même laissé passer. Les quatre valeurs passent désormais par
le gabarit, mot de passe compris.

**`docker compose restart` ne relit pas `.env`.** Il relance le conteneur existant avec
l'environnement de sa création. La pile redémarre sans erreur, sans SMTP, et l'on cherche
la panne chez le fournisseur de courriel. C'est `up -d` qui recrée — et `up -d` seul ne
suffit pas toujours : quand Compose ne détecte aucun changement, il répond `Running` et ne
recrée rien, d'où `--force-recreate` et la comparaison des empreintes MD5 de part et
d'autre pour vérifier que le conteneur a bien la valeur du fichier.

**L'instrument validait l'ancien état.** `docker compose exec authelia authelia
validate-config` s'exécute dans le conteneur EN COURS, dont l'environnement précède la
modification : il rendait « configuration valide » sur la configuration d'avant. C'est
`run --rm` qu'il faut, un conteneur jetable qui lit le `.env` du jour sans toucher à
l'instance qui sert. Le contrôle écrit pour éviter la panne la reproduisait.

**Un mot de passe a fini à la racine d'un dépôt public.** Une commande destinée à
`deploy/.env` a été lancée depuis `~/BD_ditor` : les identifiants SMTP se sont écrits dans
`./.env`, que `.gitignore` ne couvrait pas — il n'ignorait qu'un CHEMIN, `deploy/.env`.
Rien n'a été commité, le fichier était encore `??`, mais un `git add -A` suffisait. Et
l'erreur ne s'est pas manifestée comme une fuite : elle s'est manifestée comme une panne
de courriel. Le motif est désormais nu, donc valable à toute profondeur, et
`test_regressions` l'épingle.

**Enfin, la panne qu'on attendait**, et la seule : `535 5.7.0 Invalid login or password`.
Infomaniak refuse le mot de passe ordinaire d'une boîte pour du SMTP externe et exige un
mot de passe d'APPLICATION. Elle est arrivée en dernier, une fois les quatre autres
levées, et elle s'est lue en une ligne de journal.

**L'arbitrage du contrôle au démarrage a payé le soir même.** Ce `535` serait survenu au
boot d'Authelia : avec `disable_startup_check` à sa valeur par défaut, il aurait fermé
l'atelier à tout le monde pour un mot de passe de messagerie. Le conteneur est resté
`healthy`, le site accessible, et seul l'envoi a échoué — exactement la forme de panne
qu'on avait choisie.

## Contexte

Le notifier `filesystem` était le bon choix pour démarrer : aucun compte mail requis, aucun
réglage. Il a tenu exactement le temps d'un seul utilisateur.

Pour chaque nouvelle personne, il faut ouvrir une session SSH, lire
`/config/notification.txt`, en extraire la bonne URL — le fichier contient AUSSI un lien de
révocation, et se tromper est facile, c'est arrivé au premier essai — puis la transmettre
par un canal quelconque. Le lien expire en quelques minutes, donc l'opération se fait en
présence de la personne. Ce n'est pas délégable, et cela ne tient pas à cinq stagiaires.

**La boîte d'expédition est partagée, et ce n'est pas un choix de confort** : créer une
adresse dédiée est payant chez l'hébergeur. `edito.info@edito-revue.fr` sert donc aussi à
l'autre site du serveur, ce qui crée un couplage qu'on ne peut pas supprimer — le jour où
son mot de passe change pour une raison étrangère à ce projet, les courriels cessent de
partir. On ne peut pas empêcher la panne ; on a supprimé sa forme GRAVE, qui était un
redémarrage refusé des mois plus tard, pour une cause invisible et située ailleurs.

**Ce qui rend la bascule moins anodine qu'elle n'en a l'air** : aujourd'hui, aucune adresse
réelle n'existe nulle part dans la chaîne. Après, il y en a une par compte, elle transite
par `Remote-Email`, elle est écrite dans `utilisateur` (v22) et elle part dans chaque
sauvegarde. AUTH-5 a précisément un cliquet pour ça — il sème une sentinelle de courriel et
balaie 61 surfaces ; il a été écrit parce que l'énumération à la main avait échoué quatre
fois. C'est le moment de le rejouer, pas de lui faire confiance sur parole.
