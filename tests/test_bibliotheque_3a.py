"""COL-3, tranche 3a — ce que `GET /api/albums` ajoute pour les gestes de la Bibliothèque.

- `soeur` : le document de cette copie a une autre copie vivante. « Supprimer… » le dit
  (« Ses images restent : une autre copie de ce document les emploie »), SANS dire où ni
  laquelle — qui ne lit qu'un projet n'apprend pas qu'un autre emploie le document. Il suit
  la borne de `partage` : vrai seulement pour qui ÉCRIT dans la copie ; une lectrice reçoit
  toujours faux.
- `rejoindre_demande` : les collections d'arrivée où un « rejoindre » de la copie attend,
  parmi celles où l'appelant écrit — la case « Sur les collections » se dessine
  « demandée ». Rien pour qui n'écrit pas dans la collection d'arrivée.

Le décor est celui de `test_prendre.py` (`prise`) : trois documents importés dans
Principale (repli) ; le projet « Étude P » avec X (`proprio` la possède, `ecrivain` y écrit,
`lectrice` la lit) et Y (`ecrivain` et `proprio` y écrivent).
"""
import json

from conftest import ADMIN
from test_prendre import (ECRIVAIN, IMPORTEUR, LECTRICE, PROPRIO, _copie_dans,  # noqa: F401
                          prise)


def _albums_vus(client, qui):
    r = client.get("/api/albums", headers=qui)
    assert r.status_code == 200, r.text
    return {a["id"]: a for a in r.json()}


def test_soeur_se_dit_a_qui_ecrit_et_jamais_ou(client, prise):
    cx = _copie_dans(client, prise, "d1", prise["x"])        # une sœur de d1, dans X
    d1, d2 = prise["albums"]["d1"], prise["albums"]["d2"]

    # Qui écrit dans la copie apprend qu'une sœur existe — dans X comme dans Principale.
    for qui in (PROPRIO, ECRIVAIN):
        assert _albums_vus(client, qui)[cx]["soeur"] is True, qui
    vus = _albums_vus(client, IMPORTEUR)
    assert vus[d1]["soeur"] is True
    assert vus[d2]["soeur"] is False, "un document d'une seule copie n'a pas de sœur"
    assert _albums_vus(client, ADMIN)[cx]["soeur"] is True

    # La lectrice de X : faux, toujours — elle n'a aucun geste dont il change les mots.
    assert _albums_vus(client, LECTRICE)[cx]["soeur"] is False

    # Jamais OÙ : un booléen, ni la collection de l'autre copie, ni une clé de plus.
    a = _albums_vus(client, ECRIVAIN)[cx]
    assert "Principale" not in json.dumps(a, ensure_ascii=False)
    seule = _albums_vus(client, IMPORTEUR)[d2]
    assert set(a) == set(seule), "une sœur ne doit ajouter aucune clé à la réponse"


def test_un_rejoindre_en_attente_se_lit_par_qui_ecrit_a_l_arrivee(client, prise):
    cx = _copie_dans(client, prise, "d2", prise["x"])
    # `ecrivain` n'administre pas X : ranger dans Y se DEMANDE au propriétaire de X.
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text

    assert _albums_vus(client, ECRIVAIN)[cx]["rejoindre_demande"] == [prise["y"]]
    assert _albums_vus(client, PROPRIO)[cx]["rejoindre_demande"] == [prise["y"]]
    assert _albums_vus(client, ADMIN)[cx]["rejoindre_demande"] == [prise["y"]]
    # La lectrice lit la copie par X, et n'écrit pas dans Y : rien ne lui en est dit.
    assert _albums_vus(client, LECTRICE)[cx]["rejoindre_demande"] == []

    # Accepté, la demande ne s'affiche plus.
    demande = r.json()["demande_id"]
    r = client.post(f"/api/demandes/{demande}/reponse", json={"reponse": "acceptee"},
                    headers=PROPRIO)
    assert r.status_code == 200, r.text
    assert _albums_vus(client, ECRIVAIN)[cx]["rejoindre_demande"] == []


def test_une_portee_totale_qui_range_clot_le_rejoindre_qui_l_attendait(client, prise):
    """Relecture croisée de t3a-c4 : sous une portée totale, la case d'un rejoindre qui attend
    reste un geste. Ranger directement y RÉPOND — accepté —, sans quoi la demande resterait
    offerte au propriétaire pour un rangement déjà fait. Un rejoindre vers une AUTRE
    collection n'est pas touché."""
    cx = _copie_dans(client, prise, "d3", prise["x"])
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ECRIVAIN)
    assert r.status_code == 202, r.text
    demande = r.json()["demande_id"]
    r = client.put(f"/api/albums/{cx}/collections/{prise['base']}", headers=ADMIN)
    assert r.status_code == 201, r.text
    assert [d["id"] for d in client.get(f"/api/collections/{prise['x']}/demandes",
                                        headers=PROPRIO).json()] == [demande], \
        "ranger ailleurs ne répond pas à la demande"
    r = client.put(f"/api/albums/{cx}/collections/{prise['y']}", headers=ADMIN)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/collections/{prise['x']}/demandes", headers=PROPRIO).json() == []
    d = {x["id"]: x for x in client.get("/api/demandes", headers=ADMIN).json()}[demande]
    assert (d["en_attente"], d["reponse"]) == (False, "acceptee"), d
    assert _albums_vus(client, ECRIVAIN)[cx]["rejoindre_demande"] == []
