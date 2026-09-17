"""AUTH-6 — la lecture de l'annuaire : ce qu'elle rend, comment elle échoue, et ce qu'elle ne
touche pas.

Trois attendus de la fiche, dans cet ordre de gravité :
(a) le chemin d'autorisation continue de ne lire que `Remote-Groups` : `autorisation.py`
    n'atteint pas ce module, et un annuaire qui dit autre chose que le portail ne change
    aucune portée ;
(b) l'application n'authentifie toujours personne : seul l'écran d'administration lit ;
(c) une panne rend « non vérifié », en moins du délai, et ne lève jamais.
"""
import ast
import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import annuaire  # noqa: E402
import config  # noqa: E402

from conftest import ADMIN  # noqa: E402

LLDAP = "http://lldap.test:17170"


@pytest.fixture
def lldap_configure(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", LLDAP)
    monkeypatch.setattr(config, "ANNUAIRE_COMPTE", "bd-application")
    monkeypatch.setattr(config, "ANNUAIRE_MOT_DE_PASSE", "secret-de-test")
    monkeypatch.setattr(config, "ANNUAIRE_URL", "https://annuaire.example.fr/")


def _reponse_graphql():
    return {"data": {
        "users": [
            {"id": "alice", "email": "alice@x.invalid", "displayName": "Alice Martin",
             "groups": [{"id": 5, "displayName": "annotateurs"}]},
            {"id": "svc", "email": "", "displayName": "",
             "groups": [{"id": 3, "displayName": "lldap_strict_readonly"}]},
        ],
        "groups": [{"id": 3, "displayName": "lldap_strict_readonly"},
                   {"id": 5, "displayName": "annotateurs"},
                   {"id": 9, "displayName": "vide"}]}}


def _transport(login=None, graphql=None, vus=None):
    """Un LLDAP simulé. `login` / `graphql` : (statut, corps) ou une exception à lever."""
    def gerer(requete: httpx.Request):
        if vus is not None:
            vus.append(requete)
        chemin, reponse = requete.url.path, None
        if chemin == "/auth/simple/login":
            reponse = login or (200, {"token": "jeton-de-test", "refreshToken": "r"})
        elif chemin == "/api/graphql":
            reponse = graphql or (200, _reponse_graphql())
        if isinstance(reponse, Exception):
            raise reponse
        statut, corps = reponse
        if isinstance(corps, (bytes, str)):
            return httpx.Response(statut, content=corps)
        return httpx.Response(statut, json=corps)
    return httpx.MockTransport(gerer)


# --------------------------------------------------------------------------- #
# Ce que la lecture rend
# --------------------------------------------------------------------------- #
def test_sans_adresse_il_n_y_a_pas_d_annuaire_et_ce_n_est_pas_une_panne(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "")
    lecture = annuaire.lire()
    assert (lecture.etat, lecture.source, lecture.motif) == ("sans_annuaire", None, None)
    assert lecture.comptes == () and lecture.groupes == ()


def test_une_lecture_rend_comptes_groupes_et_membres(lldap_configure):
    vus = []
    lecture = annuaire.lire(transport=_transport(vus=vus))
    assert (lecture.etat, lecture.source) == ("lu", "lldap")
    assert isinstance(lecture.duree_ms, int) and lecture.lu_le.endswith("Z")
    assert lecture.lien == "https://annuaire.example.fr/"
    comptes = {c.login: c for c in lecture.comptes}
    assert comptes["alice"].groupes == ("annotateurs",)
    # LLDAP rend "" pour un champ vide : un écran qui l'afficherait croirait avoir un nom.
    assert (comptes["svc"].nom, comptes["svc"].courriel) == (None, None)
    groupes = {g.nom: g for g in lecture.groupes}
    assert (groupes["annotateurs"].id, groupes["annotateurs"].membres) == (5, ("alice",))
    assert groupes["vide"].membres == ()             # un groupe sans membre est RENDU
    # La connexion porte le compte de service, la requête porte le jeton.
    connexion, requete = vus
    assert json.loads(connexion.content) == {"username": "bd-application",
                                             "password": "secret-de-test"}
    assert requete.headers["Authorization"] == "Bearer jeton-de-test"


def test_la_doublure_passe_par_le_meme_analyseur(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:")
    lecture = annuaire.lire()
    assert (lecture.etat, lecture.source) == ("lu", "doublure")
    groupes = {g.nom: g for g in lecture.groupes}
    assert len(groupes["etudiants-bd-2026"].membres) == 12
    assert groupes["etudiants-bd-2026"].id == 6
    assert set(annuaire.GROUPES_DE_ROLE) <= set(groupes)


def test_la_doublure_en_panne_n_est_pas_verifiee(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:panne")
    lecture = annuaire.lire()
    assert (lecture.etat, lecture.source, lecture.motif) == ("non_verifie", "doublure", "delai")


# --------------------------------------------------------------------------- #
# (c) — comment elle échoue : jamais par une exception, toujours en le disant
# --------------------------------------------------------------------------- #
def test_une_adresse_sans_compte_de_service_est_un_refus(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", LLDAP)
    monkeypatch.setattr(config, "ANNUAIRE_COMPTE", "")
    monkeypatch.setattr(config, "ANNUAIRE_MOT_DE_PASSE", "")
    assert (annuaire.lire().etat, annuaire.lire().motif) == ("non_verifie", "refus")


@pytest.mark.parametrize("login,graphql,motif", [
    ((401, {"error": "mauvais mot de passe"}), None, "refus"),
    (None, (200, {"errors": [{"message": "Unauthorized"}]}), "refus"),
    (None, (403, {}), "refus"),
    (None, (500, "erreur interne"), "reponse_illisible"),
    (None, (200, b"<html>pas du json</html>"), "reponse_illisible"),
    (None, (200, {"data": {"users": [{"email": "sans-id"}], "groups": []}}),
     "reponse_illisible"),
    (httpx.ConnectError("refusée"), None, "delai"),
    (None, httpx.ReadTimeout("trop long"), "delai"),
])
def test_une_panne_rend_non_verifie_avec_son_motif(lldap_configure, login, graphql, motif):
    lecture = annuaire.lire(transport=_transport(login=login, graphql=graphql))
    assert (lecture.etat, lecture.motif) == ("non_verifie", motif)
    assert lecture.comptes == () and lecture.groupes == ()


def test_un_annuaire_muet_est_abandonne_dans_le_delai(lldap_configure, monkeypatch):
    """Un vrai serveur qui accepte la connexion et ne répond jamais : la lecture doit rendre
    la main d'elle-même. Un délai par requête ne suffirait pas — deux requêtes lentes
    doubleraient l'attente —, c'est le délai TOTAL qui est borné."""
    ecoute = socket.socket()
    ecoute.bind(("127.0.0.1", 0))
    ecoute.listen(4)
    acceptees = []

    def accepter():
        while True:
            try:
                acceptees.append(ecoute.accept()[0])
            except OSError:
                return
    threading.Thread(target=accepter, daemon=True).start()
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", f"http://127.0.0.1:{ecoute.getsockname()[1]}")
    monkeypatch.setattr(annuaire, "DELAI_S", 0.6)
    try:
        debut = time.monotonic()
        lecture = annuaire.lire()
        duree = time.monotonic() - debut
    finally:
        ecoute.close()
        for s in acceptees:
            s.close()
    assert (lecture.etat, lecture.motif) == ("non_verifie", "delai")
    assert duree < 2.0, duree


def test_le_delai_est_total_et_non_par_requete(lldap_configure, monkeypatch):
    """La connexion répond, mais tard ; la requête ne répond jamais. Un délai PAR requête
    ferait attendre la somme des deux, et la vue avec ; le délai total rend la main à
    `DELAI_S`, la seconde requête ne recevant que ce qui reste."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Lent(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path == "/auth/simple/login":
                time.sleep(0.7)
                corps = json.dumps({"token": "t"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)
            else:
                time.sleep(2.5)

        def log_message(self, *args):
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Lent)
    serveur.daemon_threads = True
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", f"http://127.0.0.1:{serveur.server_address[1]}")
    monkeypatch.setattr(annuaire, "DELAI_S", 1.0)
    try:
        debut = time.monotonic()
        lecture = annuaire.lire()
        duree = time.monotonic() - debut
    finally:
        serveur.shutdown()
        serveur.server_close()
    assert (lecture.etat, lecture.motif) == ("non_verifie", "delai")
    assert duree < 1.4, f"{duree:.2f} s : le délai s'est appliqué par requête, pas au total"


# --------------------------------------------------------------------------- #
# (a) et (b) — ce que la lecture ne touche pas
# --------------------------------------------------------------------------- #
def _modules_atteints(depart: str) -> set:
    """Les modules du dépôt qu'un module importe, de proche en proche, lus dans le SOURCE."""
    vus, a_voir = set(), [depart]
    while a_voir:
        nom = a_voir.pop()
        if nom in vus:
            continue
        vus.add(nom)
        fichier = REPO_ROOT / f"{nom.replace('.', '/')}.py"
        if not fichier.exists():
            continue
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                a_voir += [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module and not noeud.level:
                a_voir.append(noeud.module)
    return vus


def test_l_autorisation_n_atteint_pas_l_annuaire():
    """(a) — `autorisation.py` tranche sur `Remote-Groups` ; s'il atteignait ce module, même
    indirectement, une réponse de l'annuaire pourrait un jour peser sur une portée."""
    atteints = _modules_atteints("autorisation")
    assert "annuaire" not in atteints and "comptes" not in atteints, sorted(atteints)


def test_seules_les_routes_d_administration_lisent_l_annuaire():
    """(b) — l'application n'authentifie personne : aucun chemin de requête ne consulte
    l'annuaire, hormis les routes d'administration — la vue des comptes et des groupes, et
    ce que la fiche d'une collection propose à son propriétaire (étape 3). Toutes vivent
    dans `routes/collections.py`, et leur composition dans `comptes.py`."""
    lecteurs = set()
    for fichier in [*REPO_ROOT.glob("*.py"), *REPO_ROOT.glob("routes/*.py"),
                    *REPO_ROOT.glob("pipeline/*.py")]:
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            noms = ([a.name for a in noeud.names] if isinstance(noeud, ast.Import)
                    else [noeud.module] if isinstance(noeud, ast.ImportFrom) else [])
            if "annuaire" in noms:
                lecteurs.add(fichier.relative_to(REPO_ROOT).as_posix())
    assert lecteurs == {"comptes.py", "routes/collections.py"}, sorted(lecteurs)


def test_un_annuaire_qui_contredit_le_portail_ne_change_aucune_portee(
        client, derriere_proxy, monkeypatch):
    """(a) — la doublure fait de `lectrice` un membre d'`annotateurs`. Le portail, lui, ne
    transmet aucun groupe : la collection ouverte à `annotateurs` reste fermée, même après
    que la vue a lu l'annuaire. Et transmis par le portail, le groupe ouvre."""
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:")
    cid = client.post("/api/collections", json={"nom": "Ouverte aux annotateurs"},
                      headers=ADMIN).json()["id"]
    assert client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                      json={"genre": "groupe", "principal": "annotateurs",
                            "niveau": "lecture"}).status_code in (200, 201, 204)
    vue = client.get("/api/comptes-et-groupes", headers=ADMIN).json()
    assert vue["annuaire"]["etat"] == "lu"
    lectrice = next(c for c in vue["comptes"] if c["login"] == "lectrice")
    assert "annotateurs" in lectrice["groupes"]

    sans_groupe = client.get("/api/collections", headers={"Remote-User": "lectrice"}).json()
    assert cid not in {c["id"] for c in sans_groupe}
    avec_groupe = client.get("/api/collections", headers={"Remote-User": "lectrice",
                                                          "Remote-Groups": "annotateurs"}).json()
    assert cid in {c["id"] for c in avec_groupe}
