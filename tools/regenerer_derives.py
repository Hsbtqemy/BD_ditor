r"""Régénère le dérivé web d'une planche depuis sa copie de travail (IMG-1).

`make_web_derivative` n'avait qu'un appelant, l'import : un dérivé faux le restait pour
toujours, et changer la règle du dérivé (`ingest.taille_du_derive`) ou `WEB_JPEG_QUALITY`
ne touchait aucune planche déjà importée. Le cas qui a fait écrire cet outil est le premier :
jusqu'à IMG-1, un master en gris 16 bits donnait un dérivé presque blanc, sans erreur à
l'import.

**La base n'est pas touchée.** Le dérivé est réécrit au même chemin, et `largeur_px` /
`hauteur_px` sont les dimensions du SCAN, sur lesquelles reposent les coordonnées des
régions : le navigateur recalcule l'échelle depuis l'image chargée, si bien que les cases
restent à leur place même si la règle a changé entre-temps.

**La source est la copie de travail** depuis IMG-1 (`chemin_tiff`, 300 dpi effectifs) : le
serveur ne garde plus le scan, et l'outil ne part jamais d'autre chose — sans ce fichier, la
planche est sautée. Le dérivé se mesure au SCAN (`largeur_px`), et non à la copie — sans quoi
un scan à 400 dpi recevrait un dérivé réduit deux fois —, sans dépasser la copie : on
n'agrandit pas. Une planche d'avant la v34 a encore son master, à la taille du scan.

**Par défaut, l'outil ne refait QUE les dérivés plus petits que la règle** (IMG-1,
2026-10-24) : 25 % du scan, jamais moins de 1 600 px de large ni plus que l'image qu'on a.
Avant ce plancher, toute planche de moins de 6 400 px recevait un dérivé à 25 %, flou dans
l'Atelier ; l'outil se lance UNE fois en production après le déploiement, et ne touche que
ceux-là (un dérivé absent ou illisible en est). `--meme-a-la-bonne-taille` refait aussi les
autres — le rattrapage d'un dérivé écrêté, plus bas, en a besoin.

**À blanc par défaut** : l'outil dit, planche par planche, ce qu'il referait et à quelle
taille, puis combien de planches et le POIDS ajouté sur le disque — mesuré en encodant
chaque dérivé dans un dossier temporaire, pas extrapolé. `--appliquer` écrit.

**Il tourne à côté de l'application** : il n'écrit rien en base et l'ouvre en LECTURE
SEULE, sans `database.init_db()` (qui referait les vues, donc écrirait) ; une base qui n'est
pas à la version du code est refusée — c'est l'application qui migre. Aucune transaction
d'écriture, donc rien qui retienne les écritures de l'application.

**Ce que régénérer ne répare pas** : les passes de reconnaissance ont travaillé sur l'ancien
dérivé (bulles toujours, Kumiko par défaut). Sur une planche dont le master est un gris de
plus de 8 bits, celles d'avant le correctif ont été produites sur du blanc ; l'outil les
COMPTE et le dit, il ne les efface pas — la resegmentation garde le travail humain, et c'est à
elle de décider. Il ne peut pas les dater : une région posée APRÈS le correctif est comptée
aussi, et le message le dit.

Le nouveau dérivé est écrit à côté (`….jpg.regeneration`) puis substitué d'un coup
(`os.replace`) : une copie illisible ou refusée, ou une interruption, laisse l'ancien dérivé
en place plutôt qu'un fichier tronqué. Un arrêt brutal pendant l'écriture peut laisser le
fichier `.regeneration` à côté : il ne sert à rien, et `tools/convertir_en_copies_de_travail.py`
le liste parmi les fichiers qu'aucune planche ne désigne.

Usage :
    python tools/regenerer_derives.py --toutes                        # à blanc : ce qu'il referait
    python tools/regenerer_derives.py --toutes --appliquer            # refait les dérivés trop petits
    python tools/regenerer_derives.py --album 3 --appliquer
    python tools/regenerer_derives.py --planche 12 --meme-a-la-bonne-taille --appliquer
    python tools/regenerer_derives.py --toutes --mode "I;16" --mode "I;16B" --meme-a-la-bonne-taille

Les GUILLEMETS autour d'un mode ne sont pas décoratifs : `;` sépare deux commandes, en bash
comme en PowerShell. `--mode I;16` lancerait l'outil avec `--mode I` — donc sur les planches
en mode `I`, pas `I;16` —, puis bash chercherait une commande `16` et PowerShell afficherait
le nombre 16 (mesuré dans les deux le 2026-09-16). L'outil aurait tourné, sur les mauvaises
planches, et seul bash le signalerait.

En production, dans le conteneur (`tools/` est livré dans l'image) : cf. `docs/exploitation.md`.

Configuration (comme l'app) :
    BD_DATA_DIR / BD_DB_PATH   emplacement des données / de la base
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image                                  # noqa: E402

from _commun import forcer_utf8                        # noqa: E402
import database                                        # noqa: E402
from config import DATA_DIR, PILLOW_FORMATS            # noqa: E402
from pipeline.ingest import (MODES_GRIS_16_BITS, make_web_derivative,  # noqa: E402
                             taille_du_derive)

# Provenances des régions posées par un moteur (segmentation, bulles).
SOURCES_MOTEUR = ("kumiko", "auto")


def planches_selectionnees(conn, *, planche=None, album=None, modes=()):
    """Planches visées, dans l'ordre de lecture du corpus."""
    sql = ("SELECT id, album_id, numero, chemin_tiff, chemin_web, mode, largeur_px, hauteur_px "
           "FROM planches WHERE 1 = 1")
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


def _taille_lue(chemin: Path | None):
    """(largeur, hauteur) d'une image lue dans son EN-TÊTE, sans la décoder ; None si le
    fichier manque ou ne s'ouvre pas."""
    if chemin is None or not chemin.is_file():
        return None
    try:
        with Image.open(chemin, formats=PILLOW_FORMATS) as img:
            return img.size
    except (OSError, ValueError):
        return None


def _octets(n: int) -> str:
    for unite, taille in (("Go", 1 << 30), ("Mo", 1 << 20), ("Ko", 1 << 10)):
        if abs(n) >= taille:
            return f"{n / taille:.1f} {unite}".replace(".", ",")
    return f"{n} o"


def _dire(ligne: str) -> None:
    """Une ligne de suivi, VIDÉE aussitôt : sortie redirigée vers un fichier (`nohup … >
    log`), le journal avance avec le travail."""
    print(ligne, flush=True)


def regenerer(conn, planches, *, appliquer: bool, meme_a_la_bonne_taille: bool = False,
              suivre=None) -> dict:
    """Refait le dérivé des planches visées ; renvoie le bilan.

    `appliquer` faux : rien n'est écrit à côté des dérivés — chaque nouveau dérivé est encodé
    dans un dossier temporaire, pour MESURER son poids, puis jeté. `meme_a_la_bonne_taille`
    faux : un dérivé déjà aussi large que la règle le veut est laissé (`a_la_bonne_taille`).
    `suivre(n, total, ligne)` reçoit une ligne par planche refaite, sautée ou en échec.

    Le bilan : des listes d'identifiants (`regeneres` — à refaire, à blanc —,
    `a_la_bonne_taille`, `sans_master`, `echecs` avec leur message, `a_resegmenter` avec un
    compte), et `octets_avant` / `octets_apres`, le poids des dérivés refaits avant et
    après (un dérivé absent pèse 0)."""
    bilan = {"regeneres": [], "a_la_bonne_taille": [], "sans_master": [], "echecs": [],
             "a_resegmenter": [], "octets_avant": 0, "octets_apres": 0}
    total = len(planches)
    for n, p in enumerate(planches, 1):
        def dire(texte, _n=n, _p=p):
            if suivre:
                suivre(_n, total, f"planche {_p['id']} : {texte}")
        # La SOURCE est la copie de travail que désigne `chemin_tiff`, jamais autre chose.
        master = DATA_DIR / p["chemin_tiff"] if p["chemin_tiff"] else None
        taille_source = _taille_lue(master)
        if taille_source is None:
            bilan["sans_master"].append(p["id"])
            dire("– sans copie de travail lisible, sautée")
            continue
        taille_scan = ((p["largeur_px"], p["hauteur_px"])
                       if p["largeur_px"] and p["hauteur_px"] else None)
        voulue = taille_du_derive(*(taille_scan or taille_source), taille_source[0])
        dest = DATA_DIR / p["chemin_web"]
        actuelle = _taille_lue(dest)
        if not meme_a_la_bonne_taille and actuelle and actuelle[0] >= voulue[0]:
            bilan["a_la_bonne_taille"].append(p["id"])
            continue
        avant = dest.stat().st_size if dest.is_file() else 0
        de = f"{actuelle[0]} × {actuelle[1]}" if actuelle else "absent"
        try:
            if appliquer:
                provisoire = dest.with_name(dest.name + ".regeneration")
                try:
                    make_web_derivative(master, provisoire, taille_scan=taille_scan)
                    os.replace(provisoire, dest)
                finally:
                    provisoire.unlink(missing_ok=True)
                apres = dest.stat().st_size
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    essai = Path(tmp) / "derive.jpg"
                    make_web_derivative(master, essai, taille_scan=taille_scan)
                    apres = essai.stat().st_size
        except Exception as exc:               # copie illisible, mode refusé…
            bilan["echecs"].append((p["id"], f"{type(exc).__name__}: {exc}"))
            dire(f"✗ {type(exc).__name__}: {exc}")
            continue
        bilan["regeneres"].append(p["id"])
        bilan["octets_avant"] += avant
        bilan["octets_apres"] += apres
        dire(f"{'✓' if appliquer else '·'} {de} → {voulue[0]} × {voulue[1]} "
             f"({_octets(avant)} → {_octets(apres)})")
        if p["mode"] in MODES_GRIS_16_BITS:
            nb = conn.execute(
                f"SELECT COUNT(*) FROM regions WHERE planche_id = ? "
                f"AND source IN ({','.join('?' * len(SOURCES_MOTEUR))})",
                (p["id"], *SOURCES_MOTEUR)).fetchone()[0]
            if nb:
                bilan["a_resegmenter"].append((p["id"], nb))
    return bilan


def _ouvrir_en_lecture():
    """La base en LECTURE SEULE, SANS `database.init_db()` : l'outil n'écrit rien en base,
    schéma compris — `init_db` refait les vues, migrerait une base plus ancienne, et
    prendrait le verrou d'écriture de l'application qui tourne. Une base qui n'est pas à la
    version du code est refusée par son nom : c'est l'application qui migre."""
    chemin = Path(database.DB_PATH)
    if not chemin.is_file():
        raise SystemExit(f"Base introuvable : {chemin}")
    conn = sqlite3.connect(chemin.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != database.SCHEMA_VERSION:
        conn.close()
        raise SystemExit(
            f"Base au schéma v{version}, ce code attend la v{database.SCHEMA_VERSION} : "
            "démarrez l'application une fois (elle migre la base), puis relancez l'outil.")
    return conn


def main(argv=None) -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Refait les dérivés web depuis les copies de travail (IMG-1). À blanc "
                    "par défaut ; seuls les dérivés plus petits que la règle.")
    cible = ap.add_mutually_exclusive_group(required=True)
    cible.add_argument("--planche", type=int, help="identifiant d'une planche")
    cible.add_argument("--album", type=int, help="identifiant d'un album : toutes ses planches")
    cible.add_argument("--toutes", action="store_true", help="toutes les planches du corpus")
    ap.add_argument("--mode", action="append", default=[],
                    help="ne garder que les planches de ce mode Pillow (répétable), "
                         "p. ex. --mode \"I;16\" --mode \"I;16B\" — guillemets obligatoires, "
                         "le « ; » coupe la commande dans un shell")
    ap.add_argument("--meme-a-la-bonne-taille", action="store_true",
                    help="refait aussi les dérivés qui ont déjà la taille de la règle")
    ap.add_argument("--appliquer", action="store_true",
                    help="écrit les nouveaux dérivés (sans lui : à blanc, rien n'est écrit)")
    args = ap.parse_args(argv)

    conn = _ouvrir_en_lecture()
    try:
        planches = planches_selectionnees(conn, planche=args.planche, album=args.album,
                                          modes=tuple(args.mode))
        _dire(f"{len(planches)} planche(s) visée(s)"
              + ("" if args.appliquer else " — À BLANC, rien n'est écrit") + ".")
        bilan = regenerer(conn, planches, appliquer=args.appliquer,
                          meme_a_la_bonne_taille=args.meme_a_la_bonne_taille,
                          suivre=lambda n, total, ligne: _dire(f"  {n} sur {total} {ligne}"))
    finally:
        conn.close()

    nb = len(bilan["regeneres"])
    ajoute = bilan["octets_apres"] - bilan["octets_avant"]
    verbe = "refait(s)" if args.appliquer else "à refaire"
    _dire(f"✓ {nb} dérivé(s) {verbe} sur {len(planches)} planche(s)."
          + (f" {len(bilan['a_la_bonne_taille'])} déjà à la taille de la règle (laissé(s))."
             if bilan["a_la_bonne_taille"] else "")
          + (f" {len(bilan['sans_master'])} sans copie de travail (sautée(s))."
             if bilan["sans_master"] else "")
          + (f" {len(bilan['echecs'])} en échec." if bilan["echecs"] else ""))
    if nb:
        _dire(f"  Poids des dérivés {verbe} : {_octets(bilan['octets_avant'])} → "
              f"{_octets(bilan['octets_apres'])}, soit "
              f"{'+' if ajoute >= 0 else ''}{_octets(ajoute)} sur le disque"
              + ("." if args.appliquer else " (mesuré en les encodant à côté)."))
    if bilan["a_resegmenter"]:
        _dire("⚠ Master en gris de plus de 8 bits : les régions de moteur posées AVANT le "
              "correctif IMG-1 l'ont été sur un dérivé écrêté (presque blanc). À revoir, "
              "et resegmenter si elles en datent :")
        for pid, n in bilan["a_resegmenter"]:
            _dire(f"    planche {pid} : {n} région(s)")
    return 1 if bilan["echecs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
