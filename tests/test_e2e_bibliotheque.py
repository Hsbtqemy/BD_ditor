"""UX-18 — la Bibliothèque refaite, jouée dans un vrai navigateur.

Ce module garde ce que la refonte AJOUTE à la Bibliothèque ; les gestes d'une collection
qu'elle porte depuis COL-2 restent dans `test_e2e_collections.py`, ceux de « Qui entre »
dans `test_e2e_qui_entre.py`. À part de l'audit d'accessibilité pour la raison écrite en
tête de `test_e2e_collections.py` : un module e2e finit par acquérir sa propre condition
de saut, et des tests de COMPORTEMENT n'ont pas à dépendre d'un outil d'audit.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

pytestmark = pytest.mark.e2e

SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/administration": "la refonte d'UX-18 ne touche que la Bibliothèque ; l'Administration "
                       "a ses propres tests de liste et de fiche",
    "/": "l'Atelier travaille une planche ; rien de la Bibliothèque n'y vit",
    "/recherche": "rien de la Bibliothèque n'y vit",
    "/exploration": "rien de la Bibliothèque n'y vit",
}


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


@pytest.fixture
def decor(live_server):
    """Un album d'une planche, dans la collection de repli."""
    with _client(live_server) as c:
        aid = c.post("/api/albums", json={"titre": "Validable", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    return {"base": live_server, "album": aid, "planche": pid}


def _ouvrir_album(page, titre):
    """Ouvre la fiche d'un album depuis la liste de la Bibliothèque."""
    page.locator(".album-row", has_text=titre).first.click()
    page.wait_for_selector("#album-detail button[data-val]", timeout=5000)


def _validee(base, album, planche):
    with _client(base) as c:
        return next(p for p in c.get(f"/api/albums/{album}/planches").json()
                    if p["id"] == planche)["validee"]


def test_valider_est_un_bouton_qui_porte_son_etat(page, decor):
    """Valider une planche est UN bouton (tranché par Hugo le 2026-10-17) : ✔ non enfoncé
    tant qu'elle ne l'est pas, enfoncé quand elle l'est, et le même clic dans les deux sens.
    Le badge ✔ et le ↺ d'avant ont disparu : un seul contrôle par ligne, qui dit l'état.

    Ce que le test garde, c'est la BASCULE : un bouton qui enverrait toujours `true` (ou
    lirait son état à l'envers) laisserait la planche validée au second clic, et l'écran
    afficherait encore un bouton enfoncé — le serveur est donc interrogé après chaque clic,
    pas seulement l'écran."""
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    _ouvrir_album(page, "Validable")
    bouton = page.locator(f'button[data-val="{decor["planche"]}"]')
    expect(bouton).to_be_visible()
    expect(bouton).to_have_attribute("aria-pressed", "false")
    expect(bouton).to_have_text("✔")
    # Plus de badge à côté du bouton, ni de ↺ : un seul contrôle dit l'état.
    expect(page.locator("#album-detail .val-badge")).to_have_count(0)
    assert "↺" not in page.locator("#album-detail").inner_text()

    bouton.click()
    bouton = page.locator(f'button[data-val="{decor["planche"]}"]')
    expect(bouton).to_have_attribute("aria-pressed", "true", timeout=5000)
    assert _validee(decor["base"], decor["album"], decor["planche"]), (
        "le bouton s'est enfoncé sans que la planche soit validée au serveur")
    assert "↺" not in page.locator("#album-detail").inner_text()

    bouton.click()
    bouton = page.locator(f'button[data-val="{decor["planche"]}"]')
    expect(bouton).to_have_attribute("aria-pressed", "false", timeout=5000)
    assert not _validee(decor["base"], decor["album"], decor["planche"]), (
        "le second clic n'a pas retiré la validation : le bouton ne bascule pas")
