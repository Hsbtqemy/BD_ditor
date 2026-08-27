---
chantier: NLP-2
statut: à venir
---

# NLP-2 — provenance du modèle par correction

**Point de départ** — `token_correction` enregistre qui a corrigé (INFRA-2, fait) mais pas
CE QUI a été corrigé : le modèle spaCy dont la sortie a été reprise n'est pas conservé.

## Reste

- [ ] Une colonne `modele_auto` est ajoutée à `token_correction` par migration (incrément de `SCHEMA_VERSION` + étape dans `_migrate()`)
- [ ] Elle est renseignée à la création d'une correction avec le modèle effectivement chargé (`BD_SPACY_MODEL`), pas avec la valeur par défaut de la config
- [ ] Les corrections antérieures restent lisibles avec `modele_auto` à NULL, sans casser `tokens_effectifs`
- [ ] Le rapport d'accord (`accord.py`) peut restreindre son calcul à un modèle donné

## Contexte

Effort S, priorité P3 — mais la valeur monte nettement le jour où le corpus passe de
`fr_core_news_sm` à `fr_core_news_lg` (l'ops décrite dans `docs/rapport-accord.md`).

Sans cette colonne, comparer l'accord `sm` contre `lg` sur le même corpus relu suppose
que TOUTES les corrections ont été faites contre le même modèle — ce qui cesse d'être
vrai dès le premier reindex après changement de modèle. C'est donc une fiche à faire
AVANT le passage à `lg`, pas après : ensuite, l'information est perdue pour de bon.
