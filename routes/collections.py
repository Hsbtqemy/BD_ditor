"""Collections — espaces de travail, accès et diffusion (AUTH-3, DROIT-1).

Le conteneur existe depuis la v14 comme unité de DÉPÔT ; AUTH-2 en a fait l'unité de
CLOISONNEMENT, et ce module est ce par quoi on l'administre autrement qu'en SQL à la main :
créer, partager, retirer un accès, ranger un album.

Trois paliers qui s'empilent — lire · écrire · POSSÉDER — et le troisième ne découle pas du
second : écrire c'est annoter, posséder c'est décider qui d'autre entrera. Deux gestes sont
refusés par un 409 qui les NOMME : retirer ou rétrograder le DERNIER propriétaire d'une
collection, et supprimer une collection qui est la dernière d'un album. Supprimer un album de
sa dernière collection, lui, aboutit depuis le fonds (COL-3, tranche 2) : la copie y est
gardée avec son travail. Une collection peut en revanche NAÎTRE sans
propriétaire — créée par un administrateur, en mono-poste, ou par l'outil en ligne de
commande sans `--proprietaire` — et seule une portée totale l'administre alors (AUTH-12,
option B tranchée le 2026-09-16).

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
from fastapi.responses import JSONResponse, Response

import annuaire
import autorisation
import comptes
import conflit
import journal
from config import STATUTS_DIFFUSION
from database import (DEMANDE_REJOINDRE, NATURES, clore_rejoindre_d_une_copie_au_fonds,
                      collection_row, collections,
                      etat_embargo, nom_reserve, poser_projet_de_copie, projet_de_collection,
                      projet_de_jeu, projet_par_defaut, ranger_copie,
                      un_proprietaire_tient_toute_la_copie)

from socle import (
    DEMANDE, REFUSE, AccesIn, CollectionIn, CollectionUpdate, NatureIn,
    _clore_demandes_vers, _collections_lues_d_albums, _deposer, _en_attente_vers,
    _MOTIF_BAC_ACCES, _MOTIF_BAC_ANNUAIRE, _MOTIF_BAC_PROPRIETAIRE, _bac_a_sable_de,
    _get_album, _get_collection, _get_projet, _plan_rejoindre, _refuser_le_bac_a_sable,
    _refuser_le_jeu, _rows, db, portee_courante,
)

router = APIRouter()

# Le conteneur existe depuis la v14 (unité de DÉPÔT), le cloisonnement depuis AUTH-2
# (`collection_acces`). Il manquait de quoi l'ADMINISTRER autrement qu'en SQL à la main :
# créer, partager, retirer, ranger un album. C'est tout ce chantier.
#
# Trois paliers, et le troisième est la nouveauté : lire · écrire · POSSÉDER. Écrire, c'est
# annoter ; posséder, c'est décider qui d'autre entrera. Le second ne découle pas du premier.
# =========================================================================== #
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


def _acces_de(conn, collection_id: int, *, sans_signal: bool = False) -> list[dict]:
    """Les accès accordés sur une collection, propriétaires d'abord.

    **`jamais_vu` RAPPORTE une observation et n'explique aucune cause** (AUTH-6,
    2026-09-09). Un accès se déclare par un NOM : `collection_acces` accepte n'importe
    quelle chaîne, et un login mal orthographié n'ouvre rien sans que rien ne le dise. La
    table `utilisateur` sait pourtant déjà quelque chose d'utile — elle contient les logins
    qui ont OUVERT une page —, et cette connaissance ne servait nulle part.

    Ce que le champ ne fait PAS, et c'est la moitié de sa valeur : il ne distingue pas une
    faute de frappe d'un arrivant qui n'est pas encore venu. Les deux produisent exactement
    la même absence, et l'application ne peut pas les départager. Prétendre le contraire
    enverrait chercher la mauvaise panne — c'est pour cette raison précise que le bandeau
    de portée vide a été réécrit le 2026-09-06.

    **`None` pour un GROUPE, jamais `False`.** L'application ne lit aucun annuaire
    (invariant AUTH-1) : elle ne connaît que les groupes de la personne qui frappe, à
    l'instant de sa requête. Répondre `False` affirmerait « ce groupe existe », ce qu'elle
    n'a aucun moyen de savoir. C'est la leçon d'AUTH-8, où `None` et `False` ont dû être
    séparés parce qu'un en-tête ABSENT et un en-tête VIDE arrivaient identiques — et où le
    code, pas le protocole, portait l'ambiguïté.
    """
    lignes = _rows(conn.execute(
        "SELECT genre, principal, niveau, exporter, date_creation FROM collection_acces "
        "WHERE collection_id = ? "
        "ORDER BY CASE niveau WHEN 'proprietaire' THEN 0 WHEN 'ecriture' THEN 1 ELSE 2 END, "
        "         genre, principal", (collection_id,)))
    logins = sorted({acc["principal"] for acc in lignes
                     if acc["genre"] == autorisation.UTILISATEUR})
    connus = set()
    if logins:
        qm = ",".join("?" * len(logins))
        connus = {r[0] for r in conn.execute(
            f"SELECT login FROM utilisateur WHERE login IN ({qm})", logins)}
    for acc in lignes:
        # DROIT-2 — le droit EFFECTIF, pas la case stockée : un propriétaire exporte
        # d'office, et une liste qui le dirait « sans export » parce que sa case n'a
        # jamais été cochée serait exacte et trompeuse.
        #
        # Mais l'effectif et le POSÉ sont deux choses, et les rendre sous le SEUL nom
        # `exporter` a coûté un droit accordé par accident (revue du 2026-09-18) : l'écran
        # relisait cette valeur et la reposait en rétrogradant un propriétaire, si bien
        # qu'un membre en écriture repartait avec l'export, que personne ne lui avait
        # accordé. La dérivation ne doit jamais pouvoir se faire passer pour une décision,
        # d'où les deux champs — et la garde du `PUT`, qui ferme la porte à tout appelant.
        acc["exporter_pose"] = bool(acc["exporter"])
        acc["exporter"] = (bool(acc["exporter"])
                           or acc["niveau"] == autorisation.PROPRIETAIRE)
        acc["jamais_vu"] = (acc["principal"] not in connus
                            if acc["genre"] == autorisation.UTILISATEUR else None)
        if sans_signal:
            acc.pop("jamais_vu")        # COL-4 : pas d'oracle dans un bac à sable
    return lignes


def _acces_rendus(conn, collection_id: int) -> list[dict]:
    """`_acces_de`, sans le signal `jamais_vu` sur une collection de bac à sable."""
    bac, _ = _bac_a_sable_de(conn, collection_id=collection_id)
    return _acces_de(conn, collection_id, sans_signal=bac is not None)


def _ligne(conn, collection_id: int) -> dict:
    """La ligne d'une collection telle qu'une route la REND : `projet_id` y est le projet
    LU (`database.sql_projet_de`), jamais la colonne brute — la même valeur que dans la
    liste, pour qu'une collection ne change pas de projet selon la route qui la montre."""
    c = collection_row(conn, collection_id)
    c["projet_id"] = projet_de_collection(conn, collection_id)
    c["base"] = bool(c["base"])
    return c


def _compte_proprietaires(conn, collection_id: int) -> int:
    """Combien de propriétaires tiennent cette collection — les lignes de `collection_acces`
    ET, pour une collection de BASE, les responsables de son projet, qui en sont
    propriétaires par dérivation (D10 ; `autorisation.acces_derives`, la règle de
    `Portee`). C'est ce que compte le 409 « dernier propriétaire » : retirer la dernière
    ligne explicite d'une base dont le projet a un responsable ne la laisse pas sans
    propriétaire (COL-3, écran de la 3a)."""
    explicites = conn.execute(
        "SELECT COUNT(*) FROM collection_acces WHERE collection_id = ? AND niveau = ?",
        (collection_id, autorisation.PROPRIETAIRE)).fetchone()[0]
    derives = sum(1 for a in autorisation.acces_derives(conn, collection_id)
                  if a["niveau"] == autorisation.PROPRIETAIRE)
    return explicites + derives


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
    du lexique proposerait sinon de ranger un terme chez quelqu'un d'autre.

    COL-3 — chaque collection dit son PROJET (`projet_id`, `projet_nom`), lu par la règle
    de `database.sql_projet_de` : jamais vide, une collection sans projet nommé étant du
    projet de repli. Le filtre ne change pas : on liste ce qu'on LIT, quel que soit le
    projet, et être d'un projet n'y ajoute aucune ligne.

    COL-4 — la collection du JEU n'y paraît pour personne, pas même pour la portée totale,
    la seule qui la lise : elle ne se règle que par l'outil du jeu."""
    jeu = projet_de_jeu(conn)
    vues = [c for c in collections(conn)
            if (portee.tout or c["id"] in portee.lecture)
            and (jeu is None or c["projet_id"] != jeu)]
    for c in vues:
        c["mon_niveau"] = _niveau_dans(portee, c["id"])
        c["administrable"] = portee.peut_administrer(c["id"])
        # DROIT-2 — la seconde question que le client reçoit, et pour la même raison
        # qu'`administrable` : cacher un bouton d'export qu'on refuserait. La garde
        # reste celle du serveur, sur chaque porte ; ceci n'évite qu'un geste perdu.
        c["exportable"] = portee.peut_exporter(c["id"])
        # AUTH-12 — la même raison pour ÉCRIRE : la modale d'album proposait des collections
        # qu'on ne fait que lire, et l'enregistrement répondait « Collection N introuvable ».
        # L'écran lit la réponse au lieu de recalculer l'ordre des niveaux ; la garde reste
        # celle de `create_album` et `ranger_album`.
        c["ecrivable"] = portee.peut_ecrire(c["id"])
        # DROIT-1 — l'état de la date d'embargo, DÉRIVÉ ici comme il l'est à la sortie :
        # `tools/iiif_manifest.py` lit la MÊME fonction, sans quoi l'écran et l'export
        # finiraient par ne plus dire la même chose du même champ. Un embargo échu que
        # personne ne remarque garde un corpus fermé par inertie ; l'outil ne le lève pas
        # tout seul (une date qui passe ne dit pas que les droits sont acquis), mais il
        # cesse de se taire.
        c["embargo"] = etat_embargo(c)
        # D10 (COL-3, tranche 3) — la collection de BASE de son projet, et la position de
        # ses membres (`acces_membres` : `ecriture`, `lecture`, `null` = protégée), à qui la
        # lit : c'est elle que l'import présélectionne, et ce que le projet a choisi n'est
        # pas un secret pour qui y entre. Qui peut la RÉGLER se lit dans `gerable`, sur le
        # projet (`GET /api/projets`) : la question est celle du projet, pas de la
        # collection. Hors d'une base, la position ne veut rien dire et vaut `null`.
        c["base"] = bool(c["base"])
        if not c["base"]:
            c["acces_membres"] = None
    return vues


@router.post("/api/collections", status_code=201)
def create_collection(payload: CollectionIn, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Crée une collection ; son créateur en devient PROPRIÉTAIRE — sauf un administrateur
    et le mono-poste, pour les raisons ci-dessous, tenues par AUTH-12 le 2026-09-16.

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
    # COL-3 — une collection naît dans UN projet, et n'en change pas. Sans `projet_id`,
    # ou en nommant le projet de repli : rien ne change, une identité suffit — sans quoi
    # l'écran, qui enverra toujours le projet courant, fermerait ce que l'API laisse
    # ouvert. Dans un AUTRE projet, il faut en être : 404 s'il n'est pas visible, 403 nommé
    # si l'on en voit le nom (par une collection qu'on lit) sans en être membre.
    projet_id = projet_par_defaut(conn)
    if payload.projet_id is not None and payload.projet_id != projet_id:
        projet_id = _get_projet(conn, portee, payload.projet_id)["id"]
        _refuser_le_jeu(conn, projet_id=projet_id)        # COL-4 : on n'y range rien
        if not portee.est_du_projet(projet_id):
            raise HTTPException(403, "Créer une collection dans ce projet demande d'en "
                                     "être membre.")
    cur = conn.execute(
        "INSERT INTO collection (nom, description, projet_id) VALUES (?, ?, ?)",
        (nom, payload.description, projet_id))
    cid = cur.lastrowid
    if portee.utilisateur and not portee.admin:
        conn.execute(
            "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
            "VALUES (?, ?, ?, ?)",
            (cid, autorisation.UTILISATEUR, portee.utilisateur, autorisation.PROPRIETAIRE))
    journal.journaliser(conn, "creation", "collection", cid,
                        apres={"nom": nom, "proprietaire": portee.utilisateur})
    conn.commit()
    return {**_ligne(conn, cid), "acces": _acces_rendus(conn, cid)}


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
    _refuser_le_jeu(conn, collection_id=collection_id)
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
    # Ce qui CHANGE, et rien d'autre : renvoyer une valeur identique n'est pas une
    # modification, et le journal n'a pas à en inventer une.
    changes = {k: v for k, v in fields.items() if c[k] != v}
    if changes:
        cols = ", ".join(f"{k} = ?" for k in changes)
        conn.execute(f"UPDATE collection SET {cols} WHERE id = ?",
                     (*changes.values(), collection_id))
        # AUTH-12 — modifier une collection ne laissait aucune trace : ni auteur ni date
        # pour un référent remplacé, un régime passé à `public`, une base légale effacée,
        # alors que la création, la suppression et les accès en laissent une. La cible
        # `collection` est RETENUE de toute sortie (`tools/_commun.CIBLES_RETENUES`) : le
        # référent et son contact entrent au journal sans pouvoir en ressortir, ce qu'AUTH-4
        # exige d'eux — et le cliquet des cibles retenues l'éprouve.
        journal.journaliser(conn, "modification", "collection", collection_id,
                            avant={k: c[k] for k in changes}, apres=changes)
        conn.commit()
    return _ligne(conn, collection_id)


@router.delete("/api/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: int, conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime une collection. Ses ALBUMS survivent (l'appartenance est N-N : le lien se
    défait, l'œuvre reste), et ses termes de vocabulaire sont PROMUS en global
    (`ON DELETE SET NULL`) plutôt que perdus.

    Refus si un album n'appartiendrait alors plus à aucune collection. Ce n'est plus un
    album sans règle — depuis le fonds (COL-3, tranche 2), il y serait gardé — mais
    l'envoyer au fonds par ricochet, sans que personne l'ait décidé album par album,
    n'est pas un geste de cette route : le refus est gardé, et sa phrase dit ce qui reste
    à faire (proposition R6 du cadrage, suivie en route).
    """
    c = _get_collection(conn, portee, collection_id, administrer=True)
    # D10 (COL-3, tranche 3) — la collection de BASE d'un projet ne se supprime pas : née
    # avec lui, elle part avec lui (`socle._supprimer_projet`). Le refus vient après la garde
    # d'administration : il ne parle qu'à qui pourrait supprimer une autre collection.
    if c["base"]:
        raise HTTPException(409, "C'est la collection de base de son projet : elle se "
                                 "renomme, elle ne se supprime pas — elle part avec le "
                                 "projet.")
    isoles = [r[0] for r in conn.execute(
        "SELECT ca.album_id FROM collection_album ca WHERE ca.collection_id = ? "
        "AND NOT EXISTS (SELECT 1 FROM collection_album x WHERE x.album_id = ca.album_id "
        "                AND x.collection_id <> ca.collection_id)", (collection_id,))]
    if isoles:
        raise HTTPException(
            409, f"{len(isoles)} album(s) n'appartiennent qu'à cette collection : "
                 "rangez-les ailleurs, ou supprimez-les d'abord de la collection — ils "
                 "sont alors gardés au fonds avec leur travail.")
    c = collection_row(conn, collection_id)
    # COL-3 — supprimer une collection en RETIRE ses albums, un par un : la cascade défait
    # les liens sans rien dire, et chacun est un emploi qui cesse. Relevés AVANT, puisque
    # la cascade les emporte ; écrits avant, tant que la collection porte encore son nom.
    for (album_id,) in conn.execute(
            "SELECT album_id FROM collection_album WHERE collection_id = ? "
            "ORDER BY album_id", (collection_id,)).fetchall():
        journal.journaliser_emploi(conn, "delien", album_id, collection_id)
    # COL-3, tranche 3 — les demandes qui la nomment comme ARRIVÉE sont refusées : son
    # identifiant se réattribue, et une demande acceptée plus tard rangerait ailleurs.
    _clore_demandes_vers(conn, portee, collection_id)
    conn.execute("DELETE FROM collection WHERE id = ?", (collection_id,))
    journal.journaliser(conn, "suppression", "collection", collection_id,
                        avant={"nom": c["nom"]})
    conn.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# La vue des comptes et des groupes (AUTH-7, puis AUTH-6 et AUTH-12)
#
# `GET /api/comptes` la servait jusqu'au 2026-09-17 : les comptes VUS par l'application, et ce
# que chacun a laissé. `GET /api/comptes-et-groupes` la remplace, avec l'annuaire, et l'écran
# « 👥 Comptes et groupes » a cessé de lire l'ancienne. Ce qu'un compte a laissé et son
# verdict de départ sont comptés dans `comptes.py`, à un seul endroit.
# --------------------------------------------------------------------------- #
@router.get("/api/comptes-et-groupes")
def comptes_et_groupes(conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """La vue « 👥 Comptes et groupes » (AUTH-12, étape 2) : ce que l'ANNUAIRE rend, ce que
    l'application a VU, ce qu'elle a ACCORDÉ, et ce qui est « À regarder » (AUTH-6).

    RÉSERVÉE AUX ADMINISTRATEURS D'INSTANCE, pour la raison qui réserve déjà
    `GET /api/analyse/accord-inter` et réservait la vue des comptes d'AUTH-7 : elle porte
    sur des PERSONNES et non sur le corpus — elle nomme, date et compte. Un propriétaire de
    collection n'y gagnerait rien qu'il ne sache déjà (il choisit qui il ajoute) et y
    verrait la composition d'équipes qui ne sont pas la sienne.

    L'annuaire est LU ici, à chaque ouverture, pour COMPOSER cette vue — ni pour authentifier
    (Authelia), ni pour autoriser : aucune portée ne change selon ce qu'il rend, et
    `autorisation.py` n'en importe rien. Une panne ne bloque rien : la vue répond 200 avec
    ce que l'application sait seule, et le dit (`annuaire.etat`).
    """
    if not portee.tout:
        raise HTTPException(403, "La vue des comptes et des groupes est réservée aux "
                                 "administrateurs : elle porte sur des personnes, pas sur "
                                 "le corpus.")
    return comptes.composer(conn, annuaire.lire())


@router.patch("/api/comptes/{login}/nature")
def poser_nature(login: str, payload: NatureIn,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Déclarer qu'un login est PARTAGÉ, ou qu'il ne l'est plus (AUTH-6).

    RÉSERVÉE AUX ADMINISTRATEURS, comme la vue qui la porte et pour la même raison : elle
    parle d'une personne — ou justement du fait qu'il n'y en a pas une seule.

    **Elle n'accorde et ne retire AUCUN droit.** Un compte collectif écrit partout où ses
    accès le portent, décidé le 2026-09-09 ; ce qui change est ce que les MESURES ont le
    droit d'affirmer sur lui — et, depuis le 2026-09-11, jusqu'où Ctrl+Z remonte : cinq
    minutes (`undo.DELAI_COLLECTIF_MINUTES`), parce que le filtre par agent n'y désigne
    plus une personne. C'est la portée d'une commodité, pas un droit. Confondre les deux
    ferait de cette route une porte d'autorisation déguisée, et `autorisation.py`
    cesserait d'être le seul endroit qui tranche.

    Une exception, depuis le fonds (COL-3, tranche 2), et elle porte sur un GESTE, pas sur
    un accès : un compte partagé ne supprime jamais définitivement seul — « celui qui l'a
    importé » n'y désigne personne —, il le demande (proposition R7 du cadrage). C'est
    `autorisation.Portee.clause_suppression_directe` qui lit la nature pour cela, et pour
    cela seul : aucun accès n'en dépend.

    Le login doit avoir été VU : on ne déclare pas la nature d'un compte que l'application
    ne connaît pas. Ce n'est pas une restriction, c'est le périmètre de la table — un login
    créé dans l'annuaire et jamais venu n'a pas de ligne, et lui en fabriquer une ici
    inventerait un compte actif qui ne l'est pas.

    Journalisée sous `cible_table='utilisateur_nature'` et non `'utilisateur'` : cette
    dernière porte les REPRISES d'identité, qu'AUTH-7 compte pour signaler qu'un login a
    changé de mains. Y verser ce changement-ci gonflerait ce compteur d'un événement qui
    n'a rien d'une reprise — un mensonge silencieux dans l'écran qui sert à décider d'une
    suppression.
    """
    if not portee.tout:
        raise HTTPException(403, "Déclarer la nature d'un compte est réservé aux "
                                 "administrateurs.")
    if payload.nature not in NATURES:
        raise HTTPException(422, f"Nature invalide : {payload.nature} "
                                 f"({' | '.join(NATURES)}).")
    ligne = conn.execute("SELECT nature FROM utilisateur WHERE login = ?",
                         (login,)).fetchone()
    if ligne is None:
        raise HTTPException(404, f"Aucun compte connu sous « {login} » : l'application ne "
                                 "voit que les logins qui ont ouvert une page.")
    ancienne = ligne["nature"]
    if ancienne != payload.nature:
        conn.execute("UPDATE utilisateur SET nature = ? WHERE login = ?",
                     (payload.nature, login))
        journal.journaliser(conn, "modification", "utilisateur_nature", None,
                            avant={"login": login, "nature": ancienne},
                            apres={"login": login, "nature": payload.nature})
        conn.commit()
    return {"login": login, "nature": payload.nature}


@router.get("/api/collections/{collection_id}/acces")
def list_acces(collection_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Qui a accès à cette collection, et à quel niveau. Réservé au propriétaire : la liste
    des membres d'une étude est une donnée sur des PERSONNES, pas sur le corpus."""
    _get_collection(conn, portee, collection_id, administrer=True)
    return _acces_rendus(conn, collection_id)


@router.get("/api/collections/{collection_id}/acces-du-projet")
def list_acces_du_projet(collection_id: int, conn: sqlite3.Connection = Depends(db),
                         portee: autorisation.Portee = Depends(portee_courante)):
    """Qui entre dans cette collection PAR LE PROJET — pour une collection de BASE, ses
    responsables (propriétaires) et ses membres (au niveau que le projet a choisi), que
    `autorisation.Portee` dérive de `projet_acces` sans aucune ligne dans `collection_acces`
    (D10). COL-3, écran de la 3a (case « L'accès tenu par le projet se lit là où l'on regarde
    qui entre ») : sans cette lecture, un propriétaire de la base croyait son cercle
    restreint alors que tous les membres y écrivaient — la relecture croisée l'a relevé, et
    c'est l'esprit d'AUTH-4, « inévitable, mais pas invisible ».

    Les mêmes bornes que `…/acces`, parce que c'est la même donnée sur des PERSONNES : à qui
    ADMINISTRE la collection — 404 à qui ne la lit pas, 403 nommé à qui la lit sans la
    posséder. SÉPARÉE de `…/acces` plutôt qu'ajoutée à sa liste : celle-ci est aussi la
    réponse du `PUT` et du `DELETE` d'un accès, et une ligne dérivée qui s'y glisserait
    serait offerte au geste qui ne peut pas la changer.

    Rend `base` (la collection est-elle la base de son projet), le projet (`projet_id`,
    `projet_nom`), la position de ses membres (`acces_membres`), `gerable` — l'appelant
    peut-il régler ces accès, c'est-à-dire gérer le projet (`peut_gerer_projet`) — et les
    `lignes` (`autorisation.acces_derives`). Hors d'une base, `lignes` est vide."""
    c = _get_collection(conn, portee, collection_id, administrer=True)
    projet_id = projet_de_collection(conn, collection_id)
    p = conn.execute("SELECT nom FROM projet WHERE id = ?", (projet_id,)).fetchone()
    base = bool(c["base"])
    return {"base": base, "projet_id": projet_id, "projet_nom": p["nom"] if p else None,
            "acces_membres": c["acces_membres"] if base else None,
            "gerable": portee.peut_gerer_projet(projet_id),
            "lignes": autorisation.acces_derives(conn, collection_id)}


@router.get("/api/collections/{collection_id}/annuaire")
def annuaire_de_la_collection(collection_id: int, conn: sqlite3.Connection = Depends(db),
                              portee: autorisation.Portee = Depends(portee_courante)):
    """Ce que la fiche d'une collection montre en s'ouvrant, pour régler qui entre (AUTH-12,
    étape 3) : les groupes de l'annuaire à PROPOSER, et la vérification des accès déjà
    accordés — la colonne « Signal ».

    Réservée au PROPRIÉTAIRE de CETTE collection (et à l'administrateur) : 404 à qui ne la
    lit pas, 403 nommé à qui la lit sans la posséder. Le propriétaire voit les NOMS des
    groupes, sans groupes de rôle ni d'administration, et jamais leurs membres (UX-4).

    SÉPARÉE de `…/acces` exprès : cette liste est aussi la réponse du `PUT` et du `DELETE`
    d'un accès, et y lire l'annuaire ferait attendre chaque geste d'accès un annuaire en
    panne. Ici, la liste s'affiche tout de suite et les marques arrivent après."""
    _get_collection(conn, portee, collection_id, administrer=True)
    _refuser_le_bac_a_sable(conn, _MOTIF_BAC_ANNUAIRE, 403, collection_id=collection_id)
    return comptes.choix_des_acces(conn, collection_id, annuaire.lire())


@router.get("/api/projets/{projet_id}/membres/choix")
def choix_des_membres_du_projet(projet_id: int, conn: sqlite3.Connection = Depends(db),
                                portee: autorisation.Portee = Depends(portee_courante)):
    """Ce que la fiche d'un PROJET montre pour régler qui y entre (COL-3) : les groupes de
    l'annuaire à proposer, et la vérification des membres déjà posés. Le jumeau de la route
    ci-dessus, un étage plus haut, et les mêmes bornes : réservée à qui GÈRE ce projet
    (404 à qui ne le voit pas, 403 nommé à qui le voit sans le gérer), des NOMS de groupe
    sans leurs membres.

    ELLE VIT ICI et non dans `routes/projets.py`, où sont toutes les autres routes du
    projet : c'est la seule qui lise l'annuaire, et les routes qui le lisent tiennent dans
    CE module — `tests/test_annuaire.py` le verrouille par égalité. Séparée de `…/membres`
    pour la raison qui sépare `…/annuaire` de `…/acces` : aucun geste sur un membre
    n'attend un annuaire en panne."""
    _get_projet(conn, portee, projet_id, gerer=True)
    _refuser_le_bac_a_sable(conn, _MOTIF_BAC_ANNUAIRE, 403, projet_id=projet_id)
    return comptes.choix_des_membres(conn, projet_id, annuaire.lire())


# `GET …/annuaire/verifier` a vécu ici jusqu'au 2026-09-18 : elle disait si un nom TAPÉ
# existe dans l'annuaire, pour que l'écran le vérifie AVANT de l'accorder. C'est cette
# intention qui avait fait accepter son exposition — un oracle où un propriétaire sonde
# l'existence de n'importe quel login de l'instance, sans limite de débit. L'écran livré ne
# l'a jamais appelée : il pose l'accès, relit, et lit la vérification dans la liste que rend
# `…/annuaire`. On payait donc l'exposition sans rien en retirer. Le jour où « vérifier avant
# d'accorder » sera un vrai besoin d'usage, la route se réécrira et son exposition se
# redécidera EN SACHANT ce qu'on achète, au lieu d'hériter d'un oui donné pour autre chose.
@router.get("/api/droits")
def droits():
    """Ce que chaque niveau d'accès permet, dit en ACTES : l'échelle, les actes et leurs
    liaisons, ce qui est hors rang (AUTH-12, « La finesse des droits »).

    Statique, identique pour tous, sans aucune donnée du corpus : la table vit dans
    `autorisation.py`, sous `NIVEAUX`, et aucune garde ne la lit. L'écran ne connaît ainsi
    aucun niveau en dur — ce qu'AUTH-10 décidera changera la description, pas le JavaScript."""
    return autorisation.description_des_droits()


@router.put("/api/collections/{collection_id}/acces")
def accorder_acces(collection_id: int, payload: AccesIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    """Accorde (ou change) un accès. Idempotent : re-poser le même principal met à jour son
    niveau, ce qui fait de « promouvoir » et « rétrograder » le même geste.

    `principal` est un NOM — un login, ou un nom de groupe tel qu'Authelia le pose dans
    `Remote-Groups`. On n'accorde donc rien à une personne qu'on aurait vérifiée : on
    déclare qu'un nom ouvre une collection, et un nom mal orthographié n'ouvre simplement
    rien. Cette route NE LIT PAS l'annuaire (invariant AUTH-1) : l'accès se pose, et c'est la
    relecture par `…/annuaire` (AUTH-6) qui le marque « inconnu de l'annuaire » — signalé,
    jamais refusé (décision 4 (2) d'AUTH-12), et sans qu'aucun geste d'accès attende l'annuaire.

    `exporter` (DROIT-2) se pose dans le même geste, et par le même PROPRIÉTAIRE :
    décider ce qui sort d'une collection l'engage autant que décider qui y entre. Il
    est tracé avec le niveau, dans le même événement du journal.
    """
    _get_collection(conn, portee, collection_id, administrer=True)
    _refuser_le_jeu(conn, collection_id=collection_id)    # COL-4 : personne n'y entre
    _refuser_le_bac_a_sable(conn, _MOTIF_BAC_ACCES, collection_id=collection_id)
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
        "SELECT niveau, exporter FROM collection_acces WHERE collection_id = ? "
        "AND genre = ? AND principal = ?",
        (collection_id, payload.genre, principal)).fetchone()
    # `exporter` absent veut dire « ne pas y toucher » : re-poser un principal pour
    # changer son niveau ne lui retire pas une case qu'on n'a pas mentionnée.
    #
    # Et un `exporter` VRAI qui ne fait que répéter le D'OFFICE n'accorde rien non plus :
    # c'est notre propre dérivation qui nous revient. Le cas mesuré le 2026-09-18 :
    # l'écran lit « exporter: true » sur un propriétaire — vrai, mais dérivé de son niveau —
    # puis le repose en le rétrogradant ; sans cette garde, la base STOCKE un droit que le
    # geste ne demandait pas, et le membre en écriture l'emporte. La garde vaut pour le
    # niveau que nous venons de rendre COMME pour celui qu'on demande, et pour n'importe
    # quel appelant — écran, outil ou requête à la main.
    #
    # Elle ne retire jamais rien : elle laisse le posé tel quel. Un `exporter` FAUX passe
    # (révoquer reste possible), et accorder l'export à qui n'y a pas droit d'office passe
    # aussi. Rétrograder quelqu'un EN LUI LAISSANT l'export reste donc exprimable, en deux
    # gestes : rétrograder, puis accorder — le second n'est plus une dérivation, il est une
    # décision, et c'est précisément la distinction qu'on vient de payer.
    #
    # CE QU'ELLE NE FERME PAS, et c'est écrit plutôt que découvert : le MÊME envoi REJOUÉ
    # après la rétrogradation n'est plus un écho — le niveau rendu entre-temps est devenu
    # `ecriture`, où rien ne s'accorde d'office —, donc il POSE le droit. Un appelant qui
    # réessaie sa requête à l'identique accorde ainsi ce que le premier envoi n'accordait
    # pas. Le serveur ne peut pas distinguer ce second envoi d'une décision ; c'est la
    # moitié ÉCRAN de la réparation qui l'empêche de partir, en cessant d'affirmer un champ
    # que le niveau accordait déjà.
    d_office = ((avant is not None and avant["niveau"] == autorisation.PROPRIETAIRE)
                or payload.niveau == autorisation.PROPRIETAIRE)
    exporter = bool(avant["exporter"]) if avant else False
    if payload.exporter is not None and not (payload.exporter and d_office):
        exporter = bool(payload.exporter)
    conn.execute(
        "INSERT INTO collection_acces (collection_id, genre, principal, niveau, exporter) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(collection_id, genre, principal) "
        "DO UPDATE SET niveau = excluded.niveau, exporter = excluded.exporter",
        (collection_id, payload.genre, principal, payload.niveau, int(exporter)))
    # Qui a ouvert quoi à qui, et quand. La séparation « écrire ≠ partager » se justifie
    # par la TRAÇABILITÉ d'un accès accordé par erreur — sans trace, l'argument ne tenait
    # pas. `cible_id` est la collection : `collection_acces` a une clé composite et pas
    # d'id, et c'est bien la collection dont la liste d'accès change.
    _journaliser_acces(conn, collection_id, "lien",
                       avant={"genre": payload.genre, "principal": principal,
                              "niveau": avant["niveau"],
                              "exporter": bool(avant["exporter"])} if avant else None,
                       apres={"genre": payload.genre, "principal": principal,
                              "niveau": payload.niveau, "exporter": exporter})
    conn.commit()
    return _acces_rendus(conn, collection_id)


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
    _refuser_le_jeu(conn, collection_id=collection_id)
    _refuser_le_bac_a_sable(conn, _MOTIF_BAC_ACCES, collection_id=collection_id)
    ligne = conn.execute(
        "SELECT niveau, exporter FROM collection_acces WHERE collection_id = ? "
        "AND genre = ? AND principal = ?", (collection_id, genre, principal)).fetchone()
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
                              "niveau": ligne["niveau"],
                              "exporter": bool(ligne["exporter"])})
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

    UX-18 — le filtre vit dans `socle._collections_lues_d_albums`, que `GET /api/albums`
    lit aussi pour rendre l'appartenance de tous les albums en une lecture.
    """
    _get_album(conn, portee, album_id)
    lues = _collections_lues_d_albums(conn, portee, [album_id])[album_id]
    return [{**c, "mon_niveau": _niveau_dans(portee, c["id"]),
             "administrable": portee.peut_administrer(c["id"]),
             "exportable": portee.peut_exporter(c["id"])}
            for c in lues]


@router.put("/api/albums/{album_id}/collections/{collection_id}", status_code=201)
def ranger_album(album_id: int, collection_id: int,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Range un album DANS une collection — « + Ranger ici ». C'est REJOINDRE un travail
    (COL-3, tranche 3, D4 sous sa forme stricte, Hugo, 2026-10-17). Idempotent.

    Deux droits d'abord : LIRE la copie (on ne rejoint que ce qu'on voit — 404 sinon) et
    ÉCRIRE dans la collection d'arrivée (404 sinon : on ne dépose pas son travail chez
    quelqu'un d'autre). Puis la règle : le rangement ne TRAVERSE pas les projets (409 qui le
    nomme) ; il est IMMÉDIAT si l'on administre chacune des collections où la copie vit
    (`Portee.clause_rejoindre_directe`) — 201 et la liste de ses collections ; sinon il se
    DEMANDE au propriétaire (`database.DEMANDE_REJOINDRE`), et la route répond 202 avec la
    demande, sans rien ranger. Écrire des deux côtés suffisait jusqu'à la tranche 3 :
    ranger chez soi retirait aux autres la suppression directe (`AUTH-10`) sans qu'ils
    l'aient décidé, et partager un travail est la décision de qui le tient.

    C'est aussi le geste « Rendre à… » du fonds (tranche 2) : joué par une portée totale
    sur une copie gardée, il la rend à une collection de SON projet — écrit sur elle, il
    survit à sa sortie de toute collection. Une copie importée au fonds n'en a pas encore,
    et prend celui de la collection où on la range.
    """
    _get_album(conn, portee, album_id)
    collection = collection_row(conn, collection_id)
    if collection is None or not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    # COL-4 — on ne range rien dans le jeu, et la référence ne se range nulle part.
    _refuser_le_jeu(conn, collection_id=collection_id)
    _refuser_le_jeu(conn, album_id=album_id)
    conflit.verrouiller(conn)
    plan = _plan_rejoindre(conn, portee, album_id, collection_id)
    if plan["etat"] == REFUSE:
        raise HTTPException(409, "Cet album vit dans un autre projet que cette collection : "
                                 "le rangement ne traverse pas les projets.")
    if plan["etat"] == DEMANDE:
        a = conn.execute("SELECT document_id, titre FROM albums WHERE id = ?",
                         (album_id,)).fetchone()
        if a["document_id"] is None:
            raise HTTPException(409, "Cet album n'est la copie d'aucun document : le rejoindre "
                                     "ne peut pas se demander. Signalez-le à un "
                                     "administrateur.")
        qui = ("son propriétaire" if un_proprietaire_tient_toute_la_copie(conn, album_id)
               else "un administrateur")
        if qui == "un administrateur":
            # COL-4 (S3) — dans un bac à sable, aucune demande n'atteint l'administrateur.
            _refuser_le_bac_a_sable(conn, _MOTIF_BAC_PROPRIETAIRE, 403,
                                    collection_id=collection_id)
        if _en_attente_vers(conn, DEMANDE_REJOINDRE, collection_id, a["document_id"],
                            album_id):
            raise HTTPException(409, "Rejoindre ce travail depuis cette collection est déjà "
                                     f"demandé : {qui} y répondra.")
        demande_id = _deposer(conn, portee, DEMANDE_REJOINDRE, collection,
                              projet_de_collection(conn, collection_id), None,
                              [{"document_id": a["document_id"], "album_id": album_id,
                                "titre": a["titre"]}])
        conn.commit()
        # `repondra` : qui y répondra — un propriétaire qui tient toutes les collections de
        # la copie, sinon un administrateur seul (Hugo, 2026-10-17 : le message ne ment pas).
        return JSONResponse(status_code=202,
                            content={"etat": DEMANDE, "demande_id": demande_id,
                                     "repondra": ("proprietaire" if qui == "son propriétaire"
                                                  else "administrateur")})
    # « Rendre à… » joué depuis la fiche du document : `ranger_copie` clôt aussi le retour
    # que le responsable avait demandé pour cette copie (COL-3, écran de la 3a).
    ranger_copie(conn, album_id, collection_id)
    conn.commit()
    return list_collections_album(album_id, conn, portee)


@router.delete("/api/albums/{album_id}/collections/{collection_id}", status_code=204)
def sortir_album(album_id: int, collection_id: int,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    """Supprime un album DE la collection — la première des deux réponses à « supprimer »
    (COL-3, tranche 2). Elle ne détruit rien.

    Ce n'était permis jusqu'à la tranche 2 que si l'album gardait une autre collection : un
    album hors de toute collection ne correspondait à aucune règle (invariant AUTH-2), et
    un 409 le refusait. C'est renversé, par décision de Hugo (2026-10-09, confirmée le
    2026-10-11) : sorti de sa DERNIÈRE collection, l'album est GARDÉ AU FONDS avec son
    travail, que seule une portée totale voit, et un administrateur peut le rendre. Rien ne
    se déverse dans un seau commun : la copie garde son projet, écrit sur elle, et ne
    pourra être rendue qu'à une collection de ce projet.
    """
    _get_album(conn, portee, album_id, ecriture=True)
    if not portee.peut_ecrire(collection_id):
        raise HTTPException(404, f"Collection {collection_id} introuvable")
    _refuser_le_jeu(conn, album_id=album_id)              # COL-4 : la référence reste
    # L'APPARTENANCE d'abord, la contrainte ensuite. Sans ce test, sortir un album d'une
    # collection dont il ne fait pas partie déclenchait le garde-fou du dessous et
    # répondait « c'est la dernière collection de cet album » — une phrase fausse, sur une
    # opération qui n'avait de toute façon rien à défaire.
    if conn.execute("SELECT 1 FROM collection_album WHERE album_id = ? AND collection_id = ?",
                    (album_id, collection_id)).fetchone() is None:
        raise HTTPException(404, "Cet album n'appartient pas à cette collection.")
    # Le projet AVANT de sortir, tant qu'on le lit encore dans cette collection : une copie
    # qui part au fonds l'emporte, sans quoi rien ne refuserait de la rendre à un autre.
    poser_projet_de_copie(conn, album_id)
    conn.execute("DELETE FROM collection_album WHERE collection_id = ? AND album_id = ?",
                 (collection_id, album_id))
    journal.journaliser_emploi(conn, "delien", album_id, collection_id)
    # Partie au fonds : les `rejoindre` qui la visaient se closent — la reprendre relève du
    # retour, que demande son responsable (COL-3, écran de la 3a).
    clore_rejoindre_d_une_copie_au_fonds(conn, album_id)
    conn.commit()
    return Response(status_code=204)
