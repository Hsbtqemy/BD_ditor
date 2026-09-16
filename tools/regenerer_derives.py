r"""Régénère le dérivé web d'une planche depuis son master (IMG-1).

`make_web_derivative` n'avait qu'un appelant, l'import : un dérivé faux le restait pour
toujours, et changer `WEB_SCALE` ou `WEB_JPEG_QUALITY` ne touchait aucune planche déjà
importée. Le cas qui a fait écrire cet outil est le premier : jusqu'à IMG-1, un master en
gris 16 bits donnait un dérivé presque blanc, sans erreur à l'import.

**La base n'est pas touchée.** Le dérivé est réécrit au même chemin, et `largeur_px` /
`hauteur_px` sont les dimensions du MASTER, sur lesquelles reposent les coordonnées des
régions : le navigateur recalcule l'échelle depuis l'image chargée, si bien que les cases
restent à leur place même si `WEB_SCALE` a changé entre-temps.

**Ce que régénérer ne répare pas** : les passes de reconnaissance ont travaillé sur l'ancien
dérivé (bulles toujours, Kumiko par défaut). Sur une planche dont le master est un gris de
plus de 8 bits, celles d'avant le correctif ont été produites sur du blanc ; l'outil les
COMPTE et le dit, il ne les efface pas — la resegmentation garde le travail humain, et c'est à
elle de décider. Il ne peut pas les dater : une région posée APRÈS le correctif est comptée
aussi, et le message le dit.

Le nouveau dérivé est écrit à côté puis substitué d'un coup : un master illisible ou refusé
laisse l'ancien dérivé en place plutôt qu'un fichier tronqué.

Usage :
    python tools/regenerer_derives.py --planche 12
    python tools/regenerer_derives.py --album 3
    python tools/regenerer_derives.py --toutes --mode "I;16" --mode "I;16B"
    python tools/regenerer_derives.py --toutes --dry-run

Les GUILLEMETS autour d'un mode ne sont pas décoratifs : `;` sépare deux commandes, en bash
comme en PowerShell. `--mode I;16` lancerait l'outil avec `--mode I` — donc sur les planches
en mode `I`, pas `I;16` —, puis bash chercherait une commande `16` et PowerShell afficherait
le nombre 16 (mesuré dans les deux le 2026-09-16). L'outil aurait tourné, sur les mauvaises
planches, et seul bash le signalerait.

En production, dans le conteneur (`tools/` est livré dans l'image) :
    docker exec bd-app python tools/regenerer_derives.py --toutes --mode "I;16" --mode "I;16B" --dry-run

Configuration (comme l'app) :
    BD_DATA_DIR / BD_DB_PATH   emplacement des données / de la base
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _commun import forcer_utf8                        # noqa: E402
import database                                        # noqa: E402
from config import DATA_DIR                             # noqa: E402
from pipeline.ingest import MODES_GRIS_16_BITS, make_web_derivative  # noqa: E402

# Provenances des régions posées par un moteur (segmentation, bulles).
SOURCES_MOTEUR = ("kumiko", "auto")


def planches_selectionnees(conn, *, planche=None, album=None, modes=()):
    """Planches visées, dans l'ordre de lecture du corpus."""
    sql = "SELECT id, album_id, numero, chemin_tiff, chemin_web, mode FROM planches WHERE 1 = 1"
    params: list = []
    if planche is not None:
        sql += " AND id = ?"
        params.append(planche)
    if album is not None:
        sql += " AND album_id = ?"
        params.append(album)
    if modes:
        sql += f" AND mode IN ({','.join('?' * len(modes))})"
        params.extend(modes)
    return conn.execute(sql + " ORDER BY album_id, numero, id", params).fetchall()


def regenerer(conn, planches, *, dry_run: bool = False) -> dict:
    """Régénère le dérivé de chaque planche ; renvoie le bilan (listes d'identifiants)."""
    bilan = {"regeneres": [], "sans_master": [], "echecs": [], "a_resegmenter": []}
    for p in planches:
        master = DATA_DIR / p["chemin_tiff"] if p["chemin_tiff"] else None
        if master is None or not master.is_file():
            bilan["sans_master"].append(p["id"])
            continue
        if not dry_run:
            dest = DATA_DIR / p["chemin_web"]
            provisoire = dest.with_name(dest.name + ".regeneration")
            try:
                make_web_derivative(master, provisoire)
                os.replace(provisoire, dest)
            except Exception as exc:               # master illisible, mode refusé…
                provisoire.unlink(missing_ok=True)
                bilan["echecs"].append((p["id"], f"{type(exc).__name__}: {exc}"))
                continue
        bilan["regeneres"].append(p["id"])
        if p["mode"] in MODES_GRIS_16_BITS:
            n = conn.execute(
                f"SELECT COUNT(*) FROM regions WHERE planche_id = ? "
                f"AND source IN ({','.join('?' * len(SOURCES_MOTEUR))})",
                (p["id"], *SOURCES_MOTEUR)).fetchone()[0]
            if n:
                bilan["a_resegmenter"].append((p["id"], n))
    return bilan


def main(argv=None) -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(description="Régénère les dérivés web depuis les masters (IMG-1).")
    cible = ap.add_mutually_exclusive_group(required=True)
    cible.add_argument("--planche", type=int, help="identifiant d'une planche")
    cible.add_argument("--album", type=int, help="identifiant d'un album : toutes ses planches")
    cible.add_argument("--toutes", action="store_true", help="toutes les planches du corpus")
    ap.add_argument("--mode", action="append", default=[],
                    help="ne garder que les planches de ce mode Pillow (répétable), "
                         "p. ex. --mode \"I;16\" --mode \"I;16B\" — guillemets obligatoires, "
                         "le « ; » coupe la commande dans un shell")
    ap.add_argument("--dry-run", action="store_true", help="n'écrit rien, montre le bilan")
    args = ap.parse_args(argv)

    database.init_db()
    conn = database.get_connection()
    try:
        planches = planches_selectionnees(conn, planche=args.planche, album=args.album,
                                          modes=tuple(args.mode))
        bilan = regenerer(conn, planches, dry_run=args.dry_run)
    finally:
        conn.close()

    for pid, erreur in bilan["echecs"]:
        print(f"  ✗ planche {pid} : {erreur}")
    verbe = "à régénérer" if args.dry_run else "régénéré(s)"
    print(f"✓ {len(bilan['regeneres'])} dérivé(s) {verbe} sur {len(planches)} planche(s)."
          + (f" {len(bilan['sans_master'])} sans master (sauté)." if bilan["sans_master"] else "")
          + (f" {len(bilan['echecs'])} en échec." if bilan["echecs"] else ""))
    if bilan["a_resegmenter"]:
        print("⚠ Master en gris de plus de 8 bits : les régions de moteur posées AVANT le "
              "correctif IMG-1 l'ont été sur un dérivé écrêté (presque blanc). À revoir, "
              "et resegmenter si elles en datent :")
        for pid, n in bilan["a_resegmenter"]:
            print(f"    planche {pid} : {n} région(s)")
    return 1 if bilan["echecs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
