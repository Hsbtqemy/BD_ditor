---
chantier: ANA-7
statut: livré
---

# ANA-7 — l'Exploration ne rend rien d'emportable

**Arrêté sur** — 2026-09-08 : **les six exports existent**, quatre vues et deux
panneaux, avec leur bouton. Les quatre arbitrages ont été tranchés AVANT la première ligne,
comme la fiche l'exigeait, et deux d'entre eux ont demandé une décision qui ne se déduisait
d'aucune règle existante.

**Ce que la mesure a apporté aux arbitrages.** Les plafonds des routes d'analyse sont des
plafonds d'AFFICHAGE (1000 lemmes, 500 concordances, 200 comparaisons, 50 par axe), et le
corpus de développement — 443 tokens, 235 lemmes — ne les atteint jamais : un export
tronqué y serait indistinguable d'un export complet. Sur un corpus réel, l'ordre de
grandeur (loi de Heaps) est de 8 000 à 10 000 lemmes distincts, et le plafond d'affichage
n'en montrerait qu'un dixième. D'où le plafond d'export relevé à 5000, et la troncature
ÉCRITE — dans le nom du fichier, seule place qui ne coûte rien ni au tableur ni à pandas.

**Point de départ** — décidé le 2026-09-04, sur constat d'usage : « On n'a pas d'export
direct des résultats à chaque type d'exploration ? » Non, et c'est mesuré ci-dessous.
Rien n'est commencé. Le travail attendait la fin de l'étape 1 d'UX-7 : **UX-7 est `livré`
depuis le 2026-09-05, 19 cases sur 19, et ce verrou est levé.**

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

- [x] Le sort de l'export du panneau **👥 Inter** est tranché par écrit. **TRANCHÉ le 2026-09-08 : il NOMME, comme le CLI.** Le dépôt tenait déjà trois positions — l'écran nomme (réservé à qui écrit), le CLI nomme (« se lit pour arbitrer, puis se jette »), le dépôt ne publie que `nb_auteurs` et des taux —, et un fichier téléchargé tombait entre les deux dernières. Retenu : refuser au fichier ce que l'écran donne à la même personne serait une friction sans protection (la capture d'écran reste possible), et ce fichier a UN usage — réunir deux personnes pour arbitrer — que des pseudonymes rendraient impraticable. Ce qu'on accepte en échange est écrit dans `test_sorties_identite.py` : un fichier PERSISTE là où le CLI se jette, donc la garde est dans l'ACCÈS et non dans la forme. *Énoncé d'origine :* Il NOMME des personnes, et la doctrine du dépôt sépare déjà deux régimes qui se rejoignent ici : la route `/api/analyse/accord-inter` nomme (déclaré dans `test_sorties_identite.py`, réservé à qui écrit) et l'outil CLI nomme aussi, au motif qu'« un rapport d'accord se lit pour arbitrer, puis se jette ». Un CSV téléchargé a la même DESTINATION que le CLI et la persistance d'un artefact déposé — c'est précisément la ligne DEDANS/DEHORS d'AUTH-1, et elle n'a jamais été posée sur ce cas
- [x] **TRANCHÉ le 2026-09-08 : LES DEUX, au choix** (`forme=plat|matrice`). Les deux usages sont réels et aucun ne se déduit de l'autre — on cite une matrice dans un article, on retraite des lignes plates dans R. Une matrice se reconstruit d'un pivot ; l'inverse perd de l'information. *Énoncé d'origine :* Le CSV du **croisement** a une forme décidée : matrice (une ligne par valeur de X, une colonne par valeur de Y) ou lignes plates (`x ; y ; n`). La matrice se lit dans un tableur, les lignes plates se retraitent dans R ou pandas — et le tableau porte des MARGES, qui n'ont pas la même place dans les deux formes
- [x] **TRANCHÉ : le COMPLET, sous un plafond relevé (5000) et ÉCRIT.** La vue le dit (« le fichier rend le jeu TROUVÉ, pas l'aperçu affiché »), et le NOM du fichier porte `-tronque-` quand le plafond mord. Les trois autres places ont été écartées pour une raison chacune : une ligne de commentaire en tête décale l'en-tête d'un tableur, une ligne en pied entre dans les données de pandas, un en-tête HTTP ne survit pas au premier déplacement du fichier. *Énoncé d'origine :* L'export rend le jeu AFFICHÉ ou le jeu COMPLET, et le choix est écrit sur chaque vue. Le croisement affiche un top-20 par axe ; exporter ce top-là, c'est exporter une troncature dont les marges ne somment pas — ce que `renderCroise` signale déjà à l'écran (« top 20 par axe ») et qu'un CSV muet ferait passer pour un total
- [x] **TRANCHÉ : une route `.csv` par vue**, comme `/api/recherche/export.csv`. Le dépôt avait déjà choisi ce sens, et le cliquet des sorties d'identité compte UNE entrée par SORTIE : un `format=csv` ferait d'une route deux sorties sous une seule déclaration. *Énoncé d'origine :* La forme de route est décidée : une route `.csv` par vue (patron de `/api/recherche/export.csv`) ou un paramètre `format=csv` sur les routes existantes. Le dépôt a déjà tranché une fois, dans le premier sens

### Le travail

- [x] Les quatre vues de l'Exploration ont un bouton d'export qui produit un CSV du jeu courant, aux mêmes critères que l'affichage. **Fait** : l'export rejoue les paramètres RETENUS au moment où la vue les construit (`armerExport`), et non rebâtis au clic — les rebâtir aurait été écrire une seconde fois la même chose, et les deux copies auraient divergé sans que rien ne le dise. *Énoncé d'origine :* un bouton d'export qui produit un CSV du jeu courant, aux mêmes critères que l'affichage — vérifiable en comparant les totaux du fichier à ceux de `#dist-info`
- [x] Les panneaux 🎯 Accord et 👥 Inter ont le leur, sur la décision d'arbitrage ci-dessus. **Fait** — et le panneau Inter ÉCRIT à l'écran que le fichier nomme, et pourquoi
- [x] **Fait, et éprouvé** : un lemme `=CMD()` ressort préfixé d'une apostrophe. Chaque cellule de texte libre passe par `_csv_safe` (anti-injection de formule) et chaque réponse par `_csv_response` (BOM + `Content-Disposition`) : aucun `csv.writer` nu
- [x] **Fait** : quatre cœurs extraits — `_frequences_rows`, `_concordance_rows`, `_comparaison_rows`, `_croisement_data` —, chacun partagé par sa route JSON et son export, le plafond étant le SEUL paramètre qui les distingue. Un test compare le CSV au JSON ligne à ligne, sur le CONTENU et non sur le source. *Énoncé :* Le calcul n'est PAS réécrit pour l'export : la route CSV appelle le même cœur que la route JSON, comme `recherche_export` et `/api/recherche` partagent `_recherche_rows`. Deux chemins finiraient par diverger sur un filtre, et c'est le genre de divergence qu'on ne voit pas — les deux réponses restent plausibles

### Autorisation — deux cliquets à ne pas laisser au hasard

- [x] **Fait** — le cliquet compte 128 routes cloisonnées sur 135. Chaque nouvelle route consulte la portée et passe par `_analyse_filtres` : le cliquet de `test_autorisation.py` échoue si elle ne tranche pas, mais il ne dit PAS qu'elle tranche bien — un export qui recalculerait ses filtres à côté serait vert et fuirait
- [x] **Fait, et éprouvé des deux côtés** : un compte qui lit sans écrire nulle part reçoit 403 sur la route JSON ET sur le CSV. L'export d'Inter hérite du **403** de sa route (qui n'écrit nulle part ne le lit pas), et non d'un contrôle réécrit
- [x] **Fait, et le cliquet l'a EXIGÉ avant que j'y pense** : il a refusé `accord-inter.csv` en nommant la sorte qui fuyait. Une seule des six émet une identité ; les cinq autres ne portent que du corpus. Chaque nouvelle sortie est DÉCLARÉE dans `tests/test_sorties_identite.py` avec la sorte émise et sa raison — c'est un cliquet dur : une sortie non déclarée où la sentinelle apparaît fait échouer la suite
- [x] **Fait, sur les six.** Cinq passent par un décor commun ; la sixième — `accord-inter.csv` — a demandé une chaîne de révision posée dans le journal A3, sans quoi son rapport est vide des DEUX côtés et « identique » n'y prouverait rien. **Le test est bâti pour ne pas pouvoir passer à vide** : il exige de voir ce qui est AUTORISÉ avant de vérifier l'absence de ce qui ne l'est pas. Un test de comportement vérifie qu'un export ne rend RIEN d'un album hors portée, sur les six sorties — le cliquet ci-dessus ferme la porte de l'oubli, pas celle de l'erreur

## Deux erreurs de test, et un choix repris — 2026-09-08

**Mon anti-vacuité comparait des LONGUEURS de chaîne.** Le croisement passait bien de 2 à 1
partout sous la portée de bob — le cloisonnement marchait —, mais « 2 » et « 1 » font la
même largeur, et l'assertion tombait sur une propriété qui n'était pas celle qu'on garde.
Elle compare désormais le CONTENU, ce qui dit la même chose sans supposer que filtrer
raccourcisse.

**Le test de portée de la concordance filtrait sur un lemme propre à l'album AUTORISÉ.** Il
mesurait donc le FILTRE et non la portée, et passait pour une raison qui n'avait rien à voir
avec ce qu'il prétendait garder. Corrigé par un critère présent dans les DEUX albums. C'est
la forme la plus coûteuse d'un test vert : il ne signale rien, et on le croit.

**Et j'avais mis les totaux de la comparaison dans une ligne de commentaire en tête** —
exactement la place que je venais d'écarter pour la troncature, au motif qu'elle décale
l'en-tête d'un tableur. Ce sont des colonnes répétées : deux colonnes constantes coûtent
moins qu'une convention que l'un des deux lecteurs ne connaît pas.

## Contexte

**Ce chantier absorbe un point d'`ANA-6`** : « La concordance a un export dédié, cohérent
avec les autres exports (`_csv_safe` appliqué) », différé à la livraison de B2/B3. Le
laisser là aurait fait traiter la concordance seule, puis redécouvrir trois vues sans
sortie. La case reste dans `ANA-6` tant que celle-ci n'est pas ouverte ; elle se coche
avec ce chantier-ci.

**À ne pas confondre avec `EXP-1`**, qui expose dans l'UI les exports de DÉPÔT (fiche de
description de collection, manifeste IIIF, crosswalk) — des artefacts FAIR destinés à
Nakala. **`EXP-1` est `livré` depuis le 2026-09-07** : le bloc *Export de dépôt* vit dans
Administration → 👥 Collections, et cette page le donnait encore pour « différé derrière
INFRA-1 ». Et l'asymétrie que ce chantier dénonce s'est CREUSÉE : l'export de dépôt a
désormais son bouton, celui de l'Exploration n'en a toujours aucun — la surface qui produit
des chiffres reste la seule qui ne les rende pas. Ici il s'agit des RÉSULTATS d'une analyse, qu'on
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
d'`UX-7`. **`UX-7` a été livré le 2026-09-05 en ENTIER — 19 cases sur 19 — donc la
condition est remplie et au-delà de ce qu'elle demandait** (relevé le 2026-09-07 : cette
page l'annonçait encore « ouverte et à moitié faite »). Le manque reste un manque d'usage,
pas un défaut : rien n'est perdu ni faux à l'écran, et c'est ce qui décide de la priorité —
plus l'attente d'un autre chantier.

L'état des lieux ci-dessus a été REVÉRIFIÉ le 2026-09-07 et il tient : le dépôt ne porte
toujours que deux sorties CSV, `/api/recherche/export.csv` et `/api/export/csv`. Aucune des
quatre vues d'Exploration n'en a.
