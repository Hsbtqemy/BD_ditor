# Rapport d'accord modèle↔humain (NLP-1)

> **But.** Mesurer **combien de corrections humaines le modèle NLP retrouve seul** : un étalon
> de la qualité de l'index grammatical. Sert l'**opération de transition Phase 1 → Phase 2** —
> comparer `fr_core_news_sm` (léger) et `fr_core_news_lg` (grand) sur le **même corpus relu**.
> Cœur partagé `accord.py`, exposé par la route `GET /api/analyse/accord` **et** l'outil
> `tools/rapport_accord.py`, plus un panneau **🎯 Accord** dans l'Exploration.

## Ce qu'on mesure

Sur les tokens que l'humain a **relus** (une correction *active* existe — `token_correction`,
`obsolete = 0`), joints à l'auto (`tokens`) sur `(region_id, ordre)` — **en miroir de la vue
`tokens_effectifs`**. Pour chaque champ (**lemme**, **POS**, **morpho**) :

- **accord** = le modèle avait *déjà* la valeur finale : la correction est **NULL** (auto
  accepté) **ou** égale à l'auto ;
- **désaccord** = la correction pose une valeur **différente** de l'auto.

Le taux = accord / relus. S'y ajoute une **matrice de confusion POS** : les paires
`auto → corrigé` les plus fréquentes (ce que le modèle rate le plus ; `∅` = l'auto n'avait rien).

> **À lire comme un échantillon.** Le taux porte sur les tokens **relus**, souvent les cas
> **douteux** — ce n'est pas l'exactitude sur tout le corpus, mais « quand un humain a regardé,
> le modèle avait-il bon ? ». Utile en **relatif** (sm vs lg sur le même corpus).

## Doctrine

- **Miroir de `tokens_effectifs`** : mêmes règles de merge (correction non-obsolète ⊕ auto). Une
  correction **obsolète** (forme dérivée après un reindex) est **ignorée**, comme dans la vue.
- **Lecture seule** : le rapport ne modifie rien. Le modèle évalué (celui qui a produit `tokens`)
  et sa date sont lus dans la table `meta` (`nlp_model`, `nlp_reindexed_at`).

## Usage

### Transition vers `lg`

```bash
BD_SPACY_MODEL=fr_core_news_lg python -m spacy download fr_core_news_lg   # une fois
BD_SPACY_MODEL=fr_core_news_lg python tools/reindex_nlp.py                # réindexe le corpus
python tools/rapport_accord.py                                           # mesure l'accord
```

### Consulter

```bash
python tools/rapport_accord.py                  # rapport lisible (stdout)
python tools/rapport_accord.py --json r.json    # + export JSON (rapport complet)
python tools/rapport_accord.py --csv r.csv      # + export CSV (une ligne par champ)
```

Dans l'app : **Exploration → 🎯 Accord** (modale) — même rapport (route `GET /api/analyse/accord`) :
modèle évalué, tokens relus (corrigés / validés), taux par champ (avec barre), confusion POS.

## Périmètre

- **Couvert** : accord par champ (lemme/POS/morpho), confusion POS, ventilation corrigé/validé,
  modèle évalué. Route + CLI + panneau, cœur unique testé une fois (`tests/test_accord.py`).
- **Hors périmètre** (différé) : provenance **par modèle** sur chaque correction (NLP-2, pour
  savoir *quel* modèle a été corrigé) ; accord **par annotateur** ; intégration au roll-up de
  qualité de la Collection (paradonnée d'export).
