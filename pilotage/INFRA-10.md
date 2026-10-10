---
chantier: INFRA-10
statut: livré
---

# INFRA-10 — déployer se fait à la main, donc quand on y pense

**Arrêté sur** — 2026-10-10, à la fusion `dev` → `main` (`68edccd` servi) : **un REFUS a enfin été VU**, celui d'une migration de schéma, v25 → v28, et la case qui l'attendait depuis l'ouverture est cochée. La même journée a ouvert trois cases — la garde de schéma de la veille lit le dépôt et non l'image servie, la suite dans l'image n'était jouée par personne avant de pousser `main`, et `lldap` tourne encore sur une image non épinglée. Le récit est dans « La fusion du 2026-10-10 ». Ce commit-ci ne touche pas ce chantier : la date est celle de l'observation.

Avant lui, `b2f2801` (2026-09-07) : **LE MÉCANISME EST POSÉ, ET IL A DÉPLOYÉ TOUT
SEUL.** Poussé à 19:31:17, tir du timer à 19:32, `DÉPLOYÉ a5a9f6e → 889e23f` à 19:38:20 —
sans qu'une main touche le VPS. La réserve que cette fiche portait depuis son ouverture,
« écrit, éprouvé LOCALEMENT, jamais tourné sur le VPS », est levée.

Deux observations valent plus que le succès lui-même. La ligne
`·· authelia configuration inchangée depuis a5a9f6e` est la signature du `deployer.sh`
corrigé le matin même : il NOMME la référence employée, et cette référence est le commit
SERVI. La correction se lit donc dans son propre journal de production. Et le tir suivant
a été déclenché dans la MÊME SECONDE que la fin du déploiement — systemd avait accumulé un
déclenchement pendant les six minutes de travail —, répondant « rien à faire ». C'est
`Type=oneshot` plus la bonne question (« l'image est-elle en retard », et non « le timer
a-t-il sonné ») : un mécanisme qui aurait redéployé là aurait bouclé sur lui-même.

**CE QUI RESTE OUVERT EST LE CHEMIN D'ÉCHEC, et c'est le plus important pour un mécanisme
sans surveillance.** Un REFUS n'a jamais été VU : ni la migration de schéma qui doit faire
passer l'unité en `failed` avec le message nommant les deux versions, ni le témoin d'échec
qui doit refuser au tir suivant plutôt que de repasser au vert. Les deux se fabriquent
exprès, ou s'observent le jour où ça arrive ; ni l'un ni l'autre n'a eu lieu. Le statut
`livré` parle de ce qui FONCTIONNE et de son intégration — il ne dit rien de ces deux
cases, et c'est pour cela qu'elles restent ouvertes plutôt que d'être rangées ailleurs.

**Mais la première pose a échoué en `203/EXEC`, et douze tests verts ne pouvaient pas le
voir.**
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

**Point de départ** — 2026-09-06. `deployer.sh` fait bien son travail depuis INFRA-12, mais
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
- [x] **Le service ne tombe plus en `203/EXEC`** — 2026-09-07, `b2f2801` déployé : le journal non tronqué a confirmé le diagnostic mot pour mot (`status=203/EXEC` aux trois premiers tirs), et le tir de 19:04:51 est propre. La sortie était bien un `./deploy/deployer.sh` à la main : la veille ne pouvait pas tirer le correctif qui la répare. Piège à garder écrit — NE PAS faire de `chmod +x` sur l'instance : git compte un changement de mode comme une modification, l'arbre deviendrait sale, et `deployer.sh` refuse de déployer sur un arbre sale ; le geste réparateur bloquerait la réparation
- [x] La veille rend « rien à faire » LANCÉE PAR SYSTEMD — 2026-09-07, 19:04:51 : `rien à faire — main est à a5a9f6e`, puis `Deactivated successfully`. Éprouvé mieux que la case ne demandait : par le service RÉEL (`systemctl start bd-deploiement.service`) et non par `--simulation`, donc l'environnement quasi vide d'une unité a bien été traversé — `git` et `docker` s'y trouvent, ce qui était le sujet de la case

### Le premier déploiement automatique, regardé
- [x] Un `git push origin dev:main` sans migration déclenche le déploiement dans les cinq minutes, et l'instance SERT le nouveau commit — 2026-09-07 : poussé à 19:31:17, tir à 19:32, `DÉPLOYÉ a5a9f6e → 889e23f` à 19:38:20, sans qu'une main touche le VPS. Vérifié sur l'étiquette comme la case l'exigeait : `docker inspect` rend `889e23f86adf4ddbe84a234019971c5fdb955a5d`, et non sur l'absence d'erreur
- [x] La suite dans l'image a bien tourné pendant ce déploiement automatique — regardée défiler dans `journalctl -f`, de 19:32 à 19:38, cliquet AUTH-2 compris (`118/125 routes cloisonnées`, même inventaire qu'en local : l'aplatissement des routes se comporte pareil dans l'image, ce qu'ARCH-2 avait vu se taire)
- [x] **Le panneau 🏷️ Version servie a servi à constater un déploiement RÉEL, et pas seulement à exister** — 2026-09-08 : 31 commits poussés à 16:02, le panneau annonce `b717a6d…6417`, c'est-à-dire la tête de `origin/main`. C'est sa première utilisation en situation ; le déploiement du 2026-09-07 avait été constaté par `docker inspect` SUR le VPS, donc par le canal que ce panneau existe précisément pour remplacer. La chaîne entière est vérifiée depuis un poste de travail : push → tir du timer → image construite avec `BD_COMMIT` → processus servant ce commit
- [x] Un REFUS se voit : pousser une migration de schéma et constater que `systemctl status bd-deploiement.service` est `failed`, avec le message qui nomme les deux versions — **OBSERVÉ le 2026-10-10, à la fusion `dev` → `main`.** `main` poussé à 09:24:13 (heure locale, `40ea44c..cd4fabb`), tir de 07:29:03 UTC : `main a avancé : 40ea44c -> cd4fabb (369 commit(s))` puis `REFUS cette mise à jour MIGRE le schéma : v25 -> v28.`, `Main process exited, code=exited, status=1/FAILURE`, `Failed with result 'exit-code'`. `systemctl status` : `Active: failed (Result: exit-code)`. Le tir suivant (07:34:38) refuse à l'identique : un refus de MIGRATION se redit à chaque tir, et ne pose aucun témoin — le témoin n'existe que pour un `deployer.sh` qui échoue LANCÉ PAR la veille (lu dans `veille-deploiement.sh`). Journal collé par Hugo depuis le VPS

### Ce que ce mécanisme rend plus probable
- [x] La comparaison Authelia de `deployer.sh` porte sur le commit SERVI (`bd.commit`) et non sur ce que le pull a ramené — `025b0d9`. Tranché dans le sens que la case proposait. Trois états et non deux : inchangée, modifiée, et « je n'ai pas pu comparer » (image sans étiquette, service à l'arrêt), qui redémarre par précaution SANS inscrire au journal une modification que personne n'a constatée. Mesuré des deux côtés de la coupe — `tests/test_deployeur.py` joue le script réel en `--simulation` sur un vrai dépôt git, et deux de ses quatre cas virent au rouge sur la version d'avant
- [ ] Un déploiement automatique qui échoue a été constaté au moins une fois pour de vrai, et le témoin d'échec s'est comporté comme prévu : refus au tir suivant, et non retour au vert — **toujours ouverte après la fusion du 2026-10-10, et les sections du 2026-09-14 et du 2026-09-18 se trompaient en annonçant qu'elle y trouverait son occasion** : un refus de migration sort AVANT l'appel de `deployer.sh` et ne pose pas le témoin. Un `deployer.sh` a bien échoué ce jour-là (suite rouge dans l'image), mais lancé À LA MAIN : le témoin n'a pas été posé non plus. La case attend un échec d'un déploiement que la veille aura lancé elle-même

### Ce que le timer ne répare PAS
- [x] Le commit SERVI a QUITTÉ le script qui le calcule — `7f80899`. Le bloc **🏷️ Version servie** ouvre la page d'Administration ; l'image porte le commit deux fois (`LABEL` pour `docker inspect`, `ENV` pour le processus), et `GET /api/version` le rend. Ce que la case demandait — que l'écart se constate sans le chercher — est à moitié fait, et la moitié restante est décrite ci-dessous
- [x] L'EXPOSITION a été tranchée AVANT d'être écrite, le 2026-09-07 : **réservé à qui peut administrer**, dans une route SÉPARÉE de `/api/sante`. Cette dernière doit répondre sans identité (sonde de conteneur, déclarée telle dans `tests/test_autorisation.py`) ; y greffer une branche dépendant de l'appelant aurait rendu cette déclaration fausse. Le motif du refus n'est pas qu'un numéro de version soit secret, c'est que le dépôt est PUBLIC : le commit servi dit quels correctifs sont en place
- [x] La CONDITION technique est levée : un `ARG` ne survit pas au build, donc `LABEL bd.commit` seul laissait le processus ignorer ce qu'il sert. `ENV BD_COMMIT` s'ajoute, et un test l'exige — retirer l'`ENV` ne casserait RIEN de visible, la page affichant alors « l'image ne déclare pas son commit », ce qu'elle affiche aussi, légitimement, sur un poste de développement
- [ ] L'AUTRE BOUT reste hors de portée de l'application, et c'est assumé plutôt que résolu : `origin/main` vit dans le dépôt, l'app ne le connaît pas et n'ira pas le chercher (le déploiement se TIRE, aucune sortie vers GitHub). L'écran renvoie donc à `git log --oneline -1 origin/main` au lieu d'affirmer « à jour » — une phrase qu'il ne pourrait pas fonder serait le silence lu comme une approbation, exactement ce qui a laissé passer les six commits. Reste à décider si quelqu'un doit COMPARER automatiquement, et où : la veille du VPS tient les deux bouts toutes les cinq minutes, mais elle n'écrit rien (l'arbre resterait sale, cf. plus bas), donc l'endroit n'existe pas encore
- [ ] L'arrêt du timer ne se constate que depuis le VPS : `systemctl stop bd-deploiement.timer` est le recours que `docs/exploitation.md` recommande en cas de doute, et il rétablit le déploiement manuel sans que la machine de développement en sache rien — le geste prudent recrée exactement la panne, en silence

### Ce que la fusion du 2026-10-10 a appris
- [ ] **La garde de schéma de la veille compare le DÉPÔT, pas l'image servie** — attendu : après un `deployer.sh` manuel qui a tiré le code puis échoué, la veille ne répond pas « rien à faire », et un commit de plus sur `main` ne migre pas la base tout seul. LU dans `veille-deploiement.sh` le 2026-10-10, puis OBSERVÉ le même jour dans le journal du VPS : `ici` est `git rev-parse HEAD`, et `version_schema "$ici"` lit le `database.py` de ce commit. Le `deployer.sh` de 09:37 a tiré `cd4fabb` puis refusé sur une suite rouge : `HEAD` valait dès lors `cd4fabb` (schéma 28) alors que l'image servait `40ea44c` (schéma 25, base v25). À `HEAD` = `origin/main` la veille dit « rien à faire » — unité VERTE, instance en retard, c'est la panne du 2026-09-06 que `deployer.sh` a apprise à lire sur l'étiquette `bd.commit` et que la veille n'a pas apprise ; et au commit suivant (`68edccd`) elle aurait comparé 28 à 28, conclu « schéma inchangé », et lancé le déploiement qui migre. La question est celle de `025b0d9` pour Authelia : la référence est le commit SERVI. **La première moitié est observée** : `journalctl -u bd-deploiement.service --since 07:36`, collé par Hugo — `07:39:40 rien à faire — main est à cd4fabb`, `07:44:58` et `07:50:22` de même, chacun suivi de `Finished`, donc trois tirs VERTS pendant que le premier `deployer.sh` construisait puis refusait, l'instance servant `40ea44c`. L'unité `failed` de 07:34 était redevenue verte sans que rien n'ait été déployé. La seconde moitié — le commit suivant qui migre seul — a été ÉVITÉE et non observée : le timer était arrêté quand `68edccd` est arrivé sur `main`
- [ ] **La suite DANS l'image est jouée avant de pousser `main`, pas découverte sur le serveur** — attendu : « la liste d'avant la fusion » porte ce geste, et il est fait (`docker build -f deploy/Dockerfile --target test` puis `docker run --rm`, QA-5). Le 2026-10-10, deux tests écrits le 2026-09-16 lisaient un fichier que le `.dockerignore` exclut de l'image depuis le 2026-09-05 : verts sur le poste pendant vingt-quatre jours, rouges dans l'image, où personne n'avait rejoué la suite. `deployer.sh` a refusé — la garde a tenu, avant toute migration — et le correctif (`68edccd`) a coûté quarante-cinq minutes d'une fusion commencée. Jouée sur le poste avant le second push : 1447 passed, 28 skipped, les chiffres du serveur
- [ ] **`lldap` tourne encore sur l'image `stable` d'il y a quatre semaines** — attendu : le conteneur sert `lldap/lldap:v0.6.3-alpine`, l'image que le compose épingle depuis cette fusion. `deployer.sh` ne recrée que `app` (`up -d --build app`) : l'épinglage est sur le disque, pas dans le conteneur (`docker compose ps` du 2026-10-10 : `bd-lldap  lldap/lldap:stable … 4 weeks ago`). Le recréer est un geste à part, à faire à la main et en nommant le service — jamais un `up -d` nu sur cette pile (cf. `docs/exploitation.md`, « La pile n'est pas celle du dépôt par défaut »)

## La garde de l'arbre sale est TARDIVE — 2026-09-10

**Trouvé en essayant de fermer une case, et l'essai a échoué pour une raison utile.** La
passe `repli-annuaire` laisse l'arbre du VPS sale pendant une demi-heure. On attendait donc
que la veille refuse toutes les cinq minutes — `deployer.sh` porte cette garde depuis la
panne du 2026-09-05 —, ce qui aurait fermé gratuitement la case « un déploiement
automatique qui échoue a été constaté au moins une fois pour de vrai ».

Il ne s'est rien passé. Trois tirs, tous verts, `rien à faire — main est à 40ea44c`, et le
dossier de témoin n'existe même pas : `~/.local/state/bd-deploiement/` est absent, ce qui
confirme qu'aucun échec n'a jamais eu lieu depuis la pose.

**Les deux gardes sont EN SÉRIE, et l'extérieure masque l'intérieure.**
`veille-deploiement.sh` compare `main` à ce qui est déployé et sort AVANT d'appeler
`deployer.sh` quand rien n'a bougé. La garde de l'arbre sale n'est donc atteignable que
lorsque `main` avance.

**Conséquence, et c'est le mode d'échec inverse de celui qu'on redoutait.** Une édition en
place sur le serveur ne déclenche RIEN tant que personne ne pousse : ni avertissement, ni
témoin, ni unité rouge. Elle reste invisible jusqu'au jour où `main` avance — et le refus
tombe alors au moment précis où l'on voulait déployer. Ce n'est pas un écrasement
silencieux, c'est un blocage DIFFÉRÉ, et il se manifeste au plus mauvais moment possible.

**Les deux cases d'observation restent donc OUVERTES**, et elles le resteront tant qu'un
vrai échec ne se produira pas. On ne peut pas le provoquer proprement : il faudrait pousser
sur `main` en laissant l'arbre du VPS sale, c'est-à-dire fabriquer exprès la situation
qu'on veut éviter. Écrit ici pour qu'on ne réessaie pas la même chose en croyant à un
oubli.

**Et le document d'exploitation disait le contraire.** `docs/exploitation.md` portait
encore « ### Le déploiement automatique (INFRA-10) — PAS ENCORE POSÉ » et « aujourd'hui,
cela ne déclenche rien », trois jours après la pose. Corrigé le 2026-09-10. Cette section
a désormais menti dans les DEUX sens — au présent avant d'exister, au passé après —, et
c'est la même faute : un guide d'exploitation décrit un ÉTAT à quelqu'un qui l'ouvre parce
qu'il ne sait pas.

## Ce que la fusion de `dev` dans `main` déclenchera — 2026-09-14

**Écrit AVANT la fusion, parce qu'une surprise se prépare mal après.** `dev` porte seize
commits qui touchent `deploy/` — onze fichiers, +722/−57, mesuré le 2026-09-14
(`git diff --stat main..dev -- deploy/`). Le Dockerfile, le compose, le Caddyfile, la
configuration d'Authelia, `deployer.sh` lui-même, et deux outils qui n'existaient pas
(`geler_verrous.py`, `verifier_comptes.py`). Le premier déploiement d'après la fusion les
emporte tous d'un coup.

**Et il n'aura pas lieu tout seul.** `SCHEMA_VERSION` passe de **25** à **28**, et la veille
refuse une mise à jour qui migre le schéma : elle nomme les deux versions, laisse l'unité en
`failed`, et renvoie à `./deploy/deployer.sh` après sauvegarde. Le geste n'est donc pas
« pousser puis rien » — c'est pousser, s'attendre à une unité ROUGE, sauvegarder, déployer à
la main.

**Cette unité rouge sera le comportement CORRECT**, et c'est le piège de lecture à
désamorcer d'avance : un `failed` sous les yeux ressemble à une panne du mécanisme, alors
que c'est exactement l'arbitrage écrit dans le Contexte ci-dessous — « l'ordinaire passe
seul, l'irréversible garde sa main ». Le confondre ferait chercher une réparation là où il
n'y a qu'une décision rendue à un humain.

**Les deux cases d'observation trouvent là leur occasion, sans qu'on fabrique rien.** La
section du 2026-09-10 conclut qu'un vrai refus ne se provoque pas proprement — il faudrait
salir exprès l'arbre du VPS, c'est-à-dire fabriquer la situation qu'on veut éviter. Celui-ci
arrive de lui-même, à une date qu'on choisit. Reste à le CONSTATER, et c'est pourquoi les
cases restent OUVERTES : le message nomme-t-il bien v25 et v28, et le témoin refuse-t-il au
tir suivant plutôt que de repasser au vert. Ce qui est écrit ici est ce qu'on ATTEND, pas ce
qu'on a vu.

**Une conséquence qui ne se voit pas depuis cette fiche** : `4662ce3` corrige dans
`deploy/Caddyfile` une annonce HTTP/3 que la production sert toujours. `INFRA-1` expliquait
ce retard par un défaut d'accès au serveur — motif FAUX, corrigé là-bas le même jour, et
c'est cette fiche-ci qui l'a fait tomber, ouverte pour tout autre chose. Le correctif
n'attend pas un accès : il attend cette fusion.

## La liste d'avant la fusion — 2026-09-18

**Elle existe parce qu'elle n'existait pas.** Trois fiches renvoient à « la liste d'avant la
fusion que porte la coordination » ; aucun document ne la portait, et une liste qui ne vit
que dans un fil de conversation meurt avec la session qui la tient. Elle est ici et non dans
`docs/roadmap.md`, qui dit le PÉRIMÈTRE — ce que la fusion attend — là où ceci dit les
GESTES, et parce que la section du 2026-09-14 ci-dessus décrit déjà ce que la fusion
déclenche. Les deux se lisent ensemble.

Ce n'est pas un `Reste` : rien ici ne se coche, tout se fait le jour dit. Ce qui a une case
la garde dans sa propre fiche, nommée ci-dessous.

**Avant de fusionner**
1. Les passes de QA du périmètre sont jouées (`docs/roadmap.md`, tranché le 2026-09-17), et
   les étapes 1 à 4 d'`AUTH-12` sont sur `dev`.
2. `main` est encore ANCÊTRE de `dev` — l'avance rapide se vérifie le jour même, pas la
   veille : `git merge-base --is-ancestor origin/main dev`.
3. La recette est reconstruite sur le HEAD FINAL et re-recettée. Elle a servi des commits
   intermédiaires toute la journée du 18 ; ce qui part en production n'est éprouvé que si
   c'est LUI qu'on a servi.
4. ~~Trois défauts d'outillage relevés en lisant `AUTH-12`.~~ **RETIRÉ le 2026-09-18,
   quelques heures après avoir été écrit : les trois étaient DÉJÀ RÉPARÉS, et depuis le
   2026-09-16.** Les numéros de ligne de `docs/exploitation.md` par `208e781` (« le repli
   vise des repères, plus des numéros de ligne »), qui a réparé la panne exacte que le
   constat décrivait — et la page en porte le récit daté. `BD_AUTH_ADMIN_GROUPS` par la
   même journée : `verifier_deploiement.py` résout ce que Compose transmet, sa docstring
   écrit « jusqu'au 2026-09-16, ce contrôle lisait la variable directement dans `.env` », et
   il AVERTIT désormais qu'une valeur posée là est sans effet. L'avertissement « référent
   manquant » est gardé par `annuaire_actif`, avec sa raison écrite à côté : le fichier des
   comptes n'est que le repli quand l'annuaire sert, et son nombre ne dit rien de l'instance.
   Vérifiés un par un dans le code, pas dans les fiches.

   **Et cette entrée reste ici, barrée, parce que c'est ELLE la leçon.** Le constat venait
   d'une lecture d'`AUTH-12`, qui gardait la trace d'un défaut fermé ailleurs sans le savoir
   — une fiche pourrit pendant qu'on travaille à côté. Recopié dans une liste NEUVE, il
   devenait pire que dans sa fiche : une liste d'avant la fusion a l'autorité de sa
   fraîcheur, et personne n'aurait rouvert la question. **Une liste hérite de la péremption
   de ses sources et la cache derrière la sienne** : chaque entrée reprise d'une fiche se
   vérifie dans le CODE avant d'entrer ici, et celles ci-dessous l'ont été.
5. `AUTH-6` porte une case de déploiement qui naît avec la lecture de l'annuaire : une règle
   de refus pour le compte de SERVICE dans `access_control`. Sans elle, l'identifiant qui vit
   dans le `.env` est aussi un identifiant de portail (constaté sur la recette le
   2026-09-18 ; sans effet tant qu'aucun accès ne lui est donné).
6. `CONC-3` garde une case marquée « AVANT la prochaine fusion » : elle porte sur les
   testeurs qui travaillent à plusieurs, et c'est elle qui donne son sens au second temps.

**Le jour même, et dans cet ordre**
7. Sauvegarder AVANT de pousser. `SCHEMA_VERSION` passe de 25 à 28 : la migration ne se
   rétrograde pas.
8. Pousser `main`, puis **s'attendre à une unité `failed`** et NE PAS la réparer. La veille
   refuse une mise à jour qui migre le schéma ; ce rouge est le comportement correct, décrit
   dans la section du 2026-09-14. Le confondre avec une panne ferait chercher une réparation
   là où il n'y a qu'une décision rendue à un humain.
9. Déployer à la main par `./deploy/deployer.sh`.
10. CONSTATER pendant qu'on y est, sans rien fabriquer : le message du refus nomme-t-il bien
    v25 et v28, et le témoin refuse-t-il au tir suivant plutôt que de repasser au vert. Ce
    sont les deux cases d'observation de la zone « Le premier déploiement automatique,
    regardé », et la section du 2026-09-14 explique pourquoi cette occasion-là ne se
    provoque pas proprement autrement.
11. Seize commits touchant `deploy/` partent d'un coup — Dockerfile, compose, Caddyfile,
    configuration d'Authelia, `deployer.sh` lui-même, et deux outils qui n'existaient pas.
    Mesuré le 2026-09-14 ; à remesurer le jour dit.

**Après**
12. Les passes qui se cochent sur la PRODUCTION et non sur le dépôt : `AUTH-6` en porte deux,
    dont la déclaration des logins partagés, qui attendait précisément ce passage.


## La fusion du 2026-10-10 — ce qui s'est passé

`dev` → `main` par avance rapide, 369 commits, schéma 25 → 28, seize commits sur `deploy/` (huit fichiers, +948/−65 remesurés le jour même ; `deployer.sh` et `veille-deploiement.sh` n'en étaient PAS, contrairement à ce qu'écrit la section du 2026-09-14 — le script qui tourne n'a donc pas été remplacé sous lui).

Dans l'ordre : sauvegarde prise par Hugo depuis le navigateur ; `git push origin dev:main` à 09:24:13 (`cd4fabb`) ; refus de la veille à 07:29:03 UTC, nommant v25 et v28, unité `failed` — la case est cochée ci-dessus ; `./deploy/deployer.sh` à la main, qui tire, construit, joue la suite dans l'image et REFUSE : `2 failed, 1447 passed, 26 skipped`, les deux échecs dans `tests/test_repli_annuaire.py` (`FileNotFoundError: /app/deploy/authelia/configuration.yml`). L'instance n'a pas été touchée, la base est restée en v25. Timer arrêté par Hugo (`sudo systemctl stop bd-deploiement.timer`) pour que le correctif ne se déploie pas seul — cf. la première case de la zone « Ce que la fusion du 2026-10-10 a appris ». Correctif `68edccd`, validé sur le poste par la suite par défaut (1536) ET par la suite dans l'image (1447 passed, 28 skipped), poussé sur `dev` puis `main` à 10:09. Second `./deploy/deployer.sh` : `configuration MODIFIÉE depuis 40ea44c (servi) — redémarrage` d'Authelia, dix chemins refusés à un anonyme, quatre moteurs importés, `DÉPLOYÉ  cd4fabb → 68edccd`. Constaté ensuite sur le VPS : `schema 28`, `bd-authelia … (healthy)`, aucun message d'erreur au démarrage de l'application. Hugo s'est connecté en administrateur (`chercheur`) et sous un compte ordinaire (`stagiaire`).

Ce qui n'a PAS été fait ce jour-là, et qui est écrit ailleurs : le compte de service `bd-application` n'existe pas en production (aucune variable `BD_ANNUAIRE_*` dans le `.env` du serveur), donc sa connexion refusée et son adresse non délivrable attendent sa création — `pilotage/AUTH-6.md`. Le timer a été relancé par Hugo après le déploiement, et le tir de 08:32:05 UTC répond `rien à faire — main est à 68edccd` — vrai cette fois, l'image servant ce commit.

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

## Ce que la vérification EXTERNE ne peut pas dire — 2026-09-08

Mesuré depuis un poste sans identifiants, après le push de 31 commits. Les trois URL —
`/`, `/api/sante`, `/api/version` — rendent **302 vers `auth.edito-revue.fr`**, avec le
`rd=` attendu. DNS, TLS, reverse proxy et forward-auth sont donc debout.

**Et cela ne dit RIEN de l'application.** Le forward-auth intercepte AVANT de transmettre :
une requête non authentifiée ne touche jamais le backend, si bien qu'un conteneur mort
rendrait exactement le même 302. Ce n'est pas un trou de la vérification, c'est la
conception — `access_control` pose `default_policy: 'deny'` et **aucune règle de
contournement**, pas même pour une sonde. `/api/sante` répond bien sans identité, mais elle
est appelée depuis l'INTÉRIEUR du conteneur.

Cela ajoute un second angle mort à celui que la case « l'AUTRE BOUT » décrit déjà. Celle-ci
dit que l'application ignore `origin/main` ; celui-là dit que **personne, du dehors, ne peut
observer l'application** — seulement le portail qui la garde. Les deux se rejoignent sur la
même conséquence : le seul endroit d'où l'on constate un déploiement est un écran qui exige
d'être administrateur, ou le VPS lui-même.

Ce n'est pas présenté comme un défaut à corriger. Ouvrir une surface non authentifiée pour
faire plaisir à une sonde serait payer un renseignement public — le dépôt étant public, le
commit servi dit quels correctifs sont en place, ce qui est exactement le motif pour lequel
`/api/version` est réservée. La note existe pour que le prochain qui cherche « pourquoi je
ne peux pas juste faire un curl » trouve la réponse écrite plutôt que de la redécouvrir.

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
