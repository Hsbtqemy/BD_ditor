"""Lexique situé — la couche définitionnelle SKOS du vocabulaire émergent (A4).

Domaines, dimensions, valeurs et tags portent tous le même patron « contrôlé-mais-ouvert » :
une `definition`, une `note_portee` (le SKOS `scopeNote`, c'est-à-dire le « situé »), un
`etat` provisoire→défini, et une collection d'appartenance. Ce module en est le read model
et l'édition, plus l'amorçage en lot depuis un tableur.

`GET /api/lexique` agrège TOUT le vocabulaire en quatre requêtes : c'est le seul endroit où
l'oubli d'un filtre de portée rendrait vain le cloisonnement des routes unitaires, puisque
le panneau Lexique passe par ici et non par elles.

Un tag s'y REMANIE aussi (ANN-8) : renommer, fusionner dans un autre, supprimer — cf. le
bloc du même nom en fin de module.

Bloc sorti de `main.py` (ARCH-1). Chemins et contrat d'API inchangés : un routeur inclus
apparaît dans `app.routes` comme une route déclarée sur `app`, ce dont dépendent les trois
cliquets du dépôt. Les imports sont CALCULÉS depuis les noms libres du bloc, jamais
recopiés à l'œil — c'est cette erreur-là qui a produit 49 tests rouges au premier bloc.
"""
from __future__ import annotations

import io
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

import autorisation
import conflit
import journal
import lexique_import
from database import annotation_vide, cle_tag, lexique_resume, reindex_tags_regions

from socle import (
    LexiqueIn, _clause_personnage, _get_dimension, _get_valeur, _patch_lexique, _row, _rows,
    db, portee_courante,
)

router = APIRouter()

@router.get("/api/lexique")
def get_lexique(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Tout le lexique situé pour l'édition : domaines + dimensions (→ valeurs) + tags, avec
    leur couche définitionnelle (definition/note_portee/etat/portée) et le nombre d'usages ;
    plus le résumé « % défini ». Read model du panneau Lexique.

    AUTH-2 — c'est le read model qui agrège TOUT le vocabulaire : quatre requêtes, quatre
    filtres, et l'oubli d'un seul rendrait vain le cloisonnement des routes unitaires
    ci-dessus, puisque le panneau Lexique passe par ici et non par elles."""
    ou_dom, p_dom = portee.clause_terme("domaine.collection_id")
    ou_dimx, p_dimx = portee.clause_terme("x.collection_id")
    ou_dim, p_dim = portee.clause_terme("d.collection_id")
    ou_val, p_val = portee.clause_terme("v.collection_id")
    ou_tag, p_tag = portee.clause_terme("t.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    ou_perso, p_perso = _clause_personnage(portee)
    domaines = _rows(conn.execute(
        f"SELECT id, nom, definition, note_portee, etat, collection_id, "
        f"       (SELECT COUNT(*) FROM attribut_dimension x "
        f"         WHERE x.domaine_id = domaine.id AND {ou_dimx}) AS nb_dimensions "
        f"FROM domaine WHERE {ou_dom} ORDER BY nom", [*p_dimx, *p_dom]))
    dims = _rows(conn.execute(
        f"SELECT d.id, d.cible, d.nom, d.domaine_id, d.definition, d.note_portee, d.etat, "
        f"       d.collection_id "
        f"FROM attribut_dimension d WHERE {ou_dim} ORDER BY d.cible, d.nom", p_dim))
    vals = _rows(conn.execute(
        f"SELECT v.id, v.dimension_id, v.valeur, v.definition, v.note_portee, v.etat, "
        f"       v.collection_id, "
        f"       ((SELECT COUNT(*) FROM personnage_attribut pa JOIN personnages p "
        f"           ON p.id = pa.personnage_id "
        f"         WHERE pa.valeur_id = v.id AND {ou_perso}) "
        f"      + (SELECT COUNT(*) FROM region_attribut ra "
        f"           JOIN regions r   ON r.id = ra.region_id "
        f"           JOIN planches pl ON pl.id = r.planche_id "
        f"         WHERE ra.valeur_id = v.id AND {ou_album})) AS nb_usages "
        f"FROM attribut_valeur v WHERE {ou_val} ORDER BY v.valeur",
        [*p_perso, *p_album, *p_val]))
    par_dim = {}
    for v in vals:
        par_dim.setdefault(v["dimension_id"], []).append(v)
    for d in dims:
        d["valeurs"] = par_dim.get(d["id"], [])
    tags = _rows(conn.execute(
        f"SELECT t.id, t.label, t.description, t.note_portee, t.etat, t.collection_id, "
        f"       (SELECT COUNT(*) FROM annotation_tags at "
        f"          JOIN annotations an ON an.id = at.annotation_id "
        f"          JOIN regions r      ON r.id = an.region_id "
        f"          JOIN planches pl    ON pl.id = r.planche_id "
        f"        WHERE at.tag_id = t.id AND {ou_album}) AS frequence "
        f"FROM tags t WHERE {ou_tag} ORDER BY t.label", [*p_album, *p_tag]))
    # ANN-8 — la question du remaniement, tag par tag : l'écran n'offre « Renommer »,
    # « Fusionner » et la suppression d'un tag porté qu'à qui le serveur répondrait oui. Ici
    # et non dans `GET /api/tags`, que lisent l'Atelier et la Recherche pour proposer et
    # compter des tags : aucune de ces surfaces ne remanie, et le panneau Lexique, qui seul
    # le fait, ne lit que cette route.
    for t in tags:
        t["remaniable"] = portee.peut_remanier_tag(t["collection_id"])
    # AUTH-2 — le résumé se filtre COMME les quatre listes ci-dessus. Il ne montrait aucun
    # terme, mais les COMPTAIT tous : « 3 définis sur 41 » à qui n'en voit que trois dit le
    # volume de vocabulaire des autres, et rend le pourcentage faux pour qui le lit.
    return {"domaines": domaines, "dimensions": dims, "tags": tags,
            "resume": lexique_resume(conn, clause=portee.clause_terme("collection_id"))}


@router.post("/api/lexique/importer")
def importer_lexique(file: UploadFile = File(...),
                     collection_id: Optional[int] = Form(None, ge=1),
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Amorçage EN LOT du vocabulaire depuis un tableur CSV (point-virgule) — bouton
    « Importer » du panneau 📖 Lexique. Même cœur et même doctrine que l'outil headless
    (pré-remplir sans écraser, idempotent ; cf. lexique_import + docs/import-vocabulaire.md).
    `collection_id` = portée d'appartenance (absent = global)."""
    # AUTH-2 — amorcer le vocabulaire est une écriture, et une écriture de PORTÉE :
    # `collection_id` range les termes chez quelqu'un. On exige donc le droit d'écrire
    # sur CETTE collection, et un simple droit d'écriture quelque part pour du global.
    if collection_id is None:
        if not portee.peut_ecrire_quelque_part():
            raise HTTPException(403, "Importer du vocabulaire demande un droit d'écriture "
                                     "sur au moins une collection.")
    elif not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    if collection_id is not None and conn.execute(
            "SELECT 1 FROM collection WHERE id = ?", (collection_id,)).fetchone() is None:
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Fichier vide")
    try:
        texte = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Le fichier doit être encodé en UTF-8.")
    try:
        lignes, anomalies = lexique_import.lire(io.StringIO(texte))
    except lexique_import.FormatInvalide as e:
        raise HTTPException(400, str(e))
    # AUTH-11 — l'import RÉUTILISE des termes existants, et peut écrire sur eux : sa portée
    # descend jusqu'au cœur, qui refuse toute ligne nommant un terme qu'on ne voit pas
    # (comptée comme « libellé pris », sans rien en dire) ou qui ÉCRIRAIT sur un terme
    # qu'on ne peut pas modifier (cf. `lexique_import._refus`). Le verrou d'écriture est
    # pris avant la première lecture et tient jusqu'au `commit` ci-dessous : sans lui, un
    # `PATCH …/lexique` concurrent pourrait rendre illisible, entre la lecture et
    # l'écriture, un terme que la garde vient de juger visible.
    conflit.verrouiller(conn)
    res, avert = lexique_import.importer(conn, lignes, collection_id, portee=portee)
    conn.commit()
    return {"resume": res, "lignes": len(lignes),
            "anomalies": anomalies, "avertissements": avert}


@router.patch("/api/attributs/dimensions/{dim_id}/lexique")
def patch_dimension_lexique(dim_id: int, payload: LexiqueIn,
                            conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Documente une dimension : définition + note de portée + état + portée d'appartenance.

    AUTH-11 (2026-09-25) — le verrou d'écriture (`conflit.verrouiller`) est pris avant toute
    lecture : les gardes du rangement (termes liés, emport de la branche) et l'écriture
    voient le même état. Sans lui, une dimension créée entre la garde et l'UPDATE, dans
    l'ancienne collection d'un domaine qu'on range, restait derrière lui (mesuré par la
    relecture) — et l'argument « les droits des emportés sont ceux de la racine » en
    dépend aussi."""
    conflit.verrouiller(conn)
    _get_dimension(conn, portee, dim_id, ecriture=True)
    promus = _patch_lexique(conn, "attribut_dimension", dim_id, payload, portee)
    return {**_row(conn.execute("SELECT * FROM attribut_dimension WHERE id = ?", (dim_id,))),
            "promus": promus}


@router.patch("/api/attributs/valeurs/{val_id}/lexique")
def patch_valeur_lexique(val_id: int, payload: LexiqueIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Documente une valeur canonique (même couche définitionnelle).

    AUTH-11 (2026-09-25) — le verrou d'écriture (`conflit.verrouiller`) est pris avant toute
    lecture : les gardes du rangement (termes liés, emport de la branche) et l'écriture
    voient le même état. Sans lui, une dimension créée entre la garde et l'UPDATE, dans
    l'ancienne collection d'un domaine qu'on range, restait derrière lui (mesuré par la
    relecture) — et l'argument « les droits des emportés sont ceux de la racine » en
    dépend aussi."""
    conflit.verrouiller(conn)
    _get_valeur(conn, portee, val_id, ecriture=True)
    promus = _patch_lexique(conn, "attribut_valeur", val_id, payload, portee)
    return {**_row(conn.execute("SELECT * FROM attribut_valeur WHERE id = ?", (val_id,))),
            "promus": promus}


@router.patch("/api/tags/{tag_id}/lexique")
def patch_tag_lexique(tag_id: int, payload: LexiqueIn,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Documente un tag : sa `description` EST la définition SKOS ; + note de portée, état,
    portée d'appartenance (même patron que le vocabulaire facetté).

    AUTH-11 (2026-09-25) — le verrou d'écriture (`conflit.verrouiller`) est pris avant toute
    lecture : les gardes du rangement (termes liés, emport de la branche) et l'écriture
    voient le même état. Sans lui, une dimension créée entre la garde et l'UPDATE, dans
    l'ancienne collection d'un domaine qu'on range, restait derrière lui (mesuré par la
    relecture) — et l'argument « les droits des emportés sont ceux de la racine » en
    dépend aussi."""
    conflit.verrouiller(conn)
    ou, params = portee.clause_terme("t.collection_id")
    tag = _row(conn.execute(f"SELECT * FROM tags t WHERE t.id = ? AND {ou}",
                            (tag_id, *params)))
    if tag is None:
        raise HTTPException(404, f"Tag {tag_id} introuvable")
    if not portee.peut_ecrire_terme(tag.get("collection_id")):
        raise HTTPException(403, "Ce tag est en lecture seule pour vous.")
    promus = _patch_lexique(conn, "tags", tag_id, payload, portee,
                            col_definition="description")
    return {**_row(conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,))),
            "promus": promus}


# --------------------------------------------------------------------------- #
# Remanier un tag : supprimer, fusionner, renommer (ANN-8, Hugo, 2026-10-22)
# --------------------------------------------------------------------------- #
# Un tag tapé de travers restait dans le vocabulaire à fréquence 0, et dans les
# propositions de l'Atelier : aucune route ne le supprimait, ne le fusionnait ni ne le
# renommait. Trois gestes, et DEUX questions d'autorisation :
#
#   · supprimer ou renommer un tag que plus AUCUNE région ne porte — sur TOUT le corpus,
#     pas sur ce qu'on lit — est l'affaire de qui le modifie déjà (`peut_ecrire_terme`) :
#     rien de ce que d'autres ont posé ne change (le renommage : décision de la session de
#     pilotage du 2026-10-22, après la relecture croisée) ;
#   · le supprimer ou le renommer quand des régions le portent, le fusionner, c'est le
#     REMANIER (`peut_remanier_tag`) : tag local, le propriétaire de sa collection et
#     l'administrateur ; tag global, l'administrateur seul.
#
# Un tag qu'on ne voit pas répond 404 ; un tag qu'on voit sans pouvoir le faire, un 403
# qui nomme le geste et à qui il revient (VOIR n'est pas CHANGER).
#
# **Un tag local peut être posé HORS de sa collection** (constaté le 2026-10-22, en lisant
# `socle._ensure_tags`) : qui lit la collection A du tag et écrit dans un album de B l'y
# attache, puisqu'il le lit ; un tag rendu local après avoir servi partout, ou un album
# retiré de A, laissent de même le tag sur des régions que le propriétaire de A ne lit
# pas. Retirer le tag de ces régions, c'est écrire là où il n'écrit pas : hors d'une portée
# totale, retirer et fusionner exigent donc que TOUTES les régions qui portent le tag soient
# dans des albums où l'appelant écrit (`_exiger_tout_ecrit`), et se refusent sinon par un
# 403 qui le dit. Ce refus apprend au propriétaire que son tag sert ailleurs, sans dire où
# ni combien — un bit, le même que le 403 d'un tag qu'on croit inutilisé ; c'est une limite
# ÉCRITE, la seule alternative étant d'écrire hors de sa portée. Le renommage n'y est pas
# soumis : il change le TERME, qui est à lui, et pas les régions, qui le désignent par son
# identifiant. Une fusion montre, elle, quelque chose de plus : fusionner dans un tag
# GLOBAL un tag local posé hors de sa collection montre aux lecteurs de ces régions qu'un
# tag y était posé (c'est désormais la cible, lisible de tous) — l'emplacement, jamais
# l'ancien libellé.
#
# **Le nombre annoncé avant de confirmer** vient de la même route jouée à blanc (`a_blanc`),
# APRÈS toutes ses gardes : il compte tout le corpus, et ne parvient donc à une portée non
# totale que lorsque toutes les régions comptées sont dans des albums où elle écrit — donc
# qu'elle lit. Il ne révèle rien de ce qu'on ne lit pas.
#
# **L'index plein texte** agrège les libellés des tags d'une région (`tags_concat`) : toute
# région dont les tags changent — ou dont un tag change de libellé — voit ses TAGS réécrits
# dans la même transaction (`database.reindex_tags_regions`), sans analyse de langue : le
# texte et la note ne changent pas, ni donc les lemmes et les tokens. La réindexation
# complète tenait le verrou 14,7 s pour 1 500 régions (relecture croisée, 2026-10-22).
#
# **Le journal** garde chaque geste sous la cible `tags` (identifiants et libellés), RETENUE
# de toute sortie et hors de Ctrl+Z (`undo._TABLES` ne la connaît pas) : remanier le
# vocabulaire n'est pas un geste d'annotation, et le défaire région par région rendrait à
# chacune un tag qui n'existe plus.
class TagFusionIn(BaseModel):
    cible_id: int            # le tag qui RESTE
    a_blanc: bool = False    # compter sans rien écrire : le nombre dit avant de confirmer


class TagLibelleIn(BaseModel):
    label: str


_COLONNES_TAG = "id, label, couleur, description, note_portee, etat, collection_id"


def _tag_vu(conn, portee, tag_id: int, quoi: str = "Tag") -> dict:
    """Le tag, s'il est visible (`clause_terme`) ; 404 sinon, qu'il existe ou non."""
    ou, params = portee.clause_terme("t.collection_id")
    tag = _row(conn.execute(f"SELECT {_COLONNES_TAG} FROM tags t WHERE t.id = ? AND {ou}",
                            (tag_id, *params)))
    if tag is None:
        raise HTTPException(404, f"{quoi} {tag_id} introuvable")
    return tag


def _regions_du_tag(conn, tag_id: int) -> list[int]:
    """Les régions qui portent ce tag, sur TOUT le corpus — lues ou non. Une annotation par
    région (`annotations.region_id` UNIQUE) : c'est aussi le nombre d'annotations."""
    return [r["region_id"] for r in conn.execute(
        "SELECT an.region_id FROM annotation_tags at "
        "JOIN annotations an ON an.id = at.annotation_id "
        "WHERE at.tag_id = ? ORDER BY an.region_id", (tag_id,))]


def _exiger_remaniement(portee, tag: dict, local: str, global_: str) -> None:
    """Les deux gardes d'un remaniement, dans l'ordre : modifier le terme, puis le remanier.
    `local` / `global_` : la phrase du refus selon la portée du tag — elle nomme le geste et
    à qui il revient, rien de plus."""
    if not portee.peut_ecrire_terme(tag["collection_id"]):
        raise HTTPException(403, "Ce tag est en lecture seule pour vous.")
    if not portee.peut_remanier_tag(tag["collection_id"]):
        raise HTTPException(403, global_ if tag["collection_id"] is None else local)


def _exiger_tout_ecrit(conn, portee, tag_id: int, geste: str) -> None:
    """Hors d'une portée totale, toutes les régions qui portent le tag doivent être dans
    des albums où l'on ÉCRIT (cf. l'en-tête du bloc). Le refus ne dit ni où ni combien."""
    if portee.tout:
        return
    ou, params = portee.clause_album("pl.album_id", ecriture=True)
    if conn.execute(
            f"SELECT 1 FROM annotation_tags at "
            f"JOIN annotations an ON an.id = at.annotation_id "
            f"JOIN regions r      ON r.id = an.region_id "
            f"JOIN planches pl    ON pl.id = r.planche_id "
            f"WHERE at.tag_id = ? AND NOT ({ou}) LIMIT 1", (tag_id, *params)).fetchone():
        raise HTTPException(403, "Ce tag est aussi posé dans des albums où vous n'écrivez "
                                 f"pas : seul un administrateur peut le {geste} partout.")


@router.delete("/api/tags/{tag_id}")
def supprimer_tag(tag_id: int, a_blanc: bool = False,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un tag. S'il est encore posé, il quitte d'abord toutes les régions qui le
    portent — et c'est alors un REMANIEMENT (cf. l'en-tête du bloc). `a_blanc` : passe les
    mêmes gardes, compte, n'écrit rien ; la réponse dit le nombre de régions que la
    suppression toucherait.

    Une annotation à qui il ne reste ni note ni tag est supprimée, par la règle de
    `put_annotation` (`database.annotation_vide`)."""
    if not a_blanc:
        conflit.verrouiller(conn)      # le tag et ses emplois se lisent sous le verrou
    tag = _tag_vu(conn, portee, tag_id)
    if not portee.peut_ecrire_terme(tag["collection_id"]):
        raise HTTPException(403, "Ce tag est en lecture seule pour vous.")
    regions = _regions_du_tag(conn, tag_id)
    if regions:
        _exiger_remaniement(
            portee, tag,
            local="Ce tag est posé sur des régions : le supprimer revient au propriétaire "
                  "de sa collection ou à un administrateur.",
            global_="Ce tag est posé sur des régions : supprimer un tag global revient à "
                    "un administrateur.")
        _exiger_tout_ecrit(conn, portee, tag_id, "retirer")
    reponse = {"id": tag_id, "label": tag["label"], "regions": len(regions)}
    if a_blanc:
        return reponse
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))   # CASCADE : annotation_tags
    videes = [r["region_id"] for r in conn.execute(
        "SELECT an.region_id, an.note, "
        "       (SELECT COUNT(*) FROM annotation_tags at WHERE at.annotation_id = an.id) AS n "
        f"FROM annotations an WHERE an.region_id IN ({','.join('?' * len(regions))})",
        regions) if annotation_vide(r["note"], r["n"])] if regions else []
    if videes:
        conn.execute(f"DELETE FROM annotations WHERE region_id IN "
                     f"({','.join('?' * len(videes))})", videes)
    reindex_tags_regions(conn, regions)
    avant = {**tag, "regions": regions}
    if videes:
        avant["annotations_supprimees"] = videes
    journal.journaliser(conn, "suppression", "tags", tag_id, avant=avant)
    conn.commit()
    return reponse


@router.post("/api/tags/{tag_id}/fusion")
def fusionner_tag(tag_id: int, payload: TagFusionIn,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Fusionne le tag `tag_id` DANS `cible_id` : chaque annotation qui portait le premier
    porte le second — une seule fois si elle le portait déjà —, puis le premier disparaît.
    La cible garde son libellé, sa définition et sa portée. `a_blanc` : mêmes gardes, rien
    d'écrit ; `regions` dit combien de régions la fusion toucherait, `deja` combien d'entre
    elles portent déjà la cible.

    **La cible doit être au moins aussi visible que le tag fusionné** : globale, ou de la
    même collection. Fusionner un tag global dans un tag local, ou un tag de A dans un tag
    de B, le CACHERAIT à qui lisait les régions sans lire la collection de la cible — la
    règle « un terme n'est jamais plus GLOBAL que celui dont il dépend » vue de l'autre
    côté. Refusé par un 409 qui le dit, sous toute portée : c'est une propriété des données,
    pas un droit. Rendre la cible globale d'abord (Portée → Global) lève le refus."""
    if payload.cible_id == tag_id:
        raise HTTPException(422, "Un tag ne peut pas être fusionné dans lui-même.")
    if not payload.a_blanc:
        conflit.verrouiller(conn)
    tag = _tag_vu(conn, portee, tag_id)
    cible = _tag_vu(conn, portee, payload.cible_id, quoi="Tag cible")
    _exiger_remaniement(
        portee, tag,
        local="Fusionner ce tag revient au propriétaire de sa collection ou à un "
              "administrateur.",
        global_="Fusionner un tag global revient à un administrateur.")
    if cible["collection_id"] is not None and cible["collection_id"] != tag["collection_id"]:
        raise HTTPException(409, f"Fusionner « {tag['label']} » dans « {cible['label']} » "
                                 "le cacherait à qui ne lit pas la collection de "
                                 f"« {cible['label']} » : choisissez un tag global ou de "
                                 "la même collection.")
    _exiger_tout_ecrit(conn, portee, tag_id, "fusionner")
    regions = _regions_du_tag(conn, tag_id)
    deja = set(_regions_du_tag(conn, payload.cible_id)) & set(regions)
    reponse = {"id": tag_id, "label": tag["label"],
               "cible": {"id": cible["id"], "label": cible["label"]},
               "regions": len(regions), "deja": len(deja)}
    if payload.a_blanc:
        return reponse
    conn.execute("INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
                 "SELECT annotation_id, ? FROM annotation_tags WHERE tag_id = ?",
                 (payload.cible_id, tag_id))
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))   # CASCADE : annotation_tags
    reindex_tags_regions(conn, regions)
    journal.journaliser(conn, "fusion", "tags", tag_id, avant={**tag, "regions": regions},
                        apres={"cible_id": cible["id"], "label": cible["label"],
                               "regions": regions, "deja": sorted(deja)})
    conn.commit()
    return reponse


@router.put("/api/tags/{tag_id}")
def renommer_tag(tag_id: int, payload: TagLibelleIn,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme un tag sur place : les régions le désignent par son identifiant, elles
    suivent. Le libellé s'écrit sous sa CLÉ (`database.cle_tag`), comme un tag neuf.

    Un tag que plus aucune région ne porte, sur tout le corpus, se renomme par qui le
    modifie (`peut_ecrire_terme`), comme il se supprime ; un tag posé, par qui le remanie.

    Un AUTRE tag de même clé rend le renommage impossible — deux lignes pour un même mot,
    l'état que la clé existe pour éviter : c'est une fusion, et le 409 le dit en nommant ce
    tag s'il est visible. Un tag qu'on ne lit pas n'est pas nommé : « déjà pris », la phrase
    et le bit de `POST /api/tags`. Renommer un tag d'avant vers sa propre clé (« c’est » →
    « c'est ») est permis : c'est le même tag."""
    if not cle_tag(payload.label):
        raise HTTPException(422, "Libellé de tag vide.")
    conflit.verrouiller(conn)
    tag = _tag_vu(conn, portee, tag_id)
    if not portee.peut_ecrire_terme(tag["collection_id"]):
        raise HTTPException(403, "Ce tag est en lecture seule pour vous.")
    regions = _regions_du_tag(conn, tag_id)
    if regions:
        _exiger_remaniement(
            portee, tag,
            local="Ce tag est posé sur des régions : le renommer revient au propriétaire "
                  "de sa collection ou à un administrateur.",
            global_="Ce tag est posé sur des régions : renommer un tag global revient à "
                    "un administrateur.")
    label = cle_tag(payload.label)
    autre = _row(conn.execute(
        "SELECT id, label FROM tags WHERE cle_tag(label) = ? AND id <> ? "
        "ORDER BY (label = ?) DESC, id LIMIT 1", (label, tag_id, label)))
    if autre is not None:
        ou, params = portee.clause_terme("t.collection_id")
        if conn.execute(f"SELECT 1 FROM tags t WHERE t.id = ? AND {ou}",
                        (autre["id"], *params)).fetchone() is None:
            raise HTTPException(409, "Ce libellé de tag est déjà pris : choisissez-en un "
                                     "autre.")
        raise HTTPException(409, f"Le tag « {autre['label']} » porte déjà ce libellé : "
                                 "c'est une fusion — fusionnez ce tag dans "
                                 f"« {autre['label']} ».")
    if label != tag["label"]:
        conn.execute("UPDATE tags SET label = ? WHERE id = ?", (label, tag_id))
        reindex_tags_regions(conn, regions)
        journal.journaliser(conn, "modification", "tags", tag_id,
                            avant={"id": tag_id, "label": tag["label"]},
                            apres={"id": tag_id, "label": label})
    conn.commit()
    return _tag_vu(conn, portee, tag_id)
