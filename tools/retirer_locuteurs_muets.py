"""Les locuteurs que portent des régions qui n'en portent pas (ANN-8) — CLI.

Une case ou une boîte personnage n'a pas de locuteur : la route qui l'attribue le refuse,
le changement de type l'emporte, l'annulation refuse de le reposer (ANN-8, tranché par Hugo
le 2026-10-21). Avant cette règle, une bulle qui parlait DEVENAIT case en le gardant :
invisible à l'écran, il comptait encore au registre, dans la Recherche et les exports. Cet
outil dit ce que la base porte déjà, et le retire si on le lui demande.

    python tools/retirer_locuteurs_muets.py               # à blanc : dit, n'écrit rien
    python tools/retirer_locuteurs_muets.py --appliquer   # retire, et journalise

**À blanc par défaut.** La base s'ouvre alors en LECTURE SEULE, et jamais par `init_db` :
regarder ne migre rien, et rien ne s'écrit par mégarde.

**Le retrait est un acte MACHINE** (`agent_type='moteur'`, sous le nom du logiciel,
`retrait-locuteurs-muets`), comme la normalisation de casse : une règle appliquée par un
logiciel, pas un humain qui corrige. Il est donc HORS de portée de Ctrl+Z, qui ne remonte
que les actes humains — et c'est voulu : l'annulation refuserait de toute façon de reposer
un locuteur sur une case. Chaque retrait est un `delien` sous `bulle_locuteur`, la région
pour cible, le personnage dans `avant` : le journal garde de quoi le relire.

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import conflit  # noqa: E402
import config  # noqa: E402
import database  # noqa: E402
import journal  # noqa: E402

AGENT = "retrait-locuteurs-muets"
# Combien de lignes montrer : assez pour juger, pas assez pour noyer la console.
APERCU = 20


def _err(msg=""):
    print(msg, file=sys.stderr)


def _ouvrir_la_base(appliquer: bool) -> sqlite3.Connection:
    """La base, SANS `database.init_db()` — le patron de `convertir_en_copies_de_travail.py` :
    à blanc, l'outil n'écrit rien, schéma compris, et la connexion est en LECTURE SEULE. Une
    base qui n'est pas à la version du code est refusée par son nom : c'est l'application qui
    migre, à son démarrage."""
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


def _apercu(lignes) -> None:
    for r in lignes[:APERCU]:
        _err(f"    - région {r['region_id']} ({r['type']}), planche {r['planche_id']}, "
             f"album {r['album_id']} : locuteur « {r['personnage_nom']} » "
             f"(personnage {r['personnage_id']})")
    if len(lignes) > APERCU:
        _err(f"    … et {len(lignes) - APERCU} autre(s).")


def appliquer(conn: sqlite3.Connection) -> int:
    """Retire, sous le verrou d'écriture, les locuteurs des régions d'un type muet, et
    journalise la passe (A3). La liste est RELUE sous le verrou : ce qui part est ce que la
    base porte au moment d'écrire, pas ce que l'aperçu avait vu. Rend le nombre de retraits.

    L'activité d'ouverture est validée TOUT DE SUITE, comme dans `normaliser_casse.py` : une
    passe ratée doit laisser sa trace, et ne pas se confondre avec une passe jamais lancée.
    """
    aid = journal.ouvrir_activite(conn, "retrait_locuteurs_muets", agent=AGENT,
                                  agent_type="moteur",
                                  params={"types_locuteur": list(config.TYPES_LOCUTEUR)},
                                  portee={"corpus": True})
    conn.commit()
    n = 0
    try:
        conflit.verrouiller(conn)
        for r in database.locuteurs_muets(conn):
            if database.retirer_locuteur_muet(conn, r["region_id"]) is None:
                continue
            journal.journaliser(conn, "delien", "bulle_locuteur", r["region_id"],
                                avant={"personnage_id": r["personnage_id"]},
                                agent=AGENT, agent_type="moteur", activite_id=aid)
            n += 1
        journal.cloturer_activite(conn, aid, comptes={"regions": n})
        conn.commit()
    except BaseException as exc:
        # `BaseException`, pour la raison de `normaliser_casse.py` : Ctrl+C sur une CLI.
        # Les retraits sont dans UNE transaction : défaits ensemble, et l'activité dit
        # qu'aucun n'a tenu. Bilan MINIMAL : `comptes` sort de l'instance.
        conn.rollback()
        interrompu = isinstance(exc, (KeyboardInterrupt, SystemExit))
        journal.cloturer_activite(
            conn, aid, comptes={"regions": 0, "interrompu" if interrompu else "echec": True})
        conn.commit()
        raise
    return n


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                                 # Windows : stdout/stderr en UTF-8
    ap = argparse.ArgumentParser(
        description="Dit quelles cases et boîtes personnage portent encore un locuteur, "
                    "et le leur retire avec --appliquer (acte machine, journalisé).")
    ap.add_argument("--appliquer", action="store_true",
                    help="retire ces locuteurs ; sans lui, l'outil dit et n'écrit rien")
    args = ap.parse_args(argv)

    conn = _ouvrir_la_base(args.appliquer)
    try:
        lignes = database.locuteurs_muets(conn)
        if not lignes:
            _err("✓ Aucune case ni boîte personnage ne porte de locuteur.")
            return 0
        _err(f"→ {len(lignes)} région(s) d'un type sans locuteur en portent un :")
        _apercu(lignes)
        if not args.appliquer:
            _err("— À BLANC : rien n'est écrit. --appliquer les retire.")
            return 0
        n = appliquer(conn)
        _err(f"✓ {n} locuteur(s) retiré(s), journalisé(s) en acte MACHINE (hors Ctrl+Z).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
