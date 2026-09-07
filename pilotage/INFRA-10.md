---
chantier: INFRA-10
statut: interrompu
---

# INFRA-10 — déployer se fait à la main, donc quand on y pense

**Arrêté sur** — 2026-09-07, `025b0d9` : **le déployeur comparait la configuration Authelia
depuis le mauvais bout, et rejouait ainsi la panne de sept heures d'INFRA-9 à l'intérieur
de sa propre correction.** Il regardait `$avant..$apres` — ce que le pull venait de ramener
— alors que son étape 2 bis établit dix lignes plus haut que le dépôt et l'image divergent.
Quand le pull ne ramène rien, la comparaison ne voit rien, et Authelia continue de servir
une politique d'accès que le disque a cessé de porter. Corrigé : la référence est
`bd.commit`, le commit que l'image PORTE.

Ce défaut ne devient sérieux qu'ici. Il dormait depuis INFRA-9 parce qu'un déploiement
manuel est regardé par quelqu'un ; sous un timer, plus personne ne lit la ligne « pas de
redémarrage ». **Un mécanisme d'automatisation ne se contente pas de répéter ce qu'on
faisait : il retire le témoin qui rattrapait les erreurs de ce qu'on faisait.**

Et la même prémisse abandonnée — *c'est le pull qui décide*, remplacée par l'étape 2 bis —
avait survécu à deux autres endroits, sans dents mais trompeurs : l'aide de `--forcer`, et
`docs/exploitation.md`, dont la recette de secours À LA MAIN omettait entièrement le
redémarrage d'Authelia. La page qu'on suit quand le script est indisponible décrivait donc
la panne de sept heures comme la procédure normale.

Le mécanisme lui-même n'a pas bougé depuis `e0314b9` — écrit, éprouvé LOCALEMENT
(`deploy/veille-deploiement.sh`, deux unités systemd, douze tests sur deux vrais dépôts
git), **jamais tourné sur le VPS**. C'est la limite à garder en tête en lisant le reste.

**Point de départ** — 2026-09-06. `deployer.sh` fait bien son travail depuis INFRA-7, mais
il faut ouvrir une session SSH et penser à le lancer. La question posée : GitHub pourrait-il
déployer sur poussée de `main` ? La réponse retenue est OUI pour le déclenchement, NON pour
GitHub — le déploiement se TIRE.

**La thèse de cette fiche a reçu sa preuve datée le 2026-09-07, et elle est plus dure que
l'énoncé.** « Déployer se fait quand on y pense » suggère un retard qu'on constate ; ce qui
s'est passé est qu'on ne l'a pas constaté. L'instance servait `305e0bc` pendant que `main`
avait avancé de six commits, dont une fonctionnalité livrée, testée et annoncée — la vue des
comptes d'AUTH-7. Personne n'a rien vu, et il n'y avait rien à voir : aucun écran ne compare
ce qui est servi à ce qui est poussé, donc l'écart n'a pas d'endroit où apparaître. Il n'est
apparu qu'à la première commande qui l'a interrogé, par hasard, en préparant autre chose.

**Le coût n'est donc pas le retard, c'est la CONFIANCE MAL PLACÉE.** Entre le push et la
découverte, on a raisonné — et écrit — comme si l'instance portait le nouveau code : « ce
que l'écran vous montrera ce soir ». Un déploiement manuel oublié ne laisse pas un trou, il
laisse une croyance. C'est le même mode d'échec que celui qu'`ARCH-2` décrit pour les
gardes : le silence se lit comme une approbation.

## Reste

### Poser le mécanisme sur l'instance
- [ ] Le clone du VPS tire en HTTPS (`git -C ~/BD_ditor remote -v`) : le dépôt est public, donc `git fetch` n'a besoin d'aucune clé — mais un clone en SSH exigerait un agent que systemd n'a pas, et la veille échouerait toutes les cinq minutes
- [ ] Les unités sont installées et le timer actif : `systemctl list-timers bd-deploiement.timer` annonce un prochain tir
- [ ] `./deploy/veille-deploiement.sh --simulation` rend « rien à faire » LANCÉ PAR SYSTEMD (`systemctl start bd-deploiement.service`) et pas seulement depuis un terminal de connexion — une unité démarre avec un environnement quasi vide, et c'est là que `git` ou `docker` disparaissent

### Le premier déploiement automatique, regardé
- [ ] Un `git push origin dev:main` sans migration déclenche le déploiement dans les cinq minutes, et l'instance SERT le nouveau commit — vérifié sur l'étiquette `bd.commit` de l'image (`docker inspect`), pas sur l'absence d'erreur
- [ ] La suite dans l'image a bien tourné pendant ce déploiement automatique : c'est la garde qui a le plus servi, et un timer qui la sauterait serait pire que pas de timer
- [ ] Un REFUS se voit : pousser une migration de schéma et constater que `systemctl status bd-deploiement.service` est `failed`, avec le message qui nomme les deux versions

### Ce que ce mécanisme rend plus probable
- [x] La comparaison Authelia de `deployer.sh` porte sur le commit SERVI (`bd.commit`) et non sur ce que le pull a ramené — `025b0d9`. Tranché dans le sens que la case proposait. Trois états et non deux : inchangée, modifiée, et « je n'ai pas pu comparer » (image sans étiquette, service à l'arrêt), qui redémarre par précaution SANS inscrire au journal une modification que personne n'a constatée. Mesuré des deux côtés de la coupe — `tests/test_deployeur.py` joue le script réel en `--simulation` sur un vrai dépôt git, et deux de ses quatre cas virent au rouge sur la version d'avant
- [ ] Un déploiement automatique qui échoue a été constaté au moins une fois pour de vrai, et le témoin d'échec s'est comporté comme prévu : refus au tir suivant, et non retour au vert

### Ce que le timer ne répare PAS
- [ ] Un écart entre le commit SERVI et `origin/main` se constate sans le chercher. Les deux bouts EXISTENT déjà et ne se rencontrent nulle part : `deploy/Dockerfile` pose `LABEL bd.commit=$BD_COMMIT`, et `deployer.sh` le lit par `docker inspect` à son étape 2 bis — mais pendant un déploiement, c'est-à-dire au seul instant où quelqu'un regarde déjà. Ce qui manque n'est donc pas la donnée, c'est qu'elle ne quitte jamais le script qui la calcule ; la route `GET /api/sante` de `main.py` est l'endroit d'où une surface lit déjà l'état de l'instance. Le timer réduit la FRÉQUENCE de l'écart, il ne le rend pas visible, et tant que rien ne compare, le 2026-09-07 reste reproductible à l'identique
- [ ] La CONDITION d'un tel affichage est posée : l'image ne connaît son commit qu'en `ARG` (`LABEL bd.commit`), qui ne survit pas au build — le processus qui tourne ne peut pas le lire. Il faut un `ENV` en plus du `LABEL`, sans quoi la surface n'aurait rien à afficher. Constaté le 2026-09-07 en cherchant par où faire sortir la donnée
- [ ] L'EXPOSITION est tranchée avant d'être écrite : `GET /api/sante` est ouverte sans identité (déclarée telle dans `tests/test_autorisation.py`, parce que c'est la sonde d'un conteneur), et derrière Authelia elle tombe sous la règle générale `one_factor`. Y publier le commit servi le rend lisible de tout compte de l'instance — sur un dépôt PUBLIC, cela dit quels correctifs sont en place et lesquels ne le sont pas. À trancher : `/api/sante` pour tous, ou un champ réservé à qui peut administrer
- [ ] L'arrêt du timer ne se constate que depuis le VPS : `systemctl stop bd-deploiement.timer` est le recours que `docs/exploitation.md` recommande en cas de doute, et il rétablit le déploiement manuel sans que la machine de développement en sache rien — le geste prudent recrée exactement la panne, en silence

## Contexte

**Le travail était déjà fait, il ne manquait qu'un déclencheur.** `deployer.sh` EST le
déploiement : onze refus, chacun correspondant à une panne datée. Toute solution se réduit
donc à « lancer ce script quand `origin/main` bouge », et le choix porte sur QUI le lance.

**Tirer plutôt que pousser, et ce n'est pas une préférence de style.** Une action GitHub
qui se connecte au VPS exige d'y déposer une clé SSH de production. Le dépôt est PUBLIC ;
les secrets Actions ne sont pas transmis aux workflows déclenchés par un fork, donc le
risque reste borné à qui peut pousser — mais c'est un identifiant permanent d'accès shell à
la production, confié à un tiers, pour remplacer un `ssh` qu'on tape déjà. Le timer sur le
VPS n'a besoin de rien : aucune clé, aucun port, aucune configuration chez GitHub. Le prix
est la latence et le fait que le journal reste sur la machine.

**La veille n'ajoute qu'UNE règle**, et c'est la seule qui demandait un arbitrage : une
mise à jour qui change `SCHEMA_VERSION` ne se déploie pas toute seule. L'en-tête de
`deployer.sh` dit déjà que « la décision appartient à un humain qui a lu les journaux »
parce que `_migrate()` est à sens unique. Automatiser le geste ne doit pas automatiser
cette décision-là. L'ordinaire passe seul, l'irréversible garde sa main.

Elle refuse aussi quand `main` a reculé, quand elle a divergé, quand la branche du VPS
n'est pas `main`, et quand `SCHEMA_VERSION` est ILLISIBLE — ce dernier cas par fermeture
par défaut : « je ne sais pas si cette mise à jour migre » ne doit pas se comporter comme
« elle ne migre pas ».

**Le témoin d'échec ferme une faille que j'avais écrite avant de la voir.** Un déploiement
raté a déjà fait avancer `HEAD` — le `pull` précède tout le reste —, si bien que la veille
concluait « rien à faire » au tir suivant, sortait en 0, et l'unité systemd repassait au
vert. Un échec de trois heures du matin devenait invisible à trois heures cinq. Le témoin
nomme la CIBLE et non `HEAD`, parce que `deployer.sh` peut échouer avant son pull comme
après et que seule la cible est commune aux deux cas ; conséquence voulue, un commit de
plus sur `main` est une tentative neuve, tandis qu'une cible inchangée reste refusée.

**Ce que la veille n'écrit pas dans le clone**, et c'est un piège évité de justesse : un
fichier d'état déposé là rendrait l'arbre SALE, et `deployer.sh` refuse de déployer sur un
arbre sale. La veille se serait bloquée elle-même au deuxième passage.

**Ce que ce mécanisme change dans le geste.** `git push origin dev:main` devient le bouton
de déploiement. L'intervalle qui existait — on avançait `main`, puis on décidait d'aller
lancer le script — disparaît, et avec lui la dernière occasion de se raviser. Le recours
est d'arrêter le timer, pas de courir après.

## Ce qui n'a PAS été éprouvé — 2026-09-06

**Rien de tout cela n'a tourné sur le VPS.** Les douze tests montent deux vrais dépôts git
et éprouvent la décision ET le passage de main — un `deployer.sh` factice dépose un témoin,
sans quoi le test resterait vert si la veille décidait parfaitement puis n'appelait
personne. Mais ils ne disent rien de systemd, rien de l'environnement dépouillé d'une
unité, rien de `docker` sous le compte `ubuntu`, et rien du vrai `deployer.sh` — qui ne
peut pas s'exécuter ailleurs que sur l'instance.

Deux endroits où cela peut casser, et ils sont dans le `Reste` plutôt que dans une
promesse : le PATH d'une unité systemd, et le transport du clone (HTTPS ou SSH).

**Et le mécanisme rend un défaut existant plus probable.** La comparaison Authelia de
`deployer.sh` demande « qu'a ramené ce pull », quand l'étape 2 bis du même script sait
déjà que la bonne question est « qu'est-ce que l'image SERT ». Les deux coïncident tant
qu'un humain relance après chaque échec ; sous un timer, un déploiement raté devient une
occurrence ordinaire. Le défaut n'a pas été corrigé ici : `deployer.sh` ne peut pas
s'éprouver hors de l'instance, et le modifier en même temps qu'on ajoute une automatisation
ferait deux surfaces non vérifiées au lieu d'une.
