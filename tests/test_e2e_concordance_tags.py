"""Concordance : tags et note sur chaque ligne (ANA-6) — rendu, accessibilité, largeur.

`test_e2e_a11y` audite déjà la concordance, mais son décor ne sème ni tag HÉRITÉ de la
case, ni plus de deux tags sur une ligne. La puce en pointillé et le « +N » passeraient
donc devant axe sans jamais être rendus, et l'audit approuverait ce qu'il n'a pas vu —
le piège que ce dépôt s'écrit à lui-même depuis le décor des moteurs de SANTE-1. Ce
décor-ci les sème EXPRÈS, et chaque test vérifie que ce qu'il audite est bien à l'écran
AVANT de l'auditer.

Le rendu retenu, sur maquette, entre cinq mesures : en aligné, une cinquième colonne de
tags (deux puces au plus, puis « +N ») et un repère 📝 ; en liste, tout — les tags sans
plafond, la note entière.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402
# Un seul instrument axe dans le dépôt : le recopier ferait deux audits qui divergeraient.
from test_e2e_a11y import _audit, _fmt, _theme  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — le périmètre se DÉCLARE (`tests/test_surfaces.py`). Oublié au premier commit de
# ce module, et c'est la suite complète qui l'a dit : un audit qui ne dit pas ce qu'il
# regarde ne permet pas de voir qu'une surface neuve lui échappe.
SURFACES_AUDITEES = ("/exploration",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier n'affiche aucune ligne de concordance : le KWIC ne vit que dans l'Exploration",
    "/recherche": "la Recherche n'a pas de concordance ; ses puces de résultat sont les "
                  "`.r-tag`, que test_e2e_a11y audite déjà sur un résultat tagué",
    "/corpus": "la Bibliothèque n'affiche aucune ligne de concordance",
    "/administration": "l'Administration n'affiche aucune ligne de concordance",
}

NOTE ="Premier ultimatum ; le cadrage serré de la case le souligne."


@pytest.fixture
def corpus_annote(live_server):
    """Une case taguée « colère » ; dedans, une bulle à TROIS tags propres et une note ;
    à côté, une bulle nue. Les deux bulles disent « POUVOIR ABSOLU » : c'est le texte dont
    `test_e2e_a11y` sait déjà que spaCy tire le lemme « pouvoir »."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Concordance annotée"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        case = c.post(f"/api/planches/{pid}/regions",
                      json={"type": "case", "x": 0, "y": 0, "w": 300, "h": 200}).json()["id"]
        annotee = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80,
                               "parent_id": case}).json()["id"]
        nue = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 150, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{case}/annotation", json={"note": "", "tags": ["colère"]})
        for rid in (annotee, nue):
            # Le premier OCR charge spaCy À FROID : même marge que le décor de test_e2e_a11y.
            c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{annotee}/annotation",
              json={"note": NOTE, "tags": ["menace", "refus", "ironie"]})
    finally:
        c.close()
    return live_server


def _concordance(page, base, rendu):
    page.goto(f"{base}/exploration?vue=concordance&lemme=pouvoir&kwic={rendu}",
              wait_until="networkidle")
    sel = "#kwic .kwic-row" if rendu == "aligne" else "#kwic .kwic-item"
    try:
        page.wait_for_selector(sel, timeout=8000)
    except Exception:
        pytest.skip("Aucun token de concordance (spaCy absent) — rendu non exerçable")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_concordance_alignee_montre_tags_et_repere(page, corpus_annote, theme):
    """Aligné : une 5e colonne, deux puces puis « +N », le repère de note — et la colonne a
    une cellule par ligne, la bulle nue comprise, sans quoi la grille se décale."""
    _theme(page, theme)
    _concordance(page, corpus_annote, "aligne")
    assert "kwic-tags" in page.locator("#kwic").get_attribute("class")
    assert page.locator("#kwic .kw-tags").count() == page.locator("#kwic .kwic-row").count() == 2
    # Propres par ordre alphabétique (ironie, menace), puis « +2 » : refus et l'hérité.
    assert page.locator("#kwic .kw-tag:not(.kw-plus)").all_inner_texts() == ["ironie", "menace"]
    assert page.locator("#kwic .kw-plus").inner_text() == "+2"
    # Ce que cache le « +N » est DIT au lecteur d'écran, pas seulement mis en infobulle.
    assert "case · colère" in page.locator("#kwic .kw-cache").text_content()
    assert page.locator("#kwic .kw-note").count() == 1
    viol = _audit(page)
    assert not viol, f"Concordance alignée annotée ({theme}) :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_concordance_en_liste_dit_tout(page, corpus_annote, theme):
    """Liste : tous les tags, l'hérité en pointillé ET préfixé « case », la note entière."""
    _theme(page, theme)
    _concordance(page, corpus_annote, "liste")
    herite = page.locator("#kwic .kw-herite")
    assert herite.count() == 1
    assert herite.inner_text().split() == ["case", "colère"]
    assert page.locator("#kwic .kw-plus").count() == 0            # pas de plafond en liste
    assert page.locator("#kwic .kw-tag").count() == 4
    assert NOTE in page.locator("#kwic .kwic-note").inner_text()
    viol = _audit(page)
    assert not viol, f"Concordance en liste annotée ({theme}) :\n{_fmt(viol)}"


def test_la_colonne_de_tags_ne_fait_pas_deborder_la_page_a_560px(page, corpus_annote):
    """La 5e colonne se prend sur le contexte, pas sur la page : à 560 px, la grille défile
    dans son propre cadre (`overflow-x: auto`) et le corps ne défile jamais de côté."""
    page.set_viewport_size({"width": 560, "height": 900})
    _concordance(page, corpus_annote, "aligne")
    deborde = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert deborde <= 0, f"la page déborde de {deborde} px à 560 px"
