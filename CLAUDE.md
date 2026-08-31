# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Langue

Tout le projet est en **français** : commentaires, docstrings, noms de fonctions/variables/routes/colonnes, UI, messages d'erreur, commits, docs. Écris dans le même registre — code, commentaires et messages de commit en français.

## Pilotage

Le suivi ticket-par-ticket vit dans `pilotage/`, lu par [`pilote`](https://github.com/Hsbtqemy/pilote)
(`npm run journal` → `localhost:4124`). Un chantier interrompu, différé ou à venir a un
fichier `pilotage/<CODE>.md` ; une QA visuelle est une passe rejouable dans
`pilotage/qa/<nom>.md`. Voir `pilotage/_TEMPLATE.md`. `docs/backlog.md` n'est plus qu'un
renvoi ; `docs/roadmap.md` reste la vue stratégique par pistes et n'est PAS remplacé.

IMPORTANT — respecter exactement `## Reste` et les H3 de zone : l'outil ne lit que ces
sections. Une case ailleurs est invisible (le contrôleur la signale en ERREUR).

- **Vocabulaire de codes : `PREFIXE-N`**, celui du backlog (`ANN-3`, `SEC-2`, `INFRA-1`,
  `A11Y-2`…). Décision arrêtée le 2026-08-27, et elle ne se rattrape pas : l'outil date un
  chantier en cherchant son code dans les sujets de commit. Les codes de piste de la
  roadmap (`A5`, `B3`, `C1`, `D1`) restent citables **en plus**, jamais à la place.
- **Le commit de code d'abord, le commit de fiche ensuite, séparément** : une fiche ne peut
  pas citer le commit qui la met à jour, et les commits qui ne touchent que `pilotage/` (ou
  `docs/`) sont exclus du datage.
- **Le commit de code doit CITER le code du chantier**, dans son sujet ou son corps. Sans
  citation : `0 commit`, aucune date, aucune barre sur la fresque, quel que soit le travail
  fait.
- Fin de session : mettre à jour le `Reste` du chantier travaillé, et son `**Arrêté sur**`
  (l'écran le signale décalé dès qu'il ne cite plus le dernier commit de code).
- `statut:` se prend dans `à venir` · `interrompu` · `différé` · `clos` · `livré` ·
  `abandonné`, et rien d'autre. `différé` = mis en attente exprès (autre chose doit aboutir
  d'abord) ; `interrompu` = arrêté en plein travail ; `abandonné` = décidé de ne pas le
  faire, la fiche gardant son `Reste` ouvert exprès plutôt que d'être supprimée avec son
  raisonnement.
- Une case = **une affirmation vérifiable, avec son attendu**. « Vérifier le rendu » se
  contemple ; « sur 375 px, la barre ne masque pas le geste » se coche.
- QA visuelle : écrire une passe dans `pilotage/qa/`, jamais dans le fil de conversation.
  **Ne jamais cocher soi-même une case d'une passe de QA** — la rédiger, la rendre, et
  laisser cocher.
- Ne pas créer de fiche pour un finding traité en un seul commit.
- Avant de clore une session : `npm run verifier` (code de retour non nul = l'outil lira
  mal le dossier).

Le journal se lance avec `--days 90` (dans le script npm) : l'historique du dépôt s'arrête
au 2026-07-19, et la fenêtre de 60 jours par défaut en couperait le début. Et sur
`--port 4124`, parce que le port par défaut (4123) sert le journal d'un autre dépôt sur
cette machine — un dépôt à la fois par port, c'est le modèle de l'outil.

## Vue d'ensemble

Outil de recherche pour annoter des bandes dessinées numérisées (corpus franco-belge). Aucune IA dans la boucle d'annotation : le travail interprétatif est 100 % humain ; les moteurs ML ne font que du **pré-remplissage éditable**. Auto-hébergé, traitement local, mono-utilisateur par défaut. **L'application n'authentifie personne** : elle fait confiance aux en-têtes d'identité posés par un proxy d'auth (Authelia), et seulement si `BD_AUTH_PROXY` déclare qu'il est bien devant — sans quoi tout acte reste anonyme (AUTH-1). Aucun secret en base : `utilisateur` (v22) n'est qu'un miroir d'affichage, et les groupes ne sont jamais stockés, relus dans `Remote-Groups` à chaque requête. **Elle AUTORISE en revanche** (AUTH-2, v23) : le cloisonnement par collection est à elle, Authelia ne dit que « qui ». Voir `docs/hebergement-securite.md`.

Backend **Python 3.12 / FastAPI** ; frontend **JavaScript/HTML/CSS vanilla** — aucun framework, **aucune étape de build**. On édite `static/*.js` et `templates/*.html` directement.

## Commandes

```bash
# Lancer (base + dossiers data créés au 1er démarrage)
uvicorn main:app --reload          # → http://127.0.0.1:8000 (API docs : /docs)

# Dépendances
pip install -r requirements.txt          # noyau (FastAPI, Pillow, httpx)
pip install -r requirements-dev.txt      # + pytest, playwright
pip install -r requirements-ocr.txt      # moteurs ML optionnels (bulles YOLOv8, EasyOCR)
pip install -r requirements-nlp.txt && python -m spacy download fr_core_news_sm  # NLP optionnel

# Kumiko (segmentation auto, optionnelle) — cloné à part, pas de requirements.txt
git clone https://github.com/njean42/kumiko.git lib/kumiko
pip install opencv-python-headless numpy requests
```

### Tests

```bash
pytest                       # suite par défaut (exclut e2e ; INCLUT le test `live` = serveur uvicorn en sous-processus)
pytest -m "not live"         # sans le test d'intégration sous-processus
pytest -m e2e                # E2E navigateur Playwright (nécessite : python -m playwright install chromium)
pytest tests/test_api.py::test_nom_du_test      # un seul test
pytest --cov=. --cov-report=term-missing        # couverture (dépend des moteurs optionnels installés)
```

- **Suite DANS l'image** (QA-5) : `docker build -f deploy/Dockerfile --target test -t bdediteur:suite . && docker run --rm bdediteur:suite`. Le venv local n'est PAS l'artefact livré — mesuré le 2026-08-27 : 451 tests verts en local, trois moteurs morts dans l'image le même jour. L'étape `runtime` reste sans outil de test.
- Le marqueur `e2e` est exclu par défaut via `pytest.ini` (`addopts = -m "not e2e"`).
- **Tests JS purs** (`static/lib/*.js`) : lancés par `tests/test_js_unit.py`, qui appelle `node --test tests/js/*.test.js`. Skippés proprement si Node absent. Pas de runner JS séparé.
- **Accessibilité** : `tests/test_e2e_a11y.py` (marqueur `e2e`) audite les 4 surfaces × thèmes (sombre/clair) via **axe-core** (WCAG 2.1 AA) et échoue à toute violation sérieuse/critique. axe est **vendu hors ligne** dans `tests/js/vendor/axe.min.js` (skip si absent — cf. son README).
- Les tests des moteurs ML (Kumiko, bulles, OCR) et du NLP se **skippent automatiquement** si le moteur n'est pas installé (`requires_kumiko` / `requires_bulles` / `requires_ocr` dans `tests/conftest.py`). La couverture mesurée en dépend (les routes `/api/analyse/*` + correction de tokens ne sont pas encore couvertes — QA-3, livré ; cf. `docs/roadmap.md`).

## Architecture

### Les quatre surfaces (pages)

Routes HTML servies par `main.py`, chacune avec son fichier JS et son template, partageant `static/style.css` et `static/theme.js` (thèmes clair/sombre + contraste élevé + zoom UI, et nav transverse + skip-link injectés sur les 4 pages) :

| Route | Template | JS | Rôle |
|---|---|---|---|
| `/` | `index.html` | `viewer.js` | **Visionneuse** : modes Édition / Annotation / Transcription / Navigation, arbre de structure, ShareDocs, deep-link |
| `/recherche` | `recherche.html` | `recherche.js` | **Recherche** FTS5 + nuage de tags |
| `/corpus` | `corpus.html` | `corpus.js` | **Bibliothèque** : CRUD albums/planches + lancement de lots |
| `/exploration` | `exploration.html` | `exploration.js` | **Exploration** linguistique du corpus — 4 vues : distribution (fréquences), **concordance KWIC** (aligné/liste, deep-link Visionneuse), **croisement 2D** (tableau de contingence facette×facette, heatmap, cellule→concordance), comparaison A/B ; + panneaux **📖 Lexique**, **🎯 Accord** (modèle↔humain) et **👥 Inter** (inter-annotateurs) |

`static/lib/` contient des modules **UMD réutilisables et testés sous Node** (pas d'accès DOM au chargement) : `nav.js` (navigation/round-trip entre surfaces) et `dialog.js` (modale accessible : piège à focus, Échap, retour du focus). Leur logique pure est verrouillée par `tests/js/*.test.js`.

### Données : tout en pixels MASTER

`albums → planches → regions` (arbre hiérarchique via `regions.parent_id`) `→ annotations → tags` (N-N). Les coordonnées `x,y,w,h` des régions sont **toujours en pixels master** (le scan haute résolution), indépendantes du dérivé web. La conversion master↔web se fait **côté frontend** : `web_scale = web_width / master_width`. Ne jamais stocker de coordonnées web.

Deux paliers de métadonnées descriptives (FAIR/dépôt, cf. `docs/dictionnaire-metadonnees.md`) : la **collection** (`collection` ↔ `collection_album` N-N, unité de dépôt, v14) regroupe des albums pour une étude ; la **paternité** N0 des albums vit dans `contribution` ↔ `contribution_role` (Zotero-like, rôle contrôlé-ouvert, v15), plus des colonnes d'édition (`date_edition`, `isbn`…). `albums.auteur`/`annee` restent *legacy*.

Le master TIFF va dans `corpus/`, un dérivé web JPEG à 25 % (`WEB_SCALE` dans `config.py`) dans `derivatives/` ; les deux dossiers sont gitignore.

### Autorisation par collection (AUTH-2, v23)

**Un seul endroit du code tranche « qui voit quoi » : `autorisation.py`.** Il répond
`Portee` — quelles collections en lecture, lesquelles en écriture — et tout le reste
consomme la réponse sans la recalculer. `main.py` expose la dépendance `portee_courante`
et n'y gagne que des lignes d'appel ; le découpage du fichier (ARCH-1) reste entier.

- **La collection est l'unité** (`collection_acces` : collection × principal × niveau).
  `principal` = un login OU un nom de groupe lu dans `Remote-Groups` — on stocke une
  RÉFÉRENCE au groupe, jamais une appartenance (invariant AUTH-1).
- **Trois niveaux qui s'empilent** (AUTH-3) : `lecture` · `ecriture` · `proprietaire`. Le
  cumul se fait dans `Portee.__init__`, une seule fois — un `in portee.ecriture` qui
  oublierait les propriétaires serait un refus silencieux et parfaitement crédible. La
  propriété est un NIVEAU et non une colonne : une seule source de vérité, et un GROUPE
  peut posséder (un espace de travail survit rarement au départ d'une personne).
  **`peut_administrer()` est distinct de `peut_ecrire()`** : écrire c'est annoter,
  posséder c'est décider qui d'autre entrera — un membre en écriture n'hérite pas du droit
  d'élargir le cercle. `bd-admins` passe outre, et c'est écrit : sans ce recours, le départ
  d'un propriétaire fabriquerait une collection définitivement bloquée. Deux états sont
  interdits en base et refusés par un **409 qui les nomme** : zéro propriétaire sur une
  collection, zéro collection pour un album. **Créer une collection exige une IDENTITÉ, pas
  un droit** (403 nommant la panne derrière le proxy) ; le nom `Collection par défaut` est
  **réservé** (se l'attribuer capturerait les albums créés sans collection explicite) ; et
  les changements d'accès sont **tracés au journal A3** (`lien`/`delien`, non annulables).
- **Aucun album hors collection** (`database.collection_par_defaut`) : un orphelin ne
  correspondrait à aucune règle, et il faudrait inventer une politique dans le code. La
  création d'album accepte `collection_id` et retombe sinon sur la collection de repli.
- **404, jamais 403** : « existe mais pas pour vous » révèle la composition du corpus.
  Corollaire d'ergonomie : une portée vide rend l'app indistinguable d'un corpus vide, d'où
  le bloc `acces` de `GET /api/moi` et le bandeau `.portee-vide` injecté par `theme.js`,
  qui distingue « aucun droit » de « aucune identité ne parvient » (forward_auth muet).
- **Un pouvoir inévitable, mais pas invisible** (AUTH-4, v25) : un administrateur lit et
  écrit toute collection **sans figurer** dans `collection_acces` — sa portée totale
  court-circuite la table. Ce n'est pas un défaut, c'est la vérité de tout auto-hébergement ;
  c'est son INVISIBILITÉ qu'on ferme. Le panneau des accès le DÉCLARE, en nommant les
  groupes lus dans `GET /api/moi` plutôt qu'une constante recopiée, et le bandeau de portée
  vide nomme enfin un destinataire — `BD_REFERENT_NOM` / `BD_REFERENT_CONTACT`, dans
  l'environnement et non en base, parce que c'est le seul référent qu'une portée VIDE
  puisse lire. **Un référent est une ADRESSE et non un droit** : le désigner est un geste
  de PROPRIÉTAIRE (`peut_administrer`, pas `peut_ecrire`), n'accorde rien et ne retire
  rien — `autorisation.py` n'entre pas dans le chantier, faute de quoi on aurait glissé
  vers le cloisonnement entre administrateurs, écarté. `collection.referent_nom` est
  DISTINCT de `responsables`, qui est scientifique, porte un ORCID et part au dépôt : un
  test vérifie que le référent ne sort d'AUCUN artefact (IIIF, crosswalk,
  `metadonnees_collection` JSON **et** CSV — deux chemins distincts du même outil).
  **Rien de tout cela en mono-poste** : sans proxy aucun groupe n'est lu, donc `acces.
  groupes_admin` est vide — nommer `bd-admins` là où l'on est seul distinguerait deux rôles
  qui n'en font qu'un.
- **Une garde d'interface se pose sur l'ACTE, jamais sur l'écran qui le contient.** Le
  serveur distingue sept questions (`peut_lire` / `peut_ecrire` / `peut_administrer`,
  `clause_album` / `clause_terme` / `peut_ecrire_terme` / `peut_ecrire_quelque_part`) ; le
  client n'en reçoit qu'une, `administrable`, et `peut_ecrire` ne traverse même pas — l'UI
  découvre un refus d'écriture en recevant son 403. Tant que cette asymétrie tient, tout ce
  qu'on ajoute dans un panneau gardé hérite de sa garde **par défaut et non par décision** :
  c'est ainsi que le référent d'AUTH-4, une simple ADRESSE, s'est retrouvé derrière la
  garde du PARTAGE, donc lisible du seul propriétaire — celui qui venait de l'écrire.
  L'erreur échoue en se FERMANT : elle ne casse aucun test, et une revue de sécurité
  l'approuve. C'est la même forme que la portée vide d'AUTH-2, « la bonne réponse de
  sécurité et la pire réponse d'usage ». Le cliquet de `test_autorisation.py` ne couvre pas
  ce cas : il exige qu'une ROUTE ait été tranchée, rien n'exige qu'un bloc d'écran dise
  quelle question il pose.
- **Sans `BD_AUTH_PROXY`, portée TOTALE** (mono-poste inchangé) ; **avec le drapeau mais
  sans identité, portée VIDE** — fermeture par défaut, panne bruyante plutôt que fuite.
- Trois accesseurs GARDÉS sont la seule façon d'atteindre un objet : `_get_album`,
  `_get_planche`, `_get_region`. La `Portee` y est un paramètre **obligatoire** : une
  valeur par défaut qui sauterait le contrôle rendrait l'oubli invisible.
- Les requêtes de LISTE filtrent par `portee.clause_album(alias)`. Deux cœurs partagés
  portent le filtre pour tout un pan de l'app : `_recherche_rows` (recherche + export CSV)
  et `_analyse_filtres` (distribution, concordance, croisement, comparaison).
- **Un terme n'est jamais plus GLOBAL que celui dont il dépend** (v24) : une dimension
  hérite de la portée de son domaine, une valeur de celle de sa dimension. Les routes de
  création ne posaient aucun `collection_id`, si bien qu'une valeur créée sous un axe privé
  naissait globale — et ce qui fuyait n'était pas le mot mais le NOM de l'axe, c'est-à-dire
  une grille d'analyse. Les lectures à plat filtrent le terme PARENT en plus du terme
  (bases antérieures) et la migration v24 recolle l'existant, sans quoi le « % défini »
  compterait un terme que les listes masquent.
- **Le VOCABULAIRE suit une autre règle**, et c'est voulu : `portee.clause_terme(alias)` —
  un tag / domaine / dimension / valeur est visible s'il est GLOBAL (`collection_id` NULL)
  ou local à une collection qu'on lit. C'est la portée d'appartenance du lexique situé
  (A4), pas celle des données. En revanche leurs COMPTEURS (fréquence, usages) sont
  filtrés comme des données : un nuage de tags doit refléter son sous-corpus. Le RÉSUMÉ
  « % défini » de `GET /api/lexique` se filtre comme ses quatre listes (`lexique_resume`
  reçoit un fragment de portée, pas une `Portee` : la règle reste écrite dans
  `autorisation.py` seulement).
- **VOIR n'est pas CHANGER, et les deux fonctions sont distinctes** : `clause_terme` dit ce
  qu'on voit, `peut_ecrire_terme(collection_id)` ce qu'on peut modifier (terme local →
  écrire dans SA collection ; terme global → écrire quelque part). Les accesseurs
  `_get_domaine` / `_get_dimension` / `_get_valeur` / `_get_personnage` prennent donc
  `ecriture=True` sur les routes d'écriture — 19 ne l'avaient pas au premier jet, avec une
  suite entièrement verte. Le refus d'écriture est un **403** sur un terme (il vient d'être
  listé, un 404 mentirait) et un **404** sur une donnée (l'absence ne fuit rien).
- **Deux portées dérivées** — un personnage se voit par ses APPARITIONS (`_clause_personnage` ;
  celui qui n'apparaît nulle part reste visible, sans quoi on ne pourrait plus en créer) ;
  l'annulation (Ctrl+Z) se filtre par AGENT et non par collection, parce que la cible d'une
  suppression n'existe plus — un filtre par album la rendrait inannulable.

**Le cliquet, et c'est la vraie protection** : `tests/test_autorisation.py` énumère les
routes de l'app — ET les MONTAGES, qui n'ont aucune dépendance — et exige que chacun ait
été tranché : soit il consulte la portée, soit il figure sur `HORS_PERIMETRE` /
`MONTAGES_AUTORISES` avec sa raison écrite. Absent des deux, la suite échoue. Il ferme la
porte de l'OUBLI, pas celle de l'erreur : il vérifie qu'une route consulte la portée,
jamais qu'elle en tire la bonne conclusion — d'où les tests de comportement, dont la
couverture est une liste et non une garantie.

Cf. `docs/hebergement-securite.md` (§6), dont la décision assumée : `GET /api/sauvegarde`
reste ouverte à tous et déverse la base entière.

### Droits de diffusion (DROIT-1) — citer n'est pas publier

`collection.statut_diffusion` (`public` | `embargo` | `restreint` | `prive`, v14) ne bordait
rien : il était déclaré, jamais respecté. Il devient opposable **à la sortie seulement**.

- **À l'intérieur de l'instance, il ne borde RIEN** (arbitrage 2026-08-28) : qui est admis
  sur une collection en reçoit tout, scans compris — l'annotation repose sur les images, et
  le travail interne relève de l'usage savant. Le cloisonnement entre équipes est l'affaire
  d'AUTH-2/AUTH-3.
- **PUBLIER** (manifeste IIIF) n'emporte d'images que d'une collection déclarée `public`, et
  **nommée** (`--collection`) : fail-closed, sans arbitrage à inventer pour un album vivant
  dans plusieurs collections. Le manifeste amputé le DÉCLARE (`requiredStatement`,
  `iiif_manifest.DECLARATION_SANS_IMAGES`) et `valider_iiif.py` n'exempte QUE sur cette
  déclaration — sinon « retenir » et « oublier » ses images deviendraient indistinguables.
  Les Canvas survivent sans image : la géométrie et l'enrichissement restent publiables,
  c'est le scénario de la piste A.
- **CITER** (`POST /api/figures`, cœur `figure.py`) n'est jamais bloqué par le régime : il
  l'ACCOMPAGNE. Le zip lie le crop à sa légende (référence `pl·c·b` dérivée, responsabilité,
  édition, licence, base légale — « non établie » quand c'est le cas) et à sa notice JSON.
  Les mentions sont CHOISIES par l'appelant (`champs`), dans l'ordre bibliographique de
  `figure.CHAMPS` et non celui de la demande. Le cloisonnement d'AUTH-2 s'applique
  entièrement : on ne cite que ce qu'on voit.
- **`GET /api/sauvegarde` est réservée aux administrateurs** : la condition de réouverture
  écrite le 2026-08-27 (« dès qu'un tiering de droits est effectif ») s'est déclenchée. Elle
  reste ENTIÈRE — une sauvegarde partielle ne restaure pas une instance — et change de
  public.
- **ShareDocs et Nakala ne sont pas du même côté**, malgré l'opérateur commun — l'axe est
  VIVANT / FIGÉ. **ShareDocs est le stockage vivant** : modifiable, appelable à tout moment,
  un espace de travail où les ressources vivent sans question de droits. Y déposer n'est pas
  publier, et le régime n'y borde rien ; ce qui réserve
  `POST /api/sharedocs/deposer-sauvegarde` aux administrateurs, c'est que sauvegarder est un
  geste d'exploitation et que l'app ne contrôle pas le partage du dossier d'arrivée — pas
  `statut_diffusion`. **Nakala est l'entrepôt du figé** : traité, nettoyé, déposé, il ne
  bouge plus. C'est là que la déclaration mord ; on y dépose d'abord le **manifeste et ses
  Canvas**, bien plus que les planches. Le manifeste sans images n'est donc pas un mode
  dégradé : c'est la forme NORMALE du dépôt, et la raison pour laquelle le Canvas devait
  survivre sans son image.
- **Ce qui est figé doit être DATÉ.** Deux dépôts du même album à un an d'intervalle seraient
  sinon indistinguables — et l'entrepôt garde les deux. Le manifeste était le seul artefact
  de la chaîne sans date (les notices posent `genere_le`, la figure `date_export`) : il porte
  désormais « Manifeste généré le ». Surtout, la **déclaration de droits** de son
  `requiredStatement` est datée (« Constat du … ») : figée, « régime : restreint »
  l'affirmerait encore une fois la collection passée `public`, et deviendrait fausse sans que
  personne mente.
- **`date_embargo` RETIENT, elle ne PROMEUT jamais** (`database.etat_embargo`, dérivé
  jamais stocké). Une collection `public` dont l'embargo court ne publie pas ses scans — la
  date est plus restrictive que le statut, donc elle gagne ; une échéance passée ne rend
  rien publiable toute seule, parce que l'outil ignore POURQUOI l'embargo existe (un délai
  qu'on s'est donné se lève seul, un délai imposé par un ayant droit non — et `base_legale`,
  qui trancherait, est vide par construction). La bascule appartient à l'entrepôt, à qui la
  date est transmise. Une date ILLISIBLE retient aussi : une faute de frappe ne doit ni
  ouvrir la porte ni passer pour une décision. Ne rien faire n'est pas se taire — l'échéance
  dépassée est signalée (écran Collections, manifeste, `gerer_collections.py` liste et
  fiche), sans
  quoi un corpus resterait fermé par inertie. **L'état est dérivé à UN seul endroit**, lu
  par l'écran et par l'export : deux lectures du même champ finiraient par se contredire.
- La **surcharge par album** annoncée dans le dictionnaire est abandonnée par écrit : depuis
  AUTH-3 un album vit dans plusieurs collections, il n'y a plus de défaut unique à
  surcharger. Cf. `docs/dictionnaire-metadonnees.md`.

### Recherche FTS5 — index maintenu explicitement

La table virtuelle FTS5 `recherche` est **dénormalisée** (agrège OCR + note + tags + lemmes). Elle est maintenue **à la main** via `database.reindex_region()` / `unindex_region()` appelés depuis l'API — **pas par des triggers** (la relation N-N tags les rendrait fragiles). Toute route qui modifie le texte/les tags/la note d'une région doit réindexer. Tokenizer `unicode61 remove_diacritics 2` → recherche insensible aux accents.

### Schéma & migrations

`database.py` : `SCHEMA_VERSION` (actuellement 24). À tout changement structurel : incrémenter et ajouter une étape dans `_migrate()` (gaté par `user_version` ; refus de rétrograder). Conventions :
- La table FTS est **séparée** du schéma (`_FTS_SQL`) pour pouvoir la **recréer en migration** (le tokenizer est figé à la création).
- Les **vues** (`_VIEWS_SQL`) sont **toujours DROP+CREATE** au démarrage : sans données, leur définition évolue gratuitement, sans migration.

### Couche NLP (spaCy) — OPTIONNELLE, deux paliers

`pipeline/nlp.py`. Sans spaCy/modèle, `nlp_available()` est False et tout retombe proprement sur la recherche préfixe + accents.
- **Palier A (lemmes)** : indexés dans FTS pour que « otage » trouve « otages ». Le lettrage BD étant en capitales, on **minuscule avant** analyse (sinon tout est pris pour des noms propres).
- **Palier B (grammaire)** : table `tokens` (un mot du dialogue : lemme, POS/UPOS, morph), **régénérée à chaque reindex**. La correction humaine vit dans `token_correction`, une couche **overlay JAMAIS touchée par le reindex**. La vue `tokens_effectifs` est le **read model canonique** (correction vivante ⊕ auto + provenance + `a_revoir`) : toutes les surfaces d'analyse lisent CECI, jamais `tokens` brut.
- Le modèle est configurable (`BD_SPACY_MODEL`, défaut `fr_core_news_sm`), chargé paresseusement sous verrou (non thread-safe). `tools/reindex_nlp.py` réindexe tout le corpus en lot après un changement de paramètre.
- **Rapport d'accord modèle↔humain (NLP-1)** : cœur `accord.py` (part des tokens RELUS où le modèle avait déjà la valeur finale — correction NULL = auto accepté, ou correction = auto — par champ lemme/POS/morpho + confusion POS ; miroir de `tokens_effectifs`, ignore les corrections obsolètes). Exposé par la route `GET /api/analyse/accord`, l'outil `tools/rapport_accord.py` (`--json`/`--csv`) et le panneau **🎯 Accord** de l'Exploration. Étalon de la transition Phase 1→2 (comparer `sm` vs `lg` sur le même corpus relu). Cf. `docs/rapport-accord.md`.
- **Le seul rapport d'analyse RÉSERVÉ** (AUTH-1) : `GET /api/analyse/accord-inter` répond
  **403** à qui n'écrit nulle part, et son périmètre suit les albums où l'on ÉCRIT. Les
  autres surfaces d'analyse portent sur le corpus ; celle-ci porte sur des PERSONNES —
  elle nomme, apparie et cite à la ligne près. Règle : *ceux qui voient la mesure sont ceux
  qu'elle mesure* (les propriétaires cumulent l'écriture). Au DÉPÔT, la fiche ne porte plus
  que `nb_auteurs` et des paires sans identités : la valeur FAIR (« relu à plusieurs,
  accord 0,87 ») ne demande aucun nom, et un entrepôt garde ses versions. L'outil CLI, lui,
  nomme toujours — sans les noms on ne peut pas réunir deux personnes pour arbitrer.
- **Accord INTER-annotateurs (ANN-5)** : cœur `accord_inter.py` — le modèle ne gardant qu'une correction/token, la donnée multi-auteurs vit dans le **journal A3** (`cible_id` stable = chaîne de révisions). Mesure l'**accord de révision** (un auteur re-touche le token d'un autre → garde/change), par champ + par paire + points de divergence cités. Route `GET /api/analyse/accord-inter`, outil `tools/rapport_accord_inter.py`, panneau **👥 Inter**. Rare avant le multi-utilisateur (piste C). Cf. `docs/accord-inter.md`.

### Pipeline de reconnaissance — 3 passes, moteurs OPTIONNELS

`pipeline/` : `ingest.py` (image → dérivé + métadonnées), puis 3 passes ML : `segmentation.py` (passe 1, cases, **Kumiko** en sous-processus), `bulles.py` (passe 2, **ogkalu YOLOv8**), `ocr.py` (passe 3, **EasyOCR** fr). `ordering.py` recalcule l'ordre de lecture (rangées haut→bas, gauche→droite ; bulles groupées par case) après chaque passe.

Invariants :
- Chaque moteur est **optionnel** : si non installé, sa route renvoie **503** ; `GET /api/sante` indique la disponibilité de chacun.
- **L'OCR ne fait que pré-remplir** (`only_empty=True`) : il **n'écrase jamais** une correction humaine.
- `pipeline/jobs.py` : traitement **par lot en arrière-plan** (`threading`, worker sérialisé, multi-albums) avec progression et annulation. Sérialisé par un `ML_LOCK`.

### Journal de provenance / audit (A3, v16)

`journal.py` : couche **append-only** qui qualifie *qui a produit quoi* sans inverser la base. `activite` = un **run** (passe ML, ou session) ; `evenement` = un **acte** atomique immuable (avant/après JSON). Les passes ML sont enveloppées par `journal.passe_ml` (diff des régions → `regions.activite_id` = wasGeneratedBy + événements, **sans coupler** le code pipeline) ; les routes humaines journalisent leurs actes (l'**agent** vient de l'auth via le contextvar `agent_courant`, alimenté par une dépendance FastAPI globale — pas de `request` à threader). `evenement.cible_id` **n'est pas une FK** : le journal **survit à la suppression** de sa cible (substrat de l'undo **D1**) ; les actes d'annotation ciblent le `region_id` (stable), pas l'id d'annotation. Indicateurs dérivés (`indicateurs_provenance`) dans les exports ; sérialisation **PROV-O / TEI** par `tools/provenance_export.py`. Cf. `docs/provenance-audit.md`.

### Annulation (undo, D1)

`undo.py` : **remonte le journal A3** pour rejouer l'INVERSE de la dernière action d'annotation. Le journal EST l'historique (pas de pile ; append-only préservé) : annuler = exécuter l'inverse + ajouter un événement `annulation` (`cible_table='evenement'`, `cible_id`=l'acte annulé) ; la « dernière action annulable » = l'événement **humain** le plus récent, d'un type annulable, non déjà référencé par une annulation → `Ctrl+Z` répété remonte la pile. Inversions en mutations **brutes** (+ réindex FTS), **hors routes** (sinon rejournalisation) ; un seul `annulation` par undo ; atomique (rollback si échec). Périmètre : région (créer/modifier/supprimer+**cascade** recréée depuis l'instantané profond, mêmes `id`), annotation (note+tags), locuteur, présence ; actes **machine non annulables**. `GET /api/undo/prochain` + `POST /api/undo` (404 si rien, 409 si `id` réattribué) ; **UI Ctrl+Z** dans la Visionneuse. Dormant : grammaire/validation, **redo**. Cf. `docs/undo.md`.

### Lexique situé (A4, v17)

Couche définitionnelle **SKOS** sur le vocabulaire ÉMERGENT (dimensions, valeurs **et** tags — le même patron « contrôlé-mais-ouvert »). Chaque terme porte `definition` (pour un tag, sa `description` legacy EST la définition), `note_portee` (SKOS `scopeNote` = le « situé »), `etat` (`provisoire`→`defini`, miroir `auto→validé`) et `collection_id` (**portée d'appartenance** : NULL = global, sinon local ; promotion → NULL via `ON DELETE SET NULL`, patron *mentions→entités*). Édition : `PATCH /api/attributs/{dimensions,valeurs}/{id}/lexique` + `PATCH /api/tags/{id}/lexique` (partielle) ; `GET /api/lexique` (read model + **% défini** via `database.lexique_resume`). UI : bouton **📖 Lexique** sur Exploration → modale accessible (`dialog.js`). Exporté en SKOS (records + paradonnée). Cf. `docs/lexique-situe.md`.

### Alignement d'autorité (A5, v18)

Relie une **entité personnage** à des référentiels externes (`personnage_alignement` : personnage → 0..N URI Wikidata/VIAF/IdRef…, chacune un `skos:exactMatch`). `source` **auto-détectée** depuis l'hôte de l'URI (contrôlé-ouvert ; NULL si inconnu). `CASCADE` à la suppression ; la **fusion** de personnages recolle les alignements (dédup par URI). Édition : `GET/POST/DELETE /api/personnages/{id}/alignements` + UI dans le **panneau Personnage** de la Visionneuse (puces-liens + ajout d'URI, atteignable via locuteur ET boîte personnage). Export : `personnages.alignements[]` + table CSV + indicateur `% aligné`. Les **contributeurs** restent hors périmètre (chaînes non-entités → promotion requise d'abord, dormant). Cf. `docs/alignement-autorite.md`.

### Domaines analytiques (piste B, v20)

Palier `domaine` qui **regroupe les dimensions facettées** par champ analytique (émotions, représentation…) — les émotions ne sont **qu'un domaine**, pas un module figé. Table `domaine` (émergent, **même couche lexique SKOS** que dimensions/valeurs/tags) + `attribut_dimension.domaine_id` (**NULL = hors domaine**). **ORTHOGONAL à `cible`** : un domaine peut grouper des dimensions personnage ET case. Suppression d'un domaine → `domaine_id` NULL (`ON DELETE SET NULL`, promotion). API : `GET/POST/PATCH/DELETE /api/domaines` + `PATCH /api/domaines/{id}/lexique` + `PATCH /api/attributs/dimensions/{id}/domaine`. `GET /api/lexique` renvoie `domaines` + le `domaine_id` des dimensions. UI : dans le panneau **📖 Lexique**, dimensions regroupées sous leur domaine (+ sélecteur). Export : records + CSV + roll-up (% défini inclut les domaines). **Amorçage en lot** du vocabulaire (domaines → dimensions → valeurs + lexique) depuis un tableur CSV point-virgule : cœur partagé `lexique_import.py` (parsing + upsert **pré-remplir sans écraser** comme l'OCR, idempotent, portée = `collection_id`), exposé par **deux minces enveloppes** — CLI `tools/importer_vocabulaire.py` (`--collection`, `--dry-run` ; modèle `tools/vocabulaire-modele.csv`) et route `POST /api/lexique/importer` (bouton **Importer** du panneau 📖 Lexique). Cf. `docs/import-vocabulaire.md`. Différé (dormant) : nouveaux **types d'ancre** (planche/album/scène = nouvelle jointure). Cf. `docs/domaines.md`.

### Matériel de numérisation (A6, v19)

Consigne le matériel de scan des planches. `pipeline/ingest.read_metadata()` lisait déjà la résolution et le mode via Pillow mais les **jetait** ; désormais l'ingest **persiste** `planches.dpi_x`/`dpi_y`/`mode` (auto, lecture seule — un fait matériel du fichier). Les **dimensions physiques (cm)** sont **DÉRIVÉES** (`database.dimensions_cm` : px÷dpi, jamais stockées, même doctrine que le numéro éditorial). `albums.source_numerisation` (appareil/conditions, humain) vit au niveau **album** (campagne de scan = album, à côté de `format_physique`). Backfill des planches pré-v19 : `tools/reindex_materiel.py` (re-lit les masters ; `--force`/`--dry-run`). UI : champ source dans le formulaire album (Bibliothèque) + résolution/mode/cm affichés par planche. Export : records planche + album, tables CSV, roll-up `couverture.planches.materiel` (`% avec résolution`, modes). Cf. `docs/materiel-numerisation.md`.

### Concurrence SQLite

Fichier unique, mode **WAL**, `foreign_keys=ON` + `ON DELETE CASCADE`, `busy_timeout=5000`. Un job ML de fond peut entrer en contention avec une requête : `main.py` a un `@app.exception_handler(sqlite3.OperationalError)` qui transforme un « database is locked/busy » en **409** explicite (réessayer) plutôt qu'un 500. Le chargement à froid de spaCy (~10 s) doit se faire **hors transaction d'écriture** (`nlp.ensure_loaded()` / `prewarm()`), sinon il bloque les écritures concurrentes.

### Chemins : code vs données (`config.py`)

Les chemins de **code** (`static/`, `templates/`, `lib/kumiko`) sont relatifs au dépôt (`BASE_DIR`). Les chemins de **données** dérivent de `DATA_DIR`, **configurable** :
- `BD_DATA_DIR` : racine de `corpus/` + `derivatives/` + base (défaut : le dépôt). Un chemin relatif est résolu contre le dépôt, pas contre le CWD.
- `BD_DB_PATH` : chemin explicite de la base SQLite.

Ces variables servent à isoler les tests (`tests/conftest.py` les patche ou lance un serveur isolé) et à déployer les données ailleurs que dans le dépôt.

### Numérotation éditoriale & citation

Une planche a un `role` (`recit` = narrative/numérotée ; sinon paratexte, écarté de la numérotation). Le **numéro éditorial est DÉRIVÉ, jamais stocké** (`database.numeros_editoriaux()` : rang parmi les planches `recit`). Les citations `pl·c` / `pl·c·b` sont aussi dérivées (`citations_regions()`). Voir `docs/numerotation-et-citation.md`.

### Statut de relecture par planche (ANN-4, v21)

Statut de **relecture grammaticale** (`à faire` / `en cours` / `faite`), **orthogonal** à `statut` (pipeline) et `validee` (validation binaire). **DÉRIVÉ jamais stocké** (`database.relecture_planches()` : relus = tokens `corrigé`|`validé` via `tokens_effectifs` ; 0 relu → `à faire`, partiel → `en cours`, tous relus → `faite`) ; seul l'**override** est stocké (`planches.relecture`, NULL = suivre le dérivé). `GET /api/albums/{id}/planches` renvoie `relecture_statut` ; `PATCH /api/planches/{id}/relecture` force/libère. UI Bibliothèque : pastille (couleur renforçante, libellé porteur) + sélecteur d'override + filtre. Cf. `docs/relecture.md`.

### ShareDocs (WebDAV)

`pipeline/sharedocs.py` : client WebDAV (RFC 4918) pour ShareDocs Huma-Num — `PROPFIND` / `GET` / `PUT`, Basic Auth. Les identifiants restent **en mémoire serveur uniquement, jamais sur disque**. Les tests le simulent via httpx `MockTransport` (aucun réseau réel).

**Deux sortes de sessions (SHARE-1)**, et c'est la décision : les deux, pas l'une ou l'autre.

- La session d'**INSTANCE** (`BD_SHAREDOCS_URL/USER/PASS`) est vivante **dès le démarrage**, sans que personne ne clique — sinon elle ne sert de repli à personne. Non validée au chargement (un PROPFIND ferait dépendre le boot d'Huma-Num). La **couper ou la remplacer est réservé aux administrateurs** : sans cette garde, la première personne qui clique « déconnexion » prive tout le monde du repli. Coupée, elle ne repart pas de l'env (sinon la couper n'aurait aucun effet).
- Les sessions **PERSONNELLES**, une par principal. Résolution : **la mienne si j'en ai une, celle de l'instance sinon** ; forcer un compte absent est une **erreur nommée**, jamais un repli silencieux. `GET /api/sharedocs/etat` dit lequel répondrait (`actif`), et le compte se **choisit** à l'écran — le sélecteur gouverne tout le panneau, pas seulement le dépôt.
- **Le module ne sait RIEN du proxy** : il range des identifiants sous la clé qu'on lui donne, et `principal` est un paramètre **obligatoire** (keyword-only sans défaut) — un défaut ferait retomber un appelant distrait sur le compte de l'instance, ce qui marcherait parfaitement et déposerait sous le mauvais compte. Qui est « je » se décide dans `main._principal_sharedocs` : emplacement unique **hors proxy** (mono-poste inchangé), le login derrière le proxy, et **aucune session personnelle sans identité** (fermeture par défaut, comme la portée vide d'AUTH-2).
- **Le dépôt de sauvegarde est journalisé** (A3, `cible_table='sharedocs'`, invisible à l'undo dont la liste de tables est blanche) et l'événement distingue **la personne qui a cliqué** du **compte Huma-Num employé**.

### Sauvegarde

`pipeline/backup.py` : snapshot SQLite cohérent par `VACUUM INTO` → zip horodaté. Téléchargeable (`/api/sauvegarde`) ou déposable sur ShareDocs.

## Conventions de code

- **Routes API** : préfixe `/api/`, verbes/noms en français (`/api/planches/{id}/segmenter`, `/deplacer`, `/reordonner`). Pages HTML sans préfixe.
- Pas de cache sur les assets : un middleware force `Cache-Control: no-cache` sur `/static` et les pages, car le navigateur intégré d'un IDE sert sinon des CSS/JS périmés.
- Export disponible en **JSON-LD / CSV / TEI P5** (`main.py`, routes `/api/export/*`). Texte libre assaini avant sérialisation : `_xml_safe` (retire les caractères interdits XML 1.0 → TEI re-parsable) et `_csv_safe` (préfixe `'` une cellule débutant par `= + - @` → anti-injection de formule tableur).
- `tests/test_regressions.py` : un test de non-régression par bug corrigé.
- **Accessibilité (WCAG 2.1 AA)** : les accents pleins `--accent-*` servent les fills / bordures / marqueurs (seuil graphique 3:1) ; pour du **petit texte** coloré, utiliser les tokens d'encre AA-sûrs (`--ink-red`, `--danger`, ou un accent **assombri** en thème clair) — **jamais l'accent brut**, qui échoue le 4.5:1. L'audit axe (`pytest -m e2e`) verrouille la non-régression.
- `docs/` documente les décisions de conception non évidentes (grammaire, numérotation, round-trip, sécurité, Docker) ; `pilotage/` est le **suivi vivant** ticket-par-ticket (une fiche par chantier, cf. § Pilotage ; `docs/backlog.md` n'en est plus que le renvoi), `docs/roadmap.md` la **vue stratégique par pistes** (cap + ordre conseillé), `AUDIT.md` l'audit technique daté. `spike/` et `tools/` sont hors couverture (`.coveragerc`). L'**export de métadonnées** (description du corpus + IIIF ; scripts hors-app `tools/gerer_collections.py` — gestion des collections, seul outil d'écriture —, `description_collection.py`, `metadonnees_collection.py`, `iiif_manifest.py`, `valider_iiif.py`) est documenté dans `docs/export-metadonnees.md`.
