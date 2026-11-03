"""Le TABLEUR d'une grille : ses colonnes, ses mots, les identifiants qu'il ne porte pas
(ANN-7 ; gabarit tranché par Hugo sur maquette le 2026-11-03).

Une grille s'écrit dans un tableur sous DEUX formes de mots, que l'import lit toutes deux :

- les mots MACHINE — des colonnes aux noms courts (`cle`, `forme`, `libelle`…) et des
  valeurs codées (`variantes`, `bulle | cartouche | texte`) : ceux de l'outil en ligne de
  commande, du modèle fictif (`tools/grille-modele.csv`) et des grilles écrites avant le
  gabarit ;
- les mots du GABARIT — des titres qui posent les questions (« 4. Ce qu'on choisit ») et des
  cellules qui répondent en mots (« une variante », « la case ») : ceux qu'on remet à
  quelqu'un qui n'a jamais vu l'outil.

Les deux se MÊLENT sans peine : chaque titre de colonne et chaque valeur se lit d'un côté
ou de l'autre (`colonne_de`, `forme_lue`, `cibles_lues`…). Ce module ne VALIDE rien — c'est
`grille_import.lire` — : il dit les noms, et découpe un CSV en lignes.
"""
from __future__ import annotations

import csv
import re
import unicodedata

class FormatInvalide(ValueError):
    """Un fichier ou un en-tête inexploitable : une erreur de FORMAT, pas de données (400,
    ou l'outil sort en 1). `grille_import` la ré-exporte sous le même nom."""


# --------------------------------------------------------------------------- #
# Les COLONNES : leur nom machine, leur titre en mots, l'aide de leur titre
# --------------------------------------------------------------------------- #
# Dans l'ordre du gabarit. Le titre est la QUESTION du gabarit (tranché sur maquette) ;
# l'aide dit ce qu'on y écrit. `gris` : une colonne que BéDéditeur remplit.
COLONNES_ENTREES = (
    ("rubrique", "1. Rubrique",
     "Où l'entrée se range, du plus large au plus fin, les étages séparés par « > ». "
     "Vide : dans aucune rubrique. Laissez vide sur une ligne de variante.", 24, False),
    ("libelle", "Entrée",
     "Le nom de l'entrée, tel que l'annotateur le lira. Une ligne par entrée ; laissez vide "
     "sur une ligne de variante.", 22, False),
    ("variante", "Variante",
     "Pour une entrée qui se pose avec une variante (question 4) : une ligne par variante, "
     "juste sous l'entrée, la colonne « Entrée » laissée vide.", 18, False),
    ("cible", "2. Se pose sur",
     "Vide : ce que dit la feuille « 1. La grille ». Sinon : des mots, la case, la planche, "
     "ou une ou plusieurs sortes de zone (« bulle, cartouche ou texte hors bulle »). Des "
     "mots et une zone ne se combinent pas.", 18, False),
    ("cardinalite", "3. Combien de fois",
     "Vide : la règle ordinaire — plusieurs fois sur des mots, une fois sur une zone, la "
     "case ou la planche. « une seule » : en choisir une autre remplace la première.",
     14, False),
    ("forme", "4. Ce qu'on choisit",
     "Ce qu'on choisit en posant l'entrée : rien, une variante (écrite sur les lignes du "
     "dessous), ou des cases d'une liste (colonne suivante). Un relevé compte toujours UNE "
     "fois son entrée, quel que soit le nombre de cases cochées.", 18, False),
    ("liste", "Liste à cocher",
     "Pour une entrée qui se pose avec des cases d'une liste : le nom d'une liste de la "
     "feuille « 3. Listes à cocher ».", 18, False),
    ("precision", "5. Champ à écrire",
     "Vide : aucun. Sinon le nom d'un petit champ libre que l'annotateur remplit à la pose "
     "(« région »).", 14, False),
    ("lien", "6. Autre zone",
     "« oui » : à chaque pose, l'annotateur désigne une autre zone de la planche. Vide ou "
     "« non » : aucune.", 10, False),
    ("definition", "Définition",
     "Ce que dit le guide de l'entrée, ou de la variante sur sa ligne.", 34, False),
    ("structure", "Structure",
     "Facultatif : la structure que la grille donne, quand elle en donne une.", 18, False),
    ("exemples", "Exemples",
     "Un exemple par ligne dans la cellule (Alt+Entrée ; Ctrl+Entrée dans LibreOffice), ou "
     "séparés par « | ».", 24, False),
    ("piege", "Piège", "Une confusion à éviter, que le guide signale.", 22, False),
    ("cle", "Identifiant",
     "Rempli par BéDéditeur. Ne le changez pas : c'est lui qui fait d'un renommage un "
     "renommage. Vide sur une entrée neuve, il se déduit de son nom.", 16, True),
    ("variante_cle", "Identifiant de variante",
     "Rempli par BéDéditeur, sur une ligne de variante. Ne le changez pas.", 16, True),
    ("rubrique_cle", "Identifiant de rubrique",
     "Rempli par BéDéditeur : l'identifiant de chaque étage de la rubrique. Ne le changez "
     "pas.", 16, True),
)
COLONNES_LISTES = (
    ("liste", "Liste",
     "Le nom de la liste, tel que la colonne « Liste à cocher » le nomme. Une ligne par "
     "case : on répète le nom.", 24, False),
    ("libelle", "Case", "Ce qu'on coche, tel que l'annotateur le lira.", 24, False),
    ("definition", "Définition (au survol)", "Ce qu'en dit le guide.", 40, False),
    ("liste_cle", "Identifiant de liste", "Rempli par BéDéditeur. Ne le changez pas.", 16,
     True),
    ("cle", "Identifiant", "Rempli par BéDéditeur. Ne le changez pas.", 16, True),
)
TITRES = {c: t for c, t, *_ in COLONNES_ENTREES}
TITRES_LISTES = {c: t for c, t, *_ in COLONNES_LISTES}

def norme(texte) -> str:
    """Un titre ou une valeur ramené à sa forme de COMPARAISON : sans accents, en
    minuscules, l'apostrophe typographique redressée, les espaces resserrés, et sans le
    numéro de question en tête (« 4. Ce qu'on choisit » se lit « ce qu'on choisit »)."""
    t = unicodedata.normalize("NFKD", str(texte or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("‘", "'").replace("﻿", "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^\d+\s*[.)]\s*", "", t)


def _alias(colonnes) -> dict:
    alias = {}
    for c, titre, *_ in colonnes:
        alias[norme(c)] = c
        alias[norme(titre)] = c
    return alias


_ALIAS_ENTREES = _alias(COLONNES_ENTREES)
_ALIAS_LISTES = _alias(COLONNES_LISTES)


def colonne_de(titre, *, listes: bool = False) -> str | None:
    """Le nom machine d'un titre de colonne, qu'il soit écrit en machine (`forme`) ou en
    mots (« 4. Ce qu'on choisit »). None : une colonne que l'import ignore."""
    return (_ALIAS_LISTES if listes else _ALIAS_ENTREES).get(norme(titre))


# --------------------------------------------------------------------------- #
# Les VALEURS en mots
# --------------------------------------------------------------------------- #
FORMES_MOTS = {"simple": "rien", "variantes": "une variante",
               "qualificatifs": "des cases d'une liste"}
CARDINALITES_MOTS = {"une": "une seule", "plusieurs": "plusieurs"}
CIBLES_MOTS = {"mots": "des mots", "bulle": "bulle", "cartouche": "cartouche",
               "texte": "texte hors bulle", "case": "la case",
               "personnage": "boîte de personnage", "detail": "détail d'image",
               "planche": "la planche", "entite": "l'entité du registre"}

_FORMES_LUES = {norme(m): f for f, m in FORMES_MOTS.items()}
_CARDINALITES_LUES = {**{norme(m): c for c, m in CARDINALITES_MOTS.items()},
                      "une": "une", "une fois": "une"}
_CIBLES_LUES = {**{norme(m): c for c, m in CIBLES_MOTS.items()},
                "mots": "mots", "case": "case", "planche": "planche", "texte": "texte",
                "personnage": "personnage", "detail": "detail", "entite": "entite",
                "une case": "case", "la bulle": "bulle", "le cartouche": "cartouche",
                "un detail d'image": "detail", "la boite de personnage": "personnage",
                "boite": "personnage", "l'entite": "entite"}
_LIEN_LU = {"oui": "oui", "non": "non", "": ""}


def forme_lue(valeur):
    """« une variante » → `variantes` ; une valeur machine reste elle-même ; une valeur
    inconnue revient telle quelle (la validation la dit)."""
    if valeur is None:
        return None
    return _FORMES_LUES.get(norme(valeur), str(valeur).strip().lower())


def cardinalite_lue(valeur):
    if valeur is None:
        return None
    return _CARDINALITES_LUES.get(norme(valeur), str(valeur).strip().lower())


def cibles_lues(valeur):
    """« bulle, cartouche ou texte hors bulle » → `bulle | cartouche | texte` — la forme
    que `grilles.lire_cibles` valide. Un morceau inconnu revient tel quel, pour que l'erreur
    le nomme."""
    if valeur is None:
        return None
    morceaux = [m for m in re.split(r"\s*(?:\||,|;|\bou\b|\bet\b)\s*", str(valeur)) if m.strip()]
    return " | ".join(_CIBLES_LUES.get(norme(m), m.strip()) for m in morceaux) or None


# --------------------------------------------------------------------------- #
# Les identifiants DÉRIVÉS d'un libellé
# --------------------------------------------------------------------------- #
LONGUEUR_CLE = 48


def slug(texte) -> str:
    """Le libellé → un identifiant : sans accents, en minuscules, les lettres et chiffres
    gardés, tout le reste devenu un tiret, au plus 48 caractères. « Écho lointain » →
    `echo-lointain` ; « cœur » → `coeur`."""
    t = str(texte or "").replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae") \
        .replace("Æ", "ae").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:LONGUEUR_CLE].strip("-")


def deriver(libelle, prises: set, *, defaut: str) -> str:
    """Un identifiant neuf pour `libelle`, hors de `prises` (qu'il rejoint) : son `slug`,
    puis `-2`, `-3`… à la première collision ; `defaut` quand le libellé n'a ni lettre ni
    chiffre."""
    base = slug(libelle) or defaut
    cle, n = base, 2
    while cle in prises:
        cle, n = f"{base}-{n}", n + 1
    prises.add(cle)
    return cle


# --------------------------------------------------------------------------- #
# Lire : des lignes de cellules en texte
# --------------------------------------------------------------------------- #
def _est_commentaire(cellules) -> bool:
    return bool(cellules) and str(cellules[0] or "").lstrip("﻿").strip().startswith("#")


def feuille_csv(flux) -> tuple[list, list]:
    """Un CSV point-virgule → (en-tête, [(numéro de ligne, cellules)]). L'en-tête est la
    première ligne qui n'est ni vide ni un commentaire ; une ligne qui commence par `#` est
    ignorée partout. Le numéro est celui de la PREMIÈRE ligne physique de l'enregistrement
    (une cellule entre guillemets peut en couvrir plusieurs)."""
    lecteur = csv.reader(flux, delimiter=";")
    entete, lignes, avant = None, [], 0
    for cellules in lecteur:
        debut, avant = avant + 1, lecteur.line_num
        if not any(str(c).strip() for c in cellules) or _est_commentaire(cellules):
            continue
        if entete is None:
            entete = [str(c).lstrip("﻿") for c in cellules]
            continue
        lignes.append((debut, cellules))
    return entete or [], lignes
