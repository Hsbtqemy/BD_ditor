---
chantier: CONC-3
statut: interrompu
---

# CONC-3 — deux personnes sur la même planche : ce qui se perd, et ce que l'écran en dit

**Arrêté sur** — 2026-09-17, `3e74dd8` : le SERVEUR du second temps est fait (`1d374ef`),
et prouvé par dix-sept mutations. Un enregistrement fait sur une valeur vue périmée rend un
409 qui nomme l'auteur ; l'annulation se garde de même ; écrire sur une région supprimée
rend un 410 nommé. L'ÉCRAN n'est pas codé : il attend le verdict de Hugo sur la maquette
(`https://claude.ai/artifact/GPW25ZTtoJSw7N7X2Vju3p`). **Ne pas pousser le serveur sans
l'écran** : `messageErreur` ne lit qu'un détail en chaîne, si bien que le 410 s'afficherait
« Échec mise à jour : Gone » là où l'Atelier dit aujourd'hui « Région N introuvable ».

**Point de départ** — 2026-09-16, une question de Hugo en tranchant le cache des dérivés
d'IMG-1 : « ça ne servirait pas d'avoir quelque part (niveau album ou collection) un moyen
d'actualiser s'il y a des changements ? » Pour les IMAGES, non : la route des dérivés rend
`no-cache` et un 304, donc le navigateur vérifie lui-même à chaque affichage. Or personne ne
saurait quand cliquer, puisqu'une régénération se fait sur le serveur, sans prévenir. La
question vise pourtant un vrai manque, qui touche les DONNÉES et non le cache. Aucun code
n'est écrit, et le chantier commence par une mesure.

## Reste

### Mesurer ce qui se perd, avant de choisir un remède
- [x] Deux navigateurs sous deux comptes en écriture, sur la même bulle. A sélectionne la bulle ; B la sélectionne, lui AJOUTE un tag et attend l'enregistrement ; A modifie alors la note et attend l'enregistrement. Attendu : on sait si le tag de B survit. Le journal A3 (`evenement`, avant/après) sert de preuve, et le résultat est écrit ici
- [x] Même décor, deux notes : A et B modifient la note de la même bulle à quelques secondes d'intervalle. Attendu : on sait laquelle reste, et si celle ou celui dont le texte a disparu en reçoit un signe à l'écran
- [x] Même décor en Transcription : A et B corrigent le texte de la même bulle. Attendu : on sait ce que montre l'écran de A une fois que B a enregistré, y compris après un changement de bulle puis un retour sur celle-ci
- [x] A supprime une case pendant que B la modifie. Attendu : on sait ce que B lit à l'écran quand son enregistrement tombe sur une case disparue (un 404 affiché tel quel, un message, ou rien)
- [x] Les quatre mesures rejouées sous le compte COLLECTIF d'AUTH-6, deux navigateurs sous le même login. Attendu : on sait si Ctrl+Z chez l'une défait l'acte de l'autre dans la fenêtre de cinq minutes

### Trancher la forme, sur les pertes mesurées
- [x] Écrit : le remède retenu, choisi parmi trois familles, ou « rien, et pourquoi ». Refuser un enregistrement fait sur une version périmée (409 qui nomme le conflit). Signaler que la planche a changé ailleurs, avec un geste pour actualiser. Réserver la bulle ou la planche à qui l'édite. Le choix s'appuie sur ce que la zone précédente a MESURÉ, pas sur l'hypothèse de départ — **tranché par Hugo le 2026-09-16, en deux temps** : (a) tout de suite, l'Atelier n'envoie que ce qui a changé ; (b) avant la prochaine mise en production, le refus d'une version périmée, par un 409 qui nomme le conflit. La réservation est écartée. Le Ctrl+Z collectif est une limite, écrite (cf. Contexte)
- [ ] Si l'écran change, la disposition se tranche sur une maquette interactive, pas sur de la prose

### Temps a — n'envoyer que ce qui a changé (tout de suite)
- [x] Enregistrer la NOTE d'une bulle n'envoie plus sa liste de tags, et ajouter ou retirer un TAG n'envoie plus sa note. Attendu : la mesure 1 rejouée à deux navigateurs garde le tag de B ET la note de A, prouvé par le journal A3 — fait par `5caa373`, et prouvé par l'état en BASE lu par l'API dans la garde e2e, non par une relecture du journal : c'est ce qui reste qui compte, et la base le dit plus directement
- [x] Ctrl+Z après une note ou un tag isolé ne rend que ce champ-là : il ne défait pas, par un instantané entier, le geste qu'une autre personne a fait sur l'autre champ entre-temps — `test_annuler_sa_note_ne_defait_pas_le_tag_de_l_autre`, sous deux identités, dans les deux sens
- [x] Une garde e2e à deux contextes rejoue la mesure 1, et elle est vue ROUGE sur le code d'avant le correctif — `tests/test_e2e_annotation_a_deux.py`, rouge sur `8a2a506` avec sept autres tests, et tuée par les deux mutants de l'écran (tout renvoyer, ne jamais marquer la note)

### Temps b — refuser un enregistrement fait sur une version périmée (avant la prochaine mise en production)
- [ ] Une note, un texte transcrit, ou la géométrie, le type ou le parent d'une région, enregistré avec une VALEUR VUE qui n'est plus celle de la base, est refusé par un 409 qui nomme qui a modifié et quand. La version est la valeur du champ, pas une colonne, pas le journal, pas une date (Q1). Attendu : les mesures 2 et 3 rejouées ne perdent plus rien en silence
- [x] Si le dernier changement du champ vient d'un MOTEUR (OCR qui remplit une bulle vide), l'enregistrement humain passe sans 409, et le texte du moteur reste au journal (Q2) — `test_un_texte_pose_par_un_moteur_ne_bloque_pas_l_humain`, `1d374ef`
- [x] Ajouter ou retirer un tag ne rend jamais de 409 : les différences commutent (Q3) — `test_les_tags_n_ont_pas_de_garde`, `1d374ef`
- [x] Annuler une modification de RÉGION ne rend que les champs que l'acte a changés, et refuse par un 409 nommé si ces champs ont changé depuis. Attendu : A déplace une bulle, B la transcrit, A fait Ctrl+Z — le texte de B reste. Le défaut est d'abord montré par un test ROUGE sur le code d'avant (Q4) — vu rouge sur `77c0dbb` (« annuler le déplacement de A a effacé le texte de B »), vert par `1d374ef`
- [x] Annuler une note refuse par un 409 nommé si la note n'est plus celle que l'acte avait posée, au lieu d'écraser celle écrite ensuite (cadrage (c), validé avec Q4) — `test_annuler_sa_note_modifiee_depuis_est_refuse`, `1d374ef`
- [ ] Écrire sur une case supprimée par quelqu'un d'autre rend un 410 « supprimée par X à HH:MM » quand on LIT sa planche, et le 404 inchangé sinon. L'écran de B dit qu'elle a été supprimée, et non « Région N introuvable », et la case disparaît de son écran (Q5)
- [ ] Au 409, un bandeau DANS le panneau (note, transcription) nomme l'auteur, montre sa version, garde la saisie en cours, suspend l'enregistrement automatique, et offre « Garder la mienne » et « Prendre la leur ». Sa forme est tranchée par Hugo sur une MAQUETTE INTERACTIVE avant que l'écran soit codé (Q6)
- [ ] L'auteur est nommé par son nom affiché, l'heure en heure locale ; quand l'auteur a le MÊME login que l'écran, le message dit « depuis un autre écran de ce même compte » (Q7)
- [ ] La valeur vue est FACULTATIVE pour l'API (outils, appelants existants) ; l'Atelier l'envoie toujours, et une garde e2e l'exige (Q8)
- [ ] Fait AVANT la prochaine fusion de `dev` dans `main` : les testeurs de la production travaillent à plusieurs

### Hors du temps b — écarté exprès le 2026-09-17, à rouvrir ailleurs (Q9)
- [ ] Locuteur, personnage et présence : deux personnes qui posent deux valeurs différentes sur la même bulle — mesuré à deux navigateurs, avec ce qui reste en base et ce que chaque écran en dit
- [ ] Corrections grammaticales : deux personnes qui corrigent le même token — mesuré de même, ou la fiche écrit pourquoi « le dernier gagne par token » suffit encore
- [ ] Attributs de situation d'une case : deux personnes sur le même attribut — mesuré de même
- [ ] Une région créée ou supprimée ailleurs (autre personne, passe automatique) apparaît ou disparaît sur une planche déjà ouverte sans rechargement — ou la fiche écrit pourquoi on s'en passe

## Contexte

**Ce qui a été LU, pas mesuré, le 2026-09-16.** C'est une hypothèse, et la première zone
existe pour la trancher.

- `PUT /api/regions/{id}` est PARTIEL côté serveur (`model_dump(exclude_unset=True)`), et
  l'Atelier n'y envoie que ce qui change : `{ ocr_texte }` en Transcription, les champs
  édités ailleurs. Deux personnes qui touchent deux champs différents d'une même case ne
  devraient donc pas s'écraser ; sur le même champ, le dernier enregistrement gagne.
- `PUT /api/regions/{id}/annotation` REMPLACE la note ET la liste des tags ensemble, et
  l'Atelier envoie `state.currentTags`, chargé au moment où la bulle a été SÉLECTIONNÉE
  (`loadAnnotation`). Un tag ajouté ailleurs entre cette sélection et l'enregistrement
  serait donc effacé en silence. C'est la perte la plus probable, et la seule qui touche un
  AUTRE champ que celui qu'on modifie. La fenêtre est étroite, bornée par le temps passé
  sur une bulle, mais le mode d'échec est muet.
- Les corrections grammaticales : `UNIQUE(region_id, ordre)`, donc le dernier écrit gagne
  par token, jugé « suffisant pour une petite équipe » dans
  `docs/correction-grammaticale.md`.
- L'Atelier charge les régions à l'ouverture d'une planche et ne les recharge plus. Le
  verrou de planche (`verrouillee`, `verrou_par`) est INFORMATIF : il protège des passes
  automatiques, pas d'une autre personne.

**Pourquoi maintenant, et pourquoi pas tout de suite.** Des gens testent la production :
le travail à plusieurs cesse d'être théorique. Mais le cap du moment est la gestion des
comptes (AUTH-12), et ce chantier se place APRÈS lui dans `docs/roadmap.md`. La mesure, en
revanche, ne coûte qu'une demi-heure sur la pile de recette, qui a déjà plusieurs comptes :
elle peut se faire avant, et dire si l'attente est tenable.

**Voisinage.** IMG-1 (le cache des dérivés, où la question est née, réglé par HTTP et hors
de ce chantier). AUTH-6 (le compte collectif utilisé SIMULTANÉMENT, que l'application ne
distinguera jamais). UX-5 (la granularité de l'annulation : un enregistrement toutes les
500 ms n'est pas un geste). CONC-1 et CONC-2 portent sur les lots ML, pas sur les
personnes.

**Mesuré le 2026-09-16 — la première zone.** Code servi : `6cdcbe4`. Aucun code de
l'application n'a été touché.

*Le décor.* Un serveur uvicorn LOCAL sur un clone du dépôt (`git clone --shared`, puis
`checkout 6cdcbe4`), données isolées dans `BD_DATA_DIR`, `BD_AUTH_PROXY=1`. Les identités
sont SIMULÉES par en-têtes (`Remote-User`), comme dans les tests derrière le proxy : pas
d'Authelia, pas de pile de recette. Chromium par Playwright, un contexte par personne,
chaque cas sur sa propre bulle. Les accès sont posés directement en base, niveau `ecriture` sur
la collection de l'album. Le compte collectif est déclaré par la vraie route (`PATCH
/api/comptes/collectif/nature`). Chaque enregistrement est ATTENDU à l'écran (« Enregistré »)
avant le geste suivant, et ce que chaque personne VOIT est relevé : champs, puces, toasts,
requêtes d'écriture et leurs codes. La preuve est le journal A3 (`evenement`, avant/après).

*Un instrument a menti, et c'est écrit parce qu'il aurait conclu à tort.* À la première
passe, la capture des toasts observait `document.documentElement` depuis le script
d'initialisation, où il n'existe pas encore : toutes les listes sont revenues vides, y compris
celle qui DEVAIT contenir « Région supprimée ». Sans ce témoin, on aurait écrit « aucun signe
à l'écran » partout. La seconde passe observe `document`, enveloppe aussi `window.toast`, et
vérifie le témoin : les deux instruments concordent. Les pertes, prouvées par le journal, sont
identiques d'une passe à l'autre.

*Les résultats — identiques sous deux comptes nominatifs et sous le compte collectif.*

1. **Le tag ajouté par B est effacé, sans un mot.** A et B sélectionnent la bulle ; B ajoute
   `tag-de-b` (`creation`, tags `["tag-de-b"]`) ; A tape une note, et son enregistrement
   (`modification`, 200) passe les tags de `["tag-de-b"]` à `[]`. Aucun toast, ni chez A ni
   chez B. L'écran de B montre ENCORE la puce `tag-de-b`, disparue en base. **L'hypothèse
   tient, et la perte va dans les DEUX sens.** Dans le contrôle qui la départage, B, restée
   sur la bulle, ajoute un second tag : son enregistrement remet `tag-de-b` mais efface la
   note « note de A » (`"note": ""`, la note chargée à SA sélection). Une A qui rouvre la
   bulle APRÈS l'enregistrement de B, elle, garde les deux tags. Ce n'est donc pas le serveur
   qui efface : c'est l'état chargé à la sélection que chaque enregistrement renvoie en entier,
   note ET tags.
2. **Deux notes : la dernière enregistrée reste, et la première n'en sait rien.** A écrit
   « note de A » ; trois secondes plus tard, B écrit « note de B » (`modification`, avant
   « note de A », après « note de B »). L'écran de A garde « note de A » et « Enregistré »,
   sans toast ni requête. Seul un rechargement lui montre « note de B ».
3. **Transcription : l'écran de A reste sur l'ancien texte, et sa saisie suivante écrase
   celle de B.** B corrige « TEXTE INITIAL » en « TEXTE DE B ». La zone de A montre encore
   « TEXTE INITIAL » — tout de suite, et après bulle suivante (`Tab`) puis retour
   (`Maj+Tab`) : le texte vient des régions chargées à l'ouverture de la planche. A ajoute
   « + A » : la base passe de « TEXTE DE B » à « TEXTE INITIAL + A » (journal, avant/après).
   Aucun toast, deux 200.
4. **Case supprimée pendant que B la modifie : B reçoit une erreur brute, et la case reste
   dessinée.** A supprime (`DELETE` 204, toast « Région supprimée »). B change sa coordonnée X :
   `PUT` 404, toast d'erreur « Échec mise à jour : Région 4 introuvable ». La case reste tracée
   sur l'écran de B, le champ X garde la valeur saisie. Le message ne dit pas que quelqu'un
   d'autre l'a supprimée.
5. **Ctrl+Z sous le compte COLLECTIF défait l'acte de l'autre navigateur.** A (navigateur 1)
   ajoute un tag ; B (navigateur 2, même login, aucun acte sur cette bulle) tape Ctrl+Z :
   toast « Annulé : ajout d'une annotation », `POST /api/undo` 200, événement `annulation`
   qui vise l'acte de A. L'écran de A montre encore la puce, sans toast. Sous deux comptes
   NOMINATIFS, le même geste répond « Rien à annuler. » (404) et le tag reste : le filtre par
   agent protège, le délai de cinq minutes ne sépare pas deux personnes sous un même login.

*Ce qui n'est pas mesuré.* Les délais réels d'un usage — ici quelques secondes entre deux
gestes, là où la fenêtre réelle est le temps passé sur une bulle. Authelia et la pile réelle
(les en-têtes sont simulés). Les corrections grammaticales et le panneau Personnage ou
Locuteur. Le changement de PLANCHE puis retour, qui recharge les régions (lu dans le code,
non joué). La forme du remède n'est pas tranchée : c'est la seconde zone, et elle est à Hugo.

**Tranché le 2026-09-16 — deux temps, et une limite écrite.** Les mesures 1 à 4 viennent de
deux causes distinctes, et c'est ce qui fait deux temps. La première ne demande aucun
écran : chaque enregistrement renvoie TOUT l'état chargé à la sélection, note ET tags, si
bien qu'un geste sur un champ efface l'autre champ d'autrui. N'envoyer que ce qui change la
ferme sans rien montrer de neuf (temps a). La seconde est le même champ touché par deux
personnes, ou une case disparue : là, il faut que le serveur SACHE que l'écran est périmé et
le dise, ce qui touche le message affiché (temps b). La réservation d'une bulle ou d'une
planche est écartée : elle ajoute un état à libérer, pour un conflit que le 409 suffit à
rendre visible.

La mesure 5 n'a pas de remède ici. L'application ne voit que `Remote-User`, et lui donner
de quoi séparer deux personnes sous un même login serait fabriquer de l'identité, ce
qu'AUTH-1 interdit — `docs/undo.md` le disait déjà (« dans les cinq minutes, deux personnes
sous le même login peuvent encore défaire l'une l'acte de l'autre »). Ce qui manquait était
côté USAGE : `docs/guide-utilisateur.md` laissait entendre qu'en deçà des cinq minutes, l'acte
annulé était le sien. Il le dit désormais.

**Le premier temps, fait le 2026-09-16 (`5caa373`).** Trois choix à connaître pour la suite.

- *Les tags partent en DIFFÉRENCES, pas en liste.* Envoyer la liste entière « quand seuls
  les tags ont changé » aurait fermé la perte entre note et tags, mais laissé deux personnes
  qui touchent chacune un tag DIFFÉRENT s'écraser : la liste de l'une ne connaît pas le tag
  de l'autre. `tags_ajoutes` et `tags_retires` s'appliquent à ce que la base porte. `tags`
  (la liste entière) reste accepté pour les appelants existants, et refusé en 422 s'il est
  mêlé aux différences.
- *L'annulation calcule son inverse sur l'état ACTUEL.* Restaurer l'instantané `avant`
  entier rendait la perte par un autre chemin : annuler sa note rendait la liste de tags
  d'avant. Seul, rien ne change : l'état actuel est alors celui d'après l'acte. Écrit dans
  `docs/undo.md`.
- *Un enregistrement qui ne change rien ne se journalise plus*, pour ne pas fabriquer un
  Ctrl+Z qui ne défait rien de visible.

**Éprouvé.** Suite par défaut et passe navigateur ENTIÈRES sur une copie de `5caa373` :
1279 et 240 verts. Neuf mutants joués sur une copie, tous tués, chacun par l'assertion qui
le vise. Un test passait sur l'ancienne route sans rien vérifier — elle ignorait
`tags_ajoutes`, donc l'annotation dont il vérifiait la disparition n'existait jamais — et a
reçu son témoin. Une passe de QA le rejoue à la main, à deux onglets :
`pilotage/qa/compte-retour-et-annotation.md`.

**Ce que le premier temps ne ferme pas**, et c'est le second : deux personnes sur la MÊME
note ou le même texte transcrit (le dernier gagne, sans rien dire), un tag retiré par l'une
pendant que l'autre le voit encore, et la case supprimée sous les yeux de quelqu'un.

*Rejouer.* Le script a vécu dans un scratchpad de session (`conc3/mesure_conc3.py`), qui ne
dure pas ; son protocole est ci-dessus, et il se réécrit avec trois précautions mesurées ce
jour-là. Un client HTTP local doit ignorer le proxy système (`httpx.Client(trust_env=False)`,
Chromium `--no-proxy-server`), sans quoi les requêtes n'atteignent jamais le serveur. La lecture
d'une région passe par `GET /api/planches/{id}/regions`, puisqu'il n'y a pas de
`GET /api/regions/{id}` (405). Et la capture des toasts se vérifie par un témoin positif.

**Tranché par Hugo le 2026-09-17 — le second temps.** Sur un cadrage proposé le même jour,
validé d'un bloc, questions Q1 à Q9 (cases ci-dessus).

- *La version vue est la VALEUR du champ* (Q1). Trois autres options ont été écartées, pour
  des défauts lus dans le code. Une colonne `version` exigerait que chaque écrivain
  l'incrémente — un oubli reste muet — et elle vaut pour la ligne entière : poser un tag
  périmerait la note de l'autre, et la zone « Deux onglets » de
  `qa/compte-retour-et-annotation.md` deviendrait un conflit, contre le temps a. Le dernier
  événement A3 manque les annulations, journalisées sur `evenement` et non sur la cible, et
  les régions qu'une re-passe automatique remplace sans événement. Une date de modification
  est à la seconde, quand l'enregistrement automatique part toutes les 500 ms. Comparer la
  valeur vue ne demande aucune migration, est précis au champ, et voit tout écrivain. Seul
  un aller-retour X→Y→X passe inaperçu, sans rien perdre. « Qui et quand » se cherche au
  journal ; sans trace, le message dit « modifié ailleurs ».
- *Un moteur ne gagne pas contre un humain* (Q2). L'OCR n'est qu'un pré-remplissage.
- *Les tags restent sans garde* (Q3). Seul cas silencieux, rare : ajouter un tag qu'on ne
  voyait pas pendant qu'un autre le retire.
- *L'annulation se garde aussi* (Q4). Défaut LU, pas mesuré : `undo._restaurer_region_cols`
  réécrit TOUTES les colonnes depuis `avant`, si bien qu'annuler un déplacement efface le
  texte transcrit ensuite par un autre. Même famille que le temps a, réparée dans ce temps.
- *Une suppression n'est pas gardée.* Son instantané profond est pris au moment de
  supprimer, donc il contient le travail de l'autre, et Ctrl+Z le rend. C'est l'écriture
  qui TOMBE sur une case disparue qui change : un 410 nommé (Q5), quand on lit la planche, et
  le 404 inchangé sinon, pour que rien ne fuie.
- *L'écran se tranche sur maquette* (Q6), avant d'être codé. Géométrie : la région se
  recharge avec un toast nommé. Case supprimée : toast nommé, et la région quitte l'écran.
- *Le compte collectif ne change que le MESSAGE* (Q7). La détection compare des valeurs, pas
  des identités ; aucune identité n'est fabriquée (AUTH-1). La mesure 5 reste une limite.

**Le serveur du second temps, fait le 2026-09-17** (`1d374ef`, `3e74dd8`). La comparaison et
la recherche de l'auteur vivent dans `conflit.py`, partagé par les routes et l'annulation, et
qui n'importe que `journal`.

- *Les contrats.* `PUT /api/regions/{id}` accepte `vu` (texte, géométrie, type, rattachement ;
  un autre champ rend 422). `PUT /api/regions/{id}/annotation` accepte `note_vue`. Tous deux
  sont facultatifs (Q8). Le 409 porte `detail.message` et `detail.conflit` (`champ`,
  `valeur_actuelle`, `auteur` : `nom`, `login`, `agent_type`, `meme_compte`, `le` en UTC). Le
  410 porte `detail.message` et `detail.suppression.auteur`.
- *Une extension, à faire valider par Hugo avec la maquette.* La garde de l'annulation refuse
  aussi d'annuler la CRÉATION d'une région qu'un autre a transcrite, annotée ou dans laquelle il
  a rattaché une région : la supprimer emporterait son travail sans instantané.
- *Ce que la relecture a trouvé avant et après le commit.* En mono-poste, le message aurait dit
  « modifié par None » (corrigé avant `1d374ef`). Et une garde n'était exercée par aucun test :
  un acte d'avant le proxy, sans login, contre une personne identifiée (`3e74dd8`).
- *Éprouvé.* Test de Q4 rouge d'abord, puis vert. Dix-sept mutations sur un clone de
  `1d374ef`, chacune rouge en échec d'assertion sur le test visé ; 22 tests dans
  `tests/test_conflit_version.py`. Tests voisins verts sous le `.venv` (annulation,
  annotation, autorisation, découpage de l'API, sorties d'identité, provenance, régressions).
  La suite entière et la passe navigateur attendent l'écran.
