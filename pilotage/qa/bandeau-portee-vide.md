---
passe: Bandeau de portée vide
chantier: AUTH-8
duree: 10 min
derniere: 2026-09-11
---

# QA — ce que le bandeau dit à qui n'a aucune collection

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`. Une fenêtre privée par
identité. Le référent de la recette est « Référent de recette », `referent@exemple.fr`.

**Ce que la passe éprouve.** Le bandeau distingue quatre situations sur le fil. Deux se
jouent ici avec de vrais comptes : un compte SANS aucun groupe, et un compte AVEC des
groupes dont aucun n'a d'accès. La mesure du 2026-09-09 disait que, sur ce déploiement, un
compte sans groupe ne reçoit pas l'en-tête des groupes du tout, au lieu de le recevoir vide.
Le bandeau doit le rapporter sans accuser le proxy.

### Un compte sans groupe
- [ ] Sous `arrivant`, l'Atelier affiche le bandeau « Aucune collection ne vous est ouverte. », REPLIÉ : il ne se déplie pas tout seul
- [ ] Déplié, il dit « Rien n'est cassé : l'accès se donne collection par collection. », puis « Demandez un accès à Référent de recette — referent@exemple.fr »
- [ ] Sa ligne technique dit « En-tête Remote-Groups non reçu. Sur ce déploiement, un compte sans aucun groupe donne le même résultat (mesuré le 2026-09-09) : l'absence ne distingue pas les deux. » — et rien n'y envoie « vérifier côté proxy »
- [ ] La Bibliothèque est vide, sans message d'erreur

### Un compte avec des groupes, sans accès
- [ ] Sous `invite`, même bandeau replié, même titre
- [ ] Sa ligne technique dit « Groupes reçus : invites. »

### Un compte qui a un accès
- [ ] Sous `lectrice`, aucun bandeau, et « esther v1 » est dans la Bibliothèque

### La réponse écrite
- [ ] Dans `docs/modele-et-droits.md`, la FAQ (§7) dit qu'une liste de groupes « non transmise » n'est PAS forcément une panne, et le tableau des situations (§6) dit que, sur cette instance, un compte sans aucun groupe produit la même chose : c'est ce que le bandeau d'`arrivant` vient d'afficher
