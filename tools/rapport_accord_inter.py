"""Accord inter-annotateurs (ANN-5) — CLI.

Quand plusieurs linguistes corrigent : quand l'un RE-TOUCHE le token laissé par un autre,
garde-t-il (accord) ou change-t-il (divergence) sa valeur ? Mesuré sur la chaîne de révisions
du journal A3. Cœur partagé avec la route GET /api/analyse/accord-inter (module `accord_inter`).

    python tools/rapport_accord_inter.py                  # rapport lisible (stdout)
    python tools/rapport_accord_inter.py --json r.json    # + export JSON complet
    python tools/rapport_accord_inter.py --csv r.csv      # + export CSV (accord par champ)

Rare tant qu'on n'est pas multi-utilisateur (piste C). La base suit BD_DB_PATH / BD_DATA_DIR.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accord_inter  # noqa: E402
import database  # noqa: E402


def _err(msg):
    print(msg, file=sys.stderr)


def _pct(x):
    return "—" if x is None else f"{x * 100:.1f} %"


def _val(v):
    return "∅" if v in (None, "") else v


def _afficher(r):
    _err(f"Accord inter-annotateurs — {r['retouches']} re-touche(s) inter-auteurs "
         f"({len(r['auteurs'])} auteur(s) : {', '.join(r['auteurs']) or '—'})")
    if not r["retouches"]:
        _err("  (aucune re-touche entre auteurs distincts — rien à comparer)")
        return
    for ch in accord_inter.CHAMPS:
        c = r["champs"][ch]
        _err(f"  {ch:<6}: accord {c['accords']}/{c['retouches']} — {_pct(c['taux'])}")
    if r["paires"]:
        _err("  Par paire d'auteurs :")
        for p in r["paires"]:
            _err(f"    {p['a']} ↔ {p['b']} : {p['accords']}/{p['retouches']} — {_pct(p['taux'])}")
    if r["divergences"]:
        suffixe = " (tronqué)" if r["divergences_tronque"] else ""
        _err(f"  Divergences{suffixe} :")
        for d in r["divergences"]:
            cit = (d["citation"] or {}).get("texte") if d.get("citation") else None
            ref = f"{cit} · " if cit else ""
            for x in d["diffs"]:
                _err(f"    {ref}« {_val(d['forme'])} » [{x['champ']}] "
                     f"{d['de']}={_val(x['avant'])} → {d['a']}={_val(x['apres'])}")


def _export_csv(r, chemin):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["champ", "retouches", "accords", "taux"])
        for ch in accord_inter.CHAMPS:
            c = r["champs"][ch]
            w.writerow([ch, c["retouches"], c["accords"],
                        "" if c["taux"] is None else f"{c['taux']:.4f}"])


def cmd(args) -> int:
    conn = database.get_connection()
    try:
        r = accord_inter.rapport(conn)
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
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Rapport d'accord inter-annotateurs (accord de révision entre auteurs, "
                    "depuis le journal A3).")
    ap.add_argument("--json", help="exporter le rapport complet en JSON")
    ap.add_argument("--csv", help="exporter l'accord par champ en CSV (point-virgule)")
    ap.set_defaults(func=cmd)
    args = ap.parse_args(argv)
    database.init_db()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
