"""Tests ShareDocs : client WebDAV (httpx mocké) + routes connexion/liste/import.

Aucun accès réseau réel : `sharedocs._client` est remplacé par un client httpx
adossé à un MockTransport simulant un petit arbre WebDAV. L'import est testé en
mockant `sharedocs.download` pour qu'il renvoie une vraie image PNG.
"""
import io
from urllib.parse import quote, unquote, urlsplit

import httpx
import pytest
from PIL import Image

import main
import pipeline.sharedocs as sd

BASE = "https://sharedocs.huma-num.fr/remote.php/dav/files/u"   # hôte autorisé (anti-SSRF)
BP = "/remote.php/dav/files/u"

# Petit arbre distant simulé : (nom, est_dossier, taille)
TREE = {
    "": [("BD Astérix", True, None), ("cover.jpg", False, 1234)],
    "BD Astérix": [("planche01.tif", False, 1000),
                   ("planche02.tif", False, 2000),
                   ("notes.txt", False, 50)],
}


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (120, 160), "white").save(buf, "PNG")
    return buf.getvalue()


def _resp(href, is_dir, size, name):
    rtype = "<d:collection/>" if is_dir else ""
    sz = "" if size is None else f"<d:getcontentlength>{size}</d:getcontentlength>"
    dn = f"<d:displayname>{name}</d:displayname>" if name else ""
    return (f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>"
            f"<d:resourcetype>{rtype}</d:resourcetype>{sz}{dn}"
            f"</d:prop></d:propstat></d:response>")


def _multistatus(responses):
    return ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">'
            + "".join(responses) + "</d:multistatus>")


def _handler(request: httpx.Request) -> httpx.Response:
    rel = unquote(urlsplit(str(request.url)).path)[len(BP):].strip("/")
    if request.method == "PROPFIND":
        prefix = BP + (("/" + quote(rel)) if rel else "")
        # entrée du dossier lui-même (sans displayname → fallback au basename)
        items = [_resp(prefix + "/", True, None, None)]
        for name, is_dir, size in TREE.get(rel, []):
            href = prefix + "/" + quote(name) + ("/" if is_dir else "")
            items.append(_resp(href, is_dir, size, name))
        return httpx.Response(207, text=_multistatus(items))
    if request.method == "GET":
        return httpx.Response(200, content=_png())
    return httpx.Response(405)  # pragma: no cover - non utilisé


def _use(monkeypatch, handler):
    """Remplace sd._client par un client adossé au handler mocké."""
    monkeypatch.setattr(
        sd, "_client",
        lambda user, password: httpx.Client(
            transport=httpx.MockTransport(handler), auth=(user, password)))




# --------------------------------------------------------------------------- #
# Client bas niveau
# --------------------------------------------------------------------------- #
def test_join_encodes_segments():
    assert sd._join("https://h/dav", "") == "https://h/dav/"
    assert sd._join("https://h/dav/", "a b/c") == "https://h/dav/a%20b/c"


def test_real_client_constructs():
    c = sd._client("u", "p")
    assert isinstance(c, httpx.Client)
    c.close()


def test_parse_multistatus_malformed():
    with pytest.raises(sd.ShareDocsError):
        sd._parse_multistatus("<pas du xml", BASE)


def test_parse_multistatus_href_hors_base():
    xml = _multistatus([_resp("/autre/dossier/file.tif", False, 5, None)])
    entries = sd._parse_multistatus(xml, BASE)
    assert entries[0]["name"] == "file.tif"
    assert entries[0]["size"] == 5 and entries[0]["is_dir"] is False


def test_parse_multistatus_self_sans_slash():
    # Certains serveurs renvoient le dossier lui-même sans slash final (= base).
    xml = _multistatus([_resp(BP, True, None, None)])
    entries = sd._parse_multistatus(xml, BASE)
    assert entries[0]["path"] == ""   # chemin relatif vide → le dossier courant


def test_env_prefill(monkeypatch):
    monkeypatch.setenv("BD_SHAREDOCS_URL", "https://x")
    monkeypatch.setenv("BD_SHAREDOCS_USER", "bob")
    assert sd.env_prefill() == {"url": "https://x", "user": "bob"}


def test_configure_validation():
    with pytest.raises(sd.ShareDocsError):
        sd.configure("", "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.configure(BASE, "u", "")


def test_configure_host_non_autorise():
    """Anti-SSRF : un hôte hors allowlist est refusé avant toute requête réseau."""
    with pytest.raises(sd.ShareDocsError):
        sd.configure("https://evil.example/dav", "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.configure("http://169.254.169.254/", "u", "p")


def test_configure_ip_interne_refusee(monkeypatch):
    """Même autorisée par allowlist, une IP interne (link-local) reste refusée."""
    monkeypatch.setenv("BD_SHAREDOCS_ALLOWED_HOSTS", "169.254.169.254")
    with pytest.raises(sd.ShareDocsError):
        sd.configure("http://169.254.169.254/", "u", "p")


def test_redirection_non_suivie(monkeypatch):
    """Anti-SSRF : une réponse 3xx n'est pas suivie ni prise pour un succès."""
    _use(monkeypatch, lambda req: httpx.Response(
        302, headers={"Location": "http://169.254.169.254/"}))
    with pytest.raises(sd.ShareDocsError):
        sd.configure(BASE, "u", "p")


def test_connect_list_download(monkeypatch):
    _use(monkeypatch, _handler)
    assert sd.configure(BASE, "u", "p")["connecte"] is True
    st = sd.status()
    assert st["connecte"] is True and st["user"] == "u"

    root = sd.list_dir("")
    assert [e["name"] for e in root] == ["BD Astérix", "cover.jpg"]  # dossiers d'abord
    assert root[0]["is_dir"] is True and root[1]["is_dir"] is False
    assert root[1]["size"] == 1234

    sub = sd.list_dir("BD Astérix")
    assert [e["name"] for e in sub] == ["notes.txt", "planche01.tif", "planche02.tif"]  # tri alpha
    assert all(e["path"].strip("/") != "BD Astérix" for e in sub)  # self retirée

    data = sd.download("BD Astérix/planche01.tif")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_list_and_download_require_session():
    sd.disconnect()
    with pytest.raises(sd.ShareDocsError):
        sd.list_dir("")
    with pytest.raises(sd.ShareDocsError):
        sd.download("x")


def test_connect_refused(monkeypatch):
    _use(monkeypatch, lambda req: httpx.Response(401))
    with pytest.raises(sd.ShareDocsError):
        sd.configure(BASE, "u", "bad")


def test_server_error(monkeypatch):
    _use(monkeypatch, lambda req: httpx.Response(500))
    with pytest.raises(sd.ShareDocsError):
        sd.configure(BASE, "u", "p")


def test_network_error(monkeypatch):
    def boom(req):
        raise httpx.ConnectError("réseau coupé")
    _use(monkeypatch, boom)
    with pytest.raises(sd.ShareDocsError):
        sd.configure(BASE, "u", "p")


def test_download_http_error(monkeypatch):
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        return httpx.Response(404)
    _use(monkeypatch, h)
    sd.configure(BASE, "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.download("absent.tif")


def test_download_network_error(monkeypatch):
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        raise httpx.ReadError("coupure")
    _use(monkeypatch, h)
    sd.configure(BASE, "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.download("x.tif")


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def test_route_etat(client, monkeypatch):
    monkeypatch.delenv("BD_SHAREDOCS_URL", raising=False)
    r = client.get("/api/sharedocs/etat")
    assert r.status_code == 200
    body = r.json()
    assert body["connecte"] is False and "prefill" in body


def test_route_connexion_liste_deconnexion(client, monkeypatch):
    _use(monkeypatch, _handler)
    r = client.post("/api/sharedocs/connexion",
                    json={"url": BASE, "user": "u", "password": "p"})
    assert r.status_code == 200 and r.json()["connecte"] is True

    r = client.get("/api/sharedocs/liste", params={"chemin": ""})
    assert r.status_code == 200 and any(e["is_dir"] for e in r.json())

    r = client.post("/api/sharedocs/deconnexion")
    assert r.json()["connecte"] is False


def test_route_connexion_env_password(client, monkeypatch):
    monkeypatch.setenv("BD_SHAREDOCS_PASS", "secret-env")
    _use(monkeypatch, _handler)
    r = client.post("/api/sharedocs/connexion", json={"url": BASE, "user": "u"})
    assert r.status_code == 200 and r.json()["connecte"] is True


def test_route_connexion_refused(client, monkeypatch):
    _use(monkeypatch, lambda req: httpx.Response(403))
    r = client.post("/api/sharedocs/connexion",
                    json={"url": BASE, "user": "u", "password": "x"})
    assert r.status_code == 400


def test_route_liste_non_connecte(client):
    assert client.get("/api/sharedocs/liste").status_code == 400


def test_route_importer_nouvel_album(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda path: _png())
    r = client.post("/api/sharedocs/importer", json={
        "chemins": ["BD/planche01.tif", "BD/planche02.tif", "BD/notes.txt"],
        "nouvel_album": "Astérix"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["importes"]) == 2          # 2 images ingérées
    assert len(body["erreurs"]) == 1           # notes.txt ignoré (non-image)
    planches = client.get(f"/api/albums/{body['album_id']}/planches").json()
    assert len(planches) == 2


def test_route_importer_album_existant(client, album, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda path: _png())
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": ["x/p1.png"], "album_id": album["id"]})
    assert r.status_code == 200 and len(r.json()["importes"]) == 1


def test_route_importer_sans_fichier(client):
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": [], "nouvel_album": "X"})
    assert r.status_code == 422


def test_route_importer_sans_cible(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p: _png())
    r = client.post("/api/sharedocs/importer", json={"chemins": ["a.png"]})
    assert r.status_code == 422


def test_route_importer_album_introuvable(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p: _png())
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": ["a.png"], "album_id": 9999})
    assert r.status_code == 404


def test_route_importer_fichier_vide(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p: b"")
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": ["a.png"], "nouvel_album": "Vide"})
    assert r.status_code == 200 and len(r.json()["erreurs"]) == 1


def test_route_importer_download_echoue(client, monkeypatch):
    def boom(path):
        raise sd.ShareDocsError("indisponible")
    monkeypatch.setattr(sd, "download", boom)
    avant = len(client.get("/api/albums").json())
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": ["a.png"], "nouvel_album": "Z"})
    assert r.status_code == 200
    assert r.json()["importes"] == [] and len(r.json()["erreurs"]) == 1
    # l'album nouvellement créé mais resté vide a été nettoyé (pas d'orphelin)
    assert len(client.get("/api/albums").json()) == avant


def test_route_importer_avec_segmentation(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p: _png())
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    appels = []
    monkeypatch.setattr(main, "segment_planche",
                        lambda conn, pid: appels.append(pid))
    r = client.post("/api/sharedocs/importer", json={
        "chemins": ["a.png"], "nouvel_album": "Seg", "segmenter": True})
    assert r.status_code == 200
    assert appels and r.json()["importes"][0]["statut"] == "segmentee"


def test_route_importer_segmentation_echoue(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p: _png())
    monkeypatch.setattr(main, "kumiko_available", lambda: True)

    def boom(conn, pid):
        raise RuntimeError("erreur inattendue")   # PAS un KumikoError : ne doit pas perdre l'import
    monkeypatch.setattr(main, "segment_planche", boom)
    r = client.post("/api/sharedocs/importer", json={
        "chemins": ["a.png"], "nouvel_album": "Seg2", "segmenter": True})
    assert r.status_code == 200          # import OK malgré l'échec de segmentation
    assert len(r.json()["importes"]) == 1
    assert r.json()["importes"][0]["statut"] == "importee"   # planche conservée, non segmentée


# --------------------------------------------------------------------------- #
# Dépôt (PUT WebDAV) + sauvegarde
# --------------------------------------------------------------------------- #
def _rw_handler(put_status):
    """Handler PROPFIND (207) + PUT (statut donné)."""
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        if req.method == "PUT":
            return httpx.Response(put_status)
        return httpx.Response(405)  # pragma: no cover
    return h


def test_upload_success(monkeypatch):
    _use(monkeypatch, _rw_handler(201))
    sd.configure(BASE, "u", "p")
    res = sd.upload("dossier/backup.zip", b"data")
    assert res["chemin"] == "dossier/backup.zip" and res["status"] == 201


def test_upload_requires_session():
    sd.disconnect()
    with pytest.raises(sd.ShareDocsError):
        sd.upload("x.zip", b"d")


def test_upload_refused_403(monkeypatch):
    _use(monkeypatch, _rw_handler(403))
    sd.configure(BASE, "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.upload("ro/backup.zip", b"data")


def test_upload_server_error(monkeypatch):
    _use(monkeypatch, _rw_handler(500))
    sd.configure(BASE, "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.upload("x/y.zip", b"d")


def test_upload_network_error(monkeypatch):
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        raise httpx.WriteError("coupure")
    _use(monkeypatch, h)
    sd.configure(BASE, "u", "p")
    with pytest.raises(sd.ShareDocsError):
        sd.upload("x/y.zip", b"d")


def test_route_deposer_sauvegarde(client, album, monkeypatch):
    captured = {}
    monkeypatch.setattr(sd, "upload",
                        lambda chemin, data: captured.update(chemin=chemin, taille=len(data)) or {"chemin": chemin})
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={"dossier": "Projets/BD"})
    assert r.status_code == 200
    assert captured["chemin"].startswith("Projets/BD/bd_annotator_")
    assert captured["chemin"].endswith(".zip") and captured["taille"] > 0
    assert r.json()["depose"] == captured["chemin"]


def test_route_deposer_sauvegarde_racine(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(sd, "upload", lambda chemin, data: captured.update(chemin=chemin) or {})
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={})
    assert r.status_code == 200
    assert "/" not in captured["chemin"]      # racine : juste le nom de fichier


def test_route_deposer_sauvegarde_refuse(client, monkeypatch):
    def boom(chemin, data):
        raise sd.ShareDocsError("Écriture refusée (403)")
    monkeypatch.setattr(sd, "upload", boom)
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={"dossier": "ro"})
    assert r.status_code == 400
