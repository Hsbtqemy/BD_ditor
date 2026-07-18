# Backlog exécutable — BéDéditeur

> Établi le 2026-06-15. **Révisé le 2026-06-24** : ANN-2 « mince » livré (§1, entité personnage + locuteur + attributs facettés) ; A11y (§6) livré et vérifié ;
> navigation/désencombrement (§5) largement faits ; **dette technique & sécurité de
> l'audit intégrée en §7**. Recense les pistes ouvertes **après** les lots livrés
> (analyse : correction grammaticale, requête, Recherche+++, Exploration ;
> numérotation & citation éditoriale ; round-trip). Chaque ticket a un *pourquoi*,
> un *périmètre* et des *critères d'acceptation* (conditions de « fini »).

**Légende** — Priorité : **P1** (finalité / bloquant prochain), **P2** (important),
**P3** (raffinement / à la demande). Effort : **S** (< ½ j), **M** (1-2 j), **L** (≥ 3 j
ou décision de conception requise).

---

## 1. Annotation — émotions / minorités (finalité)

### ANN-1 · Vocabulaire contrôlé (émotions, représentation) — structure ✅, peuplement ouvert · P1
> L'étude des émotions/minorités repose sur du **codage humain**. Le **socle structurel** est
> désormais complet : vocabulaire facetté ÉMERGENT (ANN-2, v11) — agrégeable, insensible à la
> casse — + couche définitionnelle **SKOS** (A4, v17) + palier **`domaine`** qui regroupe les
> dimensions par champ d'étude (**B0, v20** : émotions n'est qu'un domaine, orthogonal à `cible`,
> extensible sans code ; cf. `docs/domaines.md`).
- **Reste (P1)** : *peupler* les domaines/dimensions/valeurs **avec les linguistes** (catégories
  d'émotion, marqueurs de représentation). Plus de « liste fermée vs émergent » à trancher — c'est
  émergent et documenté. Deux voies désormais : à la main (annotation + panneau 📖 Lexique) **ou**
  **amorçage en lot** depuis un tableur (`tools/importer_vocabulaire.py`). Puis l'**analyse par
  domaine** (croisements ANA-2, KWIC ANA-3).
- Done (structure) : domaines créables/documentables/regroupables (UI 📖 Lexique) ; dimensions
  filtrables/distribuables en facette ; agrégation sans doublon ; **import CSV** (amorçage
  taxonomie, pré-remplir sans écraser, idempotent, portée `--collection` ; cf.
  `docs/import-vocabulaire.md`) ; tests.

### ANN-2 · Entité « personnage » + lien bulle→personnage — ✅ Fait « mince » 2026-06-24 · P2 · L
> « Représentation des minorités » = surtout *qui* est représenté ; idiolectes, registres
> par personnage. Aujourd'hui `personnage` n'est qu'un type de région, sans identité.
- Faire : table personnage (récurrent, attributs) ; lien `region(bulle) → personnage` ;
  UI d'attribution ; facette d'analyse « par personnage ».
- ✅ Fait 2026-06-24 (schéma v11 + API 2a/2b/2c + UI 3a/3b/3c ; vocabulaire **émergent**, pas figé ; cf. `docs/personnages-et-attribution.md`) : attribuer une bulle à un personnage ; recherche/exploration/comparaison
  filtrables par personnage ; test.

### ANN-3 · EntityRuler / gazetteer pour les noms de personnages — P3 · M
> Voie « NER pas cher » pour un cast fermé (vs fine-tuning, écarté faute de données).
- Faire : gazetteer par album → EntityRuler spaCy ; pré-attribution suggérée.
- Done : les occurrences d'un nom connu sont repérées ; suggestion modifiable. Dépend d'ANN-2.

### ANN-4 · Statut de relecture explicite par planche — ✅ **Fait 2026-07-18 (B5, v21)** · P2 · S
> L'idée « Attente » : suivre quelles planches restent à relire (coordination équipe).
- ✅ Fait : statut **dérivé** des provenances de tokens (`database.relecture_planches` : relus =
  corrigé|validé → à faire / en cours / faite ; 0 token → à faire) — jamais stocké —, **forçable**
  via l'override `planches.relecture` (3 états | auto, `PATCH /api/planches/{id}/relecture`).
  Bibliothèque : **pastille** (couleur renforçante + libellé) + **sélecteur** d'override + **filtre**.
  Migration v21. Tests : dérivation/override/route + e2e a11y (round-trip). Cf. `docs/relecture.md`.
- Différé : roll-up corpus du reste-à-relire ; relecture par annotateur ; statut niveau album.

### ANN-5 · Accord inter-annotateurs — P3 · M
> Quand plusieurs linguistes corrigent : mesurer l'accord (qualité, points de divergence).
- Done : rapport d'accord par token/champ entre auteurs. **Dépend d'INFRA-2 (`auteur`).**

---

## 2. Analyse — extensions de surface

### ANA-1 · Filtre par tags dans les endpoints d'analyse — P1 · S
> **✅ Fait — 2026-06-23** (commits `6e49f75` / `40b0ceb` / `26e0f70`) : filtre `tags`
> + `tag_scope` (hérité/propre) sur fréquences/concordance/comparaison, facette tag
> dans Exploration, cohérence avec Recherche (drill sans cul-de-sac), tests
> (`tests/test_analyse.py`) — comble une partie de QA-3.
> `frequences`/`concordance`/`comparaison` filtrent album/type/POS/lemme/morph/provenance
> **mais pas les tags** → impossible de faire « distribution des lemmes parmi les régions
> taguées *colère* ». Pierre angulaire pour la finalité.
- Faire : étendre `_analyse_filtres` (EXISTS sur `annotation_tags`) ; exposer la facette tag
  côté Exploration.
- Done : distribution/concordance/comparaison filtrables par tag ; test.

### ANA-2 · Croisements (tableaux croisés, 2 dimensions) — ✅ **Fait 2026-07-18 (B3)** · P2 · M
> Conçu (« croisements ») mais non fait : tag × POS, émotion × type de région, auteur ×
> temps verbal… (on n'avait que distributions 1-D + comparaison A/B).
- ✅ Fait : endpoint `GET /api/analyse/croisement?axe_x=&axe_y=` (contingence TOKEN, réutilise
  `_analyse_filtres`) ; axes = **pos | morph | type | provenance | auteur | locuteur | tag |
  dim:<id>** (les dimensions d'attribut → le payoff des domaines B0) ; fan-out tag/dimension en
  LEFT JOIN (NULL = « (vide) ») ; marges réelles + top-N par axe. **4ᵉ vue « Croisement »** dans
  Exploration (deux sélecteurs d'axe + filtres A) ; tableau (en-têtes collantes, heatmap sobre
  AA) ; **cellule cliquable → concordance** pré-filtrée (puis deep-link Visionneuse). Tests :
  3 backend (tag×pos, axe dimension→clé de drill, axe invalide) + e2e a11y (tableau + drill).
- Limite assumée : grain TOKEN → les cases **sans texte** ne sont pas comptées ; drill impossible
  sur les cellules « (vide) » et sur un croisement type×provenance seul (aucun critère de concordance).
- Différé : grain RÉGION/personnage (compter des cases/personnages annotés), export du tableau.

### ANA-3 · Vue concordance KWIC dédiée — ✅ **Fait 2026-07-18 (B2)** · P2 · M
> `/api/analyse/concordance` (lot 2) existait **sans UI**. La modalité KWIC (une ligne par
> occurrence, mot-pivot en contexte) manquait.
- ✅ Fait (UI seule ; backend inchangé) : **vue « Concordance »** dans Exploration (sélecteur
  de vue Distribution / Concordance / Comparaison), champ **lemme/mot** + réutilisation des
  filtres A (POS, morpho, tag, locuteur, attributs) ; **deux rendus** au choix — **aligné**
  (pivots en colonne) et **liste** (bloc + pivot surligné) ; chaque ligne **deep-linke la
  Visionneuse** (case réelle). État dans l'URL (partageable). Invite si aucun critère. Tests :
  contrat backend KWIC (`test_analyse`) + e2e a11y des 2 rendus (aligné + liste).
- Différé : recherche de lemme par **préfixe** (aujourd'hui exact/lemme), tags/note dans la
  ligne, export dédié de la concordance.

### ANA-4 · Keyness (log-vraisemblance) dans la comparaison — P3 · S
> La comparaison A/B utilise la diff de fréquence relative (favorise les mots fréquents).
- Done : métrique *keyness* sélectionnable ; remonte les mots rares-mais-distinctifs.

### ANA-5 · Distribution par trait morpho — P3 · M
> Aujourd'hui `champ=morph` = signature complète. Pour distribuer par trait isolé
> (Tense=Past…), normaliser `morph` en table `token_trait` (un trait/ligne).
- Done : distribution/filtre par trait UD ; perfs OK.

### ANA-6 · Détails recherche — P3 · S
- Recherche de lemme par **préfixe** (aujourd'hui exact) ; **tags/note** dans la concordance.

---

## 3. Modèle / NLP

### NLP-1 · Index `lg` définitif + rapport d'accord modèle↔humain — ✅ **Fait 2026-07-18 (B4)** · P2 · M
> Opération de transition Phase 1 → Phase 2 : figer l'index avec `fr_core_news_lg` hors
> ligne, et mesurer combien de corrections humaines le modèle retrouve seul (étalon).
- ✅ Fait (le **rapport**, code) : cœur `accord.py` (accord par champ lemme/POS/morpho — correction
  NULL = auto accepté, ou correction = auto — + confusion POS ; miroir de `tokens_effectifs`,
  ignore les obsolètes) exposé par la route `GET /api/analyse/accord`, l'outil
  `tools/rapport_accord.py` (`--json`/`--csv`) **et** le panneau **🎯 Accord** de l'Exploration.
  Tests : cœur/route + CLI + e2e a11y. Cf. `docs/rapport-accord.md`.
- **Ops** (hors code) : passer à `lg` = `BD_SPACY_MODEL=fr_core_news_lg` + `python -m spacy download
  fr_core_news_lg` + `tools/reindex_nlp.py`, puis lire le rapport (avant/après comparables).
- Différé : provenance **par modèle** sur chaque correction (NLP-2) ; accord **par annotateur** ;
  intégration au roll-up de qualité de la Collection.

### NLP-2 · Provenance modèle par correction — P3 · S
> Stocker `modele_auto` par correction pour une provenance fine (quel modèle a été corrigé).
- Done : colonne ajoutée + renseignée à la création de correction.

### NLP-3 · Normalisation de casse de l'OCR (capitales → minuscules) — P3 · M
> Le lettrage BD est en CAPITALES → l'OCR (EasyOCR) renvoie du tout-majuscule
> (« JE SUIS LÀ »). Fidèle au dessin, mais peu lisible en transcription ; et un
> `.lower()` naïf perd les noms propres, la majuscule de début de phrase, les sigles.
> Le NLP minuscule DÉJÀ avant l'analyse spaCy (interne) — ici il s'agit du texte
> STOCKÉ / AFFICHÉ (la transcription).
- À explorer (décision de conception) : (a) `lower()` simple — rapide, perd la casse
  signifiante ; (b) **re-casing « intelligent »** (phrase-case par segmentation + majuscule
  des entités via NER/EntityRuler — recoupe ANN-3 gazetteer) ; (c) **garder le tout-MAJ
  fidèle** et n'afficher en minuscules qu'à la lecture (transform non destructif).
  Trancher : modifier le texte STOCKÉ (perte de fidélité au lettrage) ou seulement
  l'affichage ? réversibilité ? option par album ?
- Done : l'OCR pré-remplit en casse normalisée (ou option), **sans écraser** une correction
  humaine (`only_empty`) ; choix documenté ; test.
- Note : tension avec la **fidélité au lettrage** (les capitales sont un trait du médium) →
  option **non destructive** préférable. Recoupe le minusculage de `pipeline/nlp.py` et
  ANN-3 (gazetteer pour restaurer les noms propres).

---

## 4. Infra / collaboratif

### INFRA-1 · Auth + déploiement Docker — P1 · L
> Préalable au multi-utilisateur en ligne (linguistes). Pile Authelia + Caddy + Redis déjà
> spécifiée (deploy/, docs/deploiement-docker.md). Déconnexion propre attendue.
- Done : accès protégé par auth, sessions, déconnexion ; déployé sur le VPS.
- Avancement 2026-06-26 — intégration app-side faite : lien de déconnexion + utilisateur connecté (en-tête `Remote-User`, var `BD_AUTH_LOGOUT_URL`, route `/api/moi`, tests dédiés). **Reste : build de l'image + déploiement réel sur le VPS** (hors de cette machine).

### INFRA-2 · Champ `auteur` des corrections via l'auth — ✅ Fait 2026-06-26 · P2 · S
> `token_correction.auteur` est NULL faute d'identité. **Dépend d'INFRA-1.**
- Done : les corrections enregistrent l'utilisateur connecté ; affiché/filtrable.
- Fait : `corriger_token` + `valider_grammaire` posent l'auteur (en-tête `Remote-User`) ;
  validation préserve le correcteur d'origine (COALESCE). Exposé dans `tokens_effectifs`
  (`corr_auteur`) + l'API tokens, affiché dans le panneau grammaire. Filtre `auteur`
  (et `a_auteur`/`b_auteur`) sur frequences/concordance/comparaison, symétrique de
  `provenance`. NULL en local (anonyme). 7 tests dédiés.

### INFRA-3 · Credentials WebDAV par utilisateur — P2 · M
> Mémoriser les identifiants WebDAV (`<id>@webdav`), **jamais** le compte maître Huma-Num.
  **Dépend d'INFRA-1.**
- Done : chaque utilisateur enregistre ses credentials WebDAV, stockés chiffrés.

### INFRA-4 · Retirer l'instrumentation `[import-timing]` — P2 · S
> Dette propre, en place pour mesurer la vitesse d'import sur le VPS.
- Done : instrumentation retirée une fois la mesure faite.

### INFRA-5 · Reprise `sessionStorage` — P3 · S
> Restaurer la dernière recherche/exploration en revenant par le **menu** (l'URL couvre
> déjà rechargement/partage).
- Done : revenir sur Recherche/Exploration via la nav restaure le dernier état.

### INFRA-6 · Sauvegardes automatiques vers ShareDocs — P3 · M
> Le dépôt manuel d'une sauvegarde existe ; l'automatiser (planifié).
- Done : sauvegarde périodique déposée sur ShareDocs, rotation.

---

## 5. UI/UX & navigation (transverse)

> **Largement fait — 2026-06-23.** UX-1 (nav transverse unifiée « Atelier ‖ Analyse »,
> générée d'un seul endroit par `theme.js`, `aria-current`) et UX-2 (en-tête en deux
> bandes, actions regroupées Traitement / Import-Export) sont livrés. UX-3 (hiérarchie
> & découvrabilité) et UX-4 (cohérence visuelle inter-surfaces) restent ouverts ;
> **UX-5 (annulation / undo) est ✅ fait (D1, 2026-07-18)**.

### UX-1 · Navigation unifiée — P2 · M
> 4 surfaces, en-têtes bricolés et légèrement différents. `nav.js` ne fait pour l'instant
> que `safeRetour` (sécurité), pas de barre commune.
- Faire : *shell* / barre de nav **partagée** (où suis-je + accès cohérent aux 4 surfaces).
- Done : nav identique et générée d'un seul endroit sur les 4 pages.

### UX-2 · Désencombrer l'en-tête Visionneuse — P2 · S
> ~9 boutons (passes ML, ShareDocs, export, sauvegarde…).
- Faire : regrouper (menu « Traiter » = Segmenter/Bulles/OCR ; « Fichier/Outils » =
  ShareDocs/Sauvegarde/Export) ; séparer **navigation** et **actions**.
- Done : en-tête lisible, actions regroupées par intention.

### UX-3 · Hiérarchie & découvrabilité des actions — P3 · M
> Clarifier les 4 modes (N/E/A/T), le panneau Grammaire ; primaire vs secondaire.
- Done : un nouvel utilisateur trouve les actions clés sans aide.

### UX-4 · Cohérence visuelle inter-surfaces — P3 · M
> Aligner espacements/typo/composants sur l'Exploration (récemment soignée).

### UX-5 · Annulation (undo) des actions d'annotation — ✅ **Fait 2026-07-18 (D1)**
> Aujourd'hui une action destructive est IRRÉVERSIBLE sans restaurer une sauvegarde
> complète : supprimer une région **cascade** (enfants + annotations + tags + tokens),
> déplacer/redimensionner écrase l'ancienne géométrie, une correction de token remplace
> la précédente. Seuls le **verrou de planche** et la **sauvegarde** (snapshot global)
> protègent — rien de granulaire ni de réversible à l'échelle du geste.
- **Livré** (option (b) **journal d'actions serveur**, tranchée par A3) : module `undo.py` qui
  **remonte le journal `evenement`** (append-only, `avant`/`apres`, snapshot **profond**) et
  rejoue l'inverse ; **pile** via événements `annulation` (append-only préservé : un acte annulé
  est référencé, jamais modifié). Endpoints `GET /api/undo/prochain` + `POST /api/undo` ; **UI
  Ctrl+Z** dans la Visionneuse (toast + rafraîchissement). Ajustement : les événements
  d'annotation ciblent `region_id` (stable). Écarté : (a) pile client (aveugle aux cascades),
  (c) soft-delete. Cf. `docs/undo.md`.
- **Périmètre livré** : région (créer/modifier/supprimer+cascade), annotation (note+tags),
  locuteur, présence. Actes machine non annulables. **Dormant** : correction grammaticale,
  validation, et **redo** (Ctrl+Y = annuler l'annulation).
- Note : forte valeur de SÛRETÉ (la suppression cascade est le geste le plus dangereux),
  complément FIN de la sauvegarde (filet « gros grain »). Recoupe SEG-1 (re-segmentation =
  autre source de perte de travail humain).

---

## 6. Accessibilité (transverse)

> **✅ Fait — 2026-06-23**, vérifié par **axe-core** (0 violation sérieuse/critique
> sur 4 surfaces × 4 thèmes + états interactifs ; non-régression câblée dans
> `tests/test_e2e_a11y.py`). A11Y-1 (contraste élevé, AA/AAA), A11Y-3 (clavier,
> `focus-visible`, skip-link, Échap), A11Y-4 (ARIA, landmarks, live regions) et
> A11Y-5 (`prefers-reduced-motion` + audit couleur) sont livrés. A11Y-2 (zoom UI)
> est livré **via la propriété CSS `zoom`** (persisté) ; la conversion des `px`
> résiduels en `rem` reste le seul reliquat. Tickets conservés pour mémoire.

### A11Y-1 · Thème « contraste élevé » — P2 · M
> 3ᵉ variante de tokens (au-delà clair/sombre), viser WCAG AA/AAA.
- Faire : jeu de tokens contraste élevé dans `theme.js` + respect `prefers-contrast: more`
  et `prefers-color-scheme`.
- Done : thème sélectionnable ; texte ≥ 4.5:1 (idéal 7:1).

### A11Y-2 · Zoom UI — P2 · M
> Contrôle **A− / A+** (ou %) changeant la taille de police racine, **persisté**.
- Faire : convertir les `px` figés résiduels en `rem` ; contrôle de zoom + mémorisation.
- Done : l'UI grossit/réduit sans casser la mise en page ; zoom navigateur OK aussi.

### A11Y-3 · Clavier & focus — P2 · M
- Faire : `:focus-visible` partout (token `--focus` déjà présent) ; ordre de tabulation ;
  menus/dropdowns au clavier ; **skip-link** « aller au contenu » ; `Échap` ferme aperçu/modales.
- Done : tout est atteignable et utilisable au clavier seul ; focus toujours visible.

### A11Y-4 · ARIA (invisible, ciblé) — P2 · M
> Aucune icône ajoutée ; métadonnées pour lecteurs d'écran, là où le HTML natif ne suffit pas.
- Faire : `aria-label` sur les **boutons-icônes** (↺ 🔒 ✏️ ✕ ↗…) ; **`aria-live`** sur les
  toasts et le « N résultats » ; **landmarks** (`<nav>`, rôles) ; **labels** reliés aux champs.
- Done : un lecteur d'écran annonce chaque action et les mises à jour dynamiques.

### A11Y-5 · Mouvement & couleur — P2 · S
- Faire : `prefers-reduced-motion` coupe transitions/animations ; **audit couleur** (aucune
  info codée par la seule couleur : provenance, types, A/B, statuts → doubler texte/icône) ;
  audit de contraste des thèmes existants.
- Done : aucune info perdue sans la couleur ; pas d'animation imposée.

---

## 7. Dette technique & sécurité (report de `AUDIT.md`)

> Restants de l'audit (`AUDIT.md`, 13 juin) au **2026-06-23**, recensés ici pour un
> suivi unique. Les items déjà corrigés (verrou ML global, nettoyage du master,
> échappement des tags, borne pixels, courses recherche/jobs) n'y figurent plus.

### SEC-1 · Garde HTTPS + normalisation de chemin ShareDocs (SSRF) — ✅ Fait 2026-06-24 · P2 · S
> `configure()` accepte toute URL (aucun contrôle `scheme == "https"`) et le `chemin`
> distant n'est pas normalisé des `..` → identifiants Basic exposables sur `http://`,
> SSRF/traversal théoriques. Cf. `docs/deploiement-docker.md` (« reste à corriger côté code »).
- ✅ Fait 2026-06-24 : `https` imposé (opt-out `BD_SHAREDOCS_ALLOW_HTTP`) + segments `..` rejetés dans `_join` (anti-traversée) + 5 tests MockTransport. (Allowlist d'hôte, IP internes et redirections non suivies étaient déjà en place.)

### SEC-2 · CSP + CSRF — P3 · M
> Pas de Content-Security-Policy dans les templates ; les `apiSend` POST/PUT/DELETE
> n'envoient ni jeton ni en-tête custom. Risque faible en local, à traiter avant exposition réseau.
- Done : en-tête CSP servi ; protection CSRF si des sessions sont un jour introduites (dépend d'INFRA-1).

### DB-1 · `UNIQUE(album_id, numero)` + gestion de collision — ✅ Fait 2026-06-24 · P2 · S
> `MAX(numero)+1` sans contrainte : deux imports concurrents sur le même album peuvent
> produire le même numéro → collision de noms de fichiers + doublon logique.
- ✅ Fait 2026-06-24 : index UNIQUE posé en migration (v13) après dédoublonnage ; numéro alloué AVANT écriture (numéro explicite déjà pris → 409 sans écraser) ; course résiduelle → 409 via l'index ; +5 tests. *Réservation atomique « pure » (fenêtre d'écrasement de fichier en course concurrente) différée — non justifiée en mono-utilisateur ; la contrainte empêche déjà le doublon logique.*

### CONC-1 · Cache de crop, registre de jobs, annulation — P3 · M
> `_crop_lock` englobe crop + resize + encodage (tout sérialisé, TIFF gardé ouvert sans TTL) ;
> le registre `_jobs` grossit sans purge (fuite lente) ; l'annulation n'est pas préemptive
> (un Kumiko/OCR long ne s'interrompt pas, le subprocess Kumiko n'est pas tué).
- Done : verrou réduit au dict de cache + TTL/fermeture ; purge des vieux jobs ; annulation réactive.

### CONC-2 · Cycle de vie / empreinte mémoire des moteurs ML — v1 fait 2026-06-24 · P2 · M
> Les moteurs (Kumiko/opencv, bulles YOLOv8/torch, OCR EasyOCR/torch, spaCy) se chargent
> paresseusement mais restent **résidents** pour la vie du process : trois modèles torch +
> spaCy ensemble ⇒ empreinte élevée. Sur poste/VPS contraint, enchaîner segmentation → bulles
> → OCR → NLP peut **tuer le process (OOM)** — observé le 2026-06-24 en annotant une vraie
> planche (process tué SANS traceback Python ; les données committées étaient saines). Le
> `ML_LOCK` sérialise l'inférence mais ne **libère** rien.
- À explorer : (a) **déchargement** des modèles inutilisés (TTL) ; (b) un seul gros modèle à la
  fois (décharger bulles avant OCR) ; (c) **worker ML séparé** (process isolé, redémarrable —
  un OOM n'emporte pas l'API) ; (d) a minima **documenter l'empreinte** + recommander les passes
  une à une. Recoupe CONC-1 (cycle de vie des ressources) et le déploiement Docker (dimensionnement).
- ✅ v1 fait 2026-06-24 : déchargement par moteur (`liberer`/`est_charge`) + orchestrateur `pipeline/modeles.py` ; libère en **fin de lot**, **avant la passe interactive** (l'autre modèle torch) et **à la demande** (`POST /api/ml/liberer`) ; modèles résidents exposés dans `/api/sante` ; +5 tests. **Reste différé** : isolation subprocess (option (c) — seule à garantir le zéro-OOM ; tant qu'un modèle torch est chargé, le runtime occupe la RAM).
- Contournement immédiat : lancer les passes ML **séparément** (et redémarrer entre les grosses).

### SEG-1 · Préservation du travail humain à la re-segmentation — ✅ Fait 2026-06-24 · P2 · L
> AUDIT passe 3 : **S2** (deux cases annotées → une seule : doublon géométrique annoté),
> **S3** (transfert d'annotation vers case quasi-disjointe, aucun seuil de recouvrement),
> **S7** (re-rattachement à une case périmée conservée), **S4** (dédup bulles sans IoU).
> Logique la plus délicate — **à corriger avec tests de non-régression dédiés**, pas à la volée.
- ✅ Fait 2026-06-24 : **S3** seuil de recouvrement (`_best_overlap`, 50 %) ; **S2** fusion ambiguë → les 2 cases annotées **conservées** (déterministe, zéro perte) ; **S7** ré-rattachement aux **nouvelles** cases seulement ; **S4** dédup bulles par **IoU**. +6 tests dédiés (dont S2 bout-en-bout).

### QA-1 · Épinglage des versions + lockfile — ✅ Fait 2026-06-24 · P3 · S
> Bornes `>=` ouvertes (fastapi, ultralytics, easyocr, pillow…) → builds non reproductibles ;
> `numpy`/`opencv-python-headless`/`requests` (deps réelles de Kumiko) seulement en commentaires.
- ✅ Fait 2026-06-24 : `requirements.lock` (pins exacts des directes, connus-bons, dry-run vert) + `requirements-kumiko.txt` (deps Kumiko enfin **installables**, plus en commentaire) ; commentaires des specs mis à jour. Verrou des *directes* (pas un pip-compile transitif : wheels ML spécifiques à la plateforme — cf. en-tête du lock).

### QA-2 · `common.js` — dédup du frontend — ✅ Fait 2026-06-24 · P3 · S
> `$`, `apiGet`, `apiSend`, `escapeHtml`, `toast` recopiés à l'identique dans
> `viewer.js`/`recherche.js`/`corpus.js` (~80 lignes).
- ✅ Fait 2026-06-24 : `static/lib/common.js` (UMD) expose `$` / `apiGet` / `apiSend` / `escapeHtml` (+ alias `esc`) / `toast` en globals ; −97 lignes dans les 4 surfaces ; test JS (`escapeHtml`) + smoke globals sur les 4 pages.

### QA-3 · Tests de concurrence & d'analyse — ✅ Fait 2026-06-24 · P2 · M
> La sérialisation des jobs, la contention worker↔requêtes sous WAL/`busy_timeout` et la
> cohérence du backup *pendant une écriture* ne sont pas testées ; les routes `/api/analyse/*`
> et la correction de tokens n'ont **aucun test serveur dédié** (constat 2026-06-23).
- ✅ Fait 2026-06-24 : sérialisation **deux jobs** (`_run_lock`) + **backup cohérent sous écriture** (VACUUM INTO / isolation WAL) ajoutés ; endpoints **analyse/grammaire + correction de tokens** déjà couverts (`test_analyse` + `test_regressions`, NLP actif). Contention worker↔lecteur testée via mock (→ 409) ; contention WAL *réelle* différée (lente, faible valeur — teste SQLite, pas notre code).

---

## Ordre conseillé (modifiable, révisé 2026-06-24)
1. ~~**ANN-2 « mince »**~~ (entité personnage + locuteur + attributs facettés & émergents) — **✅ Fait 2026-06-24** (schéma v11 + API + UI, vocabulaire émergent ; cf. `docs/personnages-et-attribution.md`). Suite **§14** (pivot : l'image croise la langue) : brique **(a)** « boîte → identité + profil » **livrée** (schéma v13) ; (b)/(c) + attributs riches + scène **dormants**.
2. ~~**SEC-1 + DB-1**~~ (SSRF ShareDocs, UNIQUE numéro) — **✅ Fait 2026-06-24** (§7), avant toute exposition réseau.
3. ~~ANN-1~~ → **absorbé par ANN-2** : le vocabulaire devient une structure facettée *émergente*, plus une liste figée à trancher en amont.
4. **INFRA-1/2** (auth) — **✅ app-side fait 2026-06-26** : INFRA-1 (utilisateur connecté + déconnexion, route `/api/moi`) et INFRA-2 (auteur des corrections, filtrable). **Reste : déploiement Docker réel sur le VPS** (hors machine de dev) + INFRA-3 (credentials WebDAV par utilisateur).
5. ~~**SEG-1**~~ (préservation segmentation) — **✅ Fait 2026-06-24** (S2/S3/S4/S7 + tests dédiés). *(QA-3 — tests concurrence/analyse : ✅ fait.)*
6. Le reste (ANN-2/3/4, ANA-2/3, NLP, CONC-1, UX-3/4) au fil du besoin réel.

*Faits : A11Y-1→5 (§6), nav unifiée + désencombrement (UX-1/UX-2), **ANA-1** (§2), **ANN-2 « mince »** (§1), **SEC-1** + **DB-1** + **QA-2** + **QA-3** + **QA-1** + **CONC-2 (v1)** + **SEG-1** (§7), **INFRA-1** (app-side) + **INFRA-2** (§4).*
