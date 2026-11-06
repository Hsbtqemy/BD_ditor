"""Concordance : la note sur chaque ligne (ANA-6) — rendu, accessibilité, largeur.

Né sous le nom `test_e2e_concordance_tags.py`, quand chaque ligne portait aussi ses tags
(propres, puis hérités de la case, deux puces puis « +N ») ; les tags sont partis avec le
basculement d'ANN-7, la note reste. Le décor la sème EXPRÈS, et chaque test vérifie que ce
qu'il audite est bien à l'écran AVANT de l'auditer — le piège que ce dépôt s'écrit à
lui-même depuis le décor des moteurs de SANTE-1.

Le rendu retenu, sur maquette : en aligné, une cinquième colonne et un repère 📝 ; en
liste, la note entière.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402
# Un seul instrument axe dans le dépôt : le recopier ferait deux audits qui divergeraient.
from test_e2e_a11y import _audit, _fmt, _theme  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — le périmètre se DÉCLARE (`tests/test_surfaces.py`). Oublié au premier commit de
# ce module, et c'est la suite complète qui l'a dit : un audit qui ne dit pas ce qu'il
# regarde ne permet pas de voir qu'une surface neuve lui échappe.
SURFACES_AUDITEES = ("/exploration",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": "la concordance est une vue de l'Exploration seule",
    "/": "l'Atelier n'affiche aucune ligne de concordance : le KWIC ne vit que dans l'Exploration",
    "/recherche": "la Recherche n'a pas de concordance",
    "/corpus": "la Bibliothèque n'affiche aucune ligne de concordance",
    "/administration": "l'Administration n'affiche aucune ligne de concordance",
}

NOTE ="Premier ultimatum ; le cadrage serré de la case le souligne."


@pytest.fixture
def corpus_annote(live_server):
    """Une case ; dedans, une bulle qui porte une note ; à côté, une bulle nue. Les deux
    bulles disent « POUVOIR ABSOLU » : c'est le texte dont `test_e2e_a11y` sait déjà que
    spaCy tire le lemme « pouvoir ». Une troisième bulle, nue elle aussi, dit « SILENCE
    TOTAL » : une concordance dont AUCUNE ligne n'a de note."""
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
        muette = c.post(f"/api/planches/{pid}/regions",
                        json={"type": "bulle", "x": 150, "y": 100, "w": 120, "h": 80}).json()["id"]
        for rid in (annotee, nue):
            # Le premier OCR charge spaCy À FROID : même marge que le décor de test_e2e_a11y.
            c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{muette}", json={"ocr_texte": "SILENCE TOTAL"}, timeout=180)
        c.put(f"/api/regions/{annotee}/annotation", json={"note": NOTE})
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
def test_concordance_alignee_montre_le_repere(page, corpus_annote, theme):
    """Aligné : une 5e colonne et le repère de note — et la colonne a une cellule par
    ligne, la bulle nue comprise, sans quoi la grille se décale."""
    _theme(page, theme)
    _concordance(page, corpus_annote, "aligne")
    assert "kwic-notes" in page.locator("#kwic").get_attribute("class")
    assert page.locator("#kwic .kw-notes").count() == page.locator("#kwic .kwic-row").count() == 2
    assert page.locator("#kwic .kw-note").count() == 1
    viol = _audit(page)
    assert not viol, f"Concordance alignée annotée ({theme}) :\n{_fmt(viol)}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_concordance_en_liste_dit_la_note(page, corpus_annote, theme):
    """Liste : la note entière, sous la réplique."""
    _theme(page, theme)
    _concordance(page, corpus_annote, "liste")
    expect(page.locator("#kwic .kwic-note")).to_have_count(1)
    assert NOTE in page.locator("#kwic .kwic-note").inner_text()
    viol = _audit(page)
    assert not viol, f"Concordance en liste annotée ({theme}) :\n{_fmt(viol)}"


def test_la_colonne_de_note_part_quand_aucune_ligne_n_a_rien_a_y_mettre(page, corpus_annote):
    """La 5e colonne ne se pose que si une ligne AFFICHÉE a une note : sinon elle coûterait
    une gouttière vide à chaque concordance d'un corpus non annoté. Le test part d'un rendu
    qui l'a (« pouvoir »), pour prouver qu'elle se RETIRE, pas seulement qu'elle
    n'apparaît pas — et le préfixe `silen*` exerce le joker au passage."""
    _concordance(page, corpus_annote, "aligne")
    assert "kwic-notes" in page.locator("#kwic").get_attribute("class")
    page.fill("#f-lemme", "silen*")
    page.wait_for_function(
        "() => document.querySelectorAll('#kwic .kwic-row').length === 1", timeout=8000)
    assert "kwic-notes" not in page.locator("#kwic").get_attribute("class")
    assert page.locator("#kwic .kw-notes").count() == 0


def test_un_joker_seul_invite_au_lieu_d_echouer(page, corpus_annote):
    """`*` seul n'est pas un préfixe, et le serveur le refuse (422). Le client doit le lire
    comme un champ vide : l'invite, et non « Erreur : » sous l'ancien KWIC resté à l'écran,
    avec un export armé sur un fichier voué à l'échec."""
    _concordance(page, corpus_annote, "aligne")
    assert page.locator("#btn-export-analyse").is_enabled()
    page.fill("#f-lemme", "*")
    page.wait_for_function(
        "() => document.querySelector('#kwic').textContent.includes('Précisez')", timeout=8000)
    assert page.locator("#kwic .kwic-row").count() == 0
    assert "Erreur" not in page.locator("#dist-info").inner_text()
    assert page.locator("#btn-export-analyse").is_disabled()


def test_la_colonne_de_note_ne_fait_pas_deborder_la_page_a_560px(page, corpus_annote):
    """La 5e colonne se prend sur le contexte, pas sur la page : à 560 px, la grille défile
    dans son propre cadre (`overflow-x: auto`) et le corps ne défile jamais de côté."""
    page.set_viewport_size({"width": 560, "height": 900})
    _concordance(page, corpus_annote, "aligne")
    deborde = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert deborde <= 0, f"la page déborde de {deborde} px à 560 px"
