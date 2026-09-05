---
chantier: INFRA-8
statut: à venir
---

# INFRA-8 — l'enrôlement 2FA passe par un fichier sur le serveur

**Point de départ** — 2026-09-05, après le premier enrôlement réel. Il a fallu deux
allers-retours en SSH pour une seule personne.

## Reste

### La bascule
- [ ] Chaque compte de `users_database.yml` porte une adresse RÉELLE — aujourd'hui c'est celle du gabarit (`chercheur@example.fr`), et un notifier SMTP enverrait dans le vide sans le dire
- [ ] Le bloc `notifier.filesystem` est remplacé par `notifier.smtp`, ses identifiants dans `deploy/.env` et non dans un fichier versionné, comme les trois secrets d'Authelia
- [ ] Un compte neuf reçoit son lien d'enrôlement 2FA PAR COURRIEL et va au bout sans intervention sur le serveur
- [ ] Une réinitialisation de mot de passe fonctionne de bout en bout — c'est le vrai gain : aujourd'hui, un mot de passe perdu se répare en SSH
- [ ] Un appareil TOTP perdu se remplace sans SSH : c'est le seul recours quand le second facteur disparaît, et il n'existe pas tant que le notifier écrit dans un fichier

### La conséquence qu'on n'attend pas
- [ ] Des adresses RÉELLES ne changent rien à ce que les artefacts publient : rejouer `tests/test_sorties_identite.py` après la bascule. Le courriel devient une donnée personnelle là où le gabarit n'en était pas une, et il entre dans la base par `Remote-Email` → `utilisateur`, donc dans toute sauvegarde

## Contexte

Le notifier `filesystem` était le bon choix pour démarrer : aucun compte mail requis, aucun
réglage. Il a tenu exactement le temps d'un seul utilisateur.

Pour chaque nouvelle personne, il faut ouvrir une session SSH, lire
`/config/notification.txt`, en extraire la bonne URL — le fichier contient AUSSI un lien de
révocation, et se tromper est facile, c'est arrivé au premier essai — puis la transmettre
par un canal quelconque. Le lien expire en quelques minutes, donc l'opération se fait en
présence de la personne. Ce n'est pas délégable, et cela ne tient pas à cinq stagiaires.

**Ce qui rend la bascule moins anodine qu'elle n'en a l'air** : aujourd'hui, aucune adresse
réelle n'existe nulle part dans la chaîne. Après, il y en a une par compte, elle transite
par `Remote-Email`, elle est écrite dans `utilisateur` (v22) et elle part dans chaque
sauvegarde. AUTH-5 a précisément un cliquet pour ça — il sème une sentinelle de courriel et
balaie 61 surfaces ; il a été écrit parce que l'énumération à la main avait échoué quatre
fois. C'est le moment de le rejouer, pas de lui faire confiance sur parole.
