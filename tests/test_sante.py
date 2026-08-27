"""SANTE-1 — contrôle RAPIDE vs PROFOND des moteurs, et contrat d'image.

Le contrôle rapide (`find_spec`) ne voit pas une incompatibilité binaire : le 2026-08-27
`/api/sante` a annoncé `bulles: true` sur une pile dont le premier `import ultralytics`
levait une exception, et `kumiko: true` alors que la passe 1 renvoyait 500. Ces tests
verrouillent la séparation des deux profondeurs, et surtout que le contrôle profond
RAPPORTE la panne au lieu de la taire.
"""
import sante


# --------------------------------------------------------------------------- #
# La route garde son contrat historique
# --------------------------------------------------------------------------- #
def test_sante_rapide_garde_ses_clefs(client):
    """L'UI appelle cette route à chaque chargement : ses clefs ne bougent pas."""
    d = client.get("/api/sante").json()
    assert set(d) == {"kumiko", "bulles", "ocr", "lemmes", "modeles_charges"}
    assert all(isinstance(d[k], bool) for k in ("kumiko", "bulles", "ocr", "lemmes"))


def test_sante_rapide_n_importe_rien(client, monkeypatch):
    """Le contrôle rapide ne doit RIEN importer : c'est sa raison d'être (torch coûte
    plusieurs secondes). On le prouve en faisant exploser le contrôle profond — la route
    rapide ne doit pas le toucher."""
    def boum(_):
        raise AssertionError("le contrôle rapide a déclenché un import profond")
    monkeypatch.setattr(sante, "profond", boum)
    assert client.get("/api/sante").status_code == 200


def test_sante_profond_absent_par_defaut(client):
    assert "profond" not in client.get("/api/sante").json()


# --------------------------------------------------------------------------- #
# Le contrôle profond
# --------------------------------------------------------------------------- #
def test_sante_profond_sur_demande(client, monkeypatch):
    monkeypatch.setattr(sante, "rapport", lambda moteurs=None: {
        "kumiko": {"ok": True, "erreur": None},
        "bulles": {"ok": True, "erreur": None},
        "ocr": {"ok": True, "erreur": None},
        "nlp": {"ok": True, "erreur": None}})
    d = client.get("/api/sante?profond=1").json()
    assert set(d["profond"]) == {"kumiko", "bulles", "ocr", "nlp"}
    assert all(v["ok"] for v in d["profond"].values())


def test_profond_rapporte_la_cause(monkeypatch):
    """Un moteur cassé doit dire POURQUOI : sans la cause, un opérateur à distance n'a
    aucun moyen de diagnostiquer — c'est tout l'intérêt face au contrôle rapide."""
    sante._reset()
    def casse():
        raise RuntimeError("operator torchvision::nms does not exist")
    monkeypatch.setitem(sante._CONTROLES, "bulles", casse)
    r = sante.profond("bulles")
    assert r["ok"] is False
    assert "torchvision::nms" in r["erreur"]
    assert r["erreur"].startswith("RuntimeError")


def test_profond_memoise(monkeypatch):
    """Mémoïsé : on ne recharge pas torch à chaque appel."""
    sante._reset()
    appels = []
    monkeypatch.setitem(sante._CONTROLES, "ocr", lambda: appels.append(1))
    sante.profond("ocr")
    sante.profond("ocr")
    assert len(appels) == 1


def test_profond_borne_le_message(monkeypatch):
    """Une exception bavarde ne doit pas noyer la réponse."""
    sante._reset()
    def bavard():
        raise RuntimeError("x" * 5000)
    monkeypatch.setitem(sante._CONTROLES, "nlp", bavard)
    assert len(sante.profond("nlp")["erreur"]) <= 300


# --------------------------------------------------------------------------- #
# Ce que le contrôle rapide NE PEUT PAS voir — la raison d'être du profond
# --------------------------------------------------------------------------- #
def test_kumiko_profond_refuse_opencv_5(monkeypatch):
    """OpenCV 5 s'importe parfaitement et casse Kumiko ensuite (`HoughLinesP` renvoie
    (N, 4) au lieu de (N, 1, 4)). `find_spec` n'y voit rien ; le profond doit refuser."""
    sante._reset()
    import cv2
    monkeypatch.setattr(cv2, "__version__", "5.0.0", raising=False)
    r = sante.profond("kumiko")
    assert r["ok"] is False and "5.0.0" in r["erreur"]


def test_kumiko_profond_accepte_opencv_4(monkeypatch):
    sante._reset()
    import cv2
    monkeypatch.setattr(cv2, "__version__", "4.13.0", raising=False)
    assert sante.profond("kumiko")["ok"] is True


# --------------------------------------------------------------------------- #
# Contrat d'image
# --------------------------------------------------------------------------- #
def test_moteurs_declares_et_controles_coincident():
    """Tout moteur annoncé doit avoir un contrôle, sinon `--exiger` le nommerait sans
    jamais le vérifier — un vert qui ne mesure rien, précisément ce qu'on corrige ici."""
    assert set(sante.MOTEURS) == set(sante._CONTROLES)
