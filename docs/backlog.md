# Backlog exécutable — BD Annotator

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

### ANN-1 · Schéma d'annotation contrôlé (émotions, représentation) — P1 · L
> L'étude des émotions/minorités repose sur du **codage humain** ; aujourd'hui les tags
> sont **libres** → inagrégeables (« colère » ≠ « colere »). C'est le vrai socle manquant.
- Faire : décider avec l'équipe un/des **vocabulaires contrôlés** (catégories d'émotion,
  marqueurs de représentation) ; modèle de données (tags « typés »/namespacés, ou table
  dédiée) ; UI de saisie en **liste fermée** (+ libre en complément) ; exposer comme facette.
- Done : tagger une région depuis un vocabulaire fermé ; Exploration/Recherche peuvent
  **filtrer et distribuer** par catégorie ; agrégation sans doublon orthographique ; test.
- Note : décision de conception (vocabulaire) **en amont** — implique les linguistes.

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

### ANN-4 · Statut de relecture explicite par planche — P2 · S
> L'idée « Attente » : suivre quelles planches restent à relire (coordination équipe).
- Faire : statut **dérivé** par défaut (des provenances de tokens), **forçable** (override) ;
  badge Bibliothèque + filtre.
- Done : une planche affiche « à faire / en cours / faite » ; filtrable ; override possible.

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

### ANA-2 · Croisements (tableaux croisés, 2 dimensions) — P2 · M
> Conçu (« croisements ») mais non fait : tag × POS, émotion × type de région, auteur ×
> temps verbal… (on n'a que distributions 1-D + comparaison A/B).
- Faire : endpoint croisé (champ × facette) ; UI tableau croisé dans Exploration ; drill.
- Done : afficher une matrice de fréquences à deux axes ; cellule cliquable → preuves.

### ANA-3 · Vue concordance KWIC dédiée — P2 · M
> `/api/analyse/concordance` (lot 2) existe **sans UI**. La modalité KWIC (une ligne par
> occurrence, mot surligné en contexte) manque.
- Faire : surface/onglet KWIC ; une ligne par occurrence avec contexte gauche/droit ;
  drill vers l'aperçu multimodal.
- Done : « tous les impératifs en contexte » s'affiche en concordance ; export.

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

### NLP-1 · Index `lg` définitif + rapport d'accord modèle↔humain — P2 · M
> Opération de transition Phase 1 → Phase 2 : figer l'index avec `fr_core_news_lg` hors
> ligne, et mesurer combien de corrections humaines le modèle retrouve seul (étalon).
- Faire : `BD_SPACY_MODEL=fr_core_news_lg` + `tools/reindex_nlp.py` ; requête d'accord
  (`tokens.pos` auto vs `token_correction.pos` humain).
- Done : index `lg` produit ; rapport d'accord consultable.

### NLP-2 · Provenance modèle par correction — P3 · S
> Stocker `modele_auto` par correction pour une provenance fine (quel modèle a été corrigé).
- Done : colonne ajoutée + renseignée à la création de correction.

---

## 4. Infra / collaboratif

### INFRA-1 · Auth + déploiement Docker — P1 · L
> Préalable au multi-utilisateur en ligne (linguistes). Pile Authelia + Caddy + Redis déjà
> spécifiée (deploy/, docs/deploiement-docker.md). Déconnexion propre attendue.
- Done : accès protégé par auth, sessions, déconnexion ; déployé sur le VPS.

### INFRA-2 · Champ `auteur` des corrections via l'auth — P2 · S
> `token_correction.auteur` est NULL faute d'identité. **Dépend d'INFRA-1.**
- Done : les corrections enregistrent l'utilisateur connecté ; affiché/filtrable.

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
> & découvrabilité) et UX-4 (cohérence visuelle inter-surfaces) restent ouverts.

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

### SEG-1 · Préservation du travail humain à la re-segmentation — P2 · L
> AUDIT passe 3 : **S2** (deux cases annotées → une seule : doublon géométrique annoté),
> **S3** (transfert d'annotation vers case quasi-disjointe, aucun seuil de recouvrement),
> **S7** (re-rattachement à une case périmée conservée), **S4** (dédup bulles sans IoU).
> Logique la plus délicate — **à corriger avec tests de non-régression dédiés**, pas à la volée.
- Done : seuil de recouvrement à l'`_best_overlap` ; aucun doublon annoté ; IoU sur les bulles ; tests.

### QA-1 · Épinglage des versions + lockfile — P3 · S
> Bornes `>=` ouvertes (fastapi, ultralytics, easyocr, pillow…) → builds non reproductibles ;
> `numpy`/`opencv-python-headless`/`requests` (deps réelles de Kumiko) seulement en commentaires.
- Done : `requirements.lock` (pip-tools) ; deps Kumiko déclarées de façon installable.

### QA-2 · `common.js` — dédup du frontend — ✅ Fait 2026-06-24 · P3 · S
> `$`, `apiGet`, `apiSend`, `escapeHtml`, `toast` recopiés à l'identique dans
> `viewer.js`/`recherche.js`/`corpus.js` (~80 lignes).
- ✅ Fait 2026-06-24 : `static/lib/common.js` (UMD) expose `$` / `apiGet` / `apiSend` / `escapeHtml` (+ alias `esc`) / `toast` en globals ; −97 lignes dans les 4 surfaces ; test JS (`escapeHtml`) + smoke globals sur les 4 pages.

### QA-3 · Tests de concurrence & d'analyse — P2 · M
> La sérialisation des jobs, la contention worker↔requêtes sous WAL/`busy_timeout` et la
> cohérence du backup *pendant une écriture* ne sont pas testées ; les routes `/api/analyse/*`
> et la correction de tokens n'ont **aucun test serveur dédié** (constat 2026-06-23).
- Done : tests de contention (deux jobs, worker↔lecteur, backup sous écriture) ; couverture des endpoints d'analyse/grammaire.

---

## Ordre conseillé (modifiable, révisé 2026-06-23)
1. ~~**ANN-2 « mince »**~~ (entité personnage + locuteur + attributs facettés & émergents) — **✅ Fait 2026-06-24** (schéma v11 + API + UI, vocabulaire émergent ; cf. `docs/personnages-et-attribution.md`). Différé : présence (2ᵉ graphe), attributs riches, entité « scène ».
2. **SEC-1 + DB-1** (SSRF ShareDocs, UNIQUE numéro) — sécurité/intégrité, petits, avant toute exposition.
3. ~~ANN-1~~ → **absorbé par ANN-2** : le vocabulaire devient une structure facettée *émergente*, plus une liste figée à trancher en amont.
4. **INFRA-1→3** (auth/déploiement) — avant la mise en ligne multi-linguiste.
5. **SEG-1 + QA-3** (préservation segmentation + tests de concurrence/analyse) — fiabilise la logique délicate.
6. Le reste (ANN-2/3/4, ANA-2/3, NLP, CONC-1, QA-1/2, UX-3/4) au fil du besoin réel.

*Faits : A11Y-1→5 (§6), nav unifiée + désencombrement (UX-1/UX-2), **ANA-1** (§2), **ANN-2 « mince »** (§1), **SEC-1** + **DB-1** + **QA-2** (§7).*
