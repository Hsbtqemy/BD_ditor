"""COL-3, tranche 2 — ce que l'écran de « supprimer » tient du serveur sans le lui demander.

Les genres d'une demande et ses deux réponses ne sont publiés par aucune route : le serveur
les ACCEPTE (`POST /api/demandes`, `POST /api/demandes/{id}/reponse`) et les renvoie dans ce
qu'il lit, mais l'écran doit les écrire avant d'avoir rien lu. `static/lib/suppression.js`
en tient donc une copie — et une seule : le cliquet ci-dessous interdit aux deux scripts de
surface de les écrire en clair, ce qui en ferait une troisième que rien ne tiendrait.

Une copie qui s'écarte enverrait une demande que le serveur refuse par un 422 : l'écran
offrirait un geste qui n'aboutit jamais. On lit le SOURCE, comme `test_projet_ecran.py`
pour les rôles d'un projet : on compare deux énumérations de données. Suite par défaut.
"""
import re
from pathlib import Path

import database

RACINE = Path(__file__).resolve().parent.parent
LIB = RACINE / "static" / "lib" / "suppression.js"
SURFACES = ("corpus.js", "administration.js")


def _constante(nom):
    m = re.search(rf'const {nom} = "([^"]+)";', LIB.read_text(encoding="utf-8"))
    assert m, f"{nom} introuvable dans static/lib/suppression.js"
    return m.group(1)


def test_les_genres_et_les_reponses_sont_ceux_du_serveur():
    assert _constante("GENRE_DOCUMENT") == database.DEMANDE_SUPPRESSION_DOCUMENT
    assert _constante("GENRE_PROJET") == database.DEMANDE_SUPPRESSION_PROJET
    assert _constante("ACCEPTER") == database.REPONSE_ACCEPTEE
    assert _constante("REFUSER") == database.REPONSE_REFUSEE


def test_aucune_surface_ne_les_recopie():
    """Les surfaces passent par `BDSuppression` : la valeur vit à un seul endroit."""
    valeurs = (database.DEMANDE_SUPPRESSION_DOCUMENT, database.DEMANDE_SUPPRESSION_PROJET,
               database.REPONSE_ACCEPTEE, database.REPONSE_REFUSEE)
    for script in SURFACES:
        source = (RACINE / "static" / script).read_text(encoding="utf-8")
        recopies = [v for v in valeurs if f'"{v}"' in source or f"'{v}'" in source]
        assert not recopies, f"{script} écrit en clair {recopies} : passer par BDSuppression"


def test_les_genres_de_la_prise_et_l_etat_partiel_sont_ceux_du_serveur():
    """COL-3, écran de la 3a : les trois genres qui ne sont pas des suppressions, et l'état
    d'une demande acceptée en partie, recopiés une fois et mesurés de même."""
    assert _constante("GENRE_ENTREE") == database.DEMANDE_ENTREE_DOCUMENTS
    assert _constante("GENRE_REJOINDRE") == database.DEMANDE_REJOINDRE
    assert _constante("GENRE_RENDRE") == database.DEMANDE_RENDRE
    assert _constante("GENRE_AMORCER") == database.DEMANDE_AMORCER
    assert _constante("PARTIELLE") == database.REPONSE_PARTIELLE
    assert set(database.GENRES_DEMANDE) == {
        _constante(n) for n in ("GENRE_DOCUMENT", "GENRE_PROJET", "GENRE_ENTREE",
                                "GENRE_REJOINDRE", "GENRE_RENDRE", "GENRE_AMORCER")}
