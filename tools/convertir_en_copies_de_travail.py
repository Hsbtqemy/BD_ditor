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
conversion libérerait — mesuré, la copie étant réellement encodée (dans un dossier
temporaire, puis jetée), ce qui prend le temps d'une conversion. Rien n'est écrit, ni en
base — ouverte en LECTURE SEULE, sans `database.init_db()`, qui referait les vues —, ni sur
le disque des images. Une base qui n'est pas à la version du code est refusée : c'est
l'application qui migre.

Avec `--appliquer`, sous un verrou propre à l'outil (`convertir_en_copies_de_travail.verrou`
à la racine des données, créé en exclusif, retiré à la sortie : deux passages ne se
chevauchent pas), fichier par fichier :
  1. la copie de travail est écrite à côté du master (`planche_0001.jpg`, ou
     `planche_0001.travail.jpg` si ce nom est pris — un master déjà en JPEG, par exemple) ;
  2. sous le verrou d'écriture de la base, TOUTES les planches qui désignent ce master
     désignent la copie — un fichier partagé par des copies sœurs (D6) n'est converti
     qu'une fois, et toutes ses planches suivent —, et notent le nom du fichier d'origine
     (`master_origine`) ; une résolution ou un mode absents de la base y sont recopiés du
     master, qui va partir ;
  3. après le commit, sous le verrou, le master est effacé si plus aucune planche ne le
     désigne. Un effacement refusé (un fichier ouvert) est dit au bilan, sans faire tomber
     l'outil ; si aucune planche n'a basculé, la copie écrite repart et le fichier compte
     comme sauté.

À blanc comme appliqué, l'outil LISTE enfin les fichiers de `corpus/album_<N>/` qu'aucune
planche ne désigne — un master laissé par un effacement refusé ou un arrêt brutal. Il ne
les efface jamais : un import en cours y a aussi ses fichiers, réservés avant d'être
désignés.

Ce qui ne change PAS : `largeur_px` / `hauteur_px` (les dimensions du scan, sur lesquelles
reposent les coordonnées des régions), `dpi_x` / `dpi_y` / `mode` (ceux du scan, A6 : les
centimètres restent justes), le dérivé web. Les régions restent donc au même endroit : qui
ouvre la copie applique l'échelle `largeur ouverte / largeur_px` (`ocr._open_image`).

La sortie suit le travail : l'outil compte d'abord les fichiers à traiter et le dit, puis
écrit UNE ligne par fichier au moment où il en a fini (« 12 sur 340 », le chemin, ce qui
s'est passé), vidée aussitôt — sous `nohup … > journal.log`, la sortie part dans un fichier,
que Python remplirait sinon par blocs. Le bilan final ne redit pas ces lignes : il compte,
puis liste les fichiers qu'aucune planche ne désigne.

Idempotent : une planche convertie porte `master_origine`, et n'est plus vue. Un second
passage ne fait rien. S'arrête PROPREMENT sur Ctrl+C ou un arrêt du conteneur (SIGTERM) :
le fichier en cours est mené au bout, les suivants ne sont pas touchés.

Ce qui est sauté, et dit : un master absent du disque ; un chemin qui n'a pas la forme d'une
image d'album (`corpus/album_<N>/<fichier>`) ; une planche sans dimensions (`largeur_px`,
`hauteur_px`), dont les régions ne se ramèneraient à aucune échelle ; un fichier dont les
dimensions ne sont pas celles de sa planche ; des planches qui désignent le même fichier sans s'accorder sur ses
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
import re
import signal
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
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


class PassageEnCours(RuntimeError):
    """Un autre passage `--appliquer` tient le verrou de l'outil."""


# Le verrou de l'outil, à la racine des données : deux passages `--appliquer` qui se
# chevauchent écrivaient chacun leur copie du même master, et le second laissait un orphelin
# en annonçant deux fois « converti » (relecture croisée, reproduit). Un fichier créé en
# EXCLUSIF, retiré à la sortie ; le mode à blanc n'en prend pas, il n'écrit rien.
NOM_DU_VERROU = "convertir_en_copies_de_travail.verrou"


@contextmanager
def _verrou_de_l_outil():
    chemin = DATA_DIR / NOM_DU_VERROU
    try:
        fd = os.open(chemin, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            qui = chemin.read_text(encoding="utf-8").strip()
        except OSError:
            qui = "illisible"
        raise PassageEnCours(
            f"Un autre passage --appliquer tient le verrou {chemin} ({qui}). S'il ne tourne "
            "plus — arrêté brutalement —, effacez ce fichier, puis relancez.") from None
    try:
        os.write(fd, f"pid {os.getpid()}, depuis {time.strftime('%Y-%m-%d %H:%M:%S')}"
                 .encode("utf-8"))
    finally:
        os.close(fd)
    try:
        yield
    finally:
        chemin.unlink(missing_ok=True)


def orphelins(conn) -> list[tuple[str, int]]:
    """Les fichiers des dossiers `corpus/album_<N>/` et `derivatives/album_<N>/` qu'AUCUNE
    planche ne désigne : un master resté après une conversion interrompue ou dont
    l'effacement a été refusé ; et, VIDES, les deux fichiers d'une réservation laissée par un
    import tué en cours de route (`ingest._reserver`). Listés, jamais effacés : un import EN
    COURS a aussi ses fichiers réservés, et rien ne les distingue d'un reste."""
    designes = {c for r in conn.execute("SELECT chemin_tiff, chemin_web FROM planches")
                for c in r if c}
    trouves = []
    for nom in ("corpus", "derivatives"):
        racine = DATA_DIR / nom
        if not racine.is_dir():
            continue
        for dossier in sorted(racine.iterdir()):
            if not (dossier.is_dir() and re.fullmatch(r"album_\d+", dossier.name)):
                continue
            for f in sorted(dossier.iterdir()):
                rel = f.relative_to(DATA_DIR).as_posix()
                if f.is_file() and rel not in designes:
                    trouves.append((rel, f.stat().st_size))
    return trouves


def convertir(conn, *, albums=(), appliquer: bool = False, arret=None, dire=None) -> dict:
    """Parcourt les masters gardés ; avec `appliquer`, les convertit. Rend le bilan.

    Avec `appliquer`, sous le verrou de l'outil (`PassageEnCours` s'il est pris). `dire`
    reçoit, au fil du travail, le compte des fichiers puis une ligne par fichier traité."""
    if appliquer:
        with _verrou_de_l_outil():
            return _convertir(conn, albums=albums, appliquer=True, arret=arret, dire=dire)
    return _convertir(conn, albums=albums, appliquer=False, arret=arret, dire=dire)


def _planches(ids) -> str:
    return f"planche(s) {', '.join(map(str, ids))}"


class _Suivi:
    """Ce que le bilan retient d'un fichier, et la ligne qui le DIT aussitôt : « n sur N »,
    le chemin, ce qui s'est passé. Une ligne par fichier, écrite au moment où il est traité
    et non au bilan — sur un passage de plusieurs heures, c'est le seul moyen de savoir où
    en est l'outil."""

    def __init__(self, bilan, total, appliquer, dire):
        self.bilan, self.total, self.appliquer = bilan, total, appliquer
        self.dire = dire or (lambda ligne: None)
        self.n = 0

    def _ligne(self, marque, chemin, texte):
        self.dire(f"  {self.n} sur {self.total} {marque} {chemin} — {texte}")

    def saute(self, chemin, ids, raison):
        self.bilan["sautes"].append((chemin, ids, raison))
        self._ligne("–", chemin, f"sauté, {_planches(ids)} : {raison}")

    def echec(self, chemin, ids, erreur):
        self.bilan["echecs"].append((chemin, ids, erreur))
        self._ligne("✗", chemin, f"échec, {_planches(ids)} : {erreur}")

    def converti(self, chemin, ids, avant, apres, laisse=None):
        self.bilan["convertis"].append((chemin, ids, avant, apres))
        self.bilan["planches"] += len(ids)
        self.bilan["avant"] += avant
        self.bilan["apres"] += apres
        verbe = "converti" if self.appliquer else "à convertir"
        texte = f"{verbe}, {_planches(ids)} : {_octets(avant)} → {_octets(apres)}"
        if laisse:
            self.bilan["laisses"].append((chemin, laisse))
            texte += f" ; ⚠ le master reste sur le disque — {laisse}"
        self._ligne("✓" if self.appliquer else "·", chemin, texte)


def _convertir(conn, *, albums, appliquer, arret, dire=None) -> dict:
    bilan = {"convertis": [], "sautes": [], "echecs": [], "laisses": [], "planches": 0,
             "avant": 0, "apres": 0, "interrompu": False}
    a_traiter = fichiers_a_convertir(conn, albums)
    bilan["total"] = len(a_traiter)
    suivi = _Suivi(bilan, len(a_traiter), appliquer, dire)
    if dire is not None:
        dire(f"{len(a_traiter)} fichier(s) à traiter, "
             f"{sum(len(planches) for _, planches in a_traiter)} planche(s) — une ligne par "
             "fichier, au moment où il est traité.")
    for chemin, planches in a_traiter:
        if arret is not None and arret.demande:
            bilan["interrompu"] = True
            break
        suivi.n += 1
        ids = [p["id"] for p in planches]
        ancien = DATA_DIR / chemin
        if not chemin_d_image_sur(chemin):
            suivi.saute(chemin, ids, "chemin qui n'a pas la forme d'une image d'album")
            continue
        if not ancien.is_file():
            suivi.saute(chemin, ids, "master absent du disque")
            continue
        accord = _accord(planches)
        if accord is None:
            suivi.saute(chemin, ids, "planches en désaccord sur les dimensions ou la "
                                     "résolution du fichier")
            continue
        largeur, hauteur, dpi_x, dpi_y = accord
        if not (largeur and hauteur):
            # Sans les dimensions du scan, rien ne ramènerait les régions de la copie réduite
            # à leur place (`ocr._open_image` retomberait sur une échelle de 1).
            suivi.saute(chemin, ids, "planche sans dimensions (largeur_px, hauteur_px) : "
                                     "ses régions se décaleraient")
            continue
        avant = ancien.stat().st_size
        try:
            with Image.open(ancien, formats=PILLOW_FORMATS) as img:
                meta = _metadonnees(img)
                if (meta["largeur"], meta["hauteur"]) != (largeur, hauteur):
                    suivi.saute(chemin, ids, (
                        f"le fichier fait {meta['largeur']} × {meta['hauteur']} px, la planche "
                        f"{largeur} × {hauteur}"))
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
            suivi.echec(chemin, ids, f"{type(exc).__name__}: {exc}")
            continue
        if appliquer:
            apres = nouveau.stat().st_size
            try:
                basculees = _basculer(conn, chemin, nouveau, ancien.name, meta)
            except BaseException:
                conn.rollback()
                nouveau.unlink(missing_ok=True)     # la base n'a pas changé : la copie part
                raise
            if not basculees:
                # Plus aucune planche ne désignait ce master SOUS le verrou : converti
                # entre-temps par un autre chemin. La copie qu'on vient d'écrire n'est à
                # personne : elle part, et le fichier compte comme sauté.
                nouveau.unlink(missing_ok=True)
                suivi.saute(chemin, ids, "plus aucune planche ne le désignait au moment "
                                         "de basculer")
                continue
            suivi.converti(chemin, ids, avant, apres, laisse=_effacer_si_libre(conn, chemin))
        else:
            suivi.converti(chemin, ids, avant, apres)
    bilan["orphelins"] = orphelins(conn)
    return bilan


def _basculer(conn, ancien_rel: str, nouveau: Path, nom_origine: str, meta: dict) -> int:
    """Sous le verrou d'écriture : les planches qui désignent le master désignent la copie.
    Rend le nombre de planches basculées — 0 si plus aucune ne le désignait.

    La clause `master_origine IS NULL` est relue SOUS le verrou : une planche convertie entre
    la lecture et l'écriture n'est pas réécrite. Et une copie sœur née entre-temps
    (`database.creer_copie`, qui écrit sous ce même verrou) désigne l'ancien chemin : elle
    suit, puisque la clause porte sur le chemin et non sur une liste d'identifiants."""
    conflit.verrouiller(conn)
    dpi_x, dpi_y = meta["dpi"] if meta["dpi"] else (None, None)
    cur = conn.execute(
        "UPDATE planches SET chemin_tiff = ?, master_origine = ?, "
        "dpi_x = COALESCE(dpi_x, ?), dpi_y = COALESCE(dpi_y, ?), mode = COALESCE(mode, ?) "
        "WHERE chemin_tiff = ? AND master_origine IS NULL",
        (nouveau.relative_to(DATA_DIR).as_posix(), nom_origine, dpi_x, dpi_y, meta["mode"],
         ancien_rel))
    conn.commit()
    return cur.rowcount


def _effacer_si_libre(conn, rel: str) -> str | None:
    """Après le commit, sous le verrou repris : efface le master si plus aucune planche ne
    le désigne — la règle de `socle._sous_le_verrou`. Sans le verrou, ne rien effacer : un
    fichier laissé se rattrape, une image effacée sous une planche, non. Rend None si le
    master est parti, sinon la raison pour laquelle il reste — un effacement refusé (un
    fichier ouvert sous Windows) ne fait pas tomber l'outil APRÈS le commit : il est dit au
    bilan, et le fichier se retrouve dans la liste des orphelins."""
    try:
        conflit.verrouiller(conn)
    except sqlite3.Error as exc:                     # base occupée au-delà du délai
        return f"le verrou d'écriture n'a pas été obtenu ({exc})"
    try:
        employe = conn.execute(
            "SELECT 1 FROM planches WHERE chemin_tiff = ? OR chemin_web = ? LIMIT 1",
            (rel, rel)).fetchone()
        if employe is not None:
            return "une planche le désigne encore"
        try:
            (DATA_DIR / rel).unlink(missing_ok=True)
        except OSError as exc:
            return f"effacement refusé ({exc.strerror or exc})"
        return None
    finally:
        conn.rollback()                              # rien n'a été écrit : verrou rendu


def _ouvrir_la_base(appliquer: bool):
    """La base, SANS `database.init_db()` : à blanc, l'outil n'écrit rien, schéma compris —
    `init_db` refait les vues et migrerait une base plus ancienne. Une base qui n'est pas à
    la version du code est refusée par son nom : c'est l'application qui migre, à son
    démarrage. À blanc, la connexion est en LECTURE SEULE."""
    if not Path(database.DB_PATH).is_file():
        raise SystemExit(f"Base introuvable : {database.DB_PATH}")
    lecture = sqlite3.connect(Path(database.DB_PATH).resolve().as_uri() + "?mode=ro",
                              uri=True)
    version = lecture.execute("PRAGMA user_version").fetchone()[0]
    if version != database.SCHEMA_VERSION:
        lecture.close()
        raise SystemExit(
            f"Base au schéma v{version}, ce code attend la v{database.SCHEMA_VERSION} : "
            "démarrez l'application une fois (elle migre la base), puis relancez l'outil.")
    if not appliquer:
        lecture.row_factory = sqlite3.Row
        return lecture
    lecture.close()
    return database.get_connection()


def _dire(ligne: str) -> None:
    """Une ligne de suivi, VIDÉE aussitôt : redirigée vers un fichier (`nohup … > log`), la
    sortie de Python est mise en tampon par blocs, et le journal resterait vide pendant des
    dizaines de minutes."""
    print(ligne, flush=True)


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

    print(AVERTISSEMENT, flush=True)
    arret = _Arret()
    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is not None:
            signal.signal(sig, arret)

    try:
        conn = _ouvrir_la_base(args.appliquer)
    except SystemExit as exc:
        print(f"✗ {exc}")
        return 2
    try:
        bilan = convertir(conn, albums=tuple(args.album), appliquer=args.appliquer,
                          arret=arret, dire=_dire)
    except PassageEnCours as exc:
        print(f"✗ {exc}")
        return 2
    finally:
        conn.close()

    # Le bilan COMPTE : chaque fichier a déjà eu sa ligne pendant le passage, et la redire
    # ici doublerait un journal de plusieurs centaines de lignes. Les marques (–, ✗, ⚠) se
    # retrouvent par une recherche dans le journal.
    libere = bilan["avant"] - bilan["apres"]
    if args.appliquer:
        print(f"✓ {len(bilan['convertis'])} fichier(s) converti(s), {bilan['planches']} "
              f"planche(s) ; {_octets(libere)} libéré(s) sur le serveur.")
    else:
        print(f"À blanc : {len(bilan['convertis'])} fichier(s) à convertir, "
              f"{bilan['planches']} planche(s) ; {_octets(libere)} seraient libéré(s). "
              "Rien n'a été écrit — relancez avec --appliquer pour convertir.")
    if bilan["sautes"]:
        print(f"  {len(bilan['sautes'])} fichier(s) sauté(s) — lignes « – » plus haut.")
    if bilan["echecs"]:
        print(f"  {len(bilan['echecs'])} fichier(s) en échec — lignes « ✗ » plus haut.")
    if bilan["laisses"]:
        print(f"  {len(bilan['laisses'])} master(s) converti(s) mais resté(s) sur le disque "
              "— lignes « ⚠ » plus haut.")
    if bilan["orphelins"]:
        total = sum(t for _, t in bilan["orphelins"])
        print(f"  {len(bilan['orphelins'])} fichier(s) d'images qu'aucune planche ne "
              f"désigne ({_octets(total)}) — listés, jamais effacés ; un import en cours y "
              "a aussi les siens :")
        for chemin, taille in bilan["orphelins"]:
            nature = ("vide : réservation d'un import interrompu, ou d'un import en cours"
                      if taille == 0 else _octets(taille))
            print(f"    {chemin} ({nature})")
    if bilan["interrompu"]:
        traites = len(bilan["convertis"]) + len(bilan["sautes"]) + len(bilan["echecs"])
        print(f"  Arrêté avant la fin, après {traites} fichier(s) sur {bilan['total']} : "
              "relancez pour traiter le reste.")
        return 130
    return 1 if bilan["echecs"] or bilan["laisses"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
