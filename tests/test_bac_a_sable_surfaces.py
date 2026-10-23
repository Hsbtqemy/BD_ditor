"""COL-4 — les surfaces qui traversent les projets (S8) et celles de l'administrateur (S6).

La Recherche et l'Exploration ne voient les bacs à sable POUR PERSONNE, ni l'administrateur
ni leur propriétaire (Q4, Hugo, 2026-10-21) : les mesures du corpus restent celles du vrai
corpus. Et une portée totale ne reçoit, de soixante-quinze bacs à sable, que le sien et ceux
où elle est invitée, sauf à le demander (`bacs_a_sable=1`).
"""
import pytest

from conftest import ADMIN, make_png
from test_bac_a_sable import HUGO, LEA, RESP, SAM, _copie, _sql, decor, jeu  # noqa: F401


@pytest.fixture
def corpus(client, decor):
    """Une bulle « LE OTAGE » dans le vrai projet, à côté de celles du jeu."""
    pl = client.post(f"/api/albums/{decor['reel']}/import", headers=RESP,
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    reg = client.post(f"/api/planches/{pl}/regions", headers=RESP,
                      json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    client.put(f"/api/regions/{reg}", headers=RESP, json={"ocr_texte": "LE OTAGE"})
    client.put(f"/api/regions/{reg}/annotation", headers=RESP,
               json={"note": "n", "tags": ["vrai-tag"]})
    planche = _copie(decor, "exemple")["planche_ids"][0]
    breg = client.get(f"/api/planches/{planche}/regions", headers=LEA).json()[-1]["id"]
    client.put(f"/api/regions/{breg}/annotation", headers=LEA,
               json={"note": "n", "tags": ["tag-du-bac", "vrai-tag"]})
    hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    return {**decor, "region_reelle": reg, "region_du_bac": breg, "bac_hugo": hugo}


def _regions_trouvees(client, qui, q="otage"):
    return {r["region_id"] for r in client.get("/api/recherche", headers=qui,
                                               params={"q": q}).json()["results"]}


def test_la_recherche_ne_voit_aucun_bac_a_sable(client, corpus):
    assert corpus["region_du_bac"] not in _regions_trouvees(client, LEA)
    trouvees = _regions_trouvees(client, HUGO)
    assert corpus["region_reelle"] in trouvees
    # Ni les copies des bacs à sable, ni la référence du jeu : la seule bulle est la vraie.
    assert trouvees == {corpus["region_reelle"]}
    assert client.get("/api/corpus", headers=LEA).json()["regions"] == 0
    stats = client.get("/api/corpus", headers=HUGO).json()
    assert stats["albums"] == _sql(corpus["db"], "SELECT COUNT(*) AS n FROM albums a JOIN "
                                                 "projet p ON p.id = a.projet_id WHERE "
                                                 "p.bac_a_sable_de IS NULL AND p.jeu = 0"
                                   )[0]["n"]


def test_l_exploration_ne_compte_aucun_bac_a_sable(client, corpus):
    """La concordance et les fréquences : ni la copie du jeu dans le bac à sable de lea, ni
    sa référence. Le vrai corpus porte UNE bulle « LE OTAGE » ; le jeu en porte deux de
    plus (la référence, la copie)."""
    r = client.get("/api/analyse/concordance", headers=HUGO,
                   params={"tags": "vrai-tag"}).json()
    regions = {x["region_id"] for x in r["results"]}
    assert corpus["region_du_bac"] not in regions
    assert client.get("/api/analyse/concordance", headers=LEA,
                      params={"tags": "vrai-tag"}).json()["results"] == []
    freq = client.get("/api/analyse/frequences", headers=HUGO,
                      params={"champ": "lemme"}).json()["results"]
    otage = sum(x["freq"] for x in freq if (x.get("lemme") or "").lower() == "otage")
    assert otage <= 1, freq


def test_le_nuage_et_le_lexique_ne_comptent_pas_les_bacs_a_sable(client, corpus):
    nuage = {t["label"]: t["frequence"] for t in client.get("/api/tags", headers=HUGO).json()}
    assert nuage.get("vrai-tag") == 1 and "tag-du-bac" not in nuage
    lexique = {t["label"]: t for t in client.get("/api/lexique", headers=HUGO).json()["tags"]}
    assert "tag-du-bac" not in lexique
    # L'Atelier, lui, propose sur l'album qu'il ouvre ce qui s'y pose.
    album = _copie(corpus, "exemple")["album_id"]
    assert "tag-du-bac" in {t["label"] for t in client.get(
        "/api/tags", headers=LEA, params={"album": album}).json()}


def test_l_accord_modele_humain_ne_compte_pas_le_jeu(client, corpus):
    """La référence au cran grammaire et ses copies portent une correction ; aucune ne
    compte : le vrai corpus n'en a pas."""
    assert _sql(corpus["db"], "SELECT COUNT(*) AS n FROM token_correction")[0]["n"] >= 2
    assert client.get("/api/analyse/accord", headers=HUGO).json()["revus"] == 0


def test_l_administrateur_ne_voit_que_ses_bacs_a_sable_sans_le_demander(client, corpus):
    vus = {p["id"] for p in client.get("/api/projets", headers=HUGO).json()}
    assert corpus["bac_hugo"]["id"] in vus and corpus["bac"]["id"] not in vus
    tous = {p["id"] for p in client.get("/api/projets?bacs_a_sable=1", headers=HUGO).json()}
    assert corpus["bac"]["id"] in tous
    assert corpus["base"] not in {c["id"] for c in
                                  client.get("/api/collections", headers=HUGO).json()}
    assert corpus["base"] in {c["id"] for c in client.get("/api/collections?bacs_a_sable=1",
                                                          headers=HUGO).json()}
    copie = _copie(corpus, "exemple")["album_id"]
    assert copie not in {a["id"] for a in client.get("/api/albums", headers=HUGO).json()}
    assert copie in {a["id"] for a in client.get("/api/albums?bacs_a_sable=1",
                                                 headers=HUGO).json()}
    # Invité dans un bac à sable, il le voit.
    client.put(f"/api/projets/{corpus['bac']['id']}/membres", headers=LEA,
               json={"genre": "utilisateur", "principal": "hugo", "role": "membre"})
    assert corpus["bac"]["id"] in {p["id"] for p in
                                   client.get("/api/projets", headers=HUGO).json()}


def test_un_compte_ordinaire_voit_ses_bacs_a_sable(client, corpus):
    assert corpus["bac"]["id"] in {p["id"] for p in
                                   client.get("/api/projets", headers=SAM).json()}
    assert corpus["bac"]["id"] in {p["id"] for p in
                                   client.get("/api/projets", headers=LEA).json()}


def test_comptes_et_groupes_ecarte_les_bacs_a_sable(client, corpus):
    vue = client.get("/api/comptes-et-groupes", headers=HUGO).json()
    comptes = {c["login"]: c for c in vue["comptes"]}
    assert comptes["lea"]["bac_a_sable"] is True and comptes["sam"]["bac_a_sable"] is False
    assert comptes["lea"]["entrees_projet"] == 0 and comptes["sam"]["entrees_projet"] == 0
    assert "collection de base" not in comptes["lea"]["verdict"]
    assert not any(c["par"] == "projet" for c in comptes["lea"]["collections"])
    ids = {c["id"] for c in vue["collections"]}
    assert corpus["base"] not in ids


def test_aucune_demande_d_un_bac_a_sable_dans_a_faire(client, corpus):
    pid = corpus["bac"]["id"]
    chez_sam = client.post("/api/collections", headers=SAM,
                           json={"nom": "Chez Sam", "projet_id": pid}).json()["id"]
    copie = _copie(corpus, "exemple")["album_id"]
    r = client.put(f"/api/albums/{copie}/collections/{chez_sam}", headers=SAM)
    assert r.status_code == 202
    demande = r.json()["demande_id"]
    vue = client.get("/api/comptes-et-groupes", headers=HUGO).json()
    assert demande not in {l.get("demande") for l in vue["a_regarder"]}
    assert demande not in {d["id"] for d in client.get("/api/demandes", headers=HUGO).json()}
    assert demande in {d["id"] for d in client.get("/api/demandes?bacs_a_sable=1",
                                                   headers=HUGO).json()}


def test_le_fonds_masque_les_bacs_a_sable_et_le_jeu(client, corpus):
    titres = {c["titre"] for d in client.get("/api/fonds", headers=HUGO).json()["documents"]
              for c in d["copies"]}
    assert "Réel" in titres and not {"Le parcours", "Un exemple", "Sous droits"} & titres
    tout = {c["titre"] for d in client.get("/api/fonds?bacs_a_sable=1",
                                           headers=HUGO).json()["documents"]
            for c in d["copies"]}
    assert {"Le parcours", "Un exemple", "Sous droits"} <= tout
