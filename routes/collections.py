"""Collections — espaces de travail, accès et diffusion (AUTH-3, DROIT-1).

Le conteneur existe depuis la v14 comme unité de DÉPÔT ; AUTH-2 en a fait l'unité de
CLOISONNEMENT, et ce module est ce par quoi on l'administre autrement qu'en SQL à la main :
créer, partager, retirer un accès, ranger un album.

Trois paliers qui s'empilent — lire · écrire · POSSÉDER — et le troisième ne découle pas du
second : écrire c'est annoter, posséder c'est décider qui d'autre entrera. Deux états sont
refusés par un 409 qui les NOMME : zéro propriétaire sur une collection, zéro collection
pour un album.

Ce module APPLIQUE ces règles ; il ne les décide pas. `autorisation.py` reste le seul
endroit qui tranche « qui voit quoi », et le découpage n'y touche pas — sans quoi la règle
existerait à deux endroits, ce qui est la seule façon sûre de la voir diverger.

Bloc sorti de `main.py` (ARCH-1). Chemins et contrat d'API inchangés : un routeur inclus
apparaît dans `app.routes` comme une route déclarée sur `app`, ce dont dépendent les trois
cliquets du dépôt. Les imports sont CALCULÉS depuis les noms libres du bloc, jamais
recopiés à l'œil — c'est cette erreur-là qui a produit 49 tests rouges au premier bloc.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import autorisation
import journal
from config import STATUTS_DIFFUSION
from database import collection_row, collections, etat_embargo, nom_reserve

from socle import (
    AccesIn, CollectionIn, CollectionUpdate, _get_album, _rows, db, portee_courante,
)

router = APIRouter()

# Le conteneur existe depuis la v14 (unité de DÉPÔT), le cloisonnement depuis AUTH-2
# (`collection_acces`). Il manquait de quoi l'ADMINISTRER autrement qu'en SQL à la main :
# créer, partager, retirer, ranger un album. C'est tout ce chantier.
#
# Trois paliers, et le troisième est la nouveauté : lire · écrire · POSSÉDER. Écrire, c'est
# annoter ; posséder, c'est décider qui d'autre entrera. Le second ne découle pas du premier.
# =========================================================================== #
def _get_collection(conn, portee: autorisation.Portee, collection_id: int, *,
                    administrer: bool = False):
    """Collection VISIBLE (404 sinon) et, si `administrer`, qu'on a le droit de partager.

    Le refus d'administration est un **403** et non un 404 : la collection vient d'être
    listée, on connaît son nom, un « introuvable » mentirait. C'est la distinction
    qu'AUTH-2 fait déjà entre un terme (403, déjà listé) et une donnée (404, l'absence ne
    fuit rien) — ici, la collection est déjà connue de l'appelant.
    """
    c = collection_row(conn, collection_id)
    if c is None or not portee.peut_lire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    if administrer and not portee.peut_administrer(collection_id):
        raise HTTPException(403, "Seul un propriétaire de cette collection peut la "
                                 "partager ou la modifier.")
    return c


def _niveau_dans(portee: autorisation.Portee, collection_id: int):
    """Le niveau de l'APPELANT sur cette collection, pour que l'UI sache quoi proposer.

    `None` hors proxy et pour l'administrateur : ils peuvent tout, mais ne « possèdent »
    rien — afficher « propriétaire » à un administrateur lui ferait croire à un lien
    personnel avec une collection qui ne lui appartient pas.
    """
    if portee.tout:
        return None
    if collection_id in portee.propriete:
        return autorisation.PROPRIETAIRE
    if collection_id in portee.ecriture:
        return autorisation.ECRITURE
    return autorisation.LECTURE if collection_id in portee.lecture else None


def _acces_de(conn, collection_id: int) -> list[dict]:
    """Les accès accordés sur une collection, propriétaires d'abord."""
    return _rows(conn.execute(
        "SELECT genre, principal, niveau, date_creation FROM collection_acces "
        "WHERE collection_id = ? "
        "ORDER BY CASE niveau WHEN 'proprietaire' THEN 0 WHEN 'ecriture' THEN 1 ELSE 2 END, "
        "         genre, principal", (collection_id,)))


def _compte_proprietaires(conn, collection_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM collection_acces WHERE collection_id = ? AND niveau = ?",
        (collection_id, autorisation.PROPRIETAIRE)).fetchone()[0]


def _refuser_nom_reserve(nom: str) -> None:
    """Le nom du repli ne se prend pas. Cf. `database.nom_reserve` pour la raison — en
    résumé : `collection_par_defaut` désigne le repli par son NOM, et se l'attribuer capture
    les albums créés sans collection explicite."""
    if nom_reserve(nom):
        raise HTTPException(
            422, f"« {nom} » est réservé à la collection de repli : les albums créés sans "
                 "collection explicite y sont rangés. Choisissez un autre nom.")


def _journaliser_acces(conn, collection_id: int, type: str, *, avant=None, apres=None):
    """Trace un changement d'ACCÈS dans le journal A3 (append-only).

    Le journal servait jusqu'ici la provenance du CORPUS — qui a annoté quoi. Un changement
    d'accès n'est pas une annotation, mais il relève de la même exigence : `peut_administrer`
    se justifie par le fait qu'un accès accordé par erreur doit rester traçable, et sans
    trace cet argument ne tenait pas. Écart relevé en relisant ma propre justification.

    Ces événements ne sont PAS annulables : `undo._TABLES` est une liste blanche, et
    `collection_acces` n'y figure pas. Défaire un partage par Ctrl+Z serait une surprise.
    """
    journal.journaliser(conn, type, "collection_acces", collection_id,
                        avant=avant, apres=apres)


@router.get("/api/collections")
def list_collections(conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Collections (espace de travail ET unité de dépôt) + nombre d'albums + le niveau de
    l'appelant. Sert le menu « portée » du lexique, le sélecteur de la Bibliothèque et
    l'écran Collections.

    AUTH-2 — on ne liste que les siennes. C'est la route la plus directement révélatrice
    du dépôt : les noms de collections DISENT quelles études existent, et le menu de portée
    du lexique proposerait sinon de ranger un terme chez quelqu'un d'autre."""
    vues = collections(conn) if portee.tout else [
        c for c in collections(conn) if c["id"] in portee.lecture]
    for c in vues:
        c["mon_niveau"] = _niveau_dans(portee, c["id"])
        c["administrable"] = portee.peut_administrer(c["id"])
        # DROIT-1 — l'état de la date d'embargo, DÉRIVÉ ici comme il l'est à la sortie :
        # `tools/iiif_manifest.py` lit la MÊME fonction, sans quoi l'écran et l'export
        # finiraient par ne plus dire la même chose du même champ. Un embargo échu que
        # personne ne remarque garde un corpus fermé par inertie ; l'outil ne le lève pas
        # tout seul (une date qui passe ne dit pas que les droits sont acquis), mais il
        # cesse de se taire.
        c["embargo"] = etat_embargo(c)
    return vues


@router.post("/api/collections", status_code=201)
def create_collection(payload: CollectionIn, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Crée une collection ; son créateur en devient PROPRIÉTAIRE.

    AUTH-3 — cette route remplace `tools/gerer_collections.py creer`, qui exigeait un accès
    shell : ouvrir un espace de travail ne peut pas demander d'être administrateur système.
    Aucun droit préalable n'est requis, et c'est délibéré — refuser la création à qui n'a
    encore rien rendrait l'application inutilisable au premier jour de chacun.

    Hors proxy (mono-poste), il n'y a PERSONNE à inscrire comme propriétaire : la collection
    naît sans accès, et la portée totale rend la question sans objet. Idem pour un
    administrateur, qui possède déjà tout : lui inventer un lien personnel avec chaque
    collection qu'il crée fausserait la notion — s'il veut la posséder, il se l'accorde.

    « Aucun droit préalable » ne veut PAS dire « aucune identité », et la première version
    confondait les deux : derrière le proxy, une requête sans en-tête d'identité — donc qui
    n'a jamais traversé Authelia — créait des collections. C'était la seule écriture
    ouverte du dépôt, et elle contredisait la fermeture par défaut d'AUTH-2 (drapeau posé,
    identité absente ⇒ portée VIDE). Trouvé en relisant, sur une suite verte.
    """
    # Mono-poste : personne à identifier. Derrière le proxy : il FAUT une identité, sinon
    # la collection créée n'aurait aucun propriétaire possible — et l'écrire serait déjà
    # une écriture accordée à qui n'est pas passé par l'authentification.
    if not portee.tout and not portee.utilisateur:
        raise HTTPException(403, "Aucune identité ne parvient à l'application : votre "
                                 "requête n'est pas passée par l'authentification.")
    nom = (payload.nom or "").strip()
    if not nom:
        raise HTTPException(422, "Le nom de la collection est requis.")
    _refuser_nom_reserve(nom)
    cur = conn.execute("INSERT INTO collection (nom, description) VALUES (?, ?)",
                       (nom, payload.description))
    cid = cur.lastrowid
    if portee.utilisateur and not portee.admin:
        conn.execute(
            "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
            "VALUES (?, ?, ?, ?)",
            (cid, autorisation.UTILISATEUR, portee.utilisateur, autorisation.PROPRIETAIRE))
    journal.journaliser(conn, "creation", "collection", cid,
                        apres={"nom": nom, "proprietaire": portee.utilisateur})
    conn.commit()
    return {**collection_row(conn, cid), "acces": _acces_de(conn, cid)}


@router.patch("/api/collections/{collection_id}")
def update_collection(collection_id: int, payload: CollectionUpdate,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Modifie les descripteurs d'une collection (nom, description, licence, diffusion…).

    Réservé au propriétaire : ces champs sont de la métadonnée de DÉPÔT — licence, base
    légale, embargo — et les changer engage la collection entière, pas seulement le travail
    qu'on y fait.

    Deux valeurs sont contraintes : le nom de la collection de REPLI est réservé (s'y
    attribuer capturerait les albums créés sans collection explicite), et `statut_diffusion`
    est un vocabulaire contrôlé — il ne l'était que du côté de l'outil headless.
    """
    c = _get_collection(conn, portee, collection_id, administrer=True)
    fields = payload.model_dump(exclude_unset=True)
    if "nom" in fields:
        fields["nom"] = (fields["nom"] or "").strip()
        if not fields["nom"]:
            raise HTTPException(422, "Le nom de la collection est requis.")
        # Le repli, LUI, garde son nom : la garde interdit de PRENDRE ce nom, pas de le
        # conserver — sinon la collection de repli ne serait plus éditable du tout.
        if not nom_reserve(c["nom"]):
            _refuser_nom_reserve(fields["nom"])
    # `statut_diffusion` est un vocabulaire CONTRÔLÉ, et il ne l'était qu'à moitié :
    # `gerer_collections.py` le validait, cette route non. Un champ à deux portes dont une
    # seule contrôle n'est pas contrôlé — la liste est désormais partagée (config.py).
    if fields.get("statut_diffusion") and fields["statut_diffusion"] not in STATUTS_DIFFUSION:
        raise HTTPException(
            422, f"Statut de diffusion inconnu : {fields['statut_diffusion']} "
                 f"({' | '.join(STATUTS_DIFFUSION)}).")
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE collection SET {cols} WHERE id = ?",
                     (*fields.values(), collection_id))
        conn.commit()
    return collection_row(conn, collection_id)


@router.delete("/api/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une collection. Ses ALBUMS survivent (l'appartenance est N-N : le lien se
    défait, l'œuvre reste), et ses termes de vocabulaire sont PROMUS en global
    (`ON DELETE SET NULL`) plutôt que perdus.

    Refus si un album n'appartiendrait alors plus à aucune collection : l'invariant d'AUTH-2
    est qu'un album a toujours une règle d'accès. Le supprimer par ricochet fabriquerait
    exactement l'orphelin que le chantier précédent a retiré du modèle.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    isoles = [r[0] for r in conn.execute(
        "SELECT ca.album_id FROM collection_album ca WHERE ca.collection_id = ? "
        "AND NOT EXISTS (SELECT 1 FROM collection_album x WHERE x.album_id = ca.album_id "
        "                AND x.collection_id <> ca.collection_id)", (collection_id,))]
    if isoles:
        raise HTTPException(
            409, f"{len(isoles)} album(s) n'appartiennent qu'à cette collection et se "
                 "retrouveraient sans aucune règle d'accès. Rangez-les ailleurs d'abord.")
    c = collection_row(conn, collection_id)
    conn.execute("DELETE FROM collection WHERE id = ?", (collection_id,))
    journal.journaliser(conn, "suppression", "collection", collection_id,
                        avant={"nom": c["nom"]})
    conn.commit()
    return Response(status_code=204)


@router.get("/api/collections/{collection_id}/acces")
def list_acces(collection_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Qui a accès à cette collection, et à quel niveau. Réservé au propriétaire : la liste
    des membres d'une étude est une donnée sur des PERSONNES, pas sur le corpus."""
    _get_collection(conn, portee, collection_id, administrer=True)
    return _acces_de(conn, collection_id)


@router.put("/api/collections/{collection_id}/acces")
def accorder_acces(collection_id: int, payload: AccesIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Accorde (ou change) un accès. Idempotent : re-poser le même principal met à jour son
    niveau, ce qui fait de « promouvoir » et « rétrograder » le même geste.

    `principal` est un NOM — un login, ou un nom de groupe tel qu'Authelia le pose dans
    `Remote-Groups`. On n'accorde donc rien à une personne qu'on aurait vérifiée : on
    déclare qu'un nom ouvre une collection. L'application n'a aucun annuaire (invariant
    AUTH-1), et un nom mal orthographié n'ouvre simplement rien.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    if payload.genre not in autorisation.GENRES:
        raise HTTPException(422, f"Genre invalide : {payload.genre} (utilisateur | groupe).")
    if payload.niveau not in autorisation.NIVEAUX:
        raise HTTPException(
            422, f"Niveau invalide : {payload.niveau} ({' | '.join(autorisation.NIVEAUX)}).")
    principal = (payload.principal or "").strip()
    if not principal:
        raise HTTPException(422, "Le principal (login ou nom de groupe) est requis.")
    # Rétrograder le DERNIER propriétaire laisserait une collection que plus personne ne
    # peut administrer — sauf un administrateur, mais compter là-dessus est précisément le
    # SQL à la main qu'AUTH-3 supprime.
    if (payload.niveau != autorisation.PROPRIETAIRE
            and _compte_proprietaires(conn, collection_id) == 1
            and conn.execute(
                "SELECT 1 FROM collection_acces WHERE collection_id = ? AND genre = ? "
                "AND principal = ? AND niveau = ?",
                (collection_id, payload.genre, principal,
                 autorisation.PROPRIETAIRE)).fetchone()):
        raise HTTPException(409, "C'est le dernier propriétaire de cette collection : "
                                 "désignez-en un autre avant de le rétrograder.")
    avant = conn.execute(
        "SELECT niveau FROM collection_acces WHERE collection_id = ? AND genre = ? "
        "AND principal = ?", (collection_id, payload.genre, principal)).fetchone()
    conn.execute(
        "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(collection_id, genre, principal) "
        "DO UPDATE SET niveau = excluded.niveau",
        (collection_id, payload.genre, principal, payload.niveau))
    # Qui a ouvert quoi à qui, et quand. La séparation « écrire ≠ partager » se justifie
    # par la TRAÇABILITÉ d'un accès accordé par erreur — sans trace, l'argument ne tenait
    # pas. `cible_id` est la collection : `collection_acces` a une clé composite et pas
    # d'id, et c'est bien la collection dont la liste d'accès change.
    _journaliser_acces(conn, collection_id, "lien",
                       avant={"genre": payload.genre, "principal": principal,
                              "niveau": avant["niveau"]} if avant else None,
                       apres={"genre": payload.genre, "principal": principal,
                              "niveau": payload.niveau})
    conn.commit()
    return _acces_de(conn, collection_id)


@router.delete("/api/collections/{collection_id}/acces/{genre}/{principal}", status_code=204)
def retirer_acces(collection_id: int, genre: str, principal: str,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Retire un accès. Ne détruit AUCUNE donnée : les annotations faites par la personne
    restent, et le journal A3 continue de les lui attribuer — retirer un droit d'entrée
    n'efface pas ce qui a été fait, sinon le corpus perdrait sa provenance à chaque départ.

    Refus sur le dernier propriétaire : une collection sans propriétaire n'est plus
    administrable que par un administrateur, et ce chantier existe pour ne plus en dépendre.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    ligne = conn.execute(
        "SELECT niveau FROM collection_acces WHERE collection_id = ? AND genre = ? "
        "AND principal = ?", (collection_id, genre, principal)).fetchone()
    if ligne is None:
        raise HTTPException(404, "Cet accès n'existe pas.")
    if (ligne["niveau"] == autorisation.PROPRIETAIRE
            and _compte_proprietaires(conn, collection_id) == 1):
        raise HTTPException(409, "C'est le dernier propriétaire de cette collection : "
                                 "désignez-en un autre avant de le retirer.")
    conn.execute("DELETE FROM collection_acces WHERE collection_id = ? AND genre = ? "
                 "AND principal = ?", (collection_id, genre, principal))
    _journaliser_acces(conn, collection_id, "delien",
                       avant={"genre": genre, "principal": principal,
                              "niveau": ligne["niveau"]})
    conn.commit()
    return Response(status_code=204)


@router.get("/api/albums/{album_id}/collections")
def list_collections_album(album_id: int, conn: sqlite3.Connection = Depends(db),
                           portee: autorisation.Portee = Depends(portee_courante)):
    """Les collections auxquelles cet album appartient — celles qu'on VOIT seulement.

    L'appartenance est N-N depuis la v14, et c'est porteur de sens : un même album peut
    nourrir deux études. La liste est donc PARTIELLE quand l'album est partagé avec une
    étude à laquelle on ne participe pas — même compromis que les attributs d'un objet
    partagé (cf. `_attributs_de`) : mieux vaut ne pas montrer que révéler l'existence
    d'une étude voisine.
    """
    _get_album(conn, portee, album_id)
    rows = _rows(conn.execute(
        "SELECT c.id, c.nom FROM collection_album ca "
        "JOIN collection c ON c.id = ca.collection_id "
        "WHERE ca.album_id = ? ORDER BY c.nom", (album_id,)))
    return [{**c, "mon_niveau": _niveau_dans(portee, c["id"]),
             "administrable": portee.peut_administrer(c["id"])}
            for c in rows if portee.peut_lire(c["id"])]


@router.put("/api/albums/{album_id}/collections/{collection_id}", status_code=201)
def ranger_album(album_id: int, collection_id: int,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Range un album DANS une collection. Idempotent.

    Deux droits, pas un : écrire sur l'album (donc sur une collection qui le contient déjà)
    ET écrire sur la collection d'arrivée. Sans le second, on déposerait son travail dans
    l'étude de quelqu'un d'autre ; sans le premier, on s'approprierait le travail d'un
    autre en le rangeant chez soi.
    """
    _get_album(conn, portee, album_id, ecriture=True)
    if not portee.peut_ecrire(collection_id) or collection_row(conn, collection_id) is None:
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    conn.execute("INSERT OR IGNORE INTO collection_album (collection_id, album_id) "
                 "VALUES (?, ?)", (collection_id, album_id))
    conn.commit()
    return list_collections_album(album_id, conn, portee)


@router.delete("/api/albums/{album_id}/collections/{collection_id}", status_code=204)
def sortir_album(album_id: int, collection_id: int,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Sort un album d'une collection. Refus si c'était la DERNIÈRE : un album hors de
    toute collection ne correspondrait à aucune règle d'accès (invariant AUTH-2).

    Le refus est un 409 qui NOMME la contrainte, plutôt qu'un repli silencieux vers la
    collection par défaut : déplacer, c'est ranger ailleurs PUIS sortir, et l'ordre inverse
    doit se voir refuser au lieu de déverser le travail dans un seau commun.
    """
    _get_album(conn, portee, album_id, ecriture=True)
    if not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    # L'APPARTENANCE d'abord, la contrainte ensuite. Sans ce test, sortir un album d'une
    # collection dont il ne fait pas partie déclenchait le garde-fou du dessous et
    # répondait « c'est la dernière collection de cet album » — une phrase fausse, sur une
    # opération qui n'avait de toute façon rien à défaire.
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ? AND collection_id = ?",
                    (album_id, collection_id)).fetchone() is None:
        raise HTTPException(404, "Cet album n'appartient pas à cette collection.")
    if conn.execute("SELECT COUNT(*) FROM collection_album WHERE album_id = ?",
                    (album_id,)).fetchone()[0] <= 1:
        raise HTTPException(409, "C'est la dernière collection de cet album : rangez-le "
                                 "ailleurs d'abord, un album ne peut rester sans règle "
                                 "d'accès.")
    conn.execute("DELETE FROM collection_album WHERE collection_id = ? AND album_id = ?",
                 (collection_id, album_id))
    conn.commit()
    return Response(status_code=204)
