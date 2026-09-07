"""EXP-1 — le manifeste IIIF par la voie de l'application, et ce que le régime en retient.

Les deux autres artefacts de dépôt DÉCRIVENT un périmètre auquel on est déjà admis.
Celui-ci sert à PUBLIER, et il porte donc la seule question de droits du module : DROIT-1
fait mordre `statut_diffusion` à la sortie, `date_embargo` peut retenir davantage, et le
manifeste amputé doit le DÉCLARER — sans quoi « ce dépôt retient ses scans » et « ce dépôt
a oublié ses scans » deviennent indistinguables.

Ce module vérifie surtout ce que le passage de la CLI à la route met en danger. Les
constats de l'outil partaient sur `stderr`, où un humain les lit au moment où il tape la
commande ; un téléchargement n'a personne devant lui. Trois manières de les perdre, et
elles sont testées séparément : les taire, les reformuler, ou les rendre à la mauvaise
gravité.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import ADMIN

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import iiif_manifest  # noqa: E402

BASE = "https://images.example.org/iiif"


# --------------------------------------------------------------------------- #
# Décor
# --------------------------------------------------------------------------- #
@pytest.fixture
def collection_avec_planche(client, png_bytes, derriere_proxy):
    """Une collection, un album dedans, une planche importée.

    La planche compte : un Canvas exige des dimensions master, et un manifeste sans Canvas
    ne dirait rien des images qu'il porte ou retient.
    """
    col = client.post("/api/collections", json={"nom": "Corpus IIIF"},
                      headers=ADMIN).json()
    alb = client.post("/api/albums",
                      json={"titre": "Album IIIF", "serie": "S", "annee": 2016,
                            "collection_id": col["id"]}, headers=ADMIN).json()
    client.post(f"/api/albums/{alb['id']}/import",
                files={"file": ("planche.png", png_bytes, "image/png")}, headers=ADMIN)
    return col, alb


def _regime(client, collection_id, **champs):
    r = client.patch(f"/api/collections/{collection_id}", json=champs, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def _archive(reponse):
    return zipfile.ZipFile(io.BytesIO(reponse.content))


# --------------------------------------------------------------------------- #
# L'archive
# --------------------------------------------------------------------------- #
def test_l_archive_porte_la_collection_et_un_manifeste_par_album(client,
                                                                 collection_avec_planche):
    """Ce que la CLI écrit dans `--out-dir`, la route le met dans une archive.

    Le manifeste IIIF est intrinsèquement MULTI-FICHIERS — une Collection plus un Manifest
    par album — ce qui fait du zip la seule forme honnête pour un téléchargement.
    """
    col, alb = collection_avec_planche
    r = client.get(f"/api/collections/{col['id']}/depot/iiif?base_url={BASE}",
                   headers=ADMIN)
    assert r.status_code == 200, r.text
    with _archive(r) as z:
        noms = set(z.namelist())
        assert "collection.json" in noms
        assert f"manifest-a{alb['id']}.json" in noms
        manifeste = json.loads(z.read(f"manifest-a{alb['id']}.json"))
    assert manifeste["type"] == "Manifest"
    assert manifeste["items"], "aucun Canvas : la planche n'a pas été vue"


def test_base_url_est_OBLIGATOIRE(client, collection_avec_planche):
    """L'application ne peut pas le deviner, et un défaut plausible serait le pire des cas.

    Elle sert bien `/derivatives`, mais par une route cloisonnée depuis AUTH-2 : se
    désigner elle-même fabriquerait un manifeste dont chaque image répond 404 chez le
    destinataire — un défaut qui MARCHE localement et casse à la remise.
    """
    col, _ = collection_avec_planche
    r = client.get(f"/api/collections/{col['id']}/depot/iiif", headers=ADMIN)
    assert r.status_code == 422, r.text


def test_le_placeholder_est_refuse_avec_le_message_de_l_outil(client,
                                                              collection_avec_planche):
    """422, et le message est celui de la CLI — pas une reformulation.

    Reformuler serait la manière discrète de rouvrir ce que la fiche ferme : deux textes
    qui disent la même chose aujourd'hui divergent au premier ajustement, et c'est alors
    la route qui ment, puisque c'est elle qu'on lit le moins.
    """
    col, _ = collection_avec_planche
    r = client.get(f"/api/collections/{col['id']}/depot/iiif"
                   f"?base_url={iiif_manifest.PLACEHOLDER}", headers=ADMIN)
    assert r.status_code == 422, r.text
    attendu = [c.message for c in
               iiif_manifest.diagnostic_base_url(iiif_manifest.PLACEHOLDER, remis=True)
               if c.gravite == "refus"]
    assert r.json()["detail"] in attendu


# --------------------------------------------------------------------------- #
# Le régime mord à la sortie (DROIT-1)
# --------------------------------------------------------------------------- #
def test_le_verbatim_hors_regime_est_un_403_et_non_un_422(client, collection_avec_planche):
    """La demande est bien formée ; c'est le DROIT qui manque.

    La distinction n'est pas cosmétique : un 422 ferait chercher une faute de frappe dans
    l'URL, là où il faut changer le régime de la collection — ou renoncer à publier le
    texte de l'œuvre et le CITER, ce que le message propose.
    """
    col, _ = collection_avec_planche
    _regime(client, col["id"], statut_diffusion="restreint")
    r = client.get(f"/api/collections/{col['id']}/depot/iiif"
                   f"?base_url={BASE}&verbatim=true", headers=ADMIN)
    assert r.status_code == 403, r.text
    assert "restreint" in r.json()["detail"]


def test_une_collection_NON_publique_declare_son_manifeste_ampute(client,
                                                                  collection_avec_planche):
    """Le manifeste sort quand même — c'est la forme NORMALE d'un dépôt — et il le DIT.

    Un entrepôt reçoit d'abord le manifeste et ses Canvas, pas les planches. Ce qui doit
    rester impossible, c'est de confondre le manifeste qui retient ses images avec celui
    qui les a perdues : `requiredStatement` le déclare côté visionneuse, et
    `AVERTISSEMENTS.txt` le dit à qui télécharge.
    """
    col, alb = collection_avec_planche
    _regime(client, col["id"], statut_diffusion="restreint")
    r = client.get(f"/api/collections/{col['id']}/depot/iiif?base_url={BASE}",
                   headers=ADMIN)
    assert r.status_code == 200, r.text
    with _archive(r) as z:
        assert "AVERTISSEMENTS.txt" in z.namelist(), (
            "les constats de l'outil sont partis sur stderr, où personne ne les lit")
        avertis = z.read("AVERTISSEMENTS.txt").decode("utf-8")
        manifeste = json.loads(z.read(f"manifest-a{alb['id']}.json"))
    assert "SANS IMAGES" in avertis
    assert iiif_manifest.DECLARATION_SANS_IMAGES in json.dumps(manifeste,
                                                               ensure_ascii=False)


def test_une_collection_PUBLIQUE_emporte_ses_images_et_n_avertit_de_rien(
        client, collection_avec_planche):
    """L'autre bout de la bascule, sans quoi le test précédent passerait sur un outil
    qui refuserait TOUJOURS les images."""
    col, alb = collection_avec_planche
    _regime(client, col["id"], statut_diffusion="public")
    r = client.get(f"/api/collections/{col['id']}/depot/iiif?base_url={BASE}",
                   headers=ADMIN)
    assert r.status_code == 200, r.text
    with _archive(r) as z:
        assert "AVERTISSEMENTS.txt" not in z.namelist(), z.read("AVERTISSEMENTS.txt")
        manifeste = json.loads(z.read(f"manifest-a{alb['id']}.json"))
    texte = json.dumps(manifeste, ensure_ascii=False)
    assert BASE in texte, "aucune URL d'image : la collection publique n'a rien emporté"
    assert iiif_manifest.DECLARATION_SANS_IMAGES not in texte


def test_un_embargo_qui_court_retient_meme_une_collection_publique(client,
                                                                   collection_avec_planche):
    """`date_embargo` RETIENT, elle ne promeut jamais — la date est plus restrictive que
    le statut, donc elle gagne."""
    col, _ = collection_avec_planche
    _regime(client, col["id"], statut_diffusion="public", date_embargo="2099-01-01")
    r = client.get(f"/api/collections/{col['id']}/depot/iiif?base_url={BASE}",
                   headers=ADMIN)
    assert r.status_code == 200, r.text
    with _archive(r) as z:
        avertis = z.read("AVERTISSEMENTS.txt").decode("utf-8")
    assert "SANS IMAGES" in avertis
    assert "2099-01-01" in avertis


# --------------------------------------------------------------------------- #
# Le cloisonnement s'applique comme aux deux autres
# --------------------------------------------------------------------------- #
def test_une_collection_qu_on_ne_lit_pas_est_INTROUVABLE(client, collection_avec_planche):
    col, _ = collection_avec_planche
    r = client.get(f"/api/collections/{col['id']}/depot/iiif?base_url={BASE}",
                   headers={"Remote-User": "etranger"})
    assert r.status_code == 404, r.text
