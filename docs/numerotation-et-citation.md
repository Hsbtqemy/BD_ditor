# Numérotation éditoriale & citation des cases — spécification (chantier Citation)

> Conception menée le 2026-06-15, en discussion de fond.
> **Statut : Lots 0–3 implémentés le 2026-06-15.** Récit/paratexte + numéro éditorial
> dérivé (lot 0), citation `pl·c` des cases et `pl·c·b` des bulles + repère global
> `idx/total` (lots 1–2), citation portée par tous les exports savants (lot 3).
> Backlog exécutable d'un chantier « Citation » : **citer précisément une case et une
> bulle à l'échelle d'une bande dessinée entière**.

## 1. Pourquoi

On va intégrer des **BD entières** (nombre de cases conséquent). Le corpus se veut
*citable* par des chercheurs : il faut une référence **précise et stable** vers
une case, à l'échelle de l'album — aujourd'hui inexistante. Les deux nombres déjà
présents ne conviennent pas tels quels :

- `regions.id` — figé à la détection, donc stable, mais **ni lisible ni
  géographique** (identifiant technique).
- `regions.ordre` — rang de lecture **recalculé**, mais **local** (repart à 1 dans
  chaque planche / chaque case) et mélange cases + bulles orphelines au 1ᵉʳ niveau
  (cf. [pipeline/ordering.py](../pipeline/ordering.py)).

Et surtout : **`planches.numero` = ordre d'import**, attribué en `MAX(numero)+1`
(cf. [pipeline/ingest.py](../pipeline/ingest.py)). Il n'existe **aucune notion de
couverture / paratexte** dans le schéma. Donc « planche P » désigne aujourd'hui une
*position de fichier* — la couverture devient « planche 1 », la 1ʳᵉ vraie planche
« planche 4 ». Inutilisable pour citer.

## 2. Décisions figées

| # | Décision |
|---|----------|
| **D1** | **Deux nombres, deux rôles.** (a) Clé de citation **stable** `pl.P · cN`, ancrée sur le *numéro éditorial* de planche. (b) Repère **global** `idx/total` (confort de navigation, **non citable**). L'`id` SQLite figé reste l'**ancre permanente** par-dessous. |
| **D2** | **Modèle « on écarte, on ne spécifie pas ».** Toute planche est `recit` **par défaut** ; on marque explicitement certaines planches `paratexte` (couverture, faux-titre, garde, pub, cul-de-lampe…). |
| **D3** | **Numéro éditorial dérivé**, jamais saisi : rang de la planche parmi les `role='recit'` du même album, trié par `numero`. Robuste aux trous de `numero` et aux suppressions. Une planche paratexte n'a **pas** de numéro éditorial — citée par son libellé. |
| **D4** | **Rang de case = sur les cases seules** (`ROW_NUMBER` sur les `type='case'` triées par `ordre`) → insensible à une bulle orpheline intercalée au 1ᵉʳ niveau. |
| **D5** | **Tout est dérivé / calculé à la volée, jamais stocké** → toujours actualisé. Conséquence assumée : les numéros **bougent** aux ré-segmentations et reclassements (récit ⇄ paratexte). C'est précisément pourquoi la citation est **ancrée sur la planche** (impact local, pas en cascade) et pourquoi l'`id` figé reste l'ancre permanente. |

Le terme **paratexte** est pris au sens de Genette (tout ce qui entoure le récit).
Le champ est **extensible** : on pourra un jour distinguer `couverture` / `garde` /
`pub` sans nouvelle migration ; l'interface, elle, ne propose au départ que la
bascule **récit ⇄ paratexte**.

## 3. Modèle de données

Une seule colonne, ajoutée à `planches` :

```sql
role TEXT NOT NULL DEFAULT 'recit'   -- 'recit' = narratif (numéroté) ; tout autre = paratexte (écarté)
```

Migration idempotente `SCHEMA_VERSION 9 → 10` dans `_migrate()`
(cf. [database.py](../database.py), même mécanique que `validee`/`verrouillee`).
Toute base existante bascule en `recit` automatiquement (défaut de colonne).

**Dérivations** (aucun stockage) :

- *Numéro éditorial d'une planche* — `NULL` si paratexte, sinon
  `COUNT(*) FROM planches WHERE album_id = ? AND role = 'recit' AND numero <= ?`.
- *Rang de case dans sa planche* — position de la case dans
  `ROW_NUMBER() OVER (ORDER BY ordre) … WHERE type='case'`.
- *Index global de case dans l'album* — cases récit des planches de numéro
  inférieur + rang local ; *total* = cases récit de l'album.

---

## Lot 0 — Fondation : récit / paratexte + numéro éditorial

> **Prérequis de tout le reste.** Tant qu'une planche n'est pas correctement
> numérotée, aucune citation n'est juste. Testable seul : importer [couv, p1, p2],
> marquer la couv paratexte, vérifier que p1 devient « planche 1 ».
>
> **✅ Implémenté le 2026-06-15** (T0.1–T0.4).

- **T0.1 — Schéma & migration**
  - *But* : colonne `role` sur `planches`, défaut `'recit'`.
  - *Fichiers* : [database.py](../database.py) (`SCHEMA_SQL` + étape v9→v10 dans
    `_migrate`, `SCHEMA_VERSION = 10`).
  - *Fait quand* : base neuve **et** base existante exposent `role`, défaut `recit` ;
    migration ré-exécutable sans erreur.
  - *Test* : [tests/test_database.py](../tests/test_database.py) — colonne présente,
    défaut `recit`, idempotence.

- **T0.2 — Dérivation du numéro éditorial**
  - *But* : helper `numeros_editoriaux(conn, album_id)` (et/ou unitaire par planche)
    appliquant D3.
  - *Fichiers* : [database.py](../database.py) (helpers de lecture).
  - *Fait quand* : couverture → `None` ; planches récit → `1, 2, 3…` ; insérer un
    paratexte au milieu décale d'un cran les suivantes ; trous de `numero` ignorés.
  - *Test* : unitaire dédié (jeu : couv + 3 pages + pub intercalée).

- **T0.3 — API rôle**
  - *But* : route `PATCH /api/planches/{id}/role` (corps `{role: 'recit'|'paratexte'}`)
    et exposer `role` et `numero_editorial` dans les payloads planches.
  - *Fichiers* : [main.py](../main.py) (route + `album_planches` + payload planche).
  - *Fait quand* : bascule persistée ; `numero_editorial` présent dans la liste
    d'album ; valeur de rôle inconnue rejetée (422/400).
  - *Test* : [tests/test_api.py](../tests/test_api.py).

- **T0.4 — Interface : marquer paratexte / afficher le numéro éditorial**
  - *But* : badge « Paratexte » vs « planche N » + bouton de bascule.
  - *Fichiers* : [static/corpus.js](../static/corpus.js) / [templates/corpus.html](../templates/corpus.html),
    liste des planches du visualiseur [static/viewer.js](../static/viewer.js),
    [templates/index.html](../templates/index.html).
  - *Fait quand* : marquer la couverture paratexte → la 1ʳᵉ planche récit s'affiche
    « planche 1 » sans rechargement complet.
  - *Test* : vérification manuelle (pas de tests front dans le repo).

---

## Lot 1 — Citation des cases

> Construit sur le numéro éditorial du lot 0. **Périmètre retenu : complet** (T1.1–T1.5).
>
> **✅ Implémenté le 2026-06-15.** Helper `citations_regions()` (batch), citation portée
> par `/planches/{id}/regions` et la recherche ; détail, étiquette image (`c2`),
> barre d'état (`cases/album`) et carte de résultat l'affichent.

- **T1.1 — Helper de citation (case)**
  - *But* : pour une case, renvoyer `{planche_editorial, case_rang, global_idx, total}`
    et la chaîne `pl.P · cN`. **Requête fenêtrée**, jamais N requêtes par ligne.
  - *Fichiers* : [database.py](../database.py).
  - *Fait quand* : valeurs justes sur planche multi-cases ; cohérent avec D4
    (bulle orpheline ignorée).
  - *Test* : unitaire dédié.

- **T1.2 — Surface : panneau de détail (Visionneuse)**
  - *But* : ligne « Citation : pl.P · cN » + « idx/total » en muted ; `#id` conservé
    comme ancre technique.
  - *Fichiers* : [templates/index.html](../templates/index.html) (`region-id`),
    [static/viewer.js](../static/viewer.js).
  - *Fait quand* : la sélection d'une case affiche sa citation ; paratexte → libellé,
    pas « planche ».

- **T1.3 — Surface : recherche & aperçu**
  - *But* : remplacer `#id` par `pl.P · cN` dans la meta des résultats et le titre
    de l'aperçu.
  - *Fichiers* : [static/recherche.js](../static/recherche.js),
    [main.py](../main.py) (SQL de recherche : exposer éditorial + rang de case,
    fenêtré).
  - *Fait quand* : chaque résultat se cite ; pas de régression de perf (1 requête).

- **T1.4 — (option Complet) Étiquette sur l'image**
  - *But* : les cases affichent `cN` (rang de citation) plutôt que l'ordre brut.
  - *Fichiers* : [static/viewer.js](../static/viewer.js) (label de région).
  - *Fait quand* : image et panneau concordent ; décision actée pour l'étiquette des
    bulles (statu quo `ordre` tant que le lot 2 n'est pas fait).

- **T1.5 — (option Complet) Barre d'état**
  - *But* : « N cases / album » **sur le récit seul**.
  - *Fichiers* : [templates/index.html](../templates/index.html) (`stat-cases`),
    [static/viewer.js](../static/viewer.js).
  - *Fait quand* : le total exclut les cases des planches paratexte.

---

## Lot 2 — Citation des bulles

> La finalité d'un corpus linguistique est de citer une **occurrence de mot**, donc
> une **bulle**. Plus grande valeur, au prix d'un cas limite (bulle hors case).
>
> **✅ Implémenté le 2026-06-15** (fondu dans le helper `citations_regions()` : un seul
> chemin de code pour cases et bulles). `pl·c·b` au détail et en recherche ; repli
> `pl·P · hors-case` pour une bulle sans parent.

- **T2.1 — Helper de citation (bulle)**
  - *But* : `pl.P · cN · bM` (rang de la bulle dans sa case) ; **repli** pour une
    bulle hors case (parent NULL) → « pl.P · hors-case ».
  - *Fichiers* : [database.py](../database.py).
  - *Test* : unitaire (bulle en case + bulle orpheline).

- **T2.2 — Surfaces détail + recherche (bulles)**
  - *But* : afficher la citation fine sur les régions de texte.
  - *Fichiers* : [static/viewer.js](../static/viewer.js),
    [static/recherche.js](../static/recherche.js).

---

## Lot 3 — Citation dans les exports savants

> Les exports sont l'artefact que le chercheur emporte pour citer ; ils doivent porter
> le numéro ÉDITORIAL et la citation, pas l'ordre d'import.
>
> **✅ Implémenté le 2026-06-15.** CSV de recherche **et** d'album (colonne `citation`,
> `planche` éditoriale), concordance (citation par ligne), JSON (`numero_editorial` +
> `role` par planche, citation par région), TEI (`@n` éditorial sur `<surface>`,
> `type="paratexte"`, `@n` citable « c2·b1 » sur les `<zone>`).

- **T3.1 — Export CSV d'album** ([main.py](../main.py) `/api/export/csv`, ~L1406)
  - *But* : colonne `citation` (`pl·c(·b)`) + `planche` = numéro éditorial ;
    paratexte explicite.
- **T3.2 — Export concordance par token** ([main.py](../main.py), ~L1116)
  - *But* : idem, pour les lignes KWIC (chacune cite sa région).
- **T3.3 — Export JSON d'album** ([main.py](../main.py) `/api/export/json`)
  - *But* : ajouter `numero_editorial` + `role` par planche (l'`id` technique reste).
- **T3.4 — Export TEI** ([main.py](../main.py) `/api/export/tei`)
  - *But* : `@n` éditorial sur `<surface>`, **marquer le paratexte** (ex. `type`/
    `subtype`), `xml:id` technique conservé. ⚠️ demande un peu de design TEI.

---

## Séquencement & dépendances

```text
Lot 0 (fondation, prérequis)
  └─ Lot 1.1 (helper case)
       ├─ Lot 1.2 détail        ┐ Ciblé (socle)
       ├─ Lot 1.3 recherche     ┘
       ├─ Lot 1.4 étiquette      ┐ option Complet
       └─ Lot 1.5 barre d'état   ┘
            └─ Lot 2 (bulles, optionnel)
```

**Décision ouverte** (à trancher après le lot 0) : où s'arrête le lot 1 —
Ciblé (T1.2–T1.3) / Complet (+T1.4–T1.5) / jusqu'aux bulles (lot 2).
