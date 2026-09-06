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
- [ ] **Le réglage restera-t-il sur le SERVEUR ?** Donner ou retirer le second facteur à quelqu'un, c'est aujourd'hui éditer `users_database.yml`, contrôler le YAML et redémarrer Authelia. L'application ne peut pas le faire à sa place sans cesser d'être ce qu'elle est : elle N'AUTHENTIFIE PERSONNE (AUTH-1), et lui confier la base d'authentification effondrerait tout le raisonnement de sécurité. Une interface d'administration des comptes serait donc un outil DISTINCT, parlant au fichier d'Authelia — chantier à part entière, et c'est la friction nommée le 2026-09-05 : « s'il faut sortir du site à chaque fois »

### Deux pièges à vérifier dans le code
- [ ] Ce que devient un accès dont le GROUPE a été renommé ou supprimé dans `users_database.yml` : `collection_acces` stocke une RÉFÉRENCE au nom du groupe, jamais une appartenance — la ligne survit donc à un groupe qui n'existe plus, et personne ne la relie à rien. Attendu à écrire : le panneau le signale, ou bien on documente qu'il ne le fait pas
- [ ] Ce qu'une collection devient quand son unique propriétaire perd son groupe : la base refuse le zéro-propriétaire par un 409, mais ce refus porte sur une SUPPRESSION d'accès, pas sur une appartenance qui s'évapore côté Authelia. `bd-admins` est le recours prévu ; vérifier qu'il suffit

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

**Le backend fichier a une limite non mesurée.** `users_database.yml` convient à une petite
équipe ; à partir de quel nombre de comptes l'édition à la main devient-elle le goulot ?
La question se pose avec INFRA-8 (notifier SMTP), qui rend l'enrôlement délégable.
