# Une grille qui naît sans dire où se posent ses entrées — cadrage

*Cadrage du 2026-11-12, pour Hugo. Le constat vient de la passe du formulaire
(`pilotage/qa/grille-formulaire.md`), et sa case est dans `pilotage/ANN-7.md`, zone « Relevé
par Hugo en jouant la passe du formulaire ». Rien n'est codé : cette page dit ce qui change,
ce qui ne change pas, et les deux réponses de Hugo aux questions qui restaient.*

## Ce qui est tranché

Hugo, 2026-11-12 : « + Construire une grille » ne demande que le **nom** et **« fermée ou
ouverte »**. La grille naît sans défaut, et chaque entrée répond à sa question 2. Un défaut se
pose ensuite, s'il est utile, dans « Toute la grille ».

La raison : chaque entrée choisit où elle se pose, et ce choix se discute pendant la
construction. Exiger un défaut dès l'ouverture demande une réponse qu'on n'a pas encore. Sur
la grille des linguistes, 47 entrées sur 49 se posent sur des mots, les deux autres sur des
zones ; sur la grille d'exemple, 6 sur 10.

## Ce que le modèle permet déjà

**Aucune migration n'est nécessaire.** Il n'y a rien à reprendre sur l'existant :

- la colonne `grille_version.cible` (« Porte sur ») est déjà facultative ;
- une entrée sans cible prend celle de sa version (`COALESCE(e.cible, v.cible)` dans
  `releves_effectifs`, `grilles.cibles_effectives`) ;
- `grilles.sorte_de_pose` sait déjà répondre « aucune » pour une version sans « Porte sur ».

C'est la **relecture** d'une version qui exige le défaut aujourd'hui, pas le schéma : le code
`porte_sur_manque`, dans `grille_ecriture.verifier` et dans `grille_import.lire_tableur`.

## Ce qui change

**La règle.** Le défaut devient facultatif. Une entrée qui ne dit pas sa cible, dans une
version sans défaut, est une faute qui porte **sur l'entrée** et non plus sur la grille : un
code neuf (« l'entrée ne dit pas où elle se pose »), à la question 2. `porte_sur_manque`
disparaît.

**Le formulaire** (`static/administration.js`, `static/lib/grille-formulaire.js`).
- « + Construire une grille » ne demande plus la question B.
- Dans « Toute la grille », la question B reçoit une réponse « Aucun défaut », choisie
  d'office sur une grille neuve.
- Sur une entrée, la question 2 n'offre « comme la grille » que s'il y a un défaut.
- Une entrée sans cible porte l'attente ● à la question 2, et la publication attend qu'elle
  soit levée, comme pour toute attente.

**L'import et le tableur** (`grille_import.py`, `grille_tableur.py`).
- La cellule « Porte d'ordinaire sur » de la feuille « 1. La grille » devient facultative.
- La colonne « 2. Se pose sur » dit « Vide : ce que dit la feuille 1, s'il y a un défaut ».
- Une règle rouge de plus colore « 2. Se pose sur » vide quand la feuille 1 n'a pas de défaut.
- Le tableur d'une grille sans défaut se relit tel qu'il a été écrit, à la même empreinte.

**La page Annotation** (`static/lib/annotation.js`). Seuls deux endroits lisent le défaut :
- `ciblesVisees`, qui réunit les cibles des entrées et celles de la version, et tient sans lui ;
- `entreeNeuve`, qui fait naître une entrée en la posant dans une grille ouverte. C'est la
  question 1, ci-dessous.

**Ce qui ne change pas.**
- Les grilles qui ont un défaut le gardent, et leurs entrées aussi.
- La grille fictive des bacs à sable garde le sien (`config.GRILLE_DU_BAC_PORTE_SUR`).
- Le serveur garde ses refus : une entrée sans cible, dans une version sans défaut, ne se
  pose pas.

## Les deux questions, tranchées par Hugo le 2026-11-12

**1. Dans une grille ouverte sans défaut, où se pose une entrée qui naît au moment de la
pose ?** Aujourd'hui, elle prend la cible du défaut (`routes/releves.py`, `_entree_neuve`).

- **(a) Retenu : ce qu'on vient de désigner.** Des mots désignés donnent une entrée sur
  des mots ; sinon, la sorte de la zone choisie (une bulle donne une entrée sur les bulles) ;
  sur la planche, la planche. L'entrée naît avec cette cible écrite, et non héritée : la poser
  ensuite ailleurs se règle dans le formulaire.
- (b) Écarté : refuser la naissance tant que la grille n'a pas de défaut. C'est plus simple, mais
  le mode libre ne marche alors pas sur une grille ouverte neuve.

**2. Retirer le défaut d'une grille qui en a un** (passer à « Aucun défaut » dans « Toute la
grille »).

- **(a) Retenu : les entrées qui le suivaient le reçoivent écrit.** Rien ne change pour
  elles, et le formulaire dit avant d'appliquer combien d'entrées le reçoivent.
- (b) Écarté : refuser tant qu'une entrée le suit. Ça oblige à repasser les entrées une à une.

Sur une grille **fermée**, ce geste s'écrit dans le brouillon comme tout autre : une version
publiée ne change pas.

## Le découpage proposé

Trois commits, chacun avec ses tests, dans cet ordre :

1. **La règle**, côté serveur : relecture, import, écriture, naissance à la pose (selon la
   question 1). Rien ne change encore à l'écran.
2. **Le formulaire** : la création sans question B, « Aucun défaut », le retrait du défaut
   (selon la question 2).
3. **Le tableur** : la cellule facultative, l'aide de la colonne, la règle rouge, la
   relecture.

Une passe de QA courte suit : construire une grille sans défaut, la publier, l'importer, la
réimporter. Elle s'écrit au moment du code, pas avant.
