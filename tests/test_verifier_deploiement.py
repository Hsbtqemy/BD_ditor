"""INFRA-12 — le contrôle de déploiement doit distinguer « non » de « je n'ai pas pu demander ».

Ce module existe à cause d'une sortie lue le 2026-09-07 sur l'instance :

    !! `compose exec` a échoué : no configuration file provided: not found
    ÉCHEC — moteur(s) absents ou cassés : compose exec
        Le NLP est le plus coûteux et le plus SILENCIEUX : sans lui, l'Exploration,
        la relecture (ANN-4) et les deux rapports d'accord sortent vides…

Les quatre moteurs allaient parfaitement — le déploiement venait de les vérifier trois
minutes plus tôt. Le contrôle avait simplement été lancé depuis la racine du dépôt, où
`docker compose` ne trouve pas son fichier. Il n'a donc rien pu DEMANDER, et il a rendu
son incapacité dans les termes exacts d'une mesure : « absents ou cassés », avec
l'avertissement qui envoie chercher un NLP manquant.

**Le script séparait DÉJÀ ces deux états, et pour les chemins HTTP il le fait très bien :**
« refusé » d'un côté, « on ne SAIT RIEN » de l'autre, avec la phrase qui compte — *une
instance éteinte, une URL fautive ou un proxy qui répond à sa place donnent tous ce
résultat, ne pas le lire comme une protection*. Il ne l'appliquait pas à sa propre sonde.
La leçon était écrite dans le fichier, une fonction plus haut.

Ces tests bornent le contrat : `controle_interne` rend `(manques, empechement)`, et rien
de ce qui empêche de mesurer n'a le droit d'entrer dans `manques`.
"""
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SCRIPT = RACINE / "deploy" / "verifier_deploiement.py"

if not SCRIPT.exists():
    pytest.skip(
        "deploy/ est exclu du contexte de build (.dockerignore) : ce module ne tourne QUE "
        "sur la machine de développement. Son skip dans l'image N'EST PAS une couverture "
        "— cf. QA-6, « un skip se lit comme un succès »", allow_module_level=True)

sys.path.insert(0, str(RACINE / "deploy"))
import verifier_deploiement  # noqa: E402


class _Reponse:
    """Ce que rend `subprocess.run`, réduit à ce que la fonction en lit."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _sonde(monkeypatch, reponse):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: reponse)


# Le rapport que rend la sonde quand tout va bien. Les clés PROFONDES sont celles que
# `controle_interne` va chercher ; les recopier ici fige le contrat entre les deux.
_RAPPORT_SAIN = (
    '{"kumiko": true, "bulles": true, "ocr": true, "lemmes": true,'
    ' "profond": {"kumiko": {"ok": true}, "bulles": {"ok": true},'
    ' "ocr": {"ok": true}, "nlp": {"ok": true}}}')


def test_une_sonde_impossible_ne_declare_AUCUN_moteur_en_panne(monkeypatch):
    """La panne du 2026-09-07, rejouée : `compose exec` refuse, les moteurs vont bien.

    C'est LE test de ce module. Tant que `manques` reste vide, le bilan ne peut pas
    prononcer « absents ou cassés » — et l'exploitant n'ira pas chercher une panne
    d'instance là où c'est l'invocation du contrôle qui a échoué.
    """
    _sonde(monkeypatch, _Reponse(returncode=1, stderr="no configuration file provided: not found"))

    manques, empechement = verifier_deploiement.controle_interne("app")

    assert manques == [], (
        "une sonde qu'on n'a PAS PU poser a été comptée comme un moteur en panne : "
        f"{manques}. C'est un diagnostic non mesuré, rendu dans les termes d'un "
        "diagnostic mesuré")
    assert empechement, "l'empêchement doit être RAPPORTÉ, pas avalé : sans lui, le bilan conclurait que tout va bien"


def test_l_empechement_nomme_la_cause_qu_on_peut_reparer(monkeypatch):
    """« no configuration file » a une cause unique et une réparation d'une ligne.

    Le message d'erreur de Docker ne la donne pas : il dit ce qui manque, pas pourquoi.
    Or la raison est toujours la même — le script se lance depuis `deploy/`. La nommer
    ici épargne la recherche, et c'est le seul endroit qui SAIT que c'est cela.
    """
    _sonde(monkeypatch, _Reponse(returncode=1, stderr="no configuration file provided: not found"))

    _, empechement = verifier_deploiement.controle_interne("app")

    assert "deploy/" in empechement, (
        f"l'empêchement doit dire d'où se lance le script : {empechement!r}")


def test_une_reponse_illisible_est_un_empechement_pas_une_panne(monkeypatch):
    """Même famille : on a pu lancer la sonde, on n'a pas pu la LIRE.

    Un rapport tronqué, un JSON coupé, une ligne de bruit avant la réponse — rien de tout
    cela ne dit quoi que ce soit sur les moteurs, et le compter comme une panne ferait
    passer un défaut de tuyau pour un défaut d'instance.
    """
    _sonde(monkeypatch, _Reponse(returncode=0, stdout="Traceback (most recent call last):"))

    manques, empechement = verifier_deploiement.controle_interne("app")

    assert manques == [] and empechement


def test_docker_absent_est_un_empechement(monkeypatch):
    """Lancer le contrôle depuis un poste de développement n'apprend rien sur l'instance."""
    def _boum(*a, **k):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", _boum)

    manques, empechement = verifier_deploiement.controle_interne("app")

    assert manques == [] and "docker" in empechement.lower()


def test_une_sonde_qui_REPOND_non_remplit_bien_manques(monkeypatch):
    """Le sens inverse, et il vaut autant.

    Une garde éprouvée dans un seul sens ne prouve rien : à force de ne jamais rien
    déclarer en panne, `controle_interne` deviendrait un test qui passe toujours. Ici la
    sonde répond, et elle répond NON sur le NLP — `manques` doit le porter, et
    `empechement` doit rester vide.
    """
    rapport = _RAPPORT_SAIN.replace(
        '"nlp": {"ok": true}', '"nlp": {"ok": false, "erreur": "modèle introuvable"}')
    _sonde(monkeypatch, _Reponse(returncode=0, stdout=rapport))

    manques, empechement = verifier_deploiement.controle_interne("app")

    assert empechement is None, "on a mesuré : ce n'est pas un empêchement"
    assert manques, "un moteur qui répond NON doit être déclaré en panne"


def test_une_sonde_saine_ne_declare_rien(monkeypatch):
    """Et le cas nominal, sans quoi les cinq précédents pourraient tous passer à vide."""
    _sonde(monkeypatch, _Reponse(returncode=0, stdout=_RAPPORT_SAIN))

    manques, empechement = verifier_deploiement.controle_interne("app")

    assert (manques, empechement) == ([], None)
