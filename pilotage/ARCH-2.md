---
chantier: ARCH-2
statut: à venir
---

# ARCH-2 — une montée de FastAPI a rendu les cliquets aveugles à 56 % des routes

**Point de départ** — 2026-09-05, découvert en lançant la suite complète après INFRA-8.
Aucun code écrit. Le défaut ne vient pas du dépôt mais d'une dépendance, et il frappe
exactement là où le dépôt s'était protégé.

## Reste

### Rendre les cliquets capables de voir ce qu'ils prétendent inventorier
- [ ] Les quatre balayages traversent `_IncludedRouter` — `test_autorisation`, `test_sorties_identite`, `test_csp`, `test_decoupage_api` voient **122 routes et non 53**, mesuré, pas déclaré
- [ ] L'aplatissement vit à UN endroit partagé, pas recopié dans quatre fichiers : c'est la même faute que celle qu'il répare, une vérité écrite en plusieurs exemplaires
- [ ] Le balayage fonctionne sur les DEUX formes — `app.routes` aplati (≤ 0.133) et paresseux (≥ 0.137) —, sans quoi corriger pour l'un casse pour l'autre au prochain verrou

### Faire échouer un inventaire qui rétrécit
- [ ] Un cliquet dont l'inventaire tombe sous un seuil ÉCHOUE au lieu de passer : aujourd'hui `test_autorisation` est vert en n'ayant examiné que 44 % des routes, et rien ne le dit. Attendu à écrire : le nombre de routes balayées est comparé à un plancher, et une chute le fait tomber
- [ ] Ce plancher se dérive du code plutôt que d'être un chiffre recopié, sinon il vieillit et devient faux dans le sens permissif

### Empêcher la dérive qui l'a causé
- [ ] `requirements.txt` ne laisse plus `fastapi>=0.110` ouvert jusqu'à une version qui change la forme de `app.routes`
- [ ] Un `pip install -r requirements.txt` dans un venv neuf donne la même version que `requirements.lock` — aujourd'hui 0.137 contre 0.133, et c'est ainsi que l'environnement de développement s'est retrouvé à mesurer autre chose que l'image livrée

### Un second constat de la même exécution, sans rapport
- [ ] Quatre tests ÉCHOUENT sur `openpyxl` absent (`dictionnaire_xlsx.py`), quand la convention du dépôt est de SKIPPER proprement une dépendance optionnelle — c'est ce que font `requires_kumiko` / `requires_bulles` / `requires_ocr`. Un échec dur sur un extra non installé apprend la mauvaise chose : il fait croire à une régression

## Contexte

**Ce qui s'est passé.** FastAPI 0.137 n'aplatit plus les routeurs inclus dans
`app.routes` : il y dépose sept objets `_IncludedRouter` qui délèguent à l'exécution. Les
routes RÉPONDENT — `/api/analyse/info` rend 200 avec sa charge utile, une route inventée
rend 404 — mais elles ne sont plus énumérables. `app.routes` contient 53 `APIRoute` et
7 `_IncludedRouter` là où le dépôt en attend 122.

**Pourquoi c'est grave, et pas seulement gênant.** Trois cliquets de ce dépôt tirent leur
inventaire de `app.routes` : l'autorisation (« toute route consulte la portée, ou figure
sur `HORS_PERIMETRE` avec sa raison »), les sorties d'identité (61 surfaces balayées) et
la CSP. Ils ne se sont pas mis à échouer : ils ont continué de PASSER, en ne regardant plus
que 44 % du contrat. Une garde qui tombe est un incident ; une garde qui approuve en
n'ayant rien vu est un mensonge, et c'est celui-là qu'on a eu.

**Ce qui a sauvé la mise.** `test_decoupage_api` est le seul à avoir bronché, parce qu'il
compare une source à un inventaire au lieu de parcourir l'inventaire seul. Sa docstring
disait déjà le risque mot pour mot : « c'est de là que les trois cliquets du dépôt tirent
leur inventaire ; si elle n'y était pas, ils passeraient au vert en ne regardant plus
rien. » Il a été écrit contre un `include_router` oublié ; il a attrapé une montée de
version. C'est l'argument pour la deuxième zone ci-dessus — un cliquet doit refuser un
inventaire qui rétrécit, quelle qu'en soit la cause.

**La production n'est pas touchée**, et c'est le verrou qui l'a protégée :
`requirements.lock` pose `fastapi==0.133.0`, l'image livrée est donc dans l'ancienne forme.
Le `.venv` local, lui, a dérivé — `requirements.txt` dit `fastapi>=0.110`. L'écart entre
l'environnement qui MESURE et l'image qui SERT est précisément ce que QA-5 dénonçait dans
l'autre sens (« 451 tests verts en local, trois moteurs morts dans l'image »). Ici il joue
à l'envers : c'est le local qui voit juste, et il voit que la garde ne garde plus rien.
