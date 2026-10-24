#!/usr/bin/env bash
#
# Efface les bacs à sable dont le moment est venu (COL-4) : lance l'outil DANS le conteneur
# de l'application, sur sa base. Posé sur un timer systemd (deploy/systemd/bd-bacs-a-sable.*,
# toutes les heures) ; la date d'effacement est en base, ce script n'est qu'un battement.
#
#   ~/BD_ditor/deploy/effacer-bacs-a-sable.sh
#
# Un script du dépôt plutôt qu'un `docker exec` écrit dans l'unité : c'est le patron de
# `bd-deploiement`, et ce que restitue git est ce qui tourne — son bit d'exécution compris
# (`tests/test_veille_deploiement.py` le lit dans l'index).
#
# Codes de retour : ceux de `tools/effacer_bacs_a_sable.py` (0 fait, 2 refusé — un autre
# passage tient le verrou, ou la base n'est pas à la version du code —, 130 interrompu), ou
# celui de `docker exec` si le conteneur ne répond pas.
set -euo pipefail

CONTENEUR="${BD_CONTENEUR_APP:-bd-app}"
exec docker exec "$CONTENEUR" python tools/effacer_bacs_a_sable.py --appliquer
