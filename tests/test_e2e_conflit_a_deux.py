"""Deux personnes sur le MÊME champ : l'écran le dit, et ne perd rien (CONC-3, second temps).

Tranché par Hugo sur maquette le 2026-09-17. Quand le serveur refuse un enregistrement fait
sur une valeur périmée (409), l'Atelier ouvre un BANDEAU dans le panneau : il nomme
l'auteur, montre sa version, garde la saisie en cours, et offre « Remplacer » et « Garder
l'autre ». Le focus reste dans le champ. Tant qu'on n'a pas choisi, changer de mode est
bloqué. Une case supprimée ailleurs donne un toast nommé, et quitte l'écran.

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
            "url_planche": base}


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


def _note_en_base(base, rid):
    with _client(base) as c:
        return c.get(f"/api/regions/{rid}/annotation").json()["note"] or ""


def _texte_en_base(base, pid, rid):
    with _client(base) as c:
        return next(r for r in c.get(f"/api/planches/{pid}/regions").json()
                    if r["id"] == rid)["ocr_texte"]


def _attendre(fonction, attendu, delai=15):
    fin, valeur = time.time() + delai, None
    while time.time() < fin:
        valeur = fonction()
        if valeur == attendu:
            return valeur
        time.sleep(0.25)
    return valeur


@pytest.mark.parametrize("live_server", [True], indirect=True)
def test_deux_notes_le_bandeau_nomme_garde_la_saisie_et_bloque_le_mode(page, decor):
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, BOB)
    try:
        _ouvrir(a, s["url_bulle"], "annotation")
        _ouvrir(b, s["url_bulle"], "annotation")

        a.fill("#note-input", "note de A")
        expect(a.locator("#save-state")).to_have_text("Enregistré", timeout=15000)
        assert _attendre(lambda: _note_en_base(s["base"], s["bulle"]), "note de A") == "note de A"

        b.click("#note-input")
        b.keyboard.type("note de B")
        bandeau = b.locator("#bandeau-conflit")
        expect(bandeau).to_be_visible(timeout=15000)
        expect(bandeau.locator(".bandeau-titre")).to_contain_text("Note modifiée par Alice Dupont")
        expect(bandeau.locator(".bandeau-version")).to_have_text("note de A")
        expect(bandeau.locator("button")).to_have_text(["Remplacer", "Garder l'autre"])
        expect(b.locator("#save-state")).to_have_text("En attente de votre choix")
        # Le focus N'a PAS sauté au bandeau, et la saisie est restée.
        assert b.evaluate("document.activeElement.id") == "note-input"
        assert b.input_value("#note-input") == "note de B"
        assert _note_en_base(s["base"], s["bulle"]) == "note de A", "la note de A a été écrasée"
        # L'Atelier a bien déclaré ce qu'il avait vu (Q8 : facultatif pour l'API, pas pour lui).
        notes = [json.loads(d) for m, u, d in b.envois if u.endswith("/annotation") and d]
        assert notes and all("note_vue" in corps for corps in notes if "note" in corps)

        # Le bandeau s'atteint au clavier, en arrière depuis le champ.
        b.keyboard.press("Shift+Tab")
        assert b.evaluate("document.activeElement.closest('#bandeau-conflit') !== null")
        # Changer de mode est bloqué tant qu'on n'a pas choisi.
        b.click('.mode-btn[data-mode="navigation"]')
        expect(b.locator("#toasts .toast").last).to_have_text("Choisissez d'abord une version")
        expect(b.locator('.mode-btn[data-mode="annotation"]')).to_have_attribute("aria-pressed", "true")

        # « Remplacer » : la version de B écrase celle de A.
        bandeau.get_by_role("button", name="Remplacer").click()
        expect(bandeau).to_have_count(0)
        assert _attendre(lambda: _note_en_base(s["base"], s["bulle"]), "note de B") == "note de B"
        expect(b.locator("#save-state")).to_have_text("Enregistré", timeout=15000)

        # A a encore vu « note de A » : sa frappe ouvre le bandeau, et « Garder l'autre »
        # remet la version de B dans son champ sans rien envoyer.
        a.click("#note-input")
        a.keyboard.type(" (suite)")
        expect(a.locator("#bandeau-conflit .bandeau-titre")).to_contain_text(
            "Note modifiée par Bob Martin", timeout=15000)
        a.locator("#bandeau-conflit").get_by_role("button", name="Garder l'autre").click()
        expect(a.locator("#bandeau-conflit")).to_have_count(0)
        assert a.input_value("#note-input") == "note de B"
        time.sleep(1)
        assert _note_en_base(s["base"], s["bulle"]) == "note de B"
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
        bandeau = a.locator("#bandeau-conflit")
        expect(bandeau.locator(".bandeau-titre")).to_contain_text(
            "Texte modifié par Bob Martin", timeout=15000)
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
def test_le_meme_compte_ne_se_nomme_pas(page, decor):
    """Compte collectif, ou deux onglets d'une même personne : « un autre écran »."""
    s = decor
    ctx_a, a = _contexte(page, ALICE)
    ctx_b, b = _contexte(page, ALICE)
    try:
        _ouvrir(a, s["url_bulle"], "annotation")
        _ouvrir(b, s["url_bulle"], "annotation")
        a.fill("#note-input", "écran 1")
        expect(a.locator("#save-state")).to_have_text("Enregistré", timeout=15000)
        b.click("#note-input")
        b.keyboard.type("écran 2")
        titre = b.locator("#bandeau-conflit .bandeau-titre")
        expect(titre).to_contain_text("depuis un autre écran de ce même compte", timeout=15000)
        expect(titre).not_to_contain_text("Alice")
    finally:
        ctx_a.close()
        ctx_b.close()
