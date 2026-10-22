"""Le zoom d'interface du menu « Aa » ne fait sortir ni les tiroirs ni le menu de la fenêtre (UX-7).

`theme.js` règle ce zoom en posant `zoom` sur la racine (`applyZoom`), de 0,8 à 2. Mesuré le
2026-10-22 sous Chromium 151 et Firefox 153, à 320 × 640 : sous ce zoom, une unité de
FENÊTRE se calcule contre la fenêtre NON zoomée, puis le zoom la multiplie — `50vw` fait
224 px à l'écran sous 1,4, 320 sous 2. Les plafonds des tiroirs étaient en `vw` et la
hauteur de la coque de l'Atelier en `vh` : le tiroir des planches faisait 336 px pour 320
sous 1,4 et recouvrait le voile qui le referme, celui de structure débordait par la gauche
dès 1,2, et la coque, 896 px de haut sous 1,4, passait sous la fenêtre avec le bas des
tiroirs et la barre d'état. Le menu « Aa », lui, grandit avec ce qu'il règle : sous 1,8, A−
et ↺ — la seule façon de revenir en arrière — sortaient de l'Atelier, qui ne défile pas.

Ce que ces tests tiennent, chacun par une PROPRIÉTÉ et non par un nombre recopié de la
feuille :

- un tiroir ouvert reste dans la fenêtre et laisse une bande de voile qui le referme au
  clic ;
- là où son plafond le borne, sa largeur VISIBLE ne dépend plus du zoom. C'est ce qui fait
  tomber un plafond figé en pixels, que le zoom multiplierait comme il multipliait `vw` : un
  tel plafond peut tenir dans 320 px à un zoom et pas à l'autre, ou tenir aux deux — il ne
  peut pas rendre la même largeur aux deux ;
- le menu « Aa » ouvert tient dans la fenêtre, et A−, A+, ↺ s'atteignent en faisant défiler
  le menu SEUL, sur les cinq surfaces — puis ↺ ramène bien le zoom à 100 %.

**La hauteur des tests de tiroir est 900, pas 640, et c'est une limite écrite.** À 320 × 640
sous un zoom de 1,8 ou plus, les deux bandes et la barre d'état prennent à elles seules
toute la hauteur : `#body` y reçoit 30 px sous 1,8, 0 sous 2. C'est la « fenêtre plus basse
que le chrome » du `Reste` d'UX-7, qui attend une décision de forme ; ces tests ne la
tranchent pas. Le menu, lui, se mesure à 640 : c'est là que le défaut a été vu.

Le défilement de la page est évité exprès dans les mesures : `click()` de Playwright fait
défiler l'élément visé dans la vue, racine comprise malgré `overflow: hidden`, ce qu'aucun
doigt ne peut faire dans l'Atelier. Les gestes qui comptent passent donc par la souris, à
des coordonnées lues dans la page.
"""
# UX-10 — le menu « Aa » est injecté par `theme.js` sur les cinq surfaces : toutes sont
# auditées. Les tiroirs n'existent que dans l'Atelier, et leurs tests n'y vont que là.
SURFACES_AUDITEES = ("/", "/corpus", "/recherche", "/exploration", "/administration")
SURFACES_HORS_PERIMETRE = {}

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png         # noqa: E402

pytestmark = pytest.mark.e2e

TIROIRS = [("#btn-tiroir-nav", "#sidebar", "nav-ouverte"),
           ("#btn-tiroir-panneau", "#panel", "panneau-ouvert")]
SURFACES = list(SURFACES_AUDITEES)

BOITE = """(s) => { const b = document.querySelector(s).getBoundingClientRect();
  return {x: b.left, r: b.right, y: b.top, b: b.bottom, w: b.width}; }"""


@pytest.fixture
def album(live_server):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Zoom"}).json()["id"]
        c.post(f"/api/albums/{aid}/import",
               files={"file": ("p.png", make_png(), "image/png")})
    finally:
        c.close()
    return aid


def _ouvrir(page, url, zoom, largeur, hauteur):
    page.set_viewport_size({"width": largeur, "height": hauteur})
    page.add_init_script(f"try {{ localStorage.setItem('bd-zoom', '{zoom}') }} catch (e) {{}}")
    page.goto(url, wait_until="networkidle")
    # Le zoom a bien été POSÉ : sans lui, chaque test passerait à 100 % sans rien mesurer.
    pose = page.evaluate("document.documentElement.style.zoom")
    assert pose == ("" if zoom == "1" else zoom), f"zoom attendu {zoom}, posé « {pose} »"


def _ouvrir_tiroir(page, bascule):
    # La bascule est en haut de `#viewer` et dans la fenêtre : un clic à ses coordonnées,
    # pas `click()`, qui ferait défiler la racine (cf. la docstring).
    b = page.evaluate(BOITE, bascule)
    page.mouse.click((b["x"] + b["r"]) / 2, (b["y"] + b["b"]) / 2)
    page.wait_for_timeout(300)                     # la transition du tiroir


@pytest.mark.parametrize("zoom", ["1.4", "2"])
@pytest.mark.parametrize("bascule,tiroir,classe", TIROIRS)
def test_un_tiroir_ouvert_tient_dans_la_fenetre_et_le_voile_le_referme(
        live_server, page, album, bascule, tiroir, classe, zoom):
    _ouvrir(page, f"{live_server}/?album={album}", zoom, 320, 900)
    _ouvrir_tiroir(page, bascule)
    assert classe in (page.get_attribute("#body", "class") or ""), "le tiroir ne s'est pas ouvert"
    m = page.evaluate("""([T, boite]) => { const box = eval(boite); const t = box(T);
      const gauche = T === '#sidebar';
      const x = gauche ? (t.r + innerWidth) / 2 : t.x / 2;    // le milieu de la bande de voile
      const y = (t.y + t.b) / 2;
      const sous = document.elementFromPoint(x, y);
      return {t, fenetre: [innerWidth, innerHeight], x, y,
              bande: gauche ? innerWidth - t.r : t.x, sous: sous ? sous.id : null}; }""",
                      [tiroir, BOITE])
    t, (L, H) = m["t"], m["fenetre"]
    assert t["x"] >= -0.5 and t["r"] <= L + 0.5 and t["y"] >= -0.5 and t["b"] <= H + 0.5, (
        f"sous un zoom de {zoom}, {tiroir} sort de la fenêtre {L}×{H} : {t}")
    assert m["bande"] > 0 and m["sous"] == "tiroir-voile", (
        f"sous un zoom de {zoom}, {tiroir} ne laisse aucune bande de voile à toucher "
        f"(bande {m['bande']:.0f} px, sous le doigt : {m['sous']})")
    page.mouse.click(m["x"], m["y"])
    page.wait_for_timeout(300)
    assert classe not in (page.get_attribute("#body", "class") or ""), (
        f"sous un zoom de {zoom}, un clic sur le voile ne referme pas {tiroir}")


# Les zooms où le PLAFOND borne chaque tiroir à 320 px. Le tiroir des planches demande
# `--sidebar-w`, 240 px à 100 % : son plafond ne le borne que sous zoom. Celui de structure
# demande `--panel-w`, 300 px : son plafond le borne dès 100 %, et c'est ce qui permet à ce
# test de dire aussi que rien n'a changé à 100 %.
PLAFONNES = {"#sidebar": ["1.4", "2"], "#panel": ["1", "1.4", "2"]}


@pytest.mark.parametrize("bascule,tiroir,classe", TIROIRS)
def test_un_tiroir_plafonne_a_la_meme_largeur_visible_a_tout_zoom(
        live_server, page, album, bascule, tiroir, classe):
    largeurs = {}
    for zoom in PLAFONNES[tiroir]:
        _ouvrir(page, f"{live_server}/?album={album}", zoom, 320, 900)
        _ouvrir_tiroir(page, bascule)
        largeurs[zoom] = page.evaluate(BOITE, tiroir)["w"]
    assert max(largeurs.values()) - min(largeurs.values()) <= 1, (
        f"{tiroir} change de largeur visible avec le zoom, là où son plafond le borne : "
        f"{largeurs}. Un plafond en `vw` ou en pixels grandit avec le zoom ; un pourcentage "
        "de `#body`, la boîte du voile, ne grandit pas")


def _menu(page):
    """Le panneau « Aa » ouvert : sa boîte à l'ouverture, puis — défilé SEUL jusqu'à sa
    dernière rangée, celle du zoom — ce qui se trouve sous le centre de A−, A+ et ↺."""
    b = page.evaluate(BOITE, ".display-menu > button")
    page.mouse.click((b["x"] + b["r"]) / 2, (b["y"] + b["b"]) / 2)
    page.wait_for_timeout(200)
    return page.evaluate("""(boite) => { const box = eval(boite);
      const p = document.querySelector('.display-panel');
      const avant = box('.display-panel');
      p.scrollTop = p.scrollHeight;
      const boutons = {};
      for (const lab of ['Réduire le zoom', 'Augmenter le zoom', 'Zoom 100 %']) {
        const e = p.querySelector(`[aria-label="${lab}"]`); const r = e.getBoundingClientRect();
        const x = (r.left + r.right) / 2, y = (r.top + r.bottom) / 2;
        boutons[lab] = {x, y, touche: document.elementFromPoint(x, y) === e};
      }
      return {avant, fenetre: [innerWidth, innerHeight], boutons}; }""", BOITE)


def _dans_la_fenetre(m):
    p, (L, H) = m["avant"], m["fenetre"]
    return p["x"] >= -0.5 and p["r"] <= L + 0.5 and p["y"] >= -0.5 and p["b"] <= H + 0.5


@pytest.mark.parametrize("zoom", ["1.8", "2"])
@pytest.mark.parametrize("surface", SURFACES)
def test_le_menu_aa_tient_dans_la_fenetre_et_ramene_a_100(live_server, page, album, surface, zoom):
    _ouvrir(page, live_server + surface, zoom, 320, 640)
    m = _menu(page)
    assert _dans_la_fenetre(m), (
        f"{surface}, zoom {zoom} : le menu « Aa » sort de la fenêtre {m['fenetre']} : {m['avant']}")
    perdus = [lab for lab, v in m["boutons"].items() if not v["touche"]]
    assert not perdus, f"{surface}, zoom {zoom} : hors d'atteinte en faisant défiler le menu : {perdus}"
    r = m["boutons"]["Zoom 100 %"]
    page.mouse.click(r["x"], r["y"])
    assert page.evaluate("document.documentElement.style.zoom") == "", "↺ n'a pas ramené le zoom à 100 %"


def test_le_menu_aa_reste_dans_la_fenetre_quand_on_zoome_menu_ouvert(live_server, page, album):
    """A+ est DANS le menu : chaque clic l'agrandit sous le doigt. Borné à l'ouverture
    seulement, il ressortait de la fenêtre au deuxième clic."""
    _ouvrir(page, f"{live_server}/?album={album}", "1.6", 320, 640)
    m = _menu(page)
    assert _dans_la_fenetre(m)
    for attendu in ("1.7", "1.8", "1.9", "2"):
        page.evaluate("document.querySelector('.display-panel').scrollTop = 1e6")
        r = page.evaluate("""() => { const r = document.querySelector('[aria-label="Augmenter le zoom"]')
                                       .getBoundingClientRect();
                                     return {x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2}; }""")
        page.mouse.click(r["x"], r["y"])
        assert page.evaluate("document.documentElement.style.zoom") == attendu
        p = page.evaluate(BOITE, ".display-panel")
        assert p["b"] <= 640.5 and p["y"] >= -0.5, f"zoom {attendu}, menu ouvert : il sort de la fenêtre : {p}"


# ---------- Les modales, et les cadres d'une page qui défile (seconde passe, 2026-10-22) ----------
# Mêmes unités, même défaut. Toutes les modales vivent dans un voile `position: fixed;
# inset: 0` : leurs plafonds passent de `vw`/`vh` à un pourcentage de ce voile. Les cadres
# d'une page (le liste-et-fiche de la Bibliothèque et de l'Administration dans une fenêtre
# basse, le croisement, l'aperçu de la Recherche, une vignette) n'ont pas de conteneur à la
# taille de la fenêtre : ils prennent `--vh-visible` / `--vw-visible`, que `theme.js` dérive
# du zoom (cf. `:root` dans style.css). Mesuré avant : la fiche d'un album faisait 1 108 px
# de haut sous 1,4 dans une fenêtre de 900, titre et boutons hors champ, et le voile ne
# défile pas ; le Lexique sortait de 11 px par le haut sous 2 à 320 px.

MODALES = [
    # (surface, ce qui l'ouvre, la boîte, son titre, son dernier bouton)
    ("/corpus", "#btn-new", "#album-modal .modal-box", "#modal-title", "#m-cancel"),
    ("/exploration", "#btn-lexique", ".lexique-box", "#lexique-title", "#lex-close"),
]


@pytest.mark.parametrize("zoom", ["1.4", "2"])
@pytest.mark.parametrize("largeur", [320, 375, 768])
@pytest.mark.parametrize("surface,ouvre,boite,titre,dernier", MODALES,
                         ids=["fiche-album", "lexique"])
def test_une_modale_tient_dans_la_fenetre_et_tout_s_y_atteint(
        live_server, page, surface, ouvre, boite, titre, dernier, largeur, zoom):
    _ouvrir(page, live_server + surface, zoom, largeur, 900)
    page.click(ouvre)
    page.wait_for_selector(boite, state="visible")
    page.wait_for_timeout(200)
    m = page.evaluate("""([B, T, D, boite]) => { const box = eval(boite);
      const b = document.querySelector(B); const avant = box(B);
      // Défiler la BOÎTE seule, sans `scrollIntoView`, qui ferait aussi défiler la page sous
      // le voile : ce n'est pas un geste que la modale offre.
      const touche = (s) => { const e = document.querySelector(s); const r = e.getBoundingClientRect();
        return document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2) === e; };
      b.scrollTop = 0; const t = touche(T);
      b.scrollTop = b.scrollHeight; const d = touche(D);
      return {avant, fenetre: [innerWidth, innerHeight], titre: t, dernier: d}; }""", [boite, titre, dernier, BOITE])
    p, (L, H) = m["avant"], m["fenetre"]
    assert p["y"] >= -0.5 and p["b"] <= H + 0.5, f"{boite} sort de la fenêtre {L}×{H} par le haut ou le bas : {p}"
    # Le voile reste visible des deux côtés : c'est par lui qu'on referme d'un clic, et à
    # 100 % la boîte en laisse toujours une bande (8 % de la fenêtre en tout, ou plus).
    assert p["x"] >= 1 and p["r"] <= L - 1, f"{boite} touche les bords de la fenêtre {L} : {p}"
    assert m["titre"] and m["dernier"], (
        f"zoom {zoom}, {largeur} px : titre atteint={m['titre']}, dernier bouton atteint={m['dernier']}")


# Une fenêtre BASSE (sous 26.9375em de haut) : la page défile entière, et le cadre liste-et-
# fiche se compte sur la fenêtre (`calc(100vh - …)` avant, `--vh-visible` depuis). 420 px et
# non 400 : sous 1,4, le plancher de `.lf.bi` (22rem) donne 400 px à l'écran, et le test
# doit dire « tient », pas « tient au pixel près ». 768 px de large : sous 33em la page
# défait le cadre (une colonne, sans hauteur), et la règle ne s'applique plus.
@pytest.mark.parametrize("surface,cadre,propriete", [
    ("/corpus", "#biblio", "height"),
    ("/administration?vue=projets", "#projets-bloc", "minHeight"),
], ids=["bibliotheque", "administration"])
def test_dans_une_fenetre_basse_le_cadre_se_compte_sur_la_fenetre_visible(
        live_server, page, album, surface, cadre, propriete):
    _ouvrir(page, live_server + surface, "1.4", 768, 420)
    page.wait_for_selector(cadre, state="visible")
    m = page.evaluate("""([C, P]) => { const e = document.querySelector(C);
      return {v: parseFloat(getComputedStyle(e)[P]) * (e.currentCSSZoom || 1), h: innerHeight}; }""",
                      [cadre, propriete])
    assert 0 < m["v"] <= m["h"] + 0.5, (
        f"{surface} : sous un zoom de 1,4, {cadre} demande {m['v']:.0f} px de haut pour une "
        f"fenêtre de {m['h']} — une unité de fenêtre que le zoom a multipliée")


# Les quatre surfaces-documents : toutes sauf l'Atelier, coque fixe qui ne défile pas.
PAGES = [s for s in SURFACES_AUDITEES if s != "/"]


@pytest.mark.parametrize("zoom", ["1.4", "2"])
@pytest.mark.parametrize("surface", PAGES)
def test_la_page_s_atteint_jusqu_en_bas_sous_le_zoom(live_server, page, album, surface, zoom):
    """Ce qui défile — le document à 320 px, la coque au-dessus — tient dans la fenêtre, et
    le bas de la coque s'y atteint en le faisant défiler, lui seul. Ce qui défile DANS la
    coque (une liste dans son cadre) a son propre défilement et n'est pas mesuré ici."""
    _ouvrir(page, live_server + surface, zoom, 320, 900)
    page.wait_for_timeout(300)
    m = page.evaluate("""() => {
      const coque = document.querySelector('#corpus-app, #admin-app, #search-app, #explo-app');
      const docDefile = getComputedStyle(document.documentElement).overflowY === 'visible';
      const defile = docDefile ? document.scrollingElement : coque;
      defile.scrollTop = defile.scrollHeight;
      const r = coque.getBoundingClientRect();
      return {docDefile, haut: r.top, bas: r.bottom, h: innerHeight}; }""")
    assert m["bas"] <= m["h"] + 0.5, (
        f"{surface}, zoom {zoom} : défilée jusqu'au bout, la page finit encore à {m['bas']:.0f} px "
        f"pour une fenêtre de {m['h']}")
    if not m["docDefile"]:
        assert m["haut"] >= -0.5, f"{surface}, zoom {zoom} : la coque qui défile sort par le haut : {m}"
