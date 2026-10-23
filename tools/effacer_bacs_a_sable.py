r"""Efface les BACS À SABLE dont le moment est venu (COL-4).

Chaque bac à sable porte, depuis sa naissance, le moment de son effacement
(`projet.efface_le` : le lundi à 4 h, heure de Paris, pour tous et sans exception — Hugo,
2026-10-22). Cet outil efface ceux dont ce moment est PASSÉ, par le chemin de la remise à
neuf (`socle._effacer_bac_a_sable`) : leurs albums — copies du jeu, imports, copies gardées
au fonds —, leur vocabulaire, leurs collections, le projet. Les images du jeu restent : la
référence les désigne. Puis il détruit les copies de référence que plus rien n'appelle
(`tools/preparer_jeu.purger_les_references`).

La date est en base, la minuterie n'est qu'un battement : une unité systemd sur l'hôte
(`deploy/systemd/bd-bacs-a-sable.timer`) lance l'outil toutes les heures, et un battement
manqué se rattrape au suivant. Celle qu'on affiche est celle qu'on applique.

Par défaut l'outil ne fait que DIRE quels bacs à sable il effacerait, base ouverte en
LECTURE SEULE et sans `database.init_db()` ; une base qui n'est pas à la version du code est
refusée. Avec `--appliquer`, sous un verrou propre à l'outil (`effacer_bacs_a_sable.verrou`
à la racine des données, créé en exclusif — deux battements ne se chevauchent pas), bac à
sable par bac à sable. S'arrête PROPREMENT sur Ctrl+C ou un arrêt du conteneur (SIGTERM) :
le bac à sable en cours est mené au bout, les suivants attendent le battement suivant.

Le journal garde tout, append-only : l'effacement s'écrit `suppression` sous `projet`, sans
agent — un shell n'a pas d'identité.

Usage :
    python tools/effacer_bacs_a_sable.py                          # à blanc
    python tools/effacer_bacs_a_sable.py --appliquer
    python tools/effacer_bacs_a_sable.py --tous --appliquer       # tous, maintenant
    python tools/effacer_bacs_a_sable.py --maintenant "2026-11-02 03:00:00"   # UTC

En production, l'unité systemd le lance dans le conteneur ; à la main, depuis
`~/BD_ditor/deploy` :
    docker compose exec app python tools/effacer_bacs_a_sable.py --appliquer
"""
from __future__ import annotations

import argparse
import os
import signal
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _commun import forcer_utf8                                   # noqa: E402
import autorisation                                               # noqa: E402
import database                                                   # noqa: E402
from pipeline import ingest                                       # noqa: E402

NOM_DU_VERROU = "effacer_bacs_a_sable.verrou"


class PassageEnCours(RuntimeError):
    """Un autre passage `--appliquer` tient le verrou de l'outil."""


class _Arret:
    """Un arrêt demandé (Ctrl+C, SIGTERM) attend la fin du bac à sable en cours."""

    def __init__(self):
        self.demande = False

    def __call__(self, signum, frame):          # pragma: no cover - signal réel
        self.demande = True
        print("  … arrêt demandé : le bac à sable en cours est mené au bout.", flush=True)


def a_effacer(conn, *, maintenant: str, tous: bool = False) -> list[dict]:
    """Les bacs à sable dont le moment est passé (`efface_le` ≤ `maintenant`, UTC, la forme
    des dates SQLite), ou tous avec `tous`. Un bac à sable sans date (base retouchée) n'est
    effacé qu'avec `tous` : on ne devine pas un moment."""
    sql = ("SELECT id, bac_a_sable_de, efface_le FROM projet "
           "WHERE bac_a_sable_de IS NOT NULL")
    params: list = []
    if not tous:
        sql += " AND efface_le IS NOT NULL AND efface_le <= ?"
        params.append(maintenant)
    return [dict(id=r[0], de=r[1], efface_le=r[2])
            for r in conn.execute(sql + " ORDER BY efface_le, id", params)]


@contextmanager
def _verrou_de_l_outil():
    chemin = Path(ingest.DATA_DIR) / NOM_DU_VERROU
    try:
        fd = os.open(chemin, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise PassageEnCours(
            f"Un autre passage --appliquer tient le verrou {chemin}. S'il ne tourne plus — "
            "arrêté brutalement —, effacez ce fichier, puis relancez.") from None
    try:
        os.write(fd, f"pid {os.getpid()}, depuis {time.strftime('%Y-%m-%d %H:%M:%S')}"
                 .encode("utf-8"))
    finally:
        os.close(fd)
    try:
        yield
    finally:
        chemin.unlink(missing_ok=True)


def effacer(conn, *, maintenant: str | None = None, tous: bool = False,
            appliquer: bool = False, arret=None, dire=print) -> dict:
    """Le cœur, pour la ligne de commande et les tests. Rend `{a_effacer, effaces,
    references, interrompu}`."""
    import socle                                  # le chemin de l'effacement
    import preparer_jeu                           # la purge des références
    maintenant = maintenant or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    liste = a_effacer(conn, maintenant=maintenant, tous=tous)
    bilan = {"a_effacer": [b["id"] for b in liste], "effaces": [], "references": [],
             "interrompu": False}
    if not appliquer:
        for b in liste:
            dire(f"  − effacerait le bac à sable {b['id']} (prévu le {b['efface_le']} UTC)")
        return bilan
    with _verrou_de_l_outil():
        for b in liste:
            if arret is not None and arret.demande:
                bilan["interrompu"] = True
                break
            r = socle._effacer_bac_a_sable(conn, autorisation.TOTALE, b["id"],
                                           motif="effacement")
            bilan["effaces"].append(b["id"])
            dire(f"  × bac à sable {b['id']} effacé : {r['albums']} album(s)")
        bilan["references"] = preparer_jeu.purger_les_references(conn)
        for a in bilan["references"]:
            dire(f"  × référence {a} du jeu détruite : plus aucune copie ne la tenait")
    return bilan


def _ouvrir_la_base(appliquer: bool):
    """La base, SANS `database.init_db()` ; à blanc, en LECTURE SEULE. Une base qui n'est pas
    à la version du code est refusée : c'est l'application qui migre."""
    if not Path(database.DB_PATH).is_file():
        raise SystemExit(f"Base introuvable : {database.DB_PATH}")
    lecture = sqlite3.connect(Path(database.DB_PATH).resolve().as_uri() + "?mode=ro",
                              uri=True)
    version = lecture.execute("PRAGMA user_version").fetchone()[0]
    if version != database.SCHEMA_VERSION:
        lecture.close()
        raise SystemExit(f"Base au schéma v{version}, ce code attend la "
                         f"v{database.SCHEMA_VERSION} : démarrez l'application une fois.")
    if not appliquer:
        lecture.row_factory = sqlite3.Row
        return lecture
    lecture.close()
    return database.get_connection()


def main(argv=None) -> int:
    forcer_utf8()
    ap = argparse.ArgumentParser(
        description="Efface les bacs à sable dont le moment est venu (COL-4). À blanc par "
                    "défaut.")
    ap.add_argument("--appliquer", action="store_true", help="efface pour de bon")
    ap.add_argument("--tous", action="store_true",
                    help="tous les bacs à sable, quelle que soit leur date")
    ap.add_argument("--maintenant", default=None,
                    help="l'instant de référence, UTC, « AAAA-MM-JJ HH:MM:SS » (défaut : "
                         "l'heure du serveur)")
    args = ap.parse_args(argv)
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
        bilan = effacer(conn, maintenant=args.maintenant, tous=args.tous,
                        appliquer=args.appliquer, arret=arret,
                        dire=lambda ligne: print(ligne, flush=True))
    except PassageEnCours as exc:
        print(f"✗ {exc}")
        return 2
    finally:
        conn.close()
    if args.appliquer:
        print(f"✓ {len(bilan['effaces'])} bac(s) à sable effacé(s), "
              f"{len(bilan['references'])} référence(s) du jeu détruite(s).")
    else:
        print(f"À blanc : {len(bilan['a_effacer'])} bac(s) à sable à effacer. Rien n'a été "
              "écrit — relancez avec --appliquer.")
    if bilan["interrompu"]:
        print("  Arrêté avant la fin : le battement suivant finira.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
