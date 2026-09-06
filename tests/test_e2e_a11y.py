"""Audit d'accessibilité automatisé (axe-core) — non-régression des 4 surfaces.

Injecte axe-core (vendu dans `tests/js/vendor/axe.min.js`) dans un vrai Chromium
piloté par Playwright et ÉCHOUE si une violation WCAG 2.1 A/AA **sérieuse ou
critique** apparaît. Couvre le chargement des 4 surfaces en thèmes sombre + clair,
plus des états interactifs (modes Édition/Annotation, modale album) où
l'accessibilité régresse le plus souvent (focus, labels, rôles).

Marqué `e2e` → hors run par défaut (`pytest -m e2e`). Skippé proprement si
Playwright ou le fichier axe vendu sont absents.
"""
import json
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

# AUTH-2 : `ADMIN` monte le décor avec les droits qu'il faut (sans effet hors proxy).
from conftest import (ADMIN, SANTE_PROFOND, SANTE_RAPIDE, make_png,  # noqa: E402
                      requires_kumiko)

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
    """Injecte axe (idempotent) et renvoie les violations sérieuses/critiques.

    `evaluate` et NON `add_script_tag` depuis SEC-2 : `add_script_tag` fabrique un
    `<script>` inline dans la page, que la CSP (`script-src 'self'`) bloque net — l'audit
    serait mort le jour où la politique est posée, et pour la bonne raison. `evaluate`
    passe par le protocole de débogage, hors du modèle de sécurité de la page : c'est
    exactement ce qu'on veut d'un instrument de mesure, qu'il n'ait pas besoin qu'on
    desserre ce qu'il vient vérifier.
    """
    page.evaluate(_AXE_SRC)
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
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "A11y", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        # `timeout` généreux ICI et nulle part ailleurs : écrire l'OCR déclenche la
        # réindexation, donc le chargement À FROID de spaCy (~10 s, cf. CLAUDE.md), et le
        # décor est le premier à le payer. Les 30 s du client ont suffi des mois puis
        # lâché le 2026-08-31 sous une machine chargée — une `ReadTimeout` au MONTAGE,
        # qui fait passer les huit paramétrages d'un test pour cassés alors que rien ne
        # l'était. `test_live_coherence.py` avait déjà rencontré le même mur et le
        # contourne pareillement.
        #
        # Cette parade a lâché À SON TOUR le 2026-09-04, sur une course de 1 h 23 au lieu
        # de 14 min — six fois la normale. Relancé seul, le test passe en 20 s. On ne
        # remonte donc PAS le chiffre : ce n'est pas la marge qui manque, c'est la machine
        # qui était mangée par autre chose, et poursuivre une cible mobile allongerait
        # surtout le délai avant de voir un vrai échec.
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
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


@pytest.mark.parametrize("live_server", [True], indirect=True)   # AUTH-1 : proxy déclaré
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_pastille_utilisateur(page, seeded, theme):
    """Pastille « utilisateur connecté · déconnexion » (INFRA-1). Elle n'apparaît
    que derrière le proxy d'auth (en-tête `Remote-User`) → on le simule sur toutes
    les requêtes de la page (la pastille est alors rendue par theme.js depuis
    /api/moi), puis on vérifie qu'elle est bien là ET sans violation de contraste."""
    _theme(page, theme)
    # `Remote-Groups` en plus : sans entrée dans `collection_acces`, Camille ne verrait
    # aucun album (AUTH-2) et l'audit porterait sur une page vide.
    page.set_extra_http_headers({"Remote-User": "Camille Roy",
                                 "Remote-Groups": "bd-admins"})
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


# Les quatre états d'un moteur, forcés (décor partagé, cf. `conftest.SANTE_RAPIDE`).
# Sans lui, une machine de test les rend presque tous « non installé » (gris) : le vert
# et le rouge — les deux seules teintes dont le contraste puisse échouer — ne seraient
# jamais À L'ÉCRAN pendant l'audit, qui passerait au vert sans avoir rien mesuré. Même
# piège que le semis d'AUTH-5.


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_corpus_sante(page, seeded, theme):
    """Panneau des moteurs (SANTE-1) : la modale (piège à focus, titre lié) et les quatre
    états d'un moteur, éprouvés dans les deux thèmes.

    Le contraste est l'enjeu : « en panne » est du PETIT texte coloré, là où l'accent
    rouge plein échoue le 4.5:1 — d'où `--ink-red` et un `--accent-green` assombri en
    thème clair. Un audit qui n'aurait sous les yeux que des lignes grises approuverait
    une palette qu'il n'a pas regardée."""
    page.route("**/api/sante*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(SANTE_PROFOND if "profond=1" in r.request.url
                        else SANTE_RAPIDE)))
    _theme(page, theme)
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.click("#btn-sante")
    page.wait_for_selector("#sante-modal:not([hidden]) .sante-ligne", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Corpus/moteurs [{theme}] :\n{_fmt(viol)}"

    page.click("#sante-eprouver")
    page.wait_for_selector(".sante-panne", timeout=5000)
    # Les quatre états sont bien à l'écran : sinon l'audit qui suit ne mesure rien.
    for classe in (".sante-ok", ".sante-panne", ".sante-absent"):
        assert page.locator(classe).count(), f"état {classe} absent du rendu"
    viol = _audit(page)
    assert not viol, f"Corpus/moteurs éprouvés [{theme}] :\n{_fmt(viol)}"

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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        alb = c.get("/api/albums").json()
    finally:
        c.close()
    assert any(a.get("source_numerisation") == "Epson V850, 600 dpi" for a in alb)


def test_a11y_corpus_relecture(page, seeded):
    """Relecture par planche (ANN-4 / B5) : ouvrir le détail d'album, auditer la colonne
    (pastille de statut + sélecteur d'override), puis forcer « faite » → override persisté."""
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.click(".album-row .c-titre")                        # ouvre le détail
    page.wait_for_selector("#album-detail:not([hidden]) .rel-sel", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Corpus/relecture :\n{_fmt(viol)}"
    # Round-trip : forcer le statut via le sélecteur → override persisté.
    page.select_option(".rel-sel", "faite")
    page.wait_for_timeout(500)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        planches = c.get(f"/api/albums/{seeded['album']}/planches").json()
    finally:
        c.close()
    st = planches[0]["relecture_statut"]
    assert st["force"] is True and st["statut"] == "faite"


def test_deep_link_introuvable_diagnostique(page, seeded):
    """F5 : un deep-link vers une planche/région inexistante AFFICHE un diagnostic (toast) au
    lieu d'échouer en silence."""
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche=999999",
              wait_until="networkidle")
    page.wait_for_selector("#toasts .toast", timeout=4000)
    assert "introuvable" in page.locator("#toasts .toast").first.inner_text().lower()


def test_a11y_visionneuse_undo(page, seeded):
    """Undo (D1) : une action d'annotation (locuteur) posée via l'API est annulée par Ctrl+Z
    dans la Visionneuse (round-trip UI → serveur → rafraîchissement) ; le toast d'annulation
    reste accessible."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        assert c.get(f"/api/regions/{seeded['region']}/locuteur").json()["locuteur"] is None
    finally:
        c.close()


def test_a11y_exploration_domaines(page, seeded):
    """Domaines (piste B) : créer un domaine dans la modale Lexique (a11y audité), puis
    rattacher une dimension via le sélecteur → persisté (round-trip UI → serveur)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
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


def test_a11y_exploration_accord(page, seeded):
    """Accord modèle↔humain (NLP-1 / B4) : ouvrir la modale, auditer son a11y (piège à focus,
    table, barres). Si le corpus a des tokens (spaCy), on valide un token d'abord pour exercer
    aussi le rendu du tableau (sinon on audite l'état « aucun token relu »)."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        toks = c.get(f"/api/regions/{seeded['region']}/tokens").json()
        if toks:                                     # valider le 1er token → 1 token relu
            c.put(f"/api/regions/{seeded['region']}/tokens/{toks[0]['ordre']}",
                  json={"etat": "valide"})
    finally:
        c.close()
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-accord")
    page.wait_for_selector("#accord-modal:not([hidden]) #accord-body", timeout=3000)
    page.wait_for_timeout(300)                       # laisse le fetch + rendu se faire
    viol = _audit(page)
    assert not viol, f"Exploration/accord :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # attribution alice/bob
def test_a11y_exploration_accord_inter(page, seeded):
    """Accord inter-annotateurs (ANN-5) : créer une divergence, puis auditer la modale
    PEUPLÉE — table d'accord et liste de divergences.

    Il auditait une modale qu'il croyait avoir remplie, sans jamais vérifier qu'elle
    l'était. Le décor était correct — le marqueur `live_server(True)` est là, donc alice et
    bob existent vraiment — mais RIEN ne le contrôlait : sa fragilité se démontre en
    retirant `BD_AUTH_PROXY` du sous-processus, auquel cas les deux auteurs deviennent NULL,
    aucune divergence n'est créée, la modale affiche « Aucune re-touche entre auteurs
    distincts »... et le test passe. Mesuré le 2026-08-27 (constat T8). Axe ne juge que
    l'accessibilité, et une modale vide est parfaitement accessible.

    Le défaut n'est donc pas dans le décor mais dans ce que le test AFFIRME : il ne dit rien
    de son propre montage, si bien que n'importe quelle régression d'authentification, de
    route ou de contrat de token le viderait sans le faire échouer. C'est la vacuité par
    l'amont, plus discrète que l'assertion molle : elle ne s'attrape pas en lisant
    l'assertion, seulement en se demandant ce qui la précède.

    Trois gardes désormais, et elles sont l'essentiel : la divergence est CONFIRMÉE côté
    serveur avant qu'on regarde l'écran, les deux auteurs sont NOMMÉS (ce que la seule
    présence de re-touches ne garantit pas), et l'écran doit montrer la TABLE — que le rendu
    ne produit que si `retouches` est non nul. Enfin, l'absence de tokens devient un skip
    EXPLICITE : ne rien pouvoir mesurer et mesurer zéro ne sont pas le même résultat.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        toks = c.get(f"/api/regions/{seeded['region']}/tokens").json()
        if not toks:
            pytest.skip("aucun token (spaCy absent) : sans divergence constructible, "
                        "auditer la modale ne mesurerait que son état vide")
        o = toks[0]["ordre"]
        for qui, pos in (("alice", "NOUN"), ("bob", "VERB")):
            c.put(f"/api/regions/{seeded['region']}/tokens/{o}",
                  json={"etat": "corrige", "pos": pos},
                  headers={"Remote-User": qui, "Remote-Groups": "bd-admins"})
        rapport = c.get("/api/analyse/accord-inter").json()
    finally:
        c.close()
    assert rapport.get("retouches"), (
        f"aucune re-touche inter-auteurs construite : {rapport} — le décor a échoué, "
        "et auditer la modale ne dirait rien de ce que ce test prétend couvrir")
    assert set(rapport["auteurs"]) == {"alice", "bob"}, rapport["auteurs"]

    page.set_extra_http_headers(ADMIN)          # le serveur exige une identité
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-accord-inter")
    # `.accord-table` et non `#accord-inter-body` : le corps existe TOUJOURS, la table
    # seulement quand le rapport porte des re-touches. C'est là toute la différence.
    page.wait_for_selector("#accord-inter-modal:not([hidden]) .accord-table", timeout=5000)
    viol = _audit(page)
    assert not viol, f"Exploration/accord-inter :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("surface", ["/corpus", "/", "/recherche", "/exploration"])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_portee_vide(page, seeded, theme, surface):
    """Bandeau « aucune collection ne vous est ouverte » (AUTH-2).

    Il n'apparaît que dans un état qu'aucun autre test ne visite : derrière le proxy, avec
    une identité à qui rien n'a été accordé. Sans ce test, le seul écran que verra une
    personne mal configurée serait aussi le seul que l'audit n'aurait jamais regardé.

    Les QUATRE surfaces : `theme.js` l'injecte en tête de `<main>` partout, et la
    Visionneuse est celle dont la mise en page souffre le plus d'un bloc inattendu.
    """
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "sans-droits"})   # aucun groupe
    page.goto(seeded["base"] + surface, wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Portée vide [{surface} · {theme}] :\n{_fmt(viol)}"


def _deplier_bandeau(page):
    """Ouvre le bandeau de portée vide s'il est replié, et rend son `<details>`.

    Depuis le repli, tout ce qui n'est pas le titre vit derrière un `<details>` fermé,
    donc INVISIBLE : `wait_for()` et `inner_text()` de Playwright attendent la visibilité,
    pas la présence. Les tests qui parlent du CONTENU (référent, groupes) l'ouvrent donc
    d'abord — ce qu'une personne fait aussi. Celui qui parle du PLI lui-même ne l'appelle
    pas : c'est son objet.
    """
    pli = page.locator(".portee-vide details")
    pli.wait_for(timeout=3000)
    if not pli.evaluate("e => e.open"):
        page.click(".portee-vide summary")
    # On attend l'ÉTAT, pas le geste. Sans cette ligne le helper cliquait et repartait
    # sans jamais vérifier que le clic avait porté : un clic avalé — le bandeau naît
    # après la réponse d'`/api/moi`, donc pendant un rendu — laissait le test suivant
    # attendre trois secondes une visibilité qui ne viendrait pas, puis échouer en
    # accusant le RÉFÉRENT d'être absent alors que le pli était resté fermé. Cinq
    # tests passent par ici : un helper sans postcondition déplace l'erreur au lieu
    # de la dire, et c'est le plus cher des silences.
    page.wait_for_function(
        "() => { const d = document.querySelector('.portee-vide details');"
        "        return d && d.open; }", timeout=3000)
    return pli


def _geo(page, sel):
    """Rectangle rendu d'un élément, en pixels CSS entiers. `None` s'il n'existe pas."""
    return page.evaluate(
        """s => { const e = document.querySelector(s); if (!e) return null;
                  const r = e.getBoundingClientRect();
                  return {x: Math.round(r.x), y: Math.round(r.y),
                          w: Math.round(r.width), h: Math.round(r.height)}; }""", sel)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("largeur", [1440, 1024, 820])
def test_portee_vide_ne_decale_pas_la_grille_de_la_visionneuse(page, seeded, largeur):
    """Le bandeau de portée vide s'injecte en tête de `<main>` sur les QUATRE surfaces.
    Sur trois, `<main>` est un bloc qui défile et il s'y pose sans rien déranger. Sur la
    Visionneuse, `<main id="body">` est une grille de TROIS colonnes taillées pour TROIS
    panneaux : le bandeau y devient un QUATRIÈME item auto-placé, prend la colonne de la
    navigation, et décale tout le reste d'un cran — la navigation dans la colonne du
    canevas, le canevas dans les 300 px du panneau, le panneau rejeté à la rangée
    suivante.

    `test_a11y_portee_vide` visite pourtant cet écran, et sa docstring annonce que « la
    Visionneuse est celle dont la mise en page souffre le plus d'un bloc inattendu ». Il
    ne l'a jamais vu : axe-core audite l'ACCESSIBILITÉ, et une grille décalée reste
    parfaitement accessible. La garde ne s'est pas trompée, elle regardait ailleurs — et
    c'est la forme d'échec la plus coûteuse, puisqu'elle rend un vert sincère.

    Trois largeurs, une par régime de colonnes (3 · 2 · 1). Le défaut EMPIRE en
    descendant : sous 900 px il ne reste qu'un bandeau et un canevas, qui se partagent
    alors la hauteur en deux — `align-content: stretch` répartit le reste également
    entre deux rangées `auto`, et le bandeau grossit d'autant.
    """
    page.set_viewport_size({"width": largeur, "height": 900})
    page.set_extra_http_headers({"Remote-User": "sans-droits"})   # aucun groupe
    page.goto(seeded["base"] + "/", wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)

    body = _geo(page, "#body")
    bandeau = _geo(page, ".portee-vide")
    canevas = _geo(page, "#viewer")
    etat = f"[{largeur} px] body={body} bandeau={bandeau} canevas={canevas}"

    # 1. Le bandeau tient une RANGÉE et non une colonne : il occupe toute la largeur.
    assert abs(bandeau["w"] - body["w"]) <= 1, \
        "le bandeau occupe une colonne au lieu de la rangée — " + etat

    # 2. Et il se dimensionne sur son CONTENU : le canevas garde le gros de la hauteur.
    #    C'est ce que la colonne unique perd en premier, et le seul contrôle qui morde
    #    à 820 px, où la largeur est déjà pleine des deux côtés du correctif.
    #    Cette assertion a d'abord été seule, et elle mordait — le bandeau faisait alors
    #    212 px. Le repli l'a ramené à 44, et elle a cessé de voir : sans la règle des
    #    rangées, `align-content: stretch` répartit le reste également entre deux rangées
    #    `auto`. Mesuré sous mutation le 2026-09-06 : à 1440 px le bandeau monte à 339 et
    #    le canevas à 429, si bien que « le canevas est plus haut » reste VRAI et que la
    #    garde approuve le défaut entier. À 1024 et 820 px elle l'attrapait encore (382
    #    contre 386) — l'angle mort n'était donc pas total, il était pile sur la largeur
    #    de bureau. Une garde qui ne voit plus qu'aux tailles où l'on ne travaille pas
    #    est le mode d'échec d'ARCH-2, et il aura suffi d'ALLÉGER l'écran pour l'ouvrir.
    #
    #    On mesure donc l'ÉTIREMENT lui-même. `<details>` est en `display: block` : sa
    #    hauteur suit son contenu et ne s'étire jamais. L'écart entre l'enveloppe et lui
    #    vaut exactement le rembourrage (.9231rem × 2 = 24 px) tant que la grille ne tire
    #    pas dessus, et vaut 321 à 368 px dès qu'elle le fait — un ordre de grandeur au-
    #    dessus du seuil, aux TROIS largeurs. Vrai que le bandeau soit replié ou ouvert,
    #    ce que l'ancienne formulation ne pouvait pas être.
    pli = _geo(page, ".portee-vide > details")
    assert bandeau["h"] - pli["h"] <= 30, (
        f"le bandeau est ÉTIRÉ par la grille au lieu de suivre son contenu — pli={pli} "
        + etat)
    assert canevas["h"] > bandeau["h"], \
        "le bandeau prend autant de hauteur que le canevas — " + etat

    # 3. Là où les trois colonnes existent, elles sont dans le bon ordre : les trois
    #    panneaux sur UNE rangée, et le canevas tenant la colonne souple.
    #
    #    Le seuil qui les fait tomber en tiroirs vit dans `style.css` et NULLE PART
    #    ailleurs — c'est écrit en toutes lettres dans le bloc des tiroirs, et un nombre
    #    recopié ici en ferait une seconde vérité à tenir d'accord. On ne le recopie donc
    #    pas : on DEMANDE à la page si la navigation est encore une colonne. Sa règle de
    #    base ne déclare aucun `position` ; le seuil la passe en `absolute`.
    if page.evaluate("() => getComputedStyle("
                     "document.querySelector('#sidebar')).position === 'static'"):
        nav, panneau = _geo(page, "#sidebar"), _geo(page, "#panel")
        assert nav["y"] == canevas["y"] == panneau["y"], \
            f"les panneaux ne sont pas sur la même rangée — nav={nav} panneau={panneau} {etat}"
        assert canevas["w"] > nav["w"] + panneau["w"], \
            f"le canevas n'a pas la colonne souple — nav={nav} panneau={panneau} {etat}"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_a11y_proxy_sans_identite(page, seeded):
    """L'autre portée vide : l'application se croit derrière un proxy d'auth et ne reçoit
    AUCUN en-tête. Elle ferme tout, délibérément — mais sans message, l'écran est celui
    d'un corpus vide et l'opérateur cherche une panne de base de données.

    Aucune pastille utilisateur ici (il n'y a pas d'identité), donc c'est bien le bandeau
    seul qui porte l'explication.
    """
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")   # sans en-têtes
    page.wait_for_selector(".portee-vide", timeout=3000)
    assert page.locator(".user-chip").count() == 0
    # Le titre est dans le `<summary>` depuis le repli. Le sélecteur reste précis pour
    # la même raison : le bandeau porte un second `strong` depuis AUTH-4, le nom du
    # référent au milieu d'une phrase. Ce cas-ci est le SEUL ouvert d'office, donc son
    # titre se lit sans rien déplier.
    assert "ne vous reconnaît pas" in page.locator(".portee-vide summary > strong").inner_text()
    viol = _audit(page)
    assert not viol, f"Proxy sans identité :\n{_fmt(viol)}"


# --------------------------------------------------------------------------- #
# Collections (AUTH-3) — l'écran qui remplace `tools/gerer_collections.py`
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_corpus_collections(page, seeded, theme):
    """Écran Collections : créer, déplier, accorder un accès — audité à chaque étape.

    C'est le seul écran du dépôt où l'on décide QUI entre. Une régression d'accessibilité
    y coûterait plus cher qu'ailleurs : on n'administre pas des droits à l'aveugle.
    """
    _theme(page, theme)
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-collections")
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Collections [{theme}] :\n{_fmt(viol)}"

    page.fill("#col-nom", "Corpus colonial")
    page.click("#col-add")
    page.wait_for_function(
        "() => [...document.querySelectorAll('#col-body .col-nom')]"
        "        .some(e => e.textContent === 'Corpus colonial')", timeout=3000)

    # Déplier la collection créée → la liste des accès et le formulaire apparaissent.
    page.locator("#col-body .col-item", has_text="Corpus colonial").locator(
        "summary").click()
    page.wait_for_selector("#col-body .col-principal", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Collections/accès [{theme}] :\n{_fmt(viol)}"

    page.locator(".col-principal").first.fill("bd-lettrage")
    page.locator(".col-genre").first.select_option("groupe")
    page.locator(".col-niveau-neuf").first.select_option("ecriture")
    page.locator("[data-accorder]").first.click()
    page.wait_for_timeout(500)

    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ADMIN)
    try:
        cols = c.get("/api/collections").json()
        cid = next(x["id"] for x in cols if x["nom"] == "Corpus colonial")
        acces = c.get(f"/api/collections/{cid}/acces").json()
    finally:
        c.close()
    assert ("bd-lettrage", "groupe", "ecriture") in {
        (a["principal"], a["genre"], a["niveau"]) for a in acces}


def test_corpus_appartenance_album(page, seeded):
    """L'appartenance N-N depuis l'UI — la case qu'AUTH-2 avait laissée ouverte, faute de
    propriétaire pour dire qui a le droit de déplacer quoi.

    Le refus de sortir de la DERNIÈRE collection doit être RENDU : c'est un 409 qui nomme
    un état interdit, pas un droit manquant, et l'avaler ferait croire à un bug.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ADMIN)
    try:
        autre = c.post("/api/collections", json={"nom": "Représentations"}).json()["id"]
    finally:
        c.close()
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.locator('#albums-body tr [data-act="edit"]').first.click()
    page.wait_for_selector("#m-appartenance:not([hidden])", timeout=3000)
    # Une seule collection au départ : la sortir doit être refusé, et le dire.
    page.locator("#m-appartenance-liste [data-sortir]").first.click()
    page.wait_for_function(
        "() => document.querySelector('#m-appartenance-msg')"
        "        .textContent.includes('dernière collection')", timeout=3000)
    assert "erreur" in page.locator("#m-appartenance-msg").get_attribute("class")

    # Rangé ailleurs, l'album vit dans deux collections — et la sortie redevient possible.
    page.select_option("#m-appartenance-cible", str(autre))
    page.click("#m-appartenance-add")
    page.wait_for_function(
        "() => document.querySelectorAll('#m-appartenance-liste li').length === 2",
        timeout=3000)
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ADMIN)
    try:
        vues = c.get(f"/api/albums/{seeded['album']}/collections").json()
    finally:
        c.close()
    assert autre in {x["id"] for x in vues} and len(vues) == 2


# --------------------------------------------------------------------------- #
# Figures citables (DROIT-1) — citer se décide sur la région
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_figure_citable(page, seeded, theme):
    """Le panier de figures et sa modale, audités.

    Le bouton d'export ne s'affiche QUE quand le panier est garni : un bouton permanent
    sur un panier vide promet une action qui n'aboutit pas.
    """
    _theme(page, theme)
    page.goto(seeded["base"] + SURFACES["visionneuse"](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.locator("#btn-fig-open").is_hidden()      # panier vide → pas de promesse
    page.click("#btn-fig-add")
    page.wait_for_selector("#btn-fig-open:not([hidden])", timeout=3000)
    assert "1" in page.locator("#btn-fig-open").inner_text()
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Figures [{theme}] :\n{_fmt(viol)}"
    # Vider REMASQUE le bouton. Sans ce second temps, le test ne lirait que
    # l'attribut `hidden` du HTML statique — il passerait même si le code
    # cessait de le piloter.
    page.click("#fig-vider")
    # `state="hidden"` : par défaut `wait_for_selector` attend un élément VISIBLE, donc
    # attendre un `[hidden]` expire toujours — que le code marche ou non.
    page.wait_for_selector("#btn-fig-open", state="hidden", timeout=3000)


def test_les_mentions_viennent_du_serveur(page, seeded):
    """La liste des mentions n'est pas recopiée dans le JS : deux listes qui divergent
    produiraient une légende amputée sans rien signaler. L'écran doit donc afficher
    exactement ce que `GET /api/figure/champs` annonce."""
    attendus = httpx.get(seeded["base"] + "/api/figure/champs", trust_env=False,
                         timeout=30).json()
    page.goto(seeded["base"] + SURFACES["visionneuse"](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    page.click("#btn-fig-add")
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)
    values = page.locator("#fig-champs input").evaluate_all(
        "els => els.map(e => e.value)")
    assert values == [c["champ"] for c in attendus]


def test_export_de_figure_telecharge_un_zip(page, seeded):
    """Le bout de la chaîne : le zip arrive vraiment dans le navigateur, et il porte le
    nom composé par le SERVEUR — le recomposer côté client ferait diverger deux
    horodatages pour un seul export."""
    page.goto(seeded["base"] + SURFACES["visionneuse"](seeded), wait_until="networkidle")
    page.wait_for_timeout(600)
    page.click("#btn-fig-add")
    page.click("#btn-fig-open")
    page.wait_for_selector("#fig-champs label", timeout=3000)
    with page.expect_download(timeout=10000) as dl:
        page.click("#fig-export")
    fichier = dl.value
    assert fichier.suggested_filename.startswith("figures_")
    assert fichier.suggested_filename.endswith(".zip")


# --------------------------------------------------------------------------- #
# DROIT-1 — l'embargo cesse d'être muet sur l'écran Collections
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_collections_embargo_echu(page, seeded, theme):
    """L'application ne lève jamais un embargo toute seule, mais elle cesse de se taire :
    un embargo échu que personne ne remarque garde un corpus fermé par INERTIE.

    Audité dans les deux thèmes parce que la pastille est du PETIT TEXTE coloré — la
    catégorie qui échoue le 4.5:1 quand on y met un accent brut au lieu d'un token d'encre.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ADMIN)
    try:
        cid = c.post("/api/collections", json={"nom": "Fonds sous embargo"}).json()["id"]
        r = c.patch(f"/api/collections/{cid}",
                    json={"statut_diffusion": "embargo", "date_embargo": "2020-01-01"})
        assert r.status_code == 200, r.text
    finally:
        c.close()

    _theme(page, theme)
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-collections")
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    # La pastille est RENDUE, et son libellé porte le sens — pas la seule couleur.
    pastille = page.locator("#col-body .col-item", has_text="Fonds sous embargo").locator(
        ".col-embargo")
    pastille.wait_for(timeout=3000)
    assert "échu" in pastille.inner_text().lower()
    assert "2020-01-01" in (pastille.get_attribute("title") or "")

    viol = _audit(page)
    assert not viol, f"Collections/embargo [{theme}] :\n{_fmt(viol)}"


# --------------------------------------------------------------------------- #
# AUTH-4 — nommer l'administrateur plutôt que le taire
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_portee_vide_nomme_un_destinataire(page, seeded, theme):
    """Le bandeau envoyait une personne BLOQUÉE « demander un accès à un administrateur »
    sans lui dire à qui. Or elle ne lit AUCUNE collection, donc aucun référent de
    collection : seul un référent d'instance peut l'aider. C'est le seul endroit où ce
    chantier sert quelqu'un que quelque chose empêche."""
    _theme(page, theme)
    page.set_extra_http_headers({"Remote-User": "sans-droits"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)          # « sans-droits » n'est pas une panne → replié
    ligne = page.locator(".portee-vide-referent")
    ligne.wait_for(timeout=3000)
    assert "Ana Ruiz" in ligne.inner_text()
    # Le contact est CLIQUABLE : une adresse qu'il faut recopier à la main n'en est pas
    # tout à fait une.
    assert ligne.locator('a[href="mailto:ana@labo.fr"]').count() == 1
    # La réserve est dite, pas laissée à découvrir — raccourcie le 2026-09-06 d'une
    # phrase à une parenthèse, parce qu'elle s'adressait à un lecteur qui n'en peut rien.
    # Elle n'a pas DISPARU : le référent vient de la configuration, l'application ne sait
    # pas s'il est encore là, et taire cette limite serait pire que la dire brièvement.
    assert "déclaré à la configuration" in ligne.inner_text()
    viol = _audit(page)
    assert not viol, f"Portée vide + référent [{theme}] :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_panneau_des_acces_declare_les_administrateurs(page, seeded):
    """`_acces_de()` ne lit que `collection_acces`, où un administrateur ne figure sur
    AUCUNE ligne — sa portée court-circuite la table en amont. La liste affichait donc
    trois noms là où quatre personnes lisent, sur un écran qui protège soigneusement cette
    liste au motif qu'elle parle de personnes. Défaut de DÉCLARATION, pas d'autorisation."""
    page.set_extra_http_headers({"Remote-User": "alice", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-collections")
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    page.locator("#col-body .col-item").first.locator("summary").click()
    note = page.locator(".col-note-admin")
    note.wait_for(timeout=3000)
    txt = note.inner_text()
    assert "bd-admins" in txt and "toute" in txt


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_referent_d_une_collection_s_enregistre(page, seeded):
    """Une ADRESSE, pas un droit : la nommer n'accorde rien. DÉSIGNER reste au
    propriétaire — choisir l'interlocuteur d'un espace engage l'espace entier."""
    page.set_extra_http_headers({"Remote-User": "alice", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-collections")
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    page.locator("#col-body .col-item").first.locator("summary").click()
    page.wait_for_selector(".col-ref-nom", timeout=3000)
    page.locator(".col-ref-nom").first.fill("Ana Ruiz")
    page.locator(".col-ref-contact").first.fill("ana@labo.fr")
    page.locator("[data-referent]").first.click()
    page.wait_for_timeout(600)

    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers={"Remote-User": "alice", "Remote-Groups": "bd-admins"})
    try:
        cols = c.get("/api/collections").json()
    finally:
        c.close()
    assert any(x["referent_nom"] == "Ana Ruiz"
               and x["referent_contact"] == "ana@labo.fr" for x in cols)


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_participant_non_proprietaire_voit_le_referent(page, seeded):
    """Le premier jet mettait le référent ET la déclaration d'administration sous le
    `return` du panneau réservé au propriétaire — donc visibles de la seule personne qui
    les avait écrits. Or c'est le participant SANS pouvoir qui a besoin de savoir à qui
    écrire, et qu'un administrateur d'instance lit ici sans y figurer. Désigner engage la
    collection et reste au propriétaire ; lire est le geste de quelqu'un qui a une
    question."""
    admin = {"Remote-User": "alice", "Remote-Groups": "bd-admins"}
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=admin)
    try:
        cid = c.get("/api/collections").json()[0]["id"]
        assert c.patch(f"/api/collections/{cid}",
                       json={"referent_nom": "Ana Ruiz",
                             "referent_contact": "ana@labo.fr"}).status_code == 200
        assert c.put(f"/api/collections/{cid}/acces",
                      json={"principal": "bob", "genre": "utilisateur",
                            "niveau": "lecture"}).status_code in (200, 201)
    finally:
        c.close()

    # bob lit la collection sans la posséder : `administrable` est faux pour lui.
    page.set_extra_http_headers({"Remote-User": "bob", "Remote-Groups": "chercheurs"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-collections")
    page.wait_for_selector("#col-body .col-item", timeout=3000)
    page.locator("#col-body .col-item").first.locator("summary").click()

    # Il ne voit PAS la liste des accès (c'est une donnée sur des personnes)...
    page.wait_for_selector(".col-note-referent", timeout=3000)
    # `#col-body` : `.acces-liste` est aussi la classe d'un `<ul>` STATIQUE du gabarit
    # (`corpus.html:82`, la liste d'appartenance). Non porté, ce sélecteur comptait 1 quoi
    # qu'il arrive — une assertion qui échoue pour la mauvaise raison en vaut une qui
    # passe pour la mauvaise raison.
    assert page.locator("#col-body .acces-liste").count() == 0
    assert page.locator(".col-ref-nom").count() == 0, "il ne doit pas pouvoir DÉSIGNER"
    # ...mais il sait à qui écrire, et que quelqu'un d'autre lit ici.
    assert "Ana Ruiz" in page.locator(".col-note-referent").inner_text()
    assert "bd-admins" in page.locator(".col-note-admin").inner_text()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_verrou_dit_par_qui(page, seeded):
    """`planches.verrou_par` est consigné depuis la v22 et aucun écran ne le montrait :
    on lisait « verrouillée le … » sans savoir à qui demander la levée — la seule chose
    qu'on ait besoin de savoir devant un verrou purement informatif.

    « par vous » se décide sur le LOGIN et non sur le nom affiché : deux personnes peuvent
    porter le même nom, et se voir attribuer le verrou d'un homonyme serait pire que de ne
    rien dire."""
    alice = {"Remote-User": "alice", "Remote-Name": "Alice Renard",
             "Remote-Groups": "bd-admins"}
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=alice)
    try:
        c.get("/api/moi")                       # alimente le miroir `utilisateur`
        pl = c.get(f"/api/albums/{seeded['album']}/planches").json()[0]
        assert c.patch(f"/api/planches/{pl['id']}/verrou",
                       json={"verrouillee": True}).status_code == 200
    finally:
        c.close()

    # Bob voit le NOM d'alice, pas son login.
    page.set_extra_http_headers({"Remote-User": "bob", "Remote-Groups": "bd-admins"})
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche={seeded['planche']}",
              wait_until="networkidle")
    page.wait_for_timeout(600)
    titre = page.locator("#lock-toggle").get_attribute("title")
    assert "Alice Renard" in titre, titre
    assert "alice" not in page.locator("#lock-toggle").inner_text()

    # Alice, elle, lit « par vous » — la comparaison porte sur le login.
    page.set_extra_http_headers(alice)
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche={seeded['planche']}",
              wait_until="networkidle")
    page.wait_for_timeout(600)
    assert "par vous" in page.locator("#lock-toggle").inner_text()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_bandeau_ne_se_deplie_d_office_que_pour_une_vraie_panne(page, seeded):
    """Le bandeau faisait 212 px sur les quatre surfaces, quel que soit l'état décrit.

    Il se replie désormais derrière son titre — sauf dans le seul cas qu'on SACHE être
    une panne : aucune identité ne parvient alors que `BD_AUTH_PROXY` est déclaré. Là il
    n'existe pas de lecture bénigne, et celui qui doit réparer le `forward_auth` ne sait
    pas qu'il faudrait déplier.

    Les deux autres restent repliés, « aucun groupe » COMPRIS — et ce cas-là est le vrai
    arbitrage. Il se donne pour un réglage de proxy, mais `autorisation.groupes()` fait
    `headers.get("Remote-Groups") or ""` : un en-tête ABSENT et un en-tête VIDE arrivent
    identiques, si bien que « cette personne n'appartient à aucun groupe » est une lecture
    aussi valable. On ne déplie pas d'office pour une panne qu'on ne sait pas établir.

    Le test vérifie enfin que replier n'est pas PERDRE : le référent d'AUTH-4 est toujours
    dans le document, à un clic. C'est la seule chose qui distingue un repli d'une
    suppression, et rien d'autre ne la garderait.
    """
    def etat(entetes):
        page.set_extra_http_headers(entetes)
        page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
        page.wait_for_selector(".portee-vide", timeout=3000)
        return page.locator(".portee-vide details").evaluate("e => e.open")

    # Identité + groupes reçus, aucun accès accordé — rien n'est cassé.
    assert etat({"Remote-User": "carol", "Remote-Groups": "linguistes,stage"}) is False, \
        "le cas bénin ne devrait pas se déplier d'office"

    # Identité sans groupe — indécidable, donc traité comme bénin.
    assert etat({"Remote-User": "dave"}) is False, \
        "« aucun groupe » ne s'établit pas comme une panne : pas de dépliage d'office"

    # Aucune identité derrière un proxy déclaré — la seule panne certaine.
    assert etat({}) is True, "la panne de forward_auth doit se lire sans cliquer"

    # Replier n'est pas perdre : le contenu est là, invisible, à un clic.
    page.set_extra_http_headers({"Remote-User": "sans-droits"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)
    ref = page.locator(".portee-vide-referent")
    assert ref.count() == 1, "le référent doit être dans le document, même replié"
    assert not ref.is_visible(), "…et masqué tant qu'on n'a pas déplié"
    _deplier_bandeau(page)
    assert ref.is_visible(), "un clic sur le résumé doit le rendre"
    assert "Ana Ruiz" in ref.inner_text()

    viol = _audit(page)
    assert not viol, f"Bandeau replié :\n{_fmt(viol)}"


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_la_ligne_technique_distingue_trois_situations(page, seeded):
    """La ligne technique du bandeau distingue trois situations que le même écran vide
    confondait (AUTH-1) : aucun en-tête d'identité ; une identité sans groupe ; une
    identité avec ses groupes, nommés. C'est là que servent les `groupes` que `/api/moi`
    renvoie depuis INFRA-2 sans qu'aucune surface les lise.

    Elle RAPPORTE, elle n'explique pas — réécrit le 2026-09-06. Elle disait auparavant
    « le proxy pose Remote-User sans Remote-Groups », et ce test VERROUILLAIT la formule.
    Or `autorisation.groupes()` fait `headers.get("Remote-Groups") or ""` : un en-tête
    absent et un en-tête vide y arrivent identiques, si bien que « cette personne
    n'appartient à aucun groupe » est une lecture aussi valable. La garde tenait donc en
    place une affirmation que le code ne peut pas établir — le pire service qu'un test
    puisse rendre.

    Les trois situations restent distinctes, ce qu'AUTH-1 demandait ; c'est la CAUSE qui
    n'est plus tranchée à la place de qui connaît son déploiement."""
    # Identité + groupes, mais aucun accès accordé → rien n'est cassé.
    page.set_extra_http_headers({"Remote-User": "carol", "Remote-Groups": "linguistes,stage"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    txt = page.locator(".portee-vide-technique").inner_text()
    assert "linguistes" in txt and "stage" in txt

    # Identité SANS groupe → c'est un réglage du proxy, et le message le dit.
    page.set_extra_http_headers({"Remote-User": "dave"})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    _deplier_bandeau(page)
    txt = page.locator(".portee-vide-technique").inner_text()
    # Une OBSERVATION, pas une cause. L'ancienne formule — « c'est un réglage du proxy
    # (Remote-Groups), pas un droit manquant » — était verrouillée ici, et le test tenait
    # donc en place une affirmation que le code ne peut pas établir.
    assert "Aucun groupe reçu" in txt

    # Aucune identité → les groupes ne disent rien, la ligne ne paraît pas.
    page.set_extra_http_headers({})
    page.goto(seeded["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_selector(".portee-vide", timeout=3000)
    _deplier_bandeau(page)
    assert "Aucun en-tête d'identité reçu" in page.locator(
        ".portee-vide-technique").inner_text()


@requires_kumiko
@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_segmenter_depuis_la_visionneuse_ne_fait_pas_regresser_l_ecran(page, seeded):
    """B6 (AUDIT-1) — l'ÉCRAN ne doit pas montrer la régression que la base a refusée.

    Le correctif serveur ne suffisait pas : `viewer.js` posait `state.planche.statut =
    "segmentee"` en dur après le clic, et ce champ alimente le bandeau et la pastille. Une
    planche `annotee` re-segmentée paraissait donc retomber — jusqu'au prochain
    rechargement, où elle se corrigeait seule. Un défaut qui se répare en rafraîchissant
    est un défaut que personne ne signale.

    Écrit APRÈS coup, et il aura fallu DEUX corrections pour dire vrai de cette seule ligne.
    Le commit qui la réparait affirmait le cas non testable, « faute de Kumiko dans le
    serveur live » : faux, `lib/kumiko` est là. Puis ce test, écrit dans la foulée, s'est
    révélé VACANT — il passait avec la constante en dur, parce que `segmenter()` ne
    redessine pas le bandeau. Le défaut est réel mais DIFFÉRÉ : il attend le premier
    réaffichage depuis la mémoire, d'où la re-sélection ci-dessous. Deux affirmations
    confiantes et non mesurées sur trois lignes de code.

    Le test tourne avec le vrai moteur et se skippe là où le clone est absent.
    """
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=60, headers=ADMIN)
    try:
        assert c.patch(f"/api/planches/{seeded['planche']}/statut",
                       json={"statut": "annotee"}).status_code == 200
    finally:
        c.close()

    page.set_extra_http_headers(ADMIN)
    page.goto(seeded["base"] + f"/?album={seeded['album']}&planche={seeded['planche']}",
              wait_until="networkidle")
    page.wait_for_timeout(500)
    assert "annotee" in page.locator("#planche-info").inner_text()

    page.click("#btn-traitement")            # « Segmenter » vit dans un menu déroulant
    page.wait_for_selector("#btn-segmenter", state="visible", timeout=3000)
    page.click("#btn-segmenter")
    # Kumiko tourne en sous-processus : on attend la fin, pas une durée.
    page.wait_for_selector(".toast", timeout=120000)
    page.wait_for_timeout(1500)

    # RE-SÉLECTION, et c'est tout le test. `segmenter()` ne redessine pas le bandeau —
    # écrire une constante dans `state.planche.statut` n'a donc aucun effet IMMÉDIAT, et
    # une assertion posée ici passerait quoi qu'il arrive. Mais `selectPlanche()` lit
    # `state.planches` EN MÉMOIRE, sans refetch, et `state.planche` en est le même objet :
    # la valeur faussée ressort au premier réaffichage. Sans ce clic, le test est vacant —
    # vérifié par mutation le 2026-08-31, il passait avec la constante en dur.
    page.click("#planche-list li")
    page.wait_for_timeout(800)

    info = page.locator("#planche-info").inner_text()
    assert "annotee" in info, f"l'écran a fait régresser le statut : {info!r}"
    assert "segmentee" not in info, f"l'écran affiche la régression refusée par la base : {info!r}"

    # Et la base est d'accord — sans quoi le test ne dirait rien de l'écran, seulement
    # que rien ne s'est passé.
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30, headers=ADMIN)
    try:
        pl = [p for p in c.get(f"/api/albums/{seeded['album']}/planches").json()
              if p["id"] == seeded["planche"]][0]
    finally:
        c.close()
    assert pl["statut"] == "annotee"
    assert pl["date_segmentation"], "la segmentation n'a pas eu lieu : le test ne prouve rien"
