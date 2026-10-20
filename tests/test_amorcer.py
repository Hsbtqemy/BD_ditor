"""COL-3, tranche 3b — EN PARTIR : une copie amorcée avec le travail d'une autre, jusqu'à un
cran (`database.creer_copie` → `copier_le_travail`), et ce que la règle de suppression en
lit (`autorisation._sources_du_travail`, sixième source).

Les décisions qu'on éprouve (`docs/col3-tranche3b-cadrage.md`, Hugo, 2026-10-20) :

- E1 — l'échelle : à chaque cran ce qui doit suivre suit, et RIEN d'au-dessus ; la
  validation ne suit jamais ;
- E2/E3 — chaque région copiée dit sa source (`region_origine`), et AUCUN événement n'est
  recopié : le travail copié reste celui de ses auteurs par la chaîne, bornée dans le temps
  (ce qui est fait sur la source après la copie n'est pas dans la copie) et par le cran (une
  note qui n'a pas suivi ne compte pas) ;
- E5 — seul le vocabulaire visible depuis la collection d'arrivée suit, et le reste est
  compté dans la charge de la naissance ;
- E6 — les personnages suivent.

`creer_copie` est jouée en direct, sous une connexion ; la route de la prise viendra avec
son commit. La règle est lue par `destructible` de `GET /api/albums`, sous l'identité de qui
a créé la copie.
"""
import json

import pytest

import database
from conftest import ADMIN
from test_fonds import _accorder, _album, _collection, _planche
from test_projets import _sql

LEA = {"Remote-User": "lea"}
SAM = {"Remote-User": "sam"}


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


@pytest.fixture
def source(client, derriere_proxy, data_dir, db_path):
    """« Le Lotus bleu », importé et entièrement travaillé par `lea` dans Principale : une
    planche, une case et sa bulle, le texte, une note et deux tags (un global, un LOCAL à
    Principale), un attribut de case global et un local, un locuteur, une présence, une
    correction grammaticale, la planche validée. Étude est une seconde collection du même
    projet, où `lea` et `sam` écrivent."""
    principale = _collection(client, "Principale")
    etude = _collection(client, "Étude")
    for cid in (principale, etude):
        _accorder(client, cid, "lea", "ecriture")
        _accorder(client, cid, "sam", "ecriture")
    a = _album(client, "Le Lotus bleu", principale, LEA)
    pl = _planche(client, a, LEA)
    case = _ok(client.post(f"/api/planches/{pl}/regions", headers=LEA,
                           json={"type": "case", "x": 0, "y": 0, "w": 300, "h": 200}), 201)["id"]
    bulle = _ok(client.post(f"/api/planches/{pl}/regions", headers=LEA,
                            json={"type": "bulle", "x": 10, "y": 10, "w": 90, "h": 90,
                                  "parent_id": case}), 201)["id"]
    _ok(client.put(f"/api/regions/{bulle}", headers=LEA,
                   json={"ocr_texte": "TINTIN ET LES OTAGES"}))
    _ok(client.put(f"/api/regions/{bulle}/annotation", headers=LEA,
                   json={"note": "ironie", "tags": ["dialogue", "secret"]}))
    _sql(db_path, "UPDATE tags SET collection_id = ? WHERE label = 'secret'", (principale,))
    perso = _ok(client.post("/api/personnages", headers=LEA, json={"nom": "Tintin"}), 201)["id"]
    _ok(client.put(f"/api/regions/{bulle}/locuteur", headers=LEA,
                   json={"personnage_id": perso}))
    _ok(client.put(f"/api/regions/{case}/personnage", headers=LEA,
                   json={"personnage_id": perso}))
    dim = _ok(client.post("/api/attributs/dimensions", headers=LEA,
                          json={"cible": "case", "nom": "cadrage"}), 201)["id"]
    globale = _ok(client.post(f"/api/attributs/dimensions/{dim}/valeurs", headers=LEA,
                              json={"valeur": "gros plan"}), 201)["id"]
    dim_locale = _ok(client.post("/api/attributs/dimensions", headers=LEA,
                                 json={"cible": "case", "nom": "grille privée"}), 201)["id"]
    locale = _ok(client.post(f"/api/attributs/dimensions/{dim_locale}/valeurs", headers=LEA,
                             json={"valeur": "à part"}), 201)["id"]
    for v in (globale, locale):
        _ok(client.put(f"/api/regions/{case}/attributs", headers=LEA, json={"valeur_id": v}))
    _sql(db_path, "UPDATE attribut_dimension SET collection_id = ? WHERE id = ?",
         (principale, dim_locale))
    _sql(db_path, "UPDATE attribut_valeur SET collection_id = ? WHERE id = ?",
         (principale, locale))
    # Une correction grammaticale, posée en base : sans spaCy, aucun token n'existe sur
    # lequel la route l'accepterait. Ce que la copie doit en faire ne dépend pas du moteur.
    # Les tokens que l'écriture du texte a produits sont retirés d'abord : AVEC spaCy, la
    # route en pose un par mot, et la source en portait cinq au lieu d'un — ATTENDU, mesuré
    # dans un environnement sans spaCy, échouait dans le .venv et dans l'image.
    _sql(db_path, "DELETE FROM tokens WHERE region_id = ?", (bulle,))
    _sql(db_path, "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                  "VALUES (?, 0, 'TINTIN', 'tintin', 'PROPN', '')", (bulle,))
    _sql(db_path, "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, etat, "
                  "auteur) VALUES (?, 0, 'TINTIN', 'Tintin', 'PROPN', 'corrige', 'lea')",
         (bulle,))
    _ok(client.patch(f"/api/planches/{pl}/validation", headers=LEA, json={"validee": True}))
    _sql(db_path, "UPDATE planches SET relecture = 'faite', statut = 'segmentee', "
                  "verrouillee = '2026-01-01', verrou_par = 'lea' WHERE id = ?", (pl,))
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (a,))[0]["document_id"]
    return {"a": a, "doc": doc, "pl": pl, "case": case, "bulle": bulle, "perso": perso,
            "principale": principale, "etude": etude, "globale": globale, "locale": locale}


def _copier(s, cran, *, par="lea", collection=None, depuis=None):
    conn = database.get_connection()
    try:
        b = database.creer_copie(conn, s["doc"], collection or s["etude"], par=par,
                                 depuis=depuis or s["a"], cran=cran)
        conn.commit()
        return b
    finally:
        conn.close()


def _travail(db_path, album_id):
    """Ce que porte une copie, table par table."""
    def n(sql):
        return _sql(db_path, sql, (album_id,))[0]["n"]
    regions = "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id " \
              "WHERE p.album_id = ?"
    return {
        "regions": n(f"SELECT COUNT(*) AS n FROM ({regions})"),
        "textes": n(f"SELECT COUNT(*) AS n FROM regions WHERE id IN ({regions}) "
                    "AND ocr_texte IS NOT NULL"),
        "tokens": n(f"SELECT COUNT(*) AS n FROM tokens WHERE region_id IN ({regions})"),
        "corrections": n("SELECT COUNT(*) AS n FROM token_correction "
                         f"WHERE region_id IN ({regions})"),
        "annotations": n(f"SELECT COUNT(*) AS n FROM annotations WHERE region_id IN ({regions})"),
        "attributs": n(f"SELECT COUNT(*) AS n FROM region_attribut WHERE region_id IN ({regions})"),
        "locuteurs": n(f"SELECT COUNT(*) AS n FROM bulle_locuteur WHERE region_id IN ({regions})"),
        "presences": n("SELECT COUNT(*) AS n FROM personnage_presence "
                       f"WHERE region_id IN ({regions})"),
    }


ATTENDU = {
    "decoupage": {"regions": 2},
    "transcription": {"regions": 2, "textes": 1, "tokens": 1},
    "grammaire": {"regions": 2, "textes": 1, "tokens": 1, "corrections": 1},
    "annotations": {"regions": 2, "textes": 1, "tokens": 1, "corrections": 1,
                    "annotations": 1, "attributs": 1, "locuteurs": 1, "presences": 1},
}


@pytest.mark.parametrize("cran", sorted(ATTENDU))
def test_a_chaque_cran_ce_qui_doit_suivre_suit_et_rien_au_dessus(db_path, source, cran):
    b = _copier(source, cran)
    zero = dict.fromkeys(_travail(db_path, source["a"]), 0)
    assert _travail(db_path, b) == {**zero, **ATTENDU[cran]}
    # La source n'a rien perdu.
    assert _travail(db_path, source["a"]) == {**ATTENDU["annotations"], "attributs": 2}


def test_la_copie_vierge_n_a_toujours_aucune_region(db_path, source):
    b = _copier(source, database.CRAN_IMAGES)
    assert _travail(db_path, b)["regions"] == 0
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM region_origine")[0]["n"] == 0


@pytest.mark.parametrize("cran", database.CRANS)
def test_la_validation_ne_suit_jamais(db_path, source, cran):
    b = _copier(source, cran)
    pl = _sql(db_path, "SELECT * FROM planches WHERE album_id = ?", (b,))[0]
    assert (pl["validee"], pl["verrouillee"], pl["verrou_par"]) == (None, None, None)
    rang = database.rang_du_cran(cran)
    assert pl["statut"] == ("segmentee" if rang >= 1 else "importee")
    assert pl["relecture"] == ("faite" if rang >= database.rang_du_cran("grammaire") else None)


def test_chaque_region_dit_sa_source_et_garde_sa_forme(db_path, source):
    b = _copier(source, "annotations")
    lignes = _sql(db_path, "SELECT r.*, o.region_source_id FROM regions r "
                           "JOIN planches p ON p.id = r.planche_id "
                           "JOIN region_origine o ON o.region_id = r.id "
                           "WHERE p.album_id = ? ORDER BY r.id", (b,))
    assert {r["region_source_id"] for r in lignes} == {source["case"], source["bulle"]}
    case = next(r for r in lignes if r["region_source_id"] == source["case"])
    bulle = next(r for r in lignes if r["region_source_id"] == source["bulle"])
    assert bulle["parent_id"] == case["id"] and case["parent_id"] is None
    src = _sql(db_path, "SELECT * FROM regions WHERE id = ?", (source["bulle"],))[0]
    for col in ("type", "x", "y", "w", "h", "ordre", "ocr_texte", "source", "touche",
                "date_creation", "activite_id"):
        assert bulle[col] == src[col], col
    assert bulle["id"] not in (source["case"], source["bulle"])


def test_sous_la_transcription_la_region_n_a_que_sa_geometrie(db_path, source):
    b = _copier(source, "decoupage")
    bulle = _sql(db_path, "SELECT r.* FROM regions r JOIN region_origine o "
                          "ON o.region_id = r.id WHERE o.region_source_id = ? "
                          "AND r.planche_id IN (SELECT id FROM planches WHERE album_id = ?)",
                 (source["bulle"], b))[0]
    assert (bulle["ocr_texte"], bulle["touche"]) == (None, 0)


def test_le_vocabulaire_qui_ne_se_voit_pas_depuis_l_arrivee_reste_et_se_compte(db_path, source):
    """E5 — Étude ne voit pas « secret » ni la grille privée de Principale : ils restent sur
    la source ; le tag global et l'attribut global suivent. La charge de la naissance dit
    ce qui est laissé."""
    b = _copier(source, "annotations")
    tags = _sql(db_path, "SELECT t.label FROM annotation_tags at JOIN tags t ON t.id = at.tag_id "
                         "JOIN annotations an ON an.id = at.annotation_id "
                         "JOIN regions r ON r.id = an.region_id "
                         "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?", (b,))
    assert [t["label"] for t in tags] == ["dialogue"]
    valeurs = _sql(db_path, "SELECT ra.valeur_id FROM region_attribut ra "
                            "JOIN regions r ON r.id = ra.region_id "
                            "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?", (b,))
    assert [v["valeur_id"] for v in valeurs] == [source["globale"]]
    charge = json.loads(_sql(
        db_path, "SELECT apres FROM evenement WHERE cible_table = 'document' AND cible_id = ? "
                 "AND json_extract(apres, '$.album_id') = ?", (source["doc"], b))[0]["apres"])
    assert charge["copie"]["laisses"] == {"tags": 1, "attributs": 1}
    assert charge["copie"]["copies"]["tags"] == 1 and charge["copie"]["cran"] == "annotations"


def test_dans_la_collection_qui_le_voit_le_vocabulaire_local_suit(db_path, source):
    """La même règle, de l'autre côté : une copie rangée dans Principale emporte ce que
    Principale voit."""
    b = _copier(source, "annotations", collection=source["principale"])
    assert _travail(db_path, b)["attributs"] == 2
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM annotation_tags at "
                         "JOIN annotations an ON an.id = at.annotation_id "
                         "JOIN regions r ON r.id = an.region_id "
                         "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?",
                (b,))[0]["n"] == 2


def test_une_annotation_sans_note_dont_tous_les_tags_restent_ne_nait_pas(db_path, source):
    _sql(db_path, "UPDATE annotations SET note = NULL")
    _sql(db_path, "UPDATE tags SET collection_id = ?", (source["principale"],))
    b = _copier(source, "annotations")
    assert _travail(db_path, b)["annotations"] == 0


def test_les_personnages_suivent(client, db_path, source):
    """E6 — le personnage est le travail. Visible depuis la copie seule : `sam`, qui
    n'écrirait que dans Étude, lirait Tintin par la copie."""
    b = _copier(source, "annotations")
    assert _sql(db_path, "SELECT personnage_id FROM bulle_locuteur bl "
                         "JOIN regions r ON r.id = bl.region_id "
                         "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?",
                (b,)) == [{"personnage_id": source["perso"]}]


def test_l_index_suit_sans_rien_perdre(client, db_path, source):
    """La copie se trouve comme sa source ; ses tags dans l'index sont les SIENS."""
    b = _copier(source, "annotations")
    ligne = _sql(db_path, "SELECT rc.* FROM recherche rc JOIN regions r ON r.id = rc.region_id "
                          "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?", (b,))
    assert len(ligne) == 1
    assert ligne[0]["ocr_texte"] == "TINTIN ET LES OTAGES" and ligne[0]["note"] == "ironie"
    assert ligne[0]["tags_concat"] == "dialogue"


def test_sous_les_annotations_la_note_ne_passe_pas_dans_l_index(client, db_path, source):
    b = _copier(source, "transcription")
    ligne = _sql(db_path, "SELECT rc.* FROM recherche rc JOIN regions r ON r.id = rc.region_id "
                          "JOIN planches p ON p.id = r.planche_id WHERE p.album_id = ?", (b,))
    assert len(ligne) == 1 and ligne[0]["note"] == "" and ligne[0]["tags_concat"] == ""
    assert "ironie" not in (ligne[0]["lemmes"] or "")


# --------------------------------------------------------------------------- #
# E3 — aucun événement recopié ; le travail reste celui de ses auteurs
# --------------------------------------------------------------------------- #
def test_aucun_evenement_ne_nomme_une_region_copiee(client, db_path, source):
    avant = _sql(db_path, "SELECT COUNT(*) AS n FROM evenement")[0]["n"]
    prochain = client.get("/api/undo/prochain", headers=LEA)
    b = _copier(source, "annotations")
    neuves = [r["id"] for r in _sql(db_path, "SELECT r.id FROM regions r JOIN planches p "
                                             "ON p.id = r.planche_id WHERE p.album_id = ?", (b,))]
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM evenement "
                         f"WHERE cible_id IN ({','.join('?' * len(neuves))}) "
                         "AND cible_table IN ('regions', 'annotations', 'bulle_locuteur', "
                         "'personnage_presence', 'region_attribut')", neuves)[0]["n"] == 0
    # Deux actes seulement : la naissance sous le document, et l'emploi.
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM evenement")[0]["n"] == avant + 2
    apres = client.get("/api/undo/prochain", headers=LEA)
    assert (apres.status_code, apres.json()) == (prochain.status_code, prochain.json())


def _destructible(client, album_id, qui):
    return {a["id"]: a for a in client.get("/api/albums", headers=qui).json()}[album_id][
        "destructible"]


def test_le_copieur_ne_supprime_pas_seul_le_travail_d_autrui(client, db_path, source):
    b = _copier(source, "annotations", par="sam")
    assert _destructible(client, b, SAM) is False


def test_qui_copie_son_propre_travail_supprime_seul(client, db_path, source):
    """La source 2 suit la chaîne : l'attribut de case recopié a son `lien` sous la région
    SOURCE, posé par `lea` ; sans la chaîne, il compterait comme le travail d'un inconnu."""
    b = _copier(source, "annotations")
    assert _destructible(client, b, LEA) is True


def test_le_travail_fait_sur_la_source_apres_la_copie_ne_compte_pas(client, db_path, source):
    b = _copier(source, "annotations")
    _sql(db_path, "UPDATE copie SET creee_le = datetime('now', '-1 hour') WHERE album_id = ?",
         (b,))
    _ok(client.put(f"/api/regions/{source['bulle']}/annotation", headers=SAM,
                   json={"note": "après la copie", "tags": ["dialogue"]}))
    assert _destructible(client, b, LEA) is True
    assert _destructible(client, source["a"], LEA) is False


def test_une_note_qui_n_a_pas_suivi_ne_compte_pas(client, db_path, source):
    """`sam` a annoté la source ; `lea` en prend le découpage, qu'elle a fait seule."""
    _ok(client.put(f"/api/regions/{source['bulle']}/annotation", headers=SAM,
                   json={"note": "de sam", "tags": ["dialogue"]}))
    b = _copier(source, "decoupage")
    assert _destructible(client, b, LEA) is True
    c = _copier(source, "annotations")
    assert _destructible(client, c, LEA) is False


def test_le_travail_d_une_copie_intermediaire_compte(client, db_path, source):
    """Copie de copie : `sam` travaille sur la copie intermédiaire AVANT qu'on en tire la
    suivante ; son travail est dans la dernière."""
    b = _copier(source, "annotations")
    bulle_b = _sql(db_path, "SELECT region_id FROM region_origine WHERE region_source_id = ?",
                   (source["bulle"],))[0]["region_id"]
    _ok(client.put(f"/api/regions/{bulle_b}", headers=SAM, json={"ocr_texte": "RETOUCHÉ"}))
    _sql(db_path, "UPDATE evenement SET date = datetime('now', '-1 minute') "
                  "WHERE cible_table = 'regions' AND cible_id = ?", (bulle_b,))
    c = _copier(source, "annotations", depuis=b)
    assert _destructible(client, c, LEA) is False
    # Le même travail fait APRÈS la copie suivante n'y est pas.
    d = _copier(source, "annotations")
    e = _copier(source, "annotations", depuis=d)
    bulle_d = _sql(db_path, "SELECT o.region_id FROM region_origine o JOIN regions r "
                            "ON r.id = o.region_id JOIN planches p ON p.id = r.planche_id "
                            "WHERE o.region_source_id = ? AND p.album_id = ?",
                   (source["bulle"], d))[0]["region_id"]
    _sql(db_path, "UPDATE copie SET creee_le = datetime('now', '-1 hour') WHERE album_id = ?",
         (e,))
    _ok(client.put(f"/api/regions/{bulle_d}", headers=SAM, json={"ocr_texte": "PLUS TARD"}))
    assert _destructible(client, e, LEA) is True


def test_l_administrateur_lit_le_travail_copie_sous_une_demande(client, db_path, source):
    """`sql_actes_sur_album` lit les mêmes sources : ce que la règle compte, l'administrateur
    le voit."""
    import autorisation
    b = _copier(source, "annotations", par="sam")
    conn = database.get_connection()
    try:
        agents = {r[0] for r in conn.execute(
            f"SELECT agent FROM ({autorisation.sql_actes_sur_album('?')})", [b] * 6)}
    finally:
        conn.close()
    assert "lea" in agents


def test_le_travail_de_la_racine_compte_deux_copies_plus_loin(client, db_path, source):
    """La chaîne entière, pas le maillon direct : `sam` a annoté la source ; `lea` en tire
    une copie, puis une copie de cette copie — le travail de `sam` est dans les deux.
    Les attributs de case sont retirés d'abord : la source 2 lit la même chaîne, et le
    test passerait sinon par elle sans mesurer la sixième source."""
    _sql(db_path, "DELETE FROM region_attribut")
    temoin = _copier(source, "annotations", depuis=_copier(source, "annotations"))
    assert _destructible(client, temoin, LEA) is True
    _ok(client.put(f"/api/regions/{source['bulle']}/annotation", headers=SAM,
                   json={"note": "de sam", "tags": ["dialogue"]}))
    _sql(db_path, "UPDATE evenement SET date = datetime('now', '-1 minute')")
    b = _copier(source, "annotations")
    c = _copier(source, "annotations", depuis=b)
    assert _destructible(client, c, LEA) is False
