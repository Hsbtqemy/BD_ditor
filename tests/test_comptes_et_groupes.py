"""AUTH-6 / AUTH-12 — la vue « 👥 Comptes et groupes » : sa composition, et ses signaux.

Le format est un contrat avec l'écran, arrêté le 2026-09-17. Ces tests en tiennent les
règles qui trompent en silence si elles glissent : un champ inconnu vaut `None` et jamais
`False` ; une entrée par ACCÈS, jamais un niveau fusionné ; les signaux qui supposent
l'annuaire ne s'allument pas quand il n'a pas répondu ; « À regarder » est ordonné par le
serveur.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import annuaire  # noqa: E402
import comptes  # noqa: E402
import config  # noqa: E402
import database  # noqa: E402

from conftest import ADMIN  # noqa: E402


@pytest.fixture
def doublure(monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:")


def _sql(requete, *params):
    conn = database.get_connection()
    try:
        cur = conn.execute(requete, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _venu(login, nom=None, derniere="2026-09-14 16:40:00", nature="nominatif"):
    _sql("INSERT INTO utilisateur (login, nom, email, premiere_vue, derniere_vue, nature) "
         "VALUES (?, ?, ?, '2026-09-02 08:11:00', ?, ?)",
         login, nom, f"{login}@base.invalid", derniere, nature)


def _collection(client, nom):
    r = client.post("/api/collections", json={"nom": nom}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _acces(client, cid, genre, principal, niveau="lecture", exporter=False):
    r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": genre, "principal": principal, "niveau": niveau,
                         "exporter": exporter})
    assert r.status_code in (200, 201, 204), r.text


def _vue(client):
    r = client.get("/api/comptes-et-groupes", headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def _par(liste, cle, valeur):
    return next(x for x in liste if x[cle] == valeur)


# --------------------------------------------------------------------------- #
# Qui la voit
# --------------------------------------------------------------------------- #
def test_la_vue_est_reservee_aux_administrateurs(client, derriere_proxy, doublure):
    r = client.get("/api/comptes-et-groupes", headers={"Remote-User": "simple"})
    assert r.status_code == 403
    assert "personnes" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# Les trois états de la lecture
# --------------------------------------------------------------------------- #
def test_sans_annuaire_la_vue_ne_montre_que_ce_que_l_application_sait(
        client, derriere_proxy, monkeypatch):
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "")
    _venu("alice", "Alice Martin")
    vue = _vue(client)
    assert vue["annuaire"]["etat"] == "sans_annuaire"
    assert vue["limite"] == comptes.LIMITES["sans_annuaire"]
    alice = _par(vue["comptes"], "login", "alice")
    # INCONNU s'écrit None, jamais False ni [] : « pas dans l'annuaire » serait un mensonge.
    for champ in ("dans_annuaire", "usage", "groupes", "administrateur"):
        assert alice[champ] is None, champ
    assert alice["venu"] is True and alice["collections_completes"] is False
    assert not [l for l in vue["a_regarder"] if l["signal"] in
                ("groupe_absent", "compte_absent", "proprietaire_absent", "jamais_venu")]


def test_un_annuaire_muet_ne_fait_mourir_aucun_acces(client, derriere_proxy, monkeypatch):
    """(c) — la panne rend 200, avec ce que l'application sait seule ; aucun groupe, aucun
    compte, aucun propriétaire n'est déclaré absent ou mort."""
    monkeypatch.setattr(config, "ANNUAIRE_ADRESSE", "doublure:panne")
    cid = _collection(client, "Étude muette")
    _acces(client, cid, "groupe", "ancien-cours")
    _acces(client, cid, "utilisateur", "eve", niveau="proprietaire")
    vue = _vue(client)
    assert (vue["annuaire"]["etat"], vue["annuaire"]["motif"]) == ("non_verifie", "delai")
    assert vue["limite"] == comptes.LIMITES["non_verifie"]
    groupe = _par(vue["groupes"], "nom", "ancien-cours")
    assert groupe["dans_annuaire"] is None and groupe["membres"] is None
    assert groupe["id"] is None and groupe["signaux"] == []
    eve = _par(vue["comptes"], "login", "eve")
    assert eve["dans_annuaire"] is None and "compte_absent" not in eve["signaux"]
    col = _par(vue["collections"], "id", cid)
    assert col["proprietaires"][0]["vivant"] is None and col["signaux"] == []
    assert vue["a_regarder"] == []


# --------------------------------------------------------------------------- #
# Comptes et groupes, l'annuaire lu
# --------------------------------------------------------------------------- #
def test_les_comptes_reunissent_annuaire_miroir_et_acces(client, derriere_proxy, doublure):
    _venu("admin-bd", "Nom du miroir")
    _venu("parti", "Parti depuis")                       # venu, plus dans l'annuaire
    cid = _collection(client, "Collection Test")
    _acces(client, cid, "utilisateur", "eve")             # seulement par un accès
    vue = _vue(client)
    logins = {c["login"] for c in vue["comptes"]}
    assert {"admin-bd", "arrivant", "parti", "eve", "authelia"} <= logins

    admin = _par(vue["comptes"], "login", "admin-bd")
    assert (admin["nom"], admin["usage"], admin["administrateur"]) == \
        ("Camille Admin", "application", True)          # annuaire d'abord, puis le miroir
    assert admin["venu"] is True and admin["derniere_vue"] == "2026-09-14T16:40:00Z"

    parti = _par(vue["comptes"], "login", "parti")
    assert (parti["dans_annuaire"], parti["groupes"], parti["nom"]) == \
        (False, [], "Parti depuis")
    # Absent de l'annuaire, mais sans accès nominatif : rien de mort à signaler.
    assert parti["signaux"] == []

    arrivant = _par(vue["comptes"], "login", "arrivant")
    assert (arrivant["venu"], arrivant["nature"], arrivant["premiere_vue"]) == (False, None, None)
    assert "jamais_venu" in arrivant["signaux"]
    # Le verdict se calcule pour TOUS les comptes, venus ou non.
    assert (arrivant["actes"], arrivant["acces_explicites"], arrivant["verdict"]) == \
        (0, 0, "rien à orpheliner")
    eve = _par(vue["comptes"], "login", "eve")
    assert (eve["acces_explicites"], eve["verdict"]) == (1, "laisse des accès")


def test_les_comptes_qui_ne_servent_que_l_annuaire_ne_sont_pas_des_arrivants(
        client, derriere_proxy, doublure):
    """Sans cette règle, `admin` d'amorçage resterait « jamais venu » en tête des arrivants
    pour toujours. Un humain à la fois `lldap_admin` et `bd-admins` reste, lui, signalé."""
    vue = _vue(client)
    for login in ("admin", "authelia", "bd-application"):
        c = _par(vue["comptes"], "login", login)
        assert (c["usage"], c["signaux"]) == ("annuaire", []), login
    humain = _par(vue["comptes"], "login", "admin-bd")
    assert humain["usage"] == "application" and "jamais_venu" in humain["signaux"]


def test_les_groupes_portent_id_membres_role_et_derniere_venue(client, derriere_proxy, doublure):
    _venu("etu03", derniere="2026-09-10 10:00:00")
    _venu("etu07", derniere="2026-09-15 09:30:00")
    vue = _vue(client)
    etudiants = _par(vue["groupes"], "nom", "etudiants-bd-2026")
    assert (etudiants["id"], etudiants["nb_comptes"]) == (6, 12)
    assert etudiants["derniere_venue"] == "2026-09-15T09:30:00Z"
    assert etudiants["role_annuaire"] is False and etudiants["administrateur"] is False
    assert _par(vue["groupes"], "nom", "lldap_admin")["role_annuaire"] is True
    assert _par(vue["groupes"], "nom", "bd-admins")["administrateur"] is True
    vide = _par(vue["groupes"], "nom", "cours-vide")
    assert (vide["nb_comptes"], vide["membres"], vide["derniere_venue"]) == (0, [], None)


def test_une_entree_par_acces_jamais_un_niveau_fusionne(client, derriere_proxy, doublure):
    """`proprio` entre dans « Collection Test » à son nom ET par `annotateurs` : deux lignes,
    le compte d'abord. Fusionner les deux cacherait lequel retirer."""
    b = _collection(client, "B après A")
    a = _collection(client, "A avant B")
    _acces(client, b, "utilisateur", "proprio", niveau="proprietaire")
    _acces(client, b, "groupe", "annotateurs", niveau="lecture", exporter=True)
    _acces(client, a, "groupe", "annotateurs", niveau="ecriture")
    proprio = _par(_vue(client)["comptes"], "login", "proprio")
    assert [(e["nom"], e["par"], e["groupe"], e["niveau"], e["exporter"])
            for e in proprio["collections"]] == [
        ("A avant B", "groupe", "annotateurs", "ecriture", False),
        ("B après A", "compte", None, "proprietaire", True),   # un propriétaire exporte d'office
        ("B après A", "groupe", "annotateurs", "lecture", True),
    ]


# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #
def test_les_collections_ne_contredisent_pas_la_liste_des_collections(
        client, derriere_proxy, doublure):
    cid = _collection(client, "Diffusée")
    client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "public"}, headers=ADMIN)
    liste = {c["id"]: c for c in client.get("/api/collections", headers=ADMIN).json()}
    for col in _vue(client)["collections"]:
        assert (col["nb_albums"], col["statut_diffusion"]) == \
            (liste[col["id"]]["nb_albums"], liste[col["id"]]["statut_diffusion"])


def test_qui_entre_se_lit_une_ligne_par_acces_compte_d_abord(client, derriere_proxy, doublure):
    cid = _collection(client, "Qui entre")
    _acces(client, cid, "groupe", "annotateurs")
    _acces(client, cid, "utilisateur", "zoe", niveau="ecriture")
    _acces(client, cid, "utilisateur", "proprio", niveau="proprietaire")
    col = _par(_vue(client)["collections"], "id", cid)
    assert [(a["par"], a["login"], a["groupe"], a["niveau"], a["exporter"]) for a in col["acces"]] == [
        ("compte", "proprio", None, "proprietaire", True),
        ("compte", "zoe", None, "ecriture", False),
        ("groupe", None, "annotateurs", "lecture", False),
    ]
    assert col["nb_acces"] == 3


def test_la_derniere_modification_compte_la_description_et_les_acces(client, derriere_proxy,
                                                                      doublure):
    cid = _collection(client, "Datée")
    _sql("UPDATE evenement SET date = '2026-01-01 00:00:00' WHERE cible_id = ?", cid)
    _sql("INSERT INTO evenement (type, agent, cible_table, cible_id, date) "
         "VALUES ('lien', 'x', 'collection_acces', ?, '2026-03-01 00:00:00')", cid)
    # Un événement d'une autre table, plus récent, ne compte pas — ranger un album non plus.
    _sql("INSERT INTO evenement (type, agent, cible_table, cible_id, date) "
         "VALUES ('modification', 'x', 'albums', ?, '2026-05-01 00:00:00')", cid)
    assert _par(_vue(client)["collections"], "id", cid)["derniere_modification"] == \
        "2026-03-01T00:00:00Z"


# --------------------------------------------------------------------------- #
# Les signaux
# --------------------------------------------------------------------------- #
def test_les_acces_morts_sont_signales(client, derriere_proxy, doublure):
    cid = _collection(client, "Étude B")
    _acces(client, cid, "groupe", "ancien-cours")
    _acces(client, cid, "utilisateur", "eve")
    vue = _vue(client)
    assert _par(vue["groupes"], "nom", "ancien-cours")["signaux"] == ["groupe_absent"]
    assert "compte_absent" in _par(vue["comptes"], "login", "eve")["signaux"]
    assert {"signal": "groupe_absent", "groupe": "ancien-cours", "collection": cid} in vue["a_regarder"]
    assert {"signal": "compte_absent", "login": "eve", "collection": cid} in vue["a_regarder"]
    # Un groupe de l'annuaire SANS accès n'est pas un accès mort, et un groupe sans membre non plus.
    assert _par(vue["groupes"], "nom", "cours-vide")["signaux"] == []


def test_un_proprietaire_qui_n_existe_plus_ou_un_groupe_vide_ne_tient_pas_une_collection(
        client, derriere_proxy, doublure):
    orpheline = _collection(client, "Orpheline")
    _acces(client, orpheline, "utilisateur", "dora", niveau="proprietaire")
    vide = _collection(client, "Tenue par un groupe vide")
    _acces(client, vide, "groupe", "cours-vide", niveau="proprietaire")
    tenue = _collection(client, "Tenue")
    _acces(client, tenue, "utilisateur", "dora", niveau="proprietaire")
    _acces(client, tenue, "groupe", "annotateurs", niveau="proprietaire")
    vue = _vue(client)
    assert _par(vue["collections"], "id", orpheline)["signaux"] == ["proprietaire_absent"]
    assert _par(vue["collections"], "id", vide)["signaux"] == ["proprietaire_absent"]
    tenue_vue = _par(vue["collections"], "id", tenue)
    assert tenue_vue["signaux"] == []
    assert [p["vivant"] for p in tenue_vue["proprietaires"]] == [False, True]


def test_sans_proprietaire_sauf_la_collection_de_repli(client, derriere_proxy, doublure):
    sans = _collection(client, "Sans personne")
    client.post("/api/albums", json={"titre": "Range dans le repli"}, headers=ADMIN)
    vue = _vue(client)
    assert _par(vue["collections"], "id", sans)["signaux"] == ["sans_proprietaire"]
    repli = _par(vue["collections"], "nom", database.NOM_COLLECTION_DEFAUT)
    assert (repli["repli"], repli["signaux"]) == (True, [])


def test_une_identite_changee_se_signale_trente_jours(client, derriere_proxy, doublure):
    _venu("lectrice")
    _sql("INSERT INTO evenement (type, agent, cible_table, cible_id, avant, apres, date) "
         "VALUES ('modification', 'lectrice', 'utilisateur', NULL, "
         "'{\"login\": \"lectrice\", \"nom\": \"Ancien nom\"}', '{\"nom\": \"Léa\"}', "
         "'2026-09-10 12:00:00')")
    conn = database.get_connection()
    try:
        lecture = annuaire.lire()
        dans = comptes.composer(conn, lecture,
                                maintenant=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
        apres = comptes.composer(conn, lecture,
                                 maintenant=datetime(2026, 10, 10, 12, 1, tzinfo=timezone.utc))
    finally:
        conn.close()
    lea = _par(dans["comptes"], "login", "lectrice")
    assert (lea["reprises"], lea["derniere_reprise"]) == (1, "2026-09-10T12:00:00Z")
    assert "identite_changee" in lea["signaux"]
    assert {"signal": "identite_changee", "login": "lectrice"} in dans["a_regarder"]
    # Au-delà de la fenêtre, la trace reste au journal, le signal s'éteint.
    lea_apres = _par(apres["comptes"], "login", "lectrice")
    assert lea_apres["reprises"] == 1 and "identite_changee" not in lea_apres["signaux"]
    assert comptes.FENETRE_REPRISE_JOURS == 30


def test_a_regarder_est_ordonne_par_le_serveur(client, derriere_proxy, doublure):
    """Les accès morts d'abord, les arrivants à la fin ; dans un code, par nom."""
    cid = _collection(client, "Z dernière")
    _acces(client, cid, "utilisateur", "yann")
    _acces(client, cid, "groupe", "zeta")
    _acces(client, cid, "groupe", "alpha")
    codes = [l["signal"] for l in _vue(client)["a_regarder"]]
    rangs = [comptes.ORDRE_SIGNAUX.index(c) for c in codes]
    assert rangs == sorted(rangs), codes
    groupes = [l["groupe"] for l in _vue(client)["a_regarder"] if l["signal"] == "groupe_absent"]
    assert groupes == ["alpha", "zeta"]
    assert codes[-1] == "jamais_venu"
