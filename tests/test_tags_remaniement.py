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

from conftest import du_projet
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
        du_projet(client, ids['c1'], "utilisateur", qui, headers=ADMIN)
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


def test_un_tag_local_ne_se_pose_plus_hors_de_sa_collection(client, db_path, decor):
    """Le CONSTAT du 2026-10-22 — qui LIT « Étude A » et ÉCRIT dans « Étude B » posait un
    tag local à A sur une région de B — est fermé à la saisie (décision de Hugo du même
    jour) : 422 qui nomme le tag et sa collection, rien n'est posé, la note envoyée avec lui
    non plus. Sous toute portée : c'est une propriété des données."""
    t = _tag(db_path, "local-a", decor["c1"])
    for coll, niveau in (("c1", "lecture"), ("c2", "ecriture")):
        du_projet(client, decor[coll], "utilisateur", "passeur", headers=ADMIN)
        r = client.put(f"/api/collections/{decor[coll]}/acces", headers=ADMIN, json={
            "genre": "utilisateur", "principal": "passeur", "niveau": niveau})
        assert r.status_code == 200, r.text
    for qui in ({"Remote-User": "passeur"}, ADMIN):
        for corps in ({"note": "n", "tags_ajoutes": ["local-a"]},
                      {"note": "n", "tags": ["local-a"]}):
            r = client.put(f"/api/regions/{decor['r2']}/annotation", json=corps, headers=qui)
            assert r.status_code == 422, r.text
            assert r.json()["detail"] == ("Le tag « local-a » est propre à la collection "
                                          "« Étude A » : il ne se pose que sur les albums "
                                          "qu'elle range.")
    assert _porteurs(db_path, t) == []
    assert not _sql(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (decor["r2"],))
    # Sur un album de sa collection, il se pose.
    r = client.put(f"/api/regions/{decor['r1']}/annotation",
                   json={"tags_ajoutes": ["local-a"]}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert _porteurs(db_path, t) == [decor["r1"]]


def test_ce_qui_est_deja_pose_hors_de_sa_collection_reste(client, db_path, decor):
    """L'existant n'est pas refusé : une liste renvoyée entière, qui le contient, passe ; il
    se retire ; il ne revient pas une fois retiré."""
    t = _tag(db_path, "ancien-a", decor["c1"])
    _poser(db_path, decor["r2"], t, note="n")
    r = client.put(f"/api/regions/{decor['r2']}/annotation", headers=ADMIN,
                   json={"note": "m", "tags": ["ancien-a"]})
    assert r.status_code == 200, r.text
    assert _porteurs(db_path, t) == [decor["r2"]]
    r = client.put(f"/api/regions/{decor['r2']}/annotation", headers=ADMIN,
                   json={"tags_retires": ["ancien-a"]})
    assert r.status_code == 200, r.text
    r = client.put(f"/api/regions/{decor['r2']}/annotation", headers=ADMIN,
                   json={"tags_ajoutes": ["ancien-a"]})
    assert r.status_code == 422, r.text


def test_l_atelier_ne_propose_que_les_tags_qui_se_posent_sur_l_album(client, db_path, decor):
    """`GET /api/tags?album=` : les tags globaux et ceux d'une collection qui range l'album.
    Sans `album`, la liste reste celle de la portée (la Recherche, l'Exploration)."""
    _tag(db_path, "global")
    _tag(db_path, "local-a", decor["c1"])
    _tag(db_path, "local-b", decor["c2"])
    labels = lambda url, qui=ADMIN: {t["label"] for t in client.get(url, headers=qui).json()}
    a1 = _sql(db_path, "SELECT album_id FROM collection_album WHERE collection_id = ?",
              (decor["c1"],))[0]["album_id"]
    a2 = _sql(db_path, "SELECT album_id FROM collection_album WHERE collection_id = ?",
              (decor["c2"],))[0]["album_id"]
    assert labels(f"/api/tags?album={a1}") == {"global", "local-a"}
    assert labels(f"/api/tags?album={a2}") == {"global", "local-b"}
    assert labels("/api/tags") == {"global", "local-a", "local-b"}
    assert labels(f"/api/tags?album={a1}", ECRIVAIN) == {"global", "local-a"}
    assert client.get(f"/api/tags?album={a2}", headers=ECRIVAIN).status_code == 404


def test_l_outil_dit_l_existant_sans_rien_ecrire(client, db_path, decor):
    """`tools/tags_hors_collection.py` : à blanc, en lecture seule ; il nomme le tag, sa
    collection et l'album, et compte les régions."""
    import subprocess
    import sys
    from pathlib import Path
    racine = Path(__file__).resolve().parent.parent
    env = {**__import__("os").environ, "BD_DB_PATH": str(db_path)}
    outil = [sys.executable, str(racine / "tools" / "tags_hors_collection.py")]
    p = subprocess.run(outil, env=env, capture_output=True, cwd=str(racine))
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    assert "Aucun tag local" in p.stderr.decode("utf-8")
    t = _tag(db_path, "deborde-a", decor["c1"])
    _poser(db_path, decor["r2"], t)
    _poser(db_path, decor["r1"], t)
    avant = _sql(db_path, "SELECT COUNT(*) AS n FROM annotation_tags")[0]["n"]
    p = subprocess.run(outil, env=env, capture_output=True, cwd=str(racine))
    sortie = p.stderr.decode("utf-8")
    assert p.returncode == 0, sortie
    assert "« deborde-a »" in sortie and "« Étude A »" in sortie
    assert "1 région(s), 1 album(s)" in sortie and "« a2 »" in sortie
    assert "« a1 »" not in sortie
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM annotation_tags")[0]["n"] == avant


def test_un_tag_local_pose_hors_de_sa_collection_reste_a_l_administrateur(
        client, db_path, decor):
    """L'existant : un tag LOCAL à « Étude A » posé sur une région d'« Étude B » (avant la
    garde de pose du 2026-10-22, ou par un album retiré de A — ici en SQL). Le propriétaire
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
    du_projet(client, decor['c2'], "utilisateur", "proprio", headers=ADMIN)
    r = client.put(f"/api/collections/{decor['c2']}/acces", headers=ADMIN, json={
        "genre": "utilisateur", "principal": "proprio", "niveau": "lecture"})
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/tags/{t}", params={"a_blanc": True}, headers=PROPRIO)
    assert r.status_code == 403 and "regions" not in r.json()
    du_projet(client, decor['c2'], "utilisateur", "proprio", headers=ADMIN)
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
    """Un tag POSÉ se renomme par qui le remanie (le lecteur et l'écrivain : 403)."""
    glob = _tag(db_path, "global")
    a = _tag(db_path, "local", decor["c1"])
    _poser(db_path, decor["r1"], glob, a)
    for qui in (LECTEUR, ECRIVAIN):
        assert client.put(f"/api/tags/{a}", json={"label": "x"},
                          headers=qui).status_code == 403
    r = client.put(f"/api/tags/{a}", json={"label": "x"}, headers=ECRIVAIN)
    assert "propriétaire" in r.json()["detail"]
    r = client.put(f"/api/tags/{glob}", json={"label": "x"}, headers=PROPRIO)
    assert r.status_code == 403 and "global" in r.json()["detail"]
    assert client.put(f"/api/tags/{a}", json={"label": "  "},
                      headers=PROPRIO).status_code == 422
    assert client.put(f"/api/tags/{glob}", json={"label": "monde"},
                      headers=ADMIN).status_code == 200
    assert client.put(f"/api/tags/{a}", json={"label": "chez moi"},
                      headers=PROPRIO).status_code == 200


def test_un_tag_inutilise_se_renomme_par_qui_le_modifie(client, db_path, decor):
    """Décision de la session de pilotage (2026-10-22) : renommer un tag que plus aucune
    région ne porte, sur TOUT le corpus, suit la suppression d'un tag inutilisé —
    `peut_ecrire_terme` suffit. Posé ailleurs, il reste à qui le remanie."""
    glob = _tag(db_path, "fote globale")
    loc = _tag(db_path, "fote locale", decor["c1"])
    assert client.put(f"/api/tags/{glob}", json={"label": "x"},
                      headers=LECTEUR).status_code == 403
    for t, nouveau in ((glob, "faute globale"), (loc, "faute locale")):
        r = client.put(f"/api/tags/{t}", json={"label": nouveau}, headers=ECRIVAIN)
        assert r.status_code == 200, r.text
        assert r.json()["label"] == nouveau
    ailleurs = _tag(db_path, "ailleurs")
    _poser(db_path, decor["r2"], ailleurs)
    freq = {x["label"]: x["frequence"] for x in client.get("/api/tags", headers=ECRIVAIN).json()}
    assert freq["ailleurs"] == 0
    r = client.put(f"/api/tags/{ailleurs}", json={"label": "autre"}, headers=ECRIVAIN)
    assert r.status_code == 403, r.text
    assert _sql(db_path, "SELECT label FROM tags WHERE id = ?", (ailleurs,))[0]["label"] == "ailleurs"


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


# --------------------------------------------------------------------------- #
# Ctrl+Z d'un geste d'ANNOTATION fait avant un remaniement (relecture croisée,
# 2026-10-22) : l'annulation ne crée plus jamais de tag
# --------------------------------------------------------------------------- #
AUTRE = {"Remote-User": "autre"}


def _autre_sur_c2(client, decor):
    du_projet(client, decor['c2'], "utilisateur", "autre", headers=ADMIN)
    r = client.put(f"/api/collections/{decor['c2']}/acces", headers=ADMIN, json={
        "genre": "utilisateur", "principal": "autre", "niveau": "ecriture"})
    assert r.status_code == 200, r.text


def _labels_vus(client, qui):
    return {t["label"] for t in client.get("/api/tags", headers=qui).json()}


def _poser_puis_retirer(client, decor, label):
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"note": "n", "tags_ajoutes": [label]})
    assert r.status_code == 200, r.text
    assert label in [t["label"] for t in r.json()["tags"]], r.json()
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"tags_retires": [label]})
    assert r.status_code == 200, r.text


def _porte(client, decor, region="r1"):
    return sorted(x["label"] for x in client.get(
        f"/api/regions/{decor[region]}/annotation", headers=ADMIN).json()["tags"])


def test_ctrl_z_apres_renommage_rend_le_tag_sous_son_nouveau_nom(client, db_path, decor):
    """Reproduction de la relecture : Ctrl+Z d'un retrait fait avant le renommage recréait
    l'ancien libellé LOCAL en tag GLOBAL — visible de qui ne lit pas sa collection."""
    _autre_sur_c2(client, decor)
    t = _tag(db_path, "secret-a", decor["c1"])
    _poser_puis_retirer(client, decor, "secret-a")
    assert "secret-a" not in _labels_vus(client, AUTRE)
    assert client.put(f"/api/tags/{t}", json={"label": "public-a"},
                      headers=PROPRIO).status_code == 200
    r = client.post("/api/undo", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert "secret-a" not in _labels_vus(client, AUTRE)
    assert _sql(db_path, "SELECT id, label, collection_id FROM tags WHERE label LIKE '%-a'") \
        == [{"id": t, "label": "public-a", "collection_id": decor["c1"]}]
    assert _porte(client, decor) == ["public-a"]


def test_ctrl_z_ne_ressuscite_pas_un_tag_supprime_expres(client, db_path, decor):
    """Le retrait annulé ne portait que sur un tag supprimé depuis : rien à rétablir, l'acte
    est PASSÉ (seconde phrase d'AUTH-14), et aucun tag ne renaît — pas même si un tag du
    même nom a été recréé entre-temps : ce n'est pas lui."""
    t = _tag(db_path, "fote", decor["c1"])
    _poser_puis_retirer(client, decor, "fote")
    assert client.delete(f"/api/tags/{t}", headers=PROPRIO).status_code == 200
    neuf = _tag(db_path, "fote")                           # un autre, du même nom
    r = client.post("/api/undo", headers=ECRIVAIN)
    assert r.status_code == 409, r.text
    assert "ne peut plus être rétabli" in r.json()["detail"]["message"]
    assert _sql(db_path, "SELECT id FROM tags WHERE label = 'fote'") == [{"id": neuf}]
    assert _porte(client, decor) == []


def test_ctrl_z_d_un_ajout_apres_fusion_retire_la_cible(client, db_path, decor):
    """L'ajout annulé avait posé « doublon », fusionné depuis dans « garde » : c'est
    « garde » qui part — et lui seul si la région le portait déjà avant l'acte."""
    a = _tag(db_path, "doublon", decor["c1"])
    b = _tag(db_path, "garde", decor["c1"])
    c = _tag(db_path, "avant", decor["c1"])
    _poser(db_path, decor["r1b"], c)
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"note": "n", "tags_ajoutes": ["doublon"]})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/tags/{a}/fusion", json={"cible_id": b},
                       headers=PROPRIO).status_code == 200
    r = client.post("/api/undo", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert "garde" not in _porte(client, decor)
    assert not _sql(db_path, "SELECT 1 FROM tags WHERE label = 'doublon'")


def test_ctrl_z_d_un_ajout_ne_retire_pas_ce_qui_etait_deja_la(client, db_path, decor):
    """La région portait déjà « garde » ; l'acte a ajouté « doublon », fusionné depuis dans
    « garde ». Défaire l'ajout ne retire rien : « garde » était là avant l'acte."""
    a = _tag(db_path, "doublon", decor["c1"])
    b = _tag(db_path, "garde", decor["c1"])
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ADMIN,
                   json={"note": "n", "tags_ajoutes": ["garde"]})
    assert r.status_code == 200, r.text
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"tags_ajoutes": ["doublon"]})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/tags/{a}/fusion", json={"cible_id": b},
                       headers=PROPRIO).status_code == 200
    assert client.post("/api/undo", headers=ECRIVAIN).status_code == 200
    assert _porte(client, decor) == ["garde"]


def test_ctrl_z_d_une_suppression_de_region_ne_rend_que_les_tags_vivants(
        client, db_path, decor):
    """La région revient ; son tag renommé revient sous son nouveau nom, son tag supprimé ne
    revient pas et se compte à part (`tags_non_rendus`) ; `liens_non_rendus` garde son
    sens — les liens de la région (locuteur, personnage, attributs)."""
    renomme = _tag(db_path, "ancien", decor["c1"])
    parti = _tag(db_path, "parti", decor["c1"])
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ADMIN,
                   json={"note": "n", "tags": ["ancien", "parti"]})
    assert r.status_code == 200, r.text
    assert client.delete(f"/api/regions/{decor['r1']}", headers=ECRIVAIN).status_code in (200, 204)
    assert client.put(f"/api/tags/{renomme}", json={"label": "nouveau"},
                      headers=PROPRIO).status_code == 200
    assert client.delete(f"/api/tags/{parti}", headers=PROPRIO).status_code == 200
    r = client.post("/api/undo", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert r.json()["tags_non_rendus"] == 1 and r.json()["liens_non_rendus"] == 0
    assert _porte(client, decor) == ["nouveau"]
    assert not _sql(db_path, "SELECT 1 FROM tags WHERE label IN ('ancien', 'parti')")


# --------------------------------------------------------------------------- #
# L'index : les TAGS seuls, sans analyse de langue (relecture croisée, 2026-10-22)
# --------------------------------------------------------------------------- #
def _ligne_fts(db_path, region_id):
    return _sql(db_path, "SELECT rowid, tags_concat, lemmes FROM recherche "
                         "WHERE region_id = ?", (region_id,))


def test_remanier_ne_reecrit_que_les_tags_de_l_index(client, db_path, decor):
    """Les lemmes et les tokens ne bougent pas : ni analyse refaite, ni modèle substitué.
    On le voit à un lemme posé à la main, qu'une réindexation complète effacerait, et aux
    identifiants des tokens, qu'elle régénérerait. Une ligne, pas deux."""
    t = _tag(db_path, "zorglub", decor["c1"])
    _poser(db_path, decor["r1"], t)
    _reindexer(client, decor["r1"])
    _sql(db_path, "UPDATE recherche SET lemmes = 'marqueurlemme' WHERE region_id = ?",
         (decor["r1"],))
    _sql(db_path, "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                  "VALUES (?, 99, 'temoin', 'temoin', 'NOUN', '')", (decor["r1"],))
    jetons = _sql(db_path, "SELECT id FROM tokens WHERE region_id = ?", (decor["r1"],))
    assert client.put(f"/api/tags/{t}", json={"label": "zorgle"},
                      headers=PROPRIO).status_code == 200
    [ligne] = _ligne_fts(db_path, decor["r1"])
    assert ligne["tags_concat"] == "zorgle" and ligne["lemmes"] == "marqueurlemme"
    assert _sql(db_path, "SELECT id FROM tokens WHERE region_id = ?", (decor["r1"],)) == jetons
    assert _trouve(client, "zorgle") == [decor["r1"]]
    assert _trouve(client, "zorglub") == []


def test_une_region_sans_ligne_d_index_en_recoit_une(client, db_path, decor):
    """Des tags posés hors des routes : aucune ligne d'index. La fusion lui en donne une, et
    la région se trouve sous le libellé de la cible."""
    a = _tag(db_path, "sans-index", decor["c1"])
    b = _tag(db_path, "indexee")
    _poser(db_path, decor["r1b"], a)
    _sql(db_path, "DELETE FROM recherche WHERE region_id = ?", (decor["r1b"],))
    assert client.post(f"/api/tags/{a}/fusion", json={"cible_id": b},
                       headers=PROPRIO).status_code == 200
    assert len(_ligne_fts(db_path, decor["r1b"])) == 1
    assert _trouve(client, "indexee") == [decor["r1b"]]


def test_une_note_de_blancs_compte_pour_vide(client, db_path, decor):
    """La règle de `put_annotation` (`database.annotation_vide`), et non `TRIM` de SQL, qui
    ne retire que des espaces : une note faite d'un saut de ligne et d'une tabulation est
    vide, et l'annotation part avec son dernier tag."""
    t = _tag(db_path, "seul", decor["c1"])
    _poser(db_path, decor["r1"], t, note="\n\t ")
    assert client.delete(f"/api/tags/{t}", headers=PROPRIO).status_code == 200
    assert not _sql(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (decor["r1"],))


def _tags_de(db_path, region_id):
    return sorted((r["id"], r["label"], r["collection_id"]) for r in _sql(
        db_path, "SELECT t.id, t.label, t.collection_id FROM annotation_tags at "
                 "JOIN annotations an ON an.id = at.annotation_id "
                 "JOIN tags t ON t.id = at.tag_id WHERE an.region_id = ?", (region_id,)))


def test_cle_partagee_ctrl_z_rend_le_tag_vu_et_non_l_invisible(client, db_path, decor):
    """Contre-relecture (2026-10-22). Deux lignes d'avant de même clé : « c’est » (globale,
    lue) et « c'est » (locale à c2, que l'écrivain ne lit pas). Ctrl+Z d'un retrait rend le
    libellé EXACT de l'instantané, jamais le tag d'une collection qu'il ne lit pas."""
    a = _tag(db_path, "c’est")
    _tag(db_path, "c'est", decor["c2"])
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"note": "n", "tags_ajoutes": ["c’est"]})
    assert r.status_code == 200, r.text
    assert _tags_de(db_path, decor["r1"]) == [(a, "c’est", None)]
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"tags_retires": ["c’est"]})
    assert r.status_code == 200, r.text
    assert client.post("/api/undo", headers=ECRIVAIN).status_code == 200
    assert _tags_de(db_path, decor["r1"]) == [(a, "c’est", None)]


def test_par_la_cle_on_ne_rend_qu_un_tag_qu_on_voit(client, db_path, decor):
    """Le libellé exact a disparu (renommé vers sa clé, que porte AUSSI un tag local à c2
    qu'il ne lit pas — le renommage refuse alors : on le pose en SQL). La clé ne rend que le
    tag qu'il voit ; sinon le tag est perdu, compté, et rien d'illisible n'est posé."""
    vu = _tag(db_path, "Zorg")
    _tag(db_path, "zorg", decor["c2"])
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"note": "n", "tags_ajoutes": ["Zorg"]})
    assert r.status_code == 200, r.text
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                   json={"note": "m", "tags_retires": ["Zorg"]})
    assert r.status_code == 200, r.text
    _sql(db_path, "DELETE FROM tags WHERE id = ?", (vu,))      # le seul qu'il voyait
    r = client.post("/api/undo", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert r.json()["tags_non_rendus"] == 1
    assert _tags_de(db_path, decor["r1"]) == []


def test_un_tag_actuel_sans_rapport_n_est_pas_remplace_par_la_chaine(client, db_path, decor):
    """Contre-relecture : l'acte annulé ne touche que la note. Après lui, « x » est renommé
    « y », puis un NOUVEAU « x » est posé par un autre. Défaire la note ne touche aucun tag :
    les tags d'aujourd'hui se reposent par leur identifiant."""
    for note in ("a", "b"):
        r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ECRIVAIN,
                       json={"note": note})
        assert r.status_code == 200, r.text
    vieux = _tag(db_path, "x")
    assert client.put(f"/api/tags/{vieux}", json={"label": "y"},
                      headers=ADMIN).status_code == 200
    r = client.put(f"/api/regions/{decor['r1']}/annotation", headers=ADMIN,
                   json={"tags_ajoutes": ["x"]})
    assert r.status_code == 200, r.text
    neuf = [t for t in _tags_de(db_path, decor["r1"]) if t[1] == "x"][0][0]
    assert client.post("/api/undo", headers=ECRIVAIN).status_code == 200
    assert _tags_de(db_path, decor["r1"]) == [(neuf, "x", None)]
    assert _sql(db_path, "SELECT note FROM annotations WHERE region_id = ?",
                (decor["r1"],))[0]["note"] == "a"


def test_un_tag_cache_revient_par_son_libelle_exact(client, db_path, decor):
    """Cacher n'est pas saisir : une région rétablie rend aussi le tag qu'elle portait d'une
    collection que l'agent ne lit pas — par son libellé EXACT, sans passer par la clé, que
    la portée filtre. Rien n'est perdu."""
    cache = _tag(db_path, "prive-b", decor["c2"])
    vu = _tag(db_path, "vu-a", decor["c1"])
    _poser(db_path, decor["r1"], cache, vu, note="n")
    _reindexer(client, decor["r1"])
    assert client.delete(f"/api/regions/{decor['r1']}", headers=ECRIVAIN).status_code in (200, 204)
    r = client.post("/api/undo", headers=ECRIVAIN)
    assert r.status_code == 200, r.text
    assert "tags_non_rendus" not in r.json()
    assert _porteurs(db_path, cache) == [decor["r1"]] == _porteurs(db_path, vu)
