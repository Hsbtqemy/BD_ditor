"""Pont pytest → tests unitaires JS (node --test).

Permet de lancer la logique front pure (static/lib/*.js) avec la MÊME commande que
le reste (`python -m pytest`). Skippé proprement si Node n'est pas installé. Les
fichiers de test sont découverts côté Python et passés explicitement à Node (robuste
quelle que soit la gestion des dossiers/globs de la version de Node).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JS_TESTS = sorted((REPO_ROOT / "tests" / "js").glob("*.test.js"))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js non installé")
def test_js_unit_suite():
    assert JS_TESTS, "aucun fichier tests/js/*.test.js trouvé"
    proc = subprocess.run(
        ["node", "--test", *[str(p) for p in JS_TESTS]],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, "tests JS en échec :\n" + proc.stdout + proc.stderr
