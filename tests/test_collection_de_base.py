"""COL-3, tranche 3, D10 — un projet naît avec sa collection de BASE (Hugo, 2026-10-17).

« Le fonds commence avec le projet » : ses documents y entrent avant qu'on ait pensé ses
collections. Ce que ces tests tiennent, et c'est un changement de PRINCIPE — la première fois
qu'être d'un projet ouvre une collection, celle-là seule, et seulement si on l'a choisi :

- tout projet naît avec UNE collection de base, désignée par un drapeau (`collection.base`) :
  elle se renomme, ne se supprime pas, ne change pas de projet ; le projet de repli a la
  sienne, la « Collection par défaut » ;
- ses RESPONSABLES en sont propriétaires, ses MEMBRES y entrent au niveau choisi pour le
  projet (`collection.acces_membres` : écriture, lecture, ou NULL — protégée) ; les deux sont
  DÉRIVÉS de `projet_acces` dans `autorisation.Portee`, jamais recopiés dans
  `collection_acces` : qui sort du projet sort de la collection, un responsable rétrogradé
  n'en est plus propriétaire, un groupe membre y fait entrer les siens ;
- la position se pose à la création (écriture par défaut, comme l'écran la présélectionnera),
  se règle par qui GÈRE le projet, et s'écrit au journal comme un accès ;
- rien ne s'ouvre au déploiement : la migration désigne les bases de l'existant PROTÉGÉES.
"""
import sqlite3
from pathlib import Path

import pytest

import annuaire
import autorisation
import comptes
import database
from conftest import du_projet
from conftest import ADMIN
from test_projets import _acces, _collection, _membre, _outil, _repli, _sql

RITA = {"Remote-User": "rita"}                  # responsable
MARC = {"Remote-User": "marc"}                  # membre
EVE = {"Remote-User": "eve", "Remote-Groups": "etudiants"}   # membre par son groupe
ZOE = {"Remote-User": "zoe"}                    # d'aucun projet


def _projet(client, nom="Étude B", **plus):
    r = client.post("/api/projets", json={"nom": nom, **plus}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _base(db_path, projet_id):
    lignes = _sql(db_path, "SELECT * FROM collection WHERE base = 1 AND projet_id = ?",
                  (projet_id,))
    assert len(lignes) == 1, lignes
    return lignes[0]


def _vues(client, qui):
    return {c["id"]: c for c in client.get("/api/collections", headers=qui).json()}


@pytest.fixture
def projet(client, derriere_proxy, db_path):
    """« Étude B », sa base, une seconde collection « Autre » où personne n'entre ; rita
    responsable, marc membre, le groupe `etudiants` membre."""
    pid = _projet(client)
    autre = _collection(client, "Autre", projet_id=pid)
    for principal, role, genre in (("rita", "responsable", "utilisateur"),
                                   ("marc", "membre", "utilisateur"),
                                   ("etudiants", "membre", "groupe")):
        assert _membre(client, pid, principal, role, genre).status_code == 200
    return {"id": pid, "base": _base(db_path, pid)["id"], "autre": autre}


def _position(client, projet_id, niveau, qui=ADMIN):
    return client.put(f"/api/projets/{projet_id}/acces-membres", headers=qui,
                      json={"acces_membres": niveau})


# --------------------------------------------------------------------------- #
# La naissance
# --------------------------------------------------------------------------- #
def test_un_projet_nait_avec_sa_collection_de_base(client, derriere_proxy, db_path):
    """Une collection, du nom du projet, drapeau posé, ouverte en écriture à ses membres
    par défaut — et AUCUNE ligne d'accès : ce qui l'ouvre est dérivé, pas recopié."""
    pid = _projet(client)
    base = _base(db_path, pid)
    assert (base["nom"], base["acces_membres"]) == ("Étude B", "ecriture")
    assert _sql(db_path, "SELECT 1 FROM collection_acces WHERE collection_id = ?",
                (base["id"],)) == []
    vue = _vues(client, ADMIN)[base["id"]]
    assert (vue["base"], vue["acces_membres"], vue["projet_id"]) == (True, "ecriture", pid)
    acte = _sql(db_path, "SELECT type, agent, apres FROM evenement "
                         "WHERE cible_table = 'collection' AND cible_id = ?", (base["id"],))
    assert len(acte) == 1 and acte[0]["type"] == "creation" and '"base": true' in acte[0]["apres"]


@pytest.mark.parametrize("niveau", ["ecriture", "lecture", None])
def test_la_position_se_choisit_a_la_creation(client, derriere_proxy, db_path, niveau):
    pid = _projet(client, acces_membres=niveau)
    assert _base(db_path, pid)["acces_membres"] == niveau


@pytest.mark.parametrize("niveau", ["proprietaire", "tout", ""])
def test_une_position_inconnue_est_refusee(client, derriere_proxy, db_path, niveau):
    r = client.post("/api/projets", json={"nom": "Refusé", "acces_membres": niveau},
                    headers=ADMIN)
    assert r.status_code == 422 and "acces_membres" in r.json()["detail"]
    assert _sql(db_path, "SELECT 1 FROM projet WHERE nom = 'Refusé'") == []


def test_un_nom_de_projet_reserve_ne_nomme_pas_la_base_comme_le_repli(client, derriere_proxy,
                                                                     db_path):
    """« Collection par défaut » tient dans 21 caractères : un projet peut s'appeler ainsi.
    Sa base ne prend pas ce nom, réservé à la collection de repli."""
    pid = _projet(client, nom=database.NOM_COLLECTION_DEFAUT)
    assert not database.nom_reserve(_base(db_path, pid)["nom"])


# --------------------------------------------------------------------------- #
# La dérivation — trois positions, et ce qu'elle n'ouvre pas
# --------------------------------------------------------------------------- #
def test_ouverte_les_membres_y_ecrivent(client, projet):
    base = projet["base"]
    for qui in (MARC, EVE):
        vue = _vues(client, qui)
        assert list(vue) == [base], "la base, et elle SEULE"
        assert (vue[base]["mon_niveau"], vue[base]["ecrivable"],
                vue[base]["administrable"]) == ("ecriture", True, False)
    r = client.post("/api/albums", json={"titre": "Pris", "collection_id": base},
                    headers=MARC)
    assert r.status_code == 201, r.text


def test_en_lecture_les_membres_lisent_sans_ecrire(client, projet):
    assert _position(client, projet["id"], "lecture").status_code == 200
    base = projet["base"]
    vue = _vues(client, MARC)
    assert list(vue) == [base]
    assert (vue[base]["mon_niveau"], vue[base]["ecrivable"]) == ("lecture", False)
    assert client.post("/api/albums", json={"titre": "Refusé", "collection_id": base},
                       headers=MARC).status_code == 404


def test_protegee_les_membres_n_y_lisent_rien(client, projet):
    assert _position(client, projet["id"], None).status_code == 200
    assert _vues(client, MARC) == {} and _vues(client, EVE) == {}
    assert client.get(f"/api/collections/{projet['base']}/acces",
                      headers=MARC).status_code == 404


@pytest.mark.parametrize("niveau", ["ecriture", "lecture", None])
def test_les_responsables_en_sont_proprietaires(client, projet, niveau):
    """Quelle que soit la position : « protégée » veut dire le propriétaire seul."""
    assert _position(client, projet["id"], niveau).status_code == 200
    vue = _vues(client, RITA)[projet["base"]]
    assert (vue["mon_niveau"], vue["administrable"], vue["exportable"]) \
        == ("proprietaire", True, True)
    assert client.get(f"/api/collections/{projet['base']}/acces",
                      headers=RITA).status_code == 200


def test_la_base_n_ouvre_qu_elle_meme(client, projet):
    """Un MEMBRE d'un projet à base ouverte ne lit AUCUNE autre collection du projet : la
    seconde collection garde son « Qui entre ». Le RESPONSABLE la lit depuis la tranche 3c
    (F1, RENVERSÉ pour lui), en lecture seule : il n'en règle pas l'accès (403)."""
    for qui in (MARC, EVE):
        assert projet["autre"] not in _vues(client, qui)
        assert client.get(f"/api/collections/{projet['autre']}/acces",
                          headers=qui).status_code == 404
    assert _vues(client, RITA)[projet["autre"]]["mon_niveau"] == "lecture"
    assert client.get(f"/api/collections/{projet['autre']}/acces",
                      headers=RITA).status_code == 403


def test_qui_n_est_pas_du_projet_n_y_lit_rien(client, projet):
    assert _vues(client, ZOE) == {}


def test_qui_sort_du_projet_sort_de_la_base(client, projet):
    assert projet["base"] in _vues(client, MARC)
    assert client.delete(f"/api/projets/{projet['id']}/membres/utilisateur/marc",
                         headers=ADMIN).status_code == 204
    assert _vues(client, MARC) == {}


def test_un_responsable_retrograde_n_en_est_plus_proprietaire(client, projet):
    assert _membre(client, projet["id"], "marc", "responsable").status_code == 200
    assert _membre(client, projet["id"], "rita", "membre").status_code == 200
    vue = _vues(client, RITA)[projet["base"]]
    assert (vue["mon_niveau"], vue["administrable"]) == ("ecriture", False)
    assert _vues(client, MARC)[projet["base"]]["mon_niveau"] == "proprietaire"


def test_un_groupe_qui_sort_du_projet_n_y_fait_plus_entrer(client, projet):
    assert projet["base"] in _vues(client, EVE)
    assert client.delete(f"/api/projets/{projet['id']}/membres/groupe/etudiants",
                         headers=ADMIN).status_code == 204
    assert _vues(client, EVE) == {}


def test_un_acces_explicite_s_ajoute_a_la_derivation(client, projet):
    """« Qui entre » reste ouvert sur la base — à qui est du projet (tranche 3c, F2) : un
    compte d'aucun projet y est refusé (409) ; fait membre, il y entre par la position du
    projet ; un accès posé s'y ajoute, et la dérivation ne lui retire rien quand la base
    se protège."""
    r = client.put(f"/api/collections/{projet['base']}/acces", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": "zoe", "niveau": "lecture"})
    assert r.status_code == 409, r.text
    assert _membre(client, projet["id"], "zoe", "membre").status_code == 200
    assert _vues(client, ZOE)[projet["base"]]["mon_niveau"] == "ecriture"
    _acces(client, projet["base"], "zoe", "lecture")
    assert _position(client, projet["id"], None).status_code == 200
    assert list(_vues(client, ZOE)) == [projet["base"]]
    assert _vues(client, ZOE)[projet["base"]]["mon_niveau"] == "lecture"


def test_la_portee_derive_sans_recopier():
    """Table de vérité, à même la `Portee` : la dérivation est faite dans `__init__`, avec
    les niveaux, et une réduction à l'export ne la refait pas."""
    bases = ((1, 10, "ecriture"), (2, 20, "lecture"), (3, 30, None), (4, 40, "ecriture"),
             (5, 50, "proprietaire"))
    p = autorisation.Portee(projets=frozenset({1, 2, 3, 5}), projets_geres=frozenset({3}),
                            bases=bases, utilisateur="u")
    assert (p.peut_ecrire(10), p.peut_lire(20), p.peut_ecrire(20)) == (True, True, False)
    assert p.peut_administrer(30) and not p.peut_lire(40)
    # Un niveau inconnu (base retouchée à la main) se dégrade en lecture, jamais au-delà.
    assert p.peut_lire(50) and not p.peut_ecrire(50)
    export = p.pour_export()
    assert export.lecture == frozenset({30}) and not export.peut_lire(10)


# --------------------------------------------------------------------------- #
# Régler la position
# --------------------------------------------------------------------------- #
def test_qui_gere_le_projet_regle_la_position(client, projet, db_path):
    r = _position(client, projet["id"], "lecture", qui=RITA)
    assert r.status_code == 200, r.text
    assert _base(db_path, projet["id"])["acces_membres"] == "lecture"
    actes = _sql(db_path, "SELECT type, agent, avant, apres FROM evenement "
                          "WHERE cible_table = 'collection_acces' AND cible_id = ?",
                 (projet["base"],))
    assert [(a["type"], a["agent"]) for a in actes] == [("lien", "rita")]
    assert '"niveau": "ecriture"' in actes[0]["avant"]
    assert '"niveau": "lecture"' in actes[0]["apres"]
    # Rien ne change : rien ne s'écrit.
    assert _position(client, projet["id"], "lecture", qui=RITA).status_code == 200
    assert len(_sql(db_path, "SELECT 1 FROM evenement WHERE cible_table = "
                             "'collection_acces' AND cible_id = ?", (projet["base"],))) == 1


def test_qui_ne_gere_pas_ne_regle_pas(client, projet):
    assert _position(client, projet["id"], None, qui=MARC).status_code == 403
    assert _position(client, projet["id"], None, qui=ZOE).status_code == 404
    assert _position(client, projet["id"], "proprietaire").status_code == 422


def test_resserrer_n_efface_aucun_travail(client, projet):
    aid = client.post("/api/albums", json={"titre": "Le travail de Marc",
                                           "collection_id": projet["base"]},
                      headers=MARC).json()["id"]
    assert _position(client, projet["id"], None).status_code == 200
    assert aid in {a["id"] for a in client.get("/api/albums", headers=RITA).json()}
    assert aid not in {a["id"] for a in client.get("/api/albums", headers=MARC).json()}


# --------------------------------------------------------------------------- #
# Les refus qui se nomment
# --------------------------------------------------------------------------- #
def test_la_base_ne_se_supprime_pas(client, projet, db_path):
    for qui in (RITA, ADMIN):
        r = client.delete(f"/api/collections/{projet['base']}", headers=qui)
        assert r.status_code == 409 and "base" in r.json()["detail"], r.text
    assert _base(db_path, projet["id"])["id"] == projet["base"]


def test_la_base_se_renomme_et_reste_la_base(client, projet, db_path):
    r = client.patch(f"/api/collections/{projet['base']}", json={"nom": "Corpus B"},
                     headers=RITA)
    assert r.status_code == 200 and r.json()["base"] is True
    assert _base(db_path, projet["id"])["nom"] == "Corpus B"


def test_un_projet_supprime_emporte_sa_base_vide(client, derriere_proxy, db_path):
    pid = _projet(client, nom="Éphémère")
    base = _base(db_path, pid)["id"]
    assert client.delete(f"/api/projets/{pid}", headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT 1 FROM collection WHERE id = ?", (base,)) == []
    assert _sql(db_path, "SELECT type FROM evenement WHERE cible_table = 'collection' "
                         "AND cible_id = ? ORDER BY id", (base,)) \
        == [{"type": "creation"}, {"type": "suppression"}]


def test_une_base_qui_porte_un_album_retient_son_projet(client, derriere_proxy, db_path):
    pid = _projet(client, nom="Habité")
    base = _base(db_path, pid)["id"]
    assert client.post("/api/albums", json={"titre": "A", "collection_id": base},
                       headers=ADMIN).status_code == 201
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    # Le refus qui DIT la base — sans lui, un autre 409 tombait, dont la phrase parlait
    # d'une « base retouchée » et d'un album rangé chez un autre projet (mutant B10).
    assert r.status_code == 409 and "collection de base porte" in r.json()["detail"], r.text
    assert _base(db_path, pid)["id"] == base


def test_une_autre_collection_retient_toujours_son_projet(client, projet):
    r = client.delete(f"/api/projets/{projet['id']}", headers=ADMIN)
    assert r.status_code == 409 and "1 collection" in r.json()["detail"], r.text


def test_l_outil_ne_supprime_pas_la_base(client, projet, db_path):
    code, _, err = _outil(db_path, "gerer_collections.py", "supprimer", str(projet["base"]))
    assert code != 0 and "base" in err
    assert _base(db_path, projet["id"])["id"] == projet["base"]


# --------------------------------------------------------------------------- #
# Le projet de repli : une base NEUVE, comme tout projet (Hugo, 2026-10-17)
# --------------------------------------------------------------------------- #
def test_le_projet_de_repli_nait_avec_une_base_neuve_et_protegee(client, derriere_proxy,
                                                                  db_path):
    """Sur une base neuve, le projet de repli naît avec sa base : de son nom, vide, PROTÉGÉE
    — ses membres, tous ceux qui tenaient un accès à la migration v29, n'y entrent pas sans
    qu'on l'ait décidé. La « Collection par défaut », qui naît d'un album créé sans
    collection, n'en est PAS une : elle reste la collection de repli, désignée par son nom
    réservé, et renommée, un nouveau seau renaît sous ce nom, comme avant la v31."""
    repli = _repli(db_path)
    base = _base(db_path, repli)
    assert (base["nom"], base["acces_membres"]) == (database.NOM_PROJET_DEFAUT, None)
    assert _sql(db_path, "SELECT 1 FROM collection_album WHERE collection_id = ?",
                (base["id"],)) == []
    assert _membre(client, repli, "marc").status_code == 200
    assert _vues(client, MARC) == {}
    assert client.post("/api/albums", json={"titre": "Sans collection"},
                       headers=ADMIN).status_code == 201
    defaut = _sql(db_path, "SELECT id, base FROM collection WHERE nom = ?",
                  (database.NOM_COLLECTION_DEFAUT,))
    assert [d["base"] for d in defaut] == [0]
    assert _base(db_path, repli)["id"] == base["id"]
    assert client.patch(f"/api/collections/{defaut[0]['id']}", json={"nom": "Le seau"},
                        headers=ADMIN).status_code == 200
    aid = client.post("/api/albums", json={"titre": "Encore"}, headers=ADMIN).json()["id"]
    nouveau = _sql(db_path, "SELECT id FROM collection WHERE nom = ?",
                   (database.NOM_COLLECTION_DEFAUT,))[0]["id"]
    assert nouveau not in (defaut[0]["id"], base["id"])
    assert _sql(db_path, "SELECT collection_id FROM collection_album WHERE album_id = ?",
                (aid,)) == [{"collection_id": nouveau}]


def test_un_projet_de_repli_qui_renait_renait_avec_sa_base(client, derriere_proxy, db_path):
    """Retiré à la main, le projet de repli renaît au premier besoin
    (`database.projet_par_defaut`) — et, comme à la naissance de l'instance, avec sa base
    neuve et protégée : la migration n'est plus là pour la lui donner."""
    ancien = _repli(db_path)
    _sql(db_path, "DELETE FROM collection WHERE projet_id = ?", (ancien,))
    _sql(db_path, "DELETE FROM projet WHERE id = ?", (ancien,))
    assert client.post("/api/collections", json={"nom": "Fait renaître le repli"},
                       headers=ADMIN).status_code == 201
    repli = _repli(db_path)
    assert repli != ancien
    assert (_base(db_path, repli)["nom"], _base(db_path, repli)["acces_membres"])         == (database.NOM_PROJET_DEFAUT, None)


def test_la_position_du_repli_se_regle_sans_faire_naitre_la_collection_de_repli(
        client, derriere_proxy, db_path):
    repli = _repli(db_path)
    assert _position(client, repli, "lecture").status_code == 200
    assert _base(db_path, repli)["acces_membres"] == "lecture"
    assert _sql(db_path, "SELECT 1 FROM collection WHERE nom = ?",
                (database.NOM_COLLECTION_DEFAUT,)) == []


# --------------------------------------------------------------------------- #
# Ce que voit l'Administration
# --------------------------------------------------------------------------- #
def test_une_base_n_est_jamais_dite_sans_proprietaire(client, projet, db_path):
    """Ses propriétaires sont DÉRIVÉS des responsables du projet, sans ligne d'accès ; un
    projet sans responsable se dit dans la liste des projets. Le signal ne la vise pas — ni
    tenue par un responsable, ni dans un projet qui n'en a pas —, et vise toujours une
    collection ordinaire sans propriétaire."""
    vide = client.post("/api/projets", json={"nom": "Sans personne"}, headers=ADMIN).json()
    conn = database.get_connection()
    try:
        vue = {c["id"]: c for c in comptes.composer(conn, annuaire.lire())["collections"]}
    finally:
        conn.close()
    base_vide = _base(db_path, vide["id"])["id"]
    assert "sans_proprietaire" not in vue[projet["base"]]["signaux"]
    assert "sans_proprietaire" not in vue[base_vide]["signaux"]
    assert "sans_proprietaire" in vue[projet["autre"]]["signaux"]


# --------------------------------------------------------------------------- #
# La migration : rien ne s'ouvre au déploiement
# --------------------------------------------------------------------------- #
BASE_V30 = Path(__file__).resolve().parent / "bases" / "v30-5e7f56b.sql"


class _Requete:
    def __init__(self, login, groupes=""):
        self.headers = {"Remote-User": login, "Remote-Groups": groupes}


@pytest.fixture
def vraie_v30(tmp_path, monkeypatch):
    from pipeline import ingest
    db = tmp_path / "vraie.sqlite"
    c = sqlite3.connect(db)
    c.executescript(BASE_V30.read_text(encoding="utf-8"))
    c.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(ingest, "CORPUS_DIR", tmp_path / "corpus")
    monkeypatch.setattr(ingest, "DERIVATIVES_DIR", tmp_path / "derivatives")
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    return db


# Les identités du décor v30 : les responsables du projet de repli (un compte, un groupe),
# la responsable d'« Étude B », un membre des deux projets, une membre par son groupe, et
# l'administrateur sans son groupe.
QUI = (("lea", ""), ("sam", ""), ("eve", "etudiants"), ("hugo", ""), ("rita", ""),
       ("ugo", "chefs"))
RESPONSABLES = {"lea": "Étude B", "rita": database.NOM_PROJET_DEFAUT,
                "ugo": database.NOM_PROJET_DEFAUT}


def test_la_migration_designe_les_bases_protegees(vraie_v30):
    """Chaque projet existant reçoit une base NEUVE, vide, PROTÉGÉE — le projet de repli
    compris : la « Collection par défaut », habitée, n'en devient pas une (Hugo,
    2026-10-17)."""
    defaut = _sql(vraie_v30, "SELECT id FROM collection WHERE nom = ?",
                  (database.NOM_COLLECTION_DEFAUT,))[0]["id"]
    database.init_db()
    bases = _sql(vraie_v30, "SELECT c.id, c.nom, c.projet_id, c.acces_membres, p.repli "
                            "FROM collection c JOIN projet p ON p.id = c.projet_id "
                            "WHERE c.base = 1 ORDER BY p.id")
    assert [(b["nom"], b["repli"], b["acces_membres"]) for b in bases] == [
        (database.NOM_PROJET_DEFAUT, 1, None), ("Étude B", 0, None)]
    assert all(b["id"] > 4 for b in bases), "une collection existante est devenue une base"
    assert _sql(vraie_v30, "SELECT base FROM collection WHERE id = ?", (defaut,)) \
        == [{"base": 0}]
    assert _sql(vraie_v30, "SELECT COUNT(*) AS n FROM collection_album WHERE collection_id "
                           "IN (SELECT id FROM collection WHERE base = 1)")[0]["n"] == 0
    # Rejouée, elle n'en crée pas d'autre.
    _sql(vraie_v30, "PRAGMA user_version = 30")
    database.init_db()
    assert _sql(vraie_v30, "SELECT COUNT(*) AS n FROM collection WHERE base = 1")[0]["n"] == 2


def test_aucune_portee_ne_grandit_a_la_migration(vraie_v30):
    """Avant : ce que `collection_acces` ouvre à chacun (la règle de la v30). Après : la
    portée entière. Seule s'ajoute, aux responsables d'un projet — comptes et groupes —, la
    base NEUVE et vide de ce projet, à eux en propriété comme D10 le veut ; aucune
    collection existante ne s'ouvre, et aucun simple membre ne reçoit rien. Le décor porte
    des responsables du projet de repli (un compte, un groupe) : sans eux, le test ne voyait
    pas la collection de repli s'ouvrir (relecture croisée, constat 1)."""
    conn = sqlite3.connect(vraie_v30)
    avant = {login: autorisation.collections_du_principal(
        conn, login, [g for g in groupes.split(",") if g])[0:3] for login, groupes in QUI}
    existantes = {r[0] for r in conn.execute("SELECT id FROM collection")}
    conn.close()
    database.init_db()
    base_de = {r["nom"]: r["id"] for r in _sql(
        vraie_v30, "SELECT c.id, p.nom FROM collection c JOIN projet p ON p.id = c.projet_id "
                   "WHERE c.base = 1")}
    conn = database.get_connection()
    try:
        for login, groupes in QUI:
            p = autorisation.resoudre(conn, _Requete(login, groupes))
            attendu = ({base_de[RESPONSABLES[login]]} if login in RESPONSABLES
                       else set())
            # Ce que la v31 ajoute est la PROPRIÉTÉ de la base neuve, et rien d'autre.
            ajout = p.propriete - frozenset().union(*avant[login])
            assert ajout == attendu, (login, ajout, attendu)
            # Et ce qui s'ajoute est NEUF : aucune collection d'avant ne s'ouvre en écriture,
            # fût-elle devenue la base d'un projet (mutant : la « Collection par défaut »).
            assert not ajout & existantes, (login, ajout & existantes)
            assert p.ecriture - frozenset().union(*avant[login][1:]) <= attendu
            # La LECTURE d'un responsable gagne en plus, depuis la v38 (COL-3, tranche 3c,
            # F1), toutes les collections du projet qu'il gère — une lecture dérivée, en
            # lecture seule ; un simple membre ne gagne rien.
            lu = p.lecture - frozenset().union(*avant[login])
            if login not in RESPONSABLES:
                assert lu == set(), (login, lu)
            else:
                assert attendu <= lu and not (lu - attendu) & (p.ecriture | p.export)
    finally:
        conn.close()


def test_la_migration_n_ouvre_pas_la_collection_de_repli_a_ses_responsables(vraie_v30):
    """Recopié de la relecture croisée (`tests/test_relecture_t3a.py`, branche `relecture`,
    `e6473a5`), le login changé (`rose` au lieu de `rita`, que le décor v30 nomme déjà
    responsable du repli). La « Collection par défaut », habitée, désignée base du projet de
    repli, s'ouvrait en propriété à tout responsable de ce projet — un nom qui n'ouvrait rien
    en v30. Elle ne devient pas une base."""
    c = sqlite3.connect(vraie_v30)
    c.execute("INSERT INTO projet_acces (projet_id, genre, principal, role) "
              "VALUES (1, 'utilisateur', 'rose', 'responsable')")
    c.commit()
    avant = autorisation.collections_du_principal(c, "rose", [])
    c.close()
    assert avant[:3] == (frozenset(), frozenset(), frozenset())
    database.init_db()
    conn = database.get_connection()
    try:
        p = autorisation.resoudre(conn, _Requete("rose"))
        repli = conn.execute("SELECT id FROM collection WHERE nom = ?",
                             (database.NOM_COLLECTION_DEFAUT,)).fetchone()[0]
        habitee = conn.execute("SELECT COUNT(*) FROM collection_album WHERE collection_id = ?",
                               (repli,)).fetchone()[0]
    finally:
        conn.close()
    assert habitee > 0, "prémisse : la collection de repli porte des albums"
    # Depuis la v38 (COL-3, tranche 3c, F1), le responsable du repli LIT la collection de
    # repli, comme toutes celles de son projet — mais elle n'est pas devenue sa base : il
    # n'en est ni propriétaire, ni écrivain.
    assert repli not in p.propriete and repli not in p.ecriture, (
        f"la migration a ouvert la collection de repli ({habitee} album(s)) à un "
        f"responsable du projet de repli : {p!r}")


# --------------------------------------------------------------------------- #
# Une base qui porte du vocabulaire n'est pas vide (relecture croisée, constat 8)
# --------------------------------------------------------------------------- #
def test_une_base_qui_porte_un_axe_retient_son_projet_et_ne_le_divulgue_pas(
        client, derriere_proxy, db_path):
    """La sonde de la relecture : un domaine local à la base, puis le projet supprimé — la
    base partait, et le domaine devenait GLOBAL (`ON DELETE SET NULL`), lisible de toute
    l'instance. Le refus le nomme désormais, et le domaine reste à sa collection."""
    pid = _projet(client, nom="Grille privée")
    base = _base(db_path, pid)["id"]
    r = client.post("/api/domaines", json={"nom": "AxeSecret"}, headers=ADMIN)
    assert r.status_code in (200, 201), r.text
    domaine = r.json()["id"]
    assert r.json()["nom"] == "axesecret"           # la forme que les lectures rendent
    r = client.patch(f"/api/domaines/{domaine}/lexique",
                     json={"collection_id": base}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert "axesecret" not in str(client.get("/api/lexique", headers=ZOE).json())
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code == 409 and "vocabulaire" in r.json()["detail"], r.text
    assert "axesecret" not in str(client.get("/api/lexique", headers=ZOE).json())
    assert _sql(db_path, "SELECT collection_id FROM domaine WHERE id = ?", (domaine,)) \
        == [{"collection_id": base}]


@pytest.mark.parametrize("table", ["tags", "domaine", "attribut_dimension",
                                   "attribut_valeur"])
def test_tout_terme_local_a_la_base_retient_son_projet(client, derriere_proxy, db_path,
                                                       table):
    pid = _projet(client, nom="Lexique propre")
    base = _base(db_path, pid)["id"]
    if table == "tags":
        _sql(db_path, "INSERT INTO tags (label, collection_id) VALUES ('local', ?)", (base,))
    elif table == "domaine":
        _sql(db_path, "INSERT INTO domaine (nom, collection_id) VALUES ('local', ?)", (base,))
    else:
        dim = _sql(db_path, "INSERT INTO attribut_dimension (cible, nom, collection_id) "
                            "VALUES ('case', 'local', ?) RETURNING id",
                   (base if table == "attribut_dimension" else None,))[0]["id"]
        if table == "attribut_valeur":
            _sql(db_path, "INSERT INTO attribut_valeur (dimension_id, valeur, collection_id) "
                          "VALUES (?, 'local', ?)", (dim, base))
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code == 409 and "1 terme" in r.json()["detail"], r.text
    assert _base(db_path, pid)["id"] == base
