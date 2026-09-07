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
    # `encoding` EXPLICITE, et non le défaut de la plateforme : Node écrit ses rapports en
    # UTF-8, quand `text=True` décode avec `locale.getpreferredencoding()` — cp1252 sur une
    # machine Windows française. Un nom de test accentué levait donc un UnicodeDecodeError
    # DANS LE FIL DE LECTURE de subprocess, ce qui laissait `proc.stdout` à None. Le test
    # continuait de mesurer juste (il lit le CODE DE RETOUR, que rien n'abîme), mais la
    # ligne ci-dessous aurait planté sur un `None` au lieu de dire POURQUOI les tests JS
    # échouent — le diagnostic cassait exactement le jour où il sert. `errors="replace"`
    # parce qu'un rapport illisible vaut toujours mieux qu'une exception à sa place.
    proc = subprocess.run(
        ["node", "--test", *[str(p) for p in JS_TESTS]],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, "tests JS en échec :\n" + proc.stdout + proc.stderr
