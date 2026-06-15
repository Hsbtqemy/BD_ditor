# Backlog exécutable — BD Annotator

> Établi le 2026-06-15. Recense les pistes ouvertes **après** les lots livrés
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

### ANN-2 · Entité « personnage » + lien bulle→personnage — P2 · L
> « Représentation des minorités » = surtout *qui* est représenté ; idiolectes, registres
> par personnage. Aujourd'hui `personnage` n'est qu'un type de région, sans identité.
- Faire : table personnage (récurrent, attributs) ; lien `region(bulle) → personnage` ;
  UI d'attribution ; facette d'analyse « par personnage ».
- Done : attribuer une bulle à un personnage ; recherche/exploration/comparaison
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

## Ordre conseillé (modifiable)
1. **ANA-1** (filtre tags) — petit, débloque la finalité côté analyse.
2. **UX-2 + A11Y (1→5)** — adoption par l'équipe, faisable sans corpus, transverse.
3. **ANN-1** (schéma émotions/minorités) — la finalité ; nécessite une décision de vocabulaire.
4. **INFRA-1→3** (auth/déploiement) — avant la mise en ligne multi-linguiste.
5. Le reste (ANN-2/3/4, ANA-2/3, NLP, raffinements) au fil du besoin réel.
