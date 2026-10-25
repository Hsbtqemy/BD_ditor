"""COL-3, tranche 3a — les corrections de la relecture croisée, et deux décisions de Hugo
(2026-10-17) prises après elle.

- Une demande qui visait une copie — un `rejoindre`, la ligne d'une entrée qui la reprend du
  fonds — se clôt quand la copie est détruite ; une entrée de plusieurs documents ne clôt
  que sa ligne, et son état se recalcule.
- Un ménage d'images qui n'obtient pas le verrou ne fait pas échouer une destruction
  validée : il laisse les fichiers et le dit au journal du serveur.
- Reprendre : le droit AVANT l'objet — à qui n'est ni responsable ni administrateur, le même
  refus qu'une copie soit gardée ou non.
- La source d'une copie vierge est une copie du projet d'ARRIVÉE (D3), sauf portée totale.
- Les entrées d'un projet ne nomment leur demandeur qu'à lui-même et à la portée totale.
- (Hugo, a) La copie née d'une entrée acceptée est créée PAR LE DEMANDEUR ; sa naissance,
  journalisée par l'administrateur, n'est pas un travail d'autrui.
- (Hugo, b) Qui répondra à un `rejoindre` se dit juste : un propriétaire qui tient toutes
  les collections de la copie, sinon un administrateur.
"""
import sqlite3

from conftest import ADMIN
from test_fonds import _accorder, _albums, _collection
from test_prendre import (ECRIVAIN, PROPRIO, RESP, _copie_dans, _entree,
                          _prendre, _repondre, _zero, prise)  # noqa: F401
from test_projets import _sql


def _sortir(client, cid, album_id):
    assert client.delete(f"/api/albums/{album_id}/collections/{cid}",
                         headers=ADMIN).status_code == 204


# --------------------------------------------------------------------------- #
# La destruction d'une copie clôt les demandes qui la visaient
# --------------------------------------------------------------------------- #
def test_une_reprise_se_clot_avec_sa_copie_sans_clore_l_entree(client, prise, db_path):
    """Une prise de deux documents : reprendre la copie gardée de d3, partir de zéro sur d2.
    Depuis l'écran de la 3a, la reprise est un RETOUR à part (`rendre_copie`), et l'entrée ne
    porte que d2. La copie gardée est détruite : le retour se clôt refusé, l'entrée ATTEND
    toujours d2 ; d2 accepté, elle se clôt `acceptee`."""
    cx = _copie_dans(client, prise, "d3", prise["x"])
    _sortir(client, prise["x"], cx)
    r = _prendre(client, None, [{"document_id": prise["docs"]["d3"], "reponse": "reprendre"},
                                _zero(prise["docs"]["d2"])],
                 RESP, motif="Pour le séminaire", projet=prise["projet"])
    retour, entree = (x["demande_id"] for x in r.json()["documents"])
    assert retour != entree, "le retour et l'entrée sont deux demandes"
    assert client.delete(f"/api/albums/{cx}", headers=ADMIN).status_code == 204
    vues = {d["id"]: d for d in client.get("/api/demandes", headers=ADMIN).json()}
    assert (vues[retour]["genre"], vues[retour]["en_attente"], vues[retour]["reponse"])         == ("rendre_copie", False, "refusee")
    assert vues[entree]["en_attente"] is True
    assert [x["document_id"] for x in vues[entree]["documents"]] == [prise["docs"]["d2"]]
    r = _repondre(client, entree, "acceptee", document_id=prise["docs"]["d2"])
    assert (r.json()["en_attente"], r.json()["reponse"]) == (False, "acceptee"), r.text


# --------------------------------------------------------------------------- #
# Un ménage sans verrou ne fait pas échouer la destruction
# --------------------------------------------------------------------------- #
def test_un_menage_sans_verrou_laisse_les_fichiers_et_repond_le_succes(client, prise, db_path,
                                                                       monkeypatch, caplog):
    import conflit
    import socle
    a = prise["albums"]["d3"]
    vrai, appels = conflit.verrouiller, []

    def verrou(conn):
        appels.append(1)
        if len(appels) == 2:                       # le second : celui du ménage
            raise sqlite3.OperationalError("database is locked")
        return vrai(conn)
    monkeypatch.setattr(socle.conflit, "verrouiller", verrou)
    dossier = prise["data"] / "corpus" / f"album_{a}"
    with caplog.at_level("WARNING", logger="bd_annotator"):
        r = client.delete(f"/api/albums/{a}", headers=ADMIN)
    assert r.status_code == 204, r.text
    assert _sql(db_path, "SELECT id FROM albums WHERE id = ?", (a,)) == []
    assert dossier.exists() and any(dossier.iterdir()), "les fichiers sont partis sans verrou"
    assert any("verrou" in x.getMessage() for x in caplog.records)


# --------------------------------------------------------------------------- #
# Reprendre : le droit avant l'objet
# --------------------------------------------------------------------------- #
def test_reprendre_ne_dit_pas_a_un_ecrivain_si_une_copie_est_gardee(client, prise):
    _copie_dans(client, prise, "d1", prise["x"])             # il lit une copie de d1 dans P
    ligne = {"document_id": prise["docs"]["d1"], "reponse": "reprendre"}
    sans = _prendre(client, prise["x"], [ligne], ECRIVAIN).json()["documents"][0]
    cy = _copie_dans(client, prise, "d1", prise["y"])
    _sortir(client, prise["y"], cy)                          # une copie gardée au fonds de P
    avec = _prendre(client, prise["x"], [ligne], ECRIVAIN).json()["documents"][0]
    assert sans == avec and sans["etat"] == "refuse", (sans, avec)
    assert "responsable" in sans["motif"]


# --------------------------------------------------------------------------- #
# La source d'une copie vierge est une copie du projet d'arrivée
# --------------------------------------------------------------------------- #
def test_la_source_d_un_zero_est_une_copie_du_projet(client, prise, db_path):
    """`autre` écrit dans Q (un second projet), y lit une copie de d1, et lit aussi la copie
    d'origine dans Principale (projet de repli). Nommer celle-ci comme source ferait entrer
    sa notice et ses scans dans le projet de Q sans que personne y consente : refusé, avec la
    voie qui reste. Sans source nommée, la copie part de celle du projet."""
    r = client.post("/api/projets", json={"nom": "Autre projet"}, headers=ADMIN)
    q = _collection(client, "Q", projet_id=r.json()["id"])
    _accorder(client, q, "autre", "ecriture")
    _accorder(client, prise["principale"], "autre", "lecture")
    cq = _copie_dans(client, prise, "d1", q)
    autre = {"Remote-User": "autre"}
    avant = _sql(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"]
    r = _prendre(client, q, [_zero(prise["docs"]["d1"], prise["albums"]["d1"])], autre)
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "refuse" and "responsable" in ligne["motif"], ligne
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"] == avant
    r = _prendre(client, q, [_zero(prise["docs"]["d1"])], autre)
    copie = r.json()["documents"][0]["copie_id"]
    assert _sql(db_path, "SELECT depuis_album_id FROM copie WHERE album_id = ?",
                (copie,)) == [{"depuis_album_id": cq}]
    # La portée totale, elle, part d'où elle veut.
    r = _prendre(client, q, [_zero(prise["docs"]["d1"], prise["albums"]["d1"])], ADMIN)
    assert r.json()["documents"][0]["etat"] == "fait"


# --------------------------------------------------------------------------- #
# Les entrées d'un projet ne nomment leur demandeur qu'à lui-même
# --------------------------------------------------------------------------- #
def test_un_autre_responsable_ne_lit_pas_qui_a_demande(client, prise):
    assert client.put(f"/api/projets/{prise['projet']}/membres", headers=ADMIN,
                      json={"principal": "resp2", "role": "responsable"}).status_code == 200
    _entree(client, prise, ("d1",))
    vue = client.get(f"/api/projets/{prise['projet']}/demandes",
                     headers={"Remote-User": "resp2"}).json()[0]
    assert "demandeur" not in vue and "demandeur_nom" not in vue, vue
    vue = client.get(f"/api/projets/{prise['projet']}/demandes", headers=RESP).json()[0]
    assert vue["demandeur"] == "resp"
    vue = client.get(f"/api/projets/{prise['projet']}/demandes", headers=ADMIN).json()[0]
    assert vue["demandeur"] == "resp"


# --------------------------------------------------------------------------- #
# (a) La copie d'une entrée acceptée est celle du demandeur
# --------------------------------------------------------------------------- #
def test_le_demandeur_supprime_seul_la_copie_qu_on_lui_a_accordee(client, prise, db_path):
    demande = _entree(client, prise, ("d1",))
    r = _repondre(client, demande, "acceptee")
    copie = r.json()["documents"][0]["copie_id"]
    assert _sql(db_path, "SELECT creee_par FROM copie WHERE album_id = ?",
                (copie,)) == [{"creee_par": "resp"}]
    # La naissance est bien écrite par l'administrateur, et ne compte pas comme un travail.
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'document' "
                         "AND json_extract(apres, '$.album_id') = ?", (copie,)) \
        == [{"agent": ADMIN["Remote-User"]}]
    assert _albums(client, RESP)[copie]["destructible"] is True
    assert client.delete(f"/api/albums/{copie}", headers=RESP).status_code == 204


def test_un_autre_acte_de_l_administrateur_compte_encore(client, prise):
    """Borné à la naissance : la notice retouchée par l'administrateur sur cette copie est
    un travail d'autrui. Jusqu'au 2026-10-21, le demandeur demandait alors ; depuis (COL-3,
    tranche 3b), il est aussi RESPONSABLE du projet de la copie, qui a une sœur au fonds
    commun, et l'efface encore — par le chemin du responsable, non par celui du créateur. Ce
    qui reste mesuré : l'acte de l'administrateur est lu comme le travail d'un autre, ce que
    l'écran « qui perd quoi » lui montre avant d'effacer."""
    demande = _entree(client, prise, ("d1",))
    copie = _repondre(client, demande, "acceptee").json()["documents"][0]["copie_id"]
    assert client.put(f"/api/albums/{copie}", json={"titre": "Retouché"},
                      headers=ADMIN).status_code == 200
    assert _albums(client, RESP)[copie]["destructible"] is True
    vue = client.get(f"/api/albums/{copie}/travail-des-autres", headers=RESP).json()
    assert [(e["agent"], e["gestes"]) for e in vue["travail_des_autres"]] == [
        (ADMIN["Remote-User"], {"document": 1})]


def test_une_prise_directe_reste_a_l_administrateur(client, prise, db_path):
    cx = _copie_dans(client, prise, "d1", prise["x"])
    assert _sql(db_path, "SELECT creee_par FROM copie WHERE album_id = ?",
                (cx,)) == [{"creee_par": ADMIN["Remote-User"]}]


# --------------------------------------------------------------------------- #
# (b) Qui répondra à un rejoindre, dit juste
# --------------------------------------------------------------------------- #
def test_qui_repondra_un_proprietaire_ou_un_administrateur(client, prise):
    # Une copie de X, que `proprio` possède : son propriétaire répondra.
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert (r.status_code, r.json()["repondra"]) == (202, "proprietaire"), r.text
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 409 and "son propriétaire" in r.json()["detail"], r.text
    # Une copie d'une collection SANS propriétaire : un administrateur seul.
    w = _collection(client, "Sans propriétaire", projet_id=prise["projet"])
    _accorder(client, w, "ecrivain", "ecriture")
    cw = _copie_dans(client, prise, "d2", w)
    r = client.put(f"/api/albums/{cw}/collections/{prise['y']}", headers=ECRIVAIN)
    assert (r.status_code, r.json()["repondra"]) == (202, "administrateur"), r.text
    r = client.put(f"/api/albums/{cw}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 409 and "un administrateur" in r.json()["detail"], r.text
    # Partagée entre X (proprio) et une collection d'un autre propriétaire : personne ne les
    # tient toutes.
    z = _collection(client, "Z", projet_id=prise["projet"])
    _accorder(client, z, "voisin", "proprietaire")
    c3 = _copie_dans(client, prise, "d3", prise["x"])
    assert client.put(f"/api/albums/{c3}/collections/{z}", headers=ADMIN).status_code == 201
    r = _prendre(client, prise["y"], [{"document_id": prise["docs"]["d3"],
                                       "reponse": "rejoindre", "album_id": c3}], PROPRIO)
    (ligne,) = r.json()["documents"]
    assert (ligne["etat"], ligne["repondra"]) == ("demande", "administrateur"), ligne
