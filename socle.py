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
from typing import Any, Iterator, Literal, Optional
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import autorisation
import conflit
import journal
from database import (CRAN_IMAGES, DEMANDE_AMORCER, DEMANDE_ENTREE_DOCUMENTS, DEMANDE_REJOINDRE,
                      DEMANDE_RENDRE, DEMANDE_SUPPRESSION_DOCUMENT,
                      DEMANDE_SUPPRESSION_PROJET, REPONSE_ACCEPTEE, REPONSE_REFUSEE,
                      NOM_BAC_A_SABLE, clause_appartenance, cle_tag, collection_de_base,
                      collection_row, creer_collection_de_base, creer_copie,
                      demandes_vers_collection, espace_d_album, est_isole, est_jeu,
                      etat_des_reponses,
                      get_connection,
                      nature_du_projet, prochain_effacement, projet_d_album,
                      projet_de_collection, rangement_traverse, retirer_document_sans_copie,
                      sql_album_isole, sql_est_jeu, sql_projet_d_album, sql_projet_de,
                      unindex_region)
from config import BAC_A_SABLE_PLAFOND_PLANCHES
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


# ANN-8 — la clé d'un libellé de TAG (apostrophes, accents composés, casse, espaces) : un
# libellé saisi se compare par elle. `_norm_tag` reste ce qu'il était pour les noms de
# domaine, de dimension et de valeur, que rien ne cherche encore par clé.
_cle_tag = cle_tag


def _sans_accents(s: str) -> str:
    """Minuscule sans diacritiques — pour une autocomplétion insensible aux accents
    (« etienne » trouve « Étienne »)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _ensure_tags(conn: sqlite3.Connection, labels: list[str], portee, *, album_id: int,
                 deja=frozenset()) -> list[dict]:
    """Crée les tags manquants et renvoie les lignes correspondantes.

    **Un tag LOCAL ne se pose que sur les albums de sa collection** (ANN-8, décision de
    Hugo du 2026-10-22). `album_id` est l'album de la région qui le recevrait ; un tag local
    à une collection qui ne range pas cet album est refusé par un 422 qui le nomme, avec sa
    collection — l'appelant la lit, puisqu'il lit le tag. Refuser plutôt que taire : la note
    envoyée avec lui n'est pas enregistrée non plus, mais rien ne disparaît sans un mot, et
    le libellé reste pris (l'unicité) — l'écrire en tag libre ne serait pas possible. Un tag
    que la région porte DÉJÀ (`deja`, des identifiants) passe : ce qui existe reste, et une
    liste renvoyée entière ne doit pas buter sur lui (`tools/tags_hors_collection.py` dit
    l'existant). Le refus vient avant toute création. Les deux paramètres sont nommés et
    `album_id` n'a pas de défaut : un appelant qui l'oublierait poserait partout.

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

    **Elle n'atteint pas `undo._tag_a_rendre`, et c'est voulu.** L'annulation repose un
    instantané pris par le journal, qui garde l'annotation ENTIÈRE, cachés compris : y
    poser la même garde ferait de Ctrl+Z l'outil qui efface ce que `_tags_caches`
    protège. Restaurer n'est pas saisir — on ne devine pas un libellé qu'on est en train
    de remettre là où il était. Depuis ANN-8, l'annulation ne CRÉE plus aucun tag : un
    libellé renommé, fusionné ou supprimé depuis se suit dans le journal, ou ne revient pas.

    **Un libellé se cherche par sa CLÉ** (ANN-8, `database.cle_tag`) : « c’est pluriel » et
    « c'est pluriel », un accent composé ou décomposé, désignent le même tag. Un tag neuf
    naît sous sa clé ; un tag d'avant est retrouvé par la sienne, sous sa graphie. Si deux
    tags d'avant partagent une clé, on en prend UN — celui dont le libellé EST la clé, sinon
    le plus ancien — : attacher les deux poserait deux fois le même mot.
    """
    normalized = sorted({_cle_tag(l) for l in labels if _cle_tag(l)})
    if not normalized:
        return []
    marques = ",".join("?" * len(normalized))
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    # COL-4 — les libellés vivent dans un ESPACE (`tags.espace`) : celui de l'instance, ou
    # celui du bac à sable de l'album (Hugo, 2026-10-24). Tout se lit DANS l'espace de
    # l'album : un libellé pris dans un bac à sable ne l'est pas pour le corpus, ni
    # l'inverse, et rien ne se voit d'un côté à l'autre.
    espace = espace_d_album(conn, album_id)
    # Deux lectures, et l'écart entre elles EST la garde : tout ce que le libellé désigne
    # déjà dans l'espace, puis ce qu'on en lit. La différence se tait — hors d'un bac à
    # sable (AUTH-11, ci-dessus).
    pris = {r["cle"] for r in conn.execute(
        f"SELECT cle_tag(label) AS cle FROM tags WHERE espace = ? "
        f"AND cle_tag(label) IN ({marques})", (espace, *normalized))}
    lisibles = {}
    for r in _rows(conn.execute(
            f"SELECT t.id, t.label, t.couleur, t.collection_id, cle_tag(t.label) AS cle "
            f"FROM tags t "
            f"WHERE t.espace = ? AND cle_tag(t.label) IN ({marques}) AND {ou_tag} "
            f"ORDER BY (t.label = cle_tag(t.label)) DESC, t.id",
            (espace, *normalized, *p_tag))):
        cle = r.pop("cle")
        lisibles.setdefault(cle, r)
    if espace and pris - set(lisibles):
        # COL-4 — dans un bac à sable, poser un libellé qu'on ne peut pas poser ne rend
        # plus 200 en silence (Hugo, 2026-10-24) : il est pris, dans CE bac à sable, par
        # une collection que l'appelant ne lit pas — un refus nommé, entre ses comptes.
        raise HTTPException(409, "Ce libellé est déjà pris dans ce bac à sable, par une "
                                 "collection que vous ne lisez pas : choisissez-en un autre.")
    lisibles = list(lisibles.values())
    rangee_dans = {r[0] for r in conn.execute(
        "SELECT collection_id FROM collection_album WHERE album_id = ?", (album_id,))}
    for t in lisibles:
        if (t["collection_id"] is not None and t["collection_id"] not in rangee_dans
                and t["id"] not in deja):
            nom = conn.execute("SELECT nom FROM collection WHERE id = ?",
                               (t["collection_id"],)).fetchone()
            raise HTTPException(422, f"Le tag « {t['label']} » est propre à la collection "
                                     f"« {nom[0] if nom else t['collection_id']} » : il ne "
                                     "se pose que sur les albums qu'elle range.")
    # Un libellé LIBRE se crée (global, comme avant) ; un libellé pris par un terme qu'on
    # ne lit pas ne se crée pas — l'unicité l'en empêche — et ne s'attache pas.
    #
    # COL-4 (S2) — sur un album de BAC À SABLE, le libellé libre naît LOCAL à une collection
    # du bac à sable qui range l'album : global, il survivrait à l'effacement chez tout le
    # monde ; local, l'effacement l'emporte avec le reste.
    neufs = [l for l in normalized if l not in pris]
    locale = _collection_locale_d_un_bac(conn, album_id)
    for label in neufs:
        conn.execute(
            "INSERT INTO tags (label, collection_id, espace) VALUES (?, ?, ?) "
            "ON CONFLICT(espace, label) DO NOTHING",
            (label, locale, espace),
        )
    if neufs:
        marques_neufs = ",".join("?" * len(neufs))
        lisibles += _rows(conn.execute(
            f"SELECT id, label, couleur FROM tags WHERE espace = ? "
            f"AND label IN ({marques_neufs})", (espace, *neufs)))
    return sorted(lisibles, key=lambda r: r["label"])


def _collection_locale_d_un_bac(conn, album_id: int):
    """La collection où naît un tag libre tapé sur cet album s'il vit dans un BAC À SABLE —
    sa base s'il y est rangé, sinon sa plus petite collection, sinon la base (une copie
    gardée au fonds) ; None hors d'un bac à sable. COL-4."""
    projet_id, _ = _bac_a_sable_de(conn, album_id=album_id)
    if projet_id is None:
        return None
    base = collection_de_base(conn, projet_id)
    rangees = [r[0] for r in conn.execute(
        "SELECT collection_id FROM collection_album WHERE album_id = ? ORDER BY collection_id",
        (album_id,))]
    if base in rangees or not rangees:
        return base
    return rangees[0]


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

def _refuser_la_reference(conn, portee: autorisation.Portee, album_id) -> None:
    """Un accès en ÉCRITURE vient d'échouer : 409 nommé si l'album est une copie de
    RÉFÉRENCE du jeu que l'appelant LIT — en écriture, `Portee.clause_album` l'écarte pour
    toute portée (COL-4 : le jeu ne se change que par son outil). Sinon rien : l'appelant
    lève son 404. Un 409 et non un 404 : on la lit, un « introuvable » mentirait."""
    if album_id is None:
        return
    ou, params = portee.clause_album("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou} "
                    f"AND {sql_est_jeu(sql_projet_d_album('a'))}",
                    (album_id, *params)).fetchone():
        raise HTTPException(409, _MOTIF_JEU)


def _get_album(conn, portee: autorisation.Portee, album_id: int, *,
               ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("albums.id", ecriture=ecriture)
    a = _row(conn.execute(f"SELECT * FROM albums WHERE id = ? AND {ou}",
                          (album_id, *params)))
    if a is None:
        if ecriture:
            _refuser_la_reference(conn, portee, album_id)
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


# Les colonnes de `planches` qu'AUCUNE route ne rend (IMG-1, relecture croisée).
# `master_origine` dit où vit le master d'archive : un chemin ShareDocs — parfois celui d'un
# espace PERSONNEL — ou un nom de fichier. Les planches d'une copie sœur la recopient (D6),
# si bien qu'un lecteur d'un autre projet la recevait ; et rien à l'écran ne la lit. Seule
# la réponse de l'import la rend, à qui vient de donner le fichier.
#
# Taire À LA SOURCE : `_get_planche` est la seule façon d'atteindre une planche, donc toute
# route qui en rend une passe par ici ; la liste d'un album (`album_planches`), qui lit ses
# planches par `SELECT p.*`, appelle `_planche_rendue` elle-même. Une liste écrite route par
# route en avait oublié une (`PATCH …/role`). `tests/test_master_origine_tue.py` balaie
# l'inventaire des routes.
_PLANCHE_TUE = ("master_origine",)


def _planche_rendue(p: dict) -> dict:
    """Une planche lue par `SELECT *`, sans ce que l'API tait (`_PLANCHE_TUE`)."""
    for col in _PLANCHE_TUE:
        p.pop(col, None)
    return p


def _get_planche(conn, portee: autorisation.Portee, planche_id: int, *,
                 ecriture: bool = False) -> dict:
    ou, params = portee.clause_album("planches.album_id", ecriture=ecriture)
    p = _row(conn.execute(f"SELECT * FROM planches WHERE id = ? AND {ou}",
                          (planche_id, *params)))
    if p is None:
        if ecriture:
            a = conn.execute("SELECT album_id FROM planches WHERE id = ?",
                             (planche_id,)).fetchone()
            _refuser_la_reference(conn, portee, a[0] if a else None)
        raise HTTPException(404, f"Planche {planche_id} introuvable")
    return _planche_rendue(p)


def _get_region(conn, portee: autorisation.Portee, region_id: int, *,
                ecriture: bool = False) -> dict:
    """Une région s'autorise par sa planche, qui s'autorise par son album."""
    ou, params = portee.clause_album("pl.album_id", ecriture=ecriture)
    r = _row(conn.execute(
        f"SELECT r.* FROM regions r JOIN planches pl ON pl.id = r.planche_id "
        f"WHERE r.id = ? AND {ou}", (region_id, *params)))
    if r is None:
        if ecriture:
            a = conn.execute("SELECT pl.album_id FROM regions r JOIN planches pl "
                             "ON pl.id = r.planche_id WHERE r.id = ?", (region_id,)).fetchone()
            _refuser_la_reference(conn, portee, a[0] if a else None)
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
# Le JEU des bacs à sable (COL-4) — une référence qui ne se touche que par son outil
# --------------------------------------------------------------------------- #
# Le projet de jeu porte les copies de RÉFÉRENCE dont chaque bac à sable prend les siennes.
# Une portée totale le lit, comme tout ; elle n'y range rien, n'y détruit rien, ne le règle
# pas : ce qu'on y changerait, chaque bac à sable créé ensuite le recevrait. Un 409 et non
# un 403 : il ne parle que de l'objet, à qui le lit déjà. `tools/preparer_jeu.py` est le
# seul chemin d'écriture.
_MOTIF_JEU = ("C'est le jeu des bacs à sable : chaque bac à sable en prend sa copie, et il "
              "ne se change que par son outil (`tools/preparer_jeu.py`).")


def _refuser_le_jeu(conn, *, projet_id=None, collection_id=None, album_id=None) -> None:
    """409 nommé si le projet — dit, ou lu sur la collection ou sur l'album — est le projet de
    jeu. Sans effet sur tout autre projet."""
    if projet_id is None and collection_id is not None:
        projet_id = projet_de_collection(conn, collection_id)
    if projet_id is None and album_id is not None:
        projet_id = projet_d_album(conn, album_id)
    if est_jeu(conn, projet_id):
        raise HTTPException(409, _MOTIF_JEU)


# --------------------------------------------------------------------------- #
# Le BAC À SABLE (COL-4) — naître, se borner
# --------------------------------------------------------------------------- #
# Un bac à sable est ISOLÉ par sa NATURE (`projet.bac_a_sable_de`), jamais par la portée de
# qui frappe : une portée totale n'y ouvre rien de plus (Hugo, 2026-10-22). Rien n'en sort
# vers un autre projet, rien n'y entre, aucune demande n'atteint l'administrateur depuis lui
# (S3) ; et ce qu'il donne à son propriétaire — responsable d'un projet, qui « écrit quelque
# part » — ne compte pour rien ailleurs (S2, dans `autorisation.Portee`).
_MOTIF_BAC_PROPRIETAIRE = ("Dans un bac à sable, c'est son propriétaire qui le fait : rien "
                           "ne s'y demande à un administrateur.")
_MOTIF_BAC_SANS_DEMANDE = ("Dans un bac à sable, rien ne se demande — ni à un administrateur "
                           "ni à son propriétaire : ce qui demande un consentement, son "
                           "propriétaire le fait lui-même.")
_MOTIF_BAC_SANS_FONDS = ("Dans un bac à sable, rien ne part au fonds : c'est la dernière "
                         "collection de cet album, qui se supprime définitivement (son "
                         "propriétaire le peut) ou s'efface avec le bac à sable.")
_MOTIF_JEU_SOURCE = ("C'est une copie du jeu des bacs à sable : elle n'est la source de rien "
                     "hors d'un bac à sable, et le jeu ne se change que par son outil "
                     "(`tools/preparer_jeu.py`).")
_MOTIF_BAC_ISOLE = ("Un bac à sable est un cul-de-sac : rien n'en sort vers un autre projet, "
                    "et rien n'y entre d'ailleurs.")
_MOTIF_BAC_ANNUAIRE = ("Dans un bac à sable, on fait entrer un compte par son login, sans "
                       "lire l'annuaire.")
_MOTIF_BAC_ACCES = ("Dans un bac à sable, on fait entrer des comptes par le projet, au rôle "
                    "de membre — aucun accès ne se pose collection par collection.")
_MOTIF_EXPORT_BAC = ("Ce document ne sort pas d'un bac à sable : seuls les documents du jeu "
                     "dont les images vivent dans le dépôt s'en exportent.")
_MOTIF_EXPORT_IMPORTEE = ("Une planche importée dans un bac à sable n'en sort jamais : seules "
                          "les images du jeu qui vivent dans le dépôt s'exportent.")

# Les images du JEU — les fichiers que désignent les planches de ses copies de référence
# (`jeu_document.album_reference`). Une copie du jeu désigne les mêmes (D6) ; toute AUTRE
# image d'un bac à sable y a été IMPORTÉE par quelqu'un. `_SQL_IMAGES_EXPORTABLES` : celles
# des seuls documents dont l'export est ouvert (la part du dépôt). Lus ICI, une fois, par le
# plafond d'import et par l'export : un document retiré du jeu par son outil voit ses copies
# compter dans le plafond et cesser de sortir (accepté, Hugo, 2026-10-24).
_SQL_IMAGES_DU_JEU = ("SELECT _ij.chemin_tiff FROM planches _ij JOIN jeu_document _jj "
                      "ON _jj.album_reference = _ij.album_id")
_SQL_IMAGES_EXPORTABLES = _SQL_IMAGES_DU_JEU + " WHERE _jj.exportable = 1"


# La FRONTIÈRE d'un projet isolé, pour le vocabulaire (relecture croisée : un tag global
# rangé dans la base d'un bac à sable partait avec lui, et la région du vrai corpus qui le
# portait le perdait). Un terme a une RIVE : 0 s'il est global ou local à une collection
# ordinaire, l'identifiant du projet isolé s'il est local à l'une de ses collections. Un
# geste qui ferait passer un terme d'une rive à l'autre — le ranger, le fusionner, le
# rattacher, le poser — est refusé, pour toute portée : c'est une propriété des données.
_MOTIF_TERME_FRONTIERE = ("Un terme ne passe pas la frontière d'un bac à sable : ce qui y naît "
                          "y reste, et rien du vrai corpus n'y entre.")


def _rive_d_un_terme(conn, collection_id) -> int:
    """0 pour un terme global ou d'une collection ordinaire ; l'id du projet ISOLÉ (bac à
    sable, jeu) pour un terme local à l'une de ses collections."""
    if collection_id is None:
        return 0
    projet = projet_de_collection(conn, collection_id)
    return projet if est_isole(conn, projet) else 0


def _rive_d_un_album(conn, album_id) -> int:
    """La rive d'un album : l'id de son projet s'il est isolé, 0 sinon."""
    projet = projet_d_album(conn, album_id)
    return projet if est_isole(conn, projet) else 0


def _exiger_une_rive(conn, *rives) -> None:
    """409 nommé si ces rives ne sont pas toutes la même."""
    if len(set(rives)) > 1:
        raise HTTPException(409, _MOTIF_TERME_FRONTIERE)


def _bac_a_sable_de(conn, *, projet_id=None, collection_id=None, album_id=None):
    """`(projet_id, propriétaire)` si le projet — dit, ou lu sur la collection ou l'album —
    est un bac à sable ; `(None, None)` sinon."""
    if projet_id is None and collection_id is not None:
        projet_id = projet_de_collection(conn, collection_id)
    if projet_id is None and album_id is not None:
        projet_id = projet_d_album(conn, album_id)
    n = nature_du_projet(conn, projet_id)
    if n is None or n["bac_a_sable_de"] is None:
        return None, None
    return projet_id, n["bac_a_sable_de"]


def _creer_bac_a_sable(conn, login: str) -> int:
    """Fait naître le bac à sable de `login` et rend son id : le projet (nom stocké « Bac à
    sable », la date de son effacement), son propriétaire RESPONSABLE dans `projet_acces` —
    pour que tout ce qui lit les membres marche sans branche —, sa collection de base
    OUVERTE en écriture à ses membres (l'invité écrit là où est le jeu), et une copie de
    chaque document du jeu, jusqu'à son cran (`database.creer_copie` : aucune image copiée).
    S'écrit au journal comme une création de projet. À appeler SOUS le verrou d'écriture,
    après avoir relu qu'il n'en a pas ; ne commite pas."""
    efface_le = prochain_effacement()
    pid = conn.execute(
        "INSERT INTO projet (nom, description, bac_a_sable_de, efface_le) VALUES (?, ?, ?, ?)",
        (NOM_BAC_A_SABLE, "Un bac à sable : on y apprend l'outil. Il s'efface chaque semaine.",
         login, efface_le)).lastrowid
    journal.journaliser(conn, "creation", "projet", pid,
                        apres={"nom": NOM_BAC_A_SABLE, "bac_a_sable": True,
                               "efface_le": efface_le})
    conn.execute("INSERT INTO projet_acces (projet_id, genre, principal, role) "
                 "VALUES (?, ?, ?, ?)",
                 (pid, autorisation.UTILISATEUR, login, autorisation.RESPONSABLE))
    journal.journaliser(conn, "lien", "projet_acces", pid,
                        apres={"genre": autorisation.UTILISATEUR, "principal": login,
                               "role": autorisation.RESPONSABLE})
    base = creer_collection_de_base(conn, pid, nom=NOM_BAC_A_SABLE,
                                    acces_membres=autorisation.ECRITURE)
    journal.journaliser(conn, "creation", "collection", base,
                        apres={"nom": NOM_BAC_A_SABLE, "proprietaire": None, "base": True,
                               "projet_id": pid, "acces_membres": autorisation.ECRITURE})
    for document_id, reference, cran in conn.execute(
            "SELECT jd.document_id, jd.album_reference, jd.cran FROM jeu_document jd "
            "JOIN albums a ON a.id = jd.album_reference AND a.document_id = jd.document_id "
            "ORDER BY jd.rang, jd.document_id").fetchall():
        creer_copie(conn, document_id, base, par=login, depuis=reference, cran=cran)
    return pid


def _sortir_du_bac(conn, projet_id: int, genre: str, principal: str) -> bool:
    """Fait SORTIR un membre d'un bac à sable — qu'il le quitte de lui-même ou que son
    propriétaire le retire : il perd ce qu'il tenait dans ce bac à sable, y compris la
    PROPRIÉTÉ des collections qu'il y a créées (décision du pilotage, l'option fermée). Sa
    ligne de projet part, et ses accès sur les collections du bac à sable avec elle ; une
    collection qu'il était seul à tenir n'est plus lue de personne, et part avec le bac à
    sable. Rien n'est détruit : le journal lui attribue son travail. Chaque retrait s'écrit
    (`delien`). Ne commite pas ; rend False s'il n'en était pas membre."""
    ligne = conn.execute("SELECT role FROM projet_acces WHERE projet_id = ? AND genre = ? "
                         "AND principal = ?", (projet_id, genre, principal)).fetchone()
    if ligne is None:
        return False
    conn.execute("DELETE FROM projet_acces WHERE projet_id = ? AND genre = ? "
                 "AND principal = ?", (projet_id, genre, principal))
    journal.journaliser(conn, "delien", "projet_acces", projet_id,
                        avant={"genre": genre, "principal": principal, "role": ligne[0]})
    for cid, niveau, exporter in conn.execute(
            f"SELECT ca.collection_id, ca.niveau, ca.exporter FROM collection_acces ca "
            f"JOIN collection c ON c.id = ca.collection_id WHERE {sql_projet_de('c')} = ? "
            f"AND ca.genre = ? AND ca.principal = ?",
            (projet_id, genre, principal)).fetchall():
        conn.execute("DELETE FROM collection_acces WHERE collection_id = ? AND genre = ? "
                     "AND principal = ?", (cid, genre, principal))
        journal.journaliser(conn, "delien", "collection_acces", cid,
                            avant={"genre": genre, "principal": principal, "niveau": niveau,
                                   "exporter": bool(exporter)})
    return True


def _planches_importees_du_bac(conn, projet_id: int) -> int:
    """Combien d'IMAGES ont été importées dans ce bac à sable (S9) : les fichiers distincts
    que désignent les planches de ses albums et qui ne sont pas des images du jeu
    (`_SQL_IMAGES_DU_JEU`). Toute planche importée par quelqu'un compte, QUEL QUE SOIT
    l'album — un album à soi comme une copie du jeu (relecture croisée : importer dans une
    copie du jeu contournait le plafond). Une copie faite dans le bac à sable d'un album
    importé ne compte pas deux fois : elle désigne les mêmes fichiers."""
    return conn.execute(
        "SELECT COUNT(DISTINCT p.chemin_tiff) FROM planches p JOIN albums a ON a.id = p.album_id "
        f"WHERE {sql_projet_d_album('a')} = ? AND p.chemin_tiff NOT IN ({_SQL_IMAGES_DU_JEU})",
        (projet_id,)).fetchone()[0]


def _exiger_le_plafond(conn, album_id: int, ajout: int = 1) -> None:
    """409 nommé si importer `ajout` planche(s) dans cet album dépasse le plafond du bac à
    sable qui le porte (S9 ; Hugo, 2026-10-21 : « une cinquantaine »). Sans effet hors d'un
    bac à sable."""
    projet_id, _ = _bac_a_sable_de(conn, album_id=album_id)
    if projet_id is None:
        return
    deja = _planches_importees_du_bac(conn, projet_id)
    if deja + ajout > BAC_A_SABLE_PLAFOND_PLANCHES:
        raise HTTPException(409, f"Un bac à sable porte {BAC_A_SABLE_PLAFOND_PLANCHES} "
                                 f"planches importées au plus ({deja} déjà) : remettez-le à "
                                 "neuf pour recommencer.")


def _exiger_l_export_hors_bac(conn, album_id: int, planche_id: int | None = None) -> None:
    """403 nommé si l'album vit dans un projet ISOLÉ — un bac à sable, ou le JEU lui-même,
    pour sa copie de référence — et n'est pas la copie d'un document du jeu dont l'export
    est ouvert (`jeu_document.exportable` : la part du dépôt). L'export se décide DOCUMENT
    par document, jamais par bac à sable (Hugo, 2026-10-22), et pour TOUTE portée : la part
    du serveur ne sort jamais, pas même par l'administrateur qui lit la référence (relecture
    croisée). Et une planche IMPORTÉE par quelqu'un ne sort jamais, quel que soit l'album
    (Hugo, 2026-10-24) : l'album entier se refuse s'il en porte une, la figure si elle en
    est tirée (`planche_id`)."""
    isole = conn.execute(f"SELECT {sql_album_isole('a')} FROM albums a WHERE a.id = ?",
                         (album_id,)).fetchone()
    if isole is None or not isole[0]:
        return
    if conn.execute("SELECT 1 FROM albums a JOIN jeu_document jd ON jd.document_id = "
                    "a.document_id WHERE a.id = ? AND jd.exportable = 1",
                    (album_id,)).fetchone() is None:
        raise HTTPException(403, _MOTIF_EXPORT_BAC)
    une = (" AND p.id = ?", [planche_id]) if planche_id is not None else ("", [])
    if conn.execute(f"SELECT 1 FROM planches p WHERE p.album_id = ?{une[0]} "
                    f"AND p.chemin_tiff NOT IN ({_SQL_IMAGES_EXPORTABLES}) LIMIT 1",
                    (album_id, *une[1])).fetchone():
        raise HTTPException(403, _MOTIF_EXPORT_IMPORTEE)


def _refuser_le_bac_a_sable(conn, motif: str, status: int = 409, **objet) -> None:
    """Le refus d'un geste qui n'a pas cours dans un bac à sable, quelle que soit la portée."""
    projet_id, _ = _bac_a_sable_de(conn, **objet)
    if projet_id is not None:
        raise HTTPException(status, motif)


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
                        planche: bool = False, reference_du_jeu: bool = False) -> None:
    """403 si l'on ne peut pas supprimer DÉFINITIVEMENT cet album — ou, `planche`, l'une
    de ses planches : on supprime une planche là où l'on pourrait supprimer le document
    (décision B4 de Hugo, 2026-10-11).

    COL-4 — une copie de RÉFÉRENCE du jeu ne se détruit pas, quelle que soit la portée : 409
    nommé (`_refuser_le_jeu`). `reference_du_jeu` lève ce seul refus, et seul l'outil du jeu
    le passe — quand plus aucun bac à sable ne tient de copie d'un document retiré du jeu."""
    if not reference_du_jeu:
        _refuser_le_jeu(conn, album_id=album_id)
    ou, params = portee.clause_suppression_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                    (album_id, *params)).fetchone() is None:
        raise HTTPException(403, _MOTIF_DESTRUCTION_PLANCHE if planche
                            else _MOTIF_DESTRUCTION)


def _detruire_album(conn, portee: autorisation.Portee, album_id: int, *,
                    reference_du_jeu: bool = False) -> None:
    """DÉTRUIT un album — sa ligne, son travail, son document s'il n'a plus d'autre copie,
    ses images —, garde comprise. Le seul chemin de la destruction d'un album : la route
    `DELETE /api/albums/{id}` et la réponse « accepter » à une demande (`routes/fonds.py`)
    y passent toutes deux, et la garde vit ICI pour qu'aucune des deux ne l'oublie.

    Il COMMITE, puis efface les fichiers : à appeler en DERNIER, après tout ce qui doit
    partir dans la même transaction. Les fichiers quittent le disque après le commit, et
    pas avant : une base qui refuserait d'écrire laisserait sinon un album sans images. Ils
    le quittent SOUS LE VERROU d'écriture, repris pour cela (`_sous_le_verrou`) : une copie
    sœur qui naîtrait pendant le ménage garde ses fichiers.

    Ce qu'il écrit au journal : la fin de chacun des emplois de la copie (la cascade défait
    ses rangements sans rien dire), puis la destruction du document — ou, quand une copie
    sœur le porte encore, la copie qu'il perd. Et il CLÔT toute
    demande de suppression qui visait ce document : elle a reçu sa réponse, quel que soit
    le geste qui l'a donnée — l'importateur qui détruit lui-même ce qu'un autre avait
    demandé, ou l'administrateur.

    La garde se lit SOUS LE VERROU D'ÉCRITURE (`conflit.verrouiller`, le remède de CONC-3),
    et la destruction suit dans la même transaction. Lue hors transaction, elle laissait
    passer un travail validé entre la garde et le `DELETE` : il partait avec l'album, sans
    que personne l'ait demandé (relecture croisée de la tranche 2, sonde S9)."""
    conflit.verrouiller(conn)
    _exiger_destruction(conn, portee, album_id, reference_du_jeu=reference_du_jeu)
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
    else:
        # Une copie SŒUR porte encore le document (COL-3, tranche 3, D5) : il n'est pas
        # détruit, mais il PERD une copie, son travail et ses planches — et cela s'écrit,
        # sous le document, comme un scan retiré : `avant` seul, l'album dans la charge.
        # Seule la fin de ses emplois s'écrivait jusqu'ici : le journal laissait croire la
        # copie sortie de ses collections, jamais détruite.
        journal.journaliser(conn, "modification", "document", document_id,
                            avant={"album_id": album_id,
                                   "copie": {"titre": a["titre"], "planches": nb_planches}})
    # Les demandes qui visaient CETTE copie ont leur réponse (COL-3, tranche 3) : une
    # demande se dépose sur une copie (`demande_document.album_id`), et celle d'une sœur,
    # dans un autre projet, attend toujours la sienne.
    _clore_demandes(conn, portee, [r[0] for r in conn.execute(
        "SELECT d.id FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
        "WHERE d.genre = ? AND dd.album_id = ? AND d.reponse IS NULL",
        (DEMANDE_SUPPRESSION_DOCUMENT, album_id))], REPONSE_ACCEPTEE)
    _clore_lignes_d_une_copie_detruite(conn, portee, album_id)
    conn.commit()
    _sous_le_verrou(conn, _effacer_les_images_d_une_copie, conn, album_id, chemins)


def _clore_lignes_d_une_copie_detruite(conn, portee: autorisation.Portee,
                                       album_id: int) -> None:
    """Les demandes qui visaient CETTE copie et qu'elle ne peut plus satisfaire — un
    `rejoindre` (la ranger ailleurs), la ligne d'une entrée qui la REPREND du fonds, la
    demande de la RENDRE (`DEMANDE_RENDRE`, COL-3, écran de la 3a), celle d'EN PARTIR
    (`DEMANDE_AMORCER`, tranche 3b : elle en est la source) — se closent avec elle : leur ligne est refusée, et l'état de la demande se recalcule
    (`database.etat_des_reponses` — une entrée de plusieurs documents reste en attente si
    d'autres lignes attendent, `partielle` si d'autres ont été acceptées). Sans cela elles
    attendaient pour toujours, invisibles de qui doit consentir (relecture croisée de la
    tranche 3a, défaut 2). Ne commite pas ; l'appelant est `_detruire_album`."""
    lignes = conn.execute(
        "SELECT dd.demande_id, dd.document_id FROM demande_document dd "
        "JOIN demande d ON d.id = dd.demande_id "
        "WHERE dd.album_id = ? AND dd.reponse IS NULL AND d.reponse IS NULL "
        "AND d.genre IN (?, ?, ?, ?) ORDER BY dd.demande_id",
        (album_id, DEMANDE_REJOINDRE, DEMANDE_ENTREE_DOCUMENTS, DEMANDE_RENDRE,
         DEMANDE_AMORCER)).fetchall()
    for demande_id, document_id in lignes:
        conn.execute("UPDATE demande_document SET reponse = ? WHERE demande_id = ? "
                     "AND document_id = ?", (REPONSE_REFUSEE, demande_id, document_id))
        etat = etat_des_reponses(r[0] for r in conn.execute(
            "SELECT reponse FROM demande_document WHERE demande_id = ?", (demande_id,)))
        if etat is not None:
            conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                         "date_reponse = datetime('now') WHERE id = ? AND reponse IS NULL",
                         (etat, portee.utilisateur, demande_id))
        journal.journaliser(conn, "modification", "demande", demande_id,
                            apres={"documents": {str(document_id): REPONSE_REFUSEE},
                                   "copie_detruite": album_id, "reponse": etat})


def _sous_le_verrou(conn, effacer, *args) -> None:
    """Efface des images SOUS LE VERROU D'ÉCRITURE, après le commit de la destruction
    (COL-3, tranche 3 ; relecture croisée de la v31, constat 4).

    Ce qu'il faut garder se LIT dans la base — les chemins qu'une autre planche désigne
    encore —, puis les fichiers partent. Hors verrou, une copie SŒUR née entre la lecture et
    l'effacement (`database.creer_copie`, qui écrit ses planches sous ce même verrou)
    perdait les fichiers qu'elle venait de désigner : une image effacée sous une sœur, ce
    qui ne se rattrape pas. Le verrou est donc REPRIS, la lecture et l'effacement se font
    dessous, puis il est rendu sans rien avoir écrit.

    Pourquoi pas dans la transaction de la destruction elle-même : les fichiers partiraient
    AVANT son commit, et une base qui refuserait de valider laisserait un album sans images.
    Deux temps donc — la destruction validée, puis le ménage gardé —, et une sœur qui naît
    entre les deux désigne ses fichiers AVANT qu'on lise ce qu'il faut garder : ils restent."""
    try:
        conflit.verrouiller(conn)
    except sqlite3.OperationalError as exc:
        # La destruction est VALIDÉE : elle doit répondre son succès. Sans le verrou on ne
        # sait pas ce qu'une sœur née à l'instant désigne — on n'efface donc rien, et le
        # journal du serveur dit ce qui reste (relecture croisée de la tranche 3a). Un
        # fichier laissé se rattrape ; une image effacée sous une sœur, non.
        logging.getLogger("bd_annotator").warning(
            "Ménage d'images différé : le verrou d'écriture n'a pas été obtenu (%s) ; les "
            "fichiers de %s restent sur le disque.", exc, args[1:2] or args)
        return
    try:
        effacer(*args)
    finally:
        conn.rollback()                     # rien n'a été écrit : le verrou est rendu


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
    """Donne sa RÉPONSE à des demandes en attente — et à chacun de leurs documents qui
    attend encore —, et l'écrit au journal. Ne commite pas. Une demande répondue RESTE :
    c'est ce qui permet de dire qu'une même suppression a déjà été refusée, et le journal
    garde qui a répondu.

    `repondu_par` est l'appelant : l'administrateur qui répond, ou celui dont le geste a
    satisfait la demande — l'importateur qui détruit ce qu'un autre avait demandé.

    L'ÉTAT de la demande se lit sur ses documents (`database.etat_des_reponses`, COL-3,
    tranche 3) : une entrée dont l'administrateur avait déjà accepté une ligne, close
    ensuite par un refus, est `partielle` et non `refusee`. Une demande sans document (un
    projet) prend la réponse telle quelle.

    Une demande qui a DÉJÀ sa réponse n'en reçoit pas d'autre, et rien ne s'écrit au
    journal pour elle : la ligne disait jusqu'ici une réponse qu'aucun `UPDATE` n'avait
    posée (relecture croisée de la tranche 2)."""
    for demande_id in ids:
        if conn.execute("SELECT 1 FROM demande WHERE id = ? AND reponse IS NULL",
                        (demande_id,)).fetchone() is None:
            continue
        conn.execute("UPDATE demande_document SET reponse = ? "
                     "WHERE demande_id = ? AND reponse IS NULL", (reponse, demande_id))
        etat = etat_des_reponses(r[0] for r in conn.execute(
            "SELECT reponse FROM demande_document WHERE demande_id = ?", (demande_id,)))
        etat = etat or reponse
        conn.execute("UPDATE demande SET reponse = ?, repondu_par = ?, "
                     "date_reponse = datetime('now') WHERE id = ? AND reponse IS NULL",
                     (etat, portee.utilisateur, demande_id))
        journal.journaliser(conn, "modification", "demande", demande_id,
                            avant={"reponse": None}, apres={"reponse": etat})


def _clore_demandes_vers(conn, portee: autorisation.Portee, collection_id: int) -> None:
    """Refuse les demandes qui attendent encore et nomment cette collection comme ARRIVÉE
    — une entrée de documents, un rejoindre —, au moment où elle disparaît. Son
    identifiant se réattribue : acceptée plus tard, une telle demande rangerait dans la
    collection créée ensuite, une autre étude (COL-3, tranche 3). Ne commite pas."""
    _clore_demandes(conn, portee, demandes_vers_collection(conn, collection_id),
                    REPONSE_REFUSEE)


def _retour_en_attente(conn, album_id: int):
    """La demande de RENDRE cette copie qui attend sa réponse (`DEMANDE_RENDRE`), ou None.

    Par COPIE, et non par collection d'arrivée comme `_en_attente_vers` : rendre la même
    copie à deux collections à la fois n'aurait pas de sens — la seconde demande, acceptée,
    trouverait la copie déjà rendue. Un retour ne s'attend donc qu'une fois par copie (écran
    de la 3a, COL-3) ; refusé, il se redemande."""
    return conn.execute(
        "SELECT d.id, d.date_creation, d.collection_id, d.collection_nom FROM demande d "
        "JOIN demande_document dd ON dd.demande_id = d.id "
        "WHERE d.genre = ? AND dd.album_id = ? AND d.reponse IS NULL ORDER BY d.id LIMIT 1",
        (DEMANDE_RENDRE, album_id)).fetchone()


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
        _clore_demandes_vers(conn, portee, b["id"])
        conn.execute("DELETE FROM collection WHERE id = ?", (b["id"],))
        journal.journaliser(conn, "suppression", "collection", b["id"],
                            avant={"nom": b["nom"], "base": True})
    conn.execute("DELETE FROM projet WHERE id = ?", (projet_id,))
    journal.journaliser(conn, "suppression", "projet", projet_id, avant={"nom": p["nom"]})



# --------------------------------------------------------------------------- #
# Le BAC À SABLE (COL-4) — s'effacer
# --------------------------------------------------------------------------- #
_MOTIF_PAS_UN_BAC = ("Ce projet n'est pas un bac à sable : seul un bac à sable s'efface ainsi. "
                     "Un projet ordinaire ne se supprime que vide.")
# Combien de fois l'effacement relit les albums d'un bac à sable avant de renoncer : chaque
# tour détruit tout ce qu'il a lu, et un tour sans album finit sous le verrou.
_TOURS_D_EFFACEMENT = 20


def _supprimer_le_vocabulaire_du_bac(conn, projet_id: int, collections: list) -> None:
    """Supprime le vocabulaire LOCAL aux collections de ce bac à sable — SAUF ce qui est
    employé hors de lui (relecture croisée : un terme du vrai corpus rangé là partait avec
    le bac à sable, et les régions du corpus qui le portaient le perdaient). Les gestes qui
    feraient passer un terme la frontière sont refusés (`_exiger_une_rive`) ; ceci est la
    défense de l'état qu'aurait laissé une base retouchée. Ce qui reste devient GLOBAL quand
    sa collection part (`ON DELETE SET NULL`) : employé dans le corpus, le détruire
    détruirait du travail du corpus.

    Employé dehors : un tag posé sur une région d'un album d'un autre projet ; une valeur
    posée sur une telle région, ou sur un personnage qui n'est pas né dans ce bac à sable ;
    une dimension qui porte une telle valeur (elle reste avec TOUTES ses valeurs) ; un
    domaine qui porte une dimension qui n'est pas du bac à sable.
    Les valeurs avant leurs dimensions, les dimensions avant leurs domaines."""
    marques = ", ".join("?" * len(collections))
    dehors = (f"EXISTS (SELECT 1 FROM regions _r JOIN planches _p ON _p.id = _r.planche_id "
              f"JOIN albums _a ON _a.id = _p.album_id WHERE _r.id = {{region}} "
              f"AND {sql_projet_d_album('_a')} IS NOT ?)")
    valeurs_dehors = (
        f"SELECT v.id FROM attribut_valeur v WHERE "
        f"(EXISTS (SELECT 1 FROM region_attribut ra WHERE ra.valeur_id = v.id AND "
        f"{dehors.format(region='ra.region_id')}) "
        f"OR EXISTS (SELECT 1 FROM personnage_attribut pa JOIN personnages pe "
        f"ON pe.id = pa.personnage_id WHERE pa.valeur_id = v.id "
        f"AND pe.bac_a_sable_id IS NOT ?))")
    dims_gardees = (f"SELECT d.id FROM attribut_dimension d WHERE d.collection_id IN "
                    f"({marques}) AND d.id IN (SELECT dimension_id FROM attribut_valeur "
                    f"WHERE id IN ({valeurs_dehors}))")
    p_dims = [*collections, projet_id, projet_id]
    conn.execute(f"DELETE FROM attribut_valeur WHERE collection_id IN ({marques}) "
                 f"AND id NOT IN ({valeurs_dehors}) AND dimension_id NOT IN ({dims_gardees})",
                 [*collections, projet_id, projet_id, *p_dims])
    conn.execute(f"DELETE FROM attribut_dimension WHERE collection_id IN ({marques}) "
                 f"AND id NOT IN ({dims_gardees})", [*collections, *p_dims])
    conn.execute(f"DELETE FROM domaine WHERE collection_id IN ({marques}) AND NOT EXISTS "
                 f"(SELECT 1 FROM attribut_dimension d WHERE d.domaine_id = domaine.id "
                 f"AND (d.collection_id IS NULL OR d.collection_id NOT IN ({marques})))",
                 [*collections, *collections])
    # (Les dimensions gardées sont encore locales au bac à sable à cet instant : un domaine
    # qui n'a qu'elles part, et elles deviennent « hors domaine » — leur portée suit, globale.)
    employe_dehors = (f"EXISTS (SELECT 1 FROM annotation_tags at JOIN annotations an "
                      f"ON an.id = at.annotation_id WHERE at.tag_id = tags.id "
                      f"AND {dehors.format(region='an.region_id')})")
    conn.execute(f"DELETE FROM tags WHERE (collection_id IN ({marques}) OR espace = ?) "
                 f"AND NOT {employe_dehors}", [*collections, projet_id, projet_id])
    # Un tag de l'ESPACE du bac à sable employé dehors rejoint celui de l'instance : fondu
    # dans le tag de même libellé s'il y en a un (l'unicité par espace l'exige), sinon
    # déplacé tel quel.
    for tid, label in conn.execute("SELECT id, label FROM tags WHERE espace = ?",
                                   (projet_id,)).fetchall():
        autre = conn.execute("SELECT id FROM tags WHERE espace = 0 AND label = ?",
                             (label,)).fetchone()
        if autre is None:
            conn.execute("UPDATE tags SET espace = 0 WHERE id = ?", (tid,))
            continue
        conn.execute("INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
                     "SELECT annotation_id, ? FROM annotation_tags WHERE tag_id = ?",
                     (autre[0], tid))
        conn.execute("DELETE FROM tags WHERE id = ?", (tid,))


def _passer_les_gestes_du_bac(conn, projet_id: int) -> int:
    """Le témoin de l'annulation (S5) : les gestes humains encore annulables faits sur les
    régions de ce bac à sable sont PASSÉS (`undo.ecarter`, la trace append-only d'AUTH-14),
    avant que leurs objets partent. Sans lui, Ctrl+Z refusait ces gestes un par un après
    l'effacement — « ne s'annule plus », autant de fois qu'il y en avait. Ceux qu'il voit :
    les actes sur une région VIVANTE du bac à sable, ceux dont la charge nomme l'une de ses
    planches (une région créée, modifiée ou supprimée). Ne commite pas ; rend le nombre."""
    import undo                                  # import paresseux : `undo` ne dépend de rien ici
    planches = [r[0] for r in conn.execute(
        f"SELECT p.id FROM planches p JOIN albums a ON a.id = p.album_id "
        f"WHERE {sql_projet_d_album('a')} = ?", (projet_id,))]
    if not planches:
        return 0
    marques = ", ".join("?" * len(planches))
    tables = ", ".join("?" * len(undo._TABLES))
    gestes = conn.execute(
        f"SELECT * FROM evenement e WHERE e.agent_type = 'humain' "
        f"AND e.cible_table IN ({tables}) "
        f"AND (e.cible_id IN (SELECT r.id FROM regions r WHERE r.planche_id IN ({marques})) "
        f"     OR (json_valid(e.apres) AND json_extract(e.apres, '$.planche_id') IN ({marques})) "
        f"     OR (json_valid(e.avant) AND json_extract(e.avant, '$.planche_id') IN ({marques}))) "
        f"AND e.id NOT IN (SELECT cible_id FROM evenement "
        f"                 WHERE ((type = 'annulation' AND cible_table = 'evenement') "
        f"                     OR (type = 'abandon' AND cible_table = 'annulation')) "
        f"                   AND cible_id IS NOT NULL) ORDER BY e.id",
        (*undo._TABLES, *planches, *planches, *planches)).fetchall()
    for e in gestes:
        undo.ecarter(conn, e)
    return len(gestes)


def _effacer_bac_a_sable(conn, portee: autorisation.Portee, projet_id: int, *,
                         motif: str) -> dict:
    """EFFACE un bac à sable et tout ce qu'il porte — le chemin de la remise à neuf et de
    l'effacement hebdomadaire (S5 du cadrage). Distinct de `_supprimer_projet`, qui n'accepte
    qu'un projet vide et doit le rester pour les vrais.

    Sa première garde, relue SOUS le verrou d'écriture : le projet est un bac à sable
    (`projet.bac_a_sable_de`) — jamais un projet ordinaire, jamais le jeu, jamais le repli
    (409 nommé). La DROIT de l'appelant reste chez lui : la route ne l'appelle que pour le
    bac à sable de qui frappe, l'outil avec une portée totale. Puis, dans l'ordre :

    1. les gestes encore annulables faits sur ses régions sont PASSÉS (le témoin de Ctrl+Z) ;
    2. chaque album dont le projet est ce bac à sable — rangé, ou gardé au fonds — est
       détruit par `_detruire_album`, le seul chemin de la destruction d'un album : fin des
       emplois au journal, demandes closes, document parti avec sa dernière copie (ce qu'on
       y a importé), images effacées PAR RÉFÉRENCE — celles du jeu restent, la référence et
       les autres bacs à sable les désignent. Un commit par album ;
    3. son vocabulaire local (tags d'abord nés là, S2 ; dimensions, valeurs, domaines) est
       supprimé AVANT ses collections — supprimées d'abord, elles le rendraient GLOBAL
       (`ON DELETE SET NULL`) ; ses collections, base comprise, avec leurs accès (cascade),
       en refusant les demandes qui les nomment comme arrivée ;
    4. le projet, ses membres avec lui (cascade), et l'acte s'écrit : `suppression` sous
       `projet`, charge `{bac_a_sable: true, motif}`.

    Les PERSONNAGES nés dans le bac à sable partent avec lui (`personnages.bac_a_sable_id`,
    Hugo, 2026-10-24) ; un personnage du registre ne se détruit pas parce qu'il est passé
    par un bac à sable.

    Idempotent : un arrêt au milieu laisse un bac à sable à moitié effacé, que l'appel
    suivant finit ; un projet déjà parti rend `efface: False`. Le journal garde tout,
    append-only. Rend `{efface, albums, gestes_passes}`.

    D'UN SEUL TENANT pour ce qui suit les albums (relecture croisée : un album créé pendant
    l'effacement — un invité qui travaille — faisait tomber la suppression du projet sur
    une clé étrangère, 500, et laissait un bac à sable à moitié effacé). Les albums se
    relisent SOUS le verrou, tour après tour : tant qu'il en reste, ils sont détruits (un
    commit chacun, comme avant) ; quand il n'en reste aucun, le verrou est GARDÉ jusqu'à la
    suppression du projet — rien ne peut plus naître entre les deux. Au-delà de
    `_TOURS_D_EFFACEMENT` tours, un 409 dit de réessayer, sans rien laisser d'incohérent."""
    detruits, passes = 0, 0
    # Les planches et les régions qu'emporte l'effacement, écrites dans la charge de sa
    # `suppression` : ce que le journal en garde reste ainsi rattaché à un bac à sable
    # parti (`database.sql_acte_isole` — un compte ne « laisse » pas ce qui s'efface).
    emportees = {"planches": set(), "regions": set()}
    for _tour in range(_TOURS_D_EFFACEMENT):
        conflit.verrouiller(conn)
        n = nature_du_projet(conn, projet_id)
        if n is None:                                       # déjà effacé, ou par un autre
            conn.rollback()
            return {"efface": False, "albums": detruits, "gestes_passes": passes}
        if n["bac_a_sable_de"] is None:
            conn.rollback()
            raise HTTPException(409, _MOTIF_PAS_UN_BAC)
        passes += _passer_les_gestes_du_bac(conn, projet_id)
        albums = [r[0] for r in conn.execute(
            f"SELECT a.id FROM albums a WHERE {sql_projet_d_album('a')} = ? ORDER BY a.id",
            (projet_id,))]
        if not albums:
            break                                          # le verrou reste TENU
        marques = ", ".join("?" * len(albums))
        for pl_id, rg_id in conn.execute(
                f"SELECT p.id, r.id FROM planches p LEFT JOIN regions r ON r.planche_id = p.id "
                f"WHERE p.album_id IN ({marques})", albums):
            emportees["planches"].add(pl_id)
            if rg_id is not None:
                emportees["regions"].add(rg_id)
        conn.commit()
        for album_id in albums:
            _detruire_album(conn, portee, album_id)
            detruits += 1
    else:
        raise HTTPException(409, "Ce bac à sable change pendant qu'on l'efface : réessayez.")
    collections = [(r[0], r[1]) for r in conn.execute(
        f"SELECT c.id, c.nom FROM collection c WHERE {sql_projet_de('c')} = ? ORDER BY c.id",
        (projet_id,))]
    ids = [c for c, _nom in collections]
    if ids:
        _supprimer_le_vocabulaire_du_bac(conn, projet_id, ids)
    for collection_id, nom in collections:
        _clore_demandes_vers(conn, portee, collection_id)
        conn.execute("DELETE FROM collection WHERE id = ?", (collection_id,))
        journal.journaliser(conn, "suppression", "collection", collection_id,
                            avant={"nom": nom, "bac_a_sable": True})
    # COL-4 (Hugo, 2026-10-24) — les personnages NÉS dans le bac à sable partent avec lui :
    # leurs apparitions sont parties avec ses régions. Un personnage qui apparaîtrait encore
    # ailleurs (base retouchée : aucune route ne l'attribue hors de son bac à sable) rejoint
    # le registre au lieu d'emporter ce travail.
    ailleurs = ("EXISTS (SELECT 1 FROM {t} x WHERE x.personnage_id = personnages.id)")
    conn.execute(f"UPDATE personnages SET bac_a_sable_id = NULL WHERE bac_a_sable_id = ? "
                 f"AND ({ailleurs.format(t='bulle_locuteur')} "
                 f"OR {ailleurs.format(t='personnage_presence')})", (projet_id,))
    conn.execute("DELETE FROM personnages WHERE bac_a_sable_id = ?", (projet_id,))
    nom = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()[0]
    conn.execute("DELETE FROM projet WHERE id = ?", (projet_id,))
    journal.journaliser(conn, "suppression", "projet", projet_id,
                        avant={"nom": nom, "bac_a_sable": True, "motif": motif,
                               "planches": sorted(emportees["planches"]),
                               "regions": sorted(emportees["regions"])})
    conn.commit()
    return {"efface": True, "albums": detruits, "gestes_passes": passes}


# --------------------------------------------------------------------------- #
# Prendre et rejoindre (COL-3, tranche 3a) — ce que partagent la prise et « + Ranger ici »
# --------------------------------------------------------------------------- #
# Ce que devient une ligne d'une prise, ou un rangement demandé : fait tout de suite,
# demandé (une demande à qui consent), ou refusé (avec son motif).
FAIT, DEMANDE, REFUSE = "fait", "demande", "refuse"


def _nouvelle_copie(conn, portee: autorisation.Portee, document_id: int, collection_id: int,
                    depuis: int, *, pour: str | None = None, cran: str = CRAN_IMAGES) -> int:
    """Une copie du document dans cette collection, créée par l'APPELANT : VIERGE (cran
    `images`, la seule réponse de la 3a qui crée une copie), ou — tranche 3b, « en partir »
    — amorcée avec le travail de `depuis` jusqu'au `cran` dit (`database.creer_copie`).

    QUI l'a créée (`copie.creee_par`, ce que lit la suppression directe) : l'appelant, qui
    part de zéro ou prend directement — l'administrateur compris ; et pour une ENTRÉE
    acceptée, le DEMANDEUR (`pour`), pas l'administrateur qui accepte (Hugo, 2026-10-17) :
    c'est lui qui a pris le document, et il le supprime seul si les autres conditions
    tiennent. La naissance reste journalisée sous l'agent qui l'a faite ; la règle ne la
    compte pas comme un travail (`autorisation._sources_du_travail`). Une demande d'en
    partir acceptée suit la même règle : la copie est au demandeur."""
    return creer_copie(conn, document_id, collection_id,
                       par=pour if pour is not None else portee.utilisateur,
                       depuis=depuis, cran=cran)


def _plan_rejoindre(conn, portee: autorisation.Portee, album_id: int,
                    collection_id: int) -> dict:
    """Rejoindre une copie qu'on LIT depuis une collection où l'on ÉCRIT — les deux droits
    sont vérifiés par l'appelant. Rend `{etat: fait, deja: True}` (elle y est déjà), `refuse`
    (le rangement ne traverse pas les projets), `fait` (on administre chacune des
    collections où elle vit, `Portee.clause_rejoindre_directe`), ou `demande` (D4 stricte :
    le propriétaire consent). N'écrit rien ; à lire sous le verrou d'écriture."""
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ? AND collection_id = ?",
                    (album_id, collection_id)).fetchone():
        return {"etat": FAIT, "deja": True}
    if rangement_traverse(conn, album_id, collection_id):
        return {"etat": REFUSE, "motif": "Cette copie vit dans un autre projet que cette "
                                         "collection : le rangement ne traverse pas les "
                                         "projets."}
    ou, params = portee.clause_rejoindre_directe("a.id")
    if conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                    (album_id, *params)).fetchone():
        return {"etat": FAIT}
    return {"etat": DEMANDE, "genre": DEMANDE_REJOINDRE}


def _en_attente_vers(conn, genre: str, collection_id: int, document_id: int,
                     album_id) -> bool:
    """La même demande attend-elle déjà — même genre, même document (et même copie), même
    collection d'arrivée ? Elle ne se dépose pas deux fois tant qu'elle attend ; refusée,
    elle se redépose."""
    return conn.execute(
        "SELECT 1 FROM demande d JOIN demande_document dd ON dd.demande_id = d.id "
        "WHERE d.genre = ? AND d.collection_id = ? AND dd.document_id = ? "
        "AND dd.album_id IS ? AND dd.reponse IS NULL AND d.reponse IS NULL",
        (genre, collection_id, document_id, album_id)).fetchone() is not None


def _deposer(conn, portee: autorisation.Portee, genre: str, collection: dict,
             projet_id, motif, lignes, *, cran: str | None = None) -> int:
    """Écrit une demande d'ENTRÉE ou de REJOINDRE, ses documents — `document_id`, `album_id`
    (la copie visée : celle qu'on rejoint, ou la copie gardée qu'on reprend ; NULL pour une
    copie vierge), `titre` —, et sa trace au journal. Rend son id. Ne commite pas. La
    collection d'arrivée est écrite avec son NOM, son identifiant pouvant se réattribuer.
    `cran` : celui d'une demande d'EN PARTIR (tranche 3b, `demande.cran`) ; None sinon.

    COL-4 — aucune demande, d'aucun genre, ne naît d'un BAC À SABLE ni du jeu : 403 nommé,
    quelle que soit la portée (relecture croisée : une entrée de documents partait d'un bac
    à sable vers l'administrateur). Les routes refusent avant ; ceci est le dernier mot,
    là où toute demande de prise ou de rejoindre s'écrit."""
    if est_isole(conn, projet_id) or est_isole(conn, projet_de_collection(conn,
                                                                          collection["id"])):
        raise HTTPException(403, _MOTIF_BAC_SANS_DEMANDE)
    projet = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()
    cur = conn.execute(
        "INSERT INTO demande (genre, demandeur, motif, projet_id, projet_nom, collection_id, "
        "collection_nom, cran) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (genre, portee.utilisateur, motif, projet_id, projet[0] if projet else None,
         collection["id"], collection["nom"], cran))
    for ligne in lignes:
        conn.execute("INSERT INTO demande_document (demande_id, document_id, album_id, titre) "
                     "VALUES (?, ?, ?, ?)",
                     (cur.lastrowid, ligne["document_id"], ligne.get("album_id"),
                      ligne.get("titre")))
    apres = {"genre": genre, "collection_id": collection["id"],
             "documents": [ligne["document_id"] for ligne in lignes]}
    if cran is not None:
        apres["cran"] = cran
    journal.journaliser(conn, "creation", "demande", cur.lastrowid, apres=apres)
    return cur.lastrowid


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
    un album qu'aucune des collections qu'on peut exporter ne contient. COL-4 — ou à un
    album de bac à sable qui n'est pas la copie d'un document exportable du jeu."""
    album = conn.execute("SELECT pl.album_id, pl.id FROM regions r JOIN planches pl "
                         "ON pl.id = r.planche_id WHERE r.id = ?", (region_id,)).fetchone()
    if album is not None:
        _exiger_l_export_hors_bac(conn, album[0], planche_id=album[1])
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
    à qui a tous les droits, et le laisser sortir rouvrirait l'export sans titre.

    COL-4 — un album de BAC À SABLE ne sort qu'à une condition de plus, et pour toute
    portée : être la copie d'un document du jeu dont l'export est ouvert
    (`_exiger_l_export_hors_bac`, la part du dépôt). Document par document."""
    _exiger_l_export_hors_bac(conn, album_id)
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
        # COL-4 — ni dans un bac à sable, ni hors de lui : la rive d'arrivée est celle de
        # départ. Après les gardes d'écriture sur le terme (la route) ; avant celles de la
        # cible, qui ne parlent qu'à qui pourrait ranger.
        actuel = conn.execute(f"SELECT collection_id FROM {table} WHERE id = ?",
                              (oid,)).fetchone()
        _exiger_une_rive(conn, _rive_d_un_terme(conn, actuel[0] if actuel else None),
                         _rive_d_un_terme(conn, cible))
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

    COL-4 (Hugo, 2026-10-24) — deux registres. Un personnage NÉ dans un bac à sable
    (`personnages.bac_a_sable_id`) n'existe que pour les membres de ce bac à sable. Pour un
    personnage du registre, les apparitions dans un projet ISOLÉ (bac à sable, jeu) ne
    comptent pas — ni pour le cacher, ni pour le montrer : la relecture croisée avait vu un
    arrivant, en attribuant « Spirou » dans son bac à sable, le cacher à tout le monde.
    """
    if portee.tout and not portee.bornee and not portee.hors_isoles:
        return "1", []
    if portee.tout:
        ou, pp = "1", []
    else:
        ou, pp = portee.clause_album("pl.album_id")
    hors_isole = ("NOT EXISTS (SELECT 1 FROM albums _ai WHERE _ai.id = pl.album_id "
                  f"AND {sql_album_isole('_ai')})")
    apparition = (
        "EXISTS (SELECT 1 FROM {table} x "
        "          JOIN regions r   ON r.id = x.region_id "
        "          JOIN planches pl ON pl.id = r.planche_id "
        f"        WHERE x.personnage_id = p.id AND {hors_isole}{{et}})")
    apparait = apparition.replace("{et}", f" AND {ou}")
    jamais = (f"NOT {apparition.replace('{et}', '').format(table='bulle_locuteur')} "
              f"AND NOT {apparition.replace('{et}', '').format(table='personnage_presence')}")
    bacs = sorted(portee.bacs_a_sable)
    du_bac = (f"p.bac_a_sable_id IN ({', '.join('?' * len(bacs))})" if bacs else "0")
    return (f"((p.bac_a_sable_id IS NULL AND (({jamais}) "
            f" OR {apparait.format(table='bulle_locuteur')} "
            f" OR {apparait.format(table='personnage_presence')})) OR {du_bac})",
            [*pp, *pp, *bacs])


def _rive_d_un_personnage(conn, personnage_id) -> int:
    """La rive d'un personnage : le bac à sable où il est né, 0 pour le registre."""
    r = conn.execute("SELECT bac_a_sable_id FROM personnages WHERE id = ?",
                     (personnage_id,)).fetchone()
    return (r[0] or 0) if r else 0


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
    if ecriture and p["bac_a_sable_id"] is not None:
        # COL-4 (Hugo, 2026-10-24) — un personnage né dans un bac à sable se modifie par
        # les membres de ce bac à sable ; une portée totale bornée, comme un arrivant.
        if not ((portee.tout and not portee.bornee)
                or p["bac_a_sable_id"] in portee.bacs_a_sable):
            raise HTTPException(403, "Ce personnage est en lecture seule pour vous.")
    elif ecriture and not portee.peut_ecrire_quelque_part():
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
    tome: Optional[str] = None                  # rang dans la série, texte libre
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
    lieu_masters: Optional[str] = None          # IMG-1 (v34) : où vivent les masters d'archive


class AlbumUpdate(BaseModel):
    titre: Optional[str] = None
    auteur: Optional[str] = None
    annee: Optional[int] = Field(None, ge=1400, le=2200)   # mêmes bornes qu'à la création
    editeur: Optional[str] = None
    serie: Optional[str] = None
    tome: Optional[str] = None
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
    lieu_masters: Optional[str] = None          # IMG-1 (v34)


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


class OrdrePlanchesIn(BaseModel):
    """L'ordre des planches d'un album (UX-11, 2026-10-22). `ordre` : chaque planche de
    l'album, une fois, dans l'ordre voulu ; `vu` : dans l'ordre que l'écran montrait — la
    version qu'il a vue, à la manière de CONC-3, OBLIGATOIRE ici (aucun client d'avant ne
    l'ignore) ; `geste` : ce qui l'a produit, pour le journal."""
    ordre: list[int]
    vu: list[int]
    geste: Optional[Literal["monter", "descendre", "ranger_par_nom"]] = None


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
    # COL-4 (Hugo, 2026-10-24) — le BAC À SABLE où le personnage naît (`projet.id`), dont
    # l'appelant est membre ; absent, il naît au registre.
    bac_a_sable_id: Optional[int] = None


class PersonnageUpdate(BaseModel):
    nom: Optional[str] = None
    serie: Optional[str] = None
    notes: Optional[str] = None


class LocuteurIn(BaseModel):
    personnage_id: int
    # CONC-4 — le locuteur que l'écran VOYAIT : un identifiant, ou `null` pour « aucun ».
    # FACULTATIF (Q8 de CONC-3) : absent, le dernier gagne, comme avant ; présent, une base
    # qui porte autre chose répond le 409 nommé (`routes/personnages._garder_le_lien`).
    personnage_vu: Optional[int] = None


class PresenceIn(BaseModel):
    personnage_id: int   # entité montrée dans une boîte personnage (§14, brique (a))
    personnage_vu: Optional[int] = None   # CONC-4 : celui que l'écran voyait, cf. LocuteurIn


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
    """La réponse à une demande : `acceptee` ou `refusee`. `document_id` (COL-3, tranche
    3, D9) : pour une entrée de documents, la ligne à laquelle on répond ; absent, la
    réponse vaut pour toutes celles qui attendent — « tout accepter ». `album_id` (tranche
    3b, E7) : pour ACCEPTER une demande d'en partir entre deux projets, la copie source que
    choisit qui répond — une copie de SON projet, pour un responsable."""
    reponse: str
    document_id: Optional[int] = None
    album_id: Optional[int] = None


class DocumentPrisIn(BaseModel):
    """Une ligne d'une prise (COL-3, tranche 3a) : le DOCUMENT, et ce qu'on en fait —
    `zero` (une copie vierge), `rejoindre` (ranger ici une copie qu'on lit), `reprendre`
    (une copie du projet gardée au fonds). `album_id` : la copie qu'on rejoint ; pour
    `zero`, celle d'où partent les images (facultatif) ; pour `reprendre`, la copie gardée
    (facultatif). Tranche 3b — `amorcer` (en partir d'un travail qu'on lit : une copie à
    soi, amorcée jusqu'au `cran` dit, depuis la copie `album_id`, l'un et l'autre
    obligatoires)."""
    document_id: int
    reponse: str
    album_id: Optional[int] = None
    cran: Optional[str] = None


class PriseIn(BaseModel):
    """Une prise : ses documents, et le motif — exigé dès qu'une entrée se demande."""
    documents: list[DocumentPrisIn] = Field(default_factory=list)
    motif: Optional[str] = None


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
