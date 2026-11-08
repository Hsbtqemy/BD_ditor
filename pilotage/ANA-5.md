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

### Constats de la mesure du 2026-11-08, sur le code d'aujourd'hui
- [ ] **Le filtre `morph` ne prend plus un trait pour un autre** — attendu : sur l'Exploration, `morph=Type=Int` ne rend aucun token `PronType=Int`, `morph=Tense=Past` aucun `Tense=Pastx`, et `morph=PronType=Rel` rend un token `PronType=Int,Rel`. Aujourd'hui, `_analyse_filtres` (`routes/analyse.py`) cherche une sous-chaîne (`te.morph LIKE '%…%'`, insensible à la casse) : les trois cas se trompent, vérifiés sur des cas construits
- [ ] **Une morph corrigée à la main a la forme de celle du modèle** — attendu : une correction `tense=past` ou ` Number=Sing|Tense=Past ` est refusée par un 422 nommé, ou enregistrée `Number=Sing|Tense=Past`, clés triées. Le choix entre les deux revient à Hugo. Aujourd'hui, `TokenCorrectionIn.morph` est du texte libre et `_norm_corr` n'enlève que les espaces : aucun filtre de trait, table comprise, ne lit juste une morph tapée autrement

## Contexte

**Mesuré le 2026-11-08, sans table** (agent de la session de pilotage ; script et résultats hors dépôt, dans le scratchpad de la session). La question : lire le trait au moment de la requête, dans la morph de `tokens_effectifs`, sans table ni migration, est-il assez rapide ? Une migration sur dev prendrait la v39, déjà prise par la branche d'ANN-7 non fusionnée. La mesure a été faite sur le schéma réel, avec les vraies fonctions de l'Exploration (`_frequences_rows`, `_concordance_rows`, `_croisement_data`, `_analyse_filtres`), sur des corpus synthétiques de 100 k, 1 M et 3 M tokens, sur le portable du poste. Résultats :
- compter les tokens porteurs du trait, et ses lemmes : sous 1 s jusqu'à 1,3 M tokens environ ;
- croisement et distribution des valeurs : sous 1 s jusqu'à 1 M environ ;
- concordance : moins de 15 ms à toute taille ;
- un sous-corpus d'un dixième : moins de 0,5 s même à 3 M.

Le trait ne coûte que 25 à 50 % de plus que le filtre `pos` existant. Le coût vient du balayage de la vue (le `COALESCE` et la jointure des corrections), qui pèse sur toute l'Exploration. Le croisement `pos × provenance` d'aujourd'hui dépasse déjà 1 s à 1 M (1,9 s).

Une table `token_trait` gagnerait un facteur 2 sur le compte et un facteur 5 sur la distribution des valeurs. En échange :
- rien de gagné sur le croisement ;
- une concordance 50 à 150 fois plus lente ;
- une base deux fois plus lourde ;
- et, surtout, elle ignorerait les corrections de morph, sauf à relire `token_correction` à chaque requête.

Les deux cases de `### Modèle` se contredisent là-dessus : la première dit la table « jamais touchée par la couche de correction humaine », la seconde veut qu'une correction s'y reflète.

La taille visée est d'environ 7 500 planches (`IMG-1`), soit environ 750 k tokens. À cette taille, toutes les vues répondent entre 0,4 et 0,8 s. Ce que la mesure n'a pas établi : la vitesse du VPS, qui peut être deux ou trois fois plus lent, et la lecture à froid. La forme juste du filtre traite les valeurs multiples (`PronType=Int,Rel`) : `instr` sur `'|'||morph||'|'`, puis la valeur cherchée entre virgules. Les cases de `### Modèle` attendent la décision de Hugo, avec ou sans table.

Le paragraphe suivant date d'avant la mesure.

Effort M, priorité P3. Le coût réel n'est pas la requête mais la **migration** : une
nouvelle table dérivée à régénérer au reindex, donc un incrément de `SCHEMA_VERSION` et
une étape dans `_migrate()`.

Point de vigilance : `tokens` est régénérée à chaque reindex, `token_correction` ne l'est
jamais. `token_trait` doit suivre la première règle et non la seconde, sinon la
correction humaine serait écrasée — c'est l'invariant central de la couche NLP palier B.
