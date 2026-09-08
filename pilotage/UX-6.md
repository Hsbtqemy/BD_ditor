---
chantier: UX-6
statut: interrompu
---

# UX-6 — écran « par où commencer » et guide utilisateur

**Arrêté sur** — 2026-09-06, `91ed11e` : **la moitié documentaire est écrite**, en DEUX
fichiers et non un — `docs/guide-utilisateur.md` (les gestes) et `docs/modele-et-droits.md`
(les objets et les règles). Reste l'écran.

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

### Arbitrages
- [x] La liste des étapes et leur ordre sont figés AVANT la première ligne de code, chaque étape nommant une surface et un geste : c'est le contrat commun de l'écran et du guide, et le laisser flotter ferait diverger les deux
- [ ] Le rang vis-à-vis de UX-3 est tranché et écrit dans les deux fiches : UX-3 veut rendre les quatre modes de la Visionneuse compréhensibles *sans* documentation, UX-6 les explique — décider lequel passe d'abord, ou acter qu'ils sont indépendants
- [ ] L'étape 1 n'est PAS corrigée, et son câblage attend UX-11 : « Bibliothèque : créer un album, importer des planches » nomme le bon lieu et DEVANCE le code (mesuré le 2026-09-06 — `static/corpus.js` n'appelle jamais `/api/albums/{id}/import`, le geste vit dans l'Atelier et fait `files[0]`, une planche à la fois). Deep-linker l'étape vers l'Atelier aujourd'hui enverrait quelqu'un constituer un corpus de quarante pages à un contrôle qui en prend une, et serait à re-pointer après UX-11
- [ ] Une fois UX-11 livré, l'étape 1 du guide distingue les DEUX imports — la Bibliothèque pour constituer en lot, l'Atelier pour la planche ajoutée en cours d'annotation — au lieu de remplacer l'un par l'autre : UX-11 garde explicitement celui de l'Atelier, et un guide qui n'en nommerait qu'un ferait chercher le mauvais

### Écran « par où commencer »
- [ ] L'écran s'ouvre au chargement d'une des cinq surfaces tant que « ne plus afficher » n'a pas été coché ; une fois coché, aucun rechargement ne le rouvre (état en `localStorage`, clé préfixée `bd-` comme celles de `static/theme.js`)
- [ ] Fermer sans cocher — croix ou Échap — ne vaut pas renoncement : l'écran revient au chargement suivant
- [ ] Il est rappelable à tout moment depuis la nav transverse, sur les cinq surfaces — donc injecté par `static/theme.js`, pas recopié dans cinq gabarits
- [ ] Chaque étape mène en un clic à la surface ET à l'outil qu'elle décrit (deep-link, cf. `docs/navigation-round-trip.md`), pas seulement à la page d'accueil de cette surface
- [ ] Une étape tient en un titre, une phrase et un lien : le détail vit dans le guide, pas dans la carte — aucune n'a besoin d'être dépliée pour être comprise
- [ ] L'écran est bâti sur `static/lib/dialog.js` — piège à focus, Échap, retour du focus au déclencheur — sans modale réécrite pour l'occasion
- [ ] L'écran dit ce que l'outil ne fait PAS : les trois passes ML ne font que pré-remplir, l'annotation reste entièrement humaine ; une carte muette là-dessus laisserait croire à une chaîne automatique
- [ ] Une étape dont le moteur est absent (`GET /api/sante` la donne indisponible) se présente comme optionnelle et non comme cassée
- [ ] L'étape 8 ne promet que ce que l'UI porte aujourd'hui (JSON-LD / CSV / TEI depuis la Visionneuse) ; les exports de dépôt — métadonnées de collection, IIIF — n'y entrent qu'une fois `EXP-1` livré (le C5 de la roadmap)
- [ ] Les raccourcis `N`/`E`/`A`/`T` et l'ordre des onglets de la Visionneuse sont inchangés : l'écart entre le parcours de la carte et l'ordre de la barre est assumé, pas résorbé en déplaçant un raccourci

### Guide utilisateur
- [x] `docs/guide-utilisateur.md` existe et couvre les huit étapes et les cinq surfaces du point de vue de la tâche — « transcrire une bulle », « corriger un lemme » — jamais de l'architecture
- [x] Le MODÈLE — hiérarchie, collections, groupes, qui peut quoi, vocabulaire, régimes de diffusion — est écrit et SÉPARÉ du parcours (`docs/modele-et-droits.md`), les deux se renvoyant l'un à l'autre : c'est ce qui permet au guide de rester sur la tâche sans laisser un arrivant sans réponse sur « pourquoi je ne vois rien »
- [ ] Chaque étape de l'écran renvoie à une section du guide qui existe : aucune ancre morte, vérifié en fin de chantier
- [x] Le guide traite le cas des moteurs optionnels absents (503 sur la route, mention dans `/api/sante`) au lieu de supposer l'installation complète
- [x] Le guide dit où vivent les exports de dépôt tant qu'ils n'ont pas de bouton (`tools/`, cf. `docs/export-metadonnees.md`) plutôt que de les passer sous silence
- [x] `README.md` et la section « Vue d'ensemble » de `CLAUDE.md` nomment le guide comme la documentation d'usage du dépôt, distincte des notes de conception
- [ ] Une note de conception courte justifie le parcours retenu, les étapes écartées et le refus de la visite guidée surlignée
- [x] **Les deux documents d'usage décrivent QUATRE surfaces, et il y en a cinq depuis le 2026-09-07** (UX-10 : `/administration`, où 👥 Collections et 🩺 Moteurs ont DÉMÉNAGÉ — la Bibliothèque n'y renvoie plus). Constat déposé ici par la session UX-10, qui n'a pas touché ces fichiers : ils appartiennent à ce chantier, et deux sessions n'écrivent pas dans le même fichier. Neuf emplacements, relevés : `docs/guide-utilisateur.md` — le titre « ## 2. Les quatre surfaces », la mention du panneau 🩺 Moteurs « de la Bibliothèque » en tête, les deux entrées 👥 Collections / 🩺 Moteurs de la liste des panneaux, et le dépannage « Ouvrez 🩺 Moteurs dans la Bibliothèque » ; `docs/modele-et-droits.md` — le tableau « panneau *👥 Collections* de la Bibliothèque », la phrase sur ce que le panneau déclare des groupes admin, le tableau « dans l'application, panneau *👥 Collections* », et le passage sur le genre **groupe**. `README.md` (ligne 10) décrit ce que CONTIENT le guide et suivra. Attendu : plus aucun renvoi vers la Bibliothèque pour ces deux panneaux, et le compte de surfaces juste — fait le 2026-09-07 (`909fe18`), sur DIX emplacements et non neuf : le § 5 de `modele-et-droits.md` disait des descripteurs de diffusion qu'« ils s'affichent dans la Bibliothèque », alors que `static/corpus.js` n'a plus une occurrence d'`embargo` — tout est dans `static/administration.js`. Le relevé nommait les deux panneaux ; l'affichage du régime avait déménagé sans être nommé, et c'est en vérifiant la liste plutôt qu'en la suivant qu'il est apparu

### Vérifications
- [ ] `pytest -m e2e` reste sans violation axe sérieuse ou critique sur les cinq surfaces × deux thèmes, **écran ouvert** : l'audit actuel ne voit jamais de modale au chargement
- [ ] La suite E2E existante passe sans qu'aucun test n'ait été réécrit pour contourner l'écran : le harnais le neutralise explicitement, en un seul endroit
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

L'étape 8 est la seule qui dépende d'un autre chantier, et **UX-6 ne l'attend pas** : les
exports de contenu (JSON-LD / CSV / TEI) sont dans l'UI depuis longtemps, seuls les
exports de dépôt — métadonnées de collection, IIIF — vivent encore dans `tools/` sans
bouton, jusqu'à `EXP-1`. Bloquer un chantier entier là-dessus serait disproportionné ; la
carte promet donc ce qui existe, et le guide dit où trouver le reste.

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
