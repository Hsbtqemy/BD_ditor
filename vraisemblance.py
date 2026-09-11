"""Keyness par log-vraisemblance (G²) — la seconde mesure de la comparaison A/B (ANA-4).

La comparaison classait par écart de fréquence RELATIVE, ce qui favorise mécaniquement
les mots fréquents : « le » à 30 % contre 27 % passe devant un mot présent huit fois en A
et jamais en B, alors que c'est ce dernier qui CARACTÉRISE A. Le rapport de vraisemblance
(Dunning 1993, sous la forme de Rayson et Garside 2000) pèse l'écart par la quantité
d'observations qui le soutient ; c'est la mesure d'usage en linguistique de corpus pour
dire ce qui distingue un sous-corpus d'un autre.

Pur — ni base, ni FastAPI : un calcul sur quatre comptes, verrouillé par une table de
valeurs connues (`tests/test_vraisemblance.py`).
"""
import math


def log_vraisemblance(fa: int, fb: int, ta: int, tb: int) -> float:
    """G² SIGNÉ d'une valeur : positif si elle est sur-représentée en A, négatif en B.

    `fa` / `fb` : ses fréquences dans A et dans B ; `ta` / `tb` : la taille de chaque
    sous-corpus. Le signe est celui de l'écart de fréquence relative : les deux mesures
    s'accordent toujours sur le CÔTÉ, elles ne diffèrent que sur l'ORDRE. Un sous-corpus
    vide ne prouve rien, et rend 0.
    """
    if not ta or not tb or not (fa or fb):
        return 0.0
    n = fa + fb
    g2 = 2.0 * (_terme(fa, ta * n / (ta + tb)) + _terme(fb, tb * n / (ta + tb)))
    return g2 if fa / ta >= fb / tb else -g2


def _terme(observe, attendu):
    """o·ln(o/e), prolongé par continuité en 0 : une valeur absente d'un côté."""
    return observe * math.log(observe / attendu) if observe else 0.0
