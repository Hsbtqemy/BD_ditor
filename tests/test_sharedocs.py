"""Tests ShareDocs : client WebDAV (httpx mocké) + routes connexion/liste/import.

Aucun accès réseau réel : `sharedocs._client` est remplacé par un client httpx
adossé à un MockTransport simulant un petit arbre WebDAV. L'import est testé en
mockant `sharedocs.download` pour qu'il renvoie une vraie image PNG.
"""
import io
import json
from urllib.parse import quote, unquote, urlsplit

import httpx
import pytest
from PIL import Image

import main
import pipeline.sharedocs as sd
from conftest import ADMIN, direct_query

BASE = "https://sharedocs.huma-num.fr/remote.php/dav/files/u"   # hôte autorisé (anti-SSRF)
BP = "/remote.php/dav/files/u"

# SHARE-1 — toute opération exige un principal (keyword-only, sans défaut) : un défaut
# ferait retomber un appelant distrait sur le compte de l'instance, ce qui marcherait
# parfaitement et déposerait sous le mauvais compte. Les tests directs se donnent donc un
# nom ; les tests de ROUTE tournent hors proxy, où la clé est l'emplacement unique du
# mono-poste (`main._MONO`).
MOI = "alice"

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
        sd.configurer("", "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.configurer(BASE, "u", "", principal=MOI)


def test_configure_host_non_autorise():
    """Anti-SSRF : un hôte hors allowlist est refusé avant toute requête réseau."""
    with pytest.raises(sd.ShareDocsError):
        sd.configurer("https://evil.example/dav", "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.configurer("http://169.254.169.254/", "u", "p", principal=MOI)


def test_configure_ip_interne_refusee(monkeypatch):
    """Même autorisée par allowlist, une IP interne (link-local) reste refusée."""
    monkeypatch.setenv("BD_SHAREDOCS_ALLOWED_HOSTS", "169.254.169.254")
    with pytest.raises(sd.ShareDocsError):
        sd.configurer("http://169.254.169.254/", "u", "p", principal=MOI)


def test_redirection_non_suivie(monkeypatch):
    """Anti-SSRF : une réponse 3xx n'est pas suivie ni prise pour un succès."""
    _use(monkeypatch, lambda req: httpx.Response(
        302, headers={"Location": "http://169.254.169.254/"}))
    with pytest.raises(sd.ShareDocsError):
        sd.configurer(BASE, "u", "p", principal=MOI)


def test_configure_http_refuse():
    """SEC-1 : https imposé — une URL http:// (identifiants en clair) est refusée d'office."""
    with pytest.raises(sd.ShareDocsError):
        sd.configurer("http://sharedocs.huma-num.fr/dav", "u", "p", principal=MOI)


def test_configure_http_optout(monkeypatch):
    """SEC-1 : opt-out explicite BD_SHAREDOCS_ALLOW_HTTP → http toléré (réseau de confiance)."""
    monkeypatch.setenv("BD_SHAREDOCS_ALLOW_HTTP", "1")
    _use(monkeypatch, _handler)
    assert sd.configurer("http://sharedocs.huma-num.fr/remote.php/dav/files/u",
                         "u", "p", principal=MOI)["connecte"] is True


def test_join_refuse_traversee():
    """SEC-1 : un segment '..' est rejeté (anti-traversée) ; '.' et vides sont normalisés."""
    with pytest.raises(sd.ShareDocsError):
        sd._join(BASE, "dossier/../../etc")
    assert sd._join(BASE, "a/./b") == sd._join(BASE, "a/b")   # '.' ignoré
    assert sd._join(BASE, "a//b") == sd._join(BASE, "a/b")    # segment vide ignoré


def test_download_refuse_traversee(monkeypatch):
    """SEC-1 : le refus du '..' tient jusque dans download/list (tous passent par _join)."""
    _use(monkeypatch, _handler)
    sd.configurer(BASE, "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.download("BD/../../secret", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.list_dir("../autre", principal=MOI)


def test_connect_list_download(monkeypatch):
    _use(monkeypatch, _handler)
    assert sd.configurer(BASE, "u", "p", principal=MOI)["connecte"] is True
    st = sd.status(principal=MOI)
    assert st["connecte"] is True and st["user"] == "u"

    root = sd.list_dir("", principal=MOI)
    assert [e["name"] for e in root] == ["BD Astérix", "cover.jpg"]  # dossiers d'abord
    assert root[0]["is_dir"] is True and root[1]["is_dir"] is False
    assert root[1]["size"] == 1234

    sub = sd.list_dir("BD Astérix", principal=MOI)
    assert [e["name"] for e in sub] == ["notes.txt", "planche01.tif", "planche02.tif"]  # tri alpha
    assert all(e["path"].strip("/") != "BD Astérix" for e in sub)  # self retirée

    data = sd.download("BD Astérix/planche01.tif", principal=MOI)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_list_and_download_require_session():
    sd.reinitialiser()
    with pytest.raises(sd.ShareDocsError):
        sd.list_dir("", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.download("x", principal=MOI)


def test_connect_refused(monkeypatch):
    _use(monkeypatch, lambda req: httpx.Response(401))
    with pytest.raises(sd.ShareDocsError):
        sd.configurer(BASE, "u", "bad", principal=MOI)


def test_server_error(monkeypatch):
    _use(monkeypatch, lambda req: httpx.Response(500))
    with pytest.raises(sd.ShareDocsError):
        sd.configurer(BASE, "u", "p", principal=MOI)


def test_network_error(monkeypatch):
    def boom(req):
        raise httpx.ConnectError("réseau coupé")
    _use(monkeypatch, boom)
    with pytest.raises(sd.ShareDocsError):
        sd.configurer(BASE, "u", "p", principal=MOI)


def test_download_http_error(monkeypatch):
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        return httpx.Response(404)
    _use(monkeypatch, h)
    sd.configurer(BASE, "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.download("absent.tif", principal=MOI)


def test_download_network_error(monkeypatch):
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        raise httpx.ReadError("coupure")
    _use(monkeypatch, h)
    sd.configurer(BASE, "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.download("x.tif", principal=MOI)


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
    monkeypatch.setattr(sd, "download",
                        lambda path, *, principal, compte=None: _png())
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
    monkeypatch.setattr(sd, "download",
                        lambda path, *, principal, compte=None: _png())
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": ["x/p1.png"], "album_id": album["id"]})
    assert r.status_code == 200 and len(r.json()["importes"]) == 1


def test_route_importer_sans_fichier(client):
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": [], "nouvel_album": "X"})
    assert r.status_code == 422


def test_route_importer_sans_cible(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p, *, principal, compte=None: _png())
    r = client.post("/api/sharedocs/importer", json={"chemins": ["a.png"]})
    assert r.status_code == 422


def test_route_importer_album_introuvable(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p, *, principal, compte=None: _png())
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
    monkeypatch.setattr(sd, "download", lambda p, *, principal, compte=None: _png())
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    appels = []
    monkeypatch.setattr(main, "segment_planche",
                        lambda conn, pid: appels.append(pid))
    r = client.post("/api/sharedocs/importer", json={
        "chemins": ["a.png"], "nouvel_album": "Seg", "segmenter": True})
    assert r.status_code == 200
    assert appels and r.json()["importes"][0]["statut"] == "segmentee"


def test_route_importer_segmentation_echoue(client, monkeypatch):
    monkeypatch.setattr(sd, "download", lambda p, *, principal, compte=None: _png())
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
    sd.configurer(BASE, "u", "p", principal=MOI)
    res = sd.upload("dossier/backup.zip", b"data", principal=MOI)
    assert res["chemin"] == "dossier/backup.zip" and res["status"] == 201


def test_upload_requires_session():
    sd.reinitialiser()
    with pytest.raises(sd.ShareDocsError):
        sd.upload("x.zip", b"d", principal=MOI)


def test_upload_refused_403(monkeypatch):
    _use(monkeypatch, _rw_handler(403))
    sd.configurer(BASE, "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.upload("ro/backup.zip", b"data", principal=MOI)


def test_upload_server_error(monkeypatch):
    _use(monkeypatch, _rw_handler(500))
    sd.configurer(BASE, "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.upload("x/y.zip", b"d", principal=MOI)


def test_upload_network_error(monkeypatch):
    def h(req):
        if req.method == "PROPFIND":
            return httpx.Response(207, text=_multistatus([_resp(BP + "/", True, None, None)]))
        raise httpx.WriteError("coupure")
    _use(monkeypatch, h)
    sd.configurer(BASE, "u", "p", principal=MOI)
    with pytest.raises(sd.ShareDocsError):
        sd.upload("x/y.zip", b"d", principal=MOI)


def test_route_deposer_sauvegarde(client, album, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sd, "upload",
        lambda chemin, data, *, principal, compte=None:
            captured.update(chemin=chemin, taille=len(data), compte=compte)
            or {"chemin": chemin, "compte": "perso", "user": "u"})
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={"dossier": "Projets/BD"})
    assert r.status_code == 200
    assert captured["chemin"].startswith("Projets/BD/bd_annotator_")
    assert captured["chemin"].endswith(".zip") and captured["taille"] > 0
    assert r.json()["depose"] == captured["chemin"]


def test_route_deposer_sauvegarde_racine(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sd, "upload",
        lambda chemin, data, *, principal, compte=None:
            captured.update(chemin=chemin) or {"compte": "perso", "user": "u"})
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={})
    assert r.status_code == 200
    assert "/" not in captured["chemin"]      # racine : juste le nom de fichier


def test_route_deposer_sauvegarde_refuse(client, monkeypatch):
    def boom(chemin, data, *, principal, compte=None):
        raise sd.ShareDocsError("Écriture refusée (403)")
    monkeypatch.setattr(sd, "upload", boom)
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={"dossier": "ro"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# SHARE-1 — une session d'instance, et une par personne
# --------------------------------------------------------------------------- #
# Le défaut, mesuré le 2026-08-27 : `_session` était un dictionnaire de MODULE, donc une
# seule session pour tout le processus. Le premier connecté la fixait pour tout le monde,
# et Bob déposait sur Huma-Num sous le compte d'Alice. En mono-poste c'était invisible —
# il n'y a qu'un utilisateur, donc la session unique est la sienne.
# --------------------------------------------------------------------------- #
def _env_instance(monkeypatch, user="instance"):
    """Déclare un compte d'instance par l'environnement, comme un déploiement le ferait."""
    monkeypatch.setenv("BD_SHAREDOCS_URL", BASE)
    monkeypatch.setenv("BD_SHAREDOCS_USER", user)
    monkeypatch.setenv("BD_SHAREDOCS_PASS", "secret")
    sd.reinitialiser()          # force la relecture de l'environnement


def test_deux_personnes_deux_sessions(monkeypatch):
    """LE défaut du chantier. Sans clé par principal, la seconde connexion écrasait la
    première, et le suivant déposait sous le compte de quelqu'un d'autre."""
    _use(monkeypatch, _handler)
    sd.configurer(BASE, "alice", "pa", principal="alice")
    sd.configurer(BASE, "bob", "pb", principal="bob")
    assert sd.perso("alice")["user"] == "alice"
    assert sd.perso("bob")["user"] == "bob"


def test_ma_deconnexion_ne_ferme_que_la_mienne(monkeypatch):
    _use(monkeypatch, _handler)
    sd.configurer(BASE, "alice", "pa", principal="alice")
    sd.configurer(BASE, "bob", "pb", principal="bob")
    sd.deconnecter(principal="alice")
    assert sd.perso("alice") is None
    assert sd.perso("bob") is not None


def test_l_instance_sert_de_repli(monkeypatch):
    """Décision du 2026-08-28 : la session d'instance existe DÈS LE DÉMARRAGE, sans que
    personne ne clique — sinon elle ne sert de repli à personne, et le choix « compte de
    l'instance » au dépôt n'aurait rien à proposer tant que quelqu'un ne l'a pas amorcée."""
    _env_instance(monkeypatch)
    session, origine = sd.resoudre("carole")          # jamais connectée
    assert origine == sd.INSTANCE and session["user"] == "instance"


def test_ma_session_prime_sur_celle_de_l_instance(monkeypatch):
    """La règle : la mienne si j'en ai une, celle de l'instance sinon."""
    _use(monkeypatch, _handler)
    _env_instance(monkeypatch)
    sd.configurer(BASE, "alice", "pa", principal="alice")
    assert sd.resoudre("alice")[1] == sd.PERSO
    assert sd.resoudre("bob")[1] == sd.INSTANCE


def test_forcer_un_compte_absent_est_une_erreur_nommee(monkeypatch):
    """Jamais de repli silencieux sur l'autre compte : déposer sous un compte qu'on n'a
    pas choisi est exactement ce que ce chantier corrige."""
    _env_instance(monkeypatch)
    with pytest.raises(sd.ShareDocsError, match="personnelle"):
        sd.resoudre("bob", sd.PERSO)
    sd.couper_instance()
    with pytest.raises(sd.ShareDocsError, match="instance"):
        sd.resoudre("bob", sd.INSTANCE)


def test_compte_inconnu_refuse(monkeypatch):
    _env_instance(monkeypatch)
    with pytest.raises(sd.ShareDocsError, match="Compte inconnu"):
        sd.resoudre("bob", "celui-du-voisin")


def test_couper_l_instance_ne_la_fait_pas_repartir_de_l_env(monkeypatch):
    """Sans la distinction « pas encore chargée » / « coupée », la couper n'aurait aucun
    effet : elle repartirait de l'environnement au premier accès suivant."""
    _env_instance(monkeypatch)
    assert sd.instance() is not None
    sd.couper_instance()
    assert sd.instance() is None


def test_l_instance_exige_ses_trois_variables(monkeypatch):
    """Une URL sans mot de passe ne fait pas une session, seulement un pré-remplissage."""
    monkeypatch.setenv("BD_SHAREDOCS_URL", BASE)
    monkeypatch.setenv("BD_SHAREDOCS_USER", "instance")
    monkeypatch.delenv("BD_SHAREDOCS_PASS", raising=False)
    sd.reinitialiser()
    assert sd.instance() is None
    assert sd.env_prefill()["user"] == "instance"      # le formulaire, lui, est pré-rempli


def test_aucune_session_personnelle_sans_identite():
    """Derrière le proxy sans identité, aucune session personnelle : les ranger toutes
    sous une même clé y ferait partager un compte Huma-Num entre inconnus."""
    with pytest.raises(sd.ShareDocsError, match="Aucune identité"):
        sd.configurer(BASE, "u", "p", principal=None)
    assert sd.perso(None) is None


def test_le_mot_de_passe_ne_sort_jamais(monkeypatch):
    """L'invariant de `docs/hebergement-securite.md` tient après le changement."""
    _use(monkeypatch, _handler)
    _env_instance(monkeypatch)
    sd.configurer(BASE, "alice", "tres-secret", principal="alice")
    etat = sd.status(principal="alice")
    assert "tres-secret" not in json.dumps(etat)
    assert "secret" not in json.dumps({k: v for k, v in etat.items() if k != "prefill"})
    assert "password" not in json.dumps(etat)


def test_etat_dit_lequel_des_deux_comptes_repondrait(monkeypatch):
    """Sinon on dépose sans savoir où — et dès que les deux comptes existent, la question
    n'a plus de réponse évidente."""
    _use(monkeypatch, _handler)
    _env_instance(monkeypatch)
    etat = sd.status(principal="bob")
    assert etat["actif"]["compte"] == sd.INSTANCE and etat["perso"] is None
    sd.configurer(BASE, "bob", "pb", principal="bob")
    etat = sd.status(principal="bob")
    assert etat["actif"]["compte"] == sd.PERSO and etat["actif"]["user"] == "bob"
    assert etat["instance"]["user"] == "instance"      # l'autre reste visible


def test_l_allowlist_vaut_aussi_pour_une_session_personnelle():
    """Le correctif SSRF ne doit pas se contourner en apportant sa propre URL."""
    with pytest.raises(sd.ShareDocsError, match="non autorisé"):
        sd.configurer("https://evil.example/dav", "u", "p", principal="alice")


# --------------------------------------------------------------------------- #
# Les routes
# --------------------------------------------------------------------------- #
def test_route_mono_poste_inchange(client, monkeypatch):
    """Hors proxy, tout retombe dans un emplacement UNIQUE : une seule personne devant sa
    machine, le comportement d'avant SHARE-1 à l'identique. C'est une case de la fiche, et
    elle ne se coche que par un test."""
    _use(monkeypatch, _handler)
    r = client.post("/api/sharedocs/connexion", json={"url": BASE, "user": "u",
                                                     "password": "p"})
    assert r.status_code == 200 and r.json()["connecte"] is True
    etat = client.get("/api/sharedocs/etat").json()
    assert etat["connecte"] is True and etat["user"] == "u"
    assert client.get("/api/sharedocs/liste").status_code == 200
    client.post("/api/sharedocs/deconnexion")
    assert client.get("/api/sharedocs/etat").json()["connecte"] is False


def test_route_deux_personnes_ne_se_marchent_pas_dessus(client, monkeypatch,
                                                        derriere_proxy):
    _use(monkeypatch, _handler)
    for qui in ("alice", "bob"):
        r = client.post("/api/sharedocs/connexion",
                        json={"url": BASE, "user": qui, "password": "x"},
                        headers={"Remote-User": qui})
        assert r.status_code == 200, r.text
    for qui in ("alice", "bob"):
        etat = client.get("/api/sharedocs/etat", headers={"Remote-User": qui}).json()
        assert etat["actif"]["user"] == qui, f"{qui} voit la session d'un autre"


def test_route_couper_l_instance_est_reserve_aux_admins(client, monkeypatch,
                                                        derriere_proxy):
    """Sans cette garde, la première personne qui clique « déconnexion » prive tout le
    monde du repli — une action personnelle aux effets collectifs."""
    _env_instance(monkeypatch)
    r = client.post("/api/sharedocs/deconnexion?compte=instance",
                    headers={"Remote-User": "alice"})
    assert r.status_code == 403
    assert sd.instance() is not None
    r = client.post("/api/sharedocs/deconnexion?compte=instance", headers=ADMIN)
    assert r.status_code == 200 and sd.instance() is None


def test_route_remplacer_l_instance_est_reserve_aux_admins(client, monkeypatch,
                                                           derriere_proxy):
    _use(monkeypatch, _handler)
    r = client.post("/api/sharedocs/connexion",
                    json={"url": BASE, "user": "x", "password": "p",
                          "compte": "instance"},
                    headers={"Remote-User": "alice"})
    assert r.status_code == 403
    r = client.post("/api/sharedocs/connexion",
                    json={"url": BASE, "user": "x", "password": "p",
                          "compte": "instance"}, headers=ADMIN)
    assert r.status_code == 200 and sd.instance()["user"] == "x"


def test_route_deposer_journalise_la_personne_et_le_compte(client, monkeypatch, db_path):
    """Le dépôt ne laissait AUCUNE trace : rien ne disait qui avait déposé quoi, ni sous
    quel compte. Les deux faits sont distincts dès qu'il y a deux comptes possibles."""
    monkeypatch.setattr(
        sd, "upload",
        lambda chemin, data, *, principal, compte=None:
            {"chemin": chemin, "compte": "instance", "user": "compte-labo"})
    r = client.post("/api/sharedocs/deposer-sauvegarde", json={"dossier": "Sauv"})
    assert r.status_code == 200
    assert r.json()["compte"] == "instance" and r.json()["compte_user"] == "compte-labo"
    ev = direct_query(
        db_path, "SELECT * FROM evenement WHERE cible_table = 'sharedocs'")
    assert len(ev) == 1, "le dépôt doit laisser un événement"
    apres = json.loads(ev[0]["apres"])
    assert apres["compte"] == "instance" and apres["compte_user"] == "compte-labo"
    assert apres["chemin"].startswith("Sauv/") and apres["taille"] > 0


def test_route_deposer_choisit_son_compte(client, monkeypatch):
    """Décision du 2026-08-28 : le compte se choisit à CHAQUE dépôt. Une sauvegarde
    déposée sous un compte personnel atterrit dans un espace qui s'en va avec la
    personne ; mais l'imposer priverait d'un dépôt de dépannage."""
    vu = {}
    monkeypatch.setattr(
        sd, "upload",
        lambda chemin, data, *, principal, compte=None:
            vu.update(compte=compte) or {"chemin": chemin, "compte": compte or "perso",
                                         "user": "u"})
    client.post("/api/sharedocs/deposer-sauvegarde",
                json={"dossier": "S", "compte": "instance"})
    assert vu["compte"] == "instance"


def test_route_etat_porte_le_contrat_de_l_ecran(client, monkeypatch, derriere_proxy):
    """L'écran lit `actif`, `perso` et `instance` — et rien d'autre pour décider quoi
    montrer. Ce test verrouille CE contrat : la logique d'affichage elle-même n'est pas
    atteignable par l'E2E (il faudrait un serveur WebDAV réel), donc le point de contact
    entre le serveur et l'écran est le seul endroit où l'on puisse se prémunir d'une
    dérive silencieuse.
    """
    _use(monkeypatch, _handler)
    _env_instance(monkeypatch)
    etat = client.get("/api/sharedocs/etat", headers={"Remote-User": "alice"}).json()
    assert set(("actif", "perso", "instance", "connecte", "prefill")) <= set(etat)
    assert etat["perso"] is None and etat["instance"]["user"] == "instance"
    assert etat["actif"]["compte"] == "instance"

    client.post("/api/sharedocs/connexion",
                json={"url": BASE, "user": "alice", "password": "x"},
                headers={"Remote-User": "alice"})
    etat = client.get("/api/sharedocs/etat", headers={"Remote-User": "alice"}).json()
    assert etat["actif"]["compte"] == "perso" and etat["perso"]["user"] == "alice"
    # Les DEUX restent listés : c'est ce qui fait paraître le sélecteur de compte.
    assert etat["instance"]["user"] == "instance"
    assert "password" not in json.dumps(etat)
