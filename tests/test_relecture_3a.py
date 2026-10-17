"""COL-3, écran de la 3a — défauts prouvés par la relecture croisée (2026-10-17).

Chaque test ÉCHOUE sur `4ade217` et dit ce qu'il attend. Ils ne corrigent rien : ils sont la
preuve, et le correctif reste à écrire.

1. Un RETOUR reste en attente quand sa copie quitte le fonds par un chemin qui ne le clôt
   pas — ici l'acceptation d'un `rejoindre` déposé avant que la copie parte au fonds. « À
   faire » montre alors « Rendre à … » sur une copie déjà rangée : « Rendre » répond 409,
   « Garder au fonds » écrit « refusée » au responsable alors que la copie est sortie.
   (`_accepter_un_rejoindre`, `_faire_entrer` et `tools/gerer_collections.py` rangent sans
   appeler `_clore_retours_d_une_copie_rangee`.)
2. Un retour clos parce que l'administrateur a rangé la copie AILLEURS que la collection
   demandée se lit, dans la fiche du projet, « Rendre … à « base » — acceptée » : la vue
   garde la collection demandée, pas celle où la copie est entrée.
3. Le cliquet des sorties d'identité ne voit pas `…/acces-du-projet` : son balayage
   l'appelle sur une collection qui n'est pas une base, où `lignes` est vide. Sur une base,
   la route rend des logins, et aucune déclaration ne le dit.
4. Le verdict de départ d'un responsable, seul propriétaire (par le projet) de la base, dit
   « rien à orpheliner ».
"""
from conftest import ADMIN
from test_ecran_3a import _gardee, _rendre
from test_prendre import (ECRIVAIN, PROPRIO, RESP, _collections_de, _copie_dans, _prendre,
                          _repondre, prise)  # noqa: F401
from test_projets import _sql
from test_sorties_identite import seme  # noqa: F401


def test_un_retour_se_clot_quand_un_rejoindre_accepte_sort_la_copie_du_fonds(
        client, prise, db_path):
    cx = _copie_dans(client, prise, "d3", prise["x"])
    r = _prendre(client, prise["y"], [{"document_id": prise["docs"]["d3"],
                                       "reponse": "rejoindre", "album_id": cx}], ECRIVAIN)
    (rejoindre,) = r.json()["documents"]
    assert rejoindre["etat"] == "demande", rejoindre
    assert client.delete(f"/api/albums/{cx}/collections/{prise['x']}",
                         headers=PROPRIO).status_code == 204
    retour = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]
    assert retour["etat"] == "demande", retour
    assert _repondre(client, rejoindre["demande_id"], "acceptee").status_code == 200
    assert _collections_de(db_path, cx) == {prise["y"]}, "la copie a quitté le fonds"
    etat = _sql(db_path, "SELECT reponse FROM demande WHERE id = ?",
                (retour["demande_id"],))[0]["reponse"]
    assert etat is not None, (
        "le retour attend encore sur une copie qui n'est plus au fonds : « À faire » offre "
        "« Rendre à … » (qui répondra 409) et « Garder au fonds » (qui dira « refusée »)")


def test_un_retour_clos_par_un_rangement_ailleurs_ne_dit_pas_la_collection_demandee(
        client, prise, db_path):
    cx = _gardee(client, prise)
    demande = _rendre(client, prise, cx, prise["base"]).json()["documents"][0]["demande_id"]
    assert client.put(f"/api/albums/{cx}/collections/{prise['y']}",
                      headers=ADMIN).status_code == 201
    assert _collections_de(db_path, cx) == {prise["y"]}
    vue = {d["id"]: d for d in client.get(f"/api/projets/{prise['projet']}/demandes",
                                          headers=RESP).json()}[demande]
    assert not (vue["reponse"] == "acceptee" and vue["collection_id"] == prise["base"]), (
        "la fiche du projet dit « Rendre … à « Étude P » — acceptée » alors que la copie est "
        f"entrée dans la collection {prise['y']} : {vue}")


def test_le_cliquet_des_sorties_voit_l_acces_du_projet(client, seme):
    import test_sorties_identite as tsi
    conn_base = _sql(seme["db"], "SELECT id FROM collection WHERE base = 1 AND "
                                 "COALESCE(projet_id, (SELECT id FROM projet WHERE repli = 1)) "
                                 "= ?", (seme["projet_id"],))
    assert conn_base, "le projet du semis a une base"
    # La base du repli naît PROTÉGÉE (rien ne s'ouvre au déploiement) : son membre n'y
    # entre pas. Qu'elle soit ouverte, comme toute base créée par l'écran, et le login sort.
    assert client.put(f"/api/projets/{seme['projet_id']}/acces-membres", headers=seme["ident"],
                      json={"acces_membres": "ecriture"}).status_code == 200
    r = client.get(f"/api/collections/{conn_base[0]['id']}/acces-du-projet",
                   headers=seme["ident"])
    assert r.status_code == 200, r.text
    assert tsi.SENTINELLES["login"] in r.text, "sur une base, la route rend des logins"
    assert ("route", "/api/collections/{collection_id}/acces-du-projet") \
        in tsi.SORTIES_DECLAREES, (
            "la route rend des logins sur une base, et le balayage ne l'appelle que sur une "
            "collection ordinaire : la sortie n'est ni vue ni déclarée")


def test_le_verdict_d_un_responsable_seul_proprietaire_de_la_base(client, prise):
    vue = client.get("/api/comptes-et-groupes", headers=ADMIN).json()
    resp = next(c for c in vue["comptes"] if c["login"] == "resp")
    base = next(c for c in vue["collections"] if c["id"] == prise["base"])
    assert [p["login"] for p in base["proprietaires"]] == ["resp"]
    assert resp["verdict"] != "rien à orpheliner", (
        "seul propriétaire de la base (par le projet), et le verdict de départ dit qu'il "
        "n'orphelinerait rien")
