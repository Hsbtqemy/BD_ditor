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
- [ ] C1 — **Vérifié ouvert le 2026-09-03, diagnostic exact.** La mention « (limité) » cesse d'être fausse : le seuil `200` est codé en dur deux fois (`static/recherche.js:144` pour `limit`, `:210` pour le test `res.count >= 200`) et `res.count` compte les résultats RENVOYÉS, pas le total — confirmé côté serveur, `routes/recherche.py:180` renvoie `"count": len(results)` —, donc l'étiquette ment à exactement 200 correspondances
- [ ] C2 — l'ÉCRAN explique le zéro : une requête de ponctuation seule (`???`, `...`, `++`) affiche pourquoi elle ne peut rien trouver, au lieu de « 0 résultat » sec. **Requalifié le 2026-09-03** : le constat visait l'API, qui a été tranchée entre-temps — absorber une syntaxe FTS invalide en 200 + zéro résultat est un choix ÉCRIT et verrouillé par un test (`tests/test_api.py:281`, AUDIT-1/T4). Il ne reste donc que la moitié cliente, et c'est la seule qui manquait vraiment : le serveur ne ment pas, l'écran ne dit rien
- [ ] C5 — le sort du debounce des filtres est TRANCHÉ par écrit, fait ou écarté. **Vérifié ouvert le 2026-09-03** et la valeur est douteuse : les quatre filtres sont bien en `onchange = search` sans debounce (`static/recherche.js:288`) là où la saisie a le sien à 300 ms (`:284`) — mais un `change` de `<select>` ne se déclenche qu'une fois par geste, et non à chaque frappe. Débouncer n'économiserait presque aucune requête. Le constat d'audit a raisonné par symétrie avec la saisie, pas sur l'usage

### Visionneuse et Bibliothèque
- [ ] F1 — basculer le thème dans un onglet met à jour les autres onglets déjà ouverts : `static/theme.js` n'écoute pas l'événement `storage` (**revérifié le 2026-09-03, toujours zéro écouteur**)
- [ ] A4 — la barre de progression d'un lot avance par PASSE et non par planche : sur un lot de trois passes, elle bouge trois fois plus souvent, et l'écran le dit. **DIAGNOSTIC FAUX, corrigé le 2026-09-03** : la fiche affirmait que `done` est incrémenté en deux endroits pour une unité que `total` compte autrement, « ou bien la barre ment ». Les deux `done += 1` (`pipeline/jobs.py:80` et `:93`) sont des branches MUTUELLEMENT EXCLUSIVES — une planche verrouillée est comptée puis `continue` — donc une planche, une incrémentation, exactement l'unité de `total = len(planche_ids)` (`:149`). **La barre ne ment pas.** Ce qui reste est un souhait de granularité, légitime et sans urgence : il ne répare rien
- [ ] D1/D2 — le nuage de tags n'est plus figé après le démarrage : il reflète les tags créés depuis. **Vérifié ouvert le 2026-09-03** : `loadTags()` n'est appelé qu'une fois, à l'initialisation (`static/recherche.js:296`), et par rien d'autre
- [ ] E3 — le champ `annee` est borné : `socle.py:458` et `:477` déclarent `Optional[int]` sans `Field(ge=…, le=…)`, donc l'année 999999 passe (**revérifié le 2026-09-03**, après le déménagement des modèles par ARCH-1)

### Ingest
- [ ] G5 — `_rel_posix` (`pipeline/ingest.py:30`) garde le `ValueError` que lève `relative_to` quand `source` est hors de `DATA_DIR` — latent aujourd'hui, non joignable par l'API, mais une garde d'une ligne (**revérifié le 2026-09-03 : `relative_to` toujours nu**)

### Responsive
- [ ] T7 — le choix est tranché et écrit : rendre les pages responsive, ou assumer l'outil desktop et retirer le `<meta viewport>` qui promet le contraire. **Vérifié le 2026-09-03** : `static/style.css` ne porte toujours qu'UNE media query de largeur. C'est un ARBITRAGE et non un correctif — la case se coche en décidant, pas en codant, et le coût des deux branches n'est pas du même ordre

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

**REVÉRIFICATION COMPLÈTE le 2026-09-03**, huit jours après la rédaction, et le résultat
se lit exactement le long de la ligne que la fiche avait tracée elle-même.

Les **cinq vérifiés contre le code le 27 août tiennent tous les cinq**, à la virgule près —
C1, F1, E3, G5, T7. Des **quatre repris de l'audit sur parole**, **trois ne tenaient pas** :

- **A4 : le diagnostic était faux.** Les deux incrémentations qu'il accusait sont des
  branches mutuellement exclusives ; la barre compte juste. Le souhait de granularité
  survit, mais il ne répare rien — et l'aurait-on « corrigé » qu'on aurait cherché un bug
  inexistant, ou pire, cassé un compteur exact pour satisfaire l'énoncé.
- **C2 : le constat avait changé de camp.** Il visait l'API ; AUDIT-1/T4 l'a tranchée
  depuis, avec un test. Seule la moitié cliente restait, et personne ne l'aurait vu sans
  relire.
- **C5 : vrai mais de valeur douteuse.** Le raisonnement d'origine était une symétrie avec
  la saisie, pas une observation d'usage.

**La leçon est mesurable, et elle est la même qu'AUDIT-1** : ce qui pourrit dans une fiche,
ce n'est pas le constat, c'est ce qu'on n'a pas regardé soi-même. Un constat vérifié contre
le code tient huit jours sans broncher ; un constat recopié se périme avant d'être lu.
D'où la règle : **relire un item non vérifié AVANT de le corriger, jamais après**.

**Deux constats de ces mêmes listes ont été retirés après vérification** : T5 (« S2/S3 non
couverts par des tests ») est clos — `tests/test_segmentation.py` porte
`test_seg_s2_fusion_ambigue_conserve_les_deux` et `test_resegmentation_s2_fusion_conserve_les_deux`,
livrés avec SEG-1 ; T6 (`font: 13px inherit`) est clos, appliqué en passe 4.
