"""La page Annotation sur un écran étroit et au doigt (ANN-7, ANN-6, tranche 2, commit 12).

Les formes sont celles de la maquette v3, reprises par `docs/ann7-tranche2-cadrage.md` : sous
75em, la planche et le Contexte dans un tiroir ; sous 47,5em, la grille monte du bas par
« Poser… ▴ » ; au doigt, « Étendre », « Ajouter un mot » et « Tracer une zone ». Le doigt est
un VRAI toucher (`Input.dispatchTouchEvent`, par CDP) : un `pointerdown` synthétique ne
dirait rien de `touch-action`, qui est le cœur du tracé au doigt. Le jeu sur un vrai appareil
reste à faire : c'est une case d'`ANN-6`.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402
from grilles_decor import grille_active_vivante  # noqa: E402
from test_e2e_a11y import _AXE, _audit, _fmt  # noqa: E402
from test_e2e_annotation_page import _ouvrir, decor  # noqa: E402,F401

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/annotation",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier a ses tiroirs et ses audits à lui ; rien de cette page n'y est monté",
    "/recherche": "la Recherche n'a ni planche ni grille",
    "/corpus": "la Bibliothèque range des albums ; elle ne mène pas à cette page",
    "/exploration": "l'Exploration compte le corpus ; les relevés y viendront en tranche 4",
    "/administration": "rien n'y porte sur une planche",
}

TELEPHONE = {"width": 390, "height": 844}
TABLETTE = {"width": 900, "height": 1000}


@pytest.fixture
def doigt(page):
    """Un téléphone : un écran tactile, et un pointeur grossier."""
    ctx = page.context.browser.new_context(viewport=TELEPHONE, has_touch=True, is_mobile=True,
                                           device_scale_factor=2)
    pg = ctx.new_page()
    yield pg
    ctx.close()


def _http(d):
    return httpx.Client(base_url=d["base"], trust_env=False, timeout=60, headers=ECRITURE)


def _glisser_au_doigt(page, de, a, pas=6):
    """Un vrai glissé d'un doigt, de `de` à `a` (coordonnées d'écran)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": de[0], "y": de[1]}]})
    for i in range(1, pas + 1):
        x = de[0] + (a[0] - de[0]) * i / pas
        y = de[1] + (a[1] - de[1]) * i / pas
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
    # Le doigt s'arrête avant de se lever. Mesuré : levé en pleine vitesse, le toucher SUIVANT,
    # où qu'il tombe sur la page, ne donne aucun `click`. Hypothèse : Chromium le prend pour le
    # toucher qui arrête un lancer. À regarder sur un vrai appareil.
    page.wait_for_timeout(250)
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchMove", "touchPoints": [{"x": a[0], "y": a[1]}]})
    page.wait_for_timeout(100)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def _visible(page, selecteur):
    """Vraiment là : pas seulement dans le document (un tiroir fermé y reste)."""
    return page.evaluate("""(s) => { const e = document.querySelector(s);
      const st = getComputedStyle(e), r = e.getBoundingClientRect();
      return st.display !== 'none' && st.visibility === 'visible'
        && r.right > 0 && r.left < innerWidth && r.top < innerHeight && r.bottom > 0; }""",
                         selecteur)


def _hauteurs(page):
    return page.evaluate("""() => [...document.querySelector('#an-zone').children]
      .map((e) => [e.id || e.className, e.getBoundingClientRect().height])""")


# --------------------------------------------------------------------------- #
# Une fenêtre basse : rien ne s'écrase
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("hauteur", [720, 640, 560])
def test_une_fenetre_basse_n_ecrase_aucune_rangee(page, decor, hauteur):
    """Mesuré le 2026-10-31 : `.an-zones`, un cadre défilant sans hauteur minimale automatique,
    absorbait en `flex-shrink: 1` tout le manque de place — 21 px à 720 de haut, 0 à 640. Les
    bandes du proxy n'y sont pour rien, sinon qu'elles retirent de la hauteur : la mesure sans
    elles, à 640, est celle de Hugo derrière le proxy à 720. C'est la colonne qui défile."""
    page.set_viewport_size({"width": 1280, "height": 900})
    _ouvrir(page, decor, decor["bulle"])
    grand = dict(_hauteurs(page))
    page.set_viewport_size({"width": 1280, "height": hauteur})
    page.wait_for_function("h => innerHeight === h", arg=hauteur)
    bas = dict(_hauteurs(page))
    for rangee in ("an-zones", "an-tete", "an-texte-bloc", "an-pied"):
        assert abs(bas[rangee] - grand[rangee]) <= 1, (rangee, grand[rangee], bas[rangee])
    assert bas["an-porte-l"] >= 26
    # À 720, la page resserrée tient sans défiler : la règle de la v3 pour une fenêtre basse.
    if hauteur == 720:
        assert page.evaluate("""() => { const c = document.querySelector('#an-zone');
          return c.scrollHeight <= c.clientHeight + 1; }""")
    # Et le bas de la colonne reste atteignable : elle défile.
    page.locator("#an-suiv").scroll_into_view_if_needed()
    expect(page.locator("#an-suiv")).to_be_in_viewport()


# --------------------------------------------------------------------------- #
# Le tiroir de la planche
# --------------------------------------------------------------------------- #
def test_le_tiroir_de_la_planche_s_ouvre_choisit_et_se_referme(page, decor):
    page.set_viewport_size(TABLETTE)
    _ouvrir(page, decor, decor["bulle"])
    bascule = page.locator("#an-tiroir-planche")
    expect(bascule).to_be_visible()
    expect(bascule).to_have_attribute("aria-expanded", "false")
    assert not _visible(page, "#an-gauche")
    # Fermé, il n'est pas dans la tabulation : `visibility`, et non le seul hors-champ.
    assert page.evaluate("() => getComputedStyle(document.querySelector('#an-gauche')).visibility") \
        == "hidden"
    bascule.click()
    expect(bascule).to_have_attribute("aria-expanded", "true")
    page.wait_for_function("""() => {
      const r = document.querySelector('#an-gauche').getBoundingClientRect();
      return r.left === 0; }""")
    expect(page.locator("#an-gauche-fermer")).to_be_focused()
    expect(page.locator("#an-note")).to_be_visible()      # le Contexte y est
    # Échap le ferme et rend le focus d'où l'on vient.
    page.keyboard.press("Escape")
    expect(bascule).to_have_attribute("aria-expanded", "false")
    expect(bascule).to_be_focused()
    # Choisir une case sur la minicarte le referme : on va la voir.
    bascule.click()
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    expect(bascule).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#annot")).not_to_have_class(re.compile("planche-ouverte"))


def test_au_large_il_n_y_a_ni_tiroir_ni_feuille(page, decor):
    page.set_viewport_size({"width": 1400, "height": 900})
    _ouvrir(page, decor, decor["bulle"])
    for s in ("#an-tiroir-planche", "#an-gauche-fermer", "#an-grille-fermer", "#an-poser"):
        expect(page.locator(s)).to_be_hidden()
    assert "/annotation" in page.url
    assert _visible(page, "#an-gauche") and _visible(page, "#an-grille")


def test_elargir_la_fenetre_rend_la_page_a_ses_colonnes(page, decor):
    """Ouvrir la feuille à 390 px, puis élargir : plus de feuille, donc plus rien d'inerte."""
    page.set_viewport_size(TELEPHONE)
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-poser").click()
    assert page.evaluate("() => document.querySelector('#an-zone').inert")
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_function("() => !document.querySelector('#an-zone').inert")
    assert not page.evaluate("() => document.querySelector('#site-nav').inert")
    expect(page.locator("#an-suiv")).to_be_enabled()
    page.locator("#an-suiv").click()


# --------------------------------------------------------------------------- #
# La grille qui monte du bas
# --------------------------------------------------------------------------- #
def test_la_grille_monte_du_bas_et_on_y_pose(page, decor):
    page.set_viewport_size(TELEPHONE)
    _ouvrir(page, decor, decor["bulle"])
    poser = page.locator("#an-poser")
    expect(poser).to_be_visible()
    expect(poser).to_have_text("Poser… ▴")
    expect(page.locator("#an-barre-sel")).to_have_text(re.compile(r"bulle b1"))
    assert not _visible(page, "#an-grille")
    assert page.evaluate("() => getComputedStyle(document.querySelector('#an-grille')).visibility") \
        == "hidden"
    # La barre ne cache pas le pied : la page réserve sa place.
    page.locator("#an-terminee-suiv").scroll_into_view_if_needed()
    assert page.evaluate("""() => document.querySelector('#an-terminee-suiv')
      .getBoundingClientRect().bottom <= document.querySelector('#an-barre-poser')
      .getBoundingClientRect().top""")
    # Des mots désignés : la barre dit le passage.
    page.locator("#an-mot-1").click()
    expect(page.locator("#an-barre-sel")).to_have_text(re.compile("SABORDS"))
    poser.click()
    expect(poser).to_have_attribute("aria-expanded", "true")
    page.wait_for_function("""() => {
      const r = document.querySelector('#an-grille').getBoundingClientRect();
      return Math.abs(r.bottom - innerHeight) < 1; }""")
    assert page.evaluate("() => document.querySelector('#an-zone').inert")
    expect(page.locator("#an-filtre")).to_be_focused()   # à la souris, le filtre
    with page.expect_response(lambda r: r.url.endswith("/api/releves")
                              and r.request.method == "POST") as rep:
        page.locator("#an-plan [role=checkbox]", has_text="cri").first.click()
    assert rep.value.status == 201, rep.value.text()
    # Fermer rend la page et le focus.
    page.locator("#an-grille-fermer").click()
    expect(poser).to_have_attribute("aria-expanded", "false")
    expect(poser).to_be_focused()
    assert not page.evaluate("() => document.querySelector('#an-zone').inert")


def test_echap_vide_le_filtre_avant_de_fermer_la_feuille(page, decor):
    page.set_viewport_size(TELEPHONE)
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-poser").click()
    page.locator("#an-filtre").fill("cri")
    page.keyboard.press("Escape")
    expect(page.locator("#an-filtre")).to_have_value("")
    expect(page.locator("#an-poser")).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Escape")
    expect(page.locator("#an-poser")).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#an-poser")).to_be_focused()


def test_un_conflit_ouvre_la_feuille_qui_porte_son_bandeau(page, decor):
    """Le bandeau de CONC-3 vit dans la boîte du guide : sur un téléphone, une note périmée
    écrite dans le tiroir ne doit pas ouvrir un conflit que personne ne voit."""
    page.set_viewport_size(TELEPHONE)
    _ouvrir(page, decor, decor["bulle"])
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "un autre l'a changée"}).status_code == 200
    page.locator("#an-tiroir-planche").click()
    page.locator("#an-note").fill("la mienne")
    page.locator("#an-note").blur()
    expect(page.locator("#an-cf-mienne")).to_be_visible(timeout=10000)
    expect(page.locator("#an-poser")).to_have_attribute("aria-expanded", "true")
    page.wait_for_function("""() => {
      const r = document.querySelector('#an-cf-mienne').getBoundingClientRect();
      return r.top > 0 && r.bottom <= innerHeight; }""")


def test_designer_un_lien_passe_par_la_planche_et_revient(page, decor):
    """Sur un téléphone, la ligne qui offre « Désigner sur la planche » est dans la feuille, la
    zone à désigner dessous : la feuille s'efface, le tiroir montre la minicarte, et tout
    revient une fois le lien posé."""
    page.set_viewport_size(TELEPHONE)
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-poser").click()
    page.locator("#an-plan [role=checkbox]", has_text="réponse à une autre bulle").click()
    page.locator("#an-poses-liste .an-lien-btn").click()
    expect(page.locator("#an-poser")).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#an-mini-mode")).to_be_visible()
    with page.expect_response(lambda x: "/api/releves/" in x.url
                              and x.request.method == "PUT") as rep:
        page.locator(f'#an-mini rect[data-region="{decor["cartouche"]}"]').click()
    assert rep.value.status == 200, rep.value.text()
    expect(page.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#an-poser")).to_have_attribute("aria-expanded", "true")


# --------------------------------------------------------------------------- #
# Au doigt
# --------------------------------------------------------------------------- #
def test_etendre_et_ajouter_ne_s_offrent_que_la_ou_un_doigt_existe(page, doigt, decor):
    _ouvrir(page, decor, decor["bulle"])                 # une souris
    expect(page.locator("#an-mot-0")).to_be_visible()
    expect(page.locator('[data-doigt="etendre"]')).to_be_hidden()
    _ouvrir(doigt, decor, decor["bulle"])                # un doigt
    expect(doigt.locator('[data-doigt="etendre"]')).to_be_visible()
    expect(doigt.locator('[data-doigt="ajouter"]')).to_be_visible()
    # Sans mots, ils n'ont rien à faire là.
    doigt.locator('.an-zone-btn[data-zone=""]').tap()
    expect(doigt.locator('[data-doigt="etendre"]')).to_be_hidden()


def test_au_doigt_un_passage_s_etend_et_prend_un_trou(doigt, decor):
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}",
                     json={"ocr_texte": "NE RIEN DIRE DU TOUT"}).status_code == 200
    _ouvrir(doigt, decor, decor["bulle"])
    choisis = lambda: doigt.evaluate(  # noqa: E731
        "() => [...document.querySelectorAll('#an-mots .an-mot.sel')].map((m) => +m.dataset.rang)")
    doigt.locator("#an-mot-1").tap()
    assert choisis() == [1]
    # Toucher le mot seul désigné le retire.
    doigt.locator("#an-mot-1").tap()
    assert choisis() == []
    doigt.locator("#an-mot-0").tap()
    etendre = doigt.locator('[data-doigt="etendre"]')
    ajouter = doigt.locator('[data-doigt="ajouter"]')
    etendre.tap()
    expect(etendre).to_have_attribute("aria-pressed", "true")
    doigt.locator("#an-mot-2").tap()
    assert choisis() == [0, 1, 2]
    # Les deux modes s'excluent, et « Ajouter un mot » fait le trou de « ne … pas ».
    ajouter.tap()
    expect(ajouter).to_have_attribute("aria-pressed", "true")
    expect(etendre).to_have_attribute("aria-pressed", "false")
    doigt.locator("#an-mot-1").tap()
    assert choisis() == [0, 2]
    doigt.locator("#an-mot-4").tap()
    assert choisis() == [0, 2, 4]
    # Retoucher le mode l'éteint ; changer de zone aussi.
    ajouter.tap()
    expect(ajouter).to_have_attribute("aria-pressed", "false")
    ajouter.tap()
    doigt.locator('.an-zone-btn[data-zone=""]').tap()
    doigt.locator(f'.an-zone-btn[data-zone="{decor["bulle"]}"]').tap()
    expect(ajouter).to_have_attribute("aria-pressed", "false")


def test_un_glisse_au_doigt_ne_trace_rien_sans_tracer_arme(doigt, decor):
    """Au doigt, un glissé dans la case n'est pas un tracé : il ferait perdre le défilement."""
    _ouvrir(doigt, decor, decor["c1"])
    boite = doigt.locator(".an-case-svg").bounding_box()
    x, y = boite["x"] + 30, boite["y"] + 30
    _glisser_au_doigt(doigt, (x, y), (x + 40, y + 60))
    doigt.wait_for_timeout(200)
    expect(doigt.locator("#an-trace")).to_be_hidden()
    assert doigt.locator(".an-trace-rect").count() == 0
    # Le navigateur annule un tel geste (`pointercancel`) dès qu'il le prend pour un défilement ;
    # la garde est ce qui tient là où il ne le fait pas : un stylet, un écran sans défilement.
    doigt.evaluate("""([x, y]) => {
      const cible = document.querySelector('.an-case-svg .an-fond');
      const ev = (t, dx) => new PointerEvent(t, { bubbles: true, pointerType: 'touch', button: 0,
                                                  clientX: x + dx, clientY: y + dx });
      cible.dispatchEvent(ev('pointerdown', 0));
      cible.dispatchEvent(ev('pointermove', 60));
      cible.dispatchEvent(ev('pointerup', 60)); }""", [x, y])
    expect(doigt.locator("#an-trace")).to_be_hidden()
    assert doigt.locator(".an-trace-rect").count() == 0


def test_au_doigt_tracer_une_zone_puis_la_nommer(doigt, decor):
    _ouvrir(doigt, decor, decor["c1"])
    tracer = doigt.locator("#an-tracer")
    expect(tracer).to_be_visible()
    tracer.tap()
    expect(tracer).to_have_attribute("aria-pressed", "true")
    # Sur le calque de la case, et non sur sa boîte : le choix de la sorte y reste touchable.
    assert doigt.evaluate("""() => getComputedStyle(document.querySelector('.an-case-svg'))
      .touchAction""") == "none"
    assert doigt.evaluate("""() => getComputedStyle(document.querySelector('#an-trace'))
      .touchAction""") == "auto"
    doigt.locator(".an-case-svg").scroll_into_view_if_needed()
    boite = doigt.locator(".an-case-svg").bounding_box()
    x, y = boite["x"] + boite["width"] * .4, boite["y"] + boite["height"] * .55
    _glisser_au_doigt(doigt, (x, y), (x + 40, y + 50))
    expect(doigt.locator("#an-trace")).to_be_visible()
    with doigt.expect_response(lambda r: r.url.endswith("/regions")
                               and r.request.method == "POST") as rep:
        doigt.locator('#an-trace [data-trace="detail"]').tap()
    assert rep.value.status == 201, rep.value.text()
    corps = rep.value.json()
    assert corps["type"] == "detail" and corps["parent_id"] == decor["c1"]
    expect(tracer).to_have_attribute("aria-pressed", "false")
    # Le nom s'écrit dans le Contexte, donc dans le tiroir : il s'ouvre, et le champ attend.
    expect(doigt.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "true")
    expect(doigt.locator("#an-nom")).to_be_focused()
    doigt.locator("#an-nom").fill("la lampe")
    with doigt.expect_response(lambda r: f"/api/regions/{corps['id']}" in r.url
                               and r.request.method == "PUT") as rep:
        doigt.locator("#an-nom").press("Enter")
    assert rep.value.status == 200, rep.value.text()


def test_tracer_se_desarme_et_rien_ne_s_ecrit_sans_droit(page, decor):
    _ouvrir(page, decor, decor["c1"])
    tracer = page.locator("#an-tracer")
    tracer.click()
    expect(tracer).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#an-vue-case")).to_have_class(re.compile("an-dessin"))
    tracer.click()
    expect(tracer).to_have_attribute("aria-pressed", "false")
    tracer.click()
    page.keyboard.press("Escape")
    expect(tracer).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#an-vue-case")).not_to_have_class(re.compile("an-dessin"))


# --------------------------------------------------------------------------- #
# Au clavier
# --------------------------------------------------------------------------- #
def test_au_clavier_tracer_une_zone(page, decor):
    """Le rectangle naît au milieu de la case (360 × 900 : 120 × 300 en 140, 320), un pas fait
    un vingtième de la case (18 et 45) ; Maj+flèches changent sa taille."""
    _ouvrir(page, decor, decor["c1"])
    tracer = page.locator("#an-tracer")
    tracer.focus()
    page.keyboard.press("Enter")
    boite = page.locator("#an-vue-case")
    expect(boite).to_be_focused()
    expect(boite).to_have_attribute("role", "group")
    rect = lambda: page.evaluate("""() => { const r = document.querySelector('.an-trace-rect');
      return ['x', 'y', 'width', 'height'].map((k) => +r.getAttribute(k)); }""")  # noqa: E731
    assert rect() == [140, 320, 120, 300]
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowUp")
    assert rect() == [158, 275, 120, 300]
    page.keyboard.press("Shift+ArrowDown")
    assert rect() == [158, 275, 120, 345]
    page.keyboard.press("Enter")
    expect(page.locator('#an-trace [data-trace="detail"]')).to_be_focused()
    # La boîte rend sa place dans la tabulation.
    assert page.evaluate("() => document.querySelector('#an-vue-case').getAttribute('tabindex')") \
        is None
    with page.expect_response(lambda r: r.url.endswith("/regions")
                              and r.request.method == "POST") as rep:
        page.locator('#an-trace [data-trace="texte"]').focus()
        page.keyboard.press("Enter")
    assert rep.value.status == 201, rep.value.text()
    corps = rep.value.json()
    assert (corps["x"], corps["y"], corps["w"], corps["h"]) == (158, 275, 120, 345)
    assert corps["type"] == "texte"
    expect(page.locator("#an-transcription")).to_be_focused()


def test_au_clavier_echap_renonce_et_rend_le_focus(page, decor):
    _ouvrir(page, decor, decor["c1"])
    tracer = page.locator("#an-tracer")
    tracer.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#an-vue-case")).to_be_focused()
    page.keyboard.press("Escape")
    expect(tracer).to_be_focused()
    expect(tracer).to_have_attribute("aria-pressed", "false")
    assert page.locator(".an-trace-rect").count() == 0
    assert page.evaluate("() => document.querySelector('#an-vue-case').getAttribute('role')") is None


def test_changer_de_case_renonce_au_trace(page, decor):
    _ouvrir(page, decor, decor["c1"])
    page.locator("#an-tracer").focus()
    page.keyboard.press("Enter")
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    expect(page.locator("#an-tracer")).to_have_attribute("aria-pressed", "false")
    assert page.locator(".an-trace-rect").count() == 0


def test_changer_de_planche_renonce_au_trace(page, decor):
    with _http(decor) as c:
        autre = c.post(f"/api/albums/{decor['album']}/import",
                       files={"file": ("q.png", make_png(800, 1000), "image/png")}).json()["id"]
    _ouvrir(page, decor, decor["c1"])
    page.locator("#an-tracer").focus()
    page.keyboard.press("Enter")
    page.locator("#an-planche-choix").select_option(str(autre))
    expect(page.locator("#an-tracer")).to_have_attribute("aria-pressed", "false")
    assert page.locator(".an-trace-rect").count() == 0


def test_a_la_souris_le_glisse_reste_le_geste(page, decor):
    """« Tracer une zone » n'enlève rien : à la souris, on glisse sans l'armer."""
    _ouvrir(page, decor, decor["c1"])
    b = page.locator(".an-case-svg").bounding_box()
    x, y = b["x"] + b["width"] * .5, b["y"] + b["height"] * .7
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 40, y + 40, steps=4)
    page.mouse.up()
    expect(page.locator("#an-trace")).to_be_visible()
    expect(page.locator("#an-tracer")).to_have_attribute("aria-pressed", "false")


def test_tracer_ne_s_offre_pas_a_qui_lit(page, decor):
    page.route("**/api/albums", lambda r: r.fulfill(json=[
        {**a, "ecrivable": False} for a in r.fetch().json()]))
    _ouvrir(page, decor, decor["c1"])
    expect(page.locator("#an-tracer")).to_be_hidden()


# --------------------------------------------------------------------------- #
# L'audit, panneaux ouverts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("bascule", ["#an-tiroir-planche", "#an-poser"])
def test_a11y_tiroir_et_feuille_ouverts(page, decor, theme, bascule):
    """L'audit de surface mesure la page à sa largeur d'ordinateur : ces deux panneaux n'y
    existent pas. Fermés, ils ne doivent pas compter ; ouverts, ils doivent tenir."""
    if not _AXE.is_file():
        pytest.skip("axe absent (tests/js/vendor/axe.min.js)")
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    page.set_viewport_size(TELEPHONE)
    _ouvrir(page, decor, decor["bulle"])
    assert not _audit(page), "panneaux fermés"
    page.locator(bascule).click()
    page.wait_for_function("""() => !document.getAnimations()
      .some((a) => a.playState === 'running')""")
    viol = _audit(page)
    assert not viol, _fmt(viol)


def test_ouvrir_un_releve_depuis_le_tiroir_rend_le_focus_a_sa_bascule(page, decor):
    """Une ligne de la Synthèse ferme le tiroir qui la porte : le focus resterait dans un panneau
    caché, inatteignable."""
    page.set_viewport_size(TABLETTE)
    with _http(decor) as c:
        c.post("/api/releves", json={"region_id": decor["c2"], "grille_id": decor["grille"],
                                     "version": 1, "entree_cle": "regard-camera"})
    _ouvrir(page, decor, decor["bulle"])
    bascule = page.locator("#an-tiroir-planche")
    bascule.click()
    page.locator("#an-ong-synthese").click()
    ligne = page.locator("#an-syn-corps [data-syn-releve]").last
    expect(ligne).to_be_visible()
    ligne.focus()
    page.keyboard.press("Enter")
    expect(bascule).to_have_attribute("aria-expanded", "false")
    expect(bascule).to_be_focused()


# --------------------------------------------------------------------------- #
# Sur un vrai appareil (ANN-6, passe du 2026-11-02) : le téléphone couché, la feuille dans ce
# qui se voit, la consigne du lien hors de la planche
# --------------------------------------------------------------------------- #
COUCHE = [{"width": 740, "height": 340}, {"width": 667, "height": 375}]
TABLETTE_COUCHEE = {"width": 1024, "height": 768}


@pytest.fixture
def appareil(page):
    """Un écran tactile, à la taille qu'on lui donne (`appareil(viewport)`)."""
    ouverts = []

    def ouvrir(viewport):
        ctx = page.context.browser.new_context(viewport=viewport, has_touch=True,
                                               is_mobile=True, device_scale_factor=2)
        ouverts.append(ctx)
        return ctx.new_page()

    yield ouvrir
    for ctx in ouverts:
        ctx.close()


def _boite(page, selecteur):
    return page.evaluate("""(s) => { const r = document.querySelector(s).getBoundingClientRect();
      return {haut: r.top, bas: r.bottom, gauche: r.left, droite: r.right, h: r.height}; }""",
                         selecteur)


def _ouvrir_la_feuille(pg):
    pg.locator("#an-poser").tap()
    expect(pg.locator("#an-poser")).to_have_attribute("aria-expanded", "true")
    pg.wait_for_function("""() => {
      const r = document.querySelector('#an-grille').getBoundingClientRect();
      return Math.abs(r.bottom - innerHeight) < 1
        && !document.getAnimations().some((a) => a.playState === 'running'); }""")


def _la_feuille_tient_dans_la_fenetre(pg):
    """« Fermer ✕ » en entier en haut, le guide en entier en bas : tout dans la fenêtre."""
    hauteur = pg.evaluate("() => innerHeight")
    for s in ("#an-grille", "#an-grille-fermer", "#an-guide", "#an-guide-replier"):
        b = _boite(pg, s)
        assert b["haut"] >= 0 and b["bas"] <= hauteur + .5, (s, b, hauteur)
    expect(pg.locator("#an-grille-fermer")).to_be_in_viewport(ratio=1)
    # Mesurée sur la plus PETITE fenêtre, barres affichées. Chromium n'a pas de barre qui se
    # replie (`svh` y vaut `vh`) : ce qu'on peut vérifier ici, c'est l'unité, et que `vh` ne la
    # fait pas bouger.
    assert "svh" in pg.evaluate("""() => getComputedStyle(document.querySelector('#an-grille'))
      .getPropertyValue('--svh-visible')""")
    avant = _boite(pg, "#an-grille")["h"]
    pg.evaluate("""() => document.documentElement.style.setProperty('--vh-visible', '2px')""")
    assert _boite(pg, "#an-grille")["h"] == avant
    pg.evaluate("""() => document.documentElement.style.removeProperty('--vh-visible')""")


def _hauteur_de_la_case(page, repliee=None):
    """La hauteur de la case, `vh` posée au besoin sur une fenêtre plus grande que la vraie."""
    if repliee:
        page.evaluate("""(h) => document.documentElement.style.setProperty(
          '--vh-visible', `calc(${h / 100}px / var(--ui-zoom, 1))`)""", repliee)
    return page.evaluate("""() => new Promise((rendre) => requestAnimationFrame(() => rendre(
      document.querySelector('#an-vue-case').getBoundingClientRect().height)))""")


def test_tablette_couchee_suivante_tient_barres_affichees(page, decor):
    """« Suivante » reste dans la fenêtre au repos, barres du navigateur affichées.

    Chromium n'a pas de barre qui se replie : `vh` y vaut `svh`. La barre se SIMULE comme au
    banc du 2026-11-02 : une fenêtre de 700 (800 sous 100 px de barres) et `--vh-visible` posée
    sur 800, ce que `vh` donnerait sous une vraie barre. En `vh`, la case gardait 288 px et
    « Suivante » tombait à 728 : hors de la fenêtre, sans qu'on ait rien touché.
    """
    page.set_viewport_size({"width": 1280, "height": 700})
    _ouvrir(page, decor, decor["bulle"])
    _hauteur_de_la_case(page, repliee=800)
    suivante = page.evaluate("""() => { const c = document.querySelector('#an-zone');
      return {bas: document.querySelector('#an-suiv').getBoundingClientRect().bottom,
              defile: c.scrollTop}; }""")
    assert suivante["defile"] == 0 and suivante["bas"] <= 700, suivante


@pytest.mark.parametrize("largeur, hauteur, part", [(1400, 900, .44), (1280, 700, .36),
                                                    (412, 800, .40)])
def test_la_case_se_mesure_sur_ce_qui_se_voit_et_ne_bouge_pas(page, decor, largeur, hauteur, part):
    """Les trois hauteurs de la case suivent la plus petite fenêtre, jamais `vh`.

    Stable : la barre qui se replie ne déplace rien pendant le travail, et c'est pourquoi
    `svh` et non `dvh`, qui la suivrait.
    """
    page.set_viewport_size({"width": largeur, "height": hauteur})
    _ouvrir(page, decor, decor["bulle"])
    h = _hauteur_de_la_case(page, repliee=hauteur + 100)
    assert abs(h - part * hauteur) <= 2, h
    assert _hauteur_de_la_case(page, repliee=hauteur + 200) == h


@pytest.mark.parametrize("largeur, hauteur, part", [(1280, 800, .36), (1400, 1000, .44)])
def test_la_case_garde_sa_part_de_la_fenetre_sous_le_zoom(page, decor, largeur, hauteur, part):
    """`--svh-visible` retire le zoom d'interface, comme `--vh-visible`, que `zoom` multiplierait."""
    page.set_viewport_size({"width": largeur, "height": hauteur})
    page.add_init_script("try { localStorage.setItem('bd-zoom', '1.25') } catch (e) {}")
    _ouvrir(page, decor, decor["bulle"])
    assert page.evaluate("document.documentElement.style.zoom") == "1.25"
    assert abs(_hauteur_de_la_case(page) - part * hauteur) <= 2


@pytest.mark.parametrize("viewport", COUCHE, ids=lambda v: f"{v['width']}x{v['height']}")
def test_telephone_couche_la_grille_se_sert(appareil, decor, viewport):
    """Constaté par Hugo sur un Galaxy couché : la liste des entrées avait une hauteur NULLE (8 px
    à 340 et à 375 de haut, la marge seule), l'en-tête de la grille et ce qui est posé prenant
    tout. Couchée, la feuille passe en deux colonnes : la grille à gauche, ce qui est posé et le
    guide à droite, sur toute la hauteur."""
    pg = appareil(viewport)
    _ouvrir(pg, decor, decor["bulle"])
    pg.locator("#an-mot-1").tap()
    _ouvrir_la_feuille(pg)
    corps, poses, bas = (_boite(pg, s) for s in ("#an-grille-corps", "#an-poses", ".an-bas"))
    tete, fermer = _boite(pg, ".an-gr-tete"), _boite(pg, ".an-gr-fermer-l")
    # Deux colonnes : la grille à gauche, ce qui est posé à droite, côte à côte.
    assert corps["droite"] <= poses["gauche"] + .5, (corps, poses)
    assert tete["droite"] <= fermer["gauche"] + .5, (tete, fermer)
    # La liste des entrées a une hauteur UTILE, et elle défile.
    assert pg.evaluate("() => document.querySelector('#an-grille-corps').clientHeight") >= 96
    assert pg.evaluate("""() => { const c = document.querySelector('#an-grille-corps');
      const avant = c.scrollTop; c.scrollTop = 60; return c.scrollTop > avant; }""")
    pg.evaluate("() => { document.querySelector('#an-grille-corps').scrollTop = 0; }")
    # Ce qui est posé tient toute la hauteur que le guide lui laisse.
    assert poses["h"] >= 96, poses
    assert abs(bas["bas"] - _boite(pg, "#an-grille")["bas"]) <= 1.5, bas
    _la_feuille_tient_dans_la_fenetre(pg)
    # Une entrée se coche au toucher.
    entree = pg.locator("#an-plan [role=checkbox]", has_text="cri").first
    expect(entree).to_be_in_viewport(ratio=1)
    with pg.expect_response(lambda r: r.url.endswith("/api/releves")
                            and r.request.method == "POST") as rep:
        entree.tap()
    assert rep.value.status == 201, rep.value.text()
    expect(entree).to_have_attribute("aria-checked", "true")
    # Et ce qu'on vient de poser se lit à côté, sans rien fermer.
    pose = pg.locator("#an-poses-liste .an-pose-btn", has_text="cri")
    expect(pose).to_be_visible()
    expect(pose).to_be_in_viewport(ratio=1)


def test_telephone_debout_la_feuille_reste_empilee(appareil, decor):
    """Debout, rien ne change : une colonne, ce qui est posé et le guide à hauteur fixe en bas,
    la liste des entrées entre les deux — et la feuille dans ce qui se voit."""
    pg = appareil(TELEPHONE)
    _ouvrir(pg, decor, decor["bulle"])
    _ouvrir_la_feuille(pg)
    corps, poses, bas = (_boite(pg, s) for s in ("#an-grille-corps", "#an-poses", ".an-bas"))
    assert abs(corps["gauche"] - poses["gauche"]) <= 1 and corps["bas"] <= poses["haut"] + .5
    assert abs(bas["h"] - pg.evaluate("""() => 15.3846 * parseFloat(
      getComputedStyle(document.documentElement).fontSize)""")) <= 1, bas
    assert abs(_boite(pg, "#an-grille")["h"] - .88 * TELEPHONE["height"]) <= 1.5
    assert pg.evaluate("() => document.querySelector('#an-grille-corps').clientHeight") >= 300
    _la_feuille_tient_dans_la_fenetre(pg)


def _commencer_la_designation(pg):
    pg.locator("#an-plan [role=checkbox]", has_text="réponse à une autre bulle").tap()
    lien = pg.locator("#an-poses-liste .an-lien-btn")
    expect(lien).to_be_visible()
    lien.tap()
    expect(lien).to_have_attribute("aria-pressed", "true")
    return lien


def test_tablette_la_consigne_du_lien_ne_couvre_pas_la_planche(appareil, decor):
    """Relevé par Hugo sur l'iPad : posée SUR la minicarte, « Cliquez la zone liée · Échap
    annule » pouvait cacher une bulle, disait « Cliquez » au doigt, et ne s'annulait qu'au
    clavier. Elle prend la place du titre, à la même hauteur, avec « Annuler »."""
    pg = appareil(TABLETTE_COUCHEE)
    _ouvrir(pg, decor, decor["bulle"])
    pg.locator("#an-tiroir-planche").tap()
    pg.wait_for_function("""() => document.querySelector('#an-gauche').getBoundingClientRect().left === 0
      && !document.getAnimations().some((a) => a.playState === 'running')""")
    expect(pg.locator("#an-mini-titre")).to_be_visible()
    mini_avant = _boite(pg, "#an-mini")
    pg.locator("#an-gauche-fermer").tap()
    expect(pg.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "false")

    lien = _commencer_la_designation(pg)
    expect(pg.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "true")
    pg.wait_for_function("""() => document.querySelector('#an-gauche').getBoundingClientRect().left === 0
      && !document.getAnimations().some((a) => a.playState === 'running')""")
    mode, annuler = pg.locator("#an-mini-mode"), pg.locator("#an-mini-annuler")
    expect(mode).to_be_visible()
    expect(annuler).to_be_visible()
    expect(pg.locator("#an-mini-titre")).to_be_hidden()
    # Des mots qui valent au doigt comme à la souris.
    expect(mode).to_have_text(re.compile(r"Désignez la zone liée\s*Annuler"))
    assert "Cliquez" not in mode.inner_text()
    assert "Cliquez" not in (pg.locator("#an-mini").get_attribute("title") or "")
    # Rien ne recouvre la minicarte, et elle n'a pas bougé.
    m, b = _boite(pg, "#an-mini"), _boite(pg, "#an-mini-mode")
    assert b["bas"] <= m["haut"] + .5, (b, m)
    assert abs(m["haut"] - mini_avant["haut"]) <= .5 and abs(m["h"] - mini_avant["h"]) <= .5
    if _AXE.is_file():
        viol = _audit(pg)
        assert not viol, _fmt(viol)
    # « Annuler » renonce, sans rien écrire, et rend le focus au bouton qui avait lancé le geste.
    ecrits = []
    pg.on("request", lambda r: ecrits.append(r.url) if r.method == "PUT" else None)
    annuler.tap()
    expect(lien).to_have_attribute("aria-pressed", "false")
    expect(pg.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "false")
    expect(mode).to_be_hidden()
    expect(lien).to_be_focused()
    assert pg.evaluate("() => !document.body.classList.contains('an-designer')")
    assert not ecrits
    # Après quoi la minicarte rechoisit des cases, et le titre revient à sa place.
    pg.locator("#an-tiroir-planche").tap()
    expect(pg.locator("#an-mini-titre")).to_be_visible()
    expect(pg.locator("#an-mini-titre")).to_have_text(re.compile("E2E annotation"))
    pg.locator('#an-mini .an-mz[data-case="1"]').tap()
    expect(pg.locator("#an-tete-case")).to_have_text("Case c2")


def test_telephone_annuler_le_lien_rend_la_feuille_et_le_focus(appareil, decor):
    """Au téléphone, la feuille s'efface le temps de désigner ; « Annuler » la rend, le focus
    sur « Désigner sur la planche », et Échap fait de même sans refermer la feuille rendue."""
    pg = appareil(TELEPHONE)
    _ouvrir(pg, decor, decor["bulle"])
    _ouvrir_la_feuille(pg)
    lien = _commencer_la_designation(pg)
    expect(pg.locator("#an-poser")).to_have_attribute("aria-expanded", "false")
    expect(pg.locator("#an-mini-annuler")).to_be_visible()
    pg.locator("#an-mini-annuler").tap()
    expect(pg.locator("#an-poser")).to_have_attribute("aria-expanded", "true")
    expect(pg.locator("#an-tiroir-planche")).to_have_attribute("aria-expanded", "false")
    expect(lien).to_have_attribute("aria-pressed", "false")
    expect(lien).to_be_focused()
    # Échap : la même chose.
    lien.tap()
    expect(pg.locator("#an-mini-annuler")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(pg.locator("#an-poser")).to_have_attribute("aria-expanded", "true")
    expect(lien).to_have_attribute("aria-pressed", "false")
    expect(lien).to_be_focused()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_feuille_couchee(appareil, decor, theme):
    """La feuille en deux colonnes, auditée ouverte."""
    if not _AXE.is_file():
        pytest.skip("axe absent (tests/js/vendor/axe.min.js)")
    pg = appareil(COUCHE[0])
    pg.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    _ouvrir(pg, decor, decor["bulle"])
    _ouvrir_la_feuille(pg)
    viol = _audit(pg)
    assert not viol, _fmt(viol)
