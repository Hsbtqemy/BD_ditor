"""Ce que la v39 (ANN-7, le basculement) change à toute base qui migre, pour les tests de
migration des versions d'AVANT : ils migrent jusqu'à la version courante, et comparent
« avant » et « après » ligne à ligne. La v39 :

- DÉTRUIT les sept tables du vocabulaire d'hier (`TABLES_V39`, écrites ici à la main pour que
  ces tests ne soient pas le miroir d'une constante) et leurs index ;
- retire les annotations SANS NOTE (une ligne qui ne portait que des tags) ;
- pose `grille_entree.etat` et `grille.travail` (`COLONNES_V39`) ;
- écrit le plancher de Ctrl+Z dans `meta`, et donne à chaque projet sa grille de TRAVAIL —
  des grilles, des versions, des activations et des actes du journal que la version
  éprouvée n'a pas écrits.

`avant_la_v39` photographie ce qu'il faut pour en revenir ; `defaire_la_v39` retire ce que la
migration a ÉCRIT (les grilles de travail nées, leurs actes, le plancher) et RIEN d'autre ;
`sans_la_v39` ramène un état « avant » à ce qui doit survivre. Ce que la v39 vaut est éprouvé
par `tests/test_migration_v39.py`, sur la vraie base v38."""
import re
import sqlite3

TABLES_V39 = ("tags", "annotation_tags", "domaine", "attribut_dimension", "attribut_valeur",
              "personnage_attribut", "region_attribut")
COLONNES_V39 = {"grille_entree": ("etat",), "grille": ("travail",)}
_INDEX_V39 = re.compile(r"\bON\s+\"?(" + "|".join(TABLES_V39) + r")\"?\s*\(")


def _c(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def avant_la_v39(db) -> dict:
    """Avant `init_db` : le dernier acte du journal, les grilles qui existent, et les
    annotations sans note que la migration retirera."""
    c = _c(db)
    try:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        return {
            "evenement": c.execute("SELECT COALESCE(MAX(id), 0) FROM evenement").fetchone()[0],
            "grilles": ({r[0] for r in c.execute("SELECT id FROM grille")}
                        if "grille" in tables else set()),
            "compteurs": ({r[0]: r[1] for r in c.execute(
                "SELECT name, seq FROM sqlite_sequence WHERE name IN ('grille', "
                "'grille_version')")} if "sqlite_sequence" in tables else {}),
            "annotations_sans_note": (c.execute(
                "SELECT COUNT(*) FROM annotations WHERE TRIM(COALESCE(note, '')) = ''"
            ).fetchone()[0] if "annotations" in tables else 0),
        }
    finally:
        c.close()


def defaire_la_v39(db, avant: dict) -> list:
    """Après `init_db` : retire les grilles de TRAVAIL nées de la migration (leurs versions,
    leurs activations, les compteurs qu'elles ont avancés), les actes du journal écrits depuis
    `avant`, et le plancher de `meta`. Rend les noms des grilles retirées — toutes doivent être des grilles de
    travail, sans entrée."""
    from config import GRILLE_DE_TRAVAIL_NOM
    c = _c(db)
    try:
        nees = [r for r in c.execute("SELECT id, nom FROM grille")
                if r["id"] not in avant["grilles"]]
        assert all(r["nom"] == GRILLE_DE_TRAVAIL_NOM for r in nees), [tuple(r) for r in nees]
        for r in nees:
            assert not c.execute("SELECT 1 FROM grille_entree e JOIN grille_version v "
                                 "ON v.id = e.version_id WHERE v.grille_id = ?",
                                 (r["id"],)).fetchone()
            c.execute("DELETE FROM projet_grille WHERE grille_id = ?", (r["id"],))
            c.execute("DELETE FROM grille_version WHERE grille_id = ?", (r["id"],))
            c.execute("DELETE FROM grille WHERE id = ?", (r["id"],))
        # Les compteurs que ces naissances ont avancés reviennent à leur valeur d'avant (ou
        # disparaissent) : c'est l'écriture de la migration qu'on défait, rien d'autre.
        for t in ("grille", "grille_version"):
            if t in avant["compteurs"]:
                c.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
                          (avant["compteurs"][t], t))
            else:
                c.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))
        c.execute("DELETE FROM evenement WHERE id > ?", (avant["evenement"],))
        c.execute("DELETE FROM meta WHERE cle = 'plancher_annulation'")
        c.commit()
        return [r["nom"] for r in nees]
    finally:
        c.close()


def comptes_sans_la_v39(comptes: dict, avant: dict) -> dict:
    """Les comptes d'AVANT par table, ramenés à ce qui doit survivre : sans les sept tables,
    et sans les annotations qui ne portaient pas de note."""
    r = {t: n for t, n in comptes.items() if t not in TABLES_V39}
    if "annotations" in r:
        r["annotations"] -= avant["annotations_sans_note"]
    return r


def index_sans_la_v39(index) -> list:
    """Les index d'AVANT, sans ceux des sept tables."""
    return [s for s in index if not _INDEX_V39.search(s)]


def ramener_l_etat(etat: dict, avant: dict) -> dict:
    """Un état d'AVANT, de la forme que photographient les tests de migration (`tables`,
    `comptes`, `lignes`, `index` — chacune facultative), ramené à ce qui doit survivre à la
    v39 : sans les sept tables ni leurs index, sans les annotations qui ne portaient pas de
    note. Rend une copie."""
    import json
    e = dict(etat)
    if "tables" in e:
        e["tables"] = [t for t in e["tables"] if t not in TABLES_V39]
    if "comptes" in e:
        e["comptes"] = comptes_sans_la_v39(e["comptes"], avant)
    if "lignes" in e:
        lignes = {t: v for t, v in e["lignes"].items() if t not in TABLES_V39}
        if "annotations" in lignes:
            lignes["annotations"] = [
                l for l in lignes["annotations"]
                if (json.loads(l).get("note") or "").strip()]
        e["lignes"] = lignes
    if "index" in e:
        e["index"] = index_sans_la_v39(e["index"])
    return e
