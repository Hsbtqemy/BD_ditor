"""COL-3, tranche 3a — prendre un document : les notices du fonds, la prise, les demandes.

Les décisions de Hugo (2026-10-17) que ces tests tiennent, chacune jouée sous l'identité qui
compte, en regardant ensuite la base et ce que voient les AUTRES :

- D3 : le responsable d'un projet parcourt les NOTICES du fonds (titre, série, auteur, rien
  d'autre) et demande des documents pour une collection de son projet ; un écrivain qui
  n'est responsable de rien ne puise que dans ce qu'il LIT déjà. L'administrateur prend.
- D4, forme stricte : rejoindre un travail est immédiat pour qui ADMINISTRE chacune des
  collections où il vit ; sinon il se demande, et le propriétaire consent (D11). « + Ranger
  ici » est ce geste.
- D9 : l'administrateur répond document par document, ou « tout accepter » ; la demande se
  clôt à la dernière réponse, `partielle` quand elles sont mêlées.
- D10 : prendre pour un projet sans nommer de collection arrive dans sa collection de BASE.
- Geste 6 : reprendre une copie gardée au fonds de son projet se demande, même par le
  responsable.

Le décor : trois documents importés par `importeur` dans Principale (projet de repli). Le
projet « Étude P » — `resp` responsable, `membre` membre, sa base ouverte en écriture — a
deux collections : X (`proprio` la possède, `ecrivain` y écrit, `lectrice` la lit) et Y
(`ecrivain` et `proprio` y écrivent). `personne` n'est de rien.
"""
import json

import pytest

import database
from conftest import ADMIN
from test_fonds import _accorder, _album, _albums, _collection, _demander, _planche
from test_projets import _sql

RESP = {"Remote-User": "resp"}
MEMBRE = {"Remote-User": "membre"}
PROPRIO = {"Remote-User": "proprio"}
ECRIVAIN = {"Remote-User": "ecrivain"}
LECTRICE = {"Remote-User": "lectrice"}
PERSONNE = {"Remote-User": "personne"}
IMPORTEUR = {"Remote-User": "importeur"}
COLLEGUE = {"Remote-User": "collegue"}      # écrit dans Principale, n'a rien importé


@pytest.fixture
def prise(client, derriere_proxy, data_dir, db_path):
    principale = _collection(client, "Principale")
    _accorder(client, principale, "importeur", "ecriture")
    albums = {}
    for cle, titre, serie in (("d1", "Le Lotus bleu", "Tintin"),
                              ("d2", "L'Oreille cassée", "Tintin"),
                              ("d3", "Astérix légionnaire", "Astérix")):
        a = _album(client, titre, principale, IMPORTEUR)
        assert client.put(f"/api/albums/{a}", json={"serie": serie, "auteur": "Auteur"},
                          headers=IMPORTEUR).status_code == 200
        _planche(client, a, IMPORTEUR)
        albums[cle] = a
    docs = {k: _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (a,))[0]
            ["document_id"] for k, a in albums.items()}
    r = client.post("/api/projets", json={"nom": "Étude P"}, headers=ADMIN)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    for principal, role in (("resp", "responsable"), ("membre", "membre")):
        assert client.put(f"/api/projets/{pid}/membres", headers=ADMIN,
                          json={"principal": principal, "role": role}).status_code == 200
    x = _collection(client, "Collection X", projet_id=pid)
    y = _collection(client, "Collection Y", projet_id=pid)
    for cid, qui, niveau in ((x, "proprio", "proprietaire"), (x, "ecrivain", "ecriture"),
                             (x, "lectrice", "lecture"), (y, "ecrivain", "ecriture"),
                             (y, "proprio", "ecriture")):
        _accorder(client, cid, qui, niveau)
    conn = database.get_connection()
    try:
        base = database.collection_de_base(conn, pid)
    finally:
        conn.close()
    return {"principale": principale, "albums": albums, "docs": docs, "projet": pid,
            "x": x, "y": y, "base": base, "data": data_dir}


def _prendre(client, cid, lignes, qui, motif=None, projet=None):
    corps = {"documents": lignes}
    if motif is not None:
        corps["motif"] = motif
    chemin = (f"/api/projets/{projet}/prendre" if projet is not None
              else f"/api/collections/{cid}/prendre")
    return client.post(chemin, json=corps, headers=qui)


def _zero(doc, album_id=None):
    ligne = {"document_id": doc, "reponse": "zero"}
    if album_id is not None:
        ligne["album_id"] = album_id
    return ligne


def _copie_dans(client, prise, doc, cid):
    """L'administrateur prend `doc` en copie vierge pour `cid` : rend la copie."""
    r = _prendre(client, cid, [_zero(prise["docs"][doc])], ADMIN)
    assert r.status_code == 200, r.text
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "fait", ligne
    return ligne["copie_id"]


def _repondre(client, demande_id, reponse, qui=ADMIN, document_id=None):
    corps = {"reponse": reponse}
    if document_id is not None:
        corps["document_id"] = document_id
    return client.post(f"/api/demandes/{demande_id}/reponse", json=corps, headers=qui)


def _collections_de(db_path, album_id):
    return {r["collection_id"] for r in _sql(
        db_path, "SELECT collection_id FROM collection_album WHERE album_id = ?", (album_id,))}


# =========================================================================== #
# Les notices du fonds (D3)
# =========================================================================== #
@pytest.mark.parametrize("qui", [PERSONNE, ECRIVAIN, PROPRIO, LECTRICE, MEMBRE, IMPORTEUR])
def test_les_notices_se_lisent_par_les_responsables_seulement(client, prise, qui):
    """Le droit d'abord : le même 403 nommé, quels que soient les paramètres — y compris un
    projet qui n'existe pas. Être membre d'un projet, posséder une collection, écrire : rien
    de cela n'ouvre les notices de l'instance."""
    reponses = [client.get(f"/api/fonds/notices{q}", headers=qui)
                for q in ("", "?projet_id=99999", f"?projet_id={prise['projet']}&q=lotus")]
    assert [r.status_code for r in reponses] == [403, 403, 403]
    assert reponses[0].json() == reponses[1].json() == reponses[2].json()
    assert client.get("/api/fonds/notices", headers=RESP).status_code == 200
    assert client.get("/api/fonds/notices", headers=ADMIN).status_code == 200


def test_une_notice_ne_dit_que_titre_serie_auteur(client, prise):
    """Sur le JSON BRUT : aucune clé hors de la liste nommée — ni qui a importé, ni les
    copies, ni leurs projets ou collections, ni la demande, ni le nombre de planches."""
    _accorder(client, prise["principale"], "collegue", "ecriture")
    assert _demander(client, prise["albums"]["d1"], COLLEGUE).status_code == 201
    r = client.get("/api/fonds/notices", headers=RESP)
    corps = r.json()
    assert set(corps) == {"total", "offset", "limit", "notices"}
    assert corps["total"] == 3 and len(corps["notices"]) == 3
    for n in corps["notices"]:
        assert set(n) == {"document_id", "titre", "serie", "auteur"}, n
    for interdit in ("importeur", "Principale", "Projet principal", "demande", "planche",
                     "album_id", "importe"):
        assert interdit not in r.text, interdit


def test_ce_que_le_projet_a_deja_sans_dire_ou(client, prise, db_path):
    """Pour un projet qu'il GÈRE, le responsable lit deux faits par notice : le projet a-t-il
    une copie rangée du document, en a-t-il une gardée au fonds. Jamais dans quelle
    collection. Un projet qu'il ne gère pas : 404 ou 403, jamais les faits."""
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = client.get(f"/api/fonds/notices?projet_id={prise['projet']}", headers=RESP)
    assert r.status_code == 200, r.text
    par_doc = {n["document_id"]: n for n in r.json()["notices"]}
    for n in par_doc.values():
        assert set(n) == {"document_id", "titre", "serie", "auteur", "dans_le_projet",
                          "garde_au_fonds"}
    d1 = par_doc[prise["docs"]["d1"]]
    assert (d1["dans_le_projet"], d1["garde_au_fonds"]) == (True, False)
    assert par_doc[prise["docs"]["d2"]]["dans_le_projet"] is False
    assert "Collection X" not in r.text and str(cx) not in json.dumps(
        [n for n in r.json()["notices"]])
    # Sortie au fonds, la copie se dit « gardée ».
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=PROPRIO).status_code == 204
    d1 = {n["document_id"]: n for n in client.get(
        f"/api/fonds/notices?projet_id={prise['projet']}", headers=RESP).json()["notices"]}[
        prise["docs"]["d1"]]
    assert (d1["dans_le_projet"], d1["garde_au_fonds"]) == (False, True)
    repli = _sql(db_path, "SELECT id FROM projet WHERE repli = 1")[0]["id"]
    assert client.get(f"/api/fonds/notices?projet_id={repli}",
                      headers=RESP).status_code in (403, 404)


def test_les_notices_se_cherchent_et_se_paginent(client, prise):
    def titres(q):
        return [n["titre"] for n in client.get(f"/api/fonds/notices?{q}",
                                               headers=RESP).json()["notices"]]
    assert titres("q=asterix") == ["Astérix légionnaire"]      # sans accents
    assert titres("q=TINTIN") == ["L'Oreille cassée", "Le Lotus bleu"]
    page = client.get("/api/fonds/notices?limit=1&offset=1", headers=RESP).json()
    assert (page["total"], len(page["notices"]), page["offset"]) == (3, 1, 1)


def test_la_notice_est_celle_de_la_plus_ancienne_copie(client, prise):
    """D7 — la notice reste sur la copie, libre de diverger ; le fonds montre celle de la
    plus ancienne copie vivante."""
    cx = _copie_dans(client, prise, "d1", prise["x"])
    assert client.put(f"/api/albums/{cx}", json={"titre": "Lotus, relu"},
                      headers=ECRIVAIN).status_code == 200
    titres = [n["titre"] for n in client.get("/api/fonds/notices",
                                             headers=RESP).json()["notices"]]
    assert "Le Lotus bleu" in titres and "Lotus, relu" not in titres


# =========================================================================== #
# Prendre — l'administrateur, le responsable, l'écrivain
# =========================================================================== #
def test_l_administrateur_prend_une_copie_vierge(client, prise, db_path):
    a1 = prise["albums"]["d1"]
    cx = _copie_dans(client, prise, "d1", prise["x"])
    ligne = _sql(db_path, "SELECT document_id, projet_id FROM albums WHERE id = ?", (cx,))[0]
    assert (ligne["document_id"], ligne["projet_id"]) == (prise["docs"]["d1"], prise["projet"])
    assert _collections_de(db_path, cx) == {prise["x"]}
    conn = database.get_connection()
    try:
        assert database.albums_hors_de_leur_projet(conn) == []
    finally:
        conn.close()
    assert _sql(db_path, "SELECT creee_par, depuis_album_id FROM copie WHERE album_id = ?",
                (cx,)) == [{"creee_par": ADMIN["Remote-User"], "depuis_album_id": a1}]
    # Ses images répondent à qui lit X : les fichiers de la source, partagés (D6).
    web = _sql(db_path, "SELECT chemin_web FROM planches WHERE album_id = ?", (cx,))[0]
    assert client.get("/" + web["chemin_web"], headers=ECRIVAIN).status_code == 200
    assert client.get("/" + web["chemin_web"], headers=PERSONNE).status_code == 404


def test_prendre_pour_un_projet_arrive_dans_sa_base(client, prise, db_path):
    """D10 — sans nommer de collection, la copie entre dans la collection de BASE."""
    r = _prendre(client, None, [_zero(prise["docs"]["d2"])], ADMIN, projet=prise["projet"])
    assert r.status_code == 200, r.text
    copie = r.json()["documents"][0]["copie_id"]
    assert r.json()["collection_id"] == prise["base"]
    assert _collections_de(db_path, copie) == {prise["base"]}
    # Qui ne peut pas nommer le projet : 404 ; qui le nomme sans écrire dans sa base : 403.
    assert _prendre(client, None, [_zero(prise["docs"]["d2"])], PERSONNE,
                    projet=prise["projet"]).status_code == 404
    assert client.put(f"/api/projets/{prise['projet']}/acces-membres", headers=ADMIN,
                      json={"acces_membres": None}).status_code == 200
    assert _prendre(client, None, [_zero(prise["docs"]["d2"])], PROPRIO,
                    projet=prise["projet"]).status_code == 403


def test_une_collection_ou_l_on_n_ecrit_pas_est_introuvable(client, prise):
    for cid in (prise["x"], 99999):
        r = _prendre(client, cid, [_zero(prise["docs"]["d1"])], LECTRICE)
        assert r.status_code == 404, r.text


def test_le_responsable_demande_l_entree_avec_un_motif(client, prise, db_path):
    lignes = [_zero(prise["docs"][d]) for d in ("d1", "d2", "d3")]
    avant = _sql(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"]
    r = _prendre(client, None, lignes, RESP, projet=prise["projet"])
    assert r.status_code == 422 and "pourquoi" in r.json()["detail"].lower(), r.text
    r = _prendre(client, None, lignes, RESP, motif="Pour le séminaire", projet=prise["projet"])
    assert r.status_code == 200, r.text
    etats = r.json()["documents"]
    assert {e["etat"] for e in etats} == {"demande"}
    assert len({e["demande_id"] for e in etats}) == 1, "une entrée porte plusieurs documents"
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"] == avant
    demande = etats[0]["demande_id"]
    # Qui l'a déposée la lit dans la fiche de son projet ; un simple membre, non.
    vues = client.get(f"/api/projets/{prise['projet']}/demandes", headers=RESP).json()
    assert [v["id"] for v in vues] == [demande]
    assert (vues[0]["en_attente"], vues[0]["collection_id"]) == (True, prise["base"])
    assert len(vues[0]["documents"]) == 3
    assert client.get(f"/api/projets/{prise['projet']}/demandes",
                      headers=MEMBRE).status_code == 403
    assert client.get(f"/api/projets/{prise['projet']}/demandes",
                      headers=PERSONNE).status_code == 404
    # La même demande ne se dépose pas deux fois tant qu'elle attend.
    r = _prendre(client, None, lignes[:1], RESP, motif="encore", projet=prise["projet"])
    assert r.json()["documents"][0]["etat"] == "refuse"
    # L'administrateur la voit, avec sa collection d'arrivée.
    vue = [d for d in client.get("/api/demandes", headers=ADMIN).json() if d["id"] == demande][0]
    assert (vue["genre"], vue["collection_id"]) == ("entree_documents", prise["base"])


def _entree(client, prise, docs=("d1", "d2", "d3")):
    r = _prendre(client, None, [_zero(prise["docs"][d]) for d in docs], RESP,
                 motif="Pour le séminaire", projet=prise["projet"])
    assert r.status_code == 200, r.text
    return r.json()["documents"][0]["demande_id"]


def test_l_administrateur_repond_document_par_document(client, prise, db_path):
    """D9 — la demande se clôt à la DERNIÈRE réponse, et dit `partielle`."""
    demande = _entree(client, prise)
    d1, d2, d3 = (prise["docs"][d] for d in ("d1", "d2", "d3"))
    r = _repondre(client, demande, "acceptee", document_id=d1)
    assert r.status_code == 200, r.text
    assert r.json()["en_attente"] is True, "close à la première réponse"
    lignes = {x["document_id"]: x for x in r.json()["documents"]}
    copie = lignes[d1]["copie_id"]
    assert lignes[d1]["reponse"] == "acceptee" and copie is not None
    assert _collections_de(db_path, copie) == {prise["base"]}
    assert _repondre(client, demande, "refusee", document_id=d2).json()["en_attente"] is True
    assert _repondre(client, demande, "acceptee", document_id=d1).status_code == 409
    r = _repondre(client, demande, "acceptee", document_id=d3)
    assert (r.json()["en_attente"], r.json()["reponse"]) == (False, "partielle")
    vue = client.get(f"/api/projets/{prise['projet']}/demandes", headers=RESP).json()[0]
    assert vue["reponse"] == "partielle"
    assert {x["document_id"]: x["reponse"] for x in vue["documents"]} == {
        d1: "acceptee", d2: "refusee", d3: "acceptee"}
    assert _repondre(client, demande, "acceptee").status_code == 409


def test_tout_accepter(client, prise, db_path):
    demande = _entree(client, prise, ("d1", "d2"))
    r = _repondre(client, demande, "acceptee")
    assert (r.json()["en_attente"], r.json()["reponse"]) == (False, "acceptee")
    copies = [x["copie_id"] for x in r.json()["documents"]]
    assert all(copies) and all(_collections_de(db_path, c) == {prise["base"]} for c in copies)


def test_un_proprietaire_ne_repond_ni_a_une_entree_ni_a_une_suppression(client, prise):
    """Ces genres sont à qui tient le fonds. Pour qui administre une collection, ils sont
    INTROUVABLES — comme une demande qui n'existe pas ; pour qui n'administre rien, le droit
    d'abord : le même 403, que la demande existe ou non."""
    entree = _entree(client, prise, ("d1",))
    _accorder(client, prise["principale"], "collegue", "ecriture")
    suppression = _demander(client, prise["albums"]["d2"], COLLEGUE).json()["id"]
    reponses = [_repondre(client, i, "acceptee", qui=PROPRIO)
                for i in (entree, suppression, 99999)]
    assert [r.status_code for r in reponses] == [404, 404, 404]
    assert reponses[0].json()["detail"].replace(str(entree), "N") \
        == reponses[2].json()["detail"].replace("99999", "N")
    sans = [_repondre(client, i, "acceptee", qui=ECRIVAIN) for i in (entree, 99999)]
    assert [r.status_code for r in sans] == [403, 403] and sans[0].json() == sans[1].json()


def test_un_ecrivain_ne_nomme_que_ce_qu_il_lit(client, prise):
    """D3 — `ecrivain` n'est responsable de rien : un document dont il ne lit aucune copie
    dans le projet est INTROUVABLE, le même qu'un identifiant qui n'existe pas. Un document
    dont il lit une copie dans le projet, il en part de zéro sans rien demander."""
    reponses = [_prendre(client, prise["y"], [_zero(doc)], ECRIVAIN)
                for doc in (prise["docs"]["d2"], 99999)]
    assert [r.status_code for r in reponses] == [404, 404]
    assert reponses[0].json()["detail"].replace(str(prise["docs"]["d2"]), "N") \
        == reponses[1].json()["detail"].replace("99999", "N")
    _copie_dans(client, prise, "d1", prise["x"])
    r = _prendre(client, prise["y"], [_zero(prise["docs"]["d1"])], ECRIVAIN)
    assert r.status_code == 200 and r.json()["documents"][0]["etat"] == "fait", r.text


def test_qui_part_de_zero_supprime_seul_sa_copie(client, prise):
    """La copie prise par `ecrivain` est la sienne (`copie.creee_par`) : seul à y avoir
    travaillé, il la supprime sans rien demander — sa naissance au journal est son acte."""
    _copie_dans(client, prise, "d1", prise["x"])
    copie = _prendre(client, prise["y"], [_zero(prise["docs"]["d1"])],
                     ECRIVAIN).json()["documents"][0]["copie_id"]
    assert _albums(client, ECRIVAIN)[copie]["destructible"] is True
    assert client.delete(f"/api/albums/{copie}", headers=ECRIVAIN).status_code == 204


def test_une_prise_s_arrete_entiere_sur_un_document_introuvable(client, prise, db_path):
    _copie_dans(client, prise, "d1", prise["x"])
    avant = _sql(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"]
    r = _prendre(client, prise["y"], [_zero(prise["docs"]["d1"]), _zero(prise["docs"]["d2"])],
                 ECRIVAIN)
    assert r.status_code == 404
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM albums")[0]["n"] == avant


# =========================================================================== #
# Rejoindre (D4 stricte, D11)
# =========================================================================== #
def _rejoindre(doc, album_id):
    return {"document_id": doc, "reponse": "rejoindre", "album_id": album_id}


def test_un_ecrivain_demande_a_rejoindre_le_proprietaire_consent(client, prise, db_path):
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = _prendre(client, prise["y"], [_rejoindre(prise["docs"]["d1"], cx)], ECRIVAIN)
    assert r.status_code == 200, r.text
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "demande", "un écrivain non propriétaire a rejoint sans consentement"
    assert _collections_de(db_path, cx) == {prise["x"]}
    # Le propriétaire la lit dans la fiche de SA collection, avec qui demande et pour où.
    recues = client.get(f"/api/collections/{prise['x']}/demandes", headers=PROPRIO).json()
    assert [(d["id"], d["demandeur"], d["collection_nom"], d["album_id"], d["repondable"])
            for d in recues] == [(ligne["demande_id"], "ecrivain", "Collection Y", cx, True)]
    assert client.get(f"/api/collections/{prise['x']}/demandes",
                      headers=ECRIVAIN).status_code == 403
    assert client.get(f"/api/collections/{prise['x']}/demandes",
                      headers=PERSONNE).status_code == 404
    r = _repondre(client, ligne["demande_id"], "acceptee", qui=PROPRIO)
    assert r.status_code == 200 and r.json()["reponse"] == "acceptee", r.text
    assert _collections_de(db_path, cx) == {prise["x"], prise["y"]}
    assert client.get(f"/api/collections/{prise['x']}/demandes", headers=PROPRIO).json() == []


def test_qui_tient_le_travail_rejoint_sans_rien_demander(client, prise, db_path):
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = _prendre(client, prise["y"], [_rejoindre(prise["docs"]["d1"], cx)], PROPRIO)
    assert r.json()["documents"][0]["etat"] == "fait", r.text
    assert _collections_de(db_path, cx) == {prise["x"], prise["y"]}


def test_ranger_ici_est_un_rejoindre(client, prise, db_path):
    """« + Ranger ici » (`PUT /api/albums/{id}/collections/{cid}`) passe par la même règle :
    une demande pour qui ne tient pas le travail (202), un rangement pour qui le tient."""
    cx = _copie_dans(client, prise, "d1", prise["x"])
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 202 and r.json()["etat"] == "demande", r.text
    assert _collections_de(db_path, cx) == {prise["x"]}
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=PROPRIO)
    assert r.status_code == 201, r.text
    assert _collections_de(db_path, cx) == {prise["x"], prise["y"]}


def test_le_proprietaire_d_une_autre_collection_ne_repond_pas(client, prise):
    """Un propriétaire qui ne lit pas la copie : la demande lui est INTROUVABLE. Qui la lit
    sans tenir toutes ses collections : 403 nommé."""
    cx = _copie_dans(client, prise, "d1", prise["x"])
    demande = _prendre(client, prise["y"], [_rejoindre(prise["docs"]["d1"], cx)],
                       ECRIVAIN).json()["documents"][0]["demande_id"]
    autre = _collection(client, "Autre", projet_id=prise["projet"])
    _accorder(client, autre, "voisin", "proprietaire")
    voisin = {"Remote-User": "voisin"}
    assert _repondre(client, demande, "acceptee", qui=voisin).status_code == 404
    _accorder(client, prise["x"], "voisin", "lecture")
    r = _repondre(client, demande, "acceptee", qui=voisin)
    assert r.status_code == 403, r.text
    assert client.get(f"/api/collections/{autre}/demandes", headers=voisin).json() == []


def test_une_collection_sans_proprietaire_n_est_tenue_que_par_l_administrateur(client, prise,
                                                                               db_path):
    """`proprio` possède X et écrit dans W, qui n'a pas de propriétaire : il ne rejoint pas
    seul une copie de W, et ne répond pas à la demande — seul un administrateur la tient."""
    w = _collection(client, "Sans propriétaire", projet_id=prise["projet"])
    _accorder(client, w, "proprio", "ecriture")
    cw = _copie_dans(client, prise, "d2", w)
    r = _prendre(client, prise["x"], [_rejoindre(prise["docs"]["d2"], cw)], PROPRIO)
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "demande", ligne
    assert _repondre(client, ligne["demande_id"], "acceptee", qui=PROPRIO).status_code == 403
    assert _repondre(client, ligne["demande_id"], "acceptee").status_code == 200
    assert _collections_de(db_path, cw) == {w, prise["x"]}


def test_rejoindre_ne_traverse_pas_les_projets(client, prise, db_path):
    a1 = prise["albums"]["d1"]
    r = _prendre(client, prise["x"], [_rejoindre(prise["docs"]["d1"], a1)], ADMIN)
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "refuse" and "traverse" in ligne["motif"], ligne
    assert _collections_de(db_path, a1) == {prise["principale"]}


def test_rejoindre_une_copie_qu_on_ne_lit_pas_est_introuvable(client, prise):
    cx = _copie_dans(client, prise, "d1", prise["x"])
    autre = _collection(client, "Ailleurs", projet_id=prise["projet"])
    _accorder(client, autre, "personne", "ecriture")
    assert client.put(f"/api/albums/{cx}/collections/{autre}",
                      headers=PERSONNE).status_code == 404


# =========================================================================== #
# Reprendre une copie gardée au fonds (geste 6)
# =========================================================================== #
def test_reprendre_une_copie_gardee_se_demande(client, prise, db_path):
    cx = _copie_dans(client, prise, "d3", prise["x"])
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=PROPRIO).status_code == 204
    reprise = {"document_id": prise["docs"]["d3"], "reponse": "reprendre"}
    r = _prendre(client, None, [reprise], RESP, motif="On la reprend", projet=prise["projet"])
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "demande", ligne
    assert _collections_de(db_path, cx) == set()
    r = _repondre(client, ligne["demande_id"], "acceptee")
    assert r.status_code == 200, r.text
    assert r.json()["documents"][0]["copie_id"] == cx, "la copie gardée, pas une neuve"
    assert _collections_de(db_path, cx) == {prise["base"]}


def test_l_administrateur_reprend_directement(client, prise, db_path):
    cx = _copie_dans(client, prise, "d3", prise["x"])
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=PROPRIO).status_code == 204
    r = _prendre(client, prise["y"], [{"document_id": prise["docs"]["d3"],
                                       "reponse": "reprendre"}], ADMIN)
    assert r.json()["documents"][0] == {"document_id": prise["docs"]["d3"],
                                        "reponse": "reprendre", "etat": "fait",
                                        "copie_id": cx}
    assert _collections_de(db_path, cx) == {prise["y"]}


# =========================================================================== #
# Le reste
# =========================================================================== #
def test_detruire_la_source_garde_l_image_de_la_soeur(client, prise, db_path):
    """La sœur née par la prise désigne les fichiers de sa source (D6) : détruire la source,
    l'image de la sœur répond encore, et son fichier est là."""
    cx = _copie_dans(client, prise, "d1", prise["x"])
    web = _sql(db_path, "SELECT chemin_web, chemin_tiff FROM planches WHERE album_id = ?",
               (cx,))[0]
    assert client.delete(f"/api/albums/{prise['albums']['d1']}", headers=ADMIN).status_code \
        == 204
    assert (prise["data"] / web["chemin_web"]).exists()
    assert (prise["data"] / web["chemin_tiff"]).exists()
    assert client.get("/" + web["chemin_web"], headers=ECRIVAIN).status_code == 200


def test_les_genres_de_la_prise_ne_se_deposent_pas_par_les_demandes(client, prise):
    for genre in ("entree_documents", "rejoindre"):
        r = client.post("/api/demandes", headers=RESP,
                        json={"genre": genre, "album_id": prise["albums"]["d1"],
                              "motif": "x"})
        assert r.status_code == 422 and "prendre" in r.json()["detail"], r.text


def test_supprimer_la_collection_d_arrivee_clot_ses_demandes(client, prise, db_path):
    """L'identifiant d'une collection se réattribue : une demande qui la nomme encore
    rangerait, acceptée plus tard, dans la collection créée ensuite."""
    cx = _copie_dans(client, prise, "d1", prise["x"])
    demande = _prendre(client, prise["y"], [_rejoindre(prise["docs"]["d1"], cx)],
                       ECRIVAIN).json()["documents"][0]["demande_id"]
    assert client.delete(f"/api/collections/{prise['y']}", headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (demande,)) \
        == [{"reponse": "refusee"}]
