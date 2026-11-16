---
chantier: INFRA-13
statut: différé
---

# INFRA-13 — la suite dans l'image gèle le VPS

**Arrêté sur** — 2026-11-15, `e5e8d87` : **la suite dans l'image ne se joue plus sur le VPS.** `deployer.sh` ne la construit ni ne la lance plus par défaut (`--avec-suite` la rejoue, `--sans-suite` reste accepté sans effet), la veille l'appelle ainsi, `docs/exploitation.md` dit qu'elle se joue sur le poste avant de pousser `main` et quoi faire si le VPS gèle ; `test_la_suite_ne_se_joue_plus_sur_le_vps_par_defaut`, trois mutants tombés, suite par défaut verte. Différé jusqu'au prochain push de `main`, qui seul peut fermer la dernière case.

**Point de départ** — 2026-11-14, au déploiement de `2cd0d01` (la v39 d'`ANN-7`). Lancé à la main, `deployer.sh` a construit `bdediteur:suite` (21:19 UTC), puis joué la suite dans l'image à côté de l'application servie : vers 21:45 UTC, le journal du noyau cesse d'écrire, SSH accepte la connexion sans envoyer de bannière, le port 80 accepte sans répondre. Rien n'a été tué faute de mémoire (aucune ligne `oom` au démarrage d'avant) : avec 2 Go de swap, la machine a ralenti jusqu'à ne plus répondre, pendant quarante-cinq minutes, avant un redémarrage à froid depuis la console de l'hébergeur. Rien n'était migré : la base est restée en v38 jusqu'au `deployer.sh --sans-suite` qui a suivi.

## Reste

### Le remède
- [x] **Hugo tranche le remède** — attendu : (a) la veille lance `deployer.sh --sans-suite`, et la suite dans l'image devient une condition, jouée sur le poste à la révision poussée, avant tout push de `main` (la pratique depuis le 2026-10-10, cf. `INFRA-10`) ; ou (b) la suite reste sur le VPS, bornée (`docker run --memory`, un seul processus), au risque d'un rouge de mémoire. Proposition de la session : (a) **Tranché par Hugo le 2026-11-15 : (a). Appliqué au DÉFAUT de `deployer.sh` et non à la seule veille, `e5e8d87` : un `./deploy/deployer.sh` tapé à la main, comme dans toutes les procédures écrites, aurait refait la panne.**
- [ ] **Le déploiement de la v40 se lance avec `--sans-suite`** — attendu : sur le VPS, `./deploy/deployer.sh --sans-suite` (ou `git pull --ff-only`, puis `./deploy/deployer.sh`) ; tapé nu, c'est le script de `2cd0d01` qui s'exécute — bash garde le fichier ouvert avant son propre `pull` —, et il joue encore la suite dans l'image par défaut. La veille ne le fera pas à notre place : la v40 migre, et elle ne déploie jamais une migration ; sa phrase de refus, comme `docs/exploitation.md`, dit `./deploy/deployer.sh` nu (vu le 2026-11-16 en préparant le déploiement)
- [ ] **Le minuteur ne peut plus geler le VPS** — attendu : après le remède, un push de `main` déployé par la veille seule laisse SSH et le site répondre pendant tout le déploiement ; tant que ce n'est pas fait, le prochain push de `main` refait la panne, sans personne devant
- [x] **`docs/exploitation.md` dit où la suite dans l'image se joue** — attendu : la section du déploiement nomme la condition du remède retenu, et ce qu'il faut faire si un VPS gèle (redémarrer à froid, arrêter `bd-deploiement.timer` AVANT tout : un `stop` ne survit pas au redémarrage) **Le 2026-11-15, `e5e8d87` : « Mettre à jour le code », et la section des tests du poste.**

## Contexte

Le VPS : 3,8 Go de mémoire, 2 processeurs, 2 Go de swap (`/swapfile`), mesurés après le redémarrage. La suite dans l'image compte 3 457 tests ; elle était passée sur ce VPS aux fusions précédentes, sur des suites plus courtes. L'image de service a ensuite été construite sans peine : elle part de la même base, en cache.

Une hypothèse, pas une cause établie : la mémoire. Ce qui la trancherait — jouer la suite sur le VPS sous `free -s 5`, ce qu'on ne fera pas sur la production.

Le jour même, la réindexation par le moteur de langue (temps 3 de la v39) a pris 7,2 s pour 3 375 régions, sans pression visible : ce n'est pas elle qu'il faut craindre.

Mis en attente le 2026-11-15 : la dernière case ne se ferme qu'au prochain push de `main`, en regardant SSH et le site pendant que la veille déploie seule. Pas celui de la v40 (2026-11-16) : il migre, donc se déploie à la main ; le premier push de `main` SANS migration la fermera.
