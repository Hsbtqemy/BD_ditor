---
chantier: NLP-2
statut: différé
---

# NLP-2 — provenance du modèle par correction

**Arrêté sur** — le commit `3574ad7`, 2026-09-11 : **chaque correction garde ce que
l'annotateur a vu**, le modèle ET sa proposition (schéma v28). Les quatre cases d'origine
sont faites. Ce qui reste attend deux choses : le déploiement de `dev` sur `main`, qui doit
précéder tout passage à `lg`, et une décision sur l'affichage d'un token validé.

**Point de départ** — `token_correction` enregistre qui a corrigé (INFRA-2, fait) mais pas
CE QUI a été corrigé : le modèle spaCy dont la sortie a été reprise n'est pas conservé.

## Reste

### Fait le 2026-09-11
- [x] Une colonne `modele_auto` est ajoutée à `token_correction` par migration (incrément de `SCHEMA_VERSION` + étape dans `_migrate()`) — v28, `3574ad7`. **Avec trois autres colonnes**, `auto_lemme`/`auto_pos`/`auto_morph`, décidé le 2026-09-11 (cf. Contexte) : le nom seul ne permettait pas la mesure que la fiche visait
- [x] Elle est renseignée à la création d'une correction avec le modèle effectivement chargé (`BD_SPACY_MODEL`), pas avec la valeur par défaut de la config — `nlp.model_info()`, l'identifiant de `meta.nlp_model`, version comprise. Par la correction ET par la validation, qui relève aussi les corrections existantes, là seulement où un token s'affiche encore
- [x] Les corrections antérieures restent lisibles avec `modele_auto` à NULL, sans casser `tokens_effectifs` — vue inchangée, aucun rattrapage, et le rapport garde pour ces lignes sa lecture d'avant. `test_la_migration_v28_laisse_les_corrections_anterieures_a_null`
- [x] Le rapport d'accord (`accord.py`) peut restreindre son calcul à un modèle donné — `accord.rapport(modele=…)`, route `?modele=` (JSON et CSV), outil `--modele`. Restreint, il mesure en plus le modèle AU MOMENT de la relecture (`a_la_relecture`), à côté de l'index actuel ; `par_modele` décrit l'échantillon entier. Mutation : 22 mutants, tous tués

### Déploiement
- [ ] La production est en v28 AVANT tout passage à `lg` — attendu : `PRAGMA user_version` rend 28 sur la base de production pendant que `meta.nlp_model` y nomme encore `fr_core_news_sm`. Dans l'autre ordre, les relectures faites entre les deux n'auraient rien gardé, alors que c'est la raison d'être de la fiche. Passe par le déploiement MANUEL de `dev` sur `main` : la veille de déploiement refuse une mise à jour qui migre

### À trancher
- [ ] Un token validé sous un modèle, dont le suivant propose autre chose, ne s'affiche plus « validé » avec une valeur que personne n'a vue — `tokens_effectifs` lit toujours un champ vide contre l'auto d'aujourd'hui. Le relevé de la v28 rend l'écart DÉTECTABLE (`auto_*` ≠ `tokens`) ; reste à décider ce qu'on en fait (le signaler à revoir, ou afficher la valeur relue). Attendu une fois tranché : après un passage de modèle et une réindexation, un tel token n'a plus `provenance = 'valide'` avec la valeur du nouveau modèle sans que rien ne le signale. À trancher avant le passage à `lg`, pas après

## Contexte

Effort S, priorité P3 — mais la valeur monte nettement le jour où le corpus passe de
`fr_core_news_sm` à `fr_core_news_lg` (l'ops décrite dans `docs/rapport-accord.md`).

Sans cette colonne, comparer l'accord `sm` contre `lg` sur le même corpus relu suppose
que TOUTES les corrections ont été faites contre le même modèle — ce qui cesse d'être
vrai dès le premier reindex après changement de modèle. C'est donc une fiche à faire
AVANT le passage à `lg`, pas après : ensuite, l'information est perdue pour de bon.

**Le nom seul ne suffisait pas, et la fiche ne le disait pas** — relevé en la relisant le
2026-09-11, tranché par l'équipe le même jour. Un champ de correction laissé vide veut dire
« j'accepte la proposition du modèle », et le rapport relisait cette proposition dans
`tokens`, que la réindexation régénère. Ce que le passage à `lg` efface, ce n'est donc pas
seulement QUEL modèle a été relu, c'est ce qu'il PROPOSAIT. Avec le nom seul, le filtre ne
donnait un chiffre juste que pour le modèle actuellement indexé ; un token validé sous `sm`
comptait comme un accord de `lg` sur tout champ laissé vide. Avec la proposition, chaque
correction porte sa propre vérité, et `rapport(modele=<sm>)` met `sm` et `lg` face aux
mêmes relectures — sans garder `sm` installé.

**Le piège que la colonne tendait**, et qu'un test verrouille : le ré-ancrage réinsère ses
lignes colonne par colonne, et la route de correction le déclenche juste après avoir écrit.
Une colonne qu'il oublierait serait donc NULL dès l'écriture, sans qu'aucun test d'avant
ne bronche. `database.COLONNES_VU` est la seule liste.

**Ce que la mutation a trouvé** : remplacer l'égalité qui confond NULL et `''` par un `=`
nu survivait. Aucun test ne semait de proposition NULL, alors que la lecture d'avant
comptait « NULL accepté contre NULL » comme un accord. `test_rien_vaut_rien` le verrouille.

**Limite écrite** (`docs/rapport-accord.md`) : le modèle noté est celui qui est CHARGÉ.
Entre un changement de `BD_SPACY_MODEL` et la réindexation qui doit le suivre, une région
encore indexée par l'ancien modèle recevrait le nom du nouveau ; la proposition gardée,
elle, reste celle qui s'affichait.

**Écarté de ce lot, par décision du 2026-09-11** : le filtre par modèle dans le panneau
🎯 Accord. La transition se fait avec l'outil, et `static/exploration.js` était en travail
pour ANA-4.
