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


def test_a11y_corpus_materiel(page, seeded):
    """Matériel de numérisation (A6) : détail d'album ouvert (table planches + ligne matériel
    par planche) audité, puis round-trip de la source de numérisation (saisie modale →
    persistée)."""
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.click(".album-row .c-titre")                        # ouvre le détail de l'album
    page.wait_for_selector("#album-detail:not([hidden]) .planches-table", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Corpus/détail matériel :\n{_fmt(viol)}"
    # Round-trip : renseigner la source de numérisation via la modale → persistée.
    page.click("#detail-edit")
    page.wait_for_selector("#m-source-num", timeout=3000)
    page.fill("#m-source-num", "Epson V850, 600 dpi")
    page.click("#m-save")
    page.wait_for_timeout(500)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        alb = c.get("/api/albums").json()
    finally:
        c.close()
    assert any(a.get("source_numerisation") == "Epson V850, 600 dpi" for a in alb)


def test_a11y_visionneuse_undo(page, seeded):
    """Undo (D1) : une action d'annotation (locuteur) posée via l'API est annulée par Ctrl+Z
    dans la Visionneuse (round-trip UI → serveur → rafraîchissement) ; le toast d'annulation
    reste accessible."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        p = c.post("/api/personnages", json={"nom": "Tournesol"}).json()
        c.put(f"/api/regions/{seeded['region']}/locuteur", json={"personnage_id": p["id"]})
        assert c.get(f"/api/regions/{seeded['region']}/locuteur").json()["locuteur"]  # bien posé
    finally:
        c.close()
    page.goto(seeded["base"] + SURFACES["visionneuse"](seeded), wait_until="networkidle")
    page.wait_for_timeout(700)
    page.locator("body").press("Control+z")                  # hors champ de saisie
    page.wait_for_timeout(500)
    viol = _audit(page)
    assert not viol, f"Visionneuse/undo :\n{_fmt(viol)}"
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        assert c.get(f"/api/regions/{seeded['region']}/locuteur").json()["locuteur"] is None
    finally:
        c.close()


def test_a11y_exploration_domaines(page, seeded):
    """Domaines (piste B) : créer un domaine dans la modale Lexique (a11y audité), puis
    rattacher une dimension via le sélecteur → persisté (round-trip UI → serveur)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        c.post("/api/attributs/dimensions", json={"cible": "case", "nom": "valence"})
    finally:
        c.close()
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-lexique")
    page.wait_for_selector("#lex-dom-nom", timeout=3000)
    page.fill("#lex-dom-nom", "émotions")
    page.click("#lex-dom-add")
    page.wait_for_selector("#lexique-modal .lex-domaine", timeout=3000)   # domaine rendu
    viol = _audit(page)
    assert not viol, f"Exploration/domaines :\n{_fmt(viol)}"
    # Rattacher la dimension au domaine via le sélecteur → PATCH .../domaine (déplier d'abord :
    # les champs vivent dans un <details>).
    page.locator('.lex-term:not(.lex-domaine) > summary').first.click()
    page.locator('.lex-term select[data-f="domaine_id"]').first.select_option(label="émotions")
    page.wait_for_timeout(400)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        dims = c.get("/api/attributs/dimensions").json()
    finally:
        c.close()
    assert any(d["nom"] == "valence" and d["domaine"] == "émotions" for d in dims)


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


def test_a11y_visionneuse_alignement(page, seeded):
    """Panneau Personnage → alignement d'autorité (A5) : audite l'a11y de la section ouverte
    (puce-lien + champ) ET vérifie le round-trip (URI saisie dans l'UI → persistée)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        p = c.post("/api/personnages", json={"nom": "Tournesol"}).json()
        c.put(f"/api/regions/{seeded['region']}/locuteur", json={"personnage_id": p["id"]})
    finally:
        c.close()
    page.goto(seeded["base"] + SURFACES["visionneuse"](seeded), wait_until="networkidle")
    page.wait_for_timeout(700)
    page.click('.mode-btn[data-mode="annotation"]')
    page.wait_for_selector("#loc-align-section:not([hidden])", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Visionneuse/alignement :\n{_fmt(viol)}"
    # Round-trip : saisir une URI dans l'UI → alignement persisté (source auto-détectée).
    inp = page.locator("#loc-align-input")
    inp.fill("https://www.wikidata.org/wiki/Q42")
    inp.press("Enter")
    page.wait_for_timeout(400)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30)
    try:
        al = c.get(f"/api/personnages/{p['id']}/alignements").json()
    finally:
        c.close()
    assert any(a["uri"] == "https://www.wikidata.org/wiki/Q42" and a["source"] == "wikidata"
               for a in al)


def test_a11y_exploration_concordance(page, seeded):
    """Concordance (KWIC, B2) : passer en vue Concordance, chercher un lemme du corpus, puis
    auditer l'a11y des DEUX rendus (aligné + liste) et vérifier le deep-link Visionneuse.
    Skippé proprement si le corpus n'a pas de tokens (spaCy absent → concordance vide)."""
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.select_option("#f-vue", "concordance")
    page.fill("#f-lemme", "pouvoir")                 # « POUVOIR ABSOLU » du corpus semé
    try:
        page.wait_for_selector("#kwic .kwic-row", timeout=5000)      # rendu aligné (défaut)
    except Exception:
        pytest.skip("Aucun token de concordance (NLP/spaCy absent) — rendu KWIC non exerçable")
    viol = _audit(page)
    assert not viol, f"Exploration/concordance aligné :\n{_fmt(viol)}"

    page.select_option("#f-kwic-style", "liste")
    page.wait_for_selector("#kwic .kwic-item", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Exploration/concordance liste :\n{_fmt(viol)}"

    href = page.locator("#kwic a").first.get_attribute("href")       # chaque ligne mène à la case
    assert "region=" in href and "planche=" in href


def test_a11y_exploration_croisement(page, seeded):
    """Croisement 2D (ANA-2 / B3) : passer en vue Croisement (POS × type par défaut), auditer
    l'a11y du tableau (en-têtes, heatmap, cellules-boutons), puis vérifier qu'un clic de
    cellule descend aux preuves (bascule en Concordance pré-filtrée). Skippé si aucun token."""
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.select_option("#f-vue", "croisement")
    try:
        page.wait_for_selector("#croise .croise-hit", timeout=5000)      # ≥ 1 cellule cliquable
    except Exception:
        pytest.skip("Aucun token de croisement (NLP/spaCy absent) — tableau non exerçable")
    viol = _audit(page)
    assert not viol, f"Exploration/croisement :\n{_fmt(viol)}"

    page.click("#croise .croise-hit")                                   # drill → preuves
    page.wait_for_function("document.getElementById('f-vue').value === 'concordance'", timeout=3000)
    page.wait_for_selector("#kwic .kwic-row, #kwic .kwic-item", timeout=5000)
