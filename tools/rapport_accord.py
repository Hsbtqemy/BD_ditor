"""Rapport d'accord modèle↔humain (NLP-1) — CLI.

Combien de corrections humaines le modèle NLP retrouve seul : étalon de qualité de l'index.
À lancer après un (re)index (tools/reindex_nlp.py), typiquement pour comparer fr_core_news_sm
et fr_core_news_lg. Cœur partagé avec la route GET /api/analyse/accord (module `accord`).

    python tools/rapport_accord.py                  # rapport lisible (stdout)
    python tools/rapport_accord.py --json r.json    # + export JSON
    python tools/rapport_accord.py --csv r.csv      # + export CSV (une ligne par champ)

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accord  # noqa: E402
import database  # noqa: E402


def _err(msg):
    print(msg, file=sys.stderr)


def _pct(x):
    return "—" if x is None else f"{x * 100:.1f} %"


def _afficher(r):
    modele = r["modele"] or "?"
    date = f" (indexé le {r['indexe_le']})" if r["indexe_le"] else ""
    _err(f"Accord modèle↔humain — modèle : {modele}{date}")
    _err(f"  Tokens relus : {r['revus']} "
         f"({r['corriges']} corrigé(s), {r['valides']} validé(s))")
    if not r["revus"]:
        _err("  (aucun token relu — corriger/valider des tokens d'abord)")
        return
    for ch in accord.CHAMPS:
        c = r["champs"][ch]
        _err(f"  {ch:<6}: accord {c['accord']}/{c['revus']} — {_pct(c['taux'])}")
    if r["confusion_pos"]:
        _err("  Confusion POS (auto → corrigé) :")
        for x in r["confusion_pos"]:
            _err(f"    {x['auto'] or '∅'} → {x['humain']} : {x['n']}")


def _export_csv(r, chemin):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["champ", "revus", "accord", "taux"])
        for ch in accord.CHAMPS:
            c = r["champs"][ch]
            w.writerow([ch, c["revus"], c["accord"],
                        "" if c["taux"] is None else f"{c['taux']:.4f}"])


def cmd(args) -> int:
    conn = database.get_connection()
    try:
        r = accord.rapport(conn)
    finally:
        conn.close()
    _afficher(r)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        _err(f"→ JSON : {args.json}")
    if args.csv:
        _export_csv(r, args.csv)
        _err(f"→ CSV : {args.csv}")
    return 0


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                              # Windows : stdout/stderr en UTF-8
    ap = argparse.ArgumentParser(
        description="Rapport d'accord modèle↔humain (part des tokens relus où le modèle NLP "
                    "avait déjà la valeur finale).")
    ap.add_argument("--json", help="exporter le rapport complet en JSON")
    ap.add_argument("--csv", help="exporter l'accord par champ en CSV (point-virgule)")
    ap.set_defaults(func=cmd)
    args = ap.parse_args(argv)
    database.init_db()                         # garantit le schéma (idempotent)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
