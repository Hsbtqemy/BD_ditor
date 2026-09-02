"""Socle commun des routes de l'API — dépendances, helpers, accesseurs gardés.  ARCH-1.

`main.py` a franchi les 4 400 lignes pour 125 routes, contre un seuil de 3 200 déclaré
dans `pilotage/journal.config.mjs`. Le découpage se fait par DOMAINE (`routes/`), et ce
module porte ce dont tous les domaines dépendent — mesuré avant de découper : chaque bloc
de main.py n'utilisait que 5 à 20 noms définis ailleurs, et presque toujours les mêmes.

**Ce module ne définit AUCUNE route.** Il n'importe pas `main`, ce qui garantit l'absence
de cycle : `routes/*` importe `socle`, `main` importe `routes/*`.

Deux choses y gagnent plus qu'un rangement.

Les **accesseurs gardés** (`_get_album`, `_get_planche`, `_get_region`) sont, dit
CLAUDE.md, « la seule façon d'atteindre un objet du corpus ». C'était jusqu'ici une
convention : rien n'empêchait un nouveau bloc d'écrire son propre `SELECT * FROM albums`.
Les rassembler dans un module que les routes doivent IMPORTER en fait une contrainte
qu'on voit, sans rien changer à leur comportement.

Et `main.py` **ré-exporte** tout ce qui suit. Ce n'est pas de la compatibilité par
paresse : `tests/test_autorisation.py` compare l'IDENTITÉ de `main.portee_courante` aux
dépendances de chaque route, et `tests/test_sorties_identite.py` balaie les routes depuis
`main`. Le ré-export garde ces cliquets exacts sans qu'une ligne en soit réécrite — ce que
la fiche ARCH-1 posait comme condition du découpage.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from typing import Iterator, Optional

from fastapi import Depends, HTTPException, Request, Response

import autorisation
from database import get_connection

# --------------------------------------------------------------------------- #
# Dépendance connexion
# --------------------------------------------------------------------------- #


def db() -> Iterator[sqlite3.Connection]:
    """Une connexion par requête. Le commit est fait EXPLICITEMENT dans chaque
    route d'écriture (et non après le yield) : le code post-yield d'une
    dépendance FastAPI s'exécute APRÈS l'envoi de la réponse, ce qui rendait
    une écriture invisible à une lecture immédiate (course écriture→lecture).
    Ici la dépendance ne gère que le rollback en cas d'erreur et la fermeture.
    """
    conn = get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def portee_courante(request: Request,
                    conn: sqlite3.Connection = Depends(db)) -> autorisation.Portee:
    """Dépendance FastAPI : la portée d'autorisation de la requête courante (AUTH-2).

    Enveloppe minuscule autour de `autorisation.resoudre` — la logique vit dans le module,
    pas ici. Toute route qui touche aux données du corpus déclare CETTE dépendance ; c'est
    ce que vérifie `tests/test_autorisation.py`, qui échoue si une route l'oublie.
    """
    return autorisation.resoudre(conn, request)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _row(cur) -> Optional[dict]:
    r = cur.fetchone()
    return dict(r) if r else None


# --------------------------------------------------------------------------- #
# Helpers métier
# --------------------------------------------------------------------------- #
def _norm_tag(label: str) -> str:
    """Tags insensibles à la casse, stockés en minuscules, espaces compactés."""
    return " ".join(label.strip().lower().split())


def _sans_accents(s: str) -> str:
    """Minuscule sans diacritiques — pour une autocomplétion insensible aux accents
    (« etienne » trouve « Étienne »)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _ensure_tags(conn: sqlite3.Connection, labels: list[str]) -> list[dict]:
    """Crée les tags manquants et renvoie les lignes correspondantes."""
    normalized = sorted({_norm_tag(l) for l in labels if _norm_tag(l)})
    for label in normalized:
        conn.execute(
            "INSERT INTO tags (label) VALUES (?) ON CONFLICT(label) DO NOTHING",
            (label,),
        )
    if not normalized:
        return []
    placeholders = ",".join("?" * len(normalized))
    return _rows(conn.execute(
        f"SELECT id, label, couleur FROM tags WHERE label IN ({placeholders})",
        normalized,
    ))


def _annotation_for_region(conn: sqlite3.Connection, region_id: int) -> dict:
    """Représentation d'annotation (note + tags) ; structure vide si absente."""
    ann = conn.execute(
        "SELECT id, note, date_creation, date_modification "
        "FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()
    if ann is None:
        return {"region_id": region_id, "note": None, "tags": [],
                "date_modification": None}
    tags = _rows(conn.execute(
        """SELECT t.id, t.label, t.couleur
           FROM annotation_tags at JOIN tags t ON t.id = at.tag_id
           WHERE at.annotation_id = ? ORDER BY t.label""",
        (ann["id"],),
    ))
    return {"region_id": region_id, "note": ann["note"], "tags": tags,
            "date_modification": ann["date_modification"]}


# --------------------------------------------------------------------------- #
# Accesseurs GARDÉS (AUTH-2) — la seule façon d'atteindre un objet du corpus
# --------------------------------------------------------------------------- #
# Chacun exige une `Portee` et renvoie 404 quand l'objet existe mais sort d'elle. Le 404
# n'est pas une approximation du 403 : dire « cet album existe, mais pas pour vous »
# révélerait la composition du corpus — combien d'albums, quelles études voisines. La
# contrepartie est à connaître : qui perd un droit ne verra pas d'erreur, ses objets
# auront simplement disparu.
#
# La `Portee` est un paramètre OBLIGATOIRE, sans valeur par défaut. Une valeur par défaut
# qui sauterait le contrôle rendrait l'oubli invisible — c'est exactement le motif que
# SANTE-1 vient de corriger ailleurs dans ce dépôt.

def _get_album(conn, portee: autorisation.Portee, album_id: int, *,
               ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("albums.id", ecriture=ecriture)
    a = _row(conn.execute(f"SELECT * FROM albums WHERE id = ? AND {ou}",
                          (album_id, *params)))
    if a is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    return a


def _get_planche(conn, portee: autorisation.Portee, planche_id: int, *,
                 ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("planches.album_id", ecriture=ecriture)
    p = _row(conn.execute(f"SELECT * FROM planches WHERE id = ? AND {ou}",
                          (planche_id, *params)))
    if p is None:
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    return p


def _get_region(conn, portee: autorisation.Portee, region_id: int, *,
                ecriture: bool = False) -> dict:
    """Une région s'autorise par sa planche, qui s'autorise par son album."""
    ou, params = portee.clause_album("pl.album_id", ecriture=ecriture)
    r = _row(conn.execute(
        f"SELECT r.* FROM regions r JOIN planches pl ON pl.id = r.planche_id "
        f"WHERE r.id = ? AND {ou}", (region_id, *params)))
    if r is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return r


def _refuser_si_verrouillee(planche: dict) -> dict:
    """Une planche verrouillée est protégée des passes AUTOMATIQUES (segmentation /
    détection de bulles / OCR) : il faut la déverrouiller explicitement. L'édition
    manuelle (texte, tags, régions) reste libre. Renvoie la planche pour chaînage."""
    if planche.get("verrouillee"):
        raise HTTPException(409, "Planche verrouillée 🔒 : déverrouillez-la pour "
                            "relancer un traitement automatique "
                            "(l'édition manuelle reste possible).")
    return planche


def _validate_parent(conn: sqlite3.Connection, planche_id: int,
                     parent_id: Optional[int], region_id: Optional[int] = None) -> None:
    """Valide un parent_id : il doit exister, être sur LA MÊME planche, et ne pas
    créer de cycle (ni s'auto-référencer). Lève HTTPException 422 sinon. Une FK
    seule ne garantit pas ces invariants — sans quoi une région cross-planche ou
    un cycle casse l'export (région omise) et fait boucler le DELETE récursif."""
    if parent_id is None:
        return
    parent = _row(conn.execute(
        "SELECT planche_id FROM regions WHERE id = ?", (parent_id,)))
    if parent is None:
        raise HTTPException(422, f"parent_id {parent_id} introuvable")
    if parent["planche_id"] != planche_id:
        raise HTTPException(422, "parent_id appartient à une autre planche")
    if region_id is not None:
        if parent_id == region_id:
            raise HTTPException(422, "Une région ne peut pas être son propre parent")
        # parent_id ne doit pas être un descendant de region_id (UNION → termine
        # même si la base contient déjà un cycle).
        descendants = {r["id"] for r in conn.execute(
            """WITH RECURSIVE d(id) AS (
                   SELECT id FROM regions WHERE id = ?
                   UNION
                   SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
               ) SELECT id FROM d""", (region_id,))}
        if parent_id in descendants:
            raise HTTPException(422, "parent_id créerait un cycle")

# --------------------------------------------------------------------------- #
# Sortie CSV — partagée par la recherche et l'export (ARCH-1)
# --------------------------------------------------------------------------- #
# Ces trois-là vivaient dans le bloc Recherche, où l'Export allait les chercher. Le
# découpage rend la dépendance visible au lieu de la laisser au hasard du voisinage —
# et `_csv_safe` porte une règle de sécurité (anti-injection de formule) qui gagne au
# même titre que les accesseurs gardés à être un import plutôt qu'une convention.
_BOM = chr(0xFEFF)   # BOM UTF-8 : permet à Excel (Windows) de lire les accents correctement


def _csv_response(contenu: str, filename: str) -> Response:
    """Réponse CSV téléchargeable, préfixée d'un BOM UTF-8 pour qu'Excel (Windows) lise
    correctement les accents français. (R/pandas : lire en `utf-8-sig`.)"""
    return Response(content=_BOM + contenu, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _csv_safe(v):
    """Neutralise l'injection de FORMULE (CSV → tableur) : une cellule TEXTE débutant par
    `= + - @` (ou tab/CR) est préfixée d'une apostrophe → un tableur l'affiche littéralement
    au lieu de l'exécuter. À n'appliquer qu'au texte libre (pas aux nombres : « -5 » reste un
    nombre). Cf. OWASP « CSV Injection »."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v
