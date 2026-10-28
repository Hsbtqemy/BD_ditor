"""La planche ouverte a changé ailleurs : l'Atelier le SIGNALE, et « Actualiser » ne perd rien
(CONC-4 ; réécrit par Hugo le 2026-10-21 — ni temps réel ni rien, un signal).

Mesuré sur le code d'avant (CONC-3, mesure 3, 2026-09-16) : l'Atelier charge les régions à
l'ouverture d'une planche et ne les recharge plus ; une région créée ou supprimée ailleurs n'y
apparaissait jamais, et rien ne le disait. Il compare désormais de temps en temps — et au
retour sur l'onglet — l'empreinte de la planche à celle qu'il avait, et montre le bouton
« Actualiser » dans la barre d'outils, avec une infobulle qui dit combien.

Deux contextes de navigateur derrière le proxy : Bob a la planche ouverte ; Alice change des
régions, par l'API (le geste d'un autre écran, ou d'une passe automatique). « Retour sur
l'onglet » se joue en émettant `visibilitychange` sur un document visible ; l'intervalle, par
l'horloge de Playwright.
"""
import time

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "« ⟳ Actualiser » ne vient sur la page Annotation qu'au jalon 2 (commit "
        "6), avec son audit"),
    "/recherche": "aucune planche n'y est ouverte : le signal ne vit que dans l'Atelier",
    "/corpus": "aucune planche n'y est ouverte : le signal ne vit que dans l'Atelier",
    "/exploration": "aucune planche n'y est ouverte : le signal ne vit que dans l'Atelier",
    "/administration": "aucune planche n'y est ouverte : le signal ne vit que dans l'Atelier",
}

ADMIN = {"Remote-User": "decor", "Remote-Groups": "bd-admins", "X-BD-Requete": "1"}
ALICE = {"Remote-User": "alice", "Remote-Groups": "bd-admins", "Remote-Name": "Alice Dupont",
         "X-BD-Requete": "1"}
BOB = {"Remote-User": "bob", "Remote-Groups": "bd-admins", "Remote-Name": "Bob Martin"}


def _client(base, headers=ADMIN):
    return httpx.Client(base_url=base, trust_env=False, timeout=30, headers=headers)


@pytest.fixture
def decor(live_server):
    with _client(live_server) as c:
        aid = c.post("/api/albums", json={"titre": "E2E signal"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        case = c.post(f"/api/planches/{pid}/regions",
                      json={"type": "case", "x": 10, "y": 10, "w": 300, "h": 200}).json()["id"]
        bulles = []
        for i, texte in enumerate(("PREMIÈRE", "SECONDE", "TROISIÈME")):
            rid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "x": 20 + 90 * i, "y": 20, "w": 60, "h": 30,
                               "parent_id": case}).json()["id"]
            c.put(f"/api/regions/{rid}", json={"ocr_texte": texte})
            bulles.append(rid)
    return {"base": live_server, "planche": pid, "case": case, "bulles": bulles,
            "url": f"{live_server}/?album={aid}&planche={pid}"}


def _ouvrir(page, url, identite=BOB):
    ctx = page.context.browser.new_context(extra_http_headers=identite)
    p = ctx.new_page()
    p.empreintes = []
    p.on("request", lambda r: p.empreintes.append(r.url) if r.url.endswith("/empreinte") else None)
    p.goto(url, wait_until="networkidle")
    return ctx, p


def _retour_sur_l_onglet(p):
    """Le document est visible : `visibilitychange` est ce que le navigateur émet au retour."""
    with p.expect_response(lambda r: r.url.endswith("/empreinte")):
        p.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    p.wait_for_load_state("networkidle")


def _ids_a_l_ecran(p):
    return set(p.eval_on_selector_all("#overlay rect.region", "els => els.map(e => +e.dataset.id)"))


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_une_planche_changee_ailleurs_propose_actualiser_et_actualiser_la_recharge(page, decor):
    s = decor
    ctx, b = _ouvrir(page, s["url"])
    try:
        bouton = b.locator("#planche-actualiser")
        # La base se prend au chargement des régions ; rien n'a changé : rien n'est proposé.
        _retour_sur_l_onglet(b)
        expect(bouton).to_be_hidden()
        un, deux, trois = s["bulles"]
        assert _ids_a_l_ecran(b) == {s["case"], un, deux, trois}

        with _client(s["base"], ALICE) as c:          # un autre écran, ailleurs
            neuve = c.post(f"/api/planches/{s['planche']}/regions",
                           json={"type": "bulle", "x": 30, "y": 120, "w": 50, "h": 30}).json()["id"]
            assert c.put(f"/api/regions/{deux}", json={"ocr_texte": "CHANGÉ"}).status_code == 200
            assert c.delete(f"/api/regions/{trois}").status_code == 204
        # Rien ne se recharge d'office : l'écran montre encore ce qu'il avait.
        _retour_sur_l_onglet(b)
        expect(bouton).to_be_visible()
        expect(bouton).to_have_text("⟳ Actualiser")
        expect(bouton).to_have_attribute(
            "title", "La planche a changé ailleurs : 1 région modifiée, 1 créée, 1 supprimée. "
                     "Actualiser la recharge, sans perdre votre saisie.")
        assert _ids_a_l_ecran(b) == {s["case"], un, deux, trois}

        bouton.click()
        expect(bouton).to_be_hidden(timeout=15000)
        b.wait_for_load_state("networkidle")
        assert _ids_a_l_ecran(b) == {s["case"], un, deux, neuve}
        # La base a été reprise : un nouveau retour ne signale plus rien.
        _retour_sur_l_onglet(b)
        expect(bouton).to_be_hidden()
    finally:
        ctx.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_ses_propres_gestes_ne_se_signalent_pas_ceux_d_un_autre_si(page, decor):
    """Bob annote la première bulle (note, tag) et la transcrit pendant qu'Alice transcrit la
    deuxième : seule celle d'Alice est signalée. L'écran n'adopte que ce qu'il a touché — une
    empreinte unique, adoptée après chaque enregistrement de Bob, aurait absorbé celle
    d'Alice."""
    s = decor
    un, deux, _ = s["bulles"]
    ctx, b = _ouvrir(page, s["url"] + f"&region={un}")
    try:
        bouton = b.locator("#planche-actualiser")
        with b.expect_request(lambda r: r.url.endswith("/locuteur")):
            b.click('.mode-btn[data-mode="annotation"]')
        b.wait_for_load_state("networkidle")
        b.fill("#note-input", "note de Bob")
        expect(b.locator("#save-state")).to_have_text("Enregistré", timeout=15000)
        with _client(s["base"], ALICE) as c:
            assert c.put(f"/api/regions/{deux}", json={"ocr_texte": "PAR ALICE"}).status_code == 200
        b.fill("#tag-input", "cri")
        b.keyboard.press("Enter")
        b.wait_for_load_state("networkidle")
        expect(b.locator("#save-state")).to_have_text("Enregistré", timeout=15000)
        _retour_sur_l_onglet(b)
        expect(bouton).to_be_visible()
        expect(bouton).to_have_attribute("title", "La planche a changé ailleurs : 1 région "
                                                  "modifiée. Actualiser la recharge, sans perdre "
                                                  "votre saisie.")
    finally:
        ctx.close()


def _texte_en_base(s, rid, attendu):
    with _client(s["base"]) as c:
        fin, texte = time.time() + 15, None
        while time.time() < fin:
            texte = next(r for r in c.get(f"/api/planches/{s['planche']}/regions").json()
                         if r["id"] == rid)["ocr_texte"]
            if texte == attendu:
                break
            time.sleep(0.25)
    return texte


def _signal_en_transcription(page, s):
    un = s["bulles"][0]
    ctx, b = _ouvrir(page, s["url"] + f"&region={un}")
    b.click('.mode-btn[data-mode="transcription"]')
    b.wait_for_load_state("networkidle")
    expect(b.locator("#tr-text")).to_have_value("PREMIÈRE")
    with _client(s["base"], ALICE) as c:
        c.post(f"/api/planches/{s['planche']}/regions",
               json={"type": "bulle", "x": 30, "y": 120, "w": 50, "h": 30})
    _retour_sur_l_onglet(b)
    expect(b.locator("#planche-actualiser")).to_be_visible()
    return ctx, b, un


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_actualiser_enregistre_d_abord_le_texte_en_cours_de_saisie(page, decor):
    """Bob tape dans la Transcription ; une région apparaît ailleurs ; il clique « Actualiser »
    avant que son texte soit parti. Le texte part D'ABORD — avant la relecture —, reste dans
    le champ, et la planche est relue."""
    s = decor
    ctx, b, un = _signal_en_transcription(page, s)
    try:
        ordre = []
        b.on("request", lambda r: ordre.append(f"{r.method} {r.url.split('/api/')[-1]}"))
        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" DE BOB")
        b.locator("#planche-actualiser").click()
        expect(b.locator("#planche-actualiser")).to_be_hidden(timeout=15000)
        b.wait_for_load_state("networkidle")
        expect(b.locator("#tr-text")).to_have_value("PREMIÈRE DE BOB")
        assert _texte_en_base(s, un, "PREMIÈRE DE BOB") == "PREMIÈRE DE BOB"
        envoi = ordre.index(f"PUT regions/{un}")
        relecture = ordre.index(f"GET planches/{s['planche']}/regions")
        assert envoi < relecture, ordre
        expect(b.locator("#tr-mini rect.tr-region")).to_have_count(4)   # la neuve y est
    finally:
        ctx.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_une_saisie_reprise_pendant_la_relecture_reste_dans_son_champ(page, decor):
    """Rien n'attend quand Bob clique ; la relecture, elle, est lente, et il tape pendant ce
    temps. Sa frappe reste dans le champ, et part avec la valeur qu'il VOYAIT — sans faux
    conflit, sans rien écraser."""
    s = decor
    ctx, b, un = _signal_en_transcription(page, s)
    try:
        retenues, libre = [], []
        relecture = f"**/api/planches/{s['planche']}/regions"

        def retenir(route):
            if libre or route.request.method != "GET":
                route.continue_()
            else:
                retenues.append(route)
        b.route(relecture, retenir)
        b.locator("#planche-actualiser").click()
        fin = time.time() + 15
        while not retenues and time.time() < fin:
            b.wait_for_timeout(100)
        assert retenues, "la relecture n'est pas partie"
        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" ENCORE")
        libre.append(True)
        for route in retenues:
            route.continue_()
        expect(b.locator("#planche-actualiser")).to_be_hidden(timeout=15000)
        b.wait_for_load_state("networkidle")
        expect(b.locator("#tr-text")).to_have_value("PREMIÈRE ENCORE")
        assert _texte_en_base(s, un, "PREMIÈRE ENCORE") == "PREMIÈRE ENCORE"
        expect(b.locator("#bandeau-conflit")).to_have_count(0)
    finally:
        ctx.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_la_verification_suit_l_intervalle_et_se_suspend_onglet_cache(page, decor):
    s = decor
    ctx = page.context.browser.new_context(extra_http_headers=BOB)
    b = ctx.new_page()
    b.clock.install()
    b.empreintes = []
    b.on("request", lambda r: b.empreintes.append(r.url) if r.url.endswith("/empreinte") else None)
    try:
        b.goto(s["url"], wait_until="networkidle")
        expect(b.locator("#planche-actualiser")).to_be_hidden()
        avant = len(b.empreintes)
        assert avant >= 1                               # la base, au chargement des régions
        intervalle = b.evaluate("BDSignal.INTERVALLE_MS")
        # Onglet caché : l'intervalle passe, aucune lecture.
        b.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => true})")
        b.clock.run_for(intervalle * 2 + 1000)
        b.wait_for_load_state("networkidle")
        assert len(b.empreintes) == avant, b.empreintes
        # Visible de nouveau : l'intervalle relit, et voit ce qui a changé ailleurs.
        b.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => false})")
        with _client(s["base"], ALICE) as c:
            c.put(f"/api/regions/{s['bulles'][0]}", json={"ocr_texte": "AILLEURS"})
        with b.expect_response(lambda r: r.url.endswith("/empreinte")):
            b.clock.run_for(intervalle + 1000)
        expect(b.locator("#planche-actualiser")).to_be_visible()
    finally:
        ctx.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_actualiser_garde_le_nom_a_moitie_tape_d_un_personnage(page, decor):
    """Relecture de CONC-4 : « Actualiser » vidait le champ du locuteur, où Bob avait commencé
    de taper un nom. La saisie s'y garde, comme dans la note et le texte."""
    s = decor
    un, deux, _ = s["bulles"]
    ctx, b = _ouvrir(page, s["url"] + f"&region={un}")
    try:
        with b.expect_request(lambda r: r.url.endswith("/locuteur")):
            b.click('.mode-btn[data-mode="annotation"]')
        b.wait_for_load_state("networkidle")
        with _client(s["base"], ALICE) as c:
            assert c.put(f"/api/regions/{deux}", json={"ocr_texte": "AILLEURS"}).status_code == 200
        _retour_sur_l_onglet(b)
        expect(b.locator("#planche-actualiser")).to_be_visible()
        b.click("#loc-input")
        b.keyboard.type("Hadd")
        with b.expect_response(lambda r: r.url.endswith(f"/regions/{un}/locuteur")):
            b.locator("#planche-actualiser").click()
        expect(b.locator("#planche-actualiser")).to_be_hidden(timeout=15000)
        b.wait_for_load_state("networkidle")
        expect(b.locator("#loc-input")).to_have_value("Hadd")
    finally:
        ctx.close()


# ── Se REPÉRER (Hugo, 2026-10-25) ─────────────────────────────────────────────────────────
# « Laisser en blanc empêche qu'on voie la différence, ou juste l'apparition du bouton. Il
# vaut mieux un effet de couleur que changer l'emplacement. » Le bouton apparu est le seul
# PLEIN de la bande, dans la couleur d'attention ; mesuré dans les QUATRE états de couleur
# que pose `theme.js` — le contraste élevé redéfinit les jetons, et c'est sur lui qu'une
# encre choisie pour le thème ordinaire tomberait.

_STYLES_DE_LA_BANDE = """() => {
  const st = (sel) => { const c = getComputedStyle(document.querySelector(sel));
    return {fond: c.backgroundColor, bord: c.borderTopColor, encre: c.color,
            largeurBord: c.borderTopWidth, graisse: c.fontWeight}; };
  return {bouton: st('#planche-actualiser'), ghost: st('#btn-traitement'),
          bande: getComputedStyle(document.querySelector('#header')).backgroundColor}; }"""


def _rgba(css):
    """`rgb(r, g, b)` ou `rgba(r, g, b, a)` → (r, g, b, a)."""
    nombres = [float(x) for x in css[css.index("(") + 1:css.index(")")].replace(",", " ").split()
               if x != "/"]
    return tuple(nombres[:3]) + ((nombres[3],) if len(nombres) > 3 else (1.0,))


def _luminance(rgb):
    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _rapport(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("theme,contraste", [("dark", None), ("light", None),
                                             ("dark", "high"), ("light", "high")])
@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_actualiser_apparu_se_repere_par_sa_couleur(page, decor, theme, contraste):
    from test_e2e_a11y import _audit, _fmt   # l'instrument d'origine, pas une copie
    s = decor
    ctx = page.context.browser.new_context(extra_http_headers=BOB)
    pose = f"localStorage.setItem('bd-theme','{theme}');"
    if contraste:
        pose += f" localStorage.setItem('bd-contrast','{contraste}');"
    ctx.add_init_script(pose)
    b = ctx.new_page()
    try:
        b.goto(s["url"], wait_until="networkidle")
        etat = b.evaluate("() => ({t: document.documentElement.dataset.theme || null,"
                          " c: document.documentElement.dataset.contrast || null})")
        assert etat["t"] == theme and etat["c"] == contraste, (
            f"l'état de couleur n'est pas posé ({etat}) : la mesure porterait sur un autre")
        _retour_sur_l_onglet(b)
        expect(b.locator("#planche-actualiser")).to_be_hidden()
        with _client(s["base"], ALICE) as c:
            assert c.put(f"/api/regions/{s['bulles'][0]}",
                         json={"ocr_texte": "AILLEURS"}).status_code == 200
        _retour_sur_l_onglet(b)
        expect(b.locator("#planche-actualiser")).to_be_visible()
        b.mouse.move(0, 0)                              # aucun survol : l'état de repos
        m = b.evaluate(_STYLES_DE_LA_BANDE)
        bouton, ghost = m["bouton"], m["ghost"]
        fond, bord, encre, bande = (_rgba(bouton["fond"]), _rgba(bouton["bord"]),
                                    _rgba(bouton["encre"]), _rgba(m["bande"]))
        lieu = f"[{theme}{', contraste élevé' if contraste else ''}]"
        # Pas le style des autres boutons de la bande : ni leur fond, ni leur bordure.
        assert bouton["fond"] != ghost["fond"] and bouton["bord"] != ghost["bord"], (lieu, m)
        # Un fond PLEIN, sans quoi le rapport mesuré plus bas ne serait pas celui de l'écran.
        assert fond[3] == 1 and bande[3] == 1, (lieu, m)
        # Ni l'épaisseur du bord ni la graisse ne changent : seule la couleur parle (écran
        # stable). La police n'est pas comparée : le bouton est `small`, son voisin non.
        for cle in ("largeurBord", "graisse"):
            assert bouton[cle] == ghost[cle], (lieu, cle, m)
        # Le fond, accent plein : 3:1 contre la bande. L'encre posée dessus : AA, 4,5:1.
        assert _rapport(fond, bande) >= 3, (lieu, round(_rapport(fond, bande), 2), m)
        assert _rapport(encre, fond) >= 4.5, (lieu, round(_rapport(encre, fond), 2), m)
        # Et l'instrument d'origine ne relève rien sur lui.
        viol = [v for v in _audit(b) if any("planche-actualiser" in t for t in v["targets"])]
        assert not viol, f"« Actualiser » {lieu} :\n{_fmt(viol)}"
    finally:
        ctx.close()
