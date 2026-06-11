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
from database import unindex_region
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
    page = data[0] if isinstance(data, list) else data
    if "panels" not in page:
        raise KumikoError("Sortie Kumiko inattendue : clé 'panels' absente")
    return page


def segment_planche(conn: sqlite3.Connection, planche_id: int,
                    use_master: bool = False, replace: bool = True) -> dict:
    """Segmente une planche avec Kumiko et insère les cases détectées.

    Renvoie {'planche_id', 'nb_cases', 'regions'}. Les régions Kumiko
    précédentes sont remplacées par défaut (`replace=True`) ; les régions
    manuelles / corrigées sont préservées.
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
    in_w, in_h = size[0] or master_w, size[1] or master_h

    # Facteurs de conversion espace-image → espace-master.
    scale_x = master_w / in_w if in_w else 1.0
    scale_y = master_h / in_h if in_h else 1.0

    if replace:
        # Inclut les descendants : le DELETE cascade sur les enfants des cases
        # Kumiko, mais leurs lignes FTS doivent être retirées explicitement
        # (sinon elles restent orphelines et polluent la recherche).
        doomed = conn.execute(
            """WITH RECURSIVE doomed(id) AS (
                   SELECT id FROM regions
                   WHERE planche_id = ? AND source = 'kumiko'
                   UNION ALL
                   SELECT r.id FROM regions r JOIN doomed d ON r.parent_id = d.id
               ) SELECT id FROM doomed""",
            (planche_id,),
        ).fetchall()
        for r in doomed:
            unindex_region(conn, r["id"])
        conn.execute(
            "DELETE FROM regions WHERE planche_id = ? AND source = 'kumiko'",
            (planche_id,),
        )

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

    # Ordre de lecture cohérent sur toute la planche (cases + éventuelles bulles
    # et régions manuelles), `ordre` = rang per-niveau.
    reorder_planche(conn, planche_id)

    conn.execute(
        "UPDATE planches SET statut = 'segmentee', "
        "date_segmentation = datetime('now') WHERE id = ?",
        (planche_id,),
    )

    return {"planche_id": planche_id, "nb_cases": len(regions), "regions": regions}
