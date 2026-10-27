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
  RÉFÉRENCE) et le nouveau rendent les mêmes valeurs, album par album, sous neuf identités.
  Depuis la tranche 3b de COL-3, la référence porte la clause NEUVE : elle compare la forme
  CASE à la forme OR d'une même clause, et non plus à 1032d4e. Depuis la tranche 3c (F3),
  la règle d'effacement n'a plus de `CASE` à elle — plus aucune branche ne lit le journal —,
  et la référence se réduit au BORNAGE (`NOT EXISTS … OR …` contre `_bornee_sur_album`) ;
- le COÛT : ce qui ne compte pas n'est plus évalué. Pas un temps — il bruite —, mais une
  fonction SQL témoin, glissée dans le fragment coûteux, qui note chaque album pour lequel
  SQLite l'appelle. Depuis la tranche 3c : aucune clause d'effacement ne lit le journal,
  sous aucune identité — un témoin posé sur les sources du travail n'est jamais appelé.
"""
import pytest

import autorisation
import database
from conftest import du_projet
from conftest import ADMIN, make_png
from test_bac_a_sable import (HUGO, LEA, RESP, RITA, SAM, TP, _partage, _portee, decor,  # noqa: F401
                              jeu)
from database import sql_est_bac_a_sable, sql_projet_d_album

ZOE = {"Remote-User": "zoe", "Remote-Groups": "bd-admins"}        # administratrice sans bac
ZOE2 = {"Remote-User": "zoe2", "Remote-Groups": "bd-admins"}      # administratrice INVITÉE

# Les clauses d'album : `_clause_album` en lecture et en écriture (l'enveloppe du jeu,
# autour, est inchangée), puis les clauses de geste — « repartir de zéro » compris
# (tranche 3b : les chemins de la suppression, sans la règle de la dernière copie).
CLAUSES = (("_clause_album", False), ("_clause_album", True),
           ("clause_suppression_directe", None), ("clause_repartir_directe", None),
           ("clause_rejoindre_directe", None))
EFFACEMENTS = ("clause_suppression_directe", "clause_repartir_directe")


def _nouvelle(p, clause, ecriture):
    if clause == "_clause_album":
        return p._clause_album("a.id", ecriture=ecriture)
    return getattr(p, clause)("a.id")


def _ancienne(p, clause, ecriture):
    """Le SQL d'AVANT (1032d4e), recopié tel qu'il était : la référence de l'équivalence.
    Depuis la tranche 3c, seul le bornage a changé de forme ; le reste se lit dans le code
    d'aujourd'hui."""
    if p.tout and p.bornee and not p.hors_isoles:
        sql, prm = _ancienne(p._ordinaire(), clause, ecriture)
        return (f"(NOT EXISTS (SELECT 1 FROM albums _bba WHERE _bba.id = a.id "
                f"AND {sql_est_bac_a_sable(sql_projet_d_album('_bba'))}) OR {sql})", prm)
    return _nouvelle(p, clause, ecriture)


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
    - `resp`, compte ordinaire, responsable de l'Étude : « Réel » qu'elle a créé, « Touché »
      qu'elle a créé et où l'administrateur a travaillé, « D'un autre » créé par
      l'administrateur ; et son bac ;
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
    # COL-3, tranche 3b — une SŒUR de « Touché », prise par l'administrateur dans la même
    # collection : pour resp, responsable de l'Étude, « Touché » n'est plus la dernière copie
    # de son document, et le chemin 3 (le responsable du projet) le rend effaçable — sans
    # que le journal soit lu.
    doc = next(a["document_id"] for a in client.get("/api/albums", headers=ADMIN).json()
               if a["id"] == touche)
    r = client.post(f"/api/collections/{col}/prendre", headers=ADMIN,
                    json={"documents": [{"document_id": doc, "reponse": "zero",
                                         "album_id": touche}]})
    assert r.status_code == 200, r.text
    soeur = r.json()["documents"][0]["copie_id"]
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
    du_projet(client, col, "utilisateur", "groupe-tp", headers=ADMIN)
    client.put(f"/api/collections/{col}/acces", headers=RESP,
               json={"genre": "utilisateur", "principal": "groupe-tp", "niveau": "ecriture"})
    du_tp = client.post("/api/albums", headers=TP,
                        json={"titre": "Du TP", "collection_id": col}).json()["id"]
    return {**decor, "touche": touche, "d_un_autre": d_un_autre, "du_tp": du_tp,
            "soeur": soeur,
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
    # Tranche 3c (F3) — `resp`, responsable de l'Étude, efface « Touché » et sa sœur ; ni
    # « Réel » ni « D'un autre », dernières copies de leur document, quel qu'en soit le
    # créateur : plus de chemin du créateur.
    assert (r[scene["reel"]], r[scene["touche"]], r[scene["d_un_autre"]],
            r[scene["soeur"]]) == (0, 1, 0, 1)
    rep = vus["resp (ordinaire)", "clause_repartir_directe", None]
    assert (rep[scene["reel"]], rep[scene["d_un_autre"]]) == (1, 1)
    assert sup["lea (propriétaire de bac)"][scene["copie_touchee"]] == 1
    # Q4 (Hugo, 2026-10-26) : dans un bac à sable, quiconque y écrit efface.
    assert sup["sam (invité)"][scene["copie_touchee"]] == 1
    assert sup["groupe-tp (compte partagé)"][scene["du_tp"]] == 0
    h = sup["hugo (borné, a son bac)"]
    assert (h[scene["reel"]], h[scene["copie_touchee"]]) == (1, 0)
    assert sup["zoe2 (administratrice invitée)"][scene["copie_touchee"]] == 1
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


def test_aucune_clause_d_effacement_ne_lit_le_journal(client, scene, monkeypatch):
    """Tranche 3c (F3) — « le journal ne décide plus rien » : aucune clause d'effacement ne
    lit les sources du travail, sous aucune identité ni au mono-poste. Le témoin est posé sur
    `autorisation._sources_du_travail`, la seule porte vers le journal de « qui perd
    quoi » : il n'est jamais appelé, et le SQL rendu ne nomme ni le journal ni la trace des
    gestes. (Jusqu'à la tranche 3c, ce test vérifiait que le travail d'autrui ne se lisait
    que si le reste du chemin du créateur tenait.)"""
    appels = []
    vraie = autorisation._sources_du_travail

    def temoin(alias):
        appels.append(alias)
        return vraie(alias)
    monkeypatch.setattr(autorisation, "_sources_du_travail", temoin)
    portees = [_portee(scene["db"], qui) for qui in IDENTITES.values()]
    portees.append(autorisation.TOTALE)
    conn = database.get_connection()
    try:
        for p in portees:
            for clause in EFFACEMENTS:
                sql, prm = getattr(p, clause)("a.id")
                assert "evenement" not in sql and "geste_sur_copie" not in sql, (p, clause)
                _valeurs(conn, (sql, prm))
    finally:
        conn.close()
    assert appels == []
    # Le témoin mord : « qui perd quoi » passe bien par lui.
    autorisation.sql_actes_sur_album("1")
    assert appels == ["1"]


