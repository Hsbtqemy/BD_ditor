"""COL-4 — le JEU des bacs à sable : sa préparation, et les refus qui protègent la référence.

Le jeu des tests est SYNTHÉTIQUE (des pages unies fabriquées par Pillow, dans le dossier du
test) : aucune image n'entre dans le dépôt pour lui. Il garde un document de chaque rôle,
et une part de chaque source — le dépôt et le serveur —, pour que l'export, qui se décide
document par document, ait les deux cas.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

import autorisation
import database
import main
from conftest import ADMIN, make_png

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import preparer_jeu  # noqa: E402

LEA = {"Remote-User": "lea"}


def _sql(db, q, p=()):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(q, p)]
    finally:
        c.close()


def ecrire_jeu(dossier: Path, documents, images=("p1.png",)) -> Path:
    """Une source de jeu : `jeu.json` et des pages unies (400 × 500)."""
    dossier.mkdir(parents=True, exist_ok=True)
    for i, nom in enumerate(images):
        (dossier / nom).write_bytes(make_png(400, 500, ("white", "ivory", "beige")[i % 3]))
    (dossier / "jeu.json").write_text(json.dumps({"documents": documents},
                                                 ensure_ascii=False), encoding="utf-8")
    return dossier


# Un document de chaque rôle dans la part du DÉPÔT, un document de stock dans celle du
# SERVEUR. Le parcours est vierge (cran `images`) ; l'exemple porte un découpage et du texte.
DOC_PARCOURS = {"cle": "parcours", "titre": "Le parcours", "role": "pas-a-pas", "rang": 1,
                "cran": "images",
                "planches": [{"fichier": "p1.png",
                              "regions": [{"type": "case", "x": 0, "y": 0, "w": 200, "h": 250,
                                           "enfants": [{"type": "bulle", "x": 10, "y": 10,
                                                        "w": 50, "h": 30,
                                                        "texte": "BONJOUR"}]}]}]}
DOC_EXEMPLE = {"cle": "exemple", "titre": "Un exemple", "auteur": "Anonyme",
               "role": "exemple", "cran": "transcription",
               "planches": [{"fichier": "p2.png",
                             "regions": [{"type": "case", "x": 0, "y": 0, "w": 300,
                                          "h": 300, "enfants": [
                                              {"type": "bulle", "x": 5, "y": 5, "w": 40,
                                               "h": 20, "texte": "LE OTAGE"}]}]}]}
DOC_STOCK_SERVEUR = {"cle": "stock-serveur", "titre": "Sous droits", "role": "stock",
                     "planches": [{"fichier": "s1.png"}]}


@pytest.fixture
def sources(tmp_path):
    depot = ecrire_jeu(tmp_path / "jeu-depot", [DOC_PARCOURS, DOC_EXEMPLE],
                       images=("p1.png", "p2.png"))
    serveur = ecrire_jeu(tmp_path / "jeu-serveur", [DOC_STOCK_SERVEUR], images=("s1.png",))
    return {"depot": depot, "serveur": serveur}


def preparer(depot=None, serveur=None, appliquer=True):
    conn = database.get_connection()
    try:
        return preparer_jeu.preparer(conn, depot=depot, serveur=serveur,
                                     appliquer_=appliquer, dire=lambda _l: None)
    finally:
        conn.close()


@pytest.fixture
def jeu(client, sources):
    bilan = preparer(**sources)
    assert len(bilan["crees"]) == 3, bilan
    return {**sources, "bilan": bilan}


def _jeu(db):
    return {r["cle"]: r for r in _sql(db, "SELECT * FROM jeu_document")}


# --------------------------------------------------------------------------- #
# La préparation
# --------------------------------------------------------------------------- #
def test_a_blanc_rien_n_est_ecrit(client, db_path, sources):
    bilan = preparer(**sources, appliquer=False)
    assert [d["cle"] for d in bilan["plan"]["creer"]] == ["parcours", "exemple",
                                                          "stock-serveur"]
    assert _sql(db_path, "SELECT * FROM jeu_document") == []
    assert _sql(db_path, "SELECT id FROM projet WHERE jeu = 1") == []


def test_le_jeu_se_prepare_dans_un_projet_cache(client, db_path, jeu):
    projets = _sql(db_path, "SELECT * FROM projet WHERE jeu = 1")
    assert len(projets) == 1 and projets[0]["bac_a_sable_de"] is None
    pid = projets[0]["id"]
    assert _sql(db_path, "SELECT * FROM projet_acces WHERE projet_id = ?", (pid,)) == []
    rows = _jeu(db_path)
    assert {c: (r["role"], r["cran"], r["part"], r["exportable"]) for c, r in rows.items()} \
        == {"parcours": ("pas-a-pas", "images", "depot", 1),
            "exemple": ("exemple", "transcription", "depot", 1),
            "stock-serveur": ("stock", "images", "serveur", 0)}
    # Chaque référence vit dans la collection du jeu, copie d'un document né dans le jeu.
    for r in rows.values():
        a = _sql(db_path, "SELECT * FROM albums WHERE id = ?", (r["album_reference"],))[0]
        assert a["document_id"] == r["document_id"] and a["projet_id"] == pid
        assert _sql(db_path, "SELECT projet_origine_id, importe_par FROM document "
                             "WHERE id = ?", (r["document_id"],)) == [
            {"projet_origine_id": pid, "importe_par": None}]
    # Le travail décrit est posé : régions, texte, statut ; aucun événement par région.
    ex = rows["exemple"]["album_reference"]
    regions = _sql(db_path, "SELECT r.type, r.ocr_texte, r.source FROM regions r "
                            "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ? "
                            "ORDER BY r.id", (ex,))
    assert regions == [{"type": "case", "ocr_texte": None, "source": "jeu"},
                       {"type": "bulle", "ocr_texte": "LE OTAGE", "source": "jeu"}]
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'regions'"
                ) == [{"n": 0}]
    assert _sql(db_path, "SELECT master_origine FROM planches WHERE album_id = ?", (ex,)) == [
        {"master_origine": "jeu:p2.png"}]


def test_le_jeu_n_apparait_dans_aucune_liste(client, db_path, jeu, derriere_proxy):
    """Pas même pour la portée totale, la seule qui le lise."""
    pid = _sql(db_path, "SELECT id FROM projet WHERE jeu = 1")[0]["id"]
    refs = {r["album_reference"] for r in _jeu(db_path).values()}
    assert pid not in {p["id"] for p in client.get("/api/projets", headers=ADMIN).json()}
    assert all(c["projet_id"] != pid
               for c in client.get("/api/collections", headers=ADMIN).json())
    assert not refs & {a["id"] for a in client.get("/api/albums", headers=ADMIN).json()}
    # … mais une portée totale l'atteint par son identifiant : c'est elle qui le tient.
    assert client.get(f"/api/projets/{pid}/membres", headers=ADMIN).status_code == 200


def test_rejoue_le_jeu_ne_change_rien(client, db_path, jeu):
    avant = _jeu(db_path)
    bilan = preparer(depot=jeu["depot"], serveur=jeu["serveur"])
    assert bilan["crees"] == [] and sorted(bilan["gardes"]) == sorted(avant)
    assert _jeu(db_path) == avant


def test_un_document_change_est_un_document_neuf(client, db_path, jeu):
    avant = _jeu(db_path)["exemple"]
    ecrire_jeu(jeu["depot"], [DOC_PARCOURS, {**DOC_EXEMPLE, "titre": "Un autre titre"}],
               images=("p1.png", "p2.png"))
    bilan = preparer(depot=jeu["depot"], serveur=jeu["serveur"])
    apres = _jeu(db_path)["exemple"]
    assert apres["document_id"] != avant["document_id"]
    assert bilan["retires"] == [avant["document_id"]]
    # Aucune copie ne la tenait : l'ancienne référence part, son document avec elle.
    assert bilan["purges"] == [avant["album_reference"]]
    assert _sql(db_path, "SELECT id FROM albums WHERE id = ?",
                (avant["album_reference"],)) == []
    assert _sql(db_path, "SELECT id FROM document WHERE id = ?",
                (avant["document_id"],)) == []


def test_une_image_changee_change_l_empreinte(client, db_path, jeu):
    avant = _jeu(db_path)["parcours"]["empreinte"]
    (jeu["depot"] / "p1.png").write_bytes(make_png(400, 500, "black"))
    preparer(depot=jeu["depot"], serveur=jeu["serveur"])
    assert _jeu(db_path)["parcours"]["empreinte"] != avant


def test_une_reference_tenue_par_une_copie_reste(client, db_path, jeu):
    """Retirée du jeu, une référence dont une copie vit encore (un bac à sable) n'est PAS
    détruite : elle partira avec la dernière copie."""
    ref = _jeu(db_path)["stock-serveur"]
    conn = database.get_connection()
    try:
        ailleurs = conn.execute("INSERT INTO collection (nom) VALUES ('Ailleurs')").lastrowid
        copie = database.creer_copie(conn, ref["document_id"], ailleurs, par=None,
                                     depuis=ref["album_reference"], cran="images")
        conn.commit()
    finally:
        conn.close()
    ecrire_jeu(jeu["serveur"], [], images=())
    bilan = preparer(depot=jeu["depot"], serveur=jeu["serveur"])
    assert bilan["retires"] == [ref["document_id"]] and bilan["purges"] == []
    assert _sql(db_path, "SELECT id FROM albums WHERE id = ?", (ref["album_reference"],))
    # La copie partie, la référence n'est plus tenue : la purge suivante la prend.
    conn = database.get_connection()
    try:
        conn.execute("DELETE FROM albums WHERE id = ?", (copie,))
        conn.commit()
        assert preparer_jeu.purger_les_references(conn) == [ref["album_reference"]]
    finally:
        conn.close()


def test_une_part_absente_est_ignoree(client, db_path, jeu):
    """Sans la source du serveur (la recette), ses documents restent au jeu."""
    bilan = preparer(depot=jeu["depot"], serveur=None)
    assert bilan["ignorees"] == ["serveur"] and bilan["retires"] == []
    assert "stock-serveur" in _jeu(db_path)


def test_la_part_du_serveur_ne_s_ouvre_pas_a_l_export(client, db_path, tmp_path):
    """La description ne peut pas ouvrir l'export d'un scan sous droits."""
    serveur = ecrire_jeu(tmp_path / "srv", [{**DOC_STOCK_SERVEUR, "exportable": True}],
                         images=("s1.png",))
    depot = ecrire_jeu(tmp_path / "dep", [{**DOC_PARCOURS, "exportable": False}],
                       images=("p1.png",))
    preparer(depot=depot, serveur=serveur)
    assert {c: r["exportable"] for c, r in _jeu(db_path).items()} == {
        "stock-serveur": 0, "parcours": 0}


@pytest.mark.parametrize("faute, mot", [
    ({"role": "parcours"}, "rôle inconnu"),
    ({"cran": "annotations"}, "hors du jeu"),
    ({"planches": [{"fichier": "absent.png"}]}, "introuvable"),
    ({"planches": [{"fichier": "../p1.png"}]}, "sans « .. »"),
    ({"titre": ""}, "titre"),
    ({"planches": [{"fichier": "p1.png", "regions": [{"type": "nuage", "x": 0, "y": 0,
                                                       "w": 1, "h": 1}]}]}, "type de région"),
])
def test_une_description_fautive_n_ecrit_rien(client, db_path, tmp_path, faute, mot):
    depot = ecrire_jeu(tmp_path / "dep", [{**DOC_PARCOURS, **faute}], images=("p1.png",))
    with pytest.raises(preparer_jeu.DescriptionInvalide, match=mot):
        preparer(depot=depot)
    assert _sql(db_path, "SELECT * FROM jeu_document") == []


def test_une_cle_decrite_deux_fois_est_refusee(client, db_path, tmp_path):
    depot = ecrire_jeu(tmp_path / "dep", [DOC_STOCK_SERVEUR], images=("s1.png",))
    serveur = ecrire_jeu(tmp_path / "srv", [DOC_STOCK_SERVEUR], images=("s1.png",))
    with pytest.raises(preparer_jeu.DescriptionInvalide, match="deux fois"):
        preparer(depot=depot, serveur=serveur)


def test_le_verrou_de_l_outil_empeche_deux_passages(client, data_dir, sources):
    (data_dir / preparer_jeu.NOM_DU_VERROU).write_text("pid 1", encoding="utf-8")
    with pytest.raises(preparer_jeu.PassageEnCours):
        preparer(**sources)


def test_la_ligne_de_commande(client, db_path, sources, capsys, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", db_path)
    assert preparer_jeu.main(["--depot", str(sources["depot"])]) == 0
    assert "À blanc" in capsys.readouterr().out
    assert _sql(db_path, "SELECT * FROM jeu_document") == []
    assert preparer_jeu.main(["--depot", str(sources["depot"]), "--serveur",
                              str(sources["serveur"]), "--appliquer"]) == 0
    assert len(_jeu(db_path)) == 3


def test_le_jeu_du_depot_est_vide_et_lisible():
    """`jeu/jeu.json` vit dans le dépôt, vide tant que les planches de la part du dépôt ne
    sont pas versées (Hugo, 2026-10-23 : la vérification de Forton d'abord)."""
    assert preparer_jeu.lire_description(preparer_jeu.DOSSIER_DEPOT, "depot") == []


# --------------------------------------------------------------------------- #
# Les refus qui protègent la référence — pour la portée totale aussi
# --------------------------------------------------------------------------- #
@pytest.fixture
def reference(client, db_path, jeu, derriere_proxy):
    r = _jeu(db_path)["exemple"]
    pid = _sql(db_path, "SELECT id FROM projet WHERE jeu = 1")[0]["id"]
    col = database.collection_de_base(sqlite3.connect(db_path), pid)
    planche = _sql(db_path, "SELECT id FROM planches WHERE album_id = ?",
                   (r["album_reference"],))[0]["id"]
    autre = client.post("/api/albums", json={"titre": "Ordinaire"}, headers=ADMIN).json()["id"]
    return {"album": r["album_reference"], "projet": pid, "collection": col,
            "planche": planche, "autre": autre}


def _refuse_jeu(r):
    assert r.status_code == 409 and "jeu des bacs à sable" in r.json()["detail"], r.text


def test_la_reference_ne_se_detruit_pas(client, reference):
    _refuse_jeu(client.delete(f"/api/albums/{reference['album']}", headers=ADMIN))
    _refuse_jeu(client.delete(f"/api/planches/{reference['planche']}", headers=ADMIN))


def test_on_ne_range_rien_dans_le_jeu(client, reference, png_bytes):
    _refuse_jeu(client.put(f"/api/albums/{reference['autre']}/collections/"
                           f"{reference['collection']}", headers=ADMIN))
    _refuse_jeu(client.post("/api/albums", headers=ADMIN,
                            json={"titre": "X", "collection_id": reference["collection"]}))
    _refuse_jeu(client.post(f"/api/albums/{reference['album']}/import", headers=ADMIN,
                            files={"file": ("p.png", png_bytes, "image/png")}))
    _refuse_jeu(client.delete(f"/api/albums/{reference['album']}/collections/"
                              f"{reference['collection']}", headers=ADMIN))
    _refuse_jeu(client.post("/api/collections", headers=ADMIN,
                            json={"nom": "Dans le jeu", "projet_id": reference["projet"]}))
    _refuse_jeu(client.post(f"/api/collections/{reference['collection']}/prendre",
                            headers=ADMIN, json={"documents": [
                                {"document_id": 1, "reponse": "zero"}]}))


def test_le_jeu_ne_se_regle_pas(client, reference):
    pid, col = reference["projet"], reference["collection"]
    _refuse_jeu(client.patch(f"/api/projets/{pid}", json={"nom": "Autre"}, headers=ADMIN))
    _refuse_jeu(client.delete(f"/api/projets/{pid}", headers=ADMIN))
    _refuse_jeu(client.put(f"/api/projets/{pid}/membres", headers=ADMIN,
                           json={"genre": "utilisateur", "principal": "lea",
                                 "role": "membre"}))
    _refuse_jeu(client.put(f"/api/projets/{pid}/acces-membres", headers=ADMIN,
                           json={"acces_membres": "ecriture"}))
    _refuse_jeu(client.put(f"/api/collections/{col}/acces", headers=ADMIN,
                           json={"genre": "utilisateur", "principal": "lea",
                                 "niveau": "lecture"}))
    _refuse_jeu(client.patch(f"/api/collections/{col}", json={"nom": "Autre"},
                             headers=ADMIN))


# Le cliquet de la référence : TOUTE route d'écriture qui nomme un album, une planche, une
# région ou une contribution — et les deux qui en nomment un dans leur corps — est jouée
# sur la référence, par une portée TOTALE, avec un corps valide. Elle doit répondre le 409
# du jeu, et la référence ne doit pas bouger d'un octet. Une route neuve absente de la
# table fait échouer le test : elle doit être déclarée, donc jouée (COL-4, relecture
# croisée : le texte, la notice, la validation, la relecture, l'annotation, une région,
# une contribution, l'ordre des planches passaient tous).
def _corps_des_ecritures(ref):
    a, pl, rg, ct = ref["album"], ref["planche"], ref["region"], ref["contribution"]
    v, p = ref["valeur"], ref["personnage"]
    return {
        ("PUT", "/api/regions/{region_id}/tokens/{ordre}"):
            (f"/api/regions/{rg}/tokens/0", {"lemme": "x"}),
        ("POST", "/api/regions/{region_id}/grammaire/valider"):
            (f"/api/regions/{rg}/grammaire/valider", None),
        ("DELETE", "/api/regions/{region_id}/tokens/{ordre}"):
            (f"/api/regions/{rg}/tokens/0", None),
        ("PUT", "/api/regions/{region_id}/locuteur"):
            (f"/api/regions/{rg}/locuteur", {"personnage_id": p}),
        ("DELETE", "/api/regions/{region_id}/locuteur"): (f"/api/regions/{rg}/locuteur", None),
        ("PUT", "/api/regions/{region_id}/personnage"):
            (f"/api/regions/{ref['case']}/personnage", {"personnage_id": p}),
        ("DELETE", "/api/regions/{region_id}/personnage"):
            (f"/api/regions/{ref['case']}/personnage", None),
        ("PUT", "/api/regions/{region_id}/attributs"):
            (f"/api/regions/{ref['case']}/attributs", {"valeur_id": v}),
        ("DELETE", "/api/regions/{region_id}/attributs/{valeur_id}"):
            (f"/api/regions/{ref['case']}/attributs/{v}", None),
        ("PUT", "/api/albums/{album_id}/collections/{collection_id}"):
            (f"/api/albums/{a}/collections/{ref['ailleurs']}", None),
        ("DELETE", "/api/albums/{album_id}/collections/{collection_id}"):
            (f"/api/albums/{a}/collections/{ref['collection']}", None),
        ("PUT", "/api/albums/{album_id}"): (f"/api/albums/{a}", {"titre": "Altéré"}),
        ("DELETE", "/api/albums/{album_id}"): (f"/api/albums/{a}", None),
        ("DELETE", "/api/planches/{planche_id}"): (f"/api/planches/{pl}", None),
        ("POST", "/api/albums/{album_id}/import"): (f"/api/albums/{a}/import", "fichier"),
        ("POST", "/api/planches/{planche_id}/segmenter"): (f"/api/planches/{pl}/segmenter", None),
        ("POST", "/api/planches/{planche_id}/detecter-bulles"):
            (f"/api/planches/{pl}/detecter-bulles", None),
        ("POST", "/api/planches/{planche_id}/ocr"): (f"/api/planches/{pl}/ocr", None),
        ("POST", "/api/planches/{planche_id}/regions"):
            (f"/api/planches/{pl}/regions", {"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}),
        ("PUT", "/api/regions/{region_id}"): (f"/api/regions/{rg}", {"ocr_texte": "ALTÉRÉ"}),
        ("DELETE", "/api/regions/{region_id}"): (f"/api/regions/{rg}", None),
        ("POST", "/api/planches/{planche_id}/reordonner"):
            (f"/api/planches/{pl}/reordonner", None),
        ("POST", "/api/regions/{region_id}/deplacer"):
            (f"/api/regions/{rg}/deplacer", {"sens": "haut"}),
        ("PATCH", "/api/planches/{planche_id}/statut"):
            (f"/api/planches/{pl}/statut", {"statut": "valide"}),
        ("PATCH", "/api/planches/{planche_id}/relecture"):
            (f"/api/planches/{pl}/relecture", {"relecture": "faite"}),
        ("PATCH", "/api/planches/{planche_id}/validation"):
            (f"/api/planches/{pl}/validation", {"validee": True}),
        ("PATCH", "/api/planches/{planche_id}/verrou"):
            (f"/api/planches/{pl}/verrou", {"verrouillee": True}),
        ("PATCH", "/api/planches/{planche_id}/role"):
            (f"/api/planches/{pl}/role", {"role": "couverture"}),
        ("PUT", "/api/regions/{region_id}/annotation"):
            (f"/api/regions/{rg}/annotation", {"note": "ajout", "tags": ["altere"]}),
        ("POST", "/api/albums/{album_id}/contributions"):
            (f"/api/albums/{a}/contributions", {"nom": "Intrus", "role": "scenario"}),
        ("POST", "/api/albums/{album_id}/valider"): (f"/api/albums/{a}/valider", {"validee": True}),
        ("PUT", "/api/albums/{album_id}/ordre-des-planches"):
            (f"/api/albums/{a}/ordre-des-planches", {"ordre": [pl], "vu": [pl]}),
        ("DELETE", "/api/contributions/{contribution_id}"): (f"/api/contributions/{ct}", None),
    }


_CLES_D_OBJET = ("{album_id}", "{planche_id}", "{region_id}", "{contribution_id}")


def _empreinte(db, album):
    """Tout ce que porte la référence, en clair : la moindre écriture la change."""
    c = sqlite3.connect(db)
    try:
        lignes = []
        for q in ("SELECT * FROM albums WHERE id = ?",
                  "SELECT * FROM planches WHERE album_id = ? ORDER BY id",
                  "SELECT r.* FROM regions r JOIN planches p ON p.id = r.planche_id "
                  "WHERE p.album_id = ? ORDER BY r.id",
                  "SELECT an.*, at.tag_id FROM annotations an JOIN regions r ON r.id = "
                  "an.region_id JOIN planches p ON p.id = r.planche_id LEFT JOIN "
                  "annotation_tags at ON at.annotation_id = an.id WHERE p.album_id = ?",
                  "SELECT * FROM contribution WHERE album_id = ? ORDER BY id",
                  "SELECT tc.* FROM token_correction tc JOIN regions r ON r.id = tc.region_id "
                  "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?",
                  "SELECT x.* FROM region_attribut x JOIN regions r ON r.id = x.region_id "
                  "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?",
                  "SELECT x.* FROM bulle_locuteur x JOIN regions r ON r.id = x.region_id "
                  "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?",
                  "SELECT x.* FROM personnage_presence x JOIN regions r ON r.id = x.region_id "
                  "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?",
                  "SELECT * FROM collection_album WHERE album_id = ? ORDER BY collection_id"):
            lignes.append(c.execute(q, (album,)).fetchall())
        return lignes
    finally:
        c.close()


@pytest.fixture
def reference_complete(client, db_path, reference, png_bytes):
    """La référence de l'exemple, avec une case, une contribution, une valeur d'attribut et
    un personnage à attribuer."""
    regions = _sql(db_path, "SELECT id, type FROM regions WHERE planche_id = ? ORDER BY id",
                   (reference["planche"],))
    case = next(r["id"] for r in regions if r["type"] == "case")
    bulle = next(r["id"] for r in regions if r["type"] == "bulle")
    c = sqlite3.connect(db_path)
    try:
        ct = c.execute("INSERT INTO contribution (album_id, nom, rang) VALUES (?, 'X', 0)",
                       (reference["album"],)).lastrowid
        c.commit()
    finally:
        c.close()
    d = client.post("/api/attributs/dimensions", headers=ADMIN,
                    json={"cible": "case", "nom": "cadrage"}).json()["id"]
    v = client.post(f"/api/attributs/dimensions/{d}/valeurs", headers=ADMIN,
                    json={"valeur": "gros plan"}).json()["id"]
    p = client.post("/api/personnages", headers=ADMIN, json={"nom": "Spirou"}).json()["id"]
    ailleurs = client.post("/api/collections", headers=ADMIN, json={"nom": "Ailleurs"}).json()
    return {**reference, "region": bulle, "case": case, "contribution": ct, "valeur": v,
            "personnage": p, "ailleurs": ailleurs["id"]}


def test_aucune_ecriture_ne_touche_la_reference(client, db_path, reference_complete,
                                                png_bytes):
    import inventaire_routes
    ref = reference_complete
    table = _corps_des_ecritures(ref)
    ecritures = set()
    for route in inventaire_routes.routes_api():
        for m in (getattr(route, "methods", None) or set()) & {"POST", "PUT", "PATCH",
                                                                "DELETE"}:
            if any(k in route.path for k in _CLES_D_OBJET):
                ecritures.add((m, route.path))
    assert ecritures - set(table) == set(), "route d'écriture neuve, à déclarer ici"
    assert len(ecritures) >= 30
    # Les deux qui nomment l'album dans leur CORPS.
    jouees = [(m, chemin, corps) for (m, _p), (chemin, corps) in sorted(table.items())]
    jouees += [("POST", "/api/sharedocs/importer",
                {"album_id": ref["album"], "chemins": ["x/p.png"]}),
               ("POST", "/api/jobs", {"passes": ["segmenter"], "album_ids": [ref["album"]]})]
    avant = _empreinte(db_path, ref["album"])
    for m, chemin, corps in jouees:
        if corps == "fichier":
            r = client.post(chemin, headers=ADMIN,
                            files={"file": ("p.png", png_bytes, "image/png")})
        else:
            r = client.request(m, chemin, headers=ADMIN,
                               **({"json": corps} if corps is not None else {}))
        if chemin == "/api/jobs":
            # Un lot filtre au lieu de refuser (AUTH-2) : aucune planche à traiter — ou le
            # moteur absent avant tout. Jamais une planche de la référence.
            assert r.status_code in (422, 503), (chemin, r.status_code, r.text)
        else:
            assert r.status_code == 409 and "jeu des bacs à sable" in r.json()["detail"], \
                (m, chemin, r.status_code, r.text)
        assert _empreinte(db_path, ref["album"]) == avant, (m, chemin)


@pytest.fixture
def reference_serveur(client, db_path, jeu, derriere_proxy):
    """La référence de la part du SERVEUR, avec une bulle « SENTINELLE » et son mot, pour que
    les portes qui traversent le corpus aient de quoi la laisser sortir."""
    r = _jeu(db_path)["stock-serveur"]
    planche = _sql(db_path, "SELECT id FROM planches WHERE album_id = ?",
                   (r["album_reference"],))[0]["id"]
    c = sqlite3.connect(db_path)
    try:
        rid = c.execute("INSERT INTO regions (planche_id, type, x, y, w, h, ocr_texte) VALUES "
                        "(?, 'bulle', 1, 1, 9, 9, 'SENTINELLE')", (planche,)).lastrowid
        c.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                  "VALUES (?, 0, 'SENTINELLE', 'sentinelle', 'NOUN', '')", (rid,))
        c.commit()
    finally:
        c.close()
    conn = database.get_connection()
    try:
        database.reindex_region(conn, rid)
        conn.commit()
        pid = database.projet_de_jeu(conn)
        col = database.collection_de_base(conn, pid)
    finally:
        conn.close()
    return {"album": r["album_reference"], "region": rid, "collection": col}


def test_la_part_du_serveur_ne_sort_par_aucune_porte(client, reference_serveur):
    """Chaque porte de sortie déclarée par le cliquet de DROIT-2 (`test_droit_export.PORTES`),
    jouée par la portée TOTALE — la seule qui lise la référence : rien de la part du
    serveur ne sort. Les portes d'un album, d'une collection ou d'une figure refusent ; celles
    qui traversent le corpus ne portent pas sa bulle (relecture croisée : l'export JSON, CSV
    et TEI de la référence passait)."""
    from test_droit_export import PORTES
    ref = reference_serveur
    requetes = {
        "/api/export/json": {"album_id": ref["album"]},
        "/api/export/csv": {"album_id": ref["album"]},
        "/api/export/tei": {"album_id": ref["album"]},
        "/api/recherche/export.csv": {"q": "sentinelle"},
        "/api/analyse/frequences.csv": {"champ": "lemme"},
        "/api/analyse/concordance.csv": {"lemme": "sentinelle"},
        "/api/analyse/comparaison.csv": {"a_album": ref["album"], "b_album": ref["album"]},
        "/api/analyse/croisement.csv": {"axe_x": "pos", "axe_y": "type"},
        "/api/analyse/accord.csv": {}, "/api/analyse/accord-inter.csv": {},
    }
    refusent = {"/api/export/json", "/api/export/csv", "/api/export/tei", "/api/figures"}
    for methode, chemin in sorted(PORTES):
        url = chemin.replace("{collection_id}", str(ref["collection"]))
        corps = {"/api/figures": {"regions": [ref["region"]]},
                 "/api/collections/{collection_id}/depot/deposer":
                     {"quoi": "description", "format": "json"}}.get(chemin)
        r = client.request(methode, url, params=requetes.get(chemin, {}), json=corps,
                           headers=ADMIN)
        if chemin in refusent:
            assert r.status_code == 403 and "sort" in r.json()["detail"], (chemin, r.text)
        elif "/depot/" in chemin:
            _refuse_jeu(r)
        else:
            assert r.status_code >= 400 or "sentinelle" not in r.text.lower(), \
                (chemin, r.status_code, r.text[:300])


def test_un_compte_ordinaire_ne_voit_pas_le_jeu(client, reference):
    """Personne n'en est membre : 404, comme un objet qui n'existe pas."""
    assert client.get(f"/api/albums/{reference['album']}/planches",
                      headers=LEA).status_code == 404
    assert client.get(f"/api/projets/{reference['projet']}/membres",
                      headers=LEA).status_code == 404


@pytest.mark.parametrize("nom", ["Bac à sable", "bac à  SABLE de Léa", "Mon bac à sable",
                                 "Jeu des bacs à sable"])
def test_les_noms_des_natures_sont_reserves(client, nom):
    r = client.post("/api/projets", json={"nom": nom})
    assert r.status_code == 409 and "réservé" in r.json()["detail"], r.text


def test_un_nom_ordinaire_reste_unique(client):
    assert client.post("/api/projets", json={"nom": "Étude"}).status_code == 201
    assert client.post("/api/projets", json={"nom": "étude"}).status_code == 409


def test_les_corrections_du_jeu_s_ancrent_sur_les_mots(client, db_path, tmp_path):
    """Posées avant l'index, elles ne s'aligneraient sur aucun mot et partiraient
    orphelines (`obsolete`) : l'accord et la règle de suppression les liraient de travers."""
    doc = {"cle": "g", "titre": "G", "role": "exemple", "cran": "grammaire",
           "planches": [{"fichier": "p1.png", "regions": [
               {"type": "bulle", "x": 1, "y": 1, "w": 50, "h": 20, "texte": "OTAGE",
                "corrections": [{"ordre": 0, "forme": "otage", "lemme": "otage",
                                 "pos": "NOUN"}]}]}]}
    preparer(depot=ecrire_jeu(tmp_path / "g", [doc]))
    if not _sql(db_path, "SELECT 1 FROM tokens"):
        pytest.skip("sans moteur de langue, aucun mot n'est découpé")
    assert _sql(db_path, "SELECT ordre, obsolete FROM token_correction") == [
        {"ordre": 0, "obsolete": 0}]
