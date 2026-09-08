"""Tests unitaires du wrapper Kumiko (subprocess mocké, sans lancer Kumiko)."""
import json
import subprocess
import time
from pathlib import Path

import pytest

import database
import pipeline.segmentation as seg
from pipeline import interruption
from pipeline.segmentation import (KumikoError, _normalize_panel, run_kumiko,
                                   segment_planche)


def test_normalize_panel_liste():
    assert _normalize_panel([10.4, 20.6, 30, 40]) == (10, 21, 30, 40)


def test_normalize_panel_dict_xywh():
    assert _normalize_panel({"x": 1, "y": 2, "w": 3, "h": 4}) == (1, 2, 3, 4)


def test_normalize_panel_dict_coords():
    assert _normalize_panel({"coords": [5, 6, 7, 8]}) == (5, 6, 7, 8)


def test_normalize_panel_forme_invalide_leve_kumikoerror():
    with pytest.raises(KumikoError):
        _normalize_panel({"inattendu": True})
    with pytest.raises(KumikoError):
        _normalize_panel([1, 2])  # pas assez de valeurs


# ---- run_kumiko : chemins d'erreur, avec `subprocess.Popen` mocké ---- #
#
# La doublure portait sur `subprocess.run`. CONC-1 l'a remplacé par `Popen` + une attente
# par tranches, seule forme qui laisse interroger l'interrupteur entre deux tranches : la
# doublure suit le mécanisme, puisque c'est lui qu'elle simule. Elle expose donc ce que le
# code appelle vraiment — `communicate(timeout=…)`, `returncode`, `poll()`, `kill()` — et
# `tue` retient si l'enfant a été tué, ce dont dépend le test d'orphelin.
class _FauxProc:
    def __init__(self, args, write=None, returncode=0, stderr="", timeouts=0):
        self.args, self._write, self._stderr = args, write, stderr
        self.returncode = None
        self._code, self._restant, self.tue = returncode, timeouts, False

    def communicate(self, timeout=None):
        if self._restant > 0:              # tranches d'attente avant la fin
            self._restant -= 1
            raise subprocess.TimeoutExpired(cmd="kumiko", timeout=timeout)
        if self._write is not None:
            Path(self.args[self.args.index("-o") + 1]).write_text(
                self._write, encoding="utf-8")
        self.returncode = self._code
        return "", self._stderr

    def poll(self):
        return self.returncode

    def kill(self):
        self.tue = True
        self.returncode = -9


def _fake_popen(**kw):
    """Remplace `subprocess.Popen` ; garde le dernier processus créé sous `.dernier`."""
    def popen(args, **_):
        popen.dernier = _FauxProc(args, **kw)
        return popen.dernier
    popen.dernier = None
    return popen


@pytest.fixture
def kumiko_on(monkeypatch):
    monkeypatch.setattr(seg, "kumiko_available", lambda: True)


def test_run_kumiko_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(seg, "kumiko_available", lambda: False)
    with pytest.raises(KumikoError, match="introuvable"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_code_retour_non_nul(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "Popen",
                        _fake_popen(returncode=1, stderr="boom"))
    with pytest.raises(KumikoError, match="échoué"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_timeout(monkeypatch, kumiko_on, tmp_path):
    """Le délai TOTAL est épuisé — l'enfant est tué, et le message le dit."""
    monkeypatch.setattr(seg, "DELAI_KUMIKO", 0.05)
    monkeypatch.setattr(seg, "PAS_INTERRUPTION", 0.01)
    faux = _fake_popen(timeouts=10 ** 9)         # ne finit JAMAIS : c'est l'horloge qui
                                                 # doit trancher, pas un compte de tranches
                                                 # (à 10 000 la doublure cédait la première)
    monkeypatch.setattr(seg.subprocess, "Popen", faux)
    with pytest.raises(KumikoError, match="délai"):
        run_kumiko(tmp_path / "x.png")
    assert faux.dernier.tue, "un enfant qui dépasse le délai ne doit pas rester orphelin"


def test_run_kumiko_json_invalide(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "Popen", _fake_popen(write="pas du json"))
    with pytest.raises(KumikoError, match="illisible"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_sans_clef_panels(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "Popen",
                        _fake_popen(write=json.dumps([{"size": [1, 1]}])))
    with pytest.raises(KumikoError, match="panels"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_succes(monkeypatch, kumiko_on, tmp_path):
    page = [{"size": [10, 20], "panels": [[0, 0, 5, 5]]}]
    monkeypatch.setattr(seg.subprocess, "Popen", _fake_popen(write=json.dumps(page)))
    assert run_kumiko(tmp_path / "x.png")["panels"] == [[0, 0, 5, 5]]


def test_segment_planche_inexistante(data_dir):
    conn = database.get_connection()
    try:
        with pytest.raises(ValueError):
            segment_planche(conn, 999)
    finally:
        conn.close()


# ---- préservation du travail humain à la re-segmentation ---- #
def test_reattach_orphans(data_dir):
    conn = database.get_connection()
    try:
        conn.execute("INSERT INTO albums (titre) VALUES ('A')")
        aid = conn.execute("SELECT id FROM albums").fetchone()["id"]
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web, "
                     "largeur_px, hauteur_px) VALUES (?, 1, 'x.jpg', 400, 500)", (aid,))
        pid = conn.execute("SELECT id FROM planches").fetchone()["id"]
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h) "
                     "VALUES (?, 'case', 0, 0, 100, 100)", (pid,))
        cid = conn.execute("SELECT id FROM regions WHERE type='case'").fetchone()["id"]
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, parent_id) "
                     "VALUES (?, 'bulle', 10, 10, 20, 20, NULL)", (pid,))   # dans la case
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, parent_id) "
                     "VALUES (?, 'bulle', 300, 300, 20, 20, NULL)", (pid,))  # dehors
        assert seg._reattach_orphans(conn, pid) == 1
        dedans = conn.execute("SELECT parent_id FROM regions WHERE x=10").fetchone()["parent_id"]
        dehors = conn.execute("SELECT parent_id FROM regions WHERE x=300").fetchone()["parent_id"]
        assert dedans == cid and dehors is None
        conn.execute("DELETE FROM regions WHERE type='case'")
        assert seg._reattach_orphans(conn, pid) == 0          # aucune case → no-op
    finally:
        conn.close()


def test_transfer_case_annotations(data_dir):
    conn = database.get_connection()
    try:
        conn.execute("INSERT INTO albums (titre) VALUES ('A')")
        aid = conn.execute("SELECT id FROM albums").fetchone()["id"]
        conn.execute("INSERT INTO planches (album_id, numero, chemin_web, "
                     "largeur_px, hauteur_px) VALUES (?, 1, 'x.jpg', 400, 500)", (aid,))
        pid = conn.execute("SELECT id FROM planches").fetchone()["id"]

        def case(x, y, w, h):
            return conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                                "VALUES (?, 'case', ?, ?, ?, ?, 'kumiko')",
                                (pid, x, y, w, h)).lastrowid

        a1 = case(0, 0, 100, 100); conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'ANN1')", (a1,))
        a2 = case(900, 900, 50, 50); conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'ANN2')", (a2,))
        a3 = case(0, 0, 30, 30)            # pas d'annotation
        n1 = case(5, 5, 100, 100)          # nouvelle case (recouvre a1)
        olds = [{"id": a1, "x": 0, "y": 0, "w": 100, "h": 100},
                {"id": a2, "x": 900, "y": 900, "w": 50, "h": 50},   # aucune nouvelle ne recouvre
                {"id": a3, "x": 0, "y": 0, "w": 30, "h": 30}]
        news = [{"id": n1, "x": 5, "y": 5, "w": 100, "h": 100}]
        assert seg._transfer_case_annotations(conn, olds, news) == [a1]   # seul a1 transféré
        assert conn.execute("SELECT note FROM annotations WHERE region_id=?", (n1,)).fetchone()["note"] == "ANN1"
        assert conn.execute("SELECT 1 FROM annotations WHERE region_id=?", (a2,)).fetchone() is not None  # gardée (pas de cible)
        # cible déjà annotée → on ne transfère pas (UNIQUE) ; et _best_overlap sans recouvrement
        assert seg._transfer_case_annotations(
            conn, [{"id": a2, "x": 5, "y": 5, "w": 100, "h": 100}], news) == []
        assert seg._best_overlap({"x": 999, "y": 999, "w": 1, "h": 1}, news) is None
    finally:
        conn.close()


def test_resegmentation_transfere_annotation_case(client, planche, monkeypatch):
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 400, 500]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    client.put(f"/api/regions/{case['id']}/annotation",
               json={"note": "SCENENUIT", "tags": ["nuit"]})
    # re-segmentation : une nouvelle case recouvrant l'ancienne → annotation transférée
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 400, 480]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    assert res["annotations_transferees"] == 1
    new_case = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    ann = client.get(f"/api/regions/{new_case['id']}/annotation").json()
    assert ann["note"] == "SCENENUIT" and "nuit" in [t["label"] for t in ann["tags"]]
    res2 = client.get("/api/recherche", params={"q": "nuit"}).json()["results"]
    assert any(r["region_id"] == new_case["id"] for r in res2)   # cherchable, sur la nouvelle case


def test_resegmentation_conserve_case_annotee_sans_recouvrement(client, planche, monkeypatch):
    """Une case annotée que la nouvelle segmentation NE recouvre PAS est
    CONSERVÉE (et non supprimée) : aucune perte d'annotation."""
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 50, 50]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    client.put(f"/api/regions/{case['id']}/annotation",
               json={"note": "ZONEORPHELINE", "tags": ["isole"]})
    # re-segmentation : la nouvelle case ne recouvre PAS l'ancienne case annotée
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[300, 400, 50, 50]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    assert res["annotations_transferees"] == 0 and res["annotations_preservees"] == 1
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    assert any(x["id"] == case["id"] for x in regions)          # ancienne case SURVIT
    res2 = client.get("/api/recherche", params={"q": "ZONEORPHELINE"}).json()["results"]
    assert any(r["region_id"] == case["id"] for r in res2)      # annotation cherchable, in situ


def test_resegmentation_preserve_ocr(client, planche, monkeypatch):
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko",
                        lambda path: {"size": [400, 500], "panels": [[0, 0, 400, 500]]})
    client.post(f"/api/planches/{planche['id']}/segmenter")
    case1 = next(x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case")
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 50, "y": 60, "w": 80, "h": 40,
                              "parent_id": case1["id"], "ocr_texte": "DIALOGUE",
                              "source": "auto"}).json()
    # re-segmentation : 2 nouvelles cases → la bulle océrisée survit + se ré-rattache
    monkeypatch.setattr(seg, "run_kumiko", lambda path: {
        "size": [400, 500], "panels": [[0, 0, 200, 500], [200, 0, 200, 500]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    regions = client.get(f"/api/planches/{planche['id']}/regions").json()
    surv = next((x for x in regions if x["id"] == bulle["id"]), None)
    assert surv is not None and surv["ocr_texte"] == "DIALOGUE"         # OCR préservé
    new_case = next(x for x in regions if x["type"] == "case" and x["x"] == 0)
    assert surv["parent_id"] == new_case["id"] and res["reattaches"] >= 1


# ---- SEG-1 : préservation à la re-segmentation (S3 / S2 / S7) ---- #
def _planche_vide(conn):
    """Crée un album + une planche 400×500, renvoie son id."""
    conn.execute("INSERT INTO albums (titre) VALUES ('A')")
    aid = conn.execute("SELECT id FROM albums ORDER BY id DESC LIMIT 1").fetchone()["id"]
    conn.execute("INSERT INTO planches (album_id, numero, chemin_web, largeur_px, hauteur_px) "
                 "VALUES (?, 1, 'x.jpg', 400, 500)", (aid,))
    return conn.execute("SELECT id FROM planches ORDER BY id DESC LIMIT 1").fetchone()["id"]


def test_seg_s3_seuil_recouvrement(data_dir):
    """S3 : une annotation NE migre PAS vers une case qui ne recouvre presque pas
    l'ancienne (recouvrement < seuil) — l'ancienne case annotée est conservée."""
    conn = database.get_connection()
    try:
        pid = _planche_vide(conn)
        old = conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                           "VALUES (?, 'case', 0, 0, 100, 100, 'kumiko')", (pid,)).lastrowid
        conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'GARDE')", (old,))
        new = conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                           "VALUES (?, 'case', 95, 95, 100, 100, 'kumiko')", (pid,)).lastrowid
        olds = [{"id": old, "x": 0, "y": 0, "w": 100, "h": 100}]
        news = [{"id": new, "x": 95, "y": 95, "w": 100, "h": 100}]   # ne recouvre que 5×5
        assert seg._best_overlap(olds[0], news) is None              # sous le seuil
        assert seg._transfer_case_annotations(conn, olds, news) == []
        assert conn.execute("SELECT note FROM annotations WHERE region_id=?",
                            (old,)).fetchone()["note"] == "GARDE"     # in situ, non perdue
    finally:
        conn.close()


def test_seg_s2_fusion_ambigue_conserve_les_deux(data_dir):
    """S2 : deux anciennes cases annotées FUSIONNÉES en une seule nouvelle → AUCUN
    transfert (ambigu), les deux annotations sont conservées (déterministe, zéro perte)."""
    conn = database.get_connection()
    try:
        pid = _planche_vide(conn)

        def case(x, y, w, h):
            return conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                                "VALUES (?, 'case', ?, ?, ?, ?, 'kumiko')",
                                (pid, x, y, w, h)).lastrowid
        a = case(0, 0, 100, 100); conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'A')", (a,))
        b = case(0, 100, 100, 100); conn.execute("INSERT INTO annotations (region_id, note) VALUES (?, 'B')", (b,))
        n = case(0, 0, 100, 200)                                     # fusionne a + b
        olds = [{"id": a, "x": 0, "y": 0, "w": 100, "h": 100},
                {"id": b, "x": 0, "y": 100, "w": 100, "h": 100}]
        news = [{"id": n, "x": 0, "y": 0, "w": 100, "h": 200}]
        assert seg._transfer_case_annotations(conn, olds, news) == []   # ambigu → rien transféré
        assert conn.execute("SELECT note FROM annotations WHERE region_id=?", (a,)).fetchone()["note"] == "A"
        assert conn.execute("SELECT note FROM annotations WHERE region_id=?", (b,)).fetchone()["note"] == "B"
        assert conn.execute("SELECT 1 FROM annotations WHERE region_id=?", (n,)).fetchone() is None  # nouvelle NON annotée
    finally:
        conn.close()


def test_seg_s7_reattach_nouvelles_cases_seulement(data_dir):
    """S7 : une orpheline dont le centre tombe dans une ancienne case préservée ET une
    nouvelle se rattache à la NOUVELLE (cibles restreintes aux nouvelles cases)."""
    conn = database.get_connection()
    try:
        pid = _planche_vide(conn)
        conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                     "VALUES (?, 'case', 0, 0, 100, 100, 'kumiko')", (pid,))   # ancienne préservée
        new = conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, source) "
                           "VALUES (?, 'case', 0, 0, 100, 100, 'kumiko')", (pid,)).lastrowid
        orph = conn.execute("INSERT INTO regions (planche_id, type, x, y, w, h, parent_id) "
                            "VALUES (?, 'bulle', 10, 10, 20, 20, NULL)", (pid,)).lastrowid
        assert seg._reattach_orphans(conn, pid, [{"id": new, "x": 0, "y": 0, "w": 100, "h": 100}]) == 1
        assert conn.execute("SELECT parent_id FROM regions WHERE id=?",
                            (orph,)).fetchone()["parent_id"] == new   # la NOUVELLE, pas l'ancienne
    finally:
        conn.close()


def test_resegmentation_s2_fusion_conserve_les_deux(client, planche, monkeypatch):
    """S2 bout-en-bout (via segment_planche) : deux cases annotées séparément que la
    re-segmentation FUSIONNE en une seule → les deux anciennes sont CONSERVÉES (zéro
    perte, déterministe) et la nouvelle reste non annotée."""
    monkeypatch.setattr("main.kumiko_available", lambda: True)
    monkeypatch.setattr(seg, "run_kumiko", lambda path: {
        "size": [400, 500], "panels": [[0, 0, 400, 250], [0, 250, 400, 250]]})   # 2 cases
    client.post(f"/api/planches/{planche['id']}/segmenter")
    cases = [x for x in client.get(
        f"/api/planches/{planche['id']}/regions").json() if x["type"] == "case"]
    assert len(cases) == 2
    client.put(f"/api/regions/{cases[0]['id']}/annotation", json={"note": "CASEHAUT", "tags": []})
    client.put(f"/api/regions/{cases[1]['id']}/annotation", json={"note": "CASEBAS", "tags": []})
    # re-segmentation : UNE seule case couvrant les deux (fusion)
    monkeypatch.setattr(seg, "run_kumiko", lambda path: {
        "size": [400, 500], "panels": [[0, 0, 400, 500]]})
    res = client.post(f"/api/planches/{planche['id']}/segmenter").json()
    assert res["annotations_transferees"] == 0 and res["annotations_preservees"] == 2
    ids = {x["id"] for x in client.get(f"/api/planches/{planche['id']}/regions").json()}
    assert cases[0]["id"] in ids and cases[1]["id"] in ids          # les 2 anciennes survivent
    for mot in ("CASEHAUT", "CASEBAS"):                              # annotations cherchables in situ
        assert client.get("/api/recherche", params={"q": mot}).json()["results"]


# ---- CONC-1 : l'annulation atteint le sous-processus ---- #
def test_l_interruption_tue_le_sous_processus(monkeypatch, kumiko_on, tmp_path):
    """L'interrupteur est consulté ENTRE deux tranches d'attente, et l'enfant est tué.

    Doublure ici : on éprouve le chemin de code, pas le système. Le test suivant, lui,
    lance un VRAI processus — les deux sont nécessaires et ne disent pas la même chose.
    """
    monkeypatch.setattr(seg, "PAS_INTERRUPTION", 0.01)
    faux = _fake_popen(timeouts=10 ** 9)
    monkeypatch.setattr(seg.subprocess, "Popen", faux)
    interruption.poser(lambda: True)

    with pytest.raises(interruption.PasseInterrompue):
        run_kumiko(tmp_path / "x.png")
    assert faux.dernier.tue, "l'enfant doit être tué, pas abandonné à son sort"


def test_un_vrai_sous_processus_ne_survit_pas_a_l_annulation(monkeypatch, kumiko_on,
                                                             tmp_path):
    """CONC-1 — « sans laisser de processus résiduel », éprouvé sur un vrai processus.

    Le point mesuré le 2026-09-08 : `subprocess.run(timeout=…)` TUAIT déjà l'enfant, dans
    sa clause de délai comme dans sa clause générale. L'orphelin annoncé par l'audit
    n'existait pas — c'est le passage à `Popen`, nécessaire pour devenir interruptible,
    qui prend la charge de l'enfant. **Ce test garde donc une propriété que le correctif
    pouvait DÉTRUIRE, pas une qu'il apporte.**

    Il ne demande à aucun outil système si le processus vit : il regarde s'il TRAVAILLE
    encore. Un enfant tué cesse d'écrire ; un enfant orphelin continue. C'est la seule
    forme portable, et le dépôt doit tourner sous Linux dans son image comme ici.
    """
    marqueur = tmp_path / "vivant.txt"
    script = tmp_path / "faux_kumiko.py"
    script.write_text(
        "import os, time\n"
        "chemin = os.environ['BD_TEST_MARQUEUR']\n"
        "for _ in range(2000):\n"
        "    open(chemin, 'a').write('.')\n"
        "    time.sleep(0.01)\n", encoding="utf-8")

    monkeypatch.setenv("BD_TEST_MARQUEUR", str(marqueur))
    monkeypatch.setattr(seg, "KUMIKO_ENTRY", script)
    monkeypatch.setattr(seg, "PAS_INTERRUPTION", 0.05)
    # L'interruption n'est demandée qu'une fois l'enfant AU TRAVAIL : sinon on tuerait
    # un processus qui n'a pas commencé, et le test ne prouverait rien.
    interruption.poser(lambda: marqueur.exists())

    with pytest.raises(interruption.PasseInterrompue):
        run_kumiko(tmp_path / "x.png")

    assert marqueur.exists(), "l'enfant n'a jamais démarré : le test ne mesure rien"
    taille = marqueur.stat().st_size
    time.sleep(0.3)                       # 30 écritures s'il avait survécu
    assert marqueur.stat().st_size == taille, (
        f"le sous-processus écrit encore après l'annulation ({taille} -> "
        f"{marqueur.stat().st_size} octets) : il a été laissé orphelin")
