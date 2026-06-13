"""Wrapper Kumiko : détection automatique des cases d'une planche.

Kumiko (https://github.com/njean42/kumiko) est exécuté en sous-processus sur le
dérivé web (rapide) ; les coordonnées renvoyées, exprimées dans l'espace pixel
de l'image fournie, sont reconverties en pixels MASTER avant insertion en base
(source='kumiko'). Passer `use_master=True` pour segmenter directement le TIFF
haute résolution.

Kumiko doit être cloné dans lib/kumiko :
    git clone https://github.com/njean42/kumiko.git lib/kumiko
    pip install -r lib/kumiko/requirements.txt
"""
from __future__ import annotations

import json
import subprocess
import sys
import sqlite3
import tempfile
from pathlib import Path

from config import DATA_DIR, KUMIKO_DIR
from database import reindex_region, unindex_region
from pipeline.ordering import reorder_planche

KUMIKO_ENTRY = KUMIKO_DIR / "kumiko"


class KumikoError(RuntimeError):
    """Erreur d'exécution de Kumiko (absent, échec, sortie illisible)."""


def kumiko_available() -> bool:
    return KUMIKO_ENTRY.is_file()


def _normalize_panel(panel) -> tuple[int, int, int, int]:
    """Accepte [x,y,w,h] (format historique) ou un dict, renvoie un tuple int."""
    try:
        if isinstance(panel, dict):
            if all(k in panel for k in ("x", "y", "w", "h")):
                x, y, w, h = panel["x"], panel["y"], panel["w"], panel["h"]
            else:  # certaines variantes : {"coords": [x, y, w, h]}
                x, y, w, h = panel.get("coords") or panel.get("bbox")
        else:
            x, y, w, h = panel[0], panel[1], panel[2], panel[3]
        return int(round(x)), int(round(y)), int(round(w)), int(round(h))
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        raise KumikoError(f"Panneau Kumiko illisible : {panel!r}") from exc


def run_kumiko(image_path: Path) -> dict:
    """Exécute Kumiko sur une image et renvoie la page (dict avec size/panels)."""
    if not kumiko_available():
        raise KumikoError(
            f"Kumiko introuvable dans {KUMIKO_DIR}. Clonez-le :\n"
            "  git clone https://github.com/njean42/kumiko.git lib/kumiko"
        )

    image_path = Path(image_path).resolve()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [sys.executable, str(KUMIKO_ENTRY),
             "-i", str(image_path), "-o", str(out_path)],
            cwd=str(KUMIKO_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise KumikoError(
                f"Kumiko a échoué (code {proc.returncode}).\n{proc.stderr.strip()}"
            )
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired as exc:
        raise KumikoError(f"Kumiko a dépassé le délai ({exc.timeout}s)") from exc
    except json.JSONDecodeError as exc:
        raise KumikoError(f"Sortie Kumiko illisible : {exc}") from exc
    finally:
        out_path.unlink(missing_ok=True)

    # Kumiko renvoie une liste de pages ; on traite une image à la fois.
    if isinstance(data, list):
        if not data:
            raise KumikoError("Sortie Kumiko inattendue : aucune page renvoyée")
        page = data[0]
    else:
        page = data
    if not isinstance(page, dict) or "panels" not in page:
        raise KumikoError("Sortie Kumiko inattendue : clé 'panels' absente")
    return page


def _reattach_orphans(conn: sqlite3.Connection, planche_id: int) -> int:
    """Ré-rattache les régions orphelines (≠ case) à la plus petite case dont
    elles ont le centre — préserve le rattachement OCR/annotations à travers une
    re-segmentation. Renvoie le nombre de régions ré-rattachées."""
    cases = [dict(r) for r in conn.execute(
        "SELECT id, x, y, w, h FROM regions "
        "WHERE planche_id = ? AND type = 'case'", (planche_id,)).fetchall()]
    if not cases:
        return 0
    n = 0
    orphans = conn.execute(
        "SELECT id, x, y, w, h FROM regions "
        "WHERE planche_id = ? AND parent_id IS NULL AND type != 'case'",
        (planche_id,)).fetchall()
    for o in orphans:
        cx = (o["x"] or 0) + (o["w"] or 0) / 2
        cy = (o["y"] or 0) + (o["h"] or 0) / 2
        inside = [c for c in cases
                  if (c["x"] or 0) <= cx <= (c["x"] or 0) + (c["w"] or 0)
                  and (c["y"] or 0) <= cy <= (c["y"] or 0) + (c["h"] or 0)]
        if inside:
            parent = min(inside, key=lambda c: (c["w"] or 0) * (c["h"] or 0))["id"]
            conn.execute("UPDATE regions SET parent_id = ? WHERE id = ?",
                         (parent, o["id"]))
            n += 1
    return n


def _best_overlap(old: dict, new_cases: list[dict]):
    """Id de la nouvelle case dont l'intersection avec `old` est maximale, sinon None."""
    best, best_area = None, 0
    ox, oy = old["x"] or 0, old["y"] or 0
    ox2, oy2 = ox + (old["w"] or 0), oy + (old["h"] or 0)
    for c in new_cases:
        cx0, cy0 = c["x"] or 0, c["y"] or 0
        ix = min(ox2, cx0 + (c["w"] or 0)) - max(ox, cx0)
        iy = min(oy2, cy0 + (c["h"] or 0)) - max(oy, cy0)
        area = max(0, ix) * max(0, iy)
        if area > best_area:
            best_area, best = area, c["id"]
    return best


def _transfer_case_annotations(conn: sqlite3.Connection, old_cases: list[dict],
                               new_cases: list[dict]) -> list[int]:
    """Transfère l'annotation d'une ancienne case vers la NOUVELLE case qui la
    recouvre le mieux (préserve note + tags de panneau à travers une
    re-segmentation). Re-pointe la ligne `annotations` et ré-indexe le FTS.
    Renvoie la liste des id d'anciennes cases dont l'annotation a été transférée ;
    celles qui restent annotées (non transférables) seront conservées par
    l'appelant plutôt que supprimées (aucune perte de travail humain)."""
    transferred = []
    for old in old_cases:
        if conn.execute("SELECT 1 FROM annotations WHERE region_id = ?",
                        (old["id"],)).fetchone() is None:
            continue
        best = _best_overlap(old, new_cases)
        if best is None:
            continue
        if conn.execute("SELECT 1 FROM annotations WHERE region_id = ?",
                        (best,)).fetchone() is not None:
            continue                       # nouvelle case déjà annotée (UNIQUE) → 1re gagne
        conn.execute("UPDATE annotations SET region_id = ? WHERE region_id = ?",
                     (best, old["id"]))
        unindex_region(conn, old["id"])
        reindex_region(conn, best)
        transferred.append(old["id"])
    return transferred


def segment_planche(conn: sqlite3.Connection, planche_id: int,
                    use_master: bool = False, replace: bool = True) -> dict:
    """Segmente une planche avec Kumiko et insère les cases détectées.

    Renvoie {'planche_id', 'nb_cases', 'reattaches', 'annotations_transferees',
    'annotations_preservees', 'regions'}. Les cases Kumiko précédentes sont
    remplacées par défaut (`replace=True`) ; les régions manuelles / corrigées
    sont préservées, les bulles océrisées ré-rattachées, et l'annotation d'une
    ancienne case suit la nouvelle case qui la recouvre le mieux — ou, à défaut
    de recouvrement, l'ancienne case annotée est conservée (aucune perte).
    """
    planche = conn.execute(
        "SELECT id, chemin_web, chemin_tiff, largeur_px, hauteur_px "
        "FROM planches WHERE id = ?",
        (planche_id,),
    ).fetchone()
    if planche is None:
        raise ValueError(f"Planche {planche_id} inexistante")

    master_w = planche["largeur_px"]
    master_h = planche["hauteur_px"]

    if use_master and planche["chemin_tiff"]:
        image_path = DATA_DIR / planche["chemin_tiff"]
    else:
        image_path = DATA_DIR / planche["chemin_web"]

    page = run_kumiko(image_path)
    size = page.get("size") or [master_w, master_h]
    if not isinstance(size, (list, tuple)) or len(size) < 2:
        size = [master_w, master_h]
    in_w, in_h = size[0] or master_w, size[1] or master_h

    # Facteurs de conversion espace-image → espace-master.
    scale_x = master_w / in_w if in_w else 1.0
    scale_y = master_h / in_h if in_h else 1.0

    # replace : re-segmenter NE DOIT PAS détruire le travail humain. On CAPTURE
    # les anciennes cases Kumiko (géométrie) et on DÉTACHE leurs enfants (bulles
    # océrisées, régions manuelles deviennent orphelins, préservés) — mais on ne
    # supprime pas encore : on a besoin des nouvelles cases pour transférer les
    # annotations de case et ré-rattacher les orphelins par géométrie.
    old_cases, old_ids, ph = [], (), ""
    if replace:
        old_cases = [dict(r) for r in conn.execute(
            "SELECT id, x, y, w, h FROM regions "
            "WHERE planche_id = ? AND source = 'kumiko'", (planche_id,)).fetchall()]
        old_ids = tuple(c["id"] for c in old_cases)
        if old_ids:
            ph = ",".join("?" * len(old_ids))
            conn.execute(f"UPDATE regions SET parent_id = NULL WHERE parent_id IN ({ph})",
                         old_ids)

    regions = []
    for ordre, panel in enumerate(page["panels"], start=1):
        x, y, w, h = _normalize_panel(panel)
        # Conversion vers les pixels master.
        mx, my = round(x * scale_x), round(y * scale_y)
        mw, mh = round(w * scale_x), round(h * scale_y)
        cur = conn.execute(
            """
            INSERT INTO regions
                (planche_id, parent_id, type, x, y, w, h, ordre, source)
            VALUES (?, NULL, 'case', ?, ?, ?, ?, ?, 'kumiko')
            """,
            (planche_id, mx, my, mw, mh, ordre),
        )
        regions.append({
            "id": cur.lastrowid, "type": "case",
            "x": mx, "y": my, "w": mw, "h": mh,
            "ordre": ordre, "source": "kumiko",
        })

    # replace : transfère les annotations de case (ancienne → nouvelle case qui la
    # recouvre le mieux), CONSERVE les anciennes cases encore annotées (transfert
    # impossible) plutôt que de les supprimer, et supprime le reste (FTS nettoyé).
    transferred, preserved = [], []
    if old_ids:
        transferred = _transfer_case_annotations(conn, old_cases, regions)
        # Après transfert, une ancienne case qui PORTE ENCORE une annotation n'a
        # pas pu être transférée (aucune nouvelle case ne la recouvre, ou cible
        # déjà annotée) : on la conserve — jamais de perte de travail humain.
        preserved = [c["id"] for c in old_cases if conn.execute(
            "SELECT 1 FROM annotations WHERE region_id = ?", (c["id"],)).fetchone()]
        keep = set(preserved)
        to_delete = [cid for cid in old_ids if cid not in keep]
        for cid in to_delete:
            unindex_region(conn, cid)
        if to_delete:
            dph = ",".join("?" * len(to_delete))
            conn.execute(f"DELETE FROM regions WHERE id IN ({dph})", tuple(to_delete))

    # Ré-rattache les régions préservées (bulles océrisées, manuelles) aux
    # nouvelles cases par géométrie, puis recalcule l'ordre de lecture.
    reattaches = _reattach_orphans(conn, planche_id)
    reorder_planche(conn, planche_id)

    conn.execute(
        "UPDATE planches SET statut = 'segmentee', "
        "date_segmentation = datetime('now') WHERE id = ?",
        (planche_id,),
    )

    return {"planche_id": planche_id, "nb_cases": len(regions),
            "reattaches": reattaches, "annotations_transferees": len(transferred),
            "annotations_preservees": len(preserved), "regions": regions}
