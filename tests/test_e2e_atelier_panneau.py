"""Le panneau de la région, dans l'Atelier : ce qu'un changement de type DIT, et l'identifiant
stable d'une zone (ANN-6, ANN-8).

Né sous le nom `test_e2e_atelier_annotation.py`, qui mesurait le panneau d'annotation de
l'Atelier. Le basculement d'ANN-7 a retiré ce panneau et son mode : le locuteur s'écrit dans
la page Annotation, où ses gardes ont déménagé (`test_e2e_annotation_locuteur.py`) ; la
Situation et le profil, avec leurs phrases d'aide, sont partis avec le vocabulaire. Ce qui
reste ici ne dépendait du mode que pour s'y rendre :

- **une région qui change de type perd ce que son nouveau type ne montre pas**, et l'écran
  le DIT — le locuteur et le personnage montré par leur nom, la situation par son nombre de
  valeurs — ; UN Ctrl+Z rend le type ET ce qu'il avait perdu (ANN-8, Hugo, 2026-10-21). Le
  type se change dans le panneau de la région, dans n'importe quel mode ; ces tests restent
  en Navigation, le mode d'arrivée ;
- **l'identifiant stable d'une zone de texte** se lit à la ligne « Région » du panneau et dans
  l'arbre : c'est ce que le guide fait écrire dans une note pour renvoyer à une autre bulle.
"""
import re
import sqlite3

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": ("la page Annotation ne change pas le type d'une région hors de ce qu'elle "
                    "trace : ses refus ont leurs tests (`test_e2e_annotation_page.py`)"),
    "/recherche": "aucun panneau de région : la Recherche filtre, elle ne change aucun type",
    "/corpus": "aucun panneau de région : la Bibliothèque range des albums et des planches",
    "/exploration": "aucun panneau de région : l'Exploration compte, elle ne change aucun type",
    "/administration": "aucun panneau de région : rien n'y porte sur une région d'une planche",
}


@pytest.fixture
def atelier(live_server, tmp_path):
    """Une planche, une case, et sous elle une bulle, un cartouche, une zone de texte et une
    boîte personnage — plus Tintin au registre."""
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "E2E panneau"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(type_zone, x, y, parent=None):
            corps = {"type": type_zone, "x": x, "y": y, "w": 700, "h": 900}
            if parent is not None:
                corps.update(parent_id=parent, w=280, h=180)
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        case = region("case", 40, 40)
        decor = {"base": live_server, "base_sqlite": tmp_path / "live.sqlite",
                 "album": aid, "planche": pid, "case": case,
                 "bulle": region("bulle", 60, 60, case),
                 "cartouche": region("cartouche", 60, 300, case),
                 "texte": region("texte", 400, 60, case),
                 "personnage": region("personnage", 400, 300, case),
                 "tintin": c.post("/api/personnages", json={"nom": "Tintin"}).json()["id"]}
    finally:
        c.close()
    return decor


def _ouvrir(page, decor, type_zone):
    """Ouvre l'Atelier sur la région du type demandé, en Navigation."""
    page.goto(f"{decor['base']}/?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor[type_zone]}", wait_until="networkidle")
    expect(page.locator("#region-type")).to_have_value(type_zone, timeout=15000)
    expect(page.locator("#stat-mode")).to_have_text("Mode : Navigation")


def _http(decor):
    return httpx.Client(base_url=decor["base"], trust_env=False, timeout=30, headers=ECRITURE)


def _locuteur(decor, rid):
    with _http(decor) as c:
        return c.get(f"/api/regions/{rid}/locuteur").json()["locuteur"]


def _sql(decor):
    conn = sqlite3.connect(decor["base_sqlite"])
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _est(methode, chemin):
    """Prédicat de requête OU de réponse : cette méthode, sur ce chemin exact."""
    def predicat(objet):
        requete = getattr(objet, "request", objet)
        return requete.method == methode and requete.url.endswith(chemin)
    return predicat


def _noeud(page, rid):
    """Le nœud de l'arbre de structure qui porte cette région."""
    return page.locator(".tnode", has=page.locator(".tn-id", has_text=re.compile(rf"^#{rid}$")))


def _annuler(page):
    with page.expect_response(lambda r: r.url.endswith("/api/undo")
                              and r.request.method == "POST", timeout=180000) as annulation:
        page.locator("body").press("Control+z")
    assert annulation.value.status == 200, annulation.value.text()


def test_une_bulle_devenue_case_perd_son_locuteur_et_un_ctrl_z_rend_les_deux(page, atelier):
    """ANN-8 (Hugo, 2026-10-21) — la bulle de Tintin passe en case : l'écran DIT que le
    locuteur part, le serveur l'a retiré, et UN Ctrl+Z rend la bulle avec Tintin — sans
    bulle muette entre les deux."""
    rid = atelier["bulle"]
    with _http(atelier) as c:
        rep = c.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": atelier["tintin"]})
        assert rep.status_code == 200, rep.text
    _ouvrir(page, atelier, "bulle")

    with page.expect_response(_est("PUT", f"/api/regions/{rid}")) as reponse:
        page.locator("#region-type").select_option("case")
    assert reponse.value.status == 200, reponse.value.text()
    expect(page.locator("#toasts .toast", has_text=re.compile(r"Locuteur « Tintin » retiré"))
           ).to_be_visible(timeout=15000)
    assert _locuteur(atelier, rid) is None

    _annuler(page)
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    assert _locuteur(atelier, rid)["id"] == atelier["tintin"]


def test_une_case_devenue_bulle_ne_dit_rien_de_sa_situation_d_hier(page, atelier):
    """ANN-8, le miroir, puis ANN-7, le basculement : la situation d'une case n'existe plus
    (la v39 a détruit sa table). Une case passe en bulle sans qu'aucun message en parle, et
    UN Ctrl+Z rend la case."""
    rid = atelier["case"]
    _ouvrir(page, atelier, "case")

    with page.expect_response(_est("PUT", f"/api/regions/{rid}")) as reponse:
        page.locator("#region-type").select_option("bulle")
    assert reponse.value.status == 200, reponse.value.text()
    assert "situation_retiree" not in reponse.value.json()
    expect(page.locator("#region-type")).to_have_value("bulle", timeout=15000)
    expect(page.locator("#toasts .toast", has_text=re.compile("ituation"))).to_have_count(0)

    _annuler(page)
    expect(page.locator("#region-type")).to_have_value("case", timeout=15000)


def test_une_boite_devenue_bulle_dit_que_son_personnage_part(page, atelier):
    """Le même geste sur une boîte personnage : le personnage montré part, et l'écran le
    nomme."""
    rid = atelier["personnage"]
    with _http(atelier) as c:
        rep = c.put(f"/api/regions/{rid}/personnage", json={"personnage_id": atelier["tintin"]})
        assert rep.status_code == 200, rep.text
    _ouvrir(page, atelier, "personnage")

    with page.expect_response(_est("PUT", f"/api/regions/{rid}")) as reponse:
        page.locator("#region-type").select_option("bulle")
    assert reponse.value.status == 200, reponse.value.text()
    expect(page.locator("#toasts .toast",
                        has_text=re.compile(r"Personnage montré « Tintin » retiré"))
           ).to_be_visible(timeout=15000)


# --------------------------------------------------------------------------- #
# ANN-8 (Hugo, 2026-10-21) — la référence d'une autre bulle, dans la Note
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("type_zone", ["bulle", "cartouche", "texte"])
def test_l_identifiant_stable_d_une_zone_de_texte_se_lit_dans_le_panneau(page, atelier, type_zone):
    """Le guide fait écrire dans la Note l'identifiant « #123 » d'une autre bulle, et non sa
    citation, qui se dérive de l'ordre de lecture. Il dit où le lire : la ligne « Région » du
    panneau de l'Atelier, et l'arbre de structure. La Note s'écrit dans la page Annotation
    depuis le basculement ; l'identifiant, lui, se lit toujours ici."""
    rid = atelier[type_zone]
    _ouvrir(page, atelier, type_zone)
    ligne = page.locator(".panel-row", has=page.locator("#region-id"))
    expect(ligne).to_be_visible()
    expect(ligne).to_contain_text("Région")
    expect(page.locator("#region-id")).to_have_text(f"#{rid}")
    expect(_noeud(page, rid)).to_be_visible()
    expect(_noeud(page, rid).locator(".tn-id")).to_have_text(f"#{rid}")
