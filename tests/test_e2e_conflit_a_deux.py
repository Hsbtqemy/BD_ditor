"""Deux personnes sur le MÊME champ : l'écran le dit, et ne perd rien (CONC-3, second temps).

Tranché par Hugo sur maquette le 2026-09-17. Quand le serveur refuse un enregistrement fait
sur une valeur périmée (409), l'Atelier ouvre un BANDEAU au-dessus du champ : il nomme
l'auteur, montre sa version, garde la saisie en cours, et offre « Remplacer par la mienne »
et « Garder l'autre ». Le focus reste dans le champ. Tant qu'on n'a pas choisi, changer de
mode est bloqué. Une case supprimée ailleurs donne un toast nommé, et quitte l'écran.

**Depuis le basculement d'ANN-7, la machinerie se joue sur la Transcription.** Elle se
provoquait par la NOTE du mode Annotation, qui est parti : la note, le locuteur et le
personnage montré s'écrivent dans la page Annotation, qui a son bandeau et ses tests
(`test_e2e_annotation_page.py`, `test_e2e_annotation_locuteur.py`). Le bandeau de l'Atelier,
l'attente au départ, le laissez-passer et le filet servent toujours au texte transcrit : ces
gardes ne disparaissent pas avec le champ qui servait à les provoquer.

Quitter un champ dont l'enregistrement n'est pas revenu ATTEND la réponse (tranché sans
maquette, sur description) : le geste se voit, se rejoue seul, et l'attente est bornée. Les
réponses « lentes » sont fabriquées en retenant les requêtes (`_Retenue`).

Deux contextes de navigateur, derrière le proxy, sous deux identités nommées — ouverts AVANT
le premier enregistrement, ce qui rend l'état de chacun périmé. La garde juge l'écran ET la
base : le bandeau ne suffit pas s'il laisse passer une perte, et la base ne suffit pas si
l'écran se tait.
"""
import json
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
        "la page Annotation a son propre bandeau et ses tests (`test_e2e_annotation_page.py`, "
        "`test_e2e_annotation_locuteur.py`) : ce module audite celui de l'Atelier"),
    "/recherche": "on n'y écrit ni note ni texte : le conflit se joue dans l'Atelier seul",
    "/corpus": "on n'y écrit ni note ni texte : le conflit se joue dans l'Atelier seul",
    "/exploration": "on n'y écrit ni note ni texte : le conflit se joue dans l'Atelier seul",
    "/administration": "on n'y écrit ni note ni texte : le conflit se joue dans l'Atelier seul",
}

ADMIN = {"Remote-User": "decor", "Remote-Groups": "bd-admins", "X-BD-Requete": "1"}
ALICE = {"Remote-User": "alice", "Remote-Groups": "bd-admins", "Remote-Name": "Alice Dupont"}
BOB = {"Remote-User": "bob", "Remote-Groups": "bd-admins", "Remote-Name": "Bob Martin"}


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ADMIN)


@pytest.fixture
def decor(live_server):
    with _client(live_server) as c:
        aid = c.post("/api/albums", json={"titre": "E2E conflit"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        case = c.post(f"/api/planches/{pid}/regions",
                      json={"type": "case", "x": 10, "y": 10, "w": 150, "h": 100}).json()["id"]
        bulle = c.post(f"/api/planches/{pid}/regions",
                       json={"type": "bulle", "x": 15, "y": 15, "w": 40, "h": 20,
                             "parent_id": case}).json()["id"]
        seconde = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "x": 70, "y": 15, "w": 40, "h": 20,
                               "parent_id": case}).json()["id"]
        for rid, texte in ((bulle, "TEXTE INITIAL"), (seconde, "AUTRE BULLE")):
            c.put(f"/api/regions/{rid}", json={"ocr_texte": texte})
        autre_case = c.post(f"/api/planches/{pid}/regions",
                            json={"type": "case", "x": 10, "y": 200, "w": 150,
                                  "h": 100}).json()["id"]
    base = f"{live_server}/?album={aid}&planche={pid}"
    return {"base": live_server, "planche": pid, "bulle": bulle, "case": autre_case,
            "url_bulle": f"{base}&region={bulle}", "url_case": f"{base}&region={autre_case}",
            "url_seconde": f"{base}&region={seconde}", "url_planche": base, "seconde": seconde}


def _contexte(page, identite):
    ctx = page.context.browser.new_context(extra_http_headers=identite)
    p = ctx.new_page()
    p.envois = []
    p.on("request", lambda r: p.envois.append((r.method, r.url, r.post_data))
         if r.method in ("PUT", "DELETE") and "/api/regions/" in r.url else None)
    return ctx, p


def _ouvrir(p, url, mode):
    p.goto(url, wait_until="networkidle")
    p.click(f'.mode-btn[data-mode="{mode}"]')
    p.wait_for_load_state("networkidle")


def _transcrire(p, url, attendu):
    """Ouvre l'Atelier en Transcription sur la bulle de `url`, et attend son texte : la
    zone de saisie est remplie au rendu de la bulle, après le chargement de la planche."""
    _ouvrir(p, url, "transcription")
    expect(p.locator("#tr-text")).to_have_value(attendu, timeout=15000)


class _Retenue:
    """Intercepte les PUT vers `motif` et les garde en suspens : le serveur « ne répond pas »
    tant que le test ne les libère pas. Les gestionnaires de route ne tournent que PENDANT un
    appel à Playwright : on attend par `wait_for_timeout`, jamais par `time.sleep`, qui ne
    laisserait passer aucune requête. Et on libère par un drapeau : `unroute` relâche de
    lui-même ce qui est en suspens."""

    def __init__(self, p, motif):
        self.p, self.retenus, self.libre = p, [], False
        p.route(motif, self._intercepter)

    def _intercepter(self, route):
        if route.request.method == "PUT" and not self.libre:
            self.retenus.append(route)
        else:
            route.continue_()

    def attendre(self, n, delai=15):
        fin = time.time() + delai
        while len(self.retenus) < n and time.time() < fin:
            self.p.wait_for_timeout(100)
        return len(self.retenus)

    def liberer(self):
        self.libre = True
        for route in self.retenus:
            route.continue_()


def _note_d_alice(s, note):
    """Alice écrit la note de la bulle, comme le ferait la page Annotation : son acte est au
    journal, et le prochain Ctrl+Z d'Alice le vise."""
    with _client(s["base"]) as c:
        c.get("/api/moi", headers=ALICE)
        r = c.put(f"/api/regions/{s['bulle']}/annotation", headers=ALICE,
                  json={"note": note, "note_vue": ""})
        assert r.status_code == 200, r.text


def _note_en_base(base, rid):
    with _client(base) as c:
        return c.get(f"/api/regions/{rid}/annotation").json()["note"] or ""


def _texte_en_base(base, pid, rid):
    with _client(base) as c:
        return next(r for r in c.get(f"/api/planches/{pid}/regions").json()
                    if r["id"] == rid)["ocr_texte"]


def _attendre(fonction, attendu, delai=15, page=None):
    """`page` : attendre en laissant tourner ses gestionnaires de route (cf. `_Retenue`)."""
    fin, valeur = time.time() + delai, None
    while time.time() < fin:
        valeur = fonction()
        if valeur == attendu:
            return valeur
        if page is not None:
            page.wait_for_timeout(250)
        else:
            time.sleep(0.25)
    return valeur


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_deux_textes_le_bandeau_nomme_garde_la_saisie_et_bloque_le_mode(page, decor):
    """Jouée par la note jusqu'au basculement d'ANN-7, la même garde sur le texte transcrit."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, BOB)
    try:
        _transcrire(a, s["url_planche"], "TEXTE INITIAL")
        _transcrire(b, s["url_planche"], "TEXTE INITIAL")

        a.fill("#tr-text", "TEXTE DE A")
        expect(a.locator("#tr-save")).to_have_text("Enregistré", timeout=15000)
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["bulle"]),
                         "TEXTE DE A") == "TEXTE DE A"

        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" B")
        bandeau = b.locator("#bandeau-conflit")
        expect(bandeau).to_be_visible(timeout=15000)
        expect(bandeau.locator(".bandeau-titre")).to_contain_text("Texte modifié par Alice Dupont")
        expect(bandeau.locator(".bandeau-version")).to_have_text("TEXTE DE A")
        expect(bandeau.locator("button")).to_have_text(["Remplacer par la mienne", "Garder l'autre"])
        expect(b.locator("#tr-save")).to_have_text("En attente de votre choix")
        # Le focus N'a PAS sauté au bandeau, et la saisie est restée.
        assert b.evaluate("document.activeElement.id") == "tr-text"
        assert b.input_value("#tr-text") == "TEXTE INITIAL B"
        assert _texte_en_base(s["base"], s["planche"], s["bulle"]) == "TEXTE DE A", \
            "le texte de A a été écrasé"

        # Le bandeau s'atteint au clavier, en arrière depuis le champ.
        b.keyboard.press("Shift+Tab")
        assert b.evaluate("document.activeElement.closest('#bandeau-conflit') !== null")
        # Hors du champ, la touche A mène à la page Annotation (ANN-7, I7) — pas tant qu'un
        # conflit attend : elle passe par les mêmes gardes qu'un changement de mode.
        b.keyboard.press("a")
        expect(b.locator("#toasts .toast").last).to_have_text("Choisissez d'abord une version")
        b.wait_for_timeout(300)
        assert "/annotation" not in b.url, b.url
        # Changer de mode est bloqué tant qu'on n'a pas choisi.
        b.click('.mode-btn[data-mode="navigation"]')
        expect(b.locator("#toasts .toast").last).to_have_text("Choisissez d'abord une version")
        expect(b.locator('.mode-btn[data-mode="transcription"]')).to_have_attribute(
            "aria-pressed", "true")
        # Recliquer le mode COURANT, ou la bulle COURANTE de la mini-planche, rendrait la bulle
        # de nouveau — sa zone de saisie reprise du texte VU : la saisie que le bandeau garde
        # doit y survivre.
        b.click('.mode-btn[data-mode="transcription"]')
        b.locator("#tr-mini .tr-region[data-i='0']").click(force=True)
        b.wait_for_timeout(300)
        assert b.input_value("#tr-text") == "TEXTE INITIAL B"
        expect(bandeau).to_be_visible()

        # « Remplacer par la mienne » : la version de B écrase celle de A.
        bandeau.get_by_role("button", name="Remplacer par la mienne", exact=True).click()
        expect(bandeau).to_have_count(0)
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["bulle"]),
                         "TEXTE INITIAL B") == "TEXTE INITIAL B"
        expect(b.locator("#tr-save")).to_have_text("Enregistré", timeout=15000)

        # A a encore vu « TEXTE DE A » : sa frappe ouvre le bandeau, et « Garder l'autre »
        # remet la version de B dans son champ sans rien envoyer.
        a.click("#tr-text")
        a.keyboard.press("End")
        a.keyboard.type(" (suite)")
        expect(a.locator("#bandeau-conflit .bandeau-titre")).to_contain_text(
            "Texte modifié par Bob Martin", timeout=15000)
        a.locator("#bandeau-conflit").get_by_role("button", name="Garder l'autre").click()
        expect(a.locator("#bandeau-conflit")).to_have_count(0)
        assert a.input_value("#tr-text") == "TEXTE INITIAL B"
        time.sleep(1)
        assert _texte_en_base(s["base"], s["planche"], s["bulle"]) == "TEXTE INITIAL B"
    finally:
        ctx_a.close()
        ctx_b.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_quitter_l_atelier_pendant_un_conflit_demande_d_abord(page, decor):
    """La navigation passait à côté du bandeau : la saisie partait avec la page, sans un mot."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, BOB)
    try:
        _transcrire(a, s["url_planche"], "TEXTE INITIAL")
        _transcrire(b, s["url_planche"], "TEXTE INITIAL")
        vues = []
        b.on("dialog", lambda d: (vues.append(d.type), d.dismiss()))
        a.fill("#tr-text", "TEXTE DE A")
        expect(a.locator("#tr-save")).to_have_text("Enregistré", timeout=15000)
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["bulle"]),
                         "TEXTE DE A") == "TEXTE DE A"
        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" B")
        expect(b.locator("#bandeau-conflit")).to_be_visible(timeout=15000)
        b.locator('#site-nav a[href="/corpus"]').first.click()
        expect(b.locator("#bandeau-conflit")).to_be_visible()
        b.wait_for_timeout(300)
        assert vues == ["beforeunload"]
        assert "/corpus" not in b.url
        assert b.input_value("#tr-text") == "TEXTE INITIAL B"
        # Le conflit réglé, plus rien à perdre : la page part sans demander.
        b.locator("#bandeau-conflit button", has_text="Garder l'autre").click()
        expect(b.locator("#bandeau-conflit")).to_be_hidden()
        with b.expect_navigation():
            b.locator('#site-nav a[href="/corpus"]').first.click()
        assert vues == ["beforeunload"]
    finally:
        ctx_a.close()
        ctx_b.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_transcription_le_texte_de_l_autre_n_est_plus_ecrase(page, decor):
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, BOB)
    try:
        _ouvrir(a, s["url_planche"], "transcription")
        _ouvrir(b, s["url_planche"], "transcription")
        expect(a.locator("#tr-text")).to_have_value("TEXTE INITIAL", timeout=15000)

        b.fill("#tr-text", "TEXTE DE B")
        expect(b.locator("#tr-save")).to_have_text("Enregistré", timeout=15000)

        a.click("#tr-text")
        a.keyboard.press("End")
        a.keyboard.type(" + A")
        # Changer de bulle dans la mini-planche AVANT que l'enregistrement ne parte : il part
        # quand même, et le conflit s'ouvre sur la bulle qu'on quittait, sans la quitter.
        a.locator("#tr-mini .tr-region[data-i='1']").click(force=True)
        bandeau = a.locator("#bandeau-conflit")
        expect(bandeau.locator(".bandeau-titre")).to_contain_text(
            "Texte modifié par Bob Martin", timeout=15000)
        expect(a.locator("#tr-progress")).to_have_text("Bulle 1 / 2")
        assert a.input_value("#tr-text") == "TEXTE INITIAL + A"
        expect(bandeau.locator(".bandeau-version")).to_have_text("TEXTE DE B")
        expect(a.locator("#tr-next")).to_be_disabled()
        expect(a.locator("#tr-prev")).to_be_disabled()
        assert _texte_en_base(s["base"], s["planche"], s["bulle"]) == "TEXTE DE B"
        textes = [json.loads(d) for m, u, d in a.envois if m == "PUT" and d]
        assert textes and all("vu" in corps for corps in textes if "ocr_texte" in corps)

        bandeau.get_by_role("button", name="Garder l'autre").click()
        expect(bandeau).to_have_count(0)
        assert a.input_value("#tr-text") == "TEXTE DE B"
        expect(a.locator("#tr-next")).to_be_enabled()
        assert _texte_en_base(s["base"], s["planche"], s["bulle"]) == "TEXTE DE B"
    finally:
        ctx_a.close()
        ctx_b.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_quitter_pendant_l_envoi_attend_la_reponse_puis_part_seul(page, decor):
    """Le délai qui PASSE. Changer de mode pendant que le texte n'est pas revenu retient le
    geste : l'indicateur le dit, rien ne bouge, et le geste se rejoue seul à la réponse."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    try:
        _transcrire(a, s["url_planche"], "TEXTE INITIAL")
        retenue = _Retenue(a, "**/api/regions/*")
        a.click("#tr-text")
        a.keyboard.press("End")
        a.keyboard.type(" TENU")
        a.click('.mode-btn[data-mode="navigation"]')     # avant le délai de frappe
        expect(a.locator("#tr-save")).to_have_text("Enregistrement en cours…")
        assert retenue.attendre(1) == 1
        a.wait_for_timeout(1000)
        expect(a.locator('.mode-btn[data-mode="transcription"]')).to_have_attribute(
            "aria-pressed", "true")
        assert a.input_value("#tr-text") == "TEXTE INITIAL TENU"

        retenue.liberer()
        # Aucun clic à refaire : le geste retenu part de lui-même.
        expect(a.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute(
            "aria-pressed", "true", timeout=15000)
        assert _texte_en_base(s["base"], s["planche"], s["bulle"]) == "TEXTE INITIAL TENU"
        expect(a.locator("#toasts .toast")).to_have_count(0)
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_une_attente_vaine_rend_la_main_et_laisse_partir_si_l_on_insiste(page, decor):
    """Le délai qui EXPIRE. Un serveur muet ne coince personne : un message le dit, la saisie
    reste dans le champ, et refaire le geste part sans attendre."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    try:
        _transcrire(a, s["url_planche"], "TEXTE INITIAL")
        retenue = _Retenue(a, "**/api/regions/*")
        a.click("#tr-text")
        a.keyboard.press("End")
        a.keyboard.type(" MUET")
        a.click('.mode-btn[data-mode="navigation"]')
        expect(a.locator("#tr-save")).to_have_text("Enregistrement en cours…")
        toast = a.locator("#toasts .toast", has_text="L'enregistrement n'a pas encore abouti")
        expect(toast).to_have_count(1, timeout=10000)
        expect(toast).to_contain_text("Votre saisie reste dans le champ")
        expect(a.locator('.mode-btn[data-mode="transcription"]')).to_have_attribute(
            "aria-pressed", "true")
        assert a.input_value("#tr-text") == "TEXTE INITIAL MUET"

        a.click('.mode-btn[data-mode="navigation"]')     # on insiste
        expect(a.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute(
            "aria-pressed", "true")
        retenue.liberer()
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["bulle"]),
                         "TEXTE INITIAL MUET", page=a) == "TEXTE INITIAL MUET"
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_quitter_sur_une_version_perimee_reste_et_ouvre_le_bandeau(page, decor):
    """Le 409 revient pendant qu'on part : on ne part pas, et le bandeau s'ouvre sur la
    saisie. Avant, il s'ouvrait dans le panneau quitté, où le blocage interdisait de revenir.
    Deux sorties de la Transcription : le bouton d'un autre mode, puis Échap."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, BOB)
    try:
        _transcrire(a, s["url_seconde"], "AUTRE BULLE")
        _transcrire(b, s["url_seconde"], "AUTRE BULLE")
        a.fill("#tr-text", "SECONDE DE A")
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["seconde"]),
                         "SECONDE DE A") == "SECONDE DE A"

        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" B")
        b.click('.mode-btn[data-mode="navigation"]')     # avant le délai de frappe
        bandeau = b.locator("#bandeau-conflit")
        expect(bandeau).to_be_visible(timeout=15000)
        expect(bandeau.locator(".bandeau-titre")).to_contain_text("Texte modifié par Alice Dupont")
        expect(b.locator('.mode-btn[data-mode="transcription"]')).to_have_attribute(
            "aria-pressed", "true")
        assert b.input_value("#tr-text") == "AUTRE BULLE B"
        expect(b.locator("#toasts .toast", has_text="n'a pas été enregistr")).to_have_count(0)

        # Même chose sur l'autre bulle, en sortant par Échap.
        _ouvrir(a, s["url_planche"], "transcription")
        _ouvrir(b, s["url_planche"], "transcription")
        expect(b.locator("#tr-text")).to_have_value("TEXTE INITIAL", timeout=15000)
        a.fill("#tr-text", "TEXTE DE A")
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["bulle"]),
                         "TEXTE DE A") == "TEXTE DE A"
        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" B")
        b.keyboard.press("Escape")
        expect(b.locator("#bandeau-conflit .bandeau-titre")).to_contain_text(
            "Texte modifié par Alice Dupont", timeout=15000)
        expect(b.locator('.mode-btn[data-mode="transcription"]')).to_have_attribute(
            "aria-pressed", "true")
        assert b.input_value("#tr-text") == "TEXTE INITIAL B"
    finally:
        ctx_a.close()
        ctx_b.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_un_aller_retour_lent_n_ouvre_pas_de_conflit_avec_soi_meme(page, decor):
    """On tape, l'enregistrement part et tarde ; on continue de taper, le délai de frappe
    repasse. Envoyé en parallèle, le second déclarerait la valeur vue d'AVANT le premier, et
    l'écran se croirait en conflit avec lui-même. Les enregistrements d'un champ s'enchaînent."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    try:
        for url, mode, champ, lire in (
                (s["url_planche"], "transcription", "#tr-text",
                 lambda: _texte_en_base(s["base"], s["planche"], s["bulle"])),):
            _ouvrir(a, url, mode)
            retenue = _Retenue(a, "**/api/regions/*")
            a.click(champ)
            a.keyboard.press("End")
            a.keyboard.type(" un")
            assert retenue.attendre(1) == 1                      # le premier est en vol
            a.keyboard.type(" deux")
            a.wait_for_timeout(1500)                             # le délai de frappe repasse
            retenue.liberer()
            attendu = a.input_value(champ)
            assert _attendre(lire, attendu, page=a) == attendu
            a.wait_for_timeout(1000)
            expect(a.locator("#bandeau-conflit")).to_have_count(0)
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_une_reponse_tardive_eteint_le_laissez_passer(page, decor):
    """L'attente expire — le geste suivant pourrait partir sans attendre —, puis le serveur
    répond, ici par un 409. Le laissez-passer ne sert que contre un serveur MUET : la réponse
    l'éteint. Sans quoi « Remplacer par la mienne », renvoyé aussitôt, serait abandonné par le
    premier clic ailleurs, alors qu'on n'a jamais insisté pour partir."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    try:
        _transcrire(a, s["url_planche"], "TEXTE INITIAL")
        retenue = _Retenue(a, "**/api/regions/*")
        a.click("#tr-text")
        a.keyboard.press("End")
        a.keyboard.type(" A")
        a.click('.mode-btn[data-mode="navigation"]')
        expect(a.locator("#toasts .toast", has_text="L'enregistrement n'a pas encore abouti")
               ).to_have_count(1, timeout=10000)
        with _client(s["base"]) as c:
            c.get("/api/moi", headers=BOB)
            assert c.put(f"/api/regions/{s['bulle']}", headers=BOB,
                         json={"ocr_texte": "DE BOB",
                               "vu": {"ocr_texte": "TEXTE INITIAL"}}).status_code == 200
        renvoi = _Retenue(a, "**/api/regions/*")                   # retient le renvoi à venir
        retenue.liberer()                                         # le 409 tardif
        bandeau = a.locator("#bandeau-conflit")
        expect(bandeau).to_be_visible(timeout=15000)

        bandeau.get_by_role("button", name="Remplacer par la mienne", exact=True).click()
        assert renvoi.attendre(1) == 1
        a.click('.mode-btn[data-mode="navigation"]')              # sans avoir insisté
        expect(a.locator("#tr-save")).to_have_text("Enregistrement en cours…")
        a.wait_for_timeout(500)
        expect(a.locator('.mode-btn[data-mode="transcription"]')).to_have_attribute(
            "aria-pressed", "true")
        renvoi.liberer()
        expect(a.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute(
            "aria-pressed", "true", timeout=15000)
        assert _texte_en_base(s["base"], s["planche"], s["bulle"]) == "TEXTE INITIAL A"
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_insister_pour_partir_puis_un_409_ne_piege_pas_l_ecran(page, decor):
    """Le FILET. On a insisté pour partir, et l'enregistrement en suspens revient en 409. Le
    bandeau ne s'ouvre pas dans le panneau quitté — le blocage interdirait d'y revenir — : un
    toast le dit, et l'écran reste libre."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    try:
        for url, mode, champ, motif, ecrire, dit in (
                (s["url_planche"], "transcription", "#tr-text", "**/api/regions/*",
                 lambda c: c.put(f"/api/regions/{s['bulle']}", headers=BOB,
                                 json={"ocr_texte": "DE BOB", "vu": {"ocr_texte": "TEXTE INITIAL"}}),
                 "le vôtre n'a pas été enregistré"),):
            _ouvrir(a, url, mode)
            retenue = _Retenue(a, motif)
            a.click(champ)
            a.keyboard.press("End")
            a.keyboard.type(" muet")
            a.click('.mode-btn[data-mode="navigation"]')
            expect(a.locator("#toasts .toast", has_text="L'enregistrement n'a pas encore abouti")
                   ).to_have_count(1, timeout=10000)
            a.click('.mode-btn[data-mode="navigation"]')     # on insiste
            expect(a.locator('.mode-btn[data-mode="navigation"]')).to_have_attribute(
                "aria-pressed", "true")
            with _client(s["base"]) as c:
                c.get("/api/moi", headers=BOB)
                assert ecrire(c).status_code == 200
            retenue.liberer()
            expect(a.locator("#toasts .toast", has_text=dit)).to_have_count(1, timeout=15000)
            expect(a.locator("#bandeau-conflit")).to_have_count(0)
            # Libre : revenir au mode quitté répond.
            a.click(f'.mode-btn[data-mode="{mode}"]')
            expect(a.locator(f'.mode-btn[data-mode="{mode}"]')).to_have_attribute(
                "aria-pressed", "true")
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_une_case_supprimee_ailleurs_est_nommee_et_quitte_l_ecran(page, decor):
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, BOB)
    try:
        _ouvrir(a, s["url_case"], "edition")
        _ouvrir(b, s["url_case"], "edition")
        b.locator("body").press("Delete")
        expect(b.locator(f"#overlay [data-id='{s['case']}']")).to_have_count(0, timeout=15000)

        a.fill("#coord-x", "55")
        a.press("#coord-x", "Enter")
        toast =a.locator("#toasts .toast", has_text="Cette case a été supprimée par Bob Martin")
        expect(toast).to_have_count(1, timeout=15000)
        expect(a.locator(f"#overlay [data-id='{s['case']}']")).to_have_count(0)
        assert "introuvable" not in (toast.text_content() or "")
    finally:
        ctx_a.close()
        ctx_b.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_ctrl_z_refuse_dit_qui_a_change_la_note(page, decor):
    """Le serveur refuse d'annuler une note réécrite depuis par un autre ; l'écran doit le
    DIRE avec le nom, et non afficher « Conflict » ou un message technique. La note s'écrit
    dans la page Annotation depuis le basculement d'ANN-7 : Alice la pose par l'API, et c'est
    le Ctrl+Z de l'Atelier, en Navigation, qui est jugé."""
    s = decor
    _note_d_alice(s, "à défaire")
    ctx_a, a = _contexte(page, ALICE)
    try:
        _ouvrir(a, s["url_bulle"], "navigation")
        with _client(s["base"]) as c:
            c.get("/api/moi", headers=BOB)
            r = c.put(f"/api/regions/{s['bulle']}/annotation", headers=BOB,
                      json={"note": "changée par Bob", "note_vue": "à défaire"})
            assert r.status_code == 200, r.text
        # Hors du champ : dedans, Ctrl+Z est l'annulation native de la zone de texte.
        a.evaluate("document.activeElement.blur()")
        a.keyboard.press("Control+z")
        toast = a.locator("#toasts .toast", has_text="Annulation impossible")
        expect(toast).to_contain_text("la note a été modifiée depuis par Bob Martin",
                                      timeout=15000)
        assert _note_en_base(s["base"], s["bulle"]) == "changée par Bob"
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_un_ctrl_z_refuse_se_passe_d_un_clic(page, decor):
    """ANN-8 (Hugo, 2026-10-22) — le refus porte « Passer ce geste ». Le clic PART vers le
    serveur, le message le dit, la note de Bob reste, et la pile d'Alice ne retombe plus sur
    ce geste."""
    s = decor
    _note_d_alice(s, "à défaire")
    ctx_a, a = _contexte(page, ALICE)
    try:
        _ouvrir(a, s["url_bulle"], "navigation")
        with _client(s["base"]) as c:
            c.get("/api/moi", headers=BOB)
            r = c.put(f"/api/regions/{s['bulle']}/annotation", headers=BOB,
                      json={"note": "changée par Bob", "note_vue": "à défaire"})
            assert r.status_code == 200, r.text
        a.evaluate("document.activeElement.blur()")
        a.keyboard.press("Control+z")
        bouton = a.locator("#toasts .toast button", has_text="Passer ce geste")
        expect(bouton).to_be_visible(timeout=15000)
        with a.expect_response(lambda r: r.url.endswith("/api/undo/passer")
                               and r.request.method == "POST") as reponse:
            bouton.click()
        assert reponse.value.status == 200, reponse.value.text()
        expect(a.locator("#toasts .toast", has_text="Geste passé")).to_be_visible(timeout=15000)
        expect(bouton).to_have_count(0)
        assert _note_en_base(s["base"], s["bulle"]) == "changée par Bob"
        with _client(s["base"]) as c:
            assert c.get("/api/undo/prochain", headers=ALICE).json() is None
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_un_ctrl_z_de_locuteur_refuse_dit_qui_l_a_change_et_se_passe(page, decor):
    """ANN-8 — le cas de Hugo (QA du lot 1, 2026-10-23). Alice donne Zed à la bulle ; Bob le
    remplace par Yann ; le Ctrl+Z d'Alice retirait Yann. L'écran dit maintenant qui a changé
    le locuteur et offre de passer le geste ; passé, le locuteur de Bob reste."""
    s = decor
    with _client(s["base"]) as c:
        c.get("/api/moi", headers=BOB)
        zed = c.post("/api/personnages", json={"nom": "Zed QA"}).json()["id"]
        yann = c.post("/api/personnages", json={"nom": "Yann QA"}).json()["id"]
        for qui, pid in ((ALICE, zed), (BOB, yann)):
            r = c.put(f"/api/regions/{s['bulle']}/locuteur", headers=qui,
                      json={"personnage_id": pid})
            assert r.status_code == 200, r.text

    def locuteur():
        with _client(s["base"]) as c:
            return (c.get(f"/api/regions/{s['bulle']}/locuteur").json()["locuteur"]
                    or {}).get("id")

    ctx_a, a = _contexte(page, ALICE)
    try:
        _ouvrir(a, s["url_planche"], "navigation")
        a.evaluate("document.activeElement.blur()")
        a.keyboard.press("Control+z")
        toast = a.locator("#toasts .toast", has_text="Annulation impossible")
        expect(toast).to_be_visible(timeout=15000)
        expect(toast).to_contain_text("le locuteur a été modifié depuis par Bob Martin")
        bouton = toast.locator("button", has_text="Passer ce geste")
        expect(bouton).to_be_visible()
        assert locuteur() == yann
        with a.expect_response(lambda r: r.url.endswith("/api/undo/passer")
                               and r.request.method == "POST") as reponse:
            bouton.click()
        assert reponse.value.status == 200, reponse.value.text()
        expect(a.locator("#toasts .toast", has_text="Geste passé")).to_be_visible(timeout=15000)
        assert locuteur() == yann                         # le travail de Bob reste
        with _client(s["base"]) as c:
            assert c.get("/api/undo/prochain", headers=ALICE).json() is None
    finally:
        ctx_a.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_le_meme_compte_ne_se_nomme_pas(page, decor):
    """Compte collectif, ou deux onglets d'une même personne : « un autre écran »."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, ALICE)
    try:
        _transcrire(a, s["url_planche"], "TEXTE INITIAL")
        _transcrire(b, s["url_planche"], "TEXTE INITIAL")
        a.fill("#tr-text", "ÉCRAN 1")
        expect(a.locator("#tr-save")).to_have_text("Enregistré", timeout=15000)
        assert _attendre(lambda: _texte_en_base(s["base"], s["planche"], s["bulle"]),
                         "ÉCRAN 1") == "ÉCRAN 1"
        b.click("#tr-text")
        b.keyboard.press("End")
        b.keyboard.type(" 2")
        titre = b.locator("#bandeau-conflit .bandeau-titre")
        expect(titre).to_contain_text("depuis un autre écran de ce même compte", timeout=15000)
        expect(titre).not_to_contain_text("Alice")
    finally:
        ctx_a.close()
        ctx_b.close()


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_un_glissement_seul_n_est_pas_un_conflit(page, decor):
    """La région bouge PENDANT le geste : si l'écran déclarait sa position d'après comme
    valeur vue, chaque déplacement serait un faux conflit, et la case reviendrait en place."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    try:
        _ouvrir(a, s["url_case"], "edition")
        rect = a.locator(f"#overlay [data-id='{s['case']}']").first
        boite = rect.bounding_box()
        cx, cy = boite["x"] + boite["width"] / 2, boite["y"] + boite["height"] / 2
        a.mouse.move(cx, cy)
        a.mouse.down()
        a.mouse.move(cx + 25, cy + 10, steps=5)
        # La RÉPONSE, et non un temps fixe : une seconde gagnait sa course sur le poste, et la
        # perdait dès que le serveur mettait plus longtemps à écrire.
        with a.expect_response(lambda r: r.request.method == "PUT"
                               and "/api/regions/" in r.url):
            a.mouse.up()
        with _client(s["base"]) as c:
            x = next(r for r in c.get(f"/api/planches/{s['planche']}/regions").json()
                     if r["id"] == s["case"])["x"]
        assert x > 10, f"le déplacement n'a pas été enregistré : x = {x}"
        expect(a.locator("#toasts .toast", has_text="rechargée")).to_have_count(0)
        corps = [json.loads(d) for m, u, d in a.envois if m == "PUT" and d]
        assert corps and corps[-1]["vu"]["x"] == 10, corps
    finally:
        ctx_a.close()


# --------------------------------------------------------------------------- #
# CONC-4 — le locuteur et le personnage montré
# --------------------------------------------------------------------------- #
# Ils se jouaient ici dans le mode Annotation de l'Atelier, parti au basculement d'ANN-7. Ils
# s'écrivent dans la page Annotation, où leurs gardes vivent : le choix refusé, sa version et
# « Remplacer par la mienne » (`test_e2e_annotation_page.test_un_locuteur_change_ailleurs_
# ouvre_le_bandeau`, `…test_un_personnage_change_ailleurs_ouvre_le_bandeau`), le retrait
# refusé et « Garder l'autre », deux choix coup sur coup
# (`test_e2e_annotation_locuteur.py`).
