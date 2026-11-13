"""ANN-8 — une apostrophe ou un accent ne font pas deux tags.

Lu le 2026-10-12 : `socle._norm_tag` ne normalisait que la casse et les espaces, et le
libellé d'un tag est unique à l'octet. Le guide des linguistes écrit ses tags avec
l'apostrophe typographique (« c’est pluriel »), un clavier tape la droite ; un accent arrive
composé ou décomposé selon le système. Chaque variante faisait un tag de plus — donc un
compteur de plus, ce que le guide redoute en toutes lettres.

La CLÉ d'un libellé (`database.cle_tag`) les confond. Les tags sont partis avec le
basculement d'ANN-7 ; la clé reste, par laquelle une entrée de grille qui naît en posant
retrouve celle de même nom (`routes/releves._entree_neuve`). Ses tests par les routes des
tags sont partis avec elles, comme sa jumelle JS (`cleTag`) ; la table reste.
"""
import json
from pathlib import Path

import pytest

import database

TABLE = json.loads((Path(__file__).parent / "cas-tags.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_table_partagee(cas):
    assert database.cle_tag(cas["entree"]) == cas["attendu"]


def test_la_cle_est_idempotente():
    for cas in TABLE:
        assert database.cle_tag(database.cle_tag(cas["entree"])) == cas["attendu"], cas["nom"]
