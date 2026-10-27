"""Le décor des tests des grilles et des relevés (ANN-7, tranche 1).

Une grille FICTIVE, écrite pour les tests — `tools/grille-modele.csv` et sa liste —, jamais
la vraie (le dépôt est public). Les identités sont celles de la 3a, plus celles que la
mission de la tranche 1 demande : un responsable d'un second projet, un propriétaire de
collection qui masque, une stagiaire, un compte partagé, le propriétaire d'un bac à sable et
son invité, un administrateur qui a son bac.

Tout se monte par l'API, derrière le proxy, comme une personne le ferait ; seul ce que
l'API ne pose pas d'elle-même (la nature d'un compte) passe par SQL.
"""
import io
import sqlite3
from pathlib import Path

from conftest import du_projet
from conftest import ADMIN, make_png

RACINE = Path(__file__).resolve().parent.parent


def _lire(nom: str) -> str:
    """Le fichier tel qu'il est, fins de ligne comprises (CRLF, comme un tableur l'écrit)."""
    with open(RACINE / "tools" / nom, encoding="utf-8-sig", newline="") as f:
        return f.read()


MODELE = _lire("grille-modele.csv")
MODELE_LISTES = _lire("grille-modele-listes-qualificatifs.csv")

LEA = {"Remote-User": "lea", "Remote-Name": "Lea Responsable"}      # responsable de P
SAM = {"Remote-User": "sam"}                                        # membre de P, base protégée
ANA = {"Remote-User": "ana"}                                        # lit C, n'est pas de P
OLGA = {"Remote-User": "olga"}                                      # propriétaire de C
STAG = {"Remote-User": "stag", "Remote-Name": "Stagiaire Une"}      # écrit dans C
TP = {"Remote-User": "groupe-tp"}                                   # compte PARTAGÉ, écrit dans C
ZOE = {"Remote-User": "zoe"}                                        # responsable de Q, lit D
BEA = {"Remote-User": "bea"}                                        # propriétaire d'un bac
IVAN = {"Remote-User": "ivan"}                                      # invité du bac de Béa
ADM = {"Remote-User": "adm", "Remote-Groups": "bd-admins"}          # admin qui a son bac


def ok(r, *codes):
    assert r.status_code in (codes or (200, 201)), (r.request.method, str(r.request.url),
                                                    r.status_code, r.text[:500])
    return r.json() if r.content and "json" in r.headers.get("content-type", "") else r


def csv_de(lignes) -> str:
    """Un CSV point-virgule à partir de lignes (listes) — l'en-tête en premier."""
    return "\r\n".join(";".join("" if c is None else str(c) for c in l) for l in lignes) + "\r\n"


def importer(client, projet_id, qui, *, entrees=MODELE, listes=MODELE_LISTES, nom="Signaux",
             grille_id=None, ouverte=False, porte_sur="mots", a_blanc=False, note=None,
             attendu=(200,)):
    files = {"fichier": ("grille-rubriques-entrees.csv", entrees.encode("utf-8-sig"),
                         "text/csv")}
    if listes is not None:
        files["listes"] = ("grille-listes-qualificatifs.csv", listes.encode("utf-8-sig"),
                           "text/csv")
    data = {"ouverte": str(ouverte).lower(), "a_blanc": str(a_blanc).lower()}
    if nom is not None and grille_id is None:
        data["nom"] = nom
    if grille_id is not None:
        data["grille_id"] = str(grille_id)
    if porte_sur is not None:
        data["porte_sur"] = porte_sur
    if note is not None:
        data["note"] = note
    r = client.post(f"/api/projets/{projet_id}/grilles/import", files=files, data=data,
                    headers=qui)
    assert r.status_code in attendu, (r.status_code, r.text[:800])
    return r.json()


def grille_active(client, projet_id, qui=LEA, **kw) -> dict:
    """Importe le modèle, publie sa version 1 et l'active sur le projet. Rend
    `{grille_id, numero}`."""
    res = importer(client, projet_id, qui, **kw)
    gid = res["grille_id"]
    if not kw.get("ouverte"):
        ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=qui))
    ok(client.put(f"/api/projets/{projet_id}/grilles/{gid}/activation", headers=qui,
                  json={"version": 1}))
    return {"grille_id": gid, "numero": 1}


def _sql(db_path, q, p=()):
    c = sqlite3.connect(db_path)
    try:
        c.execute(q, p)
        c.commit()
    finally:
        c.close()


def monter(client, db_path) -> dict:
    """Deux projets, leurs collections, un album annotable, des zones des quatre types qui
    reçoivent des relevés, et un bac à sable. Rend les identifiants."""
    for qui in (LEA, SAM, ANA, OLGA, STAG, TP, ZOE, BEA, IVAN, ADM):
        client.get("/api/moi", headers=qui)
    _sql(db_path, "UPDATE utilisateur SET nature = 'collectif' WHERE login = 'groupe-tp'")
    p = ok(client.post("/api/projets", headers=ADMIN,
                       json={"nom": "Étude G", "acces_membres": None}), 201)["id"]
    q = ok(client.post("/api/projets", headers=ADMIN,
                       json={"nom": "Étude Q", "acces_membres": None}), 201)["id"]
    for projet, qui, role in ((p, "lea", "responsable"), (p, "sam", "membre"),
                              (q, "zoe", "responsable")):
        ok(client.put(f"/api/projets/{projet}/membres", headers=ADMIN,
                      json={"genre": "utilisateur", "principal": qui, "role": role}))
    c = ok(client.post("/api/collections", headers=LEA,
                       json={"nom": "Corpus G", "projet_id": p}), 201)["id"]
    c2 = ok(client.post("/api/collections", headers=LEA,
                        json={"nom": "Paratexte G", "projet_id": p}), 201)["id"]
    d = ok(client.post("/api/collections", headers=ZOE,
                       json={"nom": "Corpus Q", "projet_id": q}), 201)["id"]
    for col, qui, niveau in ((c, "olga", "proprietaire"), (c, "ana", "lecture"),
                             (c, "stag", "ecriture"), (c, "groupe-tp", "ecriture"),
                             (c2, "stag", "ecriture")):
        du_projet(client, col, "utilisateur", qui, headers=ADMIN)
        ok(client.put(f"/api/collections/{col}/acces", headers=LEA,
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau}))
    a = ok(client.post("/api/albums", headers=LEA,
                       json={"titre": "Album G", "collection_id": c}), 201)["id"]
    pl = ok(client.post(f"/api/albums/{a}/import", headers=LEA,
                        files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
    zones = {}
    for type_, texte in (("case", None), ("bulle", "J'SAIS PAS, IL NE VIENT PAS !!!"),
                         ("cartouche", "PENDANT CE TEMPS…"), ("personnage", None),
                         ("texte", "BANG ! CRAC")):
        zones[type_] = ok(client.post(f"/api/planches/{pl}/regions", headers=LEA,
                                      json={"type": type_, "x": 1, "y": 1, "w": 20, "h": 20}),
                          201)["id"]
        if texte:
            ok(client.put(f"/api/regions/{zones[type_]}", headers=LEA,
                          json={"ocr_texte": texte}))
    autre_bulle = ok(client.post(f"/api/planches/{pl}/regions", headers=LEA,
                                 json={"type": "bulle", "x": 30, "y": 30, "w": 9, "h": 9}),
                     201)["id"]
    b = ok(client.post("/api/albums", headers=ZOE,
                       json={"titre": "Album Q", "collection_id": d}), 201)["id"]
    plb = ok(client.post(f"/api/albums/{b}/import", headers=ZOE,
                         files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
    bulle_q = ok(client.post(f"/api/planches/{plb}/regions", headers=ZOE,
                             json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}),
                 201)["id"]
    return {"p": p, "q": q, "c": c, "c2": c2, "d": d, "album": a, "planche": pl,
            "zones": zones, "autre_bulle": autre_bulle, "album_q": b, "planche_q": plb,
            "bulle_q": bulle_q}


def bac_de_bea(client) -> dict:
    """Le bac à sable de Béa, où Ivan est invité, une collection et un album à elle."""
    bac = ok(client.post("/api/bac-a-sable", headers=BEA), 201)
    ok(client.put(f"/api/projets/{bac['id']}/membres", headers=BEA,
                  json={"genre": "utilisateur", "principal": "ivan", "role": "membre"}))
    projets = {x["id"]: x for x in ok(client.get("/api/projets", headers=BEA))}
    base = projets[bac["id"]]["base"]["id"]
    a = ok(client.post("/api/albums", headers=BEA,
                       json={"titre": "Au bac", "collection_id": base}), 201)["id"]
    pl = ok(client.post(f"/api/albums/{a}/import", headers=BEA,
                        files={"file": ("p.png", make_png(), "image/png")}), 201)["id"]
    bulle = ok(client.post(f"/api/planches/{pl}/regions", headers=BEA,
                           json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9}), 201)["id"]
    ok(client.put(f"/api/regions/{bulle}", headers=BEA, json={"ocr_texte": "OUILLE"}))
    return {"projet": bac["id"], "base": base, "album": a, "planche": pl, "bulle": bulle}


def flux(texte: str) -> io.StringIO:
    return io.StringIO(texte, newline="")
