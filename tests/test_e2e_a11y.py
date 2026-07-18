"""Audit d'accessibilité automatisé (axe-core) — non-régression des 4 surfaces.

Injecte axe-core (vendu dans `tests/js/vendor/axe.min.js`) dans un vrai Chromium
piloté par Playwright et ÉCHOUE si une violation WCAG 2.1 A/AA **sérieuse ou
critique** apparaît. Couvre le chargement des 4 surfaces en thèmes sombre + clair,
plus des états interactifs (modes Édition/Annotation, modale album) où
l'accessibilité régresse le plus souvent (focus, labels, rôles).

Marqué `e2e` → hors run par défaut (`pytest -m e2e`). Skippé proprement si
Playwright ou le fichier axe vendu sont absents.
"""
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import make_png  # noqa: E402

pytestmark = pytest.mark.e2e

_AXE = Path(__file__).parent / "js" / "vendor" / "axe.min.js"
if not _AXE.exists():
    pytest.skip("axe-core absent (cf. tests/js/vendor/README.md)", allow_module_level=True)
_AXE_SRC = _AXE.read_text(encoding="utf-8")

# axe.run sur le DOM courant, limité aux règles WCAG 2.1 A/AA, ne renvoyant que le
# sérieux/critique (le « moderate/minor » est du raffinement, pas une régression).
_RUN = """async () => {
  const r = await axe.run(document, {runOnly:{type:'tag',
    values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
  return r.violations
    .filter(v => v.impact === 'serious' || v.impact === 'critical')
    .map(v => ({id:v.id, impact:v.impact, help:v.help,
                targets:v.nodes.slice(0,5).map(n => n.target.join(' '))})); }"""


def _audit(page):
    """Injecte axe (idempotent) et renvoie les violations sérieuses/critiques."""
    page.add_script_tag(content=_AXE_SRC)
    return page.evaluate(_RUN)


def _fmt(viol):
    lines = []
    for v in viol:
        lines.append(f"  [{v['impact']}] {v['id']} — {v['help']}")
        lines += [f"      {t}" for t in v["targets"]]
    return "\n".join(lines)


def _theme(page, name):
    """Pose le thème AVANT navigation (theme.js lit localStorage au chargement)."""
    page.add_init_script(f"localStorage.setItem('bd-theme','{name}')")


@pytest.fixture
def seeded(live_server):
    """Album + planche + une bulle (avec OCR + annotation) pour peupler les 4
    surfaces, via l'API sur le serveur live."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30)
    try:
        aid = c.post("/api/albums", json={"titre": "A11y", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"})
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


SURFACES = {
    "visionneuse": lambda s: f"/?album={s['album']}&planche={s['planche']}&region={s['region']}",
    "recherche":   lambda s: "/recherche?q=pouvoir",
    "corpus":      lambda s: "/corpus",
    "exploration": lambda s: "/exploration?champ=lemme",
}


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("surface", list(SURFACES))
def test_a11y_chargement(page, seeded, surface, theme):
    """Chargement de chaque surface : aucune violation sérieuse/critique."""
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES[surface](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    viol = _audit(page)
    assert not viol, f"{surface} [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_visionneuse_modes(page, seeded, theme):
    """États interactifs de la Visionneuse (Édition → poignées, Annotation →
    panneau grammaire)."""
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES["visionneuse"](seeded), wait_until="networkidle")
    page.wait_for_timeout(700)
    for sel, label in (('.mode-btn[data-mode="edition"]', "édition"),
                       ('.mode-btn[data-mode="annotation"]', "annotation")):
        page.click(sel)
        page.wait_for_timeout(300)
        viol = _audit(page)
        assert not viol, f"Visionneuse/{label} [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_pastille_utilisateur(page, seeded, theme):
    """Pastille « utilisateur connecté · déconnexion » (INFRA-1). Elle n'apparaît
    que derrière le proxy d'auth (en-tête `Remote-User`) → on le simule sur toutes
    les requêtes de la page (la pastille est alors rendue par theme.js depuis
    /api/moi), puis on vérifie qu'elle est bien là ET sans violation de contraste."""
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "Camille Roy"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".user-chip .user-who", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Pastille utilisateur [{theme}] :\n{_fmt(viol)}"


def test_a11y_corpus_modale(page, seeded):
    """Modale d'édition d'album (piège à focus + labels de formulaire)."""
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.click('[data-act="edit"]')
    page.wait_for_timeout(300)
    viol = _audit(page)
    assert not viol, f"Corpus/modale :\n{_fmt(viol)}"


def test_a11y_exploration_lexique(page, seeded):
    """Modale « Lexique situé » (A4) : audite l'a11y du panneau ouvert (piège à focus +
    labels de formulaire, badge d'état) ET vérifie le round-trip d'édition (une définition
    saisie dans l'UI est bien persistée via PATCH)."""
    # Peuple le vocabulaire facetté (dimension + valeur) en plus du tag semé.
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        dim = c.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "registre"}).json()
        c.post(f"/api/attributs/dimensions/{dim['id']}/valeurs", json={"valeur": "argot"})
    finally:
        c.close()

    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-lexique")
    page.wait_for_selector("#lexique-modal .lex-term", timeout=3000)
    page.click("#lexique-modal .lex-term > summary")          # déplie le 1er terme
    page.wait_for_timeout(200)
    viol = _audit(page)
    assert not viol, f"Exploration/lexique :\n{_fmt(viol)}"

    # Round-trip : documenter la 1re dimension via l'UI → persisté.
    ta = page.locator('#lexique-modal .lex-term textarea[data-f="definition"]').first
    ta.fill("niveau de langue")
    ta.blur()
    page.wait_for_timeout(400)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        lex = c.get("/api/lexique").json()
    finally:
        c.close()
    defs = ([d["definition"] for d in lex["dimensions"]]
            + [v["definition"] for d in lex["dimensions"] for v in d["valeurs"]])
    assert "niveau de langue" in defs
