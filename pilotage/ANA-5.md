---
chantier: ANA-5
statut: à venir
---

# ANA-5 — distribution par trait morphologique isolé

**Point de départ** — `champ=morph` distribue aujourd'hui sur la signature morphologique
COMPLÈTE ; isoler un trait (`Tense=Past`) est impossible.

## Reste

### Modèle
- [ ] Une table `token_trait` (un trait UD par ligne) est peuplée au reindex, au même moment que `tokens`, et n'est jamais touchée par la couche de correction humaine
- [ ] La table est régénérée au reindex comme `tokens`, et une correction morphologique dans `token_correction` s'y reflète via `tokens_effectifs`

### Surface
- [ ] La distribution accepte un trait isolé comme champ et renvoie des comptes cohérents avec la signature complète
- [ ] Le filtrage par trait isolé est disponible partout où `morph` l'est déjà (fréquences, concordance, comparaison)
- [ ] Sur le corpus complet, la distribution par trait répond sans dégradation perceptible

## Contexte

Effort M, priorité P3. Le coût réel n'est pas la requête mais la **migration** : une
nouvelle table dérivée à régénérer au reindex, donc un incrément de `SCHEMA_VERSION` et
une étape dans `_migrate()`.

Point de vigilance : `tokens` est régénérée à chaque reindex, `token_correction` ne l'est
jamais. `token_trait` doit suivre la première règle et non la seconde, sinon la
correction humaine serait écrasée — c'est l'invariant central de la couche NLP palier B.
