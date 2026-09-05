"""SANTE-1 — contrôle RAPIDE vs PROFOND des moteurs, et contrat d'image.

Le contrôle rapide (`find_spec`) ne voit pas une incompatibilité binaire : le 2026-08-27
`/api/sante` a annoncé `bulles: true` sur une pile dont le premier `import ultralytics`
levait une exception, et `kumiko: true` alors que la passe 1 renvoyait 500. Ces tests
verrouillent la séparation des deux profondeurs, et surtout que le contrôle profond
RAPPORTE la panne au lieu de la taire.
"""
import re
from pathlib import Path

import pytest

import sante
from conftest import requires_kumiko


# --------------------------------------------------------------------------- #
# La route garde son contrat historique
# --------------------------------------------------------------------------- #
def test_sante_rapide_garde_ses_clefs(client):
    """Sondes de conteneur et panneau 🩺 Moteurs en dépendent : ses clefs ne bougent pas."""
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
    (N, 4) au lieu de (N, 1, 4)). `find_spec` n'y voit rien ; le profond doit refuser.

    `importorskip` et non le marqueur Kumiko : ce test-ci n'a besoin QUE de cv2 — il
    truque la version, il n'appelle jamais le script. Le marqueur exigerait en plus le
    clone `lib/kumiko`, et le ferait taire là où il sait encore mesurer (QA-6).
    """
    cv2 = pytest.importorskip("cv2", reason="OpenCV non installé")
    sante._reset()
    monkeypatch.setattr(cv2, "__version__", "5.0.0", raising=False)
    r = sante.profond("kumiko")
    assert r["ok"] is False and "5.0.0" in r["erreur"]


@requires_kumiko
def test_kumiko_profond_accepte_opencv_4(monkeypatch):
    """Le marqueur ici, parce que l'attendu est `ok is True` : il exige cv2 ET le point
    d'entrée `lib/kumiko`, que `_verifier_kumiko` vérifie avant la version. Sans garde,
    l'`import cv2` faisait ÉCHOUER la suite d'une installation noyau au lieu de la
    skipper — un rouge qui envoie chercher une régression là où un moteur manque
    légitimement (QA-6, mesuré le 2026-09-05)."""
    import cv2
    sante._reset()
    monkeypatch.setattr(cv2, "__version__", "4.13.0", raising=False)
    assert sante.profond("kumiko")["ok"] is True


# --------------------------------------------------------------------------- #
# Contrat d'image
# --------------------------------------------------------------------------- #
def test_moteurs_declares_et_controles_coincident():
    """Tout moteur annoncé doit avoir un contrôle, sinon `--exiger` le nommerait sans
    jamais le vérifier — un vert qui ne mesure rien, précisément ce qu'on corrige ici."""
    assert set(sante.MOTEURS) == set(sante._CONTROLES)


# --------------------------------------------------------------------------- #
# Le panneau de l'UI (SANTE-1) — un inventaire qui traverse la frontière HTTP
# --------------------------------------------------------------------------- #
# La RÈGLE d'affichage (présent ≠ opérationnel, absent ≠ en panne) se vérifie sous Node,
# dans `tests/js/sante.test.js` : elle est pure, et une table de vérité la dit mieux
# qu'aucune lecture de source. Ce qui reste ici est ce que Node ne peut pas savoir — que
# le panneau et le SERVEUR parlent des mêmes moteurs.
_TABLE_JS = re.compile(r'\{\s*cle:\s*"(\w+)",\s*rapide:\s*"(\w+)"')
_STATIC = Path(__file__).resolve().parent.parent / "static"


def _table_du_panneau() -> dict:
    """Les paires (moteur profond → clef rapide) déclarées par `static/lib/sante.js`."""
    return dict(_TABLE_JS.findall((_STATIC / "lib" / "sante.js").read_text(
        encoding="utf-8")))


def test_le_panneau_connait_tous_les_moteurs(client):
    """Le panneau apparie deux jeux de clefs que rien ne force à coïncider : le contrôle
    profond dit `nlp`, la route historique dit `lemmes`, et le contrat public de
    `/api/sante` interdit de renommer l'un pour l'autre.

    Cet appariement vit côté client, donc hors de portée de tout test Python — et c'est
    exactement là que se logent les pannes muettes : renommer un moteur en Python
    laisserait un panneau qui n'affiche RIEN pour lui, sans une erreur nulle part. Le
    test traverse donc la frontière et lit la table du JS."""
    table = _table_du_panneau()
    assert table, "table MOTEURS introuvable dans static/lib/sante.js"
    assert set(table) == set(sante.MOTEURS), (
        "le panneau et `sante.MOTEURS` ne parlent pas des mêmes moteurs : "
        f"{sorted(set(table) ^ set(sante.MOTEURS))}")
    rapide = set(client.get("/api/sante").json()) - {"modeles_charges"}
    manquantes = set(table.values()) - rapide
    assert not manquantes, (
        f"le panneau lit des clefs que `/api/sante` ne renvoie pas : {sorted(manquantes)}")


# « Ouvrir le panneau n'éprouve pas les moteurs » a d'abord été écrit ici, en cherchant le
# mot « profond » dans le source d'`openSante`. La mutation qui compte — `openSante`
# appelant `santeEprouver()` — laissait le test VERT : le mot n'y était toujours pas.
# L'affirmation porte sur ce que la page fait, elle a donc migré dans
# `tests/test_e2e_sante.py`, où un navigateur compte les appels. Deux tests pour la même
# chose auraient été pires qu'un : on aurait fini par croire le moins cher.

def test_la_page_charge_le_module_du_panneau():
    """`corpus.js` appelle `BDSante` : sans la balise, le panneau lève une ReferenceError
    au premier clic. Un oubli de <script> ne casse aucun test Python et aucun test Node —
    les deux voient le module, seul le navigateur ne le verrait pas."""
    html = (Path(__file__).resolve().parent.parent / "templates" / "corpus.html").read_text(
        encoding="utf-8")
    assert "/static/lib/sante.js" in html
    assert "BDSante" in (_STATIC / "corpus.js").read_text(encoding="utf-8")


def test_le_panneau_renvoie_a_une_section_qui_existe():
    """Le bilan du panneau ne se contente pas de dire « en panne », il dit où aller —
    sinon l'opérateur est exactement où il était, avec un mot de plus. Encore faut-il que
    la section existe : un renvoi vers un titre renommé est pire qu'aucun renvoi, parce
    qu'il fait chercher."""
    js = (_STATIC / "lib" / "sante.js").read_text(encoding="utf-8")
    doc = (Path(__file__).resolve().parent.parent / "docs"
           / "deploiement-docker.md").read_text(encoding="utf-8")
    assert "« Un moteur en panne »" in js, (
        "le bilan ne renvoie plus nulle part")
    assert "## 8. Un moteur en panne" in doc


def test_la_doc_dit_quoi_faire_de_chaque_panne_connue():
    """Les trois pannes ont été RENCONTRÉES, pas imaginées : chacune doit avoir son
    remède écrit. Une doc qui décrit le symptôme sans le geste laisse l'opérateur devant
    un message d'erreur exact et une page qui le lui répète."""
    doc = (Path(__file__).resolve().parent.parent / "docs"
           / "deploiement-docker.md").read_text(encoding="utf-8")
    for symptome, remede in (("torchvision::nms", "download.pytorch.org/whl/cpu"),
                             ("OpenCV 5", "grep -i opencv"),
                             ("E050", "spacy download")):
        assert symptome in doc, f"panne non documentée : {symptome}"
        assert remede in doc, f"panne documentée sans remède : {symptome}"
    # La mémoïsation par processus : sans elle écrite, une réparation à chaud paraît
    # sans effet, et le panneau passe pour cassé au moment où il vient de servir.
    assert "restart app" in doc
