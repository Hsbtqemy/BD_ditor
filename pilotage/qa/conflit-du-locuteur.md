---
passe: Deux personnes sur la même planche — le locuteur refusé sur une valeur périmée, « Actualiser »
chantier: CONC-4
duree: 20 min
---

# QA — deux comptes, deux fenêtres, la même zone : le locuteur ne s'écrase plus, et la planche dit qu'elle a changé

> **Réécrite le 2026-11-14 pour la page Annotation.** La version du 2026-10-25, jouée par Hugo
> (18 sur 18), passait par le mode Annotation de l'Atelier, que le basculement d'ANN-7 a retiré
> (v39, sur `dev` depuis `2de79fd`). Son histoire est dans celle de ce fichier. Le locuteur
> s'écrit maintenant dans le **Contexte** de la page Annotation, avec la même garde
> (`personnage_vu`). Le bandeau s'ouvre dans la boîte du guide. Cette version joue aussi
> les correctifs de « ⟳ Actualiser » du 2026-11-14 (`e99e062`) : ce qu'un écran écrit lui-même
> ne masque plus ce qu'un autre écrit à côté.

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`e99e062` ou après, état `apres-moustache` restauré
(`C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache`). Au démarrage,
l'application migre la base en v39. Les mots de passe sont dans
`C:\temp\bd-recette\comptes.txt`, hors dépôt.

**Les comptes** — `proprio` et `stagiaire`, qui écrivent tous deux dans « esther v1 » (par
« Collection Test »). Deux fenêtres privées CÔTE À CÔTE, chacune sur la page Annotation
(🖍️ dans la navigation), album « esther v1 », planche 1. La bulle « Haha coucou Esther » est
« b2 · bulle » de la case c5 : on la choisit dans la rangée « Zones de la case », après avoir
choisi c5 sur la minicarte. Les zones s'enchaînent dans l'ordre : chacune part de l'état
laissé par la précédente.

**Rejouée par la session le 2026-11-14**, dans un Chromium à 1 280 px sous les deux identités, sur une copie de l'état `apres-moustache` migrée en v39 et servie par le code de `596ec30` : toutes les cases sauf la dernière, et leurs mots pris à l'écran. Deux écarts relevés en route sont des cases de `pilotage/ANN-7.md`, pas de cette passe.

**Ce que la passe ne juge pas** — l'ordre des requêtes et la course, que l'œil ne voit pas :
`tests/test_e2e_annotation_page.py` et `tests/test_e2e_planche_changee.py` les mesurent.

### Deux personnages pour jouer — `proprio`
- [ ] `proprio`, c5 puis « b2 · bulle » : le Contexte montre « Locuteur » et le champ « Attribuer un personnage… » ; y taper `Alpha`, le créer, puis « × » (« Retirer le locuteur ») ; même chose avec `Bêta` : les deux personnages existent, et la bulle n'a pas de locuteur

### Le locuteur posé des deux côtés — `proprio` et `stagiaire`, la même bulle
- [ ] Dans les deux fenêtres, c5 puis « b2 · bulle » : le champ « Attribuer un personnage… » est vide des deux côtés
- [ ] `proprio` attribue `Alpha` : la puce « Alpha » paraît chez `proprio`
- [ ] Sans recharger, `stagiaire` attribue `Bêta` : en bas de la grille, un bandeau dit « Locuteur modifié par proprio à … », « Votre choix, Bêta, n'est pas enregistré. » et « Version enregistrée : Alpha », et offre « Remplacer par la mienne » et « Garder l'autre » ; la ligne « Locuteur » du Contexte prend l'encre d'alerte et dit « En attente de votre choix », sans que rien ne bouge
- [ ] Bandeau ouvert, `stagiaire` choisit la planche 2 dans la liste *Planche* : la page reste sur la planche 1, et un message dit « Réglez d'abord le conflit, en bas de la grille. »
- [ ] `stagiaire`, « Garder l'autre » : le bandeau se ferme et la puce dit « Alpha » ; F5 chez `proprio` : toujours « Alpha »

### Le retrait contre une attribution — `proprio` et `stagiaire`
- [ ] `stagiaire`, « × » sur « Alpha » : la bulle n'a plus de locuteur chez `stagiaire`
- [ ] Sans recharger, `proprio`, qui voit encore « Alpha », attribue `Bêta` : le bandeau s'ouvre chez `proprio` : « Locuteur modifié par stagiaire à … », « Votre choix, Bêta, n'est pas enregistré. », « Version enregistrée : Aucun locuteur »
- [ ] `proprio`, « Remplacer par la mienne » : la puce dit « Bêta » ; F5 chez `stagiaire`, c5 puis « b2 · bulle » : « Bêta »

### La planche dit qu'elle a changé ailleurs — `proprio` et `stagiaire`
- [ ] `stagiaire`, c1, puis la zone « ÉCOLE PRIMAIRE » : dans le Contexte, écrire `xylophone` dans la note, puis Tab
- [ ] `proprio`, sans recharger : au plus 30 secondes après (ou tout de suite, en passant sur un autre onglet puis en revenant), « ⟳ Actualiser » paraît dans la bande du haut, à droite de la liste *Planche*, et son infobulle dit « La planche a changé ailleurs : 1 région modifiée. Actualiser la recharge, sans perdre votre saisie. »
- [ ] `proprio`, « b2 · bulle » : commencer à taper une note SANS quitter le champ, puis « ⟳ Actualiser » : la zone de `stagiaire` porte la note `xylophone`, et la note que `proprio` tapait est toujours dans son champ, et « ⟳ Actualiser » a disparu
- [ ] `proprio`, onglet « Mode libre », « ↕ Ranger », ↓ sur la première étiquette s'il y en a deux (sinon « + Nouvelle étiquette… » en crée deux d'abord), « Fini » ; dans la minute qui suit, et après un aller-retour sur un autre onglet : « ⟳ Actualiser » ne paraît pas
- [ ] `stagiaire`, dans la minute qui suit le rangement de `proprio`, onglet « Mode libre », « ↕ Ranger », ↓, « Fini » ; `proprio`, au plus 30 secondes après : « ⟳ Actualiser » paraît, et son infobulle dit « La planche a changé ailleurs : des étiquettes. … »

### Annuler une création n'emporte pas le travail de l'autre — `proprio` puis `stagiaire`
- [ ] `proprio`, c7, « Tracer une zone », un glissé dans la case agrandie, puis « Texte hors bulle » : la zone naît dans c7, choisie, et la rangée « Zones de la case » dit « b1 · texte »
- [ ] `stagiaire`, F5, c7, la nouvelle zone : lui attribuer `Alpha`
- [ ] `proprio`, un clic sur le titre « Case c7 » (hors de tout champ), Ctrl+Z : un message dit « Annulation impossible : le locuteur a été modifié depuis par stagiaire à … » et offre « Passer ce geste » ; la zone reste. F5 des deux côtés : la zone porte « Alpha »

### Rendre la recette — PowerShell
- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-moustache` finit par « bd-app : running »
