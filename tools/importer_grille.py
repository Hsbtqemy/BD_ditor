"""Importe une GRILLE d'annotation depuis son tableur (ANN-7, tranche 1 ; cadrage R3) — CLI.

Mince enveloppe en ligne de commande autour de `grille_import` (le cœur partagé avec la route
`POST /api/projets/{id}/grilles/import`). Le tableur est vérifié ENTIER : une anomalie de
structure le refuse, toutes les anomalies dites, rien d'écrit (G12). Le BILAN dit ce qui naît,
change, disparaît depuis la dernière version publiée. Réimporter le même fichier ne change
rien. Format et formes : `docs/import-grille.md` ; modèle fictif : `tools/grille-modele.csv`
et `tools/grille-modele-listes-qualificatifs.csv`.

    # une grille NEUVE, à blanc d'abord (le bilan, rien d'écrit), puis pour de bon :
    python tools/importer_grille.py entrees.csv --listes listes.csv --projet 2 \\
        --nom "Oralité" --porte-sur mots --a-blanc
    python tools/importer_grille.py entrees.csv --listes listes.csv --projet 2 \\
        --nom "Oralité" --porte-sur mots
    # la version SUIVANTE d'une grille (un brouillon, à publier ensuite) :
    python tools/importer_grille.py entrees.csv --listes listes.csv --projet 2 --grille 7
    # publier le brouillon :
    python tools/importer_grille.py --publier 7

`--ouverte` : une grille OUVERTE (une seule version, vivante, qui s'enrichit en posant).
`--porte-sur` : la cible des entrées qui ne déclarent pas la leur (« mots », « case »,
« bulle | cartouche | texte ») ; pour une version suivante, celle de la version précédente
si on ne la dit pas. `--note` : la note de version.

L'outil passe une portée TOTALE et aucun agent au journal (« un shell n'a pas d'identité »,
le patron de `gerer_collections.py`) : qui le lance tient la base entre ses mains.

Code de retour : 0 si l'import s'est fait (ou n'avait rien à changer) ; 1 si le tableur est
refusé, ou si le projet, la grille ou un fichier sont introuvables — rien n'est écrit ; 2
pour une erreur d'usage (argparse). `--a-blanc` sort avec le code de l'import qu'il annonce.

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
import grille_import  # noqa: E402
import grilles  # noqa: E402
import journal  # noqa: E402

CODE_REFUS = 1


def _err(msg):
    print(msg, file=sys.stderr)


def _bilan(res) -> None:
    b = res["bilan"]
    compare = (f"comparé à la version {res['compare_a']}" if res["compare_a"]
               else "aucune version publiée avant elle")
    _err(f"  Bilan ({compare}) :")
    for quoi, cle in (("nés", "nes"), ("renommés", "renommes"), ("retouchés", "retouches"),
                      ("déplacés", "deplaces"), ("changés", "changes"),
                      ("disparus", "disparus")):
        lignes = b[cle]
        _err(f"    {quoi:<10}: {len(lignes)}")
        for l in lignes[:12]:
            detail = l.get("libelle") or l.get("champ") or ", ".join(l.get("champs", []))
            extra = f" — {l['releves']} relevé(s)" if l.get("releves") else ""
            _err(f"      · {l['quoi']} « {l['cle']} » {detail or ''}{extra}")
        if len(lignes) > 12:
            _err(f"      … et {len(lignes) - 12} autre(s)")
    for a in res["avertissements"]:
        _err(f"  ⚠ {a}")


def cmd_importer(args) -> int:
    for chemin in (args.fichier, args.listes):
        if chemin and not os.path.isfile(chemin):
            _err(f"Fichier introuvable : {chemin}")
            return CODE_REFUS
    conn = database.get_connection()
    try:
        if conn.execute("SELECT 1 FROM projet WHERE id = ?", (args.projet,)).fetchone() is None:
            _err(f"Projet {args.projet} introuvable.")
            return CODE_REFUS
        conn.execute("BEGIN IMMEDIATE")
        with open(args.fichier, encoding="utf-8-sig", newline="") as f:
            listes = (open(args.listes, encoding="utf-8-sig", newline="")
                      if args.listes else None)
            try:
                res = grille_import.importer(
                    conn, projet_id=args.projet, flux_entrees=f, flux_listes=listes,
                    grille_id=args.grille, nom=args.nom, ouverte=args.ouverte,
                    porte_sur=args.porte_sur, note=args.note, par=None,
                    a_blanc=args.a_blanc)
            finally:
                if listes is not None:
                    listes.close()
        if args.a_blanc:
            conn.rollback()
        else:
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except grille_import.FormatInvalide as e:
        conn.rollback()
        _err(str(e))
        return CODE_REFUS
    except grille_import.Refus as e:
        conn.rollback()
        _err(e.message)
        for a in e.anomalies:
            _err(f"  ✗ {a}")
        return CODE_REFUS
    finally:
        conn.close()
    v = res["version"] or {}
    if res["aucun_changement"]:
        _err(f"Aucun changement : la version {v.get('numero')} ({v.get('etat')}) porte déjà "
             "ce contenu. Rien n'est écrit.")
    elif args.a_blanc:
        _err("— À BLANC : aucune écriture. Ce que l'import ferait :")
    else:
        _err(f"Grille {res['grille_id']} : version {v.get('numero')} ({v.get('etat')})"
             + (" — le brouillon est remplacé" if v.get("remplace") else "") + ".")
    _bilan(res)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


def cmd_publier(args) -> int:
    conn = database.get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        v = grilles.derniere_version(conn, args.publier, grilles.ETAT_BROUILLON)
        if v is None:
            conn.rollback()
            _err(f"La grille {args.publier} n'a pas de brouillon à publier.")
            return CODE_REFUS
        conn.execute("UPDATE grille_version SET etat = ?, publiee_par = NULL, "
                     "publiee_le = datetime('now') WHERE id = ?",
                     (grilles.ETAT_PUBLIEE, v["id"]))
        journal.journaliser(conn, "modification", "grille", args.publier,
                            avant={"version": v["numero"], "etat": grilles.ETAT_BROUILLON},
                            apres={"version": v["numero"], "etat": grilles.ETAT_PUBLIEE})
        conn.commit()
    finally:
        conn.close()
    _err(f"Grille {args.publier} : la version {v['numero']} est publiée.")
    return 0


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Importe une grille d'annotation depuis son tableur (deux CSV "
                    "point-virgule), ou publie son brouillon.",
        epilog="Code de retour : 0 si l'import s'est fait ou n'avait rien à changer ; 1 si "
               "le tableur est refusé (anomalies dites) ou si le projet, la grille ou un "
               "fichier sont introuvables ; 2 pour une erreur d'usage.")
    ap.add_argument("fichier", nargs="?", help="le CSV des rubriques et entrées")
    ap.add_argument("--listes", help="le CSV des listes de qualificatifs (facultatif)")
    ap.add_argument("--projet", type=int, help="le projet de la grille")
    ap.add_argument("--grille", type=int, help="une grille existante : sa version suivante")
    ap.add_argument("--nom", help="le nom d'une grille neuve")
    ap.add_argument("--ouverte", action="store_true", help="une grille OUVERTE")
    ap.add_argument("--porte-sur", dest="porte_sur",
                    help="« Porte sur » : mots, case, planche, « bulle | cartouche | texte »…")
    ap.add_argument("--note", help="la note de version")
    ap.add_argument("--a-blanc", dest="a_blanc", action="store_true",
                    help="le bilan, sans rien écrire")
    ap.add_argument("--json", action="store_true", help="le résultat complet en JSON")
    ap.add_argument("--publier", type=int, metavar="GRILLE",
                    help="publie le brouillon de cette grille")
    args = ap.parse_args(argv)
    database.init_db()
    if args.publier is not None:
        return cmd_publier(args)
    if not args.fichier or args.projet is None:
        ap.error("le fichier des entrées et --projet sont requis pour importer")
    return cmd_importer(args)


if __name__ == "__main__":
    raise SystemExit(main())
