"""Lexique situé SKOS (A4, niveau 7) — tests.

Vérifie la couche définitionnelle posée sur le vocabulaire ÉMERGENT (dimensions, valeurs
ET tags) : schéma v17 + migration, édition par l'API (definition/note_portee/etat/portée),
indicateur « % défini », promotion local→global (SET NULL), et propagation dans les exports
(records SKOS + paradonnée). L'UI (panneau Lexique) est auditée à part (e2e/axe).
"""
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import database  # noqa: E402


def _lire(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- #
# Schéma & migration
# --------------------------------------------------------------------------- #
def test_schema_lexique(db_path):
    conn = _lire(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    for t in ("attribut_dimension", "attribut_valeur"):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
        assert {"definition", "note_portee", "etat", "collection_id"} <= cols
    tcols = {r["name"] for r in conn.execute("PRAGMA table_info(tags)")}
    assert {"note_portee", "etat", "collection_id"} <= tcols   # description EST la définition


def test_migration_v16_vers_v17(tmp_path):
    """Depuis un schéma pré-v17 (vocabulaire sans couche définitionnelle, `collection`
    présente pour la FK), `_migrate` ajoute les colonnes et passe en v17."""
    db = tmp_path / "v16.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INT);"
        "CREATE TABLE regions (id INTEGER PRIMARY KEY, planche_id INT, type TEXT,"
        "  activite_id INT, touche INT, date_modification TEXT);"
        "CREATE TABLE activite (id INTEGER PRIMARY KEY);"
        "CREATE TABLE collection (id INTEGER PRIMARY KEY, nom TEXT);"
        "CREATE TABLE tags (id INTEGER PRIMARY KEY, label TEXT, description TEXT);"
        "CREATE TABLE attribut_dimension (id INTEGER PRIMARY KEY, cible TEXT, nom TEXT);"
        "CREATE TABLE attribut_valeur (id INTEGER PRIMARY KEY, dimension_id INT, valeur TEXT);"
        "PRAGMA user_version = 16;")
    database._migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    for t in ("attribut_dimension", "attribut_valeur"):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
        assert {"definition", "note_portee", "etat", "collection_id"} <= cols
    conn.close()


# --------------------------------------------------------------------------- #
# API — édition de la couche définitionnelle
# --------------------------------------------------------------------------- #
def _dim_val_tag(client, db_path):
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "registre"}).json()
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": "argot"}).json()
    conn = _lire(db_path)
    conn.execute("INSERT INTO tags (label, description) VALUES ('colere', 'glose')")
    conn.commit()
    tag_id = conn.execute("SELECT id FROM tags WHERE label='colere'").fetchone()["id"]
    conn.close()
    return dim, val, tag_id


def test_documenter_dimension_valeur_tag(client, db_path):
    dim, val, tag_id = _dim_val_tag(client, db_path)
    r = client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                     json={"definition": "niveau de langue", "note_portee": "oral",
                           "etat": "defini"})
    assert r.status_code == 200 and r.json()["definition"] == "niveau de langue"
    assert r.json()["etat"] == "defini" and r.json()["note_portee"] == "oral"
    client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                 json={"definition": "familier"})
    # Tag : la définition va dans `description` (sa glose EST la definition SKOS).
    rt = client.patch(f"/api/tags/{tag_id}/lexique",
                      json={"definition": "émotion", "etat": "defini"})
    assert rt.status_code == 200 and rt.json()["description"] == "émotion"

    lex = client.get("/api/lexique").json()
    assert lex["resume"]["definis"] == 2 and lex["resume"]["total"] == 3    # dim + tag définis
    assert lex["resume"]["pct_defini"] == round(2 / 3, 4)
    d0 = lex["dimensions"][0]
    assert d0["definition"] == "niveau de langue" and d0["valeurs"][0]["definition"] == "familier"


def test_etat_et_collection_valides(client, db_path):
    dim, val, tag_id = _dim_val_tag(client, db_path)
    assert client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                        json={"etat": "n'importe quoi"}).status_code == 422
    assert client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                        json={"collection_id": 99999}).status_code == 404


def test_portee_promotion_globale(client, db_path):
    """`collection_id` = portée d'appartenance ; supprimer la collection PROMEUT le terme en
    global (ON DELETE SET NULL), au lieu de perdre le vocabulaire (patron mentions→entités)."""
    dim, val, tag_id = _dim_val_tag(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('Étude X')")
    cid = conn.execute("SELECT id FROM collection WHERE nom='Étude X'").fetchone()["id"]
    conn.commit()
    conn.close()
    r = client.patch(f"/api/attributs/valeurs/{val['id']}/lexique", json={"collection_id": cid})
    assert r.json()["collection_id"] == cid
    # suppression de la collection → portée NULL (global), la valeur survit
    conn = _lire(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("DELETE FROM collection WHERE id = ?", (cid,))
    conn.commit()
    got = conn.execute("SELECT collection_id FROM attribut_valeur WHERE id = ?",
                       (val["id"],)).fetchone()
    conn.close()
    assert got["collection_id"] is None


def test_pct_defini_scope_collection(client, db_path):
    """L'indicateur % défini est scopable par APPARTENANCE (global ⊕ local à la collection)."""
    dim, val, tag_id = _dim_val_tag(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('C')")
    cid = conn.execute("SELECT id FROM collection WHERE nom='C'").fetchone()["id"]
    conn.commit()
    conn.close()
    # un terme local défini + les globaux non définis
    client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                 json={"collection_id": cid, "etat": "defini"})
    conn = _lire(db_path)
    glob = database.lexique_resume(conn)
    scoped = database.lexique_resume(conn, cid)
    conn.close()
    assert glob["total"] == 3                      # dim + val + tag
    assert scoped["total"] == 3 and scoped["definis"] == 1   # global (val,tag) ⊕ local défini (dim)


# --------------------------------------------------------------------------- #
# Export — colonnes SKOS + % défini
# --------------------------------------------------------------------------- #
def test_export_porte_le_lexique(client, db_path):
    dim, val, tag_id = _dim_val_tag(client, db_path)
    client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                 json={"definition": "niveau", "note_portee": "oral", "etat": "defini"})
    import metadonnees_collection as mc
    conn = _lire(db_path)
    doc = mc.collecter(conn)["metadonnees_collection"]
    v0 = doc["vocabulaire"][0]
    assert v0["definition"] == "niveau" and v0["note_portee"] == "oral" and v0["etat"] == "defini"
    assert "definition" in v0["valeurs"][0]                     # SKOS aussi au niveau valeur
    assert doc["paradonnee"]["lexique"]["definis"] == 1
    cols = mc.tables(conn)["vocabulaire"][0]
    conn.close()
    assert {"definition", "note_portee", "etat", "collection_id",
            "dim_definition", "dim_etat"} <= set(cols)


# --------------------------------------------------------------------------- #
# v24 sur les routes qui DÉPLACENT (COL-1)
#
# « Un terme n'est jamais plus GLOBAL que celui dont il dépend » était posé à la CRÉATION
# (une dimension hérite de son domaine, une valeur de sa dimension) et dans la MIGRATION
# qui a recollé l'existant. Les routes qui déplacent ne l'avaient jamais eu : mesuré le
# 2026-09-06, promouvoir une valeur sous une dimension privée répondait 200.
#
# Rien ne cassait, et c'est ce qui rend le défaut coûteux : `lexique_resume` compte par
# APPARTENANCE quand les listes filtrent le PARENT en plus du terme, si bien que le terme
# était compté dans le « % défini » de tout le monde et masqué de leurs listes.
# --------------------------------------------------------------------------- #
def _branche(client, db_path, nom="A"):
    """Une collection privée, et dessous domaine → dimension → valeur, tous locaux."""
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES (?)", (f"Incubateur {nom}",))
    cid = conn.execute("SELECT id FROM collection WHERE nom = ?",
                       (f"Incubateur {nom}",)).fetchone()["id"]
    conn.commit()
    conn.close()
    dom = client.post("/api/domaines", json={"nom": f"emotions{nom}"}).json()
    client.patch(f"/api/domaines/{dom['id']}/lexique", json={"collection_id": cid})
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "personnage", "nom": f"valence{nom}",
                            "domaine_id": dom["id"]}).json()
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": f"colere{nom}"}).json()
    return cid, dom["id"], dim["id"], val["id"]


def _portee(db_path, table, oid):
    conn = _lire(db_path)
    try:
        return conn.execute(f"SELECT collection_id FROM {table} WHERE id = ?",
                            (oid,)).fetchone()["collection_id"]
    finally:
        conn.close()


def test_promotion_refusee_si_un_ancetre_reste_local(client, db_path):
    """409, et il NOMME tout ce qui bloque — la chaîne fait trois niveaux au plus, donc il
    n'y a pas de raison d'en citer un et de laisser découvrir le reste au coup suivant."""
    cid, dom, dim, val = _branche(client, db_path)
    r = client.patch(f"/api/attributs/valeurs/{val}/lexique", json={"collection_id": None})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    # Les noms sont NORMALISÉS à la création (`_norm_tag` minuscule) : le message cite
    # donc ce que la base contient, pas ce qu'on a tapé.
    assert "valencea" in detail and "emotionsa" in detail, detail
    assert "restent locaux" in detail, "l'accord doit suivre le nombre d'ancêtres"
    assert "promouvoir_parents" in detail
    assert _portee(db_path, "attribut_valeur", val) == cid    # rien n'a bougé


def test_la_promotion_consentie_emporte_les_ancetres(client, db_path):
    """Le geste que COL-1 veut : promouvoir la branche. Il existe, mais il se DIT — et on
    ne l'écrit qu'après avoir lu le 409 qui nomme ce qu'il emporte."""
    cid, dom, dim, val = _branche(client, db_path)
    r = client.patch(f"/api/attributs/valeurs/{val}/lexique",
                     json={"collection_id": None, "promouvoir_parents": True})
    assert r.status_code == 200, r.text
    assert _portee(db_path, "domaine", dom) is None
    assert _portee(db_path, "attribut_dimension", dim) is None
    assert _portee(db_path, "attribut_valeur", val) is None
    # Et la réponse REND COMPTE : deux autres termes ont bougé sur une demande qui n'en
    # visait qu'un. Le 409 éclaire le consentement, ceci en montre la conséquence.
    promus = r.json()["promus"]
    promus_txt = " | ".join(promus)
    assert len(promus) == 2, promus
    assert "valencea" in promus_txt and "emotionsa" in promus_txt, promus


def test_un_tag_n_a_pas_de_parent_et_ne_bute_jamais(client, db_path):
    """`tags` est plat : aucune colonne ne le rattache. Sa promotion ne peut pas bloquer,
    et faire passer un tag par la garde serait inventer une dépendance qui n'existe pas."""
    _, _, tag_id = _dim_val_tag(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('Étude T')")
    cid = conn.execute("SELECT id FROM collection WHERE nom='Étude T'").fetchone()["id"]
    conn.commit()
    conn.close()
    client.patch(f"/api/tags/{tag_id}/lexique", json={"collection_id": cid})
    r = client.patch(f"/api/tags/{tag_id}/lexique", json={"collection_id": None})
    assert r.status_code == 200 and _portee(db_path, "tags", tag_id) is None


def test_plus_local_que_son_parent_reste_legitime(client, db_path):
    """La règle ne borde QUE le sens interdit. Un domaine promu seul laisse ses dimensions
    locales, et c'est le vocabulaire situé d'A4 — pas un état à réparer."""
    cid, dom, dim, val = _branche(client, db_path)
    r = client.patch(f"/api/domaines/{dom}/lexique", json={"collection_id": None})
    assert r.status_code == 200, r.text
    assert _portee(db_path, "domaine", dom) is None
    assert _portee(db_path, "attribut_dimension", dim) == cid


def test_rendre_un_terme_local_fait_DESCENDRE_la_portee(client, db_path):
    """L'autre sens de l'invariant : rendre un parent local laisserait ses enfants
    au-dessus de lui. C'est la logique de la migration v24, appliquée aux routes."""
    cid, dom, dim, val = _branche(client, db_path)
    client.patch(f"/api/attributs/valeurs/{val}/lexique",
                 json={"collection_id": None, "promouvoir_parents": True})
    assert _portee(db_path, "attribut_valeur", val) is None       # tout est global

    r = client.patch(f"/api/domaines/{dom}/lexique", json={"collection_id": cid})
    assert r.status_code == 200, r.text
    assert _portee(db_path, "attribut_dimension", dim) == cid
    assert _portee(db_path, "attribut_valeur", val) == cid        # descendu sur deux crans


def test_la_descente_epargne_un_terme_deja_local_ailleurs(client, db_path):
    """Réserve reprise de la migration v24 : un enfant déjà local à une AUTRE collection
    est un fait délibéré, pas une omission. L'écraser rangerait chez quelqu'un le
    vocabulaire de quelqu'un d'autre.

    **Nouvel attendu, daté du 2026-09-25 (AUTH-11, relecture de la troisième porte)** :
    c'est ici un RENVOI — le domaine est déjà dans sa collection —, et la descente de sa
    dimension globale laissait sa valeur « Ailleurs » sous une dimension devenue locale :
    l'état « hors de la collection de son parent ». La réserve tient (la valeur n'est pas
    écrasée), mais le renvoi juge désormais ce que la descente déplacerait : 409, qui
    nomme la valeur, et rien ne bouge."""
    cid, dom, dim, val = _branche(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('Ailleurs')")
    autre = conn.execute("SELECT id FROM collection WHERE nom='Ailleurs'").fetchone()["id"]
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (autre, val))
    conn.execute("UPDATE attribut_dimension SET collection_id = NULL WHERE id = ?", (dim,))
    conn.commit()
    conn.close()

    r = client.patch(f"/api/domaines/{dom}/lexique", json={"collection_id": cid})
    assert r.status_code == 409, r.text
    assert "la valeur « colerea », qui en dépend, vit dans" in r.json()["detail"], r.text
    assert _portee(db_path, "attribut_dimension", dim) is None     # ne descend pas
    assert _portee(db_path, "attribut_valeur", val) == autre       # épargnée


def test_la_descente_ne_range_pas_un_terme_hors_de_la_collection_de_son_parent(client,
                                                                              db_path):
    """Réserve reprise de la migration v24 : un enfant déjà local à une AUTRE collection
    est un fait délibéré, pas une omission. L'écraser rangerait chez quelqu'un le
    vocabulaire de quelqu'un d'autre.

    **Renversement daté (Hugo, 2026-09-25, AUTH-11)** : la réserve tient — on n'écrase
    toujours pas ce terme —, mais la descente ne le laisse plus derrière elle. Ranger le
    domaine faisait descendre la dimension globale et laissait sa valeur « Ailleurs » :
    une valeur rangée hors de la collection de sa dimension, l'état même que l'import et
    le rattachement refusent. Le rangement est donc refusé (409), et rien ne bouge."""
    cid, dom, dim, val = _branche(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('Ailleurs')")
    autre = conn.execute("SELECT id FROM collection WHERE nom='Ailleurs'").fetchone()["id"]
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (autre, val))
    conn.execute("UPDATE attribut_dimension SET collection_id = NULL WHERE id = ?", (dim,))
    conn.execute("UPDATE domaine SET collection_id = NULL WHERE id = ?", (dom,))
    conn.commit()
    conn.close()

    r = client.patch(f"/api/domaines/{dom}/lexique", json={"collection_id": cid})
    assert r.status_code == 409, r.text
    assert "valeur « colerea »" in r.json()["detail"], r.text
    assert _portee(db_path, "domaine", dom) is None
    assert _portee(db_path, "attribut_dimension", dim) is None
    assert _portee(db_path, "attribut_valeur", val) == autre


def _collection(db_path, nom):
    conn = _lire(db_path)
    try:
        cid = conn.execute("INSERT INTO collection (nom) VALUES (?)", (nom,)).lastrowid
        conn.commit()
        return cid
    finally:
        conn.close()


def _ranger(client, route, oid, cid):
    return client.patch(f"/api/{route}/{oid}/lexique", json={"collection_id": cid})


def test_ranger_un_terme_hors_de_la_collection_de_son_parent_ou_de_ses_enfants(client,
                                                                              db_path):
    """AUTH-11, tranché par Hugo le 2026-09-25 — la troisième porte. Ranger un terme dans
    une collection (`PATCH …/lexique {collection_id: C}`) déplaçait sa portée sans rien
    regarder autour : une dimension sous un domaine de A rangée dans B, une dimension de
    A dont la valeur restait en A rangée dans B — l'état « hors de la collection de son
    parent » que l'import (`parent_ailleurs`) et le rattachement (409) refusent déjà.

    Refusé désormais par un 409 qui nomme ce qui retient, pour les trois sortes de termes :
    parent ailleurs (dimension, valeur — un domaine n'a pas de parent), enfant ailleurs
    (domaine, dimension — une valeur n'a pas d'enfant). Rien ne bouge.

    Depuis l'option (β) du même jour, un enfant resté dans l'ANCIENNE collection d'une
    racine ne retient plus : il part avec elle (test suivant). L'enfant qui retient le
    domaine est donc ici d'une TROISIÈME collection — une seconde dimension, en C."""
    cid, dom, dim, val = _branche(client, db_path)          # tout en A
    autre = _collection(db_path, "Étude B")
    tierce = _collection(db_path, "Étude C")
    dim_c = client.post("/api/attributs/dimensions",
                        json={"cible": "case", "nom": "axe tiers", "domaine_id": dom}).json()
    conn = _lire(db_path)
    conn.execute("UPDATE attribut_dimension SET collection_id = ? WHERE id = ?",
                 (tierce, dim_c["id"]))
    conn.commit()
    conn.close()
    termes = (("domaine", dom), ("attribut_dimension", dim), ("attribut_valeur", val),
              ("attribut_dimension", dim_c["id"]))
    avant = {(t, i): _portee(db_path, t, i) for t, i in termes}
    cas = (("domaines", dom, "dimension « axe tiers »", "qui en dépend"),
           ("attributs/dimensions", dim, "domaine « emotionsa »", "dont il dépend"),
           ("attributs/valeurs", val, "dimension « valencea »", "dont il dépend"))
    for route, oid, nomme, lien in cas:
        r = _ranger(client, route, oid, autre)
        assert r.status_code == 409, (route, r.text)
        detail = r.json()["detail"]
        assert f"{nomme}, {lien}," in detail, detail
        assert "ne peut pas être rangé dans cette collection" in detail, detail
    assert {(t, i): _portee(db_path, t, i) for t, i in termes} == avant


def test_ranger_suit_son_parent_global_et_ses_enfants_globaux_ou_deja_la(client, db_path):
    """Anti-vacuité de la troisième porte : ce qui reste permis.

    - un parent GLOBAL convient : une dimension sous un domaine global se range dans B ;
    - des enfants GLOBAUX descendent, sur deux crans, comme avant ;
    - des enfants DÉJÀ dans B ne bougent pas et ne bloquent rien ;
    - un tag n'a ni parent ni enfant : il se range toujours ;
    - seul un DÉPLACEMENT est jugé : renvoyer à un terme la collection qu'il a déjà passe,
      même sur une base antérieure où un terme lié est rangé ailleurs (sans quoi on ne
      pourrait plus y rien éditer par le menu Portée) ;
    - la promotion vers Global garde ses règles (un ancêtre local la retient, 409)."""
    b = _collection(db_path, "Étude B")
    glob = client.post("/api/domaines", json={"nom": "partage"}).json()
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "cadrage",
                            "domaine_id": glob["id"]}).json()
    assert _ranger(client, "attributs/dimensions", dim["id"], b).status_code == 200
    assert _portee(db_path, "attribut_dimension", dim["id"]) == b

    haut = client.post("/api/domaines", json={"nom": "haut"}).json()
    d2 = client.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "axe haut", "domaine_id": haut["id"]}).json()
    v2 = client.post(f"/api/attributs/dimensions/{d2['id']}/valeurs",
                     json={"valeur": "vg"}).json()
    d3 = client.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "axe deja", "domaine_id": haut["id"]}).json()
    assert _ranger(client, "attributs/dimensions", d3["id"], b).status_code == 200
    r = _ranger(client, "domaines", haut["id"], b)
    assert r.status_code == 200, r.text
    assert _portee(db_path, "attribut_dimension", d2["id"]) == b      # global → descendu
    assert _portee(db_path, "attribut_valeur", v2["id"]) == b         # sur deux crans
    assert _portee(db_path, "attribut_dimension", d3["id"]) == b      # déjà là

    tag = client.post("/api/tags", json={"label": "motif"}).json()
    assert client.patch(f"/api/tags/{tag['id']}/lexique",
                        json={"collection_id": b}).status_code == 200

    a = _collection(db_path, "Étude A")
    conn = _lire(db_path)                  # base antérieure : une valeur de B passée en A
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (a, v2["id"]))
    conn.commit()
    conn.close()
    r = _ranger(client, "attributs/dimensions", d2["id"], b)       # déjà en B : rien ne bouge
    assert r.status_code == 200, r.text
    assert _ranger(client, "attributs/dimensions", d2["id"], a).status_code == 409
    conn = _lire(db_path)
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (b, v2["id"]))
    conn.commit()
    conn.close()

    r = client.patch(f"/api/attributs/valeurs/{v2['id']}/lexique", json={"collection_id": None})
    assert r.status_code == 409 and "promouvoir_parents" in r.json()["detail"], r.text


def test_le_cas_du_relecteur_ranger_emporte_la_valeur_puis_le_rattachement_passe(client,
                                                                                 db_path):
    """Le chemin mesuré le 2026-09-25 par la relecture de `bef0b83` : une dimension de A
    porte une valeur de A ; la rattacher à un domaine de B répond 409 et conseille de
    ranger d'abord la dimension dans B ; ce rangement répondait 200, et la valeur RESTAIT
    en A — une valeur de A sous une dimension de B.

    Refusé au premier jet de la troisième porte, ce rangement répond de nouveau 200 depuis
    l'option (β) tranchée par Hugo le même jour — mais la valeur SUIT : la dimension, sans
    domaine, est la racine de sa branche, et emporte ce qui était avec elle dans A. Le
    conseil du 409 du rattachement devient vrai, et le rattachement passe ensuite ; il ne
    promet toujours pas que le rangement réussira (un terme d'une troisième collection le
    retiendrait)."""
    a = _collection(db_path, "Étude A")
    b = _collection(db_path, "Étude B")
    dom = client.post("/api/domaines", json={"nom": "champ b"}).json()
    assert _ranger(client, "domaines", dom["id"], b).status_code == 200
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "axe a"}).json()
    assert _ranger(client, "attributs/dimensions", dim["id"], a).status_code == 200
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": "val a"}).json()
    assert _portee(db_path, "attribut_valeur", val["id"]) == a

    r = client.patch(f"/api/attributs/dimensions/{dim['id']}/domaine",
                     json={"domaine_id": dom["id"]})
    assert r.status_code == 409, r.text
    assert "Rangez d'abord" in r.json()["detail"]
    assert "refus" in r.json()["detail"], "le conseil promet un rangement qui peut échouer"
    r = _ranger(client, "attributs/dimensions", dim["id"], b)
    assert r.status_code == 200, r.text
    assert _portee(db_path, "attribut_dimension", dim["id"]) == b
    assert _portee(db_path, "attribut_valeur", val["id"]) == b         # emportée
    r = client.patch(f"/api/attributs/dimensions/{dim['id']}/domaine",
                     json={"domaine_id": dom["id"]})
    assert r.status_code == 200 and r.json()["domaine_id"] == dom["id"], r.text


def test_ranger_la_racine_emporte_sa_branche_en_un_geste(client, db_path):
    """AUTH-11, option (β) tranchée par Hugo le 2026-09-25. La troisième porte fermée, une
    branche entièrement locale à A ne se déplaçait plus vers B que par Global : chaque pas
    séparait un terme de son voisin, et la seule issue était `promouvoir_parents` puis le
    rangement de la racine — la branche PUBLIQUE entre les deux gestes.

    Ranger la RACINE (un terme sans parent local) de A vers B emporte désormais, d'un seul
    geste, ses descendants rangés dans A : un domaine, ses deux dimensions et leurs valeurs
    (des petits-enfants). Les descendants GLOBAUX descendent comme avant ; ceux déjà dans
    B ne bougent pas — y compris une valeur globale sous une dimension EMPORTÉE, que la
    descente depuis la racine ne traverse pas. La réponse nomme les emportés dans
    `promus`, avec ce qui a été promu — ils étaient dans A, donc lisibles de qui range."""
    a = _collection(db_path, "Étude A")
    b = _collection(db_path, "Étude B")
    dom = client.post("/api/domaines", json={"nom": "racine"}).json()["id"]
    assert _ranger(client, "domaines", dom, a).status_code == 200
    d1 = client.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "axe un", "domaine_id": dom}).json()["id"]
    d2 = client.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "axe deux", "domaine_id": dom}).json()["id"]
    def valeur(dim, nom):
        return client.post(f"/api/attributs/dimensions/{dim}/valeurs",
                           json={"valeur": nom}).json()["id"]
    v1, v2, vb = valeur(d1, "v un"), valeur(d2, "v deux"), valeur(d2, "v b")
    vglob = valeur(d1, "v globale")
    dg = client.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "axe global", "domaine_id": dom}).json()["id"]
    vg = valeur(dg, "v g")
    conn = _lire(db_path)
    conn.execute("UPDATE attribut_valeur SET collection_id = NULL WHERE id = ?", (vglob,))
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (b, vb))
    conn.execute("UPDATE attribut_dimension SET collection_id = NULL WHERE id = ?", (dg,))
    conn.execute("UPDATE attribut_valeur SET collection_id = NULL WHERE id = ?", (vg,))
    conn.commit()
    conn.close()
    assert {_portee(db_path, "attribut_dimension", d) for d in (d1, d2)} == {a}

    r = _ranger(client, "domaines", dom, b)
    assert r.status_code == 200, r.text
    assert _portee(db_path, "domaine", dom) == b
    for t, i in (("attribut_dimension", d1), ("attribut_dimension", d2),
                 ("attribut_valeur", v1), ("attribut_valeur", v2),     # petits-enfants
                 ("attribut_valeur", vb),                               # déjà en B
                 ("attribut_valeur", vglob),         # globale sous un emporté : descend
                 ("attribut_dimension", dg), ("attribut_valeur", vg)):  # globaux : descendent
        assert _portee(db_path, t, i) == b, (t, i)
    assert sorted(r.json()["promus"]) == sorted(
        ["dimension « axe un »", "dimension « axe deux »",
         "valeur « v un »", "valeur « v deux »"]), r.json()


def test_une_branche_a_moitie_ailleurs_ou_depuis_global_ne_part_pas(client, db_path):
    """Ce que (β) ne change pas, et que le 409 retient toujours :

    - un descendant d'une TROISIÈME collection (ni A ni B) : il ne part pas, et la racine
      non plus — rien ne bouge ;
    - le MILIEU d'une branche (une dimension sous un domaine de A) ne se range pas seul :
      son parent est ailleurs ;
    - un terme dont le parent est DÉJÀ dans B (état croisé d'une base antérieure) n'est
      pas une racine : il n'emporte rien, et sa valeur restée en A le retient ;
    - depuis GLOBAL, rien n'est emporté : une racine globale dont un descendant est en A
      ne se range pas dans B (la privatisation d'un terme global reste une case à part,
      avec COL-1)."""
    a = _collection(db_path, "Étude A")
    b = _collection(db_path, "Étude B")
    c = _collection(db_path, "Étude C")
    dom = client.post("/api/domaines", json={"nom": "racine"}).json()["id"]
    assert _ranger(client, "domaines", dom, a).status_code == 200
    d1 = client.post("/api/attributs/dimensions",
                     json={"cible": "case", "nom": "axe un", "domaine_id": dom}).json()["id"]
    v1, vc = (client.post(f"/api/attributs/dimensions/{d1}/valeurs",
                          json={"valeur": n}).json()["id"] for n in ("v un", "v c"))
    conn = _lire(db_path)
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (c, vc))
    conn.commit()
    conn.close()
    termes = (("domaine", dom), ("attribut_dimension", d1), ("attribut_valeur", v1),
              ("attribut_valeur", vc))
    avant = {(t, i): _portee(db_path, t, i) for t, i in termes}

    r = _ranger(client, "domaines", dom, b)
    assert r.status_code == 409, r.text
    assert "valeur « v c », qui en dépend," in r.json()["detail"], r.text
    assert "v un" not in r.json()["detail"], r.text            # emportable : ne retient pas
    r = _ranger(client, "attributs/dimensions", d1, b)
    assert r.status_code == 409, r.text
    assert "domaine « racine », dont il dépend," in r.json()["detail"], r.text
    assert {(t, i): _portee(db_path, t, i) for t, i in termes} == avant

    dom_b = client.post("/api/domaines", json={"nom": "champ b"}).json()["id"]
    assert _ranger(client, "domaines", dom_b, b).status_code == 200
    d_x = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "axe croise", "domaine_id": dom_b}).json()["id"]
    v_x = client.post(f"/api/attributs/dimensions/{d_x}/valeurs",
                      json={"valeur": "v croisee"}).json()["id"]
    conn = _lire(db_path)                  # base antérieure : dimension et valeur restées en A
    conn.execute("UPDATE attribut_dimension SET collection_id = ? WHERE id = ?", (a, d_x))
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (a, v_x))
    conn.commit()
    conn.close()
    r = _ranger(client, "attributs/dimensions", d_x, b)
    assert r.status_code == 409, r.text
    assert "valeur « v croisee », qui en dépend," in r.json()["detail"], r.text
    assert _portee(db_path, "attribut_valeur", v_x) == a

    glob = client.post("/api/domaines", json={"nom": "commun"}).json()["id"]
    dga = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "axe de a", "domaine_id": glob}).json()["id"]
    assert _ranger(client, "attributs/dimensions", dga, a).status_code == 200
    r = _ranger(client, "domaines", glob, b)
    assert r.status_code == 409, r.text
    assert "dimension « axe de a », qui en dépend," in r.json()["detail"], r.text
    assert _portee(db_path, "domaine", glob) is None
    assert _portee(db_path, "attribut_dimension", dga) == a

def test_une_racine_sous_un_parent_global_ou_rangee_avec_son_parent(client, db_path):
    """Deux cas courants que les mutants de la relecture ont montrés sans test.

    - Une dimension LOCALE sous un domaine GLOBAL est une racine : rangée de A vers B, elle
      emporte ses valeurs de A (juger la racine sur « pas de parent du tout » la rendrait
      milieu de branche, et ses valeurs la retiendraient).
    - Ranger un terme dans la collection de son PARENT passe, même sur une base antérieure
      où il vivait ailleurs : une valeur de A sous une dimension de B, rangée dans B, la
      rejoint (refuser tout parent local, fût-il dans la cible, l'interdirait)."""
    a = _collection(db_path, "Étude A")
    b = _collection(db_path, "Étude B")
    glob = client.post("/api/domaines", json={"nom": "commun"}).json()["id"]
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "axe local", "domaine_id": glob}).json()["id"]
    assert _ranger(client, "attributs/dimensions", dim, a).status_code == 200
    val = client.post(f"/api/attributs/dimensions/{dim}/valeurs",
                      json={"valeur": "v locale"}).json()["id"]
    assert _portee(db_path, "attribut_valeur", val) == a
    r = _ranger(client, "attributs/dimensions", dim, b)
    assert r.status_code == 200, r.text
    assert _portee(db_path, "attribut_valeur", val) == b
    assert r.json()["promus"] == ["valeur « v locale »"]

    dim_b = client.post("/api/attributs/dimensions",
                        json={"cible": "case", "nom": "axe de b"}).json()["id"]
    assert _ranger(client, "attributs/dimensions", dim_b, b).status_code == 200
    v_a = client.post(f"/api/attributs/dimensions/{dim_b}/valeurs",
                      json={"valeur": "v restee"}).json()["id"]
    conn = _lire(db_path)                  # base antérieure : la valeur vit en A
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (a, v_a))
    conn.commit()
    conn.close()
    r = _ranger(client, "attributs/valeurs", v_a, b)
    assert r.status_code == 200, r.text
    assert _portee(db_path, "attribut_valeur", v_a) == b

def test_ranger_un_domaine_sous_le_verrou_ne_laisse_rien_derriere(client, db_path):
    """AUTH-11, 2026-09-25 — l'angle mort répété du chantier : le verrou d'écriture. La
    garde du rangement lit la branche, puis l'écrit ; sans `conflit.verrouiller`, une
    dimension créée ENTRE les deux (sur une autre connexion, comme le ferait
    `POST /api/attributs/dimensions {domaine_id}` : elle naît dans la collection de son
    domaine, A) échappait au jugement, et restait en A sous un domaine désormais en B —
    l'état que (β) interdit. Mesuré par la relecture, et c'est ce test qui le rejoue.

    La connexion de la route est enveloppée (`dependency_overrides[socle.db]`) pour
    intercaler la création juste avant l'UPDATE du domaine. Sous le verrou, la création
    concurrente attend puis renonce (`busy_timeout` court) : rien ne naît derrière. Sans
    lui, elle passe, et la dimension reste en A — le test tombe. L'invariant vérifié est
    celui de (β), quoi qu'il se soit passé : toute dimension du domaine est dans B."""
    import main
    import socle

    conn = _lire(db_path)
    a = conn.execute("INSERT INTO collection (nom) VALUES ('Course A')").lastrowid
    b = conn.execute("INSERT INTO collection (nom) VALUES ('Course B')").lastrowid
    dom = conn.execute("INSERT INTO domaine (nom, collection_id) VALUES ('course', ?)",
                       (a,)).lastrowid
    conn.execute("INSERT INTO attribut_dimension (cible, nom, domaine_id, collection_id) "
                 "VALUES ('case', 'axe premier', ?, ?)", (dom, a))
    conn.commit()
    conn.close()
    concurrence = {}

    def creer_en_concurrence():
        c2 = database.get_connection()
        c2.execute("PRAGMA busy_timeout = 200")
        try:
            c2.execute("BEGIN IMMEDIATE")
            c2.execute("INSERT INTO attribut_dimension (cible, nom, domaine_id, "
                       "collection_id) VALUES ('case', 'axe intercale', ?, ?)", (dom, a))
            c2.commit()
            concurrence["passee"] = True
        except sqlite3.OperationalError:
            concurrence["passee"] = False               # le verrou l'a tenue à l'écart
        finally:
            c2.close()

    class Enveloppe:
        def __init__(self, c):
            self._c, self._fait = c, False

        def execute(self, sql, *args):
            if not self._fait and sql.startswith("UPDATE domaine SET"):
                self._fait = True
                creer_en_concurrence()
            return self._c.execute(sql, *args)

        def __getattr__(self, nom):
            return getattr(self._c, nom)

    def db_enveloppee():
        c = database.get_connection()
        try:
            yield Enveloppe(c)
        finally:
            c.close()

    main.app.dependency_overrides[socle.db] = db_enveloppee
    try:
        r = client.patch(f"/api/domaines/{dom}/lexique", json={"collection_id": b})
    finally:
        main.app.dependency_overrides.pop(socle.db, None)
    assert r.status_code == 200, r.text
    assert "passee" in concurrence, "la création concurrente n'a pas été intercalée"
    conn = _lire(db_path)
    try:
        restees = conn.execute("SELECT nom FROM attribut_dimension WHERE domaine_id = ? "
                               "AND collection_id IS NOT ?", (dom, b)).fetchall()
    finally:
        conn.close()
    assert not restees, [tuple(x) for x in restees]
    assert concurrence["passee"] is False



def test_rattacher_une_dimension_ne_deplace_jamais_sa_portee(client, db_path):
    """Second chemin vers l'état interdit, et il n'y avait aucune promotion : une dimension
    GLOBALE passée sous un domaine PRIVÉ y restait globale. Ce qui fuyait n'était pas un
    mot mais le NOM DE L'AXE — la grille d'analyse d'une collection fermée.

    v24 la faisait DESCENDRE dans la collection du domaine, ses valeurs globales avec elle —
    ce qui la retirait sans un mot à toutes les autres collections. **Renversement daté
    (Hugo, 2026-09-24)** : un rattachement ne déplace plus jamais une portée. L'état
    interdit reste interdit, mais par un REFUS : 409, qui dit de ranger d'abord la
    dimension dans la collection du domaine. Ranger (`PATCH …/lexique`) reste le geste qui
    fait descendre la portée, et après lui le rattachement passe."""
    cid, dom, _, _ = _branche(client, db_path)
    libre = client.post("/api/attributs/dimensions",
                        json={"cible": "case", "nom": "cadrage"}).json()
    vlibre = client.post(f"/api/attributs/dimensions/{libre['id']}/valeurs",
                         json={"valeur": "plongee"}).json()
    assert _portee(db_path, "attribut_dimension", libre["id"]) is None

    r = client.patch(f"/api/attributs/dimensions/{libre['id']}/domaine",
                     json={"domaine_id": dom})
    assert r.status_code == 409, r.text
    assert "Rangez d'abord" in r.json()["detail"]
    assert _portee(db_path, "attribut_dimension", libre["id"]) is None
    assert _portee(db_path, "attribut_valeur", vlibre["id"]) is None     # rien n'a bougé

    client.patch(f"/api/attributs/dimensions/{libre['id']}/lexique", json={"collection_id": cid})
    assert _portee(db_path, "attribut_valeur", vlibre["id"]) == cid      # ranger, lui, descend
    r = client.patch(f"/api/attributs/dimensions/{libre['id']}/domaine",
                     json={"domaine_id": dom})
    assert r.status_code == 200 and r.json()["domaine_id"] == dom, r.text


def test_rattacher_une_dimension_locale_a_un_domaine_global_ne_la_promeut_pas(client,
                                                                             db_path):
    """L'autre moitié du renversement du 2026-09-24 : sous v24, rattacher une dimension
    LOCALE à un domaine GLOBAL la rendait globale — elle et son nom, publiés à toute
    l'instance par un geste de rangement. Désormais permis, et rien ne bouge : un terme
    plus local que son parent est légitime (A4)."""
    cid, _, dim, _ = _branche(client, db_path)
    glob = client.post("/api/domaines", json={"nom": "partage"}).json()
    r = client.patch(f"/api/attributs/dimensions/{dim}/domaine",
                     json={"domaine_id": glob["id"]})
    assert r.status_code == 200 and r.json()["domaine_id"] == glob["id"], r.text
    assert _portee(db_path, "attribut_dimension", dim) == cid


def test_detacher_une_dimension_ne_la_promeut_pas(client, db_path):
    """Créer sans domaine naît global ; DÉTACHER n'est pas le même geste. Sortir une
    dimension de son domaine est un rangement — la rendre globale au passage serait une
    publication que personne n'a demandée, soit la classe de défaut réparée ici."""
    cid, dom, dim, val = _branche(client, db_path)
    r = client.patch(f"/api/attributs/dimensions/{dim}/domaine", json={"domaine_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["domaine_id"] is None
    assert _portee(db_path, "attribut_dimension", dim) == cid
