# Alignement d'autorité — entités réconciliées (A5)

> **But.** Relier une **entité personnage** (récurrente au niveau corpus) à des **référentiels
> externes** (Wikidata, VIAF, IdRef…) via `skos:exactMatch`, pour rendre les entités
> **interopérables** et réconciliables (brique FAIR *Interoperable*). Livré en **v18**. Cadre :
> niveau 6 du `docs/dictionnaire-metadonnees.md`.

## Modèle — un personnage, 0..N autorités

Un personnage peut porter **plusieurs** liens d'autorité (Wikidata **et** VIAF **et** IdRef…),
chacun un `skos:exactMatch`. D'où une table dédiée (et non une colonne unique) :

```
personnage_alignement(id, personnage_id → personnages, source, uri, UNIQUE(personnage_id, uri))
```

- `uri` : l'identifiant du référentiel (ex. `https://www.wikidata.org/wiki/Q535`).
- `source` : l'**autorité**, **auto-détectée** depuis l'hôte de l'URI (`wikidata.org`→`wikidata`,
  `viaf.org`→`viaf`, `idref.fr`→`idref`, `isni.org`, `data.bnf.fr`→`bnf`, `id.loc.gov`→`loc`,
  `d-nb.info`→`gnd`) ; **contrôlé-ouvert** — une source explicite est respectée, un hôte inconnu
  laisse `source` NULL (l'alignement reste valide).
- `CASCADE` : supprimer un personnage retire ses alignements. La **fusion** de personnages
  (soupape *mentions→entités*) **recolle** les alignements du doublon (dédupliqués par URI).

## Édition — l'API et l'UI

- **API** : `GET /api/personnages/{id}/alignements` · `POST …/alignements`
  (`{uri, source?}` ; URI **http(s)** exigée ; idempotent : re-poster la même URI met à jour la
  source sans doublon) · `DELETE /api/personnages/{id}/alignements/{alignement_id}`.
- **UI** : section **« Autorité (référentiels externes) »** dans le panneau Personnage de la
  Visionneuse — atteignable **des deux côtés** de l'entité (via le **locuteur** d'une bulle et
  via la **boîte personnage** montrée). Saisir une URI l'ajoute (source auto-détectée) ; chaque
  alignement est une **puce-lien** (ouvre le référentiel dans un onglet) avec un ✕ pour retirer.
  Audit axe (WCAG 2.1 AA) verrouillé (`pytest -m e2e`).

## Export

- **Records** (`metadonnees_collection.py`) : chaque personnage porte `alignements: [{source,
  uri}]` (chaque `uri` = un `skos:exactMatch`) ; table CSV **`personnage_alignements`**.
- **Roll-up** (`description_collection.py`) : `couverture.personnages.avec_alignement_autorite`
  (nombre) + `pct_aligne` (%) — remplace l'ancien placeholder ; nourrit la qualité de la
  Collection.

## Périmètre & suites

- **Livré (v18)** : schéma + API + UI + export + indicateur. Tests :
  `tests/test_alignement_autorite.py` (+ e2e/axe dans `tests/test_e2e_a11y.py`).
- **Hors périmètre / dormant** : l'alignement des **contributeurs** (auteurs BD) — ce sont des
  chaînes `(nom, rôle)` par album, pas des entités ; les aligner exige d'abord de les
  **promouvoir en entités** (chantier « contributeur-entité », dormant ; patron
  *mentions→entités*, cf. `docs/dictionnaire-metadonnees.md` N0). Autres suites possibles :
  réconciliation assistée (suggestion d'URI depuis le nom), `closeMatch`/`relatedMatch`,
  sérialisation SKOS/RDF dédiée du graphe d'entités.
