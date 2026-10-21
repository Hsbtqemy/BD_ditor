"""ANN-8 — annuler la suppression d'une région rend aussi ses LIENS.

Reproduit le 2026-10-21, antérieur : une case avec une situation, dessous un cartouche avec
locuteur, note et tag ; supprimer la case, puis Ctrl+Z — case, cartouche, note et tag
reviennent, le locuteur du cartouche et la situation de la case non. L'instantané profond
n'emportait que les colonnes d'une région et son annotation ; le CASCADE, lui, emportait
aussi `bulle_locuteur`, `personnage_presence` et `region_attribut`.

Ce qui revient se décide lien par lien, sous les trois questions d'AUTH-14 : l'objet
désigné existe-t-il encore, est-il celui de l'acte, l'agent le voit-il maintenant. Un lien
qui échoue ne revient pas ; la région, elle, revient — c'est l'objet de l'acte —, et la
réponse dit COMBIEN de liens sont restés en route, sans rien dire de l'objet.
"""
import sqlite3

from conftest import ADMIN, make_png


def _sql(db_path, q, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _ok(r, *codes):
    assert r.status_code in codes, (r.status_code, r.text)
    return r


def _region(client, planche_id, headers=ADMIN, **kw):
    corps = {"type": "case", "x": 0, "y": 0, "w": 50, "h": 50, **kw}
    return _ok(client.post(f"/api/planches/{planche_id}/regions", json=corps,
                           headers=headers), 201).json()["id"]


def _valeur(client, cible, dimension, valeur):
    d = _ok(client.post("/api/attributs/dimensions", json={"cible": cible, "nom": dimension},
                        headers=ADMIN), 200, 201).json()["id"]
    return _ok(client.post(f"/api/attributs/dimensions/{d}/valeurs", json={"valeur": valeur},
                           headers=ADMIN), 200, 201).json()["id"]


def _perso(client, nom, headers=ADMIN):
    return _ok(client.post("/api/personnages", json={"nom": nom}, headers=headers),
               200, 201).json()["id"]


def _liens(db_path, rid):
    """Ce qui pend à une région : son locuteur, sa présence, ses attributs."""
    def un(table):
        r = _sql(db_path, f"SELECT personnage_id FROM {table} WHERE region_id = ?", (rid,))
        return r[0]["personnage_id"] if r else None
    return {"locuteur": un("bulle_locuteur"), "presence": un("personnage_presence"),
            "attributs": [r["valeur_id"] for r in _sql(
                db_path, "SELECT valeur_id FROM region_attribut WHERE region_id = ? "
                         "ORDER BY valeur_id", (rid,))]}


def _decor(client, planche):
    """Le décor du retour d'usage : une case avec une situation, dessous un cartouche avec
    locuteur, note et tag, et une boîte personnage qui montre quelqu'un."""
    pid = planche["id"]
    case = _region(client, pid)
    cartouche = _region(client, pid, type="cartouche", parent_id=case, w=20, h=10)
    boite = _region(client, pid, type="personnage", parent_id=case, x=25, w=20, h=20)
    lieu = _valeur(client, "case", "lieu", "falaise")
    tintin, milou = _perso(client, "Tintin"), _perso(client, "Milou")
    _ok(client.put(f"/api/regions/{case}/attributs", json={"valeur_id": lieu}, headers=ADMIN), 200)
    _ok(client.put(f"/api/regions/{cartouche}/locuteur", json={"personnage_id": tintin},
                   headers=ADMIN), 200)
    _ok(client.put(f"/api/regions/{boite}/personnage", json={"personnage_id": milou},
                   headers=ADMIN), 200)
    _ok(client.put(f"/api/regions/{cartouche}/annotation",
                   json={"note": "voix off", "tags": ["récit"]}, headers=ADMIN), 200)
    return {"case": case, "cartouche": cartouche, "boite": boite, "lieu": lieu,
            "tintin": tintin, "milou": milou}


def test_annuler_la_suppression_rend_locuteur_presence_et_situation(client, planche, db_path):
    d = _decor(client, planche)
    _ok(client.delete(f"/api/regions/{d['case']}", headers=ADMIN), 204)
    assert _liens(db_path, d["cartouche"]) == {"locuteur": None, "presence": None, "attributs": []}

    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert (res["acte"], res["cible_table"]) == ("suppression", "regions")
    assert res["liens_non_rendus"] == 0
    assert _liens(db_path, d["case"])["attributs"] == [d["lieu"]]
    assert _liens(db_path, d["cartouche"])["locuteur"] == d["tintin"]
    assert _liens(db_path, d["boite"])["presence"] == d["milou"]
    # Ce qui revenait déjà revient toujours.
    assert _sql(db_path, "SELECT note FROM annotations WHERE region_id = ?",
                (d["cartouche"],))[0]["note"] == "voix off"
    # Et l'écran le relit par ses routes, pas seulement en base.
    assert client.get(f"/api/regions/{d['cartouche']}/locuteur").json()["locuteur"]["id"] == d["tintin"]
    assert [a["valeur"] for a in client.get(f"/api/regions/{d['case']}/attributs").json()] == ["falaise"]


def test_l_instantane_de_suppression_porte_les_liens(client, planche, db_path):
    """Le journal garde les IDENTIFIANTS des liens, et seulement eux : aucun nom de
    personnage, aucun mot du vocabulaire n'entre dans l'instantané."""
    import json
    d = _decor(client, planche)
    _ok(client.delete(f"/api/regions/{d['case']}", headers=ADMIN), 204)
    avant = json.loads(_sql(db_path, "SELECT avant FROM evenement WHERE type = 'suppression' "
                                     "AND cible_table = 'regions' ORDER BY id DESC LIMIT 1")[0]["avant"])
    assert avant["attributs"] == [d["lieu"]]
    enfants = {e["id"]: e for e in avant["enfants"]}
    assert enfants[d["cartouche"]]["locuteur"] == d["tintin"]
    assert enfants[d["boite"]]["presence"] == d["milou"]
    brut = json.dumps(avant, ensure_ascii=False)
    for mot in ("Tintin", "Milou", "falaise", "lieu"):
        assert mot not in brut, f"« {mot} » est entré dans l'instantané : {brut}"


def test_un_lien_dont_l_objet_a_disparu_ne_revient_pas_et_se_compte(client, planche, db_path):
    """Le personnage supprimé entre-temps, la valeur aussi : la case et le cartouche
    reviennent, sans ces deux liens — ils seraient partis de toute façon avec ce qu'ils
    désignaient. La présence, elle, revient."""
    d = _decor(client, planche)
    _ok(client.delete(f"/api/regions/{d['case']}", headers=ADMIN), 204)
    _ok(client.delete(f"/api/personnages/{d['tintin']}", headers=ADMIN), 200, 204)
    _ok(client.delete(f"/api/attributs/valeurs/{d['lieu']}", headers=ADMIN), 200, 204)

    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["acte"] == "suppression"
    assert res["liens_non_rendus"] == 2
    assert _liens(db_path, d["case"]) == {"locuteur": None, "presence": None, "attributs": []}
    assert _liens(db_path, d["cartouche"])["locuteur"] is None
    assert _liens(db_path, d["boite"])["presence"] == d["milou"]


def test_une_valeur_nee_apres_l_acte_n_est_pas_celle_de_la_case(client, planche, db_path):
    """`attribut_valeur` n'a pas d'`AUTOINCREMENT` : la valeur supprimée rend son
    identifiant à la suivante. Née APRÈS la suppression, ce n'est plus la situation de la
    case, et elle ne s'y pose pas."""
    d = _decor(client, planche)
    _ok(client.delete(f"/api/regions/{d['case']}", headers=ADMIN), 204)
    _ok(client.delete(f"/api/attributs/valeurs/{d['lieu']}", headers=ADMIN), 200, 204)
    autre = _valeur(client, "case", "lieu", "grotte")
    assert autre == d["lieu"], "le décor suppose l'identifiant repris"
    # Les dates sont à la seconde : la reprise est datée après l'acte, comme elle le serait.
    _sql(db_path, "UPDATE attribut_valeur SET date_creation = datetime('now', '+1 minute') "
                  "WHERE id = ?", (autre,))

    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert res["liens_non_rendus"] == 1
    assert _liens(db_path, d["case"])["attributs"] == []


def test_un_personnage_que_l_agent_ne_voit_plus_ne_revient_pas(client, planche, db_path,
                                                               derriere_proxy):
    """Sous cloisonnement : Tintin parle dans le cartouche d'alice ET dans une bulle de
    l'Incubateur, qu'alice ne lit pas. Le cartouche supprimé, Tintin n'apparaît plus que
    là où alice n'entre pas : il ne lui est plus visible, et Ctrl+Z ne le repose pas —
    la région revient, et le compte dit qu'un lien manque."""
    alice = {"Remote-User": "alice"}
    principale = _ok(client.post("/api/collections", json={"nom": "Principale"}, headers=ADMIN),
                     201).json()["id"]
    incubateur = _ok(client.post("/api/collections", json={"nom": "Incubateur"}, headers=ADMIN),
                     201).json()["id"]
    _ok(client.put(f"/api/collections/{principale}/acces", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": "alice", "niveau": "ecriture"}), 200)

    def planche_de(cid):
        aid = _ok(client.post("/api/albums", json={"titre": f"A{cid}", "collection_id": cid},
                              headers=ADMIN), 201).json()["id"]
        return _ok(client.post(f"/api/albums/{aid}/import", headers=ADMIN,
                               files={"file": ("p.png", make_png(), "image/png")}), 201).json()["id"]

    ici, ailleurs = planche_de(principale), planche_de(incubateur)
    tintin = _perso(client, "Tintin")
    cartouche = _region(client, ici, headers=alice, type="cartouche")
    bulle = _region(client, ailleurs, type="bulle")
    _ok(client.put(f"/api/regions/{cartouche}/locuteur", json={"personnage_id": tintin},
                   headers=alice), 200)
    _ok(client.put(f"/api/regions/{bulle}/locuteur", json={"personnage_id": tintin},
                   headers=ADMIN), 200)
    _ok(client.delete(f"/api/regions/{cartouche}", headers=alice), 204)
    assert tintin not in [p["id"] for p in client.get("/api/personnages?q=Tintin",
                                                     headers=alice).json()]

    res = _ok(client.post("/api/undo", headers=alice), 200).json()
    assert res["acte"] == "suppression" and res["liens_non_rendus"] == 1
    assert _sql(db_path, "SELECT 1 FROM regions WHERE id = ?", (cartouche,))
    assert _liens(db_path, cartouche)["locuteur"] is None
    assert "Tintin" not in str(res)


# --------------------------------------------------------------------------- #
# ANN-8 — le premier Ctrl+Z après un redémarrage ne paie le moteur de langue que s'il sert
# --------------------------------------------------------------------------- #
def _charges(monkeypatch):
    """Compte les chargements du moteur de langue que demande la route d'annulation."""
    import routes.annulation as route
    appels = []
    monkeypatch.setattr(route.nlp, "ensure_loaded", lambda: appels.append(1))
    return appels


def test_annuler_un_locuteur_ne_charge_pas_le_moteur_de_langue(client, zone_de_texte,
                                                                monkeypatch):
    """Mesuré : 9 à 17 s sans rien afficher au premier Ctrl+Z, le temps de charger spaCy —
    que défaire un lien de locuteur n'emploie pas : il ne réindexe rien."""
    tintin = _perso(client, "Tintin")
    _ok(client.put(f"/api/regions/{zone_de_texte['id']}/locuteur",
                   json={"personnage_id": tintin}, headers=ADMIN), 200)
    appels = _charges(monkeypatch)
    res = _ok(client.post("/api/undo", headers=ADMIN), 200).json()
    assert (res["acte"], res["cible_table"]) == ("lien", "bulle_locuteur")
    assert appels == []


def test_annuler_la_creation_d_une_region_ne_charge_pas_le_moteur(client, planche,
                                                                  monkeypatch):
    _region(client, planche["id"])
    appels = _charges(monkeypatch)
    assert _ok(client.post("/api/undo", headers=ADMIN), 200).json()["acte"] == "creation"
    assert appels == []


def test_annuler_une_note_charge_toujours_le_moteur_hors_transaction(client, region,
                                                                     monkeypatch):
    """Ce qui réindexe le charge toujours AVANT le verrou : une note se lemmatise."""
    _ok(client.put(f"/api/regions/{region['id']}/annotation", json={"note": "cri"},
                   headers=ADMIN), 200)
    appels = _charges(monkeypatch)
    assert _ok(client.post("/api/undo", headers=ADMIN), 200).json()["cible_table"] == "annotations"
    assert appels == [1]
