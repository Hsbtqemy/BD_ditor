"""Client WebDAV minimal pour ShareDocs (Huma-Num) + sessions en mémoire.

SÉCURITÉ — les identifiants (URL / utilisateur / mot de passe) sont gardés
UNIQUEMENT en mémoire du process serveur : jamais écrits sur disque, jamais
renvoyés au client, jamais loggés. Ils sont perdus au redémarrage. Les variables
d'environnement BD_SHAREDOCS_URL / BD_SHAREDOCS_USER / BD_SHAREDOCS_PASS déclarent
le compte de l'INSTANCE (cf. § Sessions) et pré-remplissent le formulaire — sans
rien stocker dans le dépôt.

SHARE-1 — il y a DEUX sortes de sessions, pas une. Avant, un dictionnaire de module
en tenait une seule pour tout le processus : le premier connecté la fixait pour tout
le monde, et Bob déposait sur Huma-Num sous le compte d'Alice.

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

# --------------------------------------------------------------------------- #
# Sessions (SHARE-1) — une d'instance, et une par personne
# --------------------------------------------------------------------------- #
# Décision du 2026-08-27 : les DEUX, pas l'une ou l'autre.
#
#   · la session d'INSTANCE — le compte du porteur du projet, déclaré par
#     BD_SHAREDOCS_URL/USER/PASS. Un dépôt pérenne institutionnel n'a pas vocation à
#     dépendre de qui est connecté, ni à suivre quelqu'un qui s'en va.
#   · les sessions PERSONNELLES — une par principal. Elles apportent le suivi, les
#     dossiers propres à chacun, et l'absence de conflit d'écriture.
#
# Ce module ne sait RIEN du proxy d'authentification : il range des identifiants sous la
# clé qu'on lui donne, et ne se demande jamais d'où elle vient. Qui est « je » se décide
# dans `autorisation.py` ; deux implémentations de « qui est là » finiraient par diverger.
# C'est pourquoi `principal` est un paramètre OBLIGATOIRE (keyword-only sans défaut) de
# toute opération : un défaut ferait retomber un appelant distrait sur le compte de
# l'instance, ce qui marcherait parfaitement — et déposerait sous le mauvais compte.
PERSO = "perso"
INSTANCE = "instance"
COMPTES = (PERSO, INSTANCE)

# `_NON_CHARGEE` distingue « pas encore lue dans l'environnement » de « absente ou coupée
# exprès ». Sans cette distinction, couper la session d'instance n'aurait aucun effet :
# elle repartirait de l'env au premier accès suivant.
_NON_CHARGEE = object()
_instance = _NON_CHARGEE
_perso: dict = {}


def _env_instance():
    """La session d'instance telle que l'environnement la déclare, ou None.

    Les TROIS variables sont requises : une URL sans mot de passe ne fait pas une session,
    elle ne fait qu'un pré-remplissage de formulaire (cf. `env_prefill`).
    """
    url = (os.environ.get("BD_SHAREDOCS_URL") or "").strip().rstrip("/")
    user = (os.environ.get("BD_SHAREDOCS_USER") or "").strip()
    mdp = os.environ.get("BD_SHAREDOCS_PASS") or ""
    if not (url and user and mdp):
        return None
    return {"url": url, "user": user, "password": mdp}


def instance():
    """La session d'instance, ou None. Chargée depuis l'environnement au PREMIER accès.

    Elle n'est PAS validée au chargement : un PROPFIND de vérification ferait dépendre le
    démarrage de la disponibilité d'Huma-Num, et un serveur qui refuse de servir le corpus
    local parce qu'un service distant est en panne serait un mauvais échange. Des
    identifiants faux se signalent à la première opération, avec le message de ShareDocs.
    """
    global _instance
    if _instance is _NON_CHARGEE:
        _instance = _env_instance()
    return _instance


def configurer_instance(url: str, user: str, password: str) -> dict:
    """Remplace la session d'instance (administrateurs — la garde est dans `main`)."""
    session = _valider(url, user, password)
    global _instance
    _instance = session
    return {"url": session["url"], "user": session["user"]}


def couper_instance() -> None:
    """Coupe la session d'instance jusqu'au redémarrage — elle ne repart PAS de l'env."""
    global _instance
    _instance = None


def reinitialiser() -> None:
    """Vide TOUTES les sessions (isolation des tests). Nommée plutôt que laissée aux
    internes, parce qu'il y a deux magasins depuis SHARE-1 : n'en vider qu'un ferait fuir
    une session d'un test à l'autre, et c'est le genre de fuite qui produit un vert
    trompeur — le test suivant trouverait une session qu'il n'a pas ouverte."""
    global _instance
    _instance = _NON_CHARGEE
    _perso.clear()


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


def _valider(url: str, user: str, password: str) -> dict:
    """Contrôle l'URL (anti-SSRF) et les identifiants (PROPFIND racine), puis rend la
    session. Partagé par la session d'instance et les sessions personnelles : deux
    validations distinctes finiraient par ne plus border la même chose."""
    url = (url or "").strip().rstrip("/")
    if not url or not user or not password:
        raise ShareDocsError("URL, utilisateur et mot de passe requis.")
    _check_url(url)                                  # anti-SSRF (allowlist d'hôte)
    _propfind(url, user, password, "", depth="0")   # lève si refusé/injoignable
    return {"url": url, "user": user, "password": password}


def configurer(url: str, user: str, password: str, *, principal) -> dict:
    """Ouvre (ou remplace) la session PERSONNELLE de `principal`. RAM uniquement."""
    if principal is None:
        raise ShareDocsError(
            "Aucune identité : impossible d'ouvrir une session ShareDocs personnelle. "
            "Derrière le proxy d'authentification, cela signale que l'en-tête d'identité "
            "n'arrive pas jusqu'à l'application.")
    session = _valider(url, user, password)
    _perso[principal] = session
    return {"connecte": True, "url": session["url"], "user": session["user"],
            "compte": PERSO}


def deconnecter(*, principal) -> None:
    """Ferme MA session. Celle de l'instance ne se coupe pas par ce chemin : la première
    personne qui cliquerait « déconnexion » en priverait tout le monde."""
    _perso.pop(principal, None)


def perso(principal):
    """La session personnelle de `principal`, ou None. `principal=None` n'en a pas."""
    return _perso.get(principal) if principal is not None else None


def resoudre(principal, compte=None):
    """(session, origine) — l'origine vaut PERSO ou INSTANCE.

    `compte` force le choix ; None applique la règle simple : la mienne si j'en ai une,
    celle de l'instance sinon. Forcer un compte absent est une ERREUR nommée, jamais un
    repli silencieux sur l'autre — déposer sous un compte qu'on n'a pas choisi est
    exactement ce que ce chantier corrige.
    """
    if compte is not None and compte not in COMPTES:
        raise ShareDocsError(f"Compte inconnu : {compte} ({' | '.join(COMPTES)}).")
    mienne = perso(principal)
    if compte == PERSO:
        if mienne is None:
            raise ShareDocsError("Aucune session ShareDocs personnelle : connectez-vous.")
        return mienne, PERSO
    if compte == INSTANCE:
        celle_ci = instance()
        if celle_ci is None:
            raise ShareDocsError(
                "Aucun compte ShareDocs d'instance n'est configuré "
                "(BD_SHAREDOCS_URL / USER / PASS).")
        return celle_ci, INSTANCE
    if mienne is not None:
        return mienne, PERSO
    celle_ci = instance()
    if celle_ci is not None:
        return celle_ci, INSTANCE
    raise ShareDocsError("Non connecté à ShareDocs.")


def _vue(session):
    """Ce qu'on peut montrer d'une session : jamais le mot de passe."""
    return {"url": session["url"], "user": session["user"]} if session else None


def status(*, principal) -> dict:
    """Ce que l'écran doit savoir, et d'abord : LEQUEL des deux comptes répondrait.

    Sans `actif`, on dépose sans savoir où — et le jour où les deux comptes existent, la
    question n'a plus de réponse évidente. Les clés `url`/`user` à plat décrivent le compte
    ACTIF ; elles restent pour l'écran, qui les lisait déjà.
    """
    try:
        session, origine = resoudre(principal)
    except ShareDocsError:
        session, origine = None, None
    return {"connecte": session is not None,
            "actif": {**_vue(session), "compte": origine} if session else None,
            "perso": _vue(perso(principal)),
            "instance": _vue(instance()),
            "prefill": env_prefill(),
            "url": session["url"] if session else None,
            "user": session["user"] if session else None}


def list_dir(path: str = "", *, principal, compte=None) -> list[dict]:
    """Liste un dossier (dossiers d'abord, puis fichiers, triés par nom)."""
    session, _ = resoudre(principal, compte)
    path = (path or "").strip("/")
    entries = _propfind(session["url"], session["user"], session["password"],
                        path, depth="1")
    # Retire l'entrée représentant le dossier lui-même (incluse par PROPFIND).
    entries = [e for e in entries if e["path"].strip("/") != path]
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def download(path: str, *, principal, compte=None) -> bytes:
    """Télécharge le contenu d'un fichier distant."""
    session, _ = resoudre(principal, compte)
    target = _join(session["url"], path)
    try:
        with _client(session["user"], session["password"]) as c:
            r = c.get(target)
    except httpx.HTTPError as exc:
        raise ShareDocsError(f"Téléchargement échoué : {exc}") from exc
    _reject_redirect(r)
    if r.status_code >= 400:
        raise ShareDocsError(f"Téléchargement de {path!r} : {r.status_code}.")
    return r.content


def upload(path: str, data: bytes, *, principal, compte=None) -> dict:
    """Dépose un fichier sur ShareDocs (PUT WebDAV) ; lève si l'écriture échoue.

    Renvoie {'chemin', 'status', 'compte', 'user'} : le compte EMPLOYÉ fait partie du
    résultat, parce que l'appelant doit pouvoir le journaliser — qui a cliqué et sous quel
    compte Huma-Num sont deux faits différents dès qu'il y a deux comptes possibles.
    Un 403 signale un dossier en lecture seule (cas des montages partagés « tools »).
    """
    session, origine = resoudre(principal, compte)
    target = _join(session["url"], path)
    try:
        with _client(session["user"], session["password"]) as c:
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
    return {"chemin": path, "status": r.status_code,
            "compte": origine, "user": session["user"]}
