"""Tests E2E (navigateur réel via Playwright) du round-trip et de la reprise d'état.

Couvre ce qu'aucun test serveur ne peut atteindre : le COMPORTEMENT front (deep-link,
bouton « ← Retour », chaîne `retour`, durcissement anti-XSS) dans un vrai Chromium
pilotant l'app lancée (fixture `live_server`). Cf. docs/navigation-round-trip.md.

Marqués `e2e` → hors du run rapide par défaut (`pytest -m e2e` pour les lancer).
Skippés proprement si Playwright n'est pas installé.
"""
import re
from urllib.parse import quote

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import make_png  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture
def seeded(live_server):
    """Album + planche + une case, créés via l'API sur le serveur live. Renvoie les
    ids et l'URL de base pour construire des deep-links."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 10, "y": 10, "w": 80, "h": 60}).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


def _viewer_url(s, extra=""):
    return (f"{s['base']}/?album={s['album']}&planche={s['planche']}"
            f"&region={s['region']}{extra}")


def test_deep_link_ouvre_la_region(page, seeded):
    """Un lien profond /?album&planche&region ouvre la Visionneuse pile sur la
    région (applyDeepLink + anti-course plancheGen)."""
    page.goto(_viewer_url(seeded))
    expect(page.locator("#region-id")).to_have_text(f"#{seeded['region']}", timeout=15000)


def test_back_link_depuis_retour_interne(page, seeded):
    """Avec un `retour` interne valide, le bouton « ← Retour » apparaît, pointe
    dessus, et y ramène au clic."""
    page.goto(_viewer_url(seeded, "&retour=%2Frecherche%3Fq%3Dpouvoir"))
    back = page.locator("#back-link")
    expect(back).to_be_visible(timeout=15000)
    assert back.get_attribute("href").endswith("/recherche?q=pouvoir")
    back.click()
    expect(page).to_have_url(re.compile(r"/recherche\?q=pouvoir"))


def test_retour_javascript_est_rejete(page, seeded):
    """`retour=javascript:…` est rejeté par safeRetour → bouton masqué, aucune
    surface d'XSS via le href du ← Retour."""
    page.goto(_viewer_url(seeded, "&retour=javascript:alert(1)"))
    expect(page.locator("#region-id")).to_have_text(f"#{seeded['region']}", timeout=15000)
    expect(page.locator("#back-link")).to_be_hidden()


def test_etat_recherche_restaure_au_chargement(page, seeded):
    """La Recherche restaure sa requête depuis l'URL (reprise d'état au reload)."""
    page.goto(f"{seeded['base']}/recherche?q=bonjour")
    expect(page.locator("#q")).to_have_value("bonjour", timeout=15000)


def test_chaine_retour_deux_niveaux(page, seeded):
    """Round-trip complet : Visionneuse ──← Retour──▶ Recherche ──← Retour──▶
    Exploration, avec l'état de chaque surface restauré (chaîne `retour` à 2 niveaux)."""
    expl = "/exploration?champ=lemme"
    rech = "/recherche?q=x&retour=" + quote(expl, safe="")
    page.goto(_viewer_url(seeded, "&retour=" + quote(rech, safe="")))

    page.locator("#back-link").click()                 # Visionneuse → Recherche
    expect(page).to_have_url(re.compile(r"/recherche"))
    expect(page.locator("#q")).to_have_value("x", timeout=15000)

    page.locator("#back-link").click()                 # Recherche → Exploration
    expect(page).to_have_url(re.compile(r"/exploration"))
    expect(page.locator("#f-champ")).to_have_value("lemme", timeout=15000)
