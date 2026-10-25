"""Projets — l'étage au-dessus des collections (COL-3, tranche 1).

Un PROJET est le périmètre à l'intérieur duquel un travail pourra se partager ; une
collection appartient à UN projet. Le projet EXISTE et se RÈGLE ; ce module ne lit ni
n'écrit aucune donnée du corpus. Entrer dans un projet n'ouvre aucune de ses collections —
chacune garde son « Qui entre », dans `routes/collections.py` —, à une exception près depuis
la tranche 3 (D10, Hugo, 2026-10-17) : sa collection de BASE, née avec lui, dont ses
responsables sont propriétaires et où ses membres entrent au niveau que le projet a choisi.
Ce module la crée et en règle la position ; `autorisation.Portee` en dérive les droits.

Deux pouvoirs, et le second ne découle pas du premier — c'est la séparation d'AUTH-3, un
étage plus haut. DÉCIDER quels projets existent (créer, renommer, supprimer) revient à une
portée totale : l'administrateur, et le mono-poste. RÉGLER qui est d'un projet (faire
entrer, faire sortir, nommer un autre responsable) revient à son responsable, et à
l'administrateur qui passe outre. Quatre refus sont des 409 qui se NOMMENT : supprimer le
projet de repli, supprimer un projet qui porte encore une collection ou dont une copie est
gardée au fonds, retirer ou rétrograder son DERNIER responsable. Un projet peut en revanche
naître sans responsable : seule une portée totale le règle alors. Son responsable, qui ne
le supprime pas, DEMANDE sa suppression (`routes/fonds.py`, COL-3, tranche 2).

Ce module APPLIQUE ces règles ; `autorisation.py` les tranche (`clause_projet`,
`peut_gerer_projet`, `peut_decider_des_projets`).

**Une route de ce domaine vit ailleurs, et c'est voulu** : `GET …/membres/choix`, qui lit
l'annuaire pour proposer des groupes, est dans `routes/collections.py`. Les routes qui
lisent l'annuaire tiennent dans UN module, et un test le verrouille par égalité
(`tests/test_annuaire.py`) : en ouvrir un second ici aurait demandé de desserrer cette
garde pour un rangement.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import autorisation
import journal
from database import (DEMANDE_SUPPRESSION_PROJET, LONGUEUR_NOM_PROJET,
                      collection_de_base,
                      creer_collection_de_base, nom_de_projet_reserve, noms_lisibles,
                      sql_est_jeu, sql_projet_de)

from socle import (
    AccesMembresIn, CreationCollectionsIn, MembreIn, ProjetIn, ProjetUpdate,
    _bac_a_sable_de, _get_projet, _refuser_le_jeu, _rows, _sortir_du_bac,
    _supprimer_projet, db,
    portee_courante,
)

router = APIRouter()


_MOTIF_DECIDER = ("Créer, renommer ou supprimer un projet est réservé aux administrateurs "
                  "de l'instance.")


def _exiger_de_decider(portee: autorisation.Portee) -> None:
    """403 nommé à qui ne décide pas des projets. Un 403 et non un 404 : il parle du droit
    de l'appelant, pas d'un projet — rien n'en fuit."""
    if not portee.peut_decider_des_projets():
        raise HTTPException(403, _MOTIF_DECIDER)


def _role_dans(portee: autorisation.Portee, projet_id: int):
    """Le rôle de l'APPELANT dans ce projet. `None` pour une portée totale — même raison
    que `mon_niveau` : elle règle tout sans figurer nulle part — et pour qui ne voit le
    projet que par une collection qu'il lit. COL-4 — dans un bac à sable, une portée totale
    bornée a le rôle d'un arrivant (`Portee.couvre_projet`)."""
    if portee.couvre_projet(projet_id):
        return None
    if projet_id in portee.projets_geres:
        return autorisation.RESPONSABLE
    return autorisation.MEMBRE if projet_id in portee.projets else None


def _vue(conn, portee: autorisation.Portee, p: dict) -> dict:
    """Ce qu'on REND d'un projet — le seul endroit où sa ligne devient une réponse.

    `justification` n'y entre QUE pour qui gère le projet (responsable, administrateur) :
    elle dit pourquoi le projet existe, à ceux qui en répondent. Un simple membre, et qui
    ne voit le projet que par une collection, ne reçoivent pas la clé du tout — une clé à
    `null` ne se distinguerait pas d'une justification jamais écrite.

    `nb_collections` compte les collections LUES par l'appelant, pas celles du projet :
    le total dirait à un membre combien d'études existent hors de sa portée, ce que
    « 404, jamais 403 » existe pour ne pas dire."""
    gerable = portee.peut_gerer_projet(p["id"])
    # COL-4 — dans un bac à sable, seul son propriétaire le règle (`_exiger_le_proprietaire`),
    # une portée totale comprise : `gerable` le dit, pour que l'écran n'offre pas un geste
    # que le serveur refuserait.
    if p.get("bac_a_sable_de") is not None:
        gerable = bool(portee.utilisateur) and portee.utilisateur == p["bac_a_sable_de"]
    ids = [r[0] for r in conn.execute(
        f"SELECT c.id FROM collection c WHERE {sql_projet_de('c')} = ?", (p["id"],))]
    vue = {"id": p["id"], "nom": p["nom"], "description": p["description"],
           "repli": bool(p["repli"]), "date_creation": p["date_creation"],
           "mon_role": _role_dans(portee, p["id"]), "gerable": gerable,
           "nb_collections": sum(1 for i in ids if portee.peut_lire(i)),
           # v36 (COL-3, tranche 3b) — la question, posée au serveur projet par projet :
           # l'appelant peut-il y CRÉER une collection (`Portee.peut_creer_collection`) ?
           # L'écran n'offre « + Créer une collection » que là ; il ne le déduit pas du rôle,
           # le réglage du projet en décide pour un membre.
           "collection_creable": portee.peut_creer_collection(
               p["id"], membres_creent=bool(p.get("membres_creent_collections")),
               bac_a_sable=p.get("bac_a_sable_de") is not None)}
    if p.get("bac_a_sable_de") is not None:
        vue.update(_vue_du_bac(portee, p))
    elif not vue["collection_creable"] and vue["mon_role"] == autorisation.MEMBRE:
        # Écran de la 3b (Hugo, sur maquette, 2026-10-25) — « + Créer une collection » reste
        # à sa place, ÉTEINT, et dit au survol que seuls les responsables en créent dans ce
        # projet, EN LES NOMMANT. Les noms des RESPONSABLES, donc, au seul MEMBRE que le
        # réglage n'autorise pas — celui qui lit le bouton éteint : ni à qui crée, ni à qui ne
        # voit le projet que par une collection. Le nom lisible d'un login (le miroir
        # `utilisateur`), le login sinon ; un groupe responsable par son nom. Rien d'autre :
        # ni les membres, ni les rôles.
        vue["responsables"] = _noms_des_responsables(conn, p["id"])
    if gerable:
        vue["justification"] = p["justification"]
        # COL-3, tranche 2 — la demande de suppression qui attend, pour qui gère : sans
        # elle, un second responsable redéposerait la même et recevrait un 409. Ni nom ni
        # motif ici — la liste des projets ne nomme personne ; qui a demandé et pourquoi se
        # lisent dans le fonds, par qui y répond.
        d = conn.execute("SELECT id, date_creation FROM demande WHERE genre = ? "
                         "AND projet_id = ? AND reponse IS NULL ORDER BY id LIMIT 1",
                         (DEMANDE_SUPPRESSION_PROJET, p["id"])).fetchone()
        vue["demande_suppression"] = None if d is None else dict(d)
        # COL-3 — un FAIT, pour qui gère, et seulement lui : le projet n'a aucun responsable.
        # La liste de l'Administration l'affiche ; sans lui, elle aurait dû lire les membres
        # de chaque projet, une requête par ligne. Un booléen ne nomme personne, et un
        # simple membre ne le reçoit pas plus que la justification.
        vue["sans_responsable"] = _compte_responsables(conn, p["id"]) == 0
        # COL-3, écran de la 3a — « Ce que la base ouvre aux membres », dans la fiche : la
        # collection de base et la position choisie (`acces_membres`), et le nombre
        # d'ENTRÉES du projet qui ne sont pas responsables (`nb_membres`), que la phrase
        # dite avant d'ouvrir annonce. Pour qui gère, comme le reste : c'est lui qui la
        # règle (`PUT …/acces-membres`). `base` vaut `None` pour un projet sans base (une
        # base retouchée à la main).
        b = collection_de_base(conn, p["id"])
        ligne = None if b is None else conn.execute(
            "SELECT id, nom, acces_membres FROM collection WHERE id = ?", (b,)).fetchone()
        vue["base"] = None if ligne is None else {
            "id": ligne["id"], "nom": ligne["nom"], "acces_membres": ligne["acces_membres"]}
        # v36 — le RÉGLAGE, pour qui le règle : les membres peuvent-ils créer des
        # collections ? (`PUT …/creation-de-collections`). Un membre lit la réponse qui le
        # concerne dans `collection_creable`, pas le réglage lui-même.
        vue["membres_creent_collections"] = bool(p.get("membres_creent_collections"))
        vue["nb_membres"] = conn.execute(
            "SELECT COUNT(*) FROM projet_acces WHERE projet_id = ? AND role <> ?",
            (p["id"], autorisation.RESPONSABLE)).fetchone()[0]
    return vue


# COL-4 — ce que la bande affiche d'un bac à sable : « Mon bac à sable » à son propriétaire,
# « Bac · <login> » à qui y est invité, borné au plafond des noms de projet — un login long se
# coupe ICI, jamais à l'écran (la mesure de `LONGUEUR_NOM_PROJET`). Le préfixe court est celui
# de la maquette (Hugo, 2026-10-24) : six caractères, un login de quinze tient entier ; la
# ligne du bac à sable, sous la bande, dit le login sans coupe (« Bac à sable de <login> »).
NOM_AFFICHE_MIEN = "Mon bac à sable"
PREFIXE_AFFICHE_INVITE = "Bac · "


def _vue_du_bac(portee: autorisation.Portee, p: dict) -> dict:
    """Ce qu'un bac à sable ajoute à sa ligne : `nom` devient le nom AFFICHÉ, et
    `bac_a_sable` dit s'il est le mien, sa date d'effacement, et — à qui n'est pas son
    propriétaire, c'est-à-dire à un invité ou à une portée totale — le LOGIN de son
    propriétaire : on lit de qui est le bac à sable où l'on travaille. Personne d'autre ne
    voit un bac à sable dans cette liste."""
    mien = bool(portee.utilisateur) and portee.utilisateur == p["bac_a_sable_de"]
    bac = {"mien": mien, "efface_le": p["efface_le"]}
    if mien:
        nom = NOM_AFFICHE_MIEN
    else:
        bac["proprietaire"] = p["bac_a_sable_de"]
        nom = f"{PREFIXE_AFFICHE_INVITE}{p['bac_a_sable_de']}"[:LONGUEUR_NOM_PROJET]
    return {"nom": nom, "bac_a_sable": bac}


def _exiger_le_proprietaire(conn, portee: autorisation.Portee, projet_id: int) -> str | None:
    """Dans un bac à sable, régler qui y entre (et ce que sa base leur ouvre) revient à son
    PROPRIÉTAIRE seul — une portée totale n'y ouvre rien de plus (Hugo, 2026-10-22). 403
    nommé sinon. Rend le login du propriétaire, None hors d'un bac à sable."""
    _pid, proprietaire = _bac_a_sable_de(conn, projet_id=projet_id)
    if proprietaire is not None and portee.utilisateur != proprietaire:
        raise HTTPException(403, "Dans un bac à sable, c'est son propriétaire qui fait entrer "
                                 "qui il veut.")
    return proprietaire


def _nom_valide(conn, nom, *, sauf: int | None = None) -> str:
    """Le nom d'un projet, nettoyé, ou le refus qui dit pourquoi.

    Il est BORNÉ, et court (`database.LONGUEUR_NOM_PROJET`) : il se lit dans la bande du
    haut de chaque page, où il ne doit ni se couper ni pousser le reste hors de la
    fenêtre. Et il est UNIQUE sans égard à la casse, tenu ici plutôt que par un `UNIQUE`
    en base, qui laisserait passer « Émotions » à côté d'« émotions »."""
    nom = (nom or "").strip()
    if not nom:
        raise HTTPException(422, "Le nom du projet est requis.")
    if len(nom) > LONGUEUR_NOM_PROJET:
        raise HTTPException(
            422, f"Le nom d'un projet tient en {LONGUEUR_NOM_PROJET} caractères au plus "
                 f"(« {nom} » en fait {len(nom)}) : il se lit en haut de chaque page, où "
                 "il ne doit pas se couper.")
    # COL-4 — les noms des natures de projet (bac à sable, jeu) ne se prennent pas, en
    # préfixe : un projet « Bac à sable de Léa » serait pris pour le sien. Et l'unicité ne
    # se compare qu'aux projets ORDINAIRES — soixante-quinze bacs à sable portent le même nom.
    if nom_de_projet_reserve(nom):
        raise HTTPException(409, f"« {nom} » est réservé aux bacs à sable et à leur jeu : "
                                 "choisissez un autre nom.")
    for r in conn.execute("SELECT id, nom FROM projet "
                          "WHERE bac_a_sable_de IS NULL AND jeu = 0"):
        if r["id"] != sauf and r["nom"].strip().casefold() == nom.casefold():
            raise HTTPException(409, f"Un projet s'appelle déjà « {r['nom']} ».")
    return nom


def _membres_de(conn, projet_id: int, *, sans_signal: bool = False) -> list[dict]:
    """Les membres d'un projet, responsables d'abord. Le jumeau de `_acces_de`.

    `jamais_vu` RAPPORTE et n'explique rien : un login absent du miroir `utilisateur` est
    une faute de frappe ou un arrivant qui n'est pas encore venu, et rien ne les
    départage. `None` pour un groupe, jamais `False` — l'application ne sait d'un groupe
    que ce que le portail transmet pour la personne qui frappe."""
    lignes = _rows(conn.execute(
        "SELECT genre, principal, role, date_creation FROM projet_acces "
        "WHERE projet_id = ? ORDER BY CASE role WHEN ? THEN 0 ELSE 1 END, genre, principal",
        (projet_id, autorisation.RESPONSABLE)))
    logins = sorted({m["principal"] for m in lignes
                     if m["genre"] == autorisation.UTILISATEUR})
    connus = set()
    if logins:
        qm = ",".join("?" * len(logins))
        connus = {r[0] for r in conn.execute(
            f"SELECT login FROM utilisateur WHERE login IN ({qm})", logins)}
    for m in lignes:
        m["jamais_vu"] = (m["principal"] not in connus
                          if m["genre"] == autorisation.UTILISATEUR else None)
        if sans_signal:
            # COL-4 (S2) — dans un bac à sable, le miroir `utilisateur` ne dit pas si un
            # login tapé est venu : l'oracle d'existence fermé le 2026-09-18 pour les
            # propriétaires se rouvrirait pour chaque arrivant.
            m.pop("jamais_vu")
    return lignes


def _noms_des_responsables(conn, projet_id: int) -> list[str]:
    """Les responsables d'un projet, tels qu'un écran les NOMME : le nom lisible d'un login
    (`utilisateur.nom`), le login sinon ; un groupe, « groupe <nom> ». Dans l'ordre des
    principaux."""
    lignes = conn.execute(
        "SELECT genre, principal FROM projet_acces WHERE projet_id = ? AND role = ? "
        "ORDER BY genre DESC, principal", (projet_id, autorisation.RESPONSABLE)).fetchall()
    noms = noms_lisibles(conn, [r["principal"] for r in lignes
                                if r["genre"] == autorisation.UTILISATEUR])
    return [noms.get(r["principal"]) or r["principal"] if r["genre"] == autorisation.UTILISATEUR
            else f"groupe {r['principal']}" for r in lignes]


def _compte_responsables(conn, projet_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM projet_acces WHERE projet_id = ? AND role = ?",
        (projet_id, autorisation.RESPONSABLE)).fetchone()[0]


def _position_valide(niveau) -> str | None:
    """La position des membres dans la collection de base, ou le refus qui dit laquelle
    est possible. `None` est une valeur : la base protégée."""
    if niveau is not None and niveau not in autorisation.ACCES_MEMBRES:
        raise HTTPException(
            422, f"Position invalide pour `acces_membres` : {niveau} "
                 f"({' | '.join(autorisation.ACCES_MEMBRES)}, ou null pour la protéger).")
    return niveau


# --------------------------------------------------------------------------- #
# Les projets
# --------------------------------------------------------------------------- #
@router.get("/api/projets")
def list_projets(bacs_a_sable: bool = False, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Les projets qu'on peut NOMMER : ceux dont on est, et ceux d'une collection qu'on
    lit. Le projet de repli d'abord, puis par nom.

    C'est ce que la barre du haut lira pour dire dans quel projet on travaille. Une
    portée vide rend une liste vide, comme partout ; une portée totale les rend tous.
    La liste ne nomme pas les membres. Elle nomme les RESPONSABLES d'un projet à un seul
    lecteur — le membre que le réglage n'autorise pas à y créer de collection (écran de la
    3b, Hugo, 2026-10-25 : le bouton éteint dit à qui le demander).

    COL-4 — le projet de JEU n'y paraît pour personne, pas même pour la portée totale : il
    ne se règle que par son outil.

    COL-4 — une portée TOTALE ne reçoit, des bacs à sable, que le SIEN et ceux où elle est
    invitée : elle est BORNÉE (`Portee.clause_projet` ; Hugo, 2026-10-24 : dans le bac d'un
    autre, l'administrateur n'a rien). `bacs_a_sable=1`, pour qui décide des projets, ajoute
    TOUS les bacs à sable — la vue Projets de l'Administration : il voit qu'ils existent,
    leur propriétaire et leur date d'effacement, et rien de ce qu'ils portent (sa ligne ne
    compte aucune collection lue, ne le dit ni membre ni « gérable »). Une portée ordinaire
    voit ses bacs à sable par ses accès, comme tout projet, et le paramètre n'y change
    rien."""
    ou, params = portee.clause_projet("p.id")
    if bacs_a_sable and portee.peut_decider_des_projets():
        ou, params = f"({ou} OR p.bac_a_sable_de IS NOT NULL)", params
    lignes = _rows(conn.execute(
        f"SELECT p.* FROM projet p WHERE {ou} AND NOT {sql_est_jeu('p.id')} "
        "ORDER BY p.repli DESC, p.nom COLLATE NOCASE, p.id", params))
    return [_vue(conn, portee, p) for p in lignes]


@router.post("/api/projets", status_code=201)
def create_projet(payload: ProjetIn, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Crée un projet, sans membre ni responsable, avec sa collection de BASE (D10) — la
    seule qu'il ait en naissant, vide, de son nom. Qui le crée n'y entre pas pour autant —
    un administrateur règle tout projet sans en être, et lui inventer un rôle fausserait la
    liste de ceux qui y travaillent (la raison écrite sur `create_collection`).

    `justification` se saisit ici : pourquoi ce projet existe. `acces_membres` aussi : ce
    que ses membres pourront dans sa base (`ProjetIn` dit sa valeur par défaut, et
    pourquoi). La base n'a aucune ligne d'accès : ses propriétaires sont les responsables
    du projet, par dérivation (`autorisation.Portee`)."""
    _exiger_de_decider(portee)
    nom = _nom_valide(conn, payload.nom)
    position = _position_valide(payload.acces_membres)
    cur = conn.execute(
        "INSERT INTO projet (nom, description, justification) VALUES (?, ?, ?)",
        (nom, payload.description, payload.justification))
    pid = cur.lastrowid
    journal.journaliser(conn, "creation", "projet", pid, apres={"nom": nom})
    base = creer_collection_de_base(conn, pid, nom=nom, acces_membres=position)
    journal.journaliser(conn, "creation", "collection", base,
                        apres={"nom": conn.execute("SELECT nom FROM collection WHERE id = ?",
                                                   (base,)).fetchone()[0],
                               "proprietaire": None, "base": True, "projet_id": pid,
                               "acces_membres": position})
    conn.commit()
    return _vue(conn, portee, _get_projet(conn, portee, pid))


@router.patch("/api/projets/{projet_id}")
def update_projet(projet_id: int, payload: ProjetUpdate,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Renomme un projet, ou en change la description et la justification.

    Réservé à qui DÉCIDE des projets, pas à qui gère celui-ci : le nom d'un projet se lit
    sur l'écran de tous ceux qui y travaillent. 404 sur un projet qu'on ne voit pas, 403
    nommé sur un projet qu'on voit — y compris pour son responsable.

    Le projet de repli se renomme comme un autre : il est désigné par son drapeau."""
    p = _get_projet(conn, portee, projet_id)
    _exiger_de_decider(portee)
    _refuser_le_jeu(conn, projet_id=projet_id)
    if p["bac_a_sable_de"] is not None:
        raise HTTPException(409, "C'est un bac à sable : il ne se renomme pas.")
    fields = payload.model_dump(exclude_unset=True)
    if "nom" in fields:
        # Un nom INCHANGÉ ne se revalide pas : baisser le plafond un jour ne doit pas rendre
        # impossible de corriger la description d'un projet nommé avant.
        nom = (fields["nom"] or "").strip()
        fields["nom"] = nom if nom == p["nom"] else _nom_valide(conn, nom, sauf=projet_id)
    # Ce qui CHANGE, et rien d'autre : le journal n'a pas à inventer une modification.
    changes = {k: v for k, v in fields.items() if p[k] != v}
    if changes:
        cols = ", ".join(f"{k} = ?" for k in changes)
        conn.execute(f"UPDATE projet SET {cols} WHERE id = ?",
                     (*changes.values(), projet_id))
        journal.journaliser(conn, "modification", "projet", projet_id,
                            avant={k: p[k] for k in changes}, apres=changes)
        conn.commit()
    return _vue(conn, portee, _get_projet(conn, portee, projet_id))


@router.delete("/api/projets/{projet_id}", status_code=204)
def delete_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un projet VIDE. Ses membres en sortent avec lui (`ON DELETE CASCADE`).

    Réservé à qui DÉCIDE des projets. Les trois refus qui se nomment — le projet de repli,
    un projet qui porte une collection, un projet dont une copie est gardée au fonds —
    vivent dans `socle._supprimer_projet`, que la réponse à la demande d'un responsable
    traverse aussi (`routes/fonds.py`) : deux chemins, une règle."""
    p = _get_projet(conn, portee, projet_id)
    _exiger_de_decider(portee)
    _refuser_le_jeu(conn, projet_id=projet_id)
    if p["bac_a_sable_de"] is not None:
        raise HTTPException(409, "C'est un bac à sable : il ne se supprime pas, il se remet à "
                                 "neuf, et s'efface avec les autres chaque lundi.")
    _supprimer_projet(conn, portee, p)
    conn.commit()
    return Response(status_code=204)


@router.put("/api/projets/{projet_id}/acces-membres")
def regler_acces_membres(projet_id: int, payload: AccesMembresIn,
                         conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Règle ce que les MEMBRES du projet peuvent dans sa collection de base (D10) :
    `ecriture`, `lecture`, ou `null` — protégée, le propriétaire seul et qui il fait entrer.

    Réservé à qui GÈRE le projet (`peut_gerer_projet`) : son responsable, et
    l'administrateur qui passe outre. 404 sur un projet qu'on ne voit pas, 403 nommé sur un
    projet qu'on voit sans le gérer.

    Resserrer n'efface aucun travail : ce que les membres ont posé reste, ils cessent de le
    voir. C'est un changement d'ACCÈS, écrit au journal comme les autres (`lien` sous
    `collection_acces`, la base pour cible — non annulable, retenu de toute sortie) ; rien
    ne s'écrit si rien ne change."""
    _get_projet(conn, portee, projet_id, gerer=True,
                motif="Régler ce que les membres d'un projet peuvent dans sa collection "
                      "de base revient à son responsable.")
    _refuser_le_jeu(conn, projet_id=projet_id)
    _exiger_le_proprietaire(conn, portee, projet_id)
    position = _position_valide(payload.acces_membres)
    base = collection_de_base(conn, projet_id)
    if base is None:
        # Un projet sans base : une base retouchée à la main. On ne la refait pas ici.
        raise HTTPException(409, "Ce projet n'a pas de collection de base : signalez-le à un "
                                 "administrateur.")
    avant = conn.execute("SELECT acces_membres FROM collection WHERE id = ?",
                         (base,)).fetchone()[0]
    if avant != position:
        conn.execute("UPDATE collection SET acces_membres = ? WHERE id = ?", (position, base))
        journal.journaliser(conn, "lien", "collection_acces", base,
                            avant={"membres_du_projet": projet_id, "niveau": avant},
                            apres={"membres_du_projet": projet_id, "niveau": position})
    conn.commit()
    return {"projet_id": projet_id, "collection_id": base, "acces_membres": position}


@router.put("/api/projets/{projet_id}/creation-de-collections")
def regler_creation_de_collections(projet_id: int, payload: CreationCollectionsIn,
                                   conn: sqlite3.Connection = Depends(db),
                                   portee: autorisation.Portee = Depends(portee_courante)):
    """Règle si les MEMBRES du projet peuvent y créer des collections (v36, COL-3, tranche
    3b ; Hugo, 2026-10-21) — NON par défaut. Ses responsables et les administrateurs créent
    toujours (`Portee.peut_creer_collection`).

    Réservé à qui GÈRE le projet : 404 sur un projet qu'on ne voit pas, 403 nommé sur un
    projet qu'on voit sans le gérer. Ni sur le jeu, ni dans un bac à sable, où ses invités
    créent toujours (409 nommé). Écrit au journal sous `projet` (retenu de toute sortie) ;
    rien ne s'écrit si rien ne change. Fermer n'efface rien : les collections déjà créées
    par des membres restent les leurs."""
    p = _get_projet(conn, portee, projet_id, gerer=True,
                    motif="Régler qui crée des collections dans un projet revient à son "
                          "responsable.")
    _refuser_le_jeu(conn, projet_id=projet_id)
    if p["bac_a_sable_de"] is not None:
        raise HTTPException(409, "C'est un bac à sable : ses invités y créent des collections, "
                                 "et il s'efface chaque lundi — rien à régler.")
    avant = bool(p["membres_creent_collections"])
    if avant != payload.membres:
        conn.execute("UPDATE projet SET membres_creent_collections = ? WHERE id = ?",
                     (int(payload.membres), projet_id))
        journal.journaliser(conn, "modification", "projet", projet_id,
                            avant={"membres_creent_collections": avant},
                            apres={"membres_creent_collections": payload.membres})
    conn.commit()
    return {"projet_id": projet_id, "membres_creent_collections": payload.membres}


# --------------------------------------------------------------------------- #
# Qui est d'un projet
# --------------------------------------------------------------------------- #
@router.get("/api/projets/{projet_id}/membres")
def list_membres(projet_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Qui est de ce projet, et sous quel rôle. Réservé à qui le GÈRE : la liste des
    membres est une donnée sur des PERSONNES, et un simple membre n'a pas à savoir qui
    d'autre en est, ni qui en répond."""
    _get_projet(conn, portee, projet_id, gerer=True)
    bac, _ = _bac_a_sable_de(conn, projet_id=projet_id)
    return _membres_de(conn, projet_id, sans_signal=bac is not None)


@router.put("/api/projets/{projet_id}/membres")
def poser_membre(projet_id: int, payload: MembreIn,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Fait entrer quelqu'un dans le projet, ou change son rôle. Idempotent : « nommer
    responsable » et « rétrograder » sont le même geste, comme pour un accès.

    `principal` est un NOM — un login, ou un groupe tel que le portail le transmet. Cette
    route NE LIT PAS l'annuaire : un nom mal orthographié n'ouvre simplement rien, et c'est
    la relecture par `…/membres/choix` qui le signale, jamais un refus ici.

    ELLE N'OUVRE QU'UNE COLLECTION : la base du projet (D10), où le membre entre au niveau
    que le projet a choisi, et dont le responsable est propriétaire — par dérivation, sans
    ligne d'accès écrite. Être du projet permet aussi d'y créer une collection ; lire l'une
    des autres se règle dans son « Qui entre »."""
    _get_projet(conn, portee, projet_id, gerer=True)
    _refuser_le_jeu(conn, projet_id=projet_id)            # COL-4 : personne n'en est
    proprietaire = _exiger_le_proprietaire(conn, portee, projet_id)
    if payload.genre not in autorisation.GENRES:
        raise HTTPException(422, f"Genre invalide : {payload.genre} (utilisateur | groupe).")
    if payload.role not in autorisation.ROLES_PROJET:
        raise HTTPException(
            422, f"Rôle invalide : {payload.role} ({' | '.join(autorisation.ROLES_PROJET)}).")
    principal = (payload.principal or "").strip()
    if not principal:
        raise HTTPException(422, "Le principal (login ou nom de groupe) est requis.")
    if proprietaire is not None:
        _inviter_dans_un_bac(proprietaire, payload, principal)
    avant = conn.execute(
        "SELECT role FROM projet_acces WHERE projet_id = ? AND genre = ? AND principal = ?",
        (projet_id, payload.genre, principal)).fetchone()
    # Un projet peut NAÎTRE sans responsable ; il ne PERD pas son dernier par ce geste.
    # Sans ce refus, un responsable se rétrograderait seul et laisserait un projet que
    # plus personne ne règle, hors l'administrateur.
    if (payload.role != autorisation.RESPONSABLE and avant is not None
            and avant["role"] == autorisation.RESPONSABLE
            and _compte_responsables(conn, projet_id) == 1):
        raise HTTPException(409, "C'est le dernier responsable de ce projet : "
                                 "désignez-en un autre avant de le rétrograder.")
    conn.execute(
        "INSERT INTO projet_acces (projet_id, genre, principal, role) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(projet_id, genre, principal) DO UPDATE SET role = excluded.role",
        (projet_id, payload.genre, principal, payload.role))
    # Qui a fait entrer qui, et quand — non annulable : `projet_acces` n'est pas dans la
    # liste blanche de l'annulation. `cible_id` est le PROJET, la table n'ayant pas d'id.
    journal.journaliser(conn, "lien", "projet_acces", projet_id,
                        avant={"genre": payload.genre, "principal": principal,
                               "role": avant["role"]} if avant else None,
                        apres={"genre": payload.genre, "principal": principal,
                               "role": payload.role})
    conn.commit()
    return _membres_de(conn, projet_id, sans_signal=proprietaire is not None)


def _inviter_dans_un_bac(proprietaire: str, payload, principal: str) -> None:
    """Les bornes de l'invitation dans un bac à sable (S11 ; Q6, Hugo, 2026-10-21) : un
    COMPTE, jamais un groupe — trente étudiants d'un coup, dans un espace qu'une seule
    personne remet à neuf —, au rôle de MEMBRE — un invité responsable retirerait le
    propriétaire, qui garderait `bac_a_sable_de` sans plus rien y voir —, et jamais la ligne
    du propriétaire, inamovible. 409 nommés."""
    if payload.genre != autorisation.UTILISATEUR:
        raise HTTPException(409, "Dans un bac à sable, on invite un compte par son login, "
                                 "pas un groupe.")
    if principal == proprietaire:
        raise HTTPException(409, "C'est le propriétaire de ce bac à sable : il en reste "
                                 "le seul responsable.")
    if payload.role != autorisation.MEMBRE:
        raise HTTPException(409, "Dans un bac à sable, on invite au rôle de membre : son "
                                 "propriétaire en reste le seul responsable.")


@router.delete("/api/projets/{projet_id}/membres/{genre}/{principal}", status_code=204)
def retirer_membre(projet_id: int, genre: str, principal: str,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Fait sortir quelqu'un du projet. Il sort de la collection de base, où il n'entrait
    que par le projet (D10) ; il ne perd aucun accès de collection posé dans un « Qui
    entre », et rien n'est détruit : le journal lui attribue toujours son travail. Refus
    sur le dernier responsable."""
    _get_projet(conn, portee, projet_id, gerer=True)
    _refuser_le_jeu(conn, projet_id=projet_id)
    proprietaire = _exiger_le_proprietaire(conn, portee, projet_id)
    if proprietaire is not None and genre == autorisation.UTILISATEUR \
            and principal == proprietaire:
        raise HTTPException(409, "C'est le propriétaire de ce bac à sable : il ne se retire "
                                 "pas — le bac à sable se remet à neuf, et s'efface.")
    if proprietaire is not None:
        # COL-4 — retiré d'un bac à sable, l'invité y perd tout ce qu'il tenait, la
        # propriété de ses collections comprise (`socle._sortir_du_bac`).
        if not _sortir_du_bac(conn, projet_id, genre, principal):
            raise HTTPException(404, "Ce membre n'existe pas.")
        conn.commit()
        return Response(status_code=204)
    ligne = conn.execute(
        "SELECT role FROM projet_acces WHERE projet_id = ? AND genre = ? AND principal = ?",
        (projet_id, genre, principal)).fetchone()
    if ligne is None:
        raise HTTPException(404, "Ce membre n'existe pas.")
    if (ligne["role"] == autorisation.RESPONSABLE
            and _compte_responsables(conn, projet_id) == 1):
        raise HTTPException(409, "C'est le dernier responsable de ce projet : "
                                 "désignez-en un autre avant de le retirer.")
    conn.execute("DELETE FROM projet_acces WHERE projet_id = ? AND genre = ? "
                 "AND principal = ?", (projet_id, genre, principal))
    journal.journaliser(conn, "delien", "projet_acces", projet_id,
                        avant={"genre": genre, "principal": principal,
                               "role": ligne["role"]})
    conn.commit()
    return Response(status_code=204)
