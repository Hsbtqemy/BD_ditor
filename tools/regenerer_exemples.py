"""(Re)génère TOUT le jeu d'exemples de `docs/exemples/` de façon reproductible.

Sème un corpus de démonstration (tools/semer_demo.py) dans une base JETABLE (dossier
temporaire — aucune donnée réelle n'est touchée), puis écrit tous les exports dans
`docs/exemples/` : JSON + XLSX + ZIP + tables CSV + fiche descriptive + IIIF, en deux
périmètres — **corpus entier** ET une **collection de démo** (palier v14 : identité
renseignée, périmètre restreint au tome 1 ; fichiers `*-collection.*`).

    python tools/regenerer_exemples.py

But : les exemples versionnés reflètent l'état courant des exports (schéma, paradonnée,
inventaire `logiciels`…) et sont refabricables à l'identique, sans corpus réel.
Prérequis pour un jeu complet : openpyxl (XLSX) et spaCy + modèle (tokens NLP) — sinon
ces éléments sont simplement omis/vides (l'app dégrade proprement).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXEMPLES = REPO / "docs" / "exemples"
PY = sys.executable
BASE_URL_IIIF = "http://127.0.0.1:8000"      # base d'exemple (lecture seule, non servie)


def _run(env, *args):
    print("→", " ".join(Path(a).name if isinstance(a, Path) else str(a) for a in args))
    subprocess.run([PY, *(str(a) for a in args)], cwd=str(REPO), env=env, check=True)


def _run_capture(env, *args):
    """Comme `_run`, mais renvoie stdout (pour récupérer l'id d'une collection créée)."""
    print("→", " ".join(Path(a).name if isinstance(a, Path) else str(a) for a in args))
    return subprocess.run([PY, *(str(a) for a in args)], cwd=str(REPO), env=env,
                          check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    from _commun import forcer_utf8
    forcer_utf8()                             # Windows : stdout en UTF-8 (le « → » de _run sinon)
    EXEMPLES.mkdir(parents=True, exist_ok=True)
    # Repartir propre pour les dossiers ENTIÈREMENT générés (évite les fichiers périmés).
    for sous in ("tables-demo", "iiif", "iiif-collection"):
        shutil.rmtree(EXEMPLES / sous, ignore_errors=True)

    tmp = Path(tempfile.mkdtemp(prefix="bd_exemples_"))
    env = {**os.environ, "BD_DATA_DIR": str(tmp), "BD_DB_PATH": str(tmp / "demo.sqlite")}
    meta = REPO / "tools" / "metadonnees_collection.py"
    desc = REPO / "tools" / "description_collection.py"
    gerer = REPO / "tools" / "gerer_collections.py"
    iiif = REPO / "tools" / "iiif_manifest.py"
    try:
        _run(env, REPO / "tools" / "semer_demo.py")
        # Exports « corpus entier » (collection implicite).
        _run(env, meta, "--json", EXEMPLES / "metadonnees-demo.json")
        _run(env, meta, "--xlsx", EXEMPLES / "metadonnees-demo.xlsx")
        _run(env, meta, "--zip", EXEMPLES / "metadonnees-demo.zip")
        _run(env, meta, "--csv-dir", EXEMPLES / "tables-demo")
        _run(env, desc, "--csv", EXEMPLES / "description-collection-demo.csv")
        _run(env, iiif, "--base-url", BASE_URL_IIIF, "--out-dir", EXEMPLES / "iiif")

        # Collection de démonstration (palier v14) : le tome 1 seul → exemples SCOPÉS
        # (identité renseignée, périmètre restreint). L'id est 1 sur base fraîche, mais on
        # le récupère par sûreté. semer_demo crée les albums 1 (tome 1) et 2 (tome 2).
        cid = _run_capture(env, gerer, "creer", "--nom", "Les Explorateurs — sélection de démo",
                           "--description", "Sélection de démonstration : le tome 1 seul.",
                           "--licence", "CC-BY-4.0", "--statut", "public",
                           "--base-legale", "Exemple — à établir au dépôt",
                           "--responsable", "A. Démo;chercheur;0000-0002-1825-0097",
                           "--date-debut", "2019", "--albums", "1")
        _run(env, meta, "--json", EXEMPLES / "metadonnees-demo-collection.json", "--collection", cid)
        _run(env, desc, "--json", EXEMPLES / "description-collection-demo.json", "--collection", cid)
        _run(env, iiif, "--base-url", BASE_URL_IIIF,
             "--out-dir", EXEMPLES / "iiif-collection", "--collection", cid)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nExemples régénérés dans {EXEMPLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
