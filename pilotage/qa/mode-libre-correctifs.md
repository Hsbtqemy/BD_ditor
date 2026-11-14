---
passe: Les correctifs du mode libre — ✎, la liste vide, la trace d'une étiquette
chantier: ANN-7
duree: 25 min
---

# QA — ce que la passe du mode libre du 2026-11-11 a relevé, corrigé

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`e99e062` (« ANN-7 : « figée », la marque des valeurs, rien sous « — »… ») ou après, état
`apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`).
Au démarrage, l'application migre la base en v39. Les mots de passe sont dans
`C:\temp\bd-recette\comptes.txt`, hors dépôt. Fenêtre privée à 1 280 px, page Annotation
(🖍️), album « esther v1 », planche 1, la bulle « Haha coucou Esther » (« b2 · bulle » de la
case c5).

**Les comptes** — `proprio`, responsable du « Projet principal » ; `stagiaire`, annotateur du
même projet. Les zones s'enchaînent dans l'ordre : chacune part de l'état laissé par la
précédente.

**Rejouée par la session le 2026-11-14**, dans un Chromium à 1 280 × 860 sous les deux identités, sur une copie de l'état `apres-moustache` migrée en v39, code de `596ec30` : toutes les cases sauf la dernière, et leurs mots pris à l'écran. « vent » tombait hors de vue dans la liste de ce qui est posé (4e ligne sur trois visibles) : la case qui l'attend restera rouge tant que le correctif n'est pas là.

**Ce que la passe éprouve** — les cases de la passe `qa/mode-libre.md` que Hugo a relevées le
2026-11-11, corrigées par `c6df843` et `e99e062`. Les deux d'« ⟳ Actualiser » se jouent dans
`qa/conflit-du-locuteur.md`. Les choix à confirmer sont écrits sur leurs cases de
`pilotage/ANN-7.md` : la passe les montre, elle ne les tranche pas.

### Le bloc ✎ — `proprio`
- [ ] Onglet « Mode libre », « + Nouvelle étiquette… », `lieu : exterieur`, Entrée : l'étiquette « lieu » naît avec la valeur « exterieur », posée sur la bulle
- [ ] « ✎ » sur « lieu » : le bloc s'ouvre ; Tab jusqu'au champ du nom : l'anneau du focus ne touche pas le cadre du bloc, et le champ ne touche pas la rangée de boutons en dessous
- [ ] Changer le nom en `lieux`, Entrée : « ✓ enregistré » paraît à droite du champ, rien ne bouge autour, et le bloc reste ouvert ; taper une lettre : la marque disparaît
- [ ] Le champ « définition » : y écrire `où se passe la scène`, Entrée : « ✓ enregistré » à sa droite ; « Fini » pour refermer, puis survoler l'étiquette « lieux » : la boîte du guide dit « lieux » et « où se passe la scène »
- [ ] « ✎ », le champ de la valeur « exterieur » : la corriger en `extérieur`, Entrée : « ✓ enregistré » à sa droite, et la puce de la valeur dit « extérieur »
- [ ] « + valeur », taper `cour` touche par touche, Entrée : une valeur « cour » s'ajoute, et aucune valeur « Entrée » n'existe
- [ ] La rangée des gestes dit « Figer » ; le cliquer : la puce d'état dit « ✓ figée », et le bouton dit maintenant « Rouvrir »
- [ ] Sous la dernière étiquette du Mode libre, un espace sépare le bloc ✎ ouvert de l'étiquette qui suit

### Les gestes éteints — `stagiaire`
- [ ] F5, onglet « Mode libre » : le « ✎ » de « lieux » est éteint ; le cliquer dit « « lieux » est figée : seuls les responsables la changent »
- [ ] « + Nouvelle étiquette… », `humeur`, Entrée, puis « ✎ » sur « humeur » : le bloc s'ouvre ; « Passer dans une grille… » est éteint, et le cliquer dit « Passer une étiquette dans une autre grille : les responsables du projet », sans « (J8) » ni aucun code
- [ ] Dans le même bloc, « Figer », « Fusionner dans… » et « Retirer… », éteints, disent chacun leur geste suivi de « : les responsables du projet » (« Figer une étiquette… », « Fusionner des étiquettes… », « Retirer une étiquette… »)

### La liste de ce qui est posé — `stagiaire`
- [ ] « Fini », puis case c7 sur la minicarte : sous « Relevés : … ▾ », rien n'est écrit — ni « — » ni autre chose —, et la ligne garde sa hauteur : la barre de la case ne remonte pas

### La trace d'une étiquette créée depuis une grille fermée — `stagiaire`
- [ ] « b2 · bulle », onglet « Sons et images (fictive) », le filtre « Chercher dans la grille… », `vent`, puis « Créer « vent » dans Mode libre » : l'onglet reste « Sons et images (fictive) », et la liste de ce qui est posé montre « vent », marqué « Mode libre », sans qu'on ait à la faire défiler
- [ ] Le bouton « Relevés : … ▾ » dit « + 1 », et son menu a la case « Mode libre » cochée ; la décocher : « vent » quitte la liste, et rien d'autre ne bouge

### Rendre la recette — PowerShell
- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache` finit par « bd-app : running »
