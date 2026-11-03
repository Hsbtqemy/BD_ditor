"""UX-6 — ce que le souvenir du wizard suppose du serveur : un bac à sable effacé ne
revient jamais sous le même identifiant.

Tranché par Hugo le 2026-11-03 : le souvenir du wizard (l'album déjà vu, le parcours,
l'étape) vit dans le NAVIGATEUR, rangé par login et sous l'identifiant du bac à sable
(`static/lib/wizard.js`). Après un effacement — le lundi, ou « Remettre à neuf… » —, le
wizard doit repartir du début, et non reprendre à l'étape 6 sur une planche remise à zéro.

Le navigateur le sait sans rien demander de plus parce que l'effacement fait naître un
projet NEUF, à un autre identifiant — les identifiants de projet ne reviennent pas
(`AUTOINCREMENT`, v31). C'est cette propriété du serveur que le module tient pour acquise,
et ce test la mesure sur les DEUX chemins : la remise à neuf, et le lundi suivi d'un
nouveau « Mon bac à sable ». La date d'effacement est la seconde marque que le souvenir
compare : elle change avec le lundi, pas avec la remise à neuf — d'où l'identifiant d'abord.
Le côté navigateur est mesuré par `tests/js/wizard.test.js` (« après un effacement… »).
"""
import sys
from pathlib import Path

import pytest

import database
from test_bac_a_sable import LEA, _sql
from test_jeu import DOC_EXEMPLE, DOC_PARCOURS, ecrire_jeu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import effacer_bacs_a_sable  # noqa: E402
import preparer_jeu  # noqa: E402


@pytest.fixture
def jeu(client, tmp_path, derriere_proxy):
    depot = ecrire_jeu(tmp_path / "jeu-depot", [DOC_PARCOURS, DOC_EXEMPLE],
                       images=("p1.png", "p2.png", "p3.png"))
    conn = database.get_connection()
    try:
        preparer_jeu.preparer(conn, depot=depot, serveur=None, appliquer_=True,
                              dire=lambda _l: None)
    finally:
        conn.close()
    client.get("/api/moi", headers=LEA)


def _cle(vue):
    """Ce que le souvenir compare : l'identifiant et la date d'effacement."""
    return (vue["id"], vue["efface_le"])


def test_la_remise_a_neuf_donne_un_nouvel_identifiant(client, jeu):
    avant = client.post("/api/bac-a-sable", headers=LEA).json()
    neuf = client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA).json()
    assert neuf["id"] != avant["id"]
    # La date, elle, peut rester la même (le même lundi) : elle ne suffirait pas seule.
    assert _cle(neuf) != _cle(avant)
    # Et la ligne du projet dans `GET /api/projets`, que lit le wizard, dit la même chose.
    mien = [p for p in client.get("/api/projets", headers=LEA).json()
            if p.get("bac_a_sable", {}).get("mien")]
    assert [(p["id"], p["bac_a_sable"]["efface_le"]) for p in mien] == [_cle(neuf)]


def test_le_lundi_puis_mon_bac_a_sable_donnent_un_nouvel_identifiant(client, jeu, db_path):
    avant = client.post("/api/bac-a-sable", headers=LEA).json()
    _sql(db_path, "UPDATE projet SET efface_le = '2000-01-01 00:00:00' WHERE id = ?",
         (avant["id"],))
    conn = database.get_connection()
    try:
        bilan = effacer_bacs_a_sable.effacer(conn, appliquer=True, dire=lambda _l: None)
    finally:
        conn.close()
    assert bilan["effaces"] == [avant["id"]]
    assert client.get("/api/bac-a-sable", headers=LEA).json() is None
    apres = client.post("/api/bac-a-sable", headers=LEA).json()
    assert apres["id"] != avant["id"]
    assert apres["efface_le"] != "2000-01-01 00:00:00"


def test_un_identifiant_efface_n_est_jamais_rendu(client, jeu):
    """Trois remises à neuf de suite : trois identifiants neufs, tous plus grands que le
    précédent — un identifiant rendu ferait relire le souvenir d'un bac à sable effacé."""
    vus = [client.post("/api/bac-a-sable", headers=LEA).json()["id"]]
    for _ in range(3):
        vus.append(client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA).json()["id"])
    assert vus == sorted(set(vus)), vus
