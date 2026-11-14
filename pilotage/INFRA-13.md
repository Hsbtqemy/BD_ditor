---
chantier: INFRA-13
statut: à venir
---

# INFRA-13 — la suite dans l'image gèle le VPS

**Point de départ** — 2026-11-14, au déploiement de `2cd0d01` (la v39 d'`ANN-7`). Lancé à la main, `deployer.sh` a construit `bdediteur:suite` (21:19 UTC), puis joué la suite dans l'image à côté de l'application servie : vers 21:45 UTC, le journal du noyau cesse d'écrire, SSH accepte la connexion sans envoyer de bannière, le port 80 accepte sans répondre. Rien n'a été tué faute de mémoire (aucune ligne `oom` au démarrage d'avant) : avec 2 Go de swap, la machine a ralenti jusqu'à ne plus répondre, pendant quarante-cinq minutes, avant un redémarrage à froid depuis la console de l'hébergeur. Rien n'était migré : la base est restée en v38 jusqu'au `deployer.sh --sans-suite` qui a suivi.

## Reste

### Le remède
- [ ] **Hugo tranche le remède** — attendu : (a) la veille lance `deployer.sh --sans-suite`, et la suite dans l'image devient une condition, jouée sur le poste à la révision poussée, avant tout push de `main` (la pratique depuis le 2026-10-10, cf. `INFRA-10`) ; ou (b) la suite reste sur le VPS, bornée (`docker run --memory`, un seul processus), au risque d'un rouge de mémoire. Proposition de la session : (a)
- [ ] **Le minuteur ne peut plus geler le VPS** — attendu : après le remède, un push de `main` déployé par la veille seule laisse SSH et le site répondre pendant tout le déploiement ; tant que ce n'est pas fait, le prochain push de `main` refait la panne, sans personne devant
- [ ] **`docs/exploitation.md` dit où la suite dans l'image se joue** — attendu : la section du déploiement nomme la condition du remède retenu, et ce qu'il faut faire si un VPS gèle (redémarrer à froid, arrêter `bd-deploiement.timer` AVANT tout : un `stop` ne survit pas au redémarrage)

## Contexte

Le VPS : 3,8 Go de mémoire, 2 processeurs, 2 Go de swap (`/swapfile`), mesurés après le redémarrage. La suite dans l'image compte 3 457 tests ; elle était passée sur ce VPS aux fusions précédentes, sur des suites plus courtes. L'image de service a ensuite été construite sans peine : elle part de la même base, en cache.

Une hypothèse, pas une cause établie : la mémoire. Ce qui la trancherait — jouer la suite sur le VPS sous `free -s 5`, ce qu'on ne fera pas sur la production.

Le jour même, la réindexation par le moteur de langue (temps 3 de la v39) a pris 7,2 s pour 3 375 régions, sans pression visible : ce n'est pas elle qu'il faut craindre.
