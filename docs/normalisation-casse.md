# Normalisation de casse de l'OCR (NLP-3)

> Décision arrêtée le 2026-09-09. Trois questions étaient ouvertes depuis le backlog :
> quelle option, sur le texte STOCKÉ ou seulement AFFICHÉ, et avec quel réglage. Les
> réponses tiennent en une phrase : **le stocké reste verbatim, la normalisation est un
> geste humain outillé, et il n'y a aucun réglage.**

## Le point de départ

Le lettrage de la bande dessinée franco-belge est en CAPITALES. EasyOCR restitue donc du
tout-majuscule — « ALORS TINTIN, LE F.B.I. T'ATTEND À NEW YORK ? » — et c'est fidèle : les
capitales sont **un trait du médium**, pas un défaut de saisie.

C'est aussi illisible en concordance, où l'on parcourt deux cents lignes d'affilée.

## Ce qui n'était pas cassé, et qu'il fallait vérifier avant de toucher à quoi que ce soit

Rien, techniquement. Toutes les mécaniques qui lisent la transcription plient déjà la
casse, chacune de son côté :

| Surface | Comment elle traite la casse | Où |
|---|---|---|
| Recherche FTS5 | tokenizer `unicode61 remove_diacritics 2` : insensible à la casse | `database._FTS_SQL` |
| Analyse spaCy | minuscule AVANT traitement (sinon tout passe pour des noms propres) | `pipeline/nlp.analyse` |
| Concordance KWIC | le pivot est localisé en `toLowerCase()` des deux côtés | `static/exploration.js`, `splitPivot` |
| Gazetteer (ANN-3, à venir) | devra comparer sans casse, et le sait déjà | `pilotage/ANN-3.md` |

NLP-3 est donc une question de **qualité de transcription**, pas un défaut. C'est ce qui
rendait recevable l'option « ne rien faire », et ce qui interdisait d'aller vite.

## Les trois arbitrages

### 1. Où la normalisation agit-elle ? — un geste humain outillé

Écartées, et pourquoi :

- **Minusculer au pré-remplissage OCR** aurait été le plus simple. Écarté parce que le
  verbatim machine part à l'écriture, et qu'il porte une information qu'on ne recalcule
  pas : le CONTRASTE. Quand tout un album est en capitales et qu'un seul cartouche est en
  bas de casse — une lettre manuscrite, une coupure de presse, une voix étrangère —, cet
  écart EST le signal, et c'est exactement le genre de trait que ce corpus sert à étudier.
- **Ne minusculer qu'à l'affichage** était l'option notée préférable au backlog. Elle est
  **fausse tant que l'affichage est ÉDITABLE**, et le mode Transcription l'est : la zone
  de saisie reçoit `r.ocr_texte`, et chaque `trNext()` compare sa valeur au stocké puis
  `PUT` dès qu'ils diffèrent. Minusculer le rendu de cette zone ferait réécrire tout le
  corpus en minuscules **par simple navigation bulle-à-bulle**, sans qu'un caractère soit
  tapé. L'option n'est tenable que sur les surfaces en lecture seule — et elle y afficherait
  « tintin », c'est-à-dire un rendu faux présenté comme le texte.

Ce qui a tranché est une distinction, et elle vaut au-delà de ce chantier :

> **Normaliser la casse n'est pas une DÉRIVATION, c'est une INTERPRÉTATION.**

Le numéro éditorial, les dimensions en centimètres, le statut de relecture se dérivent —
donc ne se stockent pas — parce qu'ils se **calculent**. « TINTIN » → « Tintin » ou
« tintin » ne se calcule pas : ça se **devine**. Et la doctrine de la maison pour ce qui se
devine n'est pas « dériver à l'affichage », c'est celle de l'OCR lui-même :
**pré-remplir, et laisser corriger**.

D'où la forme retenue. La machine PROPOSE, visiblement, sur demande ; l'humain dispose :

- un bouton **« Normaliser la casse »** dans le mode Transcription : il remplit la zone de
  saisie avec la proposition, qu'on relit et retouche sur place. Le clic enregistre par le
  **même chemin qu'une frappe** (le débounce ordinaire), et c'est la seule réponse
  honnête : `trNext()` sauvegarde de toute façon dès que la zone diffère du stocké, si
  bien qu'un « non enregistré tant que vous n'avez pas confirmé » serait un état
  imaginaire. Ce qui protège n'est donc pas un différé d'écriture mais le **geste** — rien
  ne bouge sans un clic — et l'idempotence, qui rend le clic rejouable sans dégât ;
- l'outil de lot `tools/normaliser_casse.py` pour le rattrapage d'un corpus déjà océrisé,
  que personne ne rouvrira bulle par bulle.

### 2. Stocké ou affiché ? — stocké, mais jamais sans geste

`regions.ocr_texte` reste le seul texte, et il reste **verbatim tant que personne ne
demande**. Aucune colonne de plus, aucun rendu parallèle : deux textes finiraient par se
contredire, et il faudrait alors décider lequel part au dépôt.

La réversibilité est écrite et éprouvée : tant que la source était **uniformément
capitale**, `upper(normalisé) == original`. Le texte remplacé n'est donc pas perdu, il se
recalcule — et le journal A3 en garde l'avant/après ligne à ligne de toute façon.

### 3. Par album ou global ? — aucun réglage

La question se dissout avec la réponse à la première : si la normalisation est un geste,
il n'y a rien à régler — on l'applique, ou non, sur ce qu'on nomme. Un réglage global
fabriquerait deux moitiés de corpus incomparables sans que rien ne le dise, et une colonne
par album ajouterait une migration, un champ de formulaire et une règle à expliquer pour
un choix que le geste rend déjà local.

## La règle

Cinq règles, et trois sont propres à la bande dessinée. Le cœur est `casse.py` ; son jumeau
navigateur est `static/lib/casse.js`.

1. **`only_upper`** — un texte qui n'est pas INTÉGRALEMENT en capitales n'est pas touché du
   tout. C'est la transposition d'`only_empty` : une ligne mixte est soit une correction
   humaine, soit un vrai contraste de lettrage. La garde vit **dans** la fonction, pas chez
   l'appelant : aucun appelant ne peut l'oublier, et le geste devient **idempotent** — un
   second clic ne peut plus démolir « Tintin » en « tintin ».
2. **Un sigle se reconnaît à sa PONCTUATION, jamais à sa casse.** Sur une entrée toute en
   capitales, `FBI` est indiscernable d'un mot ordinaire ; seule la forme pointée `F.B.I.`
   est certaine, et c'est la seule préservée.
3. **Le saut de ligne ne ferme pas une phrase.** Le lettrage coupe ses lignes pour tenir
   dans la bulle, au milieu des phrases : « JE SUIS\nLÀ » donne « Je suis\nlà ». C'est
   l'inverse de la convention d'un texte suivi.
4. **Les points de suspension ne ferment pas une phrase.** Ils marquent l'hésitation DANS
   la réplique bien plus souvent qu'ils ne terminent.
5. **Le point qui clôt un sigle ne relève pas le mot suivant** : « LE F.B.I. ARRIVE » donne
   « Le F.B.I. arrive ».

```
ALORS TINTIN, LE F.B.I. T'ATTEND À NEW YORK ? SACRÉ MILOU !
→ Alors tintin, le F.B.I. t'attend à new york ? Sacré milou !
```

### Ce que la règle ne fait PAS, et qui est écrit exprès

**Les noms propres ne sont pas relevés.** « tintin » et « new york » sortent en bas de
casse. Ce n'est pas un manque à combler plus tard en douce : les relever suppose de les
connaître, c'est-à-dire le gazetteer d'**ANN-3**, qui n'est pas commencé. En attendant,
une erreur qui SE VOIT — sous les yeux de qui vient de cliquer, dans une zone de saisie
ouverte — vaut mieux qu'un nom inventé par heuristique, qui passerait inaperçu.

Même raison pour les sigles non pointés : `FBI` redescend en `fbi`. `tests/test_casse.py`
verrouille ces deux comportements **comme des limites assumées**, avec leur raison — sans
quoi la première relecture les prendrait pour des bugs et les « corrigerait » en devinant.

## La passe de lot, et ce qu'elle ne prétend pas être

`tools/normaliser_casse.py` (`--album` / `--planche` / `--dry-run`) applique la même règle
au corpus déjà en base. Trois précautions, et les trois échouent en silence si on les
oublie — d'où `tests/test_normaliser_casse.py`, `tools/` étant hors couverture :

- **Elle ne pose pas `regions.touche`.** Cette colonne dit « un humain a corrigé le
  pré-remplissage machine », et les indicateurs de dérive la lisent. La poser ferait
  compter des milliers de corrections qui n'ont jamais eu lieu, sans erreur nulle part, et
  le chiffre resterait faux pour toujours puisque le journal est append-only.
- **Elle est journalisée en `agent_type='moteur'`** (activité `normalisation_casse`), ce
  qu'elle est : une règle déterministe appliquée par un logiciel. Conséquence voulue, elle
  est **hors de portée de Ctrl+Z**, dont `undo.py` ne remonte que les actes humains — sans
  quoi le premier Ctrl+Z d'un annotateur défairait une ligne de la passe au lieu de son
  propre geste.
- **Elle réindexe** (`database.reindex_region`) : le texte indexé doit suivre, sinon la
  recherche et l'analyse grammaticale continueraient de porter sur l'ancienne casse —
  invisible, puisque FTS5 plie la casse de toute façon.

## La couche NLP est hors d'atteinte, et il a fallu le mesurer

La question s'est posée après coup, et elle a failli recevoir un « ça devrait aller ».

`_reancrer_corrections` (cf. `docs/correction-grammaticale.md` §4) réaligne les corrections
humaines après régénération des tokens **par la FORME du mot** — `difflib` sur
`tokens.texte` — et ne conserve une correction que si `new_forme[no] == c["forme"]`.
Normaliser « TINTIN » en « tintin » semblait donc devoir **orpheliner toutes les
corrections grammaticales** des régions traitées, faire retomber le statut de relecture des
planches de « faite » à « à faire », et cela **en silence, sur un corpus entier**.

**Mesuré le 2026-09-09 : il n'en est rien.** `pipeline/nlp.analyse` minuscule AVANT spaCy —
c'est le palier A, sans quoi tout le lettrage passerait pour des noms propres — si bien que
`tokens.texte` n'a **jamais** porté les capitales. Sur « ALORS TINTIN, LE F.B.I.
T'ATTEND. », les tokens auto sont déjà `alors`, `tintin`, `le`, `f.b.i`, `t'`, `attend`,
avant comme après la passe. La correction survit, à son ordre, `obsolete = 0`, et le statut
de relecture ne bouge pas.

**L'immunité vient donc du palier A, pas de la passe** — et elle tient à une propriété, une
seule, désormais verrouillée sur toute la table de cas :

```
normaliser(t).lower() == t.lower()
```

La règle ne change QUE la casse. L'entrée réelle de spaCy est donc rigoureusement identique
avant et après : mêmes tokens, mêmes lemmes, mêmes POS, même index FTS de lemmes. Une règle
future qui ajouterait ou retirerait un caractère — une espace insécable avant un `!`, une
élision « recollée » — romprait l'immunité, et **rien d'autre ne le dirait**. D'où
`test_la_regle_ne_change_QUE_la_casse`, doublé du bout-en-bout
`test_une_correction_grammaticale_humaine_survit_a_la_passe`.

## Ce que la passe COÛTE quand même

Rien de ce qui suit n'est un défaut à corriger : ce sont les conséquences du choix, et les
taire rendrait la note complaisante.

- **Les noms propres et les sigles non pointés redescendent en bas de casse.** Sur un
  corpus déjà transcrit, la passe de lot échange donc un défaut visible (le tout-majuscule)
  contre un autre (« tintin », « new york », « fbi »), et le second demande une relecture
  humaine que le premier ne demandait pas. Ce n'est un gain net que si quelqu'un repasse
  derrière — ou si ANN-3 arrive.
- **Appliquée à tout un corpus, elle efface le CONTRASTE de casse du TEXTE.** C'est la
  contrepartie exacte de l'argument qui a fait garder le verbatim : tant que les bulles sont
  en capitales, un cartouche en bas de casse SE VOIT. Une fois tout normalisé, il ne se
  distingue plus de ses voisins. Le journal A3 garde l'avant/après ligne à ligne, donc
  l'information n'est pas perdue — mais elle a quitté le texte pour la trace, et personne ne
  lit une trace en annotant. **Le geste unitaire n'a pas ce défaut ; la passe corpus-entier
  l'a.**
- **La passe de lot n'a pas d'annulation outillée.** Elle est hors de Ctrl+Z par
  construction (acte machine), et il n'existe pas de `--annuler`. « Réversible » veut dire
  que l'original se recalcule (`upper()`) ou se relit dans le journal, pas qu'un bouton le
  fasse. Concrètement : `--dry-run` d'abord, et une sauvegarde avant une passe large.
- **L'OCR continue de produire des capitales**, puisqu'il n'est pas touché. Un corpus
  traité par morceaux se retrouve donc dans deux états à la fois — sans conséquence pour la
  recherche ni l'analyse, qui plient la casse, mais visible à la lecture.

## Une règle en double, et son accord mesuré

La règle vit **deux fois** : `casse.py` pour l'outil de lot, `static/lib/casse.js` pour le
bouton. C'est délibéré. Une implémentation unique aurait supposé une route pour un pur
calcul de chaîne — qui ne touche aucune donnée, qu'il aurait fallu déclarer
`HORS_PERIMETRE` dans le cliquet d'autorisation, et qui aurait coûté un aller-retour réseau
par clic.

Deux implémentations coûtent moins, **à une condition** : que leur accord soit mesuré et
non supposé. `tests/cas-casse.json` est la table de cas, lue par `tests/test_casse.py` ET
par `tests/js/casse.test.js`. Elle est générée depuis `casse.py`, donc côté Python elle ne
fait que se relire ; **c'est côté JavaScript qu'elle mord**. Les deux écritures ont deux
raisons de se séparer, et les deux sont muettes : le `\w` de JavaScript est resté ASCII
(d'où `\p{L}` d'un côté, `[^\W\d_]` de l'autre), et `String.toUpperCase()` ne s'accorde pas
avec `str.upper()` sur tout l'Unicode. Aucune des deux ne lève ; elles rendent seulement un
texte un peu différent, sur un accent ou un point de suspension.

La table a elle-même un mode d'échec, et il est gardé : **ne semer que des cas capitaux**
rendrait `only_upper` invisible, et la garde pourrait disparaître sans qu'un seul cas
bronche. Les deux suites vérifient donc que le semis contient les deux sortes.

## Ce que l'audit d'accessibilité ne regarde pas — écrit plutôt que supposé

**Le bouton n'est couvert par aucun audit axe, et rien de ce panneau ne l'est.**

La question est venue d'une session voisine, sous une forme déjà juste : axe **exclut les
contrôles `disabled`** de la règle `color-contrast`, et `#tr-casse` est désactivé par
défaut — il passerait donc devant l'instrument sans être mesuré, et l'audit approuverait
une couleur qu'il n'a pas regardée. C'est le piège que ce dépôt s'écrit à lui-même depuis
le décor des moteurs de SANTE-1 : *un décor vide fait approuver ce qu'il n'a pas montré*.

La vérification a donné plus large que l'hypothèse. `tests/test_e2e_a11y.py` n'exerce que
les modes **Édition** et **Annotation** ; il n'entre **jamais** en mode Transcription, dont
la section est `hidden` au chargement. Ce ne sont donc pas seulement les contrôles
désactivés qui échappent à l'audit — c'est **tout le panneau**, `#tr-prev`, `#tr-next` et
`#tr-exit` compris, et depuis toujours.

Deux conséquences, et il faut les tenir séparées :

- **pour NLP-3**, le risque est faible et il est nommable : `#tr-casse` porte la classe
  `.ghost`, déjà employée par les trois autres boutons du même panneau, et **aucune couleur
  nouvelle n'est introduite** — pas une règle CSS n'a été ajoutée pour ce chantier. Ce qui
  n'est pas mesuré ici n'est pas mesuré ailleurs non plus ;
- **pour l'accessibilité**, c'est un angle mort réel, antérieur à ce chantier et plus large
  que lui. Le fermer demande un décor qui entre en Transcription avec une bulle **semée en
  capitales** (sans quoi le bouton reste désactivé, et l'exclusion d'axe rejoue). Cela ne
  relève pas de NLP-3 : c'est une passe d'audit à étendre, à porter par un chantier
  d'accessibilité — A11Y-2 étant clos, il en faudra un autre.

La troisième réponse — croire que c'est couvert — est la seule qui n'était pas acceptable.

## Renvois

- `pilotage/NLP-3.md` — la fiche du chantier.
- `pilotage/ANN-3.md` — le gazetteer, qui relèvera les noms propres. Les deux fiches se
  recoupent, et c'est NLP-3 qui devait passer d'abord.
- `docs/correction-grammaticale.md` — la couche NLP et ce que `pipeline/nlp.py` minuscule
  **en interne** pour spaCy, à ne pas confondre avec la transcription traitée ici.
