# ANN-7, tranche 2 — la page Annotation : cadrage

Rendu le 2026-10-27, sur `dev` à `f495305` (schéma **38** : la tranche 1 d'`ANN-7` et la 3c
de `COL-3` intégrées ; la 3c n'est pas en production). Rien n'est codé ni exécuté : c'est une
lecture. Ce qui est marqué **lu** a été lu dans le code à ce commit ou dans la source de la
maquette ; ce qui est marqué **hypothèse** ne l'a pas été, ou reste à mesurer, et dit ce qui
trancherait. Les questions qui restent à Hugo sont numérotées **H1 à H7**, en fin de note,
chacune avec une proposition et son coût.

La tranche 2 porte aussi `ANN-6` : la page Annotation est l'écran du relevé. Les décisions
qu'elle suit sont celles des deux fiches — `pilotage/ANN-6.md`, zones « Tranché par Hugo —
2026-10-14, le calibrage de l'outil d'annotation » et « Tranché par Hugo — 2026-10-22, sur la
maquette v3 » ; `pilotage/ANN-7.md`, zones « Tranché par Hugo — 2026-10-22, la séance de
conception » et « Tranché par Hugo — 2026-10-25 » — et la maquette v3 validée par les
linguistes le 2026-10-22 (page privée `https://claude.ai/artifact/3EXqt485Dv7SwwTRVogLuQ`,
source hors du dépôt). Cette note ne les rediscute pas : elle dit ce qu'elles demandent au
code, et ce que le serveur de la tranche 1 sert déjà. Quand la maquette et une décision
écrite divergent, c'est la décision qui est suivie, et l'écart est dit.

Le dépôt est public : la grille des linguistes n'est ni citée ni recopiée ici. La maquette la
contient ; ce qui en est dit ici porte sur des GESTES et des FORMES, avec des exemples
fictifs.

**Pourquoi maintenant** (Hugo, 2026-10-26) : la page passe AVANT le wizard (`UX-6`, dans le
bac à sable de `COL-4`), « pour que [le wizard] puisse intégrer la page annotation et non le
mode annotation déjà présent ». D'où deux exigences de cette note : un découpage qui donne
vite une page utilisable par les linguistes, et une réponse à ce que devient le mode
Annotation de l'Atelier (H2), sans la trancher à la place de Hugo.

---

## Ce que la tranche 2 livre, en gestes

Une sixième surface, `/annotation`, entre l'Atelier et la Bibliothèque. On y :

1. choisit une collection, un album, une planche du projet courant, puis une CASE sur la
   planche ; la case s'agrandit au centre, et l'on choisit DANS la case une bulle, un
   cartouche, un texte, une boîte personnage, ou le fond (la case elle-même) ;
2. choisit une grille parmi celles que le projet active et que la collection ne masque pas ;
   la lit (rubriques repliables, ligne du guide à hauteur fixe, guide complet), la filtre ;
3. désigne des mots de la zone (clic, glissé, Maj+clic, Ctrl+clic pour un passage à trou,
   clavier) ou choisit ce sur quoi le relevé porte (« Porte sur ») ;
4. pose un relevé des trois formes — simple, à variantes, à qualificatifs —, avec une
   précision ou un lien vers une autre bulle quand l'entrée les attend ; le retire ;
5. voit, en bas de la colonne de la grille, ce qui est posé sur les mots désignés ou sur la
   zone, et règle quelles grilles s'y affichent ;
6. doute d'un relevé, répond, lève le doute ;
7. marque la zone « terminée » pour la grille (ou une rubrique), et passe à la suivante ;
8. relit la planche entière dans la Synthèse (relevés par case, à revoir, décompte) ;
9. annule par Ctrl+Z ;
10. trace une zone dans la case — un détail d'image, ou un texte hors bulle à transcrire.

Ce que la tranche 2 ne livre pas est dit plus bas (« Hors tranche »).

---

## Ce qui existe déjà (lu)

### Le serveur de la tranche 1

Tout ce dont la page a besoin pour LIRE et pour POSER existe, dans `routes/grilles.py` et
`routes/releves.py`, et le cadrage de la tranche 1 l'avait écrit pour elle
(`docs/ann7-tranche1-cadrage.md`, section « R13 — Ce que la tranche 2 attendra des routes ») :

- `GET /api/projets/{id}/grilles` — les grilles ACTIVES du projet que l'appelant peut lire,
  leur version, ouvertes ou non, et `masquee_dans` (les collections lues qui les masquent) ;
  `gerable` pour le responsable.
- `GET /api/grilles/{id}/versions/{numero}` — le plan entier (`grilles.plan`) : rubriques
  avec parent et chemin, entrées avec leur cible et leur cardinalité EFFECTIVES (`cibles`,
  `pose` ∈ mots · zone · planche · entite, `cardinalite`), précision et lien attendus,
  variantes, listes de qualificatifs, définitions, structures, exemples (du texte), pièges.
- `GET /api/regions/{id}/mots` — le découpage de l'outil (`mots.decouper`) : `rang`,
  `forme`, `debut`, `fin`. Aucun jumeau navigateur (G11) : la page dessine depuis cette route.
- `GET /api/planches/{id}/releves` — tous les relevés de la planche (régions et surface),
  avec passage, qualificatifs, lien (et le texte d'une région liée perdue), état DÉRIVÉ et
  ses causes (`mot_perdu`, `texte_change`, `lien_perdu`, `type_change`, `entree_absente`,
  `precision_manquante`, `lien_manquant`), auteur et nom lisible, `collectif`, `recopie`,
  `modifiable`, le doute OUVERT et son fil ; et les passes de la planche, signées.
- `POST /api/releves` (avec `nouvelle_entree` pour une grille ouverte : « Créer « … » »),
  `PUT /api/releves/{id}` avec `vu` (variante, qualificatifs, précision, lien, passage),
  `DELETE /api/releves/{id}` ; `POST /api/releves/{id}/doutes`, `POST
  /api/doutes/{id}/messages`, `POST /api/doutes/{id}/levee` avec `vu` ; `PUT` / `DELETE`
  des passes sur une région ou une planche, avec `vu`.
- Les refus nommés que l'écran affiche sans rien deviner : 409 de la cardinalité (avec
  `releve_existant`), 409 de CONC-3 au format `Perime.detail()`, 409 « grille pas active »,
  409 « votre écran montre la version n, rechargez », 422 de forme et de cible.
- Ctrl+Z des relevés (`undo.py`) : poser, modifier, retirer, avec les gardes d'AUTH-14, le
  cinquième témoin de la 3b et le 409 « Passer ce geste » ; la suppression d'une région rend
  ses relevés (`releves_non_rendus` sinon).

### Ce que la page réemploie ailleurs

- Les régions et leurs citations : `GET /api/planches/{id}/regions` (`r.*`, donc
  `regions.nom` depuis la v37, et `citation`). Le locuteur et le personnage montré se lisent
  par région (`GET /api/regions/{id}/locuteur`, `…/personnage`) ; la note par
  `GET /api/regions/{id}/annotation`, et s'écrit par `PUT` avec `note_vue` sans toucher aux
  tags (CONC-3, « un champ ABSENT n'est pas touché »).
- Les listes du projet courant : `GET /api/projets`, `GET /api/collections`, `GET
  /api/albums` (`collections`, `ecrivable`), `GET /api/albums/{id}/planches`
  (`relecture_statut` : le feu vert des relevés, Q9).
- Les modules de `static/lib/` : `common.js`, `projet.js` (le projet courant,
  `BDProjet.basculeVers`), `atelier.js` (le filtre de collection d'UX-19), `nav.js`,
  `dialog.js`, `conflit.js` (`BDConflit` : les mots du bandeau de CONC-3),
  `signal-planche.js` (« ⟳ Actualiser » de CONC-4), `bac-a-sable.js` ; `theme.js` pour la
  bande du haut, la nav, les thèmes, le zoom.
- Le dérivé web de chaque planche : au moins 1 600 px de large (IMG-1, plancher du
  2026-10-24) — de quoi agrandir une case sans aller chercher la copie de travail
  (hypothèse de netteté : une case d'un sixième de planche fait ~500 px dans le dérivé, pour
  une boîte de ~44 % de la hauteur d'écran ; à regarder sur une vraie planche au commit 1).

### Le mode Annotation de l'Atelier, aujourd'hui (lu)

`templates/index.html`, `#panel-annotation`, et `static/viewer.js` (`loadAnnotation`,
`chargerBlocsDuType`) : le locuteur d'une zone de texte (avec son profil et ses
alignements), l'identité d'une boîte personnage (avec son profil et ses alignements), la
situation d'une case (« dimension : valeur »), les tags, la note. Trois de ces blocs sont le
vocabulaire que la tranche 3 retire sans conversion (tags, situation, profil, Q3) ; les trois
autres ne sont pas du vocabulaire (locuteur, identité d'une boîte, note) — ce sont, sur la
page Annotation, le « Contexte » de la colonne de gauche (ANN-6, « Le Contexte ne garde que
ce qui n'est pas du vocabulaire »).

### Ce que la 3c de `COL-3` change pour la page (lu dans `docs/col3-tranche3c-cadrage.md`)

- **Le responsable LIT toutes les collections de son projet** (F1) : il ouvrira la page sur
  des albums qu'il lit sans y écrire. Le serveur le dit déjà relevé par relevé
  (`modifiable` : la grille active dans la version du relevé ET l'album écrit) ; la page
  n'offre alors aucun geste. Rien à ajouter.
- **On n'entre dans une collection que si l'on est du projet** (F2, voie 2) : tout
  annotateur sera membre du projet, donc lit le plan des grilles par la moitié (a) de
  `clause_grille` ; la moitié (b) reste juste et ne coûte rien.
- **« Travail d'autrui » ne décide plus rien, il montre « qui perd quoi »** (F3) : les
  relevés y comptent ; la page n'efface ni album ni planche, elle n'a rien à faire de plus.
- **Les lecteurs voient les auteurs et le fil des doutes** (Hugo, 2026-10-26, « des lecteurs
  peuvent être des spécialistes, qui arpentent le corpus ») : la page montre auteurs et fils
  à quiconque LIT l'album, gestes en moins.

---

## La maquette v3, geste par geste

Pour chaque geste : ce que la v3 fait jouer (lu dans sa source), ce que le serveur sert, ce
qui lui manque, ce qui est purement écran. « Écran » veut dire : aucune route neuve ;
« logique » : une règle pure, à écrire dans `static/lib/` et à tester sous Node.

| Geste de la maquette | Ce que le serveur sert | Ce qui manque au serveur | Ce qui est écran |
|---|---|---|---|
| En-tête : Collection (infobulle « masque n grilles »), Album, Planche, « Préparée : n zones de texte, transcription relue », « Ouvrir dans l'Atelier ↗ » | les listes du projet courant ; `masquee_dans` ; `relecture_statut` | — | le filtre d'UX-19 réemployé (`lib/atelier.js`) ; le lien croisé |
| Colonne gauche « Planche » : la minicarte ne sert qu'à choisir une CASE ; marques « case en cours », « terminée » (pour la grille active), « doute ouvert » | régions ; passes et doutes ouverts dans `…/releves` | — | logique : quelles zones sont « terminées » pour la grille et la rubrique affichées |
| Contexte : locuteur (un lien au registre), note, nom d'un détail ; « Supprimer cette zone » sur une zone tracée ici | les routes du locuteur, de l'annotation (`note_vue`), `PUT /api/regions/{id}` | `regions.nom` ne s'écrit par aucune route (lu : ni `RegionIn`, ni le `PUT`) | le champ du locuteur de l'Atelier (typeahead, homonymes, d957a70) vit dans `viewer.js` : le réemployer demande de le sortir dans `static/lib/` |
| Centre : la case agrandie dans une boîte de hauteur constante ; fond = la case, clic = une zone ; noms des personnages et des détails écrits sur l'image, à ~12 px d'écran quelle que soit la case | régions ; le personnage d'une boîte par région | — (la page lit le personnage des boîtes de la case COURANTE, une requête par boîte ; hypothèse : 2 à 6 par case) | le recadrage du dérivé, les étiquettes à taille d'écran constante |
| En-tête de zone : « Case cN », la zone, « zone i / n de « grille » », « À revoir n » | — | — | logique : le PARCOURS (ci-dessous) |
| « Porte sur » : des mots de la bulle, toute la bulle, la case, une boîte personnage, un détail, la planche — ce que la grille active vise depuis la zone choisie | `cibles` et `pose` de chaque entrée, `porte_sur` de la version | — | logique : les options depuis les cibles et la zone. **La maquette offre aussi « X, partout » (l'entité) : refusé par le serveur jusqu'à l'étage de projet des personnages (G3) — la page ne l'offre pas** |
| Mots : clic, glissé, Maj+clic (passage continu), Ctrl+clic (un mot ajouté ou retiré : « ne … pas »), clavier (flèches, Maj+flèches, Espace, Entrée → filtre, Échap) ; au doigt, « Étendre » et « Ajouter un mot » | `GET /api/regions/{id}/mots` ; `mots` (les rangs) du `POST` / `PUT` | — | la sélection ; **pendant un glissé, ne rien redessiner sous le pointeur** (cf. Performance) |
| Traits sous les mots : un couloir par relevé, la teinte de sa rubrique pour la grille active, les autres en gris ; légende ; passage à trou sans trait sous les mots sautés | les passages | — | logique : les couloirs ; la teinte par rubrique (rang de la rubrique de tête, une palette de jetons) |
| Grille : onglets des grilles actives non masquées (version et note en infobulle, ✓ si terminée, nombre dans la zone) ; « Gérer les grilles ↗ » au responsable | `GET /api/projets/{id}/grilles` (`gerable`) | — | cf. « Gérer les grilles ↗ » plus bas |
| « Afficher : toute la grille / une rubrique » ; rubriques repliables (« n ici ») ; entrée simple = case à cocher, à variantes = « une parmi », à qualificatifs = le phénomène puis un ou plusieurs choix ; pastille « plusieurs » sur une cible entière ; marque d'une cible propre (« toute la zone », « la case ») | le plan | — | logique : compter « ici » ; quand marquer « plusieurs » (Q6 tranchée sur la v3) |
| Filtre : accents, apostrophes droites ou typographiques, exemples compris ; « X par Y » pour un phénomène et un qualificatif ; Entrée pose le premier résultat, ↓ ↑, Échap ; « Aussi dans : autre grille (n) » ; dans une grille ouverte, « Créer « … » » | le plan ; `nouvelle_entree` | — | logique : la recherche (normalisation, score, « par ») |
| Ligne du guide à hauteur fixe : définition, structure, exemples, piège ; « Guide complet ▸ » produit depuis la grille | le plan | — (« Dans le corpus », l'exemple qui renvoie à un relevé, n'est pas servi : `grille_exemple.releve_id` n'est rempli par rien) | le dialogue du guide ; « Dans le corpus » hors tranche |
| Poser, retirer : cocher pose, recocher sur le même passage retire ; une autre variante remplace ; un qualificatif s'ajoute ou s'ôte | `POST`, `PUT` (`vu`), `DELETE` | **`DELETE /api/releves/{id}` ne prend pas `vu`** (lu) : la v3 fait ouvrir le bandeau de conflit au RETRAIT d'une variante qu'un autre a changée ; sans `vu`, le retrait écrase en silence | les messages, l'annonce pour lecteur d'écran |
| Cardinalité : une entrée `une` déjà posée sur la cible | 409 avec `releve_existant` | — | le bandeau : « Remplacer par la mienne » = `PUT` de CE relevé avec `vu` |
| Conflit sur une valeur unique, à la place de la ligne du guide, sans changer la hauteur de la colonne ; une écriture identique passe | 409 `Perime.detail()` ; `conflit.verifier` laisse passer l'identique | — | `BDConflit` réemployé |
| Liste de ce qui est posé, en bas de la colonne de la grille : sur les mots désignés, sinon sur toute la zone ; un clic désigne exactement le passage et bascule sur sa grille ; « ? » et « ✕ » par ligne, absents d'un relevé en lecture | `…/releves` (`modifiable`) | — | — |
| « Relevés : Oralité ▾ » : par défaut la grille active seule ; des cases par grille (« masquée ici »), « Toutes », « … seule » ; retenu par personne et par projet, sur le poste | — | — | logique : le réglage retenu (stockage local sous try/catch, rangé par login, le patron de `bd-bacs-a-sable`) |
| Lien d'un chevauchement : « Désigner sur la planche », clic sur l'autre bulle ; « Changer » | `PUT` `lien_region_id` avec `vu` ; 404 hors de l'album (G4) | — | — |
| Pied à deux lignes fixes : « Grille : à faire » ou « ✓ Grille : terminée · Nom » et « Rouvrir » ; « Parcours : toutes les zones / à faire seulement » ; « ‹ Précédente », « Suivante › », « Terminée, suivante › » ; Ctrl+Entrée, Ctrl+Maj+Entrée | `PUT` / `DELETE` des passes (`rubrique_cle`, `vu`) | — | logique : le parcours ; « terminée » pour toute la grille = la passe `''` OU toutes les rubriques de tête |
| Doute : « ? » ouvre le formulaire dans la boîte du guide (commentaire obligatoire) ; un second « ? » ajoute au fil | `POST …/doutes` | — | — |
| Synthèse › À revoir : doutes ouverts, à revoir (avec ce que le relevé désignait), à compléter, **doutes levés** ; répondre ; lever en gardant, en changeant (« Changer… » : choisir l'entrée qui remplace, sur le même passage), en retirant ; « Rattacher aux mots désignés » ; la précision attendue, éditable sur la ligne | `…/messages`, `…/levee` (`garde` · `change` · `retire`) ; `PUT` `mots`, `precision` | **les doutes LEVÉS ne sont pas servis** (lu : `doute_ouvert` ne rend que l'ouvert) ; **« Changer » vers une AUTRE entrée** n'a pas de route atomique (H5) | logique : les causes en mots |
| Synthèse › Relevés : toute la planche par case dans l'ordre de lecture (« Case c3 · 9 »), puis la planche ; la case en cours marquée ; un clic ouvre le relevé | `…/releves` | — | logique : ranger par case et par ordre de lecture |
| Synthèse › Décompte : cette zone et son contexte, ou toute la planche ; par grille, rubrique, entrée, variante, qualificatif ; « zones terminées n / N » ; « Aperçu de l'Exploration ↗ » | `…/releves`, le plan | — | logique : compter (un relevé à qualificatifs compte UNE fois son phénomène, et une fois chacun de ses qualificatifs) ; l'aperçu de l'Exploration, H6 |
| Barre d'état : régions, relevés, zones terminées, doutes ouverts, légende | — | — | — |
| Tracer une zone : glisser dans la case (ou « Tracer une zone » au doigt), puis « Détail d'image » ou « Texte hors bulle » ; un détail se nomme ; un texte se transcrit puis s'annote | `POST /api/planches/{id}/regions` (type `texte`, parent la case) ; `PUT /api/regions/{id}` (`ocr_texte`, `vu`) | **le type `detail`** n'est pas dans `config.TYPES_REGION` (lu), `nom` ne s'écrit pas, et la région `detail` doit rester HORS des exports jusqu'à la tranche 4 (G17) | le tracé ; « une zone tracée ici n'est jamais une case » |
| Masque par collection : onglets cachés ; relevés des grilles masquées en gris, sans geste | `masquee_dans` | — | — |
| Tablette et téléphone : « Étendre », « Ajouter un mot », « Tracer une zone » ; la grille monte du bas par « Poser… ▴ » ; la planche en tiroir | — | — | à jouer sur un vrai appareil (case ouverte d'`ANN-6`) |
| Bande de maquette : « l'autre change une variante », « on corrige une transcription », « on supprime une bulle liée » | le 409 de CONC-3 ; l'état dérivé (`mot_perdu`, `texte_change`, `lien_perdu`) ; Ctrl+Z | voir l'empreinte, plus bas | ce sont des SITUATIONS, que les tests e2e jouent à deux contextes |

**Ce que la maquette fait et que le code ne doit pas faire** (lu dans sa source) :

- **Le parcours y est écrit grille par grille, en dur** (une liste par identifiant de grille
  fictive). L'outil est agnostique : le parcours se DÉRIVE des cibles de la version et de
  ses entrées — `mots`, `bulle`, `cartouche`, `texte` → les zones de texte de ces types ;
  `case` → les cases ; `personnage` → les boîtes ; `detail` → les détails ; `planche` → la
  planche, une seule étape ; `entite` → rien. Dans l'ordre de lecture : chaque case, puis
  ses enfants dans leur `ordre`. Une grille qui vise la case ET des mots enchaîne la case,
  puis ses textes. Règle proposée, sans question : elle ne fait que généraliser la v3.
- **Elle redessine toute la page à chaque geste** (`rendre()`), et 61 fois par seconde
  pendant un glissé : c'est ce que la note retient (« ne rien redessiner sous le
  pointeur »).
- **Elle donne aux relevés une `version` de ligne** ; le serveur garde la VALEUR vue (G1) :
  la page envoie `vu`, jamais un numéro.
- **Elle ouvre le catalogue et active une grille** : retiré en séance (Hugo, 2026-10-22, « On
  n'active pas une grille depuis la page Annotation »). Il ne reste qu'un lien.

---

## La place de la page

- **Route et gabarit** : `GET /annotation` → `templates/annotation.html`, script de surface
  `static/annotation.js`. Dans la nav (`theme.js`, `SURFACES`), entre l'Atelier et la
  Bibliothèque, groupe « atelier » (Hugo, 2026-10-14 : « une page Annotation entre Atelier et
  Bibliothèque ») ; icône : celle de la maquette (🖍️).
- **Une sixième surface coûte des déclarations, et c'est voulu.** `tests/surfaces.py` fait
  déclarer chaque surface servie par chacun des modules d'audit (`SURFACES_AUDITEES` ou
  `SURFACES_HORS_PERIMETRE` avec sa raison) : une quarantaine de fichiers `test_e2e_*.py`
  (lu, par leurs déclarations), plus `test_csp.SURFACES_HTML`, la liste des scripts de
  `test_api`, les surfaces de la bande du projet et du bac à sable (les cinq gabarits
  chargent `static/bac-a-sable.js` : ils deviennent six), et le texte de `CLAUDE.md` qui dit
  « cinq surfaces » à plusieurs endroits. Compté dans le commit 1.
- **Le projet courant borne la page**, comme la Bibliothèque et l'Atelier : ses listes sont
  celles du projet courant ; un lien vers un album d'un autre projet qu'on lit fait basculer
  (`BDProjet.basculeVers`).
- **Collection, album, planche** : le filtre de collection d'UX-19 (`lib/atelier.js`) est
  réemployé tel quel — la base par défaut, « Toutes les collections du projet », le choix
  retenu par projet. Proposé : le même choix que l'Atelier (la clé `bd-atelier-collection`),
  parce qu'on passe de l'un à l'autre sur la même planche ; « Ouvrir dans l'Atelier ↗ » et
  son retour portent de toute façon `collection` dans l'adresse. Se change en une ligne si
  l'usage demande deux choix.
- **L'adresse** : `?album=<id>&planche=<id>&region=<id>&grille=<id>` (et `collection`),
  la forme de l'Atelier (`album`, `planche`, `region`), plus la grille. L'adresse l'emporte
  sur la mémoire de session (`lib/nav.js`, INFRA-5). Les liens croisés : « Ouvrir dans
  l'Atelier ↗ » depuis la page (la zone courante), « Annoter ↗ » depuis l'Atelier (H2).
- **« Gérer les grilles ↗ »** : la v3 l'offre au responsable, vers la fiche du projet
  (Administration › Projets). Aujourd'hui cette fiche n'a aucune section des grilles (elle
  attend sa maquette, avec le catalogue). Proposé : le lien n'apparaît que le jour où la
  fiche les porte ; d'ici là, activer passe par l'outil en ligne de commande (H3).
- **Disposition** : trois colonnes (planche et Synthèse · case · grille), une boîte de case de
  hauteur constante, des pieds et une ligne du guide de hauteur fixe — « moins on change la
  disposition et les tailles au cours de l'annotation, mieux c'est » (Hugo, 2026-10-14). Deux
  colonnes et la planche en tiroir sous 75em ; une colonne et la grille « Poser… ▴ » sous
  47,5em (les seuils de la v3 ; à mesurer à 320 px et à grande police).

## Le module : une page, et sa logique en bibliothèque

Hugo l'avait voulu « monté dans l'Atelier ET sur une page à part », puis : « il vaut mieux
partir sur une page annotation », le module « restant montable dans l'Atelier si l'usage le
demande, comme second montage » (ANN-6, 2026-10-14).

**Proposé : une surface ordinaire, `static/annotation.js`, et sa logique pure dans
`static/lib/`** — pas un module MONTABLE au sens de `qui-entre.js` tant qu'il n'a qu'un hôte
(H7). La convention montable sert un second public par un second montage ; aujourd'hui il n'y
en a pas, et le wizard, tel que `COL-4` l'a posé, MÈNE à une surface (« après le clic,
l'Atelier sur la planche du parcours ») plutôt qu'il ne l'embarque. Ses cinq règles (aucun
accès au document au chargement, identifiants propres au montage, messages dans sa ligne,
routes à lui, options de l'hôte) et son cliquet coûteraient ~1 à 1½ jour sans servir
personne. Ce qui garde la porte ouverte : la logique est déjà hors de la page, et la page
n'a qu'un point d'entrée qui reçoit sa racine.

**La logique pure** — un module UMD `static/lib/annotation.js` (`BDAnnotation`), testé sous
Node (`tests/js/annotation.test.js`), et non plusieurs : elle forme un tout, et elle y entre
pour sa PROPRIÉTÉ (vérifiable par table de vérité), comme le dit `CLAUDE.md` :

- la recherche dans la grille (normalisation des accents et des apostrophes, exemples
  compris, score, « X par Y », « Créer « … » » dans une grille ouverte) ;
- les options de « Porte sur » depuis les cibles de l'entrée et la zone choisie, et la cible
  qu'un geste pose (une entrée à cible propre se pose d'elle-même sur elle) ;
- le parcours (cibles → zones, ordre de lecture) et « à faire seulement » ;
- « terminée » pour toute la grille ou une rubrique ;
- les couloirs des traits sous les mots, et le texte d'un passage à trou (« ne … pas ») ;
- le libellé d'un relevé (entrée, variante, qualificatifs, précision) ;
- les causes de l'état en mots, et le rangement de la Synthèse (par case, ordre de lecture) ;
- le décompte ;
- quand marquer « plusieurs » ;
- le réglage « Relevés : ▾ », lu et retenu sous try/catch, rangé par login et par projet ;
- la teinte d'une rubrique (rang de la rubrique de tête dans une palette de jetons).

Ctrl+Z demande une seconde extraction, dite plus bas.

---

## Concurrence (CONC-3, CONC-4)

**Chaque écriture d'une valeur unique porte `vu`, toujours** — la page est l'écran de tous
les jours de plusieurs personnes sur les mêmes planches (« on se partage les zones », Q7) :

| Geste | Route | `vu` |
|---|---|---|
| changer une variante, des qualificatifs (UN ensemble), une précision, un lien, un passage | `PUT /api/releves/{id}` | la valeur affichée de chaque champ envoyé |
| retirer un relevé | `DELETE /api/releves/{id}` | **à ajouter au serveur** (cf. tableau) : la valeur que l'écran montrait |
| lever un doute | `POST /api/doutes/{id}/levee` | `{"doute": "ouvert"}` |
| marquer « terminée », rouvrir | `PUT` / `DELETE …/passes/{grille}` | `{"passe": false}` / `vu_marquee=true` |
| la note de la zone | `PUT /api/regions/{id}/annotation` | `note_vue` |
| le locuteur | `PUT` / `DELETE /api/regions/{id}/locuteur` | `personnage_vu` |
| le texte d'une zone tracée ici | `PUT /api/regions/{id}` | `vu` |

- **Le 409 s'affiche à la place de la ligne du guide**, sans changer la hauteur de la colonne
  (ANN-6, 2026-10-22) : ce qui n'est pas enregistré, la version de l'autre, « Remplacer par la
  mienne », « Garder l'autre ». Les mots sont ceux de `BDConflit`. Tant qu'il est ouvert, un
  autre geste d'écriture le désigne au lieu de partir (le patron de `conflitBloque` de
  l'Atelier).
- **La cardinalité** reçoit le même bandeau ; « Remplacer par la mienne » est un `PUT` du
  relevé existant, avec `vu` égal à ce qu'il porte.
- **Poser ne se garde pas** : deux relevés `plusieurs` identiques sur le même passage sont
  possibles si deux personnes posent sans se voir. C'est le modèle (« plusieurs par zone, le
  même deux fois ») ; la liste les montre tous deux, et l'Actualiser ci-dessous réduit la
  fenêtre.
- **« ⟳ Actualiser »** (CONC-4 : ni temps réel ni rien, un signal). L'empreinte d'une
  planche (`empreinte.py`) ne couvre aujourd'hui que ce que l'Atelier montre (lu : type,
  géométrie, texte, note, tags, locuteur, personnage, situation) — **ni relevés, ni passes,
  ni doutes**. La page la demanderait toutes les trente secondes et au retour sur l'onglet,
  comme l'Atelier, si l'empreinte les compte (par région, et une clé pour la surface) ;
  `signal-planche.js` apprend les routes des relevés pour ne pas signaler ses propres
  écritures (la réponse porte `region_id` ou `planche_id`). Actualiser passe par les gardes
  d'un changement de planche : une saisie en cours (un doute à moitié écrit) ne se perd pas.
- **Un relevé retiré ailleurs** : `PUT` et `DELETE` reçoivent 404 ; la page le dit (« retiré
  depuis par un autre écran ») et l'ôte de la liste, sans rien relancer.

## Ctrl+Z

Le serveur tient tout (tranche 1). Ce qui reste à l'écran :

- **L'annulation est celle de l'AGENT, pas de la page** : le dernier geste annulable peut
  avoir été fait dans l'Atelier, sur une autre planche. La page fait ce que fait l'Atelier
  (`undoLast`, lu) : elle dit « Annulé : … », relit relevés et régions si l'acte touche la
  planche ouverte, sinon ouvre la planche touchée si elle est de l'album, et offre « Passer ce
  geste » sur le 409 de CONC-3. Elle compte aussi `releves_non_rendus`.
- **Proposé : sortir la partie commune de `viewer.js`** — l'appel, le message lent du premier
  appel (9 à 17 s, ANN-8), le 409 « Passer ce geste », les comptes non rendus — dans un
  module de `static/lib/` lu par les deux surfaces. Sinon c'est la duplication que
  `common.js` a fermée (« Ne pas redupliquer ces helpers dans un fichier de surface »). Le
  rafraîchissement reste à chaque surface.
- Dans un champ de saisie, Ctrl+Z reste l'annulation native.

---

## Accessibilité

- **axe-core** (WCAG 2.1 AA) sur la page, thèmes sombre et clair (`test_e2e_a11y`), avec un
  décor qui porte des relevés des trois formes, un doute ouvert, une grille masquée, un
  conflit ouvert — sinon l'audit approuve une page vide (la leçon de `2ab7911` : le décor
  n'avait ni locuteur ni boîte personnage).
- **Clavier** : tout geste a son chemin. Les mots en `listbox` multisélection
  (`aria-activedescendant`, flèches, Maj+flèches, Espace, Entrée vers le filtre, Échap) ; les
  entrées en `checkbox` ou `aria-pressed` ; « / » pour le filtre, Entrée pose le premier
  résultat ; Ctrl+Entrée, Ctrl+Maj+Entrée ; onglets en `tablist` ; dialogues par `BDDialog`.
  Chaque pose, retrait, passe et conflit s'annonce dans la région d'annonce de la page.
- **Contraste** : les TRAITS sous les mots sont des marques graphiques (3:1 contre le fond) et
  la couleur n'y porte jamais l'information seule (légende, liste, infobulle — ANN-6) ; le
  texte coloré (états, « ? » ambre, « ✕ » rouge) prend les encres AA (`--ink-*`), jamais
  l'accent brut. axe ne mesure pas un trait de 3 px dans un `<i>` : un test calcule le
  contraste de chaque teinte de la palette contre le fond des mots, dans les quatre thèmes
  (le patron du test de la rayure du bac à sable).
- **Reflow à 320 px et grande police** (`test_e2e_reflow`, `test_e2e_zoom_interface`) : la
  disposition à une colonne doit tenir dès le commit 1, même si les gestes au doigt viennent
  plus tard — sans quoi la page entre dans l'audit en échouant.
- **Masquage** (`test_e2e_masquage`) : un état se cache par `hidden` ou par une classe que
  l'audit connaît ; la page en a beaucoup (tiroirs, popover des relevés, formulaire du doute).
- Les deux cases ouvertes d'`ANN-6` restent à l'usage : « ? » et « ✕ » colorés ne doivent pas
  passer pour des gestes obligatoires ; tablette et téléphone sur un vrai appareil.

## Performance

- **Pendant un glissé, ne rien redessiner sous le pointeur** (retenu de la maquette, qui le
  faisait 61 fois par seconde et y perdait le relâchement). Le glissé ne touche que la
  classe des mots (`.sel`) ; les traits, la liste et la grille se redessinent au relâchement.
  Le glissé se termine aussi quand le navigateur l'avale (bouton relâché hors de la fenêtre,
  `pointercancel`, `blur`) — la maquette l'a appris à ses dépens ; essayé aussi dans
  Firefox (`--browser firefox`, l'instrument installé le 2026-10-09).
- **Redessiner par partie, jamais la page** : une pose redessine les traits, la liste, les
  compteurs de la grille ; jamais l'image de la case.
- **Après une écriture, la page patche sa liste** avec la vue que la route rend (`POST` et
  `PUT` rendent le relevé entier), sans relire la planche.
- **Les plans** se lisent une fois par version et restent en mémoire de la page ; ceux des
  relevés d'une grille désactivée ou d'une autre version se lisent à la demande — ce qui
  demande à la vue d'un relevé le NUMÉRO de sa version (lu : elle ne rend que `version_id`,
  et la route du plan prend le numéro) : à ajouter.
- **`GET /api/planches/{id}/releves` fait plusieurs requêtes par relevé** (lu, `vues()` :
  passage, qualificatifs, doute, activation). Hypothèse : quelques dizaines de millisecondes
  pour cent relevés ; à mesurer au commit 3 sur une planche semée de 200 relevés, et à
  grouper côté serveur seulement si la mesure le demande.
- **L'image de la case** : le dérivé, recadré, déjà en cache pour la minicarte — pas
  `GET /api/regions/{id}/crop`, qui décode la copie de travail à chaque case (hypothèse :
  quelques centaines de millisecondes ; à n'employer que si le dérivé est flou à l'œil).

---

## Hors tranche

- **L'entité personnage** comme cible (« X, partout ») et la case ouverte d'`ANN-6` « atteint
  l'entité par les deux chemins de l'Atelier » : elles attendent l'étage de projet des
  personnages (tranche 4 de `COL-3`, Q4 et G3 d'`ANN-7`). La page n'offre pas la cible ;
  l'import l'accepte déjà.
- **Ce qui compte et ce qui sort** (tranche 4) : l'Exploration et l'aperçu que la v3 en
  montre, la Recherche (« porte le relevé… »), les exports, la voie du dépôt.
- **Le basculement** (tranche 3) : les tags, la situation et le profil deviennent des
  grilles neuves ; le sort définitif du mode Annotation de l'Atelier s'y règle (H2).
- **L'écran des grilles dans la fiche du projet** : importer avec son bilan à l'écran,
  publier, activer, masquer, partager, le catalogue — à maquetter avec le catalogue.
- **La montée de version** d'un projet, et « à compléter » par changement de forme.
- **« Dans le corpus »** (un exemple qui renvoie à un relevé) : aucune route ne le remplit.
- **Le gabarit de tableur** qui ne perd personne (case d'`ANN-7`).
- **La fusion de deux régions et l'assemblage d'une double page** (`IMG-2`) : sans geste, sans
  site.
- **Les relevés de référence du jeu** (G6) : cf. H4.

---

## Les tests et les passes à prévoir

- **Logique pure** : `tests/js/annotation.test.js`, une table par règle de la liste plus haut ;
  quelques mutants par règle (la recherche, le parcours, « terminée », les couloirs, le
  décompte).
- **Serveur** : chaque manque du tableau a son test et ses mutants — `vu` du retrait (périmé
  refusé, identique accepté, absent : le dernier gagne), le numéro de version dans la vue, les
  doutes levés (et le cliquet des sorties : un doute levé porte `leve_par`, un login),
  l'empreinte qui bouge sur un relevé d'un autre et pas sur le sien, `--activer` (H3). **Le
  type `detail`** est ce qui SORT : exclu de l'export JSON, du CSV, du TEI, du manifeste IIIF,
  des outils de sortie et de la voie du dépôt — un test le JOUE (le patron de
  `test_releves_sorties.py`), et c'est le seul commit qui demande une relecture croisée.
- **E2E** (marqueur `e2e`, verrou navigateur entre agents) : la page sous trois identités —
  un annotateur qui écrit, un lecteur (auteurs et fils visibles, aucun geste), un responsable
  qui lit sans écrire (3c) ; poser chacune des trois formes et les relire après
  rechargement ; un glissé (Chromium, et Firefox pour le relâchement) ; un passage à trou ;
  le bandeau à deux contextes sur une variante et sur un retrait ; la cardinalité ; « terminée,
  suivante » et « à faire seulement » ; Ctrl+Z d'une pose ; la collection qui masque ; le
  conflit qui ne change pas la hauteur de la colonne. Chaque montage se mesure sur la requête
  PARTIE, pas sur l'état final.
- **Les audits de surface** : axe sombre et clair, reflow à 320 px, grande police, contraste
  des traits dans les quatre thèmes, masquage, CSP (dans un vrai Chromium).
- **Les passes longues** : navigateur entier et suite dans l'image une fois par jalon, avant la
  fusion — l'image n'a pas la police du poste (DejaVu Sans), et une colonne à hauteur fixe y
  tombe plus vite qu'ailleurs.
- **Une passe de QA visuelle**, à écrire dans `pilotage/qa/` au premier jalon livré — pas
  maintenant —, découpée par parcours (poser, douter, parcourir, deux écrans), chaque case
  avec sa surface, son geste et son attendu, rendue sans être cochée.

---

## Le découpage

Trois jalons. Le premier est le plus petit chemin vers une page où les linguistes annotent ;
les deux suivants complètent la maquette. Estimations tests compris ; la passe entière d'un
jalon (navigateur et image) ajoute une demi-journée à chacun. Aucune migration : le schéma
38 suffit (lu : `regions.nom` existe, `detail` n'a pas de `CHECK` à lever, les doutes levés
sont déjà dans `doute`).

### Jalon 1 — une page où l'on annote (≈ 9 jours)

0. **Les manques du serveur pour le jalon 1** : `vu` sur `DELETE /api/releves/{id}` ; le
   numéro de version dans la vue d'un relevé ; `--activer` dans `tools/importer_grille.py`
   (H3). ½ jour.
1. **La page** : la route, le gabarit, la sixième surface (nav, CSP, déclarations des audits,
   bande du projet, script du bac à sable, `CLAUDE.md`), le projet courant, Collection · Album
   · Planche, l'adresse, la minicarte, la case agrandie (le dérivé), le choix d'une zone, le
   Contexte EN LECTURE (locuteur, note) avec « Ouvrir dans l'Atelier ↗ », la disposition
   stable et le reflow à 320 px. 2 jours.
2. **La grille, en lecture** : onglets (actives, masque), le plan (trois formes, rubriques
   repliables, « n ici »), « Afficher », le filtre, la ligne du guide à hauteur fixe, le guide
   complet ; la logique pure et ses tests. Utilisable aussitôt par un lecteur. 2 jours.
3. **Désigner et poser** : les mots (souris sans redessin, clavier), « Porte sur », poser et
   retirer les trois formes, la précision, le lien désigné sur la planche, « Créer « … » » dans
   une grille ouverte, la cardinalité et le bandeau de CONC-3 dans la boîte du guide, les
   traits en couloirs et leur légende, la liste de ce qui est posé et « Relevés : ▾ ».
   3 jours.
4. **Terminée, parcours, Ctrl+Z** : le pied à deux lignes, la passe sur la zone ou la
   rubrique, « Rouvrir », le parcours, « Précédente », « Suivante », « Terminée, suivante »,
   les raccourcis, les marques de la minicarte ; Ctrl+Z, la partie commune sortie de
   `viewer.js`. 1½ jour.

### Jalon 2 — le travail à plusieurs (≈ 3½ jours)

5. **Le doute et la Synthèse** : « ? » et son formulaire dans la boîte du guide ; « À revoir »
   (doutes ouverts et levés, à revoir et ce que le relevé désignait, « Rattacher aux mots
   désignés », à compléter et sa précision éditable) ; répondre ; lever en gardant, en
   changeant (H5), en retirant ; Synthèse › Relevés par case ; Décompte (H6). Serveur : les
   doutes levés dans `GET /api/planches/{id}/releves`. 2½ jours.
6. **Deux écrans** : l'empreinte compte relevés, passes et doutes ; « ⟳ Actualiser » ; un
   relevé retiré ailleurs. 1 jour.

### Jalon 3 — la maquette entière (≈ 5½ jours)

7. **Le Contexte modifiable** : le locuteur (le champ de l'Atelier sorti dans `static/lib/`,
   homonymes et lectures en vol compris), la note (`note_vue`), le nom d'un détail. 1½ jour.
8. **Tracer une zone** : le type `detail` (`TYPES_REGION`, `nom` à l'écriture, l'Atelier qui
   le montre et le laisse, la re-segmentation qui le garde), EXCLU de toute sortie jusqu'à la
   tranche 4 (G17), et sa relecture croisée ; le texte hors bulle et sa transcription ;
   supprimer une zone tracée ici. 2 jours.
9. **Écrans étroits et doigt** : « Étendre », « Ajouter un mot », « Tracer une zone », la
   grille « Poser… ▴ », le tiroir de la planche — jouables sur un vrai appareil. 1½ jour.
10. **L'Atelier et la documentation** : le renvoi croisé (H2), `docs/guide-utilisateur.md`,
    `docs/grilles-et-releves.md` (§12 n'est plus vrai), `docs/undo.md`. ½ jour.

**Total : ≈ 18 jours** (19 avec H4), dont ≈ 9 pour le premier jalon. Ce qui se reporte sans
risque si Hugo veut moins : le jalon 3 entier (les linguistes annotent sans lui, en passant
par l'Atelier pour le locuteur et la transcription) ; dans le jalon 2, l'Actualiser (les
valeurs uniques restent gardées par le 409). Ce qui ne se reporte pas : `vu` sur chaque
écriture, et l'exclusion du type `detail` des sorties le jour où il existe.

Chaque commit de code cite `ANN-7` (et `ANN-6` pour l'écran du relevé) ; la fiche se met à
jour à part.

---

## Les questions pour Hugo

1. **H1 — Le premier jalon.** Livrer d'abord la page sans le doute, la Synthèse, l'Actualiser,
   le Contexte modifiable, les zones tracées ni les gestes au doigt — le locuteur et la
   transcription restant à l'Atelier. *Proposé : oui* (≈ 9 jours au lieu de 18 pour
   commencer). Coût : les stagiaires et les professeurs n'ont pas le doute avant le jalon 2
   (≈ 3½ jours plus tard) ; un professeur qui repasse note son doute ailleurs d'ici là.
2. **H2 — Le mode Annotation de l'Atelier pendant la tranche 2.** (a) Il reste tel quel, avec
   un renvoi croisé (« Annoter ↗ » vers la page, « Ouvrir dans l'Atelier ↗ » depuis elle), et
   son sort se règle au basculement (tranche 3) ; le wizard mène à la page. (b) Il perd tout de
   suite les tags, la situation et le profil (personne n'en pose, Q9) et ne garde que le
   locuteur, l'identité d'une boîte et la note. (c) Il est retiré, remplacé par un renvoi.
   *Proposé : (a)*, ¼ jour. (b) coûte ~1 jour et touche cinq fichiers de tests qui visent les
   champs des tags, de la situation ou du profil (lu, par leurs sélecteurs) pour un
   basculement à moitié ; (c) retire l'écran du locuteur tant que le jalon 3 n'est pas
   là.
3. **H3 — Activer la grille des linguistes avant l'écran de la fiche du projet.** Aucune
   route d'activation n'a d'écran, et l'outil d'import importe et publie sans activer (lu).
   *Proposé : une option `--activer` (et `--masquer COLLECTION`) de `tools/importer_grille.py`*,
   ¼ jour, au commit 0 ; « Gérer les grilles ↗ » n'apparaît qu'avec la fiche. Coût : en
   production, l'activation passe par Hugo sur le serveur. L'autre voie — l'écran des grilles
   dans la fiche du projet — demande sa maquette avec le catalogue (≥ 2 jours) avant que les
   linguistes puissent commencer.
4. **H4 — Le bac à sable et le wizard.** Un bac à sable naît sans grille (lu :
   `routes/bac_a_sable.py`, `tools/preparer_jeu.py`) : la page n'y a rien à poser, et le
   wizard ne peut pas l'« intégrer ». *Proposé : chaque bac à sable naît avec une grille
   FICTIVE du dépôt, importée, publiée et activée à sa création* (effacée avec lui, ce que
   `_effacer_bac_a_sable` fait déjà), ~1 jour, à la fin de la tranche 2 ou en tête du lot du
   wizard ; les relevés de référence du jeu (G6) plus tard. Coût : un fichier de grille à
   écrire pour l'exemple, et le temps de création d'un bac à sable qui s'allonge d'un import
   (hypothèse : moins d'une seconde).
5. **H5 — « Changer… » sur un doute, vers une AUTRE entrée.** Le doute vit sur son relevé et
   part avec lui (CASCADE) ; aucune route ne remplace un relevé par un autre en gardant le
   fil. *Proposé : « Changer… » modifie le relevé en place* (variante, qualificatifs, passage,
   précision, lien — puis la levée « change ») ; *pour une autre entrée, l'écran dit
   « Retirez, puis posez l'autre »* (levée « retire », que Ctrl+Z rend). Coût : 0 au serveur ;
   le fil du doute quitte l'écran avec le relevé retiré (le journal le garde). L'autre voie :
   une route atomique qui pose l'autre entrée, y reporte le fil et lève « change » — ½ jour,
   et une annulation à deux actes à penser.
6. **H6 — Le décompte** (case ouverte d'`ANN-6`, « dans la vue, l'aperçu de l'Exploration, ou
   les deux »). *Proposé : dans la vue seulement* (Synthèse › Décompte, zone ou planche) ;
   l'Exploration compte les relevés en tranche 4. Coût : aucun ; l'aperçu de la v3 n'est pas
   construit deux fois.
7. **H7 — Un module montable dès maintenant ?** *Proposé : non* — une surface et sa logique
   pure dans `static/lib/`, la convention montable appliquée le jour où un second hôte existe
   (l'Atelier, ou le wizard s'il embarque la page au lieu d'y mener). Coût évité : ~1 à
   1½ jour (identifiants propres au montage, options d'hôte, cliquet). Coût différé : le jour
   du second hôte, la page se découpe en module — moins cher alors, sa logique étant déjà
   dehors.

Se tranchent en route, sans Hugo sauf avis contraire : le parcours dérivé des cibles (ci-dessus) ;
le choix de collection partagé avec l'Atelier ; la palette des rubriques ; le dérivé plutôt
que le recadrage serveur pour l'image de la case.

---

## Ce que cette note n'a pas pu établir

- **La netteté d'une case agrandie depuis le dérivé** : non regardée sur une vraie planche.
- **Le coût de `GET /api/planches/{id}/releves`** sur une planche chargée : non mesuré.
- **La grille des linguistes dans la page** : le brouillon du tableur attend la relecture de
  la gestionnaire et des linguistes (case ouverte d'`ANN-7`) ; que ses rubriques et ses
  formes se dessinent bien dans la colonne — profondeur des rubriques, longueur des
  libellés, nombre de variantes — se verra à son import sur la recette.
- **Une grille ouverte importée sans aucune entrée** (« Lieux », qui naît vide et s'enrichit
  en posant) : que l'import l'accepte n'est pas vérifié ici.
- **Tablette et téléphone** : la v3 ne les a essayés que simulés, et cette note pas du tout.
