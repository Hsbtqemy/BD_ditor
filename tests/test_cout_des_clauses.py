"""COL-4 — les clauses d'album d'une portée BORNÉE, et `clause_suppression_directe`, ne
calculent plus ce dont leur réponse ne dépend pas.

Le constat (mesuré le 2026-10-25) : `GET /api/albums` passait de 22 à 186 ms pour un
administrateur qui a un bac à sable, sur 150 albums. `destructible` est une COLONNE du
`SELECT`, et SQLite y calcule les deux opérandes d'un `OR` comme tous ceux d'un `AND` :
`NOT EXISTS (<bac à sable>) OR <clause ordinaire>` calculait la clause ordinaire — le
journal — pour chaque album du vrai corpus, et `<détruire> AND … AND NOT <autrui>` le
travail d'autrui pour chaque album qu'on n'écrit même pas. Réécrites en `CASE`, elles ne
calculent que la branche retenue.

Deux propriétés, et chacune a son test :
- le SENS ne change pour personne : l'ancien SQL (celui de 1032d4e, recopié ici comme
  RÉFÉRENCE) et le nouveau rendent les mêmes valeurs, album par album, sous neuf identités ;
- le COÛT : ce qui ne compte pas n'est plus évalué. Pas un temps — il bruite —, mais une
  fonction SQL témoin, glissée dans le fragment coûteux, qui note chaque album pour lequel
  SQLite l'appelle.
"""
import pytest

import autorisation
import database
from conftest import ADMIN, make_png
from test_bac_a_sable import (HUGO, LEA, RESP, RITA, SAM, TP, _partage, _portee, decor,  # noqa: F401
                              jeu)
from database import NATURE_COLLECTIF, sql_est_bac_a_sable, sql_projet_d_album

ZOE = {"Remote-User": "zoe", "Remote-Groups": "bd-admins"}        # administratrice sans bac
ZOE2 = {"Remote-User": "zoe2", "Remote-Groups": "bd-admins"}      # administratrice INVITÉE

# Les clauses d'album : `_clause_album` en lecture et en écriture (l'enveloppe du jeu,
# autour, est inchangée), puis les trois clauses de geste.
CLAUSES = (("_clause_album", False), ("_clause_album", True), ("clause_destruction", None),
           ("clause_suppression_directe", None), ("clause_rejoindre_directe", None))


def _nouvelle(p, clause, ecriture):
    if clause == "_clause_album":
        return p._clause_album("a.id", ecriture=ecriture)
    return getattr(p, clause)("a.id")


def _ancienne(p, clause, ecriture):
    """Le SQL d'AVANT (1032d4e), recopié tel qu'il était : la référence de l'équivalence.
    Seuls le bornage et la suppression directe ordinaire ont changé ; le reste se lit dans
    le code d'aujourd'hui, qui est celui d'hier."""
    if p.tout and p.bornee and not p.hors_isoles:
        sql, prm = _ancienne(p._ordinaire(), clause, ecriture)
        return (f"(NOT EXISTS (SELECT 1 FROM albums _bba WHERE _bba.id = a.id "
                f"AND {sql_est_bac_a_sable(sql_projet_d_album('_bba'))}) OR {sql})", prm)
    if clause != "clause_suppression_directe" or p.tout:
        return _nouvelle(p, clause, ecriture)
    if not p.utilisateur:
        return "0", []
    bac, p_bac = "0", []
    if p.bacs_a_soi:
        ids = sorted(p.bacs_a_soi)
        bac = (f"EXISTS (SELECT 1 FROM albums _sbs WHERE _sbs.id = a.id "
               f"AND {sql_projet_d_album('_sbs')} IN ({', '.join('?' * len(ids))}))")
        p_bac = [*ids]
    detruire, p_detruire = p.clause_destruction("a.id")
    if detruire == "0":
        return bac, p_bac
    autrui, p_autrui = autorisation._sql_travail_d_autrui("a.id", p.utilisateur)
    return (f"(({detruire} "
            f"AND EXISTS (SELECT 1 FROM copie _sc WHERE _sc.album_id = a.id "
            f"AND _sc.creee_par = ?) "
            f"AND NOT EXISTS (SELECT 1 FROM utilisateur _su WHERE _su.login = ? "
            f"AND _su.nature = ?) "
            f"AND NOT {autrui}) OR {bac})",
            [*p_detruire, p.utilisateur, p.utilisateur, NATURE_COLLECTIF, *p_autrui, *p_bac])


def _valeurs(conn, frag):
    sql, prm = frag
    return [tuple(r) for r in conn.execute(
        f"SELECT a.id, ({sql}) FROM albums a ORDER BY a.id", prm)]


def _planche(client, album, qui):
    r = client.post(f"/api/albums/{album}/import", headers=qui,
                    files={"file": ("p.png", make_png(), "image/png")})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _region(client, planche, qui):
    r = client.post(f"/api/planches/{planche}/regions", headers=qui,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 201, r.text


@pytest.fixture
def scene(client, decor):  # noqa: F811
    """Le décor du bac à sable, plus ce qui fait varier chaque moitié de la règle :
    - `resp`, compte ordinaire : « Réel » qu'elle a créé et où personne d'autre n'a
      travaillé (VRAI), « Touché » qu'elle a créé et où l'administrateur a travaillé (FAUX
      par autrui), « D'un autre » créé par l'administrateur (FAUX par la copie) ; et son bac ;
    - `hugo` a son bac à sable (portée BORNÉE), `zoe` n'en a pas, `zoe2` est invitée dans
      celui de lea ;
    - `sam`, l'invité de lea, a travaillé sur une copie du bac de lea : pour lea, seul le
      chemin du bac à sable la rend destructible ;
    - `groupe-tp`, compte PARTAGÉ, membre de l'Étude, a créé un album hors de son bac."""
    col = decor["col"]
    touche = client.post("/api/albums", headers=RESP,
                         json={"titre": "Touché", "collection_id": col}).json()["id"]
    _region(client, _planche(client, touche, RESP), ADMIN)
    d_un_autre = client.post("/api/albums", headers=ADMIN,
                             json={"titre": "D'un autre", "collection_id": col}).json()["id"]
    _planche(client, decor["reel"], RESP)
    for qui in (HUGO, RESP):
        assert client.post("/api/bac-a-sable", headers=qui).status_code == 201
    client.get("/api/moi", headers=ZOE)
    client.get("/api/moi", headers=ZOE2)
    assert client.put(f"/api/projets/{decor['bac']['id']}/membres", headers=LEA,
                      json={"genre": "utilisateur", "principal": "zoe2",
                            "role": "membre"}).status_code == 200
    copie = next(j for j in decor["bac"]["jeu"] if j["planche_ids"])
    _region(client, copie["planche_ids"][0], SAM)
    _partage(client)
    client.post("/api/bac-a-sable", headers=TP)
    client.put(f"/api/projets/{decor['etude']}/membres", headers=ADMIN,
               json={"genre": "utilisateur", "principal": "groupe-tp", "role": "membre"})
    client.put(f"/api/collections/{col}/acces", headers=RESP,
               json={"genre": "utilisateur", "principal": "groupe-tp", "niveau": "ecriture"})
    du_tp = client.post("/api/albums", headers=TP,
                        json={"titre": "Du TP", "collection_id": col}).json()["id"]
    return {**decor, "touche": touche, "d_un_autre": d_un_autre, "du_tp": du_tp,
            "copie_touchee": copie["album_id"]}


IDENTITES = {"hugo (borné, a son bac)": HUGO, "zoe (administratrice sans bac)": ZOE,
             "zoe2 (administratrice invitée)": ZOE2, "resp (ordinaire)": RESP,
             "lea (propriétaire de bac)": LEA, "sam (invité)": SAM,
             "groupe-tp (compte partagé)": TP, "rita (inconnue)": RITA}


def test_l_ancien_et_le_nouveau_sql_rendent_les_memes_valeurs(client, scene):
    """Album par album, sous chaque identité et le mono-poste, l'ancien et le nouveau SQL
    rendent les mêmes valeurs — et ces valeurs sont des booléens 0/1, jamais NULL. Le décor
    fait prendre à chaque moitié ses deux valeurs, vérifié en bas : sans quoi l'équivalence
    serait celle de deux constantes."""
    portees = {nom: _portee(scene["db"], qui) for nom, qui in IDENTITES.items()}
    portees["mono-poste"] = autorisation.TOTALE
    assert portees["hugo (borné, a son bac)"].bornee
    assert portees["zoe (administratrice sans bac)"].bornee
    assert not portees["zoe (administratrice sans bac)"].bacs_a_soi
    conn = database.get_connection()
    try:
        vus = {}
        for nom, p in portees.items():
            for clause, ecriture in CLAUSES:
                neuf = _valeurs(conn, _nouvelle(p, clause, ecriture))
                assert neuf == _valeurs(conn, _ancienne(p, clause, ecriture)), (nom, clause)
                assert {v for _, v in neuf} <= {0, 1}, (nom, clause)
                vus[nom, clause, ecriture] = dict(neuf)
    finally:
        conn.close()
    sup = {nom: vus[nom, "clause_suppression_directe", None] for nom in portees}
    r = sup["resp (ordinaire)"]
    assert (r[scene["reel"]], r[scene["touche"]], r[scene["d_un_autre"]]) == (1, 0, 0)
    assert sup["lea (propriétaire de bac)"][scene["copie_touchee"]] == 1
    assert sup["sam (invité)"][scene["copie_touchee"]] == 0
    assert sup["groupe-tp (compte partagé)"][scene["du_tp"]] == 0
    h = sup["hugo (borné, a son bac)"]
    assert (h[scene["reel"]], h[scene["copie_touchee"]]) == (1, 0)
    assert sup["zoe2 (administratrice invitée)"][scene["copie_touchee"]] == 0
    assert vus["zoe2 (administratrice invitée)", "_clause_album", False][
        scene["copie_touchee"]] == 1


def _temoin(conn, nom):
    """Une fonction SQL `nom(album)` qui rend 0 et note chaque album pour lequel SQLite
    l'appelle."""
    vus = set()

    def f(album):
        vus.add(album)
        return 0
    conn.create_function(nom, 1, f)
    return vus


def test_hors_des_bacs_la_clause_ordinaire_n_est_pas_evaluee(client, scene):
    """Le bornage, dans une colonne du `SELECT` comme `destructible` : la clause ordinaire
    n'est évaluée que pour les albums d'un bac à sable — jamais pour ceux du vrai corpus,
    où la réponse est 1 sans elle. L'ancienne forme (`NOT EXISTS … OR …`) l'évaluait pour
    tous."""
    p = _portee(scene["db"], HUGO)
    conn = database.get_connection()
    try:
        vus = _temoin(conn, "bd_ordinaire_vu")
        valeurs = dict(_valeurs(conn, p._bornee_sur_album("a.id", ("bd_ordinaire_vu(a.id)", []))))
        bacs = {r[0] for r in conn.execute(
            f"SELECT a.id FROM albums a WHERE {sql_est_bac_a_sable(sql_projet_d_album('a'))}")}
    finally:
        conn.close()
    assert bacs and scene["reel"] not in bacs
    assert vus == bacs
    assert all(v == (0 if a in bacs else 1) for a, v in valeurs.items())


def test_le_travail_d_autrui_ne_se_lit_que_si_le_reste_tient(client, scene, monkeypatch):
    """`clause_suppression_directe`, dans une colonne du `SELECT` : le travail d'autrui (le
    journal) n'est lu que pour les albums où les trois moitiés bon marché tiennent — pour
    resp, les deux qu'elle a créés et où elle écrit partout ; ni pour « D'un autre », ni
    pour un album qu'elle n'écrit pas, ni dans son bac à sable, où le chemin du bac répond
    d'abord. Et pour une portée bornée, sur aucun album : le vrai corpus ne lit pas la clause
    ordinaire, le bac à sable à soi répond par son chemin."""
    lire_autrui = autorisation._sql_travail_d_autrui

    def temoin(alias, login):
        sql, prm = lire_autrui(alias, login)
        return f"(bd_autrui_vu({alias}) OR {sql})", prm
    monkeypatch.setattr(autorisation, "_sql_travail_d_autrui", temoin)
    for qui, attendu in ((RESP, {scene["reel"], scene["touche"]}), (HUGO, set()),
                         (LEA, set())):
        p = _portee(scene["db"], qui)
        conn = database.get_connection()
        try:
            vus = _temoin(conn, "bd_autrui_vu")
            _valeurs(conn, p.clause_suppression_directe("a.id"))
        finally:
            conn.close()
        assert vus == attendu, qui["Remote-User"]
