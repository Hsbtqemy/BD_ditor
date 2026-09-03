---
chantier: AUDIT-2
statut: à venir
audit: AUDIT.md
---

# AUDIT-2 — les constats mineurs que la roadmap ne cite pas

**Point de départ** — trouvés le 2026-08-27 en montant le journal : les listes « restent
ouverts » des passes 3, 4 et 5 d'`AUDIT.md` portent une dizaine de constats qu'aucun
ticket, aucune ligne de roadmap et aucune autre fiche ne reprend. Ils n'existaient que
dans le document d'audit.

## Reste

### Recherche et Exploration
- [ ] C1 — la mention « (limité) » cesse d'être fausse : le seuil `200` est codé en dur deux fois (`static/recherche.js:144` pour `limit`, `:210` pour le test `res.count >= 200`) et `res.count` compte les résultats RENVOYÉS, pas le total, donc l'étiquette ment à exactement 200 correspondances
- [ ] C2 — une requête composée uniquement de ponctuation ne renvoie plus zéro résultat sans explication
- [ ] C5 — les filtres déclenchés sur `onchange` sont débouncés, comme la recherche l'est déjà

### Visionneuse et Bibliothèque
- [ ] F1 — basculer le thème dans un onglet met à jour les autres onglets déjà ouverts : `static/theme.js` n'écoute pas l'événement `storage` (vérifié, zéro écouteur)
- [ ] A4 — la barre de progression d'un lot avance par passe et non d'un coup : `total` compte les planches (`pipeline/jobs.py:116`) alors que `done` est incrémenté en deux endroits (`:73`, `:86`) — les deux comptent la même unité, ou bien la barre ment
- [ ] D1/D2 — le nuage de tags n'est plus figé après le démarrage : il reflète les tags créés depuis
- [ ] E3 — le champ `annee` est borné : `socle.py:458` et `:477` déclarent `Optional[int]` sans `Field(ge=…, le=…)`, donc l'année 999999 passe

### Ingest
- [ ] G5 — `_rel_posix` (`pipeline/ingest.py:30`) garde le `ValueError` que lève `relative_to` quand `source` est hors de `DATA_DIR` — latent aujourd'hui, non joignable par l'API, mais une garde d'une ligne

### Responsive
- [ ] T7 — le choix est tranché et écrit : rendre les pages responsive, ou assumer l'outil desktop et retirer le `<meta viewport>` qui promet le contraire. `static/style.css` ne porte qu'UNE media query de largeur

## Contexte

Fiche séparée d'`AUDIT-1` exprès, et la distinction porte l'information : `AUDIT-1`
regroupe les reliquats que `docs/roadmap.md` cite déjà en piste D (B6, T2, T4, S1/S5, S6,
O1) ; **`AUDIT-2` regroupe ceux que rien ne citait**. Les fondre effacerait le fait qu'un
document de suivi entier est passé à côté de dix constats.

Tous sont mineurs, aucun n'est urgent, et c'est précisément pourquoi ils avaient disparu :
rien de mineur ne remonte tout seul d'un document de 324 lignes.

**Trois sont vérifiés ouverts contre le code le 2026-08-27** : C1 (seuil 200 en dur deux
fois), F1 (aucun écouteur `storage`), E3 (`annee` sans borne), plus G5 (aucune garde) et
T7 (une seule media query). Les autres reprennent le constat d'audit sans nouvelle
vérification — leurs cases sont donc écrites comme des attendus observables, pas comme
des diagnostics à croire sur parole.

**Deux constats de ces mêmes listes ont été retirés après vérification** : T5 (« S2/S3 non
couverts par des tests ») est clos — `tests/test_segmentation.py` porte
`test_seg_s2_fusion_ambigue_conserve_les_deux` et `test_resegmentation_s2_fusion_conserve_les_deux`,
livrés avec SEG-1 ; T6 (`font: 13px inherit`) est clos, appliqué en passe 4.
