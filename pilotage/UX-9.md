---
chantier: UX-9
statut: à venir
---

# UX-9 — signaler un problème, et que le rapport porte son diagnostic

**Point de départ** — 2026-09-06, en réécrivant le bandeau de portée vide. Le bandeau
expliquait à un stagiaire que « le proxy pose `Remote-User` sans `Remote-Groups` » : un
message d'exploitation montré à quelqu'un qui n'en peut rien. Il est devenu humain, et le
détail technique a été retiré de l'écran — **mais il doit aller quelque part.** Un
signalement est le véhicule : ce que la personne bloquée ne peut pas lire, le rapport le
transporte à qui sait le lire.

## Reste

### Ce que le signalement transporte
- [ ] Un signalement déposé depuis n'importe quelle surface porte la surface, l'URL,
      `BD_COMMIT`, le navigateur et la taille de fenêtre SANS que la personne les saisisse
      — vérifié en relisant le rapport en base après un clic
- [ ] Il porte le bloc `acces` de `GET /api/moi` — identité, groupes reçus, portée — de
      sorte qu'un rapport venu d'une portée vide contienne à lui seul le diagnostic
      qu'AUTH-1 affichait à l'écran avant ce chantier
- [ ] Le champ libre est le SEUL que la personne remplit : un rapport utile part sans
      qu'elle sache décrire une panne, ce qui est le but — mesuré en déposant un rapport
      au texte vide et en vérifiant qu'il reste exploitable

### Qui peut signaler, qui peut lire
- [ ] Déposer exige une IDENTITÉ et aucun droit : derrière le proxy, une portée VIDE
      dépose et reçoit 201 ; sans identité, 403 nommant la panne. Même patron que la
      création de collection (AUTH-2), pas une politique neuve
- [ ] Lire les signalements est réservé aux administrateurs : un membre en écriture sur
      toutes ses collections reçoit 403 sur la route de liste
- [ ] La garde porte sur l'ACTE et pas seulement sur l'écran qui le contient — un test
      appelle la route de liste directement, sans passer par le panneau. C'est l'erreur
      d'AUTH-4, où le référent avait hérité de la garde du partage par défaut

### Ce qu'on n'attache pas, et pourquoi
- [ ] La capture d'écran est TRANCHÉE par écrit — écartée, ou bordée par une règle qui dit
      ce qu'il advient de l'image d'une planche sous embargo. La fiche ne se clôt pas sur
      un « à voir » : DROIT-1 borde les images en sortie, et une pièce jointe serait un
      canal que personne n'a bordé
- [ ] Les journaux serveur restent hors du rapport, la raison écrite dans le code : ils
      NOMMENT les agents (A3), quand tout artefact qui quitte l'instance pseudonymise
      (AUTH-1)
- [ ] Un test balaie les champs stockés d'un rapport et échoue sur toute donnée d'image,
      ainsi que sur tout nom d'agent autre que l'auteur du rapport

### Le geste et sa base
- [ ] Le bouton est atteignable depuis les quatre surfaces, au clavier, et son libellé dit
      ce qu'il fait sans jargon — audité par axe comme les autres surfaces
- [ ] Un dépôt qui échoue (réseau coupé, base verrouillée) le DIT à la personne au lieu de
      disparaître en silence : le 409 de contention SQLite est déjà traité ailleurs, il
      doit l'être ici aussi
- [ ] `SCHEMA_VERSION` est incrémentée avec son étape dans `_migrate()`, et une base
      existante se migre sans perte — vérifié en rejouant la migration sur une copie de la
      sauvegarde de production

## Contexte

**Pourquoi maintenant.** Le bandeau de portée vide disait trois choses à la fois : que
l'écran n'est pas cassé, quoi faire, et pourquoi techniquement. La troisième ne s'adresse
pas au même lecteur que les deux premières. On l'a retirée de l'écran le 2026-09-06 ; sans
un canal de retour, on l'a simplement perdue.

**Le vrai gain n'est pas le bouton, c'est le CONTEXTE AUTOMATIQUE.** Une personne qui ne
comprend pas ce qui lui arrive ne saura pas décrire sa panne, et c'est normal — c'est la
raison d'être de la salve d'e-mails illisibles qu'on veut éviter. Ce qui rend un rapport
exploitable, elle ne peut pas le taper : la surface, la version en service, la portée
qu'on lui a accordée, les groupes que le proxy a réellement posés. Tout cela est déjà
disponible côté serveur au moment du clic.

**Deux pièces jointes évidentes sont écartées ou à border, et c'est le cœur du chantier.**
La capture d'écran est la plus tentante et la plus dangereuse : sur la Visionneuse, c'est
l'image d'une planche numérisée. DROIT-1 décide que les images ne sortent que pour une
collection déclarée `public`, par un manifeste nommé et daté ; une pièce jointe ouvrirait
un second chemin, non déclaré, y compris pour une collection sous embargo. Même en restant
dans l'instance, elle deviendrait lisible par qui lit les rapports — c'est-à-dire par
dessus le cloisonnement d'AUTH-2. Les journaux serveur posent le problème symétrique :
le journal A3 nomme les agents, et le dépôt pseudonymise à chaque export précisément pour
que l'activité d'une personne ne voyage pas sous son nom.

**Où ça vit.** En base, avec un panneau d'administration dans la Bibliothèque, à côté de
👥 Collections et 🩺 Moteurs. Pas d'e-mail — c'est ce qu'on fuit —, pas de traqueur
externe : envoyer du contexte de corpus à un tiers contredirait « auto-hébergé,
traitement local », et l'entrepôt du figé, c'est Nakala, pas un service de tickets.

**Le piège d'autorisation, et il a un précédent.** La personne la plus susceptible de
cliquer est celle dont la portée est VIDE — elle ne peut écrire nulle part. Si le dépôt
passait par le contrôle d'écriture ordinaire, le bouton serait inutilisable exactement
pour qui en a besoin. AUTH-2 a déjà tranché ce cas pour la création de collection :
« créer une collection exige une IDENTITÉ, pas un droit ». On reprend la règle, on n'en
invente pas.

**Ce que ce chantier ne fait pas.** Il ne remplace pas un traqueur de bugs pour l'équipe
de développement : il collecte ce que les UTILISATEURS rencontrent, sur une instance en
service. Le suivi fin, les priorités et les correctifs restent dans `pilotage/`.

**Voisinage.** AUTH-1 (le diagnostic des trois situations, dont ce chantier devient le
destinataire), AUTH-2 (identité vs droit), AUTH-4 (le référent d'instance, qui reste la
voie humaine et ne disparaît pas), DROIT-1 (les images en sortie), SANTE-1 (le panneau
🩺 Moteurs, dont le panneau des signalements est le voisin d'écran).
