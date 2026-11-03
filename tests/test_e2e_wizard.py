"""UX-6 — « Par où commencer », joué dans un vrai navigateur, dans un bac à sable.

La forme a été tranchée par Hugo sur maquette le 2026-11-02 (`pilotage/UX-6.md`) : un
ALBUM de présentation qui s'ouvre seul après « Mon bac à sable », avec « Passer » et
« Fermer ✕ », dont la dernière page fait choisir un parcours ; le souvenir — l'album vu, le
parcours, l'étape — vit dans le navigateur, rangé par login et sous l'identifiant du bac à
sable (Hugo, 2026-11-03). Cette tranche pose l'album et la CARTE des étapes ; la fenêtre
sur la zone et la visite des pages viendront ensuite.

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

SURFACES_AUDITEES = {"/": "l'Atelier, où « Mon bac à sable » mène et où l'album s'ouvre seul"}
SURFACES_HORS_PERIMETRE = {
    "/annotation": "le même script partagé que l'Atelier ; l'ouverture seule y suit la même "
                   "règle, jouée une fois sur la surface d'arrivée",
    "/corpus": "le même script partagé que l'Atelier ; l'ouverture seule y suit la même "
               "règle, jouée une fois sur la surface d'arrivée",
    "/recherche": "le même script partagé que l'Atelier ; l'ouverture seule y suit la même "
                  "règle, jouée une fois sur la surface d'arrivée",
    "/exploration": "le même script partagé que l'Atelier ; l'ouverture seule y suit la même "
                    "règle, jouée une fois sur la surface d'arrivée",
    "/administration": "le même script partagé que l'Atelier ; l'ouverture seule y suit la "
                       "même règle, jouée une fois sur la surface d'arrivée",
}

SOUVENIR = "() => { try { return localStorage.getItem('bd-wizard'); } catch (e) { return null; } }"


def _album(page):
    voile = page.locator("#wizard-modal")
    expect(voile).to_be_visible()
    return voile


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


# ── Accessibilité et petites fenêtres ──────────────────────────────────────────────────

@pytestmark_proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_l_album_et_la_carte(page, jeu, theme):
    """axe (WCAG 2.1 AA), album ouvert sur sa première page, sur la page du choix, puis
    la carte des étapes : aucune violation sérieuse ou critique."""
    from test_e2e_bac_a_sable import _audit_axe
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    _arriver(page, jeu["base"])
    page.locator("#bac-commencer").click()
    album = _album(page)
    rapports = []
    for quoi, geste in (("album, première page", None),
                        ("album, choix du parcours", "#wizard-passer"),
                        ("carte des étapes", "#wizard-choix-complet")):
        if geste:
            album.locator(geste).click()
        page.wait_for_timeout(250)
        v, f = _audit_axe(page)
        if v:
            rapports.append(f"{quoi} :\n{f}")
    assert not rapports, "\n".join(rapports)


@pytestmark_proxy
def test_l_album_et_la_carte_tiennent_a_320_px_sous_grande_police(page, jeu):
    """À 320 px, sous des préférences de 16 et 24 : l'album et la carte ne perdent rien et
    ne s'écrasent pas, et la ligne qui porte « Par où commencer » non plus."""
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
        perdus = _perdus(page)
        if perdus:
            echecs.append(f"ligne, police {police} : {perdus[:3]}")
        page.locator("#bac-commencer").click()
        album = _album(page)
        for quoi, geste in (("album", None), ("choix", "#wizard-passer"),
                            ("carte", "#wizard-choix-rapide")):
            if geste:
                album.locator(geste).click()
            page.wait_for_timeout(250)
            perdus = _perdus(page)
            if perdus:
                echecs.append(f"{quoi}, police {police} : {perdus[:3]}")
            ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, ".wizard-boite"))
            if ecrase:
                echecs.append(f"{quoi}, police {police} : ÉCRASÉ\n" + "\n".join(ecrase))
        page.keyboard.press("Escape")
        expect(page.locator("#wizard-modal")).to_be_hidden()
        # La carte est retenue : le tour suivant repart d'un souvenir neuf.
        page.evaluate("() => { try { localStorage.removeItem('bd-wizard'); } catch (e) {} }")
    assert not echecs, "\n".join(echecs)
