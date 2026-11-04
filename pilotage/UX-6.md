---
chantier: UX-6
statut: interrompu
---

# UX-6 — écran « par où commencer » et guide utilisateur

**Arrêté sur** — 2026-11-04, `183c757` : **la tranche 3 est sur `dev`, PAS poussée, et sa reprise
est interrompue** (`dcaa88b`, `aab9a43`, `511401b`, `183c757`) — le guide pas à pas sur la
planche, l'étape faite lue sur la planche, « Corriger » qui cadre seul, « ✎ Tracer » dans
l'Atelier au clavier et au doigt, « optionnel ici » sans moteur. Hugo a refusé la fenêtre du
guide « toujours à gauche » : elle recouvre ce que l'étape montre. La reprise — la règle de
placement de la maquette — a été arrêtée en cours le soir du 2026-11-04, l'ordinateur fermé :
son état est dans `C:	empd-reprise-2026-11-04\` (`ETAT-REPRISE.md` et le correctif non
commité, `ux6-t3-reprise.patch`, à appliquer sur `183c757`), hors dépôt (cf. la zone « En cours » ci-dessous). Joués sur `dev` combiné : suite
par défaut verte ; `test_e2e_wizard`, `test_e2e_atelier_tracer`, `test_e2e_masquage` verts.

**Plus tôt, le 2026-11-04** — `418055d` : **la tranche 2 est sur `dev`** (`6bafa84`, `fbd2bf5`,
`86175dd`, `418055d`, poussée le jour même) — le « ? » de la bande sur les six surfaces, la
fenêtre posée à côté de la zone (pas une modale : la zone jouable, le reste `inert`, le focus
sans piège), la visite des sept pages en deux temps ; choisir un parcours lance la visite, la
carte vient après. Hors d'un bac à sable, les repères ne parlent pas du bac à sable
(`418055d`). Joués sur la copie rebasée : `test_e2e_wizard` 11, `test_e2e_reflow` 52 en
entier, `test_e2e_a11y` 107, `test_e2e_bac_a_sable` 43, `test_e2e_masquage` 18, tests Node 28.
Restent les tranches 3 et 4 et les cases ci-dessous.

**Plus tôt, le 2026-11-04** — `93a7e71` : **la première tranche de l'écran est sur `dev`**
(`44bcb17`, `b83b9fb`, `9a341dc`, `93a7e71`, pas encore poussée) — la logique du wizard
sous Node, une marque stable par zone de la visite, l'album de présentation et la carte des
étapes dans son bac à sable. Suite par défaut verte sur le poste et dans l'image ; les e2e
verts sur le poste et dans l'image une fois corrigés deux tests qui couraient contre la page
(`93a7e71` ici, `4932307` pour un test de COL-3 que l'image faisait tomber). Restent la
fenêtre posée sur la zone (tranches 2 à 4) et les cases ci-dessous.

**2026-09-06, `91ed11e`** : la moitié documentaire est écrite, en DEUX fichiers et non un —
`docs/guide-utilisateur.md` (les gestes) et `docs/modele-et-droits.md` (les objets et les
règles).

**2026-10-21 — l'écran est décalé à plus tard** (Hugo, au tri des chantiers). Il passe après
l'import en lot (`UX-11`), les formats de scan (`IMG-1`), le sélecteur de collection de
l'Atelier (`UX-19`) et l'annotation (`ANN-7`, puis l'onglet d'`ANN-6`). La passe
`accueil-par-ou-commencer` est gardée telle quelle pour lui. **Le même jour, il a trouvé sa
place** : le wizard vivra dans le bac à sable personnel (`COL-4`), sur une à trois planches
d'un jeu fixe où l'on suit toutes les étapes — on comprend sur pièce. Sa forme se tranchera sur
la maquette de `COL-4`.

**Et l'étape 1 n'est PAS à corriger — cette phrase disait l'inverse jusqu'au 2026-09-07.**
Elle annonçait « l'étape 1 à corriger avant de le câbler : elle nomme la Bibliothèque pour
un import qui vit dans l'Atelier ». La décision a été RETOURNÉE le lendemain (`aa930c9`),
après coordination avec UX-11 : l'étape s'appelle « CONSTITUER le corpus », et constituer
c'est verser quarante pages, pas ajouter la trente-huitième. La liste figée le 2026-08-27
nommait donc le bon lieu — c'est le CODE qui était en retard, et UX-11 le rattrape.
Corriger l'étape aurait inscrit une régression dans le contrat commun de l'écran et du
guide, puis obligé à la défaire aussitôt UX-11 livré. **Un entête qui survit à la décision
qu'il annonce est pire qu'un entête vide** : il est lu en premier, et il envoie refaire ce
qu'on vient d'écarter.

## Reste

### Tranché par Hugo sur maquette — 2026-11-02 (https://claude.ai/artifact/CN9ufFbLW23vm8DuN45hBu, version 21, privée)
Le texte des pages de l'album est celui que Hugo a réécrit, dans la maquette, à reprendre tel quel.
- [x] **La forme : une carte, puis le guide** — attendu : tranché. Une présentation (un album), le choix d'un parcours, la visite des pages, puis les gestes. Deux parcours : rapide (4 gestes : tracer, corriger, transcrire, annoter) et complet (9 étapes). L'album s'ouvre seul après « Mon bac à sable », avec « Passer » et « Fermer ✕ » ; la page sur le corpus vient en 2e ; le travail à plusieurs a sa carte ; la visite (sept pages : la barre du haut, puis les six surfaces) passe avant les deux parcours
- [x] **Le guide : une fenêtre posée à côté de la zone, le reste assombri, la zone jouable** — attendu : tranché, contre un bandeau sous la ligne du bac (refusé par Hugo) et une colonne. Une page de plusieurs zones se joue en deux temps : la fenêtre change de côté au bouton « Suivant », jamais au survol (refusé par Hugo)
- [x] **Une étape faite se voit sur la planche, sans coche à déclarer** — attendu : tranché
- [x] **Le rappel : un bouton sur les six surfaces**, qui rouvre les repères de la page où l'on est — attendu : tranché. La forme « ? » à côté de « Aa », « Revoir les repères de cette page » en infobulle et en nom accessible, est une proposition à revoir sur l'écran codé. Il ne nomme que ce que la page montre, et ne change ni le mode ni l'album
- [x] **Neuf étapes et non huit** : « Tracer une zone » s'ajoute entre « Pré-remplir » et « Corriger le découpage » — attendu : tranché, RENVERSE la liste figée le 2026-08-27. On doit comprendre qu'on peut créer des zones, pas seulement les corriger
- [x] **La visite guidée surlignée est RETENUE** — attendu : tranché, RENVERSE le refus de cette fiche, qui tenait à son couplage au balisage des surfaces. Ce couplage devient une dépendance à tenir (première case ci-dessous)
- [x] **Les modes de l'Atelier : quatre à la sortie du wizard, trois après le basculement d'`ANN-7`** — attendu : tranché. Le 4e se dit « Annotation pour poser des tags et une note (les grilles sont dans la page Annotation) ». Ordre : `UX-20`, le wizard, le basculement. Le renvoi est chez `ANN-7`
- [x] **« Corriger » : l'Atelier cadre seul** — attendu : tranché. En entrant dans l'étape, la planche se rapproche de la bulle, et elle revient à la planche entière en sortant
- [x] **Chaque zone de la visite a une marque stable** — attendu : un attribut par zone (`data-parcours`, par exemple), et un test qui échoue si une marque nommée par le guide manque à sa surface ; sans lui, un écran remanié fait disparaître une zone du guide sans bruit — fait le 2026-11-04 (`b83b9fb`) : `data-parcours`, tenu par `tests/test_wizard_marques.py`
- [x] **La fenêtre sur la zone se dessine au clavier** — attendu : elle n'est pas une modale, la zone reste jouable, le reste est `inert`, et le focus y entre et en sort sans piège ; la maquette ne le fait pas — fait le 2026-11-04 (`86175dd`) : `test_la_fenetre_sur_la_zone_au_clavier_et_en_deux_temps` (le reste `inert`, Maj+Tab et Tab sans s'arrêter sur un inerte, Échap rend le focus, ni `role` ni `aria-modal`)
- [x] **Le souvenir est tranché** — attendu : l'album déjà vu, le parcours et l'étape vivent soit dans le navigateur, rangés par login comme `bd-bacs-a-sable`, soit avec le bac à sable ; dans les deux cas, après un effacement, le wizard ne reprend pas à l'étape 6 sur une planche remise à zéro **Tranché par Hugo le 2026-11-03 : dans le navigateur, rangé par login et sous l'identifiant du bac à sable — aucune migration, il ne suit pas d'un poste à l'autre.**
- [x] **Après un effacement, le wizard repart du début** — attendu : sur un bac à sable effacé (lundi ou « Remettre à neuf… »), le souvenir rangé sous l'ancien identifiant n'est plus lu ; si l'identifiant survit à la remise à neuf, une autre marque (`efface_le`) fait la différence, mesurée par un test — fait le 2026-11-04 : l'identifiant ne survit pas (un projet neuf, `AUTOINCREMENT`), mesuré sur les deux chemins par `tests/test_wizard_souvenir.py`, et le côté navigateur par `tests/js/wizard.test.js`
- [ ] **Ce qui compte comme une étape faite est défini** — attendu : une liste, étape par étape, lue sur les régions, les textes et les relevés, qui tient sur des données repartant à neuf chaque lundi **Codé le 2026-11-04 (`511401b`) : la liste en tête de `static/lib/wizard.js`, `faite()`, testée sous Node — à confirmer avec les choix de la tranche 3.**
- [ ] **Sans moteur, « Pré-remplir » se dit optionnel** — attendu : `GET /api/sante` suffit ; l'étape et l'album disent « optionnel ici » **Codé le 2026-11-04 (`511401b`) : la carte, le guide et la page des moteurs de l'album disent « optionnel ici » ; testé sous Node, pas joué en e2e sans moteur.**
- [ ] **« Automatisez la reconnaissance » s'écrit après la vraie passe** — attendu : le vrai découpage et le vrai OCR ont tourné sur *Moustache et Trottinette*, dont le lettrage est manuscrit, et la page dit ce qu'ils ont rendu ; la maquette SIMULE ses erreurs (`t0t`, `rec0nnaît`) et promet « 3 cases, 3 bulles, 1 cartouche » sans mesure
- [ ] **« Exporter » dit ce qui sort vraiment d'un bac à sable** — attendu : l'étape et les phrases des pages ne promettent aucune sortie refusée : le jeu de production est en part serveur, export fermé pour tous, donc rien n'y sort d'un bac à sable
- [x] **L'Atelier a un geste de tracer pour tous** — attendu : au clavier et au doigt, comme « Tracer une zone » de la page Annotation ; aujourd'hui Maj+glisser ne se voit qu'une fois une région choisie, et l'étape « Tracer une zone » ne tient pas sans lui — fait le 2026-11-04 (`aab9a43`) : « ✎ Tracer » dans la barre du canevas, en Édition ; au clavier par `rectangleInitial` / `rectangleClavier` de `lib/annotation.js`, au doigt le bouton arme le glissé (`tests/test_e2e_atelier_tracer.py`, la barre mesurée à 320, 768 et 1 280 px, polices 16 et 24)
- [ ] **`docs/guide-utilisateur.md` dit les neuf étapes** — attendu : « Tracer une zone » y a sa section, et chaque étape de l'écran y renvoie
- [ ] **La maquette se mesure sur l'écran codé** — attendu : à 320 px et en grande police, la bande du haut gagne le « ? » sans déborder ; à 768 px, la fenêtre ne cache rien d'indispensable à la dernière zone de la Recherche et de l'Exploration ; « Visite n / 7 » ne reste pas figé entre les deux temps d'une page ; le titre de la Transcription ne dit pas « Bulle 4 / 4 » sur un cartouche **Le 2026-11-04 (`86175dd`) : à 320 px, polices 16 et 24, la bande gagne le « ? » sans déborder (`test_e2e_reflow` vert en entier), et « Visite n / 7 » change entre les deux temps (« · 1 / 2 », « · 2 / 2 ») ; restent 768 px et la suite.**
- [ ] **Exploration vide : le message dit la vraie cause** — attendu : « Aucune donnée (relancer l'indexation NLP ?) » n'apparaît plus quand c'est qu'aucun corpus n'est ouvert ; le wizard y conduit tout arrivant
- [ ] **La Recherche dit « Atelier »** — attendu : le bouton de l'aperçu et son infobulle ne disent plus « Visionneuse », que le wizard n'enseigne pas
- [ ] **La visite tient pour un compte sans autre projet** — attendu : Recherche et Exploration, à zéro partout parce que le bac à sable en est exclu, ne se lisent pas comme une panne ; la phrase d'export ne s'y affiche plus à qui n'a rien à exporter
- [ ] **L'Administration se lit par un arrivant** — attendu : plus de « sa passe répond 503 » ni de « contrôle de présence » sans explication dans ce que la visite lui montre
- [ ] **L'Accord accorde au pluriel** — attendu : « 1 album », « 1 planche »
- [ ] **La citation d'une bulle suit le rang de sa case** — attendu : sur le vrai jeu, la nouvelle planche comprise, la bulle de la case du milieu se cite `c2 · b1` ; une instance jetable a donné `c3 · b1` sur *Chez les Chinois*, cases d'identifiants 1, 3 et 6, cause non cherchée

### Tranché par Hugo le 2026-11-03 — les choix de la première tranche
Proposés par l'agent qui code la première tranche (copie `ux6-wizard`, pas encore sur `dev`), confirmés tous les sept par Hugo, sans maquette : chacun se revoit sur l'écran codé.
- [x] **« Fermer ✕ » sans cocher « Ne plus afficher » ne vaut pas renoncement** — attendu : tranché, l'album revient au chargement suivant (le contrat de la section « Écran par où commencer » est gardé)
- [x] **Le wizard ne s'ouvre que dans SON bac à sable** — attendu : tranché, jamais chez un invité, ni hors d'un bac à sable
- [x] **L'album s'ouvre seul sur les six surfaces** — attendu : tranché, pas seulement dans l'Atelier
- [x] **« Ne plus afficher » vaut pour CE bac à sable** — attendu : tranché, l'album revient après l'effacement du lundi ou une remise à neuf
- [x] **L'étape « Exporter » ne promet rien** — attendu : tranché, sa phrase commence par « Ailleurs que dans un bac à sable… » ; la case « Exporter dit ce qui sort vraiment » reste ouverte jusqu'à l'écran codé
- [x] **Choisir un parcours ouvre la carte des étapes** — attendu : tranché, en attendant la fenêtre posée sur la zone
- [x] **L'album se lit une page à la fois** — attendu : tranché, sans glissé au doigt ; ses illustrations sont les miniatures du jeu servies par l'instance, les pages 6 et 7 sans illustration

### Tranché par Hugo le 2026-11-04 — les choix de la tranche 2
Proposés par l'agent qui code la tranche 2, confirmés tous les sept par Hugo, sans maquette : chacun se revoit sur l'écran codé.
- [x] **Le compte de la visite s'écrit « Visite 2 / 7 · 1 / 2 »** — attendu : tranché, le second nombre suit les deux temps d'une page
- [x] **Le « ? » est offert à tout compte, hors d'un bac à sable compris** — attendu : tranché ; hors d'un bac à sable, les repères de la Recherche et de l'Exploration ne parlent pas du bac à sable, et chez un invité ils disent « ce bac à sable » (`418055d`, un test Node balaie toute la visite)
- [x] **Le « ? » ouvre la page de la surface, jamais celle de la barre du haut** — attendu : tranché, comme la maquette
- [x] **Un repère se choisit au clic dans la liste, jamais au survol ni au focus** — attendu : tranché
- [x] **Échap ferme la visite sans ouvrir la carte** — attendu : tranché
- [x] **Sous 40em, la fenêtre est une feuille en bas, pleine largeur, 55 % de haut au plus** — attendu : tranché, à revoir sur l'écran codé
- [x] **Quand la bande passe à la ligne, le « ? » et « Aa » peuvent se séparer** — attendu : tranché
- [x] **Un menu ouvert depuis une zone n'est pas assombri** — attendu : « Aa » ou « Traitement » ouverts pendant la visite se lisent en clair ; aujourd'hui ils restent jouables mais s'affichent sous l'assombri, hors du trou — fait le 2026-11-04 (`511401b`) : un trou de l'assombri sur la liste de « Traitement » ou le panneau « Aa » (le test e2e joue « Traitement »)
- [x] **Chez un invité, la zone « Votre bac à sable » de la barre du haut dit ses gestes** — attendu : la fenêtre ne lui promet ni « inviter » ni « remettre à neuf », qu'il n'a pas, mais « Quitter… » (le titre dit déjà « Ce bac à sable » depuis `418055d`, la phrase non) — fait le 2026-11-04 (`511401b`) : « Quand il s'efface, et ce qu'on y fait : le quitter. » (texte de l'agent, à relire par Hugo)

### En cours — la tranche 3, sa reprise interrompue le 2026-11-04
Hugo a refusé la fenêtre du guide « toujours à gauche » et demandé de reprendre la règle de la maquette (`C:\temp\maquette-lot4\wizard.js`, `FOYERS`, `rectFoyer`, `majFoyer`). L'état de la reprise : `C:	empd-reprise-2026-11-04\ETAT-REPRISE.md`, et le travail non commité dans `ux6-t3-reprise.patch` à côté (sur `183c757`) : les foyers précis, l'assombri à un trou, `placerFenetre` testé sous Node, la feuille du bas, « Corriger » recadré, le test de recouvrement — restent à rejouer les e2e et à commiter.
- [ ] **La fenêtre du guide ne recouvre pas ce que l'étape montre** — attendu : chaque étape éclaire un foyer PRÉCIS (la carte de l'album, le bloc de la source, « Traitement » et son menu, la bulle à corriger et le panneau, la colonne de droite de la Transcription, la case agrandie et la grille, le champ de recherche) ; la fenêtre se pose à droite du foyer, sinon à gauche, dessous, dessus, et en bas à gauche seulement si rien ne tient ; une étape neuve fait défiler jusqu'à son foyer, et sur un écran étroit la page réserve la hauteur de la feuille
- [ ] **« Corriger » cadre la bulle hors de la fenêtre** — attendu : en entrant dans l'étape, la bulle se voit en entier, à côté de la fenêtre et non dessous
- [ ] **Un test échoue si la fenêtre recouvre le foyer** — attendu : chaque étape des deux parcours, à 1 280 et 768 px, polices 16 et 24 ; il tombe sur une fenêtre forcée à gauche
- [ ] **La tranche 3 est relue contre la maquette** — attendu : chaque écart entre l'écran codé et la maquette (foyers, textes, boutons, comportement) listé, aligné ou motivé
- [ ] **Les choix de la tranche 3 sont confirmés** — attendu : Hugo répond aux neuf choix restants proposés par l'agent le 2026-11-04 (le choix « fenêtre toujours à gauche » est retiré) : étape faite marquée sans passage automatique ; « ✎ Tracer » en Édition seulement, premier rectangle dans la case choisie ou au milieu de la part visible ; une région du jeu reprise passe à `corrige` ; l'état du guide dans l'onglet, Échap = ✕ ; la bulle à cadrer, la plus petite non reprise, cadre ×3 ; « Tracer » exige case ET bulle, « Transcrire » au complet toutes les zones de texte ; « Seule la dernière rangée… » seulement si le jeu a posé des régions ; deux textes de l'agent (le repère « Transcription », la phrase de l'invité), « Parcours terminé » sans vignettes ; « optionnel ici » sur l'album sans aucun moteur, sur l'étape dès qu'il manque l'OCR

### Arbitrages
- [x] La liste des étapes et leur ordre sont figés AVANT la première ligne de code, chaque étape nommant une surface et un geste : c'est le contrat commun de l'écran et du guide, et le laisser flotter ferait diverger les deux
- [x] Le rang vis-à-vis de UX-3 est tranché et écrit dans les deux fiches : UX-3 veut rendre les quatre modes de la Visionneuse compréhensibles *sans* documentation, UX-6 les explique — décider lequel passe d'abord, ou acter qu'ils sont indépendants **Tranché le 2026-11-02 : ils ne sont pas indépendants, le wizard dit les modes et son texte change au basculement d'`ANN-7` ; le wizard passe d'abord.**
- [ ] L'étape 1 n'est PAS corrigée, et son câblage attend UX-11 : « Bibliothèque : créer un album, importer des planches » nomme le bon lieu et DEVANCE le code (mesuré le 2026-09-06 — `static/corpus.js` n'appelle jamais `/api/albums/{id}/import`, le geste vit dans l'Atelier et fait `files[0]`, une planche à la fois). Deep-linker l'étape vers l'Atelier aujourd'hui enverrait quelqu'un constituer un corpus de quarante pages à un contrôle qui en prend une, et serait à re-pointer après UX-11
- [ ] Une fois UX-11 livré, l'étape 1 du guide distingue les DEUX imports — la Bibliothèque pour constituer en lot, l'Atelier pour la planche ajoutée en cours d'annotation — au lieu de remplacer l'un par l'autre : UX-11 garde explicitement celui de l'Atelier, et un guide qui n'en nommerait qu'un ferait chercher le mauvais

### Écran « par où commencer »
- [ ] L'écran s'ouvre au chargement d'une des cinq surfaces tant que « ne plus afficher » n'a pas été coché ; une fois coché, aucun rechargement ne le rouvre (état en `localStorage`, clé préfixée `bd-` comme celles de `static/theme.js`)
- [ ] Fermer sans cocher — croix ou Échap — ne vaut pas renoncement : l'écran revient au chargement suivant
- [ ] Il est rappelable à tout moment depuis la nav transverse, sur les cinq surfaces — donc injecté par `static/theme.js`, pas recopié dans cinq gabarits
- [ ] Chaque étape mène en un clic à la surface ET à l'outil qu'elle décrit (deep-link, cf. `docs/navigation-round-trip.md`), pas seulement à la page d'accueil de cette surface
- [ ] Une étape tient en un titre, une phrase et un lien : le détail vit dans le guide, pas dans la carte — aucune n'a besoin d'être dépliée pour être comprise **Depuis la maquette du 2026-11-02, cela ne vaut plus que pour la carte et l'album.**
- [ ] L'écran est bâti sur `static/lib/dialog.js` — piège à focus, Échap, retour du focus au déclencheur — sans modale réécrite pour l'occasion **Depuis la maquette du 2026-11-02, cela ne vaut plus que pour la carte et l'album : la fenêtre sur la zone n'est pas une modale.**
- [ ] L'écran dit ce que l'outil ne fait PAS : les trois passes ML ne font que pré-remplir, l'annotation reste entièrement humaine ; une carte muette là-dessus laisserait croire à une chaîne automatique
- [ ] Une étape dont le moteur est absent (`GET /api/sante` la donne indisponible) se présente comme optionnelle et non comme cassée
- [ ] L'étape 8 ne promet que ce que l'UI porte aujourd'hui, et l'UI en porte PLUS qu'à la rédaction de cette case : les exports de contenu (JSON-LD / CSV / TEI) depuis l'Atelier, ET les exports de dépôt — fiche de description, enregistrements, manifeste IIIF — depuis la Bibliothèque → 📚 Collections, `EXP-1` étant `livré` depuis le 2026-09-07 — le bloc vivait dans Administration → 👥 Collections jusqu'à `COL-2` (2026-09-11), qui l'a déménagé avec ce que la collection EST. La carte les nomme donc tous les deux au lieu d'excuser un manque. Le guide le fait déjà : c'est la carte qui est en retard sur lui, et non l'inverse
- [ ] Les raccourcis `N`/`E`/`A`/`T` et l'ordre des onglets de la Visionneuse sont inchangés : l'écart entre le parcours de la carte et l'ordre de la barre est assumé, pas résorbé en déplaçant un raccourci

### Guide utilisateur
- [x] `docs/guide-utilisateur.md` existe et couvre les huit étapes et les cinq surfaces du point de vue de la tâche — « transcrire une bulle », « corriger un lemme » — jamais de l'architecture
- [x] Le MODÈLE — hiérarchie, collections, groupes, qui peut quoi, vocabulaire, régimes de diffusion — est écrit et SÉPARÉ du parcours (`docs/modele-et-droits.md`), les deux se renvoyant l'un à l'autre : c'est ce qui permet au guide de rester sur la tâche sans laisser un arrivant sans réponse sur « pourquoi je ne vois rien »
- [ ] Chaque étape de l'écran renvoie à une section du guide qui existe : aucune ancre morte, vérifié en fin de chantier
- [x] Le guide traite le cas des moteurs optionnels absents (503 sur la route, mention dans `/api/sante`) au lieu de supposer l'installation complète
- [x] Le guide dit où vivent les exports de dépôt tant qu'ils n'ont pas de bouton (`tools/`, cf. `docs/export-metadonnees.md`) plutôt que de les passer sous silence
- [x] `README.md` et la section « Vue d'ensemble » de `CLAUDE.md` nomment le guide comme la documentation d'usage du dépôt, distincte des notes de conception
- [ ] Une note de conception courte justifie le parcours retenu, les étapes écartées et le refus de la visite guidée surlignée **La visite guidée surlignée est retenue depuis le 2026-11-02 : la note dira ce renversement.**
- [x] **Les deux documents d'usage décrivent QUATRE surfaces, et il y en a cinq depuis le 2026-09-07** (UX-10 : `/administration`, où 👥 Collections et 🩺 Moteurs ont DÉMÉNAGÉ — la Bibliothèque n'y renvoie plus). Constat déposé ici par la session UX-10, qui n'a pas touché ces fichiers : ils appartiennent à ce chantier, et deux sessions n'écrivent pas dans le même fichier. Neuf emplacements, relevés : `docs/guide-utilisateur.md` — le titre « ## 2. Les quatre surfaces », la mention du panneau 🩺 Moteurs « de la Bibliothèque » en tête, les deux entrées 👥 Collections / 🩺 Moteurs de la liste des panneaux, et le dépannage « Ouvrez 🩺 Moteurs dans la Bibliothèque » ; `docs/modele-et-droits.md` — le tableau « panneau *👥 Collections* de la Bibliothèque », la phrase sur ce que le panneau déclare des groupes admin, le tableau « dans l'application, panneau *👥 Collections* », et le passage sur le genre **groupe**. `README.md` (ligne 10) décrit ce que CONTIENT le guide et suivra. Attendu : plus aucun renvoi vers la Bibliothèque pour ces deux panneaux, et le compte de surfaces juste — fait le 2026-09-07 (`909fe18`), sur DIX emplacements et non neuf : le § 5 de `modele-et-droits.md` disait des descripteurs de diffusion qu'« ils s'affichent dans la Bibliothèque », alors que `static/corpus.js` n'a plus une occurrence d'`embargo` — tout est dans `static/administration.js`. Le relevé nommait les deux panneaux ; l'affichage du régime avait déménagé sans être nommé, et c'est en vérifiant la liste plutôt qu'en la suivant qu'il est apparu

### Vérifications
- [ ] `pytest -m e2e` reste sans violation axe sérieuse ou critique sur les cinq surfaces × deux thèmes, **écran ouvert** : l'audit actuel ne voit jamais de modale au chargement **Le 2026-11-04 : axe passé sur la visite ouverte (barre du haut et Atelier), thèmes sombre et clair ; pas encore sur la fenêtre des repères surface par surface.**
- [x] La suite E2E existante passe sans qu'aucun test n'ait été réécrit pour contourner l'écran : le harnais le neutralise explicitement, en un seul endroit — vérifié le 2026-11-04 : `window.BD_SANS_WIZARD` posé par la fixture `context` de `tests/conftest.py`, seul endroit ; la seule assertion existante changée (`test_e2e_bac_a_sable`) l'est parce que la ligne porte désormais « Par où commencer », pas pour contourner l'album
- [ ] Aucun petit texte coloré de l'écran n'utilise un accent brut : tokens d'encre AA-sûrs, règle d'accessibilité de `CLAUDE.md`
- [ ] Sur 375 px de large, la carte des étapes reste lisible et la fermeture atteignable sans défilement horizontal
- [ ] La passe `pilotage/qa/accueil-par-ou-commencer.md` a été jouée une fois sur l'écran construit, et son verdict sur le nombre d'étapes est reporté ici

## Contexte

Forme retenue le 2026-08-27 : un **écran « par où commencer »** — une carte des étapes,
chacune renvoyant par deep-link à sa surface et à son outil. Pas de visite guidée
surlignant les vrais éléments : elle se couple au DOM des cinq surfaces, or UX-3
(hiérarchie des actions) et UX-4 (cohérence inter-surfaces) sont ouverts et vont
précisément déplacer ces éléments. Une visite écrite maintenant serait à réécrire deux
fois. L'assistant de mise en route — celui qui *fait* les gestes du premier corpus — a
été écarté pour une autre raison : il dupliquerait la Bibliothèque, qui porte déjà la
création d'album, l'import de planches et le lancement des lots.

### Les huit étapes, figées le 2026-08-27

1. **Constituer le corpus** — Bibliothèque : créer un album, importer des planches
2. **Décrire l'album** — Bibliothèque : paternité, édition, collection, source de numérisation
3. **Pré-remplir** *(optionnel)* — Bibliothèque, lots : cases, bulles, OCR
4. **Corriger le découpage** — Visionneuse, mode Édition
5. **Transcrire et relire** — Visionneuse, mode Transcription, puis panneau Grammaire
6. **Annoter** — Visionneuse, mode Annotation : locuteur, personnages, tags, note
7. **Chercher et explorer** — Recherche, puis Exploration
8. **Exporter** — Visionneuse, menu export

L'ordre 4 → 5 → 6 n'est pas un ordre de lecture, c'est une dépendance : le crop du mode
Transcription est recadré dans le master **à partir de la bbox de la région**
(`static/viewer.js`, où le cache-buster sur les coordonnées le dit explicitement). Une
bulle mal détourée est donc intranscriptible — alors qu'elle reste taggable. La chaîne
réelle est *machine → géométrie → texte → interprétation*. C'est en inversant
transcription et annotation que l'étape 4 est apparue : la première liste n'en avait pas,
le geste étant fondu à tort dans « pré-remplir », comme si les passes ML posaient des
boîtes définitives.

L'écart avec la barre de modes de la Visionneuse — ordonnée Navigation · Édition ·
**Annotation** · **Transcription** — est **assumé**. Les onglets sont un sélecteur, pas
un parcours, et les réordonner pour faire plaisir à une carte d'accueil déplacerait des
raccourcis clavier que quelqu'un a déjà dans les doigts. Décision prise indépendamment de
l'arbitrage UX-3, qui reste ouvert.

**Huit étapes est provisoire, et c'est délibéré.** Fusionner 1 et 2 était tentant — même
formulaire de la Bibliothèque — mais on ne sait pas encore si la carte sera trop bavarde
ou trop sèche, et ça ne se juge pas sur une liste : ça se juge sur l'écran construit,
chronomètre en main. D'où la passe `pilotage/qa/accueil-par-ou-commencer.md`, **écrite
avant l'écran** pour que « trop d'info » ait un attendu, au lieu d'être un ressenti a
posteriori — c'est-à-dire au moment où l'on sera attaché à ce qu'on aura fait.

### Ce qui a été tranché ailleurs

Déclenchement : **à l'ouverture, persisté dans le navigateur**. La variante « tant que le
corpus est vide » avait un avantage réel — un fait objectif, lu en base, rien à
désynchroniser — mais elle rate le cas dominant ici : un corpus déjà rempli par quelqu'un
d'autre, ouvert par une personne qui n'a jamais vu l'outil. Le prix est connu et accepté :
un autre profil de navigateur revoit l'écran.

Précision arrachée en écrivant la passe de QA, parce que les deux cases se contredisaient :
« s'ouvre une seule fois » et « case *ne plus afficher* » ne peuvent pas tenir ensemble —
si l'écran ne revient jamais de toute façon, la case ne promet rien. Retenu : **il revient
à chaque chargement tant que la case n'est pas cochée**. Celui qui congédie la carte avant
d'avoir compris ce qu'elle propose est précisément celui à qui elle sert ; et le rappel
depuis la nav ne le rattrape pas, puisqu'il faut déjà savoir qu'il existe.

Le chantier a une **dette d'infrastructure de test** qui n'est pas anecdotique. La
fixture `page` de pytest-playwright ouvre un contexte neuf par test, donc un
`localStorage` vide : sans précaution, l'écran s'affiche devant *chaque* test E2E et
intercepte le premier clic. `tests/test_e2e_navigation.py` et `tests/test_e2e_a11y.py`
enchaînent `page.goto(...)` puis cliquent immédiatement — ils tomberaient tous ensemble.
D'où la case qui exige un seul point de neutralisation : la tentation, face à trente
tests rouges, est d'ajouter trente fermetures.

La **documentation est la moitié du chantier, pas son appendice** : `docs/` documente
depuis le début les décisions de conception, jamais l'usage. L'écran d'accueil sans
guide derrière lui ne serait qu'un sommaire pointant vers des pages qui n'expliquent
rien ; le guide sans écran resterait invisible. Les deux se tiennent, et la case des
ancres mortes est là pour que le lien entre eux soit vérifié plutôt que supposé.

Rangé **C6** dans la piste C de `docs/roadmap.md`, P2·M, **déclenché par C1** — la même
bascule que C5 : en mono-poste, l'outil s'apprend en le construisant, et la question ne
se pose pas. Déployé, il s'ouvre devant quelqu'un qui n'a jamais vu la chaîne.

L'étape 8 était la seule à dépendre d'un autre chantier, et **UX-6 ne l'attendait pas** :
les exports de contenu (JSON-LD / CSV / TEI) sont dans l'UI depuis longtemps, seuls les
exports de dépôt — métadonnées de collection, IIIF — vivaient dans `tools/` sans bouton,
jusqu'à `EXP-1`. Bloquer un chantier entier là-dessus aurait été disproportionné ; la carte
promet ce qui existe, et le guide dit où trouver le reste.

**`EXP-1` est `livré` depuis le 2026-09-07, et la contrainte tombe** : le bloc *Export de
dépôt* vit dans Administration → 👥 Collections. Le guide le dit déjà — il renvoie l'étape 8
vers ce bloc —, donc c'est la CARTE qui reste en retard sur le guide, et non l'inverse. Une
étape 8 écrite aujourd'hui peut nommer les deux sorties au lieu d'en excuser une.

**Et le bloc a déménagé depuis.** `COL-2` (2026-09-11) l'a porté dans la Bibliothèque →
📚 Collections, avec les descripteurs de la collection ; l'Administration ne garde que les
accès. Le guide, relu le même jour, range bien l'export de collection dans la Bibliothèque
(§ 2, tableau des surfaces) : c'est là que l'étape 8 doit renvoyer.

Reste hors périmètre, faute d'être tranché : une aide contextuelle par surface (un « ? »
qui ouvre la section correspondante du guide). C'est un second chantier, à ouvrir une
fois le guide écrit et ses sections stabilisées.

### La documentation, écrite le 2026-09-06 (`91ed11e`)

**DEUX fichiers et non un**, et c'est un arbitrage, pas un débordement. La fiche ne nommait
que `docs/guide-utilisateur.md`, sur la tâche et « jamais de l'architecture ». Mais un
arrivant sur l'instance déployée ne bute pas d'abord sur un geste : il bute sur « je ne vois
aucun album », « pourquoi mon collègue ne voit pas ce tag », « c'est quoi une dimension ».
Répondre exigeait le modèle — hiérarchie, collections, groupes, portées, vocabulaire — que le
guide de tâches ne peut pas porter sans cesser d'être un guide de tâches. Le critère qui a
tranché est le MOMENT DE LECTURE : on rouvre le guide chaque fois qu'on cherche un bouton, on
lit le modèle une fois, avant de commencer. Les fondre aurait posé un exposé sur les groupes
entre l'étape 2 et l'étape 3.

**Périmètre élargi jusqu'au compte Authelia**, demandé explicitement. Le risque de doublon
avec `docs/exploitation.md` est réel et traité en le DÉCLARANT : le § 6 du modèle donne la
forme du geste et ses deux pièges — le YAML contrôlé, `bd-admins` sans lequel on arrive sur
une application vide — puis renvoie pour les commandes exactes en écrivant que c'est
`exploitation.md` qui fait foi. Deux endroits où lire la même commande finissent par se
contredire ; un endroit qui explique et un endroit qui exécute, non.

**L'étape 1 est fausse, et ce sont les documents qui l'ont trouvée** — parce qu'ils ont été
écrits contre le CODE et non contre le README, qui la répète. C'est l'argument de la fiche
retourné : le contrat commun n'a pas seulement empêché l'écran et le guide de diverger, il a
fait diverger la LISTE d'avec l'application, et c'est le guide qui l'a dit. Le même passage
a confirmé que `GET /api/sauvegarde` est bien réservée aux administrateurs — la § AUTH-2 de
`CLAUDE.md` affirme encore l'inverse, non corrigé, à traiter hors de ce chantier.

Deux cases du guide restent ouvertes exprès. Les **ancres** ne se vérifient qu'une fois
l'écran écrit, puisque ce sont les siennes. Et la **note de conception** sur le parcours
retenu n'a pas été écrite : l'essentiel de son contenu vit déjà dans ce `Contexte`, et la
rédiger avant l'écran figerait un raisonnement que la passe de QA peut encore condamner.

### L'étape 1, reprise le 2026-09-07 : la liste avait raison

UX-11 ouvre l'import en lot dans la Bibliothèque, et sa fiche pose la collision avec la case
écrite ici la veille. Elle proposait deux sorties — nommer l'Atelier maintenant et corriger
après, ou nommer les deux d'emblée. **Aucune des deux n'est retenue, parce que la case posait
mal le problème.**

L'étape 1 s'appelle « **Constituer** le corpus ». Constituer, c'est verser quarante pages,
pas ajouter la trente-huitième. La liste figée disait « Bibliothèque » : elle nommait le lieu
du geste tel qu'il doit être, et c'est le CODE qui était en retard — pas elle. Corriger la
liste vers l'Atelier aurait donc inscrit dans le contrat une régression, puis obligé à la
défaire. La case devient une DÉPENDANCE : ne rien corriger, ne pas câbler, attendre UX-11.

Ce que la première rédaction avait manqué, faute d'avoir lu UX-11 : **le chantier ne DÉPLACE
pas l'import, il en ajoute un second.** « Les deux surfaces importeront, pour deux besoins
distincts », écrit sa fiche. La sortie « nommer les deux » aurait donc été juste sur le fond
et fausse sur le calendrier — les deux, oui, mais seulement après. D'où la seconde case, qui
porte sur le guide et non sur la carte : c'est lui qui devra dire lequel sert à quoi.

Le vrai défaut trouvé ce jour-là est ailleurs et n'attend personne : les deux documents
disaient **Visionneuse**, quand la nav transverse (`static/theme.js`) affiche **Atelier**
depuis `1cc3a41`. Un guide d'usage qui nomme un onglet autrement que l'écran envoie chercher
ce qui n'existe pas — c'est exactement la panne qu'il est censé éviter. Corrigé : les
documents disent Atelier, avec une note qui rattache le mot à celui du code. `CLAUDE.md` et
`README.md` disent toujours Visionneuse, et ce n'est pas rien : la nomenclature interne et
l'écran ont divergé sans que personne l'écrive. Hors périmètre d'UX-6, à signaler.

### Hors de la grande étape de fusion — 2026-09-22

La passe `pilotage/qa/accueil-par-ou-commencer.md` était l'une des trois « jamais jouées »
dont le périmètre FERMÉ du 2026-09-17 faisait attendre la fusion de `dev` dans `main`
(`docs/roadmap.md`). Elle ne pouvait pas l'être : elle éprouve l'écran, et l'écran n'existe
pas. **Hugo l'a sortie du périmètre le 2026-09-22, « pour l'instant ».** Ce chantier ne
retient donc plus la fusion, et rien n'y change de calendrier : c'est la construction de
l'écran qui la fera rentrer, avec l'étape qui le portera.
