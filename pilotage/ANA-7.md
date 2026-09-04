---
chantier: ANA-7
statut: à venir
---

# ANA-7 — l'Exploration ne rend rien d'emportable

**Point de départ** — décidé le 2026-09-04, sur constat d'usage : « On n'a pas d'export
direct des résultats à chaque type d'exploration ? » Non, et c'est mesuré ci-dessous.
Rien n'est commencé ; le travail attend la fin de l'étape 1 d'UX-7.

## L'état des lieux, mesuré le 2026-09-04

| Surface | Export |
|---|---|
| Recherche | `#btn-export` → `GET /api/recherche/export.csv`, qui rejoue les critères affichés |
| Album | `GET /api/export/{json,csv,tei}` |
| Figures | `POST /api/figures` → zip (crop + légende + notice) |
| **Exploration — distribution** | **aucun** |
| **Exploration — concordance** | **aucun** |
| **Exploration — croisement** | **aucun** |
| **Exploration — comparaison A/B** | **aucun** |
| **Panneau 🎯 Accord** | à l'écran seulement ; le CSV n'existe qu'en CLI (`tools/rapport_accord.py --csv`) |
| **Panneau 👥 Inter** | à l'écran seulement ; idem (`tools/rapport_accord_inter.py`) |

La surface qui produit des CHIFFRES est la seule qui ne les rend pas. Un tableau de
contingence qu'on ne peut ni citer ni recalculer ailleurs se retape à la main, ou se
capture en image — les deux étant exactement ce qu'un outil de recherche doit éviter.

Le patron existe déjà et il est bon : `recherche_export` rejoue les MÊMES critères que
`/api/recherche`, par le même cœur `_recherche_rows`, avec une borne haute relevée à 5000
et le commentaire qui l'explique — « on exporte le jeu trouvé, pas seulement l'aperçu ».
C'est la promesse à tenir ici, et elle n'est pas triviale : les vues d'analyse affichent
un top-N (`CROISE_LIMIT = 20` par axe, `Resultats.LIMITE` pour les listes).

## Reste

### Arbitrages — à trancher AVANT d'écrire une ligne

- [ ] Le sort de l'export du panneau **👥 Inter** est tranché par écrit. Il NOMME des personnes, et la doctrine du dépôt sépare déjà deux régimes qui se rejoignent ici : la route `/api/analyse/accord-inter` nomme (déclaré dans `test_sorties_identite.py`, réservé à qui écrit) et l'outil CLI nomme aussi, au motif qu'« un rapport d'accord se lit pour arbitrer, puis se jette ». Un CSV téléchargé a la même DESTINATION que le CLI et la persistance d'un artefact déposé — c'est précisément la ligne DEDANS/DEHORS d'AUTH-1, et elle n'a jamais été posée sur ce cas
- [ ] Le CSV du **croisement** a une forme décidée : matrice (une ligne par valeur de X, une colonne par valeur de Y) ou lignes plates (`x ; y ; n`). La matrice se lit dans un tableur, les lignes plates se retraitent dans R ou pandas — et le tableau porte des MARGES, qui n'ont pas la même place dans les deux formes
- [ ] L'export rend le jeu AFFICHÉ ou le jeu COMPLET, et le choix est écrit sur chaque vue. Le croisement affiche un top-20 par axe ; exporter ce top-là, c'est exporter une troncature dont les marges ne somment pas — ce que `renderCroise` signale déjà à l'écran (« top 20 par axe ») et qu'un CSV muet ferait passer pour un total
- [ ] La forme de route est décidée : une route `.csv` par vue (patron de `/api/recherche/export.csv`) ou un paramètre `format=csv` sur les routes existantes. Le dépôt a déjà tranché une fois, dans le premier sens

### Le travail

- [ ] Les quatre vues de l'Exploration ont un bouton d'export qui produit un CSV du jeu courant, aux mêmes critères que l'affichage — vérifiable en comparant les totaux du fichier à ceux de `#dist-info`
- [ ] Les panneaux 🎯 Accord et 👥 Inter ont le leur, sur la décision d'arbitrage ci-dessus
- [ ] Chaque cellule de texte libre passe par `_csv_safe` (anti-injection de formule) et chaque réponse par `_csv_response` (BOM + `Content-Disposition`) : aucun `csv.writer` nu
- [ ] Le calcul n'est PAS réécrit pour l'export : la route CSV appelle le même cœur que la route JSON, comme `recherche_export` et `/api/recherche` partagent `_recherche_rows`. Deux chemins finiraient par diverger sur un filtre, et c'est le genre de divergence qu'on ne voit pas — les deux réponses restent plausibles

### Autorisation — deux cliquets à ne pas laisser au hasard

- [ ] Chaque nouvelle route consulte la portée et passe par `_analyse_filtres` : le cliquet de `test_autorisation.py` échoue si elle ne tranche pas, mais il ne dit PAS qu'elle tranche bien — un export qui recalculerait ses filtres à côté serait vert et fuirait
- [ ] L'export d'Inter hérite du **403** de sa route (qui n'écrit nulle part ne le lit pas), et non d'un contrôle réécrit
- [ ] Chaque nouvelle sortie est DÉCLARÉE dans `tests/test_sorties_identite.py` avec la sorte émise et sa raison — c'est un cliquet dur : une sortie non déclarée où la sentinelle apparaît fait échouer la suite
- [ ] Un test de comportement vérifie qu'un export ne rend RIEN d'un album hors portée, sur les six sorties — le cliquet ci-dessus ferme la porte de l'oubli, pas celle de l'erreur

## Contexte

**Ce chantier absorbe un point d'`ANA-6`** : « La concordance a un export dédié, cohérent
avec les autres exports (`_csv_safe` appliqué) », différé à la livraison de B2/B3. Le
laisser là aurait fait traiter la concordance seule, puis redécouvrir trois vues sans
sortie. La case reste dans `ANA-6` tant que celle-ci n'est pas ouverte ; elle se coche
avec ce chantier-ci.

**À ne pas confondre avec `EXP-1`**, qui expose dans l'UI les exports de DÉPÔT (fiche de
description de collection, manifeste IIIF, crosswalk) — des artefacts FAIR destinés à
Nakala, différés derrière INFRA-1. Ici il s'agit des RÉSULTATS d'une analyse, qu'on
emporte pour les retravailler ou les citer. Même verbe, deux destinations : `EXP-1` va
vers l'entrepôt du FIGÉ, `ANA-7` vers le tableur du chercheur.

**Le vrai coût est dans le premier bloc, pas dans le second.** Écrire six exports CSV est
une demi-journée ; décider si le rapport inter-annotateurs peut sortir en nommant des
personnes engage la ligne qu'AUTH-1 a tracée le 2026-08-31 et que `test_sorties_identite`
fait respecter. Le CLI a été laissé nommant parce qu'il « se lit puis se jette » ; un
fichier téléchargé, non. Trois issues sont défendables — pseudonymiser comme les artefacts
de dépôt, nommer comme le CLI en assumant que l'écran le fait déjà, ou refuser l'export de
ce panneau-là — et aucune ne se déduit des règles existantes.

**Priorité et moment.** Décidé le 2026-09-04 : fiché maintenant, codé APRÈS l'étape 1
d'`UX-7`, qui est ouverte et à moitié faite. Le manque est un manque d'usage, pas un
défaut : rien n'est perdu ni faux à l'écran.
