"""Une grille s'écrit dans un TABLEUR, BD_ditor la vérifie et la garde (ANN-7, tranche 1 ;
cadrage R3, tranché par Hugo le 2026-10-14 et le 2026-10-25).

Cœur partagé, sans I/O propre — le patron de `lexique_import` : il reçoit des FLUX de texte
et une CONNEXION, l'appelant ouvre les fichiers et tient la transaction. Deux enveloppes :
`tools/importer_grille.py` et `POST /api/projets/{id}/grilles/import`.

Le FORMAT — deux CSV point-virgule, UTF-8 avec ou sans BOM, en-tête obligatoire, lus par NOM
de colonne (ordre libre, colonnes en trop tolérées). `docs/import-grille.md` le dit pour qui
remplit le tableur.

1. Les entrées (`grille-rubriques-entrees.csv`, par exemple) : une ligne par ENTRÉE, et une
   ligne par VARIANTE. Une ligne de variante RÉPÈTE la `cle` de son entrée, porte
   `variante_cle` et `variante`, et laisse vides les colonnes propres à l'entrée — ou y
   recopie exactement celles de l'entrée : un tableur qu'on a rempli en tirant une cellule
   vers le bas ne doit pas être refusé pour cela. Elle peut porter sa définition, sa
   structure, ses exemples, son piège.
   Colonnes : `cle` · `rubrique` · `rubrique_cle` · `forme` · `libelle` · `variante_cle` ·
   `variante` · `structure` · `definition` · `exemples` · `piege` · `liste` · `precision` ·
   `lien` · `cible` · `cardinalite`. Obligatoires dans l'en-tête : `cle`, `forme`, `libelle`.
   Plusieurs exemples, plusieurs cibles : séparés par ` | `. Une rubrique s'écrit du plus
   large au plus fin, `Niveau 3 > Verbe`, et `rubrique_cle` dit l'identifiant de chaque
   étage, autant d'étages, même séparateur.
2. Les listes de qualificatifs (`grille-listes-qualificatifs.csv`), facultatif : une ligne
   par qualificatif — `liste_cle` · `liste` · `cle` · `libelle` · `definition`.
La DÉCLARATION (nom, ouverte ou fermée, « Porte sur », note de version) passe en arguments
de l'outil et en champs du formulaire de la route.

La VALIDATION refuse le fichier ENTIER à la première anomalie de structure, et les dit
TOUTES (G12) : une ligne écartée se lirait, dans le bilan, comme une entrée disparue. C'est
l'inverse de `lexique_import`, et c'est voulu — une version est un tout figé. Ce qui ne
casse rien est un AVERTISSEMENT, la première valeur retenue.

Le BILAN compare au plus récent état publié de la grille (ou à sa version vivante), par
`cle` : ce qui naît, ce qui est renommé, retouché, déplacé, changé de forme, de cible ou de
cardinalité, ce qui disparaît — avec le nombre de relevés posés sur chaque disparu.
"""
from __future__ import annotations

import csv
import io
import sqlite3
import zipfile

import grilles
from grilles import CARDINALITES, FORMES, propre

COLONNES = ("cle", "rubrique", "rubrique_cle", "forme", "libelle", "variante_cle",
            "variante", "structure", "definition", "exemples", "piege", "liste",
            "precision", "lien", "cible", "cardinalite")
OBLIGATOIRES = ("cle", "forme", "libelle")
# Les colonnes PROPRES à une entrée : vides sur une ligne de variante, ou recopiées.
COLONNES_DE_L_ENTREE = ("rubrique", "rubrique_cle", "forme", "libelle", "liste",
                        "precision", "lien", "cible", "cardinalite")
COLONNES_LISTES = ("liste_cle", "liste", "cle", "libelle", "definition")
OBLIGATOIRES_LISTES = ("liste_cle", "cle", "libelle")
SEP_RUBRIQUE = ">"
SEP_EXEMPLES = "|"
NOMS_FICHIERS = ("grille-rubriques-entrees.csv", "grille-listes-qualificatifs.csv")


class FormatInvalide(ValueError):
    """Un en-tête inexploitable : une erreur de FORMAT, pas de données (400, ou l'outil sort
    en 1)."""


class Refus(Exception):
    """L'import ne se fait pas : `statut` (le code HTTP qu'une route rendrait), un message,
    et les anomalies quand c'est le tableur qui est refusé."""

    def __init__(self, statut: int, message: str, anomalies=None):
        super().__init__(message)
        self.statut, self.message, self.anomalies = statut, message, list(anomalies or [])


# --------------------------------------------------------------------------- #
# Lecture et validation
# --------------------------------------------------------------------------- #
def _lignes(flux, attendues, obligatoires, nom: str, anomalies: list):
    """Les lignes d'un CSV point-virgule, par nom de colonne, cellules nettoyées ; une ligne
    entièrement vide est ignorée en silence. Lève `FormatInvalide` sur un en-tête qui manque
    une colonne obligatoire."""
    lecteur = csv.DictReader(flux, delimiter=";")
    entete = [propre(c) or "" for c in (lecteur.fieldnames or [])]
    entete = [c.lstrip("﻿") for c in entete]
    lecteur.fieldnames = entete
    manquantes = [c for c in obligatoires if c not in entete]
    if manquantes:
        raise FormatInvalide(
            f"{nom} : en-tête invalide, colonnes obligatoires manquantes "
            f"{', '.join(manquantes)}. Attendu (point-virgule) : {';'.join(attendues)}")
    sortie = []
    for n, brut in enumerate(lecteur, start=2):            # ligne 1 = en-tête
        if None in brut:
            anomalies.append(f"{nom} l.{n} : plus de cellules que de colonnes — un « ; » "
                             "dans une cellule ?")
            continue
        ligne = {c: _sans_echappement(propre(brut.get(c))) for c in attendues}
        if not any(propre(v) for v in brut.values()):
            continue
        sortie.append((n, ligne))
    return sortie


# Une cellule qui commence par `= + - @` serait EXÉCUTÉE comme une formule par un tableur : le
# réexport la préfixe d'une apostrophe (le patron de `socle._csv_safe`), et l'import retire
# cette apostrophe-là, et elle seule — « 'tain » reste « 'tain ».
_FORMULE = ("=", "+", "-", "@", chr(9), chr(13))


def _neutre(valeur) -> str:
    """Une cellule du réexport, neutralisée contre l'injection de formule."""
    v = "" if valeur is None else str(valeur)
    return "'" + v if v[:1] in _FORMULE else v


def _sans_echappement(valeur):
    """L'inverse de `_neutre`, à la lecture."""
    if valeur and len(valeur) > 1 and valeur[0] == "'" and valeur[1] in _FORMULE:
        return valeur[1:]
    return valeur


def _etages(texte) -> list:
    return [propre(x) for x in str(texte or "").split(SEP_RUBRIQUE)] if texte else []


def _exemples(texte) -> list:
    return [x for x in (propre(e) for e in str(texte or "").split(SEP_EXEMPLES)) if x]


def lire(flux_entrees, flux_listes=None, *, porte_sur=None) -> dict:
    """Lit et VALIDE un tableur. Rend `{"contenu", "anomalies", "avertissements"}` —
    `contenu` est la forme normalisée de `grilles.contenu`, None dès qu'une anomalie existe.
    `porte_sur` : la cellule « Porte sur » de la déclaration (« mots »,
    « bulle | cartouche ») ; absente, l'appelant passe celle de la version précédente."""
    anomalies: list = []
    avert: list = []
    # Les listes d'abord : une entrée à qualificatifs nomme la sienne.
    listes: dict = {}
    if flux_listes is not None:
        for n, l in _lignes(flux_listes, COLONNES_LISTES, OBLIGATOIRES_LISTES,
                            "listes", anomalies):
            ou = f"listes l.{n}"
            if not l["liste_cle"]:
                anomalies.append(f"{ou} : qualificatif « {l['cle'] or l['libelle']} » sans "
                                 "liste (`liste_cle` vide)")
                continue
            if not l["cle"]:
                anomalies.append(f"{ou} : `cle` vide")
                continue
            if not l["libelle"]:
                anomalies.append(f"{ou} : libellé vide pour « {l['cle']} »")
                continue
            liste = listes.setdefault(l["liste_cle"], {"libelle": l["liste"],
                                                       "qualificatifs": {}})
            if l["liste"] and liste["libelle"] and l["liste"] != liste["libelle"]:
                avert.append(f"{ou} : la liste « {l['liste_cle']} » a deux libellés — "
                             f"« {liste['libelle']} » retenu")
            liste["libelle"] = liste["libelle"] or l["liste"]
            if l["cle"] in liste["qualificatifs"]:
                anomalies.append(f"{ou} : qualificatif « {l['cle']} » en double dans la "
                                 f"liste « {l['liste_cle']} »")
                continue
            liste["qualificatifs"][l["cle"]] = {
                "libelle": l["libelle"], "definition": l["definition"],
                "rang": len(liste["qualificatifs"])}

    cible_version, erreur = grilles.lire_cibles(porte_sur)
    if erreur:
        anomalies.append(f"« Porte sur » : {erreur}")
    elif not cible_version:
        anomalies.append("« Porte sur » manque : sur quoi la grille se pose-t-elle ? "
                         f"({' · '.join(grilles.CIBLES)})")

    lignes = _lignes(flux_entrees, COLONNES, OBLIGATOIRES, "entrées", anomalies)
    entrees: dict = {}
    lignes_variantes = []
    rubriques: dict = {}
    par_chemin: dict = {}
    for n, l in lignes:
        ou = f"entrées l.{n}"
        if not l["cle"]:
            anomalies.append(f"{ou} : `cle` vide")
            continue
        if l["variante_cle"] or l["variante"]:
            lignes_variantes.append((n, l))
            continue
        if l["cle"] in entrees:
            anomalies.append(f"{ou} : la `cle` « {l['cle']} » est déjà celle d'une autre "
                             "entrée (une ligne de variante porte `variante_cle`)")
            continue
        forme = (l["forme"] or "").lower()
        if forme not in FORMES:
            anomalies.append(f"{ou} : forme « {l['forme'] or ''} » inconnue pour « {l['cle']} » "
                             f"(attendu : {' · '.join(FORMES)})")
        if not l["libelle"]:
            anomalies.append(f"{ou} : libellé vide pour « {l['cle']} »")
        # La rubrique : autant d'étages des deux côtés.
        etages, cles = _etages(l["rubrique"]), _etages(l["rubrique_cle"])
        rubrique_cle = None
        if etages or cles:
            if len(etages) != len(cles) or not all(etages) or not all(cles):
                anomalies.append(f"{ou} : `rubrique` et `rubrique_cle` n'ont pas les mêmes "
                                 f"étages pour « {l['cle']} » ({len(etages)} et {len(cles)})")
            else:
                parent = None
                for k, (libelle, rc) in enumerate(zip(etages, cles)):
                    chemin = tuple(etages[:k + 1])
                    deja = rubriques.get(rc)
                    if deja is None:
                        rubriques[rc] = {"libelle": libelle, "parent_cle": parent,
                                         "rang": len(rubriques)}
                    elif deja["libelle"] != libelle:
                        anomalies.append(f"{ou} : la rubrique « {rc} » a deux libellés — "
                                         f"« {deja['libelle']} » et « {libelle} »")
                    elif deja["parent_cle"] != parent:
                        anomalies.append(f"{ou} : la rubrique « {rc} » a deux parents — "
                                         f"« {deja['parent_cle']} » et « {parent} »")
                    autre = par_chemin.setdefault(chemin, rc)
                    if autre != rc:
                        anomalies.append(f"{ou} : la rubrique « {' > '.join(chemin)} » a deux "
                                         f"identifiants — « {autre} » et « {rc} »")
                    parent = rc
                rubrique_cle = cles[-1]
        liste = l["liste"]
        if forme == "qualificatifs":
            if not liste:
                anomalies.append(f"{ou} : « {l['cle']} » est à qualificatifs, sans `liste`")
            elif liste not in listes:
                anomalies.append(f"{ou} : la liste « {liste} » de « {l['cle']} » est inconnue "
                                 "(le fichier des listes ne la porte pas)")
        elif liste:
            anomalies.append(f"{ou} : « {l['cle']} » n'est pas à qualificatifs et nomme une "
                             f"liste (« {liste} »)")
        lien = (l["lien"] or "").lower()
        if lien not in ("", "oui", "non"):
            anomalies.append(f"{ou} : `lien` vaut « {l['lien']} » pour « {l['cle']} » "
                             "(attendu : oui, ou vide)")
        cible, erreur = grilles.lire_cibles(l["cible"])
        if erreur:
            anomalies.append(f"{ou} : {erreur}, pour « {l['cle']} »")
        cardinalite = (l["cardinalite"] or "").lower() or None
        if cardinalite is not None and cardinalite not in CARDINALITES:
            anomalies.append(f"{ou} : cardinalité « {l['cardinalite']} » inconnue pour "
                             f"« {l['cle']} » (attendu : une · plusieurs, ou vide)")
        effectives = cible or cible_version
        if grilles.CIBLE_ENTITE in effectives:
            avert.append(f"{ou} : « {l['cle']} » vise l'entité du registre : elle s'importe, "
                         "mais aucun relevé ne s'y pose avant l'étage de projet des "
                         "personnages (G3)")
        if "detail" in effectives:
            avert.append(f"{ou} : « {l['cle']} » vise un détail : le type de région `detail` "
                         "viendra avec l'écran qui le trace (G17)")
        entrees[l["cle"]] = {
            "rubrique_cle": rubrique_cle, "rang": len(entrees), "forme": forme,
            "libelle": l["libelle"], "definition": l["definition"],
            "structure": l["structure"], "piege": l["piege"], "precision": l["precision"],
            "lien": lien == "oui", "cible": grilles.ecrire_cibles(cible),
            "cardinalite": cardinalite, "liste_cle": liste if forme == "qualificatifs" else None,
            "retiree": False, "exemples": _exemples(l["exemples"]), "variantes": {},
            "_ligne": l}

    for n, l in lignes_variantes:
        ou = f"entrées l.{n}"
        e = entrees.get(l["cle"])
        if e is None:
            anomalies.append(f"{ou} : la variante « {l['variante_cle'] or l['variante']} » "
                             f"nomme l'entrée « {l['cle']} », qu'aucune ligne ne déclare")
            continue
        if not l["variante_cle"] or not l["variante"]:
            anomalies.append(f"{ou} : une variante de « {l['cle']} » a besoin de "
                             "`variante_cle` ET de `variante`")
            continue
        if e["forme"] != "variantes":
            anomalies.append(f"{ou} : « {l['cle']} » n'est pas à variantes, et une ligne lui "
                             f"donne la variante « {l['variante_cle']} »")
            continue
        for c in COLONNES_DE_L_ENTREE:
            if l[c] is not None and l[c] != e["_ligne"][c]:
                anomalies.append(f"{ou} : la ligne de variante « {l['variante_cle']} » remplit "
                                 f"`{c}` autrement que son entrée « {l['cle']} » (à laisser "
                                 "vide)")
                break
        if l["variante_cle"] in e["variantes"]:
            anomalies.append(f"{ou} : variante « {l['variante_cle']} » en double sous "
                             f"« {l['cle']} »")
            continue
        e["variantes"][l["variante_cle"]] = {
            "libelle": l["variante"], "definition": l["definition"],
            "structure": l["structure"], "piege": l["piege"], "rang": len(e["variantes"]),
            "exemples": _exemples(l["exemples"])}

    for cle_, e in entrees.items():
        if e["forme"] == "variantes" and not e["variantes"]:
            anomalies.append(f"entrées : « {cle_} » est à variantes et n'en a aucune")
        e.pop("_ligne", None)
    # Un parent circulaire (« a > b » puis « b > a » a déjà deux parents ; reste le cas d'une
    # rubrique qui serait son propre ancêtre par un autre chemin).
    for rc in rubriques:
        vus, x = set(), rc
        while x is not None and x in rubriques:
            if x in vus:
                anomalies.append(f"entrées : la rubrique « {rc} » est son propre ancêtre")
                break
            vus.add(x)
            x = rubriques[x]["parent_cle"]
    utilisees = {e["liste_cle"] for e in entrees.values() if e["liste_cle"]}
    for lc in listes:
        if lc not in utilisees:
            avert.append(f"listes : la liste « {lc} » n'est nommée par aucune entrée")
    if not entrees and not anomalies:
        anomalies.append("entrées : le tableur ne porte aucune entrée")
    if anomalies:
        return {"contenu": None, "anomalies": anomalies, "avertissements": avert}
    return {"contenu": {"cible": grilles.ecrire_cibles(cible_version), "rubriques": rubriques,
                        "entrees": entrees, "listes": listes},
            "anomalies": [], "avertissements": avert}


# --------------------------------------------------------------------------- #
# Le bilan
# --------------------------------------------------------------------------- #
_CHAMPS_RETOUCHES = ("definition", "structure", "piege", "exemples")
_CHAMPS_CHANGES = ("forme", "cible", "cardinalite", "liste_cle", "precision", "lien")


def _releves_sur(conn, grille_id, entree_cle, variante_cle=None) -> int:
    if grille_id is None:
        return 0
    if variante_cle is None:
        return conn.execute("SELECT COUNT(*) FROM releve WHERE grille_id = ? "
                            "AND entree_cle = ?", (grille_id, entree_cle)).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM releve WHERE grille_id = ? AND entree_cle = ? "
                        "AND variante_cle = ?", (grille_id, entree_cle,
                                                 variante_cle)).fetchone()[0]


def bilan(conn: sqlite3.Connection, grille_id, avant: dict | None, apres: dict) -> dict:
    """Ce qui change de `avant` (le contenu d'une version, ou None) à `apres`, par `cle`.
    Les disparus comptent les relevés posés sur eux (`grille_id` : la grille d'`avant`).
    Sans relevé sur la grille, une disparition ne coûte rien ; avec, la décision « retirer,
    ou fusionner dans… » attend la montée de version (note §6) : les relevés restent sur la
    version où ils ont été posés."""
    b = {"nes": [], "renommes": [], "retouches": [], "deplaces": [], "changes": [],
         "disparus": []}
    avant = avant or {"cible": None, "rubriques": {}, "entrees": {}, "listes": {}}
    if avant["cible"] != apres["cible"]:
        b["changes"].append({"quoi": "version", "cle": None, "champ": "porte_sur",
                             "avant": avant["cible"], "apres": apres["cible"]})
    for quoi, cle_a, cle_b in (("rubrique", avant["rubriques"], apres["rubriques"]),):
        for cle_ in cle_b.keys() - cle_a.keys():
            b["nes"].append({"quoi": quoi, "cle": cle_, "libelle": cle_b[cle_]["libelle"]})
        for cle_ in cle_a.keys() - cle_b.keys():
            b["disparus"].append({"quoi": quoi, "cle": cle_, "libelle": cle_a[cle_]["libelle"],
                                  "releves": 0})
        for cle_ in cle_a.keys() & cle_b.keys():
            if cle_a[cle_]["libelle"] != cle_b[cle_]["libelle"]:
                b["renommes"].append({"quoi": quoi, "cle": cle_, "avant": cle_a[cle_]["libelle"],
                                      "apres": cle_b[cle_]["libelle"]})
            if cle_a[cle_]["parent_cle"] != cle_b[cle_]["parent_cle"]:
                b["deplaces"].append({"quoi": quoi, "cle": cle_,
                                      "avant": cle_a[cle_]["parent_cle"],
                                      "apres": cle_b[cle_]["parent_cle"]})
    ea, eb = avant["entrees"], apres["entrees"]
    for cle_ in sorted(eb.keys() - ea.keys(), key=lambda k: eb[k]["rang"]):
        b["nes"].append({"quoi": "entree", "cle": cle_, "libelle": eb[cle_]["libelle"]})
    for cle_ in sorted(ea.keys() - eb.keys()):
        b["disparus"].append({"quoi": "entree", "cle": cle_, "libelle": ea[cle_]["libelle"],
                              "releves": _releves_sur(conn, grille_id, cle_)})
    for cle_ in sorted(ea.keys() & eb.keys(), key=lambda k: eb[k]["rang"]):
        a, n = ea[cle_], eb[cle_]
        if a["libelle"] != n["libelle"]:
            b["renommes"].append({"quoi": "entree", "cle": cle_, "avant": a["libelle"],
                                  "apres": n["libelle"]})
        retouches = [c for c in _CHAMPS_RETOUCHES if a.get(c) != n.get(c)]
        if retouches:
            b["retouches"].append({"quoi": "entree", "cle": cle_, "champs": retouches})
        if a["rubrique_cle"] != n["rubrique_cle"]:
            b["deplaces"].append({"quoi": "entree", "cle": cle_, "avant": a["rubrique_cle"],
                                  "apres": n["rubrique_cle"]})
        for c in _CHAMPS_CHANGES:
            if a.get(c) != n.get(c):
                b["changes"].append({"quoi": "entree", "cle": cle_, "champ": c,
                                     "avant": a.get(c), "apres": n.get(c)})
        va, vb = a["variantes"], n["variantes"]
        for vc in vb.keys() - va.keys():
            b["nes"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                             "libelle": vb[vc]["libelle"]})
        for vc in sorted(va.keys() - vb.keys()):
            b["disparus"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                                  "libelle": va[vc]["libelle"],
                                  "releves": _releves_sur(conn, grille_id, cle_, vc)})
        for vc in va.keys() & vb.keys():
            if va[vc]["libelle"] != vb[vc]["libelle"]:
                b["renommes"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                                      "avant": va[vc]["libelle"], "apres": vb[vc]["libelle"]})
            retouches = [c for c in _CHAMPS_RETOUCHES if va[vc].get(c) != vb[vc].get(c)]
            if retouches:
                b["retouches"].append({"quoi": "variante", "cle": f"{cle_}/{vc}",
                                       "champs": retouches})
    la, lb = avant["listes"], apres["listes"]
    for lc in lb.keys() - la.keys():
        b["nes"].append({"quoi": "liste", "cle": lc, "libelle": lb[lc]["libelle"]})
    for lc in la.keys() - lb.keys():
        b["disparus"].append({"quoi": "liste", "cle": lc, "libelle": la[lc]["libelle"],
                              "releves": 0})
    for lc in la.keys() & lb.keys():
        qa, qb = la[lc]["qualificatifs"], lb[lc]["qualificatifs"]
        for qc in qb.keys() - qa.keys():
            b["nes"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                             "libelle": qb[qc]["libelle"]})
        for qc in qa.keys() - qb.keys():
            n = conn.execute(
                "SELECT COUNT(*) FROM releve_qualificatif rq JOIN releve r "
                "ON r.id = rq.releve_id WHERE r.grille_id = ? AND rq.qualificatif_cle = ?",
                (grille_id, qc)).fetchone()[0] if grille_id is not None else 0
            b["disparus"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                                  "libelle": qa[qc]["libelle"], "releves": n})
        for qc in qa.keys() & qb.keys():
            if qa[qc]["libelle"] != qb[qc]["libelle"]:
                b["renommes"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                                      "avant": qa[qc]["libelle"], "apres": qb[qc]["libelle"]})
            if qa[qc].get("definition") != qb[qc].get("definition"):
                b["retouches"].append({"quoi": "qualificatif", "cle": f"{lc}/{qc}",
                                       "champs": ["definition"]})
    b["releves_touches"] = sum(d["releves"] for d in b["disparus"])
    return b


# --------------------------------------------------------------------------- #
# L'écriture d'une version
# --------------------------------------------------------------------------- #
def ecrire_version(conn: sqlite3.Connection, grille_id: int, c: dict, *, numero: int,
                   etat: str, note, par) -> int:
    """Écrit une version et son plan — toutes ses lignes —, et rend son identifiant. Ne
    commite pas, n'écrit rien au journal (l'appelant le fait)."""
    vid = conn.execute(
        "INSERT INTO grille_version (grille_id, numero, etat, cible, note, empreinte, "
        "importee_par, importee_le) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (grille_id, numero, etat, c["cible"], note, grilles.empreinte(c), par)).lastrowid
    ecrire_plan(conn, vid, c)
    return vid


def ecrire_plan(conn: sqlite3.Connection, vid: int, c: dict) -> None:
    """Les lignes du plan d'une version, depuis un contenu normalisé."""
    conn.executemany(
        "INSERT INTO grille_rubrique (version_id, cle, libelle, parent_cle, rang) "
        "VALUES (?, ?, ?, ?, ?)",
        [(vid, k, r["libelle"], r["parent_cle"], r["rang"]) for k, r in c["rubriques"].items()])
    for k, e in c["entrees"].items():
        conn.execute(
            "INSERT INTO grille_entree (version_id, cle, rubrique_cle, rang, forme, libelle, "
            "definition, structure, piege, precision, lien, cible, cardinalite, liste_cle, "
            "retiree) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vid, k, e["rubrique_cle"], e["rang"], e["forme"], e["libelle"], e["definition"],
             e["structure"], e["piege"], e["precision"], int(bool(e["lien"])), e["cible"],
             e["cardinalite"], e["liste_cle"], int(bool(e.get("retiree")))))
        for i, texte in enumerate(e["exemples"]):
            conn.execute("INSERT INTO grille_exemple (version_id, entree_cle, variante_cle, "
                         "rang, texte) VALUES (?, ?, NULL, ?, ?)", (vid, k, i, texte))
        for vc, x in e["variantes"].items():
            conn.execute(
                "INSERT INTO grille_variante (version_id, entree_cle, cle, libelle, "
                "definition, structure, piege, rang) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (vid, k, vc, x["libelle"], x["definition"], x["structure"], x["piege"],
                 x["rang"]))
            for i, texte in enumerate(x["exemples"]):
                conn.execute("INSERT INTO grille_exemple (version_id, entree_cle, "
                             "variante_cle, rang, texte) VALUES (?, ?, ?, ?, ?)",
                             (vid, k, vc, i, texte))
    for lc, l in c["listes"].items():
        conn.execute("INSERT INTO grille_liste (version_id, cle, libelle) VALUES (?, ?, ?)",
                     (vid, lc, l["libelle"]))
        conn.executemany(
            "INSERT INTO grille_qualificatif (version_id, liste_cle, cle, libelle, "
            "definition, rang) VALUES (?, ?, ?, ?, ?, ?)",
            [(vid, lc, qc, q["libelle"], q["definition"], q["rang"])
             for qc, q in l["qualificatifs"].items()])


def effacer_plan(conn: sqlite3.Connection, vid: int) -> None:
    """Retire les lignes du plan d'une version (un brouillon qu'on remplace)."""
    for t in ("grille_rubrique", "grille_entree", "grille_variante", "grille_liste",
              "grille_qualificatif", "grille_exemple"):
        conn.execute(f"DELETE FROM {t} WHERE version_id = ?", (vid,))


# --------------------------------------------------------------------------- #
# L'import — le geste entier, partagé par l'outil et la route
# --------------------------------------------------------------------------- #
def nom_pris(conn: sqlite3.Connection, projet_id: int, nom: str, *, sauf=None) -> bool:
    """Le nom est-il celui d'une autre grille de ce projet ? Comparé par la clé d'un
    libellé (`database.cle_tag` : casse, apostrophes, espaces), dans le projet SEUL —
    aucune unicité d'instance, donc aucun oracle « ce nom est pris ailleurs »."""
    return conn.execute(
        "SELECT 1 FROM grille WHERE projet_id = ? AND cle_tag(nom) = cle_tag(?) "
        "AND id IS NOT ?", (projet_id, nom, sauf)).fetchone() is not None


def importer(conn: sqlite3.Connection, *, projet_id: int, flux_entrees, flux_listes=None,
             grille_id: int | None = None, nom: str | None = None, ouverte: bool = False,
             porte_sur: str | None = None, note: str | None = None, par=None,
             a_blanc: bool = False) -> dict:
    """Importe un tableur comme version d'une grille — neuve (`nom`), ou suivante d'une grille
    existante de ce projet (`grille_id`). Le droit de l'appelant est vérifié AVANT (gérer le
    projet) ; ici, les règles du modèle :

    - une grille FERMÉE a au plus un brouillon : réimporter le REMPLACE ; si la dernière
      version est publiée, un brouillon neuf naît, au numéro suivant — sauf si son empreinte
      est celle de la version publiée, ou du brouillon en place : « aucun changement », rien
      n'est écrit ;
    - une grille OUVERTE n'a qu'une version, `vivante`, née au premier import ; elle
      s'enrichit EN POSANT (G14) — la réimporter avec un autre contenu est refusé (409,
      option la plus fermée, à trancher : remplacer écraserait les entrées nées en posant).

    `a_blanc` : rend le bilan sans rien écrire. Lève `Refus` (statut, message, anomalies),
    `FormatInvalide` sur un en-tête. Ne commite pas ; écrit au journal sous `grille` (sauf à
    blanc). Rend `{grille_id, version: {numero, etat} | None, ecrit, aucun_changement, bilan,
    compare_a, avertissements}`."""
    import journal                               # import paresseux : le cœur reste léger
    g = None
    if grille_id is not None:
        g = conn.execute("SELECT * FROM grille WHERE id = ? AND projet_id = ?",
                         (grille_id, projet_id)).fetchone()
        if g is None:
            raise Refus(404, f"Grille {grille_id} introuvable dans ce projet.")
        if g["retiree_le"]:
            raise Refus(409, "Cette grille est retirée : on ne lui importe plus de version.")
        ouverte = bool(g["ouverte"])
    else:
        nom = propre(nom)
        if not nom:
            raise Refus(422, "Une grille neuve a besoin d'un nom.")
        if nom_pris(conn, projet_id, nom):
            raise Refus(409, f"Une grille de ce projet s'appelle déjà « {nom} » : importez "
                             "une version suivante de celle-ci, ou choisissez un autre nom.")
    reference = None                          # la version à laquelle on compare
    if g is not None:
        reference = grilles.derniere_version(conn, g["id"], grilles.ETAT_PUBLIEE,
                                             grilles.ETAT_VIVANTE)
        if porte_sur is None:
            derniere = grilles.derniere_version(conn, g["id"])
            porte_sur = (" | ".join(grilles.cibles_de(derniere["cible"]))
                         if derniere is not None else None)
    lu = lire(flux_entrees, flux_listes, porte_sur=porte_sur)
    if lu["anomalies"]:
        raise Refus(422, f"Le tableur est refusé : {len(lu['anomalies'])} anomalie(s). "
                         "Rien n'est importé.", lu["anomalies"])
    c = lu["contenu"]
    avant = grilles.contenu(conn, reference["id"]) if reference is not None else None
    b = bilan(conn, g["id"] if g is not None else None, avant, c)
    emp = grilles.empreinte(c)
    brouillon = (grilles.derniere_version(conn, g["id"], grilles.ETAT_BROUILLON)
                 if g is not None else None)
    resultat = {"grille_id": g["id"] if g is not None else None, "version": None,
                "ecrit": False, "aucun_changement": False, "bilan": b,
                "compare_a": reference["numero"] if reference is not None else None,
                "avertissements": lu["avertissements"]}
    deja = [v for v in (reference, brouillon) if v is not None and v["empreinte"] == emp]
    if deja:
        resultat["aucun_changement"] = True
        resultat["version"] = {"numero": deja[0]["numero"], "etat": deja[0]["etat"]}
        return resultat
    if ouverte and g is not None and reference is not None:
        raise Refus(409, "Une grille ouverte s'enrichit en posant : la réimporter avec un "
                         "autre contenu remplacerait les entrées nées en posant. Rien n'est "
                         "importé.")
    if a_blanc:
        if brouillon is not None:
            resultat["version"] = {"numero": brouillon["numero"], "etat": brouillon["etat"],
                                   "remplace": True}
        return resultat
    if g is None:
        gid = conn.execute("INSERT INTO grille (projet_id, nom, ouverte, cree_par) "
                           "VALUES (?, ?, ?, ?)", (projet_id, nom, int(bool(ouverte)),
                                                   par)).lastrowid
        journal.journaliser(conn, "creation", "grille", gid,
                            apres={"projet_id": projet_id, "nom": nom,
                                   "ouverte": bool(ouverte)})
        resultat["grille_id"] = gid
    else:
        gid = g["id"]
    etat = grilles.ETAT_VIVANTE if ouverte else grilles.ETAT_BROUILLON
    if brouillon is not None:
        effacer_plan(conn, brouillon["id"])
        conn.execute("UPDATE grille_version SET cible = ?, note = ?, empreinte = ?, "
                     "importee_par = ?, importee_le = datetime('now') WHERE id = ?",
                     (c["cible"], note, emp, par, brouillon["id"]))
        ecrire_plan(conn, brouillon["id"], c)
        numero = brouillon["numero"]
    else:
        derniere = grilles.derniere_version(conn, gid)
        numero = (derniere["numero"] + 1) if derniere is not None else 1
        ecrire_version(conn, gid, c, numero=numero, etat=etat, note=note, par=par)
    journal.journaliser(conn, "modification", "grille", gid,
                        apres={"import": {"numero": numero, "etat": etat, "empreinte": emp,
                                          "remplace": brouillon is not None}})
    resultat.update(ecrit=True, version={"numero": numero, "etat": etat,
                                         **({"remplace": True} if brouillon else {})})
    return resultat


# --------------------------------------------------------------------------- #
# Le réexport — le tableur, identifiants compris
# --------------------------------------------------------------------------- #
def _cellule_cibles(valeur) -> str:
    return " | ".join(grilles.cibles_de(valeur))


def exporter(conn: sqlite3.Connection, version_id: int) -> tuple[str, str]:
    """Les deux CSV d'une version, au format de l'import, identifiants compris : le chemin
    de la DÉRIVATION allégée (réexporter, réimporter comme grille de son projet, tranché le
    2026-10-22), et la seule façon de vérifier les `cle` par aller-retour. Réimporté tel
    quel, il rend la même empreinte (`tests/test_grilles.py`)."""
    c = grilles.contenu(conn, version_id)

    def ligne(**valeurs):
        return [_neutre(valeurs.get(col)) for col in COLONNES]
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    w.writerow(COLONNES)
    for cle_, e in sorted(c["entrees"].items(), key=lambda kv: kv[1]["rang"]):
        chemin = grilles.chemin_de_rubrique(c["rubriques"], e["rubrique_cle"])
        w.writerow(ligne(
            cle=cle_, rubrique=" > ".join(c["rubriques"][r]["libelle"] for r in chemin),
            rubrique_cle=" > ".join(chemin), forme=e["forme"], libelle=e["libelle"],
            structure=e["structure"], definition=e["definition"],
            exemples=" | ".join(e["exemples"]), piege=e["piege"], liste=e["liste_cle"],
            precision=e["precision"], lien="oui" if e["lien"] else "",
            cible=_cellule_cibles(e["cible"]), cardinalite=e["cardinalite"]))
        for vc, x in sorted(e["variantes"].items(), key=lambda kv: kv[1]["rang"]):
            w.writerow(ligne(cle=cle_, variante_cle=vc, variante=x["libelle"],
                             structure=x["structure"], definition=x["definition"],
                             exemples=" | ".join(x["exemples"]), piege=x["piege"]))
    listes = io.StringIO()
    w = csv.writer(listes, delimiter=";", lineterminator="\r\n")
    w.writerow(COLONNES_LISTES)
    for lc, l in sorted(c["listes"].items()):
        for qc, q in sorted(l["qualificatifs"].items(), key=lambda kv: kv[1]["rang"]):
            w.writerow([_neutre(x) for x in (lc, l["libelle"], qc, q["libelle"],
                                             q["definition"])])
    return sortie.getvalue(), listes.getvalue()


def archive(conn: sqlite3.Connection, version_id: int) -> bytes:
    """Le zip du réexport : les deux CSV, en UTF-8 AVEC BOM (pour qu'un tableur lise les
    accents), sous leurs noms d'import (`NOMS_FICHIERS`)."""
    entrees, listes = exporter(conn, version_id)
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(NOMS_FICHIERS[0], "﻿" + entrees)
        z.writestr(NOMS_FICHIERS[1], "﻿" + listes)
    return tampon.getvalue()
