---
chantier: UX-7
statut: interrompu
audit: AUDIT.md
---

# UX-7 — rendre les surfaces utilisables sous 1 000 px

**Arrêté sur** — 2026-09-04, `0faad20` : la mesure est faite et elle a immédiatement
déterré un BUG, sans rapport avec le responsive — l'Exploration perdait 1 285 px de
contenu sur un écran de 1080, en usage ordinaire. Corrigé, gardé par deux tests, et une
passe de QA écrite pour ce qu'ils n'expriment pas. **La passe jouée a rapporté deux
défauts de plus, et s'est démentie elle-même sur un troisième point** (ci-dessous).
Le chantier responsive lui-même n'a pas commencé.

## Ce que la passe de QA a rapporté, une fois jouée

Trois choses, dont une qui met en cause la passe elle-même.

**Quatre éléments déclarés cachés ne l'étaient pas** (`ae875a4`). `.dist` gardait
1 927 px de hauteur sous `hidden` : la distribution restait affichée sous le tableau de
croisement après une bascule de vue. Le balayage de la famille en a trouvé trois autres,
tous des filtres de la barre d'outils. Le défaut dormait — `overflow: hidden` le clippait
— et le cadre de défilement l'a rendu visible le jour même.

**Le coin du tableau croisé était recouvert** (`f74a911`) : `z-index` déclaré 3, reçu 2,
par spécificité. Il collait au bon pixel, sous les en-têtes de colonnes.

**Le collage VERTICAL des en-têtes est inerte, et l'a toujours été.** C'est le constat
qui compte, parce que la passe affirmait le contraire et que la case avait été validée
sur cette affirmation. `.croise` porte `overflow-x: auto`, donc c'est LUI le conteneur de
défilement le plus proche, pour les deux axes ; il a la hauteur de son contenu et ne
défile jamais verticalement, si bien que `thead th { top: 0 }` n'a rien à quoi se caler.
Sur 60 lignes, l'en-tête sort par le haut à y=-1121 ; avec le corpus de démonstration il
reste visible parce que ses dix lignes tiennent dans la fenêtre — la case était cochable
pour une raison qui n'était pas la sienne. Le fait est écrit dans `static/style.css`, à
côté de la règle inerte, et la case ci-dessous porte l'arbitrage.

L'état des lieux déplace le chantier : **la tablette va déjà bien**, c'est le téléphone
qui perd du contenu. La décision sur la Visionneuse est reportée APRÈS l'étape 1 (choix
du 2026-09-04), avec le coût réel des tiroirs sous les yeux.

Ce que le CSS dit aujourd'hui : `static/style.css` porte **une seule** media query de
largeur (`max-width: 720px`), et elle fait exactement une chose — empiler la vue de
comparaison de l'Exploration. Face à quoi les quatre gabarits promettent tous
`<meta name="viewport" content="width=device-width, initial-scale=1">`, et la feuille
compte **neuf** largeurs figées à 100 px ou plus.

## Mesures du 2026-09-04

Relevé dans un vrai Chromium sur le corpus de démonstration, en comparant le rectangle de
chaque élément à la largeur de la fenêtre.

| Surface | 320 px | 768 px |
|---|---|---|
| Visionneuse | `#site-nav`, `#header`, `#body`, `#statusbar` font **751 px** — 431 px hors champ | rien ne dépasse |
| Bibliothèque | `.corpus-table` fait **693 px** — 393 px hors champ ; plus la barre de nav | rien ne dépasse |
| Recherche | `.surf-nav` fait 361 px, le menu « Aa » sort de 214 px | rien ne dépasse |
| Exploration | idem Recherche | rien ne dépasse |

**« Rien ne dépasse » n'est pas « utilisable » — constat du 2026-09-05.** Le tableau
ci-dessus mesure le CLIPPAGE, et il a raison sur ce qu'il mesure. Mais `#body` est une
grille `240px | 1fr | 300px` : 540 px de chrome fixe, quelle que soit la fenêtre. Il reste
donc **228 px de canevas sur une tablette en portrait** (768) et 484 px en paysage (1024).
On ne dessine pas une case de bande dessinée dans 228 px. La conclusion ci-dessous vaut
pour le 1.4.10, et pour lui seul.

**La tablette n'a rien à réparer.** Aucune des quatre surfaces ne déborde à 768 px — ce qui
retire du chantier la motivation d'usage la plus immédiate, et le réduit au téléphone.

## Mesure rejouée après l'étape 1 — 2026-09-04

```
320 px   Visionneuse    → 4 élément(s) COUPÉ(s)
           ✗ #site-nav, #header, #body, #statusbar : 751 px, INATTEIGNABLES
         Recherche      → OK
         Bibliothèque   → OK
           · .corpus-table 693 px, défile dans .table-cadre — conforme 1.4.10
         Exploration    → OK
768 px   les quatre     → OK
```

**Les trois surfaces « documents » sont conformes ; il ne reste que la Visionneuse**, dont
le sort est précisément la case non tranchée ci-dessous. L'étape 1 a donc fait ce qu'elle
annonçait — mais elle ne le faisait PAS quand elle a été déclarée faite, et c'est la passe
de revue qui l'a établi.

**Le seuil de la bande 1 valait 400 px, et il en fallait 560.** Entre les deux, la barre
revenait aux libellés sans avoir la place : à 480 px le menu « Aa » sortait de 55 px sur
les trois surfaces, coupé exactement comme avant le correctif. Les deux largeurs
canoniques de l'outil — 320 et 768 — ne disaient rien de cette bande, par construction. Il
en balaie cinq depuis, et le seuil se lit maintenant sur la largeur où le contenu tient,
non sur un nombre rond.

**Mais la mesure ne pouvait pas le dire avant qu'on corrige l'outil.** `mesurer_reflow.py`
comparait le rectangle de chaque élément à la fenêtre, et rapportait donc le tableau du
corpus comme débordant de 393 px — alors qu'il défile désormais dans un cadre de 280 px
qui, lui, tient dans l'écran. Un tableau encadré et un tableau clippé se ressemblent
exactement quand on ne regarde que le rectangle ; or le 1.4.10 TOLÈRE le premier et
interdit le second. L'outil remonte maintenant le cadre par son nom et distingue les deux
états. Sans ce correctif, l'étape 1 aurait été déclarée insuffisante par son propre
instrument.

**Et ce qui dépasse n'est pas défilable : c'est COUPÉ.** `static/style.css:170` pose
`html, body { overflow: hidden }` — nécessaire à la Visionneuse, qui est une coque pleine
hauteur, mais qui transforme sur les trois autres surfaces un défaut d'ergonomie en perte
de contenu. À 320 px, le tableau du corpus n'est pas pénible à lire : ses 393 px de droite
n'existent pas. C'est le pire des deux mondes vis-à-vis du 1.4.10, qui TOLÈRE un
défilement dans un cadre et interdit qu'on ne puisse pas atteindre le contenu.

Deux raisons de le faire, et elles ne se recouvrent pas.

**L'usage.** Annoter une planche haute résolution au doigt paraît absurde ; la
**tablette**, elle, ne l'est pas du tout — et la Recherche comme l'Exploration se
consultent très bien assis ailleurs qu'à un bureau. Ce n'est pas parce que la Visionneuse
est le cœur de l'outil que les trois autres surfaces doivent en hériter les contraintes.

**Le critère AA que personne ne mesure.** WCAG 2.1 AA impose le **1.4.10 « Reflow »** :
contenu utilisable à 320 px sans défilement bidimensionnel. Le dépôt revendique AA et
l'audite avec axe — or **axe ne teste pas ce critère**, qui n'est pas automatisable. La
suite est donc verte sans rien dire à ce sujet, et c'est le pire des cas : pas un échec
signalé, un silence pris pour un succès.

## Reste

### Étape 1 — les trois surfaces « documents »
- [x] **L'Exploration retrouve son contenu.** `#explo-app` n'avait ni hauteur ni cadre de défilement, là où les deux autres en ont un : sous `html, body { overflow: hidden }`, tout ce qui dépassait la fenêtre était CLIPPÉ. Ce n'était pas un défaut de responsive mais une perte de contenu en usage normal, et c'est la mesure d'UX-7 qui l'a trouvé
- [x] **La barre de navigation tombe aux ICÔNES SEULES sous 400 px** (et non à la ligne, comme cette case le disait d'abord : mesuré, l'enroulement coûtait 165 px de hauteur, un quart d'un écran de téléphone). Les libellés sont masqués à l'œil sans quitter l'arbre d'accessibilité, la marque s'abrège en « BDé ». Arbitré le 2026-09-04 entre trois formes toutes mesurées
- [x] **Les deux tableaux du corpus vivent dans leur propre cadre** — celui des albums et celui des planches, qui vit dans `corpus.js` et se serait fait oublier. Le cadre est focusable et nommé (`role="region"` + `aria-label`) : une zone défilante qu'on ne peut pas atteindre au clavier est une violation à part entière, pas un détail. Course mesurée : 413 px et 489 px, toutes deux atteintes
- [x] **La mesure est rejouée et consignée** (ci-dessous). Elle a d'abord obligé à corriger l'INSTRUMENT

### Décider avant de coder
- [x] **`html, body { overflow: hidden }` est GARDÉ**, et la case était mal posée : elle prétendait que la règle ne sert que la Visionneuse. Les QUATRE surfaces sont des coques pleine hauteur — `#corpus-app`, `#search-app` et `#explo-app` sont en `height: 100%` avec leur propre `overflow-y: auto`, exactement comme `#app`. Et l'étape 1 a rendu trois d'entre elles conformes à 320 px SANS toucher à cette règle : ce qui les a réparées, c'est d'avoir encadré le contenu large. La lever referait du code qui marche et changerait le modèle de mise en page de la Visionneuse par-dessus le marché
- [x] **Le sort de la Visionneuse est tranché : ANNOTATION TACTILE**, décidé le 2026-09-05. Elle n'est donc pas une surface de consultation qu'on rendrait lisible faute de mieux — c'est l'écran de travail, et il doit rester un écran de travail au doigt. Le tactile proprement dit (cibles de 44 px, gestuelle de zoom) part dans **UX-8** ; ce qui reste ici est son premier étage, les tiroirs, parce qu'ils relèvent du 1.4.10 et qu'ils servent les deux largeurs
- [ ] **Le panneau latéral et la boîte d'outils deviennent des tiroirs** sous un seuil mesuré : `#body` est une grille `240px | 1fr | 300px`, donc **540 px de chrome fixe** avant que le canevas reçoive un pixel. Escamotés, le canevas prend toute la largeur ; leur bascule est atteignable au clavier et rend le focus d'où il vient
- [ ] Le seuil se lit sur la largeur où le CANEVAS devient inutilisable, pas sur un nombre rond — comme celui de la bande 1, qui valait 400 px et en demandait 560
- [ ] Le **tableau de croisement** a un comportement décidé pour les petites largeurs : il est intrinsèquement à deux dimensions, donc 1.4.10 admet le défilement — à condition qu'il soit CONTENU dans son conteneur et non subi par la page entière
- [ ] Les deux tableaux des panneaux 🎯 Accord et 👥 Inter (`.accord-table`) n'ont PAS de cadre de défilement, et leur largeur n'a pas pu être mesurée : le corpus de démonstration n'a aucun token relu, donc la table ne se rend jamais. À vérifier sur un corpus qui en a — c'est le dernier tableau du dépôt dont on ignore le comportement sous 560 px
- [ ] Le collage VERTICAL des en-têtes du croisement est tranché : le rendre effectif demande de donner à `.croise` une hauteur bornée et son propre `overflow-y`, donc un cadre de défilement IMBRIQUÉ dans celui de la page — deux barres verticales pour un même geste de molette, ce qui n'est pas gratuit. L'alternative est de l'assumer inerte et de retirer la règle, qui promet aujourd'hui ce qu'elle ne fait pas

### Vérifications
- [ ] À **320 px**, chacune des quatre surfaces s'utilise sans défilement HORIZONTAL de la page (le défilement vertical est permis, et le contenu 2D peut défiler dans son propre cadre)
- [ ] À **768 px** (tablette), la Recherche et l'Exploration sont pleinement utilisables : filtres atteignables sans zoom, résultats lisibles, aucun tableau qui déborde de la page
- [ ] Les neuf largeurs figées ≥ 100 px de `static/style.css` sont revues une à une : converties en unités relatives, ou justifiées en commentaire
- [ ] La barre de navigation transverse et le lien d'évitement, injectés par `theme.js` sur les quatre pages, restent atteignables et ne masquent rien sous 400 px

### Ne pas répéter le silence d'axe
- [ ] Un test E2E compare, à 320 px et 768 px, le RECTANGLE DE CHAQUE ÉLÉMENT à la largeur de la fenêtre — et surtout **pas** `documentElement.scrollWidth`, qui est la garde que cette fiche spécifiait au départ et qui aurait été VACANTE : `overflow: hidden` sur `html, body` rend `scrollWidth` égal à `clientWidth` alors même que 431 px de contenu sont hors champ. Mesuré le 2026-09-04 : les quatre surfaces passaient ce test-là au vert dans l'état actuel
- [ ] Le test distingue le contenu ATTEIGNABLE du contenu perdu : un cadre qui défile en interne est conforme au 1.4.10, un contenu clippé ne l'est pas — c'est exactement la différence que `scrollWidth` efface
- [ ] L'audit axe reste sans violation sérieuse ou critique après la refonte, sur les quatre surfaces et les deux thèmes

## Contexte

Vient du constat **T7** de l'audit du 13 juin 2026, resté sans décision près de trois mois. La fiche
`AUDIT-2` le portait comme un ARBITRAGE — « rendre responsive, ou assumer le desktop et
retirer le `<meta viewport>` qui promet le contraire » —, et c'est cet arbitrage qui a été
tranché le 2026-09-04, en faveur du responsive. La case correspondante d'`AUDIT-2` renvoie
ici ; le travail lui-même n'y était pas et n'y sera pas.

**Recouvrement avec `A11Y-2`, et il faut le tenir en tête** : cette fiche-là convertit les
`px` figés en `rem` et vérifie qu'à 200 % de zoom aucune surface ne défile
horizontalement. C'est le critère 1.4.4 (*Resize text*), voisin mais distinct du 1.4.10
(*Reflow*) : l'un agrandit le contenu à largeur constante, l'autre rétrécit la fenêtre à
taille de texte constante. Ils échouent souvent pour la même raison — une largeur figée —
et les traiter ensemble ferait gagner du temps. Les mener séparément reste possible ;
les mener sans savoir qu'ils se touchent, non.

La Visionneuse est la surface qui décidera du coût réel du chantier, et c'est pourquoi
son sort est la première case : elle porte un canevas, un arbre de structure, un panneau
latéral et des poignées de redimensionnement au pixel. Les trois autres surfaces sont des
listes, des tableaux et des formulaires — le genre de mise en page qui se replie sans
drame.
