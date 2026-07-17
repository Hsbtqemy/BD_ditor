# Roadmap — BéDéditeur

> **Vue stratégique par PISTES**, en complément des suivis ticket-par-ticket :
> [`docs/backlog.md`](backlog.md) (features + dette §7) et [`AUDIT.md`](../AUDIT.md)
> (audit technique, 5 passes). Ce document ne recopie pas les tickets : il **regroupe
> l'ouvert en pistes**, fixe le **cap** et l'**ordre conseillé**. Établi le **2026-07-16**.
>
> **Cap courant : piste A — FAIR / dépôt.**

**Légende** — Priorité : **P1** (finalité / bloquant), **P2** (important), **P3** (raffinement).
Effort : **S** (< ½ j), **M** (1-2 j), **L** (≥ 3 j ou décision de conception requise).

---

## Où on en est (juillet 2026)

Beaucoup est **livré** — l'ouvert ci-dessous est ce qui *reste*, pas l'ensemble.

- **Annotation & analyse** : entité personnage + locuteur + attributs facettés émergents
  (ANN-2, v11) ; analyse filtrable par tags (ANA-1) ; recherche FTS5 + exploration linguistique.
- **Accessibilité** : WCAG 2.1 AA vérifié axe-core (A11Y-1→5), non-régression câblée.
- **UI/nav** : navigation transverse unifiée + en-tête désencombré (UX-1/2).
- **Infra** : auth *app-side* (INFRA-1 : utilisateur connecté, déconnexion, `/api/moi`) +
  auteur des corrections (INFRA-2) ; cycle de vie des modèles ML v1 (CONC-2).
- **Dette/sécurité** : les 5 passes d'audit largement corrigées (parent_id validé, bornes
  géométriques, SSRF/HTTPS ShareDocs, `UNIQUE(album_id, numero)`, TEI XML-safe, lockfile…).
- **FAIR / métadonnées** *(chantier récent, hors backlog)* : exports additifs
  description / records / IIIF (conforme, prouvé via `iiif-prezi3`), paradonnée (versions +
  révision git + SBOM), droits **descriptifs**, **palier Collection (v14)**, **descriptif N0
  Zotero-like (v15)** + **crosswalk DC/DataCite (A2)**, et le **journal de provenance/audit
  (v16, A3)** — `activite`/`evenement` append-only, indicateurs de dérive, export PROV-O/TEI.
  Cf. [`docs/export-metadonnees.md`](export-metadonnees.md),
  [`docs/dictionnaire-metadonnees.md`](dictionnaire-metadonnees.md),
  [`docs/provenance-audit.md`](provenance-audit.md).

---

## Piste A — FAIR / dépôt  ⟵ **CAP COURANT**

> Rendre une **collection réellement déposable** (Nakala / HAL) et pleinement réutilisable.
> Source : dictionnaire (« à prévoir ») + travaux récents. Additif — n'altère pas les
> exports de contenu existants.

| # | Item | Effort | Pourquoi |
|---|---|---|---|
| ~~**A1**~~ | ✅ **Fait 2026-07-17 (v15)** — **enrichissement descriptif N0** : `contribution` Zotero-like (nom + rôle contrôlé-ouvert `contribution_role`, DCterms / MARC), 8 champs d'édition (`date_edition`, `date_originale`, `langue`, `type_oeuvre`, `lieu_edition`, `edition_tirage`, `isbn`, `format_physique`). Boucle complète : schéma + API + export + UI Bibliothèque | M–L | qualité bibliographique = condition d'un dépôt crédible |
| ~~**A2**~~ | ✅ **Fait 2026-07-17** — **Crosswalk Dublin Core & DataCite** : `tools/crosswalk_depot.py` (paternité Zotero, notices album + collection, DC JSON-LD + DataCite JSON/XML, garde-fou champs obligatoires ; spec `docs/crosswalk-depot.md`). Rend le dépôt *machine-ready* | M | complète l'export descriptif ; DOI frappé par l'entrepôt |
| ~~**A3**~~ | ✅ **Fait 2026-07-17 (v16)** — **Journal de provenance / audit (N8/N2)** : `activite` (runs) + `evenement` (append-only, avant/après) + `regions.activite_id`/`touche`/`date_modification`, câblés aux passes ML (`journal.passe_ml`) et aux routes humaines (agent capté par contextvar depuis l'auth) ; indicateurs dérivés (`indicateurs_provenance`) dans la paradonnée ; export **PROV-O** + TEI `revisionDesc` (`tools/provenance_export.py`). Le journal **survit à la suppression** → **débloque D1 (undo)**. Cf. `docs/provenance-audit.md` | L | qualifie *qui a produit quoi* ; substrat commun avec D1 |
| A4 | **Lexique situé SKOS (N7)** — `definition`, `note_portee`, état `provisoire→défini`, portée d'appartenance `collection_id`, indicateur « % défini » | M | vocabulaire facetté réutilisable et documenté |
| A5 | **Alignement d'autorité (N6)** — `personnages` → URI Wikidata / VIAF / IdRef (`skos:exactMatch`) | M | interopérabilité des entités |
| A6 | **Matériel (N1)** — `dpi`, `mode` colorimétrique, dimensions physiques, source de numérisation | S–M | complétude (PREMIS / DC:format) |

*Dormants (déclenchables plus tard) : gel versionné + PID/DOI au niveau collection,
surcharge des droits par album (`statut_diffusion`/`base_legale`), appartenance fine
planche/région, définition contextuelle `valeur_definition`.*

**Prochain incrément (A1)** — courte passe de conception d'abord : modèle `contribution`
(table N-N `(album, nom, rôle)`, rôle en vocabulaire contrôlé-ouvert façon tags/attributs),
puis champs d'édition. Migration **v15**. Le `responsables` JSON de la Collection a déjà été
posé « façon `contribution` » pour converger. **`base_legale` reste un prérequis hors code**
(institution + source des scans, à établir juridiquement) — décrire, pas imposer.

---

## Piste B — Finalité scientifique (annotation & analyse)

> La raison d'être : étude des émotions / de la représentation des minorités, par **codage
> humain**, et analyse linguistique du corpus. Source : [`backlog.md`](backlog.md) §1-3.

| # | Item | Prio·Effort | Note |
|---|---|---|---|
| **B1** | **ANN-1 — vocabulaire contrôlé émotions / représentation** | P1·L | **décision d'équipe en amont** : liste fermée typée *ou* facettes émergentes d'ANN-2 déjà en place ? implique les linguistes |
| **B2** | ANA-3 — **vue KWIC** (concordance : backend `/api/analyse/concordance` existe, **UI manque**) | P2·M | « tous les impératifs en contexte » |
| B3 | ANA-2 — tableaux croisés 2D (tag×POS, émotion×type de région…) | P2·M | on n'a que des distributions 1-D + comparaison A/B |
| B4 | NLP-1 — index `fr_core_news_lg` + rapport d'accord modèle↔humain | P2·M | transition Phase 1→2 |
| B5 | ANN-4 — statut de relecture par planche (dérivé + forçable) | P2·S | coordination équipe |
| B6 | ANN-5 — accord inter-annotateurs | P3·M | **débloqué** (INFRA-2 `auteur` fait) |
| — | ANN-3 gazetteer · ANA-4 keyness · ANA-5 traits morpho · ANA-6 · NLP-2/3 | P3 | au fil du besoin réel |

---

## Piste C — Mise en production / collaboratif

> Passer au multi-utilisateur en ligne (linguistes). Source : [`backlog.md`](backlog.md) §4, §7.

| # | Item | Prio·Effort | Note |
|---|---|---|---|
| **C1** | **INFRA-1 — déploiement Docker réel sur le VPS** | P1·L | app-side **fait** ; reste le build d'image + déploiement (hors machine de dev). Cf. [`docs/deploiement-docker.md`](deploiement-docker.md) |
| C2 | INFRA-3 — credentials WebDAV **par utilisateur** (chiffrés) | P2·M | dépend C1 |
| C3 | SEC-2 — **CSP** (faisable maintenant) + CSRF | P3·M | CSRF dépend des sessions (C1) ; à traiter avant exposition réseau |
| C4 | CONC-2 v2 — **isolation subprocess ML** (worker séparé, redémarrable) | P2·M | v1 fait (déchargement) ; seule option garantissant le **zéro-OOM** |
| — | CONC-1 (cache crop TTL + purge jobs + annulation préemptive) · INFRA-4 (retirer `[import-timing]`) · INFRA-5 (reprise `sessionStorage`) · INFRA-6 (sauvegardes auto ShareDocs) | P2-P3 | hygiène / confort |

---

## Piste D — Sûreté & dette technique

> Consolidation. Source : [`backlog.md`](backlog.md) §7 + restants d'[`AUDIT.md`](../AUDIT.md).

| # | Item | Prio·Effort | Note |
|---|---|---|---|
| **D1** | **UX-5 — undo des actions d'annotation** | P2·L | **forte valeur de sûreté** : la suppression cascade est le geste le plus dangereux, aujourd'hui irréversible sans restaurer une sauvegarde. **Débloqué par A3 (v16)** : le journal `evenement` survit à la suppression et porte l'instantané **profond** (avant/après) → décision tranchée (**journal serveur**) ; reste l'endpoint de restauration + l'UI |
| ~~**D2**~~ | ✅ **Fait 2026-07-16** — B5 : `_migrate` **gate par `user_version`** (refus de rétrograder + court-circuit si à jour + convention `if version < N`) ; test dédié. Assaini avant A1 | S | — |
| — | B6 (transitions de statut + régression `annotee`→`segmentee`) · B7 (injection formule CSV — export **app**, distinct des tools) · B8 (`/api/sauvegarde` sans try/except → 500) · B9 (titre d'album vide accepté) · F5 (deep-link silencieux, aucun toast) · F6-F8 · T2/T4 (tests faibles) · S1/S5/S6/O1 (latents segmentation) · A11Y-2 (reliquat `px`→`rem`) · UX-3/UX-4 | mineurs | quick wins, à la demande |

---

## Séquence conseillée (2026-07-16, modifiable)

1. **[Cap] Piste A — dépôt utilisable** : ~~**A1** (descriptif N0)~~ ✅ **fait (v15)** →
   ~~**A2** (crosswalk DC/DataCite)~~ ✅ **fait (2026-07-17)** → ~~**A3** (journal de
   provenance)~~ ✅ **fait (v16, 2026-07-17)** → **A4** (lexique situé SKOS) devient le
   prochain cran. Une collection est déposable (DOI frappé par l'entrepôt) et sa provenance
   est tracée/exportable (PROV-O).
2. ~~**D2** (gating `_migrate`)~~ — ✅ **fait 2026-07-16**, avant de toucher au schéma en A1.
3. **Ouvrir la décision B1** en parallèle (vocabulaire émotions) — elle exige une discussion
   d'équipe *en amont*, autant l'amorcer tôt.
4. Selon le cap suivant : **C1** (déploiement VPS) si le multi-utilisateur devient réel —
   débloque C2, C3 (CSRF), B6 (accord inter-annotateurs).
5. **A3 / D1** ensemble quand la provenance devient prioritaire (même journal append-only).

## Dépendances notables

- **C1 (auth déployée)** débloque → C2 (WebDAV/utilisateur), C3 (CSRF), et sert B6.
- ~~**A3 (journal de provenance)** et **D1 (undo serveur)** partagent le **même journal
  append-only**~~ → **A3 livré (v16)** : le journal `evenement` (avant/après, survit à la
  suppression) EST le substrat de D1 ; ne reste que l'endpoint de restauration + l'UI.
- **A4 (portée SKOS `collection_id`)** s'appuie sur le palier Collection (v14, fait).
- **B1** est une **décision de conception** (vocabulaire) : à trancher avec les linguistes
  avant tout code.
