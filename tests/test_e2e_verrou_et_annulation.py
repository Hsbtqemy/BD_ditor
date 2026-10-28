"""ANN-8 — ce que l'écran de l'Atelier DIT du verrou et de l'annulation.

- **Le bouton de verrou dit ce qu'il protège.** « Verrouiller la planche » se lisait comme
  une réservation (« faut-il verrouiller avant d'annoter ? »). Il protège des traitements
  automatiques et n'empêche aucune annotation : son libellé le dit, court, et son
  infobulle l'explique. La formulation n'est pas verrouillée mot à mot — Hugo la juge à la
  passe — ; ce qui l'est, c'est ce qu'elle doit porter et ne plus porter.
- **Un Ctrl+Z lent le dit.** Le premier après un redémarrage attendait le moteur de langue
  9 à 17 s sans rien afficher. La requête est tenue en vol par le test : l'attente est
  certaine, pas chronométrée.
- **Annuler la suppression d'une case rend son locuteur et sa situation, à l'écran.** Le
  serveur est mesuré par `tests/test_undo_liens.py` ; ici, ce que l'Atelier montre ensuite.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "la page Annotation (ANN-7, tranche 2) n'a pas ce geste : le verrou "
        "d'une planche et l'annulation vit dans l'Atelier, que ce module audite"),
    "/corpus": "le verrou y est un geste de liste (la planche dans la fiche d'un album), "
               "hors du panneau d'annotation que ce fichier lit",
    "/recherche": "ni verrou ni Ctrl+Z : la Recherche lit le corpus",
    "/exploration": "ni verrou ni Ctrl+Z : l'Exploration compte le corpus",
    "/administration": "ni verrou ni Ctrl+Z : rien n'y porte sur une planche",
}


@pytest.fixture
def decor(live_server):
    """Une case avec une situation ; dessous, un cartouche avec un locuteur."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E verrou"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]
        case = c.post(f"/api/planches/{pid}/regions",
                      json={"type": "case", "x": 40, "y": 40, "w": 700, "h": 900}).json()["id"]
        cartouche = c.post(f"/api/planches/{pid}/regions",
                           json={"type": "cartouche", "x": 60, "y": 60, "w": 280, "h": 120,
                                 "parent_id": case}).json()["id"]
        tintin = c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
        dim = c.post("/api/attributs/dimensions", json={"cible": "case", "nom": "lieu"}).json()["id"]
        val = c.post(f"/api/attributs/dimensions/{dim}/valeurs", json={"valeur": "falaise"}).json()["id"]
        assert c.put(f"/api/regions/{case}/attributs", json={"valeur_id": val}).status_code == 200
        assert c.put(f"/api/regions/{cartouche}/locuteur",
                     json={"personnage_id": tintin}).status_code == 200
    return {"base": live_server, "album": aid, "planche": pid, "case": case,
            "cartouche": cartouche}


def _ouvrir(page, d, region=None):
    url = f"{d['base']}/?album={d['album']}&planche={d['planche']}"
    page.goto(url + (f"&region={region}" if region else ""), wait_until="networkidle")
    expect(page.locator("#lock-toggle")).to_be_visible(timeout=15000)


def test_le_bouton_de_verrou_dit_ce_qu_il_protege(page, decor):
    d = decor
    _ouvrir(page, d)
    bouton = page.locator("#lock-toggle")
    expect(bouton).not_to_contain_text(re.compile("verrouill", re.I))
    expect(bouton).to_contain_text(re.compile("auto", re.I))      # ce qu'il protège : les passes auto
    titre = bouton.get_attribute("title")
    assert re.search(r"traitements automatiques", titre), titre
    assert re.search(r"n'empêche aucune annotation", titre, re.I), titre

    with page.expect_response(lambda r: r.request.method == "PATCH"
                              and r.url.endswith(f"/api/planches/{d['planche']}/verrou")) as rep:
        bouton.click()
    assert rep.value.status == 200, rep.value.text()
    bouton = page.locator("#lock-toggle")
    expect(bouton).to_contain_text("🔒")
    expect(bouton).not_to_contain_text(re.compile("verrouill", re.I))
    titre = bouton.get_attribute("title")
    assert re.search(r"annotation reste ouverte", titre, re.I), titre


def test_un_ctrl_z_lent_dit_qu_il_travaille(page, decor):
    d = decor
    with httpx.Client(base_url=d["base"], trust_env=False, timeout=30, headers=ECRITURE) as c:
        assert c.put(f"/api/regions/{d['case']}/annotation",
                     json={"note": "une"}).status_code == 200
        assert c.put(f"/api/regions/{d['case']}/annotation",
                     json={"note": "deux"}).status_code == 200
    _ouvrir(page, d)
    message = page.locator("#toasts .toast", has_text="Annulation en cours")

    # Un Ctrl+Z ordinaire ne dit rien de plus que son résultat.
    page.locator("body").press("Control+z")
    expect(page.locator("#toasts .toast", has_text="modification d'une annotation")
           ).to_be_visible(timeout=15000)
    page.wait_for_timeout(2000)
    expect(message).to_have_count(0)

    # Tenu en vol : au-delà d'un instant, l'écran dit qu'il travaille.
    tenues = []
    page.route("**/api/undo", lambda route: tenues.append(route)
               if route.request.method == "POST" else route.continue_())
    page.locator("body").press("Control+z")
    for _ in range(50):
        if tenues:
            break
        page.wait_for_timeout(100)
    assert tenues, "le Ctrl+Z n'est pas parti"
    expect(message).to_be_visible(timeout=5000)
    with page.expect_response(lambda r: r.url.endswith("/api/undo")
                              and r.request.method == "POST"):
        tenues[0].continue_()
    expect(page.locator("#toasts .toast", has_text="ajout d'une annotation")
           ).to_be_visible(timeout=15000)


def test_annuler_la_suppression_d_une_case_rend_son_locuteur_a_l_ecran(page, decor):
    d = decor
    with httpx.Client(base_url=d["base"], trust_env=False, timeout=30, headers=ECRITURE) as c:
        assert c.delete(f"/api/regions/{d['case']}").status_code == 204
    _ouvrir(page, d)
    with page.expect_response(lambda r: r.url.endswith("/api/undo")
                              and r.request.method == "POST") as rep:
        page.locator("body").press("Control+z")
    assert rep.value.status == 200, rep.value.text()
    assert rep.value.json()["liens_non_rendus"] == 0
    expect(page.locator("#toasts .toast", has_text="suppression d'une région")).to_be_visible()

    _ouvrir(page, d, d["cartouche"])
    page.locator('button[data-mode="annotation"]').click()
    expect(page.locator("#loc-current")).to_contain_text("Tintin", timeout=15000)
    _ouvrir(page, d, d["case"])
    page.locator('button[data-mode="annotation"]').click()
    expect(page.locator("#sit-current")).to_contain_text("falaise", timeout=15000)
