---
chantier: UX-7
statut: à venir
audit: AUDIT.md
---

# UX-7 — rendre les surfaces utilisables sous 1 000 px

**Point de départ** — décision prise le 2026-09-04, en tranchant le constat T7 de
l'audit. Rien n'est commencé, mais l'état des lieux est MESURÉ (voir ci-dessous), et il
déplace le chantier : la tablette va déjà bien, c'est le téléphone qui perd du contenu.

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

**La tablette n'a rien à réparer.** Aucune des quatre surfaces ne déborde à 768 px — ce qui
retire du chantier la motivation d'usage la plus immédiate, et le réduit au téléphone.

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

### Décider avant de coder
- [ ] Le sort d'`html, body { overflow: hidden }` est tranché : il sert la Visionneuse (coque pleine hauteur) et pénalise les trois autres surfaces, où il change un débordement en contenu perdu. Le lever surface par surface est probablement la moitié du chantier, à lui seul
- [ ] Le sort de la **Visionneuse** est tranché par écrit : viser l'annotation tactile engage les cibles de 44 px (WCAG 2.5.5) et une gestuelle de zoom, c'est-à-dire un autre chantier ; se limiter à la CONSULTATION lisible sous 1 000 px est un travail sans commune mesure. Les deux sont défendables, mais pas au même prix
- [ ] Le **tableau de croisement** a un comportement décidé pour les petites largeurs : il est intrinsèquement à deux dimensions, donc 1.4.10 admet le défilement — à condition qu'il soit CONTENU dans son conteneur et non subi par la page entière

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
