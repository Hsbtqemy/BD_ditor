"""Journal de provenance / audit (A3, niveau 8) — couche APPEND-ONLY.

Qualifie *qui a produit quoi, quand, comment* sans jamais inverser la base : les tables
métier restent la source de vérité ; ici on enregistre EN PLUS chaque acte, machine ou
humain. Cf. `docs/provenance-audit.md` et `docs/dictionnaire-metadonnees.md` (N8).

Deux grains (cf. `database.py`) :
  • `activite` (PROV *Activity*) — un RUN : une passe ML en lot, ou une session d'édition.
    Porte l'agent (moteur + version, OU humain), les paramètres, la portée, le bilan.
  • `evenement` (PROV act / TEI `change`) — un ACTE atomique IMMUABLE rattaché à son
    activité, portant l'état AVANT/APRÈS. JAMAIS mis à jour ni supprimé (append-only) ;
    il SURVIT à la suppression de sa cible (`cible_id` n'est pas une FK) → c'est ce qui
    rend l'undo (D1) et le calcul de dérive possibles a posteriori.

L'agent HUMAIN de la requête courante est capté par `agent_courant` (contextvar alimentée
par une dépendance FastAPI globale depuis l'en-tête d'auth ; cf. `main.py`). Les passes ML
passent leur agent EXPLICITEMENT (`agent_type='moteur'`). Hors requête (scripts, tests),
`agent_courant` vaut None → agent NULL, ce qui est correct (acte local / anonyme).
"""
from __future__ import annotations

import contextvars
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from pipeline.interruption import PasseInterrompue

# Identité de l'utilisateur connecté pour la requête courante (None = local / hors requête).
agent_courant: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_courant", default=None)

# Colonnes « métier » d'une région capturées dans un instantané (hors id/dates/audit).
# `nom` (v37, ANN-7, G17 ; relecture croisée, constat 5) : le nom libre d'une zone de détail,
# que l'annulation d'une suppression ou d'une modification de région doit rendre comme le
# reste. Les charges ne sortent pas de l'instance (`tools/_commun.COLONNES_EVENEMENT_PUBLIEES`).
_REGION_COLS = ("planche_id", "parent_id", "type", "x", "y", "w", "h",
                "ordre", "ocr_texte", "source", "nom")


def _js(valeur: Any) -> Optional[str]:
    """Sérialise un état en JSON (accents conservés, clés triées → diff stable) ; None→None."""
    if valeur is None:
        return None
    return json.dumps(valeur, ensure_ascii=False, sort_keys=True, default=str)


# --------------------------------------------------------------------------- #
# Activités (runs) et événements (actes)
# --------------------------------------------------------------------------- #
def ouvrir_activite(conn: sqlite3.Connection, type: str, *, agent: Optional[str] = None,
                    agent_type: str = "humain", version: Optional[str] = None,
                    params: Any = None, portee: Any = None) -> int:
    """Ouvre une activité (run) et renvoie son id. `params`/`portee` = dicts (→ JSON).
    Pour un acte humain, `agent` défaut = l'agent de la requête courante."""
    if agent_type == "humain" and agent is None:
        agent = agent_courant.get()
    cur = conn.execute(
        "INSERT INTO activite (type, agent, agent_type, version, params, portee) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (type, agent, agent_type, version, _js(params), _js(portee)))
    return cur.lastrowid


def cloturer_activite(conn: sqlite3.Connection, activite_id: int, *, comptes: Any = None) -> None:
    """Ferme une activité : horodate la fin + enregistre le bilan `comptes` (dict → JSON)."""
    conn.execute("UPDATE activite SET date_fin = datetime('now'), comptes = ? WHERE id = ?",
                 (_js(comptes), activite_id))


def inscrire_run_termine(conn: sqlite3.Connection, type: str, *, agent: Optional[str],
                         agent_type: str, version: Optional[str], params: Any,
                         portee: Any, debut: str, comptes: Any) -> int:
    """Inscrit une activité DÉJÀ CLOSE, et la valide SEULE — après un `rollback`.

    Ouvrir puis clore ne suffit pas quand l'appelant défait la transaction : l'activité
    part avec les données. Mesuré le 2026-09-08 sur les deux chemins — une passe ML ratée
    laissait **zéro** ligne dans `activite`, en lot comme en route directe, alors que le
    succès en laissait une. Le journal ne gardait donc que ce qui avait marché.

    D'où la forme : une seule ligne, complète, insérée APRÈS que les données partielles
    sont parties, et validée pour elle-même. Une seconde connexion aurait été plus propre
    en théorie et fausse en pratique — SQLite n'admet qu'un écrivain, elle aurait attendu
    le verrou que tient justement la transaction qu'on veut défaire.

    `date_debut` est celle de l'ouverture, relue en base pour être au même format et à la
    même horloge que toutes les autres.
    """
    cur = conn.execute(
        "INSERT INTO activite (type, agent, agent_type, version, params, portee, "
        "comptes, date_debut, date_fin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (type, agent, agent_type, version, _js(params), _js(portee), _js(comptes), debut))
    conn.commit()
    return cur.lastrowid


# Les cibles du journal qui désignent une RÉGION par leur `cible_id` (« les actes
# d'annotation ciblent le region_id ») ; `token_correction` la porte dans sa charge
# (`region_id`). `tools/_commun.py` la relit d'ici : une seule liste.
CIBLES_PAR_REGION = ("regions", "annotations", "bulle_locuteur", "personnage_presence",
                     "region_attribut")

# ANN-7, tranche 2, commit 10 (relecture croisée du commit 9, constat 2) — la clé qu'un acte
# sur une région RETENUE de toute sortie (un détail, G17) porte dans sa charge, avec le type
# de la région. Le journal publié se coupe par elle (`tools/_commun.sql_evenement_detail`) :
# un détail né SANS acte — une région recopiée par une copie amorcée, aucun événement n'étant
# recopié (E3) — puis emporté par la cascade de sa case, de sa planche ou de son album ne se
# reconnaissait plus, et les actes sur sa note partaient au dépôt. Écrite au moment de
# l'acte, quand la région existe forcément, elle ne dépend d'aucun chemin de suppression.
CLE_REGION_RETENUE = "region_retenue"


def _marquer_region_retenue(conn: sqlite3.Connection, cible_table: str,
                            cible_id: Optional[int], avant: Any, apres: Any):
    """Les charges de l'acte, marquées de `CLE_REGION_RETENUE` si sa région est d'un type
    retenu (`config.TYPES_REGION_RETENUS`) ; telles quelles sinon. Seules les charges qui
    sont des dicts reçoivent la clé — une charge absente le reste, pour que l'annulation,
    qui lit `avant is None` comme « il n'y avait rien », ne change pas de sens —, et un
    instantané de région qui dit déjà son type n'a rien à redire."""
    if cible_table in CIBLES_PAR_REGION:
        region = cible_id
    elif cible_table == "token_correction":
        region = next((c.get("region_id") for c in (apres, avant)
                       if isinstance(c, dict) and c.get("region_id") is not None), None)
    else:
        return avant, apres
    if region is None:
        return avant, apres
    from config import TYPES_REGION_RETENUS
    row = conn.execute("SELECT type FROM regions WHERE id = ?", (region,)).fetchone()
    if row is None or row[0] not in TYPES_REGION_RETENUS:
        return avant, apres

    def marque(charge):
        if not isinstance(charge, dict):
            return charge
        if cible_table == "regions" and charge.get("type") == row[0]:
            return charge
        return {**charge, CLE_REGION_RETENUE: row[0]}
    return marque(avant), marque(apres)


def journaliser(conn: sqlite3.Connection, type: str, cible_table: str,
                cible_id: Optional[int], *, avant: Any = None, apres: Any = None,
                agent: Optional[str] = None, agent_type: str = "humain",
                activite_id: Optional[int] = None) -> int:
    """Ajoute un événement au journal (APPEND-ONLY) et renvoie son id.

    `type` ∈ {creation, modification, suppression, validation, lien, delien}. `avant`/`apres`
    = états (dicts) sérialisés en JSON. Pour un acte humain, `agent` défaut = l'agent courant.
    Un acte sur un DÉTAIL porte son type dans sa charge (`_marquer_region_retenue`).
    """
    if agent_type == "humain" and agent is None:
        agent = agent_courant.get()
    avant, apres = _marquer_region_retenue(conn, cible_table, cible_id, avant, apres)
    cur = conn.execute(
        "INSERT INTO evenement (activite_id, type, agent, agent_type, cible_table, "
        "cible_id, avant, apres) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (activite_id, type, agent, agent_type, cible_table, cible_id,
         _js(avant), _js(apres)))
    return cur.lastrowid


def journaliser_emploi(conn: sqlite3.Connection, type: str, album_id: int,
                       collection_id: int) -> int:
    """Trace un EMPLOI : un album rangé dans une collection (`lien`), ou qui cesse d'y être
    (`delien`). COL-3, tranche 2 — jusqu'à la v30 ni l'un ni l'autre ne laissait de trace :
    `collection_album` n'a ni date ni auteur, et l'on ne savait plus qui avait fait entrer
    un document dans une étude, ni quand il en était sorti.

    UNE fonction pour toutes les portes — créer un album, le ranger, le retirer, supprimer
    sa collection, le détruire, par les routes comme par `tools/gerer_collections.py`. La
    charge s'écrivait à trois endroits ; trois écritures de la même ligne finissent par ne
    plus dire pareil.

    `cible_id` est le DOCUMENT dont l'album est la copie, pas l'album : le journal survit à
    sa cible, et un identifiant d'album se réattribuait jusqu'à la v30. Un album sans
    document — posé par `INSERT` — garde sa trace sous une cible vide, l'album restant dans
    la charge. La charge porte le NOM de la collection à côté de son identifiant, pour la même raison :
    l'identifiant d'une collection supprimée est rendu à la suivante (mesuré), et l'acte
    désignerait alors une autre étude que celle où il a eu lieu.

    À appeler tant que l'album ET la collection existent encore : avant un `DELETE` qui les
    emporte, pas après. Le rangement se pose en `apres`, le retrait en `avant`.

    Pas plus annulable qu'un accès (`undo._TABLES` est une liste blanche), et RETENU de
    toute sortie (`tools/_commun.CIBLES_RETENUES`)."""
    if type not in ("lien", "delien"):
        raise ValueError(f"emploi : lien ou delien, pas {type!r}")
    document = conn.execute("SELECT document_id FROM albums WHERE id = ?",
                            (album_id,)).fetchone()
    collection = conn.execute("SELECT nom FROM collection WHERE id = ?",
                              (collection_id,)).fetchone()
    charge = {"album_id": album_id, "collection_id": collection_id,
              "collection": collection[0] if collection else None}
    return journaliser(conn, type, "collection_album", document[0] if document else None,
                       **({"apres": charge} if type == "lien" else {"avant": charge}))


def marquer_touche(conn: sqlite3.Connection, region_id: int) -> None:
    """Surface DÉNORMALISÉE : marque une région comme RETOUCHÉE par un humain (le
    pré-remplissage machine a été corrigé) + horodate. Lu à moindre coût par les
    indicateurs de dérive, sans rejouer le journal."""
    conn.execute("UPDATE regions SET touche = 1, date_modification = datetime('now') "
                 "WHERE id = ?", (region_id,))


# --------------------------------------------------------------------------- #
# Instantanés (états avant/après)
# --------------------------------------------------------------------------- #
def snapshot_region(conn: sqlite3.Connection, region_id: int) -> Optional[dict]:
    """État métier courant d'une région (sans id/dates/audit), pour avant/après. None si absente."""
    r = conn.execute(
        f"SELECT {', '.join(_REGION_COLS)} FROM regions WHERE id = ?", (region_id,)).fetchone()
    return dict(r) if r else None


def snapshot_annotation(conn: sqlite3.Connection, region_id: int) -> Optional[dict]:
    """Contenu d'annotation d'une région : {note, tags:[labels]} ; None si aucune annotation."""
    a = conn.execute("SELECT id, note FROM annotations WHERE region_id = ?",
                     (region_id,)).fetchone()
    if a is None:
        return None
    tags = [t["label"] for t in conn.execute(
        "SELECT t.label FROM annotation_tags at JOIN tags t ON t.id = at.tag_id "
        "WHERE at.annotation_id = ? ORDER BY t.label", (a["id"],))]
    return {"note": a["note"], "tags": tags}


def snapshot_region_profond(conn: sqlite3.Connection, region_id: int) -> Optional[dict]:
    """Instantané RÉCURSIF d'une région : ses colonnes métier + son annotation (note+tags)
    + ses liens (locuteur, présence, attributs de case) + ses enfants (mêmes règles). C'est l'état AVANT capturé à la suppression : le CASCADE
    SQL détruit tout le sous-arbre, mais le journal en garde la trace → substrat de l'undo
    (D1). L'`id` est inclus ici (indispensable pour restaurer la hiérarchie)."""
    base = snapshot_region(conn, region_id)
    if base is None:
        return None
    base["id"] = region_id
    annot = snapshot_annotation(conn, region_id)
    if annot is not None:
        base["annotation"] = annot
    # ANN-8 — ce que le CASCADE emporte aussi, et que Ctrl+Z ne rendait pas : le locuteur
    # d'une zone de texte, le personnage montré dans une boîte, la situation d'une case.
    # Des IDENTIFIANTS seulement : l'annulation éprouve chacun avant de le reposer (le
    # personnage, la valeur existent-ils encore, sont-ils ceux d'alors, l'agent les
    # voit-il), et aucun nom, aucun mot du vocabulaire n'entre au journal par ici. Les clés
    # n'apparaissent que si elles portent quelque chose : un instantané sans lien garde la
    # forme qu'il avait.
    for cle, table in (("locuteur", "bulle_locuteur"), ("presence", "personnage_presence")):
        lien = conn.execute(f"SELECT personnage_id FROM {table} WHERE region_id = ?",
                            (region_id,)).fetchone()
        if lien is not None:
            base[cle] = lien["personnage_id"]
    attributs = [row["valeur_id"] for row in conn.execute(
        "SELECT valeur_id FROM region_attribut WHERE region_id = ? ORDER BY valeur_id",
        (region_id,))]
    if attributs:
        base["attributs"] = attributs
    # ANN-7 (R10) — ses relevés (profonds : mots, qualificatifs, doutes et leur fil) et ses
    # passes, que le CASCADE emporte aussi et que Ctrl+Z rend (« Supprimer une région supprime
    # ses relevés, Ctrl+Z les rend »). La charge porte du texte — une précision, des
    # messages — : elle est retenue de toute sortie, comme `ocr_texte`.
    import releves                                 # import paresseux (évite tout cycle)
    rel, passes = releves.instantanes_de_la_region(conn, region_id)
    if rel:
        base["releves"] = rel
    if passes:
        base["passes"] = passes
    enfants = [row["id"] for row in conn.execute(
        "SELECT id FROM regions WHERE parent_id = ? ORDER BY ordre, id", (region_id,))]
    if enfants:
        base["enfants"] = [snapshot_region_profond(conn, e) for e in enfants]
    return base


# --------------------------------------------------------------------------- #
# Passes ML — enveloppe qui journalise sans coupler le code pipeline
# --------------------------------------------------------------------------- #
def version_moteur(distribution: Optional[str]) -> Optional[str]:
    """Version installée d'un paquet (best-effort) pour tracer le moteur ; None si inconnu."""
    if not distribution:
        return None
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version(distribution)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Indicateurs dérivés — la couverture / la dérive lues DEPUIS le journal
# --------------------------------------------------------------------------- #
def indicateurs_provenance(conn: sqlite3.Connection, album_ids=None, *,
                           cibles=None, actes_tus: Optional[str] = None) -> dict:
    """Agrégats DÉRIVÉS de la surface dénormalisée (`activite_id`/`touche`) et du journal :
    quantifient la part machine vs humaine et la DÉRIVE (pré-remplissage machine RETOUCHÉ).

    Le bloc `regions` est SCOPÉ par `album_ids` (export `--collection`) ; les compteurs
    `activites`/`evenements` restent au grain du CORPUS (un run/acte n'appartient pas
    proprement à un album, et l'acte survit à la suppression de sa cible → non re-scopable).

    `cibles` restreint les compteurs d'événements à ces `cible_table`. Un APPELANT le passe,
    et la liste ne vit pas ici : c'est une décision d'EXPORT (`tools/_commun.py`), et
    `journal.py` important `tools/` inverserait le sens des dépendances — les outils lisent
    l'application, jamais l'inverse.

    Sans ce paramètre, un artefact se contredit LUI-MÊME : mesuré le 2026-09-06, le bloc
    `provenance` annonçait 11 événements dans un dépôt dont la table `evenement` en publiait
    7. Un lecteur qui compte les lignes en conclut que l'export a perdu des données — un
    résumé plus large que ce qu'il résume ne se lit pas comme un filtre, mais comme un
    défaut. C'est le même écart que `provenance_export.construire()` refermait de son côté,
    et le refermer là ne suffisait pas.

    `actes_tus` — un fragment SQL sur l'alias `evenement`, VRAI pour un acte que l'artefact
    TAIT alors même que sa table est publiée : aujourd'hui les actes sur un DÉTAIL
    (`tools/_commun.sql_evenement_detail`, ANN-7, tranche 2, commit 10). Fourni par
    l'appelant pour la même raison que `cibles`. Le bloc `regions`, lui, ne compte jamais un
    détail (G17, `database.sql_region_sortante`) : il compte ce qui sort, pour tout appelant.
    """
    from database import sql_region_sortante      # import paresseux (database importe journal)
    sortante = sql_region_sortante("r")
    if album_ids:
        ph = ",".join("?" * len(album_ids))
        join = (f" JOIN planches p ON p.id = r.planche_id WHERE p.album_id IN ({ph}) "
                f"AND {sortante}")
        params = list(album_ids)
    else:
        join, params = f" WHERE {sortante}", []

    def cnt(extra: str = "") -> int:
        sql = f"SELECT COUNT(*) FROM regions r{join}"
        if extra:
            sql += " AND " + extra
        return conn.execute(sql, params).fetchone()[0]

    total = cnt()
    machine = cnt("r.activite_id IS NOT NULL")     # généré par un run (wasGeneratedBy)
    touchees = cnt("r.touche = 1")                 # retouché par un humain
    derive = cnt("r.activite_id IS NOT NULL AND r.touche = 1")   # machine PUIS corrigé
    regions = {
        "total": total, "machine": machine, "humaines": total - machine,
        "touchees": touchees, "derive": derive,
        "taux_touche": round(touchees / total, 4) if total else None,
        "taux_derive": round(derive / machine, 4) if machine else None,
    }
    act = {r["type"]: r["n"] for r in conn.execute(
        "SELECT type, COUNT(*) AS n FROM activite GROUP BY type ORDER BY type")}

    # Le filtre porte aussi sur `premier`/`dernier` : une borne posée par un acte que
    # l'artefact ne publie pas daterait un corpus d'après son administration.
    if cibles is None:
        ou, p_ev = "", []
    else:
        cibles = tuple(sorted(cibles))
        ou = f" WHERE cible_table IN ({','.join('?' * len(cibles))})" if cibles else " WHERE 0"
        p_ev = list(cibles)
    if actes_tus:
        ou += (" AND " if ou else " WHERE ") + f"NOT ({actes_tus})"

    ev_type = {r["type"]: r["n"] for r in conn.execute(
        f"SELECT type, COUNT(*) AS n FROM evenement{ou} GROUP BY type ORDER BY type", p_ev)}
    ev_agent = {r["agent_type"]: r["n"] for r in conn.execute(
        f"SELECT agent_type, COUNT(*) AS n FROM evenement{ou} "
        f"GROUP BY agent_type ORDER BY agent_type", p_ev)}
    bornes = conn.execute(
        f"SELECT MIN(date) AS a, MAX(date) AS b FROM evenement{ou}", p_ev).fetchone()
    return {
        "portee_regions": "collection" if album_ids else "corpus",
        "regions": regions,
        "activites": {"total": sum(act.values()), "par_type": act},
        "evenements": {"total": sum(ev_type.values()), "par_type": ev_type,
                       "par_agent": ev_agent, "premier": bornes["a"], "dernier": bornes["b"]},
    }


@contextmanager
def passe_ml(conn: sqlite3.Connection, type: str, planche_id: int, *, agent: str,
             version: Optional[str] = None, params: Any = None) -> Iterator[int]:
    """Enveloppe une passe ML sur une planche : ouvre l'activité (agent=moteur), exécute le
    bloc, puis DÉDUIT par diff ce qui a changé sur les régions de la planche et journalise —
    régions CRÉÉES (lien `activite_id` wasGeneratedBy + événement `creation`) et OCR MODIFIÉ
    (événement `modification` avant/après). Clôt avec le bilan. Le code pipeline reste
    INTACT (aucun couplage au journal). Les régions machine REMPLACÉES par une re-passe ne
    donnent pas d'événement individuel (bruit ; le travail humain, lui, est préservé par
    SEG-1) mais sont comptées dans le bilan.

    Rend l'`activite_id` (utile si l'appelant veut journaliser d'autres actes du run)."""
    avant = {r["id"]: r["ocr_texte"] for r in conn.execute(
        "SELECT id, ocr_texte FROM regions WHERE planche_id = ?", (planche_id,))}
    portee = {"planche_id": planche_id}
    aid = ouvrir_activite(conn, type, agent=agent, agent_type="moteur", version=version,
                          params=params, portee=portee)
    debut = conn.execute(
        "SELECT date_debut FROM activite WHERE id = ?", (aid,)).fetchone()["date_debut"]

    def _rate(comptes):
        """Un run qui ne s'est pas terminé : on défait les données, on garde la TRACE.

        Le `rollback` est fait ICI plutôt que laissé à l'appelant, et c'est ce qui change
        tout : il emportait l'activité que la ligne suivante venait d'écrire. Les deux
        appelants roulaient déjà en arrière — le worker de lot explicitement, la
        dépendance `db` sur exception —, et aucun n'a d'écriture en attente en entrant
        ici. Le leur laisser n'aurait donc rien préservé, et effaçait tout.

        `comptes` reste MINIMAL, et ce n'est pas de la paresse : cette colonne SORT de
        l'instance (`metadonnees_collection`, `provenance_export`). Y verser le message
        de l'exception enverrait des chemins serveur au dépôt — exactement ce qu'AUTH-1 a
        fermé sur `GET /api/export/json`.
        """
        try:
            conn.rollback()
            inscrire_run_termine(conn, type, agent=agent, agent_type="moteur",
                                 version=version, params=params, portee=portee,
                                 debut=debut, comptes=comptes)
        except Exception:
            # **La tenue du journal ne doit jamais changer l'erreur que l'appelant voit.**
            # `commit()` peut lever un « database is locked » — un lot ML tient le verrou
            # d'écriture, SQLite n'admet qu'un écrivain —, et cette exception REMPLACERAIT
            # celle qui sort du `try` : « Kumiko a échoué (code 1) » deviendrait un 409
            # « réessayer », qui n'a rien à voir. On perd alors la trace, ce qui est le
            # moindre mal : on la voulait pour comprendre l'échec, pas pour le masquer.
            #
            # Trouvé en relecture, une heure après avoir corrigé le MÊME défaut dans le
            # `finally` de `run_kumiko`. Un bloc de réparation qui lève est un piège qui
            # se reforme à chaque fois qu'on en écrit un.
            pass

    try:
        yield aid
    except PasseInterrompue:
        # DEMANDÉE, pas subie. Sans cette branche une annulation entrerait au journal
        # comme une panne, dans une couche append-only où cela ne se corrige plus.
        _rate({"interrompu": True})
        raise
    except Exception:
        _rate({"echec": True})
        raise
    else:
        apres = {r["id"]: r["ocr_texte"] for r in conn.execute(
            "SELECT id, ocr_texte FROM regions WHERE planche_id = ?", (planche_id,))}
        crees = [rid for rid in apres if rid not in avant]
        modifies = [rid for rid in apres if rid in avant and apres[rid] != avant[rid]]
        supprimes = [rid for rid in avant if rid not in apres]
        for rid in crees:
            conn.execute("UPDATE regions SET activite_id = ? WHERE id = ?", (aid, rid))
            journaliser(conn, "creation", "regions", rid,
                        apres=snapshot_region(conn, rid),
                        agent=agent, agent_type="moteur", activite_id=aid)
        for rid in modifies:
            journaliser(conn, "modification", "regions", rid,
                        avant={"ocr_texte": avant[rid]}, apres={"ocr_texte": apres[rid]},
                        agent=agent, agent_type="moteur", activite_id=aid)
        cloturer_activite(conn, aid, comptes={
            "crees": len(crees), "modifies": len(modifies), "remplaces": len(supprimes)})
