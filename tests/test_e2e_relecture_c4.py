"""Relecture croisée COL-3 3a (t3a-c4) — l'écran de la Bibliothèque sous l'identité
concernée. Le décor est celui de `test_e2e_bibliotheque_3a.py`."""
import json

import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402
from conftest import ECRITURE, du_projet  # noqa: E402

from test_e2e_bibliotheque_3a import (_choisir_projet, _client, _comme, _ok,  # noqa: E402,F401
                                      _ouvrir, _requetes, decor)

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/administration": "relecture : les seuls gestes de la Bibliothèque",
    "/": "relecture : les seuls gestes de la Bibliothèque",
    "/recherche": "relecture : les seuls gestes de la Bibliothèque",
    "/exploration": "relecture : les seuls gestes de la Bibliothèque",
}


def _case(page, cid):
    return page.locator(f'#album-range-cases input[data-ranger="{cid}"]')


def test_decocher_quand_on_ne_pourra_pas_recocher_se_confirme(page, decor):
    """Sam écrit dans Lot A ET Lot B sans posséder ni l'un ni l'autre ; Lotus est rangé dans
    les deux. Décocher Lot B ne lui retire ni la vue ni l'écriture — mais recocher sera une
    DEMANDE à Ana (D4 stricte). Le geste est un aller simple pour lui : il doit se confirmer,
    et dire qu'il ne pourra pas le défaire seul."""
    with _client(decor["base"]) as c:
        du_projet(c, decor['lot_a'], "utilisateur", "sam", headers=ECRITURE)
        _ok(c.put(f"/api/collections/{decor['lot_a']}/acces",
                  json={"genre": "utilisateur", "principal": "sam", "niveau": "ecriture"}))
        _ok(c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['lot_b']}"), 201)
    _choisir_projet(page, decor)
    dialogues = []

    def _repondre(d):
        dialogues.append(d.message)
        d.accept()
    page.on("dialog", _repondre)
    _ouvrir(page, decor["base"], _comme("sam"), f"/corpus?album={decor['albums']['Lotus']}")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    expect(_case(page, decor["lot_b"])).to_be_enabled()
    _case(page, decor["lot_b"]).click()
    expect(page.locator("#album-range-msg")).to_contain_text("n'est plus dans", timeout=5000)
    # Recocher : ce n'est plus lui qui décide.
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    with page.expect_response(lambda r: r.request.method == "PUT") as rep:
        _case(page, decor["lot_b"]).click()
    assert rep.value.status == 202, "recocher n'est plus un geste à lui"
    assert dialogues, ("décocher Lot B s'est fait SANS confirmation, alors que Sam ne peut "
                       "plus l'y ranger lui-même (D4 stricte : la demande part à Ana)")


def test_decocher_la_derniere_collection_dit_le_fonds_avant(page, decor):
    _choisir_projet(page, decor)
    dialogues = []

    def _repondre(d):
        dialogues.append(d.message)
        d.accept()
    page.on("dialog", _repondre)
    _ouvrir(page, decor["base"], _comme("ana"), f"/corpus?album={decor['albums']['Oreille']}")
    page.locator("#album-range[data-pret]").wait_for(timeout=5000)
    _case(page, decor["lot_a"]).click()
    page.wait_for_timeout(1500)
    assert len(dialogues) == 1, dialogues
    assert "dernière collection" in dialogues[0] and "gardée au fonds" in dialogues[0], dialogues
    with _client(decor["base"]) as c:
        a = next(x for x in c.get("/api/albums").json() if x["id"] == decor["albums"]["Oreille"])
        assert a["au_fonds"] is True


def test_un_proprietaire_d_une_seule_collection_ne_voit_aucun_bouton(page, decor):
    """Lotus vit dans Lot A (Ana) et Lot B (possédé par Zoé). Sam, qui écrit dans la base,
    demande à le ranger dans la base : Ana ne tient pas toute la copie — `repondable` faux."""
    with _client(decor["base"]) as c:
        du_projet(c, decor['lot_b'], "utilisateur", "zoe", headers=ECRITURE)
        _ok(c.put(f"/api/collections/{decor['lot_b']}/acces",
                  json={"genre": "utilisateur", "principal": "zoe", "niveau": "proprietaire"}))
        _ok(c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['lot_b']}"), 201)
        du_projet(c, decor['base_id'], "utilisateur", "sam", headers=ECRITURE)
        _ok(c.put(f"/api/collections/{decor['base_id']}/acces",
                  json={"genre": "utilisateur", "principal": "sam", "niveau": "ecriture"}))
    with _client(decor["base"], _comme("sam")) as c:
        r = c.put(f"/api/albums/{decor['albums']['Lotus']}/collections/{decor['base_id']}")
        assert r.status_code == 202, r.text
    with _client(decor["base"], _comme("ana")) as c:
        l = c.get(f"/api/collections/{decor['lot_a']}/demandes").json()
        assert [d["repondable"] for d in l] == [False], l
    _choisir_projet(page, decor)
    _ouvrir(page, decor["base"], _comme("ana"), f"/corpus?collection={decor['lot_a']}&onglet=albums")
    expect(page.locator("#panneau-albums tr.col-album").first).to_be_visible(timeout=5000)
    page.wait_for_timeout(800)
    expect(page.locator("[data-repondre]")).to_have_count(0)
    expect(page.locator("#bi-recues-compteur, .col-marque")).to_have_count(0)


def test_deja_dans_ce_projet_une_seconde_copie_se_fait_tout_de_suite(page, decor):
    """Rui (responsable) coche Lotus, « déjà dans ce projet ». La requête est un `zero` (une
    seconde copie), jamais un rejoindre. Avant la tranche 3c de COL-3, Rui ne lisait pas
    Lot A et le serveur en faisait une DEMANDE d'entrée, que le pied du panneau démentait ;
    depuis (F1), le responsable LIT toutes les collections de son projet — il lit donc une
    copie du document, et la seconde copie se fait tout de suite, comme le pied le dit."""
    _choisir_projet(page, decor)
    vues = _requetes(page, "/prendre")
    _ouvrir(page, decor["base"], _comme("rui"))
    page.locator("#bi-prendre-fonds").click()
    pied = page.locator(".bi-prise-actions .muted")
    page.locator("#bi-prise-q").fill("lotus")
    ligne = page.locator(f'#bi-prise-notices li[data-notice="{decor["docs"]["Lotus"]}"]')
    expect(ligne.locator(".bi-deja")).to_be_visible(timeout=5000)
    ligne.locator("input[type=checkbox]").check()
    page.locator("#bi-prise-motif").fill("Seconde copie.")
    page.locator("#bi-prise-ok").click()
    expect(ligne.locator(".reponse")).to_be_visible(timeout=5000)
    corps = json.loads(vues[-1][2])
    assert corps["documents"] == [{"document_id": decor["docs"]["Lotus"], "reponse": "zero"}]
    with _client(decor["base"]) as c:
        dem = c.get(f"/api/projets/{decor['projet']}/demandes").json()
        assert [d["genre"] for d in dem] == [], dem
    texte_ligne = ligne.locator(".reponse").inner_text()
    assert "demandé" not in texte_ligne, texte_ligne
