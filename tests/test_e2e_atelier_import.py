"""UX-11 — l'import à l'unité de l'Atelier passe par `apiSend`, et rien ne change à l'écran.

L'Atelier gardait un `fetch` multipart écrit à la main, le jour où la Bibliothèque passait
par `apiSend` (qui accepte un `FormData` depuis UX-11). Deux chemins pour le même geste
finissent par se répondre différemment : ce fichier JOUE l'import de l'Atelier par son vrai
sélecteur de fichier, et lit ce qui part et ce qui s'affiche.

- Le geste réussi : une requête multipart, avec l'en-tête des écritures (SEC-2), une
  planche de plus dans la liste, le message de réussite.
- Le refus : le message LISIBLE de `messageErreur`. Le `fetch` d'avant passait le `detail`
  brut à `new Error`, si bien qu'un 422 de validation — dont le `detail` est une LISTE —
  s'affichait « Import : [object Object] ». C'est la seule différence visible entre les
  deux chemins, et c'est elle qui fait tomber le retour en arrière.
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
        "la page Annotation (ANN-7, tranche 2) n'a pas ce geste : l'import à "
        "l'unité vit dans l'Atelier, que ce module audite"),
    "/corpus": "l'import en lot de la Bibliothèque est mesuré par test_e2e_import_lot.py",
    "/recherche": "aucun import : la Recherche lit le corpus",
    "/exploration": "aucun import de planche : l'Exploration compte le corpus",
    "/administration": "« Importer au fonds » est mesuré par test_e2e_fonds.py",
}


@pytest.fixture
def decor(live_server):
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E import Atelier"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p1.png", make_png(), "image/png")}).json()["id"]
    return {"base": live_server, "album": aid, "planche": pid}


def _ouvrir(page, d):
    page.goto(f"{d['base']}/?album={d['album']}&planche={d['planche']}", wait_until="networkidle")
    expect(page.locator("#planche-list li")).to_have_count(1, timeout=15000)


def _choisir(page, nom, contenu, mime):
    with page.expect_file_chooser() as choix:
        page.locator("#btn-import").click()
    choix.value.set_files(files=[{"name": nom, "mimeType": mime, "buffer": contenu}])


def test_importer_une_planche_depuis_l_atelier(page, decor):
    d = decor
    _ouvrir(page, d)
    chemin = f"/api/albums/{d['album']}/import"
    with page.expect_request(lambda r: r.method == "POST" and r.url.endswith(chemin)) as envoi, \
            page.expect_response(lambda r: r.request.method == "POST"
                                 and r.url.endswith(chemin)) as reponse:
        _choisir(page, "p2.png", make_png(), "image/png")
    assert reponse.value.status == 201, reponse.value.text()
    entetes = envoi.value.headers
    assert entetes.get("x-bd-requete") == "1", entetes
    assert entetes.get("content-type", "").startswith("multipart/form-data; boundary="), entetes
    expect(page.locator("#planche-list li")).to_have_count(2, timeout=15000)
    expect(page.locator("#toasts .toast", has_text="Planche importée")).to_be_visible()
    with httpx.Client(base_url=d["base"], trust_env=False, timeout=30) as c:
        assert len(c.get(f"/api/albums/{d['album']}/planches").json()) == 2


def test_un_refus_de_l_import_se_lit(page, decor):
    """Un refus du serveur s'affiche par son texte : la chaîne d'un refus métier, et la
    liste d'une validation FastAPI traduite par `messageErreur`."""
    d = decor
    _ouvrir(page, d)
    # Le refus métier, réel : un fichier vide.
    _choisir(page, "vide.png", b"", "image/png")
    expect(page.locator("#toasts .toast.error", has_text="Import : Fichier vide")).to_be_visible(
        timeout=15000)

    # La validation : un `detail` en LISTE, tel que FastAPI le rend. Le serveur ne le produit
    # pas pour un fichier envoyé par l'écran ; la réponse est donc posée par la page.
    page.route(f"**/api/albums/{d['album']}/import", lambda route: route.fulfill(
        status=422, content_type="application/json",
        body='{"detail": [{"type": "missing", "loc": ["body", "file"], "msg": "Field required"}]}'))
    _choisir(page, "p3.png", make_png(), "image/png")
    message = page.locator("#toasts .toast.error", has_text="Import :").last
    expect(message).to_have_text("Import : file : champ obligatoire", timeout=15000)
    expect(page.locator("#planche-list li")).to_have_count(1)
