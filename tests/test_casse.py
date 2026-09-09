"""Normalisation de casse d'une transcription (NLP-3) — côté Python.

Ce fichier et `tests/js/casse.test.js` lisent LA MÊME table, `tests/cas-casse.json`.
C'est ce qui rend l'accord des deux implémentations mesuré plutôt que supposé : la règle
vit en double (le bouton du mode Transcription est en JavaScript, l'outil de lot en
Python), et deux écritures d'une même règle divergent toujours par le bas — sur un
caractère accentué, un point de suspension, une classe Unicode. Ici la divergence rend
l'une des deux suites rouge, en nommant le cas.

La table est GÉNÉRÉE depuis `casse.py`, donc elle ne prouve rien à elle seule côté
Python : c'est côté JS qu'elle mord. Ce qui la tient honnête est en dessous — les
propriétés (`only_upper`, idempotence) et les trois cas que la fiche NLP-3 exige
NOMMÉMENT (un sigle, un nom propre, une majuscule de début de phrase), écrits ici en
clair et non déduits de la table.
"""
import json
from pathlib import Path

import pytest

import casse

TABLE = json.loads((Path(__file__).parent / "cas-casse.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_table_partagee(cas):
    assert casse.normaliser(cas["entree"]) == cas["attendu"]


def test_la_table_couvre_les_deux_cotes_de_only_upper():
    """Mode d'échec de la table : ne semer que des cas capitaux.

    Une table entièrement en capitales rendrait `only_upper` invisible — la garde
    pourrait disparaître sans qu'un seul cas bronche, et c'est elle qui empêche un
    second clic de démolir « Tintin ». Le semis doit donc contenir les deux sortes.
    """
    touches = [c for c in TABLE if casse.est_tout_capitales(c["entree"])]
    epargnes = [c for c in TABLE if c["entree"] and not casse.est_tout_capitales(c["entree"])]
    assert touches, "aucun cas en capitales : la normalisation n'est pas éprouvée"
    assert epargnes, "aucun cas mixte : la garde only_upper n'est pas éprouvée"


# --------------------------------------------------------------------------- #
# Les trois cas que la fiche NLP-3 exige nommément
# --------------------------------------------------------------------------- #
def test_un_sigle_ponctue_survit():
    assert casse.normaliser("LE F.B.I. ARRIVE.") == "Le F.B.I. arrive."


def test_un_sigle_non_ponctue_ne_survit_pas_et_c_est_assume():
    """Sur une entrée toute en capitales, `FBI` est indiscernable d'un mot ordinaire.

    Le test verrouille la LIMITE, pas un défaut : préserver `FBI` demanderait de deviner,
    et la devinette produirait des faux positifs muets sur les mots courts. Une erreur
    qui se voit — « fbi » sous les yeux de qui vient de cliquer — vaut mieux.
    """
    assert casse.normaliser("LE FBI ARRIVE.") == "Le fbi arrive."


def test_un_nom_propre_n_est_pas_releve_et_c_est_assume():
    """Le relever suppose de le connaître, c'est-à-dire le gazetteer d'ANN-3 (non commencé).
    Le geste laisse donc « tintin » visible et corrigeable, plutôt qu'un nom inventé."""
    assert casse.normaliser("BONJOUR TINTIN.") == "Bonjour tintin."


def test_majuscule_de_debut_de_phrase():
    assert casse.normaliser("IL PART. IL REVIENT !") == "Il part. Il revient !"


# --------------------------------------------------------------------------- #
# Les règles propres à la bande dessinée
# --------------------------------------------------------------------------- #
def test_le_saut_de_ligne_ne_ferme_pas_la_phrase():
    """Le lettrage coupe ses lignes pour tenir dans la bulle, au milieu des phrases —
    l'inverse de la convention d'un texte suivi."""
    assert casse.normaliser("JE SUIS\nLÀ.") == "Je suis\nlà."


@pytest.mark.parametrize("entree,attendu", [
    ("JE... JE NE SAIS PAS.", "Je... je ne sais pas."),
    ("JE… JE NE SAIS PAS.", "Je… je ne sais pas."),
])
def test_les_points_de_suspension_ne_ferment_pas_la_phrase(entree, attendu):
    assert casse.normaliser(entree) == attendu


def test_le_point_d_un_sigle_ne_releve_pas_le_mot_suivant():
    assert casse.normaliser("C'EST LE F.B.I. QUI ARRIVE.") == "C'est le F.B.I. qui arrive."


# --------------------------------------------------------------------------- #
# Propriétés
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("texte", [
    "Je suis là, Tintin.",          # correction humaine déjà faite
    "je suis là",                   # bas de casse assumé
    "JE SUIS Là",                   # mixte : un vrai contraste de lettrage, ou une retouche
    "?!  …",                        # aucune lettre : rien à normaliser
    "",
])
def test_only_upper_n_y_touche_pas(texte):
    """Transposition d'`only_empty` : une ligne qui n'est pas INTÉGRALEMENT capitale est
    soit une correction humaine, soit un contraste de lettrage porteur de sens."""
    assert casse.normaliser(texte) == texte


@pytest.mark.parametrize("cas", TABLE, ids=[c["nom"] for c in TABLE])
def test_idempotence(cas):
    """Un second clic ne doit rien démolir. C'est `only_upper` qui l'assure — sans la
    garde, re-normaliser « Alors Tintin » rendrait « Alors tintin »."""
    une = casse.normaliser(cas["entree"])
    assert casse.normaliser(une) == une


def test_la_normalisation_est_reversible_quand_la_source_etait_capitale():
    """`upper(normalisé) == original` tant que la source était uniformément capitale.

    C'est ce qui rend la passe de lot rattrapable sans sauvegarde : le texte perdu n'est
    pas perdu, il se recalcule. La propriété tombe dès que la source est mixte — d'où
    `only_upper`, qui interdit justement d'y toucher.
    """
    for cas in TABLE:
        if casse.est_tout_capitales(cas["entree"]):
            assert casse.normaliser(cas["entree"]).upper() == cas["entree"]


@pytest.mark.parametrize("texte,attendu", [
    ("ALORS", True),
    ("Alors", False),
    ("alors", False),
    ("ÉTÉ", True),
    ("?!", False),          # pas une lettre : rien à normaliser
    ("", False),
    ("F.B.I.", True),
    ("30 ANS", True),
    ("30", False),          # que des chiffres : rien à normaliser
])
def test_est_tout_capitales(texte, attendu):
    assert casse.est_tout_capitales(texte) is attendu
