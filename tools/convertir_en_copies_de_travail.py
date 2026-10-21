r"""Remplace les masters gardés sur le serveur par des COPIES DE TRAVAIL (IMG-1).

Depuis la v34, l'import ne garde plus le fichier reçu (un TIFF de ~52 Mo, un JPEG 2000 de
~12 Mo) mais une copie de travail : un JPEG qualité 80 à 300 dpi effectifs — réduite si le
scan est plus fin, gardée à sa taille à 300 dpi ou moins et sans résolution écrite (décidé
par Hugo le 2026-10-21). Le master d'archive vit où le projet le met (ShareDocs, un disque,
des disques durs) : l'outil n'en impose aucun. Cet outil fait la même chose pour les
planches importées AVANT : celles dont `master_origine` est encore NULL.

    CONVERTIR EFFACE LE MASTER DU SERVEUR. Ne lancez `--appliquer` qu'après avoir vérifié
    que chaque master existe hors du serveur. Sur l'instance de production, seulement sur
    le mot de Hugo.

Par défaut l'outil ne fait que DIRE : les fichiers et les planches concernés, et ce que la
conversion libérerait — mesuré, la copie étant réellement encodée (en mémoire temporaire,
puis jetée), ce qui prend le temps d'une conversion. Rien n'est écrit, ni en base ni sur le
disque des images.

Avec `--appliquer`, fichier par fichier :
  1. la copie de travail est écrite à côté du master (`planche_0001.jpg`, ou
     `planche_0001.travail.jpg` si ce nom est pris — un master déjà en JPEG, par exemple) ;
  2. sous le verrou d'écriture de la base, TOUTES les planches qui désignent ce master
     désignent la copie — un fichier partagé par des copies sœurs (D6) n'est converti
     qu'une fois, et toutes ses planches suivent —, et notent le nom du fichier d'origine
     (`master_origine`) ; une résolution ou un mode absents de la base y sont recopiés du
     master, qui va partir ;
  3. après le commit, sous le verrou, le master est effacé si plus aucune planche ne le
     désigne.

Ce qui ne change PAS : `largeur_px` / `hauteur_px` (les dimensions du scan, sur lesquelles
reposent les coordonnées des régions), `dpi_x` / `dpi_y` / `mode` (ceux du scan, A6 : les
centimètres restent justes), le dérivé web. Les régions restent donc au même endroit : qui
ouvre la copie applique l'échelle `largeur ouverte / largeur_px` (`ocr._open_image`).

Idempotent : une planche convertie porte `master_origine`, et n'est plus vue. Un second
passage ne fait rien. S'arrête PROPREMENT sur Ctrl+C ou un arrêt du conteneur (SIGTERM) :
le fichier en cours est mené au bout, les suivants ne sont pas touchés.

Ce qui est sauté, et dit : un master absent du disque ; un chemin qui n'a pas la forme d'une
image d'album (`corpus/album_<N>/<fichier>`) ; un fichier dont les dimensions ne sont pas
celles de sa planche ; des planches qui désignent le même fichier sans s'accorder sur ses
dimensions ou sa résolution ; un fichier illisible ou d'un mode refusé (`I`, `F`).

Usage :
    python tools/convertir_en_copies_de_travail.py                 # à blanc : dit seulement
    python tools/convertir_en_copies_de_travail.py --album 3       # un album (répétable)
    python tools/convertir_en_copies_de_travail.py --appliquer     # convertit, EFFACE les masters

En production, dans le conteneur (`tools/` est livré dans l'image), depuis `~/BD_ditor/deploy` :
    docker compose exec app python tools/convertir_en_copies_de_travail.py
    docker compose exec app python tools/convertir_en_copies_de_travail.py --appliquer

Configuration (comme l'app) :
    BD_DATA_DIR / BD_DB_PATH   emplacement des données / de la base
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image                                   # noqa: E402

from _commun import forcer_utf8                         # noqa: E402
import conflit                                          # noqa: E402
import database                                         # noqa: E402
from config import DATA_DIR, PILLOW_FORMATS             # noqa: E402
from pipeline.ingest import (_metadonnees, chemin_d_image_sur,  # noqa: E402
                             ecrire_copie_de_travail, image_8_bits)

AVERTISSEMENT = (
    "⚠ Convertir EFFACE le master du serveur : la copie de travail (JPEG, 300 dpi effectifs) "
    "le remplace. Ne lancez --appliquer qu'après avoir vérifié que chaque master existe "
    "ailleurs (ShareDocs, disque, disques durs).")


class _Arret:
    """Un arrêt demandé (Ctrl+C, SIGTERM) attend la fin du fichier en cours."""

    def __init__(self):
        self.demande = False

    def __call__(self, signum, frame):          # pragma: no cover - signal réel
        self.demande = True
        print("  … arrêt demandé : le fichier en cours est mené au bout, puis l'outil "
              "s'arrête.", flush=True)


def _octets(n: int) -> str:
    for unite, taille in (("Go", 1 << 30), ("Mo", 1 << 20), ("Ko", 1 << 10)):
        if abs(n) >= taille:
            return f"{n / taille:.1f} {unite}".replace(".", ",")
    return f"{n} o"


def fichiers_a_convertir(conn, albums=()) -> list[tuple[str, list]]:
    """Les masters encore gardés, chacun avec TOUTES les planches qui le désignent.

    Une planche y entre si son fichier est encore le scan (`master_origine` NULL). Avec
    `albums`, seuls les fichiers d'une planche de ces albums — mais toutes les planches qui
    les désignent suivent, celles d'une copie sœur d'un autre album comprises : un fichier
    ne se convertit qu'une fois."""
    sql = ("SELECT DISTINCT chemin_tiff FROM planches "
           "WHERE chemin_tiff IS NOT NULL AND master_origine IS NULL")
    params: list = []
    if albums:
        sql += f" AND album_id IN ({','.join('?' * len(albums))})"
        params.extend(albums)
    chemins = [r[0] for r in conn.execute(sql + " ORDER BY chemin_tiff", params)]
    return [(c, conn.execute(
        "SELECT id, album_id, numero, largeur_px, hauteur_px, dpi_x, dpi_y, mode "
        "FROM planches WHERE chemin_tiff = ? AND master_origine IS NULL ORDER BY id",
        (c,)).fetchall()) for c in chemins]


def _chemin_libre(conn, ancien: Path) -> Path:
    """Où écrire la copie : à côté du master, en `.jpg` — jamais sur un chemin qui existe
    ou qu'une planche désigne (la règle de `ingest.numero_occupe`)."""
    def pris(p: Path) -> bool:
        rel = p.relative_to(DATA_DIR).as_posix()
        return p == ancien or p.exists() or conn.execute(
            "SELECT 1 FROM planches WHERE chemin_tiff = ? OR chemin_web = ? LIMIT 1",
            (rel, rel)).fetchone() is not None
    candidat = ancien.with_suffix(".jpg")
    n = 1
    while pris(candidat):
        suffixe = ".travail" if n == 1 else f".travail-{n}"
        candidat = ancien.with_name(f"{ancien.stem}{suffixe}.jpg")
        n += 1
    return candidat


def _accord(planches) -> tuple | None:
    """Les dimensions et la résolution que toutes les planches d'un fichier s'accordent à
    lui donner, ou None si elles divergent."""
    vus = {(p["largeur_px"], p["hauteur_px"], p["dpi_x"], p["dpi_y"]) for p in planches}
    return vus.pop() if len(vus) == 1 else None


def convertir(conn, *, albums=(), appliquer: bool = False, arret=None) -> dict:
    """Parcourt les masters gardés ; avec `appliquer`, les convertit. Rend le bilan."""
    bilan = {"convertis": [], "sautes": [], "echecs": [], "planches": 0,
             "avant": 0, "apres": 0, "interrompu": False}
    for chemin, planches in fichiers_a_convertir(conn, albums):
        if arret is not None and arret.demande:
            bilan["interrompu"] = True
            break
        ids = [p["id"] for p in planches]
        ancien = DATA_DIR / chemin
        if not chemin_d_image_sur(chemin):
            bilan["sautes"].append((chemin, ids, "chemin qui n'a pas la forme d'une image "
                                                 "d'album"))
            continue
        if not ancien.is_file():
            bilan["sautes"].append((chemin, ids, "master absent du disque"))
            continue
        accord = _accord(planches)
        if accord is None:
            bilan["sautes"].append((chemin, ids, "planches en désaccord sur les dimensions "
                                                 "ou la résolution du fichier"))
            continue
        largeur, hauteur, dpi_x, dpi_y = accord
        avant = ancien.stat().st_size
        try:
            with Image.open(ancien, formats=PILLOW_FORMATS) as img:
                meta = _metadonnees(img)
                if largeur and hauteur and (meta["largeur"], meta["hauteur"]) != (largeur,
                                                                                  hauteur):
                    bilan["sautes"].append((chemin, ids, (
                        f"le fichier fait {meta['largeur']} × {meta['hauteur']} px, la planche "
                        f"{largeur} × {hauteur}")))
                    continue
                # La résolution du SCAN : celle de la base, sinon celle du fichier.
                dpi = (dpi_x, dpi_y) if dpi_x and dpi_y else meta["dpi"]
                icc = img.info.get("icc_profile")
                img8 = image_8_bits(img)
                icc = icc if img8.mode == meta["mode"] else None
                if appliquer:
                    nouveau = _chemin_libre(conn, ancien)
                    ecrire_copie_de_travail(img8, nouveau, meta["largeur"], meta["hauteur"],
                                            dpi, icc=icc)
                else:
                    with tempfile.TemporaryDirectory() as tmp:
                        essai = Path(tmp) / "copie.jpg"
                        ecrire_copie_de_travail(img8, essai, meta["largeur"], meta["hauteur"],
                                                dpi, icc=icc)
                        apres = essai.stat().st_size
        except Exception as exc:                   # illisible, mode refusé…
            bilan["echecs"].append((chemin, ids, f"{type(exc).__name__}: {exc}"))
            continue
        if appliquer:
            apres = nouveau.stat().st_size
            try:
                _basculer(conn, chemin, nouveau, ancien.name, meta)
            except BaseException:
                conn.rollback()
                nouveau.unlink(missing_ok=True)     # la base n'a pas changé : la copie part
                raise
            _effacer_si_libre(conn, chemin)
        bilan["convertis"].append((chemin, ids, avant, apres))
        bilan["planches"] += len(ids)
        bilan["avant"] += avant
        bilan["apres"] += apres
    return bilan


def _basculer(conn, ancien_rel: str, nouveau: Path, nom_origine: str, meta: dict) -> None:
    """Sous le verrou d'écriture : les planches qui désignent le master désignent la copie.

    La clause `master_origine IS NULL` est relue SOUS le verrou : une planche convertie entre
    la lecture et l'écriture n'est pas réécrite. Et une copie sœur née entre-temps
    (`database.creer_copie`, qui écrit sous ce même verrou) désigne l'ancien chemin : elle
    suit, puisque la clause porte sur le chemin et non sur une liste d'identifiants."""
    conflit.verrouiller(conn)
    dpi_x, dpi_y = meta["dpi"] if meta["dpi"] else (None, None)
    conn.execute(
        "UPDATE planches SET chemin_tiff = ?, master_origine = ?, "
        "dpi_x = COALESCE(dpi_x, ?), dpi_y = COALESCE(dpi_y, ?), mode = COALESCE(mode, ?) "
        "WHERE chemin_tiff = ? AND master_origine IS NULL",
        (nouveau.relative_to(DATA_DIR).as_posix(), nom_origine, dpi_x, dpi_y, meta["mode"],
         ancien_rel))
    conn.commit()


def _effacer_si_libre(conn, rel: str) -> None:
    """Après le commit, sous le verrou repris : efface le master si plus aucune planche ne
    le désigne — la règle de `socle._sous_le_verrou`. Sans le verrou, ne rien effacer : un
    fichier laissé se rattrape, une image effacée sous une planche, non."""
    try:
        conflit.verrouiller(conn)
    except Exception as exc:                         # base occupée au-delà du délai
        print(f"  ⚠ {rel} : le verrou n'a pas été obtenu ({exc}) ; le master reste sur le "
              "disque.")
        return
    try:
        employe = conn.execute(
            "SELECT 1 FROM planches WHERE chemin_tiff = ? OR chemin_web = ? LIMIT 1",
            (rel, rel)).fetchone()
        if employe is None:
            (DATA_DIR / rel).unlink(missing_ok=True)
        else:
            print(f"  ⚠ {rel} : une planche le désigne encore ; il reste sur le disque.")
    finally:
        conn.rollback()                              # rien n'a été écrit : verrou rendu


def main(argv=None) -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Remplace les masters gardés sur le serveur par des copies de travail "
                    "(IMG-1). À blanc par défaut ; --appliquer EFFACE les masters.")
    ap.add_argument("--appliquer", action="store_true",
                    help="convertit pour de bon, puis EFFACE chaque master du serveur")
    ap.add_argument("--album", type=int, action="append", default=[],
                    help="ne traiter que les fichiers de cet album (répétable)")
    args = ap.parse_args(argv)

    print(AVERTISSEMENT)
    arret = _Arret()
    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is not None:
            signal.signal(sig, arret)

    database.init_db()
    conn = database.get_connection()
    try:
        bilan = convertir(conn, albums=tuple(args.album), appliquer=args.appliquer,
                          arret=arret)
    finally:
        conn.close()

    verbe = "converti" if args.appliquer else "à convertir"
    for chemin, ids, avant, apres in bilan["convertis"]:
        print(f"  {'✓' if args.appliquer else '·'} {chemin} ({verbe}) — planche(s) "
              f"{', '.join(map(str, ids))} : {_octets(avant)} → {_octets(apres)}")
    for chemin, ids, raison in bilan["sautes"]:
        print(f"  – {chemin} (sauté) — planche(s) {', '.join(map(str, ids))} : {raison}")
    for chemin, ids, erreur in bilan["echecs"]:
        print(f"  ✗ {chemin} — planche(s) {', '.join(map(str, ids))} : {erreur}")
    libere = bilan["avant"] - bilan["apres"]
    if args.appliquer:
        print(f"✓ {len(bilan['convertis'])} fichier(s) converti(s), {bilan['planches']} "
              f"planche(s) ; {_octets(libere)} libéré(s) sur le serveur.")
    else:
        print(f"À blanc : {len(bilan['convertis'])} fichier(s) à convertir, "
              f"{bilan['planches']} planche(s) ; {_octets(libere)} seraient libéré(s). "
              "Rien n'a été écrit — relancez avec --appliquer pour convertir.")
    if bilan["sautes"]:
        print(f"  {len(bilan['sautes'])} fichier(s) sauté(s).")
    if bilan["echecs"]:
        print(f"  {len(bilan['echecs'])} fichier(s) en échec.")
    if bilan["interrompu"]:
        print("  Arrêté avant la fin : relancez pour traiter le reste.")
        return 130
    return 1 if bilan["echecs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
