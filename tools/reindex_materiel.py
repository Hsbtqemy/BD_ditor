r"""Backfill du matériel de numérisation (A6) — résolution + mode colorimétrique.

Les planches importées AVANT la v19 n'ont pas de `dpi_x`/`dpi_y`/`mode` en base (ces
métadonnées étaient lues à l'ingest puis jetées). Cet outil RE-LIT le master de chaque
planche concernée et renseigne les colonnes. Sans effet destructeur : ne touche que les
planches dont le matériel manque (ou toutes avec `--force`), et saute proprement celles
dont le master est absent (dérivé seul) ou illisible.

Les dimensions physiques (cm) restent DÉRIVÉES à la lecture (px÷dpi) — rien à stocker.

Usage :
    python tools/reindex_materiel.py            # planches sans matériel connu
    python tools/reindex_materiel.py --force    # re-lit TOUTES les planches à master présent
    python tools/reindex_materiel.py --dry-run  # montre ce qui serait fait, sans écrire

Configuration (comme l'app) :
    BD_DATA_DIR / BD_DB_PATH   emplacement des données / de la base
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _commun import forcer_utf8                    # noqa: E402
import database                                    # noqa: E402
from config import DATA_DIR                         # noqa: E402
from pipeline.ingest import read_metadata           # noqa: E402


def _planches_a_traiter(conn, force: bool):
    """Planches à (re)lire : à master présent, dont le matériel manque (ou toutes si `force`)."""
    sql = "SELECT id, numero, chemin_tiff, dpi_x, dpi_y, mode FROM planches WHERE chemin_tiff IS NOT NULL"
    if not force:
        sql += " AND dpi_x IS NULL AND dpi_y IS NULL AND mode IS NULL"
    return conn.execute(sql + " ORDER BY album_id, numero, id").fetchall()


def main() -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(description="Backfill du matériel de numérisation (A6).")
    ap.add_argument("--force", action="store_true",
                    help="re-lit toutes les planches à master présent (pas seulement les manquantes)")
    ap.add_argument("--dry-run", action="store_true", help="n'écrit rien, montre le bilan")
    args = ap.parse_args()

    database.init_db()
    conn = database.get_connection()
    try:
        planches = _planches_a_traiter(conn, args.force)
        maj = absents = illisibles = 0
        for p in planches:
            master = DATA_DIR / p["chemin_tiff"]
            if not master.is_file():
                absents += 1
                continue
            try:
                meta = read_metadata(master)
            except Exception as e:                  # image corrompue / format non géré
                illisibles += 1
                print(f"  ✗ planche {p['id']} (n°{p['numero']}) illisible : {e}")
                continue
            dpi_x, dpi_y = meta["dpi"] if meta["dpi"] else (None, None)
            if not args.dry_run:
                conn.execute("UPDATE planches SET dpi_x = ?, dpi_y = ?, mode = ? WHERE id = ?",
                             (dpi_x, dpi_y, meta["mode"], p["id"]))
            maj += 1
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    verbe = "à mettre à jour" if args.dry_run else "mise(s) à jour"
    print(f"✓ {maj} planche(s) {verbe}."
          + (f" {absents} master(s) absent(s) (sauté)." if absents else "")
          + (f" {illisibles} illisible(s)." if illisibles else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
