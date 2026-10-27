"""COL-3, tranche 3b — trois réponses que l'ÉCRAN codé a demandées au serveur, au plus étroit
(écran tranché par Hugo sur maquette le 2026-10-25), et leurs bornes.

- « + Créer une collection » éteint dit au survol que seuls les responsables créent dans ce
  projet, EN LES NOMMANT : `responsables` dans `GET /api/projets`, au seul MEMBRE que le
  réglage n'autorise pas — ni à qui crée, ni à qui ne voit le projet que par une collection ;
- l'administrateur lit dans « À faire » qui ATTEND une demande consentie (« attend … »),
  pour un rejoindre comme pour en partir dans un projet : `attend`, dans `GET /api/demandes`
  (réservée à qui tient le fonds), les principaux qui tiennent toutes les collections de la
  copie visée ;
- une copie née d'une autre le dit sur sa ligne : `copie_cran` dans `GET /api/albums`, le
  cran seul.

Le décor est celui de `test_prendre` : Étude P (`resp` responsable, `membre` membre), sa
Collection X (`proprio` la possède, `ecrivain` y écrit, `lectrice` la lit) et sa Collection
Y (`ecrivain` et `proprio` y écrivent, sans propriétaire).
"""
import pytest

from conftest import ADMIN
from test_fonds import _accorder, _album, _collection, _planche
from test_prendre import (ECRIVAIN, LECTRICE, MEMBRE, PERSONNE, PROPRIO, RESP,
                          prise)  # noqa: F401


def _vue(client, qui, projet_id):
    return next((p for p in client.get("/api/projets", headers=qui).json()
                 if p["id"] == projet_id), None)


def _db(client):
    import database
    return database.DB_PATH


def _ok(r, *codes):
    assert r.status_code in (codes or (200,)), (r.status_code, r.text)
    return r.json() if r.content else None


# =========================================================================== #
# Les responsables nommés au membre qui ne crée pas
# =========================================================================== #
def test_le_membre_qui_ne_cree_pas_lit_les_noms_des_responsables(client, prise):
    p = prise["projet"]
    # Le nom lisible vient du miroir `utilisateur`, posé par une requête du compte.
    client.get("/api/moi", headers={**RESP, "Remote-Name": "Remi Responsable"})
    vue = _vue(client, MEMBRE, p)
    assert vue["collection_creable"] is False
    assert vue["responsables"] == ["Remi Responsable"]
    # Un groupe responsable se dit par son nom de groupe, après les comptes.
    _ok(client.put(f"/api/projets/{p}/membres", headers=ADMIN,
                   json={"genre": "groupe", "principal": "pilotes", "role": "responsable"}))
    assert _vue(client, MEMBRE, p)["responsables"] == ["Remi Responsable", "groupe pilotes"]


def test_les_responsables_ne_se_nomment_qu_a_lui(client, prise):
    p = prise["projet"]
    client.get("/api/moi", headers={**RESP, "Remote-Name": "Remi Responsable"})
    # Qui crée (le responsable, l'administrateur) n'a pas de bouton éteint : rien.
    for qui in (RESP, ADMIN):
        assert "responsables" not in _vue(client, qui, p), qui
    # Qui ne voit le projet que par une collection qu'il lit (il n'en est pas) : rien.
    # Depuis la tranche 3c (F2), seule une base retouchée porte un tel accès — posé en SQL.
    from test_projets import _sql
    _sql(_db(client),
         "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
         "VALUES (?, 'utilisateur', 'hors-projet', 'lecture')", (prise["x"],))
    v = _vue(client, {"Remote-User": "hors-projet"}, p)
    assert v is not None and v["mon_role"] is None and "responsables" not in v
    # Qui ne voit pas le projet ne le reçoit pas du tout.
    assert _vue(client, PERSONNE, p) is None
    # Le réglage ouvert, le membre crée : son bouton s'allume, les noms partent.
    _ok(client.put(f"/api/projets/{p}/creation-de-collections", headers=RESP,
                   json={"membres": True}))
    v = _vue(client, MEMBRE, p)
    assert v["collection_creable"] is True and "responsables" not in v


def test_sans_responsable_la_liste_est_vide(client, prise):
    """Le projet de repli, sans responsable : la liste est vide, et l'écran dit que seuls
    les administrateurs y créent."""
    repli = next(p for p in client.get("/api/projets", headers=ADMIN).json() if p["repli"])
    _ok(client.put(f"/api/projets/{repli['id']}/membres", headers=ADMIN,
                   json={"principal": "membre", "role": "membre"}))
    v = _vue(client, MEMBRE, repli["id"])
    assert v["collection_creable"] is False and v["responsables"] == []


# =========================================================================== #
# « attend … » sous une demande consentie, pour l'administrateur
# =========================================================================== #
def _demande(client, genre, album_id):
    return next(d for d in client.get("/api/demandes", headers=ADMIN).json()
                if d["genre"] == genre and d["documents"][0]["album_id"] == album_id
                and d["en_attente"])


def test_l_administrateur_lit_qui_attend_un_rejoindre_et_une_demande_d_en_partir(client, prise):
    client.get("/api/moi", headers={**PROPRIO, "Remote-Name": "Paule Proprietaire"})
    a = _album(client, "Le Gorille", prise["x"], PROPRIO)
    _planche(client, a, PROPRIO)
    doc = next(x for x in client.get("/api/albums", headers=ADMIN).json()
               if x["id"] == a)["document_id"]
    # L'écrivain de Y n'administre pas X : rejoindre et en partir se demandent à Paule.
    r = _ok(client.put(f"/api/albums/{a}/collections/{prise['y']}", headers=ECRIVAIN), 202)
    assert r["etat"] == "demande"
    assert _demande(client, "rejoindre", a)["attend"] == ["Paule Proprietaire"]
    r = _ok(client.post(f"/api/collections/{prise['y']}/prendre", headers=ECRIVAIN,
                        json={"documents": [{"document_id": doc, "reponse": "amorcer",
                                             "album_id": a, "cran": "decoupage"}]}))
    assert r["documents"][0]["etat"] == "demande"
    assert _demande(client, "amorcer", a)["attend"] == ["Paule Proprietaire"]


def test_personne_ne_tient_toute_la_copie_la_liste_est_vide(client, prise):
    """Une copie rangée dans X (Paule) ET dans Y (sans propriétaire) : personne ne les tient
    toutes, la demande ne s'adresse qu'à l'administrateur — `attend` vide."""
    a = _album(client, "Le Nid", prise["x"], PROPRIO)
    _ok(client.put(f"/api/albums/{a}/collections/{prise['y']}", headers=ADMIN), 200, 201)
    z = _collection(client, "Collection Z", projet_id=prise["projet"])
    _accorder(client, z, "ecrivain", "ecriture")
    r = client.put(f"/api/albums/{a}/collections/{z}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text
    assert _demande(client, "rejoindre", a)["attend"] == []


def test_attend_ne_sort_que_pour_qui_tient_le_fonds(client, prise):
    """`attend` vit dans `GET /api/demandes`, réservée à qui tient le fonds ; la lecture d'une
    collection par son propriétaire ne le porte pas."""
    a = _album(client, "Le Voyageur", prise["x"], PROPRIO)
    _ok(client.put(f"/api/albums/{a}/collections/{prise['y']}", headers=ECRIVAIN), 202)
    assert client.get("/api/demandes", headers=PROPRIO).status_code == 403
    recues = client.get(f"/api/collections/{prise['x']}/demandes", headers=PROPRIO).json()
    assert recues and all("attend" not in d for d in recues)


# =========================================================================== #
# Le cran où une copie est née
# =========================================================================== #
def test_une_copie_dit_le_cran_ou_elle_est_nee(client, prise):
    a = _album(client, "Le Marsupilami", prise["x"], PROPRIO)
    _planche(client, a, PROPRIO)
    lus = {x["id"]: x for x in client.get("/api/albums", headers=ADMIN).json()}
    assert lus[a]["copie_cran"] == "origine"
    doc = lus[a]["document_id"]
    r = _ok(client.post(f"/api/collections/{prise['y']}/prendre", headers=ECRIVAIN,
                        json={"documents": [{"document_id": doc, "reponse": "zero",
                                             "album_id": a}]}))
    copie = r["documents"][0]["copie_id"]
    lus = {x["id"]: x for x in client.get("/api/albums", headers=ECRIVAIN).json()}
    assert lus[copie]["copie_cran"] == "images"
    # Le cran seul : ni la source, ni qui l'a créée.
    assert "depuis_album_id" not in lus[copie] and "creee_par" not in lus[copie]
