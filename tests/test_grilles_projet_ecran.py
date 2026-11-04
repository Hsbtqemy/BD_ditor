"""ANN-7 — ce que le bloc « Grilles » de l'Administration tient du serveur sans le lui demander.

Les mots d'une CIBLE (« la case », « des mots ») ne sont publiés par aucune route : le serveur
rend « Porte sur » en mots machine (`porte_sur` de `_vue_grille`), et l'écran les dit en mots.
`static/lib/grilles-projet.js` en tient donc une copie, et une seule : ce test la confronte à
`grille_tableur.CIBLES_MOTS`, ordre compris, comme `test_echelle_ecran.py` le fait pour les
crans. Une copie qui s'écarte dirait une grille autrement que son classeur. On lit le SOURCE.
Suite par défaut.
"""
import re
from pathlib import Path

import grille_tableur

RACINE = Path(__file__).resolve().parent.parent
LIB = RACINE / "static" / "lib" / "grilles-projet.js"


def _cibles_de_l_ecran():
    source = LIB.read_text(encoding="utf-8")
    bloc = re.search(r"const CIBLES_MOTS = \{(.*?)\};", source, re.S)
    assert bloc, "la table CIBLES_MOTS est introuvable dans static/lib/grilles-projet.js"
    return re.findall(r'(\w+): "([^"]+)"', bloc.group(1))


def test_les_mots_d_une_cible_sont_ceux_du_classeur_dans_l_ordre():
    assert _cibles_de_l_ecran() == list(grille_tableur.CIBLES_MOTS.items())


def test_l_administration_ne_recopie_pas_les_mots_d_une_cible():
    """Le script de surface passe par `BDGrillesProjet` : « boîte de personnage » vit à un
    seul endroit de l'écran."""
    source = (RACINE / "static" / "administration.js").read_text(encoding="utf-8")
    recopies = [m for m in ("boîte de personnage", "texte hors bulle", "détail d'image")
                if m in source]
    assert not recopies, f"administration.js écrit en clair {recopies} : passer par BDGrillesProjet"
