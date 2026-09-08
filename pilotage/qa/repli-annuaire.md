---
passe: Repli de l'annuaire vers le fichier
chantier: AUTH-7
duree: 40 min
derniere: 2026-09-07
---

# QA — le retour arrière existe-t-il ailleurs que dans un commentaire

**La bascule est faite, le repli est écrit, et personne ne l'a exécuté.** Les deux blocs
sont dans `deploy/authelia/configuration.yml`, l'un actif, l'autre commenté juste en
dessous, et le commentaire promet que le retour arrière « tient en l'inversion des deux
commentaires suivie d'un redémarrage d'Authelia ». C'est peut-être vrai. Ce n'est pas
vérifié, et cette fiche oppose ailleurs la réserve exacte qui s'applique ici : *un repli
qu'on n'a pas déclenché n'est pas un repli*. La leçon du notifier SMTP, qu'on n'a su bon
qu'en vidant `SMTP_ADRESSE` pour de bon.

**Ce que la passe teste vraiment, et qui n'est pas la mécanique.** Inverser deux
commentaires marchera ou ne marchera pas, et `validate-config` le dira en dix secondes. La
question coûteuse est ailleurs : `users_database.yml` est resté sur le disque comme
recours, ses condensés sont ceux d'AVANT la bascule, et **rien ne dit que quelqu'un
connaisse encore les mots de passe qui vont avec**. Un fichier qu'on garde par prudence et
dont personne n'a la clé n'est pas un recours : c'est une porte peinte sur un mur. C'est la
forme habituelle du défaut dans ce dossier — un dispositif qui rassure en regardant
ailleurs.

**Et le repli PERD DES GENS, silencieusement.** Aujourd'hui les deux backends portent les
mêmes logins, parce que le temps 1 les a recréés à l'identique. Dès la première personne
inscrite dans LLDAP après le 2026-09-07, ce n'est plus vrai, et rien ne le signalera : le
repli authentifiera correctement une population plus petite, ce qui ressemble à un succès.
La passe DATE cette coïncidence pendant qu'elle tient encore.

**Elle coupe le portail pour tout le monde, brièvement.** À faire quand personne ne
travaille, et à froid — pas le jour où il faudra. Le recours en cas de faux pas est le
shell : on n'est jamais enfermé dehors tant qu'on a la machine.

## Reste

### Avant que la serrure tourne
- [ ] **On sait si la veille de déploiement TOURNE, au lieu de le supposer** — `systemctl list-timers bd-deploiement.timer --all`. Attendu au 2026-09-07 : elle n'est PAS installée, `INFRA-10` portant en tête « il n'a jamais tourné sur le VPS » et ses trois cases de pose restant ouvertes. La case se coche donc en le VÉRIFIANT, pas en le relisant : cette passe a été écrite en croyant l'inverse, sur la seule lecture de `deploy/systemd/`, et l'erreur a coûté un déploiement annoncé qui n'a pas eu lieu
- [ ] L'arbre est PROPRE au départ — `git status --short` ne rend rien. Sans ce point de comparaison, on ne saura pas à la fin si l'on a tout remis en place ou seulement ce dont on se souvient
- [ ] **Le mot de passe à employer est celui d'AVANT la bascule, pas celui d'aujourd'hui.** `users_database.yml` porte les condensés figés au 2026-09-07 : les mots de passe TEMPORAIRES posés à la création des comptes. Ceux qui ont été choisis depuis vivent dans LLDAP et n'ont jamais touché ce fichier. **C'est le piège de faux négatif de cette passe** — essayer son mot de passe courant échouera, et l'on conclura que le repli est mort alors qu'on aura simplement présenté la mauvaise clé
- [ ] **Ce que la rotation ne ferme pas, si elle a lieu un jour.** Changer un mot de passe dans LLDAP ne touche pas ce fichier : son condensé reste celui d'avant, et basculer sur le repli le RÉADMET. Attendu : ou bien le condensé est regénéré ici aussi, ou bien c'est écrit et assumé. Aujourd'hui c'est sans gravité — les valeurs concernées sont des mots de passe temporaires déjà remplacés (constaté par l'équipe le 2026-09-07) —, mais la propriété tiendra encore le jour où elles ne le seront plus. Et `verifier_comptes.py` ne dira rien : il approuve une syntaxe, jamais une fraîcheur
- [ ] **Une clé existe, et elle est en main.** Attendu : on nomme le login qu'on emploiera et l'on produit son mot de passe depuis le gestionnaire — pas « ce devait être l'ancien ». **Si personne ne l'a, la passe s'arrête ici, et c'est un RÉSULTAT** : le repli est nominal, et il faudra régénérer un condensé avant de le réputer disponible
- [ ] **Le fichier de repli est encore LISIBLE par Authelia** — `python3 -c "import yaml; yaml.safe_load(open('users_database.yml'))"`, depuis `~/BD_ditor/deploy/authelia`. Ce n'est pas une précaution de forme : **`validate-config` ne lit PAS ce fichier** (mesuré le 2026-09-06 en y glissant une tabulation — « successfully », code 0), et depuis la bascule PLUS RIEN ne le lit. Une faute qu'on y aurait laissée est donc latente, et ne se découvrirait qu'au redémarrage, c'est-à-dire au pire moment. Un fichier cesse d'être contrôlé à l'instant précis où il cesse de servir
- [ ] La syntaxe ne suffit pas, et c'est la panne du 2026-09-06 à 22:43 : un condensé portant le préfixe `Digest: ` rendu par `crypto hash generate` donne un YAML parfaitement valide et une VALEUR invalide — Authelia boucle au démarrage, six minutes de portail fermé. Attendu : aucune valeur de `password:` ne commence par autre chose que `$argon2id$`. À vérifier SANS afficher les condensés
- [ ] La clé se vérifie SANS rien casser, ou l'on constate qu'elle ne se vérifie pas. Attendu à confirmer : `authelia crypto hash validate` existe en 4.39.22 et accepte le condensé en argument en demandant le mot de passe À L'INVITE — la commande exacte est recopiée ici telle qu'elle a répondu. **Jamais `--password` sur la ligne de commande** : l'historique du shell la garde

### La bascule vers le fichier
- [ ] `validate-config` accepte la configuration inversée, **dans un conteneur jetable**, AVANT tout redémarrage. C'est la garde qui a évité une coupure le 2026-09-07 en refusant le bloc `ldap:` privé de ses variables — la première fois qu'on l'employait
- [ ] Authelia redémarre et son journal dit `Startup complete`. Un conteneur qui reste debout n'est pas une preuve : Authelia peut se lever et refuser toute authentification
- [ ] **Le compte du fichier entre pour de bon** — jusqu'à l'application, pas jusqu'au portail. Attendu : `bd.edito-revue.fr` s'ouvre sur l'Atelier — la racine sert `index.html`, pas la Bibliothèque — avec du corpus visible
- [ ] Le second facteur est demandé, et **l'appareil DÉJÀ enrôlé le satisfait**. C'est la propriété que la bascule aller a confirmée dans l'autre sens (stockage indexé par login, indépendant du backend) ; rien ne garantit qu'elle soit symétrique, et c'est une déduction tant qu'on ne l'a pas mesurée
- [ ] **`Remote-Groups` porte encore `bd-admins`** — et la source a changé : les groupes viennent maintenant des lignes `groups:` du fichier, plus du `memberof` de l'annuaire. Attendu : le panneau 👥 Collections s'ouvre et la vue des comptes s'affiche. Si les deux listes ont divergé, on se connecte parfaitement et l'on n'administre plus rien
- [ ] **Combien de temps le portail a-t-il été fermé** — mesuré, du redémarrage à la première connexion réussie, pas estimé. C'est ce chiffre qui décide si ce repli est utilisable à trois heures du matin ou seulement en journée

### Le retour à l'annuaire
- [ ] `validate-config` d'abord, ici aussi. Le sens du retour n'est pas plus sûr que celui de l'aller, et c'est précisément au retour qu'on est pressé
- [ ] Un compte LLDAP entre de nouveau, second facteur compris. La passe n'a aucune valeur si elle laisse l'instance dans l'état qu'elle voulait pouvoir quitter
- [ ] **L'arbre est propre** — `git status --short` ne rend rien, exactement comme au départ. Un `git checkout -- deploy/authelia/configuration.yml` suffit ; le vérifier est ce qui distingue « remis » de « cru remis »
- [ ] **Si la veille tournait**, elle est relancée et son tir suivant est vert (`systemctl status bd-deploiement`). Une veille laissée arrêtée est le pire résidu possible de cette passe : l'instance cesse de se déployer et rien ne le dit — le déploiement continue de « marcher » en ne faisant plus rien. **Tant qu'INFRA-10 n'est pas posé, cette case est sans objet et il faut le CONSTATER** plutôt que la cocher par habitude ; le jour où le timer existera, elle redeviendra la plus importante des quatre

### Ce qu'on ne peut pas déduire, et qu'il faut consigner
- [ ] **La liste des logins présents dans les DEUX backends est écrite ici, avec sa date.** Attendu au 2026-09-07 : les mêmes des deux côtés, le temps 1 les ayant recréés à l'identique. C'est cette coïncidence qui rend le repli complet, et elle expire à la première inscription faite dans l'annuaire seul
- [ ] La conséquence est reportée dans `AUTH-7` : soit le repli est déclaré PARTIEL par écrit, soit toute création dans l'annuaire s'accompagne d'une ligne dans le fichier. La seconde option rétablit le geste en console que ce chantier veut supprimer — ce n'est donc pas un détail d'exploitation, c'est un arbitrage
- [ ] La commande d'ajout au repli répond bien telle qu'elle est écrite. Les quatre fichiers qui nommaient `authelia/authelia:4.38` sont alignés sur `4.39.22` le 2026-09-07 (`test_une_seule_version_d_authelia_est_documentee` interdit la dérive), et la forme est passée à `-it` — mais alignée n'est pas éprouvée : personne n'a lancé la commande corrigée. C'est là qu'on ira le jour où il faudra ajouter un compte au repli

## Où reportent les constats

Une clé INTROUVABLE ne rouvre pas cette passe : elle transforme la case ouverte d'`AUTH-7`
(« le retour arrière n'a pas été éprouvé ») en une case plus dure — le repli n'existe pas,
et il faut décider si on le rétablit ou si on l'abandonne par écrit. Garder un fichier dont
personne n'a la clé en le nommant « recours » est la seule réponse à exclure.

Un repli qui MARCHE ferme la case, et le chiffre de coupure va dans `docs/exploitation.md`
avec les autres gestes d'exploitation : c'est ce qu'on lira le jour où l'annuaire tombera,
et il n'a de valeur que mesuré sur cette instance-ci.

La divergence des POPULATIONS reporte dans `AUTH-7` quoi qu'il arrive, y compris si tout
s'est bien passé — c'est le seul constat de cette passe qui se dégrade tout seul avec le
temps, et le seul dont l'absence de signal est le problème.
