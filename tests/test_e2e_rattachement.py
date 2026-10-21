"""UX-13 — voir la case dont on parle, au moment où on la choisit.

« Rattaché à » (`#region-parent`) reste un `<select>` NATIF (Hugo, 2026-10-21) : son menu
ouvert est rendu hors de la page, et ses options ne reçoivent pas de survol fiable. La case
se surligne donc quand elle est CHOISIE — à la souris, ou aux flèches sur le menu fermé,
qui émettent `change` — et quand le menu reçoit le focus ; le halo part avec le focus.

Le halo est celui de l'arbre (`highlightRegion`, classe `hover-hi`) : ce fichier le lit sur
le rectangle de la planche, pas sur le menu. Et il vérifie que le rattachement PART bien —
surligner sans enregistrer serait un autre défaut.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Le menu « Rattaché à » ne vit
# que dans le panneau de l'Atelier.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "aucune région à rattacher : la Recherche lit le corpus",
    "/corpus": "aucune région à rattacher : la Bibliothèque range des albums et des planches",
    "/exploration": "aucune région à rattacher : l'Exploration compte le corpus",
    "/administration": "aucune région à rattacher : rien n'y porte sur une planche",
}


@pytest.fixture
def decor(live_server):
    """Deux cases côte à côte, et une bulle rattachée à la première."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E rattachement"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(**corps):
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        a = region(type="case", x=20, y=20, w=360, h=900)
        b = region(type="case", x=420, y=20, w=360, h=900)
        bulle = region(type="bulle", x=60, y=60, w=200, h=120, parent_id=a)
    return {"base": live_server, "album": aid, "planche": pid, "a": a, "b": b, "bulle": bulle}


def _ouvrir(page, d):
    page.goto(f"{d['base']}/?album={d['album']}&planche={d['planche']}&region={d['bulle']}",
              wait_until="networkidle")
    expect(page.locator("#region-parent")).to_have_value(str(d["a"]), timeout=15000)


def _halo(page):
    """Les régions que le halo désigne, par identifiant."""
    return page.locator("rect.region.hover-hi")


def _parent(d, rid):
    with httpx.Client(base_url=d["base"], trust_env=False, timeout=30) as c:
        for r in c.get(f"/api/planches/{d['planche']}/regions").json():
            if r["id"] == rid:
                return r["parent_id"]
    raise AssertionError(f"région {rid} introuvable")


def _sortir(page):
    """Le focus quitte le menu pour un autre champ du panneau."""
    page.locator("#region-type").focus()
    expect(page.locator("#region-parent")).not_to_be_focused()


def test_choisir_une_case_a_la_souris_la_surligne(page, decor):
    d = decor
    _ouvrir(page, d)
    expect(_halo(page)).to_have_count(0)
    chemin = f"/api/regions/{d['bulle']}"
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(chemin)) as reponse:
        # La souris ouvre le menu (il reçoit le focus), puis choisit : `select_option` ne
        # fait que le choix, comme le menu natif rendu hors de la page.
        page.locator("#region-parent").click()
        page.locator("#region-parent").select_option(str(d["b"]))
    assert reponse.value.status == 200, reponse.value.text()
    assert reponse.value.request.post_data_json["parent_id"] == d["b"]
    # La case CHOISIE, et elle seule — y compris après le redessin de l'enregistrement.
    expect(_halo(page)).to_have_count(1)
    expect(_halo(page)).to_have_attribute("data-id", str(d["b"]))
    assert _parent(d, d["bulle"]) == d["b"]

    _sortir(page)
    expect(_halo(page)).to_have_count(0)


def test_le_focus_puis_les_fleches_surlignent_la_case_choisie(page, decor):
    d = decor
    _ouvrir(page, d)
    menu = page.locator("#region-parent")
    menu.focus()
    # Focalisé : la case courante se désigne avant tout choix.
    expect(_halo(page)).to_have_attribute("data-id", str(d["a"]))
    expect(_halo(page)).to_have_count(1)

    chemin = f"/api/regions/{d['bulle']}"
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(chemin)) as reponse:
        menu.press("ArrowDown")                        # le menu fermé : la suivante est choisie
    assert reponse.value.request.post_data_json["parent_id"] == d["b"]
    expect(menu).to_have_value(str(d["b"]))
    expect(_halo(page)).to_have_count(1)
    expect(_halo(page)).to_have_attribute("data-id", str(d["b"]))

    # « aucun (planche) » ne désigne aucune case.
    for _ in range(2):
        with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith(chemin)):
            menu.press("ArrowUp")
    expect(menu).to_have_value(re.compile(r"^$"))
    expect(_halo(page)).to_have_count(0)
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith(chemin)):
        menu.press("ArrowDown")
    expect(_halo(page)).to_have_attribute("data-id", str(d["a"]))

    _sortir(page)
    expect(_halo(page)).to_have_count(0)


def test_l_arbre_surligne_toujours_au_survol(page, decor):
    """Ce qui existait ne bouge pas : le survol d'un nœud de l'arbre pose le même halo,
    et le retire en sortant."""
    d = decor
    _ouvrir(page, d)
    noeud = page.locator(".tnode", has=page.locator(".tn-id", has_text=re.compile(rf"^#{d['b']}$")))
    noeud.hover()
    expect(_halo(page)).to_have_attribute("data-id", str(d["b"]))
    page.mouse.move(0, 0)
    expect(_halo(page)).to_have_count(0)
