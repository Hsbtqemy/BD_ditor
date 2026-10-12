"""ANN-6 — le locuteur d'un cartouche ou d'une zone de texte se RETROUVE partout où celui
d'une bulle se retrouvait.

C'est la promesse de contenu du chantier, et rien ne la tenait : la relecture croisée a
posé HUIT mutants d'un coup — sept lecteurs de `bulle_locuteur` ramenés aux seules bulles,
et une annulation qui refuserait de reposer un lien hors d'une zone de texte — et la suite
par défaut est restée verte, 1 636 passés. Les tests du chantier éprouvaient la ROUTE
(« un cartouche reçoit un locuteur ») ; aucun ne demandait ce que ce locuteur DEVIENT.
Aucun lecteur ne filtre sur le type aujourd'hui, et c'est ce qui rend l'ouverture gratuite :
il suffit qu'un seul en ajoute un pour que les cartouches disparaissent d'une analyse sans
que rien ne tombe.

Un test par sortie, et pas un test qui les lirait toutes : chacun a été joué contre SON
mutant, un par un. Un test qui en tuerait huit ne dirait pas lequel il tient.

Deux précautions de décor, qui décident si ces tests mesurent quelque chose :

- une BULLE témoin parle à côté, par un autre personnage. Sans elle, « la sortie nomme un
  locuteur » passerait sur une sortie vide de tout, et un lecteur ramené aux bulles ne se
  distinguerait pas d'un lecteur en panne ;
- le locuteur est posé par la ROUTE, donc à travers la garde de type ; les mots sont semés
  en direct dans `tokens`, comme dans `test_analyse`, pour ne pas dépendre de spaCy.
"""
import csv
import io
import json
import sqlite3
import zipfile

import pytest

from conftest import ADMIN, TYPES_PARLANTS

# Les deux types que le chantier ouvre. Dérivés de la liste écrite à la main dans
# `conftest`, pour qu'un type parlant de plus soit joué ici sans qu'on y pense.
ZONES = tuple(t for t in TYPES_PARLANTS if t != "bulle")
BASE_IIIF = "https://images.example.org/iiif"


def test_les_zones_jouees_sont_bien_le_cartouche_et_le_texte():
    """Un paramétrage vide rendrait tout ce fichier vert en ne jouant rien."""
    assert ZONES == ("cartouche", "texte")


def _semer(db_path, region_id, mots):
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) VALUES (?,?,?,?,?,?)",
            [(region_id, i, t, lemme, pos, "") for i, (t, lemme, pos) in enumerate(mots)])
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(params=ZONES)
def parole(request, client, album, planche, db_path):
    """Une case, et sous elle : la ZONE du type joué, dont « Narrateur » est le locuteur,
    et une bulle témoin dont « Tintin » est le locuteur."""
    pid = planche["id"]

    def region(type_zone, x, parent=None):
        corps = {"type": type_zone, "x": x, "y": 10, "w": 60, "h": 40}
        if parent is not None:
            corps["parent_id"] = parent
        rep = client.post(f"/api/planches/{pid}/regions", json=corps, headers=ADMIN)
        assert rep.status_code in (200, 201), rep.text
        return rep.json()["id"]

    case = region("case", 5)
    zone, bulle = region(request.param, 10, case), region("bulle", 100, case)
    narrateur = client.post("/api/personnages", json={"nom": "Narrateur"}, headers=ADMIN).json()["id"]
    tintin = client.post("/api/personnages", json={"nom": "Tintin"}, headers=ADMIN).json()["id"]
    for rid, perso in ((zone, narrateur), (bulle, tintin)):
        rep = client.put(f"/api/regions/{rid}/locuteur", json={"personnage_id": perso},
                         headers=ADMIN)
        assert rep.status_code == 200, rep.text
    _semer(db_path, zone, [("PLUS", "plus", "ADV"), ("TARD", "tard", "ADV")])
    _semer(db_path, bulle, [("BONJOUR", "bonjour", "INTJ")])
    collection = sqlite3.connect(db_path).execute(
        "SELECT collection_id FROM collection_album WHERE album_id = ?",
        (album["id"],)).fetchone()[0]
    return {"type": request.param, "album": album["id"], "planche": pid, "case": case,
            "zone": zone, "bulle": bulle, "narrateur": narrateur, "tintin": tintin,
            "collection": collection}


# --------------------------------------------------------------------------- #
# L'Exploration et la Recherche
# --------------------------------------------------------------------------- #
def test_les_frequences_par_locuteur_comptent_la_zone(client, parole):
    """Le filtre par locuteur des analyses (`_analyse_filtres`, partagé par la distribution,
    la concordance, le croisement et la comparaison)."""
    res = client.get("/api/analyse/frequences",
                     params={"champ": "lemme", "personnage": parole["narrateur"]}).json()
    assert {r["lemme"] for r in res["results"]} == {"plus", "tard"}


def test_la_concordance_nomme_le_locuteur_de_la_zone(client, parole):
    """La COLONNE « locuteur » d'une ligne de concordance, à l'écran et dans son CSV."""
    res = client.get("/api/analyse/concordance", params={"lemme": "tard"}).json()
    assert res["count"] == 1
    ligne = res["results"][0]
    assert (ligne["region_id"], ligne["type"], ligne["locuteur"]) == \
        (parole["zone"], parole["type"], "Narrateur")

    brut = client.get("/api/analyse/concordance.csv", params={"lemme": "tard"})
    assert brut.status_code == 200, brut.text
    lignes = list(csv.DictReader(io.StringIO(brut.content.decode("utf-8-sig"))))
    assert [(x["type"], x["locuteur"]) for x in lignes] == [(parole["type"], "Narrateur")]


def test_la_recherche_par_locuteur_rend_la_zone(client, parole):
    res = client.get("/api/recherche", params={"personnage": parole["narrateur"]}).json()
    assert {r["region_id"] for r in res["results"]} == {parole["zone"]}
    # Le témoin : la même recherche sur l'autre personnage rend la bulle, et elle seule.
    temoin = client.get("/api/recherche", params={"personnage": parole["tintin"]}).json()
    assert {r["region_id"] for r in temoin["results"]} == {parole["bulle"]}


def test_le_croisement_par_locuteur_range_la_zone_sous_son_personnage(client, parole):
    """L'AXE « locuteur » du tableau croisé — une jointure à lui, distincte du filtre."""
    res = client.get("/api/analyse/croisement",
                     params={"axe_x": "locuteur", "axe_y": "type"}).json()
    totaux = {x["libelle"]: x["total"] for x in res["x"]}
    assert totaux == {"Narrateur": 2, "Tintin": 1}, (
        "les deux mots de la zone ne sont pas comptés sous son locuteur : ils sont tombés "
        f"dans la ligne sans libellé — {totaux}")
    ix = [x["libelle"] for x in res["x"]].index("Narrateur")
    iy = [y["cle"] for y in res["y"]].index(parole["type"])
    assert res["grille"][ix][iy] == 2


# --------------------------------------------------------------------------- #
# Le registre — ce qu'on VOIT d'un personnage, et ce qu'il compte
# --------------------------------------------------------------------------- #
def test_le_registre_compte_la_zone(client, parole):
    registre = {p["nom"]: p["nb_bulles"] for p in client.get("/api/personnages").json()}
    assert registre == {"Narrateur": 1, "Tintin": 1}


def test_un_personnage_apparait_par_la_zone_ou_il_parle(client, parole, db_path,
                                                         derriere_proxy):
    """Sous cloisonnement, on voit un personnage qui APPARAÎT là où l'on lit
    (`socle._clause_personnage`). Le narrateur ne parle que dans un cartouche — ou une zone
    de texte : c'est par là qu'il apparaît, et une lectrice de la collection doit le voir.
    Il ne peut pas se rattraper par « n'apparaît nulle part » : il a un lien."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                     "VALUES (?, 'utilisateur', 'lea', 'lecture')", (parole["collection"],))
        conn.commit()
    finally:
        conn.close()
    lea = {"Remote-User": "lea"}
    registre = {p["nom"]: p["nb_bulles"] for p in client.get("/api/personnages", headers=lea).json()}
    assert registre == {"Narrateur": 1, "Tintin": 1}
    assert client.get(f"/api/personnages/{parole['narrateur']}/attributs",
                      headers=lea).status_code == 200
    # Le témoin : quelqu'un qui ne lit rien ne voit ni l'un ni l'autre — la lectrice ne les
    # voit donc pas « parce que tout le monde les voit ».
    assert client.get("/api/personnages", headers={"Remote-User": "zoe"}).json() == []


# --------------------------------------------------------------------------- #
# Ce qui sort vers le dépôt
# --------------------------------------------------------------------------- #
def _regions_de(noeuds):
    for n in noeuds:
        yield n
        yield from _regions_de(n.get("enfants", []))


def test_les_metadonnees_de_collection_nomment_le_locuteur_de_la_zone(client, parole):
    """`tools/metadonnees_collection.py`, par la route du dépôt : l'arbre JSON et la table
    `regions` du zip — deux chemins du même outil."""
    url = f"/api/collections/{parole['collection']}/depot/metadonnees"
    rep = client.get(url, params={"format": "json"})
    assert rep.status_code == 200, rep.text
    regions = {r["id"]: r for a in rep.json()["metadonnees_collection"]["albums"]
               for p in a["planches"]
               for r in _regions_de(p["regions"])}
    assert regions[parole["zone"]]["type"] == parole["type"]
    assert regions[parole["zone"]]["locuteur"] == "Narrateur"
    assert regions[parole["bulle"]]["locuteur"] == "Tintin"       # le témoin
    assert regions[parole["case"]]["locuteur"] is None

    rep = client.get(url, params={"format": "zip"})
    assert rep.status_code == 200, rep.text
    with zipfile.ZipFile(io.BytesIO(rep.content)) as z:
        table = list(csv.DictReader(io.StringIO(z.read("regions.csv").decode("utf-8-sig"))))
    locuteurs = {int(x["id"]): x["locuteur"] for x in table}
    assert locuteurs[parole["zone"]] == "Narrateur" and locuteurs[parole["bulle"]] == "Tintin"


def test_la_description_de_collection_compte_le_lien_de_la_zone(client, parole):
    """`tools/description_collection.py`, par la route du dépôt : la fiche compte les liens
    de locuteur — deux ici, la zone et la bulle témoin, pour deux personnages."""
    rep = client.get(f"/api/collections/{parole['collection']}/depot/description",
                     params={"format": "json"})
    assert rep.status_code == 200, rep.text

    def trouver(noeud, cle):
        if isinstance(noeud, dict):
            if cle in noeud:
                return noeud
            for v in noeud.values():
                r = trouver(v, cle)
                if r is not None:
                    return r
        elif isinstance(noeud, list):
            for v in noeud:
                r = trouver(v, cle)
                if r is not None:
                    return r
        return None

    bloc = trouver(rep.json(), "liens_locuteur")
    assert bloc is not None, "la fiche ne porte plus `liens_locuteur` : ce test ne mesurerait rien"
    assert (bloc["liens_locuteur"], bloc["locuteurs_distincts"]) == (2, 2)


def test_le_manifeste_iiif_nomme_le_locuteur_de_la_zone(client, parole):
    """`tools/iiif_manifest.py`, par la route du dépôt : l'annotation de la zone porte un
    corps « locuteur : … », comme celle d'une bulle."""
    rep = client.get(f"/api/collections/{parole['collection']}/depot/iiif",
                     params={"base_url": BASE_IIIF})
    assert rep.status_code == 200, rep.text
    with zipfile.ZipFile(io.BytesIO(rep.content)) as z:
        manifeste = json.loads(z.read(f"manifest-a{parole['album']}.json"))

    def corps(region_id):
        """Les valeurs des corps de l'annotation IIIF qui vise cette région."""
        trouves = []

        def marcher(noeud):
            if isinstance(noeud, dict):
                if noeud.get("type") == "Annotation" and \
                        str(noeud.get("id", "")).endswith(f"/annotation/region-{region_id}"):
                    b = noeud.get("body", [])
                    trouves.extend(x.get("value") for x in (b if isinstance(b, list) else [b]))
                for v in noeud.values():
                    marcher(v)
            elif isinstance(noeud, list):
                for v in noeud:
                    marcher(v)
        marcher(manifeste)
        return trouves

    assert "locuteur : Tintin" in corps(parole["bulle"]), (
        "le témoin ne se lit pas : l'annotation de la bulle n'a pas été trouvée dans le "
        f"manifeste, ce test ne mesurerait rien — {corps(parole['bulle'])}")
    assert "locuteur : Narrateur" in corps(parole["zone"])
