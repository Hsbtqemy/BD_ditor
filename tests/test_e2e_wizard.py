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
def test_les_pages_de_l_album_glissent_de_leur_cote(page, jeu, wizard_actif):
    """Comme la maquette (Hugo, 2026-11-05) : la page qui arrive glisse de la droite quand on
    avance, de la gauche quand on recule ; à l'ouverture, rien ne glisse ; et sous « moins
    d'animations », la classe est posée mais aucune animation ne joue."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    album = _album(page)
    feuille = album.locator("#wizard-page")
    expect(feuille).not_to_have_class(re.compile(r"\bglisse-"))
    album.locator("#wizard-suiv").click()
    expect(feuille).to_have_class(re.compile(r"\bglisse-avant\b"))
    assert feuille.evaluate("(e) => getComputedStyle(e).animationName") == "wizard-glisse-avant"
    album.locator("#wizard-prec").click()
    expect(feuille).to_have_class(re.compile(r"\bglisse-arriere\b"))
    page.emulate_media(reduced_motion="reduce")
    album.locator("#wizard-suiv").click()
    expect(feuille).to_have_class(re.compile(r"\bglisse-avant\b"))
    assert feuille.evaluate("(e) => getComputedStyle(e).animationName") == "none"


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
    # Le guide ne passe pas l'Atelier en Édition : il apprend à y passer (Hugo, 2026-11-06).
    expect(page.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute("aria-pressed", "true")
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
    assert liens.nth(0).get_attribute("href") == attendu
    assert liens.nth(3).get_attribute("href") == attendu.replace("/?", "/annotation?")
    assert _souvenir(page) == {"camille": {"bac": bac["id"], "efface_le": bac["efface_le"],
                                           "album_vu": True, "parcours": "rapide", "etape": 0,
                                           "k": "tracer"}}
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
    # Passer au parcours complet garde l'étape : « Transcrire et relire » est la 5e.
    album.locator("#wizard-changer").click()
    etapes = album.locator(".wizard-etapes > li")
    expect(etapes).to_have_count(9)
    expect(etapes.nth(4)).to_have_attribute("aria-current", "step")
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
                                          "album_vu": True, "parcours": "complet", "etape": 0,
                                          "k": "corpus"}


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
def test_le_survol_d_une_ligne_cerne_sa_zone_et_inversement(page, jeu):
    """Comme la maquette (Hugo, 2026-11-05) : le pointeur sur une ligne de la liste laisse sa
    zone SEULE en clair, cernée, les autres sous l'assombri ; sur la zone, il surligne sa
    ligne ; en partant, toutes les zones reviennent en clair. La fenêtre ne bouge pas."""
    _commencer_la_visite(page, jeu)
    fen = _visite(page)
    expect(page.locator("#wizard-visite-compte")).to_have_text("Visite 1 / 7")
    place = fen.bounding_box()
    ligne = page.locator('#wizard-zones .wf-zone[data-zone="bande-projet"]')
    cerne = page.locator(".wizard-voile .wf-cadre.ici")
    trous = page.locator('#wizard-masque rect[fill="#000"]')
    pastilles = page.locator(".wizard-voile .wf-pastille")
    expect(cerne).to_have_count(0)
    toutes = trous.count()
    assert toutes > 1, "au départ, toutes les zones du temps sont en clair"
    expect(pastilles).to_have_count(toutes)
    ligne.hover()
    expect(ligne).to_have_class(re.compile(r"\bici\b"))
    expect(cerne).to_have_count(1)
    # Les autres zones repassent sous l'assombri ; leurs pastilles restent.
    expect(trous).to_have_count(1)
    expect(pastilles).to_have_count(toutes)
    # Le cadre cerné est celui de la zone « Le projet » : il l'entoure.
    zone = page.locator('[data-parcours="bande-projet"]').first.bounding_box()
    cadre = cerne.bounding_box()
    assert cadre["x"] <= zone["x"] + 1 and cadre["x"] + cadre["width"] >= zone["x"] + zone["width"] - 1
    assert fen.bounding_box() == place
    # Ailleurs, plus rien n'est cerné ; sur la zone de la page, sa ligne se surligne.
    page.mouse.move(5, 600)
    expect(cerne).to_have_count(0)
    expect(trous).to_have_count(toutes)
    expect(ligne).not_to_have_class(re.compile(r"\bici\b"))
    page.locator('[data-parcours="bande-projet"]').first.hover()
    expect(ligne).to_have_class(re.compile(r"\bici\b"))
    expect(cerne).to_have_count(1)
    expect(ligne).to_have_attribute("aria-pressed", "false")


@pytestmark_proxy
def test_arrivee_sur_une_autre_page_pendant_la_visite_la_fait_suivre(page, jeu):
    """Une autre page atteinte pendant la visite par une adresse tapée (ou Précédent) : la
    visite y reprend à la page de cette surface, au lieu de se perdre. Un LIEN de la barre,
    lui, ne mène plus ailleurs pendant la visite (test suivant)."""
    _commencer_la_visite(page, jeu)
    compte = page.locator("#wizard-visite-compte")
    expect(compte).to_have_text("Visite 1 / 7")
    page.goto(page.url.split("/?")[0].rstrip("/") + "/annotation", wait_until="domcontentloaded")
    expect(compte).to_have_text("Visite 3 / 7 · 1 / 2")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Annotation")
    # « Suivant → » continue depuis là.
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 3 / 7 · 2 / 2")


# Ce qui fait perdre le fil (Hugo, 2026-11-05) : pendant la visite et les repères, le « ? »,
# « Par où commencer », la ligne du bac à sable et tout lien vers une autre page ne font
# rien ; le clic CHOISIT leur zone, comme un clic sur sa ligne.

def _ligne_choisie(page, marque):
    expect(page.locator(f'#wizard-zones .wf-zone[data-zone="{marque}"]')).to_have_attribute(
        "aria-pressed", "true")
    expect(page.locator(".wizard-voile .wf-cadre.ici")).to_have_count(1)


@pytestmark_proxy
def test_pendant_la_visite_ce_qui_perd_le_fil_choisit_sa_zone(page, jeu):
    _commencer_la_visite(page, jeu)
    compte = page.locator("#wizard-visite-compte")
    expect(compte).to_have_text("Visite 1 / 7")
    adresse = page.url
    # Le « ? » n'ouvre pas les repères à la place de la visite.
    page.locator("#site-nav > .bande-aide").click()
    expect(compte).to_have_text("Visite 1 / 7")
    expect(page.locator("#wizard-fenetre")).to_have_attribute("aria-label", "La visite des pages")
    _ligne_choisie(page, "bande-aide")
    # Un lien de la barre ne quitte pas la page.
    page.locator('.surf-nav a.surf-link[href^="/annotation"]').first.click()
    page.wait_for_timeout(400)
    assert page.url == adresse
    expect(compte).to_have_text("Visite 1 / 7")
    _ligne_choisie(page, "bande-pages")
    # « Par où commencer » ne rouvre ni l'album ni la carte.
    page.locator("#bac-commencer").click()
    expect(page.locator("#wizard-modal")).to_be_hidden()
    _ligne_choisie(page, "bande-bac")
    # « Remettre à neuf… » n'ouvre pas son dialogue.
    page.locator("#bac-remettre").click()
    page.wait_for_timeout(300)
    assert not page.locator("#bac-modal").is_visible()
    expect(compte).to_have_text("Visite 1 / 7")
    # Au temps de l'Atelier, un mode reste jouable.
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 2 / 7 · 1 / 2")
    page.locator('.mode-btn[data-mode="edition"]').click()
    expect(page.locator('.mode-btn[data-mode="edition"]')).to_have_attribute("aria-pressed", "true")
    _ligne_choisie(page, "atelier-modes")


@pytestmark_proxy
def test_dans_les_reperes_un_lien_vers_une_autre_page_choisit_sa_zone(page, jeu):
    """Les repères du « ? » suivent la même règle : sur la page Annotation, « Ouvrir dans
    l'Atelier ↗ » ne quitte pas la page, et choisit sa zone."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/annotation", wait_until="domcontentloaded")
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    expect(page.locator("#an-atelier")).to_be_visible()
    page.locator("#site-nav > .bande-aide").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Cette page")
    adresse = page.url
    page.locator("#an-atelier").click()
    page.wait_for_timeout(400)
    assert page.url == adresse
    expect(page.locator("#wizard-visite-compte")).to_have_text("Cette page")
    _ligne_choisie(page, "annotation-lieu")


# Choisir une zone ouvre son menu quand elle en a un (Hugo, 2026-11-05) : en clair, le focus
# restant dans la fenêtre ; il se referme quand on choisit une autre zone, qu'on passe au
# temps suivant ou qu'on ferme la fenêtre.

MENU_EN_CLAIR = """(sel) => {
  const m = document.querySelector(sel).getBoundingClientRect();
  return [...document.querySelectorAll('#wizard-masque rect[fill="#000"]')].some((t) => {
    const x = +t.getAttribute('x'), y = +t.getAttribute('y');
    return x <= m.left && y <= m.top && x + +t.getAttribute('width') >= m.right
      && y + +t.getAttribute('height') >= m.bottom; }); }"""


@pytestmark_proxy
def test_choisir_une_zone_ouvre_son_menu_et_une_autre_le_referme(page, jeu):
    _commencer_la_visite(page, jeu)
    expect(page.locator("#wizard-visite-compte")).to_have_text("Visite 1 / 7")
    aa = page.locator(".display-menu .btn-theme")
    ligne = page.locator('#wizard-zones .wf-zone[data-zone="bande-affichage"]')
    ligne.click()
    expect(aa).to_have_attribute("aria-expanded", "true")
    expect(page.locator(".display-panel")).to_be_visible()
    page.wait_for_function(MENU_EN_CLAIR, arg=".display-panel")
    expect(ligne).to_be_focused()
    # Une autre ligne le referme.
    page.locator('#wizard-zones .wf-zone[data-zone="bande-projet"]').click()
    expect(aa).to_have_attribute("aria-expanded", "false")
    # Au clavier : Entrée sur la ligne l'ouvre aussi ; le survol, lui, n'ouvre rien.
    ligne.focus()
    page.keyboard.press("Enter")
    expect(aa).to_have_attribute("aria-expanded", "true")
    expect(ligne).to_be_focused()
    page.keyboard.press("Enter")
    expect(aa).to_have_attribute("aria-expanded", "false")
    ligne.hover()
    page.wait_for_timeout(200)
    expect(aa).to_have_attribute("aria-expanded", "false")
    # Au second temps de l'Atelier, « Traitement » ; passer à la page suivante le referme.
    page.locator("#wizard-visite-suiv").click()
    page.locator("#wizard-visite-suiv").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Visite 2 / 7 · 2 / 2")
    page.locator('#wizard-zones .wf-zone[data-zone="atelier-actions"]').click()
    expect(page.locator("#btn-traitement")).to_have_attribute("aria-expanded", "true")
    page.wait_for_function(MENU_EN_CLAIR, arg="#traitement-menu")
    page.locator("#wizard-visite-prec").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Visite 2 / 7 · 1 / 2")
    expect(page.locator("#btn-traitement")).to_have_attribute("aria-expanded", "false")


@pytestmark_proxy
def test_dans_les_reperes_choisir_une_zone_ouvre_son_menu(page, jeu):
    """Les repères du « ? » suivent la même règle ; Échap ferme la fenêtre et le menu."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#site-nav > .bande-aide").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Cette page")
    page.locator("#wizard-reperes-suiv").click()
    page.locator('#wizard-zones .wf-zone[data-zone="atelier-actions"]').click()
    expect(page.locator("#btn-traitement")).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#traitement-menu")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    expect(page.locator("#btn-traitement")).to_have_attribute("aria-expanded", "false")


@pytestmark_proxy
def test_un_depliant_ouvert_par_la_fenetre_est_referme_par_elle(page, jeu):
    """Les « Facettes grammaticales » de la Recherche sont un dépliant (`<details>`), que
    rien ne referme au clic ailleurs : seule la fenêtre, qui l'a ouvert, le referme — au choix
    d'une autre zone, et quand elle se ferme."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/recherche", wait_until="domcontentloaded")
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    facettes = page.locator("#gram-facets")
    expect(facettes).not_to_have_attribute("open", "")
    page.locator("#site-nav > .bande-aide").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Cette page")
    ligne = page.locator('#wizard-zones .wf-zone[data-zone="recherche-facettes"]')
    ligne.click()
    expect(facettes).to_have_attribute("open", "")
    expect(ligne).to_be_focused()
    page.locator('#wizard-zones .wf-zone[data-zone="recherche-champ"]').click()
    expect(facettes).not_to_have_attribute("open", "")
    ligne.click()
    expect(facettes).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    expect(facettes).not_to_have_attribute("open", "")


@pytestmark_proxy
def test_pendant_la_visite_ce_qui_lance_est_eteint_et_le_guide_le_fait(page, jeu):
    """Hugo, 2026-11-05 : la visite montre le menu « Traitement » en entier, mais ses
    entrées qui lancent sont éteintes (`aria-disabled`, l'infobulle du guide) et leur clic
    ne lance rien ; rendues à la fermeture. Dans le guide, à « Pré-remplir », l'OCR se lance."""
    ocr = []
    page.on("request", lambda r: ocr.append(r.url) if r.url.endswith("/ocr") else None)
    _commencer_la_visite(page, jeu)
    page.locator("#wizard-visite-suiv").click()
    page.locator("#wizard-visite-suiv").click()
    expect(page.locator("#wizard-visite-compte")).to_have_text("Visite 2 / 7 · 2 / 2")
    page.locator('#wizard-zones .wf-zone[data-zone="atelier-actions"]').click()
    entree = page.locator("#btn-ocr")
    expect(entree).to_be_visible()
    expect(entree).to_have_text("OCR des bulles")
    expect(entree).to_have_attribute("aria-disabled", "true")
    expect(entree).to_have_attribute("title", "Le guide pas à pas vous le fera faire.")
    for sel in ("#btn-segmenter", "#btn-bulles"):
        expect(page.locator(sel)).to_have_attribute("aria-disabled", "true")
    # Playwright tient une entrée `aria-disabled` pour éteinte : le clic est forcé, comme
    # celui d'une souris qui ne demande rien.
    entree.click(force=True)
    page.wait_for_timeout(400)
    assert not ocr, ocr
    # La fenêtre fermée (Échap depuis elle), tout est rendu.
    page.locator("#wizard-fenetre-titre").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    expect(entree).not_to_have_attribute("aria-disabled", "true")
    expect(entree).to_have_attribute("title", re.compile(r"OCR des bulles"))


@pytestmark_proxy
def test_le_plafond_d_import_gagne_sur_la_visite(page, jeu):
    """« Importer » éteint par la visite : relu pendant la visite (un album ouvert), il reste
    éteint ; le plafond d'import atteint, c'est lui qui l'éteint, avec sa raison, et la
    fermeture de la visite ne le rallume pas (relecture du 2026-11-05). Le plafond est
    SIMULÉ — atteindre 50 planches importées coûterait cinquante imports — par la réponse de
    `BDBacEcran.raisonImport`, la seule que lit `majImportPlafond`."""
    _commencer_la_visite(page, jeu)
    _visite(page)
    entree = page.locator("#btn-import-menu")
    expect(entree).to_have_attribute("data-wizard-eteint", "1")
    guide = "Le guide pas à pas vous le fera faire."
    # Un album ouvert pendant la visite relit le plafond : pas atteint, l'entrée reste
    # éteinte par la visite.
    page.evaluate("() => majImportPlafond()")
    expect(entree).to_have_attribute("aria-disabled", "true")
    expect(entree).to_have_attribute("title", guide)
    expect(entree).to_have_attribute("data-wizard-eteint", "1")
    # Le plafond atteint pendant la visite : sa raison prend la place.
    raison = "Plafond atteint (simulé)"
    page.evaluate("(r) => { BDBacEcran.raisonImport = () => r; majImportPlafond(); }", raison)
    expect(entree).to_have_attribute("aria-disabled", "true")
    expect(entree).to_have_attribute("title", raison)
    # La visite fermée, il reste éteint, avec la raison du plafond.
    page.locator("#wizard-fenetre-titre").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    expect(entree).to_have_attribute("aria-disabled", "true")
    expect(entree).to_have_attribute("title", raison)


@pytestmark_proxy
def test_dans_le_guide_pre_remplir_lance_vraiment_l_ocr(page, jeu):
    ocr = []
    page.on("request", lambda r: ocr.append(r.url) if r.url.endswith("/ocr") else None)
    _au_guide_sur(page, jeu, "complet", "preremplir")
    titre = page.locator("#wizard-fenetre-titre")
    expect(titre).to_have_text(re.compile(r"^Pré-remplir"), timeout=15000)
    page.locator("#btn-traitement").click()
    entree = page.locator("#btn-ocr")
    expect(entree).to_be_visible()
    assert entree.get_attribute("aria-disabled") != "true"
    with page.expect_request(lambda r: r.url.endswith("/ocr")):
        entree.click()


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
    # Aucune zone choisie d'office (Hugo, 2026-11-05 : « Traitement est un gros truc, à bien
    # apprendre et repérer ») : « Structure » ET « Traitement, Import / Export » sont en
    # clair, deux trous dans l'assombri, et aucune ligne n'est pressée. Le pointeur, resté
    # où était « Suivant », est maintenant sur la Structure : il s'écarte, sans quoi le
    # survol l'isolerait.
    page.mouse.move(5, 5)
    for m in ("atelier-structure", "atelier-actions"):
        expect(page.locator(f'#wizard-zones .wf-zone[data-zone="{m}"]')).to_have_attribute(
            "aria-pressed", "false")
    expect(page.locator('#wizard-masque rect[fill="#000"]')).to_have_count(2)
    expect(page.locator(".wizard-voile .wf-cadre.ici")).to_have_count(0)
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

    # Arrivé sur une AUTRE des six pages — un lien suivi en route —, la visite SUIT : elle
    # reprend à la page de cette surface, à son premier temps (Hugo, 2026-11-05).
    page.goto(jeu["base"] + "/recherche", wait_until="domcontentloaded")
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    expect(compte).to_have_text("Visite 5 / 7")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Recherche")
    assert '"page":4' in (page.evaluate(VISITE_SESSION) or "")

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
    expect(page).to_have_url(re.compile(r"/\?album="))
    expect(page.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute("aria-pressed", "true")
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
    """axe (WCAG 2.1 AA), album ouvert sur sa première page, sur ses pages illustrées, sur
    la page du choix, la visite qui suit le choix, le guide qui la suit, puis la carte des
    étapes : aucune violation sérieuse ou critique."""
    from test_e2e_bac_a_sable import _audit_axe
    # Une page de l'album qui glisse encore serait auditée à moitié transparente.
    page.emulate_media(reduced_motion="reduce")
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    _album(page)
    rapports = []
    for quoi, geste in (("album, première page", None),
                        # Les pages illustrées (les noms de la page 3, en encre
                        # du texte sur l'image).
                        ("album, page 2", "#wizard-suiv"),
                        ("album, page 3", "#wizard-suiv"),
                        ("album, page 4", "#wizard-suiv"),
                        ("album, page 5", "#wizard-suiv"),
                        ("album, page 6", "#wizard-suiv"),
                        ("album, page 7", "#wizard-suiv"),
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
    """À 320 px, sous des préférences de 16 et 24 : l'album et ses pages illustrées, la
    fenêtre de la visite et la carte ne perdent rien et ne s'écrasent pas, et la ligne qui porte « Par où commencer »
    non plus."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    page.emulate_media(reduced_motion="reduce")   # mesurer des pages posées, pas en vol
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
                                   ("album, page 2", "#wizard-suiv", ".wizard-boite"),
                                   ("album, page 3", "#wizard-suiv", ".wizard-boite"),
                                   ("album, page 4", "#wizard-suiv", ".wizard-boite"),
                                   ("album, page 5", "#wizard-suiv", ".wizard-boite"),
                                   ("album, page 6", "#wizard-suiv", ".wizard-boite"),
                                   ("album, page 7", "#wizard-suiv", ".wizard-boite"),
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


def _au_guide_sur(page, jeu, parcours, k):
    """camille dans son bac à sable, le guide ouvert sur l'étape de clé `k` du parcours, sur
    sa page — retenue comme l'écran la retient (le rang ET la clé)."""
    bac = _ouvrir(jeu, CAMILLE)
    vue = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    e = page.evaluate("""([p, k, vue]) => { const l = BDWizard.etapes(p);
      const i = l.findIndex((x) => x.k === k);
      return { i, adresse: BDWizard.adresseEtape(l[i], vue) }; }""", [parcours, k, vue])
    page.evaluate("""([login, bac, p, i, k]) => {
      localStorage.setItem('bd-wizard', JSON.stringify({ [login]: { bac: bac.id,
        efface_le: bac.efface_le, album_vu: true, parcours: p, etape: i, k } }));
      sessionStorage.setItem('bd-wizard-guide', JSON.stringify({ login, bac: bac.id,
        efface_le: bac.efface_le, actif: true, vues: [] })); }""",
                  ["camille", bac, parcours, e["i"], k])
    page.goto(jeu["base"] + e["adresse"], wait_until="domcontentloaded")
    expect(page.locator("#wizard-guide-compte")).to_be_visible(timeout=15000)
    return bac


def _ecran(page, mx, my):
    """Un point de la planche (pixels master, planche de 400 px de large) à l'écran."""
    b = page.locator("#planche-img").bounding_box()
    k = b["width"] / 400
    return b["x"] + mx * k, b["y"] + my * k


MARQUES_DU_FOYER = "() => window.BDWizardEcran.elementsDuFoyer().map((e) => e.dataset.parcours)"


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
    # Le guide ne passe pas l'Atelier en Édition (Hugo, 2026-11-06) : en Navigation, il
    # éclaire la barre des modes et dit d'y passer ; au bouton, sans recharger la page, il
    # rend la planche et la phrase du tracé.
    page.evaluate("() => { window.__sansRecharge = true; }")
    phrase = page.locator("#wizard-fenetre .wf-phrase")
    expect(page.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute("aria-pressed", "true")
    expect(phrase).to_contain_text("Pour tracer, passez en mode Édition")
    assert page.evaluate(MARQUES_DU_FOYER) == ["atelier-modes"]
    page.locator('.mode-btn[data-mode="edition"]').click()
    expect(phrase).to_contain_text("Seule la dernière rangée")
    assert "atelier-planche" in page.evaluate(MARQUES_DU_FOYER)
    # Le jeu a découpé une rangée : la phrase de Hugo le dit. Rien n'est fait.
    expect(page.locator("#wizard-fenetre .wf-phrase")).to_contain_text("Seule la dernière rangée")
    expect(fait).to_be_hidden()
    expect(suivant).to_have_text("Passer →")
    # L'Atelier a cadré la rangée du jeu (test suivant) ; « Ajuster », un geste de la main,
    # rend la planche entière, et le guide ne le défait pas.
    _cadrage_pose(page)
    zoom = page.locator("#zoom-level")
    expect(zoom).not_to_have_text("")
    cadre = zoom.inner_text()
    page.locator("#zoom-fit").click()
    expect(zoom).not_to_have_text(cadre)
    page.wait_for_timeout(300)
    ajuste = zoom.inner_text()
    assert int(ajuste.rstrip(" %")) < int(cadre.rstrip(" %"))
    # Une nouvelle mise en page — le navigateur change de taille, la fenêtre du guide se
    # repose — ne recadre pas une vue reprise à la main (`BDAtelierVue.retouchee`).
    page.set_viewport_size({"width": 1280, "height": 690})
    page.wait_for_timeout(500)
    expect(zoom).to_have_text(ajuste)
    page.set_viewport_size({"width": 1280, "height": 720})
    page.wait_for_timeout(500)
    expect(zoom).to_have_text(ajuste)
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
    # Ni ne recadre la rangée : la phrase de « ✓ Fait » peut allonger la fenêtre (sous une
    # police plus large, celle de l'image), ce qui est une mise en page ; « Ajuster » tient.
    page.wait_for_timeout(500)
    expect(zoom).to_have_text(ajuste)

    # « Corriger » : la planche se rapproche de la plus petite bulle du jeu, choisie.
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
    # Repasser en Navigation n'est ni forcé ni empêché : au clavier, le guide rééclaire la
    # barre des modes et redit d'y repasser ; l'étape reste faite. En Édition, la suite.
    page.keyboard.press("n")
    expect(page.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute("aria-pressed", "true")
    expect(phrase).to_contain_text("Pour corriger le découpage, passez en mode Édition")
    expect(fait).to_have_text("✓ Fait")
    assert page.evaluate(MARQUES_DU_FOYER) == ["atelier-modes"]
    page.keyboard.press("e")
    expect(phrase).to_contain_text("huit poignées")
    assert page.evaluate("() => window.__sansRecharge === true")
    # En sortant de l'étape, la planche revient entière.
    page.locator("#wizard-guide-prec").click()
    expect(titre).to_have_text("Tracer une zone")
    # La planche ENTIÈRE dans la scène d'à présent, et non le zoom lu avant « Corriger » :
    # la fenêtre du guide, en feuille, réserve sa hauteur, qui suit sa phrase — la scène n'a
    # plus forcément la taille qu'elle avait (mesuré dans l'image : 358 px, puis 339).
    try:
        page.wait_for_function(PLANCHE_ENTIERE, timeout=5000)
    except Exception:
        raise AssertionError(page.evaluate(PLANCHE_ENTIERE_MESURE)) from None
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


# « Tracer une zone » : l'Atelier cadre la rangée du jeu (Hugo, 2026-11-05) — grossie, en
# entier dans la scène et à côté de la fenêtre du guide, jamais dessous ; la planche revient
# entière en sortant de l'étape.

# La planche entière dans la scène : dedans, au pixel près, et à 95 % de la scène dans une
# dimension au moins (« Ajuster »). Forme fonction : la CSP refuse l'`eval`.
PLANCHE_ENTIERE_MESURE = """() => {
  const s = document.getElementById('stage').getBoundingClientRect();
  const p = document.getElementById('planche-img').getBoundingClientRect();
  return { scene: [s.left, s.top, s.right, s.bottom].map(Math.round),
           planche: [p.left, p.top, p.right, p.bottom].map(Math.round),
           part: Math.max(p.width / s.width, p.height / s.height),
           zoom: document.getElementById('zoom-level').textContent }; }"""
PLANCHE_ENTIERE = """() => {
  const s = document.getElementById('stage').getBoundingClientRect();
  const p = document.getElementById('planche-img').getBoundingClientRect();
  const part = Math.max(p.width / s.width, p.height / s.height);
  return p.left >= s.left - 1 && p.top >= s.top - 1 && p.right <= s.right + 1
    && p.bottom <= s.bottom + 1 && Math.abs(part - 0.95) < 0.01; }"""


def _cadrage_pose(page):
    """Le cadrage du guide est posé : demandé, la planche là, et la mise en page faite."""
    page.wait_for_function("""() => !!window.BDAtelierVue && window.BDAtelierVue.estCadree()
      && !window.BDAtelierVue.enAttente()""")
    page.wait_for_timeout(500)


def _planche_du_parcours(jeu):
    vue = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    return next(j for j in vue["jeu"] if j["role"] == "pas-a-pas")["planche_ids"][0]


RANGEE_A_L_ECRAN = """(q) => {
  const ov = document.getElementById('overlay'), vb = ov.viewBox.baseVal;
  const o = ov.getBoundingClientRect(), kx = o.width / vb.width, ky = o.height / vb.height;
  const r = { l: o.left + q.x * kx, t: o.top + q.y * ky,
              r: o.left + (q.x + q.w) * kx, b: o.top + (q.y + q.h) * ky };
  const s = document.getElementById('stage').getBoundingClientRect();
  const f = document.getElementById('wizard-fenetre').getBoundingClientRect();
  return { r, dedans: r.l >= s.left - 1 && r.r <= s.right + 1 && r.t >= s.top - 1
             && r.b <= s.bottom + 1,
           recouvre: Math.min(r.r, f.right) - Math.max(r.l, f.left) > 1
             && Math.min(r.b, f.bottom) - Math.max(r.t, f.top) > 1,
           largeur: r.r - r.l };
}"""


@pytestmark_proxy
@pytest.mark.parametrize("largeur", [1280, 768])
def test_tracer_une_zone_cadre_la_rangee_du_jeu(page, jeu_decoupe, largeur):
    page.set_viewport_size({"width": largeur, "height": 800})
    _au_guide(page, jeu_decoupe)      # le parcours rapide : « Tracer » est la première étape
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Tracer une zone")
    # La planche du parcours, lue dans la vue du bac à sable : l'adresse peut ne pas encore la dire.
    pid = _planche_du_parcours(jeu_decoupe)
    jeu = [r for r in _api(jeu_decoupe["base"], CAMILLE, "GET", f"/api/planches/{pid}/regions")
           if r["source"] == "jeu"]
    assert jeu
    l, t = min(r["x"] for r in jeu), min(r["y"] for r in jeu)
    rangee = {"x": l, "y": t, "w": max(r["x"] + r["w"] for r in jeu) - l,
              "h": max(r["y"] + r["h"] for r in jeu) - t}
    _cadrage_pose(page)
    cadree = page.evaluate(RANGEE_A_L_ECRAN, rangee)
    assert cadree["dedans"], cadree
    assert not cadree["recouvre"], cadree
    zoom = page.locator("#zoom-level")
    z_cadre = int(zoom.inner_text().rstrip(" %"))
    # En sortant de l'étape (✕), la planche revient entière : la rangée y est plus petite.
    page.locator("#wizard-guide-quitter").click()
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    expect(zoom).not_to_have_text(f"{z_cadre} %")
    assert int(zoom.inner_text().rstrip(" %")) < z_cadre
    assert page.evaluate("""(q) => { const ov = document.getElementById('overlay');
      return ov.getBoundingClientRect().width * q.w / ov.viewBox.baseVal.width; }""",
                         rangee) < cadree["largeur"]


PLANCHE_DANS_LA_SCENE = """() => {
  const s = document.getElementById('stage').getBoundingClientRect();
  const i = document.getElementById('planche-img').getBoundingClientRect();
  return { zoom: document.getElementById('stage').currentCSSZoom,
           dedans: i.left >= s.left - 1 && i.right <= s.right + 1 && i.top >= s.top - 1
             && i.bottom <= s.bottom + 1,
           s: [s.left, s.top, s.right, s.bottom], i: [i.left, i.top, i.right, i.bottom] };
}"""
POINT_DE_LA_PLANCHE = """([x, y]) => {
  const q = document.getElementById('planche-img').getBoundingClientRect();
  return [(x - q.left) / q.width, (y - q.top) / q.height];
}"""


@pytestmark_proxy
def test_sous_le_zoom_d_interface_le_cadrage_tient(page, jeu_decoupe):
    """Le zoom de « Aa » est un `zoom` CSS sur la racine : la scène se mesure en pixels
    visibles, la `transform` de la planche s'écrit en pixels de la page. Mesuré le
    2026-11-06 sous `bd-zoom = 2` (borné à 151 % par la fenêtre de 1 280 px) : la rangée
    cadrée sortait de la scène et passait sous la fenêtre du guide, « ajuster » posait la
    planche une fois et demie trop grande, et la molette déplaçait le point sous le
    pointeur. Les trois tiennent, comme à 100 %."""
    page.add_init_script("try { localStorage.setItem('bd-zoom', '2'); } catch (e) {}")
    page.set_viewport_size({"width": 1280, "height": 800})
    _au_guide(page, jeu_decoupe)
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Tracer une zone")
    pid = _planche_du_parcours(jeu_decoupe)
    jeu = [r for r in _api(jeu_decoupe["base"], CAMILLE, "GET", f"/api/planches/{pid}/regions")
           if r["source"] == "jeu"]
    l, t = min(r["x"] for r in jeu), min(r["y"] for r in jeu)
    rangee = {"x": l, "y": t, "w": max(r["x"] + r["w"] for r in jeu) - l,
              "h": max(r["y"] + r["h"] for r in jeu) - t}
    _cadrage_pose(page)
    assert page.evaluate("() => document.getElementById('stage').currentCSSZoom") > 1.2
    cadree = page.evaluate(RANGEE_A_L_ECRAN, rangee)
    assert cadree["dedans"], cadree
    assert not cadree["recouvre"], cadree
    # Hors du guide : « ajuster » pose la planche entière dans la scène.
    page.locator("#wizard-guide-quitter").click()
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    page.wait_for_timeout(300)
    vue = page.evaluate(PLANCHE_DANS_LA_SCENE)
    assert vue["dedans"], vue
    # La molette garde le point de la planche sous le pointeur.
    s = vue["s"]
    x, y = s[0] + (s[2] - s[0]) * 0.4, s[1] + (s[3] - s[1]) * 0.4
    avant = page.evaluate(POINT_DE_LA_PLANCHE, [x, y])
    page.mouse.move(x, y)
    page.mouse.wheel(0, -100)
    page.wait_for_timeout(300)
    apres = page.evaluate(POINT_DE_LA_PLANCHE, [x, y])
    assert abs(avant[0] - apres[0]) < 0.003 and abs(avant[1] - apres[1]) < 0.003, (avant, apres)
    # Le glissé (bouton du milieu) suit le pointeur : 60 px à l'écran, 60 px de planche.
    g0 = page.locator("#planche-img").bounding_box()["x"]
    page.mouse.down(button="middle")
    page.mouse.move(x + 60, y, steps=4)
    page.mouse.up(button="middle")
    page.wait_for_timeout(200)
    g1 = page.locator("#planche-img").bounding_box()["x"]
    assert abs((g1 - g0) - 60) < 2, (g0, g1)


@pytestmark_proxy
@pytest.mark.parametrize("largeur", [1280, 768])
def test_corriger_cadre_la_case_de_la_bulle(page, jeu_decoupe, largeur):
    """Hugo, 2026-11-05 : « Corriger » ne grossit plus la bulle seule, « beaucoup trop
    gros » — il cadre sa CASE : la bulle choisie et sa case se voient en entier, à côté de
    la fenêtre, jamais dessous ; en revenant à « Tracer », la rangée reprend la vue."""
    page.set_viewport_size({"width": largeur, "height": 800})
    _au_guide(page, jeu_decoupe)
    titre = page.locator("#wizard-fenetre-titre")
    expect(titre).to_have_text("Tracer une zone")
    page.locator("#wizard-guide-suiv").click()
    expect(titre).to_have_text("Corriger le découpage")
    # La planche du parcours, lue dans la vue du bac à sable : l'adresse peut ne pas encore la dire.
    pid = _planche_du_parcours(jeu_decoupe)
    regions = _api(jeu_decoupe["base"], CAMILLE, "GET", f"/api/planches/{pid}/regions")
    petite = min((r for r in regions if r["type"] == "bulle"), key=lambda r: r["w"] * r["h"])
    case = next(r for r in regions if r["id"] == petite["parent_id"])
    expect(page.locator("#region-id")).to_have_text(f"#{petite['id']}")
    _cadrage_pose(page)
    for quoi in (petite, case):
        m = page.evaluate(RANGEE_A_L_ECRAN, {k: quoi[k] for k in ("x", "y", "w", "h")})
        assert m["dedans"], (largeur, quoi["type"], m)
        assert not m["recouvre"], (largeur, quoi["type"], m)


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


# Défaut vu par Hugo sur la recette (2026-11-05) : à 790 px, sous un zoom de 200 %, la
# fenêtre du guide se posait à moitié hors de l'écran, sur le panneau de la Transcription.
# Deux lectures de « 200 % » : le zoom d'interface (« Aa », un `zoom` CSS sur la racine,
# que les requêtes média ne voient pas), et le zoom du navigateur, qui fait d'une fenêtre de
# 790 px une page de 395 px CSS. La fenêtre doit tenir DANS l'écran et hors de son foyer.

@pytestmark_proxy
@pytest.mark.parametrize("largeur, zoom", [(790, 1.25), (790, 1.5), (790, 2), (395, 1)])
def test_la_fenetre_du_guide_tient_dans_l_ecran_sous_un_zoom(page, jeu_decoupe, largeur, zoom):
    page.add_init_script(f"try {{ localStorage.setItem('bd-zoom', '{zoom}'); }} catch (e) {{}}")
    bac = _ouvrir(jeu_decoupe, CAMILLE)
    vue = _api(jeu_decoupe["base"], CAMILLE, "GET", "/api/bac-a-sable")
    _sous(page, CAMILLE)
    page.set_viewport_size({"width": largeur, "height": 800})
    _arriver(page, jeu_decoupe["base"])
    plan = page.evaluate("""(vue) => BDWizard.etapes('rapide').map((e, i) =>
      ({ i, k: e.k, adresse: BDWizard.adresseEtape(e, vue) }))""", vue)
    echecs = []
    for e in plan:
        page.evaluate("""([login, bac, i, k]) => {
          localStorage.setItem('bd-wizard', JSON.stringify({ [login]: { bac: bac.id,
            efface_le: bac.efface_le, album_vu: true, parcours: 'rapide', etape: i, k } }));
          sessionStorage.setItem('bd-wizard-guide', JSON.stringify({ login, bac: bac.id,
            efface_le: bac.efface_le, actif: true, vues: [] })); }""",
                      ["camille", bac, e["i"], e["k"]])
        page.goto(jeu_decoupe["base"] + e["adresse"], wait_until="domcontentloaded")
        expect(page.locator("#wizard-guide-compte")).to_be_visible(timeout=15000)
        page.wait_for_timeout(600)
        z = page.evaluate("() => document.documentElement.currentCSSZoom || 1")
        m = page.evaluate(MESURE_FOYER)
        f = m["fen"]
        ou = f"{largeur} px, zoom {zoom} (appliqué {z}), {e['k']}"
        if f["l"] < -1 or f["t"] < -1 or f["r"] > largeur + 1 or f["b"] > 801:
            echecs.append(f"{ou} : la fenêtre {f} sort de l'écran")
        if m["recouvrent"]:
            echecs.append(f"{ou} : la fenêtre {f} recouvre {m['recouvrent']}"
                          f"{' (feuille)' if m['feuille'] else ''}")
    assert not echecs, "\n".join(echecs)


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
            page.evaluate("""([login, bac, p, i, k]) => {
              localStorage.setItem('bd-wizard', JSON.stringify({ [login]: { bac: bac.id,
                efface_le: bac.efface_le, album_vu: true, parcours: p, etape: i, k } }));
              sessionStorage.setItem('bd-wizard-guide', JSON.stringify({ login, bac: bac.id,
                efface_le: bac.efface_le, actif: true, vues: [] })); }""",
                          ["camille", bac, e["parcours"], e["i"], e["k"]])
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


# ── « Exporter » dit ce qui sort vraiment d'un bac à sable (tranche 4) ─────────────────
#
# Le serveur décide l'export d'un album de bac à sable document par document : seule la
# copie d'un document du jeu ouvert à l'export (la part du dépôt) peut sortir, et le jeu de
# production est tout entier en part serveur. La fiche de l'album, que l'étape éclaire, ne
# dit donc « exporter » que là où le serveur le permet, et la phrase de l'étape le dit
# d'abord. Les deux sens sont joués : un mutant qui fermerait tout passerait sinon.

def _export(base, album_id):
    import httpx
    with httpx.Client(base_url=base, trust_env=False, timeout=60, headers=CAMILLE) as c:
        return c.get("/api/export/json", params={"album_id": album_id})


@pytestmark_proxy
@pytest.mark.parametrize("exportable", [False, True])
def test_l_etape_exporter_ne_promet_que_ce_qui_sort(page, live_server, tmp_path, exportable):
    from test_e2e_bac_a_sable import _outil
    from test_jeu import ecrire_jeu
    doc = dict(JEU_DECOUPE[0], exportable=exportable)
    depot = ecrire_jeu(tmp_path / "jeu-depot", [doc], images=("p1.png",))
    _outil(tmp_path, "tools/preparer_jeu.py", "--depot", str(depot), "--appliquer")
    jeu = {"base": live_server, "tmp": tmp_path}
    bac = _ouvrir(jeu, CAMILLE)
    vue = _api(live_server, CAMILLE, "GET", "/api/bac-a-sable")
    parcours = next(j for j in vue["jeu"] if j["role"] == "pas-a-pas")
    assert parcours["exportable"] is exportable
    _sous(page, CAMILLE)
    _arriver(page, live_server)
    complet = page.evaluate("() => BDWizard.etapes('complet').map((e) => e.k)")
    i = complet.index("exporter")
    page.evaluate("""([login, bac, i]) => {
      localStorage.setItem('bd-wizard', JSON.stringify({ [login]: { bac: bac.id,
        efface_le: bac.efface_le, album_vu: true, parcours: 'complet', etape: i,
        k: 'exporter' } }));
      sessionStorage.setItem('bd-wizard-guide', JSON.stringify({ login, bac: bac.id,
        efface_le: bac.efface_le, actif: true, vues: [] })); }""", ["camille", bac, i])
    page.goto(f"{live_server}/corpus?album={parcours['album_id']}", wait_until="domcontentloaded")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Exporter", timeout=15000)
    # Deux paragraphes, dans cet ordre (Hugo, 2026-11-05) : ce qu'on PEUT exporter, puis
    # ce qui sort d'ici.
    phrases = page.locator("#wizard-fenetre .wf-phrase")
    expect(phrases).to_have_count(2)
    acte = page.locator('#biblio-volet .droits [data-acte="exporter"]')
    expect(acte).to_be_visible()
    expect(phrases.nth(0)).to_contain_text("Vos données sortent aux formats de la recherche")
    if exportable:
        expect(phrases.nth(1)).to_contain_text("peut être exporté, tant que vous n")
        expect(acte).to_have_class("oui")
        # Et le serveur le confirme : l'album sort.
        assert _export(live_server, parcours["album_id"]).status_code == 200
    else:
        expect(phrases.nth(1)).to_contain_text("pas autorisé")
        expect(acte).to_have_class("non")
        assert _export(live_server, parcours["album_id"]).status_code == 403


# ── 768 px : la visite ne cache pas la dernière zone de la Recherche et de l'Exploration ──
#
# `pilotage/UX-6.md`, « La maquette se mesure sur l'écran codé » : à 768 px, sous des
# polices de 16 et 24, la fenêtre de la visite ne cache rien d'indispensable à la dernière
# zone de ces deux pages — leurs résultats, qui disent à l'arrivant pourquoi ils sont vides.
# Mesuré sur le TEXTE de la zone (chaque ligne, par `Range`), coupé à l'écran : une ligne
# hors de l'écran se rejoint en défilant, une ligne sous la fenêtre ne se rejoint pas.

TEXTE_SOUS_LA_FENETRE = """(marque) => {
  const q = document.getElementById('wizard-fenetre').getBoundingClientRect();
  const zones = [...document.querySelectorAll(`[data-parcours="${marque}"]`)];
  if (!zones.length) return { zone: false };
  const lignes = [];
  for (const zone of zones) {
  const w = document.createTreeWalker(zone, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (!n.textContent.trim()) continue;
    const r = document.createRange();
    r.selectNodeContents(n);
    for (const b of r.getClientRects()) {
      if (b.width < 1 || b.height < 1 || b.bottom <= 0 || b.top >= innerHeight) continue;
      lignes.push({ texte: n.textContent.trim().slice(0, 40), l: b.left, t: b.top,
                    r: b.right, b: b.bottom });
    }
  }
  }
  const sous = lignes.filter((b) => Math.min(b.r, q.right) - Math.max(b.l, q.left) > 1
                                    && Math.min(b.b, q.bottom) - Math.max(b.t, q.top) > 1);
  return { zone: true, lignes: lignes.length, sous,
           fen: { l: q.left, t: q.top, r: q.right, b: q.bottom } };
}"""


@pytestmark_proxy
def test_a_768_px_la_visite_ne_cache_pas_les_resultats(page, jeu):
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    from test_e2e_bac_a_sable import _preference_police
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    echecs = []
    for police in (16, 24):
        _preference_police(page, police)
        page.set_viewport_size({"width": 768, "height": 800})
        for chemin, marque in (("/recherche", "recherche-resultats"),
                               ("/exploration", "exploration-resultat")):
            n = page.evaluate("(c) => BDWizard.VISITE.findIndex((v) => !v.bande && v.surface === c)",
                              chemin)
            page.evaluate("""([login, bac, n]) => sessionStorage.setItem('bd-wizard-visite',
              JSON.stringify({ login, bac: bac.id, efface_le: bac.efface_le, page: n,
                               temps: 0 }))""", ["camille", bac, n])
            page.goto(jeu["base"] + chemin, wait_until="domcontentloaded")
            expect(page.locator("#wizard-visite-compte")).to_have_text(re.compile(r"^Visite"))
            # La zone se remplit après sa réponse : on attend qu'elle dise quelque chose.
            # La zone dit pourquoi elle est vide une fois sa réponse arrivée ; puis on la
            # choisit dans la liste, comme l'arrivant qui veut la lire.
            page.wait_for_function("""(m) => [...document.querySelectorAll(
              `[data-parcours="${m}"]`)].some((z) => z.textContent.trim().length > 0)""",
                                   arg=marque)
            repere = page.locator(f'#wizard-zones .wf-zone[data-zone="{marque}"]')
            expect(repere).to_be_visible()
            repere.click()
            expect(repere).to_have_attribute("aria-pressed", "true")
            page.wait_for_timeout(300)
            m = page.evaluate(TEXTE_SOUS_LA_FENETRE, marque)
            ou = f"768 px, police {police}, {chemin}"
            if not m["zone"] or not m["lignes"]:
                echecs.append(f"{ou} : la zone {marque} ne montre aucun texte")
            elif m["sous"]:
                echecs.append(f"{ou} : la fenêtre {m['fen']} cache {m['sous']}")
    assert not echecs, "\n".join(echecs)


# ── La Transcription nomme ce qu'elle montre ───────────────────────────────────────────
#
# Le titre de la Transcription disait « Bulle 4 / 4 » sur un cartouche ou un texte hors
# bulle : il compte les zones de texte de la planche, de toutes sortes.

@pytestmark_proxy
def test_la_transcription_ne_dit_pas_bulle_sur_un_cartouche(page, jeu_decoupe):
    bac = _ouvrir(jeu_decoupe, CAMILLE)
    vue = _api(jeu_decoupe["base"], CAMILLE, "GET", "/api/bac-a-sable")
    parcours = next(j for j in vue["jeu"] if j["role"] == "pas-a-pas")
    pid = parcours["planche_ids"][0]
    case = next(r for r in _api(jeu_decoupe["base"], CAMILLE, "GET",
                                f"/api/planches/{pid}/regions") if r["type"] == "case")
    _api(jeu_decoupe["base"], CAMILLE, "POST", f"/api/planches/{pid}/regions",
         {"type": "cartouche", "x": 20, "y": 450, "w": 150, "h": 30, "parent_id": case["id"]})
    assert bac["id"]
    _sous(page, CAMILLE)
    page.goto(f"{jeu_decoupe['base']}/?album={parcours['album_id']}&planche={pid}"
              "&mode=transcription", wait_until="domcontentloaded")
    progres, sorte = page.locator("#tr-progress"), page.locator("#tr-type")
    expect(progres).to_be_visible(timeout=15000)
    vus = []
    for _ in range(3):
        expect(sorte).not_to_have_text("")
        vus.append((sorte.inner_text(), progres.inner_text()))
        page.locator("#tr-next").click()
        page.wait_for_timeout(150)
    assert {s for s, _ in vus} == {"bulle", "cartouche"}, vus
    for s, p in vus:
        assert re.fullmatch(r"Zone \d / 3", p), (s, p)


# ── Les illustrations fixes de l'album ─────────────────────────────────────────────────
#
# Des images du dépôt (`static/wizard/`, Hugo, 2026-11-05) : ouvrir l'album et tourner ses
# pages ne demande aucune image à l'instance, ni rien d'autre une fois l'album ouvert — il a
# lu `GET /api/sante` en s'ouvrant, pour la page 4 —, et chaque image arrive.

PAGES_ILLUSTREES = {1: "outil", 2: "corpus", 3: "zones", 4: "moteurs", 5: "analyse", 6: "collab",
                    7: "sortir", 8: "carte"}
# Du texte seul : des membres et un fil de doute ; l'aperçu de la carte des étapes.
SANS_IMAGE = {"collab", "carte"}


@pytestmark_proxy
def test_les_illustrations_de_l_album_ne_demandent_rien_a_l_instance(page, jeu):
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    # Écoutée AVANT d'ouvrir l'album : la première page se dessine à l'ouverture. Aucune
    # image n'y vient de l'instance — l'Atelier, dessous, finit peut-être de charger sa
    # planche, d'où une seconde liste, partie une fois la page 1 posée.
    images, demandes = [], []
    page.on("request", lambda r: images.append(r.url) if r.resource_type == "image" else None)
    page.locator("#bac-commencer").click()
    album = _album(page)
    expect(album.locator("#wizard-compte")).to_have_text("1 / 8")
    page.wait_for_timeout(300)
    page.on("request", lambda r: demandes.append(r.url))
    for n, k in PAGES_ILLUSTREES.items():
        while album.locator("#wizard-compte").inner_text() != f"{n} / 8":
            album.locator("#wizard-suiv").click()
        ill = album.locator(f".wizard-ill .wizard-fixe-{k}")
        expect(ill).to_be_visible()
        expect(ill).to_have_attribute("role", "img")
        assert (ill.get_attribute("aria-label") or "").strip()
        # Chaque image est arrivée, et vient du dossier des illustrations.
        page.wait_for_function("""(k) => [...document.querySelectorAll(
            '.wizard-fixe-' + k + ' img')].every((i) => i.complete && i.naturalWidth > 0)""",
                               arg=k)
        srcs = ill.locator("img").evaluate_all("(is) => is.map((i) => i.getAttribute('src'))")
        assert all(s.startswith("/static/wizard/") for s in srcs), srcs
        assert srcs or k in SANS_IMAGE, k
        # Rien n'y est cliquable.
        assert ill.locator("a, button, input, [tabindex]").count() == 0
        if k == "moteurs":
            expect(ill.locator(".wizard-lus .marque-e").first).to_be_visible()
        if k == "analyse":
            expect(ill.locator(".wizard-entree.cochee")).to_have_count(1)
            expect(ill.locator(".wizard-entree.cochee")).to_be_visible()
        if k == "sortir":
            expect(ill.locator(".wizard-pivot")).to_have_count(3)
            expect(ill.locator(".wizard-zone-mot")).to_have_count(3)
            expect(ill.locator(".wizard-format")).to_have_count(4)
        if k == "carte":
            # L'aperçu des neuf étapes, puis les deux choix en cartes ; « Ne plus afficher »
            # dans la barre du bas.
            expect(ill.locator(".wizard-apercu li")).to_have_count(9)
            for choix in ("rapide", "complet"):
                carte = album.locator(f"#wizard-choix-{choix}")
                expect(carte.locator(".wizard-duree")).to_be_visible()
                expect(carte.locator(".wizard-commencer")).to_be_visible()
            expect(album.locator(".wizard-bas #wizard-jamais")).to_be_visible()
        if k == "collab":
            expect(ill.locator(".wizard-membres li")).to_have_count(3)
            expect(ill.locator(".wizard-doute")).to_be_visible()
    # L'Atelier, dessous, compare sa planche à intervalles (`/empreinte`) : ce n'est pas
    # l'album qui le demande.
    vers_l_api = [u for u in demandes if "/api/" in u and "/empreinte" not in u]
    assert not vers_l_api, vers_l_api
    assert not [u for u in images if "/api/" in u], images


@pytestmark_proxy
def test_reperez_dessine_les_zones_a_leur_place(page, jeu):
    """La page 3 : une étiquette par zone, la bulle et le détail dans le cadre de la case,
    et aucun nom coupé par le bord de l'image."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    page.set_viewport_size({"width": 1280, "height": 800})
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    album = _album(page)
    album.locator("#wizard-suiv").click()
    album.locator("#wizard-suiv").click()
    expect(album.locator("#wizard-compte")).to_have_text("3 / 8")
    ill = album.locator(".wizard-fixe-zones")
    expect(ill).to_be_visible()
    page.wait_for_function("""() => { const i = document.querySelector('.wizard-fixe-zones img');
                                      return !!i && i.complete && i.naturalWidth > 0; }""")
    mesure = page.evaluate("""() => {
      const r = (e) => { const b = e.getBoundingClientRect();
                         return { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
      const s = document.querySelector('.wizard-fixe-zones .wizard-scene');
      const zones = [...s.querySelectorAll('.wizard-zone')].map((z) => ({
        type: [...z.classList].find((c) => c.startsWith('wizard-zone-')).slice(12),
        boite: r(z) }));
      const noms = [...s.querySelectorAll('.wizard-nom')].map((n) => ({
        texte: n.textContent, boite: r(n) }));
      return { scene: r(s), ill: r(s.closest('.wizard-ill')), zones, noms };
    }""")
    zones = mesure["zones"]
    assert [z["type"] for z in zones] == ["case", "bulle", "bulle", "detail"], zones
    noms = mesure["noms"]
    assert len(noms) == len(zones) and all(n["texte"].strip() for n in noms), noms

    def dans(a, b, marge=1):
        return (a["l"] >= b["l"] - marge and a["t"] >= b["t"] - marge
                and a["r"] <= b["r"] + marge and a["b"] <= b["b"] + marge)

    case = zones[0]["boite"]
    assert dans(case, mesure["scene"])
    for z in zones[1:]:
        assert dans(z["boite"], case), (z["type"], z["boite"], case)
    # La case a une vraie taille : l'image est là, pas un cadre écrasé.
    assert case["r"] - case["l"] > 150 and case["b"] - case["t"] > 150, case
    # Chaque nom se lit en entier, et près de sa zone : il la touche ou la jouxte.
    for z, n in zip(zones, noms):
        assert dans(n["boite"], mesure["ill"]), (n, mesure["ill"])
        b, nb = z["boite"], n["boite"]
        assert nb["l"] < b["r"] + 2 and nb["r"] > b["l"] - 2, (z["type"], n)
        assert nb["t"] < b["b"] + 6 and nb["b"] > b["t"] - 6, (z["type"], n)


@pytestmark_proxy
def test_sans_moteur_automatisez_montre_la_rangee_avant_tout_decoupage(page, jeu):
    """La page 4 suit `GET /api/sante` (la seule lecture de l'album) : aucun moteur, la
    rangée sans cadre ni lecture, et la page le dit."""
    page.route("**/api/sante", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body='{"kumiko": false, "bulles": false, "ocr": false}'))
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    album = _album(page)
    for _ in range(3):
        album.locator("#wizard-suiv").click()
    expect(album.locator("#wizard-compte")).to_have_text("4 / 8")
    ill = album.locator(".wizard-fixe-moteurs")
    expect(ill).to_be_visible()
    expect(ill.locator(".wizard-legende")).to_have_text("La planche, avant tout découpage")
    expect(ill.locator(".wizard-scene img")).to_be_visible()
    expect(ill.locator(".wizard-zone")).to_have_count(0)
    expect(ill.locator(".wizard-lus")).to_have_count(0)
    expect(album.locator(".wizard-marque")).to_have_text("optionnel ici")


# ── La visite montre la planche du parcours ────────────────────────────────────────────
#
# Hugo, 2026-11-05 : pendant la visite on peut changer d'album dans l'Atelier ; mais quand la
# visite ARRIVE sur un temps de l'Atelier ou de la page Annotation, elle revient à la planche
# du parcours, où l'on voit comment s'agencent cases et bulles.

@pytest.fixture
def jeu_deux_albums(live_server, tmp_path):
    from test_e2e_bac_a_sable import _outil
    from test_jeu import ecrire_jeu
    docs = JEU_DECOUPE + [{"cle": "stock", "titre": "Le stock", "role": "stock",
                           "planches": [{"fichier": "p2.png"}]}]
    depot = ecrire_jeu(tmp_path / "jeu-depot", docs, images=("p1.png", "p2.png"))
    _outil(tmp_path, "tools/preparer_jeu.py", "--depot", str(depot), "--appliquer")
    _api(live_server, CAMILLE, "GET", "/api/moi")
    return {"base": live_server, "tmp": tmp_path}


@pytestmark_proxy
def test_la_visite_revient_a_la_planche_du_parcours(page, jeu_deux_albums):
    jeu = jeu_deux_albums
    _commencer_la_visite(page, jeu)
    vue = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    parcours = next(j for j in vue["jeu"] if j["role"] == "pas-a-pas")
    autre = next(j for j in vue["jeu"] if j["role"] != "pas-a-pas" and j.get("planche_ids"))
    compte = page.locator("#wizard-visite-compte")
    page.locator("#wizard-visite-suiv").click()
    expect(compte).to_have_text("Visite 2 / 7 · 1 / 2")
    # Au premier temps de l'Atelier, la liste Album est jouable : on change d'album.
    choix = page.locator("#album-select")
    if not choix.locator(f'option[value="{autre["album_id"]}"]').count():
        page.locator("#collection-select").select_option(index=0)
    choix.select_option(str(autre["album_id"]))
    page.wait_for_url(re.compile(rf"album={autre['album_id']}\b"))
    expect(compte).to_have_text("Visite 2 / 7 · 1 / 2")
    # « Suivant → » : la visite revient à la planche du parcours, à son second temps.
    page.locator("#wizard-visite-suiv").click()
    page.wait_for_url(re.compile(rf"album={parcours['album_id']}&planche={parcours['planche_ids'][0]}"))
    expect(compte).to_have_text("Visite 2 / 7 · 2 / 2")
    # La Structure montre ses cases et ses bulles.
    expect(page.locator("#panel .tn-label", has_text="case").first).to_be_visible()
    expect(page.locator("#panel .tn-label", has_text="bulle")).to_have_count(2)


# ── « Pré-remplir » montre ce que font les trois moteurs ───────────────────────────────

@pytestmark_proxy
def test_pre_remplir_montre_les_trois_moteurs_et_lui_seul(page, jeu):
    """Hugo, 2026-11-05 : à l'étape « Pré-remplir », une bande de trois vignettes — Cases,
    Bulles, Texte —, fixe et décrite ; à aucune autre étape."""
    page.set_viewport_size({"width": 1280, "height": 800})
    _au_guide_sur(page, jeu, "complet", "transcrire")
    titre, bande = page.locator("#wizard-fenetre-titre"), page.locator("#wizard-fenetre .wf-visuel")
    expect(titre).to_have_text("Transcrire et relire", timeout=15000)
    expect(bande).to_have_count(0)
    # « Pré-remplir » suit « Transcrire et relire » (Hugo, 2026-11-05).
    page.locator("#wizard-guide-suiv").click()
    expect(titre).to_have_text(re.compile(r"^Pré-remplir"), timeout=15000)
    # En mode Édition, et non dans celui de « Transcrire et relire », d'où l'on vient (Hugo,
    # 2026-11-06) : la colonne de la Transcription s'est retirée, la planche se voit.
    expect(page.locator('.mode-btn[data-mode="edition"]')).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#transcription")).to_be_hidden()
    # Trois paragraphes : les trois moteurs, « jamais parfaits », puis le geste — la planche
    # du jeu n'a pas de bulle, d'où la ligne générique.
    phrases = page.locator("#wizard-fenetre .wf-phrase")
    expect(phrases).to_have_count(3)
    expect(phrases.nth(0)).to_contain_text("contours rouges")
    expect(phrases.nth(1)).to_contain_text("jamais parfaits")
    expect(phrases.nth(2)).to_contain_text("Essayez l'OCR")
    expect(bande).to_be_visible()
    expect(bande).to_have_attribute("role", "img")
    assert (bande.get_attribute("aria-label") or "").strip()
    expect(bande.locator(".wf-vig-titre")).to_have_text(["Cases", "Bulles", "Texte"])
    expect(bande.locator(".wizard-zone-case")).to_have_count(1)
    expect(bande.locator(".wizard-zone-bulle")).to_have_count(2)
    expect(bande.locator(".wf-vig-lus li")).to_have_count(2)
    srcs = bande.locator("img").evaluate_all("(is) => is.map((i) => i.getAttribute('src'))")
    assert srcs and all(s.startswith("/static/wizard/") for s in srcs), srcs
    page.wait_for_function("""() => [...document.querySelectorAll('.wf-visuel img')]
      .every((i) => i.complete && i.naturalWidth > 0)""")
    page.locator("#wizard-guide-suiv").click()
    expect(titre).to_have_text("Annoter", timeout=15000)
    expect(bande).to_have_count(0)


# ── La planche d'essai de « Pré-remplir » ──────────────────────────────────────────────
#
# Hugo, 2026-11-05 : « proposer de faire chaque étape de traitement, mais la planche d'après
# n'est pas celle où les traitements ont été appliqués ». Le jeu pose une planche d'essai
# après celle du parcours ; « Pré-remplir » s'y fait, la planche éclairée avec « Traitement »,
# et les étapes suivantes reviennent à la planche du parcours, que rien n'a touchée.

@pytest.fixture
def jeu_essai(live_server, tmp_path):
    from test_e2e_bac_a_sable import _outil
    from test_jeu import ecrire_jeu
    doc = dict(JEU_DECOUPE[0], planches=[*JEU_DECOUPE[0]["planches"],
                                         {"fichier": "p1.png", "essai": True}])
    depot = ecrire_jeu(tmp_path / "jeu-depot", [doc], images=("p1.png",))
    _outil(tmp_path, "tools/preparer_jeu.py", "--depot", str(depot), "--appliquer")
    _api(live_server, CAMILLE, "GET", "/api/moi")
    return {"base": live_server, "tmp": tmp_path}


@pytestmark_proxy
def test_pre_remplir_se_fait_sur_la_planche_d_essai(page, jeu_essai):
    page.set_viewport_size({"width": 1280, "height": 800})
    _au_guide_sur(page, jeu_essai, "complet", "preremplir")
    vue = _api(jeu_essai["base"], CAMILLE, "GET", "/api/bac-a-sable")
    parcours = next(j for j in vue["jeu"] if j["role"] == "pas-a-pas")
    essai, planche = parcours["planche_essai"], parcours["planche_ids"][0]
    assert essai and essai != planche
    titre = page.locator("#wizard-fenetre-titre")
    expect(titre).to_have_text(re.compile(r"^Pré-remplir"))
    assert re.search(rf"[?&]planche={essai}\b", page.url), page.url
    expect(page.locator('.mode-btn[data-mode="edition"]')).to_have_attribute("aria-pressed", "true")
    phrases = page.locator("#wizard-fenetre .wf-phrase")
    expect(phrases).to_have_count(3)
    # La phrase de Hugo (2026-11-06).
    expect(phrases.nth(2)).to_contain_text("Précédemment, vous avez découpé et transcrit à la "
                                           "main. Voyons maintenant comment automatiser ce "
                                           "travail grâce aux moteurs embarqués.")
    expect(phrases.nth(2)).to_contain_text("et lancez dans l'ordre")
    # Le foyer éclaire « Traitement » ET la planche, et la fenêtre ne recouvre ni l'un ni
    # l'autre.
    page.wait_for_timeout(600)
    m = page.evaluate(MESURE_FOYER)
    assert not m["recouvrent"], m
    assert page.evaluate("""() => window.BDWizardEcran.elementsDuFoyer()
      .some((e) => e.dataset.parcours === 'atelier-planche')""")
    # Les entrées de « Traitement » sont actives dans le guide.
    page.locator("#btn-traitement").click()
    for sel in ("#btn-segmenter", "#btn-bulles", "#btn-ocr"):
        expect(page.locator(sel)).to_be_visible()
        assert page.locator(sel).get_attribute("aria-disabled") != "true", sel
    page.keyboard.press("Escape")
    # Les moteurs passent sur la planche d'essai (simulés : aucun moteur dans les tests).
    avant = _api(jeu_essai["base"], CAMILLE, "GET", f"/api/planches/{planche}/regions")
    case = _api(jeu_essai["base"], CAMILLE, "POST", f"/api/planches/{essai}/regions",
                {"type": "case", "x": 10, "y": 10, "w": 200, "h": 200})
    _api(jeu_essai["base"], CAMILLE, "POST", f"/api/planches/{essai}/regions",
         {"type": "bulle", "x": 20, "y": 20, "w": 60, "h": 20, "parent_id": case["id"]})
    # L'étape suivante revient à la planche du parcours, intacte.
    page.locator("#wizard-guide-suiv").click()
    expect(titre).to_have_text("Annoter", timeout=15000)
    assert re.search(rf"[?&]planche={planche}\b", page.url), page.url
    apres = _api(jeu_essai["base"], CAMILLE, "GET", f"/api/planches/{planche}/regions")
    assert [(r["id"], r["x"], r["y"], r["w"], r["h"]) for r in apres] \
        == [(r["id"], r["x"], r["y"], r["w"], r["h"]) for r in avant]
    assert all(r["source"] == "jeu" for r in apres)


# Hugo, 2026-11-06 : à « Pré-remplir », « cela ne saute pas aux yeux directement et on ignore
# en partie que c'est là qu'il faut cliquer » — le foyer éclairait d'un seul rectangle la
# barre d'actions et la planche. « Traitement » y est le foyer PRINCIPAL : un cadre plein et
# plus épais, serré sur lui, tant que son menu est fermé ; immobile ; à 3:1 sur le fond de
# la barre dans les quatre thèmes ; la fenêtre du guide ne le recouvre pas.

CADRE_PRINCIPAL = """() => {
  const c = document.querySelector('.wizard-voile .wf-cadre.principal');
  if (!c) return null;
  const q = c.getBoundingClientRect();
  const b = document.getElementById('btn-traitement').getBoundingClientRect();
  const f = document.getElementById('wizard-fenetre').getBoundingClientRect();
  const st = getComputedStyle(c);
  return { entoure: q.left <= b.left && q.top <= b.top && q.right >= b.right
                    && q.bottom >= b.bottom,
           recouvert: Math.min(q.right, f.right) - Math.max(q.left, f.left) > 0
                      && Math.min(q.bottom, f.bottom) - Math.max(q.top, f.top) > 0,
           trait: parseFloat(st.strokeWidth), opacite: parseFloat(st.strokeOpacity),
           animation: st.animationName,
           encre: st.stroke, fond: getComputedStyle(document.getElementById('header')).backgroundColor };
}"""


def _rgb(c):
    return [int(float(x)) for x in re.findall(r"[\d.]+", c)[:3]]


def _rapport(a, b):
    def lum(rgb):
        v = [x / 255 for x in rgb]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    la, lb = sorted((lum(_rgb(a)), lum(_rgb(b))), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytestmark_proxy
def test_a_pre_remplir_traitement_saute_aux_yeux(page, jeu_essai):
    page.set_viewport_size({"width": 1280, "height": 800})
    _au_guide_sur(page, jeu_essai, "complet", "preremplir")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text(re.compile(r"^Pré-remplir"))
    cadre = page.locator(".wizard-voile .wf-cadre.principal")
    expect(cadre).to_have_count(1)
    page.wait_for_timeout(600)
    m = page.evaluate(CADRE_PRINCIPAL)
    assert m["entoure"] and not m["recouvert"], m
    # Plus fort que le cadre du foyer : plus épais, et plein.
    foyer = page.evaluate("""() => { const c = document.querySelector(
      '.wizard-voile .wf-cadre:not(.principal)'); const s = getComputedStyle(c);
      return { trait: parseFloat(s.strokeWidth), opacite: parseFloat(s.strokeOpacity) }; }""")
    assert m["trait"] > foyer["trait"] and m["opacite"] == 1 > foyer["opacite"], (m, foyer)
    # Immobile, avec ou sans « moins d'animations ».
    assert m["animation"] == "none", m
    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate(CADRE_PRINCIPAL)["animation"] == "none"
    # 3:1 sur le fond de la barre, dans les quatre thèmes.
    for theme in ("dark", "light"):
        for eleve in (False, True):
            page.evaluate("""([t, e]) => { const r = document.documentElement;
              r.dataset.theme = t; if (e) r.dataset.contrast = 'high';
              else delete r.dataset.contrast; }""", [theme, eleve])
            m = page.evaluate(CADRE_PRINCIPAL)
            assert _rapport(m["encre"], m["fond"]) >= 3, (theme, eleve, m)
    # Le menu ouvert, le cadre s'efface ; refermé, il revient (deux moteurs restent à lancer).
    page.locator("#btn-traitement").click()
    expect(page.locator("#btn-segmenter")).to_be_visible()
    expect(cadre).to_have_count(0)
    page.locator("#btn-traitement").click()
    expect(page.locator("#btn-segmenter")).to_be_hidden()
    expect(cadre).to_have_count(1)
    # Les autres étapes n'ont pas de foyer principal.
    page.locator("#wizard-guide-suiv").click()
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Annoter", timeout=15000)
    page.wait_for_timeout(400)
    expect(cadre).to_have_count(0)


# Hugo, 2026-11-06 : à « Annoter », la fenêtre se posait à la hauteur de la case agrandie —
# « les utilisateurs risquent de cliquer sur la bulle, et non sur la zone où se passe
# l'action ». Posée à côté du foyer, elle s'aligne sur le bloc du texte ; en feuille, le
# texte remonte au-dessus d'elle. Elle ne recouvre ni les mots ni la grille.

PLACE_ANNOTER = """() => {
  const r = (s) => { const q = document.querySelector(s).getBoundingClientRect();
                     return { l: q.left, t: q.top, r: q.right, b: q.bottom }; };
  const fen = document.getElementById('wizard-fenetre');
  return { fen: r('#wizard-fenetre'), feuille: fen.classList.contains('feuille'),
           mots: r('[data-parcours="annotation-mots"]'),
           grille: r('[data-parcours="annotation-grille"]'), haut: innerHeight };
}"""


def _se_recouvrent(a, b):
    return min(a["r"], b["r"]) - max(a["l"], b["l"]) > 1 and min(a["b"], b["b"]) - max(a["t"], b["t"]) > 1


@pytestmark_proxy
@pytest.mark.parametrize("largeur", [1440, 1280, 768])
def test_a_annoter_la_fenetre_se_pose_a_la_hauteur_du_texte(page, jeu, largeur):
    page.set_viewport_size({"width": largeur, "height": 800})
    _au_guide_sur(page, jeu, "complet", "annoter")
    expect(page.locator("#wizard-fenetre-titre")).to_have_text("Annoter", timeout=15000)
    expect(page.locator("#wizard-fenetre .wf-phrase").first).to_contain_text(
        "Cliquez un mot du texte, sous l'image")
    page.wait_for_timeout(1800)          # la feuille, sa réserve, et le texte amené en vue
    m = page.evaluate(PLACE_ANNOTER)
    if largeur == 1440:
        # À côté du foyer : le haut de la fenêtre, celui du bloc du texte.
        assert not m["feuille"], m
        assert abs(m["fen"]["t"] - m["mots"]["t"]) <= 2, m
        assert not _se_recouvrent(m["fen"], m["grille"]), m
    else:
        # En feuille : le bloc du texte se lit en entier, au-dessus d'elle.
        assert m["feuille"], m
        assert m["mots"]["t"] >= 0 and m["mots"]["b"] <= m["fen"]["t"] + 1, m
    assert not _se_recouvrent(m["fen"], m["mots"]), m
    f = page.evaluate(MESURE_FOYER)
    assert f["n"] and not f["recouvrent"], f


# ── « Parcours terminé » ───────────────────────────────────────────────────────────────
#
# Hugo, 2026-11-05 : la fin du parcours était « toute petite », dans la fenêtre du guide.
# C'est une boîte centrée, de la taille de l'album, bâtie comme lui sur `dialog.js`.

def _terminer(page, jeu):
    _au_guide_sur(page, jeu, "rapide", "annoter")
    suiv = page.locator("#wizard-guide-suiv")
    expect(suiv).to_have_text("Terminer")
    suiv.click()
    boite = _album(page)
    expect(boite.locator("#wizard-titre")).to_have_text("Parcours terminé")
    return boite


@pytestmark_proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_parcours_termine_est_une_boite_et_ses_planches_s_ouvrent_sans_guide(page, jeu, theme):
    from test_e2e_bac_a_sable import _audit_axe
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    page.set_viewport_size({"width": 1280, "height": 800})
    boite = _terminer(page, jeu)
    expect(boite.locator(".wizard-boite")).to_have_attribute("role", "dialog")
    # Le voile du guide s'est retiré.
    expect(page.locator("#wizard-fenetre")).to_be_hidden()
    # Les autres planches du jeu, en vraies vignettes, leur titre dessous.
    vue = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    autres = [j for j in vue["jeu"] if j["role"] != "pas-a-pas" and j["planche_ids"]]
    vignettes = boite.locator(".wizard-autre")
    expect(vignettes).to_have_count(len(autres))
    expect(vignettes.first).to_be_focused()
    assert vignettes.first.locator("img").bounding_box()["width"] >= 80
    expect(vignettes.locator("span")).to_have_text([j["titre"] for j in autres])
    expect(boite.locator("#wizard-revoir")).to_be_visible()
    v, f = _audit_axe(page)
    assert not v, f
    # Échap la ferme et rend le focus à « Par où commencer ».
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-modal")).to_be_hidden()
    expect(page.locator("#bac-commencer")).to_be_focused()
    # Rouverte, une vignette ouvre sa planche dans l'Atelier, sans guide.
    boite = _terminer(page, jeu)
    premiere = autres[0]
    boite.locator(".wizard-autre").first.click()
    page.wait_for_url(re.compile(rf"album={premiere['album_id']}&planche={premiere['planche_ids'][0]}"))
    page.wait_for_function("() => !!(window.BDWizardEcran && window.BDWizardEcran.decide)")
    page.wait_for_timeout(500)
    expect(page.locator("#wizard-fenetre:visible")).to_have_count(0)
    expect(page.locator("#wizard-modal:visible")).to_have_count(0)


@pytestmark_proxy
def test_parcours_termine_ne_laisse_pas_sa_forme_a_la_carte(page, jeu):
    """La boîte sert à l'album, à la carte et à la fin : rouverte sur la carte après la
    fin, elle reprend la largeur de la carte et non celle de la fin (52rem), qui lui restait
    jusqu'au rechargement (relecture du 2026-11-05)."""
    page.set_viewport_size({"width": 1280, "height": 800})
    _terminer(page, jeu)
    page.keyboard.press("Escape")
    expect(page.locator("#wizard-modal")).to_be_hidden()
    page.locator("#bac-commencer").click()
    boite = _album(page).locator(".wizard-boite")
    expect(boite).to_have_class(re.compile(r"\bwizard-carte\b"))
    expect(boite).not_to_have_class(re.compile(r"\bwizard-termine\b"))
    # La largeur de la carte — celle de `.modal-box`, 43rem, qui l'emporte sur les 40rem de
    # `.wizard-boite`, plus haut dans la feuille — et non celle de la fin (52rem).
    largeur = boite.evaluate("""(b) => [parseFloat(getComputedStyle(b).width),
      parseFloat(getComputedStyle(document.documentElement).fontSize)]""")
    assert largeur[0] < 48 * largeur[1], largeur
    # « Revoir la présentation » depuis la fin : l'album, sans les marges de la fin.
    page.keyboard.press("Escape")
    boite = _terminer(page, jeu).locator(".wizard-boite")
    boite.locator("#wizard-revoir").click()
    expect(boite).to_have_class(re.compile(r"\bwizard-album\b"))
    expect(boite).not_to_have_class(re.compile(r"\bwizard-termine\b"))


@pytestmark_proxy
def test_parcours_termine_tient_a_320_px_sous_grande_police(page, jeu):
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    from test_e2e_bac_a_sable import _perdus, _preference_police
    from tools.mesurer_reflow import ECRASEMENT, decrire_ecrasement
    _preference_police(page, 24)
    page.set_viewport_size({"width": 320, "height": 800})
    _terminer(page, jeu)
    page.wait_for_timeout(300)
    assert not _perdus(page), _perdus(page)[:3]
    assert not decrire_ecrasement(page.evaluate(ECRASEMENT, ".wizard-boite"))
