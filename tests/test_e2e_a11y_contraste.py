"""ANN-8 — le CONTRASTE ÉLEVÉ est audité, et pas seulement le thème.

L'audit d'accessibilité du dépôt (`test_e2e_a11y.py`) pose le thème, clair ou sombre, et
jamais le contraste élevé — un troisième état de l'écran, posé par `theme.js`
(`data-contrast="high"`) et qui REDÉFINIT les jetons de couleur. Un mutant qui cachait la
phrase de « Situation » en contraste élevé passait toute la suite (ANN-8, mesuré).

Ce fichier rejoue, en contraste élevé SUR CHACUN DES DEUX THÈMES, ce que l'audit d'origine
regarde au chargement des cinq surfaces, plus les deux états de l'Atelier où une phrase
d'aide n'est visible qu'à condition : une CASE en Annotation (« Situation »), et le profil
d'un personnage. Il réutilise l'instrument et le décor d'origine (`_audit`, `seeded`) au lieu
de les recopier — deux instruments finiraient par ne plus mesurer la même chose.

Deux gardes d'amont, sans lesquelles l'audit approuverait en ne regardant pas : le
contraste élevé est bien POSÉ sur la racine (une clé de stockage mal écrite donnerait un
audit du thème ordinaire), et la phrase attendue est VISIBLE avant l'audit (axe ne juge pas
ce qui est caché — c'est ce qui laissait passer le mutant).
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE  # noqa: E402
from test_e2e_a11y import _audit, _fmt, seeded  # noqa: E402,F401  (fixture réutilisée)

pytestmark = pytest.mark.e2e

# UX-10 — la déclaration de ce que cet audit regarde, confrontée au source par
# `tests/test_surfaces.py`. Les cinq, comme l'audit d'origine.
SURFACES_AUDITEES = {
    "/":            lambda s: f"/?album={s['album']}&planche={s['planche']}&region={s['region']}",
    "/annotation":  lambda s: f"/annotation?album={s['album']}&planche={s['planche']}&region={s['region']}",
    "/recherche":   lambda s: "/recherche?q=pouvoir",
    "/corpus":      lambda s: "/corpus",
    "/exploration": lambda s: "/exploration?champ=lemme",
    "/administration": lambda s: "/administration",
}
SURFACES_HORS_PERIMETRE = {}


def _contraste(page, theme):
    """Thème ET contraste élevé, posés AVANT la navigation : theme.js les lit au chargement."""
    page.add_init_script(
        f"localStorage.setItem('bd-theme','{theme}'); localStorage.setItem('bd-contrast','high')")


def _verifier_pose(page, theme):
    etat = page.evaluate("() => ({c: document.documentElement.dataset.contrast,"
                         " t: document.documentElement.dataset.theme})")
    assert etat == {"c": "high", "t": theme}, (
        f"le contraste élevé n'est pas posé ({etat}) : l'audit mesurerait le thème ordinaire")


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("surface", list(SURFACES_AUDITEES))
def test_a11y_contraste_eleve_chargement(page, seeded, surface, theme):
    _contraste(page, theme)
    page.goto(seeded["base"] + SURFACES_AUDITEES[surface](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    _verifier_pose(page, theme)
    viol = _audit(page)
    assert not viol, f"{surface} [{theme}, contraste élevé] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_contraste_eleve_situation(page, seeded, theme):
    """Une CASE en mode Annotation : le bloc « Situation » et sa phrase d'aide."""
    with httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        case = c.post(f"/api/planches/{seeded['planche']}/regions",
                      json={"type": "case", "x": 150, "y": 150, "w": 200, "h": 200}).json()["id"]
    _contraste(page, theme)
    page.goto(seeded["base"] + SURFACES_AUDITEES["/"]({**seeded, "region": case}),
              wait_until="networkidle")
    page.wait_for_timeout(700)
    _verifier_pose(page, theme)
    page.click('.mode-btn[data-mode="annotation"]')
    page.wait_for_selector("#sit-aide", state="visible", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Atelier/situation [{theme}, contraste élevé] :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_contraste_eleve_profil(page, seeded, theme):
    """Les deux champs de PROFIL d'un personnage et leur phrase d'aide."""
    with httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        perso = c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]
        boite = c.post(f"/api/planches/{seeded['planche']}/regions",
                       json={"type": "personnage", "x": 150, "y": 150, "w": 200,
                             "h": 200}).json()["id"]
        for lien in (f"/api/regions/{seeded['region']}/locuteur",
                     f"/api/regions/{boite}/personnage"):
            assert c.put(lien, json={"personnage_id": perso}).status_code == 200
    _contraste(page, theme)
    for region, aide in ((seeded["region"], "#perso-attr-aide"), (boite, "#perso-profil-aide")):
        page.goto(seeded["base"] + SURFACES_AUDITEES["/"]({**seeded, "region": region}),
                  wait_until="networkidle")
        page.wait_for_timeout(700)
        _verifier_pose(page, theme)
        page.click('.mode-btn[data-mode="annotation"]')
        page.wait_for_selector(aide, state="visible", timeout=5000)
        viol = _audit(page)
        assert not viol, f"Atelier/profil {aide} [{theme}, contraste élevé] :\n{_fmt(viol)}"
