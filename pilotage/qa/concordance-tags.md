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
- [x] **Chercher le mot noté au préalable** : les lignes de la bulle préparée apparaissent, et leur colonne de tags — la dernière, tout à droite de la ligne — montre deux puces puis « +N », avec un repère 📝 pour la note. On ne sélectionne rien : dans l'Exploration, une bulle se retrouve en cherchant un de ses mots
- [x] Le tag venu de la case porte la marque « case », séparée du mot par un espace et non collée (« case colère », pas « casecolère »)
- [x] **Chercher `abdou`** : cinq lignes, dont aucune région ni case parente ne porte de tag ou de note — la colonne de tags disparaît ENTIÈREMENT, au lieu de laisser une gouttière vide. Si ce lemme a été tagué depuis, en prendre un autre dont aucune ligne affichée n'a ni tag ni note : c'est la propriété qui compte, le mot n'est qu'un raccourci mesuré le 2026-09-14

### Les tags en liste
- [x] Basculer le sélecteur **« Affichage »** de `aligné` sur `liste` : la même ligne montre alors TOUS ses tags — plus de « +N », la liste ne plafonne pas — et la note ENTIÈRE

### L'export
- [x] Le bouton **« ⤓ Exporter (CSV) »**, au-dessus des résultats à droite, donne un CSV avec des colonnes `tags` et `note`, et les lignes de la bulle préparée y portent ses tags et sa note. Il rend le jeu TROUVÉ et non l'aperçu affiché, ce que la page annonce elle-même juste en dessous

### Petite largeur
- [x] À 560 px de large — fenêtre rétrécie, ou mode responsive des outils de développement — et **avec des résultats à l'écran**, la concordance alignée défile dans son propre cadre et la page ne défile jamais de côté
