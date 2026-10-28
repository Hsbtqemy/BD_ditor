"""ANN-8 — un tag LOCAL ne se pose que sur les albums de sa collection (Hugo, 2026-10-22).

Ce que les tests d'API ne lisent pas : ce que l'Atelier PROPOSE sous le champ de tags, et ce
qu'il dit quand on tape quand même le tag d'une autre collection. Joué en mono-poste : la
portée totale lit tout, si bien qu'un tag absent des propositions ne l'est que par la règle
de l'album, jamais par la portée.

Le décor : deux collections, un album rangé dans la première ; trois tags « zz-… » — un
global, un local à chaque collection.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "la page Annotation (ANN-7, tranche 2) n'a pas ce geste : la pose d'un "
        "tag vit dans l'Atelier, que ce module audite"),
    "/recherche": "la Recherche filtre par tag sans en poser : sa liste reste celle de la portée",
    "/corpus": "la Bibliothèque range des albums ; elle ne pose aucun tag",
    "/exploration": "le Lexique documente et remanie les tags, il ne les pose sur aucune région",
    "/administration": "l'Administration règle l'instance ; aucun tag ne s'y pose",
}


@pytest.fixture
def decor(live_server):
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        cols = []
        for nom in ("Étude Une", "Étude Deux"):
            r = c.post("/api/collections", json={"nom": nom})
            assert r.status_code in (200, 201), r.text
            cols.append(r.json()["id"])
        aid = c.post("/api/albums", json={"titre": "E2E tags", "collection_id": cols[0]}
                     ).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]
        r = c.post(f"/api/planches/{pid}/regions",
                   json={"type": "bulle", "x": 60, "y": 60, "w": 300, "h": 200})
        assert r.status_code in (200, 201), r.text
        bulle = r.json()["id"]
        for label, coll in (("zz-global", None), ("zz-une", cols[0]), ("zz-deux", cols[1])):
            t = c.post("/api/tags", json={"label": label})
            assert t.status_code == 201, t.text
            if coll is not None:
                r = c.patch(f"/api/tags/{t.json()['id']}/lexique", json={"collection_id": coll})
                assert r.status_code == 200, r.text
    return {"base": live_server, "album": aid, "planche": pid, "bulle": bulle}


def _ouvrir(page, decor):
    page.goto(f"{decor['base']}/?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor['bulle']}", wait_until="networkidle")
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    page.locator('button[data-mode="annotation"]').click()
    expect(page.locator("#panel-annotation")).to_be_visible(timeout=15000)


def test_l_atelier_ne_propose_que_les_tags_qui_se_posent_sur_l_album(page, decor):
    _ouvrir(page, decor)
    champ = page.locator("#tag-input")
    champ.click()
    champ.fill("zz")
    liste = page.locator("#tag-suggest > div")
    expect(liste.first).to_be_visible()
    vus = sorted(liste.evaluate_all("(ds) => ds.map((d) => d.dataset.label)"))
    assert vus == ["zz-global", "zz-une"], vus


def test_taper_le_tag_d_une_autre_collection_est_refuse_et_le_dit(page, decor):
    _ouvrir(page, decor)
    champ = page.locator("#tag-input")
    champ.click()
    champ.fill("zz-deux")
    with page.expect_response(lambda r: r.url.endswith(f"/api/regions/{decor['bulle']}/annotation")
                              and r.request.method == "PUT") as rep:
        champ.press("Enter")
    assert rep.value.status == 422, rep.value.text()
    expect(page.locator("#toasts .toast.error")).to_contain_text(
        "« zz-deux » est propre à la collection « Étude Deux »")
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30) as c:
        tags = c.get(f"/api/regions/{decor['bulle']}/annotation").json()["tags"]
    assert tags == [], tags
