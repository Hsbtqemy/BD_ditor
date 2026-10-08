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
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import ADMIN, direct_query, make_png

# `tools/` n'est pas un paquet et ses scripts s'importent à plat entre eux : c'est le
# DOSSIER qui doit être sur le chemin, exactement comme `routes/depot.py` le fait. Posé
# ici une fois plutôt que dans chaque test, ce qui était déjà l'usage plus bas.
_TOOLS = str(Path(__file__).resolve().parent.parent / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)


def _png():
    return make_png()


def _acces(db_path, collection_id, principal, niveau, genre="utilisateur"):
    """Pose un accès directement en base (le décor, pas le geste testé)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR REPLACE INTO collection_acces "
                     "(collection_id, genre, principal, niveau) VALUES (?, ?, ?, ?)",
                     (collection_id, genre, principal, niveau))
        conn.commit()
    finally:
        conn.close()


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
# 2 bis. Le périmètre du VOCABULAIRE (AUTH-11)
# --------------------------------------------------------------------------- #
# Le périmètre des ALBUMS était tenu ; celui des TERMES ne l'était pas. Les catalogues
# sortaient GLOBAUX — « entités canoniques du corpus », disait la doc —, si bien que
# l'export de dépôt d'une collection emportait les étiquettes, les axes et les valeurs des
# autres études, avec leur définition, leur note de portée et leur `collection_id`. Ce
# n'est pas un mot qui fuit, c'est une GRILLE D'ANALYSE, et elle part dans un entrepôt
# pérenne. La règle appliquée est celle du « % défini » : global ⊕ local à la collection
# déposée (`database.clause_appartenance`), quel que soit qui exporte.
def _terme_local(db_path, table, colonne, libelle, collection_id):
    """Rend un terme déjà créé LOCAL à une collection (le décor, pas le geste testé)."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(f"UPDATE {table} SET collection_id = ? WHERE {colonne} = ?",
                           (collection_id, libelle))
        assert cur.rowcount == 1, f"{table}.{colonne} = {libelle!r} introuvable"
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def vocabulaire_cloisonne(client, db_path, derriere_proxy):
    """Deux collections, un album chacune, et trois portées de vocabulaire.

    Les libellés sont volontairement improbables : une fuite se cherche par `in` sur le
    document entier, ce qui couvre du même coup les formes qu'on n'a pas énumérées (le
    classeur XLSX, une clé JSON ajoutée demain).

    Deux LIAISONS croisent exprès la frontière, parce qu'elles sont réelles — qui lit les
    deux collections a pu les poser : la région d'Alpha porte un tag et une valeur de
    Bravo, et le personnage (entité de corpus, sans collection) porte une valeur de
    chaque côté. Sans elles, un filtre posé sur le seul catalogue paraîtrait suffire.
    """
    alpha = _collection(client, "Corpus Alpha")
    bravo = _collection(client, "Corpus Bravo")
    a_alpha = _album(client, "ALBUM-ALPHA-9001", alpha["id"])
    _album(client, "ALBUM-BRAVO-9002", bravo["id"])
    pl = client.post(f"/api/albums/{a_alpha['id']}/import", headers=ADMIN,
                     files={"file": ("p.png", _png(), "image/png")}).json()
    reg = client.post(f"/api/planches/{pl['id']}/regions", headers=ADMIN,
                      json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}).json()

    def domaine(nom):
        return client.post("/api/domaines", json={"nom": nom}, headers=ADMIN).json()

    def dimension(nom, cible="case"):
        r = client.post("/api/attributs/dimensions",
                        json={"cible": cible, "nom": nom}, headers=ADMIN)
        assert r.status_code in (200, 201), r.text
        return r.json()

    def valeur(dim, v):
        r = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                        json={"valeur": v}, headers=ADMIN)
        assert r.status_code in (200, 201), r.text
        return r.json()

    for nom in ("dom-global-9100", "dom-alpha-9101", "dom-bravo-9102"):
        domaine(nom)
    dims = {nom: dimension(nom) for nom in
            ("dim-global-9200", "dim-alpha-9201", "dim-bravo-9202")}
    # Un axe de PERSONNAGE : les attributs d'une entité passent par `personnage_attribut`,
    # qui exige une dimension de cible `personnage` — un axe de case y est refusé en 422,
    # et le décor serait vide sans qu'aucune assertion ne s'en plaigne.
    dims["dim-perso-9203"] = dimension("dim-perso-9203", cible="personnage")
    vals = {nom: valeur(dims[dim], nom) for dim, nom in
            (("dim-global-9200", "val-global-9300"),
             ("dim-alpha-9201", "val-alpha-9301"),
             ("dim-bravo-9202", "val-bravo-9302"),
             # Une valeur qui reste GLOBALE sous un axe qui deviendra local à Bravo.
             # L'état est réel et daté : l'axe était global quand la valeur a été créée,
             # il a été restreint ensuite (v24 fait DESCENDRE la portée à la création,
             # pas rétroactivement). Elle est ici pour deux raisons. Elle donne au
             # `vocabulaire` CSV une LIGNE pour cet axe — ce dump est piloté par les
             # valeurs, donc un axe dont toutes les valeurs sont locales n'y paraît
             # jamais, et le filtre posé sur l'axe cessait d'être mesurable. Et elle pose
             # la règle « un terme n'est jamais plus GLOBAL que celui dont il dépend » :
             # son axe étant hors périmètre, elle ne voyage pas avec Alpha.
             ("dim-bravo-9202", "valg-sous-bravo-9312"),
             ("dim-perso-9203", "valp-global-9310"),
             ("dim-perso-9203", "valp-bravo-9311"))}
    # Un personnage, entité de CORPUS : il porte une valeur de chaque côté.
    perso = client.post("/api/personnages", json={"nom": "Témoin"}, headers=ADMIN).json()
    for v in ("valp-global-9310", "valp-bravo-9311"):
        r = client.put(f"/api/personnages/{perso['id']}/attributs",
                       json={"valeur_id": vals[v]["id"]}, headers=ADMIN)
        assert r.status_code == 200, r.text
    # La région d'Alpha porte trois tags et deux valeurs, des deux côtés de la frontière.
    r = client.put(f"/api/regions/{reg['id']}/annotation", headers=ADMIN,
                   json={"note": "note", "tags": ["tag-global-9400", "tag-alpha-9401",
                                                  "tag-bravo-9402"]})
    assert r.status_code == 200, r.text
    for v in ("val-alpha-9301", "val-bravo-9302"):
        r = client.put(f"/api/regions/{reg['id']}/attributs",
                       json={"valeur_id": vals[v]["id"]}, headers=ADMIN)
        assert r.status_code == 200, r.text

    # Un axe GLOBAL rattaché à un domaine LOCAL à Bravo : l'état d'une base antérieure à
    # v24, où la portée ne DESCENDAIT pas encore du domaine vers ses dimensions. C'est la
    # seule façon d'éprouver que le nom du domaine ne ressort pas par la bande, en
    # libellé d'axe, sur une dimension parfaitement lisible.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE attribut_dimension SET domaine_id = "
                     "(SELECT id FROM domaine WHERE nom = 'dom-bravo-9102') "
                     "WHERE nom = 'dim-global-9200'")
        conn.commit()
    finally:
        conn.close()

    for table, col, libelle, cid in (
            ("domaine", "nom", "dom-alpha-9101", alpha["id"]),
            ("domaine", "nom", "dom-bravo-9102", bravo["id"]),
            ("attribut_dimension", "nom", "dim-alpha-9201", alpha["id"]),
            ("attribut_dimension", "nom", "dim-bravo-9202", bravo["id"]),
            ("attribut_valeur", "valeur", "val-alpha-9301", alpha["id"]),
            ("attribut_valeur", "valeur", "val-bravo-9302", bravo["id"]),
            ("attribut_valeur", "valeur", "valp-bravo-9311", bravo["id"]),
            ("tags", "label", "tag-alpha-9401", alpha["id"]),
            ("tags", "label", "tag-bravo-9402", bravo["id"])):
        _terme_local(db_path, table, col, libelle, cid)
    return {"alpha": alpha, "bravo": bravo, "perso": perso,
            "global": ["dom-global-9100", "dim-global-9200", "val-global-9300",
                       "dim-perso-9203", "valp-global-9310", "tag-global-9400"],
            "a": ["dom-alpha-9101", "dim-alpha-9201", "val-alpha-9301", "tag-alpha-9401"],
            "b": ["dom-bravo-9102", "dim-bravo-9202", "val-bravo-9302",
                  "valg-sous-bravo-9312", "valp-bravo-9311", "tag-bravo-9402"]}


def _cw_texte(db_path, collection_id):
    """Le crosswalk de dépôt (`tools/crosswalk_depot.py`), sérialisé en texte."""
    import crosswalk_depot
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return json.dumps(crosswalk_depot.construire(conn, collection_id=collection_id),
                          ensure_ascii=False, default=str)
    finally:
        conn.close()


def _textes_de_depot(client, db_path, collection_id):
    """QUATRE des sorties d'une collection, en texte, chacune NOMMÉE — et pas toutes.

    Mesurées ici, parce qu'elles sont écrites séparément : l'arbre JSON, les tables CSV,
    la notice de dépôt, et la route que prend celui qui n'a plus de shell.

    **Ceci est une SÉLECTION, et ce n'est pas elle qui garde l'inventaire.** Elle mesure
    les CŒURS au plus près (`collecter`, `tables`, `construire`), sans emballage. Ce
    qu'elle ne regarde pas — l'archive zip et le classeur XLSX dépliés, la fiche de
    `description_collection`, le manifeste IIIF, la voie ShareDocs, les lignes de
    commande, `provenance_export`, `figure`, l'export d'album — est ÉNUMÉRÉ et joué par
    le cliquet de `tests/test_sorties_collection.py` (AUTH-11, sur le patron d'AUTH-5) :
    c'est lui qui échoue quand une sortie apparaît sans être jouée ni déclarée. Ajouter
    une sortie ICI ne la ferait entrer dans aucun inventaire.
    """
    import metadonnees_collection as mc
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        arbre = json.dumps(mc.collecter(conn, collection_id=collection_id),
                           ensure_ascii=False, default=str)
        # Le JOURNAL (A3) était EXCLU de ce contrôle jusqu'au 2026-09-24, parce que ses
        # charges `avant`/`apres` partaient mot pour mot et emportaient, avec le texte des
        # œuvres, le libellé des tags d'ailleurs. La décision de TAIRE LES CHARGES ferme
        # ce canal, et l'exclusion tombe avec lui : ses deux tables rentrent dans la
        # mesure. Une exception écrite en moins vaut mieux qu'une exception bien
        # commentée — tant qu'elle tenait, ce contrôle disait « propre » d'un artefact
        # dont il ne regardait pas deux tables sur dix-neuf.
        tbls = json.dumps(mc.tables(conn, collection_id=collection_id),
                          ensure_ascii=False, default=str)
    finally:
        conn.close()
    route = client.get(f"/api/collections/{collection_id}/depot/metadonnees",
                       headers=ADMIN)
    assert route.status_code == 200, route.text
    return {"records JSON": arbre, "tables CSV": tbls,
            "crosswalk de dépôt": _cw_texte(db_path, collection_id),
            "route /depot/metadonnees": route.content.decode("utf-8")}


def test_l_export_d_une_collection_ne_porte_que_son_vocabulaire(client, db_path,
                                                                vocabulaire_cloisonne):
    """AUTH-11 — l'export d'Alpha ne porte que le vocabulaire d'Alpha : global ⊕ local.

    Les termes de Bravo cherchés ici ne sont pas seulement dans les CATALOGUES : le tag et
    la valeur de Bravo sont POSÉS sur une région d'Alpha, et sur un personnage. Un filtre
    qui ne borderait que les listes de référence laisserait passer les liaisons — c'est le
    patron de la fiche, « la portée se pose sur la LIAISON et pas seulement sur le terme
    nommé ».

    Anti-vacuité en deux temps, et le second compte autant : le vocabulaire global ET
    celui d'Alpha doivent SORTIR (sans quoi un filtre qui vide tout passerait), et
    l'export de Bravo doit porter Bravo (sans quoi un filtre qui tairait toujours les
    termes locaux passerait aussi).
    """
    v = vocabulaire_cloisonne
    for quoi, texte in _textes_de_depot(client, db_path, v["alpha"]["id"]).items():
        for mot in v["b"]:
            assert mot not in texte, f"{quoi} : « {mot} » a fuité hors de sa collection"
        for mot in v["global"] + v["a"]:
            # Le crosswalk ne porte que des SUJETS (valeurs + tags), pas les axes.
            if quoi == "crosswalk de dépôt" and mot.startswith(("dom-", "dim-")):
                continue
            assert mot in texte, f"{quoi} : « {mot} » manque — le filtre a tout emporté"

    for quoi, texte in _textes_de_depot(client, db_path, v["bravo"]["id"]).items():
        for mot in v["b"]:
            if quoi == "crosswalk de dépôt" and mot.startswith(("dom-", "dim-")):
                continue
            assert mot in texte, f"{quoi} : Bravo n'exporte plus son propre « {mot} »"


def test_sans_collection_les_outils_exportent_TOUT_le_vocabulaire(db_path,
                                                                  vocabulaire_cloisonne):
    """Le mode « corpus entier » des CLI ne change pas (AUTH-11).

    `--collection` est un RESTREIGNEUR, et sans lui il n'y a pas de frontière à tenir :
    l'export décrit l'instance. Ce test existe parce que le remède se serait aussi bien
    écrit en filtrant toujours — auquel cas la sauvegarde descriptive du corpus entier
    aurait perdu la moitié de son lexique sans que rien ne le dise.
    """
    import metadonnees_collection as mc
    v = vocabulaire_cloisonne
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        texte = json.dumps(mc.collecter(conn), ensure_ascii=False, default=str)
        texte += json.dumps(mc.tables(conn), ensure_ascii=False, default=str)
    finally:
        conn.close()
    texte += _cw_texte(db_path, None)
    for mot in v["global"] + v["a"] + v["b"]:
        assert mot in texte, f"« {mot} » manque de l'export du corpus entier"


# --------------------------------------------------------------------------- #
# 2 ter. L'export d'un ALBUM suit la même règle (AUTH-11, tranché le 2026-10-07)
# --------------------------------------------------------------------------- #
# Un album sort « au titre d'une collection » (DROIT-2), et son vocabulaire suivait la
# portée d'export de la PERSONNE : le même fichier, étiqueté Alpha, portait le tag de
# Bravo pour qui exporte aussi Bravo, et pas pour qui n'exporte qu'Alpha. Décision (1) de
# Hugo : l'export d'un album au titre de A ne porte que le vocabulaire de A et le
# vocabulaire global, quelle que soit la personne — la règle du dépôt, et la même
# fonction (`database.clause_appartenance`).
#
# Ce que ces tests NE disent pas : qui a le droit d'exporter. C'est DROIT-2, inchangé, et
# `test_droit_export` le garde. Ici on ne regarde que ce que le fichier PORTE.
DES_DEUX = {"Remote-User": "proprio-des-deux"}      # possède Alpha ET Bravo
D_ALPHA = {"Remote-User": "proprio-d-alpha"}        # possède Alpha seule
LIT_LES_DEUX = {"Remote-User": "lit-les-deux"}      # lit les deux, n'exporte qu'Alpha
T_GLOBAL, T_ALPHA, T_BRAVO = "tag-global-9400", "tag-alpha-9401", "tag-bravo-9402"


@pytest.fixture
def album_partage(client, db_path, vocabulaire_cloisonne):
    """L'album d'Alpha et les comptes de la relecture du 2026-10-07.

    Sa région porte déjà les trois tags (`vocabulaire_cloisonne`). S'y ajoute une BULLE
    qui ne porte, elle, qu'un tag de Bravo et aucune note : la région dont il ne reste
    rien à montrer quand l'album sort au titre d'Alpha.
    """
    v = vocabulaire_cloisonne
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        album_id = conn.execute("SELECT id FROM albums WHERE titre = 'ALBUM-ALPHA-9001'"
                                ).fetchone()["id"]
        planche_id = conn.execute("SELECT id FROM planches WHERE album_id = ?",
                                  (album_id,)).fetchone()["id"]
        region_id = conn.execute("SELECT id FROM regions WHERE planche_id = ?",
                                 (planche_id,)).fetchone()["id"]
    finally:
        conn.close()
    r = client.post(f"/api/planches/{planche_id}/regions", headers=ADMIN,
                    json={"type": "bulle", "x": 1, "y": 1, "w": 3, "h": 3})
    assert r.status_code in (200, 201), r.text
    bulle_id = r.json()["id"]
    r = client.put(f"/api/regions/{bulle_id}/annotation", headers=ADMIN,
                   json={"note": "", "tags": [T_BRAVO]})
    assert r.status_code == 200, r.text
    # Le décor est RELU : sans la ligne d'annotation, « elle n'est pas dite annotée » ne
    # mesurerait rien.
    lignes = direct_query(db_path,
                          "SELECT a.note, t.label FROM annotations a "
                          "JOIN annotation_tags at ON at.annotation_id = a.id "
                          "JOIN tags t ON t.id = at.tag_id WHERE a.region_id = ?",
                          (bulle_id,))
    assert [(l["note"] or "", l["label"]) for l in lignes] == [("", T_BRAVO)], lignes

    a, b = v["alpha"]["id"], v["bravo"]["id"]
    _acces(db_path, a, "proprio-des-deux", "proprietaire")
    _acces(db_path, b, "proprio-des-deux", "proprietaire")
    _acces(db_path, a, "proprio-d-alpha", "proprietaire")
    _acces(db_path, a, "lit-les-deux", "lecture")
    _acces(db_path, b, "lit-les-deux", "lecture")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE collection_acces SET exporter = 1 "
                     "WHERE principal = 'lit-les-deux' AND collection_id = ?", (a,))
        conn.commit()
    finally:
        conn.close()
    return {**v, "album_id": album_id, "region_id": region_id, "bulle_id": bulle_id,
            "comptes": {"propriétaire d'Alpha et de Bravo": DES_DEUX,
                        "propriétaire d'Alpha seule": D_ALPHA,
                        "lit les deux, n'exporte qu'Alpha": LIT_LES_DEUX,
                        "administrateur": ADMIN}}


def _ranger_aussi_dans(db_path, album_id, collection_id):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (collection_id, album_id))
        conn.commit()
    finally:
        conn.close()


def _export_album(client, fmt, album_id, qui, collection_id=None, attendu=200):
    params = {"album_id": album_id}
    if collection_id is not None:
        params["collection_id"] = collection_id
    rep = client.get(f"/api/export/{fmt}", params=params, headers=qui)
    assert rep.status_code == attendu, (fmt, qui, rep.status_code, rep.text[:300])
    return rep.content


def _annotation_exportee(fmt, blob, region_id):
    """Ce que l'artefact dit de l'annotation d'UNE région : `None` si elle n'y est pas
    dite annotée, sinon (note, tags). Lu dans la structure, pas cherché dans le texte."""
    if fmt == "json":
        def chercher(noeuds):
            for n in noeuds:
                if n["id"] == region_id:
                    return n
                trouve = chercher(n["enfants"])
                if trouve:
                    return trouve
        noeud = next(filter(None, (chercher(p["regions"])
                                   for p in json.loads(blob)["planches"])))
        ann = noeud["annotation"]
        return None if ann is None else (ann["note"] or "", ann["tags"])
    if fmt == "csv":
        import csv
        ligne = next(l for l in csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
                     if int(l["region_id"]) == region_id)
        tags = [t for t in ligne["tags"].split("|") if t]
        return None if not (ligne["note"] or tags) else (ligne["note"], tags)
    import xml.etree.ElementTree as ET
    tei = "{http://www.tei-c.org/ns/1.0}"
    zone = next(z for z in ET.fromstring(blob).iter(f"{tei}zone")
                if z.get("{http://www.w3.org/XML/1998/namespace}id") == f"zone_{region_id}")
    note = zone.find(f"{tei}note")
    return None if note is None else (note.text or "", (note.get("ana") or "").split())


@pytest.mark.parametrize("nommee", [True, False], ids=["nommée", "par défaut"])
@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_l_album_au_titre_d_alpha_sort_identique_quel_que_soit_qui_exporte(
        client, album_partage, fmt, nommee):
    """Le MÊME artefact pour les comptes de la relecture — et il ne porte que le
    vocabulaire d'Alpha et le vocabulaire global.

    `par défaut` : aucun `collection_id`. L'album ne vit que dans Alpha, donc chacun
    l'obtient au titre d'Alpha sans la nommer — et la borne doit tenir là aussi, sans
    quoi il suffirait d'omettre un paramètre pour retrouver l'écart.
    """
    d = album_partage
    cid = d["alpha"]["id"] if nommee else None
    sortis = {nom: _export_album(client, fmt, d["album_id"], qui, cid)
              for nom, qui in d["comptes"].items()}
    for nom, blob in sortis.items():
        texte = blob.decode("utf-8")
        assert T_GLOBAL in texte and T_ALPHA in texte, (
            f"{fmt}, {nom} : le vocabulaire d'Alpha ou le global manque — le filtre a "
            "tout emporté")
        assert T_BRAVO not in texte, (
            f"{fmt}, {nom} : l'album sort au titre d'Alpha et porte un tag local à Bravo")
        # Les DONNÉES ne bougent pas : la région garde sa note et ses deux autres tags.
        assert _annotation_exportee(fmt, blob, d["region_id"]) == (
            "note", [T_ALPHA, T_GLOBAL])
    reference = sortis["propriétaire d'Alpha seule"]
    for nom, blob in sortis.items():
        assert blob == reference, (
            f"{fmt} : l'artefact de « {nom} » diffère de celui de la propriétaire "
            "d'Alpha seule — il varie selon qui clique")
    if fmt == "json":
        assert json.loads(reference)["exporte_au_titre_de"]["id"] == d["alpha"]["id"]


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_le_meme_album_au_titre_de_bravo_porte_bravo_et_plus_alpha(client, db_path,
                                                                   album_partage, fmt):
    """La contre-épreuve : la borne suit la collection NOMMÉE, elle ne tait pas les
    termes locaux. Rangé aussi dans Bravo, le même album sort au titre de Bravo avec le
    tag de Bravo — et sans celui d'Alpha, pour la même raison.

    Le droit, lui, n'a pas bougé : qui ne lit pas Bravo reçoit 404, qui la lit sans
    pouvoir l'exporter 403.
    """
    d = album_partage
    a, b = d["alpha"]["id"], d["bravo"]["id"]
    _ranger_aussi_dans(db_path, d["album_id"], b)
    sortis = {nom: _export_album(client, fmt, d["album_id"], d["comptes"][nom], b)
              for nom in ("propriétaire d'Alpha et de Bravo", "administrateur")}
    for nom, blob in sortis.items():
        texte = blob.decode("utf-8")
        assert T_GLOBAL in texte and T_BRAVO in texte, (fmt, nom)
        assert T_ALPHA not in texte, (
            f"{fmt}, {nom} : l'album sort au titre de Bravo et porte un tag local à Alpha")
        assert _annotation_exportee(fmt, blob, d["region_id"]) == (
            "note", [T_BRAVO, T_GLOBAL])
    assert len(set(sortis.values())) == 1, f"{fmt} : l'artefact varie selon qui clique"
    # Et au titre d'Alpha, le même album rend toujours Alpha, pour les deux.
    for nom in sortis:
        texte = _export_album(client, fmt, d["album_id"], d["comptes"][nom], a).decode("utf-8")
        assert T_ALPHA in texte and T_BRAVO not in texte, (fmt, nom)
    _export_album(client, fmt, d["album_id"], D_ALPHA, b, attendu=404)
    _export_album(client, fmt, d["album_id"], LIT_LES_DEUX, b, attendu=403)


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_une_region_au_seul_tag_d_ailleurs_ne_sort_pas_annotee(client, db_path,
                                                               album_partage, fmt):
    """Une bulle sans note, qui ne porte qu'un tag de Bravo : au titre d'Alpha il n'en
    reste rien à montrer, et l'export ne la dit PAS annotée — ni `annotation` vide en
    JSON, ni `<note>` vide en TEI. C'est la règle de `socle._sql_a_montrer`, posée par
    `9446d68` pour les compteurs : le marqueur suit ce qu'on montre.

    La région elle-même sort toujours : c'est une DONNÉE de l'album.
    """
    d = album_partage
    for nom, qui in d["comptes"].items():
        blob = _export_album(client, fmt, d["album_id"], qui, d["alpha"]["id"])
        assert _annotation_exportee(fmt, blob, d["bulle_id"]) is None, (
            f"{fmt}, {nom} : la bulle est dite annotée alors qu'il n'en sort rien")
    _ranger_aussi_dans(db_path, d["album_id"], d["bravo"]["id"])
    blob = _export_album(client, fmt, d["album_id"], ADMIN, d["bravo"]["id"])
    assert _annotation_exportee(fmt, blob, d["bulle_id"]) == ("", [T_BRAVO]), (
        f"{fmt} : au titre de Bravo, la bulle doit sortir annotée de son tag")


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_un_album_ne_sort_pas_au_titre_d_une_collection_ou_il_n_est_pas_range(
        client, album_partage, fmt):
    """Le titre gouverne le CONTENU, donc il ne se choisit pas librement.

    L'album n'est rangé que dans Alpha. Bravo est lue ET exportable pour le propriétaire
    des deux comme pour l'administrateur : rien, dans leurs droits, ne s'oppose à ce qu'ils
    la nomment. Si `_collection_d_export` cherchait la collection nommée parmi toutes les
    collections et non parmi celles de l'ALBUM, ils obtiendraient 200 — l'album d'Alpha,
    étiqueté Bravo, avec le vocabulaire de Bravo. Avant le 2026-10-07 cette ligne ne
    gardait qu'une étiquette ; elle est maintenant la seule chose qui empêche un album de
    sortir avec le vocabulaire d'une collection où il n'est pas (mutant de la relecture
    croisée, qui survivait). 404, comme pour une collection qui n'existe pas.
    """
    d = album_partage
    for nom in ("propriétaire d'Alpha et de Bravo", "administrateur"):
        rep = client.get(f"/api/export/{fmt}", headers=d["comptes"][nom],
                         params={"album_id": d["album_id"],
                                 "collection_id": d["bravo"]["id"]})
        assert rep.status_code == 404, (
            f"{fmt}, {nom} : {rep.status_code} — l'album sort au titre d'une collection "
            "où il n'est pas rangé")
        assert T_BRAVO not in rep.text and "ALBUM-ALPHA-9001" not in rep.text
    # Anti-vacuité : la même requête, au titre de la collection où il EST rangé, répond.
    _export_album(client, fmt, d["album_id"], DES_DEUX, d["alpha"]["id"])


def test_le_nom_du_fichier_dit_le_titre_en_csv_comme_en_tei(client, db_path,
                                                            album_partage):
    """Deux contenus différents — au titre d'Alpha, au titre de Bravo — ne doivent pas
    porter le même nom. Le CSV disait déjà `_c<N>` ; le TEI s'appelait
    `album_<id>_tei.xml` dans tous les cas. Un nom SANS `_c<N>` n'existe plus : depuis le
    2026-10-07 aucun album ne sort sans titre (cf.
    `test_sans_titre_un_album_de_plusieurs_collections_ne_sort_plus`)."""
    d = album_partage
    a, b, alb = d["alpha"]["id"], d["bravo"]["id"], d["album_id"]
    _ranger_aussi_dans(db_path, alb, b)

    def nom(fmt, collection_id):
        params = {"album_id": alb}
        if collection_id is not None:
            params["collection_id"] = collection_id
        rep = client.get(f"/api/export/{fmt}", params=params, headers=ADMIN)
        assert rep.status_code == 200, rep.text
        return re.search(r'filename="([^"]+)"', rep.headers["content-disposition"]).group(1)

    assert nom("csv", a) == f"album_{alb}_c{a}.csv"
    assert nom("tei", a) == f"album_{alb}_c{a}_tei.xml"
    assert nom("tei", b) == f"album_{alb}_c{b}_tei.xml"
    assert nom("csv", b) == f"album_{alb}_c{b}.csv"


def test_les_tags_d_une_region_sortent_dans_le_meme_ordre_dans_les_trois_formats(
        client, db_path, album_partage):
    """Triés par libellé, partout. Le CSV concaténait sans `ORDER BY` : l'ordre suivait en
    pratique la CRÉATION des tags, que SQLite ne promet pas. Deux tags globaux sont donc
    créés dans l'ordre INVERSE de l'alphabet — `zz…` d'abord — sur la bulle du décor."""
    d = album_partage
    zz, aa = "zz-ordre-9700", "aa-ordre-9701"
    for tags in ([zz], [zz, aa]):                     # deux écritures : `zz` naît avant `aa`
        r = client.put(f"/api/regions/{d['bulle_id']}/annotation", headers=ADMIN,
                       json={"note": "", "tags": tags})
        assert r.status_code == 200, r.text
    ids = {l["label"]: l["id"] for l in direct_query(
        db_path, "SELECT id, label FROM tags WHERE label IN (?, ?)", (zz, aa))}
    assert ids[zz] < ids[aa], "le décor ne crée plus `zz` avant `aa` : l'ordre ne mesure rien"
    for fmt in ("json", "csv", "tei"):
        blob = _export_album(client, fmt, d["album_id"], ADMIN, d["alpha"]["id"])
        assert _annotation_exportee(fmt, blob, d["bulle_id"]) == ("", [aa, zz]), fmt


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_sans_titre_un_album_de_plusieurs_collections_ne_sort_plus(client, db_path,
                                                                   album_partage, fmt):
    """Plus AUCUN album ne sort sans titre — portée totale comprise (Hugo, 2026-10-07).

    RENVERSEMENT DATÉ. Ce test s'appelait
    `test_sans_titre_l_export_d_album_ne_borne_pas_son_vocabulaire` et fixait l'inverse :
    en portée totale (administrateur, mono-poste), un album rangé dans plusieurs
    collections et exporté sans en nommer aucune sortait en 200, `exporte_au_titre_de:
    null`, avec TOUT le vocabulaire posé sur ses régions — « il ne sort alors sous aucun
    droit particulier » (DROIT-2, 2026-09-11). Ancien attendu : 200, les tags d'Alpha ET
    de Bravo. Nouvel attendu : le **422 nommé** que recevaient déjà les autres comptes.

    La raison : depuis que le titre gouverne le CONTENU (AUTH-11), « sans titre » était le
    seul export d'album dont le vocabulaire n'était borné par rien, et le seul où le même
    album changeait de contenu selon qu'il était rangé dans une ou deux collections.

    Ce qui reste vrai, et que `test_l_album_au_titre_d_alpha_sort_identique…[par défaut]`
    garde : un album rangé dans UNE seule collection sort sans rien nommer, au titre de
    celle-là.
    """
    d = album_partage
    a, b = d["alpha"]["id"], d["bravo"]["id"]
    _ranger_aussi_dans(db_path, d["album_id"], b)
    for nom in ("administrateur", "propriétaire d'Alpha et de Bravo"):
        rep = client.get(f"/api/export/{fmt}", params={"album_id": d["album_id"]},
                         headers=d["comptes"][nom])
        assert rep.status_code == 422, (fmt, nom, rep.status_code, rep.text[:200])
        detail = rep.json()["detail"]
        assert "Corpus Alpha" in detail and "Corpus Bravo" in detail, detail
        assert f"({a})" in detail and f"({b})" in detail, detail
        for mot in (T_GLOBAL, T_ALPHA, T_BRAVO, "ALBUM-ALPHA-9001"):
            assert mot not in rep.text, f"{fmt}, {nom} : le refus porte « {mot} »"
    # Nommée, l'une comme l'autre répond — le refus porte sur le SILENCE, pas sur l'album.
    for cid, porte, tait in ((a, T_ALPHA, T_BRAVO), (b, T_BRAVO, T_ALPHA)):
        texte = _export_album(client, fmt, d["album_id"], ADMIN, cid).decode("utf-8")
        assert porte in texte and tait not in texte, (fmt, cid)


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_un_album_sans_collection_ne_sort_pas_sans_titre_non_plus(client, db_path,
                                                                 album, planche, fmt):
    """L'invariant « aucun album hors collection » (AUTH-2) tient par les ROUTES ; une base
    retouchée à la main peut le violer, et seule une portée totale lit alors l'album. Il
    ne doit pas sortir pour autant sans titre : c'était la dernière façon d'atteindre un
    export non borné. 409 qui NOMME l'état, pas un 403 « droit d'exporter » qui mentirait
    à quelqu'un qui a tous les droits. Mono-poste, exprès : c'est le cas le plus permissif.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM collection_album WHERE album_id = ?", (album["id"],))
        conn.commit()
    finally:
        conn.close()
    rep = client.get(f"/api/export/{fmt}", params={"album_id": album["id"]})
    assert rep.status_code == 409, (fmt, rep.status_code, rep.text[:200])
    assert "aucune collection" in rep.json()["detail"], rep.text


def test_les_exports_transversaux_gardent_la_regle_de_la_personne(client, db_path,
                                                                  album_partage):
    """La décision du 2026-10-07 s'arrête à l'export d'album. La Recherche et
    l'Exploration ne sortent au titre d'AUCUNE collection : elles traversent ce que la
    personne a le droit d'exporter, et leur vocabulaire suit sa portée d'export
    (`Portee.pour_export`, DROIT-2) — même filtrées sur un seul album.

    Ce test ne peut pas être rouge sur le code d'avant : il garde ce qui ne devait PAS
    changer. Borner ces deux cœurs par erreur le ferait tomber.
    """
    d = album_partage
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, 'DIS', 'dire', 'VERB', '')", (d["region_id"],))
        conn.commit()
    finally:
        conn.close()
    sorties = (("/api/recherche/export.csv", {"album": d["album_id"]}),
               ("/api/analyse/croisement.csv",
                {"axe_x": "tag", "axe_y": "type", "album": d["album_id"]}))
    for route, params in sorties:
        def texte(qui):
            rep = client.get(route, params=params, headers=qui)
            assert rep.status_code == 200, (route, qui, rep.text[:300])
            return rep.text
        for qui in (DES_DEUX, ADMIN):
            assert T_BRAVO in texte(qui) and T_ALPHA in texte(qui), (
                f"{route} : qui exporte Alpha ET Bravo doit emporter les deux — "
                "l'export transversal a été borné comme un export d'album")
        for qui in (D_ALPHA, LIT_LES_DEUX):
            assert T_ALPHA in texte(qui) and T_BRAVO not in texte(qui), (route, qui)


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


# --------------------------------------------------------------------------- #
# 4. Le dépôt ShareDocs — même artefact, autre destination, autre droit
# --------------------------------------------------------------------------- #
def _capter_upload(monkeypatch):
    """Remplace l'envoi WebDAV et retient ce qui serait parti."""
    import pipeline.sharedocs as sd
    capte = {}
    monkeypatch.setattr(
        sd, "upload",
        lambda chemin, data, *, principal, compte=None:
            capte.update(chemin=chemin, data=data, principal=principal, compte=compte)
            or {"chemin": chemin, "compte": "instance", "user": "u"})
    return capte


def test_le_depot_envoie_L_ARTEFACT_et_le_journalise(client, db_path, monkeypatch,
                                                     derriere_proxy):
    """Le dépôt et le téléchargement fabriquent le MÊME octet.

    C'est la raison d'être de `routes.depot.produire` : deux fabrications séparées
    donneraient deux artefacts au même nom et au contenu différent, et un entrepôt garde
    les deux versions sans que rien ne dise laquelle a été déposée.
    """
    capte = _capter_upload(monkeypatch)
    col = _collection(client, "Corpus")
    r = client.post(f"/api/collections/{col['id']}/depot/deposer",
                    json={"dossier": "Projets/BD", "quoi": "description",
                          "format": "json"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert capte["chemin"].startswith("Projets/BD/depot-description-c")
    assert capte["chemin"].endswith(".json")

    # Le même artefact que la voie GET, au nom et à l'horodatage près. « À l'horodatage
    # près » était dit ici et non FAIT : les deux fabrications posent chacune leur
    # `genere_le`, à la SECONDE (`description_collection`), et le test échouait donc quand
    # la seconde tournait entre les deux appels — au hasard, une fois sur quelques
    # dizaines, mesuré le 2026-09-23. Une garde qui échoue au hasard apprend à être
    # ignorée : on retire le champ qui bouge, et on exige qu'il soit là des deux côtés.
    g = client.get(f"/api/collections/{col['id']}/depot/description", headers=ADMIN)
    depose, servi = json.loads(capte["data"]), json.loads(g.content)
    for artefact in (depose, servi):
        assert artefact["description_collection"].pop("genere_le")
    assert depose == servi

    # SHARE-1 — l'acte est tracé, et il distingue la personne du compte employé.
    lignes = direct_query(db_path,
                          "SELECT type, cible_table, apres FROM evenement "
                          "WHERE cible_table = 'sharedocs'")
    assert len(lignes) == 1, lignes
    apres = json.loads(lignes[0]["apres"])
    assert apres["export"] == "description" and apres["collection_id"] == col["id"]
    assert apres["compte"] == "instance"


def test_deposer_demande_de_POUVOIR_ADMINISTRER_la_collection(client, monkeypatch,
                                                              db_path, derriere_proxy):
    """Télécharger, c'est emporter pour soi ce qu'on a le droit de sortir ; déposer, c'est
    écrire dans un dossier partagé dont l'application ne contrôle pas l'audience.

    Depuis DROIT-2, lire ne suffit plus à télécharger : la lectrice reçoit la case
    d'export. Sans elle, le test éprouverait un refus d'EXPORT, et l'asymétrie qu'il
    garde — exporter n'est pas administrer — ne se verrait plus.

    L'asymétrie est le cœur de l'arbitrage : la MÊME personne, sur la MÊME collection,
    obtient le fichier et se voit refuser le dépôt. Un test qui ne vérifierait que le
    refus passerait aussi sur une garde posée trop haut — celle qui fermerait les deux,
    c'est-à-dire l'erreur d'AUTH-4.
    """
    _capter_upload(monkeypatch)
    col = _collection(client, "Corpus")          # créée par `decor`, qui en est propriétaire
    _acces(db_path, col["id"], "lectrice", "lecture")
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE collection_acces SET exporter = 1 WHERE principal = 'lectrice'")
        conn.commit()
    finally:
        conn.close()
    moi = {"Remote-User": "lectrice"}

    lu = client.get(f"/api/collections/{col['id']}/depot/description", headers=moi)
    assert lu.status_code == 200, "lire AVEC le droit d'exporter doit suffire à télécharger"

    depose = client.post(f"/api/collections/{col['id']}/depot/deposer",
                         json={"quoi": "description", "format": "json"}, headers=moi)
    assert depose.status_code == 403, depose.text

    # Et le refus nomme LE GESTE REFUSÉ. Il héritait du message générique de
    # `_get_collection` — « peut la partager ou la modifier » — donc on refusait un geste
    # qu'on n'avait pas demandé en en nommant deux autres qu'on n'avait pas tentés.
    # Trouvé en jouant le cas à la main : le test ne regardait que le code.
    detail = depose.json()["detail"]
    assert "ShareDocs" in detail, detail
    assert "partager ou la modifier" not in detail, detail
    # Il dit aussi ce qui RESTE possible : le refus porte sur le dépôt, pas sur l'export.
    assert "téléchargement" in detail, detail


def test_un_refus_de_ShareDocs_est_rendu_TEL_QUEL(client, monkeypatch, derriere_proxy):
    """400 en portant le message du serveur WebDAV : « Écriture refusée (403) » se corrige
    chez Huma-Num, pas dans l'application."""
    import pipeline.sharedocs as sd

    def boom(chemin, data, *, principal, compte=None):
        raise sd.ShareDocsError("Écriture refusée (403)")

    monkeypatch.setattr(sd, "upload", boom)
    col = _collection(client, "Corpus")
    r = client.post(f"/api/collections/{col['id']}/depot/deposer",
                    json={"quoi": "description", "format": "json"}, headers=ADMIN)
    assert r.status_code == 400
    assert "403" in r.json()["detail"]



@pytest.mark.parametrize("quoi,mauvais", [("description", "xlsx"), ("metadonnees", "csv"),
                                          ("iiif", "json")])
def test_le_depot_refuse_un_format_qui_n_existe_pas_pour_cet_export(client, monkeypatch,
                                                                    quoi, mauvais,
                                                                    derriere_proxy):
    """Le corps JSON du dépôt n'a pas le `Query(pattern=…)` des routes GET, et le
    dispatch retombait sur sa dernière branche.

    Concrètement : `{"quoi": "metadonnees", "format": "csv"}` déposait un CLASSEUR XLSX,
    au nom cohérent avec son contenu et sans rapport avec la demande. Une
    réinterprétation silencieuse est pire qu'un refus — le fichier a l'air bon, et c'est
    l'entrepôt qui découvre l'écart.
    """
    capte = _capter_upload(monkeypatch)
    col = _collection(client, "Corpus")
    r = client.post(f"/api/collections/{col['id']}/depot/deposer",
                    json={"quoi": quoi, "format": mauvais,
                          "base_url": "https://i.example/iiif"}, headers=ADMIN)
    assert r.status_code == 422, r.text
    assert mauvais in r.json()["detail"]
    assert not capte, "un artefact est parti malgré le refus"
