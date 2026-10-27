"""COL-3, tranche 3b, E8 — REPARTIR DE ZÉRO : ramener une copie, ou une planche, à un cran.

Les décisions (Hugo, 2026-10-20 ; pour une planche, et la règle, 2026-10-21) :

- ce qui part, par cran d'arrivée, l'inverse de l'échelle d'E1 : vers `grammaire`, les
  annotations, tags, attributs, locuteurs, présences ; vers `transcription`, en plus les
  corrections et la relecture forcée ; vers `decoupage`, en plus le texte et ses tokens ;
  vers `images`, toutes les régions, la planche repart `importee` ;
- `validee` part à tout cran, `verrouillee` (et qui l'a posé) reste ;
- on repart VERS un cran plus bas que ce que la copie porte, jamais plus haut ni au même ;
- la règle de l'effacement (`Portee.clause_repartir_directe`) : depuis la tranche 3c, qui
  TIENT l'espace — le propriétaire de toutes les collections, le responsable du projet,
  l'administrateur (F3) ; sinon une demande `repartir`, motif et certification
  obligatoires ;
- UN acte sous le document, non annulable ; Ctrl+Z ne remonte pas au-delà.

Le décor est celui de `test_amorcer` : « Le Lotus bleu », importé et entièrement travaillé
par `lea` dans Principale — une case et sa bulle, le texte, une note et deux tags, un
locuteur, une présence, deux attributs de case, une correction grammaticale, la planche
validée, relue, verrouillée. `sam` écrit dans Principale et n'y a rien fait.

Tranche 3c (F3) — le créateur n'efface plus seul : `lea` est faite PROPRIÉTAIRE de
Principale (`lea_tient`), ce qui lui laisse ses gestes ; `sam` demande.
"""
import pytest

from conftest import ADMIN
from test_amorcer import LEA, SAM, _travail, source  # noqa: F401
from test_fonds import _accorder, _planche
from test_projets import _sql

LECTRICE = {"Remote-User": "lectrice"}
PROPRIO = {"Remote-User": "proprio"}


@pytest.fixture(autouse=True)
def lea_tient(client, source):
    """Tranche 3c (F3) — qui TIENT l'espace efface : `lea` possède Principale, la seule
    collection de l'album."""
    _accorder(client, source["principale"], "lea", "proprietaire")


def _ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.text)
    return r.json() if r.content else None


def _repartir(client, album_id, cran, qui):
    return client.post(f"/api/albums/{album_id}/repartir", json={"cran": cran}, headers=qui)


def _planche_etat(db, pl):
    return _sql(db, "SELECT statut, date_segmentation, validee, verrouillee, verrou_par, "
                    "relecture FROM planches WHERE id = ?", (pl,))[0]


# Ce qui RESTE à chaque cran d'arrivée (le décor porte deux régions, un texte, une
# correction, une annotation, un attribut visible et un caché — deux en base —, un
# locuteur, une présence). Les tokens se régénèrent depuis le texte qui reste, au nombre
# que donne le moteur : ils ne se comptent qu'où ils doivent être nuls.
RESTE = {
    "grammaire": {"regions": 2, "textes": 1, "corrections": 1, "annotations": 0,
                  "attributs": 0, "locuteurs": 0, "presences": 0},
    "transcription": {"regions": 2, "textes": 1, "corrections": 0, "annotations": 0,
                      "attributs": 0, "locuteurs": 0, "presences": 0},
    "decoupage": {"regions": 2, "textes": 0, "tokens": 0, "corrections": 0,
                  "annotations": 0, "attributs": 0, "locuteurs": 0, "presences": 0},
    "images": {"regions": 0, "textes": 0, "tokens": 0, "corrections": 0, "annotations": 0,
               "attributs": 0, "locuteurs": 0, "presences": 0},
}


@pytest.mark.parametrize("cran", sorted(RESTE))
def test_chaque_cran_retire_ce_qui_est_au_dessus_et_rien_d_autre(client, source, db_path,
                                                                  cran):
    rendu = _ok(_repartir(client, source["a"], cran, LEA))
    assert (rendu["cran"], rendu["depuis_cran"]) == (cran, "annotations")
    travail = _travail(db_path, source["a"])
    assert {k: travail[k] for k in RESTE[cran]} == RESTE[cran], travail
    etat = _planche_etat(db_path, source["pl"])
    # La validation part à tout cran ; le verrou reste, et qui l'a posé.
    assert etat["validee"] is None
    assert (etat["verrouillee"], etat["verrou_par"]) == ("2026-01-01", "lea")
    assert etat["relecture"] == ("faite" if cran == "grammaire" else None)
    if cran == "images":
        assert (etat["statut"], etat["date_segmentation"]) == ("importee", None)
    else:
        assert etat["statut"] == "segmentee"
    # L'index plein texte suit : plus de note ni de tag nulle part ; le texte seulement où
    # il reste.
    lignes = _sql(db_path, "SELECT ocr_texte, note, tags_concat FROM recherche "
                           "WHERE region_id IN (?, ?)", (source["case"], source["bulle"]))
    assert all(not (l["note"] or l["tags_concat"]) for l in lignes)
    textes = [l["ocr_texte"] for l in lignes if l["ocr_texte"]]
    assert textes == (["TINTIN ET LES OTAGES"] if cran in ("grammaire", "transcription")
                      else [])
    # Les comptes de la charge disent ce qui est parti.
    assert rendu["comptes"]["annotations"] == 1
    assert rendu["comptes"]["planches_devalidees"] == 1


def test_on_ne_repart_que_vers_plus_bas(client, source):
    _ok(_repartir(client, source["a"], "transcription", LEA))
    for cran in ("transcription", "grammaire"):
        r = _repartir(client, source["a"], cran, LEA)
        assert r.status_code == 409 and "Rien à retirer" in r.json()["detail"], (cran, r.text)
    for cran in ("annotations", "origine", "rien"):
        assert _repartir(client, source["a"], cran, LEA).status_code == 422, cran
    _ok(_repartir(client, source["a"], "decoupage", LEA))


def test_un_seul_acte_sous_le_document(client, source, db_path):
    """Pas des suppressions par région : UN acte, sous le DOCUMENT, avec ce qui est parti.
    Il ne s'annule pas — la cible `document` n'est pas dans la liste blanche de Ctrl+Z."""
    avant = _sql(db_path, "SELECT MAX(id) AS n FROM evenement")[0]["n"]
    _ok(_repartir(client, source["a"], "images", LEA))
    actes = _sql(db_path, "SELECT agent, cible_table, cible_id, type, "
                          "json_extract(apres, '$.repartir.cran') AS cran, "
                          "json_extract(apres, '$.repartir.depuis_cran') AS depuis, "
                          "json_extract(apres, '$.repartir.comptes.regions') AS regions "
                          "FROM evenement WHERE id > ?", (avant,))
    assert actes == [{"agent": "lea", "cible_table": "document", "cible_id": source["doc"],
                      "type": "modification", "cran": "images", "depuis": "annotations",
                      "regions": 2}]
    import undo
    assert "document" not in undo._TABLES


def test_ctrl_z_ne_remonte_pas_au_dela(client, source, db_path):
    """Après une remise à zéro de l'album, les gestes d'AVANT sur cet album ne s'annulent
    plus : chacun est passé (« ne peut plus être rétabli »), et la note effacée ne revient
    pas. Un geste fait AVANT sur un autre album s'annule encore."""
    autre = client.post("/api/albums", headers=LEA,
                        json={"titre": "Autre", "collection_id": source["principale"]}).json()
    pl = _planche(client, autre["id"], LEA)
    reg = _ok(client.post(f"/api/planches/{pl}/regions", headers=LEA,
                          json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)["id"]
    _ok(client.put(f"/api/regions/{source['bulle']}/annotation", headers=LEA,
                   json={"note": "ironie, vraiment", "tags": ["dialogue", "secret"]}))
    _ok(client.put(f"/api/regions/{reg}", headers=LEA, json={"ocr_texte": "AILLEURS"}))
    _ok(_repartir(client, source["a"], "grammaire", LEA))
    # Le plus récent : le texte posé sur l'autre album — il s'annule.
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 200, r.text
    assert r.json()["region_id"] == reg
    # Puis la note de la bulle, effacée par la remise à zéro : passée, jamais rendue.
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 409, r.text
    assert "ne peut plus être rétabli" in r.json()["detail"]["message"]
    assert not _sql(db_path, "SELECT 1 FROM annotations WHERE region_id = ?",
                    (source["bulle"],))
    # Les gestes plus anciens de cet album suivent le même chemin, jusqu'au dernier.
    for _ in range(30):
        r = client.post("/api/undo", headers=LEA)
        if r.status_code == 404:
            break
        assert r.status_code in (200, 409), r.text
        if r.status_code == 200:
            assert r.json()["region_id"] not in (source["case"], source["bulle"]), r.json()
    assert not _sql(db_path, "SELECT 1 FROM annotations WHERE region_id = ?",
                    (source["bulle"],))


def test_ctrl_z_passe_les_creations_effacees_par_une_remise_aux_images(client, source,
                                                                       db_path):
    """Relecture croisée de la 3b, constat 4 : une région CRÉÉE puis effacée par une remise à
    zéro « vers les images » n'a plus de ligne. Le témoin la reconnaît par la planche où elle
    vivait au moment de l'acte (le journal), AVANT de demander si l'agent peut écrire la
    région — qui n'existe plus : l'acte est passé avec la phrase de la remise à zéro, « l'état
    d'avant ne peut plus être rétabli », et non « n'est plus à votre portée »."""
    reg = _ok(client.post(f"/api/planches/{source['pl']}/regions", headers=LEA,
                          json={"type": "case", "x": 5, "y": 5, "w": 9, "h": 9}), 201)["id"]
    _ok(_repartir(client, source["a"], "images", LEA))
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE id = ?", (reg,))
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 409, r.text
    assert "ne peut plus être rétabli" in r.json()["detail"]["message"], r.text
    assert r.json()["detail"]["ecarte"]
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE id = ?", (reg,))


def test_apres_une_remise_a_zero_qui_n_ecrit_plus_ne_l_apprend_pas(client, source, db_path):
    """La seconde phrase ne se dit qu'à qui écrit encore la planche remise à zéro : à `lea`,
    passée en lecture sur Principale après la remise à zéro, la création effacée répond la
    première, « n'est plus à votre portée » — elle n'apprend pas ce qui s'est passé sur un
    album où elle n'écrit plus."""
    reg = _ok(client.post(f"/api/planches/{source['pl']}/regions", headers=LEA,
                          json={"type": "case", "x": 5, "y": 5, "w": 9, "h": 9}), 201)["id"]
    _ok(_repartir(client, source["a"], "images", LEA))
    _accorder(client, source["principale"], "proprio", "proprietaire")   # un autre la tient
    _accorder(client, source["principale"], "lea", "lecture")
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 409, r.text
    assert "n'est plus à votre portée" in r.json()["detail"]["message"], r.text
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE id = ?", (reg,))


def test_une_planche_repart_seule_et_le_reste_s_annule_encore(client, source, db_path):
    """Repartir sur UNE planche : elle seule perd son travail, et Ctrl+Z ne s'arrête que pour
    ses gestes — celui d'une autre planche du même album s'annule."""
    pl2 = _planche(client, source["a"], LEA)
    r2 = _ok(client.post(f"/api/planches/{pl2}/regions", headers=LEA,
                         json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)["id"]
    _ok(client.put(f"/api/regions/{r2}", headers=LEA, json={"ocr_texte": "SECONDE"}))
    _ok(client.put(f"/api/regions/{source['bulle']}/annotation", headers=LEA,
                   json={"note": "après coup", "tags": ["dialogue"]}))
    r = client.post(f"/api/planches/{source['pl']}/repartir", json={"cran": "images"},
                    headers=LEA)
    rendu = _ok(r)
    assert rendu["planche_id"] == source["pl"]
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE planche_id = ?", (source["pl"],))
    assert _sql(db_path, "SELECT ocr_texte FROM regions WHERE id = ?",
                (r2,))[0]["ocr_texte"] == "SECONDE"
    # La note posée sur la planche remise à zéro : passée. Le texte de l'autre planche :
    # annulé.
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 409, r.text
    r = client.post("/api/undo", headers=LEA)
    assert r.status_code == 200 and r.json()["region_id"] == r2, r.text


def test_la_regle_est_celle_de_l_effacement(client, source, db_path):
    """`sam` écrit dans Principale sans la posséder : 403 nommé, qui dit qui le peut — la
    planche aussi, avec ses mots. `lectrice` la lit : 403 nommé aussi depuis la tranche 3c
    (l'accesseur en lecture, F3 — l'objet est lisible) ; qui ne la lit pas, 404.
    `proprio`, propriétaire de Principale : il en repart, même sur la DERNIÈRE copie du
    document — repartir garde les images, rien ne sort du fonds (le pilotage, 2026-10-25,
    après la relecture croisée : la règle de la dernière copie ne vaut que pour la
    suppression) —, et ne la supprime pas seul. L'administrateur, toujours."""
    r = _repartir(client, source["a"], "grammaire", SAM)
    assert r.status_code == 403 and "responsable de son projet" in r.json()["detail"]
    rp = client.post(f"/api/planches/{source['pl']}/repartir", json={"cran": "images"},
                     headers=SAM)
    assert rp.status_code == 403 and "une planche" in rp.json()["detail"]
    _accorder(client, source["principale"], "lectrice", "lecture")
    r = _repartir(client, source["a"], "grammaire", LECTRICE)
    assert r.status_code == 403 and "responsable de son projet" in r.json()["detail"]
    assert _repartir(client, source["a"], "grammaire",
                     {"Remote-User": "personne"}).status_code == 404
    _accorder(client, source["principale"], "proprio", "proprietaire")
    _ok(_repartir(client, source["a"], "grammaire", PROPRIO))
    assert client.delete(f"/api/albums/{source['a']}", headers=PROPRIO).status_code == 403
    _ok(_repartir(client, source["a"], "transcription", ADMIN))
    assert _travail(db_path, source["a"])["annotations"] == 0


def _demander(client, album_id, qui, cran="grammaire", certifie=True, motif="Fausse piste"):
    return client.post("/api/demandes", headers=qui,
                       json={"genre": "repartir", "album_id": album_id, "cran": cran,
                             "motif": motif, "certifie": certifie})


def test_repartir_se_demande_et_un_administrateur_repond(client, source, db_path):
    assert _demander(client, source["a"], SAM, certifie=False).status_code == 422
    assert _demander(client, source["a"], SAM, motif="").status_code == 422
    assert _demander(client, source["a"], SAM, cran="annotations").status_code == 422
    r = _demander(client, source["a"], LEA)
    assert r.status_code == 409 and "vous-même" in r.json()["detail"]
    d = _ok(_demander(client, source["a"], SAM), 201)
    assert (d["genre"], d["cran"], d["demandeur"]) == ("repartir", "grammaire", "sam")
    assert d["certifie_le"]
    assert _demander(client, source["a"], SAM, cran="images").status_code == 409
    a = next(x for x in client.get("/api/albums", headers=SAM).json() if x["id"] == source["a"])
    assert a["demande_repartir"]["cran"] == "grammaire"
    # L'administrateur lit ce que d'autres que le demandeur y ont fait.
    vue = next(x for x in _ok(client.get("/api/demandes", headers=ADMIN)) if x["id"] == d["id"])
    assert {e["agent"] for e in vue["documents"][0]["travail_des_autres"]} == {"lea"}
    # Seul qui tient le fonds y répond.
    assert client.post(f"/api/demandes/{d['id']}/reponse", headers=LEA,
                       json={"reponse": "acceptee"}).status_code in (403, 404)
    vue = _ok(client.post(f"/api/demandes/{d['id']}/reponse", headers=ADMIN,
                          json={"reponse": "acceptee"}))
    assert vue["reponse"] == "acceptee"
    assert _travail(db_path, source["a"])["annotations"] == 0
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'document' "
                         "AND json_extract(apres, '$.repartir.cran') = 'grammaire'") == [
        {"agent": ADMIN["Remote-User"]}]


def test_un_refus_ne_touche_a_rien_et_la_destruction_clot_la_demande(client, source, db_path):
    d = _ok(_demander(client, source["a"], SAM), 201)
    _ok(client.post(f"/api/demandes/{d['id']}/reponse", headers=ADMIN,
                    json={"reponse": "refusee"}))
    assert _travail(db_path, source["a"])["annotations"] == 1
    d2 = _ok(_demander(client, source["a"], SAM), 201)
    # La dernière copie du document : seul un administrateur la supprime (tranche 3c, F3).
    assert client.delete(f"/api/albums/{source['a']}", headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?",
                (d2["id"],))[0]["reponse"] == "refusee"


def test_dans_un_bac_a_sable_son_proprietaire_repart_et_rien_ne_se_demande(client, source,
                                                                          db_path):
    """Le bac à sable de `lea`, où `sam` est invité : `sam` y travaille sur un album de
    `lea`. Depuis la tranche 3c (Q4, Hugo, 2026-10-26, qui renverse la règle commune pour
    l'invité), quiconque écrit dans un bac à sable y efface : `sam` y repart de zéro, et
    n'a donc rien à demander (409). `lea` y repart, quel que soit qui y a travaillé."""
    bac = _ok(client.post("/api/bac-a-sable", headers=LEA), 201)
    _ok(client.put(f"/api/projets/{bac['id']}/membres", headers=LEA,
                   json={"genre": "utilisateur", "principal": "sam", "role": "membre"}))
    a = _ok(client.post("/api/albums", headers=LEA,
                        json={"titre": "Au bac", "collection_id": bac["base"]["id"]}), 201)["id"]
    pl = _planche(client, a, LEA)
    _ok(client.post(f"/api/planches/{pl}/regions", headers=SAM,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)
    r = _demander(client, a, SAM, cran="images")
    assert r.status_code == 409 and "vous-même" in r.json()["detail"], r.text
    _ok(_repartir(client, a, "images", SAM))
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE planche_id = ?", (pl,))
    _ok(client.post(f"/api/planches/{pl}/regions", headers=SAM,
                    json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}), 201)
    _ok(_repartir(client, a, "images", LEA))
    assert not _sql(db_path, "SELECT 1 FROM regions WHERE planche_id = ?", (pl,))
