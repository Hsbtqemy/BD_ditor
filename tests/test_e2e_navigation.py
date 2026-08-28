"""Tests E2E (navigateur réel via Playwright) des surfaces : round-trip & reprise
d'état, citation (Visionneuse), rôle récit/paratexte (Corpus), recherche → aperçu.

Couvre ce qu'aucun test serveur ne peut atteindre : le COMPORTEMENT front (deep-link,
bouton « ← Retour », chaîne `retour`, durcissement anti-XSS, rendu des surfaces) dans
un vrai Chromium pilotant l'app lancée (fixture `live_server`).

Marqués `e2e` → hors du run rapide par défaut (`pytest -m e2e` pour les lancer).
Skippés proprement si Playwright n'est pas installé.
"""
import re
from urllib.parse import quote

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

# AUTH-2 : `ADMIN` monte le décor avec les droits qu'il faut (sans effet hors proxy).
from conftest import ADMIN, make_png  # noqa: E402

pytestmark = pytest.mark.e2e


@pytest.fixture
def seeded(live_server):
    """Album + planche + une case, créés via l'API sur le serveur live. Renvoie les
    ids et l'URL de base pour construire des deep-links."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 10, "y": 10, "w": 80, "h": 60}).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


def _viewer_url(s, extra=""):
    return (f"{s['base']}/?album={s['album']}&planche={s['planche']}"
            f"&region={s['region']}{extra}")


def test_deep_link_ouvre_la_region(page, seeded):
    """Un lien profond /?album&planche&region ouvre la Visionneuse pile sur la
    région (applyDeepLink + anti-course plancheGen)."""
    page.goto(_viewer_url(seeded))
    expect(page.locator("#region-id")).to_have_text(f"#{seeded['region']}", timeout=15000)


def test_back_link_depuis_retour_interne(page, seeded):
    """Avec un `retour` interne valide, le bouton « ← Retour » apparaît, pointe
    dessus, et y ramène au clic."""
    page.goto(_viewer_url(seeded, "&retour=%2Frecherche%3Fq%3Dpouvoir"))
    back = page.locator("#back-link")
    expect(back).to_be_visible(timeout=15000)
    assert back.get_attribute("href").endswith("/recherche?q=pouvoir")
    back.click()
    expect(page).to_have_url(re.compile(r"/recherche\?q=pouvoir"))


def test_retour_javascript_est_rejete(page, seeded):
    """`retour=javascript:…` est rejeté par safeRetour → bouton masqué, aucune
    surface d'XSS via le href du ← Retour."""
    page.goto(_viewer_url(seeded, "&retour=javascript:alert(1)"))
    expect(page.locator("#region-id")).to_have_text(f"#{seeded['region']}", timeout=15000)
    expect(page.locator("#back-link")).to_be_hidden()


def test_etat_recherche_restaure_au_chargement(page, seeded):
    """La Recherche restaure sa requête depuis l'URL (reprise d'état au reload)."""
    page.goto(f"{seeded['base']}/recherche?q=bonjour")
    expect(page.locator("#q")).to_have_value("bonjour", timeout=15000)


def test_chaine_retour_deux_niveaux(page, seeded):
    """Round-trip complet : Visionneuse ──← Retour──▶ Recherche ──← Retour──▶
    Exploration, avec l'état de chaque surface restauré (chaîne `retour` à 2 niveaux)."""
    expl = "/exploration?champ=lemme"
    rech = "/recherche?q=x&retour=" + quote(expl, safe="")
    page.goto(_viewer_url(seeded, "&retour=" + quote(rech, safe="")))

    page.locator("#back-link").click()                 # Visionneuse → Recherche
    expect(page).to_have_url(re.compile(r"/recherche"))
    expect(page.locator("#q")).to_have_value("x", timeout=15000)

    page.locator("#back-link").click()                 # Recherche → Exploration
    expect(page).to_have_url(re.compile(r"/exploration"))
    expect(page.locator("#f-champ")).to_have_value("lemme", timeout=15000)


# --------------------------------------------------------------------------- #
# Autres surfaces : citation (Visionneuse), rôle (Corpus), recherche → aperçu
# --------------------------------------------------------------------------- #
def test_visionneuse_affiche_la_citation(page, seeded):
    """Sélectionner une région (deep-link) affiche sa citation éditoriale dans le
    panneau de détail (Lot 1 : pl·c)."""
    page.goto(_viewer_url(seeded))
    expect(page.locator("#region-citation")).to_contain_text("pl.1 · c1", timeout=15000)


@pytest.fixture
def seeded_corpus(live_server):
    """Album + DEUX planches récit (pour observer la renumérotation au marquage)."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E corpus"}).json()["id"]
        for _ in range(2):
            c.post(f"/api/albums/{aid}/import",
                   files={"file": ("p.png", make_png(), "image/png")})
    finally:
        c.close()
    return {"base": live_server, "album": aid}


def test_corpus_marquer_paratexte_renumerote(page, seeded_corpus):
    """Sur la Bibliothèque : ouvrir un album, marquer la 1re planche « paratexte »
    → elle sort de la numérotation (Lot 0, corpus.js)."""
    page.goto(f"{seeded_corpus['base']}/corpus")
    page.locator("#albums-body tr td.c-titre").first.click()   # ouvrir l'album
    detail = page.locator("#album-detail")
    expect(detail).to_contain_text("planche 1", timeout=15000)
    expect(detail).to_contain_text("planche 2")                # 2 planches récit au départ
    detail.locator("button[data-role]").first.click()          # 1re planche → paratexte
    expect(detail).to_contain_text("Paratexte", timeout=15000)
    # renumérotation effective : il ne reste qu'UNE planche récit → plus de « planche 2 ».
    expect(detail).not_to_contain_text("planche 2")


@pytest.fixture
def seeded_ocr(live_server):
    """Album + planche + une case contenant une bulle océrisée (texte indexé)."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E ocr"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        cid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "case", "x": 10, "y": 10, "w": 80, "h": 60}).json()["id"]
        bid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 15, "y": 15, "w": 30, "h": 20,
                           "parent_id": cid, "ocr_texte": "BONJOURXYZ"}).json()["id"]
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": bid}


def test_recherche_resultat_apercu_et_lien_edition(page, seeded_ocr):
    """Recherche plein texte : la bulle océrisée remonte avec sa citation (pl·c·b),
    le clic ouvre l'aperçu, et le lien ✏️ embarque la région + le retour (départ du
    round-trip avec une vraie recherche)."""
    s = seeded_ocr
    page.goto(f"{s['base']}/recherche?q=BONJOURXYZ")
    card = page.locator("#results .result").first
    expect(card).to_be_visible(timeout=15000)
    expect(card.locator(".r-cite")).to_have_text("pl.1 · c1 · b1")
    card.click()                                          # ouvre l'aperçu en place
    expect(page.locator("#preview")).to_be_visible()
    href = page.locator("#preview-edit").get_attribute("href")
    assert f"region={s['region']}" in href and "retour=" in href


def test_visionneuse_menu_import_export(page, live_server):
    """En-tête de la Visionneuse : ShareDocs n'est plus dans « Traitement » (réservé
    aux 3 passes ML) ; il est sous « Import / Export », section Importer, à côté de
    l'import d'images et des exports."""
    page.goto(f"{live_server}/")
    expect(page.locator("#traitement-menu")).not_to_contain_text("ShareDocs")
    page.locator("#btn-donnees").click()                  # ouvrir « Import / Export »
    menu = page.locator("#donnees-menu")
    expect(menu).to_be_visible()
    expect(menu).to_contain_text("Importer des images")
    expect(menu).to_contain_text("Sauvegarde")
    # Groupé SÉMANTIQUEMENT (role=group + aria-label) → lisible aux lecteurs d'écran :
    # ShareDocs sous « Importer », TEI sous « Exporter ».
    expect(menu.locator('[role="group"][aria-label="Importer"]')).to_contain_text("ShareDocs")
    expect(menu.locator('[role="group"][aria-label="Exporter"]')).to_contain_text("TEI")
    # placeholder « à venir » : présent mais désactivé (non cliquable)
    expect(menu.locator('button:has-text("Importer un PDF")')).to_be_disabled()
    # le bouton ShareDocs DÉPLACÉ reste fonctionnel : un clic ouvre bien la modale
    # (la modale s'affiche avant tout fetch → robuste sans config ShareDocs).
    menu.locator("#btn-sharedocs").click()
    expect(page.locator("#sharedocs")).to_be_visible()


def test_un_seul_menu_ouvert_a_la_fois(page, seeded):
    """Coordination inter-systèmes (événement bd:menu-open) : ouvrir le menu
    « Affichage » (theme.js, bande 1) ferme le dropdown ouvert du visualiseur
    (bande 2) — un seul menu ouvert, toutes barres confondues. Le code est symétrique
    (ouvrir un dropdown ferme aussi « Affichage »)."""
    page.goto(_viewer_url(seeded))
    page.locator("#btn-donnees").click()                        # Import/Export ouvert
    expect(page.locator("#donnees-menu")).to_be_visible()
    page.locator(".btn-theme").click()                          # ouvrir « Affichage »…
    expect(page.locator(".display-panel")).to_be_visible()
    expect(page.locator("#donnees-menu")).not_to_be_visible()   # …ferme Import/Export


def _recouvert_par(page, selector, by_selector):
    """Vrai si le centre de l'élément est RECOUVERT par un élément correspondant à
    `by_selector` (≠ lui-même et ≠ un de ses descendants) — quel que soit le
    recouvreur (#transcription, #header…)."""
    return page.evaluate(
        """([sel, by]) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
            if (!top || top === el || el.contains(top)) return false;
            return !!top.closest(by);
        }""", [selector, by_selector])


def test_transcription_planche_sans_texte(page, seeded):
    """Planche sans région de texte : pas d'image cassée (le cadre « dédoublé » venait
    de l'icône d'image cassée), mais un message propre — #tr-crop masqué, #tr-empty
    visible."""
    page.goto(_viewer_url(seeded))
    page.locator('[data-mode="transcription"]').click()
    expect(page.locator("#transcription")).to_be_visible()
    expect(page.locator("#tr-progress")).to_have_text("Aucune région de texte")
    expect(page.locator("#tr-crop")).to_be_hidden()
    expect(page.locator("#tr-empty")).to_be_visible()


def test_menus_au_dessus_du_panneau_transcription(page, seeded_ocr):
    """En mode transcription, le panneau plein écran (#transcription) ne doit PAS
    masquer les menus de l'en-tête : leurs items restent peints AU-DESSUS de
    l'overlay (sinon ils sont inaccessibles)."""
    s = seeded_ocr
    page.goto(f"{s['base']}/?album={s['album']}&planche={s['planche']}")
    page.locator('[data-mode="transcription"]').click()
    expect(page.locator("#transcription")).to_be_visible()
    # Menu bande 2 « Import / Export » : son item n'est pas masqué par l'overlay.
    page.locator("#btn-donnees").click()
    assert _recouvert_par(page, "#btn-backup", "#transcription") is False
    # Menu « Affichage » (bande 1) : ni sous l'overlay, NI sous la bande 2 (#header) —
    # la bande 1 doit recouvrir la bande 2 (sinon le menu s'ouvre derrière elle).
    page.locator(".btn-theme").click()
    assert _recouvert_par(page, ".display-panel button", "#transcription") is False
    assert _recouvert_par(page, ".display-panel button", "#header") is False


# --------------------------------------------------------------------------- #
# Navigation transverse unifiée + menus de la Visionneuse (theme.js)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path,label", [
    ("/", "Atelier"),
    ("/corpus", "Bibliothèque"),
    ("/recherche", "Recherche"),
    ("/exploration", "Exploration"),
])
def test_nav_unifiee_injectee_et_surbrillance(page, live_server, path, label):
    """La barre de nav est injectée à l'identique sur les 4 surfaces (4 liens), et la
    surface courante — et elle seule — porte aria-current=page (« vous êtes ici »)."""
    page.goto(f"{live_server}{path}")
    expect(page.locator(".surf-nav a.surf-link")).to_have_count(4, timeout=15000)
    current = page.locator('.surf-nav a[aria-current="page"]')
    expect(current).to_have_count(1)
    expect(current).to_contain_text(label)


def test_menus_visionneuse_un_seul_ouvert_et_echap(page, live_server):
    """Visionneuse : Traitement/Données s'ouvrent au clic, un seul à la fois (ouvrir
    l'un referme l'autre), et Échap referme — cf. setupMenus()."""
    page.goto(f"{live_server}/")
    trait, donnees = page.locator("#traitement-menu"), page.locator("#donnees-menu")
    expect(trait).to_be_hidden(timeout=15000)

    page.locator("#btn-traitement").click()
    expect(trait).to_be_visible()

    page.locator("#btn-donnees").click()          # un seul ouvert à la fois
    expect(trait).to_be_hidden()
    expect(donnees).to_be_visible()

    page.keyboard.press("Escape")                 # Échap referme
    expect(donnees).to_be_hidden()


def test_menu_navigation_au_clavier(page, live_server):
    """Visionneuse : les menus d'en-tête sont de vrais menus ARIA (motif APG « menu
    button ») navigables au clavier — ↓ ouvre et entre sur le 1er item, ↓ boucle, Fin
    va au dernier, Échap referme EN RENDANT le focus au déclencheur (cf. setupMenus)."""
    page.goto(f"{live_server}/")
    btn, menu = page.locator("#btn-traitement"), page.locator("#traitement-menu")
    expect(menu).to_have_attribute("role", "menu", timeout=15000)

    btn.focus()
    page.keyboard.press("ArrowDown")                       # ouvre + focus 1er item
    expect(menu).to_be_visible()
    expect(btn).to_have_attribute("aria-expanded", "true")
    seg = page.locator("#btn-segmenter")
    expect(seg).to_be_focused()
    expect(seg).to_have_attribute("role", "menuitem")

    page.keyboard.press("ArrowDown")                       # item suivant
    expect(page.locator("#btn-bulles")).to_be_focused()
    page.keyboard.press("End")                             # dernier
    expect(page.locator("#btn-ocr")).to_be_focused()
    page.keyboard.press("ArrowDown")                       # boucle → premier
    expect(seg).to_be_focused()

    page.keyboard.press("Escape")                          # ferme + rend le focus
    expect(menu).to_be_hidden()
    expect(btn).to_be_focused()


def test_menu_clavier_espace_ouvre_et_tab_referme(page, live_server):
    """Compléments clavier : Espace ouvre et entre sur le 1er item SANS rebascule
    (le clic natif d'Espace arrive au keyup, après l'ouverture au keydown → garde
    anti-flicker), et Tab referme en avançant vers le contrôle suivant (Import/Export).
    Vérifie aussi l'isolation : ← en menu ouvert ne navigue pas entre les régions."""
    page.goto(f"{live_server}/")
    trait, menu = page.locator("#btn-traitement"), page.locator("#traitement-menu")
    trait.focus()
    page.keyboard.press("Space")                          # chemin le plus à risque
    expect(menu).to_be_visible(timeout=15000)
    expect(page.locator("#btn-segmenter")).to_be_focused()
    page.keyboard.press("ArrowLeft")                      # isolé : reste dans le menu
    expect(menu).to_be_visible()
    expect(page.locator("#btn-segmenter")).to_be_focused()
    page.keyboard.press("Tab")                            # referme + avance
    expect(menu).to_be_hidden()
    expect(page.locator("#btn-donnees")).to_be_focused()


def test_menu_affichage_ferme_par_defaut(page, live_server):
    """Régression : le panneau « Affichage » (Aa) est masqué au chargement, puis
    s'ouvre / se referme au clic. Garde .display-panel[hidden] — sans lui, le
    display:flex écrasait l'attribut hidden et le menu restait ouvert en permanence."""
    page.goto(f"{live_server}/")
    panel = page.locator(".display-panel")
    expect(panel).to_be_hidden(timeout=15000)
    page.locator(".btn-theme").click()
    expect(panel).to_be_visible()
    page.locator(".btn-theme").click()
    expect(panel).to_be_hidden()


# --------------------------------------------------------------------------- #
# Modales accessibles (static/lib/dialog.js) : role=dialog, focus piégé, Échap,
# retour du focus au déclencheur
# --------------------------------------------------------------------------- #
def test_modale_album_accessible(page, live_server):
    """Bibliothèque : la modale « Nouvel album » est un vrai dialogue —
    role=dialog + aria-modal + nom accessible, focus posé sur le 1er champ à
    l'ouverture, et Échap referme EN RENDANT le focus au déclencheur."""
    page.goto(f"{live_server}/corpus")
    page.locator("#btn-new").click()
    modal = page.locator("#album-modal")
    expect(modal).to_be_visible(timeout=15000)

    box = page.locator("#album-modal .modal-box")
    expect(box).to_have_attribute("role", "dialog")
    expect(box).to_have_attribute("aria-modal", "true")
    expect(box).to_have_attribute("aria-labelledby", "modal-title")
    expect(page.locator("#m-titre")).to_be_focused()          # focus dans la boîte

    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    expect(page.locator("#btn-new")).to_be_focused()          # focus rendu au déclencheur


def test_modale_album_piege_le_focus(page, live_server):
    """Le focus clavier ne s'échappe pas de la modale : Maj+Tab depuis le 1er
    champ boucle vers le dernier focusable (il reste DANS la boîte)."""
    page.goto(f"{live_server}/corpus")
    page.locator("#btn-new").click()
    expect(page.locator("#m-titre")).to_be_focused(timeout=15000)
    page.keyboard.press("Shift+Tab")
    reste_dans_la_boite = page.evaluate(
        "() => !!document.activeElement.closest('#album-modal .modal-box')")
    assert reste_dans_la_boite


def test_modale_sharedocs_accessible_et_echap(page, live_server):
    """Visionneuse : la modale ShareDocs est un dialogue (role/aria-modal/nom) et
    Échap la referme (même chemin que le clic sur le fond)."""
    page.goto(f"{live_server}/")
    page.locator("#btn-donnees").click()
    page.locator("#btn-sharedocs").click()
    sd = page.locator("#sharedocs")
    expect(sd).to_be_visible(timeout=15000)

    box = page.locator("#sharedocs .sd-dialog")
    expect(box).to_have_attribute("role", "dialog")
    expect(box).to_have_attribute("aria-modal", "true")
    expect(box).to_have_attribute("aria-labelledby", "sd-title")

    page.keyboard.press("Escape")
    expect(sd).to_be_hidden()


def test_boutons_mode_aria_pressed(page, live_server):
    """Les boutons de mode exposent leur état sélectionné aux lecteurs d'écran
    (aria-pressed), mis à jour AU CLIC comme AU RACCOURCI clavier ; l'indicateur de
    mode est une région live → la bascule au clavier (N/E/A/T) est annoncée même
    quand le focus n'est pas sur les boutons."""
    page.goto(f"{live_server}/")
    nav = page.locator('.mode-btn[data-mode="navigation"]')
    edi = page.locator('.mode-btn[data-mode="edition"]')
    ann = page.locator('.mode-btn[data-mode="annotation"]')
    expect(nav).to_have_attribute("aria-pressed", "true", timeout=15000)
    expect(edi).to_have_attribute("aria-pressed", "false")

    edi.click()                                   # clic → Édition actif, Navigation off
    expect(edi).to_have_attribute("aria-pressed", "true")
    expect(nav).to_have_attribute("aria-pressed", "false")

    page.keyboard.press("a")                      # raccourci → Annotation
    expect(ann).to_have_attribute("aria-pressed", "true")
    expect(edi).to_have_attribute("aria-pressed", "false")
    # l'indicateur de mode (région live) reflète la bascule
    expect(page.locator("#stat-mode")).to_have_text("Mode : Annotation")
    expect(page.locator("#stat-mode")).to_have_attribute("aria-live", "polite")


def test_filtres_recherche_ont_un_nom_accessible(page, live_server):
    """Recherche : les contrôles de filtre, sans <label> visible, portent un
    aria-label → un lecteur d'écran annonce leur fonction (avant, ils n'avaient que
    le texte de l'option par défaut)."""
    page.goto(f"{live_server}/recherche")
    expect(page.locator("#q")).to_have_attribute(
        "aria-label", "Rechercher dans les dialogues, notes et tags", timeout=15000)
    expect(page.locator("#f-album")).to_have_attribute("aria-label", "Filtrer par album")
    expect(page.locator("#f-type")).to_have_attribute("aria-label", "Filtrer par type de région")
    # facettes grammaticales (dans un <details>) : nommées aussi
    expect(page.locator("#f-pos")).to_have_attribute(
        "aria-label", "Filtrer par catégorie grammaticale (POS)")


def test_filtres_exploration_distinguent_les_sous_corpus(page, live_server):
    """Exploration : les filtres du sous-corpus B sont nommés distinctement de ceux
    de A (préfixe « Sous-corpus B ») → un lecteur d'écran ne confond pas les deux
    colonnes en mode comparaison."""
    page.goto(f"{live_server}/exploration")
    expect(page.locator("#f-album")).to_have_attribute(
        "aria-label", "Filtrer par album", timeout=15000)
    expect(page.locator("#b-album")).to_have_attribute(
        "aria-label", "Sous-corpus B — filtrer par album")


def test_nettoyage_libelles_accessibles(page, live_server):
    """Nettoyage a11y : le raccourci <kbd> des boutons de mode est masqué aux lecteurs
    d'écran → nom accessible « Navigation » (et non « Navigation N ») ; les en-têtes de
    colonnes sans texte (sélection / actions) de la Bibliothèque portent un aria-label."""
    page.goto(f"{live_server}/")
    expect(page.locator('.mode-btn[data-mode="navigation"] kbd')).to_have_attribute(
        "aria-hidden", "true", timeout=15000)
    expect(page.get_by_role("button", name="Navigation", exact=True)).to_be_visible()

    page.goto(f"{live_server}/corpus")
    head = page.locator(".corpus-table thead")
    expect(head.locator("th.c-chk")).to_have_attribute("aria-label", "Sélection", timeout=15000)
    expect(head.locator('th[aria-label="Actions"]')).to_have_count(1)


def test_confort_de_lecture(page, live_server):
    """Réglage « Confort de lecture » (menu Affichage) : la bascule pose data-lecture
    sur <html>, aère le texte de lecture (espacement appliqué à #tr-text), et persiste
    au rechargement — réappliqué AVANT rendu comme le thème (theme.js en <head>)."""
    page.goto(f"{live_server}/")
    page.locator(".btn-theme").click()                         # ouvre le menu Affichage
    panel = page.locator(".display-panel")
    expect(panel).to_be_visible(timeout=15000)
    cb = panel.get_by_role("checkbox", name="Confort de lecture")
    expect(cb).not_to_be_checked()

    ls = "() => getComputedStyle(document.querySelector('#tr-text')).letterSpacing"
    avant = page.evaluate(ls)
    cb.check()
    expect(page.locator("html")).to_have_attribute("data-lecture", "confort")
    apres = page.evaluate(ls)
    assert avant == "normal" and apres != "normal", (avant, apres)   # aération effective

    page.reload()                                              # persiste, posé avant rendu
    expect(page.locator("html")).to_have_attribute("data-lecture", "confort", timeout=15000)


@pytest.mark.parametrize("path", ["/", "/corpus", "/recherche", "/exploration"])
def test_deux_bandes_navigation_au_dessus_des_outils(page, live_server, path):
    """Structure en deux bandes : la bande 1 (#site-nav, navigation) est tout en haut
    et identique partout (4 surfaces) ; la bande 2 (#header, outils de page) est juste
    en dessous, sans chevauchement. Garantit la séparation navigation / outils."""
    page.goto(f"{live_server}{path}")
    nav = page.locator("#site-nav")
    expect(nav).to_be_visible(timeout=15000)
    expect(page.locator("#site-nav .surf-nav a.surf-link")).to_have_count(4)
    nb, hb = nav.bounding_box(), page.locator("#header").bounding_box()
    assert nb["y"] == 0                                 # nav tout en haut
    assert hb["y"] >= nb["y"] + nb["height"] - 1        # outils dessous, pas de chevauchement


def test_creation_album_demande_sa_collection(page, seeded):
    """AUTH-2 — la collection est l'unité de cloisonnement : l'UI la demande à la création.

    `seeded` a déjà créé un album, donc la collection de repli existe : il y en a
    exactement une, et elle doit être PRÉSÉLECTIONNÉE — poser une question dont la
    réponse est unique serait de la cérémonie, pas de l'explicite.
    """
    page.goto(seeded["base"] + "/corpus")
    page.locator("#btn-new").click()
    expect(page.locator("#album-modal")).to_be_visible(timeout=15000)
    sel = page.locator("#m-collection")
    expect(page.locator("#m-collection-wrap")).to_be_visible()
    expect(sel).not_to_have_value("")                       # présélectionnée
    choisie = sel.input_value()

    page.fill("#m-titre", "Album rangé")
    page.locator("#m-save").click()
    expect(page.locator("#album-modal")).to_be_hidden(timeout=15000)

    c = httpx.Client(base_url=seeded["base"], trust_env=False, timeout=30,
                     headers=ADMIN)
    try:
        cols = {str(x["id"]): x for x in c.get("/api/collections").json()}
        assert choisie in cols
        # L'album est bien rangé : la collection choisie en compte un de plus qu'avant.
        assert cols[choisie]["nb_albums"] >= 2
    finally:
        c.close()


def test_le_champ_collection_disparait_a_l_edition(page, seeded):
    """Déplacer un album d'une collection à l'autre est un geste d'ESPACE DE TRAVAIL,
    qui appartient à AUTH-3. Le champ ne doit donc pas apparaître à l'édition, où il
    laisserait croire à un déplacement possible."""
    page.goto(seeded["base"] + "/corpus")
    page.locator('.album-row [data-act="edit"]').first.click()
    expect(page.locator("#album-modal")).to_be_visible(timeout=15000)
    expect(page.locator("#m-collection-wrap")).to_be_hidden()
    expect(page.locator("#m-collection-note")).to_be_hidden()
