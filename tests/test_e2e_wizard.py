"""UX-6 — « Par où commencer », joué dans un vrai navigateur, dans un bac à sable.

La forme a été tranchée par Hugo sur maquette le 2026-11-02 (`pilotage/UX-6.md`) : un
ALBUM de présentation qui s'ouvre seul après « Mon bac à sable », avec « Passer » et
« Fermer ✕ », dont la dernière page fait choisir un parcours ; le souvenir — l'album vu, le
parcours, l'étape — vit dans le navigateur, rangé par login et sous l'identifiant du bac à
sable (Hugo, 2026-11-03). Après le choix d'un parcours, la VISITE des pages, dans une
fenêtre posée à côté des zones — le reste assombri et `inert`, les zones jouables, deux
temps par page de plusieurs zones —, puis la CARTE des étapes. Le « ? » de la bande rouvre
les repères de la page où l'on est, sur les six surfaces et pour tout compte.

Chaque test mesure ce que l'écran MONTRE (visible d'abord : `to_have_text` lit aussi un
élément caché) et ce que le navigateur RETIENT (le stockage local), sous camille, une
arrivante sans autre projet, et dominique, invitée chez elle.

Le harnais neutralise l'ouverture seule de l'album pour toute la suite (`tests/conftest.py`,
`BD_SANS_WIZARD`) : les tests qui la jouent demandent `wizard_actif`.
"""
import json
import re

import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from test_e2e_bac_a_sable import (CAMILLE, DOMINIQUE, _api, _inviter, _ouvrir,  # noqa: E402,F401
                                  _sous, jeu, pytestmark_proxy)

pytestmark = pytest.mark.e2e

# Les six surfaces, avec le titre que la fenêtre leur donne : le « ? » se joue sur chacune
# (l'album, la visite et le guide sur celles où ils mènent).
SURFACES_AUDITEES = {"/": "Atelier", "/annotation": "Annotation", "/corpus": "Bibliothèque",
                     "/recherche": "Recherche", "/exploration": "Exploration",
                     "/administration": "Administration"}
SURFACES_HORS_PERIMETRE = {}

SOUVENIR = "() => { try { return localStorage.getItem('bd-wizard'); } catch (e) { return null; } }"


def _album(page):
    voile = page.locator("#wizard-modal")
    expect(voile).to_be_visible()
    return voile


def _visite(page):
    fen = page.locator("#wizard-fenetre")
    expect(fen).to_be_visible()
    return fen


def _souvenir(page):
    brut = page.evaluate(SOUVENIR)
    return json.loads(brut) if brut else None


def _arriver(page, base):
    """L'Atelier, et l'attente de ce qui décide de l'album : la ligne du bac à sable, puis
    le script qui a tranché — ouvert seul ou non. Une absence constatée avant lui ne
    prouverait rien. Attente en forme FONCTION : la CSP refuse l'`eval` d'une expression."""
    page.goto(base + "/", wait_until="domcontentloaded")
    expect(page.locator("#bac-ligne")).to_be_visible()
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")


@pytestmark_proxy
def test_l_album_s_ouvre_seul_et_se_feuillette(page, jeu, wizard_actif):
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    album = _album(page)
    expect(album.locator("#wizard-titre")).to_have_text("Bienvenue dans BéDéditeur")
    expect(album.locator(".wizard-boite")).to_have_attribute("role", "dialog")
    compte = album.locator("#wizard-compte")
    expect(compte).to_have_text("1 / 8")
    expect(album.locator("#wizard-prec")).to_be_disabled()
    album.locator("#wizard-suiv").click()
    expect(compte).to_have_text("2 / 8")
    titre = album.locator(".wizard-page h3")
    expect(titre).to_be_visible()
    expect(titre).to_have_text("Constituez votre corpus")
    # Le focus reste sur le bouton pressé, et les flèches tournent aussi les pages.
    expect(album.locator("#wizard-suiv")).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(compte).to_have_text("3 / 8")
    page.keyboard.press("ArrowLeft")
    expect(compte).to_have_text("2 / 8")
    # « Passer » mène au choix du parcours, où « Suivant » et « Passer » ne sont plus.
    album.locator("#wizard-passer").click()
    expect(compte).to_have_text("8 / 8")
    expect(album.locator("#wizard-choix-rapide")).to_be_focused()
    expect(album.locator("#wizard-suiv")).to_have_count(0)
    expect(album.locator("#wizard-passer")).to_have_count(0)
    expect(album.locator(".wizard-page h3")).to_have_text("Essayez sur une vraie planche")
    # Fermer sans rien choisir ne vaut pas renoncement : rien n'est retenu, il revient.
    album.locator("#wizard-fermer").click()
    expect(page.locator("#wizard-modal")).to_be_hidden()
    assert _souvenir(page) is None
    _arriver(page, jeu["base"])
    expect(_album(page).locator("#wizard-compte")).to_have_text("1 / 8")
    # Échap le ferme aussi, et le focus ne se perd pas sur la page.
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-modal")).to_be_hidden()
    assert page.evaluate("""() => { const a = document.activeElement;
      return !!a && a !== document.body && !a.closest('#wizard-modal'); }""")
    assert bac["id"]


@pytestmark_proxy
def test_choisir_un_parcours_mene_a_la_carte_et_l_album_ne_revient_plus(page, jeu, wizard_actif):
    bac = _ouvrir(jeu, CAMILLE)
    parcours = next(j for j in bac["jeu"] if j["role"] == "pas-a-pas")
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    album = _album(page)
    album.locator("#wizard-passer").click()
    album.locator("#wizard-choix-rapide").click()
    # La visite des pages passe avant le parcours (Hugo, 2026-11-02) ; la passer mène aux
    # gestes : le guide, sur la page de la première étape ; ☰ y ouvre la carte des étapes.
    expect(_visite(page).locator("#wizard-visite-compte")).to_have_text("Visite 1 / 7")
    expect(page.locator("#wizard-modal")).to_be_hidden()
    page.locator("#wizard-visite-passer").click()
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Tracer une zone", timeout=15000)
    expect(page).to_have_url(re.compile(r"mode=edition"))
    page.locator("#wizard-guide-carte").click()
    album = _album(page)
    expect(album.locator("#wizard-titre")).to_have_text("Par où commencer")
    etapes = album.locator(".wizard-etapes > li")
    expect(etapes).to_have_count(4)
    expect(etapes.nth(0)).to_have_attribute("aria-current", "step")
    liens = album.locator(".wizard-etapes a")
    expect(liens.nth(0)).to_be_focused()
    expect(liens.nth(0)).to_have_text("Tracer une zone")
    attendu = f"/?album={parcours['album_id']}&planche={parcours['planche_ids'][0]}"
    assert liens.nth(0).get_attribute("href") == attendu + "&mode=edition"
    assert liens.nth(3).get_attribute("href") == attendu.replace("/?", "/annotation?")
    assert _souvenir(page) == {"camille": {"bac": bac["id"], "efface_le": bac["efface_le"],
                                           "album_vu": True, "parcours": "rapide", "etape": 0}}
    # Une étape mène à sa surface et à son outil ; l'étape est retenue.
    liens.nth(2).click()
    page.wait_for_url(re.compile(r"mode=transcription"))
    expect(page.locator("#bac-ligne")).to_be_visible()
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    expect(page.locator("#bac-commencer")).to_be_visible()
    expect(page.locator("#wizard-modal")).to_have_count(0)
    assert _souvenir(page)["camille"]["etape"] == 2
    # Le guide s'ouvre sur l'étape, sur sa page ; Échap le quitte.
    expect(_visite(page).locator("#wizard-fenetre-titre")).to_have_text("Transcrire et relire")
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    # « Par où commencer » rouvre la CARTE, sur l'étape où l'on est.
    page.locator("#bac-commencer").click()
    album = _album(page)
    expect(album.locator("#wizard-titre")).to_have_text("Par où commencer")
    expect(album.locator(".wizard-etapes > li").nth(2)).to_have_attribute("aria-current", "step")
    # Passer au parcours complet garde l'étape : « Transcrire et relire » est la 6e.
    album.locator("#wizard-changer").click()
    etapes = album.locator(".wizard-etapes > li")
    expect(etapes).to_have_count(9)
    expect(etapes.nth(5)).to_have_attribute("aria-current", "step")
    expect(album.locator("#wizard-changer")).to_have_text("Passer au parcours rapide")
    album.locator("#wizard-fermer").click()
    expect(page.locator("#bac-commencer")).to_be_focused()


@pytestmark_proxy
def test_ne_plus_afficher_tient_et_la_remise_a_neuf_fait_repartir_du_debut(page, jeu, wizard_actif):
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    album = _album(page)
    album.locator("#wizard-passer").click()
    album.locator("#wizard-jamais").check()
    album.locator("#wizard-fermer").click()
    assert _souvenir(page)["camille"]["album_vu"] is True
    _arriver(page, jeu["base"])
    expect(page.locator("#bac-commencer")).to_be_visible()
    expect(page.locator("#wizard-modal")).to_have_count(0)
    # Le bac à sable remis à neuf (un nouvel identifiant) : le souvenir de l'ancien ne vaut
    # plus, et l'album s'ouvre de nouveau seul.
    neuf = _api(jeu["base"], CAMILLE, "POST", "/api/bac-a-sable/remise-a-neuf")
    assert neuf["id"] != bac["id"]
    _arriver(page, jeu["base"])
    expect(_album(page).locator("#wizard-compte")).to_have_text("1 / 8")
    assert _souvenir(page)["camille"]["bac"] == bac["id"]       # rien d'écrit pour le neuf
    page.locator("#wizard-passer").click()
    page.locator("#wizard-choix-complet").click()
    assert _souvenir(page)["camille"] == {"bac": neuf["id"], "efface_le": neuf["efface_le"],
                                          "album_vu": True, "parcours": "complet", "etape": 0}


@pytestmark_proxy
def test_le_harnais_neutralise_l_ouverture_seule_pas_le_bouton(page, jeu):
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    bouton = page.locator("#bac-commencer")
    expect(bouton).to_be_visible()
    expect(page.locator("#wizard-modal")).to_have_count(0)
    # Premier geste de la ligne.
    expect(page.locator("#bac-ligne .bac-gestes > button").first).to_have_text("Par où commencer")
    bouton.click()
    album = _album(page)
    expect(album.locator("#wizard-titre")).to_have_text("Bienvenue dans BéDéditeur")
    expect(bouton).to_have_attribute("aria-expanded", "true")
    album.locator("#wizard-fermer").click()
    expect(bouton).to_have_attribute("aria-expanded", "false")
    expect(bouton).to_be_focused()


@pytestmark_proxy
def test_chez_un_autre_le_wizard_ne_s_ouvre_pas(page, jeu, wizard_actif):
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, DOMINIQUE)
    _arriver(page, jeu["base"])
    expect(page.locator("#bac-ligne .bac-nom")).to_have_text("Bac à sable de camille")
    expect(page.locator("#bac-commencer")).to_have_count(0)
    expect(page.locator("#wizard-modal")).to_have_count(0)
    assert _souvenir(page) is None


# ── La fenêtre sur la zone : la visite des pages et le « ? » ───────────────────────────
#
# Ce n'est pas une modale (case « La fenêtre sur la zone se dessine au clavier ») : les zones
# du temps restent jouables, tout le reste est `inert`, et le focus y entre et en sort sans
# piège. Les états se lisent dans le DOM — `inert` hérité, l'élément focalisé —, jamais dans
# l'image de l'assombri.

VISITE_SESSION = ("() => { try { return sessionStorage.getItem('bd-wizard-visite'); } "
                  "catch (e) { return null; } }")
INERTE = "(sel) => { const e = document.querySelector(sel); return !!e && !!e.closest('[inert]'); }"
OU_EST_LE_FOCUS = """() => {
  const a = document.activeElement;
  if (!a || a === document.body) return { corps: true, zone: null, fenetre: false, inerte: false };
  const z = a.closest('[data-parcours]');
  return { corps: false, zone: z ? z.dataset.parcours : null,
           fenetre: !!a.closest('#wizard-fenetre'), inerte: !!a.closest('[inert]') };
}"""
VISIBLE = """(m) => [...document.querySelectorAll(`[data-parcours="${m}"]`)].some((e) => {
  const r = e.getBoundingClientRect();
  return r.width >= 1 && r.height >= 1 && getComputedStyle(e).visibility !== 'hidden'; })"""
ETAT_PAGE = """() => { const b = document.querySelector('.mode-btn[aria-pressed="true"]');
  return { adresse: location.href, mode: b ? b.dataset.mode : null }; }"""


def _commencer_la_visite(page, jeu):
    """camille dans son bac à sable, l'Atelier ; « Par où commencer », « Passer », le
    parcours rapide : la visite commence là où l'on est."""
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    album = _album(page)
    album.locator("#wizard-passer").click()
    album.locator("#wizard-choix-rapide").click()
    return bac


@pytestmark_proxy
def test_la_fenetre_sur_la_zone_au_clavier_et_en_deux_temps(page, jeu):
    _commencer_la_visite(page, jeu)
    fen = _visite(page)
    compte, titre = page.locator("#wizard-visite-compte"), page.locator("#wizard-fenetre-titre")
    expect(compte).to_have_text("Visite 1 / 7")
    expect(titre).to_have_text("La barre du haut")
    expect(titre).to_be_focused()
    expect(page.locator("#wizard-modal")).to_be_hidden()
    # Pas une modale : ni rôle de dialogue, ni `aria-modal`.
    assert fen.get_attribute("role") is None and fen.get_attribute("aria-modal") is None
    expect(page.locator("#wizard-zones .wf-zone b")).to_have_text(
        ["Les six pages", "Le projet", "Votre compte", "Aa", "?", "Votre bac à sable"])
    # La barre du haut est jouable, la bande des outils et la page ne le sont plus.
    assert page.evaluate(INERTE, "#header") and page.evaluate(INERTE, "#sidebar")
    assert not page.evaluate(INERTE, ".surf-nav") and not page.evaluate(INERTE, "#bac-ligne")

    # « Suivant » : l'Atelier, au premier temps — la fenêtre à droite, le titre focalisé.
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 2 / 7 · 1 / 2")
    expect(titre).to_have_text("Atelier")
    expect(titre).to_be_focused()
    expect(fen).not_to_have_class(re.compile(r"\bgauche\b"))
    a_droite = fen.bounding_box()
    assert page.evaluate(INERTE, "#panel") and not page.evaluate(INERTE, "#sidebar")
    assert page.evaluate(INERTE, ".surf-nav")
    # La zone est JOUABLE : un clic sur un mode le change.
    edition = page.locator('.mode-btn[data-mode="edition"]')
    edition.click()
    expect(edition).to_have_attribute("aria-pressed", "true")
    page.locator('.mode-btn[data-mode="navigation"]').click()
    # Un repère se choisit dans la liste, sans que la fenêtre bouge.
    planche = page.locator('#wizard-zones .wf-zone[data-zone="atelier-planche"]')
    planche.click()
    expect(planche).to_have_attribute("aria-pressed", "true")
    assert fen.bounding_box() == a_droite

    # « Suivant » : le second temps, la fenêtre passe à gauche ; le focus reste sur le bouton.
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 2 / 7 · 2 / 2")
    expect(fen).to_have_class(re.compile(r"\bgauche\b"))
    expect(page.locator("#wizard-visite-suiv")).to_be_focused()
    # Le second temps éclaire d'emblée sa première zone (la maquette).
    expect(page.locator('#wizard-zones .wf-zone[data-zone="atelier-structure"]')).to_have_attribute(
        "aria-pressed", "true")
    a_gauche = fen.bounding_box()
    assert a_gauche["x"] < a_droite["x"]
    assert not page.evaluate(INERTE, "#panel") and page.evaluate(INERTE, "#sidebar")
    # Jamais au survol : le pointeur qui passe sur les zones ne la déplace pas.
    for sel in ("#panel", "#viewer", "#sidebar"):
        b = page.locator(sel).bounding_box()
        page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        page.wait_for_timeout(100)
        assert fen.bounding_box() == a_gauche, sel

    # Le clavier : Maj+Tab depuis la fenêtre entre dans une zone du temps ; Tab en revient,
    # sans jamais s'arrêter sur un élément inerte.
    titre.focus()
    page.keyboard.press("Shift+Tab")
    ou = page.evaluate(OU_EST_LE_FOCUS)
    assert ou["zone"] in ("atelier-structure", "atelier-actions") and not ou["inerte"], ou
    for _ in range(80):
        page.keyboard.press("Tab")
        ou = page.evaluate(OU_EST_LE_FOCUS)
        assert not ou["inerte"], ou
        assert ou["fenetre"] or ou["zone"] in ("atelier-structure", "atelier-actions"), ou
        if ou["fenetre"]:
            break
    else:
        pytest.fail("Tab ne revient pas de la zone à la fenêtre")

    # Échap : la fenêtre part, plus rien n'est inerte, le focus revient à « Par où
    # commencer », et la visite est oubliée.
    page.keyboard.press("Escape")
    expect(fen).to_be_hidden()
    for sel in ("#header", "#sidebar", "#panel", ".surf-nav"):
        assert not page.evaluate(INERTE, sel), sel
    expect(page.locator("#bac-commencer")).to_be_focused()
    assert page.evaluate(VISITE_SESSION) is None


@pytestmark_proxy
def test_la_visite_traverse_les_pages_et_finit_sur_la_carte(page, jeu):
    bac = _commencer_la_visite(page, jeu)
    parcours = next(j for j in bac["jeu"] if j["role"] == "pas-a-pas")
    compte = page.locator("#wizard-visite-compte")
    expect(compte).to_have_text("Visite 1 / 7")
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 2 / 7 · 1 / 2")
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 2 / 7 · 2 / 2")
    # La page suivante est une autre surface : on y va, sur la planche du parcours, et la
    # visite y reprend.
    page.locator("#wizard-visite-suiv").click()
    page.wait_for_url(re.compile(r"/annotation\?"))
    assert f"album={parcours['album_id']}" in page.url
    assert f"planche={parcours['planche_ids'][0]}" in page.url
    expect(compte).to_have_text("Visite 3 / 7 · 1 / 2")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Annotation")
    expect(page.locator("#wizard-fenetre-titre")).to_be_focused()
    # « ← » revient d'où l'on vient : l'Atelier, à son second temps.
    page.locator("#wizard-visite-prec").click()
    page.wait_for_url(re.compile(r"/\?album="))
    expect(compte).to_have_text("Visite 2 / 7 · 2 / 2")
    expect(page.locator("#wizard-fenetre")).to_have_class(re.compile(r"\bgauche\b"))

    # Arrivé ailleurs que là où la visite mène — un lien suivi en route —, elle s'arrête.
    page.goto(jeu["base"] + "/recherche", wait_until="domcontentloaded")
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    expect(page.locator("#wizard-fenetre")).to_have_count(0)
    assert page.evaluate(VISITE_SESSION) is None

    # La dernière page : « Commencer → » mène aux gestes — le guide, sur la première étape
    # du parcours, sur sa page.
    page.evaluate("(v) => sessionStorage.setItem('bd-wizard-visite', JSON.stringify(v))",
                  {"login": "camille", "bac": bac["id"], "efface_le": bac["efface_le"],
                   "page": 6, "temps": 0})
    page.goto(jeu["base"] + "/administration?vue=instance", wait_until="domcontentloaded")
    expect(compte).to_have_text("Visite 7 / 7")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Administration")
    suivant = page.locator("#wizard-visite-suiv")
    expect(suivant).to_have_text("Commencer →")
    suivant.click()
    titre = page.locator("#wizard-fenetre-titre")
    expect(titre).to_have_text("Tracer une zone", timeout=15000)
    expect(page).to_have_url(re.compile(r"/\?album=.*mode=edition"))
    expect(page.locator("#wizard-guide-compte")).to_have_text("1 / 4")
    expect(titre).to_be_focused()
    assert page.evaluate(VISITE_SESSION) is None
    # ☰ ouvre la carte, qui repropose la visite.
    page.locator("#wizard-guide-carte").click()
    album = _album(page)
    expect(album.locator("#wizard-titre")).to_have_text("Par où commencer")
    expect(album.locator("#wizard-revoir-visite")).to_have_text("Revoir les pages")
    album.locator("#wizard-revoir-visite").click()
    page.wait_for_url(re.compile(r"/\?album="))
    expect(compte).to_have_text("Visite 1 / 7")


TITRES = SURFACES_AUDITEES


def test_le_point_d_interrogation_rouvre_les_reperes_sur_les_six_surfaces(page, live_server):
    """Pour tout compte — ici le mono-poste, sans bac à sable : le « ? » est juste avant
    « Aa », son nom est la phrase de l'infobulle ; il ouvre les repères de la page où l'on
    est, ne nomme que ce qu'elle montre, et ne change ni l'adresse ni le mode ; Échap rend
    le focus au « ? »."""
    for surface, titre in TITRES.items():
        page.goto(live_server + surface, wait_until="domcontentloaded")
        aide = page.locator("#site-nav > .bande-aide")
        expect(aide).to_be_visible()
        expect(aide).to_have_text("?")
        expect(aide).to_have_attribute("aria-label", "Revoir les repères de cette page")
        expect(aide).to_have_attribute("title", "Revoir les repères de cette page")
        assert aide.get_attribute("aria-expanded") is None
        assert page.evaluate("""() => {
          const a = document.querySelector('#site-nav > .bande-aide');
          return a.nextElementSibling === document.querySelector('#site-nav > .display-menu'); }""")
        page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
        if surface == "/exploration":
            # L'Exploration écrit son état dans l'adresse à sa première exécution, après ses
            # lectures : lue avant, l'adresse « change » sans que le « ? » y soit pour rien.
            page.wait_for_url(re.compile(r"[?&]vue="))
        avant = page.evaluate(ETAT_PAGE)
        aide.click()
        fen = _visite(page)
        expect(page.locator("#wizard-visite-compte")).to_have_text("Cette page")
        expect(page.locator("#wizard-fenetre-titre")).to_have_text(titre)
        expect(page.locator("#wizard-fenetre-titre")).to_be_focused()
        marques = page.locator("#wizard-zones .wf-zone").evaluate_all(
            "(bs) => bs.map((b) => b.dataset.zone)")
        assert marques, surface
        for m in marques:
            assert page.evaluate(VISIBLE, m), (surface, m)
        # La barre du haut n'est pas un repère de la page : elle est inerte, « ? » compris.
        assert page.evaluate(INERTE, "#site-nav > .bande-aide"), surface
        if surface == "/":
            # Deux temps sur l'Atelier : « → » passe au second, la fenêtre change de côté.
            page.locator("#wizard-reperes-suiv").click()
            expect(fen).to_have_class(re.compile(r"\bgauche\b"))
            expect(page.locator("#wizard-reperes-prec")).to_be_enabled()
        page.keyboard.press("Escape")
        expect(fen).to_be_hidden()
        expect(aide).to_be_focused()
        assert not page.evaluate(INERTE, "#site-nav > .bande-aide")
        assert page.evaluate(ETAT_PAGE) == avant, surface


# ── Accessibilité et petites fenêtres ──────────────────────────────────────────────────

@pytestmark_proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_l_album_et_la_carte(page, jeu, theme):
    """axe (WCAG 2.1 AA), album ouvert sur sa première page, sur la page du choix, la
    visite qui suit le choix, le guide qui la suit, puis la carte des étapes : aucune
    violation sérieuse ou critique."""
    from test_e2e_bac_a_sable import _audit_axe
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    _album(page)
    rapports = []
    for quoi, geste in (("album, première page", None),
                        ("album, choix du parcours", "#wizard-passer"),
                        ("visite, première page", "#wizard-choix-complet"),
                        ("visite, l'Atelier", "#wizard-visite-suiv"),
                        ("guide, première étape", "#wizard-visite-passer"),
                        ("carte des étapes", "#wizard-guide-carte")):
        if geste:
            page.locator(geste).click()
        if geste == "#wizard-visite-passer":
            # Passer la visite mène à la page de l'étape, où le guide s'ouvre.
            expect(page.locator("#wizard-guide-compte")).to_be_visible(timeout=15000)
        page.wait_for_timeout(250)
        v, f = _audit_axe(page)
        if v:
            rapports.append(f"{quoi} :\n{f}")
    assert not rapports, "\n".join(rapports)


@pytestmark_proxy
def test_l_album_et_la_carte_tiennent_a_320_px_sous_grande_police(page, jeu):
    """À 320 px, sous des préférences de 16 et 24 : l'album, la fenêtre de la visite et la
    carte ne perdent rien et ne s'écrasent pas, et la ligne qui porte « Par où commencer »
    non plus."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    from test_e2e_bac_a_sable import _perdus, _preference_police
    from tools.mesurer_reflow import ECRASEMENT, decrire_ecrasement
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    echecs = []
    for police in (16, 24):
        _preference_police(page, police)
        page.set_viewport_size({"width": 320, "height": 800})
        _arriver(page, jeu["base"])
        # `#canvas` est la surface de pan de l'Atelier, exemptée par décision écrite
        # (`EXEMPTIONS` de test_e2e_reflow) : il prend la largeur de la planche dès qu'elle
        # arrive, si bien que cette ligne échouait ou non selon l'image, avant ou après la
        # mesure (2026-11-04, poste et image).
        perdus = [c for c in _perdus(page) if c["id"] != "canvas"]
        if perdus:
            echecs.append(f"ligne, police {police} : {perdus[:3]}")
        page.locator("#bac-commencer").click()
        _album(page)
        for quoi, geste, boite in (("album", None, ".wizard-boite"),
                                   ("choix", "#wizard-passer", ".wizard-boite"),
                                   ("visite", "#wizard-choix-rapide", "#wizard-fenetre"),
                                   ("guide", "#wizard-visite-passer", "#wizard-fenetre"),
                                   ("carte", "#wizard-guide-carte", ".wizard-boite")):
            if geste:
                page.locator(geste).click()
            if geste == "#wizard-visite-passer":
                # La page de l'étape se charge, et le guide s'y ouvre.
                expect(page.locator("#wizard-guide-compte")).to_be_visible(timeout=15000)
            page.wait_for_timeout(250)
            perdus = _perdus(page)
            if perdus:
                echecs.append(f"{quoi}, police {police} : {perdus[:3]}")
            ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, boite))
            if ecrase:
                echecs.append(f"{quoi}, police {police} : ÉCRASÉ\n" + "\n".join(ecrase))
        page.keyboard.press("Escape")
        expect(page.locator("#wizard-modal")).to_be_hidden()
        # La carte est retenue, le guide ouvert dans l'onglet : le tour suivant repart d'un
        # souvenir neuf.
        page.evaluate("""() => { try { localStorage.removeItem('bd-wizard');
                                       sessionStorage.removeItem('bd-wizard-guide'); }
                                 catch (e) {} }""")
    assert not echecs, "\n".join(echecs)


# ── Le guide, étape par étape (tranche 3) ──────────────────────────────────────────────
#
# Une étape faite se voit sur la planche, sans coche à déclarer (Hugo, 2026-11-02) : le
# geste se fait pour de vrai, sur la planche du parcours, et le guide le lit.

# Le jeu de la maquette, en petit : une seule rangée découpée — une case, deux bulles dont
# l'une trop petite — sur une planche de 400 × 500 ; le reste est à tracer.
JEU_DECOUPE = [{
    "cle": "parcours", "titre": "Le parcours", "role": "pas-a-pas", "rang": 1,
    "cran": "decoupage",
    "planches": [{"fichier": "p1.png", "regions": [
        {"type": "case", "x": 10, "y": 300, "w": 180, "h": 190, "enfants": [
            {"type": "bulle", "x": 20, "y": 310, "w": 100, "h": 30},
            {"type": "bulle", "x": 130, "y": 312, "w": 40, "h": 18}]}]}]}]


@pytest.fixture
def jeu_decoupe(live_server, tmp_path):
    from test_e2e_bac_a_sable import _outil
    from test_jeu import ecrire_jeu
    depot = ecrire_jeu(tmp_path / "jeu-depot", JEU_DECOUPE, images=("p1.png",))
    _outil(tmp_path, "tools/preparer_jeu.py", "--depot", str(depot), "--appliquer")
    _api(live_server, CAMILLE, "GET", "/api/moi")
    return {"base": live_server, "tmp": tmp_path}


def _au_guide(page, jeu, parcours="rapide"):
    """camille dans son bac à sable : « Par où commencer », le parcours, la visite passée —
    le guide s'ouvre sur la première étape, sur sa page."""
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    album = _album(page)
    album.locator("#wizard-passer").click()
    album.locator(f"#wizard-choix-{parcours}").click()
    _visite(page)
    page.locator("#wizard-visite-passer").click()
    expect(page.locator("#wizard-guide-compte")).to_be_visible(timeout=15000)
    expect(page.locator("#wizard-fenetre-titre")).to_be_focused()
    return bac


def _ecran(page, mx, my):
    """Un point de la planche (pixels master, planche de 400 px de large) à l'écran."""
    b = page.locator("#planche-img").bounding_box()
    k = b["width"] / 400
    return b["x"] + mx * k, b["y"] + my * k


def _glisser(page, de, a, maj=False):
    with page.expect_response(lambda r: r.url.endswith("/regions")
                              and r.request.method == "POST") as rep:
        if maj:
            page.keyboard.down("Shift")
        page.mouse.move(*_ecran(page, *de))
        page.mouse.down()
        page.mouse.move(*_ecran(page, *a), steps=6)
        page.mouse.up()
        if maj:
            page.keyboard.up("Shift")
    return rep.value.json()


@pytestmark_proxy
def test_le_guide_lit_sur_la_planche_le_geste_fait(page, jeu_decoupe):
    _au_guide(page, jeu_decoupe)
    titre, fait = page.locator("#wizard-fenetre-titre"), page.locator("#wizard-guide-fait")
    suivant = page.locator("#wizard-guide-suiv")
    expect(titre).to_have_text("Tracer une zone")
    expect(page.locator("#wizard-guide-compte")).to_have_text("1 / 4")
    # Le jeu a découpé une rangée : la phrase de Hugo le dit. Rien n'est fait.
    expect(page.locator("#wizard-fenetre .wf-phrase")).to_contain_text("Seule la dernière rangée")
    expect(fait).to_be_hidden()
    expect(suivant).to_have_text("Passer →")
    # Pas une modale, et la planche est jouable : on y trace une case, à la souris…
    assert not page.evaluate(INERTE, "#stage") and page.evaluate(INERTE, "#sidebar")
    case = _glisser(page, (220, 40), (380, 260))
    assert (case["type"], case["source"]) == ("case", "manuel"), case
    expect(page.locator("#wizard-fenetre .wf-phrase")).to_contain_text("Sa bulle non plus")
    expect(fait).to_be_hidden()
    # … puis une bulle dedans, Maj+glisser : l'étape est faite, sans rien déclarer.
    bulle = _glisser(page, (240, 60), (330, 110), maj=True)
    assert (bulle["type"], bulle["parent_id"]) == ("bulle", case["id"]), bulle
    expect(fait).to_be_visible()
    expect(fait).to_have_text("✓ Fait")
    expect(suivant).to_have_text("Suivant →")
    expect(suivant).to_have_class(re.compile(r"\bprimary\b"))
    # Le guide ne passe pas seul à la suite.
    expect(titre).to_have_text("Tracer une zone")

    # « Corriger » : la planche se rapproche de la plus petite bulle du jeu, choisie.
    zoom = page.locator("#zoom-level")
    entier = zoom.inner_text()
    suivant.click()
    expect(titre).to_have_text("Corriger le découpage")
    expect(page.locator("#wizard-guide-compte")).to_have_text("2 / 4")
    expect(zoom).not_to_have_text(entier)
    assert int(zoom.inner_text().rstrip(" %")) > int(entier.rstrip(" %"))
    regions = _api(jeu_decoupe["base"], CAMILLE, "GET",
                   "/api/planches/" + re.search(r"planche=(\d+)", page.url).group(1) + "/regions")
    petite = next(r for r in regions if r["type"] == "bulle" and r["w"] == 40)
    expect(page.locator("#region-id")).to_have_text(f"#{petite['id']}")
    expect(fait).to_be_hidden()
    # Le cadre repris à la poignée : fait.
    poignee = page.locator('rect.handle[data-handle="e"]').bounding_box()
    x, y = poignee["x"] + poignee["width"] / 2, poignee["y"] + poignee["height"] / 2
    with page.expect_response(lambda r: f"/api/regions/{petite['id']}" in r.url
                              and r.request.method == "PUT") as rep:
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 40, y, steps=5)
        page.mouse.up()
    assert rep.value.json()["source"] == "corrige"
    expect(fait).to_have_text("✓ Fait")
    expect(page.locator("#wizard-fenetre .wf-phrase")).to_contain_text("huit poignées")
    # En sortant de l'étape, la planche revient entière.
    page.locator("#wizard-guide-prec").click()
    expect(titre).to_have_text("Tracer une zone")
    expect(zoom).to_have_text(entier)
    # La carte dit ce qui est fait.
    page.locator("#wizard-guide-carte").click()
    album = _album(page)
    etapes = album.locator(".wizard-etapes > li")
    expect(etapes.nth(0).locator(".wizard-n")).to_have_text("✓")
    expect(etapes.nth(1).locator(".wizard-n")).to_have_text("✓")
    expect(etapes.nth(1).locator(".wizard-fait")).to_have_text(" (fait)")
    expect(etapes.nth(2).locator(".wizard-n")).to_have_text("3")
    expect(etapes.nth(2).locator(".wizard-fait")).to_have_count(0)
    # Fermée, la carte rend la place au guide ; ✕ le quitte, et il ne revient pas seul.
    album.locator("#wizard-fermer").click()
    expect(titre).to_have_text("Tracer une zone")
    page.locator("#wizard-guide-quitter").click()
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    expect(page.locator("#bac-commencer")).to_be_focused()
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    expect(page.locator("#wizard-fenetre")).to_have_count(0)


@pytestmark_proxy
def test_un_menu_ouvert_depuis_une_zone_n_est_pas_assombri(page, jeu):
    """La visite, au second temps de l'Atelier : « Traitement » ouvert se lit en clair — un
    trou de l'assombri le couvre."""
    _commencer_la_visite(page, jeu)
    page.locator("#wizard-visite-suiv").click()
    page.locator("#wizard-visite-suiv").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Visite 2 / 7 · 2 / 2")
    page.locator("#btn-traitement").click()
    menu = page.locator("#traitement-menu")
    expect(menu).to_be_visible()
    page.wait_for_function("""() => {
      const m = document.getElementById('traitement-menu').getBoundingClientRect();
      return [...document.querySelectorAll('#wizard-masque rect[fill="#000"]')].some((t) => {
        const x = +t.getAttribute('x'), y = +t.getAttribute('y');
        return x <= m.left && y <= m.top && x + +t.getAttribute('width') >= m.right
          && y + +t.getAttribute('height') >= m.bottom; }); }""")


# ── La fenêtre du guide ne recouvre jamais son foyer ───────────────────────────────────
#
# Hugo, sur la maquette (redit le 2026-11-04) : la fenêtre se pose À CÔTÉ de ce que
# l'étape éclaire — à droite, sinon à gauche, dessous, dessus —, et en feuille en bas quand
# rien ne tient ou que l'écran est étroit, la page lui réservant sa hauteur. Ce test la
# mesure sur chaque étape des deux parcours, à 1 280 et 768 px, sous des polices de 16 et
# 24 (à 768 px sous 24, l'écran est sous 40em : la feuille). Le foyer est mesuré ICI, sur
# les éléments que l'écran éclaire, coupés par ce qui ne les laisse pas déborder.

MESURE_FOYER = """() => {
  const els = window.BDWizardEcran.elementsDuFoyer();
  const part = (x) => {
    const q = x.getBoundingClientRect();
    let r = { l: q.left, t: q.top, r: q.right, b: q.bottom };
    const couper = (z) => { r = { l: Math.max(r.l, z.left), t: Math.max(r.t, z.top),
                                  r: Math.min(r.r, z.right), b: Math.min(r.b, z.bottom) }; };
    for (let a = x.parentElement; a && a !== document.body; a = a.parentElement) {
      const s = getComputedStyle(a);
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') couper(a.getBoundingClientRect());
    }
    couper({ left: 0, top: 0, right: innerWidth, bottom: innerHeight });
    return r.r - r.l >= 1 && r.b - r.t >= 1 ? r : null;
  };
  const rs = els.map(part).filter(Boolean);
  const q = document.getElementById('wizard-fenetre').getBoundingClientRect();
  const fen = { l: q.left, t: q.top, r: q.right, b: q.bottom };
  const recouvrent = rs.filter((r) => Math.min(r.r, fen.r) - Math.max(r.l, fen.l) > 1
                                      && Math.min(r.b, fen.b) - Math.max(r.t, fen.t) > 1);
  return { n: rs.length, fen, recouvrent, feuille: document.getElementById('wizard-fenetre')
             .classList.contains('feuille'), titre: document.getElementById('wizard-fenetre-titre')
             .textContent };
}"""


@pytestmark_proxy
@pytest.mark.parametrize("largeur", [1280, 768])
def test_la_fenetre_du_guide_ne_recouvre_jamais_son_foyer(page, jeu_decoupe, largeur):
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    from test_e2e_bac_a_sable import _preference_police
    bac = _ouvrir(jeu_decoupe, CAMILLE)
    vue = _api(jeu_decoupe["base"], CAMILLE, "GET", "/api/bac-a-sable")
    _sous(page, CAMILLE)
    _arriver(page, jeu_decoupe["base"])
    plan = page.evaluate("""(vue) => ['rapide', 'complet'].flatMap((p) =>
      BDWizard.etapes(p).map((e, i) => ({ parcours: p, i, k: e.k,
                                          adresse: BDWizard.adresseEtape(e, vue) })))""", vue)
    assert len(plan) == 13
    echecs = []
    for police in (16, 24):
        _preference_police(page, police)
        page.set_viewport_size({"width": largeur, "height": 800})
        for e in plan:
            page.evaluate("""([login, bac, p, i]) => {
              localStorage.setItem('bd-wizard', JSON.stringify({ [login]: { bac: bac.id,
                efface_le: bac.efface_le, album_vu: true, parcours: p, etape: i } }));
              sessionStorage.setItem('bd-wizard-guide', JSON.stringify({ login, bac: bac.id,
                efface_le: bac.efface_le, actif: true, vues: [] })); }""",
                          ["camille", bac, e["parcours"], e["i"]])
            page.goto(jeu_decoupe["base"] + e["adresse"], wait_until="domcontentloaded")
            expect(page.locator("#wizard-guide-compte")).to_be_visible(timeout=15000)
            page.wait_for_timeout(600)          # le cadrage, la feuille et sa réserve
            m = page.evaluate(MESURE_FOYER)
            ou = f"{largeur} px, police {police}, {e['parcours']} · {e['k']}"
            if not m["n"]:
                echecs.append(f"{ou} : aucun élément du foyer ne se voit")
            elif m["recouvrent"]:
                echecs.append(f"{ou} : la fenêtre {m['fen']} recouvre {m['recouvrent']}"
                              f"{' (feuille)' if m['feuille'] else ''}")
    assert not echecs, "\n".join(echecs)
