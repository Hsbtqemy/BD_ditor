---
chantier: INFRA-12
statut: livré
---

# INFRA-12 — le contrôle de déploiement dit ce qu'il n'a PAS pu vérifier

**Arrêté sur** — 2026-09-10, `dbb67d1` : les deux docstrings d'ouverture sont repointées et
ce chantier existe enfin sous son nom. **Le travail qu'il décrit est ANTÉRIEUR à son
premier commit** — `87544ba` (2026-09-07), où le contrôle cesse d'annoncer « moteurs
absents ou cassés » pour une sonde qu'il n'avait pas pu poser, porte « INFRA-7 » dans son
sujet et restera ainsi. La fresque datera donc ce chantier du 2026-09-10 et ne montrera
rien avant, alors que l'essentiel s'y est fait trois jours plus tôt : ce vide n'est pas une
absence de travail, c'est du travail classé sous un autre nom.

**Point de départ du travail lui-même** — 2026-09-05, `9ee9a98`, « un script de
déploiement qui refuse d'avancer là où l'on s'est trompé ». Né sans code de chantier, et
c'est l'origine de tout le désordre que cette fiche referme.

## Reste

### Ce qui est fait, et sous quels commits
- [x] **`deployer.sh` refuse d'avancer sur un arbre de travail sale** — écrit le 2026-09-05 (`9ee9a98`) après la panne du même jour, où un fichier édité en place sur le VPS avait été écrasé par un déploiement. La garde est REELLE, et sa limite est écrite plus bas
- [x] **`verifier_deploiement.py` distingue « non » de « je n'ai pas pu demander »** — 2026-09-07 (`87544ba`), après une sortie lue sur l'instance : `compose exec` échouait faute de fichier de configuration, et le contrôle traduisait cet échec de SONDE en verdict « moteur(s) absents ou cassés ». Une garde qui confond l'absence de réponse avec une réponse négative crie au mauvais endroit, et l'on cesse alors de l'écouter
- [x] **Le contrôle est éprouvé par `tests/test_verifier_deploiement.py`**, écrit dans le même commit — le module dont la première ligne portait `INFRA-7` et porte désormais le code de cette fiche

### Ce qui reste ouvert
- [ ] **Lancé avec `--url` seul, le contrôle rend un vert qui n'a pas regardé la configuration, et ne le DIT pas.** Mesuré le 2026-09-09 pendant INFRA-9 : `controle_config` ne tourne que si `--config` est donné, si bien que le contrôle BLOQUANT du groupe d'administration ne s'exécute pas — il a fallu relancer avec `--config .env` pour l'obtenir. C'est exactement le défaut que `87544ba` a fermé de l'autre côté, revenu par la porte des OPTIONS : *ne pas avoir demandé* s'affiche comme *avoir vérifié*. Attendu : la sortie énumère ce qu'elle n'a pas contrôlé, et pourquoi — pas un silence qui se lit comme un succès
- [ ] **La garde de l'arbre sale est TARDIVE, et son mode d'échec est l'inverse de celui qu'on redoutait.** Mesuré le 2026-09-10 et consigné dans `INFRA-10` : `veille-deploiement.sh` sort en « rien à faire » AVANT d'appeler `deployer.sh`, donc une édition en place sur le serveur ne déclenche rien tant que `main` n'a pas bougé — ni avertissement, ni témoin, ni unité rouge. Le refus tombe le jour où l'on pousse, c'est-à-dire au moment précis où l'on voulait déployer. Décider si la garde doit remonter dans la veille, ou si ce blocage différé est accepté par écrit
- [x] **Le chantier est visible sur la fresque** — `dbb67d1` (2026-09-10) cite INFRA-12 et touche du code (les deux modules de tests), donc il DATE. C'était la seule chose qui pouvait le rendre visible : les commits antérieurs sont poussés et leur sujet ne se réécrit pas

## Ce que la nomenclature laisse derrière — 2026-09-10

**Le code INFRA-7 a désigné deux chantiers pendant trois jours**, et l'arbitrage du
2026-09-10 a donné celui-ci au sujet neuf : la session garde `INFRA-7`, qui le détenait
depuis le 2026-09-05 ; le contrôle de déploiement prend `INFRA-12` et reçoit cette fiche,
la première qu'il ait jamais eue.

**Ce que ça coûte, et qui ne se répare pas.** `87544ba` porte « INFRA-7 » dans son sujet,
il est poussé, et l'outil date un chantier en cherchant son code dans les sujets de commit.
La fresque montrera donc `INFRA-7` — la session — travaillée le 2026-09-07 pour du code de
déploiement, indéfiniment. C'était le coût de l'option retenue, il était connu au moment de
choisir, et l'autre option en avait un strictement symétrique : `0914094` aurait de la même
façon daté le déploiement pour du travail de session.

**Ce qui a fait pencher** : aucune fiche n'est renommée, donc aucune référence extérieure
au dépôt ne casse, et la fiche qui détenait le code légitimement le garde.

## Contexte

**Quatre scripts et deux modules de tests vivaient sans fiche.** `deploy/deployer.sh` et
`deploy/verifier_deploiement.py` d'un côté ; `deploy/veille-deploiement.sh` appartient à
`INFRA-10` et `deploy/verifier_comptes.py` à `INFRA-11`, tous deux fichés. Le tronc n'avait
rien : `deployer.sh` est né sans code, `verifier_deploiement.py` sous `INFRA-1` — c'est-à-dire
sous le chantier de la mise en production, qui l'a produit en passant.

**Pourquoi un chantier sans fiche finit par en emprunter une.** Le travail a continué : une
garde d'arbre sale, un durcissement du contrôle, la version servie qui sort du script. Chaque
fois qu'il fallait un code de commit, celui qui traînait à portée a servi — et c'est ainsi
qu'un chantier sur la durée des sessions s'est retrouvé à porter le contrôle de déploiement.
Ce n'est pas une négligence de nommage, c'est ce qui arrive mécaniquement quand du travail
réel n'a nulle part où s'attacher.

**Voisinage.** `INFRA-1` (la mise en production, qui a produit `verifier_deploiement.py`),
`INFRA-10` (la veille qui APPELLE `deployer.sh`, et où la garde tardive est consignée),
`INFRA-11` (le contrôle du fichier des comptes, l'autre garde de déploiement), `INFRA-9`
(la passe où le défaut de `--url` seul a été mesuré), `INFRA-7` (la durée de session, qui
garde le code et n'a jamais parlé de déploiement).
