---
passe: La fin d'une grille, et le rouge du tableur
chantier: ANN-7
duree: 15 min
---

# QA — désactiver, supprimer, retirer une grille ; le tableur rougit la case fautive

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur `a9f453f`
(« ANN-7 : une grille se supprime, se retire et se désactive depuis l'écran ») ou après, état
`apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`).
Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`, hors dépôt. Tout se joue sous
`proprio`, responsable de « Projet principal », dans une fenêtre privée à 1 280 px de large.
Le tableur demande Excel.

**Ce que la passe éprouve** — deux remarques de Hugo du 2026-11-13, pendant la passe
`qa/grille-sans-defaut.md`. Le serveur savait supprimer une grille que rien n'emploie, retirer
une grille employée et supprimer un brouillon, mais l'écran ne l'offrait pas ; le formulaire
offrait « Activer » sans « Désactiver ». Et la case fautive du tableur ne rougissait pas dans
Excel : la règle était juste, sa couleur ne se peignait pas.

**Rejouée par la session le 2026-11-14**, dans un Chromium à 1 280 px sous `proprio`, sur une copie de l'état `apres-moustache` migrée en v39, code de `596ec30` : les zones « Désactiver depuis le formulaire » et « Supprimer, retirer, depuis la ligne d'une grille », leurs phrases telles que l'écran les dit, « Rouge QA » créée par la route plutôt que par le formulaire. Une différence de décor seulement : la copie portait des étiquettes du Mode libre, si bien que « Travail en cours » offrait « Retirer… » grisé au lieu de « Supprimer… » grisé — sur le décor restauré, vide, c'est « Supprimer… ». Le rouge du tableur avait été mesuré dans Excel le 2026-11-14 au matin (`pilotage/ANN-7.md`, case du classeur).

**Le décor de l'état restauré.** « Sons et images (fictive) » est la grille de « Projet
principal » : fermée, v1 publiée et active, 3 relevés posés. « Travail en cours » est sa
grille de travail (le mode libre), active, sans relevé.

### Le rouge du tableur, sous `proprio`
- [ ] Administration → Projets → « Projet principal », bloc « Grilles », « + Construire une grille », « Rouge QA », Tab, « Créer la grille » ; « + Entrée » « escalier », Tab, question 2 « La case » : dans le plan, « escalier » ne dit plus « ● à compléter »
- [ ] « ⤓ Tableur » dans la tête du formulaire, ouvert dans Excel, feuille « 2. Les entrées » : vider « 2. Se pose sur » d'« escalier » : la case devient rouge pâle ; y remettre « la case » : elle redevient blanche. Fermer Excel sans enregistrer

### Désactiver depuis le formulaire, sous `proprio`
- [ ] « ← Projet principal », « Modifier… » sur « Sons et images (fictive) » : la tête offre « Désactiver » après « ⤒ Réimporter… » ; cliquer : un message dit « La grille n'est plus active : ses relevés restent, en lecture. », la puce dit « v1 publiée · pas active », et « Activer la v1 » remplace « Désactiver »
- [ ] « Activer la v1 » : la puce dit « v1 publiée · active », et « Désactiver » revient
- [ ] « ← Projet principal », « Modifier… » sur « Travail en cours » : « Désactiver » est grisé, et son survol dit « C'est la grille de travail du projet, qui porte son mode libre : elle ne se désactive, ne se retire ni ne se supprime. » ; le cliquer redit cette phrase, et la puce reste « ouverte · active »

### Supprimer, retirer, depuis la ligne d'une grille, sous `proprio`
- [ ] « ← Projet principal », bloc « Grilles » : la ligne de « Rouge QA » finit par « Supprimer… » ; celle de « Sons et images (fictive) » par « Retirer… » grisé, dont le survol dit « Elle est active dans le projet : désactivez-la d'abord. » ; celle de « Travail en cours » par « Supprimer… » grisé, dont le survol dit « C'est la grille de travail du projet… »
- [ ] « Supprimer… » sur « Rouge QA » : sous la ligne, un cadre dit « « Rouge QA » part : personne ne l'emploie, aucun relevé ne se perd. Ce geste ne s'annule pas. », avec « Supprimer la grille » et « Annuler » ; « Annuler » : le cadre disparaît, et rien d'autre ne change
- [ ] « Supprimer… », puis « Supprimer la grille » : la ligne de « Rouge QA » disparaît, un message dit « « Rouge QA » est supprimée. », et le titre du bloc compte une grille de moins
- [ ] « Modifier… » sur « Sons et images (fictive) », l'entrée « cri », ajouter un mot à sa définition, Tab : la puce dit « v1 publiée · active · brouillon v2 » ; « ← Projet principal » : la ligne offre « Supprimer le brouillon v2… »
- [ ] « Supprimer le brouillon v2… » : le cadre dit « Le brouillon v2 part, avec tout ce qu'il change. Les versions publiées restent. » ; « Supprimer le brouillon v2 » : la puce redit « v1 publiée · active », et « Supprimer le brouillon v2… » n'est plus offert
- [ ] « Désactiver » sur « Sons et images (fictive) », puis « Retirer… » : le cadre dit « Retirée, « Sons et images (fictive) » ne s'active plus et ne reçoit plus de version. 3 relevés restent lisibles. Ce geste ne s'annule pas. »
- [ ] « Retirer la grille » : un message dit « « Sons et images (fictive) » est retirée : ses relevés restent lisibles. », la puce dit « retirée », et la ligne n'offre plus que « ⤓ le classeur v1 » (ni « Modifier… », ni « Activer la v1 », ni « Retirer… »)
