"""Tests unitaires du wrapper Kumiko (sans lancer Kumiko)."""
import pytest

from pipeline.segmentation import KumikoError, _normalize_panel


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
