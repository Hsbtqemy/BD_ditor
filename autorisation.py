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

**Et une capacité HORS de l'échelle : exporter** (DROIT-2). Les stagiaires écrivent, et
c'est voulu ; ils n'exportent pas pour autant, et une règle « écriture et plus » ne les
arrêterait pas. `exporter` est donc une case posée À CÔTÉ du niveau, accordée par
collection, d'office pour les propriétaires — et `peut_exporter()` une question de
plus, pas un palier de plus.

**Et un étage AU-DESSUS : le projet** (COL-3). Une collection appartient à un projet, et
l'on EST d'un projet — membre, ou responsable. Ce module dit de quels projets on est et
lesquels on gère (`est_du_projet`, `peut_gerer_projet`, `peut_decider_des_projets`,
`clause_projet`). Il ne s'en sert pour ouvrir qu'UNE collection par projet, sa collection de
BASE (D10, Hugo, 2026-10-17) : ses responsables en sont propriétaires, ses membres y entrent
au niveau que le projet a choisi (écriture, lecture, ou rien) — une dérivation faite dans
`Portee.__init__`, jamais recopiée dans `collection_acces`. Et depuis la tranche 3c (F1,
Hugo, 2026-10-26), ses RESPONSABLES LISENT toutes ses autres collections — une lecture
dérivée de même, qui n'ouvre ni l'écriture, ni l'export, ni « Qui entre ». Toute autre
collection garde son « Qui entre » pour le reste : entrer dans un projet comme MEMBRE n'ouvre
aucune d'elles. Et l'on n'entre dans une collection que si l'on est du projet (F2, tranche
3c) : une règle d'ÉCRITURE de `collection_acces`, tenue par la route et l'outil
(`database.est_du_projet_par_reference`), que ce module ne lit pas.

Trois principes.

**La collection est l'unité de cloisonnement.** On n'autorise jamais un album directement :
on autorise une collection, et l'album suit celle qui le contient. Un album hors de toute
collection n'est donc ouvert à personne — sauf à la portée totale. C'était un état interdit
(`database.collection_par_defaut`) ; depuis le fonds (COL-3, tranche 2) c'est celui d'une
copie GARDÉE : supprimée de sa dernière collection, ou importée au fonds par un
administrateur. Aucune politique n'est à inventer pour elle : la règle est celle d'un
album qu'aucune collection n'ouvre.

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
from database import (CRAN_ANNOTATIONS, DEMANDE_AMORCER_ENTRE_PROJETS,
                      GENRES_CONSENTIS,
                      NATURE_COLLECTIF, rang_du_cran,
                      sql_album_isole, sql_est_bac_a_sable, sql_est_isole, sql_est_jeu,
                      sql_projet_d_album, sql_projet_de, sql_rang_du_cran)
from grilles import ETAT_PUBLIEE as ETAT_VERSION_PUBLIEE
from grilles import ETAT_VIVANTE as ETAT_VERSION_VIVANTE

# Niveaux d'accès, du plus faible au plus fort. Chacun IMPLIQUE les précédents : on ne
# modifie pas ce qu'on ne voit pas, et on n'administre pas ce qu'on ne peut pas modifier.
#
# `proprietaire` (AUTH-3) est un niveau et non une colonne à part : une seule table reste
# la source de vérité, la résolution écrite pour AUTH-2 fonctionne telle quelle, et un
# GROUPE peut posséder une collection — un espace de travail survit rarement au départ
# d'une personne. Contrepartie assumée : on ne RETIRE jamais le dernier propriétaire. Une
# collection peut en revanche NAÎTRE sans propriétaire — créée par un administrateur, en
# mono-poste, ou par `tools/gerer_collections.py` sans `--proprietaire` — et seule une
# portée TOTALE l'administre alors : un administrateur, ou le mono-poste (option B
# d'AUTH-12, 2026-09-16).
LECTURE = "lecture"
ECRITURE = "ecriture"
PROPRIETAIRE = "proprietaire"
NIVEAUX = (LECTURE, ECRITURE, PROPRIETAIRE)

# Ce que chaque niveau permet, dit en ACTES — pour l'écran qui attribue les accès (AUTH-12,
# étape 3) et pour « Mon compte ». DES DONNÉES, jamais une garde : aucune fonction de ce
# module ne les lit pour décider, et `Portee` les ignore. Elles vivent ICI, sous `NIVEAUX`,
# parce que l'ordre de l'échelle et son cumul sont tranchés quelques lignes plus bas
# (`Portee.__init__`) : une description posée ailleurs pourrait dériver sans bruit.
# `tests/test_droits.py` la confronte à `Portee` par table de vérité, si bien qu'elle ne peut
# pas promettre ce que le cumul ne fait pas.
#
# Les actes qui partagent une valeur de `lies` sont accordés ENSEMBLE aujourd'hui : l'écran
# les dessine d'un seul trait. Sans cela il promettrait une finesse que le serveur n'a pas,
# et un refus viendrait le démentir (AUTH-10). Aucune décision d'AUTH-10 n'est prise ici :
# ses remèdes feront évoluer ces données, pas l'écran. Ce que la description ne prouve PAS :
# qu'une route donnée exige le niveau de son acte — le périmètre route par route n'existe pas.
#
# LIBELLÉS VALIDÉS par Hugo le 2026-09-17 (AUTH-12). Ce sont des données : les changer ne
# touche que cette table et ses tests. Les CODES, eux, ne suivent pas les libellés —
# `structurer` et `lots` sont restés quand leurs libellés ont changé.
ACTES = (
    {"code": "lire", "libelle": "lire", "niveau": LECTURE, "lies": None,
     "avertissement": None},
    {"code": "annoter", "libelle": "annoter", "niveau": ECRITURE, "lies": ECRITURE,
     "avertissement": None},
    {"code": "structurer", "libelle": "organiser les albums", "niveau": ECRITURE,
     "lies": ECRITURE, "avertissement": None},
    {"code": "vocabulaire", "libelle": "gérer le vocabulaire", "niveau": ECRITURE,
     "lies": ECRITURE, "avertissement": None},
    {"code": "lots", "libelle": "lancer la reconnaissance automatique", "niveau": ECRITURE,
     "lies": ECRITURE, "avertissement": None},
    {"code": "decider", "libelle": "décider qui entre", "niveau": PROPRIETAIRE, "lies": None,
     # Vrai de la suppression DÉFINITIVE seule depuis le fonds (COL-3, tranche 2) :
     # supprimer un album de sa collection le garde au fonds, avec son travail. Le mot
     # « définitivement » est le seul ajout à la phrase validée par Hugo le 2026-09-17
     # (proposition R10 du cadrage, suivie en route). Portée par l'acte `structurer`
     # jusqu'à la tranche 3c : un écrivain n'efface plus, qui tient l'espace efface (F3) —
     # la phrase change de ligne, telle quelle (Q13).
     "avertissement": "Supprimer définitivement un album efface ses images et ne se "
                      "rattrape pas."},
)
# Ce qui ne s'ordonne pas avec l'échelle : une case À CÔTÉ du niveau (DROIT-2).
HORS_RANG = (
    {"code": "exporter", "libelle": "exporter", "champ": "exporter",
     "d_office": PROPRIETAIRE},
)


def description_des_droits() -> dict:
    """La description servie par `GET /api/droits` : l'échelle, les actes, ce qui est hors
    rang. Des copies, pour qu'aucun appelant ne modifie la table en la lisant."""
    return {"echelle": list(NIVEAUX),
            "actes": [dict(a) for a in ACTES],
            "hors_rang": [dict(h) for h in HORS_RANG]}

# Rôles dans un PROJET (COL-3), du plus faible au plus fort. Le responsable est membre :
# le cumul se fait dans `Portee.__init__`, une fois, pour la raison écrite sur les niveaux.
#
# CE QUE CES RÔLES NE SONT PAS : des niveaux d'accès sur les collections du projet. Deux
# exceptions, et elles sont voulues : la collection de BASE du projet, dont le responsable
# est propriétaire et où le membre entre au niveau `acces_membres` (D10, Hugo, 2026-10-17) ;
# et la LECTURE de toutes les autres collections du projet par son responsable (F1, tranche
# 3c, Hugo, 2026-10-26) — dérivées dans `Portee.__init__`, à partir de `bases_des_projets`
# et de `collections_des_projets`. Aucune des clauses qui filtrent les données
# (`clause_album`, `clause_terme`) ne connaît les projets : elles lisent les ensembles que la
# dérivation a remplis. Toute autre collection garde son « Qui entre ».
MEMBRE = "membre"
RESPONSABLE = "responsable"
ROLES_PROJET = (MEMBRE, RESPONSABLE)

# Ce qu'un projet peut ouvrir à ses MEMBRES dans sa collection de base (D10) : un niveau de
# `collection_acces`, parmi ces deux — `None` veut dire « protégée », les membres n'y entrent
# pas. `proprietaire` n'y est pas : en faire profiter chaque membre lui donnerait de décider
# qui d'autre entre, ce qu'AUTH-3 sépare d'écrire. Le premier est la valeur d'une création
# qui ne la précise pas — celle que l'écran présélectionnera.
ACCES_MEMBRES = (ECRITURE, LECTURE)

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


def entete_groupes_recu(request) -> Optional[bool]:
    """`Remote-Groups` est-il PARVENU, quel que soit son contenu ? (AUTH-8)

    True s'il est là — même vide ; False s'il manque alors qu'on est derrière le proxy ;
    None hors proxy, où aucun en-tête n'est lu et où la question ne se pose donc pas.
    C'est la forme d'`auteur()`, qui rend déjà None dans ce cas.

    POURQUOI UNE FONCTION À PART, plutôt qu'un troisième état rendu par `groupes()` : le
    contrat de `groupes()` est une LISTE, et tout ce qui l'appelle en dépend. Un appelant
    qui ignore cette fonction-ci continue de se comporter exactement comme avant.

    CE QUE `groupes()` ÉCRASE, et qu'on ne peut pas lui reprocher : son
    `headers.get("Remote-Groups") or ""` fait arriver un en-tête ABSENT et un en-tête VIDE
    de façon identique. Pour une LISTE de groupes c'est le bon comportement — dans les
    deux cas il n'y en a aucun. Mais les deux ne veulent pas dire la même chose :

    | en-têtes reçus                          | ce que ça signifie                     |
    |-----------------------------------------|----------------------------------------|
    | `Remote-User` absent                     | aucune identité                        |
    | `Remote-User` + `Remote-Groups` ABSENT   | les groupes ne sont pas recopiés       |
    | `Remote-User` + `Remote-Groups` VIDE     | ce compte n'appartient à aucun groupe  |

    La deuxième ligne rend TOUS les accès par groupe silencieusement inopérants : on se
    connecte correctement, on voit une application vide, et jusqu'ici le seul indice
    disponible était le même que pour un simple défaut d'accès.

    CE QUE CETTE FONCTION N'ÉTABLIT PAS. Que « absent » signifie une panne de recopie
    repose sur une lecture des sources d'Authelia `v4.39.22` — `handleAuthzAuthorizedStandard`
    pose `Remote-Groups` INCONDITIONNELLEMENT dès qu'il y a un login, et
    `strings.Join([], ",")` vaut `""`. Lire un dépôt n'est pas mesurer un déploiement, et
    la confirmation sur l'instance reste une case ouverte d'AUTH-8. D'où l'observation
    rapportée telle quelle à l'écran, sans que la cause soit tranchée à la place de qui
    connaît son déploiement.
    """
    if not AUTH_PROXY:
        return None
    return request.headers.get("Remote-Groups") is not None


# --------------------------------------------------------------------------- #
# La portée
# --------------------------------------------------------------------------- #
class Portee:
    """Ce que CETTE requête a le droit de voir. Immuable, calculée une fois par requête.

    `tout` court-circuite les ensembles : c'est le mono-poste et l'administrateur, pour qui
    la question ne se pose pas. On ne matérialise pas la liste de toutes les collections
    dans ce cas — elle serait juste au moment du calcul et fausse dès la création suivante.
    """

    __slots__ = ("tout", "admin", "lecture", "ecriture", "propriete", "export",
                 "projets", "projets_geres", "utilisateur", "groupes",
                 "bacs_a_sable", "bacs_a_soi", "collections_bac", "hors_isoles",
                 "bornee", "cols_bacs", "projets_bacs", "_ord")

    def __init__(self, *, tout: bool = False, admin: bool = False,
                 lecture: frozenset = frozenset(), ecriture: frozenset = frozenset(),
                 propriete: frozenset = frozenset(), export: frozenset = frozenset(),
                 projets: frozenset = frozenset(), projets_geres: frozenset = frozenset(),
                 bases: tuple = (), lues_par_le_projet: frozenset = frozenset(),
                 utilisateur: Optional[str] = None, groupes: tuple = (),
                 bacs_a_sable: frozenset = frozenset(), bacs_a_soi: frozenset = frozenset(),
                 collections_bac: frozenset = frozenset(), hors_isoles: bool = False,
                 bornee: bool = False, cols_bacs: frozenset = frozenset(),
                 projets_bacs: frozenset = frozenset()):
        self.tout = tout
        self.admin = admin
        # COL-4 (Hugo, 2026-10-24) — une portée totale BORNÉE ne passe dans AUCUN bac à
        # sable : l'administrateur, dans le bac d'un autre, n'a RIEN, comme un non-membre ;
        # dans le sien, et dans ceux où il est invité, il est un arrivant comme les autres.
        # `cols_bacs` et `projets_bacs` : toutes les collections et tous les projets des bacs
        # à sable de l'instance, lus à la résolution ; dans ce périmètre, ce sont les
        # ensembles ORDINAIRES (`lecture`, `ecriture`… restreints aux bacs à sable) qui
        # répondent, jamais `tout`. Le mono-poste (`TOTALE`) n'est pas bornée : sans proxy,
        # personne n'ouvre de bac à sable, et les outils (effacement) passent par elle.
        self.bornee = bool(bornee and tout)
        self.cols_bacs = frozenset(cols_bacs) if self.bornee else frozenset()
        self.projets_bacs = frozenset(projets_bacs) if self.bornee else frozenset()
        self._ord = None
        # COL-4 — les BACS À SABLE dont on est (`bacs_a_sable`), ceux qu'on a ouverts
        # (`bacs_a_soi`, `projet.bac_a_sable_de` = son login), et les collections qu'on
        # atteint et qui vivent dans un bac à sable (`collections_bac`). Lus par `resoudre`.
        # Ils ne changent AUCUNE question ponctuelle (`peut_lire`, `peut_ecrire(c)`,
        # `clause_album`…) : dans son bac à sable, on travaille comme ailleurs. Ils retirent
        # des questions TRANSVERSES ce qu'un bac à sable donnerait hors de lui — écrire
        # « quelque part », être responsable d'un projet (S2 du cadrage). `hors_isoles` :
        # une portée « pour le corpus » (`pour_le_corpus`, S8), qui ne voit ni bac à sable ni
        # jeu.
        self.bacs_a_sable = frozenset(bacs_a_sable)
        self.bacs_a_soi = frozenset(bacs_a_soi) & self.bacs_a_sable if not tout \
            else frozenset(bacs_a_soi)
        self.collections_bac = frozenset(collections_bac)
        self.hors_isoles = hors_isoles
        # COL-3 — les projets dont on EST, et ceux qu'on GÈRE. Le responsable est membre :
        # cumulé ici pour la même raison que les niveaux, plus bas.
        self.projets_geres = frozenset(projets_geres)
        self.projets = frozenset(projets) | self.projets_geres
        # D10 (COL-3, tranche 3, Hugo, 2026-10-17) — la collection de BASE de chaque projet
        # dont on est, `bases` : des triplets (projet, collection, `acces_membres`) lus par
        # `bases_des_projets`. C'est la PREMIÈRE fois qu'être d'un projet ouvre une
        # collection — celle-là seule. DÉRIVÉE ici, avec les niveaux, et jamais recopiée
        # dans `collection_acces` : qui sort du projet sort de la collection, un responsable
        # rétrogradé cesse d'en être propriétaire, sans qu'aucune ligne soit à retirer.
        # Le responsable en est propriétaire, quelle que soit la position ; le membre y entre
        # au niveau choisi — `None`, la base protégée, ne lui ouvre RIEN, et un niveau
        # inconnu (base retouchée à la main) se dégrade en lecture, la seule erreur qui ne
        # s'aggrave pas. `pour_export` ne repasse pas `bases` : il réduit des ensembles déjà
        # dérivés, et les redériver rouvrirait à l'export ce que la case refuse.
        propriete, ecriture, lecture = set(propriete), set(ecriture), set(lecture)
        # F1 (COL-3, tranche 3c, Hugo, 2026-10-26) — le RESPONSABLE d'un projet LIT toutes ses
        # collections (`lues_par_le_projet`, lues par `collections_des_projets` pour les
        # projets qu'on gère, hors bacs à sable). Une LECTURE, ajoutée avant le cumul et
        # jamais à `ecriture` ni à `export` (la formule d'`export`, plus bas, réduit à la
        # lecture : elle n'ajoute rien) ; DÉRIVÉE comme la base, jamais recopiée : qui cesse
        # d'être responsable cesse de lire. `pour_export` et `pour_le_corpus` repassent les
        # ensembles déjà dérivés sans redériver.
        lecture |= set(lues_par_le_projet)
        for projet_id, collection_id, niveau in bases:
            if projet_id in self.projets_geres:
                propriete.add(collection_id)
            elif projet_id in self.projets:
                if niveau == ECRITURE:
                    ecriture.add(collection_id)
                elif niveau is not None:
                    lecture.add(collection_id)
        self.propriete = frozenset(propriete)
        # Les niveaux s'empilent : posséder implique écrire, écrire implique lire. On le
        # fait ICI, une fois, plutôt que dans chaque appelant — un `in self.ecriture` qui
        # oublierait les propriétaires serait un refus silencieux et parfaitement crédible.
        self.ecriture = frozenset(ecriture) | self.propriete
        self.lecture = frozenset(lecture) | self.ecriture
        # DROIT-2 — exporter est une capacité À CÔTÉ de l'échelle, pas un palier : les
        # propriétaires l'ont d'office (décider ce qui sort de sa collection engage la
        # collection autant que décider qui y entre), les autres par la case. Réduit à
        # la lecture, par ceinture : on ne sort pas ce qu'on ne voit pas, quoi que dise
        # une ligne en base.
        self.export = (frozenset(export) | self.propriete) & self.lecture
        self.utilisateur = utilisateur
        self.groupes = tuple(groupes)

    # -- la portée totale, bornée aux bacs à sable (COL-4) -------------------- #
    def couvre(self, collection_id) -> bool:
        """La portée TOTALE répond-elle pour cette collection ? Oui partout, sauf dans un
        bac à sable quand elle est bornée — là, seuls les ensembles ordinaires répondent."""
        return self.tout and not (self.bornee and collection_id in self.cols_bacs)

    def couvre_projet(self, projet_id) -> bool:
        """Le pendant de `couvre`, pour un projet."""
        return self.tout and not (self.bornee and projet_id in self.projets_bacs)

    def _ordinaire(self) -> "Portee":
        """La même personne SANS sa portée totale : ses ensembles ordinaires seuls — ce qui
        répond, pour une portée bornée, à l'intérieur des bacs à sable."""
        if self._ord is None:
            self._ord = Portee(lecture=self.lecture, ecriture=self.ecriture,
                               propriete=self.propriete, export=self.export,
                               projets=self.projets, projets_geres=self.projets_geres,
                               utilisateur=self.utilisateur, groupes=self.groupes,
                               bacs_a_sable=self.bacs_a_sable, bacs_a_soi=self.bacs_a_soi,
                               collections_bac=self.collections_bac)
        return self._ord

    def dans_les_bacs(self) -> "Portee":
        """La portée qui répond À L'INTÉRIEUR d'un bac à sable : elle-même, sauf pour une
        portée bornée, dont ce sont les ensembles ordinaires — pour les routes qui lisent
        `tout` directement et doivent, dans un bac à sable, le lire comme un arrivant."""
        return self._ordinaire() if self.bornee else self

    def _bornee_sur_album(self, alias: str, clause: tuple[str, list]) -> tuple[str, list]:
        """Une clause d'album d'une portée bornée : tout ce qui n'est PAS d'un bac à sable,
        plus ce que la clause ORDINAIRE (`clause`) ouvre — qui ne porte, ses ensembles étant
        restreints aux bacs à sable, que sur des albums de bac à sable.

        Un `CASE` et non `NOT EXISTS (…) OR (…)`, pour le même sens : dans une COLONNE du
        `SELECT` (`destructible` de `GET /api/albums`), SQLite calcule les deux opérandes
        d'un `OR`, et la clause ordinaire — le journal, pour `clause_suppression_directe` —
        l'était pour chaque album du vrai corpus, où le premier suffit (mesuré : 186 ms au
        lieu de 22 sur 150 albums). `CASE` n'évalue que la branche retenue. Le résultat est
        le même ligne à ligne, `NULL` compris : `EXISTS` n'est jamais `NULL`, et la branche
        `THEN` rend la clause ordinaire telle qu'un `FALSE OR` la rendait."""
        sql, params = clause
        return (f"(CASE WHEN EXISTS (SELECT 1 FROM albums _bba WHERE _bba.id = {alias} "
                f"AND {sql_est_bac_a_sable(sql_projet_d_album('_bba'))}) "
                f"THEN ({sql}) ELSE 1 END)", params)

    # -- décisions ponctuelles ---------------------------------------------- #
    def peut_lire(self, collection_id: int) -> bool:
        return self.couvre(collection_id) or collection_id in self.lecture

    def peut_ecrire(self, collection_id: int) -> bool:
        return self.couvre(collection_id) or collection_id in self.ecriture

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
        return ((self.admin and not (self.bornee and collection_id in self.cols_bacs))
                or collection_id in self.propriete)

    def peut_exporter(self, collection_id: int) -> bool:
        """A-t-on le droit de SORTIR le contenu de cette collection — un fichier qui
        quitte l'instance pour un poste qu'elle ne contrôle plus ?  DROIT-2.

        Lire n'y suffit plus : télécharger n'est pas travailler dans l'instance, c'est
        sortir, et la base légale du corpus n'est pas établie (DEPOT-1). Écrire n'y
        suffit pas davantage — exporter ne s'ordonne pas avec annoter. L'administrateur
        passe outre comme partout, et le mono-poste aussi : sans proxy, il n'y a
        personne à qui refuser."""
        return self.couvre(collection_id) or collection_id in self.export

    def peut_exporter_quelque_part(self) -> bool:
        """A-t-on le droit d'exporter, où que ce soit ? Sert aux exports qui traversent
        plusieurs collections (Recherche, Exploration) : sans aucun droit, le fichier
        serait vide, et un refus qui dit pourquoi vaut mieux qu'un fichier qui se tait.

        COL-4 (S2, S8) — un BAC À SABLE n'y compte pas : les exports qui traversent les
        collections ne le voient pas (`pour_le_corpus`), et son propriétaire, qui l'exporte
        d'office, recevrait sinon un fichier vide au lieu du refus de qui n'exporte rien."""
        return self.tout or bool(self.export - self.collections_bac)

    def pour_export(self) -> "Portee":
        """La même personne, réduite à ce qu'elle peut SORTIR.  DROIT-2.

        Un export qui traverse plusieurs collections filtre par le droit d'exporter et
        non par celui de lire — sans quoi qui exporte A emporterait le texte de B dans
        une concordance qui couvre les deux. Plutôt qu'une clause de plus que chaque cœur
        devrait apprendre à recevoir, une Portee de plus : `clause_album`,
        `clause_terme` et les accesseurs gardés la consomment telle quelle, et la règle
        reste écrite ici."""
        if self.tout:
            return self
        return Portee(admin=self.admin, lecture=self.export,
                      ecriture=self.ecriture & self.export,
                      propriete=self.propriete & self.export, export=self.export,
                      projets=self.projets, projets_geres=self.projets_geres,
                      utilisateur=self.utilisateur, groupes=self.groupes,
                      bacs_a_sable=self.bacs_a_sable, bacs_a_soi=self.bacs_a_soi,
                      collections_bac=self.collections_bac, hors_isoles=self.hors_isoles)

    def pour_le_corpus(self) -> "Portee":
        """La même personne, sans les BACS À SABLE ni le JEU — ce que voient les surfaces
        qui traversent les projets : la Recherche, l'Exploration, leurs exports, l'accord
        modèle↔humain et inter-annotateurs, le lexique (COL-4, S8 ; Q4, Hugo, 2026-10-21 :
        « pour personne, d'ici la tranche 4 »). Les mesures du corpus restent celles du vrai
        corpus : soixante-quinze copies du jeu ne s'y comptent pas.

        Le patron de `pour_export` : une Portee de plus plutôt qu'une clause que chaque cœur
        devrait apprendre. Pour une portée ordinaire, les collections des bacs à sable
        sortent de ses ensembles ; pour une portée TOTALE, qui ne matérialise aucun
        ensemble, `hors_isoles` fait écarter par `clause_album` et `clause_terme` ce qui vit
        dans un projet isolé — la nature du projet, jamais la portée, tient l'isolement."""
        if self.tout:
            # Sans ses bacs à sable : ce qui s'y lit (ses personnages, par
            # `socle._clause_personnage`) ne doit pas entrer dans les chiffres du corpus —
            # aveugles aux bacs pour tout le monde (contre-relecture, D1).
            return Portee(tout=True, admin=self.admin, utilisateur=self.utilisateur,
                          groupes=self.groupes, hors_isoles=True)
        cb = self.collections_bac
        return Portee(admin=self.admin, lecture=self.lecture - cb,
                      ecriture=self.ecriture - cb, propriete=self.propriete - cb,
                      export=self.export - cb, projets=self.projets - self.bacs_a_sable,
                      projets_geres=self.projets_geres - self.bacs_a_sable,
                      utilisateur=self.utilisateur, groupes=self.groupes,
                      hors_isoles=True)

    # -- le bac à sable (COL-4) ------------------------------------------------ #
    def peut_ouvrir_un_bac_a_sable(self) -> bool:
        """Peut-on ouvrir SON bac à sable — un projet à soi, dont on est responsable ?
        COL-4 (S1 du cadrage ; Hugo, 2026-10-21).

        Une question NEUVE, et non un trou dans `peut_decider_des_projets`, qui garde son
        sens — décider quels projets existent reste à la portée totale. Un login, derrière le
        proxy : un compte ordinaire comme un administrateur (Hugo, 2026-10-22 : il en a un
        aussi). Ni le mono-poste — sans login, il n'y a ni « mien » ni personne à inviter —,
        ni une requête sans identité (portée vide). Le compte PARTAGÉ en a un aussi (Hugo,
        2026-10-24, qui renverse S1 : le travail d'un bac à sable n'a aucune valeur, et rien
        n'en sort) : la question ne lit pas la nature d'un compte."""
        return bool(AUTH_PROXY) and bool(self.utilisateur)

    def _ecriture_hors_bac(self) -> frozenset:
        """Les collections où l'on écrit, hors des bacs à sable."""
        return self.ecriture - self.collections_bac

    # -- les projets (COL-3) -------------------------------------------------- #
    def est_du_projet(self, projet_id: int) -> bool:
        """Est-on MEMBRE de ce projet ? Ce que cela permet : y créer une collection, et
        entrer dans sa collection de BASE au niveau que le projet a choisi (D10, dérivé
        dans `__init__`). Ce que cela ne permet pas, au simple membre : lire aucune AUTRE de
        ses collections — son RESPONSABLE les lit toutes (F1, tranche 3c)."""
        return self.couvre_projet(projet_id) or projet_id in self.projets

    def peut_creer_collection(self, projet_id: int, *, membres_creent: bool,
                              bac_a_sable: bool) -> bool:
        """Peut-on CRÉER une collection dans ce projet ?  COL-3, tranche 3b (Hugo,
        2026-10-21) — RENVERSEMENT daté d'AUTH-3 (« créer une collection exige une
        IDENTITÉ, pas un droit ») : une collection est une étude, un cercle d'accès, une
        unité de dépôt, et en ouvrir une dans un projet est décider de ce qu'il contient.

        Le RESPONSABLE du projet, et la portée totale (l'administrateur, le mono-poste) :
        toujours. Un MEMBRE : seulement si le projet le leur ouvre (`membres_creent`, le
        réglage de `projet.membres_creent_collections`, NON par défaut). Qui n'est pas du
        projet : jamais — le projet de REPLI compris, où il suffisait d'une identité ; sans
        responsable, seul un administrateur y crée désormais.

        Un BAC À SABLE n'est pas touché (`bac_a_sable`) : son propriétaire en est le
        responsable, ses invités y créent comme avant — le travail n'y a aucune valeur, et
        il s'efface chaque lundi.

        Les deux faits sont lus par l'appelant sur la ligne du projet ; la règle est ici. Une
        portée totale BORNÉE crée dans un bac à sable comme un arrivant (`couvre_projet`)."""
        if self.couvre_projet(projet_id) or projet_id in self.projets_geres:
            return True
        return projet_id in self.projets and (membres_creent or bac_a_sable)

    def peut_gerer_projet(self, projet_id: int) -> bool:
        """A-t-on le droit de régler QUI est de ce projet — faire entrer, faire sortir,
        nommer un autre responsable ?

        La forme est celle de `peut_administrer`, un étage plus haut : le responsable, ou
        l'administrateur qui passe outre, et c'est écrit pour la même raison — un projet
        peut naître sans responsable, et son dernier peut partir."""
        return ((self.admin and not (self.bornee and projet_id in self.projets_bacs))
                or projet_id in self.projets_geres)

    def peut_decider_des_projets(self) -> bool:
        """A-t-on le droit de décider QUELS projets existent — en créer un, le renommer,
        le supprimer ?

        Une portée TOTALE seulement : l'administrateur, et le mono-poste. Gérer un projet
        n'est pas l'instituer — un responsable règle qui entre dans le SIEN, il ne décide
        ni de son nom ni de son existence. La question ne prend pas d'identifiant, et c'est
        son sens : elle ne dépend d'aucun projet en particulier."""
        return self.tout

    def clause_projet(self, alias: str = "p.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id de projet) aux projets qu'on peut
        NOMMER. Même contrat que `clause_album` : `(sql, params)`, `alias` écrit par le
        code appelant.

        Deux moitiés. Les projets dont on est membre ; et ceux d'une collection qu'on
        LIT, même sans en être — la visibilité DÉRIVÉE. La seconde n'est pas une largesse :
        un accès de collection posé avant la tranche 3c sans être du projet (la v38 en fait
        un membre, F2 ; une base retouchée à la main peut en porter encore) doit pouvoir lire
        le nom du projet où il travaille. Le lui cacher donnerait à l'écran une collection
        sans projet.

        Ce que la clause ne donne pas : le droit de voir QUI est du projet, ni ses autres
        collections. Elle ne dit que le nom."""
        if self.tout:
            if self.bornee:                     # COL-4 : aucun bac à sable d'un autre
                o, p = self._ordinaire().clause_projet(alias)
                return (f"({alias} NOT IN (SELECT _bbp.id FROM projet _bbp "
                        f"WHERE _bbp.bac_a_sable_de IS NOT NULL) OR {o})", p)
            return "1", []
        morceaux, params = [], []
        if self.projets:
            ids = sorted(self.projets)
            morceaux.append(f"{alias} IN ({', '.join('?' * len(ids))})")
            params += ids
        if self.lecture:
            ids = sorted(self.lecture)
            morceaux.append(
                f"EXISTS (SELECT 1 FROM collection c WHERE {sql_projet_de('c')} = {alias} "
                f"AND c.id IN ({', '.join('?' * len(ids))}))")
            params += ids
        if not morceaux:
            return "0", []                      # ni projet ni collection : aucun nom
        return "(" + " OR ".join(morceaux) + ")", params

    # -- filtrage des requêtes ---------------------------------------------- #
    def clause_album(self, alias: str = "a.id", *, ecriture: bool = False) -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux albums autorisés.

        Renvoie `(sql, params)` à insérer dans un `WHERE`. `alias` est un morceau de SQL
        écrit par le code appelant, JAMAIS une valeur venue du client — les seuls
        paramètres liés sont les ids de collection, qui sortent de la base.

        On filtre par `EXISTS` sur les collections plutôt que par une liste d'albums :
        les collections sont peu nombreuses et les albums peuvent ne pas l'être. La liste
        d'ids reste donc courte quel que soit le corpus.

        COL-4 — en ÉCRITURE, jamais une copie de référence du JEU, quelle que soit la
        portée : le jeu ne se change que par son outil (`tools/preparer_jeu.py`), et ce
        qu'on y changerait passerait dans chaque bac à sable créé ensuite. Les accesseurs
        gardés disent alors pourquoi (409 nommé, `socle._refuser_la_reference`).
        """
        if ecriture:
            sql, params = self._clause_album(alias, ecriture=True)
            return (f"({sql} AND NOT EXISTS (SELECT 1 FROM albums _jxa WHERE _jxa.id = "
                    f"{alias} AND {sql_est_jeu(sql_projet_d_album('_jxa'))}))", params)
        return self._clause_album(alias, ecriture=False)

    def _clause_album(self, alias: str, *, ecriture: bool) -> tuple[str, list]:
        if self.tout:
            if self.hors_isoles:                # COL-4, S8 : `pour_le_corpus`
                return (f"NOT EXISTS (SELECT 1 FROM albums _hia WHERE _hia.id = {alias} "
                        f"AND {sql_album_isole('_hia')})", [])
            if self.bornee:
                return self._bornee_sur_album(
                    alias, self._ordinaire()._clause_album(alias, ecriture=ecriture))
            return "1", []
        ids = sorted(self.ecriture if ecriture else self.lecture)
        if not ids:
            return "0", []                      # aucune collection : rien n'est visible
        marques = ", ".join("?" * len(ids))
        return (f"EXISTS (SELECT 1 FROM collection_album ca "
                f"WHERE ca.album_id = {alias} AND ca.collection_id IN ({marques}))",
                list(ids))

    def clause_suppression_directe(self, alias: str = "a.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux albums qu'on peut SUPPRIMER
        DÉFINITIVEMENT sans rien demander. COL-3, tranche 2 (Hugo, 2026-10-11), RENVERSÉE le
        2026-10-21 (tranche 3b), puis SIMPLIFIÉE le 2026-10-26 (tranche 3c, F3 : « qui tient
        l'espace efface, les autres demandent »). Le RAMENER à un cran (« repartir de
        zéro », E8) — et supprimer l'une de ses PLANCHES (Q5) — suit les mêmes chemins sans
        la règle de la dernière copie : `clause_repartir_directe`.

        « Supprimer » a deux réponses. Supprimer DE LA COLLECTION ne détruit rien : la
        copie part au fonds avec son travail, et c'est le geste de qui écrit dans la
        collection. Effacer détruit le travail — et, pour une suppression, les images
        qu'aucune autre planche n'emploie.

        Qui TIENT l'espace efface sans rien demander — un compte PARTAGÉ jamais, hors de son
        bac à sable (F7) :

        1. le PROPRIÉTAIRE de TOUTES les collections où vit l'album, même si d'autres y ont
           travaillé ;
        2. le RESPONSABLE du projet de l'album, sur tout album RANGÉ de son projet — une
           copie gardée au fonds reste à l'administrateur (Q12) ;
        3. l'ADMINISTRATEUR et le mono-poste (la portée totale) : le recours d'une demande ;
        4. dans un BAC À SABLE, quiconque y écrit — invité compris, son import ou non —, et
           son propriétaire (Q4, Hugo, 2026-10-26 : « le bac à sable n'a pas d'importance ») ;
           rien ne s'y demande. Le compte partagé y efface comme les autres (COL-4).

        La protection du travail des membres passe par la VISIBILITÉ, pas par la
        permission : l'écran dit qui perd quoi avant d'effacer (`GET
        /api/albums/{id}/travail-des-autres`), et le journal qui l'a fait. Le CRÉATEUR d'une
        copie n'a plus de chemin à lui (F3) : il demande, comme tout annotateur, et le
        journal ne DÉCIDE plus rien — il ne sert qu'à montrer.

        La DERNIÈRE copie d'un document — aucune autre copie vivante hors d'un projet isolé
        — ne se supprime que par un administrateur, gardien du fonds : la supprimer fait
        sortir le document du fonds commun, images comprises. Ni le propriétaire ni le
        responsable ne la prennent. La règle n'a pas cours dans un projet ISOLÉ (un bac à
        sable, le jeu) : rien n'en sort vers le fonds commun.

        Ce que la réponse ne dit pas, et c'est voulu : LEQUEL des chemins manque. Le refus
        est le même dans tous les cas (`socle._MOTIF_DESTRUCTION`)."""
        return self._clause_effacement(alias, derniere_copie_gardee=True)

    def clause_repartir_directe(self, alias: str = "a.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux albums qu'on peut RAMENER à
        un cran sans rien demander — « repartir de zéro », sur l'album ou l'une de ses
        planches (E8, COL-3, tranche 3b) —, ou dont on peut SUPPRIMER une planche (Q5, Hugo,
        2026-10-26 : une planche n'est pas le document, qui reste au fonds).

        Les chemins de `clause_suppression_directe`, tels quels — le propriétaire de toutes
        les collections, le responsable du projet, la portée totale, quiconque écrit dans un
        bac à sable, jamais un compte partagé hors de son bac à sable —, SANS la règle de la
        dernière copie : repartir garde les images, la notice et les planches, rien ne sort
        du fonds commun (le pilotage, 2026-10-25 ; Q6).

        Plus large que la suppression, jamais plus étroite : qui peut supprimer peut
        repartir. C'est aussi la borne de « qui perd quoi » (`GET
        /api/albums/{id}/travail-des-autres`), qui sert les deux gestes."""
        return self._clause_effacement(alias, derniere_copie_gardee=False)

    def _clause_effacement(self, alias: str, *,
                           derniere_copie_gardee: bool) -> tuple[str, list]:
        """Les chemins de l'effacement sans demande, communs à la suppression et à
        « repartir de zéro » ; `derniere_copie_gardee` dit si la dernière copie d'un
        document en est exclue (la suppression) ou non (repartir, une planche).

        Aucune branche ne lit le journal depuis la tranche 3c : une disjonction simple, sans
        le `CASE` qui gardait le travail d'autrui pour la fin (`tests/test_cout_des_clauses.py`
        le vérifie par un témoin)."""
        if self.tout:
            if self.bornee:
                return self._bornee_sur_album(
                    alias, self._ordinaire()._clause_effacement(
                        alias, derniere_copie_gardee=derniere_copie_gardee))
            return "1", []
        if not self.utilisateur:
            return "0", []
        morceaux, params = [], []
        # COL-4 (S5), élargi par Q4 (Hugo, 2026-10-26) — dans un bac à sable, son
        # PROPRIÉTAIRE efface tout album, et QUICONQUE Y ÉCRIT efface ceux où il écrit :
        # invité compris, compte PARTAGÉ compris. Rien ne s'y demande, le lundi efface tout.
        if self.bacs_a_soi:
            ids = sorted(self.bacs_a_soi)
            morceaux.append(
                f"EXISTS (SELECT 1 FROM albums _sbs WHERE _sbs.id = {alias} "
                f"AND {sql_projet_d_album('_sbs')} IN ({', '.join('?' * len(ids))}))")
            params += ids
        ecrit_bac = sorted(self.ecriture & self.collections_bac)
        if ecrit_bac:
            morceaux.append(
                f"EXISTS (SELECT 1 FROM collection_album _sbe WHERE _sbe.album_id = {alias} "
                f"AND _sbe.collection_id IN ({', '.join('?' * len(ecrit_bac))}))")
            params += ecrit_bac
        tient, p_tient = self._sql_tient_l_album(
            alias, derniere_copie_gardee=derniere_copie_gardee)
        if tient != "0":
            morceaux.append(f"({tient} AND NOT EXISTS (SELECT 1 FROM utilisateur _su "
                            "WHERE _su.login = ? AND _su.nature = ?))")
            params += [*p_tient, self.utilisateur, NATURE_COLLECTIF]
        if not morceaux:
            return "0", []
        return f"({' OR '.join(morceaux)})", params

    def _sql_tient_l_album(self, alias: str, *,
                           derniere_copie_gardee: bool = True) -> tuple[str, list]:
        """Qui TIENT l'album hors d'un bac à sable (F3), hors du compte partagé que
        l'appelant ajoute : on POSSÈDE chacune des collections où vit l'album, ou l'on est
        RESPONSABLE de son projet et l'album y est RANGÉ (une copie gardée au fonds reste à
        l'administrateur, Q12) — et, pour une suppression (`derniere_copie_gardee`), l'album
        n'est pas la DERNIÈRE copie de son document au fonds commun ; repartir de zéro ne lit
        pas cette moitié. `"0"` quand on ne possède ni ne gère rien.

        Hors des bacs à sable, des deux côtés : une collection de bac à sable ne compte pas
        dans ce qu'on possède, un bac à sable dans ce qu'on gère — ils ont leurs chemins à
        eux. La moitié « toutes » est accompagnée d'un `EXISTS` : seule, elle serait vraie
        d'une copie rangée nulle part. « Dernière copie » : aucune AUTRE copie vivante du
        même document hors d'un projet isolé — une copie du jeu ou d'un bac à sable, qui part
        avec lui, ne garde pas un document au fonds commun."""
        morceaux, params = [], []
        possede = sorted(self.propriete - self.collections_bac)
        if possede:
            marques = ", ".join("?" * len(possede))
            morceaux.append(
                f"(EXISTS (SELECT 1 FROM collection_album _tc WHERE _tc.album_id = {alias}) "
                f"AND NOT EXISTS (SELECT 1 FROM collection_album _tc2 "
                f"WHERE _tc2.album_id = {alias} AND _tc2.collection_id NOT IN ({marques})))")
            params += possede
        geres = sorted(self.projets_geres - self.bacs_a_sable)
        if geres:
            morceaux.append(
                f"EXISTS (SELECT 1 FROM albums _tg WHERE _tg.id = {alias} "
                f"AND {sql_projet_d_album('_tg')} IN ({', '.join('?' * len(geres))}) "
                f"AND EXISTS (SELECT 1 FROM collection_album _tgc "
                f"WHERE _tgc.album_id = _tg.id))")
            params += geres
        if not morceaux:
            return "0", []
        if not derniere_copie_gardee:
            return f"({' OR '.join(morceaux)})", params
        return f"(({' OR '.join(morceaux)}) AND {_sql_une_soeur(alias)})", params

    def peut_tenir_le_fonds(self) -> bool:
        """A-t-on le droit de tenir le FONDS — le voir, rendre une copie gardée, répondre
        aux demandes, importer un document sans passer par une collection ?  COL-3.

        Une portée TOTALE seulement : l'administrateur, et le mono-poste. Le fonds est tout
        ce que l'instance détient, y compris ce qu'aucune collection n'appelle plus — le
        montrer à quelqu'un d'autre décrirait des études hors de sa portée. Un responsable
        de projet n'en lit que la NOTICE, par une question à part
        (`peut_lire_les_notices`, tranche 3). La question ne prend pas d'identifiant : la
        forme de `peut_decider_des_projets`. Elle répond aussi des demandes, à une
        exception près : un `rejoindre` se consent par le propriétaire
        (`peut_repondre_a`)."""
        return self.tout

    # -- le fonds et les copies (COL-3, tranche 3) ---------------------------- #
    def peut_lire_les_notices(self) -> bool:
        """Peut-on parcourir les NOTICES du fonds — titre, série, auteur, et rien d'autre ?
        COL-3, tranche 3 (case « La consultation du fonds est tranchée contre le
        cloisonnement », Hugo, 2026-10-09 ; D3, 2026-10-17).

        Une portée totale, et quiconque est RESPONSABLE d'un projet : c'est lui qui demande
        les documents qu'il veut faire entrer dans son projet, et il ne peut pas les demander
        sans les voir. La question ne prend pas d'identifiant : une notice appartient à
        l'instance dès l'import, pas à un projet. Un écrivain qui n'est responsable de rien
        ne lit pas les notices — il ne puise que dans ce qu'il LIT déjà (D3) : ouvrir les
        notices de toute l'instance à chaque annotateur serait plus large que ce qui a été
        confirmé.

        Ce que la question n'ouvre PAS, et que la route doit tenir par une requête à elle
        (`GET /api/fonds/notices`, colonnes nommées) : ni images, ni travail, ni qui a
        importé, ni les copies, leurs projets ou leurs collections, ni la demande qui
        attend, ni le nombre de planches. Le fonds entier reste à `peut_tenir_le_fonds`.

        COL-4 (S2) — être responsable de son BAC À SABLE n'y compte pas : chaque compte en
        ouvrirait un, et les notices de tout le fonds s'ouvriraient à soixante-quinze
        comptes d'un coup. Seuls comptent les projets ordinaires."""
        return self.tout or bool(self.projets_geres - self.bacs_a_sable)

    def clause_rejoindre_directe(self, alias: str = "a.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux copies qu'on peut REJOINDRE
        sans rien demander — les ranger dans une collection de plus. COL-3, tranche 3 (D4,
        Hugo, 2026-10-17, sous sa forme STRICTE).

        Rejoindre un travail, c'est le PARTAGER : la collection d'arrivée verra la copie, et
        tout ce qu'on y fera se verra des deux côtés. C'est la décision de qui tient le
        travail, pas de qui l'annote — la séparation d'AUTH-3, « administrer n'est pas
        écrire ». D'où deux moitiés, toutes deux nécessaires :

        - on LIT la copie (`clause_album`) : rejoindre ne s'offre que sur un travail qu'on
          voit ;
        - on ADMINISTRE CHACUNE des collections où elle vit — la forme de
          `_sql_tient_l_album` (« toutes ses collections »). Le
          propriétaire, y compris par la dérivation de la collection de BASE (un responsable
          du projet en est propriétaire) ; `bd-admins` par `peut_administrer`. Une
          collection SANS propriétaire n'est donc tenue que par la portée totale : personne
          d'autre n'y consent.

        Écrire dans la collection d'ARRIVÉE est la troisième condition, et elle reste à la
        route (`peut_ecrire`), qui la vérifie avant tout : sans elle on déposerait son
        travail chez quelqu'un d'autre. Le rangement ne TRAVERSE pas les projets
        (`database.rangement_traverse`) — rejoindre ne se fait que DANS un projet.

        Hors de là, rejoindre se DEMANDE (`database.DEMANDE_REJOINDRE`), et c'est
        `peut_repondre_a` qui dit qui y consent. Plus strict qu'avant la tranche 3, où
        écrire des deux côtés suffisait, et c'est voulu : ranger chez soi retirait aux autres
        la suppression directe (`AUTH-10`) sans qu'ils l'aient décidé.

        La moitié « toutes » seule serait vraie d'une copie rangée nulle part — gardée au
        fonds — et l'ouvrirait à quiconque ; la moitié « lire » la referme, puisqu'une copie
        gardée n'est lue que par la portée totale."""
        if self.tout:
            if self.bornee:
                return self._bornee_sur_album(
                    alias, self._ordinaire().clause_rejoindre_directe(alias))
            return "1", []
        lire, p_lire = self.clause_album(alias)
        if lire == "0":
            return "0", []
        if self.admin:
            return lire, p_lire
        ids = sorted(self.propriete)
        if not ids:
            return "0", []
        marques = ", ".join("?" * len(ids))
        return (f"({lire} AND NOT EXISTS (SELECT 1 FROM collection_album _rj "
                f"WHERE _rj.album_id = {alias} AND _rj.collection_id NOT IN ({marques})))",
                [*p_lire, *ids])

    def peut_repondre_a(self, demande) -> bool:
        """Peut-on RÉPONDRE à cette demande — l'accepter, ou la refuser ?  COL-3, tranche 3.

        `demande` : un dict (ou une ligne) qui porte `genre`, et pour un `rejoindre`
        `collections`, les collections où vit AUJOURD'HUI la copie qu'il vise — un fait que
        l'appelant relève en base, sous le verrou, au moment de répondre ; la règle est ici.

        Par genre. Une suppression (document ou projet), une entrée de documents et le
        retour d'une copie gardée au fonds (`DEMANDE_RENDRE`) : qui tient le fonds
        (`peut_tenir_le_fonds`), comme jusqu'ici — une copie gardée ne se lit que par lui. Un `rejoindre` : qui
        ADMINISTRE CHACUNE des collections où vit la copie (D4 stricte — le propriétaire de
        chacune consent ; le même test que `clause_rejoindre_directe`, posé sur qui répond),
        ou la portée totale, en recours. C'est la première demande à laquelle répond
        quelqu'un qui ne tient pas le fonds (D11 : là où vit qui consent). Une demande d'EN
        PARTIR (`DEMANDE_AMORCER`, tranche 3b, E4) suit la même règle, sur les collections
        où vit la copie SOURCE : copier son travail ailleurs le fait lire par d'autres,
        comme le partager (`GENRES_CONSENTIS`).

        Une copie qui n'est plus rangée nulle part — sortie au fonds depuis la demande — n'a
        plus de propriétaire pour consentir : seule la portée totale y répond. Une copie
        partagée entre deux collections de deux propriétaires différents ne se rejoint que
        par qui possède les deux, ou par un administrateur : la forme stricte de D4 lue
        comme le consentement de CHAQUE collection, tenu par une seule réponse.

        Une demande d'en partir ENTRE DEUX PROJETS (`DEMANDE_AMORCER_ENTRE_PROJETS`, E7,
        tranche 3b) ne nomme aucune copie : `projets`, les projets qui TIENNENT aujourd'hui
        le travail demandé (`database.projets_qui_tiennent`, relevé par l'appelant sous le
        verrou). Le RESPONSABLE de l'un d'eux y répond — c'est son travail qui sortirait du
        projet (« qui autorise qu'on amorce depuis son travail », Hugo, 2026-10-09) —, et la
        portée totale en recours, la seule quand aucun projet ne le tient. Être MEMBRE d'un
        projet source, posséder une de ses collections : rien de cela n'y suffit.

        Ce que la question ne dit pas, et c'est à la route : quoi répondre à qui ne peut pas
        répondre — un 403 nommé sur le droit, avant l'objet, à qui n'administre rien ; un
        404 à qui ne lit pas la copie visée."""
        if demande["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS:
            if self.tout:
                return True
            return any(self.peut_gerer_projet(p) for p in demande.get("projets") or ())
        if demande["genre"] in GENRES_CONSENTIS:
            if self.tout:
                return True
            collections = list(demande["collections"] or ())
            return bool(collections) and all(self.peut_administrer(c) for c in collections)
        return self.peut_tenir_le_fonds()

    def peut_nommer_le_demandeur(self, demandeur, *, consentement=None) -> bool:
        """Peut-on lire QUI a demandé une suppression ?  COL-3, tranche 2 (Hugo,
        2026-10-15).

        Une portée totale — l'administrateur, qui y répond, et le mono-poste —, et la
        personne elle-même. Tout autre lecteur de l'album voit QU'une suppression est
        demandée, jamais par qui. C'est une question de cloisonnement : un album vit dans
        plusieurs collections, et la ligne d'un album se lit par n'importe laquelle. Une
        personne qui n'écrit que dans l'Incubateur, et y demande la suppression d'un album
        partagé, aurait été nommée aux lectrices du corpus principal — plus qu'« une autre
        collection, jamais laquelle », seule révélation qu'AUTH-10 accepte.

        Le login seul en décide, jamais le nom lisible : deux personnes peuvent porter le
        même nom d'affichage.

        COL-3, tranche 3 — `consentement` : une demande qui attend le CONSENTEMENT de
        l'appelant, un `rejoindre` (`genre`, et `collections` où vit la copie visée, comme
        pour `peut_repondre_a`). Celui qui administre l'une de ces collections lit qui
        demande : on ne consent pas à partager un travail avec quelqu'un dont on ignore le
        nom — ce que le cadrage de la tranche a accepté par écrit, dans le même projet, le
        rangement ne traversant pas les projets. De même pour une demande d'en partir
        (tranche 3b), dans le projet.

        Entre deux projets (E7) : le responsable d'un projet qui TIENT le travail demandé
        (`consentement["projets"]`, comme pour `peut_repondre_a`) lit qui demande, et le nom
        du projet d'arrivée — accepté par écrit au cadrage : on ne laisse pas partir son
        travail vers quelqu'un qu'on ne connaît pas."""
        if self.tout:
            return True
        if (consentement is not None
                and consentement["genre"] == DEMANDE_AMORCER_ENTRE_PROJETS
                and any(self.peut_gerer_projet(p) for p in consentement.get("projets") or ())):
            return True
        if (consentement is not None and consentement["genre"] in GENRES_CONSENTIS
                and any(self.peut_administrer(c) for c in consentement["collections"] or ())):
            return True
        return bool(self.utilisateur) and demandeur == self.utilisateur

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
            if self.hors_isoles:                # COL-4, S8 : `pour_le_corpus`
                return (f"({alias} IS NULL OR {alias} NOT IN (SELECT _hic.id FROM collection "
                        f"_hic WHERE {sql_est_isole(sql_projet_de('_hic'))}))", [])
            if self.bornee:                     # COL-4 : les termes des bacs d'autrui
                o, p = self._ordinaire().clause_terme(alias)
                return (f"({alias} NOT IN (SELECT _bbc.id FROM collection _bbc WHERE "
                        f"{sql_est_bac_a_sable(sql_projet_de('_bbc'))}) OR {o})", p)
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
        if self.tout and (collection_id is None or self.couvre(collection_id)):
            return True
        if self.tout:                           # COL-4 : un terme d'un bac à sable
            return collection_id in self.ecriture
        if collection_id is None:
            # COL-4 (S2) — écrire dans son bac à sable ne fait pas modifier le vocabulaire
            # GLOBAL : il survivrait à l'effacement, chez tout le monde.
            return bool(self._ecriture_hors_bac())
        return collection_id in self.ecriture

    def peut_remanier_tag(self, collection_id) -> bool:
        """A-t-on le droit de REMANIER ce tag — le renommer, le fusionner dans un autre, ou
        le supprimer alors que des régions le portent ?  ANN-8 (Hugo, 2026-10-22).

        Modifier un terme (`peut_ecrire_terme`) documente sa définition, sa note, sa portée.
        Le remanier change ce que portent des régions annotées par d'autres : le nom sous
        lequel ils l'ont posé, ou sa présence même. La question suit donc la PORTÉE du tag,
        et non le droit d'écrire. Un tag LOCAL se remanie par le propriétaire de sa
        collection (`peut_administrer`, qui laisse passer l'administrateur) ; un tag GLOBAL
        par la portée totale seule — l'administrateur, et le mono-poste —, personne ne le
        possédant en propre alors que tout le monde l'emploie.

        Supprimer un tag que plus aucune région ne porte n'est PAS remanier : rien de ce
        que d'autres ont posé ne change, et la question est celle de `peut_ecrire_terme`.

        Ce que la question ne dit pas, et que la route doit tenir à part : un tag local
        peut être POSÉ hors de sa collection — sur une région d'un album rangé ailleurs,
        par qui lit la collection du tag et écrit dans celle de l'album. Remanier en
        retirerait le tag là où l'appelant n'écrit pas ; seule une portée totale le fait
        (cf. `routes/lexique.py`). Mesure d'attente : les grilles d'ANN-7 reprendront la
        question."""
        if self.tout and (collection_id is None or self.couvre(collection_id)):
            return True
        if collection_id is None:
            return False
        return self.peut_administrer(collection_id)

    def clause_grille(self, alias: str = "g.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id de grille) aux grilles dont on peut LIRE
        LE PLAN publié — ou vivant, pour une grille ouverte. ANN-7, tranche 1 (cadrage R8 ;
        §10 de la note, tranché le 2026-10-14 ; G5, Hugo, 2026-10-25). Même contrat que
        `clause_album` : `(sql, params)`, `alias` écrit par le code appelant.

        Une grille non partagée est un travail de recherche, et son seul plan peut révéler
        une étude en cours — la question de `clause_terme`, un étage plus haut. Trois moitiés,
        chacune nécessaire à un public :

        - (a) être MEMBRE du projet qui possède la grille (G5) — responsable compris : un
          membre d'une base protégée prépare l'étude sans lire encore d'album —, dès qu'elle a
          une version PUBLIÉE ou VIVANTE : une grille qui n'est qu'un brouillon n'existe pas
          pour lui, pas même son nom (relecture croisée, constat 4) ;
        - (b) LIRE un album d'un projet où la grille est ACTIVE (§10) : un annotateur qui a un
          accès de collection sans être du projet doit lire la grille qu'il applique ;
        - (c) LIRE un album qui porte un relevé de la grille (G5), même désactivée : sans quoi
          désactiver rendrait illisible le sens des relevés qui restent « en lecture ».

        Le BROUILLON n'en relève pas : il reste chez ses auteurs (`peut_gerer_projet`, à la
        route) — une grille sans autre version, jusqu'à son nom ; (b) et (c) supposent une
        activation, donc une version publiée. Une portée totale lit tout, BORNÉE hors des
        bacs à sable des autres (COL-4, le patron de `clause_projet`)."""
        if self.tout:
            if self.bornee:
                o, p = self._ordinaire().clause_grille(alias)
                return (f"(NOT EXISTS (SELECT 1 FROM grille _bbg WHERE _bbg.id = {alias} AND "
                        f"{sql_est_bac_a_sable('_bbg.projet_id')}) OR {o})", p)
            return "1", []
        morceaux, params = [], []
        if self.projets:
            ids = sorted(self.projets)
            morceaux.append(f"EXISTS (SELECT 1 FROM grille _ga WHERE _ga.id = {alias} "
                            f"AND _ga.projet_id IN ({', '.join('?' * len(ids))}) "
                            "AND EXISTS (SELECT 1 FROM grille_version _gav "
                            "WHERE _gav.grille_id = _ga.id AND _gav.etat IN (?, ?)))")
            params += [*ids, ETAT_VERSION_PUBLIEE, ETAT_VERSION_VIVANTE]
        lire, p_lire = self.clause_album("_gab.id")
        if lire != "0":
            morceaux.append(
                f"EXISTS (SELECT 1 FROM projet_grille _gpg JOIN albums _gab "
                f"ON {sql_projet_d_album('_gab')} = _gpg.projet_id "
                f"WHERE _gpg.grille_id = {alias} AND {lire})")
            params += p_lire
            lire_r, p_lire_r = self.clause_album("_grp.album_id")
            morceaux.append(
                f"EXISTS (SELECT 1 FROM releve _grl LEFT JOIN regions _grg "
                f"ON _grg.id = _grl.region_id JOIN planches _grp "
                f"ON _grp.id = COALESCE(_grg.planche_id, _grl.planche_id) "
                f"WHERE _grl.grille_id = {alias} AND {lire_r})")
            params += p_lire_r
        if not morceaux:
            return "0", []
        return "(" + " OR ".join(morceaux) + ")", params

    def peut_ecrire_quelque_part(self) -> bool:
        """A-t-on le droit d'écrire, où que ce soit ? Sert aux gestes qui ne visent aucune
        collection en particulier — enrichir le vocabulaire, par exemple. Sans cela, une
        personne en lecture seule pourrait polluer un vocabulaire partagé par tous.

        COL-4 (S2) — écrire dans un BAC À SABLE n'y compte pas : chaque arrivant en ouvrirait
        un, et ces gestes (vocabulaire global, registre des personnages, rôles de
        contribution) survivraient à son effacement, chez tout le monde. La même réponse
        que sans bac à sable."""
        return self.tout or bool(self._ecriture_hors_bac())

    def __repr__(self) -> str:                  # diagnostic uniquement
        if self.tout:
            return (f"<Portee TOUT admin={self.admin} bornee={self.bornee} "
                    f"user={self.utilisateur!r}>")
        return (f"<Portee lecture={sorted(self.lecture)} "
                f"ecriture={sorted(self.ecriture)} "
                f"propriete={sorted(self.propriete)} export={sorted(self.export)} "
                f"projets={sorted(self.projets)} geres={sorted(self.projets_geres)} "
                f"user={self.utilisateur!r}>")


TOTALE = Portee(tout=True, admin=True)


def _sql_une_soeur(alias: str) -> str:
    """Fragment SQL VRAI si le document de la copie `alias` a une AUTRE copie vivante hors
    d'un projet isolé — une copie du jeu ou d'un bac à sable, qui part avec lui, ne garde pas
    un document au fonds commun. Faux : `alias` est la DERNIÈRE copie, que seul un
    administrateur fait sortir du fonds (`Portee.clause_suppression_directe`)."""
    return (f"EXISTS (SELECT 1 FROM albums _ts1 JOIN albums _ts2 "
            f"ON _ts2.document_id = _ts1.document_id AND _ts2.id <> _ts1.id "
            f"WHERE _ts1.id = {alias} AND NOT {sql_album_isole('_ts2')})")


# --------------------------------------------------------------------------- #
# « Qui perd quoi » : le travail des autres sur un album (COL-3, tranches 2 à 3c)
# --------------------------------------------------------------------------- #
# Les cibles du journal qui portent un travail sur une RÉGION et la désignent par son id —
# la région elle-même, sa note et ses tags, son locuteur, la présence d'un personnage, un
# attribut de case. Les deux premières sont écrites par `main.py`, les trois suivantes par
# `routes/personnages.py`, la validation grammaticale (`regions`) par `routes/analyse.py`.
# `region_attribut` n'est écrit que depuis la relecture croisée de la tranche 2.
#
# COL-3, tranche 3c (F3, Hugo, 2026-10-26) — ces sources ne DÉCIDENT plus rien : la règle
# de l'effacement ne lit plus le journal (`Portee._clause_effacement`). Elles servent à
# MONTRER — « qui perd quoi » avant d'effacer, et ce que lit qui répond à une demande
# (`sql_actes_sur_album`). Ce qu'elles comptent reste ce qu'elles comptaient : un travail
# supprimé depuis ne compte plus ; un acte SANS agent compte comme celui d'un autre ; une
# passe automatique n'est attribuée qu'à son moteur ; ranger, demander, changer l'ordre
# des planches, repartir de zéro ou retirer du projet n'est pas un travail sur l'album.
_CIBLES_DE_REGION = ("regions", "annotations", "bulle_locuteur", "personnage_presence",
                     "region_attribut", "releve")
# ANN-7 (tranche 1, R10, R11) — `releve` : un relevé posé, modifié, retiré sur une région, un
# doute et son fil, une passe ; sa cible est la RÉGION, si bien que les sources 1 et 6 le
# lisent par l'index du journal, sans chercher la région dans une charge. Le même acte sur la
# SURFACE d'une planche s'écrit sous `releve_planche`, lu avec les validations (source 4).


# Les cibles d'une couche d'ANNOTATION — tout ce qui, dans `_CIBLES_DE_REGION`, ne suit
# une copie qu'au cran `annotations` (E1). La cible `regions` suit dès le découpage.
_CIBLES_D_ANNOTATION = tuple(c for c in _CIBLES_DE_REGION if c != "regions")


def _sql_chaine_des_sources(depart: str) -> str:
    """`WITH RECURSIVE …` qui rend, pour les régions que `depart` sélectionne (une requête
    `SELECT region_id`), chacune de leurs régions SOURCES en remontant `region_origine` —
    en `(d, s, borne, rang)` : la région de départ, la région source, la date de la copie qui
    l'a emportée (un acte ne compte qu'avant elle), et le plus petit cran de la chaîne
    jusque-là (une couche ne suit que si chaque maillon l'a prise). Le premier maillon est la copie de `depart` ; le
    suivant, la copie qui portait la source ; une région source supprimée arrête la chaîne
    (sa ligne `region_origine` est partie avec elle)."""
    rang = sql_rang_du_cran
    return (
        "WITH RECURSIVE _tch(d, s, borne, rang) AS ("
        "SELECT _tro.region_id, _tro.region_source_id, _tco.creee_le, " + rang("_tco.cran") + " "
        "FROM region_origine _tro JOIN regions _trr ON _trr.id = _tro.region_id "
        "JOIN planches _tpp ON _tpp.id = _trr.planche_id "
        "JOIN copie _tco ON _tco.album_id = _tpp.album_id "
        f"WHERE _tro.region_id IN ({depart}) "
        "UNION "
        "SELECT _tch.d, _tro2.region_source_id, MIN(_tch.borne, _tco2.creee_le), "
        "MIN(_tch.rang, " + rang("_tco2.cran") + ") "
        "FROM _tch JOIN region_origine _tro2 ON _tro2.region_id = _tch.s "
        "JOIN regions _trr2 ON _trr2.id = _tch.s "
        "JOIN planches _tpp2 ON _tpp2.id = _trr2.planche_id "
        "JOIN copie _tco2 ON _tco2.album_id = _tpp2.album_id) ")


def _sources_du_travail(alias: str) -> list[tuple[str, str, str, str, str]]:
    """Les dix sources du travail fait sur l'album `alias`, chacune en (qui, quelle sorte,
    quand, `FROM … WHERE …`, recopié) — la sorte est la `cible_table` de l'acte, ou le nom
    de la table lue. Qui vaut NULL quand l'auteur n'est pas écrit.

    « Recopié » est une expression SQL, vraie pour une ligne de travail RECOPIÉ — fait
    ailleurs, avant la copie, et que la copie porte (tranche 3b) : toute la sixième source,
    les quatre de la v37 (ANN-7), et dans la troisième les corrections grammaticales que la copie a reçues telles quelles
    et que personne n'a corrigées depuis (la marque EXPLICITE `token_correction.recopiee`,
    v36 — décision du pilotage du 2026-10-25 : la date confondait une correction faite dans
    la même seconde, et la validation la réécrivait). Un écran qui ne tient pas le fonds ne nomme pas ces lignes
    (relecture croisée de la 3b, constat 3 : la troisième nommait l'importeur d'un autre
    projet sous « qui perd quoi »)."""
    cibles = ", ".join(f"'{c}'" for c in _CIBLES_DE_REGION)
    annotation = ", ".join(f"'{c}'" for c in _CIBLES_D_ANNOTATION)
    regions_de_l_album = ("SELECT _tr0.id FROM regions _tr0 JOIN planches _tp0 "
                          f"ON _tp0.id = _tr0.planche_id WHERE _tp0.album_id = {alias}")
    return [
        ("_te.agent", "_te.cible_table", "_te.date",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         f"JOIN evenement _te ON _te.cible_table IN ({cibles}) AND _te.cible_id = _tr.id "
         f"WHERE _tp.album_id = {alias} AND _te.agent_type = 'humain'", "0"),
        ("NULL", "'region_attribut'", "NULL",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         "JOIN region_attribut _tra ON _tra.region_id = _tr.id "
         f"WHERE _tp.album_id = {alias} AND NOT EXISTS (SELECT 1 FROM evenement _tre "
         "WHERE _tre.cible_table = 'region_attribut' "
         "AND (_tre.cible_id = _tra.region_id OR _tre.cible_id IN ("
         + _sql_chaine_des_sources("SELECT _tra.region_id") + "SELECT s FROM _tch)) "
         "AND _tre.type = 'lien' AND _tre.agent_type = 'humain' "
         "AND json_extract(_tre.apres, '$.valeur_id') = _tra.valeur_id)", "0"),
        ("_tt.auteur", "'token_correction'", "_tt.date_modif",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         "JOIN token_correction _tt ON _tt.region_id = _tr.id "
         f"WHERE _tp.album_id = {alias}",
         "_tt.recopiee = 1"),
        ("_te.agent", "_te.cible_table", "_te.date",
         # `CROSS JOIN` : l'ordre est forcé, la planche d'abord, puis le journal par son
         # index (`idx_evenement_cible`) — sans statistiques, SQLite partait du journal.
         "planches _tp CROSS JOIN evenement _te "
         f"WHERE _tp.album_id = {alias} "
         "AND _te.cible_table IN ('planches', 'releve_planche') AND _te.cible_id = _tp.id "
         "AND _te.agent_type = 'humain'", "0"),
        ("_te.agent", "'document'", "_te.date",
         "albums _ta JOIN evenement _te "
         "ON _te.cible_table = 'document' AND _te.cible_id = _ta.document_id "
         f"WHERE _ta.id = {alias} AND _te.agent_type = 'humain' "
         f"AND {_SQL_ALBUM_DE_LA_CHARGE} = _ta.id AND NOT {_SQL_NAISSANCE_D_UNE_COPIE} "
         f"AND NOT {_SQL_ORDRE_DES_PLANCHES} AND NOT {_SQL_EFFACER_OU_RETIRER}", "0"),
        # `CROSS JOIN` : la chaîne d'abord, puis le journal par son index
        # (`idx_evenement_cible`) — sans statistiques, SQLite partait du journal et lui
        # bâtissait un index automatique à chaque requête (contre-relecture n°2).
        ("_te.agent", "_te.cible_table", "_te.date",
         "(" + _sql_chaine_des_sources(regions_de_l_album) + "SELECT d, s, borne, rang FROM _tch"
         ") _tsrc CROSS JOIN evenement _te "
         f"WHERE _te.cible_table IN ({cibles}) AND _te.cible_id = _tsrc.s "
         "AND _te.agent_type = 'humain' "
         "AND _te.date <= _tsrc.borne "
         # Les DOUTES ne suivent pas une copie : ils ne comptent nulle part comme travail
         # recopié (décision du pilotage, 2026-10-26 ; le pendant de la neuvième source).
         "AND _te.type NOT LIKE 'doute%' "
         f"AND (_te.cible_table NOT IN ({annotation}) "
         f"OR (_tsrc.rang >= {rang_du_cran(CRAN_ANNOTATIONS)} AND {_SQL_COUCHE_VIT})) "
         "AND (_te.cible_table <> 'regions' OR _te.type <> 'validation' "
         "OR EXISTS (SELECT 1 FROM token_correction _tvc WHERE _tvc.region_id = _tsrc.d "
         "AND _tvc.recopiee = 1))",
         "1"),
        # ANN-7 (R11) — le travail RECOPIÉ sur la SURFACE d'une planche : un relevé, une
        # passe, arrivés avec une copie amorcée au cran `annotations`. La chaîne de
        # `region_origine` ne remonte que des RÉGIONS, et aucun événement n'est recopié (E3) :
        # c'est sur leurs COLONNES qu'on lit qui l'a fait, le patron des corrections. Un
        # auteur NULL — recopié entre deux projets (G9) — compte comme un autre.
        ("_tsr.auteur", "'releve_planche'", "_tsr.cree_le",
         "planches _tp JOIN releve _tsr ON _tsr.planche_id = _tp.id "
         f"WHERE _tp.album_id = {alias} AND _tsr.origine_id IS NOT NULL", "1"),
        # … et le dernier qui l'a modifié à la SOURCE, que la copie emporte (contre-relecture,
        # point 1) : tant que personne ne l'a modifié dans la copie — sinon le journal de la
        # copie (quatrième source) dit qui.
        ("_tsr.modifie_par", "'releve_planche'", "_tsr.modifie_le",
         "planches _tp JOIN releve _tsr ON _tsr.planche_id = _tp.id "
         "JOIN copie _tsc ON _tsc.album_id = _tp.album_id "
         f"WHERE _tp.album_id = {alias} AND _tsr.origine_id IS NOT NULL "
         "AND _tsr.modifie_par IS NOT NULL AND _tsr.modifie_le <= _tsc.creee_le", "1"),
        # La passe recopiée se reconnaît à sa marque EXPLICITE (`passe.recopiee`, v37 ;
        # relecture croisée d'ANN-7, constat 2) : la lire par l'absence d'un acte `passe` sur
        # la planche oubliait celle d'un autre dès qu'une AUTRE passe y était marquée.
        ("_tsp.par", "'releve_planche'", "_tsp.le",
         "planches _tp JOIN passe _tsp ON _tsp.planche_id = _tp.id "
         f"WHERE _tp.album_id = {alias} AND _tsp.recopiee = 1", "1"),
        # ANN-7 (relecture croisée, constat 3) — les actes sur le relevé SOURCE d'un relevé
        # de surface recopié, antérieurs à la copie : le patron de la sixième source.
        # `CROSS JOIN` : la chaîne d'abord, puis les planches de l'album source, puis le
        # journal par son index — sans quoi SQLite partait du journal entier.
        ("_te.agent", "_te.cible_table", "_te.date",
         "(" + _sql_chaine_des_releves(alias) + "SELECT d, s, src, borne FROM _trc) _trs "
         "CROSS JOIN planches _tps CROSS JOIN evenement _te "
         "WHERE _tps.album_id = _trs.src "
         "AND _te.cible_table = 'releve_planche' AND _te.cible_id = _tps.id "
         "AND _te.agent_type = 'humain' AND _te.date <= _trs.borne "
         "AND _te.type NOT LIKE 'doute%' "
         f"AND {_SQL_RELEVE_DE_LA_CHARGE} = _trs.s", "1"),
    ]


def _sql_chaine_des_releves(alias: str) -> str:
    """`WITH RECURSIVE …` qui rend, pour chaque relevé de SURFACE recopié de l'album `alias`,
    chacun de ses relevés SOURCES en remontant `origine_id` — en `(d, s, src, borne)` : le
    relevé de départ, le relevé source, l'album d'où la copie qui l'a emporté a été tirée
    (`copie.depuis_album_id` : les actes de la source sont écrits sous l'une de ses
    planches), et la date de cette copie, la plus ancienne de la chaîne (un acte ne compte
    qu'avant elle). Le patron de `_sql_chaine_des_sources`. Le premier maillon ne lit pas la
    ligne source — retirée depuis, ses actes comptent encore, comme ceux d'une région source
    supprimée — ; le suivant, si : seule elle dit d'où elle venait."""
    return (
        "WITH RECURSIVE _trc(d, s, src, borne) AS ("
        "SELECT _trc0.id, _trc0.origine_id, _tcc0.depuis_album_id, _tcc0.creee_le "
        "FROM releve _trc0 JOIN planches _tpc0 ON _tpc0.id = _trc0.planche_id "
        "JOIN copie _tcc0 ON _tcc0.album_id = _tpc0.album_id "
        f"WHERE _tpc0.album_id = {alias} AND _trc0.origine_id IS NOT NULL "
        "AND _tcc0.depuis_album_id IS NOT NULL "
        "UNION "
        "SELECT _trc.d, _trs1.origine_id, _tcc1.depuis_album_id, "
        "MIN(_trc.borne, _tcc1.creee_le) "
        "FROM _trc JOIN releve _trs1 ON _trs1.id = _trc.s "
        "JOIN planches _tpc1 ON _tpc1.id = _trs1.planche_id "
        "JOIN copie _tcc1 ON _tcc1.album_id = _tpc1.album_id "
        "WHERE _trs1.origine_id IS NOT NULL AND _tcc1.depuis_album_id IS NOT NULL) ")


# Le relevé que nomme la charge d'un acte sur un relevé (`releve_id`, posé par chaque acte de
# `routes/releves.py` — pose, modification, retrait, doute) : `apres` d'abord, `avant` sinon.
# Une charge illisible ne nomme rien (cf. `_SQL_ALBUM_DE_LA_CHARGE`).
_SQL_RELEVE_DE_LA_CHARGE = (
    "COALESCE(CASE WHEN json_valid(_te.apres) THEN json_extract(_te.apres, '$.releve_id') END, "
    "CASE WHEN json_valid(_te.avant) THEN json_extract(_te.avant, '$.releve_id') END)")


# L'album que nomme la charge d'un acte sous la cible `document` — `apres` d'abord (une
# naissance, une notice, un scan ajouté), `avant` sinon (un scan retiré, une destruction).
# Une charge illisible ne nomme rien : `json_extract` lèverait sur elle et ferait tomber
# toute la liste des albums.
_SQL_ALBUM_DE_LA_CHARGE = (
    "COALESCE(CASE WHEN json_valid(_te.apres) THEN json_extract(_te.apres, '$.album_id') END, "
    "CASE WHEN json_valid(_te.avant) THEN json_extract(_te.avant, '$.album_id') END)")


# La NAISSANCE d'une copie sœur (`database.creer_copie`) : `apres` seul, sa charge nomme la
# copie source (`copie.depuis_album_id`). Ce n'est pas un travail sur la copie — elle naît
# vierge —, et pour une entrée acceptée l'agent en est l'ADMINISTRATEUR qui accepte, quand
# la copie est créée pour le DEMANDEUR (Hugo, 2026-10-17) : la compter interdirait à celui-ci
# de la supprimer seul. Borné à cet acte seul — tout autre acte de l'administrateur sur le
# document (notice, scans, relecture) reste le travail d'un autre.
_SQL_NAISSANCE_D_UNE_COPIE = (
    "(_te.avant IS NULL AND json_valid(_te.apres) "
    "AND json_extract(_te.apres, '$.copie.depuis_album_id') IS NOT NULL)")


# L'ORDRE DES PLANCHES changé (UX-11, `PUT /api/albums/{id}/ordre-des-planches`) : ↑ ↓ ou
# « Ranger par nom de fichier ». Ce n'est pas un travail sur l'album (Hugo, 2026-10-22) :
# un ↓ d'une collègue ne doit pas obliger l'importatrice à DEMANDER la suppression d'un
# album où personne d'autre n'a rien annoté. Reconnu par un marqueur EXPLICITE de la charge
# (`acte`, posé par la route seule), jamais par la forme d'une charge qu'un autre geste
# pourrait partager. `IS` et le `CASE` ne rendent jamais NULL : une charge vide ou illisible
# n'est pas un réordonnancement, et reste comptée.
ACTE_ORDRE_DES_PLANCHES = "ordre_des_planches"
_SQL_ORDRE_DES_PLANCHES = (
    "((CASE WHEN json_valid(_te.apres) THEN json_extract(_te.apres, '$.acte') END) "
    f"IS '{ACTE_ORDRE_DES_PLANCHES}')")


# REPARTIR DE ZÉRO (`socle._repartir`, charge `repartir`) et RETIRER DU PROJET
# (`routes/collections.retirer_du_projet`, charge `retire_du_projet`) : deux actes sous le
# document qui ne sont pas un travail sur l'album (relecture croisée de la 3b, constat 5 ;
# le patron de l'ordre des planches). L'un efface, l'autre range : les compter ôtait à qui
# a créé seul une copie le droit de l'effacer, pour un geste fait par son propriétaire ou
# son responsable — et l'administrateur les lisait sous une demande comme un travail perdu.
# Reconnus par la clé de leur charge, que seules ces deux routes posent ; `json_type` rend
# NULL sur une clé absente, et le `CASE`, jamais NULL, garde comptée une charge illisible.
_SQL_EFFACER_OU_RETIRER = (
    "(CASE WHEN json_valid(_te.apres) THEN "
    "json_type(_te.apres, '$.repartir') IS NOT NULL "
    "OR json_type(_te.apres, '$.retire_du_projet') IS NOT NULL ELSE 0 END)")


# Une couche d'ANNOTATION recopiée VIT-elle encore sur la région de départ de la chaîne
# (`_tsrc.d`) ? La sixième source lit ce qui vit, pas le cran de la copie (relecture croisée
# de la 3b, constat 5) : repartir de zéro au-dessous des annotations efface la couche, et le
# travail qu'elle portait ne compte plus — comme un travail supprimé depuis. La couche
# RECOPIÉE, et elle seule (la marque `recopiee`, v36 ; contre-relecture de la 3b) : une
# couche posée ensuite sur la copie, par qui que ce soit, ne ranime pas celle de la source.
_SQL_COUCHE_VIT = (
    "(CASE _te.cible_table "
    + " ".join(f"WHEN '{t}' THEN EXISTS (SELECT 1 FROM {t} _tv WHERE _tv.region_id = _tsrc.d "
               "AND _tv.recopiee = 1)"
               for t in ("annotations", "bulle_locuteur", "personnage_presence",
                         "region_attribut"))
    # ANN-7 — la cible `releve` porte deux couches, et l'acte dit laquelle (contre-relecture,
    # point 4) : une PASSE (marquée, rouverte) vit si une passe RECOPIÉE vit sur la région de
    # la copie — une passe posée ensuite, rouverte puis marquée, ne ranime pas celle de la
    # source (décision du pilotage, 2026-10-26, la doctrine de la 3b) ; tout autre acte porte
    # un relevé (`releve_id` de sa charge). Au PREMIER maillon — la région source est celle
    # dont la région de la copie a été tirée (`region_origine`) —, il vit si un relevé
    # recopié DE CE relevé-là (`origine_id`) vit sur la région : un autre relevé recopié n'en
    # ranime aucun. Au-delà (copie de copie), l'`origine_id` désigne le relevé de la copie
    # intermédiaire, pas celui de l'acte : la forme FERMÉE, un relevé recopié vit sur la
    # région, compte trop plutôt que trop peu (contre-relecture n°2, consigne du pilotage).
    + " WHEN 'releve' THEN CASE WHEN _te.type IN ('passe', 'passe_rouverte') "
      "THEN EXISTS (SELECT 1 FROM passe _tvp WHERE _tvp.region_id = _tsrc.d "
      "AND _tvp.recopiee = 1) "
      "WHEN EXISTS (SELECT 1 FROM region_origine _tvo WHERE _tvo.region_id = _tsrc.d "
      "AND _tvo.region_source_id = _tsrc.s) "
      "THEN EXISTS (SELECT 1 FROM releve _tv WHERE _tv.region_id = _tsrc.d "
      f"AND _tv.origine_id = {_SQL_RELEVE_DE_LA_CHARGE}) "
      "ELSE EXISTS (SELECT 1 FROM releve _tv WHERE _tv.region_id = _tsrc.d "
      "AND _tv.origine_id IS NOT NULL) END"
    + " ELSE 1 END)")


def sql_actes_sur_album(alias: str) -> str:
    """`SELECT agent, sorte, quand, recopie` — chaque geste humain des dix sources sur
    l'album `alias`, un par ligne, l'appelant compris (COL-3 ; Hugo, 2026-10-15 :
    l'administrateur voit, sous une demande, ce que les autres ont fait sur le document ;
    tranche 3b : « qui perd quoi » avant d'effacer). Lu au moment de la lecture. Ce n'est
    pas une question d'accès — depuis la tranche 3c, aucune règle ne le lit : la route qui
    le rend porte sa propre garde.

    `recopie` (tranche 3b) vaut 1 pour un geste RECOPIÉ — fait avant la copie, sur une
    région source (la sixième source) ou une correction grammaticale reçue telle quelle (la
    troisième) : il n'est pas perdu quand elle part, la source le garde si elle vit, et son
    auteur a travaillé dans une autre copie, peut-être un autre projet. Un écran qui ne
    tient pas le fonds ne le nomme pas (`routes/fonds.travail_des_autres_avant_d_effacer`)."""
    return " UNION ALL ".join(
        f"SELECT {agent} AS agent, {sorte} AS sorte, {quand} AS quand, "
        f"CASE WHEN {recopie} THEN 1 ELSE 0 END AS recopie FROM {depuis}"
        for agent, sorte, quand, depuis, recopie in _sources_du_travail(alias))


# --------------------------------------------------------------------------- #
# Résolution
# --------------------------------------------------------------------------- #
def collections_du_principal(conn: sqlite3.Connection, login: str,
                             noms_groupes: list[str]) -> tuple[frozenset, frozenset,
                                                               frozenset, frozenset]:
    """(lecture, écriture, propriété, export) — les collections ouvertes à ce login ou à
    l'un de ses groupes, rangées par niveau, plus celles dont la case `exporter` est
    cochée (DROIT-2) — à quelque niveau que ce soit.

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
    export = set()
    for cid, niveau, exporter in conn.execute(
            f"SELECT collection_id, niveau, exporter FROM collection_acces "
            f"WHERE {conditions}", params):
        par_niveau.get(niveau, par_niveau[LECTURE]).add(cid)
        if exporter:
            export.add(cid)
    return (frozenset(par_niveau[LECTURE]), frozenset(par_niveau[ECRITURE]),
            frozenset(par_niveau[PROPRIETAIRE]), frozenset(export))


def projets_du_principal(conn: sqlite3.Connection, login: str,
                         noms_groupes: list[str]) -> tuple[frozenset, frozenset]:
    """(membre, responsable) — les projets dont ce login ou l'un de ses groupes est
    (COL-3). Une requête, sur le patron de `collections_du_principal`, et pour la même
    raison : elle part à chaque requête HTTP d'un compte ordinaire.

    Le cumul responsable ⊂ membre n'est PAS fait ici — `Portee.__init__` s'en charge. Un
    rôle inconnu (base éditée à la main) est rangé MEMBRE : dégrader est la seule erreur
    qui ne s'aggrave pas."""
    principaux = [(UTILISATEUR, login)] + [(GROUPE, g) for g in noms_groupes]
    conditions = " OR ".join("(genre = ? AND principal = ?)" for _ in principaux)
    params = [v for paire in principaux for v in paire]
    par_role = {MEMBRE: set(), RESPONSABLE: set()}
    for pid, role in conn.execute(
            f"SELECT projet_id, role FROM projet_acces WHERE {conditions}", params):
        par_role.get(role, par_role[MEMBRE]).add(pid)
    return frozenset(par_role[MEMBRE]), frozenset(par_role[RESPONSABLE])


def bases_des_projets(conn: sqlite3.Connection, projets) -> tuple:
    """((projet, collection, acces_membres), …) — la collection de BASE de chacun de ces
    projets (D10), et la position que le projet a choisie pour ses membres. Une requête, sur
    le patron des deux du dessus, et pour la même raison. `Portee.__init__` en tire les
    droits ; cette fonction n'en décide aucun.

    Le drapeau `base` est la seule désignation : une collection du projet qui ne le porte
    pas n'est jamais lue ici, et c'est ce qui borne la dérivation à UNE collection par
    projet."""
    if not projets:
        return ()
    ids = sorted(projets)
    return tuple((r[0], r[1], r[2]) for r in conn.execute(
        f"SELECT {sql_projet_de('c')}, c.id, c.acces_membres FROM collection c "
        f"WHERE c.base = 1 AND {sql_projet_de('c')} IN ({', '.join('?' * len(ids))})",
        ids))


def collections_des_projets(conn: sqlite3.Connection, projets) -> frozenset:
    """Les identifiants de TOUTES les collections de ces projets (F1, COL-3, tranche 3c) —
    ce que leur responsable LIT, dérivé dans `Portee.__init__`. Le patron de
    `bases_des_projets` : une requête, et le repli compris pour une collection sans
    `projet_id` (`sql_projet_de`). Cette fonction n'en décide aucun droit ; l'appelant lui
    passe les projets GÉRÉS hors bacs à sable (un invité qui crée une collection dans un bac
    à sable la garde fermée à son propriétaire, comme avant)."""
    if not projets:
        return frozenset()
    ids = sorted(projets)
    return frozenset(r[0] for r in conn.execute(
        f"SELECT c.id FROM collection c "
        f"WHERE {sql_projet_de('c')} IN ({', '.join('?' * len(ids))})", ids))


def bacs_du_principal(conn: sqlite3.Connection, login: str, projets,
                      collections) -> tuple[frozenset, frozenset, frozenset]:
    """(bacs à sable dont on est, ceux qu'on a ouverts, collections atteintes qui vivent
    dans un bac à sable) — COL-4. Deux requêtes, au plus, à chaque requête HTTP d'un compte
    ordinaire.

    Les collections se lisent sur TOUT ce qu'on atteint, et non sur les seuls bacs à sable
    dont on est : un invité qui y a créé une collection en reste propriétaire
    (`collection_acces`) après en être sorti, et cette collection est toujours celle d'un
    bac à sable. Ce que la fonction ne décide pas : ce que ces ensembles retirent, qui est
    écrit dans `Portee`."""
    bacs, a_soi = set(), set()
    if projets:
        ids = sorted(projets)
        for pid, de in conn.execute(
                f"SELECT id, bac_a_sable_de FROM projet WHERE bac_a_sable_de IS NOT NULL "
                f"AND id IN ({', '.join('?' * len(ids))})", ids):
            bacs.add(pid)
            if de == login:
                a_soi.add(pid)
    cols = set()
    if collections:
        ids = sorted(collections)
        cols = {r[0] for r in conn.execute(
            f"SELECT c.id FROM collection c WHERE c.id IN ({', '.join('?' * len(ids))}) "
            f"AND {sql_est_bac_a_sable(sql_projet_de('c'))}", ids)}
    return frozenset(bacs), frozenset(a_soi), frozenset(cols)


def acces_derives(conn: sqlite3.Connection, collection_id: int) -> list[dict]:
    """Les accès que le PROJET tient sur cette collection — ceux que `Portee.__init__` dérive
    de `projet_acces` pour une collection de BASE (D10), dits ligne par ligne pour qui
    regarde QUI ENTRE (COL-3, tranche 3a : « inévitable, mais pas invisible », l'esprit
    d'AUTH-4). Pour toute autre collection d'un projet ordinaire, depuis la tranche 3c (F1) :
    une ligne par RESPONSABLE du projet, au niveau `lecture` — sa lecture dérivée. Vide dans
    un projet isolé (un bac à sable, le jeu : la lecture du responsable n'y vaut pas).

    La règle est CELLE de `Portee.__init__`, écrite ici à côté d'elle pour ne pas en vivre
    une seconde ailleurs : un responsable du projet est propriétaire de la base, quelle que
    soit la position ; un membre y entre au niveau `acces_membres` — `None`, la base
    protégée, ne lui ouvre rien, et un niveau inconnu se dégrade en lecture. Le droit
    d'exporter suit les niveaux : d'office pour le propriétaire, jamais pour un membre (la
    dérivation ne pose aucune case).

    Une lecture et non une décision : ce que la personne qui frappe peut faire reste à
    `Portee`. Chaque ligne : `genre`, `principal`, `niveau`, `exporter`, `role` (le rôle
    dans le projet), dans l'ordre responsables d'abord."""
    r = conn.execute(f"SELECT {sql_projet_de('c')} AS projet_id, c.base, c.acces_membres, "
                     f"{sql_est_isole(sql_projet_de('c'))} AS isole "
                     "FROM collection c WHERE c.id = ?", (collection_id,)).fetchone()
    if r is None:
        return []
    if not r["base"]:
        if r["isole"]:
            return []
        return [{"genre": m["genre"], "principal": m["principal"], "niveau": LECTURE,
                 "exporter": False, "role": RESPONSABLE}
                for m in conn.execute(
                    "SELECT genre, principal FROM projet_acces WHERE projet_id = ? "
                    "AND role = ? ORDER BY genre, principal", (r["projet_id"], RESPONSABLE))]
    niveau_membre = (None if r["acces_membres"] is None
                     else ECRITURE if r["acces_membres"] == ECRITURE else LECTURE)
    lignes = []
    for m in conn.execute(
            "SELECT genre, principal, role FROM projet_acces WHERE projet_id = ? "
            "ORDER BY CASE role WHEN ? THEN 0 ELSE 1 END, genre, principal",
            (r["projet_id"], RESPONSABLE)):
        if m["role"] == RESPONSABLE:
            niveau = PROPRIETAIRE
        elif niveau_membre is None:
            continue
        else:
            niveau = niveau_membre
        lignes.append({"genre": m["genre"], "principal": m["principal"], "niveau": niveau,
                       "exporter": niveau == PROPRIETAIRE,
                       "role": RESPONSABLE if m["role"] == RESPONSABLE else MEMBRE})
    return lignes


def proprietaires_de(conn: sqlite3.Connection, collection_id: int) -> list[dict]:
    """Qui POSSÈDE cette collection, aujourd'hui : `[{genre, principal}, …]` — les
    propriétaires écrits (`collection_acces`), puis, pour une collection de BASE, les
    responsables de son projet (`acces_derives`), sans doublon. Une LECTURE, comme
    `acces_derives` : rien de ce qu'elle rend ne décide d'un accès. « Retirer du projet » la
    photographie dans son acte (COL-3, tranche 3b) : l'avis « retiré du projet par … » ne se
    lit que par qui possédait une collection quittée AU MOMENT du retrait."""
    explicites = [{"genre": r[0], "principal": r[1]} for r in conn.execute(
        "SELECT genre, principal FROM collection_acces WHERE collection_id = ? "
        "AND niveau = ? ORDER BY genre, principal", (collection_id, PROPRIETAIRE))]
    derives = [{"genre": x["genre"], "principal": x["principal"]}
               for x in acces_derives(conn, collection_id) if x["niveau"] == PROPRIETAIRE]
    return explicites + [x for x in derives if x not in explicites]


def _portee_d_administrateur(conn: sqlite3.Connection, login: str,
                             noms_groupes: list[str]) -> Portee:
    """La portée d'un ADMINISTRATEUR, BORNÉE aux bacs à sable (COL-4 ; Hugo, 2026-10-24 :
    « l'administrateur dans le bac d'un autre : rien, comme un non-membre »). Totale hors
    des bacs à sable ; dans leur périmètre, ses ensembles ORDINAIRES — ses accès et ses
    projets, restreints aux bacs à sable : le sien, et ceux où il est invité, où il est un
    arrivant comme les autres. Sur une instance sans bac à sable, la portée d'avant, après
    une seule requête qui le constate."""
    projets_bacs = frozenset(r[0] for r in conn.execute(
        "SELECT id FROM projet WHERE bac_a_sable_de IS NOT NULL"))
    if not projets_bacs:
        return Portee(tout=True, admin=True, utilisateur=login, groupes=tuple(noms_groupes))
    cols_bacs = frozenset(r[0] for r in conn.execute(
        f"SELECT c.id FROM collection c WHERE {sql_est_bac_a_sable(sql_projet_de('c'))}"))
    lecture, ecriture, propriete, export = (
        s & cols_bacs for s in collections_du_principal(conn, login, noms_groupes))
    projets, projets_geres = (
        s & projets_bacs for s in projets_du_principal(conn, login, noms_groupes))
    bases = bases_des_projets(conn, projets | projets_geres)
    bacs, a_soi, cols_bac = bacs_du_principal(
        conn, login, projets | projets_geres,
        lecture | ecriture | propriete | {b[1] for b in bases})
    return Portee(tout=True, admin=True, lecture=lecture, ecriture=ecriture,
                  propriete=propriete, export=export, projets=projets,
                  projets_geres=projets_geres, bases=bases, utilisateur=login,
                  groupes=tuple(noms_groupes), bacs_a_sable=bacs, bacs_a_soi=a_soi,
                  collections_bac=cols_bac, bornee=True, cols_bacs=cols_bacs,
                  projets_bacs=projets_bacs)


def resoudre(conn: sqlite3.Connection, request) -> Portee:
    """La portée de CETTE requête. Le seul point d'entrée du module."""
    if not AUTH_PROXY:
        return TOTALE                           # mono-poste : comportement d'avant AUTH-2
    login = auteur(request)
    noms_groupes = groupes(request)
    if not login:
        return Portee(groupes=tuple(noms_groupes))   # pas passé par Authelia : rien
    if AUTH_ADMIN_GROUPS & set(noms_groupes):
        return _portee_d_administrateur(conn, login, noms_groupes)
    lecture, ecriture, propriete, export = collections_du_principal(conn, login,
                                                                    noms_groupes)
    # Les projets se lisent ICI : les deux premières branches du dessus rendent leur
    # portée sans toucher la base (mono-poste, sans identité), et n'en ont pas besoin —
    # une portée totale est de tous les projets, une portée vide d'aucun. L'administrateur
    # lit les siens depuis COL-4, restreints aux bacs à sable (`_portee_d_administrateur`).
    projets, projets_geres = projets_du_principal(conn, login, noms_groupes)
    bases = bases_des_projets(conn, projets | projets_geres)
    bacs, a_soi, cols_bac = bacs_du_principal(
        conn, login, projets | projets_geres,
        lecture | ecriture | propriete | {b[1] for b in bases})
    # F1 (tranche 3c) — ce que lit le responsable : les collections des projets qu'il GÈRE,
    # hors bacs à sable. Elles ne vivent dans aucun bac à sable : `cols_bac` n'a pas à les
    # connaître. L'administrateur lit tout (sa portée totale) : sa branche n'en a pas besoin.
    lues = collections_des_projets(conn, projets_geres - bacs)
    return Portee(lecture=lecture, ecriture=ecriture, propriete=propriete, export=export,
                  projets=projets, projets_geres=projets_geres, bases=bases,
                  lues_par_le_projet=lues,
                  utilisateur=login, groupes=tuple(noms_groupes),
                  bacs_a_sable=bacs, bacs_a_soi=a_soi, collections_bac=cols_bac)
