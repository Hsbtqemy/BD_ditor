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


# --------------------------------------------------------------------------- #
# AUTH-6 — la lecture de l'annuaire par l'application
# --------------------------------------------------------------------------- #
# Le banc de `controle_config` vit dans `test_regressions.py` (fichiers non suivis et Compose
# substitués) : on l'emprunte au lieu de le recopier, une copie divergerait en silence.
from test_regressions import _DOMAINES, _UN_COMPTE, _controle  # noqa: E402


def test_une_doublure_d_annuaire_refuse_le_deploiement(tmp_path, monkeypatch):
    """En production, la vue des comptes afficherait un annuaire INVENTÉ, avec ses signaux :
    une information fausse, donc bloquante. Une vraie adresse passe."""
    env = tmp_path / ".env"
    env.write_text(_DOMAINES + "BD_ANNUAIRE_ADRESSE=doublure:\n", encoding="utf-8")
    problemes, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "annuaire en doublure" in problemes, sortie

    env.write_text(_DOMAINES + "BD_ANNUAIRE_ADRESSE=http://lldap:17170\n", encoding="utf-8")
    problemes, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "annuaire en doublure" not in problemes, sortie


def test_un_annuaire_sans_url_web_se_signale_sans_bloquer(tmp_path, monkeypatch):
    """Le lien « Modifier ↗ » ne se dérive pas du domaine : sans `BD_ANNUAIRE_URL`, la vue n'a
    aucun lien à offrir. C'est un confort manquant, pas une panne : aucun problème compté."""
    env = tmp_path / ".env"
    env.write_text(_DOMAINES + "ANNUAIRE_DOMAINE=annuaire.exemple.fr\n", encoding="utf-8")
    problemes, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "BD_ANNUAIRE_URL non posée" in sortie, sortie
    assert not [p for p in problemes if "BD_ANNUAIRE_URL" in p or "lien" in p], problemes

    env.write_text(_DOMAINES + "ANNUAIRE_DOMAINE=annuaire.exemple.fr\n"
                   "BD_ANNUAIRE_URL=https://annuaire.exemple.fr/\n", encoding="utf-8")
    problemes, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "BD_ANNUAIRE_URL non posée" not in sortie, sortie


def test_un_compte_de_service_que_la_regle_ne_refuse_pas_se_signale(tmp_path, monkeypatch):
    """AUTH-6 — le nom du compte de service vit dans `.env` ET dans la règle `deny` de
    `configuration.yml`, écrit en dur. Divergents, le compte réel redevient un identifiant de
    portail : signalé, sans bloquer (sa portée reste vide). Lu sur le VRAI fichier d'Authelia,
    pour que l'expression qui y cherche la règle suive sa forme réelle."""
    env = tmp_path / ".env"
    env.write_text(_DOMAINES + "BD_ANNUAIRE_COMPTE=bd-application\n", encoding="utf-8")
    problemes, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "ok compte service" in " ".join(sortie.split()), sortie
    assert "pourra donc" not in sortie, sortie

    env.write_text(_DOMAINES + "BD_ANNUAIRE_COMPTE=lecteur-annuaire\n", encoding="utf-8")
    problemes, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "BD_ANNUAIRE_COMPTE=lecteur-annuaire" in sortie and "pourra donc" in sortie, sortie
    assert "nomme : bd-application" in sortie, sortie
    assert not [p for p in problemes if "compte" in p and "service" in p], problemes

    # LLDAP range ses identifiants en minuscules (v0.6.3) : une majuscule dans `.env` désigne
    # le même compte, celui que la règle refuse.
    env.write_text(_DOMAINES + "BD_ANNUAIRE_COMPTE=BD-Application\n", encoding="utf-8")
    _, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "ok compte service" in " ".join(sortie.split()), sortie

    # Deux formes fabriquées, que le vrai fichier ne montre pas : nommé en tête mais par une
    # règle qui OUVRE, et un vrai refus mais placé APRÈS une autre règle.
    env.write_text(_DOMAINES + "BD_ANNUAIRE_COMPTE=bd-application\n", encoding="utf-8")
    ouvre = ("access_control:\n  rules:\n"
             "    - domain: 'bd.exemple.fr'\n      subject: 'user:bd-application'\n"
             "      policy: 'one_factor'\n")
    _, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE, configuration=ouvre)
    assert "pourra donc" in sortie and "nomme : aucun" in sortie, sortie

    apres = ("access_control:\n  rules:\n"
             "    # 1. une autre règle\n"
             "    - domain: '*.exemple.fr'\n      policy: 'one_factor'\n\n"
             "    - domain:\n        - 'bd.exemple.fr'\n      subject: 'user:bd-application'\n"
             "      policy: 'deny'\n"
             "session:\n  name: 'x'\n")
    _, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE, configuration=apres)
    assert "pourra donc" in sortie and "nomme : aucun" in sortie, sortie
    en_tete = ("access_control:\n  rules:\n"
               "    # 0. le refus\n"
               "    - domain:\n        - 'bd.exemple.fr'\n      subject: 'user:bd-application'\n"
               "      policy: 'deny'\n\n"
               "    # 1. une autre règle\n"
               "    - domain: '*.exemple.fr'\n      policy: 'one_factor'\n"
               "session:\n  name: 'x'\n")
    _, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE, configuration=en_tete)
    assert "ok compte service" in " ".join(sortie.split()), sortie


def test_le_compte_de_service_se_lit_dans_ce_que_compose_transmet(tmp_path, monkeypatch):
    """Comme les groupes admin : ce que Compose RÉSOUT prime sur la ligne de `.env`."""
    env = tmp_path / ".env"
    env.write_text(_DOMAINES + "BD_ANNUAIRE_COMPTE=bd-application\n", encoding="utf-8")
    resolu = {"BD_AUTH_ADMIN_GROUPS": "bd-admins", "BD_ANNUAIRE_COMPTE": "lecteur-annuaire"}
    _, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE, resolu=resolu)
    assert "BD_ANNUAIRE_COMPTE=lecteur-annuaire" in sortie and "pourra donc" in sortie, sortie


def test_sans_compte_de_service_rien_ne_se_dit(tmp_path, monkeypatch):
    """La lecture de l'annuaire n'est pas configurée : il n'y a rien à comparer."""
    env = tmp_path / ".env"
    env.write_text(_DOMAINES, encoding="utf-8")
    _, sortie = _controle(verifier_deploiement, env, monkeypatch, _UN_COMPTE)
    assert "compte service" not in sortie, sortie
