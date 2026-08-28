"""Le point de passage UNIQUE de l'autorisation.  AUTH-2, puis AUTH-3.

Ce module répond à une seule question, et il est le seul endroit du dépôt où elle se
tranche : **quelles collections cette requête a-t-elle le droit de voir, et à quel
niveau ?** Tout le reste — routes, recherche, analyses, exports — consomme sa réponse sans
jamais la recalculer.

Pourquoi un module, et pas quelques `if` dans `main.py`.

Le risque de ce chantier n'est pas la difficulté, c'est l'exhaustivité. Il y a plus de cent
routes ; une règle d'accès qui les couvre toutes sauf une ne cloisonne rien, et le trou ne
se voit pas puisque tout marche. Un point de passage unique rend l'oubli DÉTECTABLE : on
peut demander mécaniquement « quelles routes touchent la base sans le consulter ? », ce
qu'on ne peut pas demander d'une condition dispersée. C'est `tests/test_autorisation.py`
qui pose la question.

**Trois niveaux, et le troisième n'est pas une gradation du deuxième** (AUTH-3) : `lecture`,
`ecriture` (annoter), `proprietaire` (décider qui d'autre entrera). `peut_administrer()` est
donc une fonction à part et non un `peut_ecrire()` plus exigeant — un membre en écriture
n'hérite pas du droit d'élargir le cercle.

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

# Niveaux d'accès, du plus faible au plus fort. Chacun IMPLIQUE les précédents : on ne
# modifie pas ce qu'on ne voit pas, et on n'administre pas ce qu'on ne peut pas modifier.
#
# `proprietaire` (AUTH-3) est un niveau et non une colonne à part : une seule table reste
# la source de vérité, la résolution écrite pour AUTH-2 fonctionne telle quelle, et un
# GROUPE peut posséder une collection — un espace de travail survit rarement au départ
# d'une personne. Contrepartie assumée, gardée en base : jamais zéro propriétaire.
LECTURE = "lecture"
ECRITURE = "ecriture"
PROPRIETAIRE = "proprietaire"
NIVEAUX = (LECTURE, ECRITURE, PROPRIETAIRE)

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

    __slots__ = ("tout", "admin", "lecture", "ecriture", "propriete",
                 "utilisateur", "groupes")

    def __init__(self, *, tout: bool = False, admin: bool = False,
                 lecture: frozenset = frozenset(), ecriture: frozenset = frozenset(),
                 propriete: frozenset = frozenset(),
                 utilisateur: Optional[str] = None, groupes: tuple = ()):
        self.tout = tout
        self.admin = admin
        self.propriete = frozenset(propriete)
        # Les niveaux s'empilent : posséder implique écrire, écrire implique lire. On le
        # fait ICI, une fois, plutôt que dans chaque appelant — un `in self.ecriture` qui
        # oublierait les propriétaires serait un refus silencieux et parfaitement crédible.
        self.ecriture = frozenset(ecriture) | self.propriete
        self.lecture = frozenset(lecture) | self.ecriture
        self.utilisateur = utilisateur
        self.groupes = tuple(groupes)

    # -- décisions ponctuelles ---------------------------------------------- #
    def peut_lire(self, collection_id: int) -> bool:
        return self.tout or collection_id in self.lecture

    def peut_ecrire(self, collection_id: int) -> bool:
        return self.tout or collection_id in self.ecriture

    def peut_administrer(self, collection_id: int) -> bool:
        """A-t-on le droit de PARTAGER cette collection — accorder, retirer, supprimer ?

        Administrer n'est pas écrire, et c'est le troisième palier d'AUTH-3 : écrire, c'est
        annoter ; administrer, c'est décider qui d'autre entrera. Un membre en écriture
        n'hérite donc PAS du droit d'élargir le cercle — sinon il s'élargirait sans que le
        propriétaire le sache, et un accès accordé par erreur deviendrait intraçable.

        L'administrateur (`bd-admins`) passe outre, et c'est écrit : c'est le recours quand
        quelqu'un quitte le projet en laissant une collection derrière lui. Le refuser
        fabriquerait des collections définitivement bloquées, dont la seule sortie serait
        un UPDATE en SQL — c'est-à-dire exactement ce que ce chantier existe pour supprimer.
        """
        return self.admin or collection_id in self.propriete

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

    def clause_terme(self, alias: str) -> tuple[str, list]:
        """Fragment SQL restreignant un TERME du vocabulaire (tag, domaine, dimension,
        valeur) à ce qui est visible. `alias` désigne sa colonne `collection_id`.

        Le vocabulaire ne suit pas la même règle que les données : il porte déjà sa propre
        notion de portée depuis le lexique situé (A4) — `collection_id` NULL veut dire
        GLOBAL, et c'est un état voulu, pas un oubli. Un terme est donc visible s'il est
        global, ou s'il appartient à une collection qu'on lit.

        Conséquence assumée : une personne sans aucune collection voit quand même le
        vocabulaire global. Elle ne voit aucune donnée pour autant, et un lexique vide
        serait un état plus déroutant qu'utile.
        """
        if self.tout:
            return "1", []
        ids = sorted(self.lecture)
        if not ids:
            return f"{alias} IS NULL", []
        marques = ", ".join("?" * len(ids))
        return f"({alias} IS NULL OR {alias} IN ({marques}))", list(ids)

    def peut_ecrire_terme(self, collection_id) -> bool:
        """A-t-on le droit de MODIFIER ce terme du vocabulaire ?

        `clause_terme` dit ce qu'on VOIT ; ceci dit ce qu'on peut changer, et les deux ne
        se confondent pas — un vocabulaire partagé se lit bien plus largement qu'il ne
        s'édite. Un terme LOCAL s'édite si l'on écrit dans sa collection ; un terme GLOBAL
        s'édite si l'on écrit quelque part, personne ne le « possédant » en propre.
        """
        if self.tout:
            return True
        if collection_id is None:
            return bool(self.ecriture)
        return collection_id in self.ecriture

    def peut_ecrire_quelque_part(self) -> bool:
        """A-t-on le droit d'écrire, où que ce soit ? Sert aux gestes qui ne visent aucune
        collection en particulier — enrichir le vocabulaire, par exemple. Sans cela, une
        personne en lecture seule pourrait polluer un vocabulaire partagé par tous."""
        return self.tout or bool(self.ecriture)

    def __repr__(self) -> str:                  # diagnostic uniquement
        if self.tout:
            return f"<Portee TOUT admin={self.admin} user={self.utilisateur!r}>"
        return (f"<Portee lecture={sorted(self.lecture)} "
                f"ecriture={sorted(self.ecriture)} "
                f"propriete={sorted(self.propriete)} user={self.utilisateur!r}>")


TOTALE = Portee(tout=True, admin=True)


# --------------------------------------------------------------------------- #
# Résolution
# --------------------------------------------------------------------------- #
def collections_du_principal(conn: sqlite3.Connection, login: str,
                             noms_groupes: list[str]) -> tuple[frozenset, frozenset, frozenset]:
    """(lecture, écriture, propriété) — les collections ouvertes à ce login ou à l'un de
    ses groupes, rangées par niveau.

    Une seule requête : le nombre de groupes est petit, et cette fonction est appelée à
    chaque requête HTTP.

    Les niveaux ne sont PAS cumulés ici — `Portee.__init__` s'en charge, et un seul endroit
    doit le faire. Un niveau inconnu (base éditée à la main, niveau retiré du code) est
    rangé en LECTURE : dégrader est la seule erreur qui ne s'aggrave pas.
    """
    principaux = [(UTILISATEUR, login)] + [(GROUPE, g) for g in noms_groupes]
    conditions = " OR ".join("(genre = ? AND principal = ?)" for _ in principaux)
    params = [v for paire in principaux for v in paire]
    par_niveau = {LECTURE: set(), ECRITURE: set(), PROPRIETAIRE: set()}
    for cid, niveau in conn.execute(
            f"SELECT collection_id, niveau FROM collection_acces WHERE {conditions}",
            params):
        par_niveau.get(niveau, par_niveau[LECTURE]).add(cid)
    return (frozenset(par_niveau[LECTURE]), frozenset(par_niveau[ECRITURE]),
            frozenset(par_niveau[PROPRIETAIRE]))


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
    lecture, ecriture, propriete = collections_du_principal(conn, login, noms_groupes)
    return Portee(lecture=lecture, ecriture=ecriture, propriete=propriete,
                  utilisateur=login, groupes=tuple(noms_groupes))
