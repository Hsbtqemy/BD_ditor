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

## Ce que l'annotateur a vu (NLP-2, v28)

Un champ de correction laissé vide veut dire « j'accepte la proposition du modèle ». Jusqu'à
la v28, cette proposition n'était pas gardée : le rapport la relisait dans `tokens`, que chaque
réindexation régénère. Après un passage à `lg`, un mot validé sous `sm` comptait donc comme un
accord avec `lg`, dont personne n'avait vu la proposition — et un token validé sans retouche
donnait 100 % d'accord, quoi que dise le nouveau modèle. La mesure pour laquelle ce rapport
existe était faussée par construction.

Chaque correction garde désormais :

- `modele_auto` — le modèle chargé au moment du geste, même identifiant que `meta.nlp_model`,
  version comprise (`fr_core_news_sm-3.8.0`) : deux versions du même modèle n'étiquettent pas
  pareil ;
- `auto_lemme`, `auto_pos`, `auto_morph` — sa proposition telle qu'elle s'affichait, `''`
  quand il n'en avait pas.

La **vérité humaine** d'un champ est la valeur posée, sinon la proposition vue. Deux mesures en
découlent :

| Clé | Question | Lit |
|---|---|---|
| `champs` | l'index actuel retrouve-t-il la vérité humaine ? | `tokens` |
| `a_la_relecture` (avec `modele`) | le modèle relu avait-il raison quand l'humain l'a regardé ? | le relevé seul |

Tant que le modèle n'a pas changé, `champs` rend exactement le chiffre d'avant la v28, et un
test le verrouille. `par_modele` dit de quoi l'échantillon est mêlé, avec ou sans filtre.

**Les corrections antérieures restent à NULL, sans rattrapage.** Relire `tokens` à la migration
aurait été deviner ce qui s'affichait : retoucher le texte ailleurs dans la bulle change
l'étiquette d'un mot inchangé, et sa correction survit au ré-ancrage. Pour ces lignes, le
rapport garde sa lecture d'avant, et `par_modele` les compte sous « inconnu ».

**Limite écrite.** Le modèle noté est celui qui est CHARGÉ, pas celui qui a indexé la région.
Entre un changement de `BD_SPACY_MODEL` et la réindexation qui doit le suivre, une région
encore indexée par l'ancien modèle recevrait le nom du nouveau ; la proposition gardée, elle,
reste celle qui s'affichait. D'où la procédure ci-dessous : réindexer aussitôt.

**Ce que la v28 ne corrige pas.** La vue `tokens_effectifs` lit toujours un champ vide contre
l'auto d'aujourd'hui : après un passage à `lg`, un token validé sous `sm` s'affiche « validé »
avec la valeur de `lg`. Le relevé permet désormais de le détecter ; le signaler reste ouvert
(fiche NLP-2).

## Doctrine

- **Miroir de `tokens_effectifs`** : mêmes règles de merge (correction non-obsolète ⊕ auto). Une
  correction **obsolète** (forme dérivée après un reindex) est **ignorée**, comme dans la vue.
- **Lecture seule** : le rapport ne modifie rien. Le modèle évalué (celui qui a produit `tokens`)
  et sa date sont lus dans la table `meta` (`nlp_model`, `nlp_reindexed_at`).

## Usage

### Transition vers `lg`

```bash
python tools/rapport_accord.py                                           # sm, avant le passage
BD_SPACY_MODEL=fr_core_news_lg python -m spacy download fr_core_news_lg   # une fois
BD_SPACY_MODEL=fr_core_news_lg python tools/reindex_nlp.py                # réindexe le corpus
python tools/rapport_accord.py --modele fr_core_news_sm-3.8.0             # sm et lg, mêmes relectures
```

Le dernier rapport restreint l'échantillon aux relectures faites sous `sm`, et met côte à côte
l'index actuel (`lg`) et `sm` au moment de la relecture : la comparaison se fait sur les MÊMES
tokens, sans avoir à garder `sm` installé. L'identifiant exact est celui que liste
« Relectures, par modèle relu ».

### Consulter

```bash
python tools/rapport_accord.py                  # rapport lisible (stdout)
python tools/rapport_accord.py --json r.json    # + export JSON (rapport complet)
python tools/rapport_accord.py --csv r.csv      # + export CSV (une ligne par champ)
python tools/rapport_accord.py --modele M       # restreint aux relectures faites sous M (NLP-2)
```

Le CSV ne porte que l'index actuel ; restreint, il le dit dans sa colonne `releve_sur`. La mesure
au moment de la relecture est dans le JSON (`a_la_relecture`).

Dans l'app : **Exploration → 🎯 Accord** (modale) — même rapport (route `GET /api/analyse/accord`) :
modèle évalué, tokens relus (corrigés / validés), taux par champ (avec barre), confusion POS. Le
panneau ne propose pas le filtre par modèle ; la route l'accepte (`?modele=`), et la transition se
fait avec l'outil.

## Périmètre

- **Couvert** : accord par champ (lemme/POS/morpho), confusion POS, ventilation corrigé/validé,
  modèle évalué. Route + CLI + panneau, cœur unique testé une fois (`tests/test_accord.py`).
  Depuis la v28, le modèle et la proposition vus à chaque relecture, le filtre par modèle et la
  mesure au moment de la relecture (`tests/test_nlp2_modele_relu.py`).
- **Hors périmètre** (différé) : accord **par annotateur** ; filtre par modèle dans le panneau ;
  signaler un token validé dont la proposition a changé depuis (cf. ci-dessus).
