---
chantier: UX-7
statut: livré
audit: AUDIT.md
---

# UX-7 — rendre les surfaces utilisables sous 1 000 px

**Arrêté sur** — 2026-09-05, `b01903b` : le chantier est FAIT, sa garde écrite, et son
`Reste` entièrement coché. La Visionneuse escamote ses 540 px de chrome en tiroirs sous
des seuils mesurés ; les cinq arbitrages qui restaient ouverts sont tranchés, et trois
l'ont été PAR la mesure plutôt qu'avant elle. Sept largeurs vertes sur les quatre
surfaces, 138 tests E2E dont 20 neufs, et le silence d'axe sur le 1.4.10 est comblé par
un test qui DÉMONTRE pourquoi la garde naïve aurait été vacante.

`livré` depuis le push du 2026-09-05 : `06bb07f` vit sur `origin/dev`, donc le journal ne
dément plus. La branche `arch-2-cliquets-aveugles`, entièrement fusionnée, a été supprimée
dans le même geste — les deux sessions parallèles du jour n'en laissent aucune trace.

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

Ce que le CSS disait AVANT le chantier (état du 2026-09-04, conservé pour la mesure de
l'écart) : `static/style.css` portait **une seule** media query de largeur
(`max-width: 720px`), et elle faisait exactement une chose — empiler la vue de comparaison
de l'Exploration. Face à quoi les quatre gabarits promettaient tous
`<meta name="viewport" content="width=device-width, initial-scale=1">`, et la feuille
comptait neuf largeurs figées à 100 px ou plus — dix en réalité, le compte était court
d'une (cf. l'étape 2). Elle porte aujourd'hui sept blocs de largeur, sur cinq seuils
(1079 · 899 · 720 · 659 · 559).

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

## Étape 2 — la Visionneuse, et quatre arbitrages tranchés PAR la mesure — 2026-09-05

Les tiroirs sont posés (`9c8934f`), les arbitrages restants tranchés (`12f4ef5`). Ce qui
mérite d'être retenu n'est pas le CSS mais la façon dont chaque décision a changé de
réponse une fois mesurée.

**Les seuils appartiennent au CSS SEUL.** Le JS ne connaît aucun nombre : il pose deux
classes sur `#body`, déplace le focus dans le tiroir ouvert et le rend d'où il vient. Ce
qui décide qu'un tiroir EXISTE est la media query. Un seuil recopié des deux côtés se
serait désaccordé au premier ajustement, en silence. Même règle pour le voile : sa
visibilité est une CONSÉQUENCE des classes, jamais une commande — écrit d'abord dans les
deux langages, il aurait couvert l'application entière après un redimensionnement fait
tiroir ouvert.

Quatre seuils, chacun sur la largeur où son contenu cesse de tenir : **1079** pour l'arbre
de structure, **899** pour le panneau latéral, **659** pour la barre d'état (mesuré :
651 px de contenu — l'imitation du seuil voisin aurait dit 559) et **559** pour l'en-tête,
qui passe alors à la ligne.

**Le mode Transcription s'est cassé sur ce commit même**, et il a fallu OUVRIR le mode
pour le voir : les sept mesures de reflow n'y entrent jamais. `#transcription` porte
`grid-row: 3` ; l'auto-placement d'une grille SAUTE une cellule occupée par un élément
placé explicitement, si bien que `#body` tombait en rangée 4, haut de 26 px, la barre
d'état hors écran. Deux éléments qui partagent une cellule doivent l'un et l'autre la
nommer.

### Trois largeurs figées n'avaient jamais été mesurées, et pour la même raison

Le balayage des quatre surfaces mesure l'état **AU REPOS** : pas de toast affiché, pas de
résultat de recherche, aucun token relu. Ce que la page ne rend pas, l'instrument ne le
voit pas — et c'est exactement là que vivaient les trois valeurs restantes.

- **`.accord-table`** (🎯 Accord, 👥 Inter) ne déborde qu'à 320 px, de 38 px. Elle avait
  un cadre de défilement **par ACCIDENT** : `overflow-y: auto` sur `.modal-box` force
  `overflow-x` à `auto`, donc la modale entière défilait de travers, titre et bouton
  Fermer compris. Elle a désormais le sien, atteignable au clavier.
- **Le toast** tient tout seul : son `right: 16px` le borne à 304 px dans une fenêtre de
  320, sans que sa `max-width: 320px` ait à intervenir. Rien à corriger.
- **`.r-thumb`** laissait 116 px au texte à 320 px — une douzaine de caractères par ligne.
  `clamp(72px, 22vw, 130px)` en rend 174, et ne change rien au-dessus de 591 px de fenêtre.

Les autres sont soit des PLAFONDS qui ne forcent jamais rien (`max-width` de `.toast`,
`#search-body`, `#explo-body`), soit des planchers tous sous 320 px et ancrés à droite
(`.display-panel` 210, deux menus à 120, `.explo-controls input` 110) — mesurés, aucun ne
déborde. Restent `--sidebar-w` (240) et `--panel-w` (300), désormais escamotés.

### L'objection au collage vertical ne tenait pas

`.croise-table thead th { top: 0 }` promettait des en-têtes collants sans en donner aucun.
L'arbitrage écrit dans cette fiche opposait une barre de défilement IMBRIQUÉE dans celle
de la page — deux cibles de molette pour un seul geste. **Mesurée, elle tombe** : sur
60 lignes, borner le cadre à 70vh fait passer le défilement restant de la page de
**1 018 px à 83 px**. La barre imbriquée ne s'AJOUTE pas à celle de la page, elle la
REMPLACE ; et sous 70vh, le cas ordinaire, elle n'apparaît pas du tout. Peser deux
inconvénients de tête donnait la mauvaise réponse.

### Et l'instrument, deux fois

Son exemption « hors champ » excusait tout élément entièrement sorti de la fenêtre — donc
aussi un panneau qu'aucun geste ne ramène, c'est-à-dire la violation même qu'il cherche.
Elle exige désormais qu'un contrôle le référence par `aria-controls`.

Puis une sonde écrite pour la dernière case a rapporté un défaut qui n'existait pas : le
lien d'évitement semblait prendre le focus HORS de l'écran, sur les quatre surfaces.
`.skip-link` a `transition: top .15s`, et la mesure était prise pendant la transition.
Vérifié après : il arrive à `[8, 0, 121, 34]`, dans la fenêtre et au premier plan.

### Le test a trouvé un cinquième angle mort à sa première course

`tools/mesurer_reflow.py` charge les quatre surfaces SANS paramètres : pas de planche
ouverte, donc un canevas minuscule. `tests/test_e2e_reflow.py` monte un décor et vise des
URL peuplées — et `#canvas` y fait **800 px pour 768 de fenêtre**, aux deux largeurs.

Ce n'est pas une violation : le 1.4.10 exempte explicitement le contenu qui exige une
disposition à deux dimensions, et un scan de planche est l'image même qu'on est venu
regarder. Mais l'exemption devait être ÉCRITE, pas déduite par une règle générale : « une
surface de pan » excuserait n'importe quel conteneur en `overflow: hidden`, c'est-à-dire
les quatre coques de l'application. Elle est donc nommée, sur le modèle de
`HORS_PERIMETRE` et de `BLOCAGES_ADMIS`, et un test la fait MÉRITER — `#stage` doit
continuer de clipper, tenir dans la fenêtre, et les quatre commandes de zoom doivent
exister — « Ajuster » en tête, la seule qui garantisse que la planche entière rentre, sans quoi l'atteignabilité reposerait sur un glisser de souris que le 2.1.1
n'accepte pas.

C'est le cinquième défaut trouvé par un instrument plutôt que par une relecture, sur ce
seul chantier — et le quatrième que la mesure au repos ne pouvait pas voir.

### Les tiroirs étaient modaux au doigt et pas au clavier

Le voile bloque le clic sur le reste de l'application : l'écran se LIT donc comme modal.
Mesuré le 2026-09-05 sur la Visionneuse à 320 px, tiroir de navigation ouvert, le focus en
sort au **quatrième Tab**, et **19 arrêts sur 25** tombent hors du tiroir et hors de sa
bascule — dont plusieurs SOUS LE VOILE, c'est-à-dire sur des commandes qu'aucun doigt ne
peut atteindre. Deux publics recevaient deux applications différentes, et c'est la forme
même que ce dépôt documente depuis des mois : deux vérités qui ne se parlent pas.

Le piège à focus est UNE règle et non deux. `inert` sur le reste de l'écran serait plus
complet — il couvrirait aussi le mode navigation d'un lecteur d'écran — mais il ne peut pas
s'appliquer à `#toolbar`, qui porte les DEUX bascules servant à refermer, au milieu des
commandes de zoom qu'il faudrait au contraire rendre inertes : il faudrait exempter au cas
par cas à l'intérieur d'un même conteneur, soit deux mécanismes pour une seule intention. La limite est
donc écrite plutôt que masquée : le parcours par tabulation est enfermé, le mode « browse »
d'un lecteur d'écran ne l'est pas, et Échap reste la sortie universelle.

Le correctif s'est trompé deux fois avant de tenir, et les deux erreurs sont la même :
raisonner sur une structure au lieu de l'ouvrir. N'intercepter que les BORDS du cycle ne
suffisait pas — la liste met la bascule en tête, par où l'on entre, alors que le gabarit
la place APRÈS le tiroir, dans `#toolbar` ; le focus filait donc d'un cran vers `#zoom-out`
à chaque passage, 11 arrêts sur 25 restant dehors. Et le test censé garder le bouclage a
demandé TROIS formulations avant d'échouer quand il le devait : les deux premières
passaient le piège désarmé, la seconde parce que `#btn-tiroir-nav` suit immédiatement
`</aside>` — pour ce tiroir-là, les deux sens sont nativement corrects. C'est le tiroir de
PANNEAU qui distingue, et le test est paramétré sur les deux depuis.

## Reste

### Étape 1 — les trois surfaces « documents »
- [x] **L'Exploration retrouve son contenu.** `#explo-app` n'avait ni hauteur ni cadre de défilement, là où les deux autres en ont un : sous `html, body { overflow: hidden }`, tout ce qui dépassait la fenêtre était CLIPPÉ. Ce n'était pas un défaut de responsive mais une perte de contenu en usage normal, et c'est la mesure d'UX-7 qui l'a trouvé
- [x] **La barre de navigation tombe aux ICÔNES SEULES sous 400 px** (et non à la ligne, comme cette case le disait d'abord : mesuré, l'enroulement coûtait 165 px de hauteur, un quart d'un écran de téléphone). Les libellés sont masqués à l'œil sans quitter l'arbre d'accessibilité, la marque s'abrège en « BDé ». Arbitré le 2026-09-04 entre trois formes toutes mesurées
- [x] **Les deux tableaux du corpus vivent dans leur propre cadre** — celui des albums et celui des planches, qui vit dans `corpus.js` et se serait fait oublier. Le cadre est focusable et nommé (`role="region"` + `aria-label`) : une zone défilante qu'on ne peut pas atteindre au clavier est une violation à part entière, pas un détail. Course mesurée : 413 px et 489 px, toutes deux atteintes
- [x] **La mesure est rejouée et consignée** (ci-dessous). Elle a d'abord obligé à corriger l'INSTRUMENT

### Décider avant de coder
- [x] **`html, body { overflow: hidden }` est GARDÉ**, et la case était mal posée : elle prétendait que la règle ne sert que la Visionneuse. Les QUATRE surfaces sont des coques pleine hauteur — `#corpus-app`, `#search-app` et `#explo-app` sont en `height: 100%` avec leur propre `overflow-y: auto`, exactement comme `#app`. Et l'étape 1 a rendu trois d'entre elles conformes à 320 px SANS toucher à cette règle : ce qui les a réparées, c'est d'avoir encadré le contenu large. La lever referait du code qui marche et changerait le modèle de mise en page de la Visionneuse par-dessus le marché
- [x] **Le sort de la Visionneuse est tranché : ANNOTATION TACTILE**, décidé le 2026-09-05. Elle n'est donc pas une surface de consultation qu'on rendrait lisible faute de mieux — c'est l'écran de travail, et il doit rester un écran de travail au doigt. Le tactile proprement dit (cibles de 44 px, gestuelle de zoom) part dans **UX-8** ; ce qui reste ici est son premier étage, les tiroirs, parce qu'ils relèvent du 1.4.10 et qu'ils servent les deux largeurs
- [x] **Le focus ne s'échappe pas d'un tiroir ouvert** : la tabulation tourne entre la bascule et le contenu du tiroir, dans les deux sens, tant qu'il est ouvert — mesuré à 320 px sur la Visionneuse, où le focus sortait au 4ᵉ Tab et visitait 19 cibles sur 25 hors du tiroir. 0 sortie sur 25 depuis, dans les deux sens et sur les deux tiroirs ; gardé par `tests/test_e2e_tiroirs.py`, dont cinq tests tombent quand on désarme le piège
- [x] **Le panneau latéral et la boîte d'outils deviennent des tiroirs** sous un seuil mesuré : `#body` est une grille `240px | 1fr | 300px`, donc **540 px de chrome fixe** avant que le canevas reçoive un pixel. Escamotés, le canevas prend toute la largeur ; leur bascule est atteignable au clavier et rend le focus d'où il vient. `9c8934f` — et la coque grossissait à `min-content` (665 px à 320) tant que la colonne implicite de `#app` valait `auto`
- [x] Le seuil se lit sur la largeur où le CANEVAS devient inutilisable, pas sur un nombre rond — comme celui de la bande 1, qui valait 400 px et en demandait 560. Quatre seuils, chacun sur la largeur où son contenu cesse de tenir : 1079 · 899 · 659 (mesuré : 651 px de contenu) · 559
- [x] Le **tableau de croisement** a un comportement décidé pour les petites largeurs : il est intrinsèquement à deux dimensions, donc 1.4.10 admet le défilement — à condition qu'il soit CONTENU dans son conteneur et non subi par la page entière. Il l'était déjà (`overflow-x: auto`), mais son cadre n'était **atteignable qu'à la souris** : il lui manquait `tabindex`, son rôle et son nom, que l'étape 1 avait posés sur `.table-cadre` sans balayer la famille
- [x] Les deux tableaux des panneaux 🎯 Accord et 👥 Inter (`.accord-table`) sont mesurés : ils ne débordent **qu'à 320 px, de 38 px**. Le corpus de démonstration n'ayant aucun token relu, la mesure porte sur le balisage EXACT du rendeur injecté dans la vraie modale — la question était géométrique, pas documentaire. Ils avaient un cadre par ACCIDENT (`overflow-y: auto` force `overflow-x` à `auto`), qui faisait défiler la modale entière, titre et bouton Fermer compris ; ils ont le leur, atteignable au clavier
- [x] Le collage VERTICAL des en-têtes du croisement est tranché — **en le rendant effectif**, et l'objection ne tenait pas : sur 60 lignes, borner `.croise` à 70vh fait passer le défilement restant de la page de **1 018 px à 83 px**. La barre imbriquée REMPLACE celle de la page au lieu de s'y ajouter, et sous 70vh elle n'apparaît pas. L'en-tête tient sa place (y=301 avant et après défilement) là où il sortait à y=-599

### Vérifications
- [x] À **320 px**, chacune des quatre surfaces s'utilise sans défilement HORIZONTAL de la page (le défilement vertical est permis, et le contenu 2D peut défiler dans son propre cadre). Balayage du 2026-09-05 : 7 largeurs × 4 surfaces = 28 OK
- [x] À **768 px** (tablette), la Recherche et l'Exploration sont pleinement utilisables : filtres atteignables sans zoom, résultats lisibles, aucun tableau qui déborde de la page. Et la Visionneuse y gagne le canevas entier, les deux tiroirs étant fermés sous 899 px
- [x] Les largeurs figées ≥ 100 px de `static/style.css` sont revues une à une (dix, pas neuf — le compte de cette fiche était court d'une). Trois PLAFONDS qui ne forcent jamais rien ; quatre planchers tous sous 320 px et ancrés à droite, mesurés ; `--sidebar-w`/`--panel-w` désormais escamotés ; `.r-thumb` converti en `clamp(72px, 22vw, 130px)`, seul cas où la valeur coûtait quelque chose
- [x] La barre de navigation transverse et le lien d'évitement, injectés par `theme.js` sur les quatre pages, restent atteignables et ne masquent rien sous 400 px. Mesuré par `elementFromPoint` — « tient dans la fenêtre » ne dit rien d'un RECOUVREMENT : le lien arrive à `[8, 0, 121, 34]` et la barre à `[56, 1, 40, 30]`, au premier plan, aux quatre surfaces, à 320 comme à 400

### Ne pas répéter le silence d'axe
- [x] Un test E2E compare, à 320 px et 768 px, le RECTANGLE DE CHAQUE ÉLÉMENT à la largeur de la fenêtre — et surtout **pas** `documentElement.scrollWidth`, qui est la garde que cette fiche spécifiait au départ et qui aurait été VACANTE : `overflow: hidden` sur `html, body` rend `scrollWidth` égal à `clientWidth` alors même que 431 px de contenu sont hors champ. Mesuré le 2026-09-04 : les quatre surfaces passaient ce test-là au vert dans l'état actuel. `tests/test_e2e_reflow.py`, 12 tests. La démonstration est DANS le fichier (`test_la_garde_sur_scrollwidth_serait_vacante`) : un bloc de 900 px planté dans une fenêtre de 320 laisse `scrollWidth == clientWidth` pendant que la sonde le signale — la docstring cesse d'être une croyance
- [x] Le test distingue le contenu ATTEIGNABLE du contenu perdu : un cadre qui défile en interne est conforme au 1.4.10, un contenu clippé ne l'est pas — c'est exactement la différence que `scrollWidth` efface. Trois états, pas deux : encadré (un ancêtre défile et tient dans l'écran), escamoté (hors champ ET référencé par un `aria-controls`, donc un tiroir fermé), perdu. Les deux exemptions ont chacune leur contrôle, dont le NÉGATIF — le même panneau privé de sa bascule doit être signalé
- [x] L'audit axe reste sans violation sérieuse ou critique après la refonte, sur les quatre surfaces et les deux thèmes. Suite E2E entière : **138 tests verts**, dont les 20 d'UX-7. **Une limite à ne pas gommer** : axe s'exécute à la largeur PAR DÉFAUT, pas à 320 px. Il prouve donc l'absence de RÉGRESSION, pas la conformité du repli lui-même — le faire tourner aux petites largeurs est un gain réel, versé à UX-8 plutôt que réputé acquis ici

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
