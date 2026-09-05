"""WCAG 2.1 AA — 1.4.4 « Redimensionnement du texte », versant PRÉFÉRENCE (A11Y-2).

Le dépôt mesurait déjà le reflow (`test_e2e_reflow.py`, 1.4.10) et l'audit axe. Aucun des
deux ne change la taille de police, et c'est un angle mort entier : le zoom navigateur
agrandit les `px` comme le reste, si bien qu'une feuille de style entièrement figée en
pixels passe ces deux gardes sans broncher. Ce que personne ne mesurait, c'est le lecteur
qui règle la police PAR DÉFAUT de son navigateur — le seul réglage que `px` ignore.

**L'instrument est le protocole CCP, pas une feuille injectée.** `Page.setFontSizes`
change la taille initiale du navigateur, exactement comme le réglage de l'utilisateur ;
injecter `html{font-size:24px}` écraserait au contraire la racine de l'application et
mesurerait autre chose. Mesuré le 2026-09-06 sur une page témoin : à 24 px de préférence,
`html { font-size: 81.25% }` calcule 19,5 px, `1rem` suit, `font-size: 12px` ne bouge pas,
et `@media (max-width: 45em)` bascule à 1080 px au lieu de 720.

La RÈGLE est importée de `tools/mesurer_reflow.py` — la même sonde que le reflow, pour la
même raison qu'elle n'y est pas recopiée. Le DÉCOR, lui, est propre à ce module : c'est
huit lignes, et les partager ferait dépendre cette mesure de conditions sans rapport.
"""
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ADMIN, make_png            # noqa: E402
from tools.mesurer_reflow import SONDE          # noqa: E402

pytestmark = pytest.mark.e2e

SURFACES = {
    "visionneuse": lambda d: f"/?album={d['album']}&planche={d['planche']}&region={d['region']}",
    "recherche":   lambda d: "/recherche?q=pouvoir",
    "corpus":      lambda d: "/corpus",
    "exploration": lambda d: "/exploration?champ=lemme",
}

# Reprise à l'identique de `test_e2e_reflow.EXEMPTIONS` : le canevas de la Visionneuse est
# une surface de pan/zoom, exemptée par le 1.4.10 lui-même et gardée là-bas.
EXEMPTIONS = {"canvas"}

CAS = [(1280, 24), (1280, 20), (768, 20), (320, 20)]


@pytest.fixture
def decor(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "Police", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


def _sonder(page, decor, surface, largeur, police):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + SURFACES[surface](decor), wait_until="networkidle")
    page.wait_for_timeout(400)
    return page.evaluate(SONDE)


def _decrire(coupables):
    lignes = []
    for c in coupables:
        ident = (f"#{c['id']}" if c["id"] else (f".{c['cls']}" if c["cls"] else ""))
        lignes.append(f"  <{c['tag']}>{ident} — {c['largeur']} px, dépasse de {c['depasse']} px")
    return "\n".join(lignes)


@pytest.mark.parametrize("largeur,police", CAS)
@pytest.mark.parametrize("surface", list(SURFACES))
def test_la_preference_de_police_ne_perd_pas_de_contenu(page, decor, surface, largeur, police):
    """Police par défaut portée à `police` px : rien ne sort de l'écran sans recours."""
    r = _sonder(page, decor, surface, largeur, police)
    perdus = [c for c in r["coupables"] if not c["cadre"] and c["id"] not in EXEMPTIONS]
    assert not perdus, (
        f"{surface} à {largeur} px avec une police par défaut de {police} px — "
        f"contenu INATTEIGNABLE :\n{_decrire(perdus)}")


def test_la_racine_suit_la_preference(page, decor):
    """Le cœur du chantier, et il se vérifie en un point : si la racine cessait d'être
    proportionnelle — un `font-size` en px sur `html`, la faute d'origine —, tout le
    reste de ce fichier deviendrait vert en ne mesurant plus rien."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": 24, "fixed": 24}})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    racine = page.evaluate("getComputedStyle(document.documentElement).fontSize")
    assert racine == "19.5px", (
        f"racine à {racine} pour une préférence de 24 px — attendu 19.5px (81.25 %). "
        "Une racine figée en px rendrait VACANTES toutes les mesures de ce module.")


def test_le_zoom_ui_compose_avec_la_conversion(page, decor):
    """Le zoom UI (propriété `zoom`, persisté) continue de fonctionner — et il COMPOSE.

    Il agit au RENDU, pas sur les valeurs calculées : mesuré le 2026-09-06, à `zoom: 1.5`
    `getComputedStyle` rend les mêmes 13 px et la même largeur qu'à 100 %, pendant que le
    rectangle, lui, a grandi de moitié. Une garde écrite sur `getComputedStyle` serait
    donc VACANTE — verte quel que soit le zoom. C'est le rectangle qu'on lit.

    Et il scinde ce que la conversion sépare : `zoom` multiplie px et rem indifféremment
    (130 → 195 et 120 → 180 dans la même mesure), là où la préférence de police ne touche
    que les rem. Les deux réglages ne mesurent donc pas la même chose, et c'est pourquoi
    ce module les éprouve tous les deux.
    """
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    haut = "() => Math.round(document.querySelector('#site-nav').getBoundingClientRect().height)"
    avant = page.evaluate(haut)

    page.click(".display-menu > button")
    for _ in range(2):
        page.click('[aria-label="Augmenter le zoom"]')
    page.wait_for_timeout(150)
    apres = page.evaluate(haut)
    assert apres >= round(avant * 1.15), (
        f"la bande 1 fait {apres} px après deux crans de zoom contre {avant} avant — "
        "attendu au moins +15 %. Le zoom UI ne porte plus sur une hauteur en rem.")

    page.reload(wait_until="networkidle")
    etat = page.evaluate("""() => ({
        stocke: localStorage.getItem('bd-zoom'),
        applique: document.documentElement.style.zoom,
        haut: Math.round(document.querySelector('#site-nav').getBoundingClientRect().height),
    })""")
    assert etat["stocke"] == "1.2" and etat["applique"] == "1.2", (
        f"zoom non persisté après rechargement : {etat}")
    assert etat["haut"] == apres, (
        f"la hauteur retombe à {etat['haut']} après rechargement (attendu {apres}) : "
        "le zoom est relu mais ne s'applique plus.")
