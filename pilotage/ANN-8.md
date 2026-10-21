---
chantier: ANN-8
statut: à venir
---

# ANN-8 — l'annotation d'aujourd'hui : les défauts que l'usage a relevés

**Arrêté sur** — rien de commencé. Fiche ouverte le 2026-10-21 en sortant d'`ANN-6` les
défauts de l'annotation ACTUELLE, qui ne dépendent ni du relevé ni du modèle des grilles
(`ANN-7`) : ils se traitent tôt, et les testeurs en profitent sans attendre la page Annotation.

## Reste

### Ce que l'écran dit
- [ ] **Le bouton de verrou dit ce qu'il protège** — attendu : son libellé ne laisse plus
  croire qu'il faut verrouiller avant d'annoter. Retour d'usage : « faut-il verrouiller la
  planche avant de l'annoter ? À quoi sert le verrouillage ? ». Il protège une planche des
  traitements automatiques et n'empêche aucune annotation humaine ; « Verrouiller la
  planche » se lit comme une réservation
- [ ] **Le premier Ctrl+Z ou la première note après un redémarrage ne gèle plus l'écran** —
  attendu : dit, ou fermé. Mesuré : 9 à 17 secondes sans rien afficher, le temps de charger
  le moteur de langue ; 0,01 s ensuite. Le préchauffage existe (`BD_NLP_PREWARM`) et il est
  commenté dans `deploy/docker-compose.yml`. Annuler un lien de locuteur ne réindexe rien :
  ce chargement y est payé pour rien
- [ ] **Le contraste élevé est audité quelque part** — attendu : tranché. L'audit
  d'accessibilité du dépôt ne pose que le thème, clair ou sombre ; un mutant qui cache la
  phrase de « Situation » en contraste élevé passe toute la suite

### Le locuteur et l'annulation
- [ ] **Un locuteur hérité sur une région devenue case se voit, ou part avec le type** —
  attendu : tranché. Une bulle qui a un locuteur et devient case le garde : invisible à
  l'écran, il compte encore au registre, dans la Recherche et les exports. L'annulation peut
  aussi en reposer un sur une case, la garde ne tenant que la route — écrit dans son
  commentaire et décrit par un test. « Aucune case ne porte de locuteur » n'est pas un
  invariant de la base. Non su : si la production en porte déjà
- [ ] **Annuler la suppression d'une région rend aussi son locuteur** — attendu : Ctrl+Z
  d'une suppression rend ce qui a été supprimé. Reproduit, antérieur : une case avec une
  situation, dessous un cartouche avec locuteur, note et tag ; supprimer la case, puis
  Ctrl+Z : case, cartouche, note et tag reviennent, le locuteur du cartouche et la situation
  de la case non. Cause LUE : l'instantané d'une région n'emporte que ses colonnes et son
  annotation. À rapprocher d'`UX-5`

### Les champs à propositions — laissé ouvert par le correctif du 2026-10-13
- [ ] **La région des messages existe avant son premier message, sur les cinq surfaces** —
  attendu : le premier message d'une page est annoncé par un lecteur d'écran, mesuré avec
  l'un d'eux. Aujourd'hui la région naît AVEC son premier message, et ce premier message
  est désormais « Rien n'est ajouté… ». L'auteur du correctif l'avait posée d'avance dans le
  gabarit de l'Atelier seul : non porté — rien n'est mesuré, et une surface sur cinq
- [ ] **Pendant que la liste du registre se recharge, ↓ puis Entrée ne prend pas un nom de la
  liste d'avant** — attendu : tranché. Entre une frappe et le retour de sa liste, ↓ puis
  Entrée prend la proposition surlignée de la liste précédente : elle est à l'écran, le
  geste est explicite. La fermer rend les flèches inertes le temps de la lecture
- [ ] **Plusieurs personnages du même nom se départagent à l'écran** — attendu : tranché.
  Quand plusieurs homonymes exacts existent déjà, Entrée prend le premier dans l'ordre du
  registre — nom, puis série, celui sans série d'abord —, sans le dire (mesuré, inchangé).
  Le guide le dit ; aucun test ne fige ce choix
- [ ] **Les deux champs de personnage savent ce que l'autre vient de créer** — attendu : dit,
  ou fermé. « Zed » créé par la boîte personnage, puis tapé vite dans le champ du locuteur,
  se décide sur la liste de ce champ-là — périmée seulement si « Zed » y avait déjà été
  cherché. Rapporté par l'auteur du correctif, non rejoué
- [ ] **Après une validation, la première ↓ surligne une proposition** — attendu : une seule
  flèche suffit. Antérieur, dans les champs à propositions : la première rouvre la liste
  sans rien surligner, il en faut une seconde
- [ ] **À 320 px sous une police de 24, le champ ne dépasse pas du tiroir dans l'image** —
  attendu : aucun défilement en largeur du tiroir. Antérieur, mesuré dans l'image : le
  champ « dimension : valeur » va jusqu'à 326,6 px et le tiroir défile ; sur le poste il
  s'arrête à 318,6 px. Les phrases d'aide, elles, tiennent. À rapprocher d'`UX-7`
- [ ] **La règle d'Entrée du champ « dimension : valeur » vit dans un module pur** —
  attendu : tranché. Elle ne dépend plus de l'horloge : une table de vérité sous Node la
  couvrirait en millisecondes, là où chaque variante coûte un test navigateur de cinq à dix
  secondes. Recommandé par l'auteur du correctif, non fait : un script de plus au gabarit

### Les tags et la Note, tant que les grilles n'existent pas
- [ ] **Une apostrophe ou un accent ne font pas deux tags** — attendu : « c’est pluriel »
  tapé avec l'apostrophe typographique ou avec la droite désigne le même tag. Lu le
  2026-10-12 : `socle._norm_tag` ne normalise que la casse et les espaces, et le libellé est
  unique à l'octet. Le guide écrit ses tags avec l'apostrophe typographique ; un clavier
  tape la droite
- [ ] **La référence d'une autre bulle écrite dans la Note ne devient pas fausse en silence**
  — attendu : dit aux annotateurs, ou remplacé par un lien que l'outil tient. Pour un
  chevauchement, le guide demande d'écrire dans la Note la référence de l'autre bulle telle
  que le logiciel l'affiche. Cette référence est DÉRIVÉE de l'ordre de lecture
  (`database.citations_regions`), jamais stockée : une case ajoutée ou réordonnée, et la même
  référence désigne une autre bulle

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
