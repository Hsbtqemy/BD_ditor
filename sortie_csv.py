"""Les CSV que l'instance SORT : un séparateur, un encodage, écrits une seule fois (ANN-7).

Tranché par Hugo le 2026-11-11 : tout CSV qui sort — la Recherche, l'album
(`/api/export/csv`), l'Exploration, la voie du dépôt, les outils de `tools/` — est séparé
par des POINTS-VIRGULES. Un Excel réglé en français prend la virgule pour le séparateur
DÉCIMAL et attend le point-virgule entre les colonnes : un fichier en virgules s'y ouvre
au double-clic avec la ligne entière dans une seule case (vu par Hugo).

Et en UTF-8 AVEC BOM : sans lui, ce même Excel lit le fichier dans la page de code du
poste (cp1252), et « é » s'y affiche « Ã© ». Les sorties le posaient déjà presque toutes ;
il est écrit ici pour celles qui l'oubliaient.

Côté lecteurs : R `read.csv2(f, fileEncoding = "UTF-8-BOM")` ou
`read.csv(f, sep = ";", fileEncoding = "UTF-8-BOM")` ; pandas
`pd.read_csv(f, sep=";", encoding="utf-8-sig")`.

Ce qui n'est PAS ici, et reste à sa place : l'anti-injection de formule
(`socle._csv_safe`), une règle de sécurité sur le CONTENU d'une cellule ; et les LECTURES
de CSV (l'import d'une grille lit déjà du point-virgule, `grille_tableur`), qui ne sont pas
des sorties.

`tests/test_separateur_csv.py` interdit tout `csv.writer` / `csv.DictWriter` construit
ailleurs dans le code de l'application, et JOUE chaque sortie.
"""
import csv

SEPARATEUR = ";"
BOM = "﻿"               # UTF-8 avec BOM : ce qui fait lire les accents à Excel
ENCODAGE_FICHIER = "utf-8-sig"   # le même BOM, pour un fichier écrit par `open()`


def _sans_separateur(options: dict) -> dict:
    """Le séparateur ne se choisit pas à l'appel : c'est toute la raison de ce module."""
    if "delimiter" in options:
        raise TypeError("le séparateur d'une sortie CSV est `sortie_csv.SEPARATEUR`, "
                        "il ne se passe pas à l'appel")
    return options


def ecrivain_csv(flux, **options):
    """Un `csv.writer` au séparateur de l'instance."""
    return csv.writer(flux, delimiter=SEPARATEUR, **_sans_separateur(options))


def ecrivain_csv_dict(flux, colonnes, **options):
    """Un `csv.DictWriter` au séparateur de l'instance."""
    return csv.DictWriter(flux, fieldnames=colonnes, delimiter=SEPARATEUR,
                          **_sans_separateur(options))
