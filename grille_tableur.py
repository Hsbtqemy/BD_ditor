"""Le TABLEUR d'une grille : ses deux formes, ses mots, le classeur qu'on produit et qu'on
relit (ANN-7 ; gabarit tranché par Hugo sur maquette le 2026-11-03).

Une grille s'écrit dans un tableur sous DEUX formes, que l'import lit toutes deux :

- la forme MACHINE — deux CSV point-virgule, des colonnes aux noms courts (`cle`, `forme`,
  `libelle`…) et des valeurs codées (`variantes`, `bulle | cartouche | texte`) : celle de
  l'outil en ligne de commande, du modèle fictif (`tools/grille-modele.csv`) et des grilles
  écrites avant le gabarit ;
- la forme EN MOTS — un classeur `.xlsx` à quatre feuilles (« 1. La grille », « 2. Les
  entrées », « 3. Listes à cocher », un exemple), dont les titres posent les questions
  (« 4. Ce qu'on choisit ») et dont les cellules répondent en mots (« une variante », « la
  case »). C'est celle qu'on remet à quelqu'un qui n'a jamais vu l'outil.

Les deux se MÊLENT sans peine : chaque titre de colonne et chaque valeur se lit d'un côté
ou de l'autre (`colonne_de`, `en_machine`). Ce module ne VALIDE rien — c'est
`grille_import.lire` — : il dit les noms, il lit des cellules, il écrit le classeur.

**Le classeur se lit sans danger.** Il est borné en taille REÇUE et en taille DÉPLIÉE — les
membres de l'archive sont décompressés et comptés AVANT qu'openpyxl les ouvre, si bien
qu'une bombe zip s'arrête au plafond —, son XML est lu par `defusedxml` (openpyxl le prend
de lui-même quand il est installé ; on REFUSE de lire s'il ne l'a pas pris), et aucune
formule n'est évaluée : une cellule qui en porte une est une faute du bilan, jamais une
valeur. Un nombre, une date ou un booléen que le tableur a TYPÉS reviennent en texte ; quand
le texte d'origine n'est pas sûr (une date, un nombre à virgule), le bilan le dit.

**Le classeur se produit sans danger.** Une cellule qui commence par `=` sort en TEXTE : son
type est forcé, et le préfixe de citation posé, pour qu'un tableur ne l'exécute pas, même
quand on la retouche.
"""
from __future__ import annotations

import csv
import datetime
import io
import re
import unicodedata
import zipfile

# Les bornes du classeur reçu. Une grille réelle pèse quelques dizaines de kilo-octets (le
# brouillon des linguistes : 170 lignes) : ces plafonds laissent deux ordres de grandeur.
TAILLE_MAX_RECUE = 5 * 1024 * 1024          # octets reçus, CSV comme classeur
TAILLE_MAX_DEPLIEE = 25 * 1024 * 1024       # octets décompressés, tous membres confondus
MEMBRES_MAX = 300                           # membres de l'archive
LIGNES_MAX = 5000                           # lignes lues par feuille
COLONNES_MAX = 40                           # colonnes lues par ligne

# Les noms de feuilles du classeur produit. À la LECTURE, une feuille se reconnaît à un mot
# de son nom (`_feuilles`) : on renomme une feuille sans casser l'import.
FEUILLE_GRILLE = "1. La grille"
FEUILLE_ENTREES = "2. Les entrées"
FEUILLE_LISTES = "3. Listes à cocher"
FEUILLE_EXEMPLE = "Exemple"
FEUILLE_CHOIX = "Choix"                     # cachée : les valeurs des listes déroulantes


class FormatInvalide(ValueError):
    """Un fichier ou un en-tête inexploitable : une erreur de FORMAT, pas de données (400,
    ou l'outil sort en 1). `grille_import` la ré-exporte sous le même nom."""


class TropGros(FormatInvalide):
    """Un fichier au-delà des bornes : reçu trop lourd, trop lourd une fois déplié, trop de
    membres ou de lignes (413)."""


# --------------------------------------------------------------------------- #
# Les COLONNES : leur nom machine, leur titre en mots, l'aide de leur titre
# --------------------------------------------------------------------------- #
# Dans l'ordre du classeur. Le titre est la QUESTION du gabarit (tranché sur maquette) ;
# l'aide est le commentaire posé sur le titre. `gris` : une colonne que BéDéditeur remplit.
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

# La feuille « 1. La grille » : un libellé en colonne A, sa valeur en colonne B.
CHAMPS_GRILLE = (
    ("nom", "Nom de la grille",
     "Unique dans son projet. Pour une version suivante, c'est le nom de la grille."),
    ("ouverte", "Fermée ou ouverte",
     "Fermée : elle change par versions, publiées l'une après l'autre. Ouverte : une seule "
     "version, vivante, qui s'enrichit quand on pose une entrée qu'elle n'a pas."),
    ("porte_sur", "Porte d'ordinaire sur",
     "Ce sur quoi se posent les entrées qui ne disent pas le leur (question 2) : des mots, "
     "la case, la planche, ou des sortes de zone."),
    ("note", "Note de version", "Facultatif : ce que cette version change, en une phrase."),
)
TITRES_GRILLE = {c: t for c, t, _ in CHAMPS_GRILLE}


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
_ALIAS_GRILLE = {**_alias(CHAMPS_GRILLE), "nom": "nom", "porte sur": "porte_sur",
                 "ouverte": "ouverte", "note": "note"}


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
OUVERTE_MOTS = {False: "fermée", True: "ouverte"}

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


def ouverte_lue(valeur):
    """« ouverte » → True, « fermée » → False, vide → None ; autre chose → la valeur, que
    l'appelant dit fautive."""
    n = norme(valeur)
    if not n:
        return None
    return {"ouverte": True, "fermee": False, "oui": True, "non": False}.get(n, str(valeur))


def cibles_en_mots(sortes) -> str:
    """Les sortes (`("bulle", "cartouche", "texte")`) → « bulle, cartouche ou texte hors
    bulle »."""
    mots = [CIBLES_MOTS.get(s, s) for s in sortes]
    if len(mots) <= 1:
        return "".join(mots)
    return ", ".join(mots[:-1]) + " ou " + mots[-1]


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
# Lire : des feuilles de cellules en texte
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
        if len(lignes) > LIGNES_MAX:
            raise TropGros(f"plus de {LIGNES_MAX} lignes : ce n'est pas une grille")
        if not any(str(c).strip() for c in cellules) or _est_commentaire(cellules):
            continue
        if entete is None:
            entete = [str(c).lstrip("﻿") for c in cellules]
            continue
        lignes.append((debut, cellules))
    return entete or [], lignes


def est_un_classeur(data: bytes) -> bool:
    """Le fichier est-il une archive zip (un classeur `.xlsx`) ? Le CSV n'en est jamais une."""
    return data[:4] == b"PK\x03\x04"


def _verifier_l_archive(data: bytes) -> None:
    """Borne le classeur AVANT qu'openpyxl l'ouvre : taille reçue, nombre de membres, et
    taille DÉPLIÉE — chaque membre est décompressé et compté pour de vrai, sans se fier à la
    taille que l'archive DÉCLARE (une bombe zip la déclare petite)."""
    if len(data) > TAILLE_MAX_RECUE:
        raise TropGros(f"le fichier pèse plus de {TAILLE_MAX_RECUE // (1024 * 1024)} Mo")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            membres = z.infolist()
            if len(membres) > MEMBRES_MAX:
                raise TropGros(f"le classeur a plus de {MEMBRES_MAX} membres")
            total = 0
            for m in membres:
                with z.open(m) as f:
                    while True:
                        bloc = f.read(64 * 1024)
                        if not bloc:
                            break
                        total += len(bloc)
                        if total > TAILLE_MAX_DEPLIEE:
                            raise TropGros(
                                "le classeur, une fois déplié, pèse plus de "
                                f"{TAILLE_MAX_DEPLIEE // (1024 * 1024)} Mo")
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, NotImplementedError,
            ValueError) as exc:
        if isinstance(exc, FormatInvalide):
            raise
        raise FormatInvalide("ce fichier n'est pas un classeur .xlsx lisible") from exc


def _openpyxl():
    """openpyxl, à condition qu'il lise son XML par `defusedxml` : sinon on ne lit pas.
    `OPENPYXL_DEFUSEDXML=False` dans l'environnement suffirait à le lui faire oublier."""
    import openpyxl
    if openpyxl.DEFUSEDXML is not True:
        raise FormatInvalide("le classeur ne peut pas être lu sans danger ici (defusedxml "
                             "absent) : importez les deux CSV")
    return openpyxl


def _texte_de(cellule, ou: dict, fautes: list, notes: list) -> str:
    """Le TEXTE d'une cellule de classeur. Une formule n'est jamais évaluée : c'est une
    faute. Une erreur du tableur aussi. Un nombre entier revient en chiffres ; un nombre à
    virgule, une date, un booléen reviennent en texte, et le bilan le dit."""
    v = cellule.value
    if v is None:
        return ""
    if getattr(cellule, "data_type", None) == "f":
        fautes.append({**ou, "code": "formule",
                       "probleme": f"la cellule porte une formule (« {v} ») : l'import "
                                   "n'évalue aucune formule",
                       "a_faire": "écrivez la valeur elle-même ; un texte qui commence "
                                  "par « = » se tape précédé d'une apostrophe"})
        return str(v)
    if getattr(cellule, "data_type", None) == "e":
        fautes.append({**ou, "code": "erreur_du_tableur",
                       "probleme": f"la cellule porte une erreur du tableur (« {v} »)",
                       "a_faire": "écrivez la valeur elle-même"})
        return ""
    if isinstance(v, bool):
        texte = "oui" if v else "non"
        notes.append({**ou, "code": "type_booleen",
                      "probleme": f"le tableur a lu la cellule comme un booléen : elle est "
                                  f"prise pour « {texte} »",
                      "a_faire": None})
        return texte
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        texte = repr(v)
        notes.append({**ou, "code": "type_nombre",
                      "probleme": f"le tableur a lu la cellule comme un nombre : elle est "
                                  f"prise pour « {texte} »",
                      "a_faire": "si ce n'est pas le texte voulu, mettez la cellule au "
                                 "format Texte et récrivez-la"})
        return texte
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        if isinstance(v, datetime.datetime) and v.time() == datetime.time(0):
            v = v.date()
        texte = v.isoformat()
        notes.append({**ou, "code": "type_date",
                      "probleme": f"le tableur a lu la cellule comme une date : elle est "
                                  f"prise pour « {texte} »",
                      "a_faire": "si ce n'est pas le texte voulu, mettez la cellule au "
                                 "format Texte et récrivez-la"})
        return texte
    return str(v)


def _lignes_de_feuille(ws, fautes: list, notes: list) -> list:
    """Les lignes d'une feuille, cellules en texte : [(numéro, [cellules])], au plus
    `LIGNES_MAX`, `COLONNES_MAX` colonnes chacune."""
    ws.reset_dimensions()       # la dimension DÉCLARÉE peut mentir : on lit ce qui est là
    lignes = []
    for n, rangee in enumerate(ws.iter_rows(max_row=LIGNES_MAX + 1, max_col=COLONNES_MAX),
                               start=1):
        if n > LIGNES_MAX:
            if any(c.value is not None for c in rangee):
                raise TropGros(f"la feuille « {ws.title} » a plus de {LIGNES_MAX} lignes")
            break
        cellules = [_texte_de(c, {"fichier": ws.title, "ligne": n}, fautes, notes)
                    for c in rangee]
        lignes.append((n, cellules))
    return lignes


def _feuilles(wb) -> dict:
    """Les feuilles que l'import lit, reconnues à un mot de leur nom ; l'exemple et les
    feuilles qu'il ne connaît pas sont ignorés."""
    trouvees = {}
    for ws in wb.worksheets:
        n = norme(ws.title)
        if "exemple" in n or n == norme(FEUILLE_CHOIX):
            continue
        for quoi, mot in (("entrees", "entree"), ("listes", "liste"), ("grille", "grille")):
            if mot in n and quoi not in trouvees:
                trouvees[quoi] = ws
                break
    return trouvees


def lire_classeur(data: bytes) -> dict:
    """Un classeur `.xlsx` → `{"entrees": (nom, en-tête, lignes), "listes": (…) | None,
    "grille": {champ: (valeur, numéro de ligne)}, "fautes", "notes"}`. Les `fautes` sont des
    anomalies de cellule (une formule) ; les `notes`, des avertissements (une date)."""
    _verifier_l_archive(data)
    openpyxl = _openpyxl()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False,
                                    keep_links=False, keep_vba=False)
    except FormatInvalide:
        raise
    except Exception as exc:                 # tout ce qu'un classeur forgé peut lever
        raise FormatInvalide("ce fichier n'est pas un classeur .xlsx lisible") from exc
    fautes, notes = [], []
    try:
        feuilles = _feuilles(wb)
        if "entrees" not in feuilles:
            raise FormatInvalide(
                f"le classeur n'a pas de feuille « {FEUILLE_ENTREES} » (ses feuilles : "
                + ", ".join(f"« {ws.title} »" for ws in wb.worksheets) + ")")
        sortie = {"fautes": fautes, "notes": notes, "listes": None, "grille": {}}
        for quoi in ("entrees", "listes"):
            if quoi not in feuilles:
                continue
            ws = feuilles[quoi]
            entete, lignes = None, []
            for n, cellules in _lignes_de_feuille(ws, fautes, notes):
                if not any(c.strip() for c in cellules) or _est_commentaire(cellules):
                    continue
                if entete is None:
                    entete = cellules
                    continue
                lignes.append((n, cellules))
            sortie[quoi] = (ws.title, entete or [], lignes)
        if "grille" in feuilles:
            ws = feuilles["grille"]
            for n, cellules in _lignes_de_feuille(ws, fautes, notes):
                if len(cellules) < 2:
                    continue
                champ = _ALIAS_GRILLE.get(norme(cellules[0]))
                if champ and champ not in sortie["grille"]:
                    sortie["grille"][champ] = (cellules[1].strip() or None, n)
            sortie["nom_grille"] = ws.title
        return sortie
    except FormatInvalide:
        raise
    except Exception as exc:
        raise FormatInvalide("ce fichier n'est pas un classeur .xlsx lisible") from exc
    finally:
        wb.close()


# --------------------------------------------------------------------------- #
# Écrire le classeur
# --------------------------------------------------------------------------- #
_FORMULE = ("=", "+", "-", "@", "\t", "\r")


def _poser(ws, ligne: int, colonne: int, valeur):
    """Écrit une cellule en TEXTE. openpyxl ferait d'une chaîne qui commence par `=` une
    formule : le type est forcé, et le préfixe de citation posé, pour qu'un tableur ne
    l'exécute pas, même quand on la retouche. Les caractères qu'un classeur n'admet pas
    sont retirés."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    texte = "" if valeur is None else ILLEGAL_CHARACTERS_RE.sub("", str(valeur))
    cellule = ws.cell(row=ligne, column=colonne)
    if not texte:
        return cellule
    cellule.value = texte
    cellule.data_type = "s"
    if texte[:1] in _FORMULE:
        cellule.quotePrefix = True
    return cellule


def rangees(contenu: dict) -> list[dict]:
    """Les lignes de la feuille des entrées, au format EN MOTS, dans l'ordre des entrées :
    une ligne par entrée, puis une par variante, la colonne « Entrée » vide. Une entrée
    RETIRÉE n'y est pas : elle ne se pose plus, et une grille ouverte qu'on réimporte la
    garde retirée sans qu'on la récrive. Une liste est nommée par son libellé, sauf si deux
    listes le partagent (alors par son identifiant)."""
    import grilles
    libelles = [l["libelle"] for l in contenu["listes"].values() if l["libelle"]]
    nom_de_liste = {lc: (l["libelle"] if l["libelle"] and libelles.count(l["libelle"]) == 1
                         else lc) for lc, l in contenu["listes"].items()}
    sortie = []
    for cle, e in sorted(contenu["entrees"].items(), key=lambda kv: kv[1]["rang"]):
        if e.get("retiree"):
            continue
        chemin = grilles.chemin_de_rubrique(contenu["rubriques"], e["rubrique_cle"])
        sortie.append({
            "rubrique": " > ".join(contenu["rubriques"][r]["libelle"] for r in chemin),
            "libelle": e["libelle"], "cible": cibles_en_mots(grilles.cibles_de(e["cible"])),
            "cardinalite": CARDINALITES_MOTS.get(e["cardinalite"], ""),
            "forme": FORMES_MOTS.get(e["forme"], e["forme"]),
            "liste": nom_de_liste.get(e["liste_cle"], e["liste_cle"]) if e["liste_cle"] else "",
            "precision": e["precision"], "lien": "oui" if e["lien"] else "",
            "definition": e["definition"], "structure": e["structure"],
            "exemples": "\n".join(e["exemples"]), "piege": e["piege"], "cle": cle,
            "rubrique_cle": " > ".join(chemin)})
        for vc, x in sorted(e["variantes"].items(), key=lambda kv: kv[1]["rang"]):
            sortie.append({"variante": x["libelle"], "definition": x["definition"],
                           "structure": x["structure"], "exemples": "\n".join(x["exemples"]),
                           "piege": x["piege"], "variante_cle": vc})
    return sortie


def _listes_en_rangees(contenu: dict) -> list[dict]:
    sortie = []
    for lc, l in sorted(contenu["listes"].items()):
        for qc, q in sorted(l["qualificatifs"].items(), key=lambda kv: kv[1]["rang"]):
            sortie.append({"liste": l["libelle"] or lc, "libelle": q["libelle"],
                           "definition": q["definition"], "liste_cle": lc, "cle": qc})
    return sortie


def _style():
    from openpyxl.styles import Alignment, Font, PatternFill
    return {"titre": Font(bold=True), "gros": Font(bold=True, size=14),
            "gris": PatternFill("solid", fgColor="E7E9EE"),
            "tete": PatternFill("solid", fgColor="DCE6F5"),
            "rouge": PatternFill("solid", fgColor="F4B6B6"),
            "haut": Alignment(vertical="top", wrap_text=True)}


def _feuille_tabulaire(ws, colonnes, rangees_, st, *, aides: bool):
    from openpyxl.comments import Comment
    from openpyxl.utils import get_column_letter
    for i, (c, titre, aide, largeur, gris) in enumerate(colonnes, start=1):
        cellule = _poser(ws, 1, i, titre)
        cellule.font = st["titre"]
        cellule.fill = st["gris"] if gris else st["tete"]
        if aides:
            cellule.comment = Comment(aide, "BéDéditeur", width=260, height=120)
        ws.column_dimensions[get_column_letter(i)].width = largeur
    for n, r in enumerate(rangees_, start=2):
        for i, (c, *_rest) in enumerate(colonnes, start=1):
            cellule = _poser(ws, n, i, r.get(c))
            cellule.alignment = st["haut"]
            if colonnes[i - 1][4]:
                cellule.fill = st["gris"]
    ws.freeze_panes = "A2"


def ecrire_classeur(contenu: dict, *, nom: str, ouverte: bool, porte_sur, note=None,
                    exemple: dict | None = None) -> bytes:
    """Le classeur `.xlsx` d'une version : « 1. La grille » (la déclaration), « 2. Les
    entrées », « 3. Listes à cocher », une feuille d'exemple (le modèle fictif, quand on le
    passe) et une feuille cachée des choix. Listes déroulantes sur les questions, commentaire
    sur chaque titre, et une mise en forme conditionnelle qui passe en rouge une case dont
    la réponse n'est pas l'une de celles qu'on attend. Relu par `lire_classeur`, il rend le
    même contenu (même empreinte)."""
    import grilles
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.workbook.defined_name import DefinedName

    st = _style()
    wb = Workbook()
    wb.properties.creator = "BéDéditeur"
    wb.properties.lastModifiedBy = None

    # -- La feuille cachée des choix, que nomment les listes déroulantes.
    choix = wb.active
    choix.title = FEUILLE_CHOIX
    noms_de_listes = sorted({r["liste"] for r in _listes_en_rangees(contenu)})
    colonnes_choix = {
        "cibles": [CIBLES_MOTS[c] for c in grilles.CIBLES if c != grilles.CIBLE_ENTITE]
        + [cibles_en_mots(grilles.TYPES_TEXTE)],
        "combien": list(CARDINALITES_MOTS.values()),
        "formes": list(FORMES_MOTS.values()),
        "ouinon": ["oui", "non"],
        "listes": noms_de_listes or [""],
        "natures": list(OUVERTE_MOTS.values()),
        "portes": [CIBLES_MOTS[c] for c in (grilles.CIBLE_MOTS, "case", grilles.CIBLE_PLANCHE)]
        + [cibles_en_mots(grilles.TYPES_TEXTE)],
    }
    plages = {}
    for i, (quoi, valeurs) in enumerate(colonnes_choix.items(), start=1):
        lettre = get_column_letter(i)
        _poser(choix, 1, i, quoi)
        for n, v in enumerate(valeurs, start=2):
            _poser(choix, n, i, v)
        plage = f"'{FEUILLE_CHOIX}'!${lettre}$2:${lettre}${max(2, len(valeurs) + 1)}"
        plages[quoi] = plage
        wb.defined_names[f"choix_{quoi}"] = DefinedName(f"choix_{quoi}", attr_text=plage)
    choix.sheet_state = "hidden"

    # -- 1. La grille.
    g = wb.create_sheet(FEUILLE_GRILLE, 0)
    _poser(g, 1, 1, "La grille").font = st["gros"]
    _poser(g, 2, 1, "Remplissez la colonne B, puis la feuille « 2. Les entrées » : une ligne "
                    "par chose qu'on relève. La feuille « Exemple » montre une grille "
                    "remplie ; l'import ne la lit pas.").alignment = st["haut"]
    valeurs = {"nom": nom, "ouverte": OUVERTE_MOTS[bool(ouverte)],
               "porte_sur": cibles_en_mots(grilles.cibles_de(porte_sur)), "note": note}
    ligne_de = {}
    for n, (champ, titre, aide) in enumerate(CHAMPS_GRILLE, start=4):
        _poser(g, n, 1, titre).font = st["titre"]
        _poser(g, n, 2, valeurs[champ]).alignment = st["haut"]
        _poser(g, n, 3, aide).alignment = st["haut"]
        ligne_de[champ] = n
    n = 4 + len(CHAMPS_GRILLE) + 1
    _poser(g, n, 1, "Les six questions, pour chaque entrée").font = st["titre"]
    for k, (titre, aide) in enumerate((
            (TITRES["rubrique"], "Où se range-t-elle ?"),
            (TITRES["cible"], "Sur quoi se pose-t-elle ?"),
            (TITRES["cardinalite"], "Une fois par cible, ou plusieurs ?"),
            (TITRES["forme"], "Que choisit-on en la posant ? Ce qu'on veut compter décide."),
            (TITRES["precision"], "Faut-il écrire un mot de plus ?"),
            (TITRES["lien"], "Faut-il désigner une autre zone ?")), start=n + 1):
        _poser(g, k, 1, titre)
        _poser(g, k, 2, aide)
    g.column_dimensions["A"].width = 26
    g.column_dimensions["B"].width = 30
    g.column_dimensions["C"].width = 70
    for champ, plage in (("ouverte", "natures"), ("porte_sur", "portes")):
        dv = DataValidation(type="list", formula1=f"=choix_{plage}", allow_blank=True,
                            errorStyle="warning" if champ == "porte_sur" else "stop",
                            showErrorMessage=True)
        dv.add(f"B{ligne_de[champ]}")
        g.add_data_validation(dv)

    # -- 2. Les entrées, et l'exemple.
    def _entrees(ws, c, aides):
        lignes_ = rangees(c)
        _feuille_tabulaire(ws, COLONNES_ENTREES, lignes_, st, aides=aides)
        return len(lignes_)

    e = wb.create_sheet(FEUILLE_ENTREES, 1)
    _entrees(e, contenu, True)
    lettre = {c: get_column_letter(i) for i, (c, *_r) in enumerate(COLONNES_ENTREES, start=1)}
    fin = 2000
    for col, plage, style in (("cible", "cibles", "warning"), ("cardinalite", "combien", "stop"),
                              ("forme", "formes", "stop"), ("lien", "ouinon", "stop"),
                              ("liste", "listes", "warning")):
        dv = DataValidation(type="list", formula1=f"=choix_{plage}", allow_blank=True,
                            errorStyle=style, showErrorMessage=True)
        dv.add(f"{lettre[col]}2:{lettre[col]}{fin}")
        e.add_data_validation(dv)
    # La case FAUTIVE en rouge, dans le tableur même, avant tout import. Chaque règle porte
    # sur la première ligne de données ; le tableur la recopie sur toute la plage.
    L = lettre
    rouge = st["rouge"]
    regles = (
        ("forme", f'AND(${L["variante"]}2="",${L["forme"]}2<>"",'
                  f'COUNTIF(choix_formes,${L["forme"]}2)=0)'),
        ("forme", f'AND(${L["libelle"]}2<>"",${L["variante"]}2="",${L["forme"]}2="")'),
        ("cardinalite", f'AND(${L["cardinalite"]}2<>"",COUNTIF(choix_combien,'
                        f'${L["cardinalite"]}2)=0)'),
        ("lien", f'AND(${L["lien"]}2<>"",COUNTIF(choix_ouinon,${L["lien"]}2)=0)'),
        ("liste", f'AND(${L["liste"]}2<>"",COUNTIF(choix_listes,${L["liste"]}2)=0)'),
        ("liste", f'AND(${L["forme"]}2="{FORMES_MOTS["qualificatifs"]}",${L["liste"]}2="")'),
        ("liste", f'AND(${L["liste"]}2<>"",${L["forme"]}2<>"",'
                  f'${L["forme"]}2<>"{FORMES_MOTS["qualificatifs"]}")'),
        ("libelle", f'AND(${L["libelle"]}2="",${L["variante"]}2="",'
                    f'COUNTA(${L["rubrique"]}2:${L["piege"]}2)>0)'),
    )
    for col, formule in regles:
        e.conditional_formatting.add(f"{L[col]}2:{L[col]}{fin}",
                                     FormulaRule(formula=[formule], fill=rouge))

    # -- 3. Listes à cocher.
    li = wb.create_sheet(FEUILLE_LISTES, 2)
    _feuille_tabulaire(li, COLONNES_LISTES, _listes_en_rangees(contenu), st, aides=True)

    # -- L'exemple : une grille remplie, que l'import ne lit pas.
    if exemple is not None:
        x = wb.create_sheet(FEUILLE_EXEMPLE, 3)
        _entrees(x, exemple, False)
        x.sheet_properties.tabColor = "9AA3B8"
    wb.active = 0
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
