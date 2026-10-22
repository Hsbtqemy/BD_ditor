"""Les tags LOCAUX posés hors de leur collection (ANN-8) — CLI, à blanc seulement.

Un tag local ne se pose que sur les albums de sa collection (décision de Hugo du
2026-10-22) : la saisie le refuse depuis (`socle._ensure_tags`). Avant, qui lisait la
collection d'un tag et écrivait dans un album rangé ailleurs l'y posait ; un tag rendu local
après avoir servi, ou un album retiré de la collection, laissent le même état. Ce qui existe
RESTE — rien ne l'efface — et cet outil le dit : quels tags, de quelle collection, sur
combien de régions, dans quels albums.

    python tools/tags_hors_collection.py

**Il n'écrit rien, jamais.** La base s'ouvre en LECTURE SEULE, et jamais par `init_db` :
regarder ne migre rien. Pour défaire un emploi, c'est un geste à faire à la main (retirer le
tag dans l'Atelier, ou fusionner le tag dans un tag global depuis le panneau 📖 Lexique —
la fusion d'un tag posé là où l'on n'écrit pas reste à un administrateur).

Son compte rendu nomme des tags, des collections et des albums — des objets du corpus,
jamais une colonne d'identité. La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402

# Combien d'albums nommer par tag : assez pour juger, pas assez pour noyer la console.
APERCU = 10

# Une région porte un tag local hors de sa collection quand son album n'est pas rangé dans
# la collection du tag — un album au fonds (sans collection) compris.
SQL_HORS_COLLECTION = """
SELECT t.id AS tag_id, t.label, t.collection_id, c.nom AS collection_nom,
       a.id AS album_id, a.titre, COUNT(*) AS regions
  FROM annotation_tags at
  JOIN tags t        ON t.id = at.tag_id
  JOIN annotations an ON an.id = at.annotation_id
  JOIN regions r     ON r.id = an.region_id
  JOIN planches pl   ON pl.id = r.planche_id
  JOIN albums a      ON a.id = pl.album_id
  LEFT JOIN collection c ON c.id = t.collection_id
 WHERE t.collection_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM collection_album ca
                    WHERE ca.album_id = a.id AND ca.collection_id = t.collection_id)
 GROUP BY t.id, a.id
 ORDER BY t.label, t.id, a.id
"""


def _err(msg=""):
    print(msg, file=sys.stderr)


def _ouvrir_la_base() -> sqlite3.Connection:
    """La base en LECTURE SEULE, sans `database.init_db()` (le patron de
    `retirer_locuteurs_muets.py`). Une base qui n'est pas à la version du code est refusée
    par son nom : c'est l'application qui migre, à son démarrage."""
    if not Path(database.DB_PATH).is_file():
        raise SystemExit(f"Base introuvable : {database.DB_PATH}")
    conn = sqlite3.connect(Path(database.DB_PATH).resolve().as_uri() + "?mode=ro", uri=True)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != database.SCHEMA_VERSION:
        conn.close()
        raise SystemExit(
            f"Base au schéma v{version}, ce code attend la v{database.SCHEMA_VERSION} : "
            "démarrez l'application une fois (elle migre la base), puis relancez l'outil.")
    conn.row_factory = sqlite3.Row
    return conn


def emplois_hors_collection(conn: sqlite3.Connection) -> list[dict]:
    """Une ligne par (tag local, album hors de sa collection), avec le nombre de régions."""
    return [dict(r) for r in conn.execute(SQL_HORS_COLLECTION)]


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                                 # Windows : stdout/stderr en UTF-8
    argparse.ArgumentParser(
        description="Dit quels tags locaux sont posés sur des albums que leur collection "
                    "ne range pas. N'écrit rien.").parse_args(argv)
    conn = _ouvrir_la_base()
    try:
        lignes = emplois_hors_collection(conn)
    finally:
        conn.close()
    if not lignes:
        _err("✓ Aucun tag local n'est posé hors de sa collection.")
        return 0
    par_tag: dict[int, list[dict]] = {}
    for l in lignes:
        par_tag.setdefault(l["tag_id"], []).append(l)
    _err(f"→ {len(par_tag)} tag(s) local(aux) posé(s) hors de leur collection :")
    for albums in par_tag.values():
        t = albums[0]
        n = sum(a["regions"] for a in albums)
        _err(f"  - « {t['label']} » (tag {t['tag_id']}, collection "
             f"« {t['collection_nom'] or t['collection_id']} ») : {n} région(s), "
             f"{len(albums)} album(s)")
        for a in albums[:APERCU]:
            _err(f"      album {a['album_id']} « {a['titre']} » : {a['regions']} région(s)")
        if len(albums) > APERCU:
            _err(f"      … et {len(albums) - APERCU} autre(s).")
    _err("— À BLANC : rien n'est écrit. Ce qui existe reste ; la saisie refuse désormais "
         "d'en poser de nouveaux.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
