"""INFRA-10 — la veille qui déploie `main` toute seule, et les cas où elle REFUSE.

Le déploiement se tire, il ne se pousse pas : aucune clé de production n'est confiée à
GitHub. Ce qui reste à prouver, c'est la DÉCISION — car une veille qui se trompe de sens
déploie ce qu'il ne fallait pas, ou ne déploie plus rien en silence.

Le harnais monte deux vrais dépôts git (un amont, un clone) plutôt que de simuler git :
la décision repose entièrement sur `merge-base --is-ancestor` et sur `git show`, et une
doublure de git ne prouverait que la doublure.

**Et il éprouve le PASSAGE DE MAIN, pas seulement la décision.** Un `deployer.sh` factice
dépose un témoin ; sans cette moitié, le test resterait vert si la veille décidait
parfaitement puis n'appelait personne.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
VEILLE = RACINE / "deploy" / "veille-deploiement.sh"

if not VEILLE.exists():
    pytest.skip(
        "deploy/ est exclu du contexte de build (.dockerignore) : ce module ne tourne QUE "
        "sur la machine de développement. Son skip dans l'image N'EST PAS une couverture "
        "— cf. QA-6, « un skip se lit comme un succès »", allow_module_level=True)
# Le CHEMIN et non le nom : sur Windows, `subprocess` passe par `CreateProcess`, qui
# cherche dans System32 AVANT le PATH — « bash » y résout le lanceur WSL, lequel échoue
# par `execvpe /bin/bash failed`. `shutil.which` suit le PATH et rend celui de Git.
BASH = shutil.which("bash")
if BASH is None:
    pytest.skip("bash absent", allow_module_level=True)


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=True)


def _commiter(depot, contenu_schema, message):
    # Le fichier de note porte le message : sans lui, deux commits au même
    # `SCHEMA_VERSION` n'auraient RIEN à commiter et `git commit` sortirait en 1. Le
    # décor doit vraiment changer d'état, sinon il ne monte pas le cas qu'on croit.
    (depot / "note.txt").write_text(message, encoding="utf-8")
    (depot / "database.py").write_text(contenu_schema, encoding="utf-8")
    _git(depot, "add", "-A")
    _git(depot, "-c", "user.email=t@t.invalid", "-c", "user.name=T",
         "commit", "-q", "-m", message)


V25 = "# en-tête\nSCHEMA_VERSION = 25\n"
V26 = "# en-tête\nSCHEMA_VERSION = 26\n"
SANS = "# ce fichier ne déclare plus sa version\n"


@pytest.fixture
def instance(tmp_path):
    """Un amont et un clone qui le suit, plus un `deployer.sh` factice qui laisse un témoin."""
    amont = tmp_path / "amont"
    amont.mkdir()
    _git(amont, "init", "-q")
    _git(amont, "symbolic-ref", "HEAD", "refs/heads/main")
    _commiter(amont, V25, "socle")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(amont), "clone")

    (clone / "deploy").mkdir(exist_ok=True)
    shutil.copy(VEILLE, clone / "deploy" / "veille-deploiement.sh")
    (clone / "deploy" / ".env").write_text("BD_DOMAINE=exemple\n", encoding="utf-8")

    etat = tmp_path / "etat"
    temoin = clone / "deployer-appele"
    faux = clone / "deploy" / "deployer.sh"
    faux.write_text(f'#!/usr/bin/env bash\necho "deployer factice" > "{temoin.as_posix()}"\n',
                    encoding="utf-8")
    os.chmod(faux, 0o755)
    return {"amont": amont, "clone": clone, "temoin": temoin, "etat": etat,
            "faux": faux}


def _veiller(instance, *args):
    r = subprocess.run(
        [BASH, "deploy/veille-deploiement.sh", *args],
        cwd=str(instance["clone"]), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        # L'état vit HORS du clone ; on le déroute pour ne pas écrire dans le vrai
        # ~/.local/state en jouant les tests.
        env={**os.environ, "BD_VEILLE_ETAT": str(instance["etat"])})
    return r.returncode, r.stdout + r.stderr


# --------------------------------------------------------------------------- #
# Ce qu'elle laisse passer
# --------------------------------------------------------------------------- #
def test_rien_a_faire_quand_main_n_a_pas_bouge(instance):
    code, sortie = _veiller(instance)
    assert code == 0, sortie
    assert "rien à faire" in sortie, sortie
    assert not instance["temoin"].exists(), (
        "la veille a appelé le déploiement alors que main n'avait pas bougé")


def test_une_mise_a_jour_ordinaire_passe_la_main(instance):
    """Le cœur du mécanisme, et la moitié qu'un test de décision seul manquerait."""
    _commiter(instance["amont"], V25, "un correctif sans migration")
    code, sortie = _veiller(instance)
    assert code == 0, sortie
    assert "schéma inchangé (v25)" in sortie, sortie
    assert instance["temoin"].exists(), (
        f"la veille a décidé de déployer mais n'a appelé personne :\n{sortie}")


def test_la_simulation_decide_sans_deployer(instance):
    _commiter(instance["amont"], V25, "un correctif sans migration")
    code, sortie = _veiller(instance, "--simulation")
    assert code == 0, sortie
    assert "SIMULATION" in sortie, sortie
    assert not instance["temoin"].exists(), "la simulation a déployé pour de vrai"


# --------------------------------------------------------------------------- #
# Ce qu'elle refuse — et un refus qui déploierait quand même serait le pire des deux
# --------------------------------------------------------------------------- #
def test_une_migration_de_schema_est_refusee(instance):
    """La seule règle que cette veille ajoute à `deployer.sh`."""
    _commiter(instance["amont"], V26, "v26 : une table de plus")
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert "v25 -> v26" in sortie, sortie
    assert not instance["temoin"].exists(), (
        "une migration a été déployée sans intervention humaine — c'est exactement ce que "
        "cette veille existe pour empêcher")


def test_un_schema_illisible_ferme_la_porte(instance):
    """Fermeture par défaut : « je ne sais pas » ne doit pas se comporter comme « non »."""
    _commiter(instance["amont"], SANS, "database.py sans version")
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert "illisible" in sortie, sortie
    assert not instance["temoin"].exists()


def test_main_en_arriere_est_refuse(instance):
    """Reculer n'est pas déployer : la base a peut-être migré depuis."""
    _commiter(instance["clone"], V25, "commit local, le clone prend de l'avance")
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert "ARRIÈRE" in sortie, sortie
    assert not instance["temoin"].exists()


def test_une_divergence_est_refusee_avant_le_pull(instance):
    """`deployer.sh` tire en --ff-only et échouerait ; un échec répété toutes les cinq
    minutes ne s'explique pas tout seul, donc on le nomme avant."""
    _commiter(instance["amont"], V25, "côté amont")
    _commiter(instance["clone"], V25, "côté clone")
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert "DIVERGÉ" in sortie, sortie
    assert not instance["temoin"].exists()


def test_la_veille_ne_deploie_que_depuis_main(instance):
    """Sur une machine restée par accident sur une autre branche, « suivre l'amont »
    déploierait du travail en cours."""
    _git(instance["clone"], "checkout", "-q", "-b", "dev")
    _commiter(instance["amont"], V25, "amont avance")
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert "'dev'" in sortie, sortie
    assert not instance["temoin"].exists()


def test_hors_de_l_instance_elle_refuse(instance):
    """`deploy/.env` absent = ce n'est pas la machine déployée."""
    (instance["clone"] / "deploy" / ".env").unlink()
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert ".env" in sortie, sortie


# --------------------------------------------------------------------------- #
# Le témoin d'échec — sans lui, le signal ne survivait pas cinq minutes
# --------------------------------------------------------------------------- #
def _casser_le_deployeur(instance):
    instance["faux"].write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")


def test_un_deploiement_echoue_laisse_un_temoin(instance):
    _casser_le_deployeur(instance)
    _commiter(instance["amont"], V25, "une mise à jour qui va mal tourner")
    code, sortie = _veiller(instance)
    assert code == 1, sortie
    assert "ÉCHOUÉ" in sortie, sortie
    pose = instance["etat"] / "echec"
    assert pose.exists(), f"aucun témoin posé après un déploiement raté :\n{sortie}"
    cible = subprocess.run(["git", "rev-parse", "origin/main"], cwd=str(instance["clone"]),
                           capture_output=True, text=True).stdout.strip()
    assert pose.read_text(encoding="utf-8").strip() == cible, (
        "le témoin ne nomme pas la CIBLE : il ne reconnaîtrait donc pas la tentative "
        "suivante, et `deployer.sh` peut échouer avant son pull comme après")


def test_le_temoin_survit_au_tir_suivant(instance):
    """La faille que ce témoin ferme, et je l'avais écrite avant de la voir.

    Un déploiement raté a déjà fait avancer `HEAD` — le `pull` précède tout le reste —,
    si bien que la veille concluait « rien à faire » au tir suivant, sortait en 0, et
    l'unité systemd repassait au vert. Un échec de trois heures du matin devenait
    invisible à trois heures cinq.
    """
    _casser_le_deployeur(instance)
    _commiter(instance["amont"], V25, "une mise à jour qui va mal tourner")
    assert _veiller(instance)[0] == 1
    code, sortie = _veiller(instance)            # le tir suivant, cible inchangée
    assert code == 1, f"le second tir a effacé le signal d'échec :\n{sortie}"
    assert "ÉCHOUÉ" in sortie, sortie


def test_un_commit_de_plus_sur_main_relance_la_veille(instance):
    """Une cible neuve est une tentative neuve : le témoin ne doit pas bloquer le correctif."""
    _casser_le_deployeur(instance)
    _commiter(instance["amont"], V25, "la mise à jour qui casse")
    assert _veiller(instance)[0] == 1

    instance["faux"].write_text(
        '#!/usr/bin/env bash\necho ok > "' + instance["temoin"].as_posix() + '"\n',
        encoding="utf-8")
    _commiter(instance["amont"], V25, "le correctif")
    code, sortie = _veiller(instance)
    assert code == 0, sortie
    assert instance["temoin"].exists(), "le témoin d'échec a bloqué un correctif"
    assert not (instance["etat"] / "echec").exists(), (
        "le témoin survit à un déploiement réussi — il refuserait tout, ensuite")
