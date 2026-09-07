"""EXP-1 — les exports de dépôt, atteignables sans shell.

La doctrine « scripts hors-app » supposait le mono-poste. Déployé derrière Authelia, plus
personne n'a de shell : ces routes sont ce qui rend `tools/description_collection.py` et
`tools/metadonnees_collection.py` utilisables par ceux à qui ils servent.

Trois familles de contrôles, et la deuxième est celle qui vaut le détour.

1. **Les formats sortent** — c'est le smoke test, il dit que la plomberie tient.
2. **Le PÉRIMÈTRE est celui de la collection.** `test_autorisation.py` prouve qu'une route
   consulte la portée ; il ne prouve jamais qu'elle en tire la bonne conclusion, et il le
   dit lui-même. Ici l'erreur possible est nommable : les trois outils acceptent
   `collection_id=None`, qui vaut « corpus entier » sans consulter la moindre portée.
   Une route qui l'oublierait répondrait 200, avec un fichier plausible, contenant le
   corpus des autres. Deux tests s'en occupent — un sur le comportement, un sur la forme
   des chemins déclarés.
3. **Les refus disent la vérité** — 404 sur l'invisible (AUTH-2 : « existe mais pas pour
   vous » révèle la composition du corpus), 503 nommé sur un extra absent.
"""
import io
import json
import re
import sqlite3
import zipfile

import pytest

from conftest import ADMIN


# --------------------------------------------------------------------------- #
# Décor
# --------------------------------------------------------------------------- #
def _collection(client, nom, headers=ADMIN):
    r = client.post("/api/collections", json={"nom": nom}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _album(client, titre, collection_id, headers=ADMIN):
    r = client.post("/api/albums",
                    json={"titre": titre, "serie": "S", "annee": 2016,
                          "collection_id": collection_id},
                    headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.fixture
def deux_collections(client, derriere_proxy):
    """Deux collections cloisonnées, un album dans chacune.

    Le décor du test de périmètre : les titres sont volontairement distincts et
    improbables, pour qu'une fuite se cherche par `in` plutôt que par comptage.
    """
    a = _collection(client, "Corpus Alpha")
    b = _collection(client, "Corpus Bravo")
    _album(client, "ALBUM-ALPHA-9001", a["id"])
    _album(client, "ALBUM-BRAVO-9002", b["id"])
    return a, b


# --------------------------------------------------------------------------- #
# 1. Les formats sortent
# --------------------------------------------------------------------------- #
def test_la_fiche_de_description_se_telecharge(client, album, derriere_proxy):
    """Le geste que le chantier existe pour rendre possible : obtenir la fiche sans shell."""
    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/description", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert "description_collection" in json.loads(r.content)
    assert r.headers["content-disposition"].startswith("attachment;")


def test_le_catalogue_csv_porte_son_BOM(client, derriere_proxy):
    """Sans BOM, Excel affiche « collectionÂ » au lieu de « collection ».

    La CLI écrit en `utf-8-sig` pour cette raison exacte ; un CSV téléchargé s'ouvre dans
    un tableur bien plus souvent qu'un CSV écrit sur disque par un script.
    """
    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/description?format=csv",
                   headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 absent"


@pytest.mark.parametrize("fmt", ["json", "zip", "xlsx"])
def test_les_metadonnees_sortent_dans_les_trois_formats(client, album, fmt, derriere_proxy):
    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/metadonnees?format={fmt}",
                   headers=ADMIN)
    if fmt == "xlsx" and r.status_code == 503:
        pytest.skip("openpyxl absent (extra d'export) — c'est le comportement attendu")
    assert r.status_code == 200, r.text
    assert r.content, "réponse vide"


def test_l_archive_porte_EXACTEMENT_les_tables_du_coeur(client, album, db_path,
                                                        derriere_proxy):
    """La route ne choisit pas ce qu'elle expédie : elle expédie ce que le cœur produit.

    C'est la case « aucune logique d'export réécrite côté serveur », rendue vérifiable.
    Une route qui filtrerait, renommerait ou oublierait une table répondrait 200 avec une
    archive parfaitement lisible — seule la comparaison à la source le dirait.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import metadonnees_collection

    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/metadonnees?format=zip",
                   headers=ADMIN)
    assert r.status_code == 200, r.text

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        attendues = set(metadonnees_collection.tables(conn, collection_id=col["id"]))
    finally:
        conn.close()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        noms = set(z.namelist())
        assert noms == {f"{t}.csv" for t in attendues}
        # Le BOM voyage AUSSI dans l'archive : c'est le seul format que la CLI ne
        # produisait par aucun test, donc rien ne l'aurait signalé.
        for n in noms:
            assert z.read(n).startswith(b"\xef\xbb\xbf"), f"{n} sans BOM"


def test_le_nom_du_fichier_est_DATE(client, derriere_proxy):
    """Ce qui est figé doit être daté (DROIT-1).

    Deux exports de la même collection à un an d'intervalle sont autrement
    indistinguables dans un dossier de dépôt — c'est l'argument qui a fait dater le
    manifeste IIIF, et il vaut pour tout ce qui part d'ici.
    """
    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/description", headers=ADMIN)
    dispo = r.headers["content-disposition"]
    assert re.search(rf'filename="depot-description-c{col["id"]}-\d{{8}}-\d{{6}}\.json"',
                     dispo), dispo


# --------------------------------------------------------------------------- #
# 2. Le périmètre est celui de la collection
# --------------------------------------------------------------------------- #
# L'administrateur est le cas le PLUS exigeant, et c'est pourquoi les deux tests suivants
# l'emploient : sa portée est totale, donc aucune garde d'autorisation ne peut rattraper un
# périmètre mal passé. Si `collection_id` n'arrivait pas jusqu'au cœur, ces tests seraient
# les seuls à le voir — un utilisateur ordinaire, lui, serait protégé par sa portée, et le
# défaut dormirait jusqu'au premier export fait par quelqu'un qui a tous les droits.
def test_les_metadonnees_ne_franchissent_pas_la_frontiere_de_collection(client,
                                                                        deux_collections):
    """Les enregistrements NOMMENT les albums : la fuite se cherche donc par le titre."""
    a, _b = deux_collections
    r = client.get(f"/api/collections/{a['id']}/depot/metadonnees", headers=ADMIN)
    assert r.status_code == 200, r.text
    texte = r.content.decode("utf-8")
    assert "ALBUM-ALPHA-9001" in texte, "l'album de la collection demandée est absent"
    assert "ALBUM-BRAVO-9002" not in texte, "un album d'une AUTRE collection a fuité"


def test_la_fiche_ne_compte_que_les_albums_de_la_collection(client, deux_collections):
    """La fiche est un ROLL-UP : elle ne nomme rien, elle compte.

    Sa fuite à elle n'est donc pas un titre qui apparaît, mais un COMPTEUR trop grand —
    et c'est la forme la plus discrète des deux, puisqu'un « 2 » au lieu d'un « 1 » ne
    ressemble à rien. `couverture.albums` est la mesure directe du périmètre : sur deux
    collections d'un album chacune, tout autre chiffre que 1 dit que le cœur a été appelé
    en mode « corpus entier ».
    """
    a, _b = deux_collections
    r = client.get(f"/api/collections/{a['id']}/depot/description", headers=ADMIN)
    assert r.status_code == 200, r.text
    fiche = json.loads(r.content)["description_collection"]
    assert fiche["couverture"]["albums"] == 1, (
        f"{fiche['couverture']['albums']} albums comptés pour une collection qui n'en a "
        "qu'un : le périmètre n'est pas arrivé jusqu'au cœur")
    # Et la fiche identifie bien la collection demandée, pas « le corpus ».
    assert fiche["identite"]["nom"] == "Corpus Alpha", fiche["identite"]


def test_aucune_route_de_depot_n_atteint_les_outils_SANS_collection():
    """Le cas « corpus entier » ne doit pas être atteignable, et pas seulement inutilisé.

    Les trois outils traitent `collection_id=None` comme « tout le corpus », sans consulter
    la moindre portée — c'est le défaut de leur CLI, qui tourne sur la machine de la base.
    En faisant du `collection_id` un segment de CHEMIN, ce cas cesse d'être joignable : une
    route qui l'omettrait ne répondrait pas.

    Ce contrôle porte sur la FORME des chemins et non sur un appel, parce qu'il doit tenir
    pour les routes qu'on ajoutera ici plus tard — le manifeste IIIF, le dépôt ShareDocs —
    sans qu'on ait à y repenser.
    """
    import main
    chemins = [r.path for r in main.app.routes
               if "/depot/" in getattr(r, "path", "")]
    assert chemins, "aucune route de dépôt trouvée : le contrôle ne mesurerait rien"
    for c in chemins:
        assert "{collection_id}" in c, (
            f"{c} n'impose pas de collection : elle peut atteindre les outils en mode "
            "« corpus entier », qui ignore AUTH-2")


# --------------------------------------------------------------------------- #
# 3. Les refus disent la vérité
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chemin", ["description", "metadonnees"])
def test_une_collection_qu_on_ne_lit_pas_est_INTROUVABLE(client, deux_collections, chemin):
    """404 et jamais 403 : un « interdit » révélerait que la collection existe.

    C'est la règle d'AUTH-2, et `_get_collection` la porte pour nous — c'est même la
    raison pour laquelle il est descendu au socle plutôt que d'être redérivé ici.
    """
    a, _b = deux_collections
    r = client.get(f"/api/collections/{a['id']}/depot/{chemin}",
                   headers={"Remote-User": "etranger"})
    assert r.status_code == 404, f"{r.status_code} — un 403 nommerait une collection cachée"


def test_le_xlsx_indisponible_repond_503_en_NOMMANT_le_paquet(client, monkeypatch,
                                                              derriere_proxy):
    """Un extra absent n'est pas une faute de l'appelant, et `SystemExit` n'est pas une
    réponse HTTP.

    Le cœur levait un `SystemExit` — parfait pour une CLI, intenable ici : il n'hérite pas
    d'`Exception`, donc il traverse les gardes d'un serveur. EXP-1 l'a remplacé par
    `ExportIndisponible`, et ce test vérifie les DEUX moitiés : que la route l'attrape, et
    qu'elle nomme le paquet à installer plutôt que de dire « erreur interne ».
    """
    import metadonnees_collection

    def _absent(*a, **k):
        raise metadonnees_collection.ExportIndisponible(
            "XLSX demandé mais 'openpyxl' est absent "
            "(pip install -r requirements-export.txt).")

    monkeypatch.setattr(metadonnees_collection, "xlsx_tables", _absent)
    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/metadonnees?format=xlsx",
                   headers=ADMIN)
    assert r.status_code == 503, r.text
    assert "openpyxl" in r.json()["detail"]


@pytest.mark.parametrize("chemin,mauvais", [("description", "xlsx"), ("metadonnees", "csv")])
def test_un_format_inconnu_est_refuse_avant_tout_calcul(client, chemin, mauvais,
                                                        derriere_proxy):
    """422, et non un export vide ou un 500 : le format est validé par le contrat de route.

    `description` ne produit pas de XLSX et `metadonnees` pas de CSV isolé — demander l'un
    pour l'autre est une erreur d'appelant, pas un cas dégradé à servir.
    """
    col = _collection(client, "Corpus")
    r = client.get(f"/api/collections/{col['id']}/depot/{chemin}?format={mauvais}",
                   headers=ADMIN)
    assert r.status_code == 422, r.text
