"""Le balayage des plafonds voit-il ce qu'il est venu chercher ? (SEC-3)

Ce module existe parce que l'outil a MASQUÉ son propre cas d'école. `iiif-prezi3` impose
`Pillow<=12.0.0` — le plafond qui a motivé SEC-3 — et la première version du balayage le
rangeait parmi les « conventions de version majeure », donc invisible sans `--tous`.

Le mode d'échec est celui qui ne s'annonce jamais : l'outil sort en 0, la liste des
plafonds serrés paraît courte, et une liste courte se lit comme une bonne nouvelle. Aucune
suite ne pouvait broncher — `tools/` est hors couverture, et un rapport n'a pas de contrat.

D'où une table de vérité sur la classification, qui est de la logique pure : on n'éprouve
pas ici l'environnement installé (il change d'une machine à l'image), mais la RÈGLE.
"""
import importlib
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE / "tools") not in sys.path:
    sys.path.insert(0, str(RACINE / "tools"))

plafonds_dependances = importlib.import_module("plafonds_dependances")
est_convention = plafonds_dependances.est_convention
lire_exigence = plafonds_dependances.lire_exigence
sans_redites = plafonds_dependances.sans_redites


# ---------------------------------------------------------------- la classification

@pytest.mark.parametrize("op, version", [
    ("<", "2"),          # « rien de promis au-delà de la 2 »
    ("<", "2.0"),
    ("<", "1.0.0"),
    ("<", "13"),
    ("<", "3.0.0"),
])
def test_une_borne_de_majeure_stricte_est_une_convention(op, version):
    """`<2.0` exclut TOUTE la majeure suivante : un correctif passe dessous."""
    assert est_convention(op, version) is True


@pytest.mark.parametrize("op, version, pourquoi", [
    ("<=", "12.0.0", "LE cas du chantier : iiif-prezi3 fige Pillow sur une release"),
    ("<=", "2.3.5", "ultralytics sur numpy — même forme, vue dès le premier jet"),
    ("<=", "2", "« au plus la 2 » admet 2.x : ce n'est pas une borne de majeure"),
    ("<=", "1.0.0", "la forme majeure ne sauve pas un `<=`"),
    ("<", "2.8", "une borne de MINEURE retient sous un correctif de 2.8.x"),
    ("<", "0.29.0", "starlette sur httpx"),
    ("<", "12.0.1", "une corrective : tout 12.0.0.x est exclu"),
])
def test_tout_le_reste_est_un_plafond_serre(op, version, pourquoi):
    assert est_convention(op, version) is False, pourquoi


def test_c_est_l_operateur_qui_decide_pas_le_numero():
    """La régression exacte, énoncée en une ligne.

    Le même numéro change de camp selon l'opérateur qui le porte. Ne lire que la
    version — ce que faisait `MAJEUR.match(version)` seul — range `<=12.0.0` avec
    `<12.0.0`, c'est-à-dire le plafond le plus serré avec le plus lâche.
    """
    assert est_convention("<", "12.0.0") is True
    assert est_convention("<=", "12.0.0") is False


def test_le_plafond_du_chantier_est_dans_les_serres_et_non_masque():
    """Le cliquet nommé : `Pillow<=12.0.0` ne doit plus jamais se ranger en convention."""
    cible, bornes, marqueur = lire_exigence("Pillow<=12.0.0,>=9.1.1")
    assert cible == "pillow"
    assert ("<=", "12.0.0") in bornes
    assert marqueur == ""
    assert not any(est_convention(op, v) for op, v in bornes)


# ---------------------------------------------------------------- la lecture des lignes

def test_un_marqueur_est_rendu_et_non_jete():
    """Une borne derrière `extra` ne mord que si l'on installe cet extra."""
    cible, bornes, marqueur = lire_exigence('Pillow<=12.0.0,>=9.1.1; extra == "dev"')
    assert cible == "pillow"
    assert ("<=", "12.0.0") in bornes
    assert marqueur == 'extra == "dev"'


def test_un_extra_sur_la_CIBLE_n_emporte_pas_la_specification():
    """`requests[security]<3.0` — couper au premier `[` perdait le plafond en SILENCE.

    C'est le mode d'échec de tout ce module : l'outil ne se plaint pas, il rapporte
    simplement un plafond de moins.
    """
    cible, bornes, marqueur = lire_exigence("requests[security]<3.0.0,>=2.28.0")
    assert cible == "requests"
    assert bornes == [("<", "3.0.0")]
    assert marqueur == ""


@pytest.mark.parametrize("exigence", [
    "pydantic>=2.0.0",           # aucun plafond
    "colorama!=0.4.5",           # exclut une version isolée, n'empêche pas de monter
    "packaging~=24.0",           # borne qu'on s'impose, pas un tiers
])
def test_ce_qui_ne_retient_personne_ne_remonte_pas(exigence):
    _cible, bornes, _marqueur = lire_exigence(exigence)
    assert bornes == []


def test_une_ligne_illisible_ne_fait_pas_tomber_le_balayage():
    assert lire_exigence("   ") == ("", [], "")


def test_le_nom_de_la_cible_est_normalise():
    """`Pillow`, `pillow` et `PIL_low` doivent tomber sur la même clé que le verrou."""
    assert lire_exigence("Pillow<=12.0.0")[0] == "pillow"
    assert lire_exigence("opencv_python<2.0")[0] == "opencv-python"


# ---------------------------------------------------------------- les redites

def test_la_meme_borne_redite_sous_un_extra_ne_compte_qu_une_fois():
    """`iiif-prezi3` déclare `Pillow<=12.0.0` DEUX fois — obligatoire, puis sous `dev`.

    Les afficher toutes deux ferait passer une redite pour deux plafonds distincts.
    """
    entrees = {
        ("iiif-prezi3", "<=", "12.0.0", ""),
        ("iiif-prezi3", "<=", "12.0.0", 'extra == "dev"'),
    }
    assert sans_redites(entrees) == [("iiif-prezi3", "<=", "12.0.0", "")]


def test_c_est_l_OBLIGATOIRE_qui_survit_a_la_redite():
    """Garder la variante marquée ferait passer une obligation pour une option."""
    (survivant,) = sans_redites({
        ("iiif-prezi3", "<=", "12.0.0", 'extra == "dev"'),
        ("iiif-prezi3", "<=", "12.0.0", ""),
    })
    assert survivant[3] == "", "le marqueur vide EST l'obligation"


def test_une_borne_qui_n_existe_QUE_sous_un_extra_reste_visible():
    """On la RAPPORTE en la marquant — la masquer serait la faute qu'on vient de réparer.

    Elle ne retient personne tant que l'extra n'est pas installé, et c'est au lecteur
    de le savoir : l'outil ne peut pas deviner quels extras sont posés.
    """
    entrees = {("tox", "<", "5.0.0", 'extra == "dev"')}
    assert sans_redites(entrees) == [("tox", "<", "5.0.0", 'extra == "dev"')]


def test_deux_bornes_DIFFERENTES_du_meme_paquet_survivent_toutes_deux():
    """`ultralytics` plafonne numpy en `<2` ET en `<=2.3.5` : ce sont deux faits."""
    entrees = {
        ("ultralytics", "<", "2", ""),
        ("ultralytics", "<=", "2.3.5", ""),
    }
    assert len(sans_redites(entrees)) == 2
