"""Le point de passage UNIQUE de l'autorisation.  AUTH-2.

Ce module répond à une seule question, et il est le seul endroit du dépôt où elle se
tranche : **quelles collections cette requête a-t-elle le droit de voir, et en écriture ou
en lecture ?** Tout le reste — routes, recherche, analyses, exports — consomme sa réponse
sans jamais la recalculer.

Pourquoi un module, et pas quelques `if` dans `main.py`.

Le risque de ce chantier n'est pas la difficulté, c'est l'exhaustivité. Il y a 109 routes ;
une règle d'accès qui en couvre 108 ne cloisonne rien, et le trou ne se voit pas puisque
tout marche. Un point de passage unique rend l'oubli DÉTECTABLE : on peut demander
mécaniquement « quelles routes touchent la base sans le consulter ? », ce qu'on ne peut pas
demander d'une condition dispersée. C'est `tests/test_autorisation.py` qui pose la question.

Trois principes.

**La collection est l'unité de cloisonnement.** On n'autorise jamais un album directement :
on autorise une collection, et l'album suit celle qui le contient. C'est aussi la raison
pour laquelle aucun album ne peut rester hors collection (`database.collection_par_defaut`) :
un orphelin ne correspondrait à aucune règle, et il faudrait alors inventer une politique
dans le code, à un endroit qu'on oublierait de relire.

**On répond 404, pas 403.** Dire « cet album existe, mais pas pour vous » révèle la
composition du corpus — le nombre d'albums, l'existence d'une étude concurrente. L'absence
est la seule réponse qui ne fuit rien. Corollaire à connaître : un utilisateur qui a perdu
un droit ne verra pas d'erreur explicite, ses objets auront simplement disparu.

**Sans proxy d'auth, tout passe.** `BD_AUTH_PROXY` faux, c'est le mono-poste : une seule
personne devant sa machine, aucune identité à opposer à personne. La portée est alors
totale, et le comportement du dépôt reste STRICTEMENT celui d'avant AUTH-2. Le contraire —
cloisonner sans savoir qui est là — rendrait l'outil inutilisable en local.

Le pendant du troisième principe, et il faut le regarder en face : avec `BD_AUTH_PROXY`
vrai mais sans en-tête d'identité, la portée est VIDE. Une requête qui n'est pas passée par
Authelia ne voit rien. Si le proxy est mal configuré, l'application paraîtra vide pour tout
le monde — panne bruyante et immédiate, plutôt que fuite silencieuse. C'est délibéré : un
contrôle d'accès qui échoue doit fermer, pas ouvrir.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from config import AUTH_ADMIN_GROUPS, AUTH_PROXY

# Niveaux d'accès. L'écriture IMPLIQUE la lecture — on ne modifie pas ce qu'on ne voit pas.
LECTURE = "lecture"
ECRITURE = "ecriture"
NIVEAUX = (LECTURE, ECRITURE)

# Genres de principal. EXPLICITE plutôt que déduit : un login et un nom de groupe peuvent
# être la même chaîne, et une ambiguïté silencieuse sur un contrôle d'accès n'est pas une
# hypothèse qu'on se permet.
UTILISATEUR = "utilisateur"
GROUPE = "groupe"
GENRES = (UTILISATEUR, GROUPE)


# --------------------------------------------------------------------------- #
# Identité — lecture des en-têtes posés par le proxy
# --------------------------------------------------------------------------- #
def auteur(request) -> Optional[str]:
    """Login de la personne connectée, depuis `Remote-User`. None hors proxy.

    L'en-tête n'est cru QUE si `BD_AUTH_PROXY` déclare qu'on est bien derrière le proxy
    (AUTH-1) : sans le drapeau, n'importe quel client pourrait se déclarer administrateur
    en une ligne de curl.
    """
    if not AUTH_PROXY:
        return None
    return (request.headers.get("Remote-User") or "").strip() or None


def groupes(request) -> list[str]:
    """Groupes de la personne connectée, depuis `Remote-Groups` (séparés par des virgules).

    JAMAIS stockés : ils vivent dans Authelia et sont relus à chaque requête, pour qu'un
    retrait de groupe prenne effet immédiatement, sans intervention en base.
    """
    if not AUTH_PROXY:
        return []
    brut = request.headers.get("Remote-Groups") or ""
    return [g for g in (x.strip() for x in brut.split(",")) if g]


# --------------------------------------------------------------------------- #
# La portée
# --------------------------------------------------------------------------- #
class Portee:
    """Ce que CETTE requête a le droit de voir. Immuable, calculée une fois par requête.

    `tout` court-circuite les ensembles : c'est le mono-poste et l'administrateur, pour qui
    la question ne se pose pas. On ne matérialise pas la liste de toutes les collections
    dans ce cas — elle serait juste au moment du calcul et fausse dès la création suivante.
    """

    __slots__ = ("tout", "admin", "lecture", "ecriture", "utilisateur", "groupes")

    def __init__(self, *, tout: bool = False, admin: bool = False,
                 lecture: frozenset = frozenset(), ecriture: frozenset = frozenset(),
                 utilisateur: Optional[str] = None, groupes: tuple = ()):
        self.tout = tout
        self.admin = admin
        self.lecture = frozenset(lecture) | frozenset(ecriture)   # écrire implique lire
        self.ecriture = frozenset(ecriture)
        self.utilisateur = utilisateur
        self.groupes = tuple(groupes)

    # -- décisions ponctuelles ---------------------------------------------- #
    def peut_lire(self, collection_id: int) -> bool:
        return self.tout or collection_id in self.lecture

    def peut_ecrire(self, collection_id: int) -> bool:
        return self.tout or collection_id in self.ecriture

    # -- filtrage des requêtes ---------------------------------------------- #
    def clause_album(self, alias: str = "a.id", *, ecriture: bool = False) -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux albums autorisés.

        Renvoie `(sql, params)` à insérer dans un `WHERE`. `alias` est un morceau de SQL
        écrit par le code appelant, JAMAIS une valeur venue du client — les seuls
        paramètres liés sont les ids de collection, qui sortent de la base.

        On filtre par `EXISTS` sur les collections plutôt que par une liste d'albums :
        les collections sont peu nombreuses et les albums peuvent ne pas l'être. La liste
        d'ids reste donc courte quel que soit le corpus.
        """
        if self.tout:
            return "1", []
        ids = sorted(self.ecriture if ecriture else self.lecture)
        if not ids:
            return "0", []                      # aucune collection : rien n'est visible
        marques = ", ".join("?" * len(ids))
        return (f"EXISTS (SELECT 1 FROM collection_album ca "
                f"WHERE ca.album_id = {alias} AND ca.collection_id IN ({marques}))",
                list(ids))

    def __repr__(self) -> str:                  # diagnostic uniquement
        if self.tout:
            return f"<Portee TOUT admin={self.admin} user={self.utilisateur!r}>"
        return (f"<Portee lecture={sorted(self.lecture)} "
                f"ecriture={sorted(self.ecriture)} user={self.utilisateur!r}>")


TOTALE = Portee(tout=True, admin=True)


# --------------------------------------------------------------------------- #
# Résolution
# --------------------------------------------------------------------------- #
def collections_du_principal(conn: sqlite3.Connection, login: str,
                             noms_groupes: list[str]) -> tuple[frozenset, frozenset]:
    """(lecture, écriture) — les collections ouvertes à ce login ou à l'un de ses groupes.

    Une seule requête : le nombre de groupes est petit, et cette fonction est appelée à
    chaque requête HTTP.
    """
    principaux = [(UTILISATEUR, login)] + [(GROUPE, g) for g in noms_groupes]
    if not principaux:
        return frozenset(), frozenset()
    conditions = " OR ".join("(genre = ? AND principal = ?)" for _ in principaux)
    params = [v for paire in principaux for v in paire]
    lecture, ecriture = set(), set()
    for cid, niveau in conn.execute(
            f"SELECT collection_id, niveau FROM collection_acces WHERE {conditions}",
            params):
        (ecriture if niveau == ECRITURE else lecture).add(cid)
    return frozenset(lecture), frozenset(ecriture)


def resoudre(conn: sqlite3.Connection, request) -> Portee:
    """La portée de CETTE requête. Le seul point d'entrée du module."""
    if not AUTH_PROXY:
        return TOTALE                           # mono-poste : comportement d'avant AUTH-2
    login = auteur(request)
    noms_groupes = groupes(request)
    if not login:
        return Portee(groupes=tuple(noms_groupes))   # pas passé par Authelia : rien
    if AUTH_ADMIN_GROUPS & set(noms_groupes):
        return Portee(tout=True, admin=True, utilisateur=login, groupes=tuple(noms_groupes))
    lecture, ecriture = collections_du_principal(conn, login, noms_groupes)
    return Portee(lecture=lecture, ecriture=ecriture,
                  utilisateur=login, groupes=tuple(noms_groupes))
