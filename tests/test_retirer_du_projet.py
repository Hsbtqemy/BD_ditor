"""COL-3, tranche 3b — « Retirer du projet », le geste du responsable (Hugo, 2026-10-21).

Le scénario de Hugo : un album entré par erreur (contenu, qualité, contexte), déjà pris et
travaillé dans plusieurs collections. Le responsable du projet — et l'administrateur — lui
fait quitter TOUTES les collections du projet, quels qu'en soient les propriétaires ; il part
au fonds AVEC son travail, comme sorti de sa dernière collection, et un administrateur le
rend. Les propriétaires le voient disparaître ; le journal dit qui l'a retiré. Refusé dans un
bac à sable et sur le jeu.

Le décor est celui de `test_qui_efface` : B1, une copie de L'Oreille cassée née dans la
base d'Étude P (créée par `membre`) et rangée aussi dans la Collection X, que `proprio`
possède — `resp` gère Étude P.
"""
import database
from conftest import ADMIN
from test_prendre import (ECRIVAIN, LECTRICE, MEMBRE, PERSONNE, PROPRIO, RESP,
                          prise)  # noqa: F401
from test_projets import _sql
from test_qui_efface import RESP2, efface  # noqa: F401


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _retirer(client, album_id, qui):
    return client.post(f"/api/albums/{album_id}/retirer-du-projet", headers=qui)


def _collections(db, album_id):
    return sorted(r["collection_id"] for r in _sql(
        db, "SELECT collection_id FROM collection_album WHERE album_id = ?", (album_id,)))


def test_le_responsable_retire_un_album_de_toutes_les_collections_du_projet(client, efface):
    db, b1 = efface["db"], efface["b1"]
    travail_avant = _sql(db, "SELECT COUNT(*) AS n FROM planches WHERE album_id = ?", (b1,))
    rendu = _ok(_retirer(client, b1, RESP))
    assert rendu == {"album_id": b1, "projet_id": efface["projet"],
                     "collections": sorted([efface["base"], efface["x"]]), "au_fonds": True}
    assert _collections(db, b1) == []
    # Gardé au fonds, avec son travail, et son projet écrit sur lui.
    assert _sql(db, "SELECT projet_id FROM albums WHERE id = ?", (b1,))[0]["projet_id"] == \
        efface["projet"]
    assert _sql(db, "SELECT COUNT(*) AS n FROM planches WHERE album_id = ?", (b1,)) == \
        travail_avant
    # Les propriétaires le voient disparaître ; l'administrateur le voit au fonds.
    for qui in (PROPRIO, ECRIVAIN, MEMBRE, RESP):
        assert b1 not in {a["id"] for a in client.get("/api/albums", headers=qui).json()}, qui
    a = next(x for x in client.get("/api/albums", headers=ADMIN).json() if x["id"] == b1)
    assert a["au_fonds"] is True


def test_le_journal_dit_qui_l_a_retire(client, efface):
    db, b1 = efface["db"], efface["b1"]
    _ok(_retirer(client, b1, RESP))
    fins = _sql(db, "SELECT agent, json_extract(avant, '$.collection_id') AS c FROM evenement "
                    "WHERE cible_table = 'collection_album' AND type = 'delien' "
                    "AND json_extract(avant, '$.album_id') = ? ORDER BY id", (b1,))
    assert fins == [{"agent": "resp", "c": c} for c in sorted([efface["base"], efface["x"]])]
    (acte,) = _sql(db, "SELECT agent, cible_table, "
                       "json_extract(apres, '$.retire_du_projet.projet_id') AS projet "
                       "FROM evenement WHERE json_extract(apres, '$.retire_du_projet') "
                       "IS NOT NULL")
    assert acte == {"agent": "resp", "cible_table": "document", "projet": efface["projet"]}
    fonds = _ok(client.get("/api/fonds", headers=ADMIN))
    copie = next(c for d in fonds["documents"] for c in d["copies"] if c["album_id"] == b1)
    assert (copie["retire_du_projet"]["par"], copie["collections"]) == ("resp", [])


def test_un_administrateur_le_rend(client, efface):
    """La copie emporte son projet — écrit sur elle avant de sortir, même quand rien ne
    l'avait écrit (une copie d'avant le fonds) —, et ne revient que dans ce projet. Rendue
    puis sortie autrement, le fonds ne la dit plus retirée."""
    db, b1 = efface["db"], efface["b1"]
    _sql(db, "UPDATE albums SET projet_id = NULL WHERE id = ?", (b1,))
    _ok(_retirer(client, b1, RESP))
    assert _sql(db, "SELECT projet_id FROM albums WHERE id = ?", (b1,))[0]["projet_id"] == \
        efface["projet"]
    autre = database.collection_de_base(database.get_connection(), efface["repli"])
    assert client.put(f"/api/albums/{b1}/collections/{autre}", headers=ADMIN).status_code == 409
    r = client.put(f"/api/albums/{b1}/collections/{efface['x']}", headers=ADMIN)
    assert r.status_code == 201, r.text
    assert _collections(db, b1) == [efface["x"]]
    assert client.delete(f"/api/albums/{b1}/collections/{efface['x']}",
                         headers=PROPRIO).status_code == 204
    fonds = _ok(client.get("/api/fonds", headers=ADMIN))
    copie = next(c for d in fonds["documents"] for c in d["copies"] if c["album_id"] == b1)
    assert (copie["collections"], copie["retire_du_projet"]) == ([], None)


def test_seul_qui_gere_le_projet_retire(client, efface):
    """`proprio` possède X, où vit B1 ; `membre` l'a créée ; `ecrivain` et `lectrice` le
    lisent par X : 403 nommé, rien ne bouge. Qui ne le lit pas — `resp2`, `personne` — : 404,
    le même qu'un album absent."""
    db, b1 = efface["db"], efface["b1"]
    for qui in (PROPRIO, MEMBRE, ECRIVAIN, LECTRICE):
        r = _retirer(client, b1, qui)
        assert r.status_code == 403, (qui, r.text)
    for qui in (RESP2, PERSONNE):
        r, absent = _retirer(client, b1, qui), _retirer(client, 999999, qui)
        assert (r.status_code, absent.status_code) == (404, 404), qui
    assert _collections(db, b1) == sorted([efface["base"], efface["x"]])
    _ok(_retirer(client, b1, ADMIN))


def test_une_demande_de_rejoindre_ou_d_en_partir_se_clot(client, efface):
    """Partie au fonds, la copie ne se rejoint plus et on n'en part plus : les demandes qui
    la visaient se closent refusées, comme quand elle sort de sa dernière collection."""
    db, b1 = efface["db"], efface["b1"]
    r = client.put(f"/api/albums/{b1}/collections/{efface['y']}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text
    demande = r.json()["demande_id"]
    _ok(_retirer(client, b1, RESP))
    assert _sql(db, "SELECT reponse FROM demande WHERE id = ?",
                (demande,))[0]["reponse"] == "refusee"


def test_deja_au_fonds_on_ne_le_retire_pas_deux_fois(client, efface):
    _ok(_retirer(client, efface["b1"], RESP))
    assert _retirer(client, efface["b1"], ADMIN).status_code == 409


def test_ni_dans_un_bac_a_sable_ni_sur_le_jeu(client, efface, db_path):
    """Dans un bac à sable, rien ne part au fonds ; le jeu ne se change que par son outil. Le
    même refus pour son propriétaire et pour l'administrateur."""
    lea = {"Remote-User": "lea"}
    bac = _ok(client.post("/api/bac-a-sable", headers=lea), 201)
    a = _ok(client.post("/api/albums", headers=lea,
                        json={"titre": "Au bac", "collection_id": bac["base"]["id"]}), 201)["id"]
    assert _retirer(client, a, lea).status_code == 409
    _sql(db_path, "UPDATE projet SET jeu = 1 WHERE id = ?", (efface["projet"],))
    assert _retirer(client, efface["b1"], ADMIN).status_code == 409
