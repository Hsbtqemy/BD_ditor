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
