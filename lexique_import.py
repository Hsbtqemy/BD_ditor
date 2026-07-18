"""Amorçage en lot du VOCABULAIRE analytique (piste B) — cœur partagé.

Logique de parsing + upsert d'un tableur CSV (domaines → dimensions → valeurs + couche
lexique SKOS A4), commune à l'outil headless `tools/importer_vocabulaire.py` et à la route
`POST /api/lexique/importer` (bouton « Importer » du panneau 📖 Lexique). Aucune I/O propre :
on reçoit un FLUX de texte (fichier ou tampon décodé) et une CONNEXION — l'appelant gère
l'ouverture du fichier et la transaction.

Doctrine « pré-remplir, jamais écraser » (comme l'OCR, `pipeline/ocr.py`, `only_empty=True`) :
un terme déjà présent est RÉUTILISÉ (idempotent) ; sa `definition` / `note_portee` n'est
renseignée QUE si elle est encore vide ; le rattachement au domaine et la portée
(`collection_id`) ne se posent qu'à la CRÉATION du terme. L'état (`provisoire`→`defini`) et
sa validation restent des actes humains dans l'app. Cf. docs/import-vocabulaire.md.
"""
from __future__ import annotations

import csv
import sqlite3

CIBLES = ("personnage", "case")
COLONNES = ("domaine", "domaine_definition", "cible", "dimension", "dimension_definition",
            "dimension_note_portee", "valeur", "valeur_definition")


class FormatInvalide(ValueError):
    """En-tête inexploitable (colonnes obligatoires absentes) : erreur de FORMAT, pas de
    données. L'outil la transforme en message CLI, la route en HTTP 400."""


def _norm(nom) -> str:
    """Nom canonique, IDENTIQUE à l'app (`main._norm_tag`) : minuscule, espaces compactés.
    Garantit que l'import et la création émergente convergent sur la même forme."""
    return " ".join((nom or "").strip().lower().split())


def _txt(v):
    """Cellule de texte libre → contenu nettoyé, ou None si vide (une définition vide veut
    dire « non fournie », pas « effacer »)."""
    v = (v or "").strip()
    return v or None


# --------------------------------------------------------------------------- #
# Lecture / validation
# --------------------------------------------------------------------------- #
def lire(flux) -> tuple[list[dict], list[str]]:
    """Analyse un flux de texte CSV (point-virgule) → (lignes valides, anomalies). Une ligne
    invalide (dimension vide, cible inconnue) est ÉCARTÉE et signalée ; une ligne entièrement
    vide est ignorée en silence. Lecture par nom de colonne (ordre libre, colonnes en trop
    tolérées). Lève `FormatInvalide` si une colonne obligatoire manque."""
    lignes, anomalies = [], []
    lecteur = csv.DictReader(flux, delimiter=";")
    entete = lecteur.fieldnames or []
    manquantes = [c for c in ("cible", "dimension") if c not in entete]
    if manquantes:
        raise FormatInvalide(
            f"En-tête invalide : colonnes obligatoires manquantes {manquantes}. "
            f"Attendu (point-virgule) : {';'.join(COLONNES)}")
    for i, brut in enumerate(lecteur, start=2):          # ligne 1 = en-tête
        domaine, cible = _norm(brut.get("domaine")), _norm(brut.get("cible"))
        dimension, valeur = _norm(brut.get("dimension")), _norm(brut.get("valeur"))
        if not (domaine or dimension or valeur):
            continue                                     # ligne blanche → ignorée
        if not dimension:
            anomalies.append(f"L.{i} : dimension vide — ligne ignorée")
            continue
        if cible not in CIBLES:
            anomalies.append(
                f"L.{i} : cible « {(brut.get('cible') or '').strip()} » invalide "
                f"(attendu : {' | '.join(CIBLES)}) — ligne ignorée")
            continue
        lignes.append({
            "no": i, "domaine": domaine, "cible": cible, "dimension": dimension,
            "valeur": valeur,
            "domaine_def": _txt(brut.get("domaine_definition")),
            "dimension_def": _txt(brut.get("dimension_definition")),
            "dimension_note": _txt(brut.get("dimension_note_portee")),
            "valeur_def": _txt(brut.get("valeur_definition"))})
    return lignes, anomalies


# --------------------------------------------------------------------------- #
# Écriture (upsert « pré-remplir sans écraser »)
# --------------------------------------------------------------------------- #
def _upsert(conn, table, cle: dict, creation: dict, fill: dict) -> tuple[int, bool]:
    """Upsert idempotent d'un terme. `cle` = clé naturelle (WHERE + posée à la création) ;
    `creation` = colonnes fixées SEULEMENT à la création (portée) ; `fill` = colonnes
    définitionnelles remplies uniquement si ENCORE vides (jamais d'écrasement). Renvoie
    (id, cree). Ne commit pas : l'appelant gère la transaction."""
    where = " AND ".join(f"{k} = ?" for k in cle)
    row = conn.execute(f"SELECT * FROM {table} WHERE {where}", tuple(cle.values())).fetchone()
    if row is None:
        cols = {**cle, **creation, **fill}
        cur = conn.execute(f"INSERT INTO {table} ({','.join(cols)}) "
                           f"VALUES ({','.join('?' * len(cols))})", tuple(cols.values()))
        return cur.lastrowid, True          # id = INTEGER PRIMARY KEY → lastrowid fiable
    a_poser = {k: v for k, v in fill.items()
               if v is not None and (row[k] is None or str(row[k]).strip() == "")}
    if a_poser:
        conn.execute(f"UPDATE {table} SET {', '.join(f'{k} = ?' for k in a_poser)} "
                     f"WHERE id = ?", (*a_poser.values(), row["id"]))
    return row["id"], False


def _divergence(memo, cle, champ, valeur, avert, quoi):
    """Signale (sans bloquer) deux valeurs DIFFÉRENTES pour un même champ définitionnel dans
    le fichier — faute de saisie typique. La première rencontrée fait foi (cohérent avec le
    « ne jamais écraser » côté base)."""
    if valeur is None:
        return
    ancienne = memo.get((cle, champ))
    if ancienne is None:
        memo[(cle, champ)] = valeur
    elif ancienne != valeur:
        avert.append(f"{quoi} : deux « {champ} » divergentes (« {ancienne} » ≠ "
                     f"« {valeur} ») — la première est retenue")


def importer(conn, lignes, collection_id) -> tuple[dict, list[str]]:
    """Applique les lignes déjà validées. Renvoie (résumé, avertissements). Chaque palier
    est compté UNE fois (à sa première rencontre), en distinguant créés / déjà présents."""
    res = {k: {"cree": 0, "existant": 0} for k in ("domaines", "dimensions", "valeurs")}
    avert, memo, vus = [], {}, set()

    def _compter(palier, cle, cree):
        if cle not in vus:
            vus.add(cle)
            res[palier]["cree" if cree else "existant"] += 1

    for r in lignes:
        domaine_id = None
        if r["domaine"]:
            _divergence(memo, ("dom", r["domaine"]), "domaine_definition",
                        r["domaine_def"], avert, f"domaine « {r['domaine']} »")
            domaine_id, cree = _upsert(
                conn, "domaine", {"nom": r["domaine"]},
                {"collection_id": collection_id}, {"definition": r["domaine_def"]})
            _compter("domaines", ("dom", r["domaine"]), cree)

        cle_dim = ("dim", r["cible"], r["dimension"])
        _divergence(memo, cle_dim, "dimension_definition", r["dimension_def"], avert,
                    f"dimension « {r['cible']}/{r['dimension']} »")
        _divergence(memo, cle_dim, "note_portee", r["dimension_note"], avert,
                    f"dimension « {r['cible']}/{r['dimension']} »")
        if r["domaine"]:
            _divergence(memo, cle_dim, "domaine", r["domaine"], avert,
                        f"dimension « {r['cible']}/{r['dimension']} »")
        dim_id, cree = _upsert(
            conn, "attribut_dimension", {"cible": r["cible"], "nom": r["dimension"]},
            {"collection_id": collection_id},
            {"domaine_id": domaine_id, "definition": r["dimension_def"],
             "note_portee": r["dimension_note"]})
        _compter("dimensions", cle_dim, cree)

        if r["valeur"]:
            cle_val = ("val", dim_id, r["valeur"])
            _divergence(memo, cle_val, "valeur_definition", r["valeur_def"], avert,
                        f"valeur « {r['dimension']}/{r['valeur']} »")
            _, cree = _upsert(
                conn, "attribut_valeur", {"dimension_id": dim_id, "valeur": r["valeur"]},
                {"collection_id": collection_id}, {"definition": r["valeur_def"]})
            _compter("valeurs", cle_val, cree)
    return res, avert
