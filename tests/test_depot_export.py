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

    **Ce qui n'est PAS couvert, et qu'il ne faut pas croire couvert** : l'archive zip et
    le classeur XLSX (ils dérivent de `tables()`, donc le même cœur, mais leur emballage
    n'est pas relu ici), la fiche de `description_collection` (elle a sa limite écrite
    dans `docs/export-metadonnees.md`), le manifeste IIIF, le dépôt ShareDocs, et les
    artefacts hors de ce module — `provenance_export`, `figure`, l'export d'album. Un
    cliquet qui ÉNUMÈRE les sorties, sur le patron d'AUTH-5, reste à écrire ; tant qu'il
    n'existe pas, cette liste est une sélection, pas un inventaire, et une sortie ajoutée
    demain n'y entrera pas toute seule.
    """
    import metadonnees_collection as mc
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        arbre = json.dumps(mc.collecter(conn, collection_id=collection_id),
                           ensure_ascii=False, default=str)
        brutes = mc.tables(conn, collection_id=collection_id)
        # Le JOURNAL (A3) est HORS de ce contrôle, et c'est écrit plutôt que subi. Ses
        # deux tables sortent au grain CORPUS par décision — « un run/acte n'appartient
        # pas à un album, et l'acte SURVIT à la suppression de sa cible → non
        # re-scopable » (`metadonnees_collection.tables`) —, et leurs charges
        # `avant`/`apres` sont publiées mot pour mot. Ce qui y voyage n'est pas seulement
        # le libellé d'un tag d'ailleurs : `journal._REGION_COLS` contient `ocr_texte`,
        # donc le TEXTE des œuvres de toute l'instance, `--verbatim` ou non (mesuré le
        # 2026-09-23). C'est une case ouverte à part, plus large qu'AUTH-11 ; l'exclure
        # ICI garde le contrôle honnête sur ce qu'il mesure, au lieu de le faire échouer
        # sur une question qu'on n'a pas tranchée. Cf. `docs/export-metadonnees.md`.
        tbls = json.dumps({k: v for k, v in brutes.items()
                           if k not in ("activite", "evenement")},
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
