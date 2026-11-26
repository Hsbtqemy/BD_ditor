#!/usr/bin/env bash
#
# Réindexation NLP de NUIT (NLP-4) : spaCy est en veille dans l'application (`BD_NLP=0`,
# deploy/docker-compose.yml), et ce script le rallume pour UN processus à part, le temps de
# rattraper les lemmes et les tokens de ce qui a été écrit dans la journée. Posé sur un
# timer systemd (deploy/systemd/bd-reindex-nlp.*, chaque nuit à 3 h, heure de Paris).
#
#   ~/BD_ditor/deploy/reindex-nlp.sh
#
# Pourquoi un processus à part et non un chargement suivi d'un déchargement dans
# l'application : décharger le modèle ne rend pas ce que son import a pris — spaCy, thinc
# et torch restent en mémoire jusqu'à la fin du processus (mesuré le 2026-11-26 : 70 Mo
# sans spaCy, 498 Mo avec). Celui-ci rend tout en se terminant.
#
# Il tourne DANS le conteneur, donc sous sa limite de mémoire : la limite doit laisser à
# l'application ses ~500 Mo de plus pendant le passage. `nice` : il cède le processeur aux
# requêtes si quelqu'un travaille à cette heure-là.
#
# Codes de retour : ceux de `tools/reindex_nlp.py` (0 fait ou rien à rattraper, 1 moteur
# indisponible, 130 interrompu), ou celui de `docker exec` si le conteneur ne répond pas.
set -euo pipefail

CONTENEUR="${BD_CONTENEUR_APP:-bd-app}"
exec docker exec -e BD_NLP=1 "$CONTENEUR" nice -n 10 python tools/reindex_nlp.py --a-rattraper
