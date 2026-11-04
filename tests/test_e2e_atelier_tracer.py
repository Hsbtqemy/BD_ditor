"""UX-6 — « ✎ Tracer » : l'Atelier a un geste de tracer pour TOUS, au clavier et au doigt.

À la souris, on trace en glissant sur le fond de la planche (Maj+glisser au-dessus d'une
case). Ni le clavier ni le doigt n'avaient ce geste, et l'étape « Tracer une zone » du wizard
ne tenait pas sans lui (`pilotage/UX-6.md`). Le bouton de la barre du canevas, en mode
Édition, le donne comme « Tracer une zone » de la page Annotation, dont il reprend la règle
(`BDAnnotation.rectangleInitial`, `rectangleClavier`) : au clavier il pose un rectangle que
les flèches déplacent et que Maj+flèches redimensionnent, Entrée le crée ; au doigt il arme
le glissé. Ce fichier lit ce qui PART au serveur — la zone créée, sa place, sa sorte —, pas
seulement ce que l'écran montre.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. « ✎ Tracer » vit dans la
# barre du canevas de l'Atelier.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": "la page Annotation a son propre « Tracer une zone » (`#an-tracer`), joué "
                   "par ses tests ; ce fichier audite celui de l'Atelier",
    "/recherche": "aucune planche à découper : la Recherche lit le corpus",
    "/corpus": "aucune planche à découper : la Bibliothèque range des albums et des planches",
    "/exploration": "aucune planche à découper : l'Exploration compte le corpus",
    "/administration": "aucune planche à découper : rien n'y porte sur une planche",
}


@pytest.fixture
def decor(live_server):
    """Une planche de 800 × 1 000 px et une case sur sa moitié gauche."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E tracer"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]
        rep = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 20, "y": 20, "w": 360, "h": 900})
        assert rep.status_code in (200, 201), rep.text
    return {"base": live_server, "album": aid, "planche": pid, "case": rep.json()["id"]}


def _ouvrir(page, d, suite=""):
    """L'Atelier sur la planche, en mode Édition ; on attend ses régions, pas le réseau."""
    with page.expect_response(lambda r: r.url.endswith(f"/api/planches/{d['planche']}/regions")
                              and r.request.method == "GET"):
        page.goto(f"{d['base']}/?album={d['album']}&planche={d['planche']}&mode=edition{suite}",
                  wait_until="domcontentloaded")
    bouton = page.locator("#atelier-tracer")
    expect(bouton).to_be_visible()
    return bouton


def _creation(page):
    return page.expect_response(lambda r: r.url.endswith("/regions")
                                and r.request.method == "POST")


def test_le_bouton_est_un_geste_du_mode_edition(page, decor):
    bouton = _ouvrir(page, decor)
    expect(bouton).to_have_attribute("aria-pressed", "false")
    page.locator('.mode-btn[data-mode="navigation"]').click()
    expect(bouton).to_be_hidden()
    page.locator('.mode-btn[data-mode="edition"]').click()
    expect(bouton).to_be_visible()


def test_au_clavier_un_rectangle_que_les_fleches_placent(page, decor):
    bouton = _ouvrir(page, decor)
    # Échap y renonce : rien ne part, le focus revient au bouton.
    bouton.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#stage")).to_be_focused()
    expect(page.locator("#draw-rect")).to_have_count(1)
    expect(bouton).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Escape")
    expect(page.locator("#draw-rect")).to_have_count(0)
    expect(bouton).to_be_focused()
    expect(bouton).to_have_attribute("aria-pressed", "false")

    # Sans case choisie, le rectangle naît au milieu de la planche, qu'on voit en entier :
    # le tiers de ses côtés. Une flèche le déplace d'un vingtième, Maj+flèche l'agrandit.
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Shift+ArrowDown")
    # Les flèches ne sont pas montées au raccourci de l'Atelier (zone suivante) : rien n'est
    # choisi.
    expect(page.locator("#panel-content")).to_be_hidden()
    with _creation(page) as rep:
        page.keyboard.press("Enter")
    zone = rep.value.json()
    assert (zone["x"], zone["y"], zone["w"], zone["h"]) == (307, 334, 267, 383), zone
    # Hors de toute case : une case, tracée à la main.
    assert (zone["type"], zone["parent_id"], zone["source"]) == ("case", None, "manuel")
    expect(page.locator("#draw-rect")).to_have_count(0)
    expect(bouton).to_have_attribute("aria-pressed", "false")


def test_au_clavier_dans_la_case_choisie_une_bulle(page, decor):
    bouton = _ouvrir(page, decor, f"&region={decor['case']}")
    expect(page.locator("#panel-content")).to_be_visible()
    bouton.focus()
    page.keyboard.press("Enter")
    with _creation(page) as rep:
        page.keyboard.press("Enter")
    zone = rep.value.json()
    # Le rectangle naît au milieu de la case choisie (le tiers de ses côtés) : une bulle.
    assert (zone["x"], zone["y"], zone["w"], zone["h"]) == (140, 320, 120, 300), zone
    assert (zone["type"], zone["parent_id"]) == ("bulle", decor["case"])


# Un glissé au doigt, en événements de pointeur `touch` : Playwright n'a pas de glissé
# tactile, et c'est ce que l'Atelier écoute.
DOIGT = """([x1, y1, x2, y2]) => {
  const stage = document.getElementById('stage');
  const pt = (type, x, y) => stage.dispatchEvent(new PointerEvent(type, {
    pointerId: 7, pointerType: 'touch', isPrimary: true, clientX: x, clientY: y,
    bubbles: true, cancelable: true }));
  pt('pointerdown', x1, y1);
  pt('pointermove', (x1 + x2) / 2, (y1 + y2) / 2);
  pt('pointermove', x2, y2);
  pt('pointerup', x2, y2);
}"""


def test_au_doigt_le_bouton_arme_le_glisse(page, decor):
    bouton = _ouvrir(page, decor)
    s = page.locator("#planche-img").bounding_box()
    # La moitié droite de la planche, hors de la case.
    x1, y1 = s["x"] + s["width"] * 0.6, s["y"] + s["height"] * 0.3
    x2, y2 = s["x"] + s["width"] * 0.8, s["y"] + s["height"] * 0.45
    # Désarmé, un glissé au doigt ne trace rien.
    page.evaluate(DOIGT, [x1, y1, x2, y2])
    expect(page.locator("#draw-rect")).to_have_count(0)
    bouton.click()
    expect(bouton).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#stage")).to_have_class(re.compile(r"\btrace-arme\b"))
    with _creation(page) as rep:
        page.evaluate(DOIGT, [x1, y1, x2, y2])
    zone = rep.value.json()
    assert (zone["type"], zone["source"]) == ("case", "manuel"), zone
    assert zone["w"] > 8 and zone["h"] > 8
    # Une zone née désarme le bouton.
    expect(bouton).to_have_attribute("aria-pressed", "false")
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30) as c:
        regions = c.get(f"/api/planches/{decor['planche']}/regions").json()
    assert len(regions) == 2


@pytest.mark.parametrize("largeur", [320, 768, 1280])
def test_la_barre_du_canevas_garde_tout_avec_le_bouton(page, decor, largeur):
    """Le bouton s'ajoute à la barre du canevas, mesurée au pixel (cf. `#toolbar` dans
    `style.css`) : en mode Édition, sous des préférences de police de 16 et 24, rien n'y est
    perdu ni hors champ (la sonde de `test_e2e_reflow`, la surface de pan exemptée comme
    là-bas)."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    from tools.mesurer_reflow import SONDE
    echecs = []
    for police in (16, 24):
        cdp = page.context.new_cdp_session(page)
        cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
        page.set_viewport_size({"width": largeur, "height": 900})
        _ouvrir(page, decor)
        page.wait_for_timeout(300)
        perdus = [c for c in page.evaluate(SONDE)["coupables"]
                  if not c["cadre"] and c["id"] != "canvas"]
        if perdus:
            echecs.append(f"police {police} : {perdus[:4]}")
        b = page.locator("#atelier-tracer").bounding_box()
        t = page.locator("#toolbar").bounding_box()
        if not (t["x"] - 1 <= b["x"] and b["x"] + b["width"] <= t["x"] + t["width"] + 1):
            echecs.append(f"police {police} : « ✎ Tracer » hors de la barre {b} / {t}")
    assert not echecs, "\n".join(echecs)
