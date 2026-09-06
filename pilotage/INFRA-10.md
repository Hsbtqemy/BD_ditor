---
chantier: INFRA-10
statut: interrompu
---

# INFRA-10 — déployer se fait à la main, donc quand on y pense

**Arrêté sur** — le mécanisme est écrit et éprouvé LOCALEMENT : `deploy/veille-deploiement.sh`,
deux unités systemd, douze tests sur deux vrais dépôts git. **Il n'a jamais tourné sur le
VPS**, et c'est la limite à garder en tête en lisant le reste.

**Point de départ** — 2026-09-06. `deployer.sh` fait bien son travail depuis INFRA-7, mais
il faut ouvrir une session SSH et penser à le lancer. La question posée : GitHub pourrait-il
déployer sur poussée de `main` ? La réponse retenue est OUI pour le déclenchement, NON pour
GitHub — le déploiement se TIRE.

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
- [ ] La comparaison Authelia de `deployer.sh` porte sur `$avant..$apres` — ce que ce PULL a ramené — alors que l'étape 2 bis sait que la référence est le commit SERVI par l'image. Un déploiement qui échoue après le pull laisse donc la politique d'accès non appliquée au passage suivant, en silence : même famille que la panne de sept heures d'INFRA-9. À trancher — comparer depuis le commit servi
- [ ] Un déploiement automatique qui échoue a été constaté au moins une fois pour de vrai, et le témoin d'échec s'est comporté comme prévu : refus au tir suivant, et non retour au vert

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
