"""Rapport d'accord modèle↔humain (NLP-1) — CLI.

Combien de corrections humaines le modèle NLP retrouve seul : étalon de qualité de l'index.
À lancer après un (re)index (tools/reindex_nlp.py), typiquement pour comparer fr_core_news_sm
et fr_core_news_lg. Cœur partagé avec la route GET /api/analyse/accord (module `accord`).

    python tools/rapport_accord.py                  # rapport lisible (stdout)
    python tools/rapport_accord.py --json r.json    # + export JSON
    python tools/rapport_accord.py --csv r.csv      # + export CSV (une ligne par champ)
    python tools/rapport_accord.py --modele fr_core_news_sm-3.8.0   # NLP-2, cf. ci-dessous

`--modele` (NLP-2) restreint le rapport aux relectures faites sur la sortie de ce modèle, et
le mesure AU MOMENT de la relecture, à côté de l'index actuel : après un passage à `lg`,
`--modele <sm>` met `sm` et `lg` face aux MÊMES relectures. Les identifiants sont ceux que
liste « Relectures, par modèle relu ». Le CSV ne porte que l'index actuel, et nomme le
filtre dans sa colonne `releve_sur` ; la mesure au moment de la relecture est dans le JSON
(`a_la_relecture`).

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


def _afficher_mesure(champs, confusion, retrait):
    for ch in accord.CHAMPS:
        c = champs[ch]
        _err(f"{retrait}{ch:<6}: accord {c['accord']}/{c['revus']} — {_pct(c['taux'])}")
    if confusion:
        _err(f"{retrait}Confusion POS (proposé → retenu par l'humain) :")
        for x in confusion:
            _err(f"{retrait}  {x['auto'] or '∅'} → {x['humain']} : {x['n']}")


def _afficher(r):
    modele = r["modele"] or "?"
    date = f" (indexé le {r['indexe_le']})" if r["indexe_le"] else ""
    _err(f"Accord modèle↔humain — modèle : {modele}{date}")
    if r["par_modele"]:
        _err("  Relectures, par modèle relu : " + " · ".join(
            f"{p['modele'] or 'inconnu'} : {p['revus']}" for p in r["par_modele"]))
    if r["filtre_modele"] is not None:
        _err(f"  Restreint aux relectures faites sur : {r['filtre_modele']}")
    _err(f"  Tokens relus : {r['revus']} "
         f"({r['corriges']} corrigé(s), {r['valides']} validé(s))")
    if not r["revus"]:
        _err("  (aucune relecture faite sur ce modèle)" if r["filtre_modele"] is not None
             else "  (aucun token relu — corriger/valider des tokens d'abord)")
        return
    rel = r["a_la_relecture"]
    if rel is None:
        _afficher_mesure(r["champs"], r["confusion_pos"], "  ")
        return
    _err(f"  L'index actuel ({modele}) :")
    _afficher_mesure(r["champs"], r["confusion_pos"], "    ")
    _err(f"  {rel['modele']}, au moment de la relecture :")
    _afficher_mesure(rel["champs"], rel["confusion_pos"], "    ")


def _export_csv(r, chemin):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        # `releve_sur` (NLP-2) : restreint à un modèle, le fichier ne porte plus sur tout le
        # corpus relu, et rien d'autre ne le distinguerait d'un fichier complet.
        w.writerow(["champ", "revus", "accord", "taux", "releve_sur"])
        for ch in accord.CHAMPS:
            c = r["champs"][ch]
            w.writerow([ch, c["revus"], c["accord"],
                        "" if c["taux"] is None else f"{c['taux']:.4f}",
                        r["filtre_modele"] or ""])


def cmd(args) -> int:
    conn = database.get_connection()
    try:
        r = accord.rapport(conn, modele=args.modele)
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
    ap.add_argument("--modele",
                    help="restreindre aux relectures faites sur la sortie de ce modèle, et "
                         "le mesurer au moment de la relecture (NLP-2)")
    ap.set_defaults(func=cmd)
    args = ap.parse_args(argv)
    database.init_db()                         # garantit le schéma (idempotent)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
