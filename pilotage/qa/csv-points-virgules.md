---
passe: Les CSV dans un Excel français
chantier: ANN-7
duree: 10 min
---

# QA — un CSV qui sort s'ouvre en colonnes, et ses décimaux sont des nombres

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`9e75b30` (« ANN-7 : les décimaux d'un CSV qui sort s'écrivent avec une virgule ») ou après,
état `apres-moustache` restauré (`C:\temp\bd-recette\etat-de-base.ps1 restaurer
apres-moustache`). Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`, hors dépôt.
Tout se joue sous `proprio`, qui peut exporter « Projet principal ». Excel en français est
nécessaire : un double-clic sur le fichier téléchargé l'ouvre.

**Ce que la passe éprouve** — le constat de Hugo du 2026-11-11 : dans Excel, un export
arrivait en une seule colonne, chaque ligne entière dans sa première case. Tranché le même
jour : tout CSV qui sort est séparé par des points-virgules. Le 2026-11-14, Hugo a ajouté
la virgule décimale : avec un point, Excel lisait les décimaux comme du texte, et on ne
pouvait pas calculer dessus.

### L'export d'un album, sous `proprio`
- [ ] Atelier, l'album « Moustache et Trottinette », « ⇅ Import / Export ▾ », « Export CSV », double-clic sur le fichier : Excel l'ouvre en plusieurs colonnes, une valeur par case, et les accents des dialogues sont justes (ni « Ã© » ni « ? »)

### La Recherche, sous `proprio`
- [ ] Recherche, un mot qui rend au moins un résultat, « ⤓ Export CSV », double-clic : une colonne par champ, et une bulle qui contient un point-virgule le garde dans sa case (la ligne n'a pas une colonne de trop)

### L'Exploration, sous `proprio`
- [ ] Exploration, la vue « Comparaison A / B », deux sous-corpus différents, « ⤓ Exporter (CSV) », double-clic : les colonnes de fréquence relative et de différence affichent des nombres à virgule (« 0,0123 »), alignés à droite comme des nombres
- [ ] Dans ce fichier, cliquer l'en-tête de la colonne « diff » : la barre d'état d'Excel, en bas à droite, affiche « Somme : » suivie d'un nombre (sur une colonne de texte, elle n'affiche que « Nb »)
