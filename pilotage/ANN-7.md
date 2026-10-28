---
chantier: ANN-7
statut: interrompu
---

# ANN-7 — les grilles d'annotation : un seul modèle, plusieurs vocabulaires, un catalogue

**Arrêté sur** — 2026-10-28, `9982e09` : **le jalon 1 de la tranche 2 est codé (cinq commits), et le premier commit du JALON 2 est sur `dev`** — `fa820e4` (les manques du serveur : `vu` au retrait d'un relevé, `version` dans sa vue, `--activer` et `--masquer` dans `tools/importer_grille.py`, les règles d'activation sorties dans `grille_import`), `db9a93f` (la page `/annotation`, SIXIÈME surface : trois colonnes stables, la minicarte, la case agrandie depuis le dérivé, le choix d'une zone, le Contexte en lecture, l'adresse et « Ouvrir dans l'Atelier ↗ » ; déclarée partout où l'on énumère les surfaces) et `c280fac` (la grille en LECTURE : les onglets des grilles actives non masquées, le plan et ses trois formes, rubriques repliables avec « n ici », le filtre « / », la ligne du guide à hauteur fixe, le guide complet en modale, `&grille=` dans l'adresse ; rien ne se pose encore, « terminée » viendra avec les passes ; le filtre est un champ à `aria-activedescendant` et non une combobox, pour que la sonde du reflow ne le compte pas parmi les repliables ; les décors de l'a11y, du reflow et des modales activent la grille fictive). et `2c26a0b` (DÉSIGNER et POSER : des mots au clic, au glissé, à Maj et Ctrl, et au clavier comme une liste à sélection multiple ; les traits des relevés sous les mots, en couloirs teintés par rubrique ; « Porte sur » mots, zone, case ou planche ; cocher pose, recocher retire, une autre variante remplace en place avec `vu`, une autre entrée se pose après retrait — H5 au plus prudent, sans route atomique ; la liste de ce qui est posé, précision et lien sur place, ✕ avec `vu` ; le 409 de CONC-3 dans un bandeau à la place de la ligne du guide ; une lectrice voit les entrées éteintes, NON joué en e2e, le décor étant mono-poste). et `c7369b8` (« TERMINÉE », le PARCOURS, Ctrl+Z : le pied de la colonne de la case — « Grille : à faire / ✓ terminée », « Rouvrir », « ‹ Précédente », « Suivante › », « Terminée, suivante › », Ctrl+Entrée et Ctrl+Maj+Entrée ; la passe sur la grille ou sur la rubrique de tête affichée ; le parcours dérivé des cibles de la grille, la planche en dernière étape ; ✓ dans l'onglet, case terminée et case en doute sur la minicarte ; Ctrl+Z commun à l'Atelier et à la page, sorti de `viewer.js` dans `static/lib/annulation.js` ; un défaut trouvé en vérifiant une hypothèse du commit 3 — le défilement dû au focus faisait passer une entrée sous le pointeur immobile et le survol reprenait la ligne du guide — corrigé : un survol ne compte que si la souris a bougé). Mutants 12 + 14 + 20 + 37 + 35, tous rougis (trois équivalents, remplacés ou qui ont fait retirer une garde morte) (un équivalent, qui a fait retirer une garde morte) ; suite par défaut verte à chaque commit (3 260 au dernier) ; e2e de la page et des audits de surfaces verts. Cadrage : `docs/ann7-tranche2-cadrage.md`, H1–H7 tranchés le 2026-10-27. Relevé en route : la sixième entrée de la nav fait passer « Aa » sur une seconde ligne à 1 000 px, sur toutes les surfaces. Hugo, le 2026-10-28 : ce retour à la ligne ne le gêne pas pour l'instant ; si la place manque, l'icône de compte et le nom affiché (« chercheur »…) se fondront en un seul élément. Non joués en e2e, faute d'un décor à deux identités sur la page : une lectrice (entrées éteintes) et « Passer ce geste » (couvert par l'Atelier et par Node). Les audits de surfaces ont été joués sur /annotation seule, commit par commit : la passe navigateur ENTIÈRE reste due avant la fusion vers `main`. Jalon 2, commit 5 — `9982e09` (le DOUTE et la SYNTHÈSE, par un agent neuf : « ? » sur chaque ligne posée, le formulaire dans la boîte du guide, le fil ; deux onglets à gauche, « Planche » et « Synthèse » — Relevés par case, À revoir avec Répondre et la levée Garder / Changer… / Retirer, Décompte (H6) — ; le serveur rend les doutes levés dans `GET /api/planches/{id}/releves`, une seule forme pour un doute, le cliquet des sorties d'identité redéclaré ; H5 au plus étroit : « Changer… » en place pour une entrée à variantes seulement, éteint ailleurs avec « retirez, puis posez l'autre » ; la première partie e2e à deux identités sur la page, une lectrice derrière le proxy). Mutants 36, tous tombés ; suite par défaut 3 262 verts. La passe `pilotage/qa/page-annotation-jalon-1.md` (33 cases) est rendue à Hugo, recette reconstruite sur `312e8a5`, état `avant-ann7-j1`. À la reprise : commit 6 (deux écrans : l'empreinte compte relevés, passes et doutes ; « ⟳ Actualiser » ; un relevé retiré ailleurs), qui clôt le jalon 2.

**Plus tôt, le 2026-10-26** — `3dc6b48` : **la tranche 1 est sur `dev` (local, non poussée)**, 21 commits de `f511997` (rejoué) à `3dc6b48`, cherry-pickés sur `53d258e` sans conflit, suite par défaut 3 198 verts sur la copie d'intégration. La v37 (grilles, versions, entrées, relevés, passes, doutes ; `regions.nom`, `passe.recopiee`), l'import d'une grille en tableur (`tools/importer_grille.py`, `tools/grille-modele.csv`), les routes des relevés, des passes et des doutes, la règle du travail d'autrui étendue (dix sources), Ctrl+Z des relevés. Relu QUATRE fois — relecture croisée (six constats), contre-relecture (sept), contre-relecture n°2 (trois), vérification finale — : la règle « personne d'autre n'y a travaillé » a produit à chaque tour des cas limites de copie de copie, réglés au dernier tour par la forme FERMÉE (compter trop plutôt que trop peu) ; c'est l'un des arguments de la séance de simplification des règles d'effacement (`pilotage/COL-3.md`, zone « Le responsable voit tout son projet »). Pas en production avant le lot 5. À la reprise : la tranche 2 (la page Annotation d'`ANN-6`, sur la maquette v3), et la relecture du brouillon de la grille par la gestionnaire et les linguistes.

**Point de départ** — 2026-10-14. La grille des linguistes (cf. `ANN-6`) a posé une question
plus large qu'elle-même : l'outil annote-t-il avec CE vocabulaire, ou avec des vocabulaires ?
Discutée avec Hugo le même jour, sans rien coder : l'outil sera agnostique, accueillera
plusieurs grilles côte à côte, les partagera dans un catalogue où chacune entre si ses
responsables le décident, et n'aura qu'UN modèle — les tags et les attributs d'aujourd'hui y
entreront. Rien n'est écrit ; cette fiche garde ce qui est tranché et ce qui reste à cadrer.

## Reste

### Tranché par Hugo — 2026-10-14

- [x] **L'outil est agnostique** — attendu : tranché. Le code ne connaît aucun vocabulaire —
  ni un tag, ni un niveau, ni le mot « linguistique » — ; tout ce qui fait une grille est une
  donnée importée. Plusieurs grilles vivent côte à côte, et une même bulle reçoit des relevés
  de plusieurs. Le contenu est libre, les FORMES sont bornées : trois (simple, à variantes, à
  qualificatifs), et une forme nouvelle demande du code, une fois, pour toutes les grilles.
  Chaque grille est fermée (elle se coche, ses responsables seuls l'enrichissent) ou ouverte
  (elle s'enrichit pendant l'annotation, comme les tags libres). Hugo : « Je suis d'accord sur
  ce que tu décris pour le caractère agnostique »
- [x] **Un catalogue, où une grille entre par une case « Partager »** — attendu : tranché.
  Hugo : « il faut que les utilisateurs puissent choisir si leur grille entre dans le pot
  commun (une case à cocher sur le mode du "Partager", avec du versioning) », avec la crainte
  qui fonde les versions : « si on commence à utiliser un vocabulaire issu d'une autre
  personne, mais qu'elle fait évoluer la grille et modifie toute la lecture des images, ce
  serait compliqué »
- [x] **Une grille s'écrit dans un tableur, BD_ditor la vérifie et la garde** — attendu :
  tranché. Hugo : « Je vais suivre ta recommandation je pense ». Pas d'éditeur d'arborescence
  dans l'outil ; un écran de BILAN à l'import, cf. « Le modèle »
- [x] **Les responsables du projet publient les versions et cochent « Partager »** —
  attendu : tranché. Aucune validation préalable par un administrateur : il trie après coup.
  Hugo : « Quitte à ce qu'il y ait plein de proposition de vocabulaire, mais que je fasse le
  tri parfois. ça me parait plus simple »
- [x] **Une grille s'active sur le projet** — attendu : tranché. Toutes les collections d'un
  projet comptent avec les mêmes grilles. Hugo : « Sur le projet également je pense »
- [x] **Un seul modèle : les tags et les attributs d'aujourd'hui deviennent des grilles** —
  attendu : tranché. Hugo : « ok pour un seul modèle ». Le basculement a lieu quand le nouveau
  mode d'annotation remplace le panneau actuel, cf. « Un seul modèle »

### Tranché par Hugo — 2026-10-22, la séance de conception

- [x] **Q1 — Le projet STOCKE l'activation, une collection peut RESTREINDRE l'affichage** —
  attendu : tranché. Une grille s'active sur le projet ; une collection du projet peut ne
  montrer qu'une partie de ses grilles actives (« Paratexte » n'affiche que les tags libres).
  La restriction est un FILTRE D'ÉCRAN, pas une garde : le serveur ne refuse aucun relevé selon
  la collection d'où l'on vient, et les relevés déjà posés restent visibles en lecture. **Un
  relevé ne porte aucun `collection_id`** : il tient à sa cible, et un album rangé dans deux
  collections du projet montre les mêmes relevés par l'une et par l'autre. Tranché par Hugo le
  2026-10-22 (proposition (b) du dossier) ; l'activation par collection, que rouvrait
  `docs/collections-niveau-ou-calque.md`, est écartée
- [x] **Q2 — Les grilles SONT le vocabulaire au niveau du projet de la tranche 4 de `COL-3`** —
  attendu : tranché. Le vocabulaire ne migre qu'une fois, vers les grilles ; la tranche 4 de
  `COL-3` ne garde que les personnages, la Recherche et l'Exploration bornées au projet, et le
  double compte des copies sœurs. Tranché par Hugo le 2026-10-22 ; le renvoi est posé sous la
  case « Le vocabulaire et les personnages ont un étage de projet » de `COL-3`
- [x] **Q3 — Le basculement part d'un vocabulaire NEUF, sans conversion** — attendu : tranché.
  Ce que la production porte est un corpus de test (Hugo, 2026-10-21) : les tags, dimensions,
  valeurs et leurs affectations ne deviennent pas des grilles ; leurs tables sont retirées au
  basculement, et les Ctrl+Z d'avant lui sont coupés (passés, comme un acte d'`AUTH-14`) au lieu
  de réécrire dans des tables mortes (`undo._ensure_tag`). Aucun terme local ne devient donc
  visible du projet entier : la question de portée d'`AUTH-11` ne se pose pas. **Condition** :
  que personne ne pose de vrai travail en tags d'ici là — cf. Q9, les stagiaires. Tranché par
  Hugo le 2026-10-22
- [x] **Q8 — Activer une grille partagée est LIBRE** — attendu : tranché. Partager vaut
  publier : tout responsable de projet active une grille du catalogue sans rien demander.
  L'asymétrie avec le fonds est voulue et s'écrit ainsi : prendre au fonds touche des
  DOCUMENTS (des images, le travail d'autrui), activer une grille ne copie rien et n'expose que
  son plan, que le partage a rendu public. Le catalogue emprunte au fonds son patron d'écran
  (liste et fiche), pas sa demande. Tranché par Hugo le 2026-10-22
- [x] **Q4 — Le personnage est DEUX cibles : la boîte et l'entité** — attendu : tranché. La
  boîte (`personnage`, une région : ce personnage dans cette case, sous les droits de l'album)
  et l'entité du registre (`entite` : ce personnage partout, le profil d'aujourd'hui), rattachée
  au PROJET de la grille. L'entité n'ayant aujourd'hui ni album ni portée, la cible `entite`
  attend son étage de projet, la moitié des personnages qui reste à la tranche 4 de `COL-3`
  (Q2) : à séquencer ensemble. Avec Q3, le profil d'entité ne se convertit pas, il se repose.
  Tranché par Hugo le 2026-10-22
- [x] **Q5 — À l'assemblage d'une double page, les relevés « planche » sont REPORTÉS** —
  attendu : tranché. La planche reste la surface (`IMG-2`, 2026-10-16) ; l'assemblage reporte
  sur la surface les relevés de la planche absorbée, avec une trace au journal. La table des
  relevés n'est PAS en `CASCADE` sur la planche. Le chantier qui arrive second (`IMG-2` ou la
  tranche 1 des grilles) écrit le report ; d'ici là, assembler une planche qui porte des
  relevés est refusé par un 409 qui le nomme. Les relevés des régions suivent d'eux-mêmes (une
  région garde son identifiant). Tranché par Hugo le 2026-10-22 — le cas est l'ordinaire et
  non l'exception, toute double page se scannant en deux images (`IMG-2`, 2026-10-21)
- [x] **Q6 — La cardinalité se déclare dans le tableur** — attendu : tranché. Une colonne
  `cardinalite` (`une` · `plusieurs`) ; vide, elle prend le défaut de la cible : `plusieurs`
  sur des mots (deux élisions dans une bulle), `une` sur une région entière ou la planche (un
  seul registre par bulle). Le serveur refuse un second relevé d'une entrée `une` sur la même
  cible ; à l'écran, en choisir une autre remplace. Tranché par Hugo le 2026-10-22
- [x] **Q7 — La passe est COMMUNE et signée, les valeurs uniques portent une version** —
  attendu : tranché. Une passe « appliquée » vaut pour tous et dit qui l'a faite, quand : on se
  partage les zones. La variante choisie, la levée d'un doute et la passe portent une version de
  ligne dès la tranche 1, et une écriture sur une valeur périmée reçoit le 409 de `CONC-3`
  — c'est la réponse au renvoi de `CONC-4` (les attributs de case à plusieurs). La double
  annotation à l'aveugle (deux passes séparées, pour mesurer l'accord) n'est pas exclue : elle
  serait un mode de campagne, plus tard, et la question va aux linguistes. Tranché par Hugo le
  2026-10-22
- [x] **Les champs d'un relevé** — attendu : arrêtés, avant de maquetter l'onglet Annotation.
  Un identifiant `AUTOINCREMENT` ; UNE cible parmi quatre — une région (bulle, cartouche,
  texte, case, boîte personnage, détail), la planche (la surface), l'entité personnage, ou des
  mots d'une région ; le passage (rang et forme de chaque mot) ; la version de la grille ; la
  `cle` de l'entrée ; la `cle` de la variante ou la liste des qualificatifs ; la précision libre ;
  le lien vers une autre région ; un état (normal · à revoir · à compléter) ; l'auteur, les dates
  de création et de modification, la version de ligne (Q7). AUCUN `collection_id` (Q1).
  `CASCADE` sur la région cible (Ctrl+Z les rend, note §11), jamais sur la planche (Q5).
  Tranché par Hugo le 2026-10-22, tels que proposés
- [x] **Un lien dont la région désignée disparaît passe « à revoir »** — attendu : tranché. Le
  relevé reste, perd sa cible, garde le texte de la région qu'il désignait ; Ctrl+Z de la
  suppression le rattache. Le patron d'un passage dont un mot a disparu (note §5). Tranché par
  Hugo le 2026-10-22
- [x] **Une copie sœur n'emporte les relevés que d'une grille active à l'arrivée** — attendu :
  tranché en principe, codé avec la 3b de `COL-3`. Les relevés partent au cran `annotations`
  avec leur auteur (aucun événement recopié, la chaîne de `region_origine` les attribue, E3) ;
  les zones `detail` et `texte`, des régions, partent au cran `decoupage`. Le patron d'E5 : ils
  suivent si leur grille est active dans le projet d'arrivée, QUELLE QUE SOIT la version (un
  relevé de la v2 se relit en v2) ; sinon ils sont COMPTÉS dans l'aperçu, qui propose d'activer
  d'abord une grille partagée. Jamais posés et invisibles (le piège de `COL-1`). Tranché par
  Hugo le 2026-10-22
- [x] **À la copie, les passes suivent, les doutes non** — attendu : tranché en principe. Sans
  ses passes, un relevé copié arriverait sur une zone « à faire » ; un doute est une
  conversation de l'équipe source, qui nomme ses membres, et l'arrivée n'en hérite pas.
  Tranché par Hugo le 2026-10-22
- [x] **Deux gardes qui échouent OUVERT couvrent les relevés, et un cliquet les tient** —
  attendu : tranché en principe. La règle « travail d'autrui » de la suppression directe
  (`autorisation._sql_travail_d_autrui`) compte les actes sur les relevés, les passes et les
  doutes — sans quoi on supprimerait seul un album annoté par d'autres ; « Repartir de zéro »
  (E8) les efface. Un test exige que toute table de l'annotation soit lue par l'une et par
  l'autre. Et la fusion de deux régions réunit leurs relevés, ceux d'une entrée `une` qui se
  contredisent passant « à revoir ». Tranché par Hugo le 2026-10-22
- [x] **Q9 — Les stagiaires commencent par ce qui ne se reprend pas** — attendu : tranché.
  Découpage, transcription relue, locuteurs, lieux ; AUCUN tag avant le basculement — c'est la
  condition de Q3, qui tient donc sans règle de conversion. Une planche relue (statut de
  relecture) est le feu vert des relevés. Option (b) d'`ANN-6`, retenue par Hugo le 2026-10-22
  (le dossier proposait (c) ; le vocabulaire neuf l'a fait préférer)
- [x] **Q9 — Qui publie la grille des linguistes** — attendu : tranché. Elle s'importera dans
  le projet « Principal » ou « LingApp », à choisir au déploiement ; Hugo, administrateur, et
  la gestionnaire du projet la publient. Dit par Hugo le 2026-10-22. Reste à vérifier au
  déploiement, case ci-dessous

### Tranché par Hugo — 2026-10-25, sur le cadrage de la tranche 1 (`docs/ann7-tranche1-cadrage.md`)

- [x] **Le cadrage de la tranche 1 est écrit, lu dans le code** — attendu : une note qui réconcilie la note du modèle (2026-10-14) avec la séance du 2026-10-22 et la maquette v3, jusqu'aux tables (v37, après la v36 de la 3b de `COL-3`), aux routes et aux gardes **Écrit le 2026-10-25** : `docs/ann7-tranche1-cadrage.md` (R1 à R13, sept commits, 8 à 9 jours estimés), vingt décisions G1 à G20
- [x] **G1 à G18, G20 (a) et (b) : les propositions de la note** — attendu : tranché. **« Oui à tout », Hugo, 2026-10-25** — la valeur vue de CONC-3 pour Q7, sans colonne de version (G1) ; l'état d'un relevé DÉRIVÉ par une vue (G2) ; la cible entité refusée à la pose avant l'étage de projet des personnages (G3) ; un lien vers une région du même album (G4) ; le plan lu aussi par les membres du projet et par qui lit un album portant un relevé de la grille (G5) ; des grilles dans un bac à sable, jamais partagées, effacées avec lui (G6) ; le propriétaire de la collection masque (G7) ; une région qui change de type : relevés « à revoir », rien retiré (G8) ; l'auteur d'un relevé recopié entre deux projets à NULL (G9) ; les relevés comptent dans les rangs des pseudonymes dès la tranche 1 (G10) ; les mots rendus par une route, sans jumeau JS (G11) ; une anomalie refuse le tableur entier (G12) ; deux CSV, pas de XLSX (G13) ; une entrée naît en la posant, renommer et fusionner en tranche 3 (G14) ; la coquille corrigée sans nouvelle version dès la tranche 1 (G15) ; le réexport dès la tranche 1, réservé aux gérants, déclaré hors du droit d'export (G16) ; `regions.nom` en v37 (G17) ; supprimer un projet qui a des grilles : 409 nommé (G18) ; douter, répondre, lever : qui écrit dans l'album (G20 a) ; la re-segmentation garde une case qui porte une situation ou des relevés, corrigé au commit 5 (G20 b — défaut existant, lu : une situation de case est perdue aujourd'hui)
- [x] **G19 — la vraie grille en tableur** — attendu : tranché. **Hugo, 2026-10-25 : un agent fait le brouillon** — la grille n'existe qu'en PDF, hors du dépôt ; un agent la transcrit en tableur HORS DU DÉPÔT, avec ses `cle`, et liste ce qui ne tient pas dans les trois formes ; la gestionnaire et les linguistes le relisent et le corrigent avant l'import
- [x] **G20 (c) — les lieux des stagiaires avant le basculement** — attendu : tranché. **Hugo, 2026-10-25 : elles attendent la grille.** Les lieux ne se posent qu'une fois la grille « Lieux » et la page Annotation prêtes ; d'ici là, les stagiaires découpent et transcrivent. Rien n'est à convertir, et la tension entre Q9 et Q3 ne se pose pas
- [x] **Qui lit les auteurs d'un relevé** — attendu : tranché. La relecture croisée de la tranche 1 (2026-10-26) a relevé qu'un simple LECTEUR de l'album lit dans `GET /api/planches/{id}/releves` le login des auteurs et le fil des doutes ouverts (déclaré dans `SORTIES_DECLAREES`), alors que la fiche disait qu'un doute « nomme ses membres ». **Hugo, 2026-10-26 : « Ils peuvent voir les auteurs »**, et le fil des doutes aussi : « des lecteurs peuvent être des spécialistes, qui arpentent le corpus » — le cercle des lecteurs est le bon public ; rien ne change dans le code
- [ ] **Le brouillon de la grille est relu par la gestionnaire et les linguistes** — attendu : le tableur corrigé, ses six écarts du guide réglés, prêt pour l'outil d'import ; il vit hors du dépôt
- [ ] **Un gabarit de tableur qui ne perd personne** — attendu : quelqu'un qui n'a jamais vu l'outil construit seul une grille nouvelle dans le tableur, sans se tromper de forme ni casser l'import. Demandé par Hugo le 2026-10-25, pour plus tard : le format d'import de la tranche 1 (deux CSV, `cle`, une ligne de variante qui répète la `cle` de son entrée, des cibles séparées par ` | `) est fait pour une machine ; le gabarit doit l'être pour une personne — des exemples remplis, une colonne par question qu'on se pose, les trois formes expliquées là où on les choisit, les erreurs dites en mots par le bilan d'import. À concevoir avant que d'autres équipes créent leurs grilles (catalogue, Q8). Le brouillon de la grille des linguistes, `C:\temp\grille-linguistes\`, montre ce qui déroute aujourd'hui

### Tranché par Hugo — 2026-10-27, sur le cadrage de la tranche 2 (`docs/ann7-tranche2-cadrage.md`)

- [x] **Le cadrage de la tranche 2 est écrit, lu dans le code** — attendu : une note qui suit la maquette v3 geste par geste jusqu'aux routes de la tranche 1. **Écrite le 2026-10-27** : trois jalons (≈ 9, 3½ et 5½ jours), onze commits, aucune migration ; cinq manques du serveur ; la cible « personnage, partout » non offerte (G3)
- [x] **H1 à H7** — attendu : tranché. **Hugo, 2026-10-27, la proposition à chaque question** : le jalon 1 d'abord (H1) ; le mode Annotation de l'Atelier gardé avec un renvoi croisé (H2) ; chaque bac à sable naît avec une grille fictive activée (H4) ; « Changer… » en place, sinon « retirez, puis posez l'autre » (H5). Le pilotage prend H3 (`--activer`), H6 (le décompte dans la Synthèse) et H7 (une page, pas un module montable)
- [x] **Jalon 1 — une page où l'on annote** — attendu : codé. Les manques du serveur et `--activer` (commit 0, **fait** `fa820e4`) ; la page, sixième surface (commit 1, **fait** `db9a93f`) ; la grille en lecture (commit 2, **fait** `c280fac`) ; désigner les mots et poser les relevés (commit 3, **fait** `2c26a0b`) ; « terminée », le parcours, Ctrl+Z (commit 4, **fait** `c7369b8`)
- [ ] **Jalon 2 — le travail à plusieurs** — attendu : codé. Le doute et la Synthèse (commit 5, **fait** `9982e09`) ; « ⟳ Actualiser » (l'empreinte compte relevés, passes, doutes)
- [ ] **Jalon 3 — la maquette entière** — attendu : codé. Le Contexte modifiable ; tracer une zone (le type `detail`, exclu de toute sortie, relecture croisée) ; écrans étroits et doigt ; le renvoi depuis l'Atelier et les docs
- [ ] **Un bac à sable naît avec une grille fictive activée** — attendu : codé (H4, ≈ 1 jour), à la fin de la tranche 2 ou en tête du wizard ; effacée avec lui

### Relevé par Hugo en jouant la passe du jalon 1 — 2026-10-28 (`pilotage/qa/page-annotation-jalon-1.md`)

- [ ] Dans la liste de ce qui est posé, la précision d'un relevé et son ✕ tiennent sur UNE ligne : le champ se réduit, ✕ reste à sa droite (sur la recette, à la largeur de Hugo, ✕ passait sous le champ)
- [ ] Un lien posé dit QUELLE zone il désigne : la ligne du relevé dans la liste de ce qui est posé nomme la bulle liée (son étiquette ou le début de son texte), et non seulement « Changer le lien » — Hugo n'a pas pu vérifier à l'écran que « Pédé ! » était la bulle choisie (elle l'était, lu en base)
- [ ] « Désigner sur la planche » dit qu'on peut cliquer une bulle sur la minicarte : en dehors de ce mode, la minicarte ne choisit que des cases, et rien n'annonce qu'elle change de rôle (le contour ambre seul ne l'a pas fait voir)
- [ ] La liste de ce qui est posé a plus de place : la boîte du guide (définition, exemples) se REPLIE et se déplie (`aria-expanded`), repliée la liste prend sa hauteur, et le choix est retenu (stockage local, sous try/catch) — Hugo, 2026-10-28. La boîte du guide porte aussi le formulaire du doute et le bandeau du 409 : ils la déplient d'office quand ils s'ouvrent, sinon un conflit passerait inaperçu ; la sonde du reflow la mesure dépliée (`tools/mesurer_reflow.DEPLIES`)

### Le modèle — à écrire avant tout code

- [ ] **Les quatre objets sont définis** — attendu : écrit, avec leurs champs. La GRILLE (un
  nom, ses responsables, son projet, son état : brouillon, en usage, retirée) ; la VERSION (un
  état daté et figé, sa note de changement) ; la RUBRIQUE (range, s'imbrique, ordonnée ; on
  n'y pose rien) ; l'ENTRÉE (ce qu'on pose), avec un identifiant stable et invisible, un
  libellé, une définition, une structure, des exemples, une cible, un état
  **Posés le 2026-10-14** dans `docs/grilles-et-releves.md` (§2), avec leur rôle : grille, version, rubrique, entrée, variante, liste de qualificatifs, activation, relevé, doute, passe. Leurs champs s'écrivent avec la migration de la tranche 1 : la case se coche là
- [x] **Les trois formes d'entrée sont définies** — attendu : écrit, chacune avec son geste.
  Simple (posée ou non) ; à variantes (un phénomène, puis UNE variante des siennes) ; à
  qualificatifs (un phénomène, plus un ou plusieurs choix dans une liste PARTAGÉE entre
  plusieurs entrées). Une précision libre peut s'ajouter à une entrée. La grille des
  linguistes s'y range entière : à vérifier en l'important
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§3), avec la précision libre et le lien vers une autre zone
- [x] **Une entrée à qualificatifs compte comme les linguistes comptent** — attendu : tranché
  avant la migration de la tranche 1. Les linguistes ont répondu le 2026-10-22 (rapporté par
  Hugo) : « emphase par typographie et ponctuation » fait DEUX tags, donc deux emphases.
  **Tranché par Hugo le même jour : le modèle ne change pas.** Une grille est une DONNÉE —
  l'outil est agnostique, la grille appartient à ses responsables, qui la modifient et
  décident de ses entrées et de ce qu'elles comptent. La grille des linguistes écrira donc
  l'emphase par manière (une entrée « emphase par typographie », une « emphase par
  ponctuation »), et la forme à qualificatifs garde sa règle : un relevé compte UNE fois son
  phénomène. Ce que l'outil doit, c'est DIRE comment chaque forme compte, dans le modèle du
  tableur et sa documentation, pour que l'auteur d'une grille choisisse en connaissance de
  cause
- [x] **La cible d'une grille est une donnée** — attendu : écrit. Des mots d'une zone, une
  zone entière, une case, un personnage, une planche : c'est ce qui laisse entrer dans le même
  modèle une grille d'oralité, des émotions de personnages et la situation d'une case
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§4) : une version déclare ce qu'elle vise, parmi huit sortes ; le détail devient un type de région
- [x] **Une entrée peut déclarer sa propre cible** — attendu : tranché. La note fait déclarer
  la cible à la VERSION de la grille ; or la sorte de locuteur se pose sur la zone entière et le
  lieu sur la case, dans une grille qui vise surtout des mots (`ANN-6`, 2026-10-22). Une colonne
  `cible` facultative dans le tableur ; vide, l'entrée prend la cible choisie dans « Porte
  sur ». Sur la maquette v3, une telle entrée se pose d'elle-même sur sa cible et le dit
  (« toute la zone »). Tranché par Hugo le 2026-10-22 ; la note le dira au premier commit de la
  tranche 1 (case « La note est à jour » ci-dessous)
- [x] **Le doute n'est pas une entrée** — attendu : écrit. C'est une propriété de tout relevé,
  fournie par l'outil quelle que soit la grille, avec son commentaire. Le guide des
  linguistes le range comme un tag transversal
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§2, §8)
- [x] **Ce qu'une grille ne redéfinit pas se déclare « pris dans l'outil »** — attendu :
  écrit. Le premier niveau de la grille des linguistes (type de zone, locuteur, lieu) existe
  déjà dans l'outil
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§2)
- [x] **Un exemple peut désigner un relevé du corpus** — attendu : tranché. Un exemple est du
  texte, ou un renvoi à un vrai relevé, qui s'ouvre en un clic ; le guide laisse plusieurs
  « [exemple du corpus] » vides
  **Tranché par Hugo le 2026-10-22** : un exemple est un texte, ou un renvoi à un relevé, qui
  s'ouvre en un clic pour qui LIT son album. Les autres, en particulier depuis le catalogue,
  lisent « exemple du corpus d'un autre projet » SANS son texte : le guide d'une grille
  partagée ne fait pas sortir de transcription
- [x] **Une version en usage ne se modifie pas en place** — attendu : écrit. On prépare la
  suivante, on la publie ; un relevé dit dans quelle version il a été posé. Effet de chaque
  changement : ajouter, renommer (l'identifiant tient), retoucher une définition (le sens
  bouge, la note de version le dit) n'abîment aucun relevé ; déplacer une entrée change les
  comptes par rubrique, passé compris ; supprimer une entrée employée est interdit, elle
  devient « retirée » ; fusionner reporte les relevés, tracé ; scinder met les relevés « à
  revoir » ; changer de forme met les relevés incomplets « à compléter »
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§6) : une version est un instantané complet, tranché par Hugo ; la montée de version d'un projet attend une tranche ultérieure
- [x] **Le tableur porte une colonne d'identifiants, et l'import rend un bilan** — attendu :
  écrit, sur le format d'import existant (`lexique_import.py`, `tools/vocabulaire-modele.csv`).
  Sans identifiant, un libellé renommé se lit comme une suppression suivie d'un ajout.
  L'écran de bilan prend les décisions du tableau des changements avant de publier :
  ajouts, renommages, et pour chaque entrée disparue qui a des relevés, « retirer, ou fusionner
  dans… ». BD_ditor réexporte la grille vers le tableur, identifiants compris
  **Écrit le 2026-10-14** dans `docs/grilles-et-releves.md` (§7) : les colonnes, le bilan avant publication, le réexport
- [x] **Une coquille se corrige à l'écran** — attendu : tranché. Seule exception au tableur
  envisagée : une définition ou un exemple, qui ne touchent aucun relevé
  **Tranché par Hugo le 2026-10-22** : par un responsable, sans nouvelle version, tracé au
  journal (déjà écrit dans la note, §6)
- [ ] **Le guide des linguistes découle de la grille** — attendu : tranché. BD_ditor peut en
  produire les pages (rubriques, entrées, structures, exemples), pour qu'il ne soit plus tenu
  à côté
  **Tranché par Hugo le 2026-10-22 : oui**, en tranche 2 ou après — la tranche 1 n'a pas d'écran
- [ ] **La note est à jour des décisions du 2026-10-22** — attendu : `docs/grilles-et-releves.md`
  dit la cible `entite` (§4, Q4), la restriction d'affichage par collection (§10, Q1),
  l'absence de `CASCADE` sur la planche et le report à l'assemblage (§11, Q5), la colonne
  `cardinalite` (§7, Q6), la passe commune et la version de ligne (§9, Q7), le lien « à revoir »
  (§3), les relevés aux crans de copie (nouveau §) ; sa question ouverte n°7 renvoie à Q9 ; la
  n°6 est tranchée sur la maquette v3 d'`ANN-6` (2026-10-22) : la passe s'appelle « terminée »,
  et « à compléter » a une seconde cause, un lien ou une précision attendus et absents (§3, §9) ;
  une entrée peut déclarer sa propre cible, colonne `cible` (§4, §7) ; le lieu et la sorte de
  locuteur ne sont plus « pris dans l'outil » (§2).
  À faire au premier commit de la tranche 1, pas avant : la note fixe ce qui se code

### Le catalogue et le partage

- [x] **Seules les versions publiées se partagent** — attendu : écrit. Décochée par défaut, la
  case « Partager » laisse la grille à son projet, invisible des autres ; cochée, elle entre au
  catalogue et tout projet peut l'activer. Le brouillon reste chez ses auteurs
  **Tranché par Hugo le 2026-10-22**, tel qu'écrit
- [x] **Un projet reste sur sa version et choisit quand passer à la suivante** — attendu :
  écrit. Il voit qu'une version neuve existe, lit son bilan pour SES relevés, et décide ;
  sans son accord, rien ne bouge — l'écran d'annotation montre les entrées et les définitions
  de sa version. Une campagne en cours ne voit pas sa grille changer sous elle
  **Tranché par Hugo le 2026-10-22**, tel qu'écrit
- [x] **Décocher « Partager » ne retire rien à personne** — attendu : écrit. La grille sort
  du catalogue pour les nouveaux venus ; les projets qui l'emploient la gardent
  **Tranché par Hugo le 2026-10-22**, après avoir demandé si la règle servait : il en faut
  une, les deux autres issues étant d'ôter sa grille à un projet qui y a posé des relevés, ou
  d'interdire de décocher dès qu'un autre projet l'emploie. Celle-ci est la plus simple
- [x] **Adapter une grille commune, c'est proposer ou dériver** — attendu : écrit. Proposer
  aux responsables, pour la version suivante ; ou dériver une grille neuve qui garde la trace
  de son origine et les identifiants des entrées héritées, donc comparable sur ce qu'elles
  partagent. Jamais modifier une grille commune pour son seul projet
  **Tranché par Hugo le 2026-10-22, en version ALLÉGÉE** : seul l'interdit est une règle
  (jamais modifier une grille commune pour son seul projet). Proposer n'est pas un geste de
  l'outil : on écrit aux responsables. Dériver, c'est réexporter le tableur (identifiants
  compris) et le réimporter comme grille de son projet ; les `cle` héritées la gardent
  comparable. La trace de l'origine viendra plus tard, si l'usage la demande
- [x] **La suppression suit l'emploi** — attendu : écrit. Une grille que nul autre projet
  n'emploie, son responsable la supprime ; employée ailleurs, elle ne peut que sortir du
  catalogue, et la supprimer se DEMANDE à un administrateur. Le tri de l'administrateur suit la
  même règle
  **Tranché par Hugo le 2026-10-22, en version ALLÉGÉE** : employée par un autre projet, une
  grille ne se supprime pas, elle peut seulement sortir du catalogue. Seul un administrateur
  la supprime, lors du tri. Pas de demande, donc pas de sixième genre dans « À faire »
- [x] **Les grilles d'un projet se règlent dans la fiche du projet** — attendu : tranché. Dans
  Administration › Projets, la fiche dit les grilles actives et leur version, et c'est là
  qu'on importe, qu'on partage et qu'on active depuis le catalogue (liste et fiche, le patron
  du fonds). La page Annotation n'en garde qu'un lien, au responsable. Choisi par Hugo le
  2026-10-22, en revue de la maquette v3 d'`ANN-6` ; l'écran lui-même reste à maquetter avec
  le catalogue
- [x] **Désactiver une grille dans un projet ne supprime aucun relevé** — attendu : écrit.
  Ils restent, en lecture
  **Tranché par Hugo le 2026-10-22**, avec la case « Décocher »
- [ ] **Les relevés sortent avec leur grille et sa version** — attendu : cadré. Une lecture
  faite en v1 reste interprétable quand la grille en est à la v5 ; la grille sort dans un
  format standard (SKOS, comme le lexique aujourd'hui), et une grille venue d'ailleurs peut
  entrer au catalogue. Ce pan touche ce qui SORT : relecture croisée
- [x] **Qui voit le plan d'une grille réservée** — attendu : tranché. Une grille non partagée
  est un travail de recherche, et son seul plan peut révéler une étude en cours : la même
  question qu'aux termes d'une collection, un étage plus haut (`clause_terme`)
  **Tranché par Hugo le 2026-10-14** : quiconque lit un album du projet où la grille est active (`docs/grilles-et-releves.md`, §10). Être membre du projet n'est pas exigé, pas plus que pour annoter

### Un seul modèle : ce qui existe y entre

- [x] **Les trois vocabulaires d'aujourd'hui ont leur place de grille** — attendu : écrit.
  Les tags libres : une grille ouverte, de forme simple, sur la zone. La situation d'une
  case : une grille à variantes sur la case. Le profil d'un personnage : une grille à
  variantes sur le personnage. Le vocabulaire d'étude proposé dans `ANN-1` : une grille de
  plus. Le lexique situé (définition, note de portée, état) devient ce que porte une entrée
  **Tenu le 2026-10-22, avec deux précisions de la séance** : ces grilles naissent NEUVES, les
  termes d'aujourd'hui ne s'y convertissent pas (Q3) ; le profil vise l'ENTITÉ, la boîte
  personnage étant une autre cible (Q4)
- [ ] **Le coût de la réécriture est mesuré** — attendu : chaque lecteur des tags et des
  attributs relevé, avec un ordre de grandeur. Le coût n'est pas dans les données mais dans
  le code : Recherche et index plein texte, Exploration (distribution, croisement,
  concordance), exports (CSV, JSON, TEI, SKOS), lexique et import du tableur, annulation,
  cloisonnement des termes, registre des personnages. Une lecture du code, sans passe de
  tests
- [x] **Ce que la production porte déjà est compté** — attendu : nombres de tags, de tags
  posés, d'attributs et d'affectations, sur la production. Des utilisateurs en ont posé ; peu,
  sans doute. Commande à préparer pour Hugo, qui seul a la main sur le serveur
  **Mesuré par Hugo le 2026-10-21**, en lecture seule : cf. Contexte, « Mesuré en production ».
  Sans objet depuis Q3 : rien n'est converti
- [x] **Ce que les stagiaires poseront en attendant se convertit** — attendu : la règle est
  écrite avant leur premier jour. Ils commencent dans quelques semaines, sans doute avant le
  nouveau mode : ce qu'ils poseront sera des tags, à convertir au basculement (cf. `ANN-6`)
  **Tranché par Hugo le 2026-10-22 : il n'y a rien à convertir.** Ils ne posent aucun tag
  avant le basculement (Q9) ; la règle à leur donner est celle-là, avec le statut de relecture
  comme feu vert
- [x] **La réindexation plein texte se paie une fois** — attendu : tranché. L'index agrège
  les tags d'une région (`tags_concat`), et la limite écrite sous `AUTH-11` attend la
  prochaine migration forcée de l'index pour être reprise : le basculement en est une
  **Tranché par Hugo le 2026-10-22** : le basculement RETIRE `tags_concat` et ne met pas les
  relevés dans l'index — structurés et versionnés, ils y vieilliraient à chaque montée de
  version. Une seule réindexation complète, au basculement ; la Recherche gagne en tranche 4 un
  filtre « porte le relevé… », et le champ promet « dialogues, notes ». La limite d'`AUTH-11` se
  ferme avec lui
- [x] **Supprimer, fusionner, renommer un terme a sa règle dans le modèle** — attendu : écrit. Les
  tags libres reçoivent ces gestes AVANT les grilles, en mesure d'attente (`ANN-8`, Hugo,
  2026-10-22 : tag local, le propriétaire de la collection ; global, l'administrateur seul) ;
  le modèle dit ce qu'ils deviennent pour une entrée de grille, versionnée et partagée
  **Tranché par Hugo le 2026-10-22.** Grille FERMÉE : seulement par une nouvelle version
  (tableur et bilan, note §6) — renommer garde la `cle`, fusionner reporte les relevés, une
  entrée employée devient « retirée » ; rien en place. Grille OUVERTE (les tags libres) : propre
  à son projet, sans version publiée, NON partageable tant qu'on ne la fige pas en grille
  fermée ; les gestes d'`ANN-8` s'y font en place, par les responsables du projet, journalisés.
  Dans les deux cas, Ctrl+Z désigne une entrée par sa `cle`, jamais par son libellé — la
  généralisation du correctif qui fait suivre à Ctrl+Z les renommages et les fusions de tags
- [x] **Une référence à une autre bulle se tient par l'outil** — attendu : tranché dans le
  modèle. Aujourd'hui, pour un chevauchement, la Note porte la référence de l'autre bulle écrite
  à la main ; dérivée de l'ordre de lecture, elle désignait une autre bulle dès qu'une case
  bougeait. Renvoi d'`ANN-8` (Hugo, 2026-10-21) : d'ici là le guide fait écrire l'identifiant
  stable « #123 », et un lien que l'outil tient vient avec les grilles
  **Tranché par Hugo le 2026-10-22** : un champ `lien` du relevé désigne la région ; si elle
  disparaît, le relevé passe « à revoir » (cf. « Tranché par Hugo — 2026-10-22 »)

### L'ordre

*La file des lots, tranchée par Hugo le 2026-10-21 : lot 1 (imports, copie de travail, sélecteur
de collection, petits et `ANN-8`) ; lot 2 le bac à sable SANS wizard (`COL-4` — la vague de
nouveaux comptes arrive avant les annotateurs) ; lot 3 la 3b de `COL-3` (E7, E8, droits
d'effacement) ; lot 4 le wizard (`UX-6`, dans le bac à sable) ; lot 5 : ce chantier, avec la
tranche 4 de `COL-3`, puis la page Annotation d'`ANN-6`. Les séances de conception commencent
dès le lot 1, en parallèle : le code attend son lot, pas la conception.*

- [x] **Sa place face à `ANN-6` et `COL-3` est décidée** — attendu : tranché par Hugo. Le
  relevé d'`ANN-6` se pose avec une entrée de grille, donc après le modèle ; le catalogue
  et le fonds de `COL-3` partagent le patron du pot commun, et gagnent à être conçus ensemble
  **Tranché par Hugo le 2026-10-14** : `COL-3` d'abord (fusion de sa tranche 1, puis sa tranche 2), puis le modèle des grilles, en quatre tranches (`docs/grilles-et-releves.md`, §1). Commits sur `dev`, sans push, chacun après revue
- [x] **La cible « planche » attend le modèle d'`IMG-2`, ou le tranche** — attendu : avant que la tranche 1 fige « la planche » comme cible d'une entrée, dit si c'est la PAGE (unité imprimée, numérotée, citée) ou la SURFACE (le repère où vivent les régions). Ouvert le 2026-10-16 : `docs/images-pages-surfaces.md` propose de séparer image, page et surface, que la planche confond aujourd'hui ; les régions changeraient alors de repère **Tranché par Hugo le 2026-10-16, dans `IMG-2` : la cible « planche » est la SURFACE** — pour une double page, la double page entière, que l'écran nomme « la planche (ou la double page) » ; une cible « page » viendra si une grille en a besoin
- [x] **La tranche 1 est codée et relue** — attendu : sur `dev`, suite verte, relue croisée parce qu'elle touche les droits. **Fait le 2026-10-26, `3dc6b48`** (sur `dev` local) : le cadrage `docs/ann7-tranche1-cadrage.md` codé, quatre tours de relecture, chaque garde éprouvée par mutant
- [ ] **La gestionnaire est responsable du projet de la grille des linguistes** — attendu : au
  déploiement de la tranche 1, dans « Qui y entre » du projet retenu (« Principal » ou
  « LingApp »), la gestionnaire figure avec le rôle « responsable » ; sinon seul un
  administrateur publie (Q9)

## Contexte

### La séance de conception — 2026-10-22

Une séance d'une heure et demie avec Hugo, sur le dossier ci-dessous, sans maquette (elle
viendra après, en session dédiée, avec ces décisions). Tout le dossier a été parcouru : Q1 à
Q9, le catalogue, le relevé, les copies en principe, les cases ouvertes du modèle. Chaque
décision est une case cochée de « Tranché par Hugo — 2026-10-22 » ou de sa zone d'origine.
Le dossier recommandait ; Hugo a suivi la recommandation partout, sauf trois fois, où elle a été
reprise avec lui : le catalogue en version ALLÉGÉE (proposer hors de l'outil, dériver par le
tableur, aucune demande de suppression), Q9 en (b) plutôt qu'en (c), le vocabulaire neuf
(Q3) l'ayant rendue nécessaire, et la passe commune avec la double annotation renvoyée aux
linguistes.

**Ce que la séance a changé au dossier** : le basculement ne convertit RIEN (Q3), ce qui fait
tomber la question de portée d'`AUTH-11`, la règle de conversion des stagiaires et la mesure de
la production ; le relevé a ses champs, et aucun `collection_id` ; la tranche 4 de `COL-3` perd
le vocabulaire et garde les personnages, dont la cible `entite` dépend.

**Ce qui reste ouvert ici** : les champs des objets de grille (à la migration de la tranche 1) ;
le coût de la réécriture, lu dans le code — moindre depuis Q3, les lecteurs à réécrire restant
les mêmes ; ce que les relevés deviennent à la SORTIE (tranche 4, relecture croisée) ; la note à
mettre à jour au premier commit ; la gestionnaire responsable du projet retenu.

**Aux linguistes**, à jour : occurrences ou bulles ; le compte d'un relevé à qualificatifs ; un
passage qui saute des mots ; compter par niveau et par famille ; la grille tient-elle dans les
trois formes, cardinalité comprise (colonne `cardinalite`) ; une ou deux grilles avec
`tools/vocabulaire-etude-propose.csv` ; la double annotation à l'aveugle (case d'`ANN-6`) ; les
« [exemple du corpus] » du guide, à désigner une fois les relevés posés. Le narrateur au
registre des personnages reste une question pour eux, avec Q4.

**À mesurer sans Hugo** : la durée d'une réindexation FTS complète sur la recette ; l'import de
la vraie grille (hors dépôt) dans les trois formes ; le coût de la réécriture.

### Préparer la séance de conception — relu le 2026-10-21

Relecture faite avant la première séance de conception avec Hugo (1 h 30), sur la fiche,
`docs/grilles-et-releves.md` et les fiches voisines, avec des vérifications dans le code de
`dev` (v33). Rien n'est tranché ici : ce sont les questions, et ce qui a vieilli.

**Vérifié dans le code** : aucun objet grille ni relevé n'existe ; `detail` n'est pas dans
`config.TYPES_REGION` ; `tags.label` est UNIQUE sur toute l'instance ; le vocabulaire ne porte
qu'un `collection_id`, aucun `projet_id` ; `personnages` n'a aucune portée ;
`database.creer_copie` recopie déjà tags, attributs de case, locuteurs et présences au cran
`annotations` ; `undo._ensure_tag` recrée un tag par son libellé. Lecteurs de code (et de
tests) par table à réécrire au basculement : `annotation_tags` 10 (21), `region_attribut` 10
dont `autorisation.py` (23), `attribut_valeur` 10 (33), `personnage_attribut` 7 (10).

**Ce qui a vieilli depuis le 2026-10-14**
- *L'activation sur le projet* : le projet ouvre désormais sa collection de base (D10, v31)
  et l'Atelier choisit une collection avant l'album (`UX-19`) ;
  `docs/collections-niveau-ou-calque.md` rouvre l'activation par collection. Il faut dire ce
  qui STOCKE (le projet) et ce qui FILTRE (la collection), et qu'un relevé ne porte aucun
  `collection_id`.
- *`COL-3`, tranche 4, et cette fiche répondent à la même question* — le vocabulaire au niveau
  du projet — sans se citer. Et ni l'une ni l'autre ne dit ce que deviennent au basculement
  les termes GLOBAUX et ceux LOCAUX à une collection : convertir un terme local en grille de
  projet élargit sa visibilité, décision d'`AUTH-11` et non détail de migration.
- *Le personnage* : « un seul modèle » vise l'ENTITÉ (`personnage_attribut`), la note §4 la
  BOÎTE (ce personnage dans cette case) — deux cibles sous un mot. L'entité n'a ni album ni
  portée, et suit les copies entre projets (E6 de la 3b).
- *Les copies sœurs* (`COL-3`, 3b, E1 à E8) ignorent les relevés : leur cran (et la zone
  `detail`, une région, donc partie avec le cran `decoupage`), l'équivalent d'E5 pour une
  grille non active à l'arrivée, l'effacement d'E8, et surtout la règle « travail d'autrui » :
  des actes sur les relevés journalisés hors de `_CIBLES_DE_REGION` laisseraient supprimer
  seul un album annoté par d'autres — un défaut qui échoue OUVERT. `region_origine` permettra
  en revanche de comparer les relevés de deux sœurs.
- *La cible « planche » et l'assemblage* (`IMG-2`, une page par image depuis le 2026-10-21) :
  assemblée, une planche « cesse d'être une planche » ; son relevé changerait de sens ou
  disparaîtrait par `CASCADE`. Fusionner deux régions doit fusionner leurs relevés.
- *Le catalogue face au fonds* : le fonds de la 3a se DEMANDE, le catalogue se publie et
  s'active librement ; l'asymétrie est à vouloir et à écrire (case ouverte de `COL-3`).
- *La portée des termes* : le basculement est la « prochaine migration FTS forcée » qu'attend
  `AUTH-11` pour retirer `tags_concat`, à décider dans la même migration ; il peut fermer
  « taper un tag caché l'attache » (`AUTH-11`) et l'unicité de `COL-1`. Et depuis D10, un
  membre d'une base OUVERTE « écrit quelque part » et édite le vocabulaire global : une grille
  fermée ne doit pas en hériter.
- *Les migrations* : la note §1 dit « la suivante » après la v30 ; v31 à v33 sont prises, et
  la v34 l'est par `IMG-1`. Deux règles nées depuis s'appliquent : `AUTOINCREMENT` sur toute
  table que le journal nomme, et la vraie base de la version précédente.
- *Qui publie en production* : « les responsables du projet » — or la migration du premier
  projet n'en a désigné AUCUN : seul un administrateur pourrait importer la grille des
  linguistes (question ouverte n°7 de la note).
- *Plusieurs personnes sur une planche* (`CONC-4`) : les relevés commutent comme des tags, mais
  une variante choisie, une passe, la levée d'un doute sont des valeurs uniques — le patron du
  409 de `CONC-3` ; une colonne de version ne coûte rien dès la tranche 1.
- *Mineur* : « une coquille se corrige à l'écran » est ouverte ici et acquise dans la note §6.

**À trancher AVANT de maquetter l'onglet Annotation (`ANN-6`, `UX-17`)** : la liste des cibles
(boîte ou entité pour le personnage ; planche ou page) ; les champs d'un relevé ; la
cardinalité ; la passe, commune ou par personne ; le doute ; l'activation et le filtre par
collection ; ce que l'écran fait des tags d'avant le basculement ; où vivent la synthèse et le
compte. **Peut attendre** : catalogue, partage, dérivation, montée de version, guide produit
depuis la grille, SKOS et exports, Recherche et Exploration, crans des copies (à écrire en
principe, à coder avec la 3b).

**Les questions pour Hugo, avec la recommandation de la relecture**
- Q1 — Où vit une grille : le projet seul ; le projet stocke et une collection RESTREINT
  l'affichage ; ou une activation par collection. *Recommandé : la deuxième*, le relevé sans
  collection.
- Q2 — Les grilles sont-elles « le vocabulaire au niveau du projet » de la tranche 4 de
  `COL-3` ? *Recommandé : oui*, la tranche 4 ne garde que personnages, Recherche et
  Exploration — sinon le vocabulaire migre deux fois.
- Q3 — *Simplifiée par Hugo le 2026-10-21 : le corpus annoté en production est un corpus de
  TEST, et rien de ce qu'on y supprime ou modifie n'a de conséquence. Le basculement peut donc
  partir d'un vocabulaire neuf, sans conversion, et couper les Ctrl+Z d'avant lui ; la
  question ci-dessous ne vaut plus que si l'on VEUT garder ces termes.*
  Le sort des termes existants : une grille par projet pour les termes globaux qu'il
  emploie, dérivées d'une origine commune ; une grille d'instance unique ; les termes locaux
  en grille distincte. *Recommandé : la première et la troisième*, en acceptant par écrit que
  les termes locaux deviennent visibles du projet entier (ou en les comptant d'abord).
- Q4 — Le personnage : deux cibles (la boîte et l'entité) ou la boîte seule. *Recommandé :
  deux*, l'entité rattachée au projet de la grille, séquencé avec la tranche 4.
- Q5 — Une cible « planche » face à l'assemblage : la cible « page » dès la tranche 1 ; la
  planche reste la surface et l'assemblage reporte les relevés avec une trace ; interdire
  d'assembler une planche qui en porte. *Recommandé : la deuxième*, avec un refus nommé tant
  qu'`IMG-2` n'existe pas.
- Q6 — La cardinalité : chaque entrée déclare « une fois par cible » ou « plusieurs », ou
  toujours plusieurs. *Recommandé : déclarée dans le tableur.*
- Q7 — La passe à plusieurs : une par personne, ou commune et signée. *Recommandé : commune*,
  avec le 409 sur les valeurs uniques dès la tranche 1 (la réponse à `CONC-4`).
  *Renvoi posé le 2026-10-21 : `CONC-4` a RENVOYÉ ici les attributs de case à plusieurs —
  le refus sur valeur périmée des attributs se fait avec les grilles, pas avant.*
- Q8 — Le catalogue : « partager = publier, activation libre », ou activer se demande.
  *Recommandé : libre*, le fonds prêtant son patron d'écran et la demande pour la seule
  suppression.
- Q9 — L'ordre : nommer un responsable du projet existant pour publier la grille des
  linguistes ; les stagiaires commencent par découpage, transcription et locuteurs (option (c)
  d'`ANN-6`) ; les tags basculent avec la page Annotation, pas avant.

**Aux linguistes** : occurrences ou bulles ; un relevé à qualificatifs compte-t-il une fois ;
un passage peut-il sauter des mots ; le narrateur au registre des personnages ; compter par
niveau et par famille ; la grille tient-elle dans les trois formes ; une ou deux grilles avec
`tools/vocabulaire-etude-propose.csv` (`ANN-1`). **À mesurer sans Hugo** : en production, le
nombre de tags, d'attributs, de termes locaux, et les responsables des projets ; la durée
d'une réindexation FTS complète sur la recette ; l'import de la vraie grille (hors dépôt) dans
les trois formes ; la cible des actes sur les relevés au journal.

**Mesuré en production le 2026-10-21** (Hugo, lecture seule, `mode=ro`) : 13 tags dont 6
locaux à une collection, posés 31 fois ; 4 dimensions (2 locales) et 10 valeurs (8 locales),
aucun domaine ; 11 attributs posés sur des cases, 3 sur des personnages ; 5 personnages,
16 locuteurs, aucune présence ; 3 projets, 2 responsables, 7 membres ; 14 albums, 866
planches, 330 régions. Le basculement ne coûte donc presque rien en DONNÉES — le coût est dans
les lecteurs de code — ; Q3 porte sur 16 termes locaux, qu'on peut relire un par un au lieu de
trancher par principe ; et l'annotation n'a presque pas commencé : chaque semaine d'attente
ajoute à convertir. Q9 est à moitié réglée : des responsables existent, reste à vérifier que
le projet de la grille des linguistes en a un.

**Ordre du jour proposé** : 10 min de rappel et un schéma des étages (fonds, projet, base et
collections, copies sœurs ; image, page, surface ; grille, version, relevé) ; 25 min « où vit
une grille » (Q1, Q2, Q3, Q8) ; 25 min « ce qu'est un relevé » (Q4 à Q7) ; 15 min copies et
assemblage, en principe ; 10 min l'ordre et les stagiaires (Q9) ; 5 min la suite. À montrer :
la seconde maquette d'`ANN-6` (`https://claude.ai/artifact/97Xznyg2dqkQ7bX9EYwhkU`), trois
scénarios — un stagiaire et un professeur sur la même bulle ; une copie sœur partie au cran
annotations dans un projet où la grille n'est pas active ; une double page assemblée qui porte
un relevé « planche » —, et un extrait de grille FICTIVE au format du tableur (note §7).

**Ce qui coûterait cher à défaire** : une table de relevé sans `AUTOINCREMENT`, avec un
`collection_id`, ou en `CASCADE` sur la planche (une reconstruction de table, données posées) ;
payer la réindexation FTS deux fois ; la conversion du vocabulaire, irréversible pour la
portée, et les Ctrl+Z d'avant le basculement qui réécriraient dans les anciennes tables
(`undo._ensure_tag`) ; des relevés oubliés par la règle « travail d'autrui », les crans de
copie ou « repartir de zéro » (gardes qui échouent OUVERT) ; des `cle` absentes à la première
importation de la grille des linguistes — chaque renommage se lirait comme une suppression.

### D'où cela vient

Le 2026-10-13, une maquette du mode d'annotation faite depuis la session de pilotage n'a
pas convaincu Hugo (cf. `ANN-6`). En y repensant, il a posé la question de fond : la grille
des linguistes est un vocabulaire conçu en amont ; est-ce LE vocabulaire de l'outil, une
nomenclature partagée partout, un vocabulaire qu'on change, qu'on choisit à l'entrée d'un
projet ? Peut-on en ajouter un autre, d'un tout autre système ? Puis : ajouter un niveau,
des tags, en supprimer, sont des actions à penser en amont — et passent-elles par l'outil ou
par le tableur qu'on lui fait lire ?

La discussion a avancé par six réponses, dans l'ordre : agnostique ; un catalogue où l'on
entre par « Partager », versionné ; le tableur pour écrire ; les responsables publient,
l'administrateur trie après coup ; activation sur le projet ; un seul modèle.

### Ce que l'outil a, lu le 2026-10-14

Trois vocabulaires, câblés partout : les tags (un libellé libre, unique dans l'instance, à
plat), les attributs de situation (une case) et de profil (un personnage), rangés en domaine,
dimension et valeur. Tous portent une portée — globale, ou propre à une collection — et le
lexique situé : définition, note de portée, état. Un vocabulaire s'importe d'un tableur,
collection par collection, en préremplissant sans écraser. Il n'existe aucun objet
« grille » : une grille importée se dissout dans ce pot commun. Le projet, depuis `COL-3`,
se nomme et se règle, et ne porte aucun vocabulaire.

### Ce qui a été écarté, et pourquoi

Un vocabulaire unique pour l'instance : elle accueille plusieurs projets, qui n'annotent pas
avec la même grille. Un vocabulaire par collection : une étude couvre souvent plusieurs
collections, la grille y serait recopiée et les comptes ne s'additionneraient plus. Un
éditeur de grilles complet dans l'outil : un vrai chantier, et deux sources à tenir alignées
avec le guide. Des formes libres : ce serait un éditeur d'ontologies, sans fond. Suivre
automatiquement la dernière version d'une grille partagée : la crainte de Hugo, une lecture
changée sous les pieds d'une équipe.
