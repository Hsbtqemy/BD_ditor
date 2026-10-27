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
    # publier ET activer sur le projet de la grille, puis la masquer dans la collection 12 :
    python tools/importer_grille.py --publier 7 --activer --masquer 12
    # activer une grille déjà publiée (ou une grille ouverte), sans rien importer :
    python tools/importer_grille.py --grille 7 --activer

`--activer` (ANN-7, tranche 2, H3 — tant que la fiche du projet n'a pas son écran des
grilles) : active la grille sur SON projet, dans sa version vivante (grille ouverte) ou dans
sa dernière version publiée (grille fermée). Avec un import, la version que l'import vient
d'écrire — celle d'une grille fermée est un brouillon : l'outil refuse alors tout, import
compris, et dit de publier d'abord (`--publier G --activer`). `--masquer COLLECTION` (à
répéter) : la masque ensuite dans ces collections de son projet, où elle doit être active.
Mêmes règles que les routes (`grille_import.activer`, `grille_import.masquer`) ; tout se
fait dans UNE transaction, et un refus n'écrit rien. Ni l'un ni l'autre à blanc.

`--ouverte` : une grille OUVERTE (une seule version, vivante, qui s'enrichit en posant).
`--porte-sur` : la cible des entrées qui ne déclarent pas la leur (« mots », « case »,
« bulle | cartouche | texte ») ; pour une version suivante, celle de la version précédente
si on ne la dit pas. `--note` : la note de version.

L'outil passe une portée TOTALE et aucun agent au journal (« un shell n'a pas d'identité »,
le patron de `gerer_collections.py`) : qui le lance tient la base entre ses mains.

Code de retour : 0 si l'import s'est fait (ou n'avait rien à changer) ; 1 si le tableur est
refusé, si le projet, la grille ou un fichier sont introuvables, ou si l'activation ou le
masque sont refusés — rien n'est écrit ; 2
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


def _activer_et_masquer(conn, args, grille_id: int, numero=None) -> list:
    """Active la grille sur son projet (`--activer`), puis la masque dans chaque collection
    de `--masquer` — dans la transaction de l'appelant. `numero` : la version à activer ;
    sans lui, `grille_import.version_activable`. Lève `grille_import.Refus` ; rend les
    lignes à dire une fois la transaction validée."""
    dit = []
    g = conn.execute("SELECT projet_id FROM grille WHERE id = ?", (grille_id,)).fetchone()
    if g is None:
        raise grille_import.Refus(404, f"Grille {grille_id} introuvable.")
    if args.activer:
        if numero is None:
            v = grille_import.version_activable(conn, grille_id)
            if v is None:
                raise grille_import.Refus(409, f"La grille {grille_id} n'a aucune version "
                                               "publiée à activer : publiez-la d'abord "
                                               f"(--publier {grille_id} --activer).")
            numero = v["numero"]
        else:
            v = grilles.version(conn, grille_id, numero)
            if v is not None and v["etat"] == grilles.ETAT_BROUILLON:
                raise grille_import.Refus(409, f"La version {numero} est un brouillon : "
                                               "elle ne s'active pas, et rien n'est écrit. "
                                               "Importez sans --activer, puis publiez et activez "
                                               f"(--publier {grille_id} --activer).")
        ecrit = grille_import.activer(conn, projet_id=g["projet_id"], grille_id=grille_id,
                                      numero=numero, par=None)
        dit.append(f"Grille {grille_id} : active sur le projet {g['projet_id']}, version "
                   f"{numero}" + ("." if ecrit else " (elle l'était déjà)."))
    for collection_id in args.masquer or []:
        ecrit = grille_import.masquer(conn, collection_id=collection_id, grille_id=grille_id,
                                      par=None)
        dit.append(f"Grille {grille_id} : masquée dans la collection {collection_id}"
                   + ("." if ecrit else " (elle l'était déjà)."))
    return dit


def cmd_activer(args) -> int:
    """`--grille G --activer` / `--masquer C`, sans rien importer ni publier."""
    conn = database.get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            dit = _activer_et_masquer(conn, args, args.grille)
        except grille_import.Refus as e:
            conn.rollback()
            _err(e.message)
            return CODE_REFUS
        conn.commit()
    finally:
        conn.close()
    for ligne in dit:
        _err(ligne)
    return 0


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
        dit = []
        if args.a_blanc:
            conn.rollback()
        else:
            if args.activer or args.masquer:
                dit = _activer_et_masquer(conn, args, res["grille_id"],
                                          (res["version"] or {}).get("numero"))
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
    for ligne in dit:
        _err(ligne)
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
        try:
            dit = _activer_et_masquer(conn, args, args.publier, v["numero"])
        except grille_import.Refus as e:
            conn.rollback()
            _err(e.message + " La version n'est pas publiée non plus.")
            return CODE_REFUS
        conn.commit()
    finally:
        conn.close()
    _err(f"Grille {args.publier} : la version {v['numero']} est publiée.")
    for ligne in dit:
        _err(ligne)
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
    ap.add_argument("--activer", action="store_true",
                    help="active la grille sur son projet (la version importée ou publiée, "
                         "sinon la dernière publiée, ou la vivante d'une grille ouverte)")
    ap.add_argument("--masquer", type=int, action="append", metavar="COLLECTION",
                    help="masque la grille dans cette collection de son projet (à répéter)")
    args = ap.parse_args(argv)
    if args.a_blanc and (args.activer or args.masquer):
        ap.error("--activer et --masquer écrivent : ils ne se jouent pas à blanc")
    database.init_db()
    if args.publier is not None:
        return cmd_publier(args)
    if not args.fichier and args.grille is not None and (args.activer or args.masquer):
        return cmd_activer(args)
    if not args.fichier or args.projet is None:
        ap.error("le fichier des entrées et --projet sont requis pour importer (ou --grille "
                 "avec --activer / --masquer)")
    return cmd_importer(args)


if __name__ == "__main__":
    raise SystemExit(main())
