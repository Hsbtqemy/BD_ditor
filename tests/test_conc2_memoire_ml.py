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
import pipeline.jobs as jobs
import pipeline.modeles as modeles
import pipeline.nlp as nlpm
import pipeline.ocr as ocrm
import pipeline.segmentation as seg
from pipeline.bulles import BullesError
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


# --------------------------------------------------------------------------- #
# 2026-11-25 — la mémoire rendue au système, et l'échéance d'inactivité
# --------------------------------------------------------------------------- #
# Mesuré en production : décharger les deux modèles n'a rien rendu (1,94 → 2,12 Go), et le
# va-et-vient bulles ↔ OCR des passes interactives fragmentait la mémoire jusqu'à l'OOM.


def _attendre(condition, delai=3.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_rendre_au_systeme_rend_un_booleen_sans_jamais_lever():
    # Sous glibc il appelle `malloc_trim` ; ailleurs (Windows, macOS, musl) il ne fait rien.
    assert modeles.rendre_au_systeme() in (True, False)


def test_decharger_rend_la_memoire_au_systeme(monkeypatch):
    appels = []
    monkeypatch.setattr(modeles, "rendre_au_systeme", lambda: appels.append(1) or True)
    assert liberer_modeles_ml() == []          # rien de chargé : rien à rendre
    assert appels == []
    _charger_factices()
    liberer_modeles_ml()
    assert appels == [1]


def test_l_echeance_decharge_les_modeles_torch_et_garde_spacy(monkeypatch):
    monkeypatch.setattr(modeles, "TTL_MODELES", 0.05)
    _charger_factices()
    modeles.signaler_usage()
    assert _attendre(lambda: not bul.est_charge() and not ocrm.est_charge())
    assert nlpm.est_charge(), "chaque transcription emploie spaCy : il reste"


def test_l_echeance_attend_la_fin_d_une_passe(monkeypatch):
    """Le verrou des moteurs tenu, l'échéance se repousse au lieu de décharger — ni pendant
    l'inférence, ni en l'attendant."""
    monkeypatch.setattr(modeles, "TTL_MODELES", 0.05)
    _charger_factices()
    with jobs.ML_LOCK:
        modeles.signaler_usage()
        time.sleep(0.3)
        assert bul.est_charge() and ocrm.est_charge()
    assert _attendre(lambda: not bul.est_charge())


def test_une_passe_recente_repousse_l_echeance(monkeypatch):
    monkeypatch.setattr(modeles, "TTL_MODELES", 0.4)
    _charger_factices()
    modeles.signaler_usage()
    time.sleep(0.25)
    modeles.signaler_usage()
    time.sleep(0.25)                           # 0,5 s après la première : pas après la seconde
    assert bul.est_charge() and ocrm.est_charge()
    assert _attendre(lambda: not bul.est_charge())


def test_a_zero_rien_ne_se_decharge_seul(monkeypatch):
    monkeypatch.setattr(modeles, "TTL_MODELES", 0)
    _charger_factices()
    modeles.signaler_usage()
    assert modeles._minuterie is None
    time.sleep(0.1)
    assert bul.est_charge() and ocrm.est_charge()


def test_la_passe_de_bulles_ne_decharge_plus_l_ocr(client, planche, monkeypatch):
    monkeypatch.setattr(main, "bulles_available", lambda: True)
    monkeypatch.setattr(main, "detect_bulles", lambda conn, pid, conf=0.3: {"nb_bulles": 0})
    ocrm._reader = object()
    r = client.post(f"/api/planches/{planche['id']}/detecter-bulles")
    assert r.status_code == 200
    assert ocrm.est_charge(), "le va-et-vient bulles ↔ OCR fragmentait la mémoire"
    assert modeles._minuterie is not None, "la passe arme l'échéance d'inactivité"


def test_la_passe_d_ocr_ne_decharge_plus_les_bulles(client, planche, monkeypatch):
    monkeypatch.setattr(main, "ocr_available", lambda: True)
    monkeypatch.setattr(main, "ocr_planche", lambda conn, pid, only_empty=True: {"ocr": 0})
    bul._model = object()
    r = client.post(f"/api/planches/{planche['id']}/ocr")
    assert r.status_code == 200
    assert bul.est_charge()
    assert modeles._minuterie is not None


def test_une_passe_qui_echoue_arme_aussi_l_echeance(client, planche, monkeypatch):
    """Elle a pu charger son modèle avant d'échouer : sans échéance, il resterait."""
    def boom(*a, **k):
        raise BullesError("explosion")
    monkeypatch.setattr(main, "bulles_available", lambda: True)
    monkeypatch.setattr(main, "detect_bulles", boom)
    assert client.post(f"/api/planches/{planche['id']}/detecter-bulles").status_code == 500
    assert modeles._minuterie is not None


def test_chaque_passe_d_un_lot_repousse_l_echeance(client, planche, monkeypatch):
    monkeypatch.setattr(main, "kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "segment_planche", lambda c, pid: None)
    vus = []
    monkeypatch.setattr(modeles, "signaler_usage", lambda: vus.append(1))
    jid = client.post("/api/jobs", json={"passes": ["segmenter"],
                                         "planche_ids": [planche["id"]]}).json()["id"]
    assert _attendre(lambda: client.get(f"/api/jobs/{jid}").json()["status"] != "en_cours")
    assert vus == [1]


def test_une_echeance_deja_partie_ne_decharge_pas_un_modele_qui_vient_de_servir(monkeypatch):
    """`cancel()` ne rattrape pas une minuterie déjà partie : elle se réveille alors juste
    après une passe. Le contrôle de l'âge la fait se réarmer au lieu de décharger (on
    l'appelle directement, comme si elle avait échappé à l'annulation)."""
    monkeypatch.setattr(modeles, "TTL_MODELES", 10)
    _charger_factices()
    modeles.signaler_usage()
    modeles._echoir()
    assert bul.est_charge() and ocrm.est_charge()
    assert modeles._minuterie is not None, "elle se réarme pour le temps qui reste"
