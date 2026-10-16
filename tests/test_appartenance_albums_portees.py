"""UX-18 — l'appartenance de `GET /api/albums`, sous les portées que `test_appartenance_albums`
ne joue pas (relecture croisée du 2026-10-17).

Le premier fichier pose ses accès sur des LOGINS, dans un seul projet, sur des albums dont
le document porte le même identifiant que l'album. Trois mutants de la relecture
survivaient à cela, et chacun est une erreur crédible :

- être du PROJET ouvrirait les noms de ses collections (`est_du_projet` ajouté au filtre) :
  rien n'y distinguait « lire une collection » d'« être du projet » ;
- le rangement lu sous `document_id` au lieu de l'identifiant de l'album : les deux
  coïncident tant qu'un album naît avec son document, et cessent de coïncider dès qu'un
  document existe sans copie (tranche 3, base migrée) ;
- (tué ailleurs, gardé ici par sa forme) l'accès porté par un GROUPE lu dans
  `Remote-Groups`, que le premier fichier n'emploie jamais.

S'y ajoutent les formes de bord : une collection d'un autre projet (base retouchée), la
demande en attente, et une liste de 1 200 albums (la liaison `IN (…)` d'une seule requête).
"""
import sqlite3

import pytest

from conftest import ADMIN

CACHEE_NOM = "Zq étude voisine cachée"
EQUIPE = {"Remote-User": "m1", "Remote-Groups": "equipe"}      # lit A par son groupe
CHEFS = {"Remote-User": "m2", "Remote-Groups": "chefs"}        # possède la cachée par son groupe


def _post(client, url, json, qui=ADMIN):
    r = client.post(url, json=json, headers=qui)
    assert r.status_code == 201, r.text
    return r.json()


def _accorder(client, cid, genre, principal, niveau):
    r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": genre, "principal": principal, "niveau": niveau})
    assert r.status_code == 200, r.text


@pytest.fixture
def decor(client, derriere_proxy):
    """« Étude A » et la cachée, du projet de repli ; `mixte` rangé dans les deux, `seul`
    dans la cachée seule. Les accès passent par des GROUPES."""
    a = _post(client, "/api/collections", {"nom": "Étude A"})["id"]
    cachee = _post(client, "/api/collections", {"nom": CACHEE_NOM})["id"]
    mixte = _post(client, "/api/albums", {"titre": "Mixte", "collection_id": a})["id"]
    r = client.put(f"/api/albums/{mixte}/collections/{cachee}", headers=ADMIN)
    assert r.status_code == 201, r.text
    seul = _post(client, "/api/albums", {"titre": "Seul caché", "collection_id": cachee})["id"]
    _accorder(client, a, "groupe", "equipe", "lecture")
    _accorder(client, cachee, "groupe", "chefs", "proprietaire")
    return {"a": a, "cachee": cachee, "mixte": mixte, "seul": seul}


def _appartenance(client, qui):
    rep = client.get("/api/albums", headers=qui)
    assert rep.status_code == 200, rep.text
    return rep, {x["id"]: [(c["id"], c["nom"]) for c in x["collections"]] for x in rep.json()}


def _repli(client):
    return next(p["id"] for p in client.get("/api/projets", headers=ADMIN).json()
                if p.get("repli"))


# ── par un groupe ────────────────────────────────────────────────────────────────────────
def test_un_groupe_en_lecture_ne_nomme_que_sa_collection(client, decor):
    rep, app = _appartenance(client, EQUIPE)
    assert app == {decor["mixte"]: [(decor["a"], "Étude A")]}
    assert CACHEE_NOM.encode() not in rep.content


def test_un_groupe_proprietaire_ne_nomme_pas_la_collection_voisine(client, decor):
    """Propriétaire de la cachée par son groupe : il la lit (cumul des niveaux) et ne lit
    pas A. `partage` lui dit qu'un autre usage existe — ce qu'AUTH-10 accepte —, la liste
    ne dit jamais lequel."""
    rep, app = _appartenance(client, CHEFS)
    assert app == {decor["mixte"]: [(decor["cachee"], CACHEE_NOM)],
                   decor["seul"]: [(decor["cachee"], CACHEE_NOM)]}
    assert "Étude A".encode() not in rep.content
    par_id = {x["id"]: x for x in rep.json()}
    assert par_id[decor["mixte"]]["partage"] is True
    assert par_id[decor["seul"]]["partage"] is False


def test_deux_groupes_cumulent_leurs_collections(client, decor):
    _, app = _appartenance(client, {"Remote-User": "m3", "Remote-Groups": "equipe,chefs"})
    assert app[decor["mixte"]] == sorted([(decor["a"], "Étude A"),
                                          (decor["cachee"], CACHEE_NOM)], key=lambda c: c[1])


# ── être du projet n'est pas lire ────────────────────────────────────────────────────────
def test_etre_responsable_du_projet_n_ouvre_pas_le_nom_d_une_collection(client, decor):
    """Responsable du projet de repli ET lecteur de A : la cachée est du même projet, il ne
    la lit pas, il ne doit pas la lire ici. Un filtre qui accepterait « du projet » à côté
    de « lit la collection » la nommerait (mutant de la relecture, survivant sans ce test)."""
    r = client.put(f"/api/projets/{_repli(client)}/membres", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": "resp", "role": "responsable"})
    assert r.status_code in (200, 201), r.text
    _accorder(client, decor["a"], "utilisateur", "resp", "lecture")
    rep, app = _appartenance(client, {"Remote-User": "resp"})
    assert app == {decor["mixte"]: [(decor["a"], "Étude A")]}
    assert CACHEE_NOM.encode() not in rep.content


# ── formes de bord ───────────────────────────────────────────────────────────────────────
def test_une_collection_d_un_autre_projet_se_nomme_si_on_la_lit(client, decor, db_path):
    """Base retouchée : `mixte` rangé AUSSI dans une collection d'un autre projet (la route
    le refuserait). Qui ne lit que celle-là la voit nommée, et seule ; les deux routes
    disent la même chose."""
    p2 = _post(client, "/api/projets", {"nom": "P2"})["id"]
    c2 = _post(client, "/api/collections", {"nom": "Coll P2", "projet_id": p2})["id"]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (c2, decor["mixte"]))
        conn.commit()
    finally:
        conn.close()
    _accorder(client, c2, "utilisateur", "x2", "lecture")
    qui = {"Remote-User": "x2"}
    rep, app = _appartenance(client, qui)
    assert app == {decor["mixte"]: [(c2, "Coll P2")]}
    seule = client.get(f"/api/albums/{decor['mixte']}/collections", headers=qui).json()
    assert [(c["id"], c["nom"]) for c in seule] == [(c2, "Coll P2")]


def test_la_demande_en_attente_ne_change_pas_l_appartenance(client, decor):
    c = _post(client, "/api/collections", {"nom": "Incub"})["id"]
    alb = _post(client, "/api/albums", {"titre": "Demandé", "collection_id": c})["id"]
    _accorder(client, c, "utilisateur", "ecr", "ecriture")
    _accorder(client, c, "utilisateur", "lec", "lecture")
    _post(client, "/api/demandes", {"genre": "suppression_document", "album_id": alb,
                                    "motif": "doublon", "certifie": True},
          qui={"Remote-User": "ecr"})
    for qui, nomme in (({"Remote-User": "lec"}, False), ({"Remote-User": "ecr"}, True),
                       (ADMIN, True)):
        x = {a["id"]: a for a in client.get("/api/albums", headers=qui).json()}[alb]
        assert x["collections"] == [{"id": c, "nom": "Incub"}]
        assert x["demande"] is not None
        assert ("demandeur" in x["demande"]) is nomme


def test_l_appartenance_suit_l_album_et_non_son_document(client, derriere_proxy, db_path):
    """Des documents sans copie DÉCALENT les identifiants : l'album N porte alors le
    document N+3. L'appartenance doit suivre l'album — lue sous `document_id`, elle
    tomberait sur un autre album, ou sur rien, sans qu'aucun test le voie tant que les deux
    numérotations coïncident."""
    conn = sqlite3.connect(db_path)
    try:
        for _ in range(3):
            conn.execute("INSERT INTO document (importe_par) VALUES (NULL)")
        conn.commit()
    finally:
        conn.close()
    a = _post(client, "/api/collections", {"nom": "Une"})["id"]
    b = _post(client, "/api/collections", {"nom": "Deux"})["id"]
    premier = _post(client, "/api/albums", {"titre": "P", "collection_id": a})["id"]
    second = _post(client, "/api/albums", {"titre": "S", "collection_id": b})["id"]
    lignes = {x["id"]: x for x in client.get("/api/albums", headers=ADMIN).json()}
    # Le témoin : sans décalage, ce test ne prouverait rien.
    assert lignes[premier]["document_id"] != premier
    assert lignes[premier]["collections"] == [{"id": a, "nom": "Une"}]
    assert lignes[second]["collections"] == [{"id": b, "nom": "Deux"}]


def test_mille_deux_cents_albums_en_une_liste(client, decor, db_path):
    """Une seule requête lie un identifiant par album : 1 200 albums passent, et le filtre
    tient sur chacun."""
    conn = sqlite3.connect(db_path)
    try:
        for i in range(1200):
            album = conn.execute("INSERT INTO albums (titre) VALUES (?)",
                                 (f"Masse {i}",)).lastrowid
            conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                         (decor["a"] if i % 2 else decor["cachee"], album))
        conn.commit()
    finally:
        conn.close()
    _, app = _appartenance(client, ADMIN)
    assert len(app) == 1202
    rep, app = _appartenance(client, EQUIPE)
    assert len(app) == 601
    assert all(v == [(decor["a"], "Étude A")] for v in app.values())
    assert CACHEE_NOM.encode() not in rep.content
