"""Tests E2E (navigateur réel via Playwright) des surfaces : round-trip & reprise
d'état, citation (Visionneuse), rôle récit/paratexte (Corpus), recherche → aperçu.

Couvre ce qu'aucun test serveur ne peut atteindre : le COMPORTEMENT front (deep-link,
bouton « ← Retour », chaîne `retour`, durcissement anti-XSS, rendu des surfaces) dans
un vrai Chromium pilotant l'app lancée (fixture `live_server`).

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


# --------------------------------------------------------------------------- #
# Autres surfaces : citation (Visionneuse), rôle (Corpus), recherche → aperçu
# --------------------------------------------------------------------------- #
def test_visionneuse_affiche_la_citation(page, seeded):
    """Sélectionner une région (deep-link) affiche sa citation éditoriale dans le
    panneau de détail (Lot 1 : pl·c)."""
    page.goto(_viewer_url(seeded))
    expect(page.locator("#region-citation")).to_contain_text("pl.1 · c1", timeout=15000)


@pytest.fixture
def seeded_corpus(live_server):
    """Album + DEUX planches récit (pour observer la renumérotation au marquage)."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E corpus"}).json()["id"]
        for _ in range(2):
            c.post(f"/api/albums/{aid}/import",
                   files={"file": ("p.png", make_png(), "image/png")})
    finally:
        c.close()
    return {"base": live_server, "album": aid}


def test_corpus_marquer_paratexte_renumerote(page, seeded_corpus):
    """Sur la Bibliothèque : ouvrir un album, marquer la 1re planche « paratexte »
    → elle sort de la numérotation (Lot 0, corpus.js)."""
    page.goto(f"{seeded_corpus['base']}/corpus")
    page.locator("#albums-body tr td.c-titre").first.click()   # ouvrir l'album
    detail = page.locator("#album-detail")
    expect(detail).to_contain_text("planche 1", timeout=15000)
    expect(detail).to_contain_text("planche 2")                # 2 planches récit au départ
    detail.locator("button[data-role]").first.click()          # 1re planche → paratexte
    expect(detail).to_contain_text("Paratexte", timeout=15000)
    # renumérotation effective : il ne reste qu'UNE planche récit → plus de « planche 2 ».
    expect(detail).not_to_contain_text("planche 2")


@pytest.fixture
def seeded_ocr(live_server):
    """Album + planche + une case contenant une bulle océrisée (texte indexé)."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E ocr"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        cid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 10, "y": 10, "w": 80, "h": 60}).json()["id"]
        bid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 15, "y": 15, "w": 30, "h": 20,
                           "parent_id": cid, "ocr_texte": "BONJOURXYZ"}).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "album": aid, "region": bid}


def test_recherche_resultat_apercu_et_lien_edition(page, seeded_ocr):
    """Recherche plein texte : la bulle océrisée remonte avec sa citation (pl·c·b),
    le clic ouvre l'aperçu, et le lien ✏️ embarque la région + le retour (départ du
    round-trip avec une vraie recherche)."""
    s = seeded_ocr
    page.goto(f"{s['base']}/recherche?q=BONJOURXYZ")
    card = page.locator("#results .result").first
    expect(card).to_be_visible(timeout=15000)
    expect(card.locator(".r-cite")).to_have_text("pl.1 · c1 · b1")
    card.click()                                          # ouvre l'aperçu en place
    expect(page.locator("#preview")).to_be_visible()
    href = page.locator("#preview-edit").get_attribute("href")
    assert f"region={s['region']}" in href and "retour=" in href


def test_visionneuse_menu_import_export(page, live_server):
    """En-tête de la Visionneuse : ShareDocs n'est plus dans « Traitement » (réservé
    aux 3 passes ML) ; il est sous « Import / Export », section Importer, à côté de
    l'import d'images et des exports."""
    page.goto(f"{live_server}/")
    expect(page.locator("#traitement-menu")).not_to_contain_text("ShareDocs")
    page.locator("#btn-donnees").click()                  # ouvrir « Import / Export »
    menu = page.locator("#donnees-menu")
    expect(menu).to_be_visible()
    expect(menu).to_contain_text("Importer des images")
    expect(menu).to_contain_text("Sauvegarde")
    # Groupé SÉMANTIQUEMENT (role=group + aria-label) → lisible aux lecteurs d'écran :
    # ShareDocs sous « Importer », TEI sous « Exporter ».
    expect(menu.locator('[role="group"][aria-label="Importer"]')).to_contain_text("ShareDocs")
    expect(menu.locator('[role="group"][aria-label="Exporter"]')).to_contain_text("TEI")


# --------------------------------------------------------------------------- #
# Navigation transverse unifiée + menus de la Visionneuse (theme.js)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path,label", [
    ("/", "Atelier"),
    ("/corpus", "Bibliothèque"),
    ("/recherche", "Recherche"),
    ("/exploration", "Exploration"),
])
def test_nav_unifiee_injectee_et_surbrillance(page, live_server, path, label):
    """La barre de nav est injectée à l'identique sur les 4 surfaces (4 liens), et la
    surface courante — et elle seule — porte aria-current=page (« vous êtes ici »)."""
    page.goto(f"{live_server}{path}")
    expect(page.locator(".surf-nav a.surf-link")).to_have_count(4, timeout=15000)
    current = page.locator('.surf-nav a[aria-current="page"]')
    expect(current).to_have_count(1)
    expect(current).to_contain_text(label)


def test_menus_visionneuse_un_seul_ouvert_et_echap(page, live_server):
    """Visionneuse : Traitement/Données s'ouvrent au clic, un seul à la fois (ouvrir
    l'un referme l'autre), et Échap referme — cf. setupMenus()."""
    page.goto(f"{live_server}/")
    trait, donnees = page.locator("#traitement-menu"), page.locator("#donnees-menu")
    expect(trait).to_be_hidden(timeout=15000)

    page.locator("#btn-traitement").click()
    expect(trait).to_be_visible()

    page.locator("#btn-donnees").click()          # un seul ouvert à la fois
    expect(trait).to_be_hidden()
    expect(donnees).to_be_visible()

    page.keyboard.press("Escape")                 # Échap referme
    expect(donnees).to_be_hidden()


def test_menu_affichage_ferme_par_defaut(page, live_server):
    """Régression : le panneau « Affichage » (Aa) est masqué au chargement, puis
    s'ouvre / se referme au clic. Garde .display-panel[hidden] — sans lui, le
    display:flex écrasait l'attribut hidden et le menu restait ouvert en permanence."""
    page.goto(f"{live_server}/")
    panel = page.locator(".display-panel")
    expect(panel).to_be_hidden(timeout=15000)
    page.locator(".btn-theme").click()
    expect(panel).to_be_visible()
    page.locator(".btn-theme").click()
    expect(panel).to_be_hidden()


@pytest.mark.parametrize("path", ["/", "/corpus", "/recherche", "/exploration"])
def test_deux_bandes_navigation_au_dessus_des_outils(page, live_server, path):
    """Structure en deux bandes : la bande 1 (#site-nav, navigation) est tout en haut
    et identique partout (4 surfaces) ; la bande 2 (#header, outils de page) est juste
    en dessous, sans chevauchement. Garantit la séparation navigation / outils."""
    page.goto(f"{live_server}{path}")
    nav = page.locator("#site-nav")
    expect(nav).to_be_visible(timeout=15000)
    expect(page.locator("#site-nav .surf-nav a.surf-link")).to_have_count(4)
    nb, hb = nav.bounding_box(), page.locator("#header").bounding_box()
    assert nb["y"] == 0                                 # nav tout en haut
    assert hb["y"] >= nb["y"] + nb["height"] - 1        # outils dessous, pas de chevauchement
