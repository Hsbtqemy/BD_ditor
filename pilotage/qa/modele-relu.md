---
passe: Ce que l'annotateur a vu
chantier: NLP-2
duree: 15 min
derniere: 2026-09-11
---

# QA — chaque correction garde le modèle et sa proposition

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, et un terminal pour
`docker exec bd-app …`. **À jouer APRÈS la passe `comparaison-keyness` (ANA-4)**, qui
suppose les tokens de la base intacts : corriger un token réindexe sa bulle.

**Ce que la passe éprouve.** Un champ de correction laissé vide veut dire « j'accepte la
proposition du modèle ». Depuis la v28, la correction garde cette proposition et le nom du
modèle chargé, et le rapport d'accord peut se restreindre à un modèle. L'écran du panneau
🎯 Accord ne change pas : la transition vers `lg` se fait avec l'outil. Le corpus copié ne
porte aucune correction de token, si bien que la part « inconnu », celle d'avant la v28,
n'apparaîtra pas ici ; elle est éprouvée par la suite de tests.

### La migration
- [ ] `docker exec bd-app python -c "import sqlite3; c=sqlite3.connect('/data/bd_annotator.sqlite'); print(c.execute('PRAGMA user_version').fetchone()[0], [r[1] for r in c.execute('PRAGMA table_info(token_correction)')][-4:])"` rend `28 ['modele_auto', 'auto_lemme', 'auto_pos', 'auto_morph']`

### La correction
- [ ] Sous `proprio`, dans l'Atelier, le panneau Grammaire d'une bulle d'« esther v1 » montre ses tokens ; le POS d'un mot est corrigé, et le token s'affiche « corrigé »
- [ ] `docker exec bd-app python tools/rapport_accord.py` affiche « Relectures, par modèle relu : fr_core_news_sm-3.8.0 : 1 » — le modèle CHARGÉ, version comprise (relevé dans l'image le 2026-09-11), et non « inconnu »
- [ ] « Valider » la grammaire de la même bulle : le rapport compte désormais tous ses tokens, tous sous le même modèle

### Le filtre
- [ ] `docker exec bd-app python tools/rapport_accord.py --modele <identifiant>` affiche « Restreint aux relectures faites sur : <identifiant> », puis deux blocs, « L'index actuel (…) » et « <identifiant>, au moment de la relecture ». Tant que le modèle n'a pas changé, leurs taux sont égaux
- [ ] Dans le navigateur, `https://bd.127-0-0-1.sslip.io/api/analyse/accord?modele=<identifiant>` rend `filtre_modele` et `a_la_relecture` ; sans le paramètre, `a_la_relecture` vaut `null`

### Ce que l'écran n'a pas perdu
- [ ] Exploration → 🎯 Accord s'ouvre, et son nombre de tokens relus égale celui de l'outil
- [ ] Son export CSV porte une dernière colonne `releve_sur`, vide
