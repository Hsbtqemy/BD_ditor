# Lexique situé — vocabulaire SKOS documenté (A4)

> **But.** Rendre le vocabulaire ÉMERGENT du corpus (attributs facettés **et** tags)
> non seulement contrôlé mais **documenté et situé** : chaque terme peut porter une
> **définition**, une **note de portée** (« ici, ce mot signifie X »), un **état** de maturité
> et une **portée d'appartenance** (global ou propre à une collection). C'est la brique FAIR
> *Interoperable/Reusable* : un tiers sait exactement ce que chaque terme voulait dire dans
> l'étude. Décision arrêtée le 2026-07-15, livrée en **v17**. Cadre : niveau 7 du
> `docs/dictionnaire-metadonnees.md`.

## SKOS, appliqué à notre vocabulaire

**SKOS** (W3C) décrit un vocabulaire contrôlé : des *concepts* dans des *schémas*, avec
libellé, définition, note de portée, et liens. Correspondance :

| Notre schéma | SKOS | Rôle |
|---|---|---|
| `attribut_dimension` (axe, ex. « registre ») | schéma / facette | le référentiel |
| `attribut_valeur` (ex. « argot ») | `skos:Concept` (`inScheme` sa dimension) | le terme |
| `valeur` / `label` | `skos:prefLabel` | libellé préféré |
| **`definition`** | `skos:definition` | le sens |
| **`note_portee`** | `skos:scopeNote` | **le cadre d'emploi = le « situé »** |
| **`etat`** `provisoire → defini` | *(statut projet, miroir `auto→validé`)* | maturité |
| **`collection_id`** | portée d'appartenance (≈ `inScheme` d'une étude) | global / local |
| *(A5, dormant)* alignement | `skos:exactMatch` | lien Wikidata / IdRef |

**Un seul patron, appliqué partout.** La même couche définitionnelle est posée sur les
**dimensions**, les **valeurs** ET les **tags** — les trois vocabulaires « contrôlés-mais-
ouverts » du projet. Pour un **tag**, la `description` (déjà là) **EST** la `skos:definition` ;
il gagne en plus `note_portee`, `etat`, `collection_id`. (Les rôles de contribution restent
hors périmètre : leur « définition » est le relator MARC.)

## Portée d'appartenance — patron *mentions→entités*

`collection_id` **NULL = global** ; renseigné = **local** à une collection (un terme forgé pour
une étude). La **promotion local→global** = repasser à NULL. Corollaire de sûreté : supprimer
une collection **PROMEUT** ses termes locaux en global (`ON DELETE SET NULL`) plutôt que de
perdre le vocabulaire. C'est le même mouvement que personnages / contributeurs (mention locale
→ entité canonique), cf. `docs/personnages-et-attribution.md`.

## Édition — l'API et l'UI

- **API** (partielle, un `PATCH` par champ) :
  `PATCH /api/attributs/dimensions/{id}/lexique`, `.../valeurs/{id}/lexique`,
  `PATCH /api/tags/{id}/lexique` — corps `{definition?, note_portee?, etat?, collection_id?}`
  (`collection_id: null` explicite = promotion en global). `GET /api/lexique` renvoie tout le
  lexique (dimensions → valeurs + tags) + le résumé **% défini** ; `GET /api/collections`
  alimente le menu de portée.
- **UI** : bouton **📖 Lexique** sur la page Exploration → modale accessible (module
  `dialog.js` : piège à focus, Échap, retour du focus). Chaque terme est un `<details>`
  éditable (définition, note de portée, case « Défini », menu Portée) ; un compteur **% défini**
  suit la maturité en direct. Audit axe (WCAG 2.1 AA) verrouillé (`pytest -m e2e`).

## Indicateur « % défini »

`database.lexique_resume(conn, collection_id)` — part des termes (dimensions + valeurs + tags)
à l'état `defini`, **scopée par appartenance** (global ⊕ local à la collection). Nourrit la
qualité de la Collection ; exposé dans les exports sous `paradonnee.lexique`
(`metadonnees_collection.py`) et `vocabulaire.lexique` (`description_collection.py`).

## Export

Les records portent la couche SKOS : chaque dimension/valeur du bloc `vocabulaire` et chaque
`tags` gagnent `definition` / `note_portee` / `etat` / `collection_id` (JSON arbre + tables CSV
`vocabulaire`/`tags`). Le `% défini` remonte dans la paradonnée et le roll-up. Cf.
`docs/export-metadonnees.md`.

## Périmètre & suites

- **Livré (v17)** : schéma (4 colonnes × dimensions/valeurs, 3 × tags) + API + UI + indicateur
  + export. Tests : `tests/test_lexique_situe.py` (+ e2e/axe dans `tests/test_e2e_a11y.py`).
- **Dormants (déclenchables plus tard)** : **définition contextuelle** `valeur_definition`
  (glose d'un terme *par collection*, si un terme diverge vraiment entre études) ; **version**
  de concept (le gel se fait au niveau Collection) ; **alignement d'autorité** (A5,
  `skos:exactMatch` → Wikidata/VIAF/IdRef) ; unification mécanique des quatre vocabulaires
  (tags / attributs / rôles / lexique) en un seul patron (refonte, pas maintenant).
