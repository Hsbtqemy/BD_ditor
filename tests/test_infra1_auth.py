"""INFRA-1 / AUTH-1 — identité de l'utilisateur connecté.

Derrière le proxy d'authentification (Authelia via Caddy), l'app reçoit `Remote-User`,
`Remote-Groups`, `Remote-Name` et `Remote-Email`. /api/moi les relaie et enregistre la
personne dans la table `utilisateur` (miroir d'affichage — aucun secret stocké).

AUTH-1 pose une GARDE : ces en-têtes ne sont crus que si `BD_AUTH_PROXY` déclare qu'on
est derrière le proxy. Sans le drapeau, ils sont ignorés — sinon n'importe quel client
atteignant l'app en direct pourrait se déclarer qui il veut, ce qui deviendra une
escalade de privilège dès que l'autorisation en dépendra (AUTH-2, AUTH-3).
"""
import json
import sqlite3

import pytest

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
    # L'égalité EXACTE est le sujet du test, et on la garde en ajoutant les clés plutôt
    # qu'en la relâchant : ce qu'elle vérifie, c'est qu'en mono-poste `/api/moi` ne rend
    # RIEN de plus que ce qui est écrit ici. Un sous-ensemble laisserait entrer sans bruit
    # le prochain champ d'identité — c'est exactement ce que ce test existe pour empêcher.
    assert d == {"utilisateur": None, "nom": None, "groupes": [],
                 # AUTH-2 : la portée est totale en mono-poste, et les compteurs sont None
                 # — « pas de restriction », qui ne se confond pas avec « zéro collection ».
                 "acces": {"total": True, "admin": True,
                           "collections": None, "ecriture": None,
                           # AUTH-4 : les deux champs de référent sont VIDES ici, et c'est
                           # la bonne réponse. Sans proxy aucun groupe n'est lu, donc
                           # `bd-admins` ne désigne personne ; et aucun référent n'est
                           # déclaré à l'environnement. Nommer l'un ou l'autre ferait
                           # parler l'écran d'un tiers à qui écrire, sur une machine où
                           # l'on est seul.
                           "groupes_admin": [], "referent": None},
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
# La reprise d'un login (AUTH-7)
#
# `utilisateur` est un miroir : l'UPSERT écrase l'ancien nom sans rien laisser. Un login
# se réutilisant (tranché le 2026-09-06 : il ne portera pas l'année), `premiere_vue` date
# alors un arrivant de l'arrivée de son prédécesseur — dans l'instrument même dont la
# règle de suppression de comptes dépend. La trace ne se reconstruit pas après coup.
# --------------------------------------------------------------------------- #
def _traces_utilisateur(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return [(r[0], r[1], json.loads(r[2]), json.loads(r[3])) for r in conn.execute(
            "SELECT type, agent, avant, apres FROM evenement "
            "WHERE cible_table = 'utilisateur' ORDER BY id")]
    finally:
        conn.close()


def test_reprise_d_un_login_laisse_une_trace_datee(client, derriere_proxy, db_path):
    """Le nom change sous un login connu → un événement A3 qui porte les DEUX valeurs.

    L'ancienne valeur n'existe plus nulle part après l'UPSERT ; c'est ce qui rend la
    capture urgente, alors que la vue qui la lira n'est pas écrite."""
    client.get("/api/moi", headers={"Remote-User": "stagiaire1",
                                    "Remote-Name": "Alice Martin"})
    client.get("/api/moi", headers={"Remote-User": "stagiaire1",
                                    "Remote-Name": "Bob Durand"})
    traces = _traces_utilisateur(db_path)
    assert len(traces) == 1
    type_, agent, avant, apres = traces[0]
    assert (type_, agent) == ("modification", "stagiaire1")
    assert avant == {"login": "stagiaire1", "nom": "Alice Martin"}
    assert apres == {"login": "stagiaire1", "nom": "Bob Durand"}


def test_la_trace_porte_le_login_car_cible_id_est_nul(client, derriere_proxy, db_path):
    """`cible_id` est un INTEGER et un login est du TEXTE : sans le login dans la charge,
    l'événement ne désignerait aucun compte."""
    client.get("/api/moi", headers={"Remote-User": "stagiaire1", "Remote-Name": "Alice"})
    client.get("/api/moi", headers={"Remote-User": "stagiaire1", "Remote-Name": "Bob"})
    conn = sqlite3.connect(db_path)
    try:
        cid = conn.execute("SELECT cible_id FROM evenement "
                           "WHERE cible_table = 'utilisateur'").fetchone()[0]
    finally:
        conn.close()
    assert cid is None
    assert all(c["login"] == "stagiaire1" for _, _, a, b in _traces_utilisateur(db_path)
               for c in (a, b))


def test_premiere_visite_ne_laisse_aucune_trace(client, derriere_proxy, db_path):
    """Une création n'est pas une reprise : sans valeur antérieure, il n'y a rien à dire."""
    client.get("/api/moi", headers={"Remote-User": "chercheur", "Remote-Name": "Jeanne"})
    assert _traces_utilisateur(db_path) == []


def test_un_nom_inchange_ne_laisse_aucune_trace(client, derriere_proxy, db_path):
    """Le chemin lent se reparcourt (cache vide, TTL) sans rien journaliser."""
    for _ in range(3):
        main._vus.clear()
        client.get("/api/moi", headers={"Remote-User": "chercheur", "Remote-Name": "Jeanne"})
    assert _traces_utilisateur(db_path) == []


def test_une_valeur_qui_apparait_n_est_pas_une_reprise(client, derriere_proxy, db_path):
    """Un proxy qui SE MET à envoyer `Remote-Name` enrichit le miroir ; personne n'a
    changé. Compter ce cas ferait battre la trace à chaque variation d'en-tête."""
    client.get("/api/moi", headers={"Remote-User": "chercheur"})
    client.get("/api/moi", headers={"Remote-User": "chercheur", "Remote-Name": "Jeanne"})
    assert _traces_utilisateur(db_path) == []


def test_une_valeur_qui_disparait_n_est_pas_une_reprise(client, derriere_proxy, db_path):
    """Et un proxy qui CESSE de l'envoyer est une panne d'en-tête, pas une succession."""
    client.get("/api/moi", headers={"Remote-User": "chercheur", "Remote-Name": "Jeanne"})
    client.get("/api/moi", headers={"Remote-User": "chercheur"})
    assert _traces_utilisateur(db_path) == []


def test_la_trace_n_est_pas_annulable(client, derriere_proxy, db_path):
    """La reprise est une OBSERVATION, pas un acte : `Ctrl+Z` ne doit pas la proposer.

    Elle est hors de la liste blanche de tables de l'undo — la même protection que
    `sharedocs`, et elle vaut d'être éprouvée plutôt que déduite."""
    client.get("/api/moi", headers={"Remote-User": "stagiaire1", "Remote-Name": "Alice"})
    client.get("/api/moi", headers={"Remote-User": "stagiaire1", "Remote-Name": "Bob"})
    assert len(_traces_utilisateur(db_path)) == 1
    r = client.get("/api/undo/prochain", headers={"Remote-User": "stagiaire1"})
    assert r.status_code == 200 and r.json() is None


@pytest.mark.parametrize("ancien, nouveau, attendu", [
    (("Alice", "a@x.fr"), ("Bob", "a@x.fr"), ({"nom": "Alice"}, {"nom": "Bob"})),
    (("Alice", "a@x.fr"), ("Alice", "b@x.fr"), ({"email": "a@x.fr"}, {"email": "b@x.fr"})),
    (("Alice", "a@x.fr"), ("Bob", "b@x.fr"),
     ({"nom": "Alice", "email": "a@x.fr"}, {"nom": "Bob", "email": "b@x.fr"})),
    (("Alice", "a@x.fr"), ("Alice", "a@x.fr"), None),   # rien n'a bougé
    ((None, None), ("Alice", "a@x.fr"), None),          # apparition
    (("Alice", "a@x.fr"), (None, None), None),          # disparition
    (("Alice", None), ("Bob", "b@x.fr"), ({"nom": "Alice"}, {"nom": "Bob"})),
])
def test_identite_reprise_table_de_verite(ancien, nouveau, attendu):
    """La règle sans la base : seul un renseigné→renseigné DIFFÉRENT compte."""
    assert main._identite_reprise(*ancien, *nouveau) == attendu


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
