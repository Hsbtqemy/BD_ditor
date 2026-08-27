---
chantier: AUDIT-1
statut: à venir
audit: AUDIT.md
---

# AUDIT-1 — les reliquats ouverts des cinq passes d'audit

**Point de départ** — les cinq passes d'audit de juin 2026 ont été largement traitées ;
sept constats sont restés ouverts, dispersés dans les sections « restent ouverts » et
cités nulle part ailleurs que dans `AUDIT.md`.

## Reste

### Transitions de statut
- [ ] B6 (régression) — re-segmenter une planche `annotee` ne la fait plus régresser en `segmentee` : `pipeline/segmentation.py:305` pose `statut = 'segmentee'` sans condition, et la route `POST /api/planches/{id}/segmenter` (`main.py:604`) l'appelle sur n'importe quel statut
- [ ] B6 (ordre) — la route `PATCH /api/planches/{id}/statut` (`main.py:968`) valide un ORDRE de transition et pas seulement l'appartenance à `STATUTS`, qu'elle vérifie déjà en `main.py:972`

### Tests faibles
- [ ] T2 — `tests/test_live_race.py` teste une vraie concurrence, ou bien il est renommé pour ne plus promettre une course qu'il ne joue pas : aux lignes 36-44 il fait N=30 PUT puis GET sur un unique client `httpx` synchrone, ce que sa propre docstring reconnaît (« frappé par un client séquentiel »)
- [ ] T4 — les trois assertions molles sont resserrées : `tests/test_api.py:280` (`status_code in (200, 400)`), `tests/test_api.py:415` (`"BD" in r.text`), `tests/test_backup.py:35` (`len(data) > 0`)
- [ ] T8 — `test_a11y_exploration_accord_inter` (`tests/test_e2e_a11y.py:372`) vérifie le CONTENU qu'il prétend construire, pas seulement l'accessibilité : il pose une divergence alice/bob puis n'assère que l'absence de violations axe, si bien qu'une modale VIDE le fait passer aussi bien qu'une modale peuplée. Mesuré le 2026-08-27 : en retirant `BD_AUTH_PROXY` du sous-processus, les deux auteurs deviennent NULL, aucune divergence n'est créée — et le test passe quand même
- [ ] T4 (suite) — `test_make_backup_horodatage_auto` (`tests/test_backup.py:32`) vérifie le FORMAT de l'horodatage, et pas seulement le préfixe `bd_annotator_` et le suffixe `.zip`

### Latents de segmentation
- [ ] S1/S5 — dans `segment_planche`, le détachement (`pipeline/segmentation.py:254`, un seul niveau) et la désindexation FTS (`:293`, les seules cases supprimées) deviennent récursifs, sur le modèle du `WITH RECURSIVE` de la route `delete_region` (`main.py:782`) et de `pipeline/bulles.py:139`
- [ ] S6 — re-segmenter deux fois de suite une planche à case annotée conservée donne le même résultat la seconde fois qu'à la première (point fixe)
- [ ] O1 — le regroupement en rangées de `pipeline/ordering.py:37-46` ne peut plus agglomérer transitivement des cases en escalier sur `y` : la boucle élargit `row["top"]` par `min()` à chaque ajout, donc de proche en proche

## Contexte

Fiche d'agrégation volontaire : sept constats mineurs ou latents qui ne justifient pas
sept fiches, mais qui n'existaient plus pour qui planifie — ils ne vivaient que dans
`AUDIT.md`, exactement le défaut que le contrôleur du journal cherche.

**S1/S5 est le seul à surveiller** : il est marqué « latent » parce que la profondeur
d'arbre est aujourd'hui ≤ 2, ce qui le neutralise. Ce n'est pas une correction, c'est une
coïncidence de données — le jour où une 3ᵉ profondeur est autorisée, il devient une perte
de données silencieuse. À traiter AVANT toute évolution de la hiérarchie des régions.

Les références de ligne ci-dessus ont été **revérifiées contre le code le 2026-08-27** :
celles de `AUDIT.md` avaient dérivé (B6 y pointe `main.py:631-642`, où il n'y a plus de
`statut` ; T2 y pointe des lignes 83-92 d'un fichier qui n'en compte que 45 ; T4 y pointe
`test_api.py:208/245`, devenus de vraies assertions). Les constats eux-mêmes sont tous
encore vrais — seuls les pointeurs étaient périmés.

`audit: AUDIT.md` est déclaré ici pour que l'écran renvoie à la source. Attention :
`AUDIT.md` n'a pas de tableau de constats à codes `X-NN`, ses codes sont de la forme `B6`,
`T2`, `S1`. Le contrôleur le rangera donc « INCONNU » plutôt que d'en compter les
constats ouverts — c'est le document qu'il faudrait reformater, pas la règle de lecture.
