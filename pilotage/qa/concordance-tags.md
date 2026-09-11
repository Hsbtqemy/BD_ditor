---
passe: Tags et joker dans la concordance
chantier: ANA-6
duree: 15 min
derniere: 2026-09-11
---

# QA — la concordance dit les tags, et un joker seul ne casse rien

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, sous `proprio` : il
lit et écrit « Collection Test », et c'est le seul à pouvoir en exporter tant que personne
n'a coché la case de DROIT-2.

**Préalable, si le corpus copié n'a aucun tag** : dans l'Atelier, poser un tag sur une case,
puis trois tags et une note sur une bulle de cette case. C'est ce qu'il faut pour voir la
puce héritée, le « +N » et le repère de note.

### Le joker
- [ ] Exploration → Concordance, lemme `*` seul : le tableau cède la place à « Précisez un lemme / mot, ou un filtre POS, morpho, tag, locuteur ou attribut. », sans aucun « Erreur », et le bouton d'export est grisé
- [ ] Un préfixe suivi de `*` rend les formes de sa famille ; le même mot sans `*` n'en rend que le lemme exact, en autant de lignes ou moins

### Les tags en aligné
- [ ] Sur la bulle préparée, une colonne de tags montre deux puces puis « +N », et un repère 📝 signale la note
- [ ] Le tag venu de la case porte la marque « case », séparée du mot par un espace et non collée (« case colère », pas « casecolère »)
- [ ] Sur un lemme dont aucune ligne affichée n'a de tag ni de note, la colonne de tags disparaît au lieu de laisser une gouttière vide

### Les tags en liste
- [ ] En liste, la même ligne montre tous ses tags et la note ENTIÈRE

### L'export
- [ ] L'export de la concordance donne un CSV avec des colonnes `tags` et `note`, et la bulle préparée y porte ses trois tags et sa note

### Petite largeur
- [ ] À 560 px de large, la concordance alignée défile dans son propre cadre et la page ne défile jamais de côté
