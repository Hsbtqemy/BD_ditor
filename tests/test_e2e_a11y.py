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

# AUTH-2 : `ADMIN` monte le décor avec les droits qu'il faut (sans effet hors proxy).
from conftest import ADMIN, make_png  # noqa: E402

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
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers=ADMIN)
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
    """Accord inter-annotateurs (ANN-5 / B6) : créer une divergence (alice corrige, bob
    re-corrige le même token via l'en-tête Remote-User) puis auditer la modale (table +
    liste de divergences). Si le corpus n'a pas de tokens (spaCy absent), on audite l'état vide."""
    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        toks = c.get(f"/api/regions/{seeded['region']}/tokens").json()
        if toks:
            o = toks[0]["ordre"]
            c.put(f"/api/regions/{seeded['region']}/tokens/{o}",
                  json={"etat": "corrige", "pos": "NOUN"}, headers={"Remote-User": "alice", "Remote-Groups": "bd-admins"})
            c.put(f"/api/regions/{seeded['region']}/tokens/{o}",
                  json={"etat": "corrige", "pos": "VERB"}, headers={"Remote-User": "bob", "Remote-Groups": "bd-admins"})
    finally:
        c.close()
    page.goto(seeded["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click("#btn-accord-inter")
    page.wait_for_selector("#accord-inter-modal:not([hidden]) #accord-inter-body", timeout=3000)
    page.wait_for_timeout(300)
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
    assert "identité" in page.locator(".portee-vide strong").inner_text()
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
