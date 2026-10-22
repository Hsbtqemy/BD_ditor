"""ANN-8 — renommer, fusionner, supprimer un tag depuis le panneau 📖 Lexique.

Ce que les tests d'API ne lisent pas : ce que l'écran OFFRE à qui, le nombre que la
confirmation du navigateur annonce, et la phrase qui dit ce qui a été fait. Joué derrière le
proxy, sous deux identités : l'administrateur (`decor`), qui remanie tout, et `bob`, qui
écrit dans « Étude A » sans la posséder — à lui, la seule suppression d'un tag inutilisé.

Le décor : deux régions ; « zorglub » posé sur les deux, « zorglonde » sur la première ;
« fote » et « inutile » posés nulle part. Tous globaux.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/exploration",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier pose des tags sur une bulle ; il n'en renomme ni n'en fusionne aucun",
    "/corpus": "la Bibliothèque gère albums et collections ; le vocabulaire n'y vit pas",
    "/recherche": "la Recherche filtre par tag ; elle ne remanie pas le vocabulaire",
    "/administration": "l'Administration règle l'instance ; le vocabulaire n'y vit pas",
}

ADMIN = {"Remote-User": "decor", "Remote-Groups": "bd-admins"}


@pytest.fixture
def decor(live_server):
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers={**ECRITURE, **ADMIN}) as c:
        r = c.post("/api/collections", json={"nom": "Étude A"})
        assert r.status_code in (200, 201), r.text
        coll = r.json()["id"]
        a = c.post("/api/albums", json={"titre": "Album", "collection_id": coll}).json()
        pl = c.post(f"/api/albums/{a['id']}/import",
                    files={"file": ("p.png", make_png(), "image/png")}).json()
        regions = []
        for k in range(2):
            r = c.post(f"/api/planches/{pl['id']}/regions",
                       json={"type": "bulle", "x": 10 * k, "y": 0, "w": 9, "h": 9})
            assert r.status_code == 201, r.text
            regions.append(r.json()["id"])
        for rid, tags in zip(regions, (["zorglub", "zorglonde"], ["zorglub"])):
            r = c.put(f"/api/regions/{rid}/annotation", json={"tags": tags})
            assert r.status_code == 200, r.text
        for label in ("fote", "inutile"):
            assert c.post("/api/tags", json={"label": label}).status_code == 201
        r = c.put(f"/api/collections/{coll}/acces", json={
            "genre": "utilisateur", "principal": "bob", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
    return {"base": live_server}


def _tags(decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                      headers={**ECRITURE, **ADMIN}) as c:
        return {t["label"]: t["frequence"] for t in c.get("/api/lexique").json()["tags"]}


def _ouvrir(page, decor, entetes, label):
    """Ouvre 📖 Lexique sous une identité, puis l'éditeur du tag `label`."""
    page.set_extra_http_headers(entetes)
    page.goto(decor["base"] + "/exploration", wait_until="networkidle")
    page.click("#btn-lexique")
    return _editeur(page, label)


def _editeur(page, label):
    terme = page.locator("#lex-body details.lex-term").filter(
        has=page.locator(".lex-name", has_text=label)).first
    terme.wait_for()
    if not terme.evaluate("(d) => d.open"):
        terme.locator("summary").click()
    return terme


def _repondre(page, accepter):
    """Le prochain dialogue du navigateur : son message est gardé, puis accepté ou refusé."""
    vu = []

    def surgit(dialogue):
        vu.append(dialogue.message)
        dialogue.accept() if accepter else dialogue.dismiss()
    page.once("dialog", surgit)
    return vu


def _attendre(page, vu):
    """Une confirmation REFUSÉE ne laisse rien à l'écran : on attend qu'elle ait surgi."""
    for _ in range(100):
        if vu:
            return
        page.wait_for_timeout(100)
    raise AssertionError("aucune confirmation n'a été demandée")


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_fusionner_annonce_le_nombre_puis_dit_ce_qui_est_fait(page, decor):
    terme = _ouvrir(page, decor, ADMIN, "zorglub")
    menu = terme.locator('[data-g="cible"]')
    expect(menu).to_be_visible()
    # Les cibles : les autres tags visibles, sans lui-même.
    options = menu.locator("option").evaluate_all("(os) => os.map((o) => o.textContent)")
    assert options == ["Fusionner dans…", "fote", "inutile", "zorglonde"], options
    menu.select_option(label="zorglonde")
    vu = _repondre(page, accepter=True)
    terme.locator('[data-g="fusionner"]').click()
    toast = page.locator("#toasts .toast.success")
    expect(toast).to_have_text("« zorglub » fusionné dans « zorglonde » (2 régions).")
    assert vu == ["Fusionner « zorglub » dans « zorglonde » ? 2 régions passeront à "
                  "« zorglonde » (1 le porte déjà), et « zorglub » disparaîtra."], vu
    expect(page.locator("#lex-body .lex-name", has_text="zorglub")).to_have_count(0)
    tags = _tags(decor)
    assert "zorglub" not in tags and tags["zorglonde"] == 2


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_supprimer_un_tag_pose_se_confirme_et_s_annule(page, decor):
    terme = _ouvrir(page, decor, ADMIN, "zorglub")
    bouton = terme.locator('[data-g="supprimer"]')
    expect(bouton).to_have_attribute("title", "Retire ce tag de toutes les régions qui le "
                                              "portent, puis le supprime.")
    vu = _repondre(page, accepter=False)
    with page.expect_response(lambda r: "a_blanc=true" in r.url) as blanc:
        bouton.click()
    assert blanc.value.status == 200
    _attendre(page, vu)
    assert vu == ["Supprimer le tag « zorglub » ? Il sera retiré de 2 régions."], vu
    assert _tags(decor)["zorglub"] == 2                      # refusé : rien n'a bougé

    vu = _repondre(page, accepter=True)
    bouton.click()
    expect(page.locator("#toasts .toast.success")).to_have_text(
        "Tag « zorglub » supprimé et retiré de 2 régions.")
    assert vu == ["Supprimer le tag « zorglub » ? Il sera retiré de 2 régions."], vu
    assert "zorglub" not in _tags(decor)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_renommer_sur_place(page, decor):
    terme = _ouvrir(page, decor, ADMIN, "fote")
    terme.locator('[data-g="label"]').fill("Faute")
    terme.locator('[data-g="renommer"]').click()
    expect(page.locator("#toasts .toast.success")).to_have_text("Tag « fote » renommé « faute ».")
    expect(page.locator("#lex-body .lex-name", has_text="faute")).to_have_count(1)
    tags = _tags(decor)
    assert "faute" in tags and "fote" not in tags


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_ecrivain_renomme_un_tag_inutilise(page, decor):
    terme = _ouvrir(page, decor, {"Remote-User": "bob"}, "fote")
    terme.locator('[data-g="label"]').fill("faute")
    terme.locator('[data-g="renommer"]').click()
    expect(page.locator("#toasts .toast.success")).to_have_text("Tag « fote » renommé « faute ».")
    assert "faute" in _tags(decor)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_renommer_vers_un_tag_existant_dit_que_c_est_une_fusion(page, decor):
    terme = _ouvrir(page, decor, ADMIN, "fote")
    terme.locator('[data-g="label"]').fill("inutile")
    terme.locator('[data-g="renommer"]').click()
    expect(page.locator("#toasts .toast.error")).to_contain_text("c'est une fusion")
    assert "fote" in _tags(decor)


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_un_ecrivain_ne_se_voit_offrir_que_les_gestes_sur_un_tag_inutilise(page, decor):
    """`bob` écrit dans « Étude A » sans la posséder : un tag global posé ne se remanie que
    par l'administrateur. Sur un tag posé, rien ; sur un tag que personne ne porte,
    Renommer et Supprimer (décision du 2026-10-22), jamais Fusionner."""
    pose = _ouvrir(page, decor, {"Remote-User": "bob"}, "zorglonde")
    expect(pose.locator(".lex-gestes")).to_have_count(0)
    libre = _editeur(page, "inutile")
    expect(libre.locator('[data-g="supprimer"]')).to_be_visible()
    expect(libre.locator('[data-g="renommer"]')).to_be_visible()
    expect(libre.locator('[data-g="fusionner"]')).to_have_count(0)
    vu = _repondre(page, accepter=True)
    libre.locator('[data-g="supprimer"]').click()
    expect(page.locator("#toasts .toast.success")).to_have_text("Tag « inutile » supprimé.")
    assert vu == ["Supprimer le tag « inutile » ? Aucune région ne le porte."], vu
    assert "inutile" not in _tags(decor)
