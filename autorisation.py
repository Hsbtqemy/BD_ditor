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
from database import DEMANDE_REJOINDRE, NATURE_COLLECTIF, sql_projet_de

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
                 "projets", "projets_geres", "utilisateur", "groupes")

    def __init__(self, *, tout: bool = False, admin: bool = False,
                 lecture: frozenset = frozenset(), ecriture: frozenset = frozenset(),
                 propriete: frozenset = frozenset(), export: frozenset = frozenset(),
                 projets: frozenset = frozenset(), projets_geres: frozenset = frozenset(),
                 bases: tuple = (),
                 utilisateur: Optional[str] = None, groupes: tuple = ()):
        self.tout = tout
        self.admin = admin
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

    def peut_exporter(self, collection_id: int) -> bool:
        """A-t-on le droit de SORTIR le contenu de cette collection — un fichier qui
        quitte l'instance pour un poste qu'elle ne contrôle plus ?  DROIT-2.

        Lire n'y suffit plus : télécharger n'est pas travailler dans l'instance, c'est
        sortir, et la base légale du corpus n'est pas établie (DEPOT-1). Écrire n'y
        suffit pas davantage — exporter ne s'ordonne pas avec annoter. L'administrateur
        passe outre comme partout, et le mono-poste aussi : sans proxy, il n'y a
        personne à qui refuser."""
        return self.tout or collection_id in self.export

    def peut_exporter_quelque_part(self) -> bool:
        """A-t-on le droit d'exporter, où que ce soit ? Sert aux exports qui traversent
        plusieurs collections (Recherche, Exploration) : sans aucun droit, le fichier
        serait vide, et un refus qui dit pourquoi vaut mieux qu'un fichier qui se tait."""
        return self.tout or bool(self.export)

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
                      utilisateur=self.utilisateur, groupes=self.groupes)

    # -- les projets (COL-3) -------------------------------------------------- #
    def est_du_projet(self, projet_id: int) -> bool:
        """Est-on MEMBRE de ce projet ? Ce que cela permet : y créer une collection, et
        entrer dans sa collection de BASE au niveau que le projet a choisi (D10, dérivé
        dans `__init__`). Ce que cela ne permet pas : lire aucune AUTRE de ses
        collections."""
        return self.tout or projet_id in self.projets

    def peut_gerer_projet(self, projet_id: int) -> bool:
        """A-t-on le droit de régler QUI est de ce projet — faire entrer, faire sortir,
        nommer un autre responsable ?

        La forme est celle de `peut_administrer`, un étage plus haut : le responsable, ou
        l'administrateur qui passe outre, et c'est écrit pour la même raison — un projet
        peut naître sans responsable, et son dernier peut partir."""
        return self.admin or projet_id in self.projets_geres

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
            return "1", []
        if not self.utilisateur:
            return "0", []
        detruire, p_detruire = self.clause_destruction(alias)
        if detruire == "0":
            return "0", []
        autrui, p_autrui = _sql_travail_d_autrui(alias, self.utilisateur)
        return (f"({detruire} "
                f"AND EXISTS (SELECT 1 FROM copie _sc WHERE _sc.album_id = {alias} "
                f"AND _sc.creee_par = ?) "
                f"AND NOT EXISTS (SELECT 1 FROM utilisateur _su WHERE _su.login = ? "
                f"AND _su.nature = ?) "
                f"AND NOT {autrui})",
                [*p_detruire, self.utilisateur, self.utilisateur, NATURE_COLLECTIF,
                 *p_autrui])

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
        attend, ni le nombre de planches. Le fonds entier reste à `peut_tenir_le_fonds`."""
        return self.tout or bool(self.projets_geres)

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

        Par genre. Une suppression (document ou projet) et une entrée de documents : qui
        tient le fonds (`peut_tenir_le_fonds`), comme jusqu'ici. Un `rejoindre` : qui
        ADMINISTRE CHACUNE des collections où vit la copie (D4 stricte — le propriétaire de
        chacune consent ; le même test que `clause_rejoindre_directe`, posé sur qui répond),
        ou la portée totale, en recours. C'est la première demande à laquelle répond
        quelqu'un qui ne tient pas le fonds (D11 : là où vit qui consent).

        Une copie qui n'est plus rangée nulle part — sortie au fonds depuis la demande — n'a
        plus de propriétaire pour consentir : seule la portée totale y répond. Une copie
        partagée entre deux collections de deux propriétaires différents ne se rejoint que
        par qui possède les deux, ou par un administrateur : la forme stricte de D4 lue
        comme le consentement de CHAQUE collection, tenu par une seule réponse.

        Ce que la question ne dit pas, et c'est à la route : quoi répondre à qui ne peut pas
        répondre — un 403 nommé sur le droit, avant l'objet, à qui n'administre rien ; un
        404 à qui ne lit pas la copie visée."""
        if demande["genre"] == DEMANDE_REJOINDRE:
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
        rangement ne traversant pas les projets."""
        if self.tout:
            return True
        if (consentement is not None and consentement["genre"] == DEMANDE_REJOINDRE
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
    sinon à la créatrice d'une copie de la supprimer seule. Chaque sous-requête part de
    l'album et descend par les index
    (`idx_evenement_cible`) : la liste des albums la pose album par album.

    Les cinq sources sont écrites UNE fois (`_sources_du_travail`), et lues aussi par
    `sql_actes_sur_album` : ce que l'administrateur voit du travail des autres, sous une
    demande, est ce que cette règle a lu — deux écritures finiraient par ne plus dire
    pareil. Un attribut de case dont un `lien` humain a été écrit est compté par son acte
    (première source) ; la deuxième ne garde que ceux dont AUCUN `lien` humain n'est écrit,
    et l'auteur y est inconnu."""
    sources = _sources_du_travail(alias)
    sql = "(" + " OR ".join(f"EXISTS (SELECT 1 FROM {depuis} AND {agent} IS NOT ?)"
                            for agent, _sorte, _quand, depuis in sources) + ")"
    return sql, [login] * len(sources)


def _sources_du_travail(alias: str) -> list[tuple[str, str, str, str]]:
    """Les cinq sources du travail fait sur l'album `alias`, chacune en (qui, quelle sorte,
    quand, `FROM … WHERE …`) — la sorte est la `cible_table` de l'acte, ou le nom de la
    table lue. Qui vaut NULL quand l'auteur n'est pas écrit."""
    cibles = ", ".join(f"'{c}'" for c in _CIBLES_DE_REGION)
    return [
        ("_te.agent", "_te.cible_table", "_te.date",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         f"JOIN evenement _te ON _te.cible_table IN ({cibles}) AND _te.cible_id = _tr.id "
         f"WHERE _tp.album_id = {alias} AND _te.agent_type = 'humain'"),
        ("NULL", "'region_attribut'", "NULL",
         "planches _tp JOIN regions _tr ON _tr.planche_id = _tp.id "
         "JOIN region_attribut _tra ON _tra.region_id = _tr.id "
         f"WHERE _tp.album_id = {alias} AND NOT EXISTS (SELECT 1 FROM evenement _tre "
         "WHERE _tre.cible_table = 'region_attribut' AND _tre.cible_id = _tra.region_id "
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
         f"AND {_SQL_ALBUM_DE_LA_CHARGE} = _ta.id"),
    ]


# L'album que nomme la charge d'un acte sous la cible `document` — `apres` d'abord (une
# naissance, une notice, un scan ajouté), `avant` sinon (un scan retiré, une destruction).
# Une charge illisible ne nomme rien : `json_extract` lèverait sur elle et ferait tomber
# toute la liste des albums.
_SQL_ALBUM_DE_LA_CHARGE = (
    "COALESCE(CASE WHEN json_valid(_te.apres) THEN json_extract(_te.apres, '$.album_id') END, "
    "CASE WHEN json_valid(_te.avant) THEN json_extract(_te.avant, '$.album_id') END)")


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
    lecture, ecriture, propriete, export = collections_du_principal(conn, login,
                                                                    noms_groupes)
    # Les projets se lisent ICI seulement : les trois branches du dessus rendent leur
    # portée sans toucher la base (mono-poste, sans identité, administrateur), et aucune
    # n'en a besoin — une portée totale est de tous les projets, une portée vide d'aucun.
    projets, projets_geres = projets_du_principal(conn, login, noms_groupes)
    return Portee(lecture=lecture, ecriture=ecriture, propriete=propriete, export=export,
                  projets=projets, projets_geres=projets_geres,
                  bases=bases_des_projets(conn, projets | projets_geres),
                  utilisateur=login, groupes=tuple(noms_groupes))
