---
passe: Préférence de police — ce que la géométrie ne dit pas
chantier: A11Y-2
duree: 30 min
derniere: 2026-09-06
---

# QA — le texte agrandi reste-t-il LISIBLE, et pas seulement dans l'écran

A11Y-2 est livré avec dix-huit tests neufs, et ils mesurent tous la même chose : le
contenu reste-t-il ATTEIGNABLE quand la police par défaut du navigateur grossit. C'est la
bonne question et ils la posent bien. Mais un rectangle qui tient dans l'écran peut
contenir un texte coupé, une pastille devenue minuscule à côté d'un mot devenu grand, ou
une disposition qui a basculé sans qu'on l'ait demandé.

Cette passe pose les questions qu'aucun `getBoundingClientRect` ne pose. Elle ne rejoue
pas les tests : ce qu'ils couvrent est écrit ci-dessous en toutes lettres, pour qu'on ne le
refasse pas à la main.

**Le geste à faire n'est PAS Ctrl+molette.** Le zoom du navigateur agrandit tout, `px`
compris, et ne mesure donc rien de ce chantier — c'est le 1.4.4 sous sa lecture facile, et
il passait déjà avant. Ce qui se règle ici est la **taille de police par défaut** :

- Chrome / Edge — `chrome://settings/appearance`, « Taille de police » → *Grande* ou
  *Très grande*, ou « Personnaliser les polices » pour poser une valeur exacte.
- Firefox — Paramètres → Général → Polices → « Taille », ou *Avancé* pour la valeur exacte.

**Firefox est la moitié non mesurée, et c'est sa raison d'être.** Les dix-huit tests
tournent dans Chromium et posent le réglage par le protocole CCP. Aucune machine n'a jamais
regardé cette application sous Firefox avec une grande police ; les deux navigateurs
n'appliquent pas ce réglage à la même chose (Firefox le pousse plus loin dans les formulaires).

**Où reportent les constats.** A11Y-2 est livré et son `Reste` est vide : un défaut trouvé
ici ne s'y recoche pas. Ce qui relève d'un SEUIL mal placé rouvre une fiche à part, avec la
largeur, la taille de police et le navigateur en tête. Ce qui relève du geste tactile part
dans `UX-8`. Et si la passe se dément elle-même sur un point, c'est le démenti qui compte,
pas la case.

## Ce que les tests couvrent déjà — ne pas le refaire ici

- `tests/test_e2e_police.py` : à 1280/24, 1280/20, 768/20 et 320/20, sur les quatre
  surfaces, aucun élément n'est hors champ sans cadre ni bascule. Plus deux gardes d'amont
  — la racine vaut bien 81,25 % de la préférence, et la page a bien rendu.
- Le même fichier vérifie que le zoom UI (`A−`/`A+`) fonctionne toujours et survit à un
  rechargement, en lisant le RECTANGLE et non les valeurs calculées.
- `tests/test_e2e_reflow.py` et `test_e2e_a11y.py` : reflow à 320 et 768 px, et audit axe
  sur les quatre surfaces × deux thèmes — **à la police par défaut**, dans les deux cas.
- Mesuré le 2026-09-06 et non à revérifier : le rendu à la police par défaut est identique
  au pixel près à celui d'avant le chantier (2865 rectangles comparés).

## Reste

### Le réglage prend, et la passe mesure donc quelque chose

- [ ] Après avoir posé une grande police et rechargé, le texte courant de la Bibliothèque est visiblement plus grand qu'avant — si rien ne bouge, le réglage n'a pas pris et TOUTES les cases suivantes seraient vides de sens
- [ ] Le même réglage produit un effet dans les DEUX navigateurs essayés, et le navigateur est nommé en tête du constat

### Ce que la sonde ne voit pas — le texte coupé dans son cadre

- [ ] Exploration, grande police : le gabarit du champ morpho se coupe (« filtre morpho (ex. Tense=Pas »). Constat CONNU en Chromium à 24 px ; le champ porte `aria-label="Filtrer par trait morphologique"`, donc son nom accessible est intact. À confirmer, et à dire s'il se coupe plus tôt ailleurs
- [ ] Aucun libellé de bouton ne se coupe en milieu de mot sur les quatre surfaces — un libellé qui passe à la ligne est normal, un libellé tronqué ne l'est pas
- [ ] Les en-têtes du tableau de la Bibliothèque restent lisibles en entier, ou passent à la ligne — aucun n'est coupé par la colonne voisine
- [ ] Dans la Visionneuse, le nom de planche et le fil d'Ariane se raccourcissent par ellipse (« … ») et non par coupure sèche

### Ce que la bascule anticipée change — l'effet des seuils en em

Les seuils sont en `em` : une grande police fait basculer la disposition étroite plus tôt.
C'est voulu. Ces cases demandent si le résultat est UTILISABLE, pas s'il est conforme.

- [ ] Sur un écran large (1280 px ou plus) avec une très grande police, la barre latérale devient un tiroir : la bascule qui la rouvre est visible, et on comprend où est passé l'arbre de structure
- [ ] Vers 768 px avec une grande police, la légende de couleurs de la barre d'état disparaît : on peut encore comprendre le code des couleurs sans elle, ou bien c'est un manque à écrire
- [ ] Aucune bascule ne se produit à un moment qui SURPREND : passer d'un cran de police au suivant ne réorganise pas l'écran sans qu'on voie pourquoi
- [ ] En largeur de téléphone avec une grande police, la barre de navigation s'enroule sur deux lignes et le menu « Aa » reste atteignable — c'est par lui qu'on revient en arrière si l'on est allé trop loin

### Les marques restées physiques

Pastilles, jauges, vignettes et bordures sont restées en pixels par décision. Elles
paraissent donc plus petites à mesure que le texte grandit.

- [ ] Les pastilles de statut de planche restent distinguables à grande police : on voit encore de quelle couleur elles sont, à la distance de lecture habituelle
- [ ] Les jauges (progression de lot, distribution, accord) restent lisibles : on distingue encore le rempli du vide
- [ ] Les bordures et l'anneau de focus restent visibles — un trait d'un pixel qui devient invisible à côté d'un texte de 24 px est un constat à écrire
- [ ] Aucune de ces marques ne paraît CASSÉE plutôt que petite : rien ne déborde de son cadre, rien ne chevauche un texte

### Le zoom UI et la préférence, ensemble

- [ ] Avec une grande police système, les quatre crans du zoom UI (`A−`, `A+`, `↺`) agissent encore et l'écran reste utilisable aux deux extrêmes
- [ ] Le réglage combiné le plus agressif qu'on ose (grande police + zoom UI au maximum) laisse encore atteindre les commandes principales de la Visionneuse
- [ ] Après rechargement, le zoom UI est retrouvé et la police système aussi — les deux réglages ne se mangent pas l'un l'autre

### Ce que la passe ne peut pas juger

À laisser cochées vides et à écrire en clair si l'on constate quelque chose — ce sont les
angles morts CONNUS de cette passe, pas des vérifications.

- [ ] Le zoom navigateur (Ctrl+molette) n'est PAS l'objet de cette passe : il agrandit les `px` comme le reste, il passait déjà avant le chantier, et le confondre avec la préférence de police fausserait les deux
- [ ] La taille des cibles au doigt relève d'`UX-8` : les rencontrer ici est normal, les traiter serait déborder
- [ ] Un lecteur d'écran ne se juge pas ici — l'arbre d'accessibilité ne change pas avec la taille de police, et `test_e2e_a11y.py` en garde la structure
