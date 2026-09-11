---
passe: Compte collectif et Ctrl+Z borné
chantier: AUTH-6
duree: 20 min
derniere: 2026-09-11
---

# QA — un login partagé se déclare, et Ctrl+Z se borne à cinq minutes

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io` (certificat de recette
à accepter une fois). Les mots de passe sont remis par la session qui a monté la pile. Une
fenêtre privée par identité : une session Authelia est partagée par tous les onglets d'une
même fenêtre.

**Ce que la passe éprouve.** Sous un login partagé, l'agent du journal ne désigne plus une
personne : sans borne, n'importe qui défait par Ctrl+Z l'acte d'un collègue. La borne ne
s'applique qu'à un compte DÉCLARÉ collectif, et c'est la déclaration qu'il faut voir
fonctionner. `collectif` écrit sur « Collection Test » par son groupe `etudiants`.

**Une seule attente de plus de cinq minutes**, si l'on suit l'ordre : deux régions posées
avant, et c'est la déclaration faite APRÈS l'attente qui change la réponse de Ctrl+Z.

### Avant la déclaration
- [ ] Sous `collectif` (mot de passe seul, sans second facteur), l'Atelier ouvre « esther v1 » et ses planches s'affichent
- [ ] En mode Édition, deux régions sont posées sur une même planche, l'une après l'autre — noter l'heure
- [ ] Plus de cinq minutes plus tard, toujours sous `collectif`, Ctrl+Z hors d'un champ de saisie défait la SECONDE région : un compte non déclaré n'a aucune borne

### La déclaration
- [ ] Sous `admin-bd` (second facteur TOTP ; le code d'enrôlement de la première fois est écrit dans `authelia/notification.txt` de la pile), Administration → 👤 Comptes vus liste `collectif`
- [ ] Son sélecteur passe de « Nominatif (une personne) » à « Collectif (login partagé) », et le texte du panneau dit que Ctrl+Z n'y remonte que les cinq dernières minutes, et qu'aucun droit d'accès n'en dépend
- [ ] Sous `collectif`, Ctrl+Z ne défait PAS la première région, vieille de plus de cinq minutes, et un message neutre (pas une erreur rouge) dit « Rien à annuler dans les 5 dernières minutes : sur un compte partagé, Ctrl+Z ne remonte pas plus loin. »
- [ ] Toujours sous `collectif`, une troisième région posée puis Ctrl+Z aussitôt : elle disparaît. La borne n'empêche pas l'annulation récente

### Témoin
- [ ] Sous `proprio`, compte nominatif, une région posée pendant la même attente de cinq minutes, puis Ctrl+Z : elle disparaît. Ce qui borne est la nature du compte, pas l'instance

Pour rejouer la passe à neuf, remettre `collectif` en « Nominatif (une personne) » à la fin.
