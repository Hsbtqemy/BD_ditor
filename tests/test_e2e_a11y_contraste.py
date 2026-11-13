"""ANN-8 — le CONTRASTE ÉLEVÉ est audité, et pas seulement le thème.

L'audit d'accessibilité du dépôt (`test_e2e_a11y.py`) pose le thème, clair ou sombre, et
jamais le contraste élevé — un troisième état de l'écran, posé par `theme.js`
(`data-contrast="high"`) et qui REDÉFINIT les jetons de couleur. Un mutant qui cachait la
phrase de « Situation » en contraste élevé passait toute la suite (ANN-8, mesuré).

Ce fichier rejoue, en contraste élevé SUR CHACUN DES DEUX THÈMES, ce que l'audit d'origine
regarde au chargement des surfaces. Il réutilise l'instrument et le décor d'origine
(`_audit`, `seeded`) au lieu de les recopier — deux instruments finiraient par ne plus
mesurer la même chose. Les deux états de l'Atelier qu'il auditait aussi — une CASE en
Annotation (« Situation ») et le profil d'un personnage, deux phrases d'aide visibles à
condition — sont partis avec le mode Annotation (ANN-7, le basculement).

Une garde d'amont, sans laquelle l'audit approuverait en ne regardant pas : le contraste
élevé est bien POSÉ sur la racine (une clé de stockage mal écrite donnerait un audit du
thème ordinaire).
"""
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

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
