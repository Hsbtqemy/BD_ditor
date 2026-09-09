"""L'environnement qui MESURE est-il celui qui SERT ?  QA-5.

**La thèse de QA-5, prise au mot.** Le dépôt n'a eu d'artefact qu'à partir du 2026-08-27,
et toute sa culture de vérification s'était construite sous une hypothèse alors vraie :
ce qu'on teste EST ce qu'on exécute. Le premier build l'a rompue — 451 tests verts en
local, trois moteurs morts dans l'image. ARCH-2 a rejoué la même forme dans l'autre sens :
un `fastapi` local plus récent que celui de l'image avait rendu deux cliquets aveugles à
56 % des routes, et c'est le verrou qui a protégé la production.

**Mesuré le 2026-09-09** : 51 paquets communs portent une version différente entre ce
poste et l'image, dont `numpy` en **1.26 contre 2.4** — un saut de version MAJEURE sous
OpenCV, torch, scipy et scikit-image. La suite passe donc au vert sur numpy 1.x et livre
sur numpy 2.x.

**Ce test ne garde PAS les 51**, et ce n'est pas une reculade. Les paquets transitifs
flottent par construction : exiger leur égalité sur un poste de travail — ici un Python
partagé avec Django, Jupyter et le reste — serait une demande qu'on ne peut pas
satisfaire, et une garde impossible à satisfaire s'apprend à ne plus se lire. Il garde
les **17 épingles DÉLIBÉRÉES**, celles que le dépôt a décidées avec leur raison écrite :
là, un écart est actionnable en une commande.

Les écarts CONSTATÉS le sont dans `ECARTS_ADMIS`, avec leur date et ce qu'ils coûtent.
Déclarer n'est pas fermer — c'est empêcher que la liste grandisse sans que personne ne
l'ait voulu, et c'est le patron de `HORS_PERIMETRE` et de `BLOCAGES_ADMIS` ailleurs.
"""
import os
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import identite_pile  # noqa: E402

# Les écarts qu'on SAIT porter, chacun avec sa date et son coût. Les retirer d'ici se fait
# par `pip install -r requirements.lock -r requirements-dev.lock`, et la ligne disparaît.
#
# Ils ne sont pas anodins, et c'est pourquoi ils sont écrits plutôt que tolérés en
# silence : tant qu'ils tiennent, un défaut propre à ces versions-là ne peut pas être vu
# ici. Ce qui les rend supportables est que l'image, elle, EST vérifiée — la suite y
# tourne (QA-5) et les verrous y sont contrôlés (QA-4).
ECARTS_ADMIS = {
    "numpy": "2026-09-09 — local 1.26.2 contre 2.4.6 dans l'image, un saut de version "
             "MAJEURE. C'est le plus lourd des trois : numpy 2 change des règles de "
             "promotion de types et de copie sur lesquelles reposent OpenCV, torch, "
             "scipy et scikit-image. Non corrigé ici parce que ce Python est PARTAGÉ "
             "avec d'autres projets du poste, et qu'y imposer numpy 2 déborde de ce "
             "dépôt. La couverture réelle de ces chemins est celle de l'image.",
    "pillow": "2026-09-09 — local 12.1.0 contre 12.0.0. L'épingle à 12.0.0 vient de QA-4 "
              "et n'est pas cosmétique : `iiif-prezi3==3.1.1` exige `Pillow<=12.0.0`, "
              "et c'est ce qui a permis au test de conformance IIIF de cesser de se "
              "skipper dans l'image. Le venv local porte donc la version qui rendait ce "
              "test impossible — d'où, ci-dessous, son absence d'`iiif-prezi3`.",
    "requests": "2026-09-09 — local 2.31.0 contre 2.32.5. Le moins conséquent des trois ; "
                "il n'est ici que parce que le poste traîne une version ancienne, pas "
                "parce qu'une décision l'y retient.",
}

# Un paquet épinglé mais ABSENT ici. Ce n'est pas un écart de version, c'est une COUVERTURE
# qui manque : un test qui en dépend se SKIPPE, et un skip se lit comme un succès (QA-6).
ABSENCES_ADMISES = {
    "iiif-prezi3": "2026-09-09 — outil de test seulement, et son absence a une CAUSE "
                   "mesurée : il exige `Pillow<=12.0.0` quand ce poste porte 12.1.0. "
                   "`test_iiif_conformance_stricte` se skippe donc ici et ne tourne QUE "
                   "dans l'image, où QA-4 a vérifié qu'il PASSE. C'est le seul test du "
                   "dépôt dont la couverture repose entièrement sur l'artefact.",
}


@pytest.fixture(scope="module")
def presents():
    return identite_pile.installes()


def test_aucun_ecart_NON_DECLARE_sur_une_epingle_deliberee(presents):
    """Un écart nouveau sur une dépendance CHOISIE fait échouer la suite.

    « Choisie » veut dire : quelqu'un a écrit sa version et sa raison dans
    `requirements.lock` ou `requirements-dev.lock`, et `test_verrou_dependances` exige
    déjà que cette raison existe. Un venv qui la contredit mesure donc autre chose que ce
    que le dépôt a décidé de livrer — et c'est exactement le défaut d'ARCH-2, où la
    version LOCALE était la plus récente et la plus fausse.

    La réparation tient en une commande, ce qui est la condition pour qu'une garde soit
    tenable : `pip install -r requirements.lock -r requirements-dev.lock`.
    """
    ecarts = identite_pile.ecarts(identite_pile.pins_choisis(), presents)
    inattendus = {p: v for p, v in ecarts.items() if p not in ECARTS_ADMIS}
    assert not inattendus, (
        "l'environnement local contredit une épingle délibérée sans que ce soit "
        f"déclaré : {inattendus}. Réparer par `pip install -r requirements.lock "
        "-r requirements-dev.lock`, ou déclarer l'écart dans `ECARTS_ADMIS` avec sa date "
        "et ce qu'il coûte")


def test_aucune_absence_NON_DECLAREE_sur_une_epingle_deliberee(presents):
    """Un paquet épinglé qu'on n'a pas ne casse rien — il fait SKIPPER, ce qui est pire.

    Un échec se voit ; un skip se lit comme un succès. C'est la leçon de QA-6, et elle
    vaut ici sur une surface que rien ne surveillait : le dépôt peut gagner une
    dépendance de test sans que personne ne l'installe, et les tests qui en dépendent se
    tairont poliment.
    """
    manquants = identite_pile.absents(identite_pile.pins_choisis(), presents)
    inattendus = [p for p in manquants if p not in ABSENCES_ADMISES]
    assert not inattendus, (
        f"{inattendus} sont épinglés mais absents ici : les tests qui en dépendent se "
        f"SKIPPENT, et un skip se lit comme un succès. Installer, ou déclarer dans "
        f"`ABSENCES_ADMISES` avec ce que ça fait perdre")


@pytest.mark.skipif(os.environ.get("BD_IMAGE") == "1",
                    reason="dans l'image, l'écart est nul par construction : ces "
                           "déclarations décrivent un POSTE DE TRAVAIL, et les lire ici "
                           "reviendrait à les déclarer toutes périmées")
def test_les_declarations_ne_survivent_pas_a_leur_objet(presents):
    """**La garde de la garde.** Une déclaration qui ne décrit plus rien doit disparaître.

    **Sauté DANS L'IMAGE, et lui seul du module.** Il a échoué là-bas au premier essai, et
    c'était un défaut de conception de ma part : `ECARTS_ADMIS` décrit un poste de travail,
    or l'image porte exactement les versions des verrous — l'écart y est nul, donc toute
    déclaration y paraît périmée. Les deux tests précédents, eux, gardent quelque chose
    dans les DEUX environnements : que rien ne contredise une épingle délibérée.

    Sans ce test, `ECARTS_ADMIS` deviendrait un cimetière : on y ajoute au fil des
    incidents, on n'en retire jamais, et la liste finit par excuser d'avance des écarts
    qui n'existent plus — ou, pire, par en excuser un qui vient de RÉAPPARAÎTRE sous un
    nom déjà pardonné. C'est le mode d'échec des listes d'exception, et il ne se voit
    qu'en le cherchant.
    """
    ecarts = identite_pile.ecarts(identite_pile.pins_choisis(), presents)
    perimes = sorted(set(ECARTS_ADMIS) - set(ecarts))
    assert not perimes, (
        f"{perimes} sont déclarés dans `ECARTS_ADMIS` alors que l'environnement est "
        f"désormais conforme : retirer la ligne, elle ne décrit plus rien")

    manquants = set(identite_pile.absents(identite_pile.pins_choisis(), presents))
    perimes = sorted(set(ABSENCES_ADMISES) - manquants)
    assert not perimes, (
        f"{perimes} sont déclarés absents alors qu'ils sont installés : retirer la ligne")


def test_l_identite_de_la_pile_est_calculable(presents):
    """Le bandeau que l'image imprime avant sa suite doit tenir debout partout.

    Il vaut d'être éprouvé : il s'exécute AVANT pytest dans l'image, donc une exception
    y ferait échouer la construction pour une raison sans rapport avec le code testé. Et
    il a déjà menti une fois — `sante.MOTEURS` dit « nlp » là où `sante.rapide()` dit
    « lemmes », si bien que le bandeau affichait `nlp ✗` sur une machine où spaCy et son
    modèle sont installés.
    """
    ident = identite_pile.identite()
    assert set(ident) >= {"commit", "python", "plateforme", "verrous", "cles", "moteurs"}
    assert ident["verrous"], "aucun verrou lu : le bandeau n'identifierait plus la pile"
    assert all(len(e) == 12 for e in ident["verrous"].values()), ident["verrous"]
    # Les moteurs viennent de `sante.rapide()` tel quel : aucune clé inventée ici.
    import sante
    assert set(ident["moteurs"]) == set(sante.rapide())
