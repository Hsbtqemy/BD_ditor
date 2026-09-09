---
chantier: NLP-3
statut: livré
---

# NLP-3 — normalisation de casse de l'OCR (capitales vers minuscules)

**Arrêté sur** — la couche NLP est hors d'atteinte de la passe, mesuré plutôt que supposé,
et la propriété qui l'assure est verrouillée ; commit `c0f3a31`, 9 septembre. L'arbitrage
et sa mise en œuvre sont au commit `35a28ce`. Poussé sur `origin/dev` le 9 septembre — les
trois commits de code vivent sur une ref d'intégration, le démenti tombe. `main` n'a pas
suivi : c'est la branche DÉPLOYÉE, et l'avancer est un geste à part.

## Reste

### Arbitrage
- [x] L'option retenue est écrite et argumentée dans `docs/` : `docs/normalisation-casse.md` — ni (a) ni (b) ni (c) telles quelles, mais le geste humain outillé, parce que normaliser la casse est une INTERPRÉTATION et non une dérivation
- [x] La question « modifie-t-on le texte STOCKÉ ou seulement l'AFFICHAGE ? » est tranchée explicitement, avec sa réversibilité : stocké, mais jamais sans geste ; réversible par construction tant que la source était capitale (`upper(normalisé) == original`, éprouvé)
- [x] Le choix « option par album ou réglage global » est tranché : AUCUN réglage — la question se dissout dès lors que la normalisation est un geste

### Mise en œuvre
- [x] La règle est un cœur partagé (`casse.py`) doublé d'un jumeau navigateur (`static/lib/casse.js`), et leur accord est MESURÉ par une table de cas lue par les deux suites (`tests/cas-casse.json`)
- [x] La garde `only_upper` vit DANS la fonction et non chez l'appelant : une ligne non intégralement capitale n'est jamais touchée, et le geste est idempotent
- [x] Le geste unitaire existe dans le mode Transcription (bouton `#tr-casse`), éteint quand il n'a rien à faire, et enregistre par le même chemin qu'une frappe
- [x] Le rattrapage en lot existe (`tools/normaliser_casse.py`, `--album`/`--planche`/`--dry-run`), ne pose pas `regions.touche`, se journalise en `agent_type='moteur'` donc hors Ctrl+Z, et réindexe le FTS
- [x] Un test couvre un sigle, un nom propre et une majuscule de début de phrase — nommément, plus les trois règles propres à la BD (saut de ligne, points de suspension, point d'un sigle)
- [x] Les limites sont verrouillées COMME limites, avec leur raison : `FBI` et les noms propres ne sont pas relevés, et un test le dit pour que la relecture suivante ne « corrige » pas en devinant
- [x] La couche NLP est prouvée hors d'atteinte : `normaliser(t).lower() == t.lower()` verrouillé sur toute la table, plus un bout-en-bout montrant qu'une correction grammaticale humaine survit à la passe (`obsolete = 0`, même ordre) et que `relecture_planches` ne recule pas
- [x] Ce que la passe COÛTE est écrit, et pas seulement ce qu'elle apporte : noms propres à relever, contraste de casse effacé du texte par une passe corpus-entier, et pas d'annulation outillée

## Contexte

**Une case de la version d'origine a été réécrite, et il faut le savoir.** Elle disait
« l'OCR pré-remplit en casse normalisée sans jamais écraser une correction humaine
(`only_empty` préservé) » — ce qui présupposait l'option (b), la normalisation au
pré-remplissage. L'arbitrage l'a écartée : `pipeline/ocr.py` n'est pas touché, il écrit
toujours le verbatim du moteur. La cocher aurait été une fausse déclaration ; la laisser
ouverte aurait laissé croire à un reste de travail qui n'existe pas. Elle est donc
remplacée par ce qui a réellement été construit.

**Ce que l'arbitrage a retenu, en une phrase.** Le numéro éditorial, les centimètres et le
statut de relecture se dérivent — donc ne se stockent pas — parce qu'ils se CALCULENT.
« TINTIN » → « Tintin » ne se calcule pas, ça se devine ; et la doctrine de la maison pour
ce qui se devine est celle de l'OCR : pré-remplir, laisser corriger. La normalisation est
donc une proposition visible, demandée, et retouchable — jamais une transformation
appliquée dans le dos de qui transcrit.

**L'option (c) du backlog est tombée sur une mesure, pas sur un avis.** « Ne minusculer
qu'à l'affichage » est faux tant que l'affichage est ÉDITABLE : la zone de saisie du mode
Transcription reçoit `ocr_texte`, et `trNext()` PUT dès qu'elle diffère du stocké.
Minusculer ce rendu aurait réécrit tout le corpus en minuscules par simple navigation
bulle-à-bulle, sans qu'un caractère soit tapé.

**Un angle mort d'accessibilité a été trouvé en route, et il n'est PAS à ce chantier.**
`tests/test_e2e_a11y.py` n'exerce que les modes Édition et Annotation ; il n'entre jamais
en mode Transcription, dont la section est `hidden` au chargement. Ce n'est donc pas le
`disabled` du bouton neuf qui échappe à axe — c'est tout le panneau, `#tr-prev`,
`#tr-next` et `#tr-exit` compris, et depuis toujours. NLP-3 n'introduit aucune couleur
neuve (`.ghost`, zéro règle CSS ajoutée), donc le risque propre à ce chantier est nul ;
l'angle mort, lui, reste ouvert. Le fermer demande un décor qui entre en Transcription
avec une bulle semée EN CAPITALES — sans quoi le bouton reste désactivé et l'exclusion
d'axe rejoue. A11Y-2 étant clos, cela mérite sa propre fiche : **à ouvrir, pas encore
fait**. Écrit ici pour que ça ne se perde pas.

**Recoupe ANN-3**, et l'ordre annoncé était le bon : c'est NLP-3 qui devait passer d'abord.
Le gazetteer y gagne deux choses. La comparaison insensible à la casse n'est plus une
question ouverte — le corpus reste en capitales, et c'est `casse.py` qui sait les plier.
Et le relevé des noms propres, laissé ouvert ici exprès, est exactement ce qu'ANN-3
apportera : le jour où le gazetteer existe, la règle gagne une sixième clause sans que rien
d'autre ne bouge.
