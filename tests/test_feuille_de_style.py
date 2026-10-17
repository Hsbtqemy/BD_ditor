"""La feuille de style s'équilibre : chaque accolade ouverte se referme, et aucune ne se
ferme de trop.

Ce que ce test garde ne se voit nulle part ailleurs. Une accolade de trop au milieu de
`static/style.css` ne lève rien : le navigateur ignore la suite jusqu'à la règle suivante
qu'il sait relire, et c'est le bloc d'APRÈS qui cesse d'agir, sans un mot. Trouvé le
2026-10-17 pendant la refonte de la Bibliothèque (UX-18) : une accolade orpheline laissée
derrière une requête de conteneur désactivait la règle des fenêtres basses (A11Y-2) — et
c'est un test de l'ADMINISTRATION qui l'a dit, deux surfaces plus loin. Suite par défaut.
"""
import re
from pathlib import Path

FEUILLE = Path(__file__).resolve().parent.parent / "static" / "style.css"


def _profondeurs(source: str):
    """Les commentaires et les chaînes ôtés — une accolade y est du texte —, la profondeur
    d'imbrication à chaque accolade, et la ligne où elle passerait sous zéro."""
    sans = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S)
    sans = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', '""', sans)
    profondeur = 0
    for i, c in enumerate(sans):
        if c == "{":
            profondeur += 1
        elif c == "}":
            profondeur -= 1
            if profondeur < 0:
                return profondeur, sans[:i].count("\n") + 1
    return profondeur, None


def test_la_garde_mord():
    """Le plancher : la mesure voit une accolade de trop, et en dit la ligne."""
    assert _profondeurs("a { b: c; }\n}\nd { e: f; }") == (-1, 2)
    assert _profondeurs("a { b: c;") == (1, None)
    assert _profondeurs('a::before { content: "}"; }') == (0, None)


def test_la_feuille_s_equilibre():
    profondeur, ligne = _profondeurs(FEUILLE.read_text(encoding="utf-8"))
    assert ligne is None, (
        f"static/style.css ferme une accolade de trop à la ligne {ligne} : la règle qui "
        "suit cesse d'agir sans que rien ne le dise")
    assert profondeur == 0, f"static/style.css laisse {profondeur} accolade(s) ouverte(s)"
