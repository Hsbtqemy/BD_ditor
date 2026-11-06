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

from conftest import ADMIN, direct_query, make_png, poser_tags

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
        # COL-3, tranche 3c (F2) : un accès de collection suppose d'être du projet — ce
        # que la v38 fait de tout accès hors projet ; le décor le pose de même.
        conn.execute("INSERT OR IGNORE INTO projet_acces (projet_id, genre, principal, role) "
                     "SELECT p.id, ?, ?, 'membre' FROM collection c JOIN projet p "
                     "ON p.id = COALESCE(c.projet_id, (SELECT id FROM projet WHERE repli = 1)) "
                     "WHERE c.id = ? AND p.bac_a_sable_de IS NULL AND p.jeu = 0",
                     (genre, principal, collection_id))
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
# 2 bis. Le VOCABULAIRE d'hier ne sort plus (ANN-7, le basculement)
# --------------------------------------------------------------------------- #
# Jusqu'au basculement, ces tests gardaient le PÉRIMÈTRE du vocabulaire (AUTH-11) : un
# export de dépôt emportait les termes globaux et ceux de SA collection, jamais ceux d'une
# autre — la règle d'appartenance (`database.clause_appartenance`, retirée). Le
# basculement retire tout le vocabulaire d'hier des sorties : tags, domaines, dimensions,
# valeurs, situation d'une case, profil d'un personnage. Les tables restent jusqu'à la
# migration ; le décor les remplit donc en base, et ces tests vérifient qu'AUCUN de leurs
# termes ne sort, de quelque portée qu'il soit — la sentinelle d'à côté comme la globale
# et celle de la collection déposée. Ce que les relevés des grilles deviennent ici est la
# tranche 4.
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
    """Deux collections, un album chacune, et trois portées de vocabulaire d'hier.

    Les libellés sont volontairement improbables : une fuite se cherche par `in` sur le
    document entier, ce qui couvre du même coup les formes qu'on n'a pas énumérées (le
    classeur XLSX, une clé JSON ajoutée demain).

    Le vocabulaire est POSÉ, pas seulement catalogué — c'était le patron d'AUTH-11, « la
    portée se pose sur la LIAISON », et il reste le bon : la région d'Alpha porte trois
    tags et deux valeurs, des trois portées, et le personnage (entité de corpus) un profil
    de deux valeurs. Un export qui ne retirerait que les catalogues laisserait passer les
    liaisons.
    """
    alpha = _collection(client, "Corpus Alpha")
    bravo = _collection(client, "Corpus Bravo")
    a_alpha = _album(client, "ALBUM-ALPHA-9001", alpha["id"])
    _album(client, "ALBUM-BRAVO-9002", bravo["id"])
    pl = client.post(f"/api/albums/{a_alpha['id']}/import", headers=ADMIN,
                     files={"file": ("p.png", _png(), "image/png")}).json()
    reg = client.post(f"/api/planches/{pl['id']}/regions", headers=ADMIN,
                      json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}).json()

    # Le vocabulaire d'hier n'a plus de table (ANN-7, la v39) : ses libellés ne vivent plus
    # que dans le JOURNAL, où les actes qui le posaient restent (`conftest.poser_tags`). Ce
    # que ces tests mesurent désormais : aucun de ces libellés ne sort, d'où qu'il vienne.
    # Un personnage, entité de CORPUS : il porte une valeur de chaque côté.
    perso = client.post("/api/personnages", json={"nom": "Témoin"}, headers=ADMIN).json()
    # La région d'Alpha porte une note, trois tags et deux valeurs.
    r = client.put(f"/api/regions/{reg['id']}/annotation", headers=ADMIN,
                   json={"note": "note"})
    assert r.status_code == 200, r.text
    poser_tags(db_path, reg["id"], ["tag-global-9400", "tag-alpha-9401", "tag-bravo-9402"],
               agent="admin")
    return {"alpha": alpha, "bravo": bravo, "perso": perso, "region_id": reg["id"],
            # Depuis la v39, seuls les libellés des TAGS vivent encore quelque part : dans les
            # charges du journal. Les domaines, axes et valeurs n'ont plus de trace.
            "global": ["tag-global-9400"], "a": ["tag-alpha-9401"], "b": ["tag-bravo-9402"]}


def _tout_le_vocabulaire(v) -> list:
    return v["global"] + v["a"] + v["b"]


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
        tbls = json.dumps(mc.tables(conn, collection_id=collection_id),
                          ensure_ascii=False, default=str)
    finally:
        conn.close()
    route = client.get(f"/api/collections/{collection_id}/depot/metadonnees",
                       headers=ADMIN)
    assert route.status_code == 200, route.text
    desc = client.get(f"/api/collections/{collection_id}/depot/description",
                      headers=ADMIN)
    assert desc.status_code == 200, desc.text
    return {"records JSON": arbre, "tables CSV": tbls,
            "crosswalk de dépôt": _cw_texte(db_path, collection_id),
            "route /depot/metadonnees": route.content.decode("utf-8"),
            "route /depot/description": desc.content.decode("utf-8")}


def test_l_export_d_une_collection_ne_porte_plus_aucun_vocabulaire(client, db_path,
                                                                   vocabulaire_cloisonne):
    """ANN-7, le basculement — l'export de dépôt d'Alpha ne porte AUCUN terme d'hier : ni
    ceux de Bravo (ce que gardait AUTH-11), ni les globaux, ni les siens. Celui de Bravo
    non plus.

    Anti-vacuité : chaque sortie nomme sa collection ou son album — sans quoi un export
    vide serait propre —, et les records gardent la NOTE de la région, le seul reste de
    l'annotation d'hier qui sorte encore.
    """
    v = vocabulaire_cloisonne
    for cle, temoin in ((v["alpha"]["id"], "ALBUM-ALPHA-9001"),
                        (v["bravo"]["id"], "ALBUM-BRAVO-9002")):
        for quoi, texte in _textes_de_depot(client, db_path, cle).items():
            for mot in _tout_le_vocabulaire(v):
                assert mot not in texte, f"{quoi} ({cle}) : « {mot} » sort encore"
            nom = "Corpus Alpha" if cle == v["alpha"]["id"] else "Corpus Bravo"
            assert temoin in texte or nom in texte, (
                f"{quoi} ({cle}) : ni l'album ni la collection n'y sont — l'artefact est "
                "vide, le test ne mesure rien")
    import metadonnees_collection as mc
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        arbre = mc.collecter(conn, collection_id=v["alpha"]["id"])["metadonnees_collection"]
        tbls = mc.tables(conn, collection_id=v["alpha"]["id"])
    finally:
        conn.close()
    regions = [r for a in arbre["albums"] for p in a["planches"] for r in p["regions"]]
    assert [r["annotation"]["note"] for r in regions if r["id"] == v["region_id"]] == ["note"]
    # Les clés et les tables sont RETIRÉES, pas laissées vides (un catalogue vide se lirait
    # « aucun vocabulaire »).
    for cle in ("domaines", "vocabulaire", "tags"):
        assert cle not in arbre, f"la clé `{cle}` des records est encore là"
    assert "lexique" not in arbre["paradonnee"]
    assert all("attributs" not in p for p in arbre["personnages"])
    assert all("attributs" not in r for r in regions)
    assert all(set(r["annotation"]) == {"note", "date_creation", "date_modification"}
               for r in regions if "annotation" in r)
    for table in ("tags", "domaines", "vocabulaire", "region_attributs",
                  "personnage_attributs"):
        assert table not in tbls, f"la table `{table}` des CSV est encore là"
    assert tbls["annotations"][0] == ["region_id", "note", "date_creation",
                                      "date_modification"]


def test_sans_collection_les_outils_n_exportent_aucun_vocabulaire_non_plus(
        db_path, vocabulaire_cloisonne):
    """Le mode « corpus entier » des CLI : il décrivait TOUT le vocabulaire de l'instance
    (AUTH-11 : `--collection` est un restreigneur, sans lui pas de frontière). Le
    basculement le retire là aussi — ce mode est celui qui en sortait le plus."""
    import description_collection as dc
    import metadonnees_collection as mc
    v = vocabulaire_cloisonne
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        texte = json.dumps(mc.collecter(conn), ensure_ascii=False, default=str)
        texte += json.dumps(mc.tables(conn), ensure_ascii=False, default=str)
        fiche, agg = dc.collecter(conn)
        texte += json.dumps(fiche, ensure_ascii=False, default=str) + dc.catalogue_csv(agg)
    finally:
        conn.close()
    texte += _cw_texte(db_path, None)
    for mot in _tout_le_vocabulaire(v):
        assert mot not in texte, f"« {mot} » sort de l'export du corpus entier"
    assert "ALBUM-ALPHA-9001" in texte and "ALBUM-BRAVO-9002" in texte, (
        "le corpus entier ne nomme plus ses albums : le test ne mesure rien")


# --------------------------------------------------------------------------- #
# 2 ter. L'export d'un ALBUM (AUTH-11, puis ANN-7, le basculement)
# --------------------------------------------------------------------------- #
# Un album sort « au titre d'une collection » (DROIT-2). Depuis AUTH-11 (2026-10-07), ce
# titre gouvernait son vocabulaire : celui de la collection et le global, quel que soit qui
# exporte. Le basculement retire le vocabulaire : l'album ne porte plus que la NOTE de ses
# régions. Ce qui reste de ces tests : l'artefact ne varie pas selon qui clique, le titre
# ne se choisit pas librement (« aucun export sans titre », cadrage de la tranche 3), et une
# région qui ne portait que des tags ne se dit pas annotée.
#
# Ce que ces tests NE disent pas : qui a le droit d'exporter. C'est DROIT-2, inchangé, et
# `test_droit_export` le garde. Ici on ne regarde que ce que le fichier PORTE.
DES_DEUX = {"Remote-User": "proprio-des-deux"}      # possède Alpha ET Bravo
D_ALPHA = {"Remote-User": "proprio-d-alpha"}        # possède Alpha seule
LIT_LES_DEUX = {"Remote-User": "lit-les-deux"}      # lit les deux, n'exporte qu'Alpha
T_GLOBAL, T_ALPHA, T_BRAVO = "tag-global-9400", "tag-alpha-9401", "tag-bravo-9402"


def _album_d_alpha(db_path) -> int:
    return direct_query(db_path, "SELECT id FROM albums WHERE titre = 'ALBUM-ALPHA-9001'"
                        )[0]["id"]


@pytest.fixture
def album_partage(client, db_path, vocabulaire_cloisonne):
    """L'album d'Alpha et les comptes de la relecture du 2026-10-07.

    Sa région porte déjà une note et les trois tags (`vocabulaire_cloisonne`). S'y ajoute
    une BULLE qui ne porte, elle, qu'un tag et aucune note : la région dont il ne reste
    rien à montrer.
    """
    v = vocabulaire_cloisonne
    album_id = _album_d_alpha(db_path)
    planche_id = direct_query(db_path, "SELECT id FROM planches WHERE album_id = ?",
                              (album_id,))[0]["id"]
    r = client.post(f"/api/planches/{planche_id}/regions", headers=ADMIN,
                    json={"type": "bulle", "x": 1, "y": 1, "w": 3, "h": 3})
    assert r.status_code in (200, 201), r.text
    bulle_id = r.json()["id"]
    # Le tag de Bravo : l'acte d'hier qui le posait, au journal (ANN-7, la v39 a retiré la
    # ligne aux seuls tags avec la table) ; la bulle n'a plus d'annotation.
    poser_tags(db_path, bulle_id, [T_BRAVO], agent="admin")
    assert direct_query(db_path, "SELECT 1 FROM annotations WHERE region_id = ?",
                        (bulle_id,)) == []

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
    return {**v, "album_id": album_id, "bulle_id": bulle_id,
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
    dite annotée, sinon sa note. Lu dans la structure, pas cherché dans le texte — et la
    structure d'hier y est REFUSÉE : une clé `tags` en JSON, une colonne `tags` en CSV, un
    `@type` ou un `@ana` sur la `<note>` du TEI font échouer, vides ou non."""
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
        if ann is None:
            return None
        assert set(ann) == {"note"}, f"l'annotation JSON porte encore {sorted(ann)}"
        return ann["note"] or ""             # dite annotée sans note : "" et non None
    if fmt == "csv":
        import csv
        lecteur = csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
        assert "tags" not in lecteur.fieldnames, lecteur.fieldnames
        ligne = next(l for l in lecteur if int(l["region_id"]) == region_id)
        return ligne["note"] or None
    import xml.etree.ElementTree as ET
    tei = "{http://www.tei-c.org/ns/1.0}"
    zone = next(z for z in ET.fromstring(blob).iter(f"{tei}zone")
                if z.get("{http://www.w3.org/XML/1998/namespace}id") == f"zone_{region_id}")
    note = zone.find(f"{tei}note")
    if note is None:
        return None
    assert not note.attrib, f"la <note> TEI porte encore {note.attrib}"
    return note.text or ""                   # une <note/> vide : "" et non None


@pytest.mark.parametrize("nommee", [True, False], ids=["nommée", "par défaut"])
@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_l_album_au_titre_d_alpha_sort_identique_quel_que_soit_qui_exporte(
        client, album_partage, fmt, nommee):
    """Le MÊME artefact pour les comptes de la relecture — et il ne porte aucun tag, ni
    global, ni d'Alpha, ni de Bravo : la région garde sa note, et rien d'autre.

    `par défaut` : aucun `collection_id`. L'album ne vit que dans Alpha, donc chacun
    l'obtient au titre d'Alpha sans la nommer.
    """
    d = album_partage
    cid = d["alpha"]["id"] if nommee else None
    sortis = {nom: _export_album(client, fmt, d["album_id"], qui, cid)
              for nom, qui in d["comptes"].items()}
    for nom, blob in sortis.items():
        texte = blob.decode("utf-8")
        assert "ALBUM-ALPHA-9001" in texte, f"{fmt}, {nom} : l'album n'est pas dans l'export"
        for mot in _tout_le_vocabulaire(d):
            assert mot not in texte, f"{fmt}, {nom} : l'export d'album porte « {mot} »"
        assert _annotation_exportee(fmt, blob, d["region_id"]) == "note"
    reference = sortis["propriétaire d'Alpha seule"]
    for nom, blob in sortis.items():
        assert blob == reference, (
            f"{fmt} : l'artefact de « {nom} » diffère de celui de la propriétaire "
            "d'Alpha seule — il varie selon qui clique")
    if fmt == "json":
        assert json.loads(reference)["exporte_au_titre_de"]["id"] == d["alpha"]["id"]


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_au_titre_de_bravo_le_meme_album_ne_porte_aucun_tag_non_plus(client, db_path,
                                                                     album_partage, fmt):
    """La contre-épreuve d'AUTH-11 portait Bravo au titre de Bravo ; plus rien ne sort,
    sous aucun titre. Le droit, lui, n'a pas bougé : qui ne lit pas Bravo reçoit 404, qui
    la lit sans pouvoir l'exporter 403."""
    d = album_partage
    b = d["bravo"]["id"]
    _ranger_aussi_dans(db_path, d["album_id"], b)
    sortis = {nom: _export_album(client, fmt, d["album_id"], d["comptes"][nom], b)
              for nom in ("propriétaire d'Alpha et de Bravo", "administrateur")}
    for nom, blob in sortis.items():
        texte = blob.decode("utf-8")
        assert "ALBUM-ALPHA-9001" in texte, (fmt, nom)
        for mot in _tout_le_vocabulaire(d):
            assert mot not in texte, f"{fmt}, {nom} : au titre de Bravo, « {mot} » sort"
        assert _annotation_exportee(fmt, blob, d["region_id"]) == "note"
    assert len(set(sortis.values())) == 1, f"{fmt} : l'artefact varie selon qui clique"
    _export_album(client, fmt, d["album_id"], D_ALPHA, b, attendu=404)
    _export_album(client, fmt, d["album_id"], LIT_LES_DEUX, b, attendu=403)


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_une_region_qui_ne_portait_que_des_tags_ne_sort_pas_annotee(client, db_path,
                                                                    album_partage, fmt):
    """Une bulle sans note, qui ne porte qu'un tag : il n'en reste rien à montrer, et
    l'export ne la dit PAS annotée — ni `annotation` vide en JSON, ni `<note>` vide en
    TEI —, sous aucun titre. AUTH-11 la disait annotée au titre de la collection de son
    tag ; ce tag ne sort plus.

    La région elle-même sort toujours : c'est une DONNÉE de l'album.
    """
    d = album_partage
    _ranger_aussi_dans(db_path, d["album_id"], d["bravo"]["id"])
    for cid in (d["alpha"]["id"], d["bravo"]["id"]):
        blob = _export_album(client, fmt, d["album_id"], ADMIN, cid)
        assert _annotation_exportee(fmt, blob, d["bulle_id"]) is None, (
            f"{fmt}, au titre de {cid} : la bulle est dite annotée alors qu'il n'en sort "
            "rien")


def test_les_enregistrements_ne_disent_pas_annotee_une_region_aux_seuls_tags(
        db_path, album_partage):
    """La même règle dans les enregistrements de dépôt (`metadonnees_collection`) : la bulle
    qui ne porte qu'une ligne d'annotation aux seuls tags d'hier n'a pas d'`annotation` dans
    l'arbre, ni de ligne dans la table `annotations` — une note posée, sinon rien. La région
    à note, elle, y est."""
    import metadonnees_collection as mc
    d = album_partage
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        arbre = mc.collecter(conn, collection_id=d["alpha"]["id"])["metadonnees_collection"]
        tbls = mc.tables(conn, collection_id=d["alpha"]["id"])
    finally:
        conn.close()
    regions = {r["id"]: r for a in arbre["albums"] for p in a["planches"]
               for r in p["regions"]}
    assert d["bulle_id"] in regions and "annotation" not in regions[d["bulle_id"]]
    assert regions[d["region_id"]]["annotation"]["note"] == "note"
    assert [l[0] for l in tbls["annotations"][1]] == [d["region_id"]]


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_un_album_ne_sort_pas_au_titre_d_une_collection_ou_il_n_est_pas_range(
        client, album_partage, fmt):
    """Le titre ne se choisit pas librement.

    L'album n'est rangé que dans Alpha. Bravo est lue ET exportable pour le propriétaire
    des deux comme pour l'administrateur : rien, dans leurs droits, ne s'oppose à ce qu'ils
    la nomment. Si `_collection_d_export` cherchait la collection nommée parmi toutes les
    collections et non parmi celles de l'ALBUM, ils obtiendraient 200 — l'album d'Alpha,
    étiqueté Bravo (mutant de la relecture croisée du 2026-10-07, qui survivait ; le titre
    gouvernait alors aussi le vocabulaire, que le basculement d'ANN-7 a retiré). 404, comme
    pour une collection qui n'existe pas.
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
    """Le titre reste dit dans le NOM du fichier. Le CSV disait déjà `_c<N>` ; le TEI
    s'appelait `album_<id>_tei.xml` dans tous les cas. Un nom SANS `_c<N>` n'existe plus :
    depuis le 2026-10-07 aucun album ne sort sans titre (cf.
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


def test_les_trois_formats_retirent_les_tags_au_lieu_de_les_vider(client, album_partage):
    """Retirer n'est pas vider (cadrage de la tranche 3, « se tranchent en route » : la
    colonne `tags` du CSV est retirée et non laissée vide). Joué sur l'ARTEFACT, pour la
    région qui porte une note et des tags : en JSON, l'annotation n'a que `note` ; en CSV,
    l'en-tête n'a plus de colonne `tags` ; en TEI, aucune `<note>` ne porte `@type` ni
    `@ana`, et le document reste du XML bien formé."""
    import csv
    import xml.etree.ElementTree as ET
    d = album_partage
    blob = _export_album(client, "json", d["album_id"], ADMIN, d["alpha"]["id"])
    annotations = []

    def parcourir(noeuds):
        for n in noeuds:
            if n["annotation"] is not None:
                annotations.append(n["annotation"])
            parcourir(n["enfants"])
    for p in json.loads(blob)["planches"]:
        parcourir(p["regions"])
    assert annotations and all(set(a) == {"note"} for a in annotations), annotations
    blob = _export_album(client, "csv", d["album_id"], ADMIN, d["alpha"]["id"])
    entete = next(csv.reader(io.StringIO(blob.decode("utf-8-sig"))))
    assert entete[-1] == "note" and "tags" not in entete, entete
    blob = _export_album(client, "tei", d["album_id"], ADMIN, d["alpha"]["id"])
    notes = list(ET.fromstring(blob).iter("{http://www.tei-c.org/ns/1.0}note"))
    assert notes and all(not n.attrib for n in notes), [n.attrib for n in notes]


@pytest.mark.parametrize("fmt", ["json", "csv", "tei"])
def test_sans_titre_un_album_de_plusieurs_collections_ne_sort_plus(client, db_path,
                                                                   album_partage, fmt):
    """Plus AUCUN album ne sort sans titre — portée totale comprise (Hugo, 2026-10-07).

    RENVERSEMENT DATÉ. Ce test s'appelait
    `test_sans_titre_l_export_d_album_ne_borne_pas_son_vocabulaire` et fixait l'inverse :
    en portée totale (administrateur, mono-poste), un album rangé dans plusieurs
    collections et exporté sans en nommer aucune sortait en 200, `exporte_au_titre_de:
    null`, avec TOUT le vocabulaire posé sur ses régions — « il ne sort alors sous aucun
    droit particulier » (DROIT-2, 2026-09-11). Nouvel attendu : le **422 nommé** que
    recevaient déjà les autres comptes.

    La raison d'alors — depuis AUTH-11, le titre gouvernait le vocabulaire — attend la
    tranche 4 d'ANN-7, qui dira ce que les relevés emportent ; la règle reste (cadrage de
    la tranche 3, « se tranchent en route »).

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
    for cid in (a, b):
        texte = _export_album(client, fmt, d["album_id"], ADMIN, cid).decode("utf-8")
        assert "ALBUM-ALPHA-9001" in texte, (fmt, cid)


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


def test_les_exports_transversaux_ne_sortent_plus_aucun_tag(client, db_path, album_partage):
    """ANN-7, le basculement — la Recherche et l'Exploration ne lisent plus le vocabulaire
    d'hier : leurs exports ne portent aucun tag, pour personne, même filtrés sur un album
    dont les régions en portent encore. Ce test gardait, jusque-là, que leur vocabulaire
    suivait la portée d'export de la personne (`Portee.pour_export`, DROIT-2)."""
    d = album_partage
    rep = client.get("/api/recherche/export.csv", params={"album": d["album_id"]},
                     headers=ADMIN)
    assert rep.status_code == 200, rep.text[:300]
    assert "ALBUM-ALPHA-9001" in rep.text, "le décor ne sort plus : le test ne mesure rien"
    for qui in (DES_DEUX, D_ALPHA, LIT_LES_DEUX, ADMIN):
        texte = client.get("/api/recherche/export.csv", params={"album": d["album_id"]},
                           headers=qui).text
        assert T_ALPHA not in texte and T_BRAVO not in texte and T_GLOBAL not in texte, qui


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
