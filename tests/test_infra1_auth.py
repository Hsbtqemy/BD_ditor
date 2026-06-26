"""INFRA-1 — identité de l'utilisateur connecté exposée par /api/moi.

Derrière le proxy d'authentification (Authelia via Caddy), l'app reçoit l'en-tête
`Remote-User`. /api/moi le relaie (affichage seul) avec l'URL de déconnexion du
portail. Sans proxy (local), aucun en-tête → l'UI n'affiche ni nom ni logout.
"""
import main


def test_moi_sans_auth_local_renvoie_null(client, monkeypatch):
    """En local (pas de proxy d'auth, pas d'URL configurée) : tout est None."""
    monkeypatch.setattr(main, "AUTH_LOGOUT_URL", "")
    d = client.get("/api/moi").json()
    assert d == {"utilisateur": None, "nom": None, "deconnexion_url": None}


def test_moi_relaye_remote_user(client):
    """L'en-tête Remote-User (posé par le proxy) devient l'utilisateur courant."""
    d = client.get("/api/moi", headers={"Remote-User": "chercheur"}).json()
    assert d["utilisateur"] == "chercheur"
    assert d["nom"] == "chercheur"      # à défaut de Remote-Name, le nom = l'identifiant


def test_moi_nom_affichable_prioritaire(client):
    """Remote-Name (nom affichable) prime sur l'identifiant pour l'affichage."""
    d = client.get("/api/moi", headers={"Remote-User": "chercheur",
                                        "Remote-Name": "Jeanne Dupont"}).json()
    assert d["utilisateur"] == "chercheur"
    assert d["nom"] == "Jeanne Dupont"


def test_moi_entete_vide_ignoree(client):
    """Un en-tête présent mais vide/espaces ne fabrique pas un faux utilisateur."""
    d = client.get("/api/moi", headers={"Remote-User": "   "}).json()
    assert d["utilisateur"] is None
    assert d["nom"] is None


def test_moi_url_deconnexion_configuree(client, monkeypatch):
    """Quand BD_AUTH_LOGOUT_URL est posée, /api/moi la renvoie (lien de logout)."""
    monkeypatch.setattr(main, "AUTH_LOGOUT_URL", "https://auth.example.fr/logout")
    d = client.get("/api/moi", headers={"Remote-User": "chercheur"}).json()
    assert d["deconnexion_url"] == "https://auth.example.fr/logout"
