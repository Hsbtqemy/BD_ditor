"""ANN-7 — la MONTÉE DE VERSION depuis le bloc « Grilles » de la fiche d'un projet
(Administration › Projets ; l'écran minimal d'avant la maquette, M6 (a), tranché par Hugo le
2026-11-15 : une confirmation sous la ligne, avec les nombres du bilan).

Un parcours, dans un vrai navigateur, sur la vraie route : une grille fermée en v1 sous deux
relevés, une v2 publiée qui retire l'une de leurs entrées ; « Activer » est devenu « Monter à la
version 2… », la confirmation dit la phrase du bilan et attend la réponse pour l'entrée retirée,
« Monter » s'offre une fois « Laisser » choisi, et les relevés passent. L'état est RELU par
l'API : un bilan affiché ne prouve pas ce qui s'est écrit. La grille est FICTIVE
(`tools/grille-modele.csv`)."""
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ECRITURE, make_png  # noqa: E402
from grilles_decor import MODELE, MODELE_LISTES, grille_active_vivante  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — le périmètre de cet audit (`tests/test_surfaces.py`).
SURFACES_AUDITEES = ("/administration",)
SURFACES_HORS_PERIMETRE = {
    "/": "la montée de version ne vit que dans le bloc « Grilles » de l'Administration",
    "/annotation": "la page Annotation pose des relevés ; elle ne monte pas de version",
    "/recherche": "la montée de version ne vit que dans le bloc « Grilles » de l'Administration",
    "/corpus": "la montée de version ne vit que dans le bloc « Grilles » de l'Administration",
    "/exploration": "la montée de version ne vit que dans le bloc « Grilles » de "
                    "l'Administration",
}


def _http(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


def _ok(r, *codes):
    assert r.status_code in (codes or (200, 201)), (r.request.url, r.status_code, r.text[:500])
    return r.json() if r.content else None


def _decor(base) -> dict:
    """Un projet, une collection, un album, une bulle ; la grille fermée en v1 et deux relevés
    posés ; une v2 publiée qui RETIRE « cri » (l'une de leurs entrées)."""
    with _http(base) as c:
        projet = _ok(c.post("/api/projets", json={"nom": "Étude montée"}), 201)["id"]
        col = _ok(c.post("/api/collections", json={"nom": "Corpus M", "projet_id": projet}),
                  201)["id"]
        album = _ok(c.post("/api/albums", json={"titre": "Album M", "collection_id": col}),
                    201)["id"]
        planche = _ok(c.post(f"/api/albums/{album}/import",
                             files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
        bulle = _ok(c.post(f"/api/planches/{planche}/regions",
                           json={"type": "bulle", "x": 1, "y": 1, "w": 20, "h": 20}), 201)["id"]
        _ok(c.put(f"/api/regions/{bulle}", json={"ocr_texte": "AAAH ! BANG !"}))
        g = grille_active_vivante(c, projet_id=projet, nom="Signaux")
        gid = g["grille_id"]
        cri = _ok(c.post("/api/releves", json={"grille_id": gid, "version": 1,
                                               "region_id": bulle, "entree_cle": "cri",
                                               "mots": [0]}), 201)["id"]
        _ok(c.post("/api/releves", json={"grille_id": gid, "version": 1, "region_id": bulle,
                                         "entree_cle": "onomatopee", "variante_cle": "bang",
                                         "mots": [2]}), 201)
        sans_cri = "".join(l for l in MODELE.splitlines(keepends=True)
                           if not l.startswith("cri;"))
        files = {"fichier": ("e.csv", sans_cri.encode("utf-8-sig"), "text/csv"),
                 "listes": ("l.csv", MODELE_LISTES.encode("utf-8-sig"), "text/csv")}
        _ok(c.post(f"/api/projets/{projet}/grilles/import", files=files,
                   data={"grille_id": str(gid), "reponses": '{"cri": "retirer"}'}))
        _ok(c.post(f"/api/grilles/{gid}/versions/2/publication"))
    return {"projet": projet, "grille_id": gid, "planche": planche, "cri": cri}


def test_monter_a_la_version_2_depuis_la_ligne_de_la_grille(page, live_server):
    base = live_server
    d = _decor(base)
    page.goto(f"{base}/administration?vue=projets&projet={d['projet']}",
              wait_until="networkidle")
    ligne = page.locator(f'[data-gr-ligne="{d["grille_id"]}"]')
    expect(ligne).to_be_visible(timeout=10000)
    # « Activer » est devenu « Monter à la version 2… ».
    expect(ligne.get_by_role("button", name="Activer la v2")).to_have_count(0)
    with page.expect_response(lambda r: "/montee?version=2" in r.url):
        ligne.get_by_role("button", name="Monter à la version 2…").click()
    verdict = page.locator("#pg-montee-verdict")
    expect(verdict).to_be_visible()
    expect(verdict).to_be_focused()
    expect(verdict).to_contain_text("2 relevés passent en version 2.")
    expect(verdict).to_contain_text("1 entrée retirée attend votre réponse.")
    monter = ligne.get_by_role("button", name="Monter à la version 2", exact=True)
    expect(monter).to_have_attribute("aria-disabled", "true")
    expect(page.locator("#pg-monter-raison")).to_be_visible()
    # Rien ne part tant que l'entrée retirée n'a pas sa réponse.
    monter.click(force=True)                  # éteint : rien ne part, il dit pourquoi
    expect(page.locator("#pj-grilles-msg")).to_contain_text("à répondre")
    ligne.locator("[data-gr-mon-reponse='cri']").select_option("laisser")
    expect(monter).not_to_have_attribute("aria-disabled", "true")
    with page.expect_response(lambda r: r.url.endswith(
            f"/grilles/{d['grille_id']}/activation") and r.request.method == "PUT") as rep:
        monter.click()
    assert rep.value.status == 200, rep.value.text()
    expect(page.locator("#pj-grilles-msg")).to_contain_text(
        "est montée à la version 2 : 2 relevés passent.")
    expect(page.locator("#pg-montee-verdict")).to_have_count(0)
    # Relu par l'API : les relevés sont en version 2, « cri » à revoir.
    with _http(base) as c:
        releves = _ok(c.get(f"/api/planches/{d['planche']}/releves"))["releves"]
    assert {r["version"] for r in releves} == {2}
    cri = next(r for r in releves if r["id"] == d["cri"])
    assert (cri["etat"], cri["causes"]) == ("a_revoir", ["entree_absente"])
