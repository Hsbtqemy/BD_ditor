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
    vocabulaire de quelqu'un d'autre."""
    cid, dom, dim, val = _branche(client, db_path)
    conn = _lire(db_path)
    conn.execute("INSERT INTO collection (nom) VALUES ('Ailleurs')")
    autre = conn.execute("SELECT id FROM collection WHERE nom='Ailleurs'").fetchone()["id"]
    conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?", (autre, val))
    conn.execute("UPDATE attribut_dimension SET collection_id = NULL WHERE id = ?", (dim,))
    conn.commit()
    conn.close()

    client.patch(f"/api/domaines/{dom}/lexique", json={"collection_id": cid})
    assert _portee(db_path, "attribut_dimension", dim) == cid     # global → descendu
    assert _portee(db_path, "attribut_valeur", val) == autre      # déjà placé → épargné


def test_rattacher_une_dimension_lui_donne_la_portee_du_domaine(client, db_path):
    """Second chemin vers l'état interdit, et il n'y avait aucune promotion : une dimension
    GLOBALE passée sous un domaine PRIVÉ y restait globale. Ce qui fuyait n'était pas un
    mot mais le NOM DE L'AXE — la grille d'analyse d'une collection fermée."""
    cid, dom, _, _ = _branche(client, db_path)
    libre = client.post("/api/attributs/dimensions",
                        json={"cible": "case", "nom": "cadrage"}).json()
    vlibre = client.post(f"/api/attributs/dimensions/{libre['id']}/valeurs",
                         json={"valeur": "plongee"}).json()
    assert _portee(db_path, "attribut_dimension", libre["id"]) is None

    r = client.patch(f"/api/attributs/dimensions/{libre['id']}/domaine",
                     json={"domaine_id": dom})
    assert r.status_code == 200, r.text
    assert _portee(db_path, "attribut_dimension", libre["id"]) == cid
    assert _portee(db_path, "attribut_valeur", vlibre["id"]) == cid   # descendue aussi


def test_detacher_une_dimension_ne_la_promeut_pas(client, db_path):
    """Créer sans domaine naît global ; DÉTACHER n'est pas le même geste. Sortir une
    dimension de son domaine est un rangement — la rendre globale au passage serait une
    publication que personne n'a demandée, soit la classe de défaut réparée ici."""
    cid, dom, dim, val = _branche(client, db_path)
    r = client.patch(f"/api/attributs/dimensions/{dim}/domaine", json={"domaine_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["domaine_id"] is None
    assert _portee(db_path, "attribut_dimension", dim) == cid
