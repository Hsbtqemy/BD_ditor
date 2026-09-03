# Audit technique — BéDéditeur

*Audit réalisé le 13 juin 2026 · périmètre : backend FastAPI, pipeline, frontend vanilla, tests.*

> **CE DOCUMENT EST UN JOURNAL DE CAMPAGNE, PAS UN SUIVI VIVANT** (constat du 2026-09-01).
> Cinq passes menées le 13 juin, plus des mises à jour. Le suivi ticket-par-ticket vit
> désormais dans `pilotage/` — voir `AUDIT-1` (les reliquats) et `AUDIT-2` (les mineurs).
>
> Il se lisait faux, et c'était structurel : les CLÔTURES sont consignées dans des blocs de
> passe ULTÉRIEURS, jamais sur le constat lui-même. Une lecture de haut en bas montrait donc
> `🔴 P1`, `🔴 T1`, `🔴 G1`, `🟠 G2` comme ouverts alors que le document déclare plus bas leur
> correction. Chaque constat porte maintenant son état là où on le lit.
>
> **`npm run verifier` ne sait pas compter ces constats, et l'affiche « INCONNU ».** Ce n'est
> pas un défaut de l'outil : `journal-contrat.mjs` ne reconnaît qu'un code de forme
> `[A-Z]{1,5}-\d+`, en ligne de tableau ou en titre. Les codes d'ici — `P1`, `T2`, `S1`,
> `G1`, `B6`, `O1` — n'ont pas de tiret. Renuméroter fermerait cet angle mort ; ç'a été
> écarté le 2026-09-01, parce que tous les renvois existants (fiches `pilotage/`, messages de
> commit déjà poussés) casseraient pour un gain d'affichage.

> **Tous les renvois `main.py:NNN` de ce document sont CADUCS depuis le 2026-09-03**
> (ARCH-1). `main.py` est passé de 4 483 à 1 811 lignes : le socle partagé vit dans
> `socle.py`, et sept domaines dans `routes/`. Un renvoi qui tombe encore dans le fichier
> est le plus trompeur des deux — il désigne du code sans rapport, et rien ne l'annonce.
>
> Ils ne sont pas corrigés, et c'est délibéré : ce document est un JOURNAL DE CAMPAGNE
> (cf. l'encadré ci-dessus), il consigne ce qui a été vu en juin. Le suivi vivant est dans
> `pilotage/`, dont les cinq pointeurs `main.py` ont été repointés le même jour — ceux-là
> servent à agir. Se fier ici au NOM du symbole cité, jamais au numéro.

> **État vérifié CONTRE LE CODE le 2026-09-01**, et non recopié des blocs de clôture — trois
> mois, `v14 → v25` et cinq gros chantiers ont passé dessus.
>
> **Fermé depuis** : auto-référence CSS (P1), coordonnées NULL (P1), modèles ML non protégés
> (`ML_LOCK`), SSRF/HTTPS ShareDocs (`_check_url`), `Image.MAX_IMAGE_PIXELS` désormais borné
> par `config.MAX_IMAGE_PIXELS`, XSS résiduels (plus aucune interpolation hors `esc()` /
> `textContent` / `confirm()`), duplication frontend (`static/lib/common.js`), T1, G1, G2.
>
> **Encore vrai** : verrou de crop trop large (`ocr.py`, il englobe crop + resize + encodage),
> `COALESCE(MAX(numero),0)+1` en course à DEUX endroits (`ingest.py:37`, `main.py:800`),
> registre de jobs en RAM non purgé, versions non épinglées (aucun `==` dans
> `requirements.txt` — cf. QA-4), concurrence non testée, CSRF (cf. SEC-2, zone en attente
> d'INFRA-1).
>
> **Tombés à l'examen** — et c'est le résultat le plus utile de cette relecture : sur les
> trois constats de segmentation encore ouverts, AUCUN n'était un bug. `O1` était réfuté (la
> bonne crainte, le mauvais coupable : le `min()` qu'il accuse est ce qui empêche la dérive),
> `S1/S5` n'est pas reproductible dans le scénario qu'il décrit, `S6` est conforme. Détail et
> mesures dans `pilotage/AUDIT-1.md`.

> **Mise à jour 2026-06-23.** Corrigés depuis l'audit : verrou d'inférence ML global
> (`jobs.ML_LOCK`, routes directes *et* worker), nettoyage du master en cas d'échec
> d'ingestion, échappement des labels de tags, borne explicite `BD_MAX_IMAGE_PIXELS`,
> courses recherche/jobs (C3/C4/A1/B1/E1), accessibilité clavier + **contrastes AA**
> (audit axe-core câblé : `tests/test_e2e_a11y.py`). **Restent ouverts**, désormais
> suivis dans `docs/backlog.md` §7 : SSRF/HTTPS ShareDocs, `UNIQUE(album_id, numero)`,
> cache de crop + purge des jobs + annulation préemptive, préservation segmentation
> (S2/S3/S7/S4), épinglage des versions, dédup front (`common.js`), tests de concurrence.

## Verdict global

Projet **mûr, cohérent et soigné** pour un outil de recherche auto-hébergé mono-utilisateur. L'architecture est lisible, le découplage backend/pipeline/frontend est net, la documentation (README) est exemplaire et la philosophie « aucune IA dans la boucle d'annotation, l'OCR n'est qu'un pré-remplissage » est tenue de bout en bout dans le code (`only_empty=True`, préservation du travail humain à la re-segmentation).

Les faiblesses ne remettent pas en cause le produit : elles concernent surtout la **robustesse sous concurrence** (le design est explicitement threadé mais la synchronisation est implicite), quelques **bugs réels mais localisés** (un bug CSS visible, des `TypeError` possibles sur régions à coordonnées nulles), et la **reproductibilité** (aucune version épinglée). Aucune faille critique exploitable dans le modèle mono-poste local visé.

| Axe | Note | Synthèse |
|---|---|---|
| Architecture & lisibilité | ★★★★★ | Découplage clair, commentaires de qualité, conventions stables |
| Robustesse / concurrence | ★★★☆☆ | Threads + WAL, mais synchro implicite (GIL), modèles ML non protégés |
| Sécurité | ★★★★☆ | Très bon pour le modèle local ; angles morts ShareDocs (HTTPS, traversal) |
| Tests | ★★★★☆ | Isolation exemplaire, assertions réelles ; concurrence sous-testée, « 100 % » conditionnel |
| Frontend | ★★★★☆ | Accessibilité réelle, état bien géré ; 1 bug CSS, XSS résiduels, duplication |
| Reproductibilité | ★★☆☆☆ | Aucun pin de version, pas de lockfile, deps Kumiko hors `requirements` |

---

## Forces

1. **Architecture claire et étanche.** `main.py` (routes) → `pipeline/*` (métier) → `database.py` (SQLite/FTS) → `config.py` (chemins/constantes). Chaque module a une responsabilité unique. Les chemins de données sont configurables par variables d'environnement (`BD_DATA_DIR`, `BD_DB_PATH`), ce qui isole proprement les tests du dépôt.

2. **Le choix « pas d'IA décisionnelle » est réellement implémenté.** `ocr_planche(only_empty=True)` n'écrase jamais une correction humaine ; à la re-segmentation/re-détection, les cases annotées et les bulles non vides sont préservées et les annotations transférées par recouvrement maximal ([pipeline/segmentation.py:194-247](pipeline/segmentation.py#L194-L247), [pipeline/bulles.py:107-143](pipeline/bulles.py#L107-L143)). C'est la partie la plus délicate du code et elle est bien traitée et bien testée.

3. **Persistance et cohérence soignées.** Connexion par requête avec **commit explicite dans chaque route d'écriture** — le commentaire de [main.py:51-66](main.py#L51-L66) documente la course écriture→lecture qu'a posée le commit post-`yield` de FastAPI : bug réel, compris et corrigé. Sauvegarde par `VACUUM INTO` ([pipeline/backup.py:27](pipeline/backup.py#L27)) → snapshot cohérent indépendant du WAL, bien meilleur qu'une copie brute.

4. **Index FTS5 maintenu explicitement** plutôt que par triggers (justifié par la relation N-N tags), avec désindexation manuelle là où le `CASCADE` SQL ne touche pas la table FTS ([main.py:264-268](main.py#L264-L268), [main.py:477-488](main.py#L477-L488)). Le piège est identifié et traité.

5. **Secrets ShareDocs en RAM uniquement**, jamais sur disque, jamais renvoyés au client, mot de passe exclu du pré-remplissage ([pipeline/sharedocs.py:112-115](pipeline/sharedocs.py#L112-L115)). Bonne hygiène.

6. **Frontend accessible pour du vanilla** : `:focus-visible` cohérent, respect de `prefers-reduced-motion` et `prefers-color-scheme`, thème appliqué avant rendu (anti-FOUC), `aria-label` synchronisés. Sauvegarde auto débouncée avec *flush* avant chaque transition (planche/mode/sélection) — on ne perd pas une annotation en attente.

7. **Tests à l'isolation exemplaire** : base jetable + dossiers sous `tmp_path`, frontières de mock bien placées (on mocke le moteur ML / le réseau / le subprocess, pas la logique métier), chemins d'erreur HTTP couverts systématiquement, et un vrai test d'intégration uvicorn (`test_live_coherence.py`) qui capture une classe de bug invisible au `TestClient`.

---

## Faiblesses & bugs (par priorité)

### ✅ P1 — Bugs réels, correction simple — **LES TROIS FERMÉS**

*Vérifié contre le code le 2026-09-01 : plus d'auto-référence dans `style.css` ; `reading_order` traite les coordonnées NULL comme 0 (`_y`/`_x`) ; `run_kumiko` lève `KumikoError` sur une liste vide comme sur une taille malformée (`segmentation.py:96` et `:233`).*

- **Bug CSS : modales sans voile et survols invisibles en thème sombre (défaut).**
  [static/style.css:23-24](static/style.css#L23-L24) :
  ```css
  --hover:  var(--hover);   /* auto-référence → invalide → unset */
  --scrim:  var(--scrim);   /* idem */
  ```
  Ces deux tokens ne sont définis pour de vrai que dans le thème *clair* ([style.css:66-67](static/style.css#L66-L67)). En mode sombre ils se résolvent à `unset` : le fond de modale (`#album-modal`, `#sharedocs`) est **transparent** et le survol des modes/nœuds d'arbre n'a aucun fond. **Correctif** : donner de vraies valeurs sombres, p. ex. `--hover: rgba(255,255,255,.06); --scrim: rgba(0,0,0,.55);`.

- **`TypeError` sur régions à coordonnées NULL.** `reading_order`, `_reattach_orphans`, `_best_overlap`, `_parent_case` supposent `x/y/w/h` non nuls ([pipeline/ordering.py:29-36](pipeline/ordering.py#L29-L36), [pipeline/segmentation.py:106-125](pipeline/segmentation.py#L106-L125), [pipeline/bulles.py:60-67](pipeline/bulles.py#L60-L67)). Or une région *manuelle* peut être créée avec `x=y=w=h=0` (défauts Pydantic) puis modifiée partiellement. Un `None <= float` lève une exception non gérée (500 brut). **Correctif** : `COALESCE`/`or 0` systématique sur les bornes, pas seulement sur le centre.

- **Edge cases Kumiko non convertis en `KumikoError`.** `data[0]` sur une liste vide et `size[1]` sur une taille à un élément lèvent `IndexError` non capturé ([pipeline/segmentation.py:86](pipeline/segmentation.py#L86), [pipeline/segmentation.py:188](pipeline/segmentation.py#L188)) → 500 opaque au lieu d'un message clair.

### 🟠 P2 — Concurrence & ressources — **2 ouverts sur 5** au 2026-09-01

*Restent : le verrou de crop trop large, et le registre de jobs (RAM, non purgé — un process tué emporte le lot sans laisser de trace, cf. `pilotage/CONC-2.md`).*

- ✅ **FERMÉ** (CONC-2 v1 : `jobs.ML_LOCK` sérialise worker ET routes directes) — ~~**Modèles ML globaux non protégés, partagés entre worker batch et routes directes.**~~ `bulles._model` et `ocr._reader` sont des singletons chargés paresseusement **sans verrou** ([pipeline/bulles.py:35-46](pipeline/bulles.py#L35-L46), [pipeline/ocr.py:36-48](pipeline/ocr.py#L36-L48)). Le `_run_lock` de `jobs.py` sérialise *les jobs entre eux*, mais **pas** une route `/ocr` ou `/detecter-bulles` directe qui tournerait en parallèle d'un job. Or `predict()` (ultralytics) et `readtext()` (EasyOCR) ne sont pas thread-safe → double chargement possible et état potentiellement corrompu. **Correctif** : un `threading.Lock` global d'inférence couvrant routes directes *et* worker.

- **Verrou trop large dans `region_crop_png`.** Le `with _crop_lock` englobe crop + resize LANCZOS + encodage PNG ([pipeline/ocr.py:144-167](pipeline/ocr.py#L144-L167)) : sous le threadpool FastAPI, **tous** les crops (vignettes de recherche incluses) sont sérialisés, encodage compris. Le cache garde aussi un TIFF (potentiellement des dizaines de Mo) ouvert indéfiniment, sans TTL ni fermeture à l'arrêt. **Correctif** : ne verrouiller que l'accès au dict de cache ; libérer/expirer l'image.

- **Job : synchronisation implicite et registre non purgé.** Le worker écrit `current/done/status/errors` pendant que `snapshot`/`cancel_job` les lisent **sans `_lock`** ([pipeline/jobs.py:48-64](pipeline/jobs.py#L48-L64) vs [pipeline/jobs.py:67-99](pipeline/jobs.py#L67-L99)) : ça « marche » grâce au GIL mais un `snapshot` peut voir un état composite incohérent. L'**annulation n'est pas préemptive** (testée seulement entre planches/passes — un Kumiko de 300 s ou un OCR de grosse planche ne s'interrompt pas, et le subprocess Kumiko n'est pas tué). Le registre `_jobs` **grossit indéfiniment** (fuite mémoire lente sur process long-vécu).

- ✅ **FERMÉ** (DB-1 : index `idx_planches_album_numero` UNIQUE posé en migration v12→v13, numéro alloué AVANT écriture, `IntegrityError` → 409 nommant la course + master nettoyé, `main.py:820-828`) — ~~**Numéro de planche en course.**~~ `MAX(numero)+1` ([pipeline/ingest.py:33-38](pipeline/ingest.py#L33-L38), [main.py:326-329](main.py#L326-L329)) sans `UNIQUE(album_id, numero)` au schéma : deux imports concurrents sur le même album peuvent produire le même numéro → collision de noms de fichiers (`planche_0001.jpg` écrasé) et doublon logique. **Correctif** : contrainte `UNIQUE(album_id, numero)` + retry, ou réservation transactionnelle.

- ✅ **FERMÉ** (`master.unlink(missing_ok=True)` sur les deux chemins d'échec, `main.py:827` et `:831`, plus l'import ShareDocs `:1279`) — ~~**Master orphelin sur disque si l'ingestion échoue.**~~ `store_upload` écrit le fichier *avant* l'INSERT ([pipeline/ingest.py:142-151](pipeline/ingest.py#L142-L151)) ; si `ingest_image` lève ensuite ([main.py:331-334](main.py#L331-L334)), le master (et parfois le dérivé) reste sur disque sans ligne en base. **Correctif** : nettoyage dans le `except`.

### 🟡 P3 — Sécurité — **1 ouvert sur 4** au 2026-09-01

*Reste le CSRF seul, et il dépend d'INFRA-1 : il n'y a pas de session de navigateur à voler tant que l'application n'authentifie personne. Cf. `pilotage/SEC-2.md`, dont la zone CSP est close.*

- ✅ **FERMÉ** (`pipeline/sharedocs._check_url` : allowlist d'hôte, refus des IP internes, `follow_redirects=False`) — ~~**ShareDocs : pas de garde HTTPS ni de normalisation de chemin.**~~ `configure()` accepte n'importe quelle URL cliente ([pipeline/sharedocs.py:124-131](pipeline/sharedocs.py#L124-L131)) : aucun contrôle `scheme == "https"` → identifiants Basic potentiellement en clair sur une URL `http://` ; et un hôte interne arbitraire (SSRF théorique). Le `chemin` distant n'est pas normalisé des `..` ([pipeline/sharedocs.py:48-54](pipeline/sharedocs.py#L48-L54)) → remontée d'arborescence WebDAV possible (bornée par les droits du serveur distant). Acceptable pour un poste local de confiance, à documenter comme tel.

- ✅ **FERMÉ** (borné par `config.MAX_IMAGE_PIXELS`, défaut 200 Mpx, `BD_MAX_IMAGE_PIXELS`) — ~~**`Image.MAX_IMAGE_PIXELS = None`**~~ désactive globalement la garde anti-décompression-bomb pour tout le process ([pipeline/ingest.py:25](pipeline/ingest.py#L25), [pipeline/ocr.py](pipeline/ocr.py)), y compris les flux importés depuis le réseau (ShareDocs). Justifié pour des masters maîtrisés, mais une borne haute explicite serait plus sûre.

- ✅ **FERMÉ** (vérifié le 2026-09-01 : plus aucune interpolation de donnée utilisateur hors `esc()` / `textContent` / `confirm()` ; la CSP de SEC-2 est la seconde moitié du correctif recommandé) — ~~**XSS résiduels côté client.**~~ Le code échappe *généralement* bien, mais quelques `innerHTML` interpolent des données sans `escapeHtml` : labels de tags ([static/viewer.js:703](static/viewer.js#L703), [static/viewer.js:915](static/viewer.js#L915)). Un tag contenant `<img onerror=…>` injecté via l'API s'exécuterait. Pas de CSP dans les templates pour mitiger. **Correctif** : échapper systématiquement, ajouter une CSP.

- **Pas de protection CSRF.** Les `apiSend` POST/PUT/DELETE n'envoient ni token ni en-tête custom ([static/viewer.js:58-66](static/viewer.js#L58-L66)). Sans cookie de session côté backend, le risque est faible, mais à confirmer si l'app est un jour exposée.

### 🟢 P4 — Qualité, tests, reproductibilité — **4 ouverts sur 6** au 2026-09-01

*Restent : versions non épinglées (aucun `==` dans `requirements.txt`, cf. QA-4), couverture « 100 % » conditionnelle aux moteurs ML, concurrence non testée, inefficacités de rendu.*

- **Aucune version épinglée, pas de lockfile.** Tout est en bornes basses ouvertes (`fastapi>=0.110`, `ultralytics>=8.0`, `easyocr>=1.7`, `pillow>=10.0`…). Les builds ne sont pas reproductibles et le « 176 tests / 100 % » n'est garanti sur aucune combinaison figée — risqué pour ultralytics/easyocr/Pillow dont les API bougent. **Correctif** : `pip-tools`/`requirements.lock`. De plus `numpy`, `opencv-python-headless`, `requests` (deps réelles) ne figurent qu'en *commentaires* d'instructions, non installables via `pip install -r`.

- **« Couverture 100 % » conditionnelle et non annoncée comme telle.** Elle suppose les moteurs ML installés (les corps de `bulles._run`, `_load_model`, `ocr._get_reader` ne sont exécutés que par les tests *gated*). Sur une install minimale, ces lignes ne sont pas couvertes. À préciser dans le README.

- **Concurrence sous-testée malgré un design threadé.** La sérialisation `_run_lock` n'est jamais vérifiée (aucun test ne lance deux jobs concurrents) ; la contention worker↔requêtes sous WAL/`busy_timeout` — justification centrale du design — n'est pas testée sous charge ; la cohérence du backup *pendant une écriture* n'est pas validée alors que c'est l'argument du `VACUUM INTO`.

- ✅ **FERMÉ** (`static/lib/common.js`, module UMD testé : `$`, `apiGet`, `apiSend`, `escapeHtml`/`esc`, `toast`) — ~~**Duplication frontend.**~~ `$`, `apiGet`, `apiSend`, `escapeHtml`, `toast` sont recopiés à l'identique dans `viewer.js`, `recherche.js`, `corpus.js` (~80 lignes). Un `common.js` partagé suffirait.

- ✅ **FERMÉ pour l'essentiel** (gestionnaires clavier posés — 15 dans `viewer.js`, 4 dans `corpus.js` — et surtout la non-régression est verrouillée par l'audit axe-core WCAG 2.1 AA sur les 4 surfaces × 2 thèmes, `tests/test_e2e_a11y.py`) — ~~**Accessibilité clavier incomplète.**~~ Beaucoup de `<li>`/`<div>`/`<tr>` cliquables via `onclick` sans `role="button"`, `tabindex` ni gestion Enter/Espace (liste de planches, arbre, lignes de table, entrées ShareDocs) ; modales sans `role="dialog"`, sans piège de focus ni fermeture par Échap.

- **Quelques inefficacités** : `renderTree()`/`renderOverlay()` reconstruisent tout le DOM (`innerHTML=""`) à chaque sélection/sauvegarde ; `refreshTagVocab()` (GET `/api/tags`) appelé après *chaque* sauvegarde d'annotation ; `mousemove` global non throttlé qui inverse une matrice à chaque pixel ([static/viewer.js:1079](static/viewer.js#L1079)) ; jusqu'à 200 requêtes de vignettes par recherche.

---

## Recommandations — ordre suggéré

**Quick wins (quelques lignes, fort impact)**
1. Corriger `--hover`/`--scrim` du thème sombre — bug visible immédiat.
2. Échapper les labels de tags (`viewer.js:703`, `915`).
3. `COALESCE`/`or 0` sur les bornes géométriques (ordering, segmentation, bulles).
4. Convertir les `IndexError` Kumiko en `KumikoError`.
5. Nettoyer le master en cas d'échec d'ingestion.

**Robustesse (un peu plus de travail)**
6. Un verrou d'inférence global couvrant routes directes + worker.
7. Réduire la portée de `_crop_lock` + expirer le cache de crop.
8. Protéger les accès au dict de job par `_lock` + purge des vieux jobs ; rendre l'annulation plus réactive.
9. `UNIQUE(album_id, numero)` + gestion de collision.

**Fond**
10. Épingler les versions + lockfile ; déclarer `numpy`/`opencv`/`requests` proprement.
11. Garde HTTPS + normalisation de chemin ShareDocs ; CSP dans les templates.
12. Ajouter des tests de concurrence (deux jobs, worker↔lecteur, backup sous écriture).
13. Extraire un `common.js` ; améliorer l'accessibilité clavier des éléments cliquables et des modales.

---

*Aucune de ces remarques n'est bloquante pour l'usage visé (poste local, mono-utilisateur). Les P1 méritent un correctif rapide ; les P2 deviennent importantes si l'app est multi-utilisateur ou exposée au réseau.*

---

## Vérification (passe de contrôle du 13 juin 2026)

Chaque point a été recontrôlé ligne par ligne contre le code réel. Verdict : **CONFIRMÉ** (réel et joignable), **CORRIGÉ** (déjà patché), ou nuance.

### P1 — tous CONFIRMÉS puis CORRIGÉS
| Point | Vérif | Note |
|---|---|---|
| CSS `--hover`/`--scrim` sombre | ✅ Corrigé | valeurs réelles posées ([style.css:23-24](static/style.css#L23-L24)) ; thème clair inchangé |
| XSS labels de tags | ✅ Corrigé | `escapeHtml` en place ([viewer.js:703](static/viewer.js#L703), [915](static/viewer.js#L915)) |
| Kumiko `IndexError` | ✅ Corrigé | `data[0]`/`size[1]` gardés → `KumikoError` |
| NULL coords `TypeError` | ✅ Corrigé | `or 0` dans ordering/segmentation/bulles ; joignable via `PATCH {"x":null}` |
| Master orphelin | ✅ Corrigé | `master.unlink()` sur échec d'ingestion ([main.py:334](main.py#L334)) |

**Inexactitude trouvée à la vérif** : à l'échec de chargement d'image ([viewer.js:167-176](static/viewer.js#L167-L176)), `webScale` vaut **0** (et non `NaN`, sauf si `largeur_px` est nul). Le défaut reste réel (état incohérent), la cause exacte est corrigée ici.

### P2 — tous CONFIRMÉS (non corrigés)
- **Modèles ML sans verrou** : `ocr._get_reader` ([ocr.py:36-48](pipeline/ocr.py#L36-L48)) et `bulles._load_model` ([bulles.py:35-46](pipeline/bulles.py#L35-L46)) n'ont aucun lock ; `_run_lock` ([jobs.py:21](pipeline/jobs.py#L21)) sérialise les *jobs* mais **pas** les routes directes `/ocr`, `/detecter-bulles`, `/crop` → double-chargement et appel concurrent de `readtext`/`predict` (non thread-safe) possibles. **CONFIRMÉ.**
- **`_crop_lock` trop large + cache non libéré** : le `with _crop_lock` couvre crop+resize+encodage PNG ([ocr.py:144-167](pipeline/ocr.py#L144-L167)) ; le master reste ouvert indéfiniment, sans TTL ni fermeture à l'arrêt. **CONFIRMÉ.** (Réduire la portée demande de copier la réf d'image hors-verrou.)
- **Jobs** : accès non synchronisés au dict (`_run` écrit `current/done/status/errors` [jobs.py:48-64](pipeline/jobs.py#L48-L64) ; `snapshot`/`cancel_job` lisent sans `_lock`) → cohérent seulement grâce au GIL ; **annulation non préemptive** (testée entre planches/passes seulement, subprocess Kumiko non tué) ; **registre `_jobs` jamais purgé**. **CONFIRMÉ.** Nuance : `cancel_job` garde `if status == "en_cours"` ([jobs.py:97](pipeline/jobs.py#L97)), ce qui atténue la course « annuler un job terminé ».
- **Numéro de planche en course** : aucune contrainte `UNIQUE(album_id, numero)` au schéma ([database.py:64-74](database.py#L64-L74)), numéro par `MAX+1`. **CONFIRMÉ.**

### P3 — CONFIRMÉS, avec précisions
- **ShareDocs** : `configure` accepte toute URL sans garde `https` ([sharedocs.py:124-131](pipeline/sharedocs.py#L124-L131)) → Basic auth en clair possible sur `http://` ; `_join` n'normalise pas les `..` ([sharedocs.py:48-54](pipeline/sharedocs.py#L48-L54)) → traversal WebDAV distant (borné par les droits serveur) ; `_session` global lu/écrit sans verrou (course `download`↔`disconnect`) ; nouveau `httpx.Client` par requête (pas de pooling). **CONFIRMÉ.**
- **`MAX_IMAGE_PIXELS = None`** process-wide ([ingest.py:25](pipeline/ingest.py#L25), [ocr.py:55](pipeline/ocr.py#L55)). **CONFIRMÉ.**
- **XSS — points ADDITIONNELS non couverts par l'audit initial** (trouvés à la vérif, données semi-contrôlables) : `corpus.js:112` injectait `p.url_web` dans `src="..."` (nom de fichier ShareDocs) ; `viewer.js:123` et `corpus.js:114` injectaient `p.statut` brut dans un nom de classe et un attribut `title` (une `"` permettait une évasion d'attribut). **✅ Corrigés** (`esc`/`escapeHtml`, `node --check` OK). Les `img.src = url_web` ([viewer.js:166](static/viewer.js#L166), [784](static/viewer.js#L784)) sont des affectations directes, sans risque d'injection. Le reste des interpolations non échappées sont numériques/enum (serveur-figées).
- **CSRF** : aucun token dans `apiSend` **CONFIRMÉ** ; précision : le backend n'a **aucune authentification** → pas de session à forger, mais l'API localhost sans auth reste joignable par tout process local et, via le navigateur, par des requêtes cross-site simples (à garder à l'esprit si un jour exposée).

### P4 — CONFIRMÉS, avec une correction au README
- **Versions non épinglées / pas de lockfile** : tout en `>=`, aucun `==`, aucun `*.lock`. **CONFIRMÉ.**
- **`numpy`/`opencv`/`requests` non déclarés** (en commentaires seulement ; `numpy` pourtant utilisé [ocr.py:80](pipeline/ocr.py#L80)). **CONFIRMÉ.**
- **« 100 % » conditionnel** : corps ML exercés uniquement par tests `skipif` (`@requires_kumiko/bulles/ocr`), aucun `pragma: no cover` dessus. **CONFIRMÉ.**
- **Concurrence sous-testée** : aucun test de (a) deux jobs concurrents / `_run_lock`, (b) écriture worker ↔ lecture serveur au-delà de la cohérence commit-après-réponse de `test_live_coherence.py`, (c) `make_backup` pendant une écriture. **CONFIRMÉ.**
- **Décompte de tests** : le README annonce **176** ([README.md:200](README.md#L200), [205](README.md#L205)) mais il y a **184** fonctions `def test_` (dont 6 `skipif` + 1 `live`). **README inexact** — à mettre à jour.
- **Duplication frontend** : `$`, `apiGet`, `escapeHtml` dupliqués dans les 3 JS ; **mais** `apiSend` et `toast` ne sont que dans `viewer.js`+`corpus.js` (absents de `recherche.js`), et `esc` (corpus) diffère légèrement (`String(s ?? "")`). **PARTIEL** (l'idée tient, le « à l'identique entre les trois » est imprécis).
- **Accessibilité** (clavier des éléments cliquables, modales sans `role="dialog"`/focus trap/Échap) et **perf** (`renderTree` complet, `refreshTagVocab` après chaque save, `mousemove` non throttlé, ~200 vignettes/recherche). **CONFIRMÉS.**

**Bilan** : sur ~30 affirmations, **toutes confirmées réelles** sauf le décompte de tests du README (176→184, à corriger) ; 3 imprécisions mineures relevées (webScale=0 et non NaN ; duplication `apiSend`/`toast` partielle ; 2 points XSS supplémentaires à ajouter). Les 5 P1 sont corrigés et la suite de tests non-live passe (exit 0).

---

## Passe 2 — nouvelles trouvailles (revue adversariale du 13 juin 2026)

Trouvailles **absentes de la première passe**. ✔ = vérifiée de visu dans cette session.

### Intégrité des données — `parent_id` non validé (cause racine commune backend + frontend)
- **✔ B1 — `parent_id` accepté sans aucun contrôle** ([main.py:412-438](main.py#L412-L438) create, [main.py:454-471](main.py#L454-L471) update). La FK garantit seulement l'existence ; rien ne vérifie que le parent est **sur la même planche**, est une **case**, n'est pas **soi-même**, ni qu'il ne forme pas un **cycle**. Conséquences réelles, toutes déclenchables par un `PATCH /api/regions/{id}` direct :
  - parent cross-planche ou cycle → la région est **omise silencieusement de l'export** JSON/arbre (`_region_tree` ne descend que depuis `None`, [main.py:859-883](main.py#L859-L883)) ;
  - auto-parent / cycle → le `WITH RECURSIVE … UNION ALL` de `delete_region` ([main.py:479-490](main.py#L479-L490)) **ne se termine pas** → 500/boucle au `DELETE`.
  - **Gravité : majeure** (perte de données à l'export + 500). Le frontend a une garde `canReparent`, donc joignable surtout par appel API direct (modèle mono-utilisateur ⇒ probabilité faible, intégrité réelle).
- **✔ F1 — corollaire frontend** : une région à `parent_id` orphelin (parent absent de `state.regions`) est **absente de l'arbre, de la séquence de lecture, de la transcription et de la navigation clavier** ([viewer.js:397-411](static/viewer.js#L397-L411) `readingSequence` ne parcourt que depuis `"root"`), **mais reste dessinée dans l'overlay** → bulle visible et sélectionnable à l'image, mais **non transcriptible**. Correctif défensif : rabattre tout `parent_id` non résolu sur `"root"`.

### Backend — autres
- **✔ B2 — orphelin disque sur `sharedocs_importer`** ([main.py:587-600](main.py#L587-L600)) : même séquence `store_upload`→`ingest_image` que `import_planche`, mais le `except` ne fait **pas** `master.unlink()`. Le correctif P1 (master orphelin) n'a pas été reporté ici. **Majeur** (incohérence avec le fix déjà appliqué).
- **B3 — `x/y/w/h` négatifs acceptés** ([main.py:98-119](main.py#L98-L119), pas de `Field(ge=0)`) → crops hors-limites, ordre de lecture incohérent, zones TEI `lrx<ulx`. **Majeur.**
- **B4 — `recherche` `limit` non borné** ([main.py:728](main.py#L728), [772](main.py#L772)) : `limit=-1` ⇒ `LIMIT -1` SQLite ⇒ **tout le corpus** + sous-requête tags par résultat (N+1) — DoS trivial, alors que `region_crop` borne bien sa taille. **Majeur.**
- **B5 — `_migrate` sans gating par `user_version`** — ✅ **Fait 2026-07-16** : idempotent *par chance* (garde par présence de colonne), aucun *gating* par version ni garde anti-downgrade ; le pattern « incrémenter `SCHEMA_VERSION` + ajouter une étape » aurait été **faux dès la 1re migration non détectable par colonne** (backfill, `UPDATE`). **Corrigé** : `_migrate` **refuse de rétrograder** une base plus récente que le code (`RuntimeError`), **court-circuite** si déjà au schéma courant, et la convention `if version < N` est documentée pour les étapes futures. Test de non-régression (`test_migration_refuse_downgrade`). **Majeur (dette).**
- **B6 — transitions de statut libres** ([main.py:631-642](main.py#L631-L642)) : aucune validation d'ordre ; et `segment_planche` force `statut='segmentee'` → **re-segmenter une planche `annotee` la fait régresser**. **Mineur.**
- **B7 — injection de formule CSV** — ✅ **Fait 2026-07-18** : les deux exports CSV de l'app (`/api/export/csv`, `/api/recherche/export.csv`) neutralisent une cellule TEXTE débutant par `= + - @` (ou tab/CR) via un préfixe apostrophe (`_csv_safe`, OWASP CSV Injection) ; les nombres (coordonnées) ne sont pas touchés. Test de non-régression. **Mineur.**
- **B8 — `GET /api/sauvegarde`** — ✅ **Fait 2026-07-18** : `make_backup` enveloppé (`_faire_sauvegarde`) — une `OperationalError` (base occupée) file au handler global (**409**), toute autre erreur → **503** propre + trace, plus de **500 brut**. Les deux routes de sauvegarde. Tests 409/503. **Mineur.**
- **B9/B10 — validations manquantes** — ✅ **Fait 2026-07-18 (B9)** : `create_album` **et** `update_album` refusent un `titre` vide/blanc (422, titre `strip`é), comme `create_tag`. **B10 déjà couvert** (`numero` d'import `Form(ge=1)`). Test de non-régression. **Mineurs.**

### Frontend (`viewer.js`) — autres
- **✔ F2 — poignée de resize sans garde null** ([viewer.js:1045-1049](static/viewer.js#L1045-L1049)) : `const r = selectedRegion()` puis `r.x` sans `if (!r) return` ⇒ `TypeError` si la sélection a été vidée. **Majeur.**
- **F3 — inversion de resize `w`/`n`** ([viewer.js:1133-1145](static/viewer.js#L1133-L1145)) : tirer la poignée gauche/haute au-delà du bord opposé clampe `w`/`h` à 1 **sans re-corriger `x`/`y`** → la région se **téléporte**. **Majeur (UX).**
- **F4 — région 1×1 persistée** : le seuil `w>4 && h>4` ne s'applique qu'au **dessin**, pas au **resize** → on peut sauvegarder une région d'1 px. **Majeur.**
- **F5 — deep-link silencieux** — ✅ **Fait 2026-07-19** : `applyDeepLink` **diagnostique** (toast) une planche/région introuvable (`selectAndCenter` renvoie un booléen, vérification `state.planche.id`) ; `selectAlbum(id, autoSelect=false)` ne pré-charge plus `planches[0]` sur un deep-link. Test e2e (`test_deep_link_introuvable_diagnostique`). **Majeur (diagnostic absent).**
- **F6 — `navigateRegion` re-déplie l'arbre** — ✅ **Fait 2026-07-19** : la navigation clavier passe `selectRegion(id, reveal=false)` → le repli manuel des cases est respecté (un clic/deep-link révèle toujours). **Mineur.**
- **F7 — `#note-input` non réinitialisé si `loadAnnotation` échoue** — ✅ **Fait 2026-07-19** : le `catch` VIDE note + tags (+ `setSaveState("")`) → plus de contamination de la région suivante par un `scheduleSave`. **Mineur.**
- **F8 — indicateur « Enregistrement… » bloqué** — ✅ **Fait 2026-07-19** : `saveAnnotation` fait `setSaveState("")` quand il retourne tôt (mode ≠ annotation / pas de sélection). **Mineur.**
- Autres mineurs : sélection ShareDocs conservée entre dossiers (import non vu), incohérence Suppr clavier (édition) vs bouton (tous modes), `caseContaining` départage les aires égales par ordre d'insertion.

**Priorité passe 2** : **B1+F1** (validation `parent_id` côté serveur + repli défensif côté client — corrige perte de données et 500 à la source), **B2** (orphelin ShareDocs, fix trivial déjà écrit ailleurs), **F2/F3/F4** (resize en mode édition, faciles et très visibles), **B3/B4** (bornes `Field(ge=0)` + `limit`).

### ✅ Cluster passe 2 appliqué (suite non-live verte, exit 0)
- **B1** — `_validate_parent()` ([main.py:215-244](main.py#L215-L244)) : parent existant + même planche + anti-cycle (auto-parent et descendants) ; appelé dans `create_region` et `update_region`. `delete_region` passe en `UNION` (termine même sur cycle pré-existant).
- **F1** — repli orphelin sur `"root"` dans `readingSequence` et `renderTree` ([viewer.js](static/viewer.js)) : une région à parent absent reste visible dans l'arbre/séquence/transcription.
- **B2** — `master.unlink(missing_ok=True)` dans le `except` de `sharedocs_importer` ([main.py:587-606](main.py#L587-L606)) ; `master = None` avant le `try` pour gérer l'échec de download.
- **B3** — `Field(0, ge=0)` / `Field(None, ge=0)` sur `x/y/w/h` (`RegionIn`/`RegionUpdate`).
- **B4** — `limit = max(1, min(limit, 500))` dans `recherche`.
- **F2** — garde `if (!r) return` sur la poignée de resize ; idem dans `resizeFrom`.
- **F3** — resize `w`/`n` : bord opposé ancré (plus de téléportation), clamp qui préserve le bord fixe.
- **F4** — `MIN_REGION = 5` : le resize ne peut plus persister une région < 5 px (cohérent avec le seuil de dessin).

**Restent ouverts (non traités ce tour)** : ~~B5~~ (✅ 2026-07-16), B6 (transitions de statut + régression `annotee`→`segmentee`), ~~B7~~ ~~B8~~ ~~B9/B10~~ (✅ 2026-07-18 : sûreté serveur), ~~F5–F8~~ (✅ 2026-07-19 : robustesse Visionneuse — deep-link diagnostiqué, arbre non re-déplié, note non contaminée, indicateur non bloqué), et mineurs. Plus les **P2/P3** de la passe 1 (verrou d'inférence ML, `_crop_lock`, jobs, `UNIQUE(album_id,numero)`, HTTPS ShareDocs).

---

## Passe 3 — nouvelles trouvailles (revue adversariale du 13 juin 2026)

Territoire neuf : logique de **préservation du travail humain** (segmentation/bulles), **`corpus.js`** (jobs/sélection/modale) et **`recherche.js`/`theme.js`**, jamais audités en entier. ✔ = vérifiée de visu.

### Solides et corrigeables (frontend)
- **✔ C4 — course de recherche, résultats périmés** ([recherche.js:131-133](static/recherche.js#L131-L133)) : `apiGet().then(renderResults)` sans garde de fraîcheur. Une réponse lente pour « ab » peut écraser celle de « abc » (aggravé par `onchange`/`toggleTag` non débouncés). **Majeur.**
- **✔ C3 — tags à virgule cassés** ([recherche.js:127](static/recherche.js#L127) ↔ [main.py:796](main.py#L796)) : `tags.join(",")` re-splitté côté serveur sur `,` → un label contenant une virgule (`"paris, france"`) devient deux filtres et ne matche jamais. **Majeur (silencieux).**
- **✔ A1 — polling concurrent** ([corpus.js:238-249](static/corpus.js#L238-L249)) : `clearTimeout` placé **après** l'`await` ⇒ un `pollJobs()` déclenché (Annuler/Lancer) pendant qu'un tick est en vol crée une 2ᵉ chaîne de polling ; les requêtes `/api/jobs` se multiplient. **Majeur.**
- **✔ B1 — `checkedPlanches` jamais purgé** ([corpus.js:48-57](static/corpus.js#L48-L57), [92-95](static/corpus.js#L92-L95)) : `checkedAlbums` est purgé des ids disparus, **pas** `checkedPlanches` ; après suppression d'album/de planche (autre onglet, lot) des pids fantômes restent comptés et envoyés au lot (le backend les ignore, mais le compteur ment). **Majeur.**
- **✔ E1 — double-soumission d'album** ([corpus.js:169-188](static/corpus.js#L169-L188)) : `#m-save` jamais désactivé pendant l'`await` ⇒ double-clic en création = **deux POST = album dupliqué** (pas de contrainte d'unicité de titre). **Majeur.**
- **C1 — mention « (limité) » trompeuse** ([recherche.js:128](static/recherche.js#L128), [138](static/recherche.js#L138)) : seuil `200` codé en dur ×2 ; `res.count` = résultats renvoyés, pas le total ⇒ « limité » faux à exactement 200 matches. **Mineur.**
- **F1 — thème non synchronisé entre onglets** ([theme.js](static/theme.js)) : pas d'écouteur `storage` ; basculer le thème dans un onglet ne met pas à jour les autres déjà ouverts. **Mineur** (limite, pas régression).
- Mineurs : A4 (barre 0 %→100 % car `done` incrémenté par planche, pas par passe — [jobs.py:59](pipeline/jobs.py#L59)), C2 (`q` ponctuation→0 résultat), C5 (filtres `onchange` non débouncés), D1/D2 (nuage de tags figé après démarrage), E3 (année non bornée).

### Préservation du travail humain (segmentation) — qualité, à traiter avec soin
- **S2 — cases fantômes annotées en doublon** ([segmentation.py:140-156](pipeline/segmentation.py#L140-L156)) : si **deux** anciennes cases annotées recouvrent **une seule** nouvelle (fusion Kumiko), la 1ʳᵉ transfère, la 2ᵉ est *conservée* (donnée non perdue) mais survit comme **doublon géométrique annoté** sous la nouvelle case → deux cases empilées, état non déterministe au cycle suivant. **Majeur (cohérence).**
- **S3 — transfert vers une case quasi-disjointe** ([segmentation.py:119-129](pipeline/segmentation.py#L119-L129)) : `_best_overlap` accepte tout recouvrement `> 0` (pas de seuil) ⇒ une annotation peut migrer vers une case voisine sans rapport, et l'ancienne case (désormais non annotée) est **supprimée** → annotation mal réattribuée, irrécupérable. **Moyen.**
- **S7 — re-rattachement aux cases périmées conservées** ([segmentation.py:96-116](pipeline/segmentation.py#L96-L116)) : `_reattach_orphans` cible **toutes** les cases (dont les anciennes `preserved`), pas seulement les nouvelles ⇒ une bulle peut se rattacher à une case fantôme. **Moyen** (corollaire S2).
- **S4 — dédup bulles unidirectionnelle** ([bulles.py:140-143](pipeline/bulles.py#L140-L143)) : test « centre du nouveau ∈ ancien » seulement (pas d'IoU) ⇒ doublons auto accumulés selon décalage/taille. **Moyen** (pas de perte humaine).

### Latents / heuristiques (notés, non prioritaires)
- **S1/S5 — détachement & désindexation FTS non récursifs avant `DELETE`** dans `segment_planche` : **neutralisés aujourd'hui** par la profondeur ≤ 2 (les `old_ids` n'ont plus d'enfants au moment du DELETE), mais deviennent perte de données + FTS fantôme dès qu'on autorise une 3ᵉ profondeur. Aligner sur le `WITH RECURSIVE` de `delete_region`/`detect_bulles`. **Latent.**
- **S6 — non-idempotence** : re-segmenter une planche à case annotée conservée n'est pas un point fixe (transfert/rattachement peuvent osciller). **Faible.**
- **O1 — regroupement en rangées non déterministe** ([ordering.py:33-46](pipeline/ordering.py#L33-L46)) : agglomération transitive possible sur `y` en escalier ; heuristique corrigeable à la main par l'utilisateur. **Faible.**

**Priorité passe 3** : **C4 + A1** (deux races async réelles), **B1 + E1** (sélection fantôme + albums dupliqués), **C3** (filtre silencieusement faux). **S2/S3/S7** sont réels mais touchent la logique la plus délicate — à corriger **avec des tests de non-régression** dédiés, pas à la volée.

### ✅ Cluster frontend passe 3 appliqué (suite non-live verte, exit 0 ; `node --check` OK)
- **C4** — jeton de fraîcheur `state.searchGen` ([recherche.js](static/recherche.js)) : `renderResults`/erreur ignorés si une recherche plus récente est partie.
- **C3** — tags envoyés en **paramètres répétés** (`params.append("tags", t)`) ; backend `tags: Optional[list[str]] = Query(None)` + suppression du `split(",")` ([main.py](main.py)). Plus de filtre faux sur un label à virgule. Rétro-compatible (16 tests search/tag verts).
- **A1** — `pollJobs` : `clearTimeout` en tête + jeton `state.jobGen` ([corpus.js:238](static/corpus.js#L238)) → une seule chaîne de polling, fini la multiplication des requêtes `/api/jobs`.
- **B1** — `checkedPlanches` purgé des ids disparus dans `openAlbum` (intersection avec les planches courantes) et vidé quand l'album ouvert disparaît ([corpus.js](static/corpus.js)).
- **E1** — `#m-save` désactivé pendant l'`await` (`finally` réactive) → plus de double-soumission/album dupliqué.

**Restent ouverts passe 3** : C1 (« limité » trompeur), F1 (thème inter-onglets), A4 (barre de progression par planche), C2/C5/D1/D2/E3 mineurs, et **S2/S3/S7/S4** (préservation segmentation — à traiter avec tests dédiés), S1/S5/S6/O1 latents.

---

## Passe 4 — nouvelles trouvailles (revue du 13 juin 2026)

Territoire neuf : **templates HTML + CSS**, **cohérence des `#id` JS↔HTML**, **correction réelle des tests**.

### ✅ T1 — Les correctifs des passes 2-3 ne sont couverts par AUCUN test (MAJEUR) — **FERMÉ**, cf. le bloc « T1 + T6 appliqués » plus bas
La « suite verte, exit 0 » citée à chaque passe ne prouve que l'absence de régression sur les chemins **nominaux** — elle n'exerce **aucune** des nouvelles validations. On pourrait réintroduire chaque bug sans qu'un test échoue. Manquent (convention `test_regressions.py` : un test par bug) :
- **B1** — `_validate_parent` ([main.py:215-244](main.py#L215-L244)) : ses 4 branches 422 (parent introuvable / cross-planche / auto-parent / cycle) ne sont jamais déclenchées par un test.
- **B3** — `Field(ge=0)` : aucun test n'envoie `x/y/w/h` négatif → 422 attendu, non vérifié.
- **B4** — `limit = max(1, min(limit, 500))` : aucun test `limit=-1`/`0`/`99999`.
- Frontend (C3/C4/A1/B1/E1) : non testable en unitaire ici (pas de harness JS), mais C3 backend (`tags` en liste) mérite un test multi-tags.
- **À faire** : ajouter ces tests de non-régression. C'est le filet manquant le plus important.

### Tests — autres (moyen/mineur)
- **T2** — `test_live_race.py` est **séquentiel**, pas une vraie course : `PUT` puis `GET` 30× sur le même client synchrone. Capte bien le bug « commit après réponse » mais le nom survend une concurrence inexistante. **Moyen** (faux sentiment de sécurité). → ✅ 2026-08-31 : renommé [tests/test_live_coherence.py](tests/test_live_coherence.py). Le pointeur d'origine (`test_live_race.py:83-92`) désignait des lignes d'un fichier qui n'en comptait que 45 — il est retiré plutôt que corrigé, un lien mort dans un constat daté étant la forme la plus discrète de la dérive que ce constat dénonce.
- **T3** — `_counter` de [jobs.py:22](pipeline/jobs.py#L22) jamais réinitialisé par `_reset_jobs` (qui ne fait que `_jobs.clear()`) ; `_reset_jobs`/`_reset_crop_cache` sont **locaux à un fichier** au lieu d'être en `conftest.py`. Inoffensif aujourd'hui, fuite d'état latente. **Mineur.**
- **T4** — Assertions faibles : `status in (200, 400)`, `"BD" in r.text`, `len(data) > 0` ; `test_make_backup_horodatage_auto` ne vérifie pas le format de l'horodatage. **Mineur** (smoke tests). → ✅ 2026-08-31 (AUDIT-1) : la première acceptait DEUX contrats opposés sur une seule entrée — mesuré, la route répond 200 avec zéro résultat sur douze syntaxes FTS invalides, et le test le vérifie désormais APRÈS s'être assuré qu'une requête valide trouve sa cible ; la deuxième reconnaissait le shell à trois lettres, elle vérifie titre, langue et scripts ; la troisième acceptait un octet, le zip doit s'ouvrir et porter la base ; l'horodatage est contrôlé par motif ET doit tomber dans l'intervalle d'exécution. Les trois pointeurs de ce constat étaient morts — retirés, pas corrigés.
- **T5** — S2/S3 (passe 3) non couverts : `test_transfer_case_annotations` ne teste jamais le cas **2 anciennes cases → 1 nouvelle**, ni un recouvrement minuscule. **Moyen** (à inclure dans le tour S2/S3).

### Templates / CSS / id (résultat largement SAIN)
- **✔ Cohérence id JS↔HTML : exhaustivement vérifiée, AUCUN id manquant.** Les 4 références « suspectes » (`#handles-group`, `#draw-rect`, `#toasts`, `#detail-edit`) sont des éléments créés dynamiquement — légitimes. Point positif réel.
- **T6** — `font: 13px inherit` ([style.css:600](static/style.css#L600), [785](static/style.css#L785)) : raccourci `font` invalide (pas de `font-family` valide) → déclaration potentiellement ignorée. **Mineur.** Correctif : `font-size: 13px; font-family: inherit;`.
- **T7** — Aucune media query de largeur malgré `<meta viewport>` présent : pages non responsive (grilles à largeurs fixes). **Mineur** (outil desktop).
- Confirmés sains : `lang="fr"`, viewport, labels for/id, ordre des scripts, z-index/overflow, pas de `<form>` (donc pas de soumission implicite). CSP absente = déjà noté passe 1.

**Priorité passe 4** : **T1** (écrire les tests de non-régression des correctifs B1/B3/B4 — le manque le plus important), puis T6 (CSS trivial). T2/T3/T4/T5 selon appétit.

### ✅ T1 + T6 appliqués (suite non-live verte, exit 0)
- **T1 — 8 tests de non-régression ajoutés** à [tests/test_regressions.py](tests/test_regressions.py) : parent introuvable / cross-planche / auto-parent / cycle → 422, **détachement (`parent_id=null`) toujours autorisé** (garde anti-faux-positif), coords négatives (création + MAJ) → 422, `limit=-1` borné (count=1, pas tout le corpus), tags en **paramètres répétés** + label à virgule non scindé + ET logique (couvre C3). Chacun échouerait si le correctif était retiré (vérifié par construction : sans clamp `limit=-1`→3 résultats ; sans `split` retiré le tag à virgule ne matche pas ; sans `_validate_parent` le cross-planche renvoie 201 ; sans `Field(ge=0)` les coords négatives passent).
- **T6 — `font: 13px inherit`** remplacé par `font-size: 13px; font-family: inherit;` ([style.css:600](static/style.css#L600), [785](static/style.css#L785)).
- Décompte de tests : ~184 → ~192 (README à mettre à jour, cf. passe 1 : il annonce encore 176).

**Restent ouverts passe 4** : ~~T2~~ (✅ traité le 2026-08-31, AUDIT-1 : fichier renommé `test_live_coherence.py`, docstring et message ne promettent plus une concurrence — laquelle reste non testée, et c'est désormais ÉCRIT dans le fichier), ~~T3~~ (✅ corrigé : `_reset_global_state` global en conftest + `_counter` reset), ~~T4~~ (✅ traité le 2026-08-31, AUDIT-1), T5 (tests S2/S3 à écrire avec le tour préservation), T7 (non-responsive). Décompte README corrigé : **176 → 192**.

---

## Passe 5 — nouvelles trouvailles (revue du 13 juin 2026)

Dernier territoire : `ingest.py`, `config.py`, **service de fichiers statiques**, exports sous l'angle fichier/sérialisation. (`spike/` confirmé hors périmètre — jamais importé.)

### ✅ G1 — Export TEI corrompu silencieusement par des caractères non-XML — **FERMÉ** (`_xml_safe`, `main.py:4200`)
[main.py:1014-1022](main.py#L1014-L1022) : `ocr_texte` et `note` (texte libre utilisateur) sont injectés dans `<line>.text`/`<note>.text`. `ET.tostring()` **n'échappe ni ne rejette** les caractères de contrôle interdits par XML 1.0 (`\x00`-\x08, \x0b, \x0c, \x0e-\x1f) : il les écrit bruts. Un `\x00` collé dans une correction OCR → `GET /api/export/tei` renvoie **200 OK** avec un XML que **tout parseur conforme rejette** (`not well-formed`). Corruption silencieuse du livrable. **Correctif** : filtrer ces caractères avant `.text`. (Le CSV, lui, ne casse pas — vérifié.)

### ✅ G2 — `config.py` : `mkdir` à l'import → crash opaque — **FERMÉ** (le `mkdir` est encadré, `OSError` → `RuntimeError` nommant le chemin fautif, `config.py:129-136`)
[config.py:42-43](config.py#L42-L43) : la création des dossiers s'exécute **à l'import** de `config` (donc importé par tout le code + les tests). Un `BD_DATA_DIR` non inscriptible (RO, permissions, disque plein) lève `OSError` **à l'import**, stack brute, avant tout `lifespan`/message clair → l'app ne démarre pas sans diagnostic. **Correctif** : différer la création dans le `lifespan` ou encadrer avec un message explicite.

### 🟡 Mineurs
- **G3** — `BD_DATA_DIR` **relatif** résolu contre le **CWD** du process ([config.py:17](config.py#L17)) → selon d'où `uvicorn` est lancé, l'app pointe silencieusement vers une base/corpus différents. Documenter « chemin absolu » ou résoudre contre `BASE_DIR`.
- **G4** — `read_metadata` ([ingest.py:49](pipeline/ingest.py#L49)) suppose `dpi` itérable : un DPI **scalaire** (`300`) lève `TypeError` → image valide rejetée en 400. Garde `isinstance`.
- **G5** — `_rel_posix` ([ingest.py:28-30](pipeline/ingest.py#L28-L30)) : `ValueError` non gardé si `source` hors `DATA_DIR` (latent, non joignable par l'API actuelle).
- **G6** — `numero=0` (falsy) ([ingest.py:148](pipeline/ingest.py#L148)) : le master prend le stem du nom uploadé tandis que le dérivé est `planche_0000.jpg` → **noms master/dérivé désalignés** (invariant rompu). `Field(ge=1)` sur `numero` + tester `is not None`.

### ✅ Vérifié SAIN (résultats positifs)
- **Service de fichiers `/derivatives` et `/static`** : pas de path traversal (Starlette normalise/confine). **Sûr.**
- **`FileResponse` index/recherche/corpus** : chemins constants, pas de traversal.
- **`Content-Disposition`** des exports/sauvegarde : noms générés serveur, pas d'injection d'en-tête.
- **Nom de fichier uploadé** : neutralisé par `.stem`/`.suffix`.
- **PIL** : pas de fuite de handle ; GIF animé / mode P / RGBA / CMYK produisent un dérivé sans planter.
- **Orientation EXIF ignorée mais cohérente** (master et dérivé même orientation brute) → pas un bug pour des scans TIFF.

**Priorité passe 5** : **G1** (livrable TEI corrompu — filtrer les caractères de contrôle), **G2** (crash d'import opaque). G3/G4/G6 = gardes simples.

### ✅ G1–G4 + G6 appliqués (suite non-live verte, exit 0)
- **G1** — helper `_xml_safe()` ([main.py](main.py)) retire les caractères interdits par XML 1.0 (garde tab/LF/CR) ; appliqué à `title`/`author`/`publisher`/`sourceDesc` + `line`/`note`/`ana`. Test de régression : un OCR contenant `\x0b`/`\x1f` produit un TEI **re-parsable**.
- **G2** — création des dossiers data encadrée ([config.py:45-52](config.py#L45-L52)) : un `DATA_DIR` non inscriptible donne un `RuntimeError` nommant le chemin + `BD_DATA_DIR`, pas une stack brute.
- **G3** — `BD_DATA_DIR` **relatif** résolu contre `BASE_DIR` (dépôt), plus contre le CWD ([config.py:17-25](config.py#L17-L25)).
- **G4** — `read_metadata` tolère un `dpi` scalaire/non numérique (normalisé ou `None`) au lieu de rejeter l'image ([ingest.py:43-57](pipeline/ingest.py#L43-L57)).
- **G6** — `numero` d'import borné `Form(None, ge=1)` (→ 422 si < 1) + `store_upload` teste `is not None` (plus de désalignement master/dérivé sur 0). Test de régression : `numero=0`/`-3` → 422.
- **G5** reste ouvert (latent, non joignable par l'API actuelle).

Décompte de tests : 192 → **194** (2 nouveaux régressions G1/G6).
