"""CONC-2 : cycle de vie mémoire des moteurs ML.

Déchargement par moteur, orchestrateur `liberer_modeles_ml`, visibilité `/api/sante`,
endpoint `/api/ml/liberer`, et libération automatique en fin de lot. On évite de
CHARGER de vrais modèles (torch/spaCy, lourds) : on simule la résidence en posant un
sentinel sur le cache global de chaque moteur, puis on vérifie qu'il est bien lâché.
"""
import time

import pytest

import main
import pipeline.bulles as bul
import pipeline.nlp as nlpm
import pipeline.ocr as ocrm
import pipeline.segmentation as seg
from pipeline.modeles import etat_modeles, liberer_modeles_ml


@pytest.fixture(autouse=True)
def _reset_caches_ml():
    """Aucun cache de modèle ne fuit entre tests (on remet les globals à None)."""
    yield
    bul._model = None
    ocrm._reader = None
    ocrm._reader_langs = None
    nlpm._nlp = None


def _charger_factices():
    """Simule trois modèles résidents — sans importer torch ni spaCy."""
    bul._model = object()
    ocrm._reader = object()
    ocrm._reader_langs = ("fr",)
    nlpm._nlp = object()


def test_est_charge_et_liberer_par_moteur():
    _charger_factices()
    assert bul.est_charge() and ocrm.est_charge() and nlpm.est_charge()
    assert bul.liberer() is True and bul.est_charge() is False
    assert ocrm.liberer() is True and ocrm._reader_langs is None
    assert nlpm.liberer() is True and nlpm.est_charge() is False
    assert bul.liberer() is False        # déjà déchargé → rien à libérer


def test_liberer_modeles_ml_sauf():
    _charger_factices()
    liberes = liberer_modeles_ml(sauf=("nlp",))
    assert set(liberes) == {"bulles", "ocr"}
    assert etat_modeles() == {"bulles": False, "ocr": False, "nlp": True}


def test_route_sante_expose_modeles_charges(client):
    s = client.get("/api/sante").json()
    assert s["modeles_charges"] == {"bulles": False, "ocr": False, "nlp": False}
    bul._model = object()
    assert client.get("/api/sante").json()["modeles_charges"]["bulles"] is True


def test_route_liberer_ml(client):
    _charger_factices()
    r = client.post("/api/ml/liberer")
    assert r.status_code == 200
    assert set(r.json()["liberes"]) == {"bulles", "ocr", "nlp"}
    assert r.json()["modeles_charges"] == {"bulles": False, "ocr": False, "nlp": False}


def test_lot_libere_les_modeles_en_fin(client, planche, monkeypatch):
    """Un job terminé décharge les modèles ML résidents (jobs._run finally)."""
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: None)
    bul._model = object()                # simule un modèle resté chargé pendant le lot
    jid = client.post("/api/jobs", json={"passes": ["segmenter"],
                                         "planche_ids": [planche["id"]]}).json()["id"]
    for _ in range(200):
        if client.get(f"/api/jobs/{jid}").json()["status"] != "en_cours":
            break
        time.sleep(0.02)
    assert bul.est_charge() is False     # libéré en fin de lot
