"""Chaque vraie base de `tests/bases/` se refait : le commit qu'elle cite est dans le dépôt.

La règle de Hugo (2026-10-16, `CLAUDE.md` § Schéma & migrations) veut qu'une migration se
vérifie sur une base faite par le code de la version précédente, et chaque fichier
`v<N>-<commit>.sql` dit comment le refaire : `tools/fabriquer_base_de_version.py <commit>`.
La base v36 citait `b9183c0`, la tête d'une copie d'intégration qui n'est jamais entrée dans
le dépôt (vu le 2026-11-05, refaite le 2026-11-14 depuis `53d258e`) : la commande écrite dans
son en-tête ne menait nulle part, et rien ne le disait.

Le test lit le commit dans le NOM du fichier et dans la commande de son en-tête, et exige
qu'ils disent le même et qu'il existe. Hors d'un dépôt git (l'image de test n'en porte pas),
il n'a rien à mesurer et se met de côté.
"""
import re
import subprocess
from pathlib import Path

import pytest

DEPOT = Path(__file__).resolve().parent.parent
BASES = sorted((DEPOT / "tests" / "bases").glob("v*.sql"))
NOM = re.compile(r"^v(\d+)-([0-9a-f]{7,40})\.sql$")
COMMANDE = re.compile(r"fabriquer_base_de_version\.py ([0-9a-f]{7,40}) (\S+\.sql)")


def _git(*args):
    return subprocess.run(["git", *args], cwd=DEPOT, capture_output=True, text=True)


def _dans_un_depot():
    try:
        return _git("rev-parse", "--git-dir").returncode == 0
    except OSError:
        return False


def test_il_y_a_des_bases_a_mesurer():
    # Une garde qui ne trouverait aucun fichier approuverait tout.
    assert len(BASES) >= 10, [b.name for b in BASES]


@pytest.mark.parametrize("base", BASES, ids=lambda b: b.name)
def test_le_nom_et_l_en_tete_citent_le_meme_commit(base):
    m = NOM.match(base.name)
    assert m, f"{base.name} : le nom n'a pas la forme v<version>-<commit>.sql"
    tete = "".join(base.open(encoding="utf-8").readlines()[:5])
    c = COMMANDE.search(tete)
    assert c, f"{base.name} : l'en-tête ne dit pas la commande qui la refait"
    assert c.group(1) == m.group(2), f"{base.name} : l'en-tête cite {c.group(1)}"
    assert c.group(2) == f"tests/bases/{base.name}", f"{base.name} : la commande écrit {c.group(2)}"


@pytest.mark.skipif(not _dans_un_depot(), reason="hors d'un dépôt git, aucun commit à chercher")
@pytest.mark.parametrize("base", BASES, ids=lambda b: b.name)
def test_le_commit_cite_est_dans_le_depot(base):
    commit = NOM.match(base.name).group(2)
    r = _git("cat-file", "-e", f"{commit}^{{commit}}")
    assert r.returncode == 0, (
        f"{base.name} : le commit {commit} n'est pas dans le dépôt — la base ne se refait plus ; "
        "refaites-la depuis le dernier état de sa version qui y est "
        "(`tools/fabriquer_base_de_version.py <commit> tests/bases/v<N>-<commit>.sql`)"
    )
