# Domaines analytiques (piste B)

> **But.** Rendre les **domaines d'étude de première classe** : les émotions ne sont **pas** un
> module à part, mais **un domaine parmi d'autres** (représentation des minorités, style visuel,
> actes de langage…). Un `domaine` regroupe des **dimensions facettées** ; ajouter un domaine
> ne coûte **aucun code**. Livré en **v20**. Cadre : piste B (ANN-1 « absorbé par ANN-2 »).

## Le socle existait déjà

Le vocabulaire d'annotation est **facetté et émergent** depuis ANN-2 (v11) :

```
attribut_dimension (AXE émergent)  →  attribut_valeur (valeurs canoniques)
        └─ cible = 'personnage' | 'case'   (à quoi l'axe s'accroche)
```

Une « émotion » n'est qu'une **dimension** (ex. `valence` → colère/joie…). Le seul chaînon
manquant pour *organiser* plusieurs domaines × plusieurs axes était une **couche de
regroupement**. C'est ce qu'ajoute la v20.

## Le palier `domaine`

```
domaine (émergent, SKOS)               « émotions », « représentation », « style visuel »…
   └─ attribut_dimension.domaine_id     (NULL = hors domaine)
```

- **Contrôlé-mais-ouvert + lexique SKOS** : un domaine se crée au fil de l'eau et porte la
  **même couche définitionnelle** que dimensions/valeurs/tags (A4 : `definition`, `note_portee`,
  `etat` provisoire→défini, `collection_id` = portée d'appartenance). Il compte dans le **% défini**.
- **ORTHOGONAL à `cible`.** `cible` dit *à quoi* une dimension s'accroche (personnage / région) ;
  `domaine` dit *de quel champ analytique* elle relève. Un même domaine « représentation » peut
  grouper une dimension **personnage** (`genre`, `origine`) ET une dimension **région** (scène
  représentant une minorité).
- **Promotion à la suppression** : supprimer un domaine ne détruit **pas** ses dimensions —
  `domaine_id` repasse à NULL (`ON DELETE SET NULL`), elles redeviennent « hors domaine ». Même
  soupape que `collection_id` (patron *mentions→entités*).

## Ce que ça change (et ne change pas)

| Nouveau domaine qui… | Coût |
|---|---|
| s'accroche à un **personnage** ou à une **région** | **0** — créer un domaine + une dimension |
| a besoin d'un **nouveau type d'ancre** (planche, album, collection, scène = case×personnage) | une **table de jointure** + une valeur de `cible` — **différé** (dormant, ajouté au besoin réel) |

Les **tags** restent la couche **plate transversale** (étiquettes légères sur l'annotation) ;
les **domaines** organisent le vocabulaire **structuré** (dimensions). Doctrine : domaine
analysable → dimension ; étiquette légère → tag.

## Boucle

- **API** : `GET/POST /api/domaines` · `PATCH /api/domaines/{id}` (renommer, préserve le
  regroupement) · `DELETE …` (promotion) · `PATCH /api/domaines/{id}/lexique` (couche SKOS) ·
  `PATCH /api/attributs/dimensions/{id}/domaine` (rattacher / détacher). `create_dimension`
  accepte un `domaine_id` optionnel. `GET /api/lexique` renvoie désormais `domaines` + le
  `domaine_id` de chaque dimension.
- **UI** : panneau **📖 Lexique** (Exploration) — création d'un domaine, domaines documentables
  (mêmes champs SKOS), dimensions **regroupées sous leur domaine** (+ section « Hors domaine »),
  chaque dimension portant un **sélecteur de domaine**.
- **Export** : records `domaines[]` + `domaine` sur chaque dimension ; tables CSV `domaines` +
  colonne `domaine` dans `vocabulaire` ; roll-up `vocabulaire.domaines` + `% défini` (les
  domaines comptent dans `lexique_resume`) ; dictionnaire (lignes `domaine` / `dimension.domaine`).

## Prochaine étape naturelle

L'**analyse *par domaine*** (regrouper toutes les facettes d'un domaine, croisements
domaine×type — B2/B3 KWIC & tableaux croisés) : la structure est maintenant là pour l'alimenter.
Le **premier domaine à peupler** reste les émotions — mais dans un système qui sert tout ce qui
viendra après.
