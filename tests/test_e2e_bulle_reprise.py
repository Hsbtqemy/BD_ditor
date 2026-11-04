"""UX-6 — une bulle trouvée par le moteur, dont on reprend le cadre, devient « corrigée ».

L'Atelier faisait passer à `corrige` un cadre posé par Kumiko ou par le jeu d'un bac à
sable, et pas une bulle du moteur de bulles (`auto`) : reprise à la main, elle gardait
`auto`, et la détection suivante (`pipeline/bulles.py`) l'effaçait avec la correction. Le
serveur la garde désormais par `touche` (`tests/test_bulles_ocr.py` rejoue la perte) ; ce
fichier mesure la moitié de l'écran, sur la requête PARTIE : le geste de l'Atelier écrit
`corrige`, et seulement sur un cadre posé par une machine.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Reprendre un cadre est un
# geste de l'Atelier.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "la page Annotation ne reprend pas le cadre d'une bulle : elle trace des détails et "
        "des textes hors bulle, jamais une région du moteur"),
    "/recherche": "aucune région à reprendre : la Recherche lit le corpus",
    "/corpus": "aucune région à reprendre : la Bibliothèque range des albums et des planches",
    "/exploration": "aucune région à reprendre : l'Exploration compte le corpus",
    "/administration": "aucune région à reprendre : rien n'y porte sur une planche",
}


@pytest.fixture
def decor(live_server):
    """Une case, une bulle posée par le moteur de bulles et une bulle tracée à la main."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E reprise"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(**corps):
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        case = region(type="case", x=20, y=20, w=760, h=900)
        auto = region(type="bulle", x=60, y=60, w=200, h=120, parent_id=case, source="auto")
        manuelle = region(type="bulle", x=400, y=60, w=200, h=120, parent_id=case)
    return {"base": live_server, "album": aid, "planche": pid, "auto": auto,
            "manuelle": manuelle}


def _reprendre_la_largeur(page, d, rid, largeur):
    """L'Atelier ouvert sur la région, sa largeur changée au champ « L » : la requête partie."""
    page.goto(f"{d['base']}/?album={d['album']}&planche={d['planche']}&region={rid}",
              wait_until="networkidle")
    expect(page.locator("#region-id")).to_have_text(f"#{rid}", timeout=15000)
    page.locator('.mode-btn[data-mode="edition"]').click()
    champ = page.locator("#coord-w")
    expect(champ).to_be_visible()
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(f"/api/regions/{rid}")) as reponse:
        champ.fill(str(largeur))
        champ.press("Enter")
    assert reponse.value.status == 200, reponse.value.text()
    return reponse.value


def test_une_bulle_du_moteur_reprise_devient_corrigee(page, decor):
    rep = _reprendre_la_largeur(page, decor, decor["auto"], 240)
    assert rep.request.post_data_json["source"] == "corrige", rep.request.post_data_json
    assert (rep.json()["source"], rep.json()["w"]) == ("corrige", 240)
    expect(page.locator("#region-source")).to_have_text("corrige")


def test_une_bulle_tracee_a_la_main_garde_sa_source(page, decor):
    """Le témoin : la règle ne marque que ce qu'une machine a posé."""
    rep = _reprendre_la_largeur(page, decor, decor["manuelle"], 230)
    assert "source" not in rep.request.post_data_json, rep.request.post_data_json
    assert rep.json()["source"] == "manuel"
