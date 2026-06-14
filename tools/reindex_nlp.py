r"""Réindexation NLP en lot (lemmes + tokens) de tout le corpus.

À lancer explicitement — c'est l'outil qui sert les deux phases du projet :
  - Phase 1 (constitution) : recalculer après un changement de paramètre/modèle ;
  - transition vers la consultation : figer l'index DÉFINITIF, éventuellement avec
    un modèle plus riche (fr_core_news_lg) lancé HORS LIGNE (vecteurs sémantiques).

La migration au démarrage ne fait que l'indexation STRUCTURELLE (recherche par
préfixe+accents) ; l'enrichissement NLP (lemmes + tokens) se fait ici, sans bloquer
le démarrage du serveur.

Usage :
    python tools/reindex_nlp.py

Configuration (variables d'environnement, comme l'app) :
    BD_SPACY_MODEL   modèle spaCy (défaut fr_core_news_sm ; fr_core_news_lg pour
                     l'index définitif riche, de préférence hors ligne)
    BD_DATA_DIR / BD_DB_PATH   emplacement de la base

Peut tourner pendant que le serveur lit (SQLite WAL) ; commit par lots.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import database                                    # noqa: E402
from pipeline.nlp import model_info, nlp_available  # noqa: E402


def main() -> int:
    if not nlp_available():
        print("✗ spaCy / modèle indisponible — rien à réindexer.\n"
              "  (La recherche fonctionne en repli préfixe+accents.)\n"
              "  Installer :  pip install -r requirements-nlp.txt && "
              "python -m spacy download fr_core_news_sm")
        return 1

    database.init_db()                              # schéma à jour (sans bloquer : structurel)
    print(f"→ Modèle : {model_info().get('model')}")
    print("→ Réindexation NLP en lot (lemmes + tokens)…")
    t0 = time.perf_counter()
    conn = database.get_connection()
    try:
        n = database.reindex_all(conn)
    finally:
        conn.close()
    print(f"✓ {n} région(s) réindexée(s) en {time.perf_counter() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
