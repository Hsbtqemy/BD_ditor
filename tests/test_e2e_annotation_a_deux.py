"""Deux personnes sur la même bulle : ce que l'une enregistre n'efface pas l'autre (CONC-3).

Mesuré le 2026-09-16 à deux navigateurs (`pilotage/CONC-3.md`, mesure 1) : l'Atelier
renvoyait la note ET les tags chargés quand la bulle avait été sélectionnée. B ajoutait un
tag ; A, restée sur la bulle, tapait sa note, et son enregistrement effaçait le tag de B
sans un mot. Dans l'autre sens, le tag suivant de B effaçait la note de A.

La garde rejoue le geste tel quel, dans deux contextes de navigateur ouverts AVANT le premier
enregistrement : c'est ce qui rend l'état de chacun périmé. Elle juge par l'API, pas par
l'écran : ce qui compte est ce qui reste en base.
"""
import time

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/recherche": "on n'y annote pas : la note et les tags s'écrivent dans l'Atelier seul",
    "/corpus": "on n'y annote pas : la note et les tags s'écrivent dans l'Atelier seul",
    "/exploration": "on n'y annote pas : la note et les tags s'écrivent dans l'Atelier seul",
    "/administration": "on n'y annote pas : la note et les tags s'écrivent dans l'Atelier seul",
}


@pytest.fixture
def bulle(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E à deux"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        cid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 10, "y": 10, "w": 80, "h": 60}).json()["id"]
        bid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 15, "y": 15, "w": 30, "h": 20,
                           "parent_id": cid}).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "url": f"{live_server}/?album={aid}&planche={pid}&region={bid}",
            "region": bid}


def _en_base(base, region):
    with httpx.Client(base_url=base, trust_env=False, timeout=10, headers=ECRITURE) as c:
        a = c.get(f"/api/regions/{region}/annotation").json()
    return a["note"] or "", {t["label"] for t in a["tags"]}


def _attendre(base, region, predicat):
    """Attend que la base satisfasse `predicat` : l'enregistrement part 500 ms après le geste."""
    fin, etat = time.time() + 15, None
    while time.time() < fin:
        etat = _en_base(base, region)
        if predicat(*etat):
            return etat
        time.sleep(0.25)
    return etat


def _ouvrir(page, url):
    page.goto(url, wait_until="networkidle")
    page.click('.mode-btn[data-mode="annotation"]')
    expect(page.locator("#note-input")).to_be_visible(timeout=15000)


def test_la_note_de_l_une_n_efface_pas_le_tag_de_l_autre(page, bulle):
    s = bulle
    autre = page.context.browser.new_context()
    try:
        page_b = autre.new_page()
        _ouvrir(page, s["url"])          # A sélectionne la bulle…
        _ouvrir(page_b, s["url"])        # …et B aussi, avant tout enregistrement

        page_b.fill("#tag-input", "tag-de-b")
        page_b.press("#tag-input", "Enter")
        note, tags = _attendre(s["base"], s["region"], lambda n, t: "tag-de-b" in t)
        assert "tag-de-b" in tags, f"le tag de B n'a jamais été enregistré : {tags}"

        page.fill("#note-input", "note de A")
        note, tags = _attendre(s["base"], s["region"], lambda n, t: n == "note de A")
        assert note == "note de A", f"la note de A n'a jamais été enregistrée : {note!r}"
        # Laisser partir un éventuel second envoi avant de juger.
        expect(page.locator("#save-state")).to_have_text("Enregistré", timeout=15000)
        note, tags = _en_base(s["base"], s["region"])
        assert "tag-de-b" in tags, (
            f"la note de A a effacé le tag que B venait de poser : tags en base {tags}")

        # L'autre sens : B, dont l'écran montre toujours une note vide, ajoute un tag.
        page_b.fill("#tag-input", "second-de-b")
        page_b.press("#tag-input", "Enter")
        note, tags = _attendre(s["base"], s["region"], lambda n, t: "second-de-b" in t)
        expect(page_b.locator("#save-state")).to_have_text("Enregistré", timeout=15000)
        note, tags = _en_base(s["base"], s["region"])
        assert tags == {"tag-de-b", "second-de-b"}, f"tags en base : {tags}"
        assert note == "note de A", (
            f"le tag de B a effacé la note de A : note en base {note!r}")
    finally:
        autre.close()
