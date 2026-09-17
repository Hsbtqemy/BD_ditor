"""AUTH-12, étape 3 — la description des droits en ACTES, et ce qui l'empêche de mentir.

L'écran d'attribution ne connaît aucun niveau en dur : il lit `GET /api/droits`. Une
description fausse y serait pire qu'absente — l'écran promettrait ce que le serveur refuse.
Elle est donc confrontée à `Portee`, par table de vérité : ce qu'elle dit d'un niveau, le
cumul doit le faire.

Chaque acte est aussi JOUÉ, par un geste qui le représente, sous un membre de chaque niveau :
confronter l'échelle à `Portee` ne dit rien du couple acte → niveau, et le harnais de
mutation l'a montré — « décider qui entre » passé en écriture survivait à la table de vérité.

Ce que ces tests ne prouvent PAS, et c'est écrit dans `autorisation.py` : que TOUTES les
routes d'un acte exigent son niveau. Un geste par acte n'est pas le périmètre route par route
(AUTH-10), qui n'existe pas encore.
"""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import autorisation  # noqa: E402
import main  # noqa: E402

from autorisation import (ACTES, ECRITURE, HORS_RANG, LECTURE, NIVEAUX,  # noqa: E402
                          PROPRIETAIRE, Portee)
from conftest import ADMIN, make_png  # noqa: E402

C = 7   # une collection quelconque

# La question que `Portee` pose pour chaque niveau.
QUESTION = {LECTURE: "peut_lire", ECRITURE: "peut_ecrire", PROPRIETAIRE: "peut_administrer"}


def _portee(niveau, export=False):
    ensembles = {LECTURE: "lecture", ECRITURE: "ecriture", PROPRIETAIRE: "propriete"}
    kw = {ensembles[niveau]: frozenset({C})}
    if export:
        kw["export"] = frozenset({C})
    return Portee(**kw)


def test_l_echelle_est_celle_des_niveaux():
    assert autorisation.description_des_droits()["echelle"] == list(NIVEAUX)
    assert set(QUESTION) == set(NIVEAUX), "un niveau sans question de Portee à confronter"


def test_chaque_acte_dit_ce_que_le_cumul_fait():
    """Accordé au niveau L, un acte de niveau N est permis si et seulement si L est au-dessus
    ou au niveau de N — et c'est `Portee`, non la description, qui répond.

    Ce test éprouve l'ÉCHELLE, pas le niveau de chaque acte : la question posée se choisit
    d'après le niveau que l'acte déclare, donc un acte déclaré trop haut ou trop bas y reste
    cohérent. C'est le test suivant qui le prend en défaut."""
    for acte in ACTES:
        rang_acte = NIVEAUX.index(acte["niveau"])
        for accorde in NIVEAUX:
            permis = getattr(_portee(accorde), QUESTION[acte["niveau"]])(C)
            assert permis == (NIVEAUX.index(accorde) >= rang_acte), (acte["code"], accorde)


def _decor(client):
    """Une collection, un membre par niveau, et de quoi jouer chaque geste : un album avec une
    région, et un second album dont la planche est VERROUILLÉE — un lot la compte sans la
    traiter, donc son refus se lit sans qu'aucun moteur tourne."""
    cid = client.post("/api/collections", json={"nom": "Actes"}, headers=ADMIN).json()["id"]
    membres = {}
    for niveau in NIVEAUX:
        membres[niveau] = f"membre-{niveau}"
        r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                       json={"genre": "utilisateur", "principal": membres[niveau],
                             "niveau": niveau})
        assert r.status_code in (200, 201), r.text

    def album(titre):
        a = client.post("/api/albums", json={"titre": titre, "collection_id": cid},
                        headers=ADMIN).json()
        p = client.post(f"/api/albums/{a['id']}/import", headers=ADMIN,
                        files={"file": ("planche.png", make_png(), "image/png")}).json()
        return a, p
    album_lu, planche = album("Lu")
    region = client.post(f"/api/planches/{planche['id']}/regions", headers=ADMIN,
                         json={"type": "case", "x": 10, "y": 10, "w": 100, "h": 80}).json()
    album_lot, planche_lot = album("Lot")
    r = client.patch(f"/api/planches/{planche_lot['id']}/verrou", json={"verrouillee": True},
                     headers=ADMIN)
    assert r.status_code == 200, r.text
    return cid, membres, album_lu["id"], region["id"], album_lot["id"]


def test_chaque_acte_se_joue_au_niveau_qu_il_declare(client, derriere_proxy, monkeypatch):
    """Sous un membre de chaque niveau, le geste qui représente l'acte réussit si et seulement
    si ce niveau atteint celui que la description lui donne. Un acte ajouté à la table sans
    geste fait échouer le test : il ne passe pas sans avoir été joué."""
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    cid, membres, album_id, region_id, album_lot = _decor(client)

    def lire(h):
        return album_id in [a["id"] for a in client.get("/api/albums", headers=h).json()]

    def annoter(h):
        r = client.put(f"/api/regions/{region_id}/annotation", json={"note": "vu"}, headers=h)
        assert r.status_code in (200, 404), r.text
        return r.status_code == 200

    def structurer(h):
        r = client.post("/api/albums", json={"titre": "Neuf", "collection_id": cid}, headers=h)
        assert r.status_code in (201, 404), r.text
        return r.status_code == 201

    def vocabulaire(h):
        r = client.post("/api/tags", json={"label": "motif"}, headers=h)
        assert r.status_code in (201, 403), r.text
        return r.status_code == 201

    def lots(h):
        r = client.post("/api/jobs", json={"passes": ["segmenter"], "album_ids": [album_lot]},
                        headers=h)
        assert r.status_code == 422, r.text
        return "verrouillée" in r.json()["detail"]

    def decider(h):
        r = client.put(f"/api/collections/{cid}/acces", headers=h,
                       json={"genre": "utilisateur", "principal": "invite", "niveau": "lecture"})
        assert r.status_code in (200, 201, 403), r.text
        return r.status_code in (200, 201)

    gestes = {"lire": lire, "annoter": annoter, "structurer": structurer,
              "vocabulaire": vocabulaire, "lots": lots, "decider": decider}
    assert set(gestes) == {a["code"] for a in ACTES}, "un acte sans geste qui le joue"
    for acte in ACTES:
        rang_acte = NIVEAUX.index(acte["niveau"])
        for accorde in NIVEAUX:
            permis = gestes[acte["code"]]({"Remote-User": membres[accorde]})
            assert permis == (NIVEAUX.index(accorde) >= rang_acte), (acte["code"], accorde)


def test_exporter_est_hors_rang_et_d_office_au_proprietaire():
    (exporter,) = HORS_RANG
    assert (exporter["code"], exporter["champ"], exporter["d_office"]) == \
        ("exporter", "exporter", PROPRIETAIRE)
    assert _portee(PROPRIETAIRE).peut_exporter(C) is True          # d'office
    assert _portee(ECRITURE).peut_exporter(C) is False             # écrire n'y suffit pas
    assert _portee(LECTURE, export=True).peut_exporter(C) is True  # la case y suffit
    assert _portee(LECTURE).peut_exporter(C) is False


def test_des_actes_lies_ont_le_meme_niveau_et_la_table_est_saine():
    codes = [a["code"] for a in ACTES] + [h["code"] for h in HORS_RANG]
    assert len(codes) == len(set(codes)), codes
    for a in ACTES:
        assert a["niveau"] in NIVEAUX, a
        assert set(a) == {"code", "libelle", "niveau", "lies", "avertissement"}, a
        assert a["libelle"], a
    liaisons = {}
    for a in ACTES:
        if a["lies"] is not None:
            liaisons.setdefault(a["lies"], set()).add(a["niveau"])
    # Une barre dessinée entre deux actes qui n'ont pas le même niveau serait fausse.
    assert all(len(niveaux) == 1 for niveaux in liaisons.values()), liaisons
    # Aujourd'hui, les quatre actes d'écriture sont inséparables.
    assert {a["code"] for a in ACTES if a["lies"] == ECRITURE} == \
        {"annoter", "structurer", "vocabulaire", "lots"}


def test_aucune_garde_ne_lit_la_description():
    """Des données, jamais une garde : dans `autorisation.py`, seule la fonction qui la met en
    forme nomme `ACTES` et `HORS_RANG`, et aucun autre module de l'application ne les lit."""
    arbre = ast.parse((REPO_ROOT / "autorisation.py").read_text(encoding="utf-8"))
    lecteurs = {f.name for f in ast.walk(arbre) if isinstance(f, ast.FunctionDef)
                and any(isinstance(n, ast.Name) and n.id in ("ACTES", "HORS_RANG")
                        for n in ast.walk(f))}
    assert lecteurs == {"description_des_droits"}, lecteurs
    for fichier in [*REPO_ROOT.glob("*.py"), *REPO_ROOT.glob("routes/*.py")]:
        if fichier.name == "autorisation.py":
            continue
        # Par l'arbre syntaxique et non par le texte : le mot figure dans des docstrings.
        noms = {n.id if isinstance(n, ast.Name) else n.attr
                for n in ast.walk(ast.parse(fichier.read_text(encoding="utf-8")))
                if isinstance(n, (ast.Name, ast.Attribute))}
        assert not noms & {"ACTES", "HORS_RANG"}, fichier.name


def test_la_route_sert_la_description_a_tous(client, derriere_proxy):
    """Sans aucune donnée du corpus : une personne qui ne possède rien la lit aussi."""
    for headers in ({"Remote-User": "personne"}, {}):
        r = client.get("/api/droits", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json() == autorisation.description_des_droits()
    corps = client.get("/api/droits").json()
    assert [a["code"] for a in corps["actes"]] == [a["code"] for a in ACTES]
    structurer = next(a for a in corps["actes"] if a["code"] == "structurer")
    assert structurer["avertissement"]
