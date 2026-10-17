"""Socle commun des routes de l'API — dépendances, helpers, accesseurs gardés.  ARCH-1.

`main.py` a franchi les 4 400 lignes pour 125 routes, contre un seuil de 3 200 déclaré
dans `pilotage/journal.config.mjs`. Le découpage se fait par DOMAINE (`routes/`), et ce
module porte ce dont tous les domaines dépendent — mesuré avant de découper : chaque bloc
de main.py n'utilisait que 5 à 20 noms définis ailleurs, et presque toujours les mêmes.

**Ce module ne définit AUCUNE route.** Il n'importe pas `main`, ce qui garantit l'absence
de cycle : `routes/*` importe `socle`, `main` importe `routes/*`.

Deux choses y gagnent plus qu'un rangement.

Les **accesseurs gardés** (`_get_album`, `_get_planche`, `_get_region`,
`_get_collection`) sont, dit CLAUDE.md, « la seule façon d'atteindre un objet du
corpus ». C'était jusqu'ici une
convention : rien n'empêchait un nouveau bloc d'écrire son propre `SELECT * FROM albums`.
Les rassembler dans un module que les routes doivent IMPORTER en fait une contrainte
qu'on voit, sans rien changer à leur comportement.

Et `main.py` **ré-exporte** tout ce qui suit. Ce n'est pas de la compatibilité par
paresse : `tests/test_autorisation.py` compare l'IDENTITÉ de `main.portee_courante` aux
dépendances de chaque route, et `tests/test_sorties_identite.py` balaie les routes depuis
`main`. Le ré-export garde ces cliquets exacts sans qu'une ligne en soit réécrite — ce que
la fiche ARCH-1 posait comme condition du découpage.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from typing import Any, Iterator, Optional
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import autorisation
import conflit
import journal
from database import (DEMANDE_SUPPRESSION_DOCUMENT, DEMANDE_SUPPRESSION_PROJET,
                      REPONSE_ACCEPTEE, clause_appartenance, collection_row,
                      get_connection, retirer_document_sans_copie, sql_projet_de,
                      unindex_region)
from pipeline.ingest import (chemin_d_image_sur, dossiers_d_album, elaguer_dossier_d_album,
                             remove_album_files, remove_planche_files)

# --------------------------------------------------------------------------- #
# Dépendance connexion
# --------------------------------------------------------------------------- #


def db() -> Iterator[sqlite3.Connection]:
    """Une connexion par requête. Le commit est fait EXPLICITEMENT dans chaque
    route d'écriture (et non après le yield) : le code post-yield d'une
    dépendance FastAPI s'exécute APRÈS l'envoi de la réponse, ce qui rendait
    une écriture invisible à une lecture immédiate (course écriture→lecture).
    Ici la dépendance ne gère que le rollback en cas d'erreur et la fermeture.
    """
    conn = get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def portee_courante(request: Request,
                    conn: sqlite3.Connection = Depends(db)) -> autorisation.Portee:
    """Dépendance FastAPI : la portée d'autorisation de la requête courante (AUTH-2).

    Enveloppe minuscule autour de `autorisation.resoudre` — la logique vit dans le module,
    pas ici. Toute route qui touche aux données du corpus déclare CETTE dépendance ; c'est
    ce que vérifie `tests/test_autorisation.py`, qui échoue si une route l'oublie.
    """
    return autorisation.resoudre(conn, request)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _row(cur) -> Optional[dict]:
    r = cur.fetchone()
    return dict(r) if r else None


# --------------------------------------------------------------------------- #
# Helpers métier
# --------------------------------------------------------------------------- #
def _norm_tag(label: str) -> str:
    """Tags insensibles à la casse, stockés en minuscules, espaces compactés."""
    return " ".join(label.strip().lower().split())


def _sans_accents(s: str) -> str:
    """Minuscule sans diacritiques — pour une autocomplétion insensible aux accents
    (« etienne » trouve « Étienne »)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _ensure_tags(conn: sqlite3.Connection, labels: list[str], portee) -> list[dict]:
    """Crée les tags manquants et renvoie les lignes correspondantes.

    **Ce qu'on ne LIT pas ne s'attache pas, et ne se crée pas non plus** (AUTH-11,
    demi-mesure tranchée le 2026-09-24). Le libellé d'un tag est unique dans TOUTE
    l'instance (`ON CONFLICT(label)`), si bien que taper le nom d'un tag local à une
    collection qu'on ne lit pas attachait CE tag-là. Deux dommages, et le second est
    celui qui coûtait : l'oracle par l'écriture, et surtout une région qui repartait
    porteuse d'un terme étranger — invisible à qui vient de l'écrire, et **impossible à
    retirer**, puisqu'une garde refuse de retirer un tag qu'on ne lit pas.

    La `Portee` est OBLIGATOIRE, comme dans les accesseurs gardés : un défaut ferait
    retomber un appelant distrait sur l'ancien comportement, qui marche parfaitement.

    **Ce n'est PAS la fin du sujet**, et il ne faut pas le lire comme tel. La fin est une
    unicité `(libellé, collection)` — un changement de schéma qui croise `COL-1`, doit
    trancher la collision à la promotion, et bute sur trois pièges écrits dans la fiche
    (les NULL distincts d'un index SQLite, le journal qui nomme les tags par libellé, et
    « à quelle collection appartient un tag TAPÉ »). Cette garde ferme le dommage de
    DONNÉES ; elle ne ferme pas l'oracle, puisque le libellé ne revient toujours pas.

    Elle n'ajoute aucun mode de panne : le silence existait déjà. Aujourd'hui comme hier,
    l'appelant reçoit son annotation SANS le libellé qu'il a tapé — ce qui change est
    qu'il n'y a plus rien en base derrière ce silence.

    **Un seul cas voit sa réponse changer**, et il a été mesuré : une note VIDE plus le
    seul libellé illisible. Hier l'annotation naissait quand même, coquille ne portant que
    le tag caché ; aujourd'hui il ne reste rien à enregistrer, donc `put_annotation`
    supprime la ligne et rend `note: null` au lieu de `note: ""`. À l'écran c'est le même
    vide, et la coquille était de toute façon comptée comme NON annotée depuis
    `_sql_a_montrer`. Surtout, cela ne donne aucun bit de plus : ce qui distingue « libellé
    pris ailleurs » de « libellé libre » reste ce qui le distinguait hier — le libellé
    revient, ou il ne revient pas —, et on ne peut pas le retirer sans mentir.

    **Elle n'atteint pas `undo._ensure_tag`, et c'est voulu.** L'annulation repose un
    instantané pris par le journal, qui garde l'annotation ENTIÈRE, cachés compris : y
    poser la même garde ferait de Ctrl+Z l'outil qui efface ce que `_tags_caches`
    protège. Restaurer n'est pas saisir — on ne devine pas un libellé qu'on est en train
    de remettre là où il était.
    """
    normalized = sorted({_norm_tag(l) for l in labels if _norm_tag(l)})
    if not normalized:
        return []
    marques = ",".join("?" * len(normalized))
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    # Deux lectures, et l'écart entre elles EST la garde : tout ce que le libellé désigne
    # déjà dans l'instance, puis ce qu'on en lit. La différence se tait.
    pris = {r["label"] for r in conn.execute(
        f"SELECT label FROM tags WHERE label IN ({marques})", normalized)}
    lisibles = _rows(conn.execute(
        f"SELECT t.id, t.label, t.couleur FROM tags t "
        f"WHERE t.label IN ({marques}) AND {ou_tag}", (*normalized, *p_tag)))
    # Un libellé LIBRE se crée (global, comme avant) ; un libellé pris par un terme qu'on
    # ne lit pas ne se crée pas — l'unicité l'en empêche — et ne s'attache pas.
    neufs = [l for l in normalized if l not in pris]
    for label in neufs:
        conn.execute(
            "INSERT INTO tags (label) VALUES (?) ON CONFLICT(label) DO NOTHING",
            (label,),
        )
    if neufs:
        marques_neufs = ",".join("?" * len(neufs))
        lisibles += _rows(conn.execute(
            f"SELECT id, label, couleur FROM tags WHERE label IN ({marques_neufs})",
            neufs))
    return sorted(lisibles, key=lambda r: r["label"])


def _annotation_selon(conn: sqlite3.Connection, clause_tag: tuple[str, list],
                      region_id: int) -> dict:
    """Représentation d'annotation (note + tags) ; structure vide si absente. Les tags
    rendus sont ceux que `clause_tag` retient — un fragment `(sql, params)` sur
    `t.collection_id`.

    C'est le CŒUR, et il ne tranche rien : il reçoit un fragment plutôt qu'une `Portee`,
    comme `database.lexique_resume`, parce que DEUX questions s'y posent et qu'elles ne
    se confondent pas. Ce qu'une PERSONNE lit (`_annotation_for_region`, l'Atelier) ; ce
    qu'une COLLECTION emporte quand un album sort à son titre (`_vocabulaire_d_export`,
    AUTH-11). Le fragment est OBLIGATOIRE : un défaut qui ne filtrerait rien rendrait
    l'oubli invisible."""
    ann = conn.execute(
        "SELECT id, note, date_creation, date_modification "
        "FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()
    if ann is None:
        return {"region_id": region_id, "note": None, "tags": [],
                "date_modification": None}
    ou_tag, p_tag = clause_tag
    tags = _rows(conn.execute(
        f"""SELECT t.id, t.label, t.couleur
           FROM annotation_tags at JOIN tags t ON t.id = at.tag_id
           WHERE at.annotation_id = ? AND {ou_tag} ORDER BY t.label""",
        (ann["id"], *p_tag),
    ))
    return {"region_id": region_id, "note": ann["note"], "tags": tags,
            "date_modification": ann["date_modification"]}


def _annotation_for_region(conn: sqlite3.Connection, portee, region_id: int) -> dict:
    """L'annotation d'une région telle que CETTE personne la lit.

    Les tags sont ceux dont on lit le TERME (`clause_terme`) : lire une région ne donne
    pas à lire tous les tags qu'elle porte, un tag pouvant être local à une collection
    qu'on ne lit pas. La `Portee` est OBLIGATOIRE, comme dans les accesseurs gardés : une
    valeur par défaut rendrait l'oubli invisible. Ce qu'on ne montre pas, l'écriture
    doit le PRÉSERVER (`_tags_caches`) ; le journal, lui, garde l'annotation ENTIÈRE.

    Ne sert PLUS aux exports d'un album (AUTH-11, 2026-10-07) : un fichier qui sort au
    titre d'une collection ne suit pas la portée de qui clique, cf. `_vocabulaire_d_export`."""
    return _annotation_selon(conn, portee.clause_terme("t.collection_id"), region_id)


def _sql_a_montrer(portee, alias_annotation: str = "a") -> tuple[str, list]:
    """Fragment SQL `(sql, params)` vrai quand une annotation a quelque chose À MONTRER
    à CET appelant : une note non vide, ou au moins un tag dont il lit le terme.

    AUTH-11 — `annotee`, `nb_annotees` et le compteur « annotées » de la Recherche
    lisaient l'EXISTENCE de la ligne `annotations`. Une région dont il ne restait qu'un
    tag local à une collection qu'on ne lit pas s'affichait donc cochée dans l'arbre de
    structure, sans rien d'annoté à l'ouverture : un indice — mineur, mais un indice —
    sur du travail qu'on ne voit pas, et surtout un marqueur qui ment à qui le regarde.

    La ligne vide n'existe pas en base : `put_annotation` SUPPRIME l'annotation dès que
    la note est vide et qu'il ne reste aucun tag, cachés compris. Ce fragment ne change
    donc RIEN pour qui lit tout — il ne se distingue de « la ligne existe » que dans le
    cas exact qu'il ferme. C'est aussi la définition que l'écran applique déjà de son
    côté après un enregistrement (`static/viewer.js`), qui divergeait de celle du serveur.

    Les alias internes sont `_atm` / `_tgm` et non `at` / `t`, exprès. Ce fragment
    s'INSÈRE dans la requête d'un appelant, et `t` est justement l'alias usuel des tags
    dans `routes/recherche.py` et `routes/analyse.py` : un appelant qui passerait
    `alias_annotation="t"` verrait son propre `t` masqué par celui-ci, et la sous-requête
    répondrait faux **sans erreur SQL** — un compteur qui se tait est précisément le
    défaut que ce fragment vient de corriger. Aucun appel actuel n'est concerné ; le piège
    est retiré plutôt que documenté comme une précaution à retenir.
    """
    ou_tag, p_tag = portee.clause_terme("_tgm.collection_id")
    return (f"(TRIM(COALESCE({alias_annotation}.note, '')) <> '' "
            f" OR EXISTS (SELECT 1 FROM annotation_tags _atm "
            f"              JOIN tags _tgm ON _tgm.id = _atm.tag_id "
            f"            WHERE _atm.annotation_id = {alias_annotation}.id AND {ou_tag}))",
            list(p_tag))


def _tags_caches(conn: sqlite3.Connection, portee, region_id: int) -> list[int]:
    """Ids des tags que porte la région et que l'appelant ne LIT pas — l'exact
    complément de ce que montre `_annotation_for_region`.

    Une écriture qui remplace la liste des tags ne reçoit que ce que l'écran a montré.
    Sans ce complément, enregistrer une annotation effacerait, sans un mot, le tag
    d'une collection qu'on ne voit pas — et personne ne le verrait disparaître."""
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    return [r["tag_id"] for r in conn.execute(
        f"""SELECT at.tag_id FROM annotation_tags at
           JOIN annotations an ON an.id = at.annotation_id
           JOIN tags t ON t.id = at.tag_id
           WHERE an.region_id = ? AND NOT ({ou_tag})""",
        (region_id, *p_tag))]


# --------------------------------------------------------------------------- #
# Accesseurs GARDÉS (AUTH-2) — la seule façon d'atteindre un objet du corpus
# --------------------------------------------------------------------------- #
# Chacun exige une `Portee` et renvoie 404 quand l'objet existe mais sort d'elle. Le 404
# n'est pas une approximation du 403 : dire « cet album existe, mais pas pour vous »
# révélerait la composition du corpus — combien d'albums, quelles études voisines. La
# contrepartie est à connaître : qui perd un droit ne verra pas d'erreur, ses objets
# auront simplement disparu.
#
# La `Portee` est un paramètre OBLIGATOIRE, sans valeur par défaut. Une valeur par défaut
# qui sauterait le contrôle rendrait l'oubli invisible — c'est exactement le motif que
# SANTE-1 vient de corriger ailleurs dans ce dépôt.

def _get_album(conn, portee: autorisation.Portee, album_id: int, *,
               ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("albums.id", ecriture=ecriture)
    a = _row(conn.execute(f"SELECT * FROM albums WHERE id = ? AND {ou}",
                          (album_id, *params)))
    if a is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    return a


def _collections_lues_d_albums(conn, portee: autorisation.Portee,
                               album_ids) -> dict[int, list[dict]]:
    """Les collections où chacun de ces albums est rangé — celles que l'appelant LIT, et
    elles seules : `{album_id: [{id, nom, projet_id}, …]}`, par nom. UX-18.

    C'est la règle de `GET /api/albums/{id}/collections`, écrite ICI pour les deux routes
    qui la servent — celle d'un album et la liste de tous (`GET /api/albums`) —, et non
    recopiée dans la seconde : deux écritures du filtre finiraient par ne plus répondre
    pareil. Une collection qu'on ne lit pas n'y laisse RIEN, ni nom, ni identifiant, ni
    trace dans le nombre (« 404, jamais 403 », AUTH-2) : un album partagé avec une étude à
    laquelle on ne participe pas a une liste PARTIELLE, et c'est voulu.

    Le filtre est `Portee.peut_lire`, la question telle qu'`autorisation.py` la tranche,
    et non une clause recopiée. Une seule requête, quel que soit le nombre d'albums.

    Elle ne vérifie PAS qu'on lit les albums eux-mêmes : l'appelant les a déjà passés par
    un accesseur gardé ou par `clause_album`. Un album absent du résultat n'est rangé dans
    aucune collection qu'on lit."""
    ids = sorted({int(i) for i in album_ids})
    par_album: dict[int, list[dict]] = {i: [] for i in ids}
    if not ids:
        return par_album
    for ligne in conn.execute(
            f"SELECT ca.album_id, c.id, c.nom, {sql_projet_de('c')} AS projet_id "
            "FROM collection_album ca JOIN collection c ON c.id = ca.collection_id "
            f"WHERE ca.album_id IN ({', '.join('?' * len(ids))}) "
            "ORDER BY c.nom, c.id", ids):
        if portee.peut_lire(ligne["id"]):
            par_album[ligne["album_id"]].append(
                {"id": ligne["id"], "nom": ligne["nom"], "projet_id": ligne["projet_id"]})
    return par_album


def _get_planche(conn, portee: autorisation.Portee, planche_id: int, *,
                 ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("planches.album_id", ecriture=ecriture)
    p = _row(conn.execute(f"SELECT * FROM planches WHERE id = ? AND {ou}",
                          (planche_id, *params)))
    if p is None:
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    return p


def _get_region(conn, portee: autorisation.Portee, region_id: int, *,
                ecriture: bool = False) -> dict:
    """Une région s'autorise par sa planche, qui s'autorise par son album."""
    ou, params = portee.clause_album("pl.album_id", ecriture=ecriture)
    r = _row(conn.execute(
        f"SELECT r.* FROM regions r JOIN planches pl ON pl.id = r.planche_id "
        f"WHERE r.id = ? AND {ou}", (region_id, *params)))
    if r is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return r


_MOTIF_ADMIN = ("Seul un propriétaire de cette collection peut la partager ou la "
                "modifier.")


def _get_collection(conn, portee: autorisation.Portee, collection_id: int, *,
                    administrer: bool = False, motif: str = _MOTIF_ADMIN) -> dict:
    """Collection VISIBLE (404 sinon) et, si `administrer`, qu'on a le droit de partager.

    Le refus d'administration est un **403** et non un 404 : la collection vient d'être
    listée, on connaît son nom, un « introuvable » mentirait. C'est la distinction
    qu'AUTH-2 fait déjà entre un terme (403, déjà listé) et une donnée (404, l'absence ne
    fuit rien) — ici, la collection est déjà connue de l'appelant.

    `motif` dit CE QU'ON REFUSE, et il ne s'agit pas d'un détail de rédaction. Le texte
    par défaut parle de partager ou modifier la collection, parce que c'est ce que faisait
    l'unique appelant. Un second est arrivé — déposer un export sur ShareDocs (EXP-1) — et
    il héritait de ce message : on refusait à quelqu'un un geste qu'il n'avait pas
    demandé, en lui nommant deux autres qu'il n'avait pas tentés. Mesuré en jouant le cas
    à la main, pas par un test : les tests vérifiaient le CODE 403, jamais ce qu'il dit.

    IL A VÉCU DANS `routes/collections.py` jusqu'au 2026-09-07, et il en descend le jour où
    un SECOND domaine en a besoin (EXP-1, l'export de dépôt). C'est la place que la
    doctrine ARCH-1 lui donne : les accesseurs gardés vivent ici parce qu'« la seule façon
    d'atteindre un objet » était une convention, et qu'un module qu'il faut IMPORTER en
    fait une contrainte visible. Le laisser là-haut aurait obligé un module de routes à en
    importer un autre, ou — bien pire — à redériver la garde, ce que ce bloc existe
    précisément pour interdire.
    """
    c = collection_row(conn, collection_id)
    if c is None or not portee.peut_lire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    if administrer and not portee.peut_administrer(collection_id):
        raise HTTPException(403, motif)
    return c


_MOTIF_PROJET = "Seul un responsable de ce projet peut régler qui y entre."


def _get_projet(conn, portee: autorisation.Portee, projet_id: int, *,
                gerer: bool = False, motif: str = _MOTIF_PROJET) -> dict:
    """Projet qu'on peut NOMMER (404 sinon) et, si `gerer`, dont on règle les membres.

    Le jumeau de `_get_collection`, un étage plus haut, et la même distinction : 404 sur
    un projet qu'on ne voit pas — dire qu'il existe révélerait une étude voisine —, 403
    NOMMÉ sur un projet qu'on voit sans le gérer, puisque son nom est déjà à l'écran et
    qu'un « introuvable » mentirait. `motif` dit ce qu'on refuse, pour la raison écrite
    ci-dessus : le texte par défaut ne vaut que pour le geste de régler les membres.

    La ligne rendue est BRUTE, `justification` comprise : c'est à la route de décider ce
    qu'elle en montre, et à qui (`routes/projets.py`)."""
    ou, params = portee.clause_projet("p.id")
    p = _row(conn.execute(f"SELECT p.* FROM projet p WHERE p.id = ? AND {ou}",
                          (projet_id, *params)))
    if p is None:
        raise HTTPException(404, f"Projet {projet_id} introuvable")
    if gerer and not portee.peut_gerer_projet(projet_id):
        raise HTTPException(403, motif)
    return p


# --------------------------------------------------------------------------- #
# DÉTRUIRE n'est pas écrire (AUTH-10), et « supprimer » a deux réponses (COL-3)
# --------------------------------------------------------------------------- #
# Comme pour l'export, ce helper ne tranche rien : `Portee.clause_suppression_directe` dit
# qui peut supprimer quoi DÉFINITIVEMENT, sans rien demander. Il dit comment REFUSER, et le
# refus est un 403 NOMMÉ — il ne s'appelle qu'APRÈS l'accesseur gardé en écriture, donc sur
# un album que l'appelant lit et annote : un « introuvable » lui mentirait.
#
# Le refus ne dit PAS laquelle des conditions manque — une autre collection le porte, ce
# n'est pas lui qui l'a importé, quelqu'un d'autre y a travaillé : la phrase de la maquette
# les dit ensemble, et c'est la bonne (cadrage de la tranche 2). Ce qu'elle révèle reste ce
# qu'AUTH-10 avait accepté par écrit le 2026-10-08 : qu'un AUTRE usage existe, jamais
# lequel. Elle dit aussi les deux gestes qui restent : supprimer l'album de sa collection —
# il est gardé au fonds —, ou demander. Une planche n'a ni l'un ni l'autre (décision B4) :
# sa suppression se dit à un administrateur.
_MOTIF_DESTRUCTION = ("D'autres s'en servent, ou ce n'est pas vous qui l'avez importé : "
                      "supprimer définitivement cet album se demande à un administrateur. "
                      "Vous pouvez le supprimer de votre collection, où il est gardé au "
                      "fonds avec son travail.")
_MOTIF_DESTRUCTION_PLANCHE = ("D'autres se servent de cet album, ou ce n'est pas vous qui "
                              "l'avez importé : supprimer l'une de ses planches se demande "
                              "à un administrateur de l'instance.")


def _exiger_destruction(conn, portee: autorisation.Portee, album_id: int, *,
                        planche: bool = False) -> None:
    """403 si l'on ne peut pas supprimer DÉFINITIVEMENT cet album — ou, `planche`, l'une
    de ses planches : on supprime une planche là où l'on pourrait supprimer le document
    (décision B4 de Hugo, 2026-10-11)."""
    ou, params = portee.clause_suppression_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                    (album_id, *params)).fetchone() is None:
        raise HTTPException(403, _MOTIF_DESTRUCTION_PLANCHE if planche
                            else _MOTIF_DESTRUCTION)


def _detruire_album(conn, portee: autorisation.Portee, album_id: int) -> None:
    """DÉTRUIT un album — sa ligne, son travail, son document s'il n'a plus d'autre copie,
    ses images —, garde comprise. Le seul chemin de la destruction d'un album : la route
    `DELETE /api/albums/{id}` et la réponse « accepter » à une demande (`routes/fonds.py`)
    y passent toutes deux, et la garde vit ICI pour qu'aucune des deux ne l'oublie.

    Il COMMITE, puis efface les fichiers : à appeler en DERNIER, après tout ce qui doit
    partir dans la même transaction. Les fichiers quittent le disque après le commit, et
    pas avant : une base qui refuserait d'écrire laisserait sinon un album sans images.

    Ce qu'il écrit au journal : la fin de chacun des emplois de la copie (la cascade défait
    ses rangements sans rien dire), puis la destruction du document. Et il CLÔT toute
    demande de suppression qui visait ce document : elle a reçu sa réponse, quel que soit
    le geste qui l'a donnée — l'importateur qui détruit lui-même ce qu'un autre avait
    demandé, ou l'administrateur.

    La garde se lit SOUS LE VERROU D'ÉCRITURE (`conflit.verrouiller`, le remède de CONC-3),
    et la destruction suit dans la même transaction. Lue hors transaction, elle laissait
    passer un travail validé entre la garde et le `DELETE` : il partait avec l'album, sans
    que personne l'ait demandé (relecture croisée de la tranche 2, sonde S9)."""
    conflit.verrouiller(conn)
    _exiger_destruction(conn, portee, album_id)
    a = _row(conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)))
    # Désindexe les régions du FTS (le CASCADE SQL ne touche pas la table FTS).
    for r in conn.execute(
        "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id "
        "WHERE p.album_id = ?", (album_id,)).fetchall():
        unindex_region(conn, r["id"])
    # Les chemins de ses images, relevés AVANT le `DELETE` qui emporte les planches : ceux
    # qu'aucune autre planche n'emploie quitteront le disque après le commit.
    chemins = [(r[0], r[1]) for r in conn.execute(
        "SELECT chemin_tiff, chemin_web FROM planches WHERE album_id = ?", (album_id,))]
    nb_planches = len(chemins)
    # Détruire l'album met fin à chacun de ses emplois : la cascade défait les liens sans
    # rien dire, comme quand on supprime une collection, et un journal où un rangement
    # n'aurait jamais de fin laisserait croire le document encore employé. Écrits AVANT le
    # `DELETE`, tant que l'album se lit encore.
    for (collection_id,) in conn.execute(
            "SELECT collection_id FROM collection_album WHERE album_id = ? "
            "ORDER BY collection_id", (album_id,)).fetchall():
        journal.journaliser_emploi(conn, "delien", album_id, collection_id)
    conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))   # CASCADE planches/regions
    # Le document part avec sa dernière copie, et sa destruction s'écrit : le journal est
    # tout ce qui reste de lui, ses images quittant le disque juste après. Un album SANS
    # document — posé par `INSERT` — l'écrit aussi, sous une cible vide, comme ses scans et
    # ses emplois : l'acte a eu lieu. Seul cas qui n'écrit pas de `suppression` : une autre
    # copie porte encore le document, qui n'est donc pas détruit.
    document_id = a["document_id"]
    if retirer_document_sans_copie(conn, document_id) or document_id is None:
        journal.journaliser(conn, "suppression", "document", document_id,
                            avant={"album_id": album_id, "titre": a["titre"],
                                   "planches": nb_planches})
    # Les demandes qui visaient CETTE copie ont leur réponse (COL-3, tranche 3) : une
    # demande se dépose sur une copie (`demande_document.album_id`), et celle d'une sœur,
    # dans un autre projet, attend toujours la sienne.
    _clore_demandes(conn, portee, [r[0] for r in conn.execute(
        "SELECT d.id FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
        "WHERE d.genre = ? AND dd.album_id = ? AND d.reponse IS NULL",
        (DEMANDE_SUPPRESSION_DOCUMENT, album_id))], REPONSE_ACCEPTEE)
    conn.commit()
    _effacer_les_images_d_une_copie(conn, album_id, chemins)


def _chemins_employes(conn, chemins) -> set:
    """Ceux de ces chemins d'image (la forme de `planches.chemin_*`) qu'une planche désigne
    ENCORE — celle d'une copie sœur, qui emploie les fichiers de la copie dont elle a été
    tirée (COL-3, tranche 3, D6). Une requête, quel que soit le nombre de chemins."""
    voulus = sorted({c for c in chemins if c})
    if not voulus:
        return set()
    marques = ", ".join("?" * len(voulus))
    return {c for r in conn.execute(
        f"SELECT chemin_tiff, chemin_web FROM planches WHERE chemin_tiff IN ({marques}) "
        f"OR chemin_web IN ({marques})", voulus * 2) for c in r if c in voulus}


def _effacer_les_images_d_une_copie(conn, album_id: int, chemins) -> None:
    """Après le commit d'une destruction : efface les images d'une copie PAR RÉFÉRENCE
    (COL-3, tranche 3, D6). Les images appartiennent au document, et une copie sœur pointe
    vers les fichiers de celle dont elle a été tirée — un fichier ne quitte donc le disque
    que lorsque plus aucune planche ne le désigne. C'est le risque irréversible de la
    tranche : une image effacée sous une sœur ne se rattrape pas.

    Deux moitiés. Les dossiers `album_<id>` de la copie : ce qu'une autre planche y emploie
    reste, le reste part — et en entier, comme avant, quand rien n'y est employé. Puis les
    fichiers que la copie employait AILLEURS — dans le dossier d'une copie détruite avant
    elle : partis s'ils ne sont plus désignés, et leur dossier élagué s'il est vide. Un
    identifiant d'album ne revenant plus depuis la v30, un dossier qui survit ainsi à sa
    copie n'est jamais repris par un album neuf."""
    # Relecture croisée de la v31 : sans forme RELATIVE des dossiers, rien ne se recoupe
    # avec les chemins de la base — on ne saurait pas ce qu'une sœur emploie. Rien n'est
    # effacé, et le journal du serveur le dit : un dossier laissé se rattrape, une image
    # effacée sous une sœur, non.
    try:
        dossiers = dossiers_d_album(album_id)
    except ValueError:
        logging.getLogger("bd_annotator").warning(
            "Album %s détruit : ses images sont hors de la racine de données, elles ne "
            "se recoupent pas avec la base et restent sur le disque.", album_id)
        return
    longueurs = [x for d in dossiers for x in (len(d), d)]
    garder = {c for r in conn.execute(
        "SELECT chemin_tiff, chemin_web FROM planches "
        "WHERE substr(chemin_tiff, 1, ?) = ? OR substr(chemin_tiff, 1, ?) = ? "
        "OR substr(chemin_web, 1, ?) = ? OR substr(chemin_web, 1, ?) = ?",
        longueurs * 2) for c in r if c}
    remove_album_files(album_id, garder=garder)
    # Ailleurs que dans ses dossiers, seulement ce qui a bien la forme d'une image d'album
    # (`ingest.chemin_d_image_sur`) : une ligne retouchée ne fait rien effacer d'autre.
    ailleurs = [c for paire in chemins for c in paire
                if c and not c.startswith(dossiers) and chemin_d_image_sur(c)]
    employes = _chemins_employes(conn, ailleurs)
    for c in ailleurs:
        if c not in employes:
            remove_planche_files(c, None)
            elaguer_dossier_d_album(c)


def _clore_demandes(conn, portee: autorisation.Portee, ids, reponse: str) -> None:
    """Donne sa RÉPONSE à des demandes en attente — et à chacun de leurs documents —, et
    l'écrit au journal. Ne commite pas. Une demande répondue RESTE : c'est ce qui permet de
    dire qu'une même suppression a déjà été refusée, et le journal garde qui a répondu.

    `repondu_par` est l'appelant : l'administrateur qui répond, ou celui dont le geste a
    satisfait la demande — l'importateur qui détruit ce qu'un autre avait demandé.

    Une demande qui a DÉJÀ sa réponse n'en reçoit pas d'autre, et rien ne s'écrit au
    journal pour elle : la ligne disait jusqu'ici une réponse qu'aucun `UPDATE` n'avait
    posée (relecture croisée de la tranche 2)."""
    for demande_id in ids:
        if not conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                            "date_reponse = datetime('now') WHERE id = ? AND reponse IS NULL",
                            (reponse, portee.utilisateur, demande_id)).rowcount:
            continue
        conn.execute("UPDATE demande_document SET reponse = ? "
                     "WHERE demande_id = ? AND reponse IS NULL", (reponse, demande_id))
        journal.journaliser(conn, "modification", "demande", demande_id,
                            avant={"reponse": None}, apres={"reponse": reponse})


def _supprimer_projet(conn, portee: autorisation.Portee, p: dict) -> None:
    """Supprime un projet VIDE, ou refuse en se NOMMANT. Ne commite pas. Les deux chemins
    de la suppression d'un projet y passent : la route (`DELETE /api/projets/{id}`) et la
    réponse « accepter » à la demande de son responsable (`routes/fonds.py`). La question
    du DROIT reste chez l'appelant : décider des projets, ou tenir le fonds.

    Trois refus, tous des 409 : le projet de REPLI, où tombe toute collection qui ne nomme
    pas le sien ; un projet qui PORTE une collection — la reverser en silence dans le repli
    la ferait changer de projet sans que personne l'ait décidé ; et un projet dont des
    copies sont GARDÉES AU FONDS (`albums.projet_id`) — supprimé, il les laisserait
    désigner un projet qui n'existe plus, et dont l'identifiant, rendu au suivant, les
    ferait passer dans un autre. Les détruire d'abord, depuis le fonds ; à la tranche
    suivante, elles pourront aussi être confiées à un autre projet. La clé étrangère, sans
    action, est la ceinture derrière ces refus.

    Accepté, il clôt aussi toute demande de suppression qui le visait. Ses refus se lisent
    sous le verrou d'écriture, pour la raison écrite sur `_detruire_album` : une collection
    créée entre le compte et le `DELETE` ferait sinon tomber la clé étrangère en 500."""
    conflit.verrouiller(conn)
    projet_id = p["id"]
    if p["repli"]:
        raise HTTPException(409, "C'est le projet de repli : les collections qui ne "
                                 "nomment aucun projet y sont rangées. Il se renomme, il "
                                 "ne se supprime pas.")
    # La collection de BASE (D10) ne compte pas comme une collection du projet tant qu'elle
    # est VIDE : née avec lui, elle part avec lui. Elle ne se supprime pas seule, si bien que
    # la compter rendrait tout projet insupprimable. Portant un album, elle le retient — la
    # supprimer enverrait l'album au fonds par ricochet, le refus de `delete_collection`.
    n = conn.execute(f"SELECT COUNT(*) FROM collection c WHERE {sql_projet_de('c')} = ? "
                     "AND c.base = 0", (projet_id,)).fetchone()[0]
    if n:
        raise HTTPException(409, f"{n} collection(s) appartiennent à ce projet : un "
                                 "projet ne se supprime que vide.")
    bases = conn.execute(
        "SELECT c.id, c.nom, (SELECT COUNT(*) FROM collection_album ca "
        "                     WHERE ca.collection_id = c.id) AS n "
        f"FROM collection c WHERE {sql_projet_de('c')} = ? AND c.base = 1",
        (projet_id,)).fetchall()
    habitees = sum(b["n"] for b in bases)
    if habitees:
        raise HTTPException(409, f"Sa collection de base porte encore {habitees} album(s) : "
                                 "rangez-les ailleurs, ou supprimez-les d'abord de la "
                                 "collection. Un projet ne se supprime que vide.")
    # Une base qui porte du VOCABULAIRE local n'est pas vide non plus (relecture croisée) :
    # supprimée, ses termes deviendraient GLOBAUX (`ON DELETE SET NULL`), donc visibles de
    # toute l'instance — une grille d'analyse qui fuit, ce qu'AUTH-2 (v24) ferme ailleurs.
    # Le refus le nomme ; c'est à qui le tient de le promouvoir ou de le supprimer, en le
    # sachant.
    ids = [b["id"] for b in bases]
    termes = sum(conn.execute(
        f"SELECT COUNT(*) FROM {t} WHERE collection_id IN ({', '.join('?' * len(ids))})",
        ids).fetchone()[0] for t in ("domaine", "attribut_dimension", "attribut_valeur",
                                     "tags")) if ids else 0
    if termes:
        raise HTTPException(409, f"Sa collection de base porte {termes} terme(s) de "
                                 "vocabulaire qui lui sont propres : supprimés avec elle, "
                                 "ils deviendraient visibles de toute l'instance. Rendez-les "
                                 "globaux, ou supprimez-les, d'abord. Un projet ne se "
                                 "supprime que vide.")
    # Lu dans la colonne ÉCRITE, pas par la règle de lecture : c'est elle que la clé
    # étrangère garde, et c'est elle qui porte le projet d'une copie au fonds. Un album
    # encore rangé est déjà arrêté par le refus du dessus. Le compte ne dit rien de plus
    # que ce que voit qui décide des projets — une portée totale, qui lit tout album.
    #
    # Deux cas, comptés à part : la phrase « gardés au fonds » était fausse pour un album
    # encore rangé dans une collection d'un AUTRE projet (relecture croisée) — un état
    # interdit, qu'une base retouchée porte, et que `albums_hors_de_leur_projet` nomme.
    au_fonds, ailleurs = conn.execute(
        "SELECT COALESCE(SUM(NOT EXISTS (SELECT 1 FROM collection_album ca "
        "                                WHERE ca.album_id = a.id)), 0), "
        "       COALESCE(SUM(EXISTS (SELECT 1 FROM collection_album ca "
        "                            WHERE ca.album_id = a.id)), 0) "
        "FROM albums a WHERE a.projet_id = ?", (projet_id,)).fetchone()
    if au_fonds or ailleurs:
        raisons = []
        if au_fonds:
            raisons.append(f"{au_fonds} album(s) de ce projet sont gardés au fonds, hors de "
                           "toute collection — détruisez-les d'abord depuis le fonds")
        if ailleurs:
            raisons.append(f"{ailleurs} album(s) désignent ce projet en étant rangés dans "
                           "la collection d'un autre — un état qu'une base retouchée "
                           "produit, à réparer à la main")
        raise HTTPException(409, " ; ".join(raisons) + ". Un projet ne se supprime que "
                                 "lorsque plus aucun album n'en est.")
    _clore_demandes(conn, portee, [r[0] for r in conn.execute(
        "SELECT id FROM demande WHERE genre = ? AND projet_id = ? AND reponse IS NULL",
        (DEMANDE_SUPPRESSION_PROJET, projet_id))], REPONSE_ACCEPTEE)
    # Sa base VIDE — ni album ni vocabulaire à elle, refusés plus haut — part avec lui ;
    # ses accès posés partent par cascade.
    for b in bases:
        conn.execute("DELETE FROM collection WHERE id = ?", (b["id"],))
        journal.journaliser(conn, "suppression", "collection", b["id"],
                            avant={"nom": b["nom"], "base": True})
    conn.execute("DELETE FROM projet WHERE id = ?", (projet_id,))
    journal.journaliser(conn, "suppression", "projet", projet_id, avant={"nom": p["nom"]})


# --------------------------------------------------------------------------- #
# Le droit d'EXPORTER (DROIT-2) — une garde sur ce qui SORT de l'instance
# --------------------------------------------------------------------------- #
# Ces helpers ne tranchent rien : `autorisation.Portee` dit qui peut sortir quoi. Ils
# disent comment REFUSER, et le refus est un 403 NOMMÉ, jamais un 404 — l'objet est
# lisible, on vient de l'afficher, et un « introuvable » mentirait.
_MOTIF_EXPORT = ("Exporter demande le droit d'exporter, que le propriétaire d'une "
                 "collection accorde collection par collection : la lire ou l'annoter "
                 "n'y suffit pas.")


def _exiger_export(portee: autorisation.Portee, collection_id: int) -> None:
    """403 si l'on voit la collection sans pouvoir en sortir le contenu."""
    if not portee.peut_exporter(collection_id):
        raise HTTPException(403, _MOTIF_EXPORT)


def _portee_d_export(portee: autorisation.Portee) -> autorisation.Portee:
    """La portée d'un export qui TRAVERSE plusieurs collections (Recherche, Exploration) :
    ce qu'on peut sortir, et non ce qu'on lit — sans quoi qui exporte A emporterait le
    texte de B dans une concordance qui couvre les deux. 403 si l'on n'exporte nulle
    part : le fichier serait vide, et un refus qui dit pourquoi vaut mieux qu'un fichier
    qui se tait."""
    if not portee.peut_exporter_quelque_part():
        raise HTTPException(403, _MOTIF_EXPORT)
    return portee.pour_export()


def _exiger_export_region(conn, portee: autorisation.Portee, region_id: int) -> None:
    """403 si la région — qu'on LIT, l'accesseur gardé l'a vérifié avant — appartient à
    un album qu'aucune des collections qu'on peut exporter ne contient."""
    ou, params = portee.pour_export().clause_album("pl.album_id")
    if conn.execute(f"SELECT 1 FROM regions r JOIN planches pl ON pl.id = r.planche_id "
                    f"WHERE r.id = ? AND {ou}", (region_id, *params)).fetchone() is None:
        raise HTTPException(403, _MOTIF_EXPORT)


def _collection_d_export(conn, portee: autorisation.Portee, album_id: int,
                         collection_id: Optional[int] = None) -> dict:
    """Au titre de QUELLE collection cet album sort-il ? Rend `{"id", "nom"}`.  DROIT-2.

    Un album vit dans plusieurs collections, et le droit d'exporter peut être accordé sur
    l'une et pas sur l'autre. « Au moins une » était permissif ; « toutes » fermait un
    album dès son second rangement. Tranché le 2026-09-11 : il sort AU TITRE d'une
    collection où l'on a le droit — le patron du manifeste IIIF —, et l'export le dit.

    - nommée : elle doit contenir l'album et être lue (404 sinon), et s'exporter (403) ;
    - non nommée : la seule collection exportable de l'album ; aucune, 403 ; plusieurs,
      un 422 qui les NOMME, parce que le choix appartient à qui exporte, pas au code.

    **La portée totale suit la MÊME règle** (Hugo, 2026-10-07) — renversement daté du
    « en mono-poste, rien à nommer » de DROIT-2, restreint au cas multi-collections. Elle
    rendait `None` pour un album rangé dans plusieurs collections sans qu'aucune soit
    nommée : « il ne sort alors sous aucun droit particulier ». C'était tenable tant que le
    titre n'était qu'une ÉTIQUETTE ; depuis AUTH-11 il gouverne le CONTENU
    (`_vocabulaire_d_export`), et un export sans titre était le seul dont rien ne bornait
    le vocabulaire. Il n'y a donc plus de branche à part : `peut_exporter` répond déjà
    vrai partout en portée totale, et le 422 nommé vaut pour l'administrateur et le
    mono-poste comme pour les autres. Une seule collection : rien à nommer, comme avant.

    **Cette fonction ne rend JAMAIS `None`.** Le dernier chemin qui y menait est un album
    rangé dans AUCUNE collection — une copie gardée au FONDS depuis COL-3 (tranche 2),
    supprimée de sa dernière collection ou importée au fonds ; seule une portée totale lit
    alors l'album. Il répond 409 en nommant l'état : un 403 « droit d'exporter » mentirait
    à qui a tous les droits, et le laisser sortir rouvrirait l'export sans titre."""
    rows = _rows(conn.execute(
        "SELECT c.id, c.nom FROM collection_album ca "
        "JOIN collection c ON c.id = ca.collection_id "
        "WHERE ca.album_id = ? ORDER BY c.nom, c.id", (album_id,)))
    if collection_id is not None:
        c = next((r for r in rows
                  if r["id"] == collection_id and portee.peut_lire(r["id"])), None)
        if c is None:
            raise HTTPException(404, f"Collection {collection_id} introuvable pour cet album")
        _exiger_export(portee, collection_id)
        return c
    if not rows:
        raise HTTPException(
            409, "Cet album n'est rangé dans aucune collection : il ne peut sortir au "
                 "titre d'aucune. Rangez-le dans une collection avant de l'exporter.")
    ouvertes = [r for r in rows if portee.peut_exporter(r["id"])]
    if not ouvertes:
        raise HTTPException(403, _MOTIF_EXPORT)
    if len(ouvertes) > 1:
        raise HTTPException(
            422, "Cet album vit dans plusieurs collections que vous pouvez exporter : "
                 "précisez au titre de laquelle il sort (`collection_id`) — "
                 + ", ".join(f"« {r['nom']} » ({r['id']})" for r in ouvertes) + ".")
    return ouvertes[0]


def _vocabulaire_d_export(titre: dict,
                          alias: str = "t.collection_id") -> tuple[str, list]:
    """Le VOCABULAIRE qu'emporte un album qui sort au titre de `titre` — fragment SQL
    `(sql, params)` sur la colonne `collection_id` d'un terme.  AUTH-11, 2026-10-07.

    `titre` est ce que rend `_collection_d_export` : la collection AU TITRE DE LAQUELLE
    l'album sort, qu'elle ait été nommée ou choisie par défaut. L'album n'emporte que le
    vocabulaire de celle-là et le vocabulaire global — **quel que soit qui exporte**.
    C'est la règle du dépôt, et la même fonction (`database.clause_appartenance`), pas
    une seconde écriture.

    Avant, ces exports suivaient la portée d'export de la PERSONNE (`pour_export` →
    `clause_terme`) : le même fichier, étiqueté A, portait un tag local à B pour qui
    exporte aussi B et pas pour qui n'exporte que A. Pas un accès indu — un artefact qui
    variait selon qui clique, sous une étiquette qui ne variait pas.

    Ce fragment ne restreint jamais MOINS que la personne : `titre` est une collection
    qu'elle a le droit d'exporter (`_collection_d_export` l'a vérifié), donc « global ⊕
    local à A » est inclus dans ce que sa portée d'export lui laissait sortir. Le DROIT
    reste celui de DROIT-2 et se décide avant ; ici on ne dit que ce que le fichier porte.

    Il ne borne que le VOCABULAIRE. Les données de l'album — régions, texte, notes —
    sortent entières : une région qui porte un tag d'ailleurs garde son annotation, sans
    ce tag ; et s'il n'en reste rien à montrer, elle n'est plus dite annotée (la règle de
    `_sql_a_montrer`, que les trois exports appliquent en lisant ce qui RESTE).

    **`titre` n'est jamais `None`** (2026-10-07) : `_collection_d_export` rend toujours une
    collection ou lève. Un export « sans titre » a existé une journée comme limite écrite
    — portée totale, plusieurs collections, aucune nommée — et il ne bornait rien ; il
    répond désormais 422. Aucun repli n'est donc écrit ici : un `None` lèverait un
    `TypeError` bruyant, là où un `clause_appartenance(None)` rendrait « corpus entier »
    en silence — exactement l'export non borné qu'on vient de fermer.

    Les exports TRANSVERSAUX (Recherche, Exploration) ne passent pas par ici : ils ne
    sortent au titre d'aucune collection et suivent la personne (`_portee_d_export`)."""
    return clause_appartenance(titre["id"], alias)


def _refuser_si_verrouillee(planche: dict) -> dict:
    """Une planche verrouillée est protégée des passes AUTOMATIQUES (segmentation /
    détection de bulles / OCR) : il faut la déverrouiller explicitement. L'édition
    manuelle (texte, tags, régions) reste libre. Renvoie la planche pour chaînage."""
    if planche.get("verrouillee"):
        raise HTTPException(409, "Planche verrouillée 🔒 : déverrouillez-la pour "
                            "relancer un traitement automatique "
                            "(l'édition manuelle reste possible).")
    return planche


def _validate_parent(conn: sqlite3.Connection, planche_id: int,
                     parent_id: Optional[int], region_id: Optional[int] = None) -> None:
    """Valide un parent_id : il doit exister, être sur LA MÊME planche, et ne pas
    créer de cycle (ni s'auto-référencer). Lève HTTPException 422 sinon. Une FK
    seule ne garantit pas ces invariants — sans quoi une région cross-planche ou
    un cycle casse l'export (région omise) et fait boucler le DELETE récursif."""
    if parent_id is None:
        return
    parent = _row(conn.execute(
        "SELECT planche_id FROM regions WHERE id = ?", (parent_id,)))
    if parent is None:
        raise HTTPException(422, f"parent_id {parent_id} introuvable")
    if parent["planche_id"] != planche_id:
        raise HTTPException(422, "parent_id appartient à une autre planche")
    if region_id is not None:
        if parent_id == region_id:
            raise HTTPException(422, "Une région ne peut pas être son propre parent")
        # parent_id ne doit pas être un descendant de region_id (UNION → termine
        # même si la base contient déjà un cycle).
        descendants = {r["id"] for r in conn.execute(
            """WITH RECURSIVE d(id) AS (
                   SELECT id FROM regions WHERE id = ?
                   UNION
                   SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
               ) SELECT id FROM d""", (region_id,))}
        if parent_id in descendants:
            raise HTTPException(422, "parent_id créerait un cycle")

# --------------------------------------------------------------------------- #
# Accesseurs GARDÉS du VOCABULAIRE (AUTH-2) — VOIR n'est pas CHANGER
# --------------------------------------------------------------------------- #
# Même garde que ci-dessus, autre règle : un terme se VOIT par `clause_terme` (global,
# ou local à une collection qu'on lit) et se MODIFIE par `peut_ecrire_terme`. D'où le
# refus en 403 et non en 404 — le terme vient d'être listé, prétendre qu'il n'existe
# pas serait incohérent, et le refus ne parle que des droits de l'appelant.
#
# Ils descendent ici parce qu'ils sont à CHEVAL sur la coupe : définis dans le bloc
# Personnages, ils servent au bloc Collections (lexique) — les laisser en place aurait
# obligé `routes/collections.py` à remonter vers `main`, ce qu'un cliquet interdit.

def _get_dimension(conn, portee: autorisation.Portee, dim_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    d = _row(conn.execute(
        f"SELECT t.* FROM attribut_dimension t WHERE t.id = ? AND {ou}", (dim_id, *params)))
    if d is None:
        raise HTTPException(404, f"Dimension {dim_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(d.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return d


def _get_valeur(conn, portee: autorisation.Portee, val_id, *, ecriture: bool = False):
    """Terme du vocabulaire, VISIBLE (404 sinon) et, si `ecriture`, MODIFIABLE.

    Le refus d'écriture est un 403 et non un 404, contrairement aux données : le
    terme vient d'être listé, prétendre qu'il n'existe pas serait incohérent — et
    le refus ne parle que des droits de l'appelant, il ne fuit rien.
    """
    ou, params = portee.clause_terme("t.collection_id")
    v = _row(conn.execute(
        f"SELECT t.* FROM attribut_valeur t WHERE t.id = ? AND {ou}", (val_id, *params)))
    if v is None:
        raise HTTPException(404, f"Valeur d'attribut {val_id} introuvable")
    if ecriture and not portee.peut_ecrire_terme(v.get("collection_id")):
        raise HTTPException(403, "Ce terme du vocabulaire est en lecture seule "
                                 "pour vous.")
    return v


def _attributs_de(conn, portee, table, col, oid):
    """Valeurs (avec leur dimension) affectées à une cible (personnage | région).

    AUTH-2 — les valeurs sont filtrées comme des TERMES : sans cela, un objet partagé
    (typiquement un personnage, qui traverse les albums) exposerait le vocabulaire privé
    d'une autre étude — sa grille d'analyse, pas seulement un mot. Écart trouvé en
    relisant : `GET /api/attributs/valeurs` masquait déjà ces termes, mais on les
    retrouvait ici par la bande.

    Conséquence assumée : la liste d'attributs d'un objet peut être PARTIELLE. C'est le
    bon compromis — un objet peut légitimement porter les annotations d'études auxquelles
    on ne participe pas, et il vaut mieux ne pas les montrer que de montrer un vocabulaire
    qu'on ne peut ni comprendre ni situer.

    La DIMENSION est filtrée à son tour (relecture du 2026-08-28). Les routes de création
    ne posaient aucun `collection_id` : toute base antérieure à v24 contient des valeurs
    globales sous des axes privés, et c'est le NOM de l'axe qui fuit, pas le mot. Les
    créations héritent désormais de leur parent, et la migration v24 recolle l'existant ;
    ce filtre-ci reste la ceinture.
    """
    ou, params = portee.clause_terme("v.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    return _rows(conn.execute(
        f"SELECT v.id AS valeur_id, v.valeur, d.id AS dimension_id, d.nom AS dimension, d.cible "
        f"FROM {table} x JOIN attribut_valeur v ON v.id = x.valeur_id "
        f"JOIN attribut_dimension d ON d.id = v.dimension_id "
        f"WHERE x.{col} = ? AND {ou} AND {ou_dim} ORDER BY d.nom, v.valeur",
        (oid, *params, *p_dim)))


_ETATS_LEXIQUE = ("provisoire", "defini")


# v24 — de qui un terme DÉPEND. Absent de cette table = aucun parent : un `domaine` est
# la racine, et un `tag` est plat (aucune colonne ne le rattache à quoi que ce soit), donc
# sa promotion ne bute jamais. La chaîne fait TROIS niveaux au plus, ce qui est la raison
# pour laquelle un refus peut nommer tout ce qui manque au lieu d'en citer un et de laisser
# découvrir le reste au coup suivant.
_PARENT_TERME = {
    "attribut_valeur": ("attribut_dimension", "dimension_id", "valeur"),
    "attribut_dimension": ("domaine", "domaine_id", "nom"),
}
_NOM_TERME = {"attribut_valeur": "valeur", "attribut_dimension": "nom",
              "domaine": "nom", "tags": "label"}
_LIBELLE = {"attribut_valeur": "valeur", "attribut_dimension": "dimension",
            "domaine": "domaine", "tags": "tag"}


def _ancetres_terme(conn, table, oid) -> list:
    """La chaîne de dépendance d'un terme, du parent immédiat vers la racine.

    Chaque entrée : (table, id, nom, collection_id). Vide pour un domaine ou un tag.
    """
    chaine = []
    while table in _PARENT_TERME:
        p_table, fk, _ = _PARENT_TERME[table]
        ligne = conn.execute(f"SELECT {fk} FROM {table} WHERE id = ?", (oid,)).fetchone()
        if ligne is None or ligne[fk] is None:
            break
        parent = conn.execute(
            f"SELECT id, {_NOM_TERME[p_table]} AS nom, collection_id "
            f"FROM {p_table} WHERE id = ?", (ligne[fk],)).fetchone()
        if parent is None:
            break
        chaine.append((p_table, parent["id"], parent["nom"], parent["collection_id"]))
        table, oid = p_table, parent["id"]
    return chaine


def _descendre_portee(conn, table, oid, cible) -> list:
    """Fait DESCENDRE une portée aux termes qui en dépendent et deviendraient plus globaux.

    Symétrique de la garde de promotion, et nécessaire pour la même raison : rendre un
    terme plus LOCAL peut laisser ses enfants au-dessus de lui. C'est la logique de la
    migration v24 — « le domaine descend vers ses dimensions, qui descendent vers leurs
    valeurs » — appliquée aux routes, qui ne l'avaient jamais eue.

    RÉSERVE de la migration, gardée telle quelle : on ne touche QUE les enfants GLOBAUX,
    c'est-à-dire ceux qui violeraient l'invariant. Un enfant déjà local à une autre
    collection est un fait délibéré, pas une omission, et l'écraser déplacerait chez
    quelqu'un le vocabulaire de quelqu'un d'autre.
    """
    if cible is None:                      # devenir global ne peut rien rendre trop global
        return []
    enfants = [(t, fk) for t, (p, fk, _) in _PARENT_TERME.items() if p == table]
    bouges = []
    for t_enfant, fk in enfants:
        lignes = conn.execute(
            f"SELECT id, {_NOM_TERME[t_enfant]} AS nom FROM {t_enfant} "
            f"WHERE {fk} = ? AND collection_id IS NULL", (oid,)).fetchall()
        for l in lignes:
            conn.execute(f"UPDATE {t_enfant} SET collection_id = ? WHERE id = ?",
                         (cible, l["id"]))
            bouges.append(f"{_LIBELLE[t_enfant]} « {l['nom']} »")
            bouges += _descendre_portee(conn, t_enfant, l["id"], cible)
    return bouges


def _patch_lexique(conn, table, oid, payload, portee, *, col_definition="definition"):
    """Mise à jour PARTIELLE de la couche définitionnelle (definition/note_portee/etat/
    collection_id) d'un terme. `col_definition='description'` pour les tags (leur glose EST
    la définition). Valide l'état et l'existence de la collection de portée. Champ omis =
    inchangé ; `collection_id: null` explicite = promotion en global."""
    fields = payload.model_dump(exclude_unset=True)
    fields.pop("promouvoir_parents", None)      # une INSTRUCTION, pas un champ à écrire
    updates = {}
    if "definition" in fields:
        updates[col_definition] = fields["definition"]
    for k in ("note_portee", "etat", "collection_id"):
        if k in fields:
            updates[k] = fields[k]
    if "etat" in updates and updates["etat"] not in _ETATS_LEXIQUE:
        raise HTTPException(422, f"État invalide : {updates['etat']} (provisoire | defini).")
    # AUTH-2 — changer la PORTÉE d'un terme, c'est le déplacer chez quelqu'un (ou l'en
    # sortir). Il faut donc écrire dans la collection VISÉE, pas seulement dans celle
    # d'origine : sans cela, on rangerait son vocabulaire dans l'étude d'un autre.
    if "collection_id" in updates:
        cible = updates["collection_id"]
        if cible is None:
            if not portee.peut_ecrire_quelque_part():
                raise HTTPException(403, "Promouvoir un terme en global demande un droit "
                                         "d'écriture.")
        elif not portee.peut_ecrire(cible):
            raise HTTPException(404, f"Collection {cible} introuvable.")
        elif conn.execute("SELECT 1 FROM collection WHERE id = ?",
                          (cible,)).fetchone() is None:
            raise HTTPException(404, f"Collection {cible} introuvable.")

    # AUTH-11 — la TROISIÈME PORTE, fermée le 2026-09-25 (décision de Hugo). Ranger un
    # terme dans une collection C le déplaçait sans rien regarder autour : une dimension
    # sous un domaine de A rangée dans B, une dimension rangée dans B en laissant en A une
    # valeur locale — l'état « hors de la collection de son parent » que l'import
    # (`parent_ailleurs`) et le rattachement (`PATCH …/domaine`, 409) refusent depuis la
    # veille. Refusé ici par un 409, si le parent est local à une autre collection que C ou
    # si un terme qui en dépend l'est ; les enfants globaux descendent comme avant.
    #
    # RENVOYER un terme à la collection où il est déjà (relecture du 2026-09-25) n'est pas
    # un déplacement du terme, mais sa descente l'est pour ses enfants GLOBAUX : un domaine
    # de A dont la dimension globale porte une valeur de B faisait descendre la dimension en
    # A — sous elle, une valeur de B. Choisi : JUGER ce que la descente déplacerait (les
    # termes liés atteints à travers un enfant global) et refuser par le même 409, plutôt
    # que de ne plus faire descendre. Ne pas faire descendre laisserait un enfant global
    # au-dessus d'un parent local — l'état que v24 répare, et que la lecture masque — et le
    # même geste ferait descendre ou non selon qu'il déplace ou renvoie : deux règles pour
    # une. Les enfants DIRECTS d'un terme renvoyé ne sont pas jugés, eux : rien ne les
    # déplace, et les juger bloquerait l'édition d'une base antérieure.
    #
    # Le refus nomme ce que l'appelant LIT, et lui seul — même forme que le 409 de la
    # promotion ci-dessous. Tout terme lié qu'il ne lit pas devient « un terme lié que vous
    # ne lisez pas », une seule fois : ni son nom, ni leur nombre. Ce qui en reste n'est
    # PAS la seule chose connue : le sens et la sorte se déduisent souvent de la structure
    # (une valeur n'a pas d'enfant, un domaine pas de parent ; l'ancêtre d'une dimension ne
    # peut être qu'un domaine), et un rangement DEPUIS GLOBAL refusé révèle qu'une autre
    # collection a spécialisé ce terme global — rangé sous lui un terme à elle. Ce bit est
    # ACCEPTÉ comme limite écrite (Hugo, 2026-09-25, fiche AUTH-11) : il ne se fermera que
    # si privatiser un terme global cesse d'être ouvert à qui écrit quelque part (COL-1). Le
    # refus vient APRÈS les gardes d'écriture (sur le terme, puis sur C) : il ne répond qu'à
    # qui pourrait ranger, et rien ne parle avant elles.
    #
    # Option (β), tranchée par Hugo le même jour : ranger la RACINE d'une branche — un
    # terme sans parent local (un domaine, une dimension sans domaine ou sous un domaine
    # global, une valeur sous une dimension globale) — de sa collection A vers B EMPORTE ses
    # descendants rangés dans A, d'un seul geste. Sans cela, une branche entièrement locale
    # ne passait de A à B que par Global (`promouvoir_parents` puis le rangement de sa
    # racine) : publique entre les deux gestes. Restent refusés : un descendant d'une
    # TROISIÈME collection, et le milieu d'une branche (son parent est ailleurs). Depuis
    # GLOBAL, rien n'est emporté — privatiser un terme global est une question à part
    # (COL-1). DROITS : emporter un descendant, c'est l'écrire ; il est dans A, donc
    # modifiable par qui écrit dans A — et ranger la racine l'exige déjà (la route garde le
    # terme en écriture, `_get_*(ecriture=True)`, avant d'appeler ici ; il est dans A), comme
    # elle exige d'écrire dans B (garde de la cible, au-dessus). Aucune garde de plus n'est
    # donc nécessaire, et aucune n'est écrite : elle serait inatteignable. Les emportés sont
    # rendus dans la réponse (`promus`, ce qui a bougé en plus du terme) — ils étaient dans
    # A, donc lisibles de qui range.
    emportes = []
    if "collection_id" in updates and updates["collection_id"] is not None:
        cible = updates["collection_id"]
        # Les termes LIÉS qui retiennent : le parent immédiat s'il est local à une autre
        # collection que C (un parent GLOBAL convient, A4), et les descendants locaux à une
        # autre collection que C (un enfant déjà dans C ne gêne rien). Un enfant GLOBAL
        # descendra (`_descendre_portee`) : ses propres enfants comptent donc, sans quoi la
        # descente les laisserait derrière elle — ranger un domaine ferait descendre sa
        # dimension globale et laisserait « ailleurs » une valeur locale à une autre
        # collection. Un tag n'a ni parent ni enfant. Imbriquée et non exposée par le
        # module : `main.py` ré-exporte tout nom que `socle` définit (ARCH-1).
        lies = []

        def descendants(t, i, tous=True):
            # `tous=False` : ne juger que sous un enfant GLOBAL (le renvoi, plus bas).
            for t_enfant, (p, fk, _) in _PARENT_TERME.items():
                if p != t:
                    continue
                for l in conn.execute(f"SELECT id, {_NOM_TERME[t_enfant]} AS nom, "
                                      f"collection_id FROM {t_enfant} WHERE {fk} = ? "
                                      f"ORDER BY id", (i,)):
                    if l["collection_id"] is None:
                        descendants(t_enfant, l["id"])      # descendra : ses enfants comptent
                    elif not tous:
                        continue                            # enfant direct d'un renvoi
                    elif emporter and l["collection_id"] == actuelle:
                        emportes.append((t_enfant, l["id"], l["nom"]))   # (β) : part avec
                        descendants(t_enfant, l["id"])      # la racine, et ses enfants aussi
                    elif l["collection_id"] != cible:
                        lies.append(("enfant", t_enfant, l["id"], l["nom"],
                                     l["collection_id"]))

        actuelle = conn.execute(f"SELECT collection_id FROM {table} WHERE id = ?",
                                (oid,)).fetchone()["collection_id"]
        if actuelle != cible:
            chaine = _ancetres_terme(conn, table, oid)
            parent_local = bool(chaine) and chaine[0][3] is not None
            if parent_local and chaine[0][3] != cible:
                lies.append(("parent", *chaine[0]))
            # Une racine emporte ; depuis GLOBAL, rien : aucun descendant local n'y est « dans
            # l'ancienne collection » (NULL), et les globaux descendent de toute façon.
            emporter = not parent_local
            descendants(table, oid)
        else:                                   # renvoi : ne juger que ce qui descendrait
            emporter = False
            descendants(table, oid, tous=False)
        if lies:
            article = {"domaine": "le", "attribut_dimension": "la", "attribut_valeur": "la"}
            nommes = [f"{article[t]} {_LIBELLE[t]} « {nom} », "
                      f"{'dont il dépend' if role == 'parent' else 'qui en dépend'},"
                      for role, t, _, nom, col in lies if portee.peut_lire(col)]
            tait = len(nommes) < len(lies)
            morceaux = nommes + (["un terme lié que vous ne lisez pas"] if tait else [])
            verbe = "vivent" if len(morceaux) > 1 else "vit"
            raise HTTPException(409, f"Ce terme ne peut pas être rangé dans cette collection : "
                                     f"{' et '.join(morceaux)} {verbe} dans une autre "
                                     f"collection. Un terme ne se range pas hors de la "
                                     f"collection de son parent, ni de celle des termes "
                                     f"qui en dépendent.")

    # v24 — UN TERME N'EST JAMAIS PLUS GLOBAL QUE CELUI DONT IL DÉPEND. L'invariant était
    # posé à la CRÉATION (une dimension hérite de son domaine, une valeur de sa dimension)
    # et dans la MIGRATION qui a recollé l'existant ; les routes qui DÉPLACENT ne l'ont
    # jamais eu. Mesuré le 2026-09-06 : promouvoir une valeur sous une dimension privée
    # répondait 200, et rien ne cassait — le terme était COMPTÉ dans le « % défini » de
    # tout le monde (`lexique_resume` compte par appartenance) et MASQUÉ de leurs listes
    # (qui filtrent le parent en plus du terme). Le désaccord même que v24 avait effacé.
    #
    # Le refus NOMME tout ce qui bloque, exhaustivement — la chaîne fait trois niveaux au
    # plus, donc il n'y a pas de raison d'en citer un et de laisser découvrir le reste au
    # coup suivant. C'est ce qui rend `promouvoir_parents` un consentement ÉCLAIRÉ plutôt
    # qu'un « oui » à l'aveugle : on ne l'écrit qu'après avoir lu ce qu'il emporte.
    #
    # La règle ne borde QUE le sens interdit. Un terme plus LOCAL que son parent est
    # légitime — c'est le vocabulaire situé d'A4. Deux termes locaux à des collections
    # DIFFÉRENTES, eux, ne sont ni l'un ni l'autre plus globaux, et ce n'est pas cette
    # garde-ci qui les refuse : c'est celle du rangement, plus haut (AUTH-11, 2026-09-25),
    # qui interdit d'en PRODUIRE. Promouvoir vers Global n'en produit jamais.
    #
    # AUTH-11 (2026-09-24) — « exhaustivement » s'entend de ce qu'on LIT. La chaîne se
    # remonte sans filtre de portée (il faut la connaître pour refuser), et le refus
    # nommait tout, y compris un ancêtre local à une collection que l'appelant ne lit pas :
    # une valeur de c1 sous une dimension et un domaine de c3 (l'import d'avant AUTH-11 en
    # produisait) livrait à qui n'écrit que dans c1 deux noms de la grille d'analyse de c3.
    # Un ancêtre qu'on ne voit pas n'est plus nommé : il devient « un terme que vous ne
    # lisez pas », une seule fois quel que soit leur nombre. Le message ne NOMME pas ce
    # terme ; sa SORTE, elle, peut se déduire de la structure — l'ancêtre tu d'une
    # dimension ne peut être qu'un domaine, et, pour une valeur dont la dimension est
    # nommée, le terme tu est son domaine. Ce que le refus livre en plus du blocage lui-même
    # est donc « un ancêtre, à tel palier, vit dans une collection que vous ne lisez pas »,
    # jamais son nom ni sa collection. Le 403 de `promouvoir_parents`
    # suit la même règle : on ne peut pas écrire ce qu'on ne lit pas, et le dire ne nomme
    # rien. Un ancêtre qu'on lit reste nommé, et c'est lui que le consentement vise.
    promus = []
    if "collection_id" in updates and updates["collection_id"] is None:
        bloquants = [a for a in _ancetres_terme(conn, table, oid) if a[3] is not None]
        if bloquants and not getattr(payload, "promouvoir_parents", False):
            nommes = [f"{_LIBELLE[t]} « {nom} »" for t, _, nom, col in bloquants
                      if portee.peut_lire(col)]
            tait = len(nommes) < len(bloquants)
            morceaux = nommes + (["un terme que vous ne lisez pas"] if tait else [])
            quoi = " et ".join(morceaux)
            quoi = f"d'{quoi}" if quoi.startswith("un ") else f"de {quoi}"
            accord = "qui restent locaux" if len(morceaux) > 1 else "qui reste local"
            suite = ("Seul qui écrit dans sa collection peut le promouvoir." if tait else
                     "Pour les promouvoir aussi : promouvoir_parents=true.")
            raise HTTPException(409, f"Ce terme dépend {quoi}, {accord}. Un terme ne peut "
                                     f"pas être plus global que celui dont il dépend. "
                                     f"{suite}")
        for t_anc, id_anc, nom_anc, col_anc in bloquants:
            if not portee.peut_ecrire_terme(col_anc):
                if not portee.peut_lire(col_anc):
                    raise HTTPException(403, "Promouvoir ce terme emporterait un terme que "
                                             "vous ne lisez pas.")
                raise HTTPException(403, f"Promouvoir {_LIBELLE[t_anc]} « {nom_anc} » demande "
                                         f"un droit d'écriture sur sa collection.")
        for t_anc, id_anc, nom_anc, _ in bloquants:
            conn.execute(f"UPDATE {t_anc} SET collection_id = NULL WHERE id = ?", (id_anc,))
            promus.append(f"{_LIBELLE[t_anc]} « {nom_anc} »")

    if updates:
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE {table} SET {cols} WHERE id = ?", (*updates.values(), oid))
        # L'autre sens : rendre un terme plus LOCAL laisserait ses enfants au-dessus de lui.
        # Et (β) : les descendants emportés suivent la racine, puis leurs enfants globaux
        # descendent à leur tour — `_descendre_portee` ne traverse que des termes GLOBAUX,
        # il ne passerait pas par eux.
        if "collection_id" in updates:
            for t_e, i_e, _ in emportes:
                conn.execute(f"UPDATE {t_e} SET collection_id = ? WHERE id = ?",
                             (updates["collection_id"], i_e))
            _descendre_portee(conn, table, oid, updates["collection_id"])
            for t_e, i_e, _ in emportes:
                _descendre_portee(conn, t_e, i_e, updates["collection_id"])
            promus += [f"{_LIBELLE[t_e]} « {nom_e} »" for t_e, _, nom_e in emportes]
        conn.commit()
    return promus


# --------------------------------------------------------------------------- #
# Portée DÉRIVÉE — le registre des personnages (AUTH-2)
# --------------------------------------------------------------------------- #

def _clause_personnage(portee: autorisation.Portee) -> tuple[str, list]:
    """Visibilité d'un personnage (`p.id`), DÉRIVÉE de ses apparitions.  AUTH-2.

    `personnages` est un registre posé à côté du corpus : la table ne porte aucune
    collection, et lui en ajouter une reviendrait à demander, à la création, à quelle
    collection appartient un personnage — question sans bonne réponse pour une série qui
    traverse plusieurs albums. La portée se dérive donc de l'usage : on voit un personnage
    qui apparaît quelque part où l'on peut lire.

    Avec une exception nécessaire : le personnage qui n'apparaît NULLE PART reste visible.
    Sans elle, le geste courant — créer le personnage, puis lui attribuer une bulle —
    serait cassé, l'entité disparaissant à l'instant même de sa création, y compris pour
    la personne qui vient de la créer.

    Ce n'est pas une mesure de confidentialité : quiconque accède à l'instance peut déjà
    télécharger la base entière (décision du 2026-08-27, cf. docs/hebergement-securite.md
    §6). C'est une mesure d'USAGE — sans elle, l'autocomplétion de locuteur grossit avec
    l'instance entière au lieu de rester à la taille de l'étude en cours.
    """
    ou, pp = portee.clause_album("pl.album_id")
    if ou == "1":
        return "1", []
    apparait = (
        "EXISTS (SELECT 1 FROM {table} x "
        "          JOIN regions r   ON r.id = x.region_id "
        "          JOIN planches pl ON pl.id = r.planche_id "
        f"        WHERE x.personnage_id = p.id AND {ou})")
    jamais = ("NOT EXISTS (SELECT 1 FROM bulle_locuteur b WHERE b.personnage_id = p.id) "
              "AND NOT EXISTS (SELECT 1 FROM personnage_presence q "
              "                WHERE q.personnage_id = p.id)")
    return (f"(({jamais}) "
            f" OR {apparait.format(table='bulle_locuteur')} "
            f" OR {apparait.format(table='personnage_presence')})",
            [*pp, *pp])


def _get_personnage(conn, portee: autorisation.Portee, personnage_id, *,
                    ecriture: bool = False):
    """Personnage VISIBLE (404 sinon) et, si `ecriture`, modifiable.

    Un personnage n'appartient à aucune collection (sa portée se DÉRIVE de ses
    apparitions) : il n'y a donc pas de collection sur laquelle vérifier le droit
    d'écrire. La règle est celle du vocabulaire global — écrire quelque part suffit,
    personne ne possède le registre."""
    ou, params = _clause_personnage(portee)
    p = _row(conn.execute(
        f"SELECT p.* FROM personnages p WHERE p.id = ? AND {ou}",
        (personnage_id, *params)))
    if p is None:
        raise HTTPException(404, f"Personnage {personnage_id} introuvable")
    if ecriture and not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Le registre des personnages est en lecture seule "
                                 "pour vous.")
    return p


# --------------------------------------------------------------------------- #
# Sortie CSV — partagée par la recherche et l'export (ARCH-1)
# --------------------------------------------------------------------------- #
# Ces trois-là vivaient dans le bloc Recherche, où l'Export allait les chercher. Le
# découpage rend la dépendance visible au lieu de la laisser au hasard du voisinage —
# et `_csv_safe` porte une règle de sécurité (anti-injection de formule) qui gagne au
# même titre que les accesseurs gardés à être un import plutôt qu'une convention.
_BOM = chr(0xFEFF)   # BOM UTF-8 : permet à Excel (Windows) de lire les accents correctement


def _disposition(nom: str) -> str:
    """En-tête `Content-Disposition` d'un téléchargement, sûr QUEL QUE SOIT le nom (ANA-6).

    Le nom d'un export d'analyse porte la saisie de l'utilisateur (`concordance-<lemme>`),
    et l'en-tête la recevait telle quelle. Trois pannes, mesurées le 2026-09-11 :
    `lemme=œil` levait `UnicodeEncodeError` — un en-tête HTTP s'encode en latin-1, et « œ »
    n'y est pas, donc « cœur », « sœur » ou « œuvre » rendaient un 500 ; `a"b` refermait
    les guillemets au milieu du nom ; `otage*` proposait un nom que Windows refuse.

    Deux formes, comme le prévoit la RFC 6266 : `filename` porte un repli ASCII que tout
    client comprend, `filename*` le nom exact en UTF-8 (RFC 5987), que les navigateurs
    préfèrent quand ils le connaissent. Les caractères interdits dans un nom de fichier
    sont remplacés dans LES DEUX : un nom exact que le système refuse ne sert à rien.
    `NFKD` retire les diacritiques du repli (« été » → « ete ») mais laisse intactes les
    deux ligatures du français, qui n'ont pas de décomposition — elles sont dépliées à la
    main, sans quoi « œil » deviendrait « il ».
    """
    sain = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]+', "_", nom).strip(" .") or "export"
    deplie = (sain.replace("œ", "oe").replace("Œ", "OE")
                  .replace("æ", "ae").replace("Æ", "AE"))
    repli = unicodedata.normalize("NFKD", deplie).encode("ascii", "ignore").decode("ascii")
    repli = re.sub(r"[^A-Za-z0-9._-]+", "_", repli).strip("_") or "export"
    return f"attachment; filename=\"{repli}\"; filename*=UTF-8''{quote(sain, safe='')}"


def _csv_response(contenu: str, filename: str) -> Response:
    """Réponse CSV téléchargeable, préfixée d'un BOM UTF-8 pour qu'Excel (Windows) lise
    correctement les accents français. (R/pandas : lire en `utf-8-sig`.)"""
    return Response(content=_BOM + contenu, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": _disposition(filename)})


def _csv_safe(v):
    """Neutralise l'injection de FORMULE (CSV → tableur) : une cellule TEXTE débutant par
    `= + - @` (ou tab/CR) est préfixée d'une apostrophe → un tableur l'affiche littéralement
    au lieu de l'exécuter. À n'appliquer qu'au texte libre (pas aux nombres : « -5 » reste un
    nombre). Cf. OWASP « CSV Injection »."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _clause_lemme(colonne: str, lemme: Optional[str]) -> Optional[tuple[str, list]]:
    """Critère de lemme (ANA-6) : EXACT, ou PRÉFIXE quand la saisie finit par `*`.

    Partagé par l'analyse (`_analyse_filtres`) et la facette lemme de la Recherche
    (`_recherche_rows`) : `lemme=` doit dire la même chose partout, sans quoi une descente
    de l'une vers l'autre changerait de sens en chemin.

    Le joker est EXPLICITE, et c'est la décision. Un préfixe implicite aurait fait de
    `pas` une recherche de « passer » et « passage » ; or la cellule d'un croisement ouvre
    sa concordance par la valeur EXACTE, qui aurait alors compté plus que la cellule — en
    silence, avec des nombres plausibles. `%` et `_`, les jokers de LIKE, sont échappés :
    ici ils ne signifient rien.

    Renvoie None quand il ne reste rien à chercher (vide, ou « * » seul) : l'appelant
    n'ajoute alors aucune clause, et une concordance sans autre critère répond son 422
    ordinaire plutôt que de rendre tout le corpus pour un astérisque.
    """
    v = (lemme or "").strip().lower()                        # lemmes minusculés
    if not v.endswith("*"):
        return (f"{colonne} = ?", [v]) if v else None
    racine = v.rstrip("*")
    if not racine:
        return None
    motif = racine.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return f"{colonne} LIKE ? ESCAPE '\\'", [motif]

# --------------------------------------------------------------------------- #
# Qui appelle (AUTH-2) — lecture des en-têtes d'identité
# --------------------------------------------------------------------------- #

def _auteur(request: Request) -> Optional[str]:
    """Login de la personne connectée — délégué à `autorisation.auteur` (AUTH-2).

    La lecture des en-têtes d'identité a migré dans `autorisation.py` : la portée
    d'autorisation en dépend, et deux implémentations de « qui est là » finiraient par
    diverger. Le nom local reste, il a des appelants dans tout le fichier.
    """
    return autorisation.auteur(request)


def _groupes(request: Request) -> list[str]:
    """Groupes de la personne connectée — délégué à `autorisation.groupes` (AUTH-2)."""
    return autorisation.groupes(request)


# Miroir des identités déjà écrites : évite une écriture SQLite à CHAQUE requête, ce qui
# sérialiserait tout le trafic derrière l'unique verrou d'écriture du WAL.
#
# On réécrit dans DEUX cas : le nom ou l'email a changé (Authelia fait foi), ou la
# dernière écriture date de plus d'une heure. Ce second cas n'est pas du zèle : sans lui,
# `derniere_vue` ne bougerait qu'au changement de nom, et la colonne mentirait sur ce
# qu'elle prétend mesurer. Une écriture par personne et par heure reste négligeable.


# --------------------------------------------------------------------------- #
# Modèles Pydantic — le CONTRAT d'entrée de l'API (ARCH-1)
# --------------------------------------------------------------------------- #
# Ici plutôt que dans chaque domaine, et c'est une décision : `LexiqueIn` sert à deux
# blocs, `AttributIn` à un bloc sorti et un bloc resté. Les répartir exactement
# demanderait une carte d'usage pour 27 déclarations sans logique, et se tromperait
# sans bruit. Ce sont des contrats, pas de la mécanique de domaine.

class AlbumIn(BaseModel):
    # AUTH-2 : collection d'accueil. N'est PAS une colonne d'`albums` —
    # l'appartenance vit dans `collection_album` (N-N) et le champ est
    # retiré avant l'INSERT. Omis => collection de repli.
    collection_id: Optional[int] = None
    # COL-3, tranche 2 — « Importer au fonds » (Hugo, 2026-10-11) : l'album naît SANS
    # collection ni projet, « appelé par personne », pour être distribué ensuite. Réservé à
    # qui tient le fonds. N'est PAS une colonne non plus : retiré avant l'INSERT.
    au_fonds: bool = False
    titre: str
    auteur: Optional[str] = None                # legacy → voir contributions
    # Bornes larges à dessein : il ne s'agit pas de policer l'histoire de l'édition
    # mais d'écarter l'absurde — 999999 passait, et une base ne se nettoie pas après
    # coup aussi facilement qu'elle se salit (E3).
    annee: Optional[int] = Field(None, ge=1400, le=2200)   # legacy → cf. date_edition
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None
    # Enrichissement descriptif N0 (v15) — édition détenue.
    date_edition: Optional[str] = None
    date_originale: Optional[str] = None
    langue: Optional[str] = None
    type_oeuvre: Optional[str] = None
    lieu_edition: Optional[str] = None
    edition_tirage: Optional[str] = None
    isbn: Optional[str] = None
    format_physique: Optional[str] = None
    source_numerisation: Optional[str] = None   # matériel N1 (A6) : appareil / conditions de scan


class AlbumUpdate(BaseModel):
    titre: Optional[str] = None
    auteur: Optional[str] = None
    annee: Optional[int] = Field(None, ge=1400, le=2200)   # mêmes bornes qu'à la création
    editeur: Optional[str] = None
    serie: Optional[str] = None
    description: Optional[str] = None
    date_edition: Optional[str] = None
    date_originale: Optional[str] = None
    langue: Optional[str] = None
    type_oeuvre: Optional[str] = None
    lieu_edition: Optional[str] = None
    edition_tirage: Optional[str] = None
    isbn: Optional[str] = None
    format_physique: Optional[str] = None
    source_numerisation: Optional[str] = None   # matériel N1 (A6)


class ContributionIn(BaseModel):
    nom: str
    role: Optional[str] = None                  # label du rôle (contrôlé-ouvert : créé au besoin)


class ContributionRoleIn(BaseModel):            # ≠ `RoleIn` (rôle de planche, plus bas)
    label: str
    bucket: Optional[str] = None                # 'creator' | 'contributor' (défaut : contributor)
    marc: Optional[str] = None


class RegionIn(BaseModel):
    type: str
    x: int = Field(0, ge=0)
    y: int = Field(0, ge=0)
    w: int = Field(0, ge=0)
    h: int = Field(0, ge=0)
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: str = "manuel"


# CONC-3 (Q1) — les champs d'une région dont l'écran peut déclarer la valeur qu'il avait vue.
# `ordre` et `source` n'en sont pas : l'ordre se recalcule, la source suit la retouche.
CHAMPS_VUS = ("type", "x", "y", "w", "h", "parent_id", "ocr_texte")


class RegionUpdate(BaseModel):
    """Ce qu'une modification de région change. `vu` associe à chaque champ changé la
    valeur que l'écran avait vue (CONC-3) : facultatif, et vérifié par la route."""
    type: Optional[str] = None
    x: Optional[int] = Field(None, ge=0)
    y: Optional[int] = Field(None, ge=0)
    w: Optional[int] = Field(None, ge=0)
    h: Optional[int] = Field(None, ge=0)
    parent_id: Optional[int] = None
    ordre: Optional[int] = None
    ocr_texte: Optional[str] = None
    source: Optional[str] = None
    vu: Optional[dict[str, Any]] = None


class StatutIn(BaseModel):
    statut: str


class ValidationIn(BaseModel):
    validee: bool


class VerrouIn(BaseModel):
    verrouillee: bool


class RoleIn(BaseModel):
    role: str


class RelectureIn(BaseModel):
    relecture: Optional[str] = None      # 'a_faire'|'en_cours'|'faite' ; null = auto (dérivé)


class TokenCorrectionIn(BaseModel):
    lemme: Optional[str] = None
    pos: Optional[str] = None
    morph: Optional[str] = None
    etat: str = "corrige"          # 'corrige' | 'valide'


class MoveIn(BaseModel):
    sens: str   # "haut" | "bas"


class SharedocsConnIn(BaseModel):
    url: str
    user: str
    password: Optional[str] = None   # vide => repli sur BD_SHAREDOCS_PASS
    # SHARE-1 — 'instance' remplace le compte de l'instance (administrateurs seuls) ;
    # sinon on ouvre SA propre session.
    compte: Optional[str] = None


class SharedocsImportIn(BaseModel):
    chemins: list[str] = Field(default_factory=list)
    album_id: Optional[int] = None
    # Gardé pour être REFUSÉ par son nom (COL-3, 2026-10-15) : sans lui, un appel qui
    # l'enverrait encore perdrait le champ en silence et recevrait « album cible manquant ».
    nouvel_album: Optional[str] = None
    segmenter: bool = False
    compte: Optional[str] = None            # SHARE-1 : 'perso' | 'instance' | None (auto)


class DeposerIn(BaseModel):
    dossier: str = ""   # dossier ShareDocs cible (vide = racine)
    # SHARE-1 — le compte se CHOISIT à chaque dépôt (décision du 2026-08-28). Une
    # sauvegarde déposée sous un compte personnel atterrit dans un espace qui s'en va
    # avec la personne ; mais l'imposer priverait d'un dépôt de dépannage. None = la
    # règle par défaut (la mienne si j'en ai une, celle de l'instance sinon).
    compte: Optional[str] = None


class DeposerExportIn(DeposerIn):
    """Dépôt ShareDocs d'un export de dépôt (EXP-1). Hérite du dossier et du compte.

    Les quatre champs qui s'ajoutent sont ceux de la requête GET équivalente : c'est le
    même artefact, produit par le même `routes.depot.produire`, et seule sa destination
    change.
    """
    quoi: str                       # description | metadonnees | iiif
    format: str = "json"
    verbatim: bool = False
    base_url: str = ""


class JobIn(BaseModel):
    passes: list[str] = Field(default_factory=list)        # segmenter / bulles / ocr
    album_ids: list[int] = Field(default_factory=list)
    planche_ids: list[int] = Field(default_factory=list)


class AnnotationIn(BaseModel):
    """Ce qu'un enregistrement d'annotation CHANGE — et seulement cela (CONC-3).

    Un champ ABSENT garde sa valeur en base : `{"note": …}` ne touche pas aux tags. `tags`
    remplace la liste visible ; `tags_ajoutes` / `tags_retires` la modifient, sans rien
    savoir des tags que d'autres ont posés entre-temps. La route refuse `tags` avec l'un des
    deux autres. Voir `main.put_annotation`."""
    note: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    tags_ajoutes: list[str] = Field(default_factory=list)
    tags_retires: list[str] = Field(default_factory=list)
    # CONC-3, second temps : la note que l'écran avait vue. Facultative (Q8).
    note_vue: Optional[str] = None


class TagIn(BaseModel):
    label: str
    couleur: Optional[str] = None
    description: Optional[str] = None


class PersonnageIn(BaseModel):
    nom: str
    serie: Optional[str] = None
    notes: Optional[str] = None


class PersonnageUpdate(BaseModel):
    nom: Optional[str] = None
    serie: Optional[str] = None
    notes: Optional[str] = None


class LocuteurIn(BaseModel):
    personnage_id: int


class PresenceIn(BaseModel):
    personnage_id: int   # entité montrée dans une boîte personnage (§14, brique (a))


class FusionIn(BaseModel):
    cible_id: int   # personnage canonique dans lequel fusionner le doublon


class AlignementIn(BaseModel):
    """Alignement d'autorité (A5) : URI d'un référentiel externe (skos:exactMatch)."""
    uri: str
    source: Optional[str] = None   # 'wikidata'|'viaf'|'idref'… ; auto-détecté si absent


class DomaineIn(BaseModel):
    """Domaine analytique (piste B) — champ émergent qui regroupe des dimensions."""
    nom: str


class FigureIn(BaseModel):
    """Demande d'export de figure(s) citable(s) — DROIT-1.

    `champs` choisit les MENTIONS qui composeront la légende : une légende d'article, une
    légende de diapositive et une notice de catalogue n'ont pas les mêmes besoins, et
    imposer un gabarit obligerait à le retailler à la main, donc hors de l'outil, donc en
    perdant le lien entre l'image et sa référence. Défaut = tout, faute d'en savoir plus.

    `collection_id` dit AU NOM DE QUELLE ÉTUDE on cite : un album vit dans plusieurs
    collections depuis AUTH-3, et le corpus crédité n'est pas déductible.
    """
    regions: list[int]
    champs: Optional[list[str]] = None
    collection_id: Optional[int] = None
    taille: int = 1600


class CollectionIn(BaseModel):
    """Création d'une collection (AUTH-3). Volontairement minimale : un espace de travail
    s'ouvre avec un nom, et les descripteurs de DÉPÔT (licence, base légale, embargo…) se
    remplissent ensuite, quand la collection sert vraiment à quelque chose."""
    nom: str
    description: Optional[str] = None
    # COL-3 — le projet où elle naît. Absent : le projet de repli, c'est-à-dire le
    # comportement d'avant la v29. Une collection ne change pas de projet ensuite :
    # `CollectionUpdate` ne porte pas ce champ, et c'est voulu.
    projet_id: Optional[int] = None


class ProjetIn(BaseModel):
    """Création d'un projet (COL-3). `justification` dit POURQUOI il existe — texte libre,
    scientifique d'abord ; elle ne se rend qu'à qui gère le projet.

    `acces_membres` (COL-3, tranche 3, D10) : ce que les MEMBRES du projet peuvent dans sa
    collection de base — `ecriture`, `lecture`, ou `null` (protégée). Omis, il vaut
    `ecriture` : la position que l'écran présélectionne (« ouverte », le cas du débutant),
    et le même défaut des deux côtés. Rien ne s'ouvre pour autant à la création : un projet
    naît sans membre, et en faire entrer un est la décision qui ouvre."""
    nom: str
    description: Optional[str] = None
    justification: Optional[str] = None
    acces_membres: Optional[str] = autorisation.ECRITURE


class AccesMembresIn(BaseModel):
    """La position des membres d'un projet dans sa collection de base (D10) : `ecriture`,
    `lecture`, ou `null` (protégée). OBLIGATOIRE — `null` est une valeur, pas une
    absence."""
    acces_membres: Optional[str]


class ProjetUpdate(BaseModel):
    """Édition partielle d'un projet. Champ omis = inchangé. `repli` n'y est pas : le projet
    de repli ne se désigne pas par une route."""
    nom: Optional[str] = None
    description: Optional[str] = None
    justification: Optional[str] = None


class DemandeIn(BaseModel):
    """Une demande (COL-3, tranche 2). `genre` dit ce qu'on demande ; `album_id` désigne
    le document par l'une de ses copies, `projet_id` le projet ; `motif` dit pourquoi, et
    il est obligatoire. `certifie` : la case « ces données ne sont pas importantes »,
    exigée pour un document (Hugo, 2026-10-15)."""
    genre: str
    album_id: Optional[int] = None
    projet_id: Optional[int] = None
    motif: Optional[str] = None
    certifie: bool = False


class ReponseIn(BaseModel):
    """La réponse à une demande : `acceptee` ou `refusee`."""
    reponse: str


class MembreIn(BaseModel):
    """Un membre de projet : QUI (genre + principal) et sous quel RÔLE. Le patron
    d'`AccesIn` — `principal` est un nom, jamais une référence vérifiée."""
    genre: str = autorisation.UTILISATEUR      # 'utilisateur' | 'groupe'
    principal: str
    role: str = autorisation.MEMBRE            # 'membre' | 'responsable'


class CollectionUpdate(BaseModel):
    """Édition partielle des descripteurs. Champ omis = inchangé."""
    nom: Optional[str] = None
    description: Optional[str] = None
    licence_defaut: Optional[str] = None
    base_legale: Optional[str] = None
    statut_diffusion: Optional[str] = None
    date_embargo: Optional[str] = None
    date_debut: Optional[str] = None
    date_fin: Optional[str] = None
    # AUTH-4 — le référent d'EXPLOITATION, désigné par le propriétaire. Distinct de
    # `responsables`, qui est scientifique et part au dépôt.
    referent_nom: Optional[str] = None
    referent_contact: Optional[str] = None


class AccesIn(BaseModel):
    """Un accès accordé : QUI (genre + principal) et à quel NIVEAU.

    `principal` est un nom, pas une référence vérifiée — l'application n'a aucun annuaire
    (invariant AUTH-1) et lit les groupes dans `Remote-Groups` à chaque requête."""
    genre: str = autorisation.UTILISATEUR      # 'utilisateur' | 'groupe'
    principal: str
    niveau: str = autorisation.LECTURE         # 'lecture' | 'ecriture' | 'proprietaire'
    # DROIT-2 — le droit de sortir le contenu, À CÔTÉ du niveau. `None` veut dire « ne
    # pas y toucher » : re-poser un principal pour changer son niveau ne doit pas lui
    # retirer une case qu'on n'a pas mentionnée. Une ligne NEUVE part sans le droit.
    exporter: Optional[bool] = None


class NatureIn(BaseModel):
    """La nature d'un compte (AUTH-6) : `nominatif` ou `collectif`.

    Un seul champ, et c'est voulu — la nature ne se pose pas en passant, au milieu d'une
    mise à jour de profil. C'est une déclaration sur ce qu'un login EST, et deux mesures en
    dépendent : l'accord inter-annotateurs et la pseudonymisation de sortie.
    """
    nature: str


class DimensionDomaineIn(BaseModel):
    domaine_id: Optional[int] = None   # null = retirer la dimension de son domaine


class DimensionIn(BaseModel):
    cible: str      # 'personnage' | 'case'
    nom: str
    domaine_id: Optional[int] = None   # champ analytique de rattachement (v20 ; optionnel)


class ValeurIn(BaseModel):
    valeur: str


class LexiqueIn(BaseModel):
    """Couche définitionnelle SKOS (A4) — mise à jour PARTIELLE (patch). Champ omis = laissé
    tel quel ; `collection_id: null` explicite = promotion en GLOBAL (patron mentions→entités)."""
    definition: Optional[str] = None      # SKOS definition (→ tags.description)
    note_portee: Optional[str] = None     # SKOS scopeNote — le « situé »
    etat: Optional[str] = None            # 'provisoire' | 'defini'
    collection_id: Optional[int] = None   # portée d'appartenance ; null = global
    # v24 / COL-1 — promouvoir AUSSI les ancêtres qui bloquent. Faux par défaut : un terme
    # ne peut pas devenir plus global que celui dont il dépend, et le refus nomme alors
    # exhaustivement ce qu'il faudrait emporter (au plus deux, la chaîne étant
    # domaine→dimension→valeur). Ce drapeau n'est donc jamais coché à l'aveugle — on ne
    # l'écrit qu'après avoir lu le 409 qui dit ce qu'il déplace.
    promouvoir_parents: bool = False


class AttributIn(BaseModel):
    valeur_id: int
