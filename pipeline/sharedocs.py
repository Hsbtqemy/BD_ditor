"""Client WebDAV minimal pour ShareDocs (Huma-Num) + session en mémoire.

SÉCURITÉ — les identifiants (URL / utilisateur / mot de passe) sont gardés
UNIQUEMENT en mémoire du process serveur : jamais écrits sur disque, jamais
renvoyés au client, jamais loggés. Ils sont perdus au redémarrage. Un
pré-remplissage est possible via les variables d'environnement
BD_SHAREDOCS_URL / BD_SHAREDOCS_USER / BD_SHAREDOCS_PASS — pratique pour ne pas
retaper, sans rien stocker dans le dépôt.

On n'utilise que la LECTURE : PROPFIND pour lister un dossier, GET pour
télécharger un fichier. Le dépôt sur ShareDocs passe par l'interface web
(l'écriture WebDAV est bloquée sur les montages partagés).
"""
from __future__ import annotations

import ipaddress
import os
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlsplit

import httpx

_DAV = {"d": "DAV:"}

_PROPFIND_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:"><d:prop>'
    "<d:resourcetype/><d:getcontentlength/>"
    "<d:getlastmodified/><d:displayname/>"
    "</d:prop></d:propfind>"
)

# Session en mémoire (application locale mono-poste : un seul utilisateur).
_session: dict = {"url": None, "user": None, "password": None}


class ShareDocsError(RuntimeError):
    """Erreur ShareDocs (non connecté, identifiants refusés, réseau…)."""


# --------------------------------------------------------------------------- #
# Bas niveau HTTP / WebDAV
# --------------------------------------------------------------------------- #
def _client(user: str, password: str) -> httpx.Client:
    """Client httpx authentifié (Basic). Isolé pour pouvoir être mocké en test.

    `follow_redirects=False` : anti-SSRF — une redirection depuis l'hôte autorisé
    vers une cible interne (ex. métadonnées cloud) ne doit jamais être suivie."""
    return httpx.Client(auth=(user, password), timeout=30.0, follow_redirects=False)


def _allowed_hosts() -> set[str]:
    """Hôtes ShareDocs autorisés (anti-SSRF), configurables et évolutifs."""
    raw = os.environ.get("BD_SHAREDOCS_ALLOWED_HOSTS", "sharedocs.huma-num.fr")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _http_autorise() -> bool:
    """Autorise http:// (identifiants Basic en clair) — opt-out EXPLICITE, à réserver à
    un réseau de confiance ou aux tests. Par défaut, https est imposé."""
    return os.environ.get("BD_SHAREDOCS_ALLOW_HTTP", "").strip().lower() in ("1", "true", "oui")


def _check_url(url: str) -> None:
    """Refuse toute URL hors allowlist d'hôte (et toute IP interne) — anti-SSRF.
    L'URL ShareDocs est saisie par l'utilisateur ; sans ce garde-fou, le serveur
    pourrait être détourné pour requêter des cibles internes."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ShareDocsError("URL ShareDocs invalide (schéma http/https requis).")
    host = (parts.hostname or "").lower()
    if not host:
        raise ShareDocsError("URL ShareDocs invalide (hôte manquant).")
    allowed = _allowed_hosts()
    if host not in allowed:
        raise ShareDocsError(
            f"Hôte ShareDocs non autorisé : {host}. "
            f"Autorisé(s) : {', '.join(sorted(allowed)) or '(aucun)'} "
            "(configurable via BD_SHAREDOCS_ALLOWED_HOSTS).")
    try:                                   # défense supplémentaire : pas d'IP interne
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ShareDocsError("Adresse IP interne interdite.")
    except ValueError:
        pass                               # host = nom de domaine (pas une IP) → OK
    # HTTPS imposé EN DERNIER (après allowlist/IP, pour que ces refus priment) : sinon
    # les identifiants Basic partiraient en clair. Opt-out explicite documenté.
    if parts.scheme != "https" and not _http_autorise():
        raise ShareDocsError(
            "URL ShareDocs en http:// refusée : les identifiants partiraient en clair. "
            "Utilisez https:// (ou BD_SHAREDOCS_ALLOW_HTTP=1 sur un réseau de confiance).")


def _reject_redirect(r: httpx.Response) -> None:
    """Anti-SSRF : les redirections ne sont pas suivies (`follow_redirects=False`),
    donc une réponse 3xx ne doit jamais être prise pour un succès — on la traite
    explicitement en erreur (sinon `download` renverrait le corps de la redirection)."""
    if 300 <= r.status_code < 400:
        raise ShareDocsError(
            f"Redirection inattendue ({r.status_code}) — non suivie (sécurité).")


def _join(base_url: str, path: str) -> str:
    """Concatène base + chemin relatif, chaque segment étant url-encodé.

    Refuse tout segment `..` (anti-traversée : un chemin distant ne doit jamais
    remonter au-dessus de la racine ShareDocs) ; les segments vides et `.` sont
    ignorés (normalisation). Couvre list_dir / download / upload (tous via _join)."""
    base = base_url.rstrip("/")
    segs = [s for s in (path or "").split("/") if s not in ("", ".")]
    if any(s == ".." for s in segs):
        raise ShareDocsError("Chemin ShareDocs invalide : '..' interdit (anti-traversée).")
    if not segs:
        return base + "/"
    return base + "/" + "/".join(quote(seg) for seg in segs)


def _parse_multistatus(text: str, base_url: str) -> list[dict]:
    """Transforme un <d:multistatus> en liste {name, path, is_dir, size}."""
    base_path = unquote(urlsplit(base_url).path).rstrip("/")
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        raise ShareDocsError(f"Réponse ShareDocs illisible : {exc}") from exc

    entries = []
    for resp in root.findall("d:response", _DAV):
        href = resp.findtext("d:href", default="", namespaces=_DAV)
        rel = unquote(urlsplit(href).path)
        # Retire le préfixe de base, mais seulement sur une frontière de segment
        # (évite de tronquer un voisin du type .../u → .../username2).
        if rel == base_path:
            rel = ""
        elif rel.startswith(base_path + "/"):
            rel = rel[len(base_path):]
        rel = rel.strip("/")

        prop = resp.find("d:propstat/d:prop", _DAV)
        is_dir, size, name = False, None, None
        if prop is not None:
            rtype = prop.find("d:resourcetype", _DAV)
            is_dir = rtype is not None and rtype.find("d:collection", _DAV) is not None
            size_txt = (prop.findtext("d:getcontentlength", namespaces=_DAV) or "").strip()
            size = int(size_txt) if size_txt.isdigit() else None
            name = (prop.findtext("d:displayname", namespaces=_DAV) or "").strip() or None
        if not name:
            name = rel.rsplit("/", 1)[-1] or "/"
        entries.append({"name": name, "path": rel, "is_dir": is_dir, "size": size})
    return entries


def _propfind(url: str, user: str, password: str, path: str, depth: str) -> list[dict]:
    target = _join(url, path)
    try:
        with _client(user, password) as c:
            r = c.request(
                "PROPFIND", target,
                headers={"Depth": depth, "Content-Type": "application/xml"},
                content=_PROPFIND_BODY,
            )
    except httpx.HTTPError as exc:
        raise ShareDocsError(f"Connexion ShareDocs échouée : {exc}") from exc
    _reject_redirect(r)
    if r.status_code in (401, 403):
        raise ShareDocsError("Identifiants refusés par ShareDocs (401/403).")
    if r.status_code >= 400:
        raise ShareDocsError(f"ShareDocs a répondu {r.status_code}.")
    return _parse_multistatus(r.text, url)


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
def env_prefill() -> dict:
    """Pré-remplissage du formulaire (URL + user uniquement, JAMAIS le mot de passe)."""
    return {"url": os.environ.get("BD_SHAREDOCS_URL", ""),
            "user": os.environ.get("BD_SHAREDOCS_USER", "")}


def status() -> dict:
    return {"connecte": bool(_session["url"]),
            "url": _session["url"], "user": _session["user"],
            "prefill": env_prefill()}


def configure(url: str, user: str, password: str) -> dict:
    """Valide les identifiants (PROPFIND racine) puis les mémorise (RAM only)."""
    url = (url or "").strip().rstrip("/")
    if not url or not user or not password:
        raise ShareDocsError("URL, utilisateur et mot de passe requis.")
    _check_url(url)                                  # anti-SSRF (allowlist d'hôte)
    _propfind(url, user, password, "", depth="0")   # lève si refusé/injoignable
    _session.update(url=url, user=user, password=password)
    return {"connecte": True, "url": url, "user": user}


def disconnect() -> None:
    _session.update(url=None, user=None, password=None)


def _require_session() -> None:
    if not _session["url"]:
        raise ShareDocsError("Non connecté à ShareDocs.")


def list_dir(path: str = "") -> list[dict]:
    """Liste un dossier (dossiers d'abord, puis fichiers, triés par nom)."""
    _require_session()
    path = (path or "").strip("/")
    entries = _propfind(_session["url"], _session["user"], _session["password"],
                        path, depth="1")
    # Retire l'entrée représentant le dossier lui-même (incluse par PROPFIND).
    entries = [e for e in entries if e["path"].strip("/") != path]
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def download(path: str) -> bytes:
    """Télécharge le contenu d'un fichier distant."""
    _require_session()
    target = _join(_session["url"], path)
    try:
        with _client(_session["user"], _session["password"]) as c:
            r = c.get(target)
    except httpx.HTTPError as exc:
        raise ShareDocsError(f"Téléchargement échoué : {exc}") from exc
    _reject_redirect(r)
    if r.status_code >= 400:
        raise ShareDocsError(f"Téléchargement de {path!r} : {r.status_code}.")
    return r.content


def upload(path: str, data: bytes) -> dict:
    """Dépose un fichier sur ShareDocs (PUT WebDAV) ; lève si l'écriture échoue.

    Renvoie {'chemin', 'status'}. Un 403 signale un dossier en lecture seule
    (cas des montages partagés « tools ») — message explicite pour l'utilisateur.
    """
    _require_session()
    target = _join(_session["url"], path)
    try:
        with _client(_session["user"], _session["password"]) as c:
            r = c.put(target, content=data)
    except httpx.HTTPError as exc:
        raise ShareDocsError(f"Dépôt échoué : {exc}") from exc
    _reject_redirect(r)
    if r.status_code in (401, 403):
        raise ShareDocsError(
            "Écriture refusée par ShareDocs (403) — ce dossier est en lecture "
            "seule. Choisissez un dossier perso/projet inscriptible.")
    if r.status_code >= 400:
        raise ShareDocsError(f"Dépôt de {path!r} : {r.status_code}.")
    return {"chemin": path, "status": r.status_code}
