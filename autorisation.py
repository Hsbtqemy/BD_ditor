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
`Portee.__init__`, jamais recopiée dans `collection_acces`. Toute autre collection du projet
garde son « Qui entre » seul : entrer dans un projet n'ouvre aucune d'elles, et un accès de
collection se passe d'être du projet.

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
from database import (CRAN_ANNOTATIONS, GENRES_CONSENTIS, NATURE_COLLECTIF, rang_du_cran,
                      sql_album_isole, sql_est_bac_a_sable, sql_est_isole, sql_est_jeu,
                      sql_projet_d_album, sql_projet_de, sql_rang_du_cran)

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
     "lies": ECRITURE,
     # Vrai de la suppression DÉFINITIVE seule depuis le fonds (COL-3, tranche 2) :
     # supprimer un album de sa collection le garde au fonds, avec son travail. Le mot
     # « définitivement » est le seul ajout à la phrase validée par Hugo le 2026-09-17
     # (proposition R10 du cadrage, suivie en route).
     "avertissement": "Supprimer définitivement un album efface ses images et ne se "
                      "rattrape pas."},
    {"code": "vocabulaire", "libelle": "gérer le vocabulaire", "niveau": ECRITURE,
     "lies": ECRITURE, "avertissement": None},
    {"code": "lots", "libelle": "lancer la reconnaissance automatique", "niveau": ECRITURE,
     "lies": ECRITURE, "avertissement": None},
    {"code": "decider", "libelle": "décider qui entre", "niveau": PROPRIETAIRE, "lies": None,
     "avertissement": None},
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
# CE QUE CES RÔLES NE SONT PAS : des niveaux d'accès sur les collections du projet. Une
# seule exception, et elle est voulue (D10, Hugo, 2026-10-17) : la collection de BASE du
# projet, dont le responsable est propriétaire et où le membre entre au niveau
# `acces_membres` — dérivée dans `Portee.__init__`, à partir de `bases_des_projets`. Aucune
# des clauses qui filtrent les données (`clause_album`, `clause_destruction`,
# `clause_terme`) ne connaît les projets : elles lisent les ensembles que la dérivation a
# remplis. Toute autre collection garde son « Qui entre ».
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
                 bases: tuple = (),
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
        restreints aux bacs à sable, que sur des albums de bac à sable."""
        sql, params = clause
        return (f"(NOT EXISTS (SELECT 1 FROM albums _bba WHERE _bba.id = {alias} "
                f"AND {sql_est_bac_a_sable(sql_projet_d_album('_bba'))}) OR {sql})", params)

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
        ni une requête sans identité (portée vide). Le compte PARTAGÉ est refusé à la route,
        qui lit sa nature en base : un bac à sable est à une personne."""
        return bool(AUTH_PROXY) and bool(self.utilisateur)

    def _ecriture_hors_bac(self) -> frozenset:
        """Les collections où l'on écrit, hors des bacs à sable."""
        return self.ecriture - self.collections_bac

    # -- les projets (COL-3) -------------------------------------------------- #
    def est_du_projet(self, projet_id: int) -> bool:
        """Est-on MEMBRE de ce projet ? Ce que cela permet : y créer une collection, et
        entrer dans sa collection de BASE au niveau que le projet a choisi (D10, dérivé
        dans `__init__`). Ce que cela ne permet pas : lire aucune AUTRE de ses
        collections."""
        return self.couvre_projet(projet_id) or projet_id in self.projets

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
        avoir un accès de collection sans être du projet continue de marcher, et la
        personne doit pouvoir lire le nom du projet où elle travaille. Le lui cacher
        donnerait à l'écran une collection sans projet.

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

    def clause_destruction(self, alias: str = "a.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux albums qu'on peut
        DÉTRUIRE — lui, ou l'une de ses planches.  AUTH-10, 2026-10-08.

        Écrire dans UNE collection de l'album suffit pour l'annoter : c'est l'union de
        `clause_album`, et elle est voulue — le travail fait dans une étude se voit dans
        l'autre. Détruire est l'autre règle : il faut écrire dans TOUTES les collections où
        l'album vit. Sans elle, le droit reçu sur une collection s'exerçait hors d'elle, y
        compris sur une étude que celui qui supprime ne lit pas (reproduit le 2026-10-08).
        Qui n'écrit que d'un côté garde un geste, qui ne détruit rien : SORTIR l'album de
        sa collection. Il se défait — par qui écrit des deux côtés, ou par un
        administrateur ; pas par celui qui n'écrivait dans l'album que par cette
        collection-là : ranger demande d'y écrire, et il n'y écrit plus, qu'il continue de le
        lire ou non.

        Les deux moitiés sont nécessaires. `NOT EXISTS` seul serait vrai d'un album rangé
        nulle part — une base retouchée à la main —, et l'ouvrirait à quiconque.
        """
        if self.tout:
            if self.bornee:
                return self._bornee_sur_album(alias,
                                              self._ordinaire().clause_destruction(alias))
            return "1", []
        ids = sorted(self.ecriture)
        if not ids:
            return "0", []
        marques = ", ".join("?" * len(ids))
        return (f"(EXISTS (SELECT 1 FROM collection_album ca "
                f"WHERE ca.album_id = {alias} AND ca.collection_id IN ({marques})) "
                f"AND NOT EXISTS (SELECT 1 FROM collection_album ca "
                f"WHERE ca.album_id = {alias} AND ca.collection_id NOT IN ({marques})))",
                list(ids) * 2)

    def clause_suppression_directe(self, alias: str = "a.id") -> tuple[str, list]:
        """Fragment SQL restreignant `alias` (un id d'album) aux albums qu'on peut
        SUPPRIMER DÉFINITIVEMENT sans rien demander — lui, ou l'une de ses planches.
        COL-3, tranche 2 (Hugo, 2026-10-11).

        « Supprimer » a deux réponses. Supprimer DE LA COLLECTION ne détruit rien : la
        copie part au fonds avec son travail, et c'est le geste de qui écrit dans la
        collection. Supprimer DÉFINITIVEMENT efface les images et le travail ; il existe
        pour l'import par erreur, et ne doit alors attendre personne. Hors de ce cas, il se
        DEMANDE à un administrateur.

        La règle est la conjonction de quatre moitiés, toutes nécessaires :

        - `clause_destruction`, INCHANGÉE (AUTH-10) : on écrit dans toutes les collections
          où la copie vit. Elle reste nécessaire, et cesse d'être suffisante ;
        - CETTE COPIE a été créée PAR CET APPELANT (`copie.creee_par`, v31). Pour la copie
          d'origine d'un document, c'est son importateur ; pour une copie sœur, qui l'a
          prise (COL-3, tranche 3, D5) — l'importatrice d'origine ne supprime pas seule la
          copie d'un autre, et qui a pris une copie n'attend pas l'importatrice pour la
          sienne. Jamais vrai sans login, ni sans ligne `copie`, ni pour la copie d'un
          document d'avant le fonds, dont l'importateur n'a été écrit nulle part — celles-là
          se demandent, seul un administrateur les détruit (décision B3) ;
        - l'appelant n'est pas un compte PARTAGÉ : « celui qui l'a importé » n'y désigne
          personne (proposition R7, suivie en route). C'est le premier endroit où la nature
          d'un compte borde un geste ; elle ne borde toujours aucun ACCÈS ;
        - PERSONNE D'AUTRE n'y a travaillé (`_sql_travail_d_autrui`).

        Ce que la règle ne lit PAS, et c'est cohérent avec elle : une demande REFUSÉE. Qu'un
        administrateur ait répondu « garder » à la demande d'un collègue ne retire rien à
        l'importatrice : si les quatre moitiés tiennent — le collègue n'a donc pas travaillé
        dans l'album —, elle le supprime encore elle-même (relecture croisée, constat 7).
        « Garder » répond à une demande ; il ne protège pas le document de qui l'a importé.

        « Aucun autre projet ne l'emploie », les mots de Hugo, n'a pas de moitié à lui, et
        n'en aura pas : la règle porte sur CETTE copie, et détruire une copie ne retire rien
        à sa sœur — ni son travail, ni les images qu'elle emploie (`socle._detruire_album`),
        ni le document, qui part avec sa DERNIÈRE copie (D5, Hugo, 2026-10-17).

        Ce que la réponse ne dit pas, et c'est voulu : LAQUELLE des moitiés manque. Le refus
        est le même dans tous les cas (`socle._MOTIF_DESTRUCTION`) — dire « c'est Léa qui y
        a travaillé » ou « une autre collection le porte » à qui ne lit pas cette collection
        décrirait le corpus hors de sa portée.

        La portée totale passe outre, et c'est écrit : l'administrateur et le mono-poste
        détruisent tout, c'est le recours d'une demande."""
        if self.tout:
            if self.bornee:
                return self._bornee_sur_album(
                    alias, self._ordinaire().clause_suppression_directe(alias))
            return "1", []
        if not self.utilisateur:
            return "0", []
        # COL-4 (S5 du cadrage) — un cinquième chemin, disjoint des quatre moitiés : le
        # PROPRIÉTAIRE d'un bac à sable détruit tout album de son bac à sable, sans rien
        # demander, quel que soit qui y a travaillé — rien ne s'y demande à un
        # administrateur (S3), et le travail d'un invité s'y efface de toute façon chaque
        # lundi. Le projet de l'album (écrit, ou lu dans ses collections) est l'un des bacs à
        # sable qu'il a ouverts ; et il n'est pas un compte PARTAGÉ, la quatrième moitié
        # gardée telle quelle. Un INVITÉ garde la règle commune.
        bac, p_bac = "0", []
        if self.bacs_a_soi:
            ids = sorted(self.bacs_a_soi)
            bac = (f"(EXISTS (SELECT 1 FROM albums _sbs WHERE _sbs.id = {alias} "
                   f"AND {sql_projet_d_album('_sbs')} IN ({', '.join('?' * len(ids))})) "
                   f"AND NOT EXISTS (SELECT 1 FROM utilisateur _sbu WHERE _sbu.login = ? "
                   f"AND _sbu.nature = ?))")
            p_bac = [*ids, self.utilisateur, NATURE_COLLECTIF]
        detruire, p_detruire = self.clause_destruction(alias)
        if detruire == "0":
            return bac, p_bac
        autrui, p_autrui = _sql_travail_d_autrui(alias, self.utilisateur)
        return (f"(({detruire} "
                f"AND EXISTS (SELECT 1 FROM copie _sc WHERE _sc.album_id = {alias} "
                f"AND _sc.creee_par = ?) "
                f"AND NOT EXISTS (SELECT 1 FROM utilisateur _su WHERE _su.login = ? "
                f"AND _su.nature = ?) "
                f"AND NOT {autrui}) OR {bac})",
                [*p_detruire, self.utilisateur, self.utilisateur, NATURE_COLLECTIF,
                 *p_autrui, *p_bac])

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
          `clause_destruction` (« toutes ses collections »), un palier plus haut. Le
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

        Ce que la question ne dit pas, et c'est à la route : quoi répondre à qui ne peut pas
        répondre — un 403 nommé sur le droit, avant l'objet, à qui n'administre rien ; un
        404 à qui ne lit pas la copie visée."""
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
        (tranche 3b), dans le projet."""
        if self.tout:
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


# --------------------------------------------------------------------------- #
# « Personne d'autre n'y a travaillé » (COL-3, tranche 2)
# --------------------------------------------------------------------------- #
# Les cibles du journal qui portent un travail sur une RÉGION et la désignent par son id —
# la région elle-même, sa note et ses tags, son locuteur, la présence d'un personnage, un
# attribut de case. Les deux premières sont écrites par `main.py`, les trois suivantes par
# `routes/personnages.py`, la validation grammaticale (`regions`) par `routes/analyse.py`.
# `region_attribut` n'est écrit que depuis la relecture croisée de la tranche 2 : un
# attribut posé par un autre ne comptait pas, et l'importatrice détruisait sans demander.
_CIBLES_DE_REGION = ("regions", "annotations", "bulle_locuteur", "personnage_presence",
                     "region_attribut")


def _sql_travail_d_autrui(alias: str, login: str) -> tuple[str, list]:
    """Fragment SQL VRAI si un autre humain que `login` a travaillé sur l'album `alias`.

    C'est la première fois qu'une décision d'accès dépend du CONTENU du journal, et la
    lecture en a des limites, écrites plutôt que découvertes :

    - le travail se lit par jointure sur ce qui VIT encore : une région supprimée depuis,
      une correction effacée, n'ont plus de ligne, et le travail qu'un tiers y avait fait
      ne compte plus (Hugo l'a accepté en tranchant : « un travail supprimé depuis ne
      compte plus ») ;
    - un acte SANS agent compte comme celui de quelqu'un d'autre — on ne sait pas qui l'a
      posé, donc on ne sait pas que c'est l'appelant ;
    - une passe automatique n'est attribuée qu'à son moteur (`agent_type = 'moteur'`) :
      celle qu'un collègue a lancée ne compte pas, et c'est voulu par la même décision ;
    - ranger l'album dans une collection n'est pas y travailler (`collection_album` n'est
      pas lu) : c'est un emploi, et `clause_destruction` en répond déjà ;
    - une demande déposée n'est pas un travail non plus (`demande` n'est pas lu) ;
    - un attribut de case dont on ne sait pas qui l'a posé — aucun `lien` de l'appelant ne
      l'a écrit au journal : posé avant que le geste s'y écrive, ou recopié par la fusion
      de deux valeurs — compte comme le travail d'un autre, la prudence de la décision B3
      (« inconnu veut dire demander ») appliquée à l'auteur au lieu de l'importateur.

    Cinq sources : le journal des régions de l'album, les attributs de ses cases que
    l'appelant n'a pas posés, les corrections grammaticales vivantes (leur `auteur` — la
    correction est une couche à part, que le journal ne relie à la région que par l'id de
    la correction), les validations de ses planches, et les actes sur son DOCUMENT — un
    scan ajouté ou retiré, la notice ou la paternité modifiée, la relecture d'une planche
    forcée, par un autre. Ces derniers sont écrits sous le document, qu'une copie SŒUR
    partage (COL-3, tranche 3) : seuls comptent ceux dont la charge nomme CET album — la
    notice retouchée sur une autre copie n'est pas un travail sur celle-ci, et interdirait
    sinon à la créatrice d'une copie de la supprimer seule. Changer l'ORDRE des planches
    n'en est pas un (UX-11, Hugo, 2026-10-22 ; `_SQL_ORDRE_DES_PLANCHES`) : écrit sous le
    document lui aussi, il n'y compte pas, et l'administrateur ne le lit pas non plus sous
    une demande. Chaque sous-requête part de
    l'album et descend par les index
    (`idx_evenement_cible`) : la liste des albums la pose album par album.

    Une sixième depuis la v32 (COL-3, tranche 3b, E3) : le travail RECOPIÉ. Une copie
    amorcée jusqu'à un cran reprend les régions de sa source sous des identifiants neufs, et
    aucun événement n'est recopié — Ctrl+Z les remonterait, et chaque révision compterait
    deux fois. Ce qui a été fait sur les régions SOURCES compte donc comme le travail de
    ses auteurs, par la chaîne de `region_origine`, copie de copie comprise, et deux bornes :
    un acte ne compte que s'il est ANTÉRIEUR à la copie qui l'a emporté (le travail fait
    ensuite sur la source n'est pas dans la copie), et une couche d'annotation (note,
    locuteur, présence, attribut) ne compte que si chaque maillon de la chaîne l'a emportée
    (cran `annotations`). C'est un écart ÉCRIT avec « on lit ce qui vit encore » : la
    région source peut être supprimée depuis, et le journal qui la nomme lui survit ; le
    travail copié, lui, vit. La lecture penche vers la demande : tout acte humain sur une
    région source avant la copie compte — un texte modifié puis copié au seul cran du
    découpage aussi, la cible `regions` ne distinguant pas la géométrie du texte.

    Les six sources sont écrites UNE fois (`_sources_du_travail`), et lues aussi par
    `sql_actes_sur_album` : ce que l'administrateur voit du travail des autres, sous une
    demande, est ce que cette règle a lu — deux écritures finiraient par ne plus dire
    pareil. Un attribut de case dont un `lien` humain a été écrit est compté par son acte
    (première source) ; la deuxième ne garde que ceux dont AUCUN `lien` humain n'est écrit,
    et l'auteur y est inconnu."""
    sources = _sources_du_travail(alias)
    sql = "(" + " OR ".join(f"EXISTS (SELECT 1 FROM {depuis} AND {agent} IS NOT ?)"
                            for agent, _sorte, _quand, depuis in sources) + ")"
    return sql, [login] * len(sources)


# Les cibles d'une couche d'ANNOTATION — tout ce qui, dans `_CIBLES_DE_REGION`, ne suit
# une copie qu'au cran `annotations` (E1). La cible `regions` suit dès le découpage.
_CIBLES_D_ANNOTATION = tuple(c for c in _CIBLES_DE_REGION if c != "regions")


def _sql_chaine_des_sources(depart: str) -> str:
    """`WITH RECURSIVE …` qui rend, pour les régions que `depart` sélectionne (une requête
    `SELECT region_id`), chacune de leurs régions SOURCES en remontant `region_origine` —
    en `(s, borne, rang)` : la région source, la date de la copie qui l'a emportée (un acte
    ne compte qu'avant elle), et le plus petit cran de la chaîne jusque-là (une couche ne
    suit que si chaque maillon l'a prise). Le premier maillon est la copie de `depart` ; le
    suivant, la copie qui portait la source ; une région source supprimée arrête la chaîne
    (sa ligne `region_origine` est partie avec elle)."""
    rang = sql_rang_du_cran
    return (
        "WITH RECURSIVE _tch(s, borne, rang) AS ("
        "SELECT _tro.region_source_id, _tco.creee_le, " + rang("_tco.cran") + " "
        "FROM region_origine _tro JOIN regions _trr ON _trr.id = _tro.region_id "
        "JOIN planches _tpp ON _tpp.id = _trr.planche_id "
        "JOIN copie _tco ON _tco.album_id = _tpp.album_id "
        f"WHERE _tro.region_id IN ({depart}) "
        "UNION "
        "SELECT _tro2.region_source_id, MIN(_tch.borne, _tco2.creee_le), "
        "MIN(_tch.rang, " + rang("_tco2.cran") + ") "
        "FROM _tch JOIN region_origine _tro2 ON _tro2.region_id = _tch.s "
        "JOIN regions _trr2 ON _trr2.id = _tch.s "
        "JOIN planches _tpp2 ON _tpp2.id = _trr2.planche_id "
        "JOIN copie _tco2 ON _tco2.album_id = _tpp2.album_id) ")


def _sources_du_travail(alias: str) -> list[tuple[str, str, str, str]]:
    """Les six sources du travail fait sur l'album `alias`, chacune en (qui, quelle sorte,
    quand, `FROM … WHERE …`) — la sorte est la `cible_table` de l'acte, ou le nom de la
    table lue. Qui vaut NULL quand l'auteur n'est pas écrit."""
    cibles = ", ".join(f"'{c}'" for c in _CIBLES_DE_REGION)
    annotation = ", ".join(f"'{c}'" for c in _CIBLES_D_ANNOTATION)
    regions_de_l_album = ("SELECT _tr0.id FROM regions _tr0 JOIN planches _tp0 "
                          f"ON _tp0.id = _tr0.planche_id WHERE _tp0.album_id = {alias}")
    return [
        ("_te.agent", "_te.cible_table", "_te.date",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         f"JOIN evenement _te ON _te.cible_table IN ({cibles}) AND _te.cible_id = _tr.id "
         f"WHERE _tp.album_id = {alias} AND _te.agent_type = 'humain'"),
        ("NULL", "'region_attribut'", "NULL",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         "JOIN region_attribut _tra ON _tra.region_id = _tr.id "
         f"WHERE _tp.album_id = {alias} AND NOT EXISTS (SELECT 1 FROM evenement _tre "
         "WHERE _tre.cible_table = 'region_attribut' "
         "AND (_tre.cible_id = _tra.region_id OR _tre.cible_id IN ("
         + _sql_chaine_des_sources("SELECT _tra.region_id") + "SELECT s FROM _tch)) "
         "AND _tre.type = 'lien' AND _tre.agent_type = 'humain' "
         "AND json_extract(_tre.apres, '$.valeur_id') = _tra.valeur_id)"),
        ("_tt.auteur", "'token_correction'", "_tt.date_modif",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         "JOIN token_correction _tt ON _tt.region_id = _tr.id "
         f"WHERE _tp.album_id = {alias}"),
        ("_te.agent", "'planches'", "_te.date",
         "planches _tp JOIN evenement _te "
         "ON _te.cible_table = 'planches' AND _te.cible_id = _tp.id "
         f"WHERE _tp.album_id = {alias} AND _te.agent_type = 'humain'"),
        ("_te.agent", "'document'", "_te.date",
         "albums _ta JOIN evenement _te "
         "ON _te.cible_table = 'document' AND _te.cible_id = _ta.document_id "
         f"WHERE _ta.id = {alias} AND _te.agent_type = 'humain' "
         f"AND {_SQL_ALBUM_DE_LA_CHARGE} = _ta.id AND NOT {_SQL_NAISSANCE_D_UNE_COPIE} "
         f"AND NOT {_SQL_ORDRE_DES_PLANCHES}"),
        ("_te.agent", "_te.cible_table", "_te.date",
         "evenement _te JOIN ("
         + _sql_chaine_des_sources(regions_de_l_album) + "SELECT s, borne, rang FROM _tch"
         f") _tsrc ON _te.cible_id = _tsrc.s "
         f"WHERE _te.cible_table IN ({cibles}) AND _te.agent_type = 'humain' "
         "AND _te.date <= _tsrc.borne "
         f"AND (_te.cible_table NOT IN ({annotation}) "
         f"OR _tsrc.rang >= {rang_du_cran(CRAN_ANNOTATIONS)})"),
    ]


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


def sql_actes_sur_album(alias: str) -> str:
    """`SELECT agent, sorte, quand` — chaque geste humain que la règle de suppression lit
    sur l'album `alias`, un par ligne, l'appelant compris (COL-3 ; Hugo, 2026-10-15 :
    l'administrateur voit, sous une demande, ce que les autres ont fait sur le document).
    Lu à la source même de la règle, au moment de la lecture. Ce n'est pas une question
    d'accès : la route qui le rend porte sa propre garde (`peut_tenir_le_fonds`)."""
    return " UNION ALL ".join(f"SELECT {agent} AS agent, {sorte} AS sorte, {quand} AS quand "
                              f"FROM {depuis}"
                              for agent, sorte, quand, depuis in _sources_du_travail(alias))


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
    d'AUTH-4). Vide pour toute autre collection.

    La règle est CELLE de `Portee.__init__`, écrite ici à côté d'elle pour ne pas en vivre
    une seconde ailleurs : un responsable du projet est propriétaire de la base, quelle que
    soit la position ; un membre y entre au niveau `acces_membres` — `None`, la base
    protégée, ne lui ouvre rien, et un niveau inconnu se dégrade en lecture. Le droit
    d'exporter suit les niveaux : d'office pour le propriétaire, jamais pour un membre (la
    dérivation ne pose aucune case).

    Une lecture et non une décision : ce que la personne qui frappe peut faire reste à
    `Portee`. Chaque ligne : `genre`, `principal`, `niveau`, `exporter`, `role` (le rôle
    dans le projet), dans l'ordre responsables d'abord."""
    r = conn.execute(f"SELECT {sql_projet_de('c')} AS projet_id, c.base, c.acces_membres "
                     "FROM collection c WHERE c.id = ?", (collection_id,)).fetchone()
    if r is None or not r["base"]:
        return []
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
    return Portee(lecture=lecture, ecriture=ecriture, propriete=propriete, export=export,
                  projets=projets, projets_geres=projets_geres, bases=bases,
                  utilisateur=login, groupes=tuple(noms_groupes),
                  bacs_a_sable=bacs, bacs_a_soi=a_soi, collections_bac=cols_bac)
