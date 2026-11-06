# ANN-7 — le mode libre dans le modèle des grilles : cadrage

Rendu le 2026-11-06, sur la branche `ann7-bascule` à `ed0a317` (schéma **38** ; commits 0 à 4
du basculement et le commit 2 bis, `dbd455e`, la grille de travail). Le commit 5 — la
migration v39, en pause — a été **lu** dans sa copie de travail, sans y rien écrire : il n'est
pas commité, et ce que cette note en dit vaut pour son état du 2026-11-06. Rien n'est codé.
Comme les cadrages précédents : ce qui est marqué **lu** a été lu dans le code ; **mesuré**
sort d'une commande ou d'un test jetable cité dans l'annexe ; **hypothèse** ne l'a pas été, et
dit ce qui trancherait. Les questions qui restent à Hugo sont numérotées **J1 à J9** — la suite
de G (tranche 1), H (tranche 2) et I (tranche 3) — et viennent EN TÊTE, chacune avec une
proposition et son coût.

**Ce qui est tranché et que cette note ne rediscute pas** : un seul modèle, la grille (Hugo,
2026-11-06), « à condition que le libre y soit un vrai mode » ; chaque projet naît avec une
grille OUVERTE « Travail en cours » (Hugo, 2026-11-05) ; « nom : valeur » fait naître une entrée
à variantes et sa variante (« les variables aussi », le même jour). Cette note dit ce qu'il faut
changer pour que la grille de travail soit un MODE : la règle, l'écran, la Recherche, le passage
vers une vraie grille, et ce que la migration en pause doit en recevoir.

Le dépôt est public : aucune grille réelle n'est citée ici ; « sentiment », « lieu », « ironie »
sont les exemples de Hugo et des tests.

---

## Les questions pour Hugo

1. **J1 — À quoi s'attachent les règles du mode libre ?** Elles sont quatre (J3 à J6) : la
   cardinalité, l'état provisoire, qui remanie, la Recherche. (a) À l'ENTRÉE NÉE EN POSANT,
   dans toute grille ouverte — c'est déjà là que G14 place la création. (b) À la seule grille
   de travail. (c) À une propriété « libre » de grille, qui se pose et se retire. *Proposé :
   (a).* Une grille ouverte importée (« Lieux », écrite par la gestionnaire) garde les règles
   de ce qui a été ÉCRIT (cardinalité déclarée, entrée définie) ; ce qu'un annotateur y fait
   naître en posant suit les règles du libre. Aucune propriété neuve, aucun réglage à
   expliquer, et la règle se lit sur l'objet qu'elle touche. Coût : nul de plus que (b) ; (c)
   coûterait une colonne, une route, un écran et un état de plus à tester.

2. **J2 — L'écran désigne-t-il LA grille de travail d'un projet ?** Pour que le libre soit un
   mode et non un onglet parmi d'autres, la page Annotation doit savoir quelle grille le porte
   — un projet peut avoir plusieurs grilles ouvertes. Aujourd'hui elle n'est reconnue que par
   son NOM (`grille_import.installer_grille_de_travail` → `nom_pris`, **lu**), et le nom se
   change (`PATCH /api/grilles/{id}`). (a) Un drapeau `grille.travail`, posé par la v39 (au
   plus une par projet, index unique partiel) ; elle se renomme, ne se retire ni ne se
   supprime tant qu'elle porte quelque chose. (b) La reconnaître par son nom. (c) Ne rien
   désigner : le mode libre est « la grille ouverte choisie ». *Proposé : (a).* Coût : ¼ de
   jour dans le commit 5 ; plus tard, ce serait une migration v40, donc une vraie base v39 à
   fabriquer (règle du 2026-10-16). (c) laisse le libre être un onglet parmi d'autres — le
   constat de Hugo.

3. **J3 — La cardinalité d'une étiquette née en posant.** Aujourd'hui (**mesuré**) : une
   entrée née en posant n'a pas de cardinalité, donc prend le défaut d'une région entière,
   `une` (`grilles.cardinalite_effective`) ; « sentiment : tristesse » après « sentiment :
   perte » sur la même bulle reçoit le 409 de la cardinalité, et l'écran propose de remplacer.
   (a) Une entrée qui naît À VARIANTES en la posant naît `plusieurs` (écrit sur l'entrée, que
   le formulaire montre et peut changer) ; une entrée qui naît SIMPLE garde `une` — la poser
   deux fois sur une zone la retire, comme un tag ; et, dans toute grille, une même variante
   ne se pose pas deux fois sur la même cible entière (refus nommé). (b) Toute entrée née en
   posant naît `plusieurs`. (c) Une troisième cardinalité, « une par valeur ». *Proposé :
   (a)* — exactement la sémantique des tags (« sentiment : perte » et « sentiment : tristesse »
   font deux relevés, « ironie » une fois par zone). (b) laisserait poser « ironie » trois fois
   sur la même bulle (**mesuré** : en `plusieurs`, le doublon exact est accepté) ; (c) ajoute
   une valeur à une liste bornée, au tableur, au formulaire, et un index. Coût de (a) : ½ jour
   serveur (une ligne dans `routes/releves._entree_par_nom`, le refus du doublon sous le
   verrou, leurs tests), et le geste d'écran (une variante cochée se retire, une autre
   s'ajoute) dans la tranche d'écran.

4. **J4 — L'état provisoire / défini : où il naît, ce qu'il gouverne.** Hugo (2026-11-05) :
   « provisoire par défaut dans une grille ouverte ». Le commit 5 l'applique à la lettre
   (**lu**) : toute entrée d'une grille ouverte naît provisoire, celles qu'on IMPORTE comprises
   (`grille_import.ecrire_plan`), et la migration rend provisoires toutes les entrées des
   grilles ouvertes existantes. L'état ne gouverne encore rien. (a) Provisoire = née en
   posant ; écrite (import, formulaire) = définie, même dans une grille ouverte ; l'état
   gouverne qui remanie (J5) et une marque à l'écran, rien d'autre (ni la cardinalité, ni la
   Recherche) ; il se change par les responsables (« Définir », et le formulaire). (b) La
   lettre : provisoire pour toute entrée d'une grille ouverte. *Proposé : (a).* **C'est la
   seule contradiction relevée** : si l'état ouvre le remaniement à tout annotateur (J5), (b)
   permet à un annotateur de renommer les lieux que la gestionnaire a écrits dans « Lieux ».
   Si J5 reste « les responsables », (b) suffit. Coût de (a) : ¼ de jour dans le commit 5 (le
   défaut d'`ecrire_plan` et du formulaire ; la migration rend provisoires les seules entrées
   dont le journal garde la naissance en posant, `entree_neuve` sous `grille`).

5. **J5 — Qui renomme, fusionne, retire une étiquette, et d'où.** Aujourd'hui : les
   responsables du projet, dans le bloc « Grilles » de l'Administration (**mesuré** : un
   stagiaire reçoit 403 sur `PATCH …/entrees/{cle}`). (a) Les responsables, mais sur place,
   dans la page Annotation. (b) Tout annotateur qui écrit dans un album du projet, sur une
   entrée PROVISOIRE, pour les trois gestes ; avec, avant une fusion ou un retrait, « qui perd
   quoi » (les relevés de qui) et un Ctrl+Z de la fusion. (c) Mixte : renommer une étiquette ou
   une valeur et ajouter une valeur, tout annotateur sur une entrée provisoire ; fusionner et
   retirer, les responsables — tous sur place. *Proposé : (c).* Renommer se défait en
   renommant, et la valeur vue de CONC-3 le garde déjà (`vu`, l'acte `grille` dont la charge
   nomme l'objet, **lu**) ; une fusion, elle, ne se défait pas (Ctrl+Z ne défait rien du
   formulaire, **lu**) et réécrit les relevés des autres. Coût : (a) ½ jour ; (c) 1 jour (une
   question d'autorisation neuve, la vingt-troisième, et une clé `remaniable` par entrée dans
   le plan, pour que l'écran pose la question sur l'acte) ; (b) 2 jours (le Ctrl+Z d'une
   fusion n'existe pas).

6. **J6 — Les étiquettes dans le plein texte : décisif pour la migration en pause.** La décision
   du 2026-10-22 laisse les relevés hors de l'index, parce que « structurés et versionnés, ils
   y vieilliraient à chaque montée de version ». La raison ne vaut pas pour une grille OUVERTE,
   qui n'a qu'une version, vivante. (a) La v39 recrée l'index de toute façon (I6) : elle y met,
   À LA PLACE de `tags_concat`, une colonne `etiquettes`, remplie des libellés des relevés des
   grilles OUVERTES (entrée, variante, qualificatifs), et la Recherche la cherche (« dialogues,
   notes, étiquettes »). (b) Rien dans l'index ; un filtre seulement (J7). (c) Les libellés de
   toutes les entrées, grilles fermées comprises. *Proposé : (a)*, qui renverse la décision du
   2026-10-22 pour les seules grilles ouvertes. **Ce qui ne se reporte pas, c'est la
   COLONNE** : quels libellés la remplissent peut changer plus tard sans migration (une
   réécriture de la colonne, **mesurée** à 74 ms pour 1 500 régions sur 20 000) ; la colonne,
   elle, demanderait une seconde reconstruction de l'index et, d'après I6, une seconde
   réindexation complète par spaCy. Coût : ¾ de jour dans le commit 5, 1 jour juste après
   (les appels qui maintiennent la colonne), ¾ de jour pour la Recherche. (c) ferait remonter
   dans le champ, sur chaque bulle relevée, le vocabulaire technique d'une grille fermée.

7. **J7 — Un filtre « porte l'étiquette » avant la tranche 4 ?** Hugo l'attend (« un filtre les
   isole »). (a) Oui, juste après le basculement, minimal et générique : un paramètre
   `releve=<grille>:<entrée>[:<variante>]` de la Recherche (un `EXISTS` sur `releve`, exact,
   hors de l'index), qu'on pose en cliquant une étiquette dans un résultat ; la tranche 4
   l'étend (grilles fermées, héritance d'une case vers ses bulles, Exploration) au lieu de le
   refaire. (b) Attendre la tranche 4. *Proposé : (a).* Coût : ½ jour serveur et écran ; aucun
   schéma.

8. **J8 — « Structurer » : faire passer une étiquette, avec ses relevés, dans une autre
   grille.** (a) Une tranche à part, juste après le basculement, aux règles de la section
   « Structurer » (vers la version ACTIVE de la grille d'arrivée, ouverte ou fermée ; les
   relevés qui ne conviennent pas restent, un bilan les dit relevé par relevé ; un acte par
   relevé au journal ; pas de Ctrl+Z du geste). (b) Dans le basculement. *Proposé : (a).*
   Rien dans le schéma ne l'attend, il ne retarde donc pas la migration ; son bilan se
   dessine sur la même maquette. Coût : 3 jours.

9. **J9 — L'ordre : la migration reprend-elle avant la maquette ?** Hugo (2026-11-06) : « un
   cadrage du mode libre suit, puis une maquette, avant que la migration reprenne ». (a) La
   migration reprend dès que J2, J4 et J6 sont tranchées — ce sont les seules réponses qui
   touchent le schéma — et la maquette se fait en parallèle. (b) L'ordre du 2026-11-06 : la
   maquette d'abord. *Proposé : (a).* Ce qu'une maquette pourrait demander au schéma est
   listé (section « L'écran ») et n'y demande rien : l'ordre des étiquettes a sa colonne
   (`rang`), la récence se lit sur les relevés. Coût de (b) : la migration attend la séance.

**Se tranchent en route**, sans Hugo sauf avis contraire (le plus prudent à chaque fois) :
changer la cardinalité d'une entrée EMPLOYÉE de `plusieurs` à `une` est refusé (409 nommé)
quand deux relevés s'en contredisent sur une même cible — la règle de `_fusion_en_double`
(aujourd'hui accepté sans rien dire, **mesuré**) ; la colonne `etiquettes` ne porte pas la
précision d'un relevé (un texte libre, qui n'est pas du vocabulaire) ; une entrée RETIRÉE garde
ses libellés dans l'index (ses relevés restent, et disent encore cela) ; une grille désactivée
aussi (ses relevés restent en lecture) ; le libellé d'une étiquette n'est pas lemmatisé (le
préfixe suffit, et un renommage ne demande pas le moteur de langue).

---

## Ce qui est déjà tranché (cité)

- **Un seul modèle** — Hugo, 2026-11-06 (`pilotage/ANN-7.md`, zone « Le mode libre ») : (A),
  « à condition que le libre y soit un vrai mode » ; un cadrage, puis une maquette, avant que la
  migration reprenne.
- **La grille de travail** — Hugo, 2026-11-05 : chaque projet, bacs à sable compris, naît avec
  une grille OUVERTE « Travail en cours », sur la zone ; la migration la donne aux projets
  existants ; les entrées portent un état, provisoire ou défini, « provisoire par défaut dans une
  grille ouverte » ; on les renomme, les fusionne, ou on les fait passer dans une vraie grille.
  La note de portée reste ouverte. Codé au commit 2 bis (`dbd455e`) ; l'état et la grille des
  projets existants sont dans le commit 5.
- **« Les variables aussi »** — Hugo, 2026-11-05 : « lieu : forêt » fait naître ou retrouve
  l'entrée « lieu » à variantes et sa variante ; une valeur nouvelle s'ajoute.
- **G14** (2026-10-25) : une entrée naît en la posant, dans une grille ouverte ; renommer et
  fusionner viennent en tranche 3 — **codé** dans le formulaire le 2026-11-04 (`f2c78cc`,
  `edc9ae7`), à qui gère le projet.
- **Supprimer, fusionner, renommer un terme** — Hugo, 2026-10-22 : dans une grille ouverte, en
  place, « par les responsables du projet, journalisés » ; Ctrl+Z désigne une entrée par sa
  `cle`. Hugo a rouvert le QUI le 2026-11-06 (case « Une étiquette se renomme… », « les
  responsables, ou tout annotateur sur une entrée provisoire est à trancher ») : J5.
- **La réindexation plein texte se paie une fois** — Hugo, 2026-10-22 : le basculement retire
  `tags_concat` et ne met pas les relevés dans l'index ; la Recherche gagne en tranche 4 « porte
  le relevé… ». La case « Une étiquette libre se trouve dans la Recherche » la dit « à rouvrir si
  (A) » : J6, J7.
- **I6** — Hugo, 2026-11-05 : une réindexation complète par spaCy au basculement, hors de la
  migration de démarrage (`tools/reindex_nlp.py` au déploiement, dit le commit 5).
- **Q6** (2026-10-22) : la cardinalité se déclare ; vide, `une` sur une région entière ; à
  l'écran, en choisir une autre remplace.
- **Une entrée employée ne se supprime jamais** (2026-11-03) ; « fusionner dans… » refusé sur
  une grille FERMÉE (choix 1 des routes d'écriture, 2026-11-04).
- **Q1** : une collection masque une grille par un FILTRE d'écran, jamais une garde.
- **E5** (2026-10-22) : une copie n'emporte que les relevés d'une grille active à l'arrivée ;
  **S8** (COL-4) : la Recherche ne voit ni bac à sable ni jeu.

---

## Les constats de Hugo, un par un

La zone « Le mode libre » de la fiche porte sept cases. Pour chacune : ce qui se passe, la
règle, l'écran.

### 1. La création est cachée derrière le champ de recherche

**Lu** : un plan sans entrée dessine un arbre vide (`static/annotation.js`, `rendreCorps` →
`A.arbre`, rien à dessiner) ; la seule création est la dernière ligne des résultats du filtre,
« Créer « … » » ou « Ajouter « grotte » à « lieu » » (`rendreResultats`,
`BDAnnotation.creerDansLeFiltre`), qui n'existe que si l'on tape dans « Chercher dans la grille
ouverte… », et seulement dans la grille choisie si elle est ouverte.

**Règle** : rien ne change au serveur — `POST /api/releves` avec `nouvelle_entree` fait déjà
naître l'entrée en posant (**lu**, `routes/releves.poser_releve`).

**Écran** : un champ de création À LUI, visible même quand la grille est vide, qui dit sa
syntaxe en infobulle (« nom », ou « nom : valeur ») ; Entrée crée et pose sur la cible courante.
Sa place est la première question de la maquette.

### 2. Les étiquettes se rangent sous « Sans rubrique »

**Lu** : `BDAnnotation.arbre` range toute entrée sans rubrique dans un groupe « Sans
rubrique », en dernier — même quand la grille n'a AUCUNE rubrique. Une entrée née en posant
n'en a pas (`_entree_par_nom` ne pose pas de `rubrique_cle`).

**Règle** : aucune ; une étiquette née en posant reste sans rubrique (les ranger se fait au
formulaire, par un responsable).

**Écran** : sans rubrique dans la grille, les entrées se listent sans intitulé ; avec des
rubriques, le groupe « Sans rubrique » garde sa place. Une fonction pure et son test sous Node :
moins d'une heure.

### 3. Une seconde valeur propose de remplacer la première

**Mesuré** (test jetable, annexe) : dans la grille de travail, « sentiment : perte » sur une
bulle pose un relevé `une = 1` ; « sentiment : tristesse » sur la même bulle reçoit le 409 de la
cardinalité (« Cette entrée ne se pose qu'une fois sur cette cible »), avec le relevé existant ;
le plan dit `cardinalite: "une"` pour une entrée née en posant. Même chose pour « ironie » posé
deux fois. La cause : une entrée née en posant n'écrit pas de cardinalité, et le défaut d'une
région entière est `une` (`grilles.cardinalite_effective`, **lu**). À l'écran, le bandeau propose
« Remplacer par la mienne » (`refus` → `remplacementCardinalite`).

Hugo a vu la variante « tristesse » naître quand même. **Non reproduit** à la route : le refus
défait la transaction, et la variante n'existe pas après le 409 (`VARIANTES [perte]`, annexe). Cf.
« Ce que cette note n'a pas pu établir ».

**Règle** : J3. Une entrée qui naît à variantes naît `plusieurs` ; une même variante ne se pose
pas deux fois sur la même cible entière. **Mesuré** : une fois l'entrée en `plusieurs` (posé au
formulaire), « sentiment : tristesse » se pose à côté de « perte » — et un second « tristesse »
aussi, d'où le refus du doublon que J3 ajoute.

**Écran** : le geste d'une entrée à variantes ignore aujourd'hui la cardinalité — une autre
variante REMPLACE toujours (`BDAnnotation.geste`, branche `variantes`, **lu**). Pour une entrée
`plusieurs`, une variante non posée s'ajoute, une variante posée se retire : des puces qui se
cochent une à une (`aria-pressed` par variante).

### 4. Plusieurs valeurs d'un geste

**Lu** : un relevé ne porte qu'une variante ; les qualificatifs sont multiples, mais viennent
d'une liste écrite d'avance et comptent UNE fois leur phénomène (2026-10-22).

**Règle** : J3 suffit — chaque valeur cochée est un relevé, comme deux tags. Écarté : faire
naître les étiquettes « à qualificatifs » (un relevé, plusieurs valeurs) — « lieu » cesserait
d'être « une parmi », et le compte changerait de sens. Plusieurs valeurs cochées partent en
autant de `POST` ; chacune se défait par son Ctrl+Z. Une route « par lot » n'est pas nécessaire.

**Écran** : les puces de J3 ; une saisie « sentiment : perte ; tristesse » d'un coup est à juger
sur la maquette (une valeur peut contenir une virgule ; « heure : 10:30 » sépare déjà au premier
deux-points).

### 5. Renommer, fusionner, retirer ne se font que dans l'Administration, aux responsables

**Lu** : les vingt routes du formulaire (`routes/grilles.py`) passent par `_ecrire`, qui exige
`gerer=True` (403 nommé sinon) ; chaque geste relit la version entière sous les refus de
l'import, garde `vu` (CONC-3, l'auteur trouvé par l'acte `grille` dont la charge nomme l'objet)
et écrit un acte `grille` par objet. Ctrl+Z n'en défait rien. La fusion (`…/fusion`) ne va qu'à
une entrée de la MÊME grille, de même forme, posée de la même manière, de la même liste, qui
porte les variantes employées (`grille_import._vers_possibles`), et refuse de poser deux fois une
entrée `une` (`_fusion_en_double`) ; elle réécrit `releve.entree_cle` en masse, sans acte par
relevé — le journal garde seulement `releve_ids` dans l'acte `grille` (`_fusionner`, **lu**).
**Mesuré** : un stagiaire reçoit 403 sur un renommage.

**Règle** : J5. Avec (c) : une question d'autorisation neuve, « peut remanier cette entrée »
— vrai pour qui gère le projet ; et, sur une entrée PROVISOIRE d'une grille ouverte, pour qui
écrit dans un album du projet où la grille est active (le cercle de ceux qui peuvent la poser),
pour renommer l'étiquette ou l'une de ses valeurs et ajouter une valeur ; fusionner et retirer
restent à qui gère. Ce que cela fait :

- **Le journal** : inchangé — un acte `grille` par objet, l'agent étant le sien.
- **Ctrl+Z** : rien de plus — renommer se défait en renommant. Un relevé posé AVANT une fusion
  reste défaisable par son auteur : Ctrl+Z relit le relevé tel qu'il est (son entrée
  d'arrivée) et le retire (`undo._inverser_releve`, **lu**).
- **CONC-3** : `vu` sur le libellé, existant ; deux annotateurs qui renomment la même étiquette
  reçoivent le 409 qui nomme l'autre.
- **« Qui perd quoi »** : rien ne change — un acte `grille` n'est pas un travail sur un album,
  et une fusion n'efface aucun relevé. Si J5 (b) : la confirmation compte les relevés touchés
  par auteur (`releve.auteur`), lus au moment du geste.
- **Le signal « ⟳ Actualiser »** ne couvre pas le plan (**lu**, `empreinte.empreintes_releves`
  lit les relevés, pas la version) : une étiquette renommée ou née sur un autre écran ne se voit
  qu'au rechargement. Les étiquettes changeant souvent, l'empreinte de la version VIVANTE des
  grilles ouvertes entre dans le signal (¼ de jour).

**Écran** : les gestes sur place (section « L'écran »), éteints avec leur raison en infobulle
pour qui ne les a pas — la question posée sur l'ACTE, par la clé `remaniable`.

### 6. Les étiquettes ne sont pas dans la Recherche

**Lu** : la Recherche ne cherche que `ocr_texte`, `note`, `lemmes` (`routes/recherche.py`,
`COLONNES_CHERCHEES`) ; aucun relevé n'est dans l'index. **Mesuré** : « tristesse » ne trouve
rien après qu'on l'a posée. Section « La Recherche ».

### 7. Aucun geste pour faire passer une étiquette dans une vraie grille

**Lu** : la fusion ne va qu'à une entrée de la même grille. Section « Structurer ».

---

## La règle, en une table

| Ce qui change | Pour quoi | Où |
|---|---|---|
| Une entrée née À VARIANTES en posant naît `plusieurs` ; une simple garde `une` | toute entrée née en posant (J1, J3) | `routes/releves._entree_par_nom` |
| Une même variante ne se pose pas deux fois sur une même cible entière | toute grille | `poser_releve`, sous le verrou |
| Née en posant : provisoire ; écrite : définie | toute grille ouverte (J4 a) | commit 5 : `ecrire_plan`, formulaire, migration |
| Renommer une étiquette ou une valeur, ajouter une valeur : tout annotateur du projet | entrée provisoire d'une grille ouverte (J5 c) | `autorisation.py`, `routes/grilles.py` |
| Fusionner, retirer : qui gère, sur place | inchangé (J5 c) | écran seulement |
| Les libellés des relevés dans l'index, colonne `etiquettes` | grilles ouvertes (J6) | v39 et `database.py` |
| LA grille de travail désignée | une par projet (J2) | v39 : `grille.travail` |
| `plusieurs` → `une` refusé sur deux relevés contradictoires | toute grille | `routes/grilles.modifier_entree` |

Ce qui ne change PAS : le modèle (une entrée, ses variantes, un relevé par valeur), les versions,
la fusion refusée sur une fermée, les droits de pose (écrire dans l'album), CONC-3, Ctrl+Z des
relevés, E5.

---

## L'écran

**Le besoin** : sur la page Annotation, le libre doit être un MODE — on y arrive sans chercher,
on y crée sans savoir taper la bonne requête, on y voit ce qui est posé, on y corrige un nom
sans quitter la zone. Les quatre constats d'écran (1 à 5) en sont la liste.

**Les contraintes**, écrites et tranchées ailleurs : trois colonnes de taille STABLE pendant le
travail ; aucune phrase d'aide à l'écran, l'aide en infobulle ; un état se marque là où l'on
agit ; une étiquette qui naît ne fait sauter aucune hauteur (la liste défile dans sa boîte) ;
`redessinerSansPerdreLeFocus` partout où un bloc se redessine ; le clavier (le filtre passe par
`aria-activedescendant`, Ctrl+Entrée et Ctrl+Z gardent leur sens) ; sous 47,5em la grille est une
FEUILLE (« Poser… ▴ ») et le champ de création doit y être en tête ; au doigt, des cibles de
taille suffisante et aucun geste qui ne passe que par le survol.

**Ce que la maquette doit trancher** (séance dédiée, une vraie planche) :

1. **Où vit le mode** : un onglet permanent « Étiquettes » à côté des grilles, ou un bloc fixe
   au-dessus de la grille choisie (les étiquettes visibles quelle que soit la grille ouverte), ou
   une rangée sous la case agrandie. Et s'il se crée depuis une grille FERMÉE choisie.
2. **Le champ de création** : séparé du filtre, ou le filtre lui-même rendu explicite ; ce que dit
   l'infobulle ; ce qu'Entrée fait quand le nom existe déjà (poser l'existante).
3. **Une étiquette à valeurs** : des puces cochables, « + valeur » en place ; ce qui est posé ici,
   marqué sur la puce même.
4. **L'ordre** de la liste : création, alphabétique, emploi, récence.
5. **Remanier sur place** : un « ✎ » ou un menu « ⋯ » par étiquette ; le renommage en place ;
   « Fusionner dans… » (la liste des entrées compatibles, celle de `_vers_possibles`) et
   « Retirer », confirmés sur place, sans modale ; leur forme éteinte pour qui ne les a pas.
6. **La marque provisoire / défini**, et « Définir » pour un responsable.
7. **« Passer dans une grille… »** (J8) : son entrée et son bilan relevé par relevé.
8. **L'état vide** : le champ et son infobulle, jamais un tiret.
9. **Étroit, doigt, clavier** : la place du champ dans la feuille ; un raccourci pour y aller.
10. **La Recherche** : comment une étiquette se lit dans un résultat, la puce qui l'isole (J7),
    la promesse du champ (« dialogues, notes, étiquettes »).

Rien de cette liste ne demande de colonne : l'ordre a `grille_entree.rang`, la récence et l'emploi
se lisent sur `releve` (J9).

---

## La Recherche — décisif pour la migration en pause

### Ce que fait la v39 telle qu'elle est en pause (lu)

Le commit 5 recrée l'index sans `tags_concat` (`_FTS_V39` : `region_id`, `ocr_texte`, `note`,
`lemmes`), RECOPIE les lignes non vides, détruit l'ancienne table, renomme la neuve ; il ramène
`_region_index_payload` à deux valeurs (texte, note) et `_index_region` à quatre colonnes. La
réindexation complète par spaCy (I6) se lance au déploiement. Une colonne ajoutée ensuite
demanderait de tout refaire : le schéma d'une table FTS5 ne se modifie pas.

### Ce qu'elle doit recevoir, au plus juste (si J6 a)

1. **Remplacer la troisième colonne au lieu de la retirer** : `etiquettes` à la place de
   `tags_concat`, dans `_FTS_SQL` (les bases neuves) et dans `_FTS_V39` (la migration).
2. **La remplir à la recopie, en SQL** : pour chaque région, les libellés de ses relevés dans une
   grille OUVERTE — l'entrée, sa variante, ses qualificatifs, lus dans la version du relevé —, et
   AJOUTER une ligne pour une région qui n'en avait pas (une CASE qui porte « lieu : forêt » n'a ni
   texte ni note, donc aucune ligne aujourd'hui). L'index est juste dès le démarrage, avant la
   réindexation complète.
3. **`_region_index_payload` rend trois valeurs** (texte, note, étiquettes) et `_index_region`
   écrit une ligne dès que l'une des quatre (étiquettes comprises) est non vide. Les appelants
   qui lisent `payload[0]` et `payload[1]` (le déclenchement du moteur de langue) ne changent
   pas.
4. **Ses tests**, sur la vraie base v38 : elle ne porte aucune grille ouverte ni aucun relevé
   dans l'une d'elles (**lu** : trois grilles, toutes fermées, un relevé) — le test y pose une
   grille ouverte et un relevé sur une case par SQL avant de migrer, puis vérifie qu'un mot de
   l'étiquette trouve la case, qu'un mot du texte trouve ce qu'il trouvait, et qu'un ancien tag ne
   trouve plus rien. Mutant : la recopie sans le remplissage (le test de l'étiquette rougit).

**Mesuré** : recopier l'index en ajoutant la colonne, 4 ms pour 330 lignes, 89 ms pour 20 000,
380 ms pour 100 000 (SQLite 3.49.1) — le coût de la recopie de I6, inchangé.

### Quels libellés, sous quelle portée

- **Les grilles ouvertes seulement** (J6). Leur unique version est vivante : un renommage réécrit
  la colonne, rien ne « vieillit ». Une grille ne change pas d'ouverte à fermée (choix 1 du
  formulaire, 2026-11-04) : l'appartenance à l'index est stable. « Lieux », ouverte, y entre aussi
  — les lieux des stagiaires deviennent cherchables.
- **La portée** : un relevé se lit avec son album, et la Recherche filtre déjà ses résultats par
  `clause_album` (**lu**, `_recherche_rows`). Qui lit la région lit aussi le plan de la grille :
  moitié (c) de `clause_grille`, « lire un album qui porte un relevé de la grille » (**lu**). Une
  grille masquée par une collection : sans effet, le masque est un filtre d'écran (Q1) et la
  Recherche traverse les collections.
- **La limite écrite sous `AUTH-11`** se ferme et ne revient pas. `tags_concat` agrégeait des tags
  dont le libellé pouvait être illisible (un terme local d'une collection qu'on ne lit pas) : un
  oracle de confirmation. Un libellé d'étiquette est toujours lisible de qui lit la région. Le
  paragraphe de `CLAUDE.md` (§ Recherche FTS5) se réécrit en ce sens.
- **Ce qui n'y entre pas** : un relevé de la PLANCHE (l'index est par région ; la grille de travail
  ne vise que des zones, **lu**, `CIBLES_ZONE`) ; un bac à sable (S8 : on y essaie le libre, mais
  la Recherche ne le voit pas — à dire à Hugo s'il a essayé dans un bac à sable) ; un détail
  (`sql_region_sortante`, G17).

### Maintenu par quels appels

Le patron existe : `reindex_tags_regions` (ANN-8, retiré au commit 2) réécrivait la seule colonne
`tags_concat` de N régions, par paquets de 500, en lisant le `rowid` de chacune — parce que
`reindex_region` relance le moteur et tenait le verrou 14,7 s pour 1 500 régions (mesuré le
2026-10-22). Un `reindex_etiquettes(conn, region_ids)` sur ce patron, **mesuré** à 2 ms pour 30
régions sur 330, 74 ms pour 1 500 sur 20 000, 520 ms pour 5 000 sur 100 000. Ses appelants
(**lu**, chaque écriture de `releve` et chaque changement de libellé) :

| Où | Ce qui change |
|---|---|
| `routes/releves.poser_releve`, `modifier_releve`, `retirer` (route et levée d'un doute) | une région |
| `undo._inverser_releve`, `releves.rendre` (Ctrl+Z) | une région |
| `routes/grilles` : renommer une entrée, une variante, une case ; retirer ou remettre ne change rien | les régions de ses relevés |
| `grille_import._fusionner` (route de fusion, réimport d'une grille ouverte) | les régions des relevés fusionnés |
| `grille_import.importer` sur une grille ouverte (un libellé changé sous une même `cle`) | les régions de ses relevés |
| `database.copier_le_travail`, `repartir_de_zero` | déjà couverts : ils indexent par `_region_index_payload` APRÈS avoir écrit ou retiré les relevés (**lu**, l. ~3490 puis ~3497 ; ~4075 puis ~4120) |
| une région supprimée | déjà couvert : `unindex_region` |

Un CLIQUET, sur le patron de `test_csrf.py` : toute écriture de `releve` dans le source
(`INSERT`, `UPDATE`, `DELETE`) vit dans une fonction qui appelle `reindex_etiquettes`, ou est
déclarée avec sa raison. Sans lui, une étiquette posée par un chemin neuf serait introuvable sans
que rien ne tombe. Écartés : des déclencheurs SQL (la règle du dépôt, « pas par des triggers »).

### Le filtre (J7)

`releve=<grille>:<entrée>[:<variante>]`, un `EXISTS (SELECT 1 FROM releve …)` sur la région,
dans `_recherche_rows` (donc l'écran et son export CSV), sous la clause d'album existante. La
tranche 4 l'étend (grilles fermées, héritance d'une case vers ses bulles — l'ancien
`tag_scope=herite` — et l'Exploration). Le nom du paramètre ne heurte pas
`PARAMETRES_DU_VOCABULAIRE` (`tags`, `tag_scope`, `attributs`), refusés par un 422 (I7).

---

## Structurer — une tranche à part (J8)

Faire passer une étiquette, et ses relevés, dans une entrée d'une AUTRE grille active du projet.

- **Vers quelle version** : la version ACTIVE de la grille d'arrivée dans le projet
  (`projet_grille.version_id`). Pour une grille fermée, c'est une version publiée : on y AJOUTE des
  relevés, ce qui est le geste ordinaire, et on ne la modifie pas — la règle « une fermée ne
  fusionne pas » parle des relevés qui en SORTENT, pas de ceux qui y entrent. L'entrée d'arrivée
  doit exister dans cette version : si elle manque, un responsable l'écrit dans le brouillon et
  publie, et la montée de version d'un projet n'existant pas, l'activation doit suivre — à dire dans
  le bilan, pas à contourner.
- **La variante** : une table de correspondance, proposée par le libellé (`cle_tag`), corrigée à la
  main. Vers une entrée simple, la valeur n'a pas de place : le relevé reste.
- **La cible** : l'entrée d'arrivée doit accepter le type de la région (`grilles.type_convient`) ;
  une entrée qui vise des MOTS ne reçoit pas un relevé de zone entière (il n'a pas de passage) : il
  reste.
- **La cardinalité d'arrivée** : une entrée `une` déjà posée sur la même cible ne reçoit pas un
  second relevé : il reste.
- **Une précision ou un lien attendus** à l'arrivée : le relevé passe, et se dit « à compléter »
  (dérivé, `releves_effectifs`).
- **Le bilan, relevé par relevé** : passés, et restés par cause (valeur sans équivalent, cible,
  déjà posé, entrée absente) ; « Passer » éteint tant qu'il n'y a rien à passer ; l'étiquette
  vidée se propose au retrait.
- **Le journal** : un acte `releve` par relevé passé (`avant` : grille, version, entrée, variante),
  contrairement à `_fusionner` aujourd'hui — sans quoi « qui perd quoi » et le 409 de CONC-3 ne
  voient pas qu'un autre a touché ce relevé ; plus un acte `grille` qui résume. Les doutes suivent
  le relevé (`doute.releve_id`) ; les passes ne bougent pas.
- **Ctrl+Z** : pas du geste lui-même dans cette tranche (comme la fusion). Pour les gestes d'avant,
  `grille_id` et `entree_cle` entrent dans les valeurs que Ctrl+Z compare
  (`undo._VALEURS_DU_RELEVE`) : défaire une ancienne retouche d'un relevé structuré depuis reçoit
  le 409 qui nomme qui l'a structuré.
- **Qui** : qui gère le projet (le geste réécrit les relevés des autres et fixe un vocabulaire).

**Coût** : 3 jours (la route, son aperçu, le bilan, les tests, l'écran), et le bilan sur la même
maquette. Rien dans le schéma : il ne retarde pas la migration.

Une conséquence d'E5 à dire à Hugo : les étiquettes ne passent PAS d'un projet à l'autre à la
copie (la grille de travail d'un projet n'est active que chez lui : ses relevés sont COMPTÉS, pas
posés). Structurer vers une grille partagée est le chemin pour qu'un travail libre voyage.

---

## Le découpage

Estimations tests compris, sur le patron des cadrages précédents.

**Dans le commit 5 (la migration v39), ce qu'il doit ajouter ou changer** — ≈ 1¼ jour de plus :

- `etiquettes` à la place de `tags_concat` : `_FTS_SQL`, `_FTS_V39`, la recopie remplie en SQL,
  les lignes neuves des régions qui n'en avaient pas, `_region_index_payload` à trois valeurs,
  `_index_region`, et le test sur la vraie base v38 (J6). ¾ de jour.
- Le drapeau `grille.travail`, son index unique partiel, posé par `installer_grille_de_travail`
  (donc par la migration pour les projets existants) (J2). ¼ de jour.
- L'état : défini par défaut à l'import et au formulaire, provisoire en posant ; la migration ne
  rend provisoires que les entrées que le journal dit nées en posant (J4 a). ¼ de jour.

**Juste après, sans migration** (le serveur du mode libre) — ≈ 3½ jours :

- J3 : `plusieurs` à la naissance d'une entrée à variantes, le refus du doublon de variante, le
  refus de `plusieurs` → `une` contradictoire. ½ jour.
- `reindex_etiquettes`, ses appelants et son cliquet. 1 jour.
- La Recherche : la colonne cherchée, les étiquettes de chaque résultat (bornées par l'album), le
  filtre `releve=` (J7). ¾ de jour.
- J5 (c) : la question d'autorisation, les gestes ouverts sur une entrée provisoire, la clé
  `remaniable` dans le plan, et les deux cliquets (`test_autorisation.py`,
  `test_sorties_identite.py`). 1 jour.
- Le signal « ⟳ Actualiser » couvre l'empreinte des versions vivantes. ¼ de jour.

**Après la maquette** (l'écran) — ≈ 4¾ jours : la page Annotation (le champ, les puces, les
gestes sur place, la marque, l'arbre sans « Sans rubrique », l'état vide, l'étroit, le doigt, le
clavier ; Node et navigateur) 3½ jours ; la Recherche (la promesse du champ, les étiquettes d'un
résultat, la puce qui isole, la zone `recherche-champ` du wizard, « dialogues et notes » →
« dialogues, notes et étiquettes ») ¾ de jour ; la documentation (`CLAUDE.md` § Données et
§ Recherche FTS5, `docs/guide-utilisateur.md`, `docs/grilles-et-releves.md` § 4 et § 6) ½ jour.

**Structurer** (J8) : 3 jours, tranche à part.

**Total** : ≈ 9½ jours hors structurer, dont 1¼ dans la migration ; plus la séance de maquette.

**Ce qui ne se reporte pas** : la colonne `etiquettes` (après la v39, une seconde reconstruction de
l'index et, d'après I6, une seconde réindexation complète) ; le SENS de l'état provisoire avant
que la migration l'écrive (le commit 5 rend provisoires toutes les entrées des grilles ouvertes :
changer de règle ensuite serait une correction de données) ; le drapeau `grille.travail`, s'il est
voulu (sinon une migration v40 et sa vraie base v39). Tout le reste se fait sans schéma.

Chaque commit de code cite `ANN-7` ; la fiche se met à jour à part.

---

## Vu en passant

- **La cardinalité d'une entrée EMPLOYÉE change sans contrôle** (**mesuré**) : `PATCH
  …/entrees/{cle}` accepte `plusieurs` → `une` alors que deux relevés de l'entrée sont sur la même
  bulle ; ils restent, et `une`, figé à la pose, n'est pas réévalué. La forme et la liste d'une
  entrée employée, elles, ne changent pas (`reconcilier_ouverte`, **lu**). Cf. « se tranchent en
  route ».
- **En `plusieurs`, un doublon exact est accepté** (**mesuré**) : la même entrée, la même
  variante, deux fois sur la même bulle. J3 le refuse pour une variante.
- **La fusion n'écrit aucun acte par relevé** (**lu**, `grille_import._fusionner`) : seulement
  `releve_ids` dans l'acte `grille`. Pour une fusion entre entrées d'une même grille ouverte, faite
  par qui gère, c'est tenable ; structurer ne doit pas reprendre ce patron.
- **La grille de travail n'est reconnue que par son nom** (**lu**) : renommée, rien ne la
  distingue d'une autre grille ouverte (J2).
- **Le commit 5 rend provisoires les entrées importées d'une grille ouverte** (**lu**,
  `ecrire_plan`) : sans effet tant que l'état ne gouverne rien ; contradictoire avec J5 (b) ou (c)
  (J4).
- **Le signal « ⟳ Actualiser » ignore le plan** (**lu**, `empreinte.py`) : une étiquette née ou
  renommée ailleurs ne paraît qu'au rechargement.

---

## Ce que cette note n'a pas pu établir

- **La variante « tristesse » née malgré le refus**, vue par Hugo sur la recette : non reproduite à
  la route à `ed0a317` (le 409 défait tout), ni par le geste d'écran lu (« Remplacer par la
  mienne » envoie un corps vide, `remplacementCardinalite` sur `corps: {}`). Deux hypothèses : la
  recette sert un autre commit ; ou la variante est née par un autre geste (une autre zone,
  « Ajouter » rejoué). Ce qui trancherait : sur la recette, le journal — l'acte `grille` dont la
  charge porte `variante_neuve` « tristesse », sa date, et les relevés de la bulle à cette heure.
- **Où Hugo a essayé** : dans un bac à sable, la Recherche ne montrera jamais une étiquette (S8),
  quoi que décide J6.
- **Le tri des tests navigateur existants** que les puces de J3 et le champ de création touchent
  (`test_e2e_page_annotation*`, le test qui pose « lieu : forêt ») : non fait.
- **Que la recopie remplie en SQL tient sur la vraie base v38** : écrite ici, pas jouée.
- **L'état de la production** : la fiche dit la tranche 1 « pas en production avant le lot 5 » ; si
  des grilles ouvertes y portent déjà des relevés, la recopie les indexe, et J4 (a) demande leur
  journal — le contrôle d'I8 peut y ajouter une ligne (`SELECT COUNT(*) FROM releve r JOIN grille g
  ON g.id = r.grille_id WHERE g.ouverte = 1`).

---

## Annexe : les mesures

Toutes dans la copie à `ed0a317`, interpréteur `C:\Dev\BD_ditor\.venv\Scripts\python`, SQLite
3.49.1. Le test jetable n'est pas commité.

**Le test jetable** (`tests/test_jetable_mode_libre.py`, sur le décor de
`tests/test_grille_de_travail.py` : la grille de travail du projet du décor, une bulle, le compte
`stag` qui écrit dans l'album, `ADMIN` qui gère le projet) :

```text
« sentiment : perte » puis « sentiment : tristesse » sur la même bulle :
  R1 sentiment perte une=True
  R2 409 « Cette entrée ne se pose qu'une fois sur cette cible… » (releve_existant : perte)
  VARIANTES [perte]                       ← la variante n'est pas née
« ironie » deux fois sur la même bulle : 409 de la cardinalité
plan : [('sentiment', 'une', None, []), ('ironie', 'une', None, [])]
« élision » sur des mots dans la grille de travail : 422 « se pose sur toute la zone »

ADMIN passe « sentiment » à plusieurs (200), puis :
  « sentiment : tristesse » 201 ; une seconde fois 201 (doublon exact accepté)
  stag renomme « sentiment » : 403 « Les grilles d'un projet se règlent par ses responsables »
  GET /api/recherche?q=tristesse : 0 résultat

ADMIN passe « ironie » à plusieurs, pose un second relevé, repasse à une : 200 ;
  une troisième pose : 409 ; RELEVES [une=1, une=0]
```

**L'index** (`<scratchpad>/mesures/fts_etiquettes.py`, en mémoire) : une table FTS5 de cinq
colonnes remplie de N lignes synthétiques, recopiée dans une table où `etiquettes` remplace
`tags_concat`, puis la seule colonne `etiquettes` réécrite pour K régions par paquets de 500
(lecture des `rowid`, puis `UPDATE … WHERE rowid = ?`), puis une recherche sur la colonne :

```text
N=330      recopie 4 ms     K=30    réécriture 2 ms     trouvées 30
N=20 000   recopie 89 ms    K=1 500 réécriture 74 ms    trouvées 1 500
N=100 000  recopie 380 ms   K=5 000 réécriture 520 ms   trouvées 5 000
```

**La lecture du commit 5** : `diff --strip-trailing-cr` entre la copie à `ed0a317` et la copie
du commit 5 en pause, pour `database.py`, `grilles.py`, `grille_import.py`, `grille_ecriture.py`,
`routes/grilles.py`, `routes/releves.py` (les deux fichiers de la page Annotation sont
identiques).

**Les écritures de `releve`** :

```sh
git grep -n -E "INSERT INTO releve |DELETE FROM releve|UPDATE releve SET entree_cle" -- '*.py' ':!tests'
git grep -n -E "_index_region\(|_region_index_payload\(" -- database.py
```
