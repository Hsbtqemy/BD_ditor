r"""Fait les miniatures qui manquent, celles des planches d'avant UX-20.

L'import écrit la miniature d'une planche à côté de son dérivé
(`pipeline.ingest.chemin_de_miniature`). Une planche importée avant n'en a pas : la grille de
la Bibliothèque montre alors son titre sur un aplat, rien n'est cassé. L'outil se lance UNE
fois en production, sur le mot de Hugo. Cf. `docs/ux20-miniature-cadrage.md`.

**À blanc par défaut** : il dit, chemin par chemin, ce qu'il ferait, puis combien de
miniatures et le POIDS ajouté sur le disque, mesuré en les encodant dans un dossier temporaire.
`--appliquer` écrit.

**Une fois par `chemin_web`** : deux copies sœurs désignent le même dérivé, donc la même
miniature, le jeu des bacs à sable compris. Une miniature qui existe est laissée, sauf
`--meme-existantes`.

**La source est le dérivé**, jamais la copie de travail. Un dérivé absent ou illisible est
compté, et l'outil sort en 1 s'il y a des échecs.

**Il tourne à côté de l'application** : il n'écrit rien en base et l'ouvre en lecture seule
(`regenerer_derives._ouvrir_en_lecture`, qui refuse une base d'une autre version). Une
miniature est écrite à côté puis substituée d'un coup. Si une planche est détruite pendant le
passage, sa miniature peut rester : `tools/convertir_en_copies_de_travail.py` la liste.

Usage :
    python tools/faire_miniatures.py --toutes                # à blanc : ce qu'il ferait
    python tools/faire_miniatures.py --toutes --appliquer
    python tools/faire_miniatures.py --album 3 --appliquer
    python tools/faire_miniatures.py --planche 12 --meme-existantes --appliquer

En production, dans le conteneur (`tools/` est livré dans l'image) : cf. `docs/exploitation.md`.

Configuration (comme l'app) :
    BD_DATA_DIR / BD_DB_PATH   emplacement des données / de la base
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _commun import forcer_utf8                        # noqa: E402
from regenerer_derives import _dire, _octets, _ouvrir_en_lecture  # noqa: E402
from pipeline import ingest                            # noqa: E402


def derives_selectionnes(conn, *, planche=None, album=None) -> list[str]:
    """Les `chemin_web` visés, chacun une fois, dans l'ordre du corpus."""
    sql = "SELECT DISTINCT chemin_web FROM planches WHERE chemin_web IS NOT NULL"
    params: list = []
    if planche is not None:
        sql += " AND id = ?"
        params.append(planche)
    if album is not None:
        sql += " AND album_id = ?"
        params.append(album)
    return [r[0] for r in conn.execute(sql + " ORDER BY chemin_web", params)]


def faire(chemins, *, appliquer: bool, meme_existantes: bool = False, suivre=None) -> dict:
    """Fait la miniature de ces dérivés ; rend le bilan : `faites` (à faire, à blanc),
    `existantes`, `sans_derive`, `echecs` avec leur message, et `octets`, le poids ajouté.
    `suivre(n, total, ligne)` reçoit une ligne par miniature faite, sautée ou en échec."""
    bilan = {"faites": [], "existantes": [], "sans_derive": [], "echecs": [], "octets": 0}
    total = len(chemins)
    for n, chemin in enumerate(chemins, 1):
        def dire(texte, _n=n, _c=chemin):
            if suivre:
                suivre(_n, total, f"{_c} : {texte}")
        derive = ingest.DATA_DIR / chemin
        dest = ingest.DATA_DIR / ingest.chemin_de_miniature(chemin)
        # Une ligne retouchée à la main ne fait rien écrire hors des dossiers d'images.
        if not ingest.chemin_d_image_sur(chemin) or not derive.is_file():
            bilan["sans_derive"].append(chemin)
            dire("– sans dérivé, sautée")
            continue
        if dest.exists() and not meme_existantes:
            bilan["existantes"].append(chemin)
            continue
        avant = dest.stat().st_size if dest.exists() else 0
        try:
            if appliquer:
                ingest.faire_miniature(derive, dest)
                apres = dest.stat().st_size
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    essai = Path(tmp) / "miniature.jpg"
                    ingest.faire_miniature(derive, essai)
                    apres = essai.stat().st_size
        except Exception as exc:               # dérivé illisible, mode refusé, disque…
            bilan["echecs"].append((chemin, f"{type(exc).__name__}: {exc}"))
            dire(f"✗ {type(exc).__name__}: {exc}")
            continue
        bilan["faites"].append(chemin)
        bilan["octets"] += apres - avant
        dire(f"{'✓' if appliquer else '·'} {_octets(apres)}")
    return bilan


def main(argv=None) -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Fait les miniatures qui manquent (UX-20). À blanc par défaut.")
    cible = ap.add_mutually_exclusive_group(required=True)
    cible.add_argument("--planche", type=int, help="identifiant d'une planche")
    cible.add_argument("--album", type=int, help="identifiant d'un album : toutes ses planches")
    cible.add_argument("--toutes", action="store_true", help="toutes les planches du corpus")
    ap.add_argument("--meme-existantes", action="store_true",
                    help="refait aussi les miniatures qui existent déjà")
    ap.add_argument("--appliquer", action="store_true",
                    help="écrit les miniatures (sans lui : à blanc, rien n'est écrit)")
    args = ap.parse_args(argv)

    conn = _ouvrir_en_lecture()
    try:
        chemins = derives_selectionnes(conn, planche=args.planche, album=args.album)
    finally:
        conn.close()
    _dire(f"{len(chemins)} dérivé(s) visé(s)"
          + ("" if args.appliquer else " — À BLANC, rien n'est écrit") + ".")
    bilan = faire(chemins, appliquer=args.appliquer, meme_existantes=args.meme_existantes,
                  suivre=lambda n, total, ligne: _dire(f"  {n} sur {total} {ligne}"))
    verbe = "faite(s)" if args.appliquer else "à faire"
    _dire(f"✓ {len(bilan['faites'])} miniature(s) {verbe} sur {len(chemins)} dérivé(s)."
          + (f" {len(bilan['existantes'])} existent déjà (laissée(s))."
             if bilan["existantes"] else "")
          + (f" {len(bilan['sans_derive'])} sans dérivé (sautée(s))."
             if bilan["sans_derive"] else "")
          + (f" {len(bilan['echecs'])} en échec." if bilan["echecs"] else ""))
    if bilan["faites"]:
        _dire(f"  Poids ajouté sur le disque : {_octets(bilan['octets'])}"
              + ("." if args.appliquer else " (mesuré en les encodant à côté)."))
    return 1 if bilan["echecs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
