"""Ce que la v38 (COL-3, tranche 3c) ajoute à toute base qui migre, pour les tests de
migration des versions d'AVANT : ils migrent jusqu'à la version courante, et comparent
« avant » et « après » ligne à ligne. La v38 fait entrer dans leur projet les principaux qui
tenaient un accès de collection hors projet (F2) — des lignes de `projet_acces` que la
version éprouvée n'a pas écrites. `retirer_les_membres_de_la_v38` les retire, et RIEN
d'autre : ce qu'elles valent est éprouvé par `tests/test_migration_v38.py`, sur la vraie base
v37. Les deux autres apports de la v38 se déclarent dans chaque test : `demande.planche_id`
et `planche_numero` (des colonnes neuves), `geste_sur_copie` (une table qui part)."""
import sqlite3

COLONNES_V38 = {"demande": ("planche_id", "planche_numero")}


def membres(db) -> set:
    c = sqlite3.connect(db)
    try:
        return {tuple(r) for r in c.execute(
            "SELECT projet_id, genre, principal FROM projet_acces")}
    finally:
        c.close()


def retirer_les_membres_de_la_v38(db, avant: set) -> set:
    """Retire de `projet_acces` les lignes nées de la migration (absentes d'`avant`) ; les
    rend. Toutes doivent être des MEMBRES — la v38 n'écrit pas d'autre rôle."""
    c = sqlite3.connect(db)
    try:
        nees = {tuple(r) for r in c.execute(
            "SELECT projet_id, genre, principal, role FROM projet_acces")
            if tuple(r)[:3] not in avant}
        assert all(r[3] == "membre" for r in nees), nees
        for pid, genre, principal, _ in nees:
            c.execute("DELETE FROM projet_acces WHERE projet_id = ? AND genre = ? "
                      "AND principal = ?", (pid, genre, principal))
        c.commit()
        return nees
    finally:
        c.close()
