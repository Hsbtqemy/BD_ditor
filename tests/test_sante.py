"""SANTE-1 — contrôle RAPIDE vs PROFOND des moteurs, et contrat d'image.

Le contrôle rapide (`find_spec`) ne voit pas une incompatibilité binaire : le 2026-08-27
`/api/sante` a annoncé `bulles: true` sur une pile dont le premier `import ultralytics`
levait une exception, et `kumiko: true` alors que la passe 1 renvoyait 500. Ces tests
verrouillent la séparation des deux profondeurs, et surtout que le contrôle profond
RAPPORTE la panne au lieu de la taire.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import sante
from conftest import requires_kumiko

_RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def ici(monkeypatch):
    """L'épreuve dans CE processus : les tests qui truquent `_CONTROLES`, `cv2` ou le point
    d'entrée de Kumiko le font ici, et le processus d'à côté ne le verrait pas."""
    monkeypatch.setattr(sante, "_eprouver", sante._eprouver_ici)


# --------------------------------------------------------------------------- #
# La route garde son contrat historique
# --------------------------------------------------------------------------- #
def test_sante_rapide_garde_ses_clefs(client):
    """Sondes de conteneur et panneau 🩺 Moteurs en dépendent : ses clefs ne bougent pas."""
    d = client.get("/api/sante").json()
    assert set(d) == {"kumiko", "bulles", "ocr", "lemmes", "modeles_charges", "en_veille"}
    assert all(isinstance(d[k], bool) for k in ("kumiko", "bulles", "ocr", "lemmes"))
    # NLP-4 : une clef AJOUTÉE, une liste — les quatre booléens d'avant n'ont pas bougé.
    assert isinstance(d["en_veille"], list)


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


def test_profond_rapporte_la_cause(monkeypatch, ici):
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


def test_profond_memoise(monkeypatch, ici):
    """Mémoïsé : on ne recharge pas torch à chaque appel."""
    sante._reset()
    appels = []
    monkeypatch.setitem(sante._CONTROLES, "ocr", lambda: appels.append(1))
    sante.profond("ocr")
    sante.profond("ocr")
    assert len(appels) == 1


def test_profond_borne_le_message(monkeypatch, ici):
    """Une exception bavarde ne doit pas noyer la réponse."""
    sante._reset()
    def bavard():
        raise RuntimeError("x" * 5000)
    monkeypatch.setitem(sante._CONTROLES, "nlp", bavard)
    assert len(sante.profond("nlp")["erreur"]) <= 300


# --------------------------------------------------------------------------- #
# Ce que le contrôle rapide NE PEUT PAS voir — la raison d'être du profond
# --------------------------------------------------------------------------- #
def test_kumiko_profond_refuse_opencv_5(monkeypatch, tmp_path, ici):
    """OpenCV 5 s'importe parfaitement et casse Kumiko ensuite (`HoughLinesP` renvoie
    (N, 4) au lieu de (N, 1, 4)). `find_spec` n'y voit rien ; le profond doit refuser.

    `importorskip` et non le marqueur Kumiko : ce test-ci n'a besoin QUE de cv2 — il
    truque la version, il n'appelle jamais le script. Le marqueur exigerait en plus le
    clone `lib/kumiko`, et le ferait taire là où il sait encore mesurer (QA-6).

    Le point d'entrée est donc POSÉ : `_verifier_kumiko` le cherche avant la version, et
    sans lui le test échouait sur « point d'entrée absent » dans une copie sans clone
    (2026-11-12).
    """
    cv2 = pytest.importorskip("cv2", reason="OpenCV non installé")
    import pipeline.segmentation as seg
    entree = tmp_path / "kumiko"
    entree.write_text("", encoding="utf-8")
    monkeypatch.setattr(seg, "KUMIKO_ENTRY", entree)
    sante._reset()
    monkeypatch.setattr(cv2, "__version__", "5.0.0", raising=False)
    r = sante.profond("kumiko")
    assert r["ok"] is False and "5.0.0" in r["erreur"]


@requires_kumiko
def test_kumiko_profond_accepte_opencv_4(monkeypatch, ici):
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
# L'épreuve profonde ne laisse rien dans l'application (CONC-2, 2026-11-26)
# --------------------------------------------------------------------------- #
_LOURDS = ("torch", "cv2", "ultralytics", "easyocr", "spacy", "thinc")

_MESURE = (
    "import json, sys\n"
    f"sys.path.insert(0, {str(_RACINE)!r})\n"
    "import sante\n"
    "r = sante.rapport()\n"
    f"print(json.dumps({{'rapport': r, 'charges': [m for m in {_LOURDS!r} "
    "if m in sys.modules]}))\n")


def test_l_epreuve_profonde_ne_charge_rien_dans_l_application():
    """Mesuré en production le 2026-11-26 : après le contrôle de déploiement, qui joue
    `/api/sante?profond=1`, l'application tenait 440 Mo et `/proc/1/maps` portait torch,
    torchvision et cv2 — contre 78 Mo juste après un redémarrage. L'épreuve se joue donc
    dans un processus à part, et celui qui l'appelle n'importe AUCUN moteur.

    Mesuré dans un processus NEUF : celui de la suite a déjà importé cv2 ou torch par
    d'autres tests, et n'y verrait rien. Les moteurs présents doivent répondre `ok` : un
    processus d'à côté qui n'éprouverait rien rendrait ce test vert pour rien."""
    fini = subprocess.run([sys.executable, "-c", _MESURE], cwd=str(_RACINE),
                          capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert fini.returncode == 0, fini.stderr[-2000:]
    d = json.loads(fini.stdout.strip().splitlines()[-1])
    assert d["charges"] == [], f"l'épreuve a chargé dans l'application : {d['charges']}"
    for moteur, module in (("bulles", "ultralytics"), ("ocr", "easyocr"), ("nlp", "spacy")):
        if importlib.util.find_spec(module):
            assert d["rapport"][moteur]["ok"] is True, d["rapport"][moteur]


def test_l_epreuve_d_a_cote_rapporte_la_cause():
    """La panne vient du processus d'à côté avec son type et son message, comme avant."""
    r = sante._eprouver_a_part("moteur-inconnu")
    assert r == {"ok": False, "erreur": "KeyError: 'moteur-inconnu'"}


@pytest.mark.parametrize("code, sortie, erreurs, attendu", [
    (-9, "", "", "code -9) : aucune sortie"),                    # tué : l'OOM, par exemple
    (1, "", "ligne\nImportError: libtorch.so", "code 1) : ImportError: libtorch.so"),
    (0, "pas du json", "", "code 0) : aucune sortie"),
    (0, '{"erreur": null}', "", "sans répondre"),                # pas de `ok` : pas une réponse
])
def test_une_epreuve_qui_meurt_sans_repondre_est_une_panne(code, sortie, erreurs, attendu):
    r = sante._lire_reponse(code, sortie, erreurs)
    assert r["ok"] is False and attendu in r["erreur"] and len(r["erreur"]) <= 300


def test_la_reponse_est_la_derniere_ligne():
    """Une bibliothèque peut écrire pendant son import : la réponse est la dernière ligne."""
    r = sante._lire_reponse(0, 'Downloading…\n{"ok": false, "erreur": "X: y"}\n', "")
    assert r == {"ok": False, "erreur": "X: y"}


def test_une_reponse_lue_fait_foi_meme_si_le_processus_tombe_ensuite():
    """L'épreuve a répondu ; tomber en rendant ses bibliothèques n'en fait pas une panne."""
    assert sante._lire_reponse(-11, '{"ok": true, "erreur": null}', "Segmentation fault") \
        == {"ok": True, "erreur": None}


def test_une_epreuve_trop_longue_est_une_panne(monkeypatch):
    def lent(*a, **k):
        raise subprocess.TimeoutExpired(a[0], sante.DELAI_EPREUVE)
    monkeypatch.setattr(sante.subprocess, "run", lent)
    r = sante._eprouver_a_part("bulles")
    assert r["ok"] is False and f"{sante.DELAI_EPREUVE} s" in r["erreur"]


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
    """`administration.js` appelle `BDSante` : sans la balise, le panneau lève une
    ReferenceError au premier rendu. Un oubli de <script> ne casse aucun test Python et
    aucun test Node — les deux voient le module, seul le navigateur ne le verrait pas.

    La page a CHANGÉ le 2026-09-07 : le panneau des moteurs a quitté la Bibliothèque pour
    `/administration` (UX-10). Ce test l'a signalé de lui-même en devenant rouge, ce qui
    est exactement ce qu'on lui demande — il suit le panneau, pas l'écran d'hier.
    """
    html = (Path(__file__).resolve().parent.parent / "templates"
            / "administration.html").read_text(encoding="utf-8")
    assert "/static/lib/sante.js" in html
    assert "BDSante" in (_STATIC / "administration.js").read_text(encoding="utf-8")
    # Et il ne doit PLUS être chargé là où il ne sert plus : un <script> orphelin coûte une
    # requête et fait croire que le panneau est encore là.
    corpus = (Path(__file__).resolve().parent.parent / "templates" / "corpus.html").read_text(
        encoding="utf-8")
    assert "/static/lib/sante.js" not in corpus


def test_le_panneau_se_lit_par_un_arrivant():
    """UX-6 — le panneau est ce que la visite de l'Administration montre à un arrivant :
    l'écran ne lui dit ni « 503 » (un code du protocole) ni « contrôle de présence » (une
    notion du serveur). L'explication vit en infobulle, et pour un lecteur d'écran à côté
    d'elle — l'écran reste stable. Ce test lit le bloc tel qu'il s'affiche : le gabarit
    hors commentaires et hors attributs, puis les attributs `title` à part."""
    html = (Path(__file__).resolve().parent.parent / "templates"
            / "administration.html").read_text(encoding="utf-8")
    bloc = re.search(r'<section[^>]*id="sante-bloc".*?</section>', html, re.DOTALL).group(0)
    bloc = re.sub(r"<!--.*?-->", "", bloc, flags=re.DOTALL)
    visible = re.sub(r"<[^>]+>", " ", bloc)
    for mot in ("503", "contrôle de présence"):
        assert mot not in visible, f"le panneau des moteurs dit encore « {mot} »"
    # Les phrases sont parties en infobulle, pas disparues : le « pourquoi » d'Éprouver et
    # ce qu'un moteur absent fait reste lisible au survol et au lecteur d'écran.
    titres = " ".join(re.findall(r'title="([^"]*)"', bloc))
    assert "refusée" in titres and "Charge réellement" in titres
    assert "aria-describedby=\"sante-eprouver-aide\"" in bloc
    # La phrase à l'écran est COURTE : des mots, pas un paragraphe.
    intro = re.search(r'<p[^>]*id="sante-intro"[^>]*>(.*?)<span', bloc, re.DOTALL).group(1)
    assert len(" ".join(intro.split())) <= 60, intro
    # Et le module ne le dit pas davantage : la note d'un moteur absent, et le bilan.
    module = (_STATIC / "lib" / "sante.js").read_text(encoding="utf-8")
    chaines = " ".join(re.findall(r'"([^"\n]*)"', module))
    assert "503" not in chaines, "une note du panneau dit encore « 503 »"


def test_le_panneau_renvoie_a_une_section_qui_existe():
    """Le bilan du panneau ne se contente pas de dire « en panne », il dit où aller —
    sinon l'opérateur est exactement où il était, avec un mot de plus. Encore faut-il que
    la section existe : un renvoi vers un titre renommé est pire qu'aucun renvoi, parce
    qu'il fait chercher.

    Le contrôle porte sur le TITRE et non sur le numéro, corrigé le 2026-09-07. Il exigeait
    `## 8. Un moteur en panne` et a échoué le jour où une section a été INSÉRÉE plus haut —
    un renumérotage qui ne déplace pas la cible d'un pouce et ne trompe personne. Il aurait
    fini par se faire relâcher pour la mauvaise raison, alors que ce qu'il garde est juste :
    l'écran nomme une section, et cette section doit exister sous ce nom. C'est la même
    règle que pour les renvois de `CLAUDE.md` — citer par section, jamais par numéro, parce
    qu'un numéro désigne ce qui a glissé dessous."""
    js = (_STATIC / "lib" / "sante.js").read_text(encoding="utf-8")
    doc = (Path(__file__).resolve().parent.parent / "docs"
           / "deploiement-docker.md").read_text(encoding="utf-8")
    assert "« Un moteur en panne »" in js, (
        "le bilan ne renvoie plus nulle part")
    assert re.search(r"^## \d+\. Un moteur en panne\s*$", doc, re.M), (
        "l'écran renvoie à « Un moteur en panne » et aucun titre de `deploiement-docker.md` "
        "ne porte ce nom : le renvoi fait chercher au lieu de conduire")


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
