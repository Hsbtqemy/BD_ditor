"""Import en lot du VOCABULAIRE analytique depuis un tableur CSV (piste B) — CLI.

Mince enveloppe en ligne de commande autour de `lexique_import` (le cœur partagé avec la
route `POST /api/lexique/importer` du panneau 📖 Lexique). PRÉ-SEMER la taxonomie (domaines →
dimensions → valeurs + couche lexique SKOS) sans la saisir terme à terme dans l'app. Additif
et COMPATIBLE ÉMERGENT : les annotateurs continuent de créer des dimensions/valeurs au fil de
l'annotation.

Doctrine « pré-remplir, jamais écraser » (comme l'OCR) : un terme déjà présent est réutilisé
(idempotent) ; sa glose n'est posée que si vide ; la portée (`collection_id`) et le
rattachement au domaine ne se posent qu'à la CRÉATION. L'état (`provisoire`→`defini`) se
promeut dans l'app, pas ici. Cf. docs/import-vocabulaire.md, modèle tools/vocabulaire-modele.csv.

Format (point-virgule, en-tête obligatoire) :

    domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition

Une ligne = une VALEUR. Colonnes d'IDENTITÉ (domaine, cible, dimension, valeur) sur CHAQUE
ligne (robuste au tri) ; définitions une seule fois. `domaine` vide = dimension hors domaine ;
`valeur` vide = déclarer une dimension sans énumérer ses valeurs.

    python tools/importer_vocabulaire.py fichier.csv                 # → vocabulaire global
    python tools/importer_vocabulaire.py fichier.csv --collection 3  # → local à la collection 3
    python tools/importer_vocabulaire.py fichier.csv --dry-run       # aperçu, n'écrit rien

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
import lexique_import  # noqa: E402
from lexique_import import FormatInvalide, importer  # noqa: E402


def _err(msg):
    print(msg, file=sys.stderr)


def lire_csv(chemin) -> tuple[list[dict], list[str]]:
    """Ouvre le tableur (UTF-8 avec ou sans BOM) et le confie à `lexique_import.lire`."""
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return lexique_import.lire(f)


def _bilan(res, avert, anomalies, *, dry_run):
    for quoi, cle in (("Domaines", "domaines"), ("Dimensions", "dimensions"),
                      ("Valeurs", "valeurs")):
        c = res[cle]
        _err(f"  {quoi:<11}: {c['cree']} créé(s), {c['existant']} déjà présent(s)")
    for a in anomalies + avert:
        _err(f"  ⚠ {a}")
    if dry_run:
        _err("— APERÇU (--dry-run) : aucune écriture.")


def cmd_importer(args) -> int:
    if not os.path.isfile(args.fichier):
        raise SystemExit(f"Fichier introuvable : {args.fichier}")
    try:
        lignes, anomalies = lire_csv(args.fichier)
    except FormatInvalide as e:
        raise SystemExit(str(e))

    conn = database.get_connection()
    try:
        if args.collection is not None and conn.execute(
                "SELECT 1 FROM collection WHERE id = ?", (args.collection,)).fetchone() is None:
            raise SystemExit(
                f"Collection {args.collection} introuvable "
                f"(créez-la d'abord : tools/gerer_collections.py creer --nom \"…\").")
        res, avert = importer(conn, lignes, args.collection)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")   # les exports RO voient l'écriture
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    portee = "global" if args.collection is None else f"collection {args.collection}"
    _err(f"Import du vocabulaire ({portee}) — {len(lignes)} ligne(s) de valeur :")
    _bilan(res, avert, anomalies, dry_run=args.dry_run)
    return 0


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                                 # Windows : stdout/stderr en UTF-8
    ap = argparse.ArgumentParser(
        description="Import en lot du vocabulaire analytique (domaines / dimensions / "
                    "valeurs + lexique) depuis un tableur CSV point-virgule.")
    ap.add_argument("fichier", help="tableur CSV (séparateur « ; », en-tête obligatoire)")
    ap.add_argument("--collection", type=int,
                    help="portée : id de collection (vocabulaire LOCAL) ; absent = global")
    ap.add_argument("--dry-run", action="store_true",
                    help="analyse et compte sans rien écrire en base")
    ap.set_defaults(func=cmd_importer)
    args = ap.parse_args(argv)
    database.init_db()                            # garantit le schéma (idempotent)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
