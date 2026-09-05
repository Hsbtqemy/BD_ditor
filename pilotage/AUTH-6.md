---
chantier: AUTH-6
statut: à venir
---

# AUTH-6 — le modèle de comptes et de groupes, avant les stagiaires

**Point de départ** — 2026-09-05. Le cadrage appartient à l'utilisateur du dépôt, qui l'a
annoncé et le rendra ; cette fiche note les questions que le CODE pose à ce cadrage, et
deux pièges que le modèle actuel ne signale pas.

## Reste

### À trancher (hors code — la décision revient à l'équipe)
- [ ] Combien de comptes, et lesquels sont NOMMÉS : un compte par personne est la condition d'ANN-5 (accord inter-annotateurs) et de tout le journal A3 — un compte partagé fait de plusieurs personnes une seule dans la provenance, sans que rien ne le dise
- [ ] Quels groupes existent, et ce que chacun signifie en termes de collections — un groupe n'est utile que s'il reçoit des accès ; un groupe sans ligne dans `collection_acces` ne change rien
- [ ] Ce qui se passe quand quelqu'un CHANGE de groupe en cours de route : l'accès suit immédiatement, la provenance non — et c'est correct, mais il faut le vouloir
- [ ] Combien d'administrateurs, sachant qu'un membre de `bd-admins` court-circuite entièrement `collection_acces` (AUTH-4) et voit tout le corpus

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
