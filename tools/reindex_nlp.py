r"""Réindexation NLP en lot (lemmes + tokens) de tout le corpus.

À lancer explicitement — c'est l'outil qui sert les deux phases du projet :
  - Phase 1 (constitution) : recalculer après un changement de paramètre/modèle ;
  - transition vers la consultation : figer l'index DÉFINITIF, éventuellement avec
    un modèle plus riche (fr_core_news_lg) lancé HORS LIGNE (vecteurs sémantiques).

La migration au démarrage ne fait que l'indexation STRUCTURELLE (recherche par
préfixe+accents) ; l'enrichissement NLP (lemmes + tokens) se fait ici, sans bloquer
le démarrage du serveur.

Usage :
    python tools/reindex_nlp.py                  # tout le corpus
    python tools/reindex_nlp.py --a-rattraper    # seulement ce qu'une écriture a laissé
                                                 # sans lemmes ni tokens (NLP-4)

EN VEILLE (NLP-4) : quand l'application tourne avec `BD_NLP=0`, l'outil la respecte et
refuse — une réindexation sans moteur EFFACERAIT les tokens de tout le corpus. Il se
rallume pour son seul processus : `BD_NLP=1 python tools/reindex_nlp.py --a-rattraper`,
ce que fait chaque nuit `deploy/reindex-nlp.sh`. Le processus rend sa mémoire en se
terminant ; l'application, elle, ne charge jamais spaCy.

Configuration (variables d'environnement, comme l'app) :
    BD_SPACY_MODEL   modèle spaCy (défaut fr_core_news_sm ; fr_core_news_lg pour
                     l'index définitif riche, de préférence hors ligne)
    BD_NLP           0 (ou false, no, non, off) : moteur en veille, l'outil refuse
    BD_DATA_DIR / BD_DB_PATH   emplacement de la base

Peut tourner pendant que le serveur lit (SQLite WAL) ; commit par lots.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import database                                               # noqa: E402
from pipeline.nlp import en_veille, model_info, nlp_available  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Réindexation NLP en lot (lemmes + tokens).")
    ap.add_argument("--a-rattraper", action="store_true",
                    help="ne refaire que les régions réindexées sans moteur de langue "
                         "(spaCy en veille ou absent) : lemmes vides, aucun token")
    args = ap.parse_args(argv)
    if en_veille():
        print("✗ spaCy est EN VEILLE (BD_NLP=0) — rien n'est réindexé.\n"
              "  Sans moteur, la réindexation effacerait les tokens du corpus.\n"
              "  Pour ce seul passage :  BD_NLP=1 python tools/reindex_nlp.py --a-rattraper")
        return 1
    if not nlp_available():
        print("✗ spaCy / modèle indisponible — rien à réindexer.\n"
              "  (La recherche fonctionne en repli préfixe+accents.)\n"
              "  Installer :  pip install -r requirements-nlp.txt && "
              "python -m spacy download fr_core_news_sm")
        return 1

    database.init_db()                              # schéma à jour (sans bloquer : structurel)
    conn = database.get_connection()
    try:
        regions = None
        if args.a_rattraper:
            regions = database.regions_a_rattraper(conn)
            if not regions:
                # Rien à faire : le modèle ne se charge pas, et le journal ne compte pas
                # une activité vide chaque nuit.
                print("✓ Rien à rattraper.")
                return 0
            print(f"→ {len(regions)} région(s) à rattraper.")
        print(f"→ Modèle : {model_info().get('model')}")
        print("→ Réindexation NLP en lot (lemmes + tokens)…")
        t0 = time.perf_counter()
        n = database.reindex_all(conn, regions=regions)
    finally:
        conn.close()
    print(f"✓ {n} région(s) réindexée(s) en {time.perf_counter() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
