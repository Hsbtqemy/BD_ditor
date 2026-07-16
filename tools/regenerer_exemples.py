"""(Re)génère TOUT le jeu d'exemples de `docs/exemples/` de façon reproductible.

Sème un corpus de démonstration (tools/semer_demo.py) dans une base JETABLE (dossier
temporaire — aucune donnée réelle n'est touchée), puis écrit tous les exports dans
`docs/exemples/` : JSON + XLSX + ZIP + tables CSV + fiche descriptive + IIIF.

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


def main() -> int:
    EXEMPLES.mkdir(parents=True, exist_ok=True)
    # Repartir propre pour les dossiers ENTIÈREMENT générés (évite les fichiers périmés).
    for sous in ("tables-demo", "iiif"):
        shutil.rmtree(EXEMPLES / sous, ignore_errors=True)

    tmp = Path(tempfile.mkdtemp(prefix="bd_exemples_"))
    env = {**os.environ, "BD_DATA_DIR": str(tmp), "BD_DB_PATH": str(tmp / "demo.sqlite")}
    meta = REPO / "tools" / "metadonnees_collection.py"
    try:
        _run(env, REPO / "tools" / "semer_demo.py")
        _run(env, meta, "--json", EXEMPLES / "metadonnees-demo.json")
        _run(env, meta, "--xlsx", EXEMPLES / "metadonnees-demo.xlsx")
        _run(env, meta, "--zip", EXEMPLES / "metadonnees-demo.zip")
        _run(env, meta, "--csv-dir", EXEMPLES / "tables-demo")
        _run(env, REPO / "tools" / "description_collection.py",
             "--csv", EXEMPLES / "description-collection-demo.csv")
        _run(env, REPO / "tools" / "iiif_manifest.py",
             "--base-url", BASE_URL_IIIF, "--out-dir", EXEMPLES / "iiif")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nExemples régénérés dans {EXEMPLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
