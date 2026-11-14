"""Les CSV que l'instance SORT : un séparateur, un encodage, écrits une seule fois (ANN-7).

Tranché par Hugo le 2026-11-11 : tout CSV qui sort — la Recherche, l'album
(`/api/export/csv`), l'Exploration, la voie du dépôt, les outils de `tools/` — est séparé
par des POINTS-VIRGULES. Un Excel réglé en français prend la virgule pour le séparateur
DÉCIMAL et attend le point-virgule entre les colonnes : un fichier en virgules s'y ouvre
au double-clic avec la ligne entière dans une seule case (vu par Hugo).

Et ses nombres décimaux s'écrivent avec une VIRGULE (`0,8571`), tranché par Hugo ensuite :
le même Excel lit « 0.8571 » et « 1.5 » comme du TEXTE (vérifié par le pilotage), un
entier comme un nombre. La règle porte sur le TYPE de la valeur, pas sur son allure :
seuls un `float` et un `Decimal` passés à l'écrivain changent — jamais une chaîne, si bien
qu'une date, un identifiant, une citation ou « 1.5 » écrit dans une bulle sortent tels
quels. Une sortie qui veut un nombre de décimales fixe passe par `nombre()`, jamais par un
`.replace('.', ',')` à elle.

Et en UTF-8 AVEC BOM : sans lui, ce même Excel lit le fichier dans la page de code du
poste (cp1252), et « é » s'y affiche « Ã© ». Les sorties le posaient déjà presque toutes ;
il est écrit ici pour celles qui l'oubliaient.

Côté lecteurs : R `read.csv2(f, fileEncoding = "UTF-8-BOM")` — point-virgule et virgule
décimale sont ses réglages par défaut ; pandas
`pd.read_csv(f, sep=";", decimal=",", encoding="utf-8-sig")`.

Ce qui n'est PAS ici, et reste à sa place : l'anti-injection de formule
(`socle._csv_safe`), une règle de sécurité sur le CONTENU d'une cellule de texte ; et les
LECTURES de CSV (l'import d'une grille lit déjà du point-virgule, `grille_tableur`), qui ne
sont pas des sorties.

`tests/test_separateur_csv.py` interdit tout `csv.writer` / `csv.DictWriter` construit
ailleurs dans le code de l'application, et JOUE chaque sortie.
"""
import csv
from decimal import Decimal

SEPARATEUR = ";"
SEPARATEUR_DECIMAL = ","
BOM = chr(0xFEFF)               # UTF-8 avec BOM : ce qui fait lire les accents à Excel
ENCODAGE_FICHIER = "utf-8-sig"  # le même BOM, pour un fichier écrit par `open()`


def nombre(valeur, decimales=None) -> str:
    """Un nombre comme il sort dans un CSV : la virgule décimale, et `decimales` chiffres
    après elle s'il est donné. Un entier sort sans décimale (sauf `decimales`). Ce qui n'est
    pas un nombre — `None`, une chaîne, un booléen — est refusé : c'est une cellule de texte,
    et elle sort telle quelle sans passer par ici."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, Decimal)):
        raise TypeError(f"`nombre()` attend un nombre, pas {type(valeur).__name__}")
    if decimales is not None:
        texte = f"{valeur:.{decimales}f}"
    elif isinstance(valeur, float):
        texte = repr(valeur)
    elif isinstance(valeur, Decimal):
        texte = format(valeur, "f")
    else:
        texte = str(valeur)
    return texte.replace(".", SEPARATEUR_DECIMAL)


def _cellule(valeur):
    """Un `float` ou un `Decimal` prend la virgule ; tout le reste passe tel quel."""
    if isinstance(valeur, (float, Decimal)):
        return nombre(valeur)
    return valeur


def _sans_separateur(options: dict) -> dict:
    """Le séparateur ne se choisit pas à l'appel : c'est toute la raison de ce module."""
    if "delimiter" in options:
        raise TypeError("le séparateur d'une sortie CSV est `sortie_csv.SEPARATEUR`, "
                        "il ne se passe pas à l'appel")
    return options


class _Ecrivain:
    """Un `csv.writer` dont chaque ligne passe par `_cellule`."""

    def __init__(self, flux, **options):
        self._ecrivain = csv.writer(flux, delimiter=SEPARATEUR, **_sans_separateur(options))

    @property
    def dialect(self):
        return self._ecrivain.dialect

    def writerow(self, ligne):
        return self._ecrivain.writerow([_cellule(c) for c in ligne])

    def writerows(self, lignes):
        for ligne in lignes:
            self.writerow(ligne)


class _EcrivainDict(csv.DictWriter):
    """Un `csv.DictWriter` dont chaque ligne passe par `_cellule` (l'en-tête compris, qui
    n'est fait que de chaînes)."""

    def writerow(self, ligne):
        return super().writerow({k: _cellule(v) for k, v in ligne.items()})

    def writerows(self, lignes):
        for ligne in lignes:
            self.writerow(ligne)


def ecrivain_csv(flux, **options):
    """Un `csv.writer` au séparateur de l'instance, virgule décimale comprise."""
    return _Ecrivain(flux, **options)


def ecrivain_csv_dict(flux, colonnes, **options):
    """Un `csv.DictWriter` au séparateur de l'instance, virgule décimale comprise."""
    return _EcrivainDict(flux, fieldnames=colonnes, delimiter=SEPARATEUR,
                         **_sans_separateur(options))
