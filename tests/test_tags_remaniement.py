"""ANN-8 — supprimer, fusionner, renommer un tag (décision de Hugo du 2026-10-22).

Aucune route ne le faisait : un tag tapé de travers restait dans le vocabulaire, et dans les
propositions de l'Atelier. Trois gestes, deux questions :

- supprimer un tag que plus AUCUNE région ne porte, sur tout le corpus : qui modifie déjà
  le tag (`peut_ecrire_terme`) ;
- le supprimer quand il est posé, le fusionner, le renommer — le REMANIER
  (`peut_remanier_tag`) : tag local, le propriétaire de sa collection et l'administrateur ;
  tag global, l'administrateur seul.

Le décor : deux collections, « Étude A » (c1, album a1, régions r1 et r1b) et « Étude B »
(c2, album a2, région r2). Quatre identités sur c1 : `proprio` (propriétaire), `ecrivain`
(écriture), `lecteur` (lecture) ; l'administrateur voit tout. Personne d'autre que lui ne
lit c2.

Chaque garde est jouée sous l'identité qu'elle concerne, et les effets sont relus EN BASE —
ce que l'API montre ne distingue pas « rien n'a changé » de « changé là où vous ne lisez
pas ».
"""
import json
import sqlite3

import pytest

from conftest import ADMIN

PROPRIO = {"Remote-User": "proprio"}
ECRIVAIN = {"Remote-User": "ecrivain"}
LECTEUR = {"Remote-User": "lecteur"}


def _sql(db_path, sql, params=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        out = [dict(r) for r in c.execute(sql, params)]
        c.commit()
        return out
    finally:
        c.close()


def _tag(db_path, label, collection_id=None):
    c = sqlite3.connect(db_path)
    try:
        tid = c.execute("INSERT INTO tags (label, collection_id) VALUES (?, ?)",
                        (label, collection_id)).lastrowid
        c.commit()
        return tid
    finally:
        c.close()


def _poser(db_path, region_id, *tag_ids, note=""):
    """Pose des tags en SQL — sans journal, donc sans rien qu'un Ctrl+Z puisse trouver."""
    c = sqlite3.connect(db_path)
    try:
        c.execute("INSERT OR IGNORE INTO annotations (region_id, note) VALUES (?, ?)",
                  (region_id, note))
        ann = c.execute("SELECT id FROM annotations WHERE region_id = ?",
                        (region_id,)).fetchone()[0]
        for t in tag_ids:
            c.execute("INSERT OR IGNORE INTO annotation_tags VALUES (?, ?)", (ann, t))
        c.commit()
    finally:
        c.close()


def _porteurs(db_path, tag_id):
    return sorted(r["region_id"] for r in _sql(
        db_path, "SELECT an.region_id FROM annotation_tags at JOIN annotations an "
                 "ON an.id = at.annotation_id WHERE at.tag_id = ?", (tag_id,)))


def _existe(db_path, tag_id):
    return bool(_sql(db_path, "SELECT 1 FROM tags WHERE id = ?", (tag_id,)))


def _evenements(db_path):
    return _sql(db_path, "SELECT type, agent, cible_id, avant, apres FROM evenement "
                         "WHERE cible_table = 'tags' ORDER BY id")


def _trouve(client, mot):
    """Les régions qu'une recherche plein texte du mot rend à l'administrateur."""
    r = client.get("/api/recherche", params={"q": mot}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return sorted(x["region_id"] for x in r.json()["results"])


def _reindexer(client, region_id):
    """L'index d'une région, refait par une écriture ordinaire (une note posée par l'API) :
    les tags posés en SQL n'y sont pas encore."""
    r = client.put(f"/api/regions/{region_id}/annotation", json={"note": "vu"},
                   headers=ADMIN)
    assert r.status_code == 200, r.text


@pytest.fixture
def decor(client, db_path, png_bytes, derriere_proxy):
    ids = {}
    for nom, cle in (("Étude A", "c1"), ("Étude B", "c2")):
        r = client.post("/api/collections", json={"nom": nom}, headers=ADMIN)
        assert r.status_code in (200, 201), r.text
        ids[cle] = r.json()["id"]
    for album, coll, regions in (("a1", "c1", ("r1", "r1b")), ("a2", "c2", ("r2",))):
        a = client.post("/api/albums", json={"titre": album, "collection_id": ids[coll]},
                        headers=ADMIN).json()
        pl = client.post(f"/api/albums/{a['id']}/import", headers=ADMIN,
                         files={"file": ("p.png", png_bytes, "image/png")}).json()
        for k, nom in enumerate(regions):
            r = client.post(f"/api/planches/{pl['id']}/regions", headers=ADMIN,
                            json={"type": "bulle", "x": 10 * k, "y": 0, "w": 9, "h": 9})
            assert r.status_code == 201, r.text
            ids[nom] = r.json()["id"]
    for qui, niveau in (("proprio", "proprietaire"), ("ecrivain", "ecriture"),
                        ("lecteur", "lecture")):
        r = client.put(f"/api/collections/{ids['c1']}/acces", headers=ADMIN, json={
            "genre": "utilisateur", "principal": qui, "niveau": niveau})
        assert r.status_code == 200, r.text
    return ids


def _remaniable(client, qui):
    return {t["label"]: t["remaniable"]
            for t in client.get("/api/lexique", headers=qui).json()["tags"]}


# --------------------------------------------------------------------------- #
# La clé transmise à l'écran : la question, posée tag par tag
# --------------------------------------------------------------------------- #
def test_la_cle_remaniable_suit_la_portee_du_tag(client, db_path, decor):
    _tag(db_path, "global")
    _tag(db_path, "local-a", decor["c1"])
    _tag(db_path, "local-b", decor["c2"])
    assert _remaniable(client, ADMIN) == {"global": True, "local-a": True, "local-b": True}
    assert _remaniable(client, PROPRIO) == {"global": False, "local-a": True}
    assert _remaniable(client, ECRIVAIN) == {"global": False, "local-a": False}
    assert _remaniable(client, LECTEUR) == {"global": False, "local-a": False}


def test_en_mono_poste_tout_se_remanie(client, db_path):
    _tag(db_path, "global")
    lex = client.get("/api/lexique").json()
    assert [t["remaniable"] for t in lex["tags"]] == [True]


# --------------------------------------------------------------------------- #
# Supprimer un tag inutilisé : qui le modifie
# --------------------------------------------------------------------------- #
def test_un_tag_inutilise_se_supprime_par_qui_le_modifie(client, db_path, decor):
    t = _tag(db_path, "fote de frape")
    blanc = client.delete(f"/api/tags/{t}", params={"a_blanc": True}, headers=ECRIVAIN)
    assert blanc.status_code == 200, blanc.text
    assert blanc.json()["regions"] == 0 and _existe(db_path, t)
    assert client.delete(f"/api/tags/{t}", headers=LECTEUR).status_code == 403
    assert _existe(db_path, t)
    r = client.delete(f"/api/tags/{t}", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert not _existe(db_path, t)
    [e] = _evenements(db_path)
    assert (e["type"], e["agent"], e["cible_id"]) == ("suppression", "ecrivain", t)
    assert json.loads(e["avant"])["label"] == "fote de frape"


def test_un_tag_qu_on_ne_voit_pas_est_introuvable(client, db_path, decor):
    t = _tag(db_path, "secret", decor["c2"])
    for qui in (PROPRIO, ECRIVAIN, LECTEUR):
        assert client.delete(f"/api/tags/{t}", headers=qui).status_code == 404
        assert client.put(f"/api/tags/{t}", json={"label": "x"}, headers=qui).status_code == 404
        assert client.post(f"/api/tags/{t}/fusion", json={"cible_id": t + 1},
                           headers=qui).status_code == 404
    assert _existe(db_path, t)


def test_zero_pour_moi_n_est_pas_inutilise(client, db_path, decor):
    """Le piège de `GET /api/tags` : sa fréquence compte les régions LISIBLES. Un tag posé
    seulement dans « Étude B » vaut 0 pour l'écrivain d'« Étude A » — et ne lui est pas
    supprimable pour autant."""
    t = _tag(db_path, "ailleurs")
    _poser(db_path, decor["r2"], t)
    freq = {x["label"]: x["frequence"] for x in client.get("/api/tags", headers=ECRIVAIN).json()}
    assert freq["ailleurs"] == 0
    r = client.delete(f"/api/tags/{t}", headers=ECRIVAIN)
    assert r.status_code == 403
    assert "administrateur" in r.json()["detail"]
    assert _existe(db_path, t) and _porteurs(db_path, t) == [decor["r2"]]


# --------------------------------------------------------------------------- #
# Supprimer un tag utilisé
# --------------------------------------------------------------------------- #
def test_le_proprietaire_supprime_un_tag_local_pose_chez_lui(client, db_path, decor):
    t = _tag(db_path, "zorglub", decor["c1"])
    garde = _tag(db_path, "garde", decor["c1"])
    _poser(db_path, decor["r1"], t)                 # note vide, plus rien après : supprimée
    _poser(db_path, decor["r1b"], t, garde)         # garde un autre tag : reste
    _reindexer(client, decor["r1"])
    assert _trouve(client, "zorglub") == [decor["r1"]]

    blanc = client.delete(f"/api/tags/{t}", params={"a_blanc": True}, headers=PROPRIO)
    assert blanc.status_code == 200, blanc.text
    assert blanc.json()["regions"] == 2
    assert _existe(db_path, t) and _porteurs(db_path, t) == [decor["r1"], decor["r1b"]]

    r = client.delete(f"/api/tags/{t}", headers=PROPRIO)
    assert r.status_code == 200, r.text
    assert r.json()["regions"] == 2
    assert not _existe(db_path, t)
    assert _porteurs(db_path, garde) == [decor["r1b"]]
    # r1 avait reçu la note « vu » de `_reindexer` : son annotation reste.
    assert _sql(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (decor["r1"],))
    assert _trouve(client, "zorglub") == []
    [e] = _evenements(db_path)
    avant = json.loads(e["avant"])
    assert (e["type"], avant["label"], avant["regions"]) == (
        "suppression", "zorglub", [decor["r1"], decor["r1b"]])


def test_une_annotation_videe_disparait(client, db_path, decor):
    t = _tag(db_path, "seul", decor["c1"])
    _poser(db_path, decor["r1"], t)
    assert client.delete(f"/api/tags/{t}", headers=PROPRIO).status_code == 200
    assert not _sql(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (decor["r1"],))
    avant = json.loads(_evenements(db_path)[0]["avant"])
    assert avant["annotations_supprimees"] == [decor["r1"]]


def test_un_tag_utilise_ne_se_supprime_pas_par_un_simple_ecrivain(client, db_path, decor):
    local = _tag(db_path, "local", decor["c1"])
    glob = _tag(db_path, "global")
    _poser(db_path, decor["r1"], local, glob)
    for t in (local, glob):
        for qui in (ECRIVAIN, LECTEUR):
            assert client.delete(f"/api/tags/{t}", params={"a_blanc": True},
                                 headers=qui).status_code == 403
            assert client.delete(f"/api/tags/{t}", headers=qui).status_code == 403
    r = client.delete(f"/api/tags/{glob}", headers=PROPRIO)
    assert r.status_code == 403
    assert "global" in r.json()["detail"]
    assert _porteurs(db_path, local) == [decor["r1"]] == _porteurs(db_path, glob)


def test_le_lecteur_n_apprend_rien_de_l_emploi(client, db_path, decor):
    """La garde « lecture seule » parle AVANT de compter : un tag posé ailleurs et un tag
    inutilisé lui répondent la même phrase."""
    pose = _tag(db_path, "pose", decor["c1"])
    libre = _tag(db_path, "libre", decor["c1"])
    _poser(db_path, decor["r2"], pose)
    reponses = {client.delete(f"/api/tags/{t}", headers=LECTEUR).json()["detail"]
                for t in (pose, libre)}
    assert reponses == {"Ce tag est en lecture seule pour vous."}


def test_un_tag_local_se_pose_hors_de_sa_collection(client, db_path, decor):
    """Le CONSTAT (2026-10-22), joué par la route : qui LIT « Étude A » et ÉCRIT dans
    « Étude B » pose un tag local à A sur une région de B — `_ensure_tags` attache tout tag
    qu'on lit. La prémisse « un tag local n'est porté que dans sa collection » est fausse ;
    d'où la garde `_exiger_tout_ecrit` des deux tests suivants."""
    t = _tag(db_path, "local-a", decor["c1"])
    for coll, niveau in (("c1", "lecture"), ("c2", "ecriture")):
        r = client.put(f"/api/collections/{decor[coll]}/acces", headers=ADMIN, json={
            "genre": "utilisateur", "principal": "passeur", "niveau": niveau})
        assert r.status_code == 200, r.text
    r = client.put(f"/api/regions/{decor['r2']}/annotation",
                   json={"tags_ajoutes": ["local-a"]}, headers={"Remote-User": "passeur"})
    assert r.status_code == 200, r.text
    assert _porteurs(db_path, t) == [decor["r2"]]


def test_un_tag_local_pose_hors_de_sa_collection_reste_a_l_administrateur(
        client, db_path, decor):
    """Le constat : un tag LOCAL à « Étude A » peut être posé sur une région d'« Étude B »
    (ici par l'administrateur ; aussi par quiconque lit A et écrit dans B). Le propriétaire
    de A n'écrit pas dans B : il ne l'en retire pas, ni à blanc — aucun nombre ne lui
    parvient —, et l'administrateur le peut."""
    t = _tag(db_path, "deborde", decor["c1"])
    _poser(db_path, decor["r1"], t)
    _poser(db_path, decor["r2"], t)
    for blanc in (True, False):
        r = client.delete(f"/api/tags/{t}", params={"a_blanc": blanc}, headers=PROPRIO)
        assert r.status_code == 403, r.text
        assert "n'écrivez pas" in r.json()["detail"]
        assert "regions" not in r.json()
    autre = _tag(db_path, "cible", decor["c1"])
    r = client.post(f"/api/tags/{t}/fusion", json={"cible_id": autre, "a_blanc": True},
                    headers=PROPRIO)
    assert r.status_code == 403 and "n'écrivez pas" in r.json()["detail"]
    assert _porteurs(db_path, t) == [decor["r1"], decor["r2"]]

    blanc = client.delete(f"/api/tags/{t}", params={"a_blanc": True}, headers=ADMIN).json()
    assert blanc["regions"] == 2
    assert client.delete(f"/api/tags/{t}", headers=ADMIN).status_code == 200
    assert not _existe(db_path, t)


def test_le_proprietaire_ne_voit_compter_que_ce_qu_il_ecrit(client, db_path, decor):
    """Un album lu par une AUTRE collection que celle du tag, sans y écrire : le compte ne
    lui parvient pas non plus — l'écriture borne, pas la lecture."""
    t = _tag(db_path, "lu", decor["c1"])
    _poser(db_path, decor["r2"], t)
    r = client.put(f"/api/collections/{decor['c2']}/acces", headers=ADMIN, json={
        "genre": "utilisateur", "principal": "proprio", "niveau": "lecture"})
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/tags/{t}", params={"a_blanc": True}, headers=PROPRIO)
    assert r.status_code == 403 and "regions" not in r.json()
    r = client.put(f"/api/collections/{decor['c2']}/acces", headers=ADMIN, json={
        "genre": "utilisateur", "principal": "proprio", "niveau": "ecriture"})
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/tags/{t}", params={"a_blanc": True}, headers=PROPRIO)
    assert r.status_code == 200 and r.json()["regions"] == 1


# --------------------------------------------------------------------------- #
# Fusionner
# --------------------------------------------------------------------------- #
def test_fusionner_reporte_sans_doublon_puis_supprime(client, db_path, decor):
    a = _tag(db_path, "zorglub", decor["c1"])
    b = _tag(db_path, "zorglonde")
    _poser(db_path, decor["r1"], a, b)
    _poser(db_path, decor["r1b"], a)
    _reindexer(client, decor["r1"])
    _reindexer(client, decor["r1b"])
    assert _trouve(client, "zorglub") == [decor["r1"], decor["r1b"]]

    blanc = client.post(f"/api/tags/{a}/fusion", json={"cible_id": b, "a_blanc": True},
                        headers=PROPRIO)
    assert blanc.status_code == 200, blanc.text
    assert (blanc.json()["regions"], blanc.json()["deja"]) == (2, 1)
    assert _existe(db_path, a) and _porteurs(db_path, b) == [decor["r1"]]

    r = client.post(f"/api/tags/{a}/fusion", json={"cible_id": b}, headers=PROPRIO)
    assert r.status_code == 200, r.text
    assert r.json()["cible"] == {"id": b, "label": "zorglonde"}
    assert not _existe(db_path, a)
    assert _porteurs(db_path, b) == [decor["r1"], decor["r1b"]]
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM annotation_tags WHERE tag_id = ?",
                (b,))[0]["n"] == 2
    assert _trouve(client, "zorglub") == []
    assert _trouve(client, "zorglonde") == [decor["r1"], decor["r1b"]]
    [e] = _evenements(db_path)
    assert (e["type"], e["agent"], e["cible_id"]) == ("fusion", "proprio", a)
    apres = json.loads(e["apres"])
    assert (apres["cible_id"], apres["label"], apres["deja"]) == (b, "zorglonde",
                                                                  [decor["r1"]])


def test_fusionner_ne_cache_pas_un_tag(client, db_path, decor):
    """La cible est globale, ou de la même collection — même pour l'administrateur."""
    glob = _tag(db_path, "global")
    a = _tag(db_path, "dans-a", decor["c1"])
    b = _tag(db_path, "dans-b", decor["c2"])
    a2 = _tag(db_path, "aussi-a", decor["c1"])
    for source, cible in ((glob, a), (a, b)):
        r = client.post(f"/api/tags/{source}/fusion", json={"cible_id": cible, "a_blanc": True},
                        headers=ADMIN)
        assert r.status_code == 409, r.text
        assert "cacherait" in r.json()["detail"]
    for source, cible in ((a, a2), (a2, glob)):
        r = client.post(f"/api/tags/{source}/fusion", json={"cible_id": cible, "a_blanc": True},
                        headers=ADMIN)
        assert r.status_code == 200, r.text


def test_qui_fusionne(client, db_path, decor):
    glob = _tag(db_path, "global")
    glob2 = _tag(db_path, "global-deux")
    a = _tag(db_path, "local", decor["c1"])
    secret = _tag(db_path, "secret", decor["c2"])
    corps = {"cible_id": glob, "a_blanc": True}
    assert client.post(f"/api/tags/{a}/fusion", json=corps, headers=LECTEUR).json()[
        "detail"] == "Ce tag est en lecture seule pour vous."
    r = client.post(f"/api/tags/{a}/fusion", json=corps, headers=ECRIVAIN)
    assert r.status_code == 403 and "propriétaire" in r.json()["detail"]
    r = client.post(f"/api/tags/{glob2}/fusion", json=corps, headers=PROPRIO)
    assert r.status_code == 403 and "global" in r.json()["detail"]
    assert client.post(f"/api/tags/{a}/fusion", json=corps, headers=PROPRIO).status_code == 200
    assert client.post(f"/api/tags/{a}/fusion", json={"cible_id": secret},
                       headers=PROPRIO).status_code == 404
    assert client.post(f"/api/tags/{a}/fusion", json={"cible_id": a},
                       headers=PROPRIO).status_code == 422
    assert client.post(f"/api/tags/{glob2}/fusion", json=corps, headers=ADMIN).status_code == 200
    assert _existe(db_path, a) and _existe(db_path, glob2)      # tout était à blanc


# --------------------------------------------------------------------------- #
# Renommer
# --------------------------------------------------------------------------- #
def test_renommer_sur_place_et_reindexer(client, db_path, decor):
    t = _tag(db_path, "zorglub", decor["c1"])
    _poser(db_path, decor["r1"], t)
    _reindexer(client, decor["r1"])
    r = client.put(f"/api/tags/{t}", json={"label": "  Zorg’Lub  "}, headers=PROPRIO)
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "zorg'lub" and r.json()["id"] == t
    assert _porteurs(db_path, t) == [decor["r1"]]
    assert _trouve(client, "zorglub") == []
    assert _trouve(client, "lub") == [decor["r1"]]
    [e] = _evenements(db_path)
    assert (e["type"], json.loads(e["avant"])["label"], json.loads(e["apres"])["label"]) == (
        "modification", "zorglub", "zorg'lub")
    # Rien à changer : rien au journal.
    assert client.put(f"/api/tags/{t}", json={"label": "ZORG'LUB"},
                      headers=PROPRIO).status_code == 200
    assert len(_evenements(db_path)) == 1


def test_renommer_vers_un_libelle_pris_est_une_fusion(client, db_path, decor):
    t = _tag(db_path, "colere", decor["c1"])
    _tag(db_path, "colère")
    _tag(db_path, "cachee", decor["c2"])
    r = client.put(f"/api/tags/{t}", json={"label": "Colère"}, headers=PROPRIO)
    assert r.status_code == 409
    assert "« colère »" in r.json()["detail"] and "fusion" in r.json()["detail"]
    r = client.put(f"/api/tags/{t}", json={"label": "cachee"}, headers=PROPRIO)
    assert r.status_code == 409
    assert r.json()["detail"] == "Ce libellé de tag est déjà pris : choisissez-en un autre."
    assert _sql(db_path, "SELECT label FROM tags WHERE id = ?", (t,))[0]["label"] == "colere"


def test_un_tag_d_avant_se_renomme_vers_sa_propre_cle(client, db_path, decor):
    t = _tag(db_path, "c’est pluriel")
    r = client.put(f"/api/tags/{t}", json={"label": "c'est pluriel"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "c'est pluriel"


def test_qui_renomme(client, db_path, decor):
    glob = _tag(db_path, "global")
    a = _tag(db_path, "local", decor["c1"])
    for qui, attendu in ((LECTEUR, 403), (ECRIVAIN, 403)):
        assert client.put(f"/api/tags/{a}", json={"label": "x"},
                          headers=qui).status_code == attendu
    r = client.put(f"/api/tags/{glob}", json={"label": "x"}, headers=PROPRIO)
    assert r.status_code == 403 and "global" in r.json()["detail"]
    assert client.put(f"/api/tags/{a}", json={"label": "  "},
                      headers=PROPRIO).status_code == 422
    assert client.put(f"/api/tags/{glob}", json={"label": "monde"},
                      headers=ADMIN).status_code == 200
    assert client.put(f"/api/tags/{a}", json={"label": "chez moi"},
                      headers=PROPRIO).status_code == 200


# --------------------------------------------------------------------------- #
# Hors de Ctrl+Z
# --------------------------------------------------------------------------- #
def test_ctrl_z_ne_defait_aucun_remaniement(client, db_path, decor):
    a = _tag(db_path, "un", decor["c1"])
    b = _tag(db_path, "deux", decor["c1"])
    c = _tag(db_path, "trois", decor["c1"])
    _poser(db_path, decor["r1"], a, c)
    assert client.post(f"/api/tags/{a}/fusion", json={"cible_id": b},
                       headers=PROPRIO).status_code == 200
    assert client.put(f"/api/tags/{b}", json={"label": "quatre"},
                      headers=PROPRIO).status_code == 200
    assert client.delete(f"/api/tags/{c}", headers=PROPRIO).status_code == 200
    assert len(_evenements(db_path)) == 3
    assert client.get("/api/undo/prochain", headers=PROPRIO).json() is None


def test_ranger_le_vocabulaire_ne_donne_ni_rang_ni_acte(client, db_path, decor):
    """Qui n'a fait que remanier des tags ne prend pas de pseudonyme (il décalerait ceux
    qui annotent après lui) et ne « laisse » aucun acte en partant : rien n'est orphelin."""
    import _commun
    import comptes
    t = _tag(db_path, "seul", decor["c1"])
    _poser(db_path, decor["r1"], t)
    assert client.put(f"/api/tags/{t}", json={"label": "unique"},
                      headers=PROPRIO).status_code == 200
    assert client.delete(f"/api/tags/{t}", headers=PROPRIO).status_code == 200
    assert len(_evenements(db_path)) == 2
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert "proprio" not in _commun.pseudonymes(conn)
        assert "proprio" not in comptes.traces(conn)[0]
    finally:
        conn.close()
