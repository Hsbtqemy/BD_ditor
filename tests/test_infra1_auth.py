"""INFRA-1 / AUTH-1 — identité de l'utilisateur connecté.

Derrière le proxy d'authentification (Authelia via Caddy), l'app reçoit `Remote-User`,
`Remote-Groups`, `Remote-Name` et `Remote-Email`. /api/moi les relaie et enregistre la
personne dans la table `utilisateur` (miroir d'affichage — aucun secret stocké).

AUTH-1 pose une GARDE : ces en-têtes ne sont crus que si `BD_AUTH_PROXY` déclare qu'on
est derrière le proxy. Sans le drapeau, ils sont ignorés — sinon n'importe quel client
atteignant l'app en direct pourrait se déclarer qui il veut, ce qui deviendra une
escalade de privilège dès que l'autorisation en dépendra (AUTH-2, AUTH-3).
"""
import sqlite3

import main


# --------------------------------------------------------------------------- #
# La garde de confiance (AUTH-1)
# --------------------------------------------------------------------------- #
def test_entete_ignoree_sans_declaration_de_proxy(client):
    """SANS `BD_AUTH_PROXY`, un `Remote-User` forgé n'a AUCUN effet.

    C'est le cœur de la garde : hors déploiement, l'app ne croit personne."""
    d = client.get("/api/moi", headers={"Remote-User": "intrus",
                                        "Remote-Groups": "admins"}).json()
    assert d["utilisateur"] is None
    assert d["groupes"] == []


def test_entete_ignoree_ne_signe_pas_les_actes(client, album, planche, db_path):
    """Sans proxy déclaré, un en-tête forgé ne s'inscrit pas non plus sur un verrou."""
    client.patch(f"/api/planches/{planche['id']}/verrou", json={"verrouillee": True},
                 headers={"Remote-User": "intrus"})
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT verrouillee, verrou_par FROM planches WHERE id = ?",
                           (planche["id"],)).fetchone()
    finally:
        conn.close()
    assert row[0] is not None      # le verrou est bien posé...
    assert row[1] is None          # ...mais anonyme, l'en-tête n'ayant pas été crue


# --------------------------------------------------------------------------- #
# Comportement local (mono-poste, sans proxy) — inchangé depuis INFRA-1
# --------------------------------------------------------------------------- #
def test_moi_sans_auth_local_renvoie_null(client, monkeypatch):
    """En local (pas de proxy, pas d'URL configurée) : tout est None."""
    monkeypatch.setattr(main, "AUTH_LOGOUT_URL", "")
    d = client.get("/api/moi").json()
    assert d == {"utilisateur": None, "nom": None, "groupes": [],
                 "deconnexion_url": None}


# --------------------------------------------------------------------------- #
# Derrière le proxy
# --------------------------------------------------------------------------- #
def test_moi_relaye_remote_user(client, derriere_proxy):
    """L'en-tête Remote-User (posé par le proxy) devient l'utilisateur courant."""
    d = client.get("/api/moi", headers={"Remote-User": "chercheur"}).json()
    assert d["utilisateur"] == "chercheur"
    assert d["nom"] == "chercheur"      # à défaut de Remote-Name, le nom = l'identifiant


def test_moi_nom_affichable_prioritaire(client, derriere_proxy):
    """Remote-Name (nom affichable) prime sur l'identifiant pour l'affichage."""
    d = client.get("/api/moi", headers={"Remote-User": "chercheur",
                                        "Remote-Name": "Jeanne Dupont"}).json()
    assert d["utilisateur"] == "chercheur"
    assert d["nom"] == "Jeanne Dupont"


def test_moi_entete_vide_ignoree(client, derriere_proxy):
    """Un en-tête présent mais vide/espaces ne fabrique pas un faux utilisateur."""
    d = client.get("/api/moi", headers={"Remote-User": "   "}).json()
    assert d["utilisateur"] is None
    assert d["nom"] is None


def test_moi_url_deconnexion_configuree(client, derriere_proxy, monkeypatch):
    """Quand BD_AUTH_LOGOUT_URL est posée, /api/moi la renvoie (lien de logout)."""
    monkeypatch.setattr(main, "AUTH_LOGOUT_URL", "https://auth.example.fr/logout")
    d = client.get("/api/moi", headers={"Remote-User": "chercheur"}).json()
    assert d["deconnexion_url"] == "https://auth.example.fr/logout"


# --------------------------------------------------------------------------- #
# Groupes (AUTH-1) — relus à chaque requête, JAMAIS stockés
# --------------------------------------------------------------------------- #
def test_groupes_lus_depuis_remote_groups(client, derriere_proxy):
    """Authelia envoie les groupes séparés par des virgules."""
    d = client.get("/api/moi",
                   headers={"Remote-User": "chercheur",
                            "Remote-Groups": "annotateurs, linguistes"}).json()
    assert d["groupes"] == ["annotateurs", "linguistes"]


def test_groupes_absents_donnent_liste_vide(client, derriere_proxy):
    """Pas d'en-tête de groupes → liste vide, pas None (contrat stable pour l'UI)."""
    d = client.get("/api/moi", headers={"Remote-User": "chercheur"}).json()
    assert d["groupes"] == []


def test_groupes_non_stockes_en_base(client, derriere_proxy, db_path):
    """Les groupes ne sont PAS persistés : retirer quelqu'un d'un groupe doit prendre
    effet immédiatement, sans intervention en base."""
    client.get("/api/moi", headers={"Remote-User": "chercheur",
                                    "Remote-Groups": "annotateurs"})
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(utilisateur)")}
    finally:
        conn.close()
    assert "groupes" not in cols and "role" not in cols


# --------------------------------------------------------------------------- #
# Miroir `utilisateur`
# --------------------------------------------------------------------------- #
def _utilisateurs(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT login, nom, email FROM utilisateur ORDER BY login").fetchall()
    finally:
        conn.close()


def test_utilisateur_enregistre_a_la_premiere_visite(client, derriere_proxy, db_path):
    client.get("/api/moi", headers={"Remote-User": "chercheur",
                                    "Remote-Name": "Jeanne Dupont",
                                    "Remote-Email": "j@example.fr"})
    assert _utilisateurs(db_path) == [("chercheur", "Jeanne Dupont", "j@example.fr")]


def test_utilisateur_rafraichi_si_le_nom_change(client, derriere_proxy, db_path):
    """Authelia reste la source de vérité : un nom modifié là-bas se reflète ici."""
    client.get("/api/moi", headers={"Remote-User": "chercheur", "Remote-Name": "Ancien"})
    client.get("/api/moi", headers={"Remote-User": "chercheur", "Remote-Name": "Nouveau"})
    assert _utilisateurs(db_path) == [("chercheur", "Nouveau", None)]


def test_aucun_utilisateur_enregistre_sans_proxy(client, db_path):
    """Sans proxy déclaré, aucune ligne n'est créée — même en forgeant l'en-tête."""
    client.get("/api/moi", headers={"Remote-User": "intrus"})
    assert _utilisateurs(db_path) == []


def test_aucun_secret_dans_la_table(client, derriere_proxy, db_path):
    """L'app n'authentifie personne : ni mot de passe, ni hash, ni jeton en base."""
    client.get("/api/moi", headers={"Remote-User": "chercheur"})
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1].lower() for r in conn.execute("PRAGMA table_info(utilisateur)")}
    finally:
        conn.close()
    assert not (cols & {"password", "mot_de_passe", "hash", "jeton", "token", "secret"})


# --------------------------------------------------------------------------- #
# Verrou de planche attribué (AUTH-1)
# --------------------------------------------------------------------------- #
def test_verrou_consigne_son_auteur(client, derriere_proxy, album, planche, db_path):
    client.patch(f"/api/planches/{planche['id']}/verrou", json={"verrouillee": True},
                 headers={"Remote-User": "chercheur", "Remote-Groups": "bd-admins"})
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT verrou_par FROM planches WHERE id = ?",
                           (planche["id"],)).fetchone()
    finally:
        conn.close()
    assert row[0] == "chercheur"


def test_deverrouiller_efface_l_auteur(client, derriere_proxy, album, planche, db_path):
    client.patch(f"/api/planches/{planche['id']}/verrou", json={"verrouillee": True},
                 headers={"Remote-User": "chercheur", "Remote-Groups": "bd-admins"})
    client.patch(f"/api/planches/{planche['id']}/verrou", json={"verrouillee": False},
                 headers={"Remote-User": "chercheur", "Remote-Groups": "bd-admins"})
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT verrouillee, verrou_par FROM planches WHERE id = ?",
                           (planche["id"],)).fetchone()
    finally:
        conn.close()
    assert row == (None, None)


# --------------------------------------------------------------------------- #
# Migration v21 → v22
# --------------------------------------------------------------------------- #
def test_migration_v21_vers_v22_ajoute_verrou_par(tmp_path):
    """Chemin ADD : sur un schéma « v21 » (planches SANS `verrou_par`), `_migrate` pose la
    colonne par ALTER, gardé par présence. Une base neuve la tient de SCHEMA_SQL. Schéma
    minimal, comme les autres tests de migration, pour isoler l'étape."""
    import database
    db = tmp_path / "pre22.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row                        # _migrate lit r["name"]
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INTEGER);"
        "PRAGMA user_version = 21;")
    conn.commit()
    database._migrate(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(planches)")}
    assert "verrou_par" in cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    conn.close()
