"""COL-4 — ce que l'ÉCRAN du bac à sable demande au serveur, et qu'il ne rendait pas.

Trois données, chacune au plus étroit (le commit d'écran, après la maquette du 2026-10-24) :

- `bac_a_sable_ouvrable` dans `GET /api/moi` : l'écran n'offre « Mon bac à sable » qu'à qui
  le serveur l'ouvrirait. `GET /api/bac-a-sable` rend `null` dans deux cas qu'il ne
  distingue pas — « vous n'en avez pas » et « vous ne pouvez pas en avoir » ;
- `GET /api/corpus?bac_a_sable=<id>` : les chiffres de la Bibliothèque d'un bac à sable
  (relevé sur la maquette : « 0 albums » dans un bac tout neuf), bornés comme le reste —
  l'administrateur n'a rien dans le bac d'un autre ;
- le nom court « Bac · <login> » que le sélecteur de projet montre à un invité.

Les identités et le jeu sont ceux de `test_bac_a_sable.py`, dont on reprend le décor.
"""
import pytest

from conftest import ADMIN
from test_bac_a_sable import HUGO, LEA, RESP, RITA, SAM, decor, jeu  # noqa: F401


# --------------------------------------------------------------------------- #
# Qui se voit offrir « Mon bac à sable »
# --------------------------------------------------------------------------- #
def test_un_login_derriere_le_proxy_peut_ouvrir_le_sien(client, decor):
    # Celle qui en a un comme celui qui n'en a pas encore : la question est « le serveur
    # l'ouvrirait-il », pas « en avez-vous un » — recliquer y ramène.
    for qui in (LEA, RITA, HUGO, RESP):
        assert client.get("/api/moi", headers=qui).json()["bac_a_sable_ouvrable"] is True


def test_ni_le_mono_poste_ni_une_requete_sans_identite(client, jeu, derriere_proxy):
    # Derrière le proxy, sans en-tête d'identité : portée vide, rien à ouvrir.
    assert client.get("/api/moi").json()["bac_a_sable_ouvrable"] is False


def test_le_mono_poste_ne_se_voit_rien_offrir(client, jeu):
    assert client.get("/api/moi").json()["bac_a_sable_ouvrable"] is False


def test_un_compte_partage_ne_se_voit_rien_offrir(client, decor):
    tp = {"Remote-User": "groupe-tp"}
    assert client.get("/api/moi", headers=tp).json()["bac_a_sable_ouvrable"] is True
    assert client.patch("/api/comptes/groupe-tp/nature", headers=ADMIN,
                        json={"nature": "collectif"}).status_code == 200
    assert client.get("/api/moi", headers=tp).json()["bac_a_sable_ouvrable"] is False
    # La contre-épreuve : la route le refuse aussi. Les deux répondent la même chose.
    assert client.post("/api/bac-a-sable", headers=tp).status_code == 403


# --------------------------------------------------------------------------- #
# Le nom court, à un invité
# --------------------------------------------------------------------------- #
def test_l_invite_lit_bac_point_login(client, decor):
    vue = {p["id"]: p for p in client.get("/api/projets", headers=SAM).json()}[decor["bac"]["id"]]
    assert vue["nom"] == "Bac · lea"
    # Son propriétaire, lui, lit toujours « Mon bac à sable », sans login.
    mien = {p["id"]: p for p in client.get("/api/projets", headers=LEA).json()}[decor["bac"]["id"]]
    assert mien["nom"] == "Mon bac à sable" and "proprietaire" not in mien["bac_a_sable"]


def test_le_nom_court_tient_un_login_de_quinze_caracteres_entier(client, decor):
    quinze = {"Remote-User": "hsemil01-abcdef"}
    assert len(quinze["Remote-User"]) == 15
    bac = client.post("/api/bac-a-sable", headers=quinze).json()["id"]
    client.put(f"/api/projets/{bac}/membres", headers=quinze,
               json={"genre": "utilisateur", "principal": "sam", "role": "membre"})
    vue = {p["id"]: p for p in client.get("/api/projets", headers=SAM).json()}[bac]
    assert vue["nom"] == "Bac · hsemil01-abcdef"


def test_l_administrateur_lit_le_meme_nom_court_dans_la_vue_projets(client, decor):
    vus = {p["id"]: p for p in client.get("/api/projets?bacs_a_sable=1", headers=HUGO).json()}
    vue = vus[decor["bac"]["id"]]
    assert vue["nom"] == "Bac · lea" and vue["bac_a_sable"]["proprietaire"] == "lea"
    # Ce que la fiche de l'Administration lit : la date d'ouverture et celle d'effacement.
    assert vue["date_creation"] and vue["bac_a_sable"]["efface_le"]


# --------------------------------------------------------------------------- #
# Les chiffres de la Bibliothèque d'un bac à sable
# --------------------------------------------------------------------------- #
def _compte(client, qui, bac=None):
    chemin = "/api/corpus" if bac is None else f"/api/corpus?bac_a_sable={bac}"
    return client.get(chemin, headers=qui)


def test_la_bibliotheque_d_un_bac_compte_ses_albums(client, decor):
    bac = decor["bac"]
    attendus = {"albums": len(bac["jeu"]),
                "planches": sum(len(j["planche_ids"]) for j in bac["jeu"])}
    assert attendus["albums"] >= 3                     # le décor : quatre documents du jeu
    for qui in (LEA, SAM):                             # le propriétaire et son invité
        r = _compte(client, qui, bac["id"])
        assert r.status_code == 200, r.text
        c = r.json()
        assert (c["albums"], c["planches"]) == (attendus["albums"], attendus["planches"])
        assert c["statuts"]["importee"] + c["statuts"]["segmentee"] >= 0


def test_sans_le_parametre_les_chiffres_restent_aveugles_aux_bacs(client, decor):
    # Le corpus de lea : rien — son bac à sable n'y compte pas (S8), comme avant.
    c = _compte(client, LEA).json()
    assert (c["albums"], c["planches"]) == (0, 0)
    # Celui de resp : son vrai album, et lui seul.
    assert _compte(client, RESP).json()["albums"] == 1


def test_le_bac_d_un_autre_ne_se_compte_pas(client, decor):
    """L'administrateur n'a RIEN dans le bac d'un autre (Hugo, 2026-10-24) : 404, comme un
    inconnu, et la même réponse qu'un identifiant qui n'existe pas."""
    bac = decor["bac"]["id"]
    for qui in (HUGO, RITA, RESP):
        r = _compte(client, qui, bac)
        assert r.status_code == 404, (qui, r.text)
        absent = _compte(client, qui, 999999)
        assert absent.status_code == 404
        assert r.json()["detail"].replace(str(bac), "N") ==             absent.json()["detail"].replace("999999", "N")


def test_un_vrai_projet_ne_se_compte_pas_par_ce_chemin(client, decor):
    """Le paramètre ne vaut que pour un bac à sable : les chiffres d'un projet ordinaire ne
    sont pas une question de cette route (les surfaces transverses restent ce qu'elles
    sont)."""
    assert _compte(client, RESP, decor["etude"]).status_code == 404


def test_les_tags_comptes_sont_ceux_de_l_espace_du_bac(client, decor):
    bac = decor["bac"]
    region = None
    for j in bac["jeu"]:
        for pid in j["planche_ids"]:
            regions = client.get(f"/api/planches/{pid}/regions", headers=LEA).json()
            if regions:
                region = regions[0]["id"]
                break
        if region:
            break
    assert region, "le décor ne porte aucune région"
    # Deux tags de l'INSTANCE (espace 0), globaux — donc lisibles de lea — : ils ne sont pas
    # ceux du bac, et le compte ne doit pas les voir. Une mesure d'ÉCART ne le dirait pas :
    # sans le filtre de l'espace, les deux comptes bougent ensemble (relecture, mutant).
    for label in ("instance-a", "instance-b"):
        assert client.post("/api/tags", headers=ADMIN, json={"label": label}).status_code in (200, 201)
    r = client.put(f"/api/regions/{region}/annotation", headers=LEA,
                   json={"note": "", "tags": ["essai-du-bac"]})
    assert r.status_code == 200, r.text
    from test_bac_a_sable import _sql
    du_bac = _sql(decor["db"], "SELECT label FROM tags WHERE espace = ?", (bac["id"],))
    assert [t["label"] for t in du_bac] == ["essai-du-bac"]
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM tags WHERE espace = 0 "
                             "AND collection_id IS NULL")[0]["n"] >= 2
    assert _compte(client, LEA, bac["id"]).json()["tags"] == 1
    # Le corpus ne le compte pas : il est né dans le bac.
    assert all(t["label"] != "essai-du-bac"
               for t in client.get("/api/tags", headers=ADMIN).json())


@pytest.mark.parametrize("valeur", ["abc", "-1"])
def test_un_parametre_illisible_est_refuse(client, decor, valeur):
    assert _compte(client, LEA, valeur).status_code in (404, 422)
