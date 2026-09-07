---
chantier: INFRA-10
statut: interrompu
---

# INFRA-10 — déployer se fait à la main, donc quand on y pense

**Arrêté sur** — 2026-09-07, `b2f2801` : **la première pose sur le VPS a échoué en
`203/EXEC`, et douze tests verts ne pouvaient pas le voir.**
`deploy/veille-deploiement.sh` était commité en mode `100644` quand `deployer.sh` est en
`100755`. `ExecStart` exige le bit d'exécution : systemd n'a pas pu LANCER le fichier, et
l'unité est passée `failed` sans qu'une seule ligne du script ne tourne.

**Le harnais ne pouvait pas le trouver, et c'est mécanique** : il invoque
`[BASH, "deploy/veille-deploiement.sh"]`, c'est-à-dire le script comme ARGUMENT de bash —
une forme qui ne consulte jamais le bit d'exécution. Il éprouvait donc parfaitement la
DÉCISION de la veille, sur un chemin d'invocation que la production n'emprunte pas. C'est
la limite que cette fiche s'écrivait à elle-même depuis le début — « éprouvé LOCALEMENT,
jamais tourné sur le VPS » — arrivée par l'endroit qu'on ne surveillait pas : non pas la
logique, mais la façon dont on la lance.

Le contrôle neuf lit le mode dans l'INDEX git (le disque ne le porte pas sous Windows) et
se DÉRIVE des unités : une unité future pointant vers un script non exécutable tombe dans
le même trou, et un test qui ne connaîtrait que ce fichier-ci la laisserait passer.

**Plus tôt le même jour, `7f80899` : le commit servi a quitté le script qui le
calcule.** Le bloc 🏷️ Version servie ouvre la page d'Administration, réservé à qui peut
administrer — le dépôt étant public, le commit servi dit quels correctifs sont en place.
L'écran n'affirme rien qu'il n'ait vu : il connaît un seul bout de la comparaison, le dit,
et renvoie à `origin/main` plutôt que d'écrire « à jour ». Une phrase qu'il ne pourrait pas
fonder serait le silence lu comme une approbation — ce qui a laissé passer les six commits.

**Plus tôt le même jour, `025b0d9` : le déployeur comparait la configuration Authelia
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
- [x] Le clone du VPS tire en HTTPS — constaté le 2026-09-07 : `origin https://github.com/Hsbtqemy/BD_ditor.git`. (`git -C ~/BD_ditor remote -v`) : le dépôt est public, donc `git fetch` n'a besoin d'aucune clé — mais un clone en SSH exigerait un agent que systemd n'a pas, et la veille échouerait toutes les cinq minutes
- [x] Les unités sont installées et le timer actif : `systemctl list-timers bd-deploiement.timer` annonce un prochain tir — fait le 2026-09-07, le clone tirant bien en HTTPS
- [ ] **Le service ne tombe plus en `203/EXEC`** : le mode `100755` est poussé, mais l'instance sert encore la version sans lui. Il faut un `./deploy/deployer.sh` À LA MAIN une fois — la veille ne peut pas tirer le correctif qui la répare. Et surtout PAS de `chmod +x` sur le VPS : git compte un changement de mode comme une modification, l'arbre deviendrait SALE, et `deployer.sh` refuse de déployer sur un arbre sale — le geste réparateur bloquerait la réparation
- [ ] `./deploy/veille-deploiement.sh --simulation` rend « rien à faire » LANCÉ PAR SYSTEMD (`systemctl start bd-deploiement.service`) et pas seulement depuis un terminal de connexion — une unité démarre avec un environnement quasi vide, et c'est là que `git` ou `docker` disparaissent

### Le premier déploiement automatique, regardé
- [ ] Un `git push origin dev:main` sans migration déclenche le déploiement dans les cinq minutes, et l'instance SERT le nouveau commit — vérifié sur l'étiquette `bd.commit` de l'image (`docker inspect`), pas sur l'absence d'erreur
- [ ] La suite dans l'image a bien tourné pendant ce déploiement automatique : c'est la garde qui a le plus servi, et un timer qui la sauterait serait pire que pas de timer
- [ ] Un REFUS se voit : pousser une migration de schéma et constater que `systemctl status bd-deploiement.service` est `failed`, avec le message qui nomme les deux versions

### Ce que ce mécanisme rend plus probable
- [x] La comparaison Authelia de `deployer.sh` porte sur le commit SERVI (`bd.commit`) et non sur ce que le pull a ramené — `025b0d9`. Tranché dans le sens que la case proposait. Trois états et non deux : inchangée, modifiée, et « je n'ai pas pu comparer » (image sans étiquette, service à l'arrêt), qui redémarre par précaution SANS inscrire au journal une modification que personne n'a constatée. Mesuré des deux côtés de la coupe — `tests/test_deployeur.py` joue le script réel en `--simulation` sur un vrai dépôt git, et deux de ses quatre cas virent au rouge sur la version d'avant
- [ ] Un déploiement automatique qui échoue a été constaté au moins une fois pour de vrai, et le témoin d'échec s'est comporté comme prévu : refus au tir suivant, et non retour au vert

### Ce que le timer ne répare PAS
- [x] Le commit SERVI a QUITTÉ le script qui le calcule — `7f80899`. Le bloc **🏷️ Version servie** ouvre la page d'Administration ; l'image porte le commit deux fois (`LABEL` pour `docker inspect`, `ENV` pour le processus), et `GET /api/version` le rend. Ce que la case demandait — que l'écart se constate sans le chercher — est à moitié fait, et la moitié restante est décrite ci-dessous
- [x] L'EXPOSITION a été tranchée AVANT d'être écrite, le 2026-09-07 : **réservé à qui peut administrer**, dans une route SÉPARÉE de `/api/sante`. Cette dernière doit répondre sans identité (sonde de conteneur, déclarée telle dans `tests/test_autorisation.py`) ; y greffer une branche dépendant de l'appelant aurait rendu cette déclaration fausse. Le motif du refus n'est pas qu'un numéro de version soit secret, c'est que le dépôt est PUBLIC : le commit servi dit quels correctifs sont en place
- [x] La CONDITION technique est levée : un `ARG` ne survit pas au build, donc `LABEL bd.commit` seul laissait le processus ignorer ce qu'il sert. `ENV BD_COMMIT` s'ajoute, et un test l'exige — retirer l'`ENV` ne casserait RIEN de visible, la page affichant alors « l'image ne déclare pas son commit », ce qu'elle affiche aussi, légitimement, sur un poste de développement
- [ ] L'AUTRE BOUT reste hors de portée de l'application, et c'est assumé plutôt que résolu : `origin/main` vit dans le dépôt, l'app ne le connaît pas et n'ira pas le chercher (le déploiement se TIRE, aucune sortie vers GitHub). L'écran renvoie donc à `git log --oneline -1 origin/main` au lieu d'affirmer « à jour » — une phrase qu'il ne pourrait pas fonder serait le silence lu comme une approbation, exactement ce qui a laissé passer les six commits. Reste à décider si quelqu'un doit COMPARER automatiquement, et où : la veille du VPS tient les deux bouts toutes les cinq minutes, mais elle n'écrit rien (l'arbre resterait sale, cf. plus bas), donc l'endroit n'existe pas encore
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
