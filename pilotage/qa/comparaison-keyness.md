---
passe: Comparaison A/B classée par keyness
chantier: ANA-4
duree: 10 min
---

# QA — la comparaison se classe par écart ou par keyness, et l'écran suit la mesure

Le calcul est verrouillé par des valeurs connues, la route et l'export par deux tests, et
l'écran par deux tests navigateur semés sur un jeu FABRIQUÉ. Ce que la passe regarde est
ce que la mesure fait sur de VRAIES bulles : les deux albums de la base, OCR compris, bruit
compris (« 9u », « cp » sont des lectures de l'OCR, pas des mots).

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`, **sous `admin-bd`** : il lit les
deux albums, et la comparaison porte sur tout ce qu'on lit. Les rangs cités viennent d'une
mesure faite sur cette même base le 2026-09-11 ; si l'index des tokens a été refait depuis,
ils peuvent bouger, et ce n'est pas un défaut.

**Réglage** : *Exploration*, vue « Comparaison A / B », distribuer par « lemme » ;
sous-corpus A = album « esther v1 », sous-corpus B = album « Eau-terre ».

### Le sélecteur n'existe qu'en comparaison

- [x] « Classer par » est visible en vue « Comparaison A / B », et disparaît en Distribution, en Concordance et en Croisement
- [x] Par défaut il dit « écart de fréquence relative », et l'adresse de la page ne contient pas `metrique`

### Ce que la keyness change

- [x] À l'écart, « de » est en tête des « Sur-représentés en B », et « pas » est 2e des « Sur-représentés en A »
- [x] Passé à « keyness (log-vraisemblance) », l'adresse gagne `metrique=ll`, et la ligne d'information — la ligne grise au-dessus des deux colonnes, à gauche du bouton d'export — CONTIENT « keyness : log-vraisemblance G², qui pèse l'écart par le nombre d'occurrences ». C'est une parenthèse au milieu d'une phrase plus longue (« Comparaison par lemme — A : … occ. · B : … occ. (…) »), et non une ligne à elle seule : avant la bascule, la même parenthèse dit « différence de fréquence relative », et c'est ce fragment-là qui change
- [x] En keyness, « phat » passe en tête de B et « de » descend (6e à la mesure) ; « pas » descend dans A (9e à la mesure) — un mot fréquent des deux côtés perd la tête, un mot propre à un côté la prend
- [x] Aucun mot ne change de COLONNE entre les deux mesures : seul l'ordre bouge
- [x] En keyness, la barre de la première ligne de chaque colonne est la plus longue, et les suivantes décroissent : la barre montre la force de la mesure choisie
- [x] Le survol du compte « A/B » d'une ligne affiche aussi « G² » et sa valeur

### L'état se partage, et l'export suit

- [x] Recharger la page garde « keyness » dans le sélecteur et le même ordre
- [x] L'adresse copiée dans un nouvel onglet rouvre la même comparaison, classée par keyness
- [x] « ⤓ Exporter (CSV) » télécharge un fichier dont l'en-tête porte les deux colonnes `diff` et `ll`, et dont les lignes suivent l'ordre de la keyness : « pas » n'y est plus 2e

### Étroit, clavier, thèmes

- [x] À 375 px, la barre de réglages passe à la ligne sans que la page déborde de côté
- [x] « Classer par » s'atteint à la tabulation, se change aux flèches, et un lecteur d'écran l'annonce par son libellé
- [x] En thème clair comme en sombre, les barres des deux colonnes se distinguent l'une de l'autre
