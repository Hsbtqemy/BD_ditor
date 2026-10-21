---
chantier: ANN-8
statut: interrompu
---

# ANN-8 — l'annotation d'aujourd'hui : les défauts que l'usage a relevés

**Arrêté sur** — 2026-10-21, `da108ba` : neuf des quatorze cases sont faites, dans le lot 1, sur
`dev` en local (`9c8a9cc`, `3d22f37`, `0e96424`, `a685f30`, `988876c`, `d87bbdc`, `da108ba`). Deux
le sont à moitié — le premier gel après un redémarrage, la région des messages. Quatre ont leur
décision, prise par Hugo le jour même sur recommandation, et restent à coder : le locuteur d'une
région devenue case, ↓ puis Entrée pendant un rechargement, les homonymes, la référence d'une
bulle dans la Note. Le
libellé du verrou est une proposition, à juger à la passe. D'où `interrompu`.

**Ouverte le 2026-10-21** — rien de commencé. Fiche ouverte le 2026-10-21 en sortant d'`ANN-6` les
défauts de l'annotation ACTUELLE, qui ne dépendent ni du relevé ni du modèle des grilles
(`ANN-7`) : ils se traitent tôt, et les testeurs en profitent sans attendre la page Annotation.

## Reste

### Ce que l'écran dit
- [x] **Le bouton de verrou dit ce qu'il protège** — attendu : son libellé ne laisse plus
  croire qu'il faut verrouiller avant d'annoter. Retour d'usage : « faut-il verrouiller la
  planche avant de l'annoter ? À quoi sert le verrouillage ? ». Il protège une planche des
  traitements automatiques et n'empêche aucune annotation humaine ; « Verrouiller la
  planche » se lit comme une réservation **Fait le 2026-10-21, `a685f30`** : « 🔓 Protéger
  des passes auto », « 🔒 Protégée par … », et l'infobulle explique — segmentation, bulles et
  OCR sautent la planche, l'annotation reste ouverte à tous. Une PROPOSITION, que Hugo juge à la
  passe du lot ; le serveur, la Bibliothèque et le guide disent encore « verrou »
- [ ] **Le premier Ctrl+Z ou la première note après un redémarrage ne gèle plus l'écran** —
  attendu : dit, ou fermé. Mesuré : 9 à 17 secondes sans rien afficher, le temps de charger
  le moteur de langue ; 0,01 s ensuite. Le préchauffage existe (`BD_NLP_PREWARM`) et il est
  commenté dans `deploy/docker-compose.yml`. Annuler un lien de locuteur ne réindexe rien :
  ce chargement y est payé pour rien *À moitié, 2026-10-21, `9c8a9cc` et `a685f30`* :
  Ctrl+Z ne charge plus le moteur quand l'inversion ne réindexe rien (un lien, l'annulation
  d'une création) ; quand il le faut, l'Atelier dit au bout d'1,5 s que l'annulation
  travaille. La première NOTE après un redémarrage gèle encore : reste à activer
  `BD_NLP_PREWARM` en production, un geste de Hugo
- [x] **Le contraste élevé est audité quelque part** — attendu : tranché. L'audit
  d'accessibilité du dépôt ne pose que le thème, clair ou sombre ; un mutant qui cache la
  phrase de « Situation » en contraste élevé passe toute la suite **Fait le 2026-10-21,
  `da108ba`** : `tests/test_e2e_a11y_contraste.py` audite en contraste élevé, sur chacun des
  deux thèmes, les cinq surfaces au chargement, la Situation d'une case et les deux champs de
  profil ; il vérifie d'abord que le contraste est posé sur la racine et que la phrase attendue
  est visible

### Le locuteur et l'annulation
- [ ] **Un locuteur hérité sur une région devenue case se voit, ou part avec le type** —
  attendu : tranché. Une bulle qui a un locuteur et devient case le garde : invisible à
  l'écran, il compte encore au registre, dans la Recherche et les exports. L'annulation peut
  aussi en reposer un sur une case, la garde ne tenant que la route — écrit dans son
  commentaire et décrit par un test. « Aucune case ne porte de locuteur » n'est pas un
  invariant de la base. Non su : si la production en porte déjà **Tranché par Hugo le 2026-10-21 :
  le locuteur part avec le type**, journalisé ; l'annulation refuse un locuteur sur un type qui
  n'en porte pas ; un outil à blanc dit ce que la base porte déjà. ~½ journée — pas encore codé
- [x] **Annuler la suppression d'une région rend aussi son locuteur** — attendu : Ctrl+Z
  d'une suppression rend ce qui a été supprimé. Reproduit, antérieur : une case avec une
  situation, dessous un cartouche avec locuteur, note et tag ; supprimer la case, puis
  Ctrl+Z : case, cartouche, note et tag reviennent, le locuteur du cartouche et la situation
  de la case non. Cause LUE : l'instantané d'une région n'emporte que ses colonnes et son
  annotation. À rapprocher d'`UX-5` **Fait le 2026-10-21, `9c8a9cc`** : l'instantané profond
  garde les IDENTIFIANTS des liens — locuteur, présence, attribut de case —, et rien d'autre ;
  l'annulation les repose sous les questions d'`AUTH-14`, lien par lien. Un lien qui échoue ne
  revient pas, la région revient, et la réponse dit combien (`liens_non_rendus`), sans rien
  nommer ; l'Atelier l'affiche

- [ ] **Une case ou une boîte personnage qui devient zone de texte perd ce que son nouveau type
  ne montre pas** — attendu : le miroir de la décision du locuteur, demandé par Hugo le
  2026-10-21 (« c'est utile »). Une case devenue bulle gardait sa situation
  (`region_attribut`), une boîte personnage devenue bulle son personnage montré
  (`personnage_presence`) : ni l'un ni l'autre ne se voit sur une bulle. Ils partent avec le
  type, dans le même acte, et un seul Ctrl+Z les rend ; ce que la base porte déjà se dit par
  un outil à blanc. Relevé par l'agent qui a codé le locuteur

### Les champs à propositions — laissé ouvert par le correctif du 2026-10-13
- [ ] **La région des messages existe avant son premier message, sur les cinq surfaces** —
  attendu : le premier message d'une page est annoncé par un lecteur d'écran, mesuré avec
  l'un d'eux. Aujourd'hui la région naît AVEC son premier message, et ce premier message
  est désormais « Rien n'est ajouté… ». L'auteur du correctif l'avait posée d'avance dans le
  gabarit de l'Atelier seul : non porté — rien n'est mesuré, et une surface sur cinq
  *À moitié, 2026-10-21, `d87bbdc`* : `theme.js` pose la région vide au chargement des cinq
  surfaces, et `toast()` la retrouve ; l'Atelier pose de même celle de l'annonce d'un conflit.
  Un test relève l'ordre des naissances. Ce qu'un lecteur d'écran prononce n'est pas mesuré :
  c'est l'attendu, et il reste
- [ ] **Pendant que la liste du registre se recharge, ↓ puis Entrée ne prend pas un nom de la
  liste d'avant** — attendu : tranché. Entre une frappe et le retour de sa liste, ↓ puis
  Entrée prend la proposition surlignée de la liste précédente : elle est à l'écran, le
  geste est explicite. La fermer rend les flèches inertes le temps de la lecture **Tranché par
  Hugo le 2026-10-21 : à Entrée, revérifier que la proposition surlignée répond encore à la
  saisie** — pas encore codé
- [ ] **Plusieurs personnages du même nom se départagent à l'écran** — attendu : tranché.
  Quand plusieurs homonymes exacts existent déjà, Entrée prend le premier dans l'ordre du
  registre — nom, puis série, celui sans série d'abord —, sans le dire (mesuré, inchangé).
  Le guide le dit ; aucun test ne fige ce choix **Tranché par Hugo le 2026-10-21 :
  Entrée ne décide pas, la liste se réduit aux homonymes, chacun avec sa série** — pas encore
  codé
- [x] **Les deux champs de personnage savent ce que l'autre vient de créer** — attendu : dit,
  ou fermé. « Zed » créé par la boîte personnage, puis tapé vite dans le champ du locuteur,
  se décide sur la liste de ce champ-là — périmée seulement si « Zed » y avait déjà été
  cherché. Rapporté par l'auteur du correctif, non rejoué **Fermé le 2026-10-21, `0e96424`** :
  rejoué d'abord — il créait un second « Zed » ; une création avance `registreModifie`, et une
  liste lue avant ne décide plus
- [x] **Après une validation, la première ↓ surligne une proposition** — attendu : une seule
  flèche suffit. Antérieur, dans les champs à propositions : la première rouvre la liste
  sans rien surligner, il en faut une seconde **Fait le 2026-10-21, `0e96424`** : la flèche
  comptait les lignes restées de la liste précédente ; elle compte celle qui va s'afficher,
  dans les trois sortes de champs
- [x] **À 320 px sous une police de 24, le champ ne dépasse pas du tiroir dans l'image** —
  attendu : aucun défilement en largeur du tiroir. Antérieur, mesuré dans l'image : le
  champ « dimension : valeur » va jusqu'à 326,6 px et le tiroir défile ; sur le poste il
  s'arrête à 318,6 px. Les phrases d'aide, elles, tiennent. À rapprocher d'`UX-7` **Fait le
  2026-10-21, `988876c`** : `.tag-input-wrap > input` est borné à sa colonne, ce qui ne dépend
  d'aucune chasse ; joué sur trois zones, sous la police du navigateur puis sous une chasse
  forcée plus large. Pas encore rejoué dans l'image : la passe du lot le fera
- [x] **La règle d'Entrée du champ « dimension : valeur » vit dans un module pur** —
  attendu : tranché. Elle ne dépend plus de l'horloge : une table de vérité sous Node la
  couvrirait en millisecondes, là où chaque variante coûte un test navigateur de cinq à dix
  secondes. Recommandé par l'auteur du correctif, non fait : un script de plus au gabarit
  **Fait le 2026-10-21, `0e96424`** : `static/lib/propositions.js` (`BDPropositions`), sous
  table Node ; l'écran garde ce qui dépend du temps

### Les tags et la Note, tant que les grilles n'existent pas
- [ ] **L'infobulle de la ligne « Citation » de l'Atelier ne pousse plus à citer une bulle par sa
  citation** — attendu : elle dit que la citation se dérive de l'ordre de lecture et change
  quand une case bouge, et renvoie à l'identifiant de la ligne « Région » pour désigner une
  bulle. Aujourd'hui : « Repère stable à l'échelle de l'album » (`templates/index.html`). Hugo,
  2026-10-21 : « pourquoi pas »
- [ ] **Le guide d'annotation des linguistes fait écrire « #123 »** — attendu : corrigé de leur
  côté. La phrase « la référence de l'autre bulle telle que le logiciel l'affiche » vient de
  ce guide, qui n'est pas dans le dépôt ; le guide d'usage du dépôt le dit depuis `72447d8`
- [x] **Une apostrophe ou un accent ne font pas deux tags** — attendu : « c’est pluriel »
  tapé avec l'apostrophe typographique ou avec la droite désigne le même tag. Lu le
  2026-10-12 : `socle._norm_tag` ne normalise que la casse et les espaces, et le libellé est
  unique à l'octet. Le guide écrit ses tags avec l'apostrophe typographique ; un clavier
  tape la droite **Fait le 2026-10-21, `3d22f37` et `0e96424`** : `database.cle_tag` — NFC,
  apostrophes ramenées à la droite, minuscules, espaces compactés —, appelable en SQL, par
  laquelle un libellé saisi cherche son tag partout ; son jumeau navigateur `cleTag` lit la
  même table, `tests/cas-tags.json`. Aucune migration : deux tags d'avant de même clé restent
  deux lignes, et une saisie n'en attache qu'un
- [ ] **La référence d'une autre bulle écrite dans la Note ne devient pas fausse en silence**
  — attendu : dit aux annotateurs, ou remplacé par un lien que l'outil tient. Pour un
  chevauchement, le guide demande d'écrire dans la Note la référence de l'autre bulle telle
  que le logiciel l'affiche. Cette référence est DÉRIVÉE de l'ordre de lecture
  (`database.citations_regions`), jamais stockée : une case ajoutée ou réordonnée, et la même
  référence désigne une autre bulle **Tranché par Hugo le 2026-10-21 : le guide
  dit d'écrire l'identifiant stable « #123 »** ; un lien tenu par l'outil va dans `ANN-7` — pas
  encore écrit

## Contexte

**D'où ces cases viennent.** Des retours d'usage des testeurs du 2026-10-12, de la relecture
croisée des correctifs du même jour, et de ce que le correctif des champs du 2026-10-13 a
laissé ouvert — toutes écrites dans `ANN-6`, qui mêlait jusque-là deux choses : la page
Annotation et le relevé, qui attendent le modèle d'`ANN-7`, et ces défauts, qui n'attendent
rien. Découpage décidé avec Hugo le 2026-10-21. Les cases sont recopiées telles quelles ; leur
historique (mesures, reproductions, correctifs voisins déjà faits) reste dans `ANN-6`.

**Ce qui reste chez `ANN-6`.** Le narrateur d'un récitatif (à trancher avec les linguistes),
l'organisation du travail des stagiaires, les tags du guide créés d'avance, la maquette et la
page Annotation, le relevé.

**Ce que le basculement vers les grilles changera ici.** Les deux cases de la dernière zone
portent sur les tags d'aujourd'hui : quand les tags deviendront des grilles (`ANN-7`), la
normalisation d'un libellé et la référence d'une bulle se reposeront dans le modèle. Les
traiter avant vaut tant que des stagiaires taguent en attendant.

**Voisinage.** `UX-5` (la granularité de Ctrl+Z, à rapprocher de l'annulation du locuteur),
`UX-7` (le champ à 320 px), `CONC-4` (deux personnes sur le même locuteur), `A11Y-3`.
