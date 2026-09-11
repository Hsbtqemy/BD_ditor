"""DROIT-2 — exporter est un droit à part, accordé par collection.

Jusqu'au 2026-09-11, toute personne qui LISAIT une collection pouvait en sortir le contenu,
texte relevé compris. L'équipe a tranché : « l'export reste quelque chose de particulièrement
sensible, et il ne faut pas que tout le monde y ait accès. » Exporter devient une case posée
À CÔTÉ du niveau d'accès, par collection, d'office pour les propriétaires.

Ce module éprouve le MODÈLE — la case, la Portee qui la lit, le geste qui la pose. Les
portes qu'elle garde ont leurs propres tests plus bas, parce qu'un modèle juste que personne
ne consulte laisse tout sortir, et qu'aucun test du modèle ne le verrait.
"""
import json
import sqlite3

import autorisation
import database
from test_autorisation import _ouvrir, deux_albums  # noqa: F401  (fixture importée)


def _poser_export(db_path, collection_id, principal, exporter=True, genre="utilisateur"):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE collection_acces SET exporter = ? WHERE collection_id = ? "
                     "AND genre = ? AND principal = ?",
                     (int(exporter), collection_id, genre, principal))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# La Portee
# --------------------------------------------------------------------------- #
def test_exporter_est_une_case_a_cote_du_niveau_pas_un_palier():
    """Le cas qui a fait trancher : les stagiaires ÉCRIVENT, et c'est voulu. Une règle
    « écriture et plus » ne les arrêterait pas — écrire ne donne donc pas l'export, lire
    avec la case le donne, et posséder le donne d'office."""
    p = autorisation.Portee(lecture=frozenset({1}), ecriture=frozenset({2}),
                            propriete=frozenset({3}), export=frozenset({1}))
    assert p.peut_exporter(1)            # lecture seule, case cochée
    assert not p.peut_exporter(2)        # écrire n'y suffit pas
    assert p.peut_exporter(3)            # propriétaire : d'office
    assert not p.peut_exporter(4)        # hors de portée


def test_on_n_exporte_pas_ce_qu_on_ne_lit_pas():
    """Une case orpheline en base — une collection hors de la lecture — ne donne rien."""
    p = autorisation.Portee(lecture=frozenset({1}), export=frozenset({1, 9}))
    assert p.export == frozenset({1}) and not p.peut_exporter(9)


def test_la_portee_totale_exporte_tout():
    """Mono-poste et administrateur : personne à qui refuser, rien à réduire."""
    t = autorisation.TOTALE
    assert t.peut_exporter(42) and t.peut_exporter_quelque_part()
    assert t.pour_export() is t


def test_pour_export_reduit_la_lecture_a_ce_qui_peut_sortir():
    """La même personne, réduite à ce qu'elle peut SORTIR : c'est ce que consomment les
    exports qui traversent plusieurs collections, sans qu'aucun cœur ne change."""
    p = autorisation.Portee(lecture=frozenset({1, 2}), ecriture=frozenset({2}),
                            export=frozenset({1}))
    pe = p.pour_export()
    assert pe.lecture == frozenset({1}) and pe.ecriture == frozenset()
    assert pe.clause_album("a.id")[1] == [1]
    assert p.peut_exporter_quelque_part()
    assert not autorisation.Portee(lecture=frozenset({1})).peut_exporter_quelque_part()


# --------------------------------------------------------------------------- #
# La case en base, et le geste qui la pose
# --------------------------------------------------------------------------- #
def _exportables(client, h):
    return {c["id"]: c["exportable"] for c in client.get("/api/collections", headers=h).json()}


def test_la_case_se_lit_en_base_par_login_et_par_groupe(client, db_path, deux_albums,
                                                        derriere_proxy):
    """Un accès se pose sur un login OU sur un groupe ; la case aussi. Bob écrit sur c1 et
    lit c2 par son groupe : il n'exporte rien, jusqu'à ce que la case du GROUPE soit
    cochée sur c2 — et alors c2 seulement."""
    c1, c2 = deux_albums["c1"], deux_albums["c2"]
    _ouvrir(db_path, c1, "bob", niveau="ecriture")
    _ouvrir(db_path, c2, "equipe", genre="groupe")
    bob = {"Remote-User": "bob", "Remote-Groups": "equipe"}
    assert _exportables(client, bob) == {c1: False, c2: False}
    _poser_export(db_path, c2, "equipe", genre="groupe")
    assert _exportables(client, bob) == {c1: False, c2: True}


def test_un_proprietaire_exporte_sans_rien_cocher(client, db_path, deux_albums,
                                                  derriere_proxy):
    """Sa case n'est pas cochée, et la liste des accès le dit quand même exportateur : le
    droit EFFECTIF, pas la case stockée."""
    c1 = deux_albums["c1"]
    _ouvrir(db_path, c1, "carole", niveau="proprietaire")
    carole = {"Remote-User": "carole"}
    assert _exportables(client, carole)[c1] is True
    acces = client.get(f"/api/collections/{c1}/acces", headers=carole).json()
    assert next(a for a in acces if a["principal"] == "carole")["exporter"] is True


def test_accorder_la_case_est_un_geste_de_proprietaire_et_se_trace(client, db_path,
                                                                   deux_albums,
                                                                   derriere_proxy):
    """Décider ce qui sort engage la collection autant que décider qui entre : un membre en
    écriture ne se l'accorde pas. Re-poser un niveau sans mentionner la case ne la retire
    pas. Et le changement est au journal, avec l'état d'avant."""
    c1 = deux_albums["c1"]
    _ouvrir(db_path, c1, "carole", niveau="proprietaire")
    _ouvrir(db_path, c1, "bob", niveau="ecriture")
    carole, bob = {"Remote-User": "carole"}, {"Remote-User": "bob"}
    corps = {"principal": "bob", "niveau": "ecriture", "exporter": True}

    assert client.put(f"/api/collections/{c1}/acces", json=corps,
                      headers=bob).status_code == 403
    rep = client.put(f"/api/collections/{c1}/acces", json=corps, headers=carole)
    assert rep.status_code == 200, rep.text
    assert next(a for a in rep.json() if a["principal"] == "bob")["exporter"] is True
    assert _exportables(client, bob)[c1] is True

    rep = client.put(f"/api/collections/{c1}/acces",
                     json={"principal": "bob", "niveau": "lecture"}, headers=carole)
    assert next(a for a in rep.json() if a["principal"] == "bob")["exporter"] is True

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        evs = [(json.loads(e["avant"] or "null"), json.loads(e["apres"] or "null"))
               for e in conn.execute("SELECT avant, apres FROM evenement "
                                     "WHERE cible_table = 'collection_acces' ORDER BY id")]
    finally:
        conn.close()
    assert ({"genre": "utilisateur", "principal": "bob", "niveau": "ecriture",
             "exporter": False},
            {"genre": "utilisateur", "principal": "bob", "niveau": "ecriture",
             "exporter": True}) in evs


def test_un_acces_neuf_part_sans_le_droit(client, db_path, deux_albums, derriere_proxy):
    c1 = deux_albums["c1"]
    _ouvrir(db_path, c1, "carole", niveau="proprietaire")
    rep = client.put(f"/api/collections/{c1}/acces",
                     json={"principal": "dora", "niveau": "ecriture"},
                     headers={"Remote-User": "carole"})
    assert next(a for a in rep.json() if a["principal"] == "dora")["exporter"] is False


def test_la_migration_v27_ferme_l_export_a_qui_lisait(client, db_path, deux_albums):
    """Le changement de COMPORTEMENT de la migration, écrit comme tel : un accès existant
    arrive sans le droit. Aucun rattrapage — ouvrir d'office à qui lisait reconduirait
    l'état que le chantier ferme."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                     "VALUES (?, 'utilisateur', 'bob', 'ecriture')", (deux_albums["c1"],))
        conn.execute("ALTER TABLE collection_acces DROP COLUMN exporter")
        conn.execute("PRAGMA user_version = 26")
        conn.commit()
    finally:
        conn.close()
    database.init_db()
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
        assert conn.execute("SELECT exporter FROM collection_acces "
                            "WHERE principal = 'bob'").fetchone()[0] == 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Les portes — l'oubli d'une garde échoue ici OUVERT
# --------------------------------------------------------------------------- #
# Une porte oubliée continuerait de laisser sortir : c'était l'état de toutes jusqu'au
# 2026-09-11, et il ne faisait tomber aucun test. D'où deux questions posées à la machine
# plutôt qu'à une liste tenue de mémoire : quelles routes produisent un fichier, et chacune
# refuse-t-elle qui lit sans la case ?
import inspect  # noqa: E402

import pytest  # noqa: E402

from inventaire_routes import exiger_plancher, routes_api  # noqa: E402

# Ce qui fait d'une route une PORTE DE SORTIE, lu dans son source ET dans son chemin. Deux
# lectures, parce qu'une seule en rate : l'export JSON d'un album ne pose aucun en-tête de
# pièce jointe — c'est le client qui l'enregistre — et seul son chemin le trahit.
_MARQUES = ("_csv_response(", "Content-Disposition", "_piece_jointe(")


def _sort_un_fichier(route) -> bool:
    chemin = route.path
    if "/export" in chemin or "/depot/" in chemin or chemin.endswith(".csv"):
        return True
    return any(m in inspect.getsource(route.endpoint) for m in _MARQUES)


PORTES = {
    ("GET", "/api/export/json"), ("GET", "/api/export/csv"), ("GET", "/api/export/tei"),
    ("GET", "/api/recherche/export.csv"),
    ("GET", "/api/analyse/frequences.csv"), ("GET", "/api/analyse/concordance.csv"),
    ("GET", "/api/analyse/comparaison.csv"), ("GET", "/api/analyse/croisement.csv"),
    ("GET", "/api/analyse/accord.csv"), ("GET", "/api/analyse/accord-inter.csv"),
    ("GET", "/api/collections/{collection_id}/depot/description"),
    ("GET", "/api/collections/{collection_id}/depot/metadonnees"),
    ("GET", "/api/collections/{collection_id}/depot/iiif"),
    ("POST", "/api/collections/{collection_id}/depot/deposer"),
    ("POST", "/api/figures"),
}
# Déclarées HORS du droit d'exporter, chacune avec sa raison.
HORS_EXPORT = {
    ("GET", "/api/sauvegarde"):
        "réservée aux administrateurs (DROIT-1) : c'est la base ENTIÈRE, un geste "
        "d'exploitation, et ni la portée ni la case n'y ont de sens",
}
# Le dépôt ShareDocs refuse bien qui n'a pas la case — sa garde est la PROPRIÉTÉ, plus
# stricte, puisque tout propriétaire exporte d'office. Sa contre-épreuve suppose un
# ShareDocs, et `test_depot_export` la joue déjà : elle n'est pas refaite ici.
SANS_CONTRE_EPREUVE = {("POST", "/api/collections/{collection_id}/depot/deposer")}


def _requete(porte, d):
    methode, chemin = porte
    a1, r1 = d["a1"]["id"], d["r1"]["id"]
    url = chemin.replace("{collection_id}", str(d["c1"]))
    params = {
        "/api/export/json": {"album_id": a1}, "/api/export/csv": {"album_id": a1},
        "/api/export/tei": {"album_id": a1},
        "/api/recherche/export.csv": {"q": "MOTSECRET"},
        "/api/analyse/concordance.csv": {"lemme": "dire"},
        "/api/analyse/comparaison.csv": {"a_album": a1, "b_album": a1},
        "/api/analyse/croisement.csv": {"axe_x": "pos", "axe_y": "type"},
    }.get(chemin, {})
    corps = {"/api/figures": {"regions": [r1]},
             "/api/collections/{collection_id}/depot/deposer":
                 {"quoi": "description", "format": "json"}}.get(chemin)
    return methode, url, params, corps


@pytest.fixture
def sortie(client, db_path, deux_albums, derriere_proxy):
    """Bob ÉCRIT sur c1 et LIT c2, sans aucune case : il voit tout, il ne sort rien. Un
    token dans chaque région, pour que les surfaces d'analyse aient de quoi rendre."""
    conn = sqlite3.connect(db_path)
    try:
        for r in ("r1", "r2"):
            conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                         "VALUES (?, 0, 'DIS', 'dire', 'VERB', '')", (deux_albums[r]["id"],))
        conn.commit()
    finally:
        conn.close()
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    _ouvrir(db_path, deux_albums["c2"], "bob")
    return {**deux_albums, "bob": {"Remote-User": "bob"}}


def test_toute_route_qui_sort_un_fichier_est_une_porte_declaree():
    """Le cliquet. Une route qui produit un fichier doit être une porte déclarée, ou être
    déclarée hors du droit avec sa raison ; et une déclaration sans route MENT."""
    routes = routes_api()
    exiger_plancher(len(routes), "portes de sortie (DROIT-2)")
    trouvees = {(m, r.path) for r in routes if _sort_un_fichier(r) for m in r.methods}
    declarees = PORTES | set(HORS_EXPORT)
    assert not trouvees - declarees, f"porte(s) non déclarée(s) : {sorted(trouvees - declarees)}"
    assert not declarees - trouvees, f"déclaration(s) sans route : {sorted(declarees - trouvees)}"


@pytest.mark.parametrize("porte", sorted(PORTES))
def test_une_porte_refuse_qui_lit_sans_la_case(client, sortie, porte):
    """Un compte en ÉCRITURE, sans la case, ne sort rien — ni le TEI de l'Atelier, ni une
    concordance, ni une figure. Et le refus est un 403 qui dit ce qui manque."""
    methode, url, params, corps = _requete(porte, sortie)
    rep = client.request(methode, url, params=params, json=corps, headers=sortie["bob"])
    assert rep.status_code == 403, (porte, rep.status_code, rep.text[:200])
    assert "export" in rep.json()["detail"].lower(), rep.text


@pytest.mark.parametrize("porte", sorted(PORTES - SANS_CONTRE_EPREUVE))
def test_la_meme_porte_s_ouvre_avec_la_case(client, db_path, sortie, porte):
    """La contre-épreuve, sans laquelle le refus ne prouverait rien : une porte qui refuse
    TOUT LE MONDE passerait le test précédent. Même compte, case cochée sur c1."""
    _poser_export(db_path, sortie["c1"], "bob")
    methode, url, params, corps = _requete(porte, sortie)
    rep = client.request(methode, url, params=params, json=corps, headers=sortie["bob"])
    assert rep.status_code == 200, (porte, rep.status_code, rep.text[:300])


def test_la_case_sur_a_n_emporte_pas_b(client, db_path, sortie):
    """La case sur c1 seulement. À l'écran, Bob voit les deux collections ; le fichier
    n'emporte que c1 — dans une concordance qui couvre les deux comme dans la Recherche."""
    _poser_export(db_path, sortie["c1"], "bob")
    bob = sortie["bob"]
    ecran = client.get("/api/analyse/concordance", params={"lemme": "dire"}, headers=bob)
    assert {ligne["album_titre"] for ligne in ecran.json()["results"]} == {"Autorisé", "Interdit"}
    fichier = client.get("/api/analyse/concordance.csv", params={"lemme": "dire"},
                         headers=bob).text
    assert "Autorisé" in fichier and "Interdit" not in fichier
    fichier = client.get("/api/recherche/export.csv", params={"q": "MOTSECRET"},
                         headers=bob).text
    assert "MOTSECRET ici" in fichier and "MOTSECRET ailleurs" not in fichier


def test_un_album_sort_au_titre_d_une_collection_nommee(client, db_path, sortie):
    """Tranché le 2026-09-11 : un album rangé dans plusieurs collections sort AU TITRE de
    l'une d'elles, où l'on a le droit, et l'export le dit. Le choix appartient à qui
    exporte dès qu'il y en a plus d'une."""
    c1, c2, a1, bob = sortie["c1"], sortie["c2"], sortie["a1"]["id"], sortie["bob"]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (c2, a1))
        conn.commit()
    finally:
        conn.close()
    _poser_export(db_path, c1, "bob")

    rep = client.get("/api/export/json", params={"album_id": a1}, headers=bob)
    assert rep.status_code == 200, rep.text
    assert rep.json()["exporte_au_titre_de"]["id"] == c1          # la seule ouverte
    rep = client.get("/api/export/json", params={"album_id": a1, "collection_id": c2},
                     headers=bob)
    assert rep.status_code == 403                 # lue, pas exportable : 403, pas 404
    rep = client.get("/api/export/json", params={"album_id": a1, "collection_id": 99999},
                     headers=bob)
    assert rep.status_code == 404

    _poser_export(db_path, c2, "bob")
    rep = client.get("/api/export/json", params={"album_id": a1}, headers=bob)
    assert rep.status_code == 422 and "Étude B" in rep.json()["detail"], rep.text
    rep = client.get("/api/export/tei", params={"album_id": a1, "collection_id": c2},
                     headers=bob)
    assert rep.status_code == 200 and "Étude B" in rep.text
    rep = client.get("/api/export/csv", params={"album_id": a1, "collection_id": c2},
                     headers=bob)
    assert f"_c{c2}" in rep.headers["content-disposition"]


def test_le_mono_poste_exporte_sans_rien_nommer(client, db_path, deux_albums):
    """Sans proxy, la portée est totale, export compris : rien à cocher, rien à nommer,
    même pour un album rangé dans deux collections — et l'export ne prétend alors sortir
    sous aucun droit particulier."""
    a1 = deux_albums["a1"]["id"]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (deux_albums["c2"], a1))
        conn.commit()
    finally:
        conn.close()
    rep = client.get("/api/export/json", params={"album_id": a1})
    assert rep.status_code == 200 and rep.json()["exporte_au_titre_de"] is None
    assert client.get("/api/recherche/export.csv",
                      params={"q": "MOTSECRET"}).status_code == 200


def test_ce_qui_sort_suit_la_portee_d_export_pas_celle_de_lecture(client, db_path, sortie):
    """Voir n'est pas emporter. Bob LIT c2 et n'y exporte rien. Un tag local à c2, posé sur
    une région de l'album qu'il exporte au titre de c1, lui est montré à l'écran — et ne
    part dans aucun des exports : l'album en trois formats, et la Recherche."""
    from conftest import ADMIN
    from test_autorisation import _poser_tag
    _poser_tag(db_path, "grille-b", sortie["c2"])
    r1, a1, bob = sortie["r1"]["id"], sortie["a1"]["id"], sortie["bob"]
    client.put(f"/api/regions/{r1}/annotation", json={"note": "", "tags": ["grille-b"]},
               headers=ADMIN)
    _poser_export(db_path, sortie["c1"], "bob")
    vus = {t["label"] for t in
           client.get(f"/api/regions/{r1}/annotation", headers=bob).json()["tags"]}
    assert vus == {"grille-b"}, "le décor doit montrer le tag à l'écran"
    for route, params in (("/api/export/json", {"album_id": a1}),
                          ("/api/export/csv", {"album_id": a1}),
                          ("/api/export/tei", {"album_id": a1}),
                          ("/api/recherche/export.csv", {"q": "MOTSECRET"})):
        rep = client.get(route, params=params, headers=bob)
        assert rep.status_code == 200, (route, rep.text)
        assert "MOTSECRET ici" in rep.text or route != "/api/recherche/export.csv"
        assert "grille-b" not in rep.text, (
            f"{route} emporte un terme qu'on lit sans pouvoir l'exporter")


def test_api_moi_dit_ce_qu_un_export_transversal_emportera(client, db_path, sortie):
    """La Recherche et l'Exploration n'ont aucune collection sous la main à qui demander
    `exportable` : `/api/moi` le leur dit, en trois états. « rien » passe AVANT la
    comparaison — sans quoi une portée vide, lecture et export vides donc égaux, se lirait
    « tout », et l'écran proposerait un export à qui n'a rien."""
    from conftest import ADMIN

    def etat(h):
        return client.get("/api/moi", headers=h).json()["acces"]["exporter"]

    bob = sortie["bob"]                       # écrit c1, lit c2, aucune case
    assert etat(bob) == "rien"
    _poser_export(db_path, sortie["c1"], "bob")
    assert etat(bob) == "partiel"
    _poser_export(db_path, sortie["c2"], "bob")
    assert etat(bob) == "tout"
    assert etat({"Remote-User": "personne"}) == "rien"      # portée vide
    assert etat(ADMIN) == "tout"
