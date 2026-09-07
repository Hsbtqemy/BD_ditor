---
chantier: AUTH-6
statut: à venir
---

# AUTH-6 — le modèle de comptes et de groupes, avant les stagiaires

**Point de départ** — 2026-09-05. Le cadrage appartient à l'utilisateur du dépôt, qui l'a
annoncé et le rendra ; cette fiche note les questions que le CODE pose à ce cadrage, et
deux pièges que le modèle actuel ne signale pas.

**Un premier morceau a été pris le 2026-09-06, parce qu'il bloquait une arrivée**, et il
contraint la suite. `two_factor` partout exigeait de chacun une application
d'authentification sur un téléphone lui appartenant, ce qui poussait vers un COMPTE
PARTAGÉ — dont le coût est invisible ici : `undo.py` filtre l'annulation par AGENT (Ctrl+Z
défait l'action d'un collègue), l'accord inter-annotateurs n'a plus rien à mesurer, et le
journal de provenance aplatit les chaînes de révision. D'où : comptes NOMINATIFS en
`one_factor`, second facteur maintenu pour `bd-admins` et sur `/api/sauvegarde`. Détail et
raisons dans `INFRA-8`. Ce chantier peut le défaire, mais en connaissant ce qu'il paie.

## Reste

### À trancher (hors code — la décision revient à l'équipe)
- [ ] Combien de comptes, et lesquels sont NOMMÉS : un compte par personne est la condition d'ANN-5 (accord inter-annotateurs) et de tout le journal A3 — un compte partagé fait de plusieurs personnes une seule dans la provenance, sans que rien ne le dise
- [ ] Quels groupes existent, et ce que chacun signifie en termes de collections — un groupe n'est utile que s'il reçoit des accès ; un groupe sans ligne dans `collection_acces` ne change rien
- [ ] Ce qui se passe quand quelqu'un CHANGE de groupe en cours de route : l'accès suit immédiatement, la provenance non — et c'est correct, mais il faut le vouloir
- [ ] Combien d'administrateurs, sachant qu'un membre de `bd-admins` court-circuite entièrement `collection_acces` (AUTH-4) et voit tout le corpus

- [ ] **Le second facteur se règle-t-il compte par compte, et selon quoi ?** Techniquement c'est un GROUPE — `subject: ['group:bd-admins', 'group:bd-2fa']` dans `access_control` —, et le sens du réglage se choisit : opt-in vers le fort (le défaut reste `one_factor`, l'appartenance renforce) plutôt qu'un groupe « dispensé », où un oubli affaiblirait quelqu'un en silence. Non posé le 2026-09-06 exprès : aucun cas intermédiaire n'existe encore, et un mécanisme de sécurité sans utilisateur est un mécanisme que personne ne vérifie
- [ ] **Ou le facteur dépend-il de la COLLECTION plutôt que de la personne ?** Une collection sous embargo ou à base légale non établie appelle peut-être un second facteur que le corpus libre n'exige pas. Cette lecture-là rendrait le groupe ci-dessus inutile — les deux s'excluent, et c'est ce chantier qui tranche
- [ ] **L'OUTILLAGE de ce modèle est parti dans `AUTH-7`** — administrer les comptes sans console, demandé le 2026-09-06. Les deux se lisent ensemble : choisir un annuaire avant de savoir quels groupes on veut serait absurde, arrêter un modèle sans savoir ce qu'il coûtera à administrer aussi
- [ ] **Le réglage restera-t-il sur le SERVEUR ?** **La question s'est COUPÉE EN DEUX le 2026-09-07 (AUTH-7), et une moitié seulement a sa réponse.** L'APPARTENANCE à un groupe se change désormais dans l'interface web de LLDAP, derrière Authelia et réservée à `bd-admins` : plus de shell, plus de YAML, plus de redémarrage — c'est exactement la friction nommée le 2026-09-05 (« s'il faut sortir du site à chaque fois »), et elle tombe. La POLITIQUE, elle, reste un fichier sur le serveur : décider qu'un groupe `bd-2fa` exige un second facteur, c'est éditer `access_control` dans `deploy/authelia/configuration.yml` et redémarrer Authelia — qui relit sa configuration au démarrage du PROCESSUS (INFRA-9). L'application ne peut toujours pas le faire à sa place sans cesser d'être ce qu'elle est : elle N'AUTHENTIFIE PERSONNE (AUTH-1), et lui confier la base d'authentification effondrerait tout le raisonnement de sécurité. Reste donc à trancher la seule moitié qui demeure : la politique bouge-t-elle assez rarement pour qu'un fichier suffise ?

### Les pièges que le modèle ne signale pas
- [ ] Ce que devient un accès dont le GROUPE a été renommé ou supprimé **dans LLDAP** (`users_database.yml` jusqu'au 2026-09-07, AUTH-7) : `collection_acces` stocke une RÉFÉRENCE au nom du groupe, jamais une appartenance — la ligne survit donc à un groupe qui n'existe plus, et personne ne la relie à rien. Attendu à écrire : le panneau le signale, ou bien on documente qu'il ne le fait pas. **Le piège n'a pas changé de nature, il a changé d'écran** — renommer un groupe demandait une session SSH et une relecture de YAML, cela demande maintenant deux clics dans une interface web : le geste qui casse silencieusement un accès est devenu le geste facile, ce qui monte l'intérêt de cette case sans rien changer à son énoncé
- [ ] Ce qu'une collection devient quand son unique propriétaire perd son groupe : la base refuse le zéro-propriétaire par un 409, mais ce refus porte sur une SUPPRESSION d'accès, pas sur une appartenance qui s'évapore côté Authelia. `bd-admins` est le recours prévu ; vérifier qu'il suffit
- [ ] **Un accès accordé à un login que l'application n'a JAMAIS vu le dit** — attendu : après enregistrement, le panneau rapporte l'observation (« ce nom n'a encore ouvert l'application ») sans en nommer la cause, et un test la couvre. **C'est le JUMEAU de la case ci-dessus, et il faut deux cases parce qu'ils ne se mesurent pas pareil** : un groupe supprimé dans LLDAP, l'application ne PEUT pas le détecter — elle ne stocke aucune appartenance et ne lit aucun annuaire, si bien que cette moitié-là appelle une lecture de l'annuaire ou une documentation assumée ; un login jamais vu, la table `utilisateur` le sait déjà, donc c'est faisable aujourd'hui sans rien ajouter. **La branche « on documente » a DÉJÀ été prise pour les logins** (case cochée d'AUTH-3, la phrase sous le formulaire), et c'est ce qui rouvre l'arbitrage plutôt que de le découvrir : cette note vivait dans une modale qu'on ouvrait exprès, elle est depuis le 2026-09-07 sur un écran d'administration (UX-10), où l'on vient précisément pour accorder des accès. Demandé par l'utilisateur du dépôt le 2026-09-07 en découvrant l'écran ; le rapport ne doit PAS prétendre distinguer une faute de frappe d'un arrivant qui n'est pas encore venu — l'application ne le peut pas, et le bandeau de portée vide a été réécrit la veille pour cette raison exacte

### Préparer l'arrivée
- [ ] Un compte stagiaire créé de bout en bout voit un corpus NON VIDE dès sa première connexion — c'est le piège d'AUTH-2, et il est silencieux : la connexion réussit, l'application s'affiche, elle est simplement vide
- [ ] `BD_REFERENT_NOM` / `BD_REFERENT_CONTACT` sont renseignés dans `deploy/.env` AVANT le premier compte non-administrateur : c'est le seul destinataire qu'une portée vide puisse lire, et il n'a de valeur que posé d'avance

## Contexte

**L'invariant à ne pas casser** (AUTH-1) : les groupes ne sont JAMAIS stockés, ils sont
relus dans `Remote-Groups` à chaque requête. Conséquence directe et utile — déplacer
quelqu'un d'un groupe à l'autre dans Authelia prend effet à la requête suivante, sans rien
à synchroniser côté application. Conséquence moins visible : `collection_acces` garde une
référence à un NOM de groupe, et rien ne vérifie que ce nom existe encore.

**Ce que le passage d'un groupe à l'autre ne change pas** : les actes déjà journalisés
restent attribués à la personne qui les a faits. C'est le comportement voulu — une
annotation n'est pas moins la sienne parce qu'elle a changé d'équipe — mais cela veut dire
que la provenance nomme des gens qui n'ont plus accès, et c'est exactement pourquoi les
sorties pseudonymisent (`annotateur-N`, AUTH-1).

**Le backend fichier avait une limite non mesurée, et elle a été tranchée sans jamais être
mesurée.** `users_database.yml` convenait à une petite équipe ; « à partir de quel nombre de
comptes l'édition à la main devient-elle le goulot ? » n'a jamais reçu de chiffre et n'en
recevra pas — AUTH-7 a basculé sur LLDAP le 2026-09-07.

**Et le motif n'était pas le volume**, ce qui vaut d'être gardé parce que l'intuition de
cette page allait dans l'autre sens. Le chiffrage d'AUTH-7 conclut explicitement que le
temps de saisie ne justifie pas la bascule : trente arrivants restent trente formulaires.
Ce qui a décidé, c'est que le geste cessait d'exiger un shell sur le VPS — déléguer la
création d'un compte revenait à déléguer un accès serveur. La limite du backend fichier
n'était pas sa CAPACITÉ, c'était QUI pouvait s'en servir.
