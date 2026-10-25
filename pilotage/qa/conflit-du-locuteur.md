---
passe: Deux personnes sur la même planche — le locuteur refusé sur une valeur périmée, « Actualiser »
chantier: CONC-4
duree: 20 min
derniere: 2026-10-25
---

# QA — deux comptes, deux fenêtres, la même bulle : le locuteur ne s'écrase plus, et la planche dit qu'elle a changé

**Écrite le 2026-10-25 sur la recette reconstruite sur `24c5e13`, jouée par Hugo le même jour** (18 sur 18), décor de l'état `avant-conc4`. Elle porte sur `CONC-4` : le locuteur et le personnage montré d'une boîte refusent un
enregistrement fait sur une valeur que l'écran ne voyait plus (le bandeau de `CONC-3`, celui de la
note) ; la planche ouverte signale, toutes les 30 secondes et au retour sur l'onglet, qu'elle a changé
ailleurs, et « ⟳ Actualiser » la recharge sans rien perdre ; annuler la création d'une bulle n'emporte
plus le locuteur qu'un autre lui a donné.

**Les comptes** : `proprio` et `stagiaire`, qui écrivent tous deux dans « esther v1 » (par « Collection
Test »). Deux fenêtres privées CÔTE À CÔTE, l'Atelier ouvert dans chacune sur « esther v1 », planche 1,
mode Annotation (`a`). Le panneau de droite porte « Locuteur ». **Ce que la passe ne juge pas** : la
forme du bouton « ⟳ Actualiser » (sa place est à trancher sur l'écran, voir la dernière zone) ; les
tests mesurent l'ordre des requêtes et la course, que l'œil ne voit pas.

## Reste

### Deux personnages pour jouer — compte `proprio`

- [x] `proprio`, première bulle de la planche 1, champ « Attribuer un personnage… » : taper `Alpha`, le créer, puis retirer ce locuteur (×) ; même chose avec `Bêta` → les deux personnages existent, la bulle n'a aucun locuteur

### Le locuteur posé de part et d'autre — `proprio` et `stagiaire`, la même bulle

- [x] Les deux fenêtres affichent la première bulle sélectionnée, « Locuteur » vide dans les deux
- [x] `proprio` attribue `Alpha` → la puce « Alpha » s'affiche chez `proprio`
- [x] Sans recharger, `stagiaire` attribue `Bêta` → un bandeau s'ouvre au-dessus de la puce : « Votre choix, Bêta, n'est pas enregistré. », il nomme `proprio` et dit qu'il a choisi Alpha, et offre « Remplacer par la mienne » et « Garder l'autre »
- [x] Tant que le bandeau est ouvert, `stagiaire` ne peut pas changer de bulle ni de mode (un clic ailleurs ne fait rien, ou un message demande de choisir d'abord)
- [x] `stagiaire`, « Garder l'autre » → le bandeau se ferme, la puce dit « Alpha » ; F5 chez `proprio` : toujours « Alpha »

### Le retrait contre une attribution — `proprio` et `stagiaire`

- [x] `stagiaire` retire « Alpha » (×) → la bulle n'a plus de locuteur chez `stagiaire`
- [x] Sans recharger, `proprio` (qui voit encore « Alpha ») attribue `Bêta` → le bandeau s'ouvre chez `proprio` : son choix n'est pas enregistré, `stagiaire` a retiré le locuteur
- [x] `proprio`, « Remplacer par la mienne » → la puce dit « Bêta » ; F5 chez `stagiaire` : « Bêta »

### La planche signale qu'elle a changé ailleurs — `proprio` et `stagiaire`

- [x] `stagiaire`, mode Transcription (`t`), une AUTRE bulle de la planche 1 : taper `xylophone`, Tab
- [x] `proprio`, sans recharger : au plus 30 secondes après (ou tout de suite en passant sur un autre onglet puis en revenant), « ⟳ Actualiser » apparaît dans la barre d'outils, et son infobulle dit ce qui a changé
- [x] `proprio`, commencer à taper une note dans la première bulle SANS l'enregistrer, puis « ⟳ Actualiser » → la bulle de `stagiaire` affiche `xylophone`, et la note en cours de frappe est toujours dans son champ
- [x] `proprio` : après ses propres enregistrements (une note, un locuteur), « ⟳ Actualiser » ne réapparaît pas tout seul

### Annuler une création n'emporte pas le travail de l'autre — `proprio` puis `stagiaire`

- [x] `proprio`, mode Édition (`e`), trace une nouvelle bulle sur la planche 1
- [x] `stagiaire`, F5, sélectionne cette nouvelle bulle, mode Annotation, lui attribue `Alpha`
- [x] `proprio`, Échap puis Ctrl+Z, répété : chaque Ctrl+Z défait d'abord un réglage de la bulle (position, taille, type — un par geste fait en la traçant) ; quand on arrive au réglage qui l'a faite bulle, ou à sa création, un message refuse : un autre lui a donné un locuteur, avec « Passer ce geste » ; la bulle reste, avec « Alpha » chez les deux après F5

### La place de « ⟳ Actualiser » — à dire, pas à cocher seulement

- [x] « ⟳ Actualiser » est trouvé sans le chercher, à côté du nom de la planche, dans tous les modes (Annotation, Transcription, Édition) — sinon, écrire ici où on l'attendait

### Rendre la recette — PowerShell

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-conc4` finit par « bd-app : running »
