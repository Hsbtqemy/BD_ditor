"""Les personnages montrés et les situations que portent des régions qui ne les montrent
pas (ANN-8) — CLI.

Le miroir du locuteur, tranché par Hugo le 2026-10-21 : une région qui change de type perd
ce que son nouveau type ne montre pas. Une boîte personnage devenue bulle perd son
personnage montré, une case devenue bulle (cartouche, zone de texte, boîte personnage) sa
situation ; l'annulation ne les repose que sur un type qui les montre. Avant cette règle,
ils restaient : invisibles à l'écran, ils comptaient encore au registre, dans la Recherche,
l'Exploration et les exports. Cet outil dit ce que la base porte déjà, et le retire si on le
lui demande. Les locuteurs ont leur outil, `retirer_locuteurs_muets.py` : au déploiement,
les deux.

    python tools/retirer_liens_caches.py               # à blanc : dit, n'écrit rien
    python tools/retirer_liens_caches.py --appliquer   # retire, et journalise

**À blanc par défaut**, la base ouverte en LECTURE SEULE et jamais par `init_db` — le
patron de `retirer_locuteurs_muets.py`, dont il reprend l'ouverture.

**Le retrait est un acte MACHINE** (`agent_type='moteur'`, sous le nom du logiciel,
`retrait-liens-caches`), hors de portée de Ctrl+Z. Chaque retrait est un `delien` — sous
`personnage_presence` (le personnage dans `avant`) ou sous `region_attribut` (la valeur dans
`avant`), la région pour cible : le journal garde de quoi le relire.

Le compte rendu nomme un personnage du registre, jamais un terme de vocabulaire : une
situation se dit par l'identifiant de sa valeur — un terme peut être local à une
collection, et l'outil porte sur la base entière.

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conflit  # noqa: E402
import config  # noqa: E402
import database  # noqa: E402
import journal  # noqa: E402
from retirer_locuteurs_muets import _ouvrir_la_base  # noqa: E402

AGENT = "retrait-liens-caches"
# Combien de lignes montrer : assez pour juger, pas assez pour noyer la console.
APERCU = 20


def _err(msg=""):
    print(msg, file=sys.stderr)


def _lignes(conn) -> list:
    """Ce que la base porte de trop, présences puis situations : (sorte, ligne)."""
    return ([("presence", r) for r in database.presences_cachees(conn)]
            + [("situation", r) for r in database.situations_cachees(conn)])


def _apercu(lignes) -> None:
    for sorte, r in lignes[:APERCU]:
        quoi = (f"personnage montré « {r['personnage_nom']} » (personnage {r['personnage_id']})"
                if sorte == "presence" else f"situation, valeur {r['valeur_id']}")
        _err(f"    - région {r['region_id']} ({r['type']}), planche {r['planche_id']}, "
             f"album {r['album_id']} : {quoi}")
    if len(lignes) > APERCU:
        _err(f"    … et {len(lignes) - APERCU} autre(s).")


def appliquer(conn: sqlite3.Connection) -> dict:
    """Retire, sous le verrou d'écriture, les personnages montrés hors des boîtes personnage
    et les situations hors des cases, et journalise la passe (A3). La liste est RELUE sous le
    verrou. Rend `{"presences": n, "situations": n}` (une situation compte par valeur).

    L'activité d'ouverture est validée TOUT DE SUITE, comme dans `retirer_locuteurs_muets.py` :
    une passe ratée doit laisser sa trace."""
    aid = journal.ouvrir_activite(conn, "retrait_liens_caches", agent=AGENT,
                                  agent_type="moteur",
                                  params={"types_presence": list(config.TYPES_PRESENCE),
                                          "types_situation": list(config.TYPES_SITUATION)},
                                  portee={"corpus": True})
    conn.commit()
    n = {"presences": 0, "situations": 0}
    try:
        conflit.verrouiller(conn)
        for r in database.presences_cachees(conn):
            conn.execute("DELETE FROM personnage_presence WHERE region_id = ?",
                         (r["region_id"],))
            journal.journaliser(conn, "delien", "personnage_presence", r["region_id"],
                                avant={"personnage_id": r["personnage_id"]},
                                agent=AGENT, agent_type="moteur", activite_id=aid)
            n["presences"] += 1
        for r in database.situations_cachees(conn):
            conn.execute("DELETE FROM region_attribut WHERE region_id = ? AND valeur_id = ?",
                         (r["region_id"], r["valeur_id"]))
            journal.journaliser(conn, "delien", "region_attribut", r["region_id"],
                                avant={"valeur_id": r["valeur_id"]},
                                agent=AGENT, agent_type="moteur", activite_id=aid)
            n["situations"] += 1
        journal.cloturer_activite(conn, aid, comptes=dict(n))
        conn.commit()
    except BaseException as exc:
        # Ctrl+C sur une CLI : tout est défait ensemble, et l'activité le dit. Bilan MINIMAL :
        # `comptes` sort de l'instance.
        conn.rollback()
        interrompu = isinstance(exc, (KeyboardInterrupt, SystemExit))
        journal.cloturer_activite(
            conn, aid, comptes={"presences": 0, "situations": 0,
                                "interrompu" if interrompu else "echec": True})
        conn.commit()
        raise
    return n


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                                 # Windows : stdout/stderr en UTF-8
    ap = argparse.ArgumentParser(
        description="Dit quelles régions montrent un personnage hors d'une boîte personnage, "
                    "ou portent une situation hors d'une case, et le leur retire avec "
                    "--appliquer (acte machine, journalisé).")
    ap.add_argument("--appliquer", action="store_true",
                    help="retire ces liens ; sans lui, l'outil dit et n'écrit rien")
    args = ap.parse_args(argv)

    conn = _ouvrir_la_base(args.appliquer)
    try:
        lignes = _lignes(conn)
        if not lignes:
            _err("✓ Aucune région ne montre de personnage hors d'une boîte personnage, "
                 "ni ne porte de situation hors d'une case.")
            return 0
        _err(f"→ {len(lignes)} lien(s) que le type de leur région ne montre pas :")
        _apercu(lignes)
        if not args.appliquer:
            _err("— À BLANC : rien n'est écrit. --appliquer les retire.")
            return 0
        n = appliquer(conn)
        _err(f"✓ {n['presences']} personnage(s) montré(s) et {n['situations']} valeur(s) de "
             "situation retirés, journalisés en acte MACHINE (hors Ctrl+Z).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
