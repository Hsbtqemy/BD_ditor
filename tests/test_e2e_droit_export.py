"""DROIT-2 — l'écran ne propose un export qu'à qui peut le faire, et le dit sinon.

Exporter est une case que le propriétaire d'une collection accorde accès par accès. Le
serveur garde chaque porte (`tests/test_droit_export.py`) ; ce module vérifie ce que l'écran
en fait, sous l'identité concernée — une suite verte ne lit pas ce que l'écran DIT.

Trois défauts qu'aucun test d'API ne verrait : un bouton d'export offert à qui sera refusé
(un geste perdu, et le refus lu comme une panne) ; une case posée dans les accès qui ne
changerait rien à l'écran ; un album exportable au titre de deux collections dont le choix
serait fait par le code au lieu de la personne.

À part de `test_e2e_a11y`, pour la raison écrite dans `test_e2e_collections` : ce module-là
se saute tout entier sans axe-core, et des tests de COMPORTEMENT n'ont pas à en dépendre.
Le seul test d'accessibilité d'ici importe l'audit à l'intérieur, et se saute seul.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e,
              pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source. Les cinq surfaces portent
# chacune un export, ou le panneau qui l'accorde : aucune n'est hors périmètre.
SURFACES_AUDITEES = ("/corpus", "/administration", "/", "/recherche", "/exploration")
SURFACES_HORS_PERIMETRE = {}

# Bob ÉCRIT sur la collection de l'album, sans la case : il voit tout, il ne sort rien.
BOB = {"Remote-User": "bob", "Remote-Groups": "etudiants"}
ADMIN = {"Remote-User": "decor", "Remote-Groups": "bd-admins"}


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


@pytest.fixture
def decor(live_server):
    """Un album et une planche, dans la collection de repli ; Bob y écrit, sans la case."""
    with _client(live_server) as c:
        aid = c.post("/api/albums", json={"titre": "Sortie", "auteur": "X"}).json()["id"]
        c.post(f"/api/albums/{aid}/import", files={"file": ("p.png", make_png(), "image/png")})
        cid = c.get(f"/api/albums/{aid}/collections").json()[0]["id"]
        r = c.put(f"/api/collections/{cid}/acces",
                  json={"principal": "bob", "niveau": "ecriture"})
        assert r.status_code == 200, r.text
    return {"base": live_server, "album": aid, "collection": cid}


def _deux_collections_exportables(decor):
    """L'album entre dans une seconde collection, et Bob a la case sur les deux."""
    with _client(decor["base"]) as c:
        c2 = c.post("/api/collections", json={"nom": "Seconde étude"}).json()["id"]
        assert c.put(f"/api/albums/{decor['album']}/collections/{c2}").status_code == 201
        for cid in (decor["collection"], c2):
            r = c.put(f"/api/collections/{cid}/acces",
                      json={"principal": "bob", "niveau": "lecture", "exporter": True})
            assert r.status_code == 200, r.text
    return c2


def _cache(page, selecteur):
    """L'attribut `hidden` POSÉ, et non la simple invisibilité : un bouton rangé dans un
    panneau replié est invisible sans que le code l'ait caché, et l'assertion serait vide."""
    return page.locator(selecteur).evaluate("el => el.hidden")


def test_sans_la_case_aucune_surface_ne_propose_d_exporter(page, decor):
    """Bob écrit, et c'est tout. Chaque surface doit le lui dire, au lieu de lui tendre un
    bouton que le serveur refusera."""
    page.set_extra_http_headers(BOB)
    base = decor["base"]

    page.goto(base + "/corpus", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{decor["collection"]}"]')
    item.locator("summary").click()
    item.locator(".col-export").wait_for(timeout=3000)
    assert item.locator("[data-dep]").count() == 0, "le bloc d'export est offert sans le droit"
    assert "droit d'exporter" in item.locator(".col-export").inner_text()

    page.goto(base + f"/?album={decor['album']}", wait_until="networkidle")
    page.wait_for_function("() => !document.querySelector('#export-pourquoi').hidden",
                           timeout=5000)
    for fmt in ("json", "csv", "tei"):
        assert _cache(page, f'[data-fmt="{fmt}"]'), f"le format {fmt} reste offert"
    assert _cache(page, "#btn-fig-add"), "l'ajout de figures reste offert"
    page.click("#btn-donnees")
    assert page.locator("#export-pourquoi").is_visible()
    assert not page.locator('[data-fmt="json"]').is_visible(), (
        "une règle CSS l'emporte sur `hidden` dans le menu")

    page.goto(base + "/recherche", wait_until="networkidle")
    page.wait_for_selector("#export-note", state="visible", timeout=3000)
    assert _cache(page, "#btn-export")
    assert not page.locator("#btn-export").is_visible()

    page.goto(base + "/exploration", wait_until="networkidle")
    page.wait_for_selector("#export-note", state="visible", timeout=3000)
    assert _cache(page, "#btn-export-analyse")
    assert not page.locator("#btn-export-analyse").is_visible()


def test_la_case_cochee_dans_les_acces_rend_l_export_a_l_ecran(page, decor):
    """Le trajet entier. Un administrateur coche la case de Bob dans le panneau des accès :
    le serveur l'enregistre, et les surfaces de Bob lui rendent ses exports."""
    base = decor["base"]
    page.set_extra_http_headers(ADMIN)
    page.goto(base + "/administration", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{decor["collection"]}"]')
    item.locator("summary").click()
    case = item.locator('input[data-export][data-principal="bob"]')
    case.wait_for(timeout=3000)
    assert not case.is_checked()
    case.check()
    page.wait_for_timeout(600)
    with _client(base) as c:
        acces = c.get(f"/api/collections/{decor['collection']}/acces").json()
    assert next(a for a in acces if a["principal"] == "bob")["exporter"] is True

    page.set_extra_http_headers(BOB)
    page.goto(base + "/corpus", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{decor["collection"]}"]')
    item.locator("summary").click()
    item.locator("[data-dep]").first.wait_for(timeout=3000)
    page.goto(base + "/recherche", wait_until="networkidle")
    page.wait_for_timeout(300)
    assert not _cache(page, "#btn-export")
    assert _cache(page, "#export-note"), "Bob exporte TOUT ce qu'il lit : aucune note à faire"


def test_le_depliant_reste_ouvert_et_le_focus_avec_lui(page, decor):
    """AUTH-3 — régler un accès ne doit pas replier la collection sous la main.

    Les quatre gestes du panneau rechargent la liste ENTIÈRE, et c'est voulu : l'écran doit
    montrer ce que le serveur a enregistré, pas ce qu'on a cliqué. Mais `loadCollections`
    reconstruisait chaque `<details>` à neuf, donc FERMÉ — cocher « peut exporter » repliait
    la collection et détruisait le contrôle qui portait le focus. Sur une collection à
    plusieurs accès, chaque réglage demandait de tout rouvrir et de retrouver sa ligne.

    Aucun test ne pouvait le voir, et c'est le point : ceux de ce module interrogent l'API
    après le clic (`/api/collections/{id}/acces`) et ne regardent plus le panneau. Relevé à
    l'usage pendant la recette du 2026-09-13.

    Les DEUX moitiés sont exigées. L'ouverture seule laisserait le clavier perdre sa place
    à chaque réglage — un défaut qui ne se voit qu'en naviguant sans souris, donc jamais.
    """
    page.set_extra_http_headers(ADMIN)
    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{decor["collection"]}"]')
    item.locator("summary").click()
    case = item.locator('input[data-export][data-principal="bob"]')
    case.wait_for(timeout=3000)
    assert not case.is_checked(), "prémisse fausse : Bob a déjà la case"

    case.check()
    page.wait_for_timeout(800)          # le réglage part, la liste se redessine

    assert item.evaluate("el => el.open"), (
        "la collection s'est repliée après le réglage — le rechargement reconstruit les "
        "<details> à neuf et perd leur état d'ouverture")
    # La case REVENUE cochée prouve que le rechargement a bien eu lieu : sans lui, on
    # lirait l'état cliqué et non l'état enregistré, et l'assertion ci-dessus serait vide.
    assert item.locator('input[data-export][data-principal="bob"]').is_checked(), (
        "la case n'est pas revenue cochée : le panneau n'a pas été redessiné, donc ce test "
        "ne prouve rien de l'état d'ouverture")
    actif = page.evaluate(
        "() => { const a = document.activeElement; return a ? (a.dataset.principal || null) : null; }")
    assert actif == "bob", (
        f"le focus est reparti sur {actif!r} au lieu de la case réglée : le contrôle est "
        "détruit par le re-rendu, et le clavier perd sa place à chaque réglage")


def test_un_album_exportable_au_titre_de_deux_collections_fait_choisir(page, decor):
    """Tranché le 2026-09-11 : le choix appartient à qui exporte. L'Atelier le demande, et
    l'export part avec la collection choisie — pas la première venue."""
    c2 = _deux_collections_exportables(decor)
    page.set_extra_http_headers(BOB)
    page.goto(decor["base"] + f"/?album={decor['album']}", wait_until="networkidle")
    page.wait_for_function("() => !document.querySelector('[data-fmt=\"json\"]').hidden",
                           timeout=5000)
    # `window.open` est remplacé : l'onglet ouvert ne porterait pas l'identité de la page,
    # et c'est l'ADRESSE demandée qu'on vérifie, pas ce que le serveur y répond.
    page.evaluate("() => { window.__ouverts = []; window.open = (u) => window.__ouverts.push(u); }")
    page.click("#btn-donnees")
    page.click('[data-fmt="json"]')
    page.wait_for_selector("#export-modal:not([hidden])", timeout=3000)
    assert page.locator("#export-choix input").count() == 2
    page.locator("#export-choix label", has_text="Seconde étude").locator("input").check()
    page.click("#export-go")
    ouverts = page.evaluate("() => window.__ouverts")
    assert len(ouverts) == 1 and f"collection_id={c2}" in ouverts[0], ouverts
    assert _cache(page, "#export-modal")


def test_a11y_la_case_et_le_choix_d_export(page, decor):
    """Les deux contrôles neufs, audités : la case d'un accès, et la fenêtre de choix."""
    from test_e2e_a11y import _audit, _fmt       # se saute seul si axe-core manque
    _deux_collections_exportables(decor)
    page.set_extra_http_headers(ADMIN)
    page.goto(decor["base"] + "/administration", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{decor["collection"]}"]')
    item.locator("summary").click()
    item.locator('input[data-export][data-principal="bob"]').wait_for(timeout=3000)
    viol = _audit(page)
    assert not viol, f"Accès et case d'export :\n{_fmt(viol)}"

    page.set_extra_http_headers(BOB)
    page.goto(decor["base"] + f"/?album={decor['album']}", wait_until="networkidle")
    page.wait_for_function("() => !document.querySelector('[data-fmt=\"json\"]').hidden",
                           timeout=5000)
    page.evaluate("() => { window.open = () => null; }")
    page.click("#btn-donnees")
    page.click('[data-fmt="json"]')
    page.wait_for_selector("#export-modal:not([hidden])", timeout=3000)
    viol = _audit(page)
    assert not viol, f"Choix de la collection d'export :\n{_fmt(viol)}"
