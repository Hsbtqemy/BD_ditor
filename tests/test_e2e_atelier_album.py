"""L'Atelier ne crée plus d'albums (COL-3 ; Hugo, 2026-10-15).

Un album se crée dans la Bibliothèque, qui demande sa collection — donc son projet, que le
document garde comme ORIGINE. Créé depuis l'Atelier, il tombait dans la collection de
repli : l'origine écrite était fausse pour qui travaille dans un second projet. L'Atelier
importe des planches dans un album qui EXISTE, et où l'on écrit.

Ce que ce fichier mesure, sous des identités derrière le proxy :

- le bouton « ＋ » (nouvel album) n'existe plus ;
- l'import ShareDocs ne propose QUE les albums où l'on écrit — ni « Nouvel album… », ni un
  album qu'on ne fait que lire — et la requête qui PART vise l'album choisi, sans qu'aucun
  album ne soit créé en route ;
- sans album où l'on écrit, le formulaire le dit, mène à la Bibliothèque, et n'importe
  rien.

Le formulaire s'ouvre par la fonction de l'écran (`sdOpenImport`), une sélection posée à
la main : parcourir ShareDocs demanderait une session WebDAV, et ce n'est pas ce qu'on
mesure. La requête d'import est interceptée, pour la même raison.
"""
import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/corpus": "la Bibliothèque crée les albums, avec leur collection : c'est le geste que "
               "l'Atelier lui laisse, mesuré par test_e2e_collections.py",
    "/recherche": "aucun import ni création d'album : la Recherche lit le corpus",
    "/exploration": "aucun import ni création d'album : l'Exploration compte le corpus",
    "/administration": "« Importer au fonds » y est un geste d'administrateur à part, "
                       "mesuré par test_e2e_fonds.py",
}


def _decor(base):
    """« Étude », où sam écrit, et « Lecture », que sam et lina ne font que lire ; un album
    dans chacune."""
    with httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE) as c:
        ids = {}
        for nom in ("Étude", "Lecture"):
            ids[nom] = c.post("/api/collections", json={"nom": nom}).json()["id"]
        for cid, qui, niveau in ((ids["Étude"], "sam", "ecriture"),
                                 (ids["Lecture"], "sam", "lecture"),
                                 (ids["Lecture"], "lina", "lecture")):
            r = c.put(f"/api/collections/{cid}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau})
            assert r.status_code == 200, r.text
        albums = {}
        for titre, nom in (("Ecrit", "Étude"), ("Lu", "Lecture")):
            r = c.post("/api/albums", json={"titre": titre, "collection_id": ids[nom]})
            assert r.status_code == 201, r.text
            albums[titre] = r.json()["id"]
    return albums


def _ouvrir_import(page, base, qui):
    page.set_extra_http_headers({"Remote-User": qui})
    page.goto(base + "/", wait_until="networkidle")
    page.evaluate("() => { state.sd.selected.add('BD/p1.png'); sdOpenImport(); }")
    expect(page.locator("#sd-import-form")).to_be_visible()


def test_l_atelier_n_importe_que_dans_un_album_ou_l_on_ecrit(page, live_server):
    albums = _decor(live_server)
    _ouvrir_import(page, live_server, "sam")
    expect(page.locator("#btn-new-album")).to_have_count(0)
    options = page.locator("#sd-album option")
    expect(options).to_have_count(1)
    expect(options).to_have_text(["Ecrit"])
    expect(page.locator("#sd-album")).to_be_enabled()
    expect(page.locator("#sd-sans-album")).to_be_hidden()
    expect(page.locator("#sd-import-go")).to_be_enabled()

    # Le geste PART vers l'album choisi, et aucun album ne naît en route.
    envoyees = []
    page.on("request", lambda r: envoyees.append(r) if r.method == "POST" else None)
    page.route("**/api/sharedocs/importer", lambda route: route.fulfill(
        status=200, json={"album_id": albums["Ecrit"], "importes": ["BD/p1.png"],
                          "erreurs": []}))
    page.click("#sd-import-go")
    expect(page.locator(".toast", has_text="Import : 1 planche")).to_be_visible(timeout=5000)
    chemins = [r.url.split("/api/", 1)[1] for r in envoyees if "/api/" in r.url]
    assert chemins == ["sharedocs/importer"], chemins
    assert envoyees[0].post_data_json["album_id"] == albums["Ecrit"]
    assert "nouvel_album" not in envoyees[0].post_data_json


def test_sans_album_ou_l_on_ecrit_l_import_mene_a_la_bibliotheque(page, live_server):
    _decor(live_server)
    _ouvrir_import(page, live_server, "lina")
    expect(page.locator("#sd-album option")).to_have_count(0)
    expect(page.locator("#sd-album")).to_be_disabled()
    expect(page.locator("#sd-import-go")).to_be_disabled()
    phrase = page.locator("#sd-sans-album")
    expect(phrase).to_be_visible()
    expect(phrase).to_have_text("Aucun album où vous écrivez : un album se crée dans la "
                                "Bibliothèque, avec sa collection, puis ses planches "
                                "s'importent ici.")
    expect(phrase.locator("a")).to_have_attribute("href", "/corpus")
