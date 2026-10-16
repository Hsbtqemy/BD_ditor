"""UX-18 — l'appartenance album → collections, en UNE lecture, et seulement ce qu'on lit.

La Bibliothèque montre la collection en CALQUE : elle filtre le corpus par collection, et
chaque album nomme les siennes. Il lui faut donc, pour CHAQUE album, la liste des
collections où il est rangé — et `GET /api/albums/{id}/collections` ne la donnait qu'un
album à la fois. `GET /api/albums` la rend désormais sous `collections`.

Ce qui se garde ici est un FILTRE, et un filtre oublié échoue OUVERT : la réponse reste
juste pour qui lit tout, et se met à nommer une étude voisine à qui ne la lit pas, sans
qu'aucun code de retour change. D'où ces tests joués sous chaque identité, sur un album
rangé dans une collection lue ET dans une qui ne l'est pas, et relus sur le JSON BRUT : la
collection non lue n'y laisse ni son nom, ni son identifiant, ni une place dans le nombre
(« 404, jamais 403 », AUTH-2).

L'identifiant de la collection cachée est posé GRAND et singulier (`CACHEE_ID`) pour que
son absence du texte brut veuille dire quelque chose : un « 3 » se trouve partout dans une
réponse, « 97531 » nulle part ailleurs.
"""
import sqlite3

import pytest

import main
import socle
from conftest import ADMIN

CACHEE_ID = 97531
CACHEE_NOM = "Zq étude voisine cachée"

LECTRICE = {"Remote-User": "lectrice"}          # lit A, rien d'autre
ECRIVAIN = {"Remote-User": "ecrivain"}          # écrit dans C, LIT A
PROPRIO = {"Remote-User": "proprio"}            # possède la collection cachée, rien d'autre
PERSONNE = {"Remote-User": "personne"}          # une identité, aucun accès : portée vide


def _collection(client, nom):
    r = client.post("/api/collections", json={"nom": nom}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _album(client, titre, cid):
    r = client.post("/api/albums", json={"titre": titre, "collection_id": cid}, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ranger(client, album_id, cid):
    r = client.put(f"/api/albums/{album_id}/collections/{cid}", headers=ADMIN)
    assert r.status_code == 201, r.text


def _accorder(client, cid, principal, niveau):
    r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": principal, "niveau": niveau})
    assert r.status_code == 200, r.text


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    """Trois collections du projet de repli — « Étude A », la cachée, « Incubateur » — et
    quatre albums :

    - `mixte` : rangé dans A ET dans la cachée — le cas qui compte ;
    - `cache` : rangé dans la cachée seule ;
    - `double` : rangé dans A et dans l'Incubateur ;
    - `fonds` : sorti de sa dernière collection, gardé au fonds.
    """
    a, c = _collection(client, "Étude A"), _collection(client, "Incubateur")
    # Posée APRÈS les deux autres, qui gardent ainsi de petits identifiants.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection (id, nom) VALUES (?, ?)", (CACHEE_ID, CACHEE_NOM))
        conn.commit()
    finally:
        conn.close()
    mixte = _album(client, "Mixte", a)
    _ranger(client, mixte, CACHEE_ID)
    cache = _album(client, "Caché", CACHEE_ID)
    double = _album(client, "Double", c)
    _ranger(client, double, a)
    fonds = _album(client, "Au fonds", c)
    r = client.delete(f"/api/albums/{fonds}/collections/{c}", headers=ADMIN)
    assert r.status_code == 204, r.text
    _accorder(client, a, "lectrice", "lecture")
    _accorder(client, a, "ecrivain", "lecture")
    _accorder(client, c, "ecrivain", "ecriture")
    _accorder(client, CACHEE_ID, "proprio", "proprietaire")
    return {"a": a, "c": c, "mixte": mixte, "cache": cache, "double": double,
            "fonds": fonds}


def _liste(client, qui):
    rep = client.get("/api/albums", headers=qui)
    assert rep.status_code == 200, rep.text
    return rep


def _par_nom(*collections):
    """L'ordre servi : par nom, à la comparaison binaire de SQLite — « Étude » se range
    APRÈS « Incubateur », comme dans `sorted` de Python."""
    return sorted(collections, key=lambda c: c[1])


def _appartenance(rep) -> dict:
    """{album_id: [(collection_id, nom), …]} dans l'ordre servi."""
    return {a["id"]: [(c["id"], c["nom"]) for c in a["collections"]] for a in rep.json()}


# ── ce que chacun lit ────────────────────────────────────────────────────────────────────
def test_la_lectrice_ne_lit_que_sa_collection_sur_un_album_partage(client, decor):
    """Le cas de la case : un album rangé dans une collection lue ET une qui ne l'est pas.
    La lectrice lit l'album par A ; la cachée n'apparaît NULLE PART — ni dans la liste de
    l'album (un seul élément, et non deux), ni dans le texte brut de la réponse."""
    rep = _liste(client, LECTRICE)
    assert _appartenance(rep) == {
        decor["mixte"]: [(decor["a"], "Étude A")],
        decor["double"]: [(decor["a"], "Étude A")],
    }
    assert CACHEE_NOM.encode() not in rep.content
    assert str(CACHEE_ID).encode() not in rep.content
    # L'Incubateur non plus : elle ne le lit pas, et `double` y vit.
    assert b"Incubateur" not in rep.content


def test_l_ecrivain_lit_aussi_les_collections_ou_il_n_ecrit_pas(client, decor):
    """La règle est LIRE, pas écrire : A, qu'il ne fait que lire, est nommée à côté de
    l'Incubateur où il écrit. Un filtre par écriture rendrait `[Incubateur]` seul."""
    rep = _liste(client, ECRIVAIN)
    assert _appartenance(rep) == {
        decor["mixte"]: [(decor["a"], "Étude A")],
        decor["double"]: _par_nom((decor["a"], "Étude A"), (decor["c"], "Incubateur")),
    }
    assert CACHEE_NOM.encode() not in rep.content
    assert str(CACHEE_ID).encode() not in rep.content


def test_le_proprietaire_lit_sa_collection_et_pas_celle_des_autres(client, decor):
    """L'envers de la lectrice : le propriétaire de la cachée lit `mixte` par elle, et
    c'est A, cette fois, qui ne doit pas se lire."""
    rep = _liste(client, PROPRIO)
    assert _appartenance(rep) == {
        decor["mixte"]: [(CACHEE_ID, CACHEE_NOM)],
        decor["cache"]: [(CACHEE_ID, CACHEE_NOM)],
    }
    assert "Étude A".encode() not in rep.content
    assert b"Incubateur" not in rep.content


def test_la_portee_totale_lit_tout_par_nom(client, decor):
    """Un administrateur ne figure dans aucun accès : sa portée TOTALE doit tout lui
    nommer quand même, dans l'ordre des noms. Et la copie gardée au fonds n'a aucune
    collection — une liste vide, pas une clé absente."""
    rep = _liste(client, ADMIN)
    assert _appartenance(rep) == {
        decor["mixte"]: _par_nom((decor["a"], "Étude A"), (CACHEE_ID, CACHEE_NOM)),
        decor["cache"]: [(CACHEE_ID, CACHEE_NOM)],
        decor["double"]: _par_nom((decor["a"], "Étude A"), (decor["c"], "Incubateur")),
        decor["fonds"]: [],
    }
    # Le témoin des lectures BRUTES des autres tests : le nom et l'identifiant de la
    # cachée s'écrivent tels quels dans le texte de la réponse. Si le JSON échappait les
    # accents (une séquence `\u` à la place du « é »), chercher le nom ailleurs ne
    # prouverait plus rien.
    assert CACHEE_NOM.encode() in rep.content
    assert str(CACHEE_ID).encode() in rep.content


def test_la_portee_vide_ne_lit_rien(client, decor):
    """Une identité sans aucun accès : aucun album, donc aucune collection — et aucun nom
    qui traînerait dans la réponse."""
    rep = _liste(client, PERSONNE)
    assert rep.json() == []
    for nom in (CACHEE_NOM, "Étude A", "Incubateur"):
        assert nom.encode() not in rep.content


def test_la_liste_et_la_route_d_un_album_disent_la_meme_chose(client, decor):
    """Deux routes, UNE règle : pour chaque identité et chaque album qu'elle lit, la liste
    groupée nomme exactement les collections que `GET /api/albums/{id}/collections` rend,
    dans le même ordre. Une seconde écriture du filtre finirait par diverger ; ce test la
    ferait tomber."""
    for qui in (LECTRICE, ECRIVAIN, PROPRIO, ADMIN):
        for a in _liste(client, qui).json():
            seule = client.get(f"/api/albums/{a['id']}/collections", headers=qui)
            assert seule.status_code == 200, seule.text
            assert a["collections"] == [{"id": c["id"], "nom": c["nom"]}
                                        for c in seule.json()], (qui, a["titre"])


def test_la_route_d_un_album_ne_nomme_pas_non_plus_la_collection_cachee(client, decor):
    """La règle a déménagé dans le socle : la route d'un album la lit désormais là, et doit
    toujours taire la cachée — et garder ce qu'elle rendait en plus (niveau, droits)."""
    rep = client.get(f"/api/albums/{decor['mixte']}/collections", headers=LECTRICE)
    assert rep.status_code == 200, rep.text
    assert [(c["id"], c["mon_niveau"], c["administrable"], c["exportable"])
            for c in rep.json()] == [(decor["a"], "lecture", False, False)]
    assert CACHEE_NOM.encode() not in rep.content
    assert str(CACHEE_ID).encode() not in rep.content


def test_la_forme_de_l_appartenance_est_sobre(client, decor):
    """`id` et `nom`, rien d'autre : ce que l'appelant peut faire dans une collection se
    lit dans `GET /api/collections`. Une clé ajoutée ici se publierait par défaut et non
    par décision."""
    for a in _liste(client, ADMIN).json():
        for c in a["collections"]:
            assert set(c) == {"id", "nom"}, c


# ── en mono-poste ────────────────────────────────────────────────────────────────────────
def test_en_mono_poste_tout_se_lit(client):
    """Sans proxy, la portée est TOTALE : tout se nomme, sans aucun accès posé."""
    a = client.post("/api/collections", json={"nom": "Une"}).json()["id"]
    b = client.post("/api/collections", json={"nom": "Deux"}).json()["id"]
    album = client.post("/api/albums", json={"titre": "T", "collection_id": a}).json()["id"]
    r = client.put(f"/api/albums/{album}/collections/{b}")
    assert r.status_code == 201, r.text
    ligne = {x["id"]: x for x in client.get("/api/albums").json()}[album]
    assert ligne["collections"] == [{"id": b, "nom": "Deux"}, {"id": a, "nom": "Une"}]


# ── en une lecture ───────────────────────────────────────────────────────────────────────
def _compter_requetes(client, qui) -> int:
    """Le nombre d'instructions SQL qu'exécute `GET /api/albums`, mesuré sur la connexion
    de la requête elle-même (la dépendance `db`, remplacée le temps de l'appel)."""
    traces: list[str] = []

    def db_tracee():
        conn = socle.get_connection()
        conn.set_trace_callback(traces.append)
        try:
            yield conn
        finally:
            conn.close()

    main.app.dependency_overrides[socle.db] = db_tracee
    try:
        _liste(client, qui)
    finally:
        main.app.dependency_overrides.pop(socle.db, None)
    return len(traces)


def test_l_appartenance_ne_coute_pas_une_requete_par_album(client, decor):
    """Le but même de la case : l'écran dessine sans un appel par album, et le serveur ne
    le fait pas à sa place. Trois albums de plus, rangés chacun dans deux collections, ne
    changent RIEN au nombre de requêtes."""
    avant = _compter_requetes(client, ADMIN)
    for i in range(3):
        album = _album(client, f"Plus {i}", decor["a"])
        _ranger(client, album, CACHEE_ID)
    apres = _compter_requetes(client, ADMIN)
    assert avant > 0
    assert apres == avant, (avant, apres)
