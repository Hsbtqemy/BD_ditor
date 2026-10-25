"""COL-3, tranche 3b — ce que l'écran tranché sur maquette (Hugo, 2026-10-25) demande au
serveur, et les bornes de chaque réponse.

- une copie REMISE À ZÉRO le dit dans sa fiche : `repartie` de `GET /api/albums` (le dernier
  acte `repartir` sur l'album entier : cran, d'où, date ; qui, à qui écrit dans la copie et
  à la portée totale seulement) ;
- « Supprimer la DERNIÈRE copie » : `derniere_copie`, la règle de l'effacement dite album par
  album, à qui écrit dans la copie ;
- le panneau « Repartir de zéro » : `GET /api/albums/{id}/repartir/apercu` (ce qui part, le
  plus haut travail, direct ou demandé) ;
- « Retirer du projet » : son aperçu (les collections, leurs propriétaires, qui y a
  travaillé), son motif facultatif, et l'avis à chaque propriétaire jusqu'à « Vu »
  (`GET /api/collections/{id}/retraits`, `POST …/retraits/{acte}/vu`) ;
- le responsable source choisit sa copie parmi TOUTES celles de son projet, les trop peu
  travaillées éteintes, chacune avec son aperçu ; l'administrateur lit qui attend.
"""
import pytest

from conftest import ADMIN
from test_amorcer import LEA, SAM, source  # noqa: F401
from test_amorcer_entre_projets import (RESP2, _demander_ailleurs, _repondre, _travailler,
                                        ailleurs)  # noqa: F401
from test_fonds import _accorder
from test_prendre import ECRIVAIN, LECTRICE, PERSONNE, PROPRIO, RESP, prise  # noqa: F401
from test_projets import _sql
from test_qui_efface import efface  # noqa: F401

import database


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _album(client, qui, album_id):
    return next((a for a in client.get("/api/albums", headers=qui).json()
                 if a["id"] == album_id), None)


# =========================================================================== #
# La puce « repartie … le … », et la dernière copie
# =========================================================================== #
def test_une_copie_remise_a_zero_le_dit_et_le_nom_est_borne(client, source):
    lectrice = {"Remote-User": "lectrice"}
    _accorder(client, source["principale"], "lectrice", "lecture")
    assert _album(client, LEA, source["a"])["repartie"] is None
    # Une planche remise à zéro ne fait pas la puce de l'album.
    _ok(client.post(f"/api/planches/{source['pl']}/repartir", headers=LEA,
                    json={"cran": "grammaire"}))
    assert _album(client, LEA, source["a"])["repartie"] is None
    _ok(client.post(f"/api/albums/{source['a']}/repartir", headers=LEA,
                    json={"cran": "decoupage"}))
    p = _album(client, LEA, source["a"])["repartie"]
    assert (p["cran"], p["depuis_cran"], p["par"]) == ("decoupage", "grammaire", "lea")
    assert p["le"]
    for qui in (SAM, ADMIN):
        assert _album(client, qui, source["a"])["repartie"]["par"] == "lea", qui
    lue = _album(client, lectrice, source["a"])["repartie"]
    assert lue["cran"] == "decoupage" and "par" not in lue and "par_nom" not in lue


def test_la_derniere_copie_se_dit_a_qui_ecrit(client, source):
    lectrice = {"Remote-User": "lectrice"}
    _accorder(client, source["principale"], "lectrice", "lecture")
    assert _album(client, LEA, source["a"])["derniere_copie"] is True
    assert _album(client, lectrice, source["a"])["derniere_copie"] is False
    conn = database.get_connection()
    try:
        database.creer_copie(conn, source["doc"], source["etude"], par="sam",
                             depuis=source["a"], cran="images")
        conn.commit()
    finally:
        conn.close()
    assert _album(client, LEA, source["a"])["derniere_copie"] is False


# =========================================================================== #
# Le panneau « Repartir de zéro »
# =========================================================================== #
@pytest.mark.parametrize("cran", ["grammaire", "transcription", "decoupage", "images"])
def test_l_apercu_de_repartir_est_ce_que_l_acte_retire(client, source, cran):
    apercu = _ok(client.get(f"/api/albums/{source['a']}/repartir/apercu?cran={cran}",
                            headers=LEA))
    assert (apercu["niveau"], apercu["direct"], apercu["rien_a_retirer"]) == (
        "annotations", True, False)
    rendu = _ok(client.post(f"/api/albums/{source['a']}/repartir", headers=LEA,
                            json={"cran": cran}))
    assert apercu["comptes"] == rendu["comptes"]


def test_l_apercu_de_repartir_est_borne(client, source):
    lectrice = {"Remote-User": "lectrice"}
    _accorder(client, source["principale"], "lectrice", "lecture")
    r = _ok(client.get(f"/api/albums/{source['a']}/repartir/apercu?cran=grammaire",
                       headers=SAM))
    assert r["direct"] is False
    assert client.get(f"/api/albums/{source['a']}/repartir/apercu?cran=grammaire",
                      headers=lectrice).status_code == 404
    assert client.get(f"/api/albums/{source['a']}/repartir/apercu?cran=annotations",
                      headers=LEA).status_code == 422
    autre = _ok(client.post("/api/albums", headers=LEA,
                            json={"titre": "Autre", "collection_id": source["principale"]}),
                201)["id"]
    assert client.get(f"/api/albums/{autre}/repartir/apercu?cran=images&planche="
                      f"{source['pl']}", headers=LEA).status_code == 404
    planche = _ok(client.get(f"/api/albums/{source['a']}/repartir/apercu?cran=images&planche="
                             f"{source['pl']}", headers=LEA))
    assert planche["comptes"]["regions"] == 2


# =========================================================================== #
# « Retirer du projet » : l'aperçu, le motif, l'avis jusqu'à « Vu »
# =========================================================================== #
def test_l_apercu_du_retrait_nomme_les_proprietaires(client, efface):
    vue = _ok(client.get(f"/api/albums/{efface['b1']}/retirer-du-projet/apercu", headers=RESP))
    proprios = {c["id"]: [x["principal"] for x in c["proprietaires"]]
                for c in vue["collections"]}
    assert proprios == {efface["base"]: ["resp"], efface["x"]: ["proprio"]}
    for qui, code in ((PROPRIO, 403), (ECRIVAIN, 403), (PERSONNE, 404)):
        assert client.get(f"/api/albums/{efface['b1']}/retirer-du-projet/apercu",
                          headers=qui).status_code == code, qui


def test_chaque_proprietaire_lit_le_retrait_jusqu_a_vu(client, efface):
    b1, x, base = efface["b1"], efface["x"], efface["base"]
    _ok(client.post(f"/api/albums/{b1}/retirer-du-projet", headers=RESP,
                    json={"motif": "Mauvaise numérisation"}))
    (avis,) = _ok(client.get(f"/api/collections/{x}/retraits", headers=PROPRIO))
    assert (avis["album_id"], avis["titre"], avis["par"], avis["motif"]) == (
        b1, "L'Oreille cassée", "resp", "Mauvaise numérisation")
    # Qui écrit dans X sans la posséder ne le lit pas ; qui ne la lit pas, 404.
    assert client.get(f"/api/collections/{x}/retraits", headers=ECRIVAIN).status_code == 403
    assert client.get(f"/api/collections/{x}/retraits", headers=PERSONNE).status_code == 404
    # « Vu » par proprio : il ne le lit plus ; le responsable, propriétaire de la base, si.
    assert client.post(f"/api/collections/{x}/retraits/{avis['evenement_id']}/vu",
                       headers=ECRIVAIN).status_code == 403
    _ok(client.post(f"/api/collections/{x}/retraits/{avis['evenement_id']}/vu",
                    headers=PROPRIO), 204)
    assert _ok(client.get(f"/api/collections/{x}/retraits", headers=PROPRIO)) == []
    assert [a["evenement_id"] for a in _ok(client.get(f"/api/collections/{base}/retraits",
                                                      headers=RESP))] == [avis["evenement_id"]]
    # Un acte qui n'est pas un retrait de cette collection : 404, comme un acte absent.
    autre = _sql(efface["db"], "SELECT MIN(id) AS i FROM evenement")[0]["i"]
    for acte in (autre, 999999):
        assert client.post(f"/api/collections/{x}/retraits/{acte}/vu",
                           headers=PROPRIO).status_code == 404
    # La fiche du projet le dit dans ses copies gardées.
    (gardee,) = _ok(client.get(f"/api/projets/{efface['projet']}/copies-gardees",
                               headers=RESP))
    assert (gardee["retire_du_projet"]["par"], gardee["retire_du_projet"]["motif"]) == (
        "resp", "Mauvaise numérisation")


def test_le_motif_d_un_retrait_est_borne(client, efface):
    r = client.post(f"/api/albums/{efface['b1']}/retirer-du-projet", headers=RESP,
                    json={"motif": "x" * (database.LONGUEUR_MOTIF + 1)})
    assert r.status_code == 422
    _ok(client.post(f"/api/albums/{efface['b1']}/retirer-du-projet", headers=RESP))
    (avis,) = _ok(client.get(f"/api/collections/{efface['x']}/retraits", headers=PROPRIO))
    assert avis["motif"] is None


# =========================================================================== #
# Le responsable source choisit sa copie ; l'administrateur lit qui attend
# =========================================================================== #
def test_le_responsable_source_voit_toutes_ses_copies_eteintes_ou_non(client, ailleurs):
    """Une seconde copie du Lotus bleu dans le repli, vierge : elle s'affiche, éteinte
    (`tient` faux), et accepter en la nommant répond le 404 d'une copie qu'on ne tient pas."""
    vierge = _ok(client.post(f"/api/collections/{ailleurs['principale']}/prendre",
                             headers=ADMIN,
                             json={"documents": [{"document_id": ailleurs["docs"]["d1"],
                                                  "reponse": "zero"}]}))
    vierge = vierge["documents"][0]["copie_id"]
    ligne = _demander_ailleurs(client, ailleurs)
    (d,) = _ok(client.get(f"/api/projets/{ailleurs['repli']}/demandes-recues", headers=RESP2))
    copies = {c["album_id"]: c for c in d["copies"]}
    assert copies[ailleurs["albums"]["d1"]]["tient"] is True
    assert copies[vierge]["tient"] is False
    assert copies[ailleurs["albums"]["d1"]]["apercu"]["copies"]["textes"] == 1
    assert "collection_id" not in d
    assert _repondre(client, ligne["demande_id"], "acceptee", RESP2,
                     album_id=vierge).status_code == 404


def test_l_administrateur_lit_qui_attend_et_l_apercu(client, ailleurs):
    ligne = _demander_ailleurs(client, ailleurs)
    d = next(x for x in _ok(client.get("/api/demandes", headers=ADMIN))
             if x["id"] == ligne["demande_id"])
    (s,) = d["sources"]
    assert [r["principal"] for r in s["responsables"]] == ["resp2"]
    assert s["apercu"]["copies"]["regions"] == 2
    # L'administrateur répond à la place du responsable source.
    vue = _ok(_repondre(client, ligne["demande_id"], "acceptee", ADMIN,
                        album_id=ailleurs["albums"]["d1"]))
    assert vue["reponse"] == "acceptee"


def test_une_demande_d_en_partir_dans_le_projet_porte_son_apercu(client, prise):
    """La propriétaire de X reçoit, dans le bloc ⚑, une demande d'en partir d'une copie de X
    vers Y : elle la lit avec ses nombres ; l'administrateur aussi."""
    cx = _ok(client.post(f"/api/collections/{prise['x']}/prendre", headers=ADMIN,
                         json={"documents": [{"document_id": prise["docs"]["d1"],
                                              "reponse": "zero"}]}))["documents"][0]["copie_id"]
    _travailler(client, cx, ADMIN)
    r = _ok(client.post(f"/api/collections/{prise['y']}/prendre", headers=ECRIVAIN,
                        json={"documents": [{"document_id": prise["docs"]["d1"],
                                             "reponse": "amorcer", "album_id": cx,
                                             "cran": "transcription"}]}))
    assert r["documents"][0]["etat"] == "demande"
    (d,) = _ok(client.get(f"/api/collections/{prise['x']}/demandes", headers=PROPRIO))
    assert d["genre"] == "amorcer" and d["apercu"]["copies"]["textes"] == 1
    adm = next(x for x in _ok(client.get("/api/demandes", headers=ADMIN))
               if x["id"] == d["id"])
    assert adm["apercu"]["copies"]["regions"] == 2
    assert LECTRICE  # (décor : la lectrice de X ne reçoit rien — la route est au propriétaire)
    assert client.get(f"/api/collections/{prise['x']}/demandes",
                      headers=LECTRICE).status_code == 403
