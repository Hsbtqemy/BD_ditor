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

**Préalable — le décor, dans l'Atelier** (~5 min, **à faire même si le corpus porte déjà des
tags** : c'est l'ARRANGEMENT qui compte, pas leur nombre). Choisir une bulle **qui a du
texte** — sans transcription elle n'a aucun token et ne sortira d'aucune concordance, si
bien qu'un décor parfait y resterait introuvable. Lui poser **un** tag et une note ; poser
sur **sa case parente** deux tags aux libellés **différents**. **Noter un mot du texte de la
bulle** : c'est lui qu'on cherchera pour la retrouver, et rien d'autre ne permet d'y revenir.

L'écran ne montre que deux puces, les PROPRES d'abord — un seul tag sur la bulle laisse donc
la puce « case » visible, là où trois l'enverraient dans le « +N », c'est-à-dire hors de vue
dans la zone même qui demande de la voir. Un tag porté à la fois par la bulle et par sa case
compte comme propre et ne se répète pas : d'où les libellés distincts.

### Le joker
- [x] Exploration → Concordance, lemme `*` seul : le tableau cède la place à « Précisez un lemme / mot, ou un filtre POS, morpho, tag, locuteur ou attribut. », sans aucun « Erreur », et le bouton d'export est grisé
- [x] Un préfixe suivi de `*` rend les formes de sa famille ; le même mot sans `*` n'en rend que le lemme exact, en autant de lignes ou moins

### Les tags en aligné
- [ ] **Chercher le mot noté au préalable** : les lignes de la bulle préparée apparaissent, et leur colonne de tags — la dernière, tout à droite de la ligne — montre deux puces puis « +N », avec un repère 📝 pour la note. On ne sélectionne rien : dans l'Exploration, une bulle se retrouve en cherchant un de ses mots
- [ ] Le tag venu de la case porte la marque « case », séparée du mot par un espace et non collée (« case colère », pas « casecolère »)
- [ ] Sur un lemme dont aucune ligne affichée n'a de tag ni de note, la colonne de tags disparaît au lieu de laisser une gouttière vide

### Les tags en liste
- [ ] En liste, la même ligne montre tous ses tags et la note ENTIÈRE

### L'export
- [ ] L'export de la concordance donne un CSV avec des colonnes `tags` et `note`, et les lignes de la bulle préparée y portent ses tags et sa note

### Petite largeur
- [ ] À 560 px de large, la concordance alignée défile dans son propre cadre et la page ne défile jamais de côté
