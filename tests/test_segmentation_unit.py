"""Tests unitaires du wrapper Kumiko (subprocess mocké, sans lancer Kumiko)."""
import json
import subprocess
import types
from pathlib import Path

import pytest

import database
import pipeline.segmentation as seg
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


# ---- run_kumiko : chemins d'erreur, avec subprocess.run mocké ---- #
def _fake_run(write=None, returncode=0, stderr="", raises=None):
    def run(args, **kw):
        if raises is not None:
            raise raises
        if write is not None:
            Path(args[args.index("-o") + 1]).write_text(write, encoding="utf-8")
        return types.SimpleNamespace(returncode=returncode, stderr=stderr, stdout="")
    return run


@pytest.fixture
def kumiko_on(monkeypatch):
    monkeypatch.setattr(seg, "kumiko_available", lambda: True)


def test_run_kumiko_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(seg, "kumiko_available", lambda: False)
    with pytest.raises(KumikoError, match="introuvable"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_code_retour_non_nul(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "run", _fake_run(returncode=1, stderr="boom"))
    with pytest.raises(KumikoError, match="échoué"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_timeout(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(
        seg.subprocess, "run",
        _fake_run(raises=subprocess.TimeoutExpired(cmd="kumiko", timeout=1)))
    with pytest.raises(KumikoError, match="délai"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_json_invalide(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "run", _fake_run(write="pas du json"))
    with pytest.raises(KumikoError, match="illisible"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_sans_clef_panels(monkeypatch, kumiko_on, tmp_path):
    monkeypatch.setattr(seg.subprocess, "run",
                        _fake_run(write=json.dumps([{"size": [1, 1]}])))
    with pytest.raises(KumikoError, match="panels"):
        run_kumiko(tmp_path / "x.png")


def test_run_kumiko_succes(monkeypatch, kumiko_on, tmp_path):
    page = [{"size": [10, 20], "panels": [[0, 0, 5, 5]]}]
    monkeypatch.setattr(seg.subprocess, "run", _fake_run(write=json.dumps(page)))
    assert run_kumiko(tmp_path / "x.png")["panels"] == [[0, 0, 5, 5]]


def test_segment_planche_inexistante(data_dir):
    conn = database.get_connection()
    try:
        with pytest.raises(ValueError):
            segment_planche(conn, 999)
    finally:
        conn.close()
