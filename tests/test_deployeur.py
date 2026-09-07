"""INFRA-10 — `deployer.sh` décide de redémarrer Authelia, et depuis QUELLE référence.

Authelia lit sa configuration au démarrage du PROCESSUS : un fichier remplacé sur le
disque ne change rien à ce que l'instance applique. `deployer.sh` doit donc redémarrer le
service quand `deploy/authelia/` a bougé — et la question est de savoir bougé DEPUIS QUOI.

Le script a longtemps répondu « depuis l'état d'avant mon pull ». C'est l'indicateur pris
pour la chose : son étape 2 bis établit dix lignes plus haut que le dépôt et l'image
divergent, et cette divergence est même sa panne fondatrice (2026-09-06, dépôt à jour,
conteneur de l'avant-veille). Quand le pull ne ramène rien — quelqu'un a tiré à la main,
ou le déploiement précédent a échoué après le pull — la comparaison ne voit RIEN et
Authelia continue de servir une politique d'accès périmée, en silence. La correction
compare depuis `bd.commit`, le commit que l'image PORTE.

Ce module éprouve le script RÉEL, dans `--simulation` : il y prend sa décision et
l'annonce sans rien redémarrer. Le décor est un vrai dépôt git — la décision repose
entièrement sur `git diff`, et une doublure de git ne prouverait que la doublure — plus un
`docker` factice, parce que c'est la seule dépendance qu'on ne peut pas monter ici.

**Le cas 1 est la mesure, les trois autres sont les bords.** Rejoué sur la version d'avant
la correction, le cas 1 annonce « configuration inchangée » : le test échoue des deux
côtés de la coupe, ce qui est la seule chose qui prouve qu'il regarde quelque chose.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DEPLOYEUR = RACINE / "deploy" / "deployer.sh"

if not DEPLOYEUR.exists():
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


# `docker` factice. Il ne simule que ce que le script lui demande AVANT la décision qui
# nous intéresse ; tout le reste passe par `faire`, donc n'est pas exécuté en simulation.
#
# `DockerRootDir` rend `/` et non un chemin plausible comme `/var/lib/docker` : le script
# enchaîne `df -Ph "$racine_docker" | awk …` sous `set -o pipefail`, si bien qu'un chemin
# INEXISTANT y fait échouer le pipeline, donc l'affectation, donc le script — sans un mot.
DOCKER_FACTICE = """#!/usr/bin/env bash
case "$1 $2" in
  "info --format")    echo "/" ;;
  "compose version")  echo "Docker Compose version v2.29.0" ;;
  "compose config")   cat "$STUB_CONFIG" ;;
  "compose ps")       echo "$STUB_CID" ;;
  "inspect --format") echo "$STUB_LABEL" ;;
  *) echo "docker factice : $*" ;;
esac
"""

# Ce que `docker compose config` doit rendre pour que les deux gardes de l'étape 2
# passent : l'override présent (reconnu à un chemin de volume) et le port publié sur la
# boucle locale (forme LONGUE, celle des Compose récents).
CONFIG_RESOLUE = """services:
  caddy:
    volumes:
      - /srv/deploy/Caddyfile.derriere-proxy:/etc/caddy/Caddyfile
    ports:
      - host_ip: 127.0.0.1
        published: "8080"
        target: 80
"""


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=True)


def _commiter(depot, message):
    _git(depot, "add", "-A")
    _git(depot, "-c", "user.email=t@t.invalid", "-c", "user.name=T",
         "commit", "-q", "-m", message)
    return _git(depot, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def instance(tmp_path):
    """Un vrai dépôt portant le script réel, et de quoi lui donner un `docker`.

    Rend `(depot, lancer)` où `lancer(servi=…)` joue `deployer.sh --simulation` en
    faisant croire que l'image en service porte le commit `servi`.
    """
    outils = tmp_path / "bin"
    outils.mkdir()
    (outils / "docker").write_text(DOCKER_FACTICE, encoding="utf-8")
    os.chmod(outils / "docker", 0o755)
    config = tmp_path / "config.yml"
    config.write_text(CONFIG_RESOLUE, encoding="utf-8")

    depot = tmp_path / "depot"
    (depot / "deploy" / "authelia").mkdir(parents=True)
    _git(depot, "init", "-q")
    _git(depot, "symbolic-ref", "HEAD", "refs/heads/main")

    shutil.copy(DEPLOYEUR, depot / "deploy" / "deployer.sh")
    (depot / "deploy" / ".env").write_text("BD_DOMAINE=exemple\n", encoding="utf-8")
    (depot / "deploy" / "authelia" / "configuration.yml").write_text(
        "access_control:\n  default_policy: deny\n", encoding="utf-8")
    (depot / "deploy" / "authelia" / "users_database.example.yml").write_text(
        "users: {}\n", encoding="utf-8")
    (depot / "README.md").write_text("socle\n", encoding="utf-8")
    _commiter(depot, "socle")

    def lancer(servi):
        # Le PATH se compose DANS bash : sur Windows un chemin `C:/…` porte un
        # deux-points, qui est le séparateur de PATH — préfixer depuis Python couperait
        # le chemin en deux entrées inexistantes, et le vrai `docker` répondrait.
        preambule = ('p="$1"; command -v cygpath >/dev/null 2>&1 && p="$(cygpath -u "$p")"; '
                     'PATH="$p:$PATH"; shift; exec bash "$@"')
        env = {**os.environ, "STUB_CONFIG": str(config),
               "STUB_CID": "c0ffee", "STUB_LABEL": servi}
        return subprocess.run(
            [BASH, "-c", preambule, "_", str(outils),
             "deploy/deployer.sh", "--simulation"],
            cwd=str(depot), env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace")

    return depot, lancer


def _authelia(res):
    """La seule ligne qui nous intéresse, et l'exigence qu'il y en ait EXACTEMENT une."""
    assert res.returncode == 0, f"le script a refusé :\n{res.stdout}\n{res.stderr}"
    lignes = [l.strip() for l in res.stdout.splitlines() if "authelia " in l]
    assert len(lignes) == 1, f"attendu une décision Authelia, vu {lignes}\n{res.stdout}"
    return lignes[0]


def test_une_configuration_tiree_mais_jamais_deployee_redemarre(instance):
    """LE cas. Le pull ne ramène rien, et pourtant l'instance sert une politique périmée.

    C'est l'état du 2026-09-06 : le dépôt est à jour parce que quelqu'un a tiré à la
    main, l'image date d'avant. `$avant` égale `$apres`, donc une comparaison fondée sur
    le pull ne voit rien — et c'est précisément là qu'il y a tout à voir.
    """
    depot, lancer = instance
    servi = _git(depot, "rev-parse", "HEAD").stdout.strip()
    (depot / "deploy" / "authelia" / "configuration.yml").write_text(
        "access_control:\n  default_policy: one_factor\n", encoding="utf-8")
    _commiter(depot, "durcissement de la politique d'accès")

    ligne = _authelia(lancer(servi))
    assert "MODIFIÉE" in ligne, (
        "la politique d'accès a changé depuis le commit que sert l'image, et le script "
        f"ne redémarre pas Authelia : {ligne!r}. C'est la panne de sept heures d'INFRA-9, "
        "rejouée à l'intérieur de sa propre correction.")
    assert servi[:7] in ligne, (
        f"le message doit NOMMER la référence employée, pour qu'un journal de "
        f"déploiement relu après incident dise depuis quoi il a comparé : {ligne!r}")


def test_un_changement_hors_authelia_ne_redemarre_pas(instance):
    """Le bord opposé : redémarrer à chaque déploiement rendrait la décision inutile."""
    depot, lancer = instance
    servi = _git(depot, "rev-parse", "HEAD").stdout.strip()
    (depot / "README.md").write_text("autre chose\n", encoding="utf-8")
    _commiter(depot, "documentation")

    ligne = _authelia(lancer(servi))
    assert "inchangée" in ligne, ligne


def test_un_gabarit_ne_redemarre_pas(instance):
    """La leçon du 2026-09-07, gardée : un `.example.` n'est jamais monté, ni lu.

    Une correction de `users_database.example.yml` avait redémarré le portail, et le
    contrôle qui suivait avait trouvé `/` en 502 — un `health: starting`. Une correction
    de documentation produisait donc une micro-coupure ET un faux échec de déploiement.
    """
    depot, lancer = instance
    servi = _git(depot, "rev-parse", "HEAD").stdout.strip()
    (depot / "deploy" / "authelia" / "users_database.example.yml").write_text(
        "users:\n  exemple: {}\n", encoding="utf-8")
    _commiter(depot, "gabarit de comptes")

    ligne = _authelia(lancer(servi))
    assert "inchangée" in ligne, ligne


def test_une_image_sans_etiquette_redemarre_en_le_disant(instance):
    """« Je n'ai pas pu comparer » n'est pas « rien n'a changé », et se dit autrement.

    Ce troisième état est NEUF : la correction l'introduit. L'ancienne écriture comparait
    deux `git rev-parse HEAD`, toujours valides, et ne pouvait donc pas le rencontrer —
    d'où son échec ici sur le mauvais message, « inchangée », qui est le pire des trois.

    L'acte attendu est le redémarrage, puisqu'on ne sait pas ; ce que ce test garde, c'est
    que le journal du déploiement n'AFFIRME pas au passage une modification que personne
    n'a constatée. C'est ce journal qu'on relit après un incident.
    """
    depot, lancer = instance
    (depot / "deploy" / "authelia" / "configuration.yml").write_text(
        "access_control:\n  default_policy: two_factor\n", encoding="utf-8")
    _commiter(depot, "politique")

    ligne = _authelia(lancer(""))          # image d'avant `LABEL bd.commit`
    assert "impossible" in ligne, (
        f"sans étiquette, le script doit dire qu'il n'a pas pu comparer : {ligne!r}")
    assert "MODIFIÉE" not in ligne, (
        f"rien n'a été constaté, donc rien ne doit être affirmé : {ligne!r}")
