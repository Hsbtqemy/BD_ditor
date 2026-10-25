"""COL-3, tranche 3b — ce que l'écran de l'échelle tient du serveur sans le lui demander.

La liste des crans n'est publiée par aucune route : le serveur l'ACCEPTE (la prise, `cran`
d'une demande, « repartir de zéro ») et la renvoie dans ce qu'il lit, mais l'écran doit
l'écrire avant d'avoir rien lu — les radios de « Copie… », celles de « Revenir… », le cran de
chaque notice de « + Prendre du fonds… ». `static/lib/echelle.js` en tient donc une copie, et
une seule : ce test la confronte à `database`, ordre compris, comme
`test_suppression_ecran.py` le fait pour les genres d'une demande. Une copie qui s'écarte
enverrait un cran que le serveur refuse par un 422 : l'écran offrirait un geste qui
n'aboutit jamais. On lit le SOURCE. Suite par défaut.
"""
import re
from pathlib import Path

import database

RACINE = Path(__file__).resolve().parent.parent
LIB = RACINE / "static" / "lib" / "echelle.js"


def _crans_de_l_ecran():
    source = LIB.read_text(encoding="utf-8")
    bloc = re.search(r"const CRANS = \[(.*?)\];", source, re.S)
    assert bloc, "la liste CRANS est introuvable dans static/lib/echelle.js"
    return re.findall(r'valeur: "([a-z_]+)"', bloc.group(1))


def test_les_crans_sont_ceux_du_serveur_dans_l_ordre():
    assert tuple(_crans_de_l_ecran()) == tuple(database.CRANS)


def test_les_crans_de_repartir_sont_tous_sauf_le_plus_haut():
    """L'écran les dérive (`VALEURS.slice(0, -1)`) : la règle du serveur doit rester celle-là."""
    source = LIB.read_text(encoding="utf-8")
    assert "const CRANS_DE_REPARTIR = VALEURS.slice(0, -1);" in source
    assert tuple(database.CRANS_DE_REPARTIR) == tuple(database.CRANS[:-1])


def test_aucune_surface_n_ecrit_les_mots_d_un_cran():
    """Les surfaces passent par `BDEchelle` : « jusqu'à la transcription » vit à un seul
    endroit. Une phrase recopiée dans un script de surface vieillirait seule."""
    mots = ("jusqu'au découpage", "jusqu'à la transcription", "jusqu'à la grammaire relue",
            "jusqu'aux annotations", "Repartir de la transcription")
    for script in ("corpus.js", "administration.js"):
        source = (RACINE / "static" / script).read_text(encoding="utf-8")
        recopies = [m for m in mots if m in source]
        assert not recopies, f"{script} écrit en clair {recopies} : passer par BDEchelle"
