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

# Identité de l'utilisateur connecté pour la requête courante (None = local / hors requête).
agent_courant: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_courant", default=None)

# Colonnes « métier » d'une région capturées dans un instantané (hors id/dates/audit).
_REGION_COLS = ("planche_id", "parent_id", "type", "x", "y", "w", "h",
                "ordre", "ocr_texte", "source")


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


def journaliser(conn: sqlite3.Connection, type: str, cible_table: str,
                cible_id: Optional[int], *, avant: Any = None, apres: Any = None,
                agent: Optional[str] = None, agent_type: str = "humain",
                activite_id: Optional[int] = None) -> int:
    """Ajoute un événement au journal (APPEND-ONLY) et renvoie son id.

    `type` ∈ {creation, modification, suppression, validation, lien, delien}. `avant`/`apres`
    = états (dicts) sérialisés en JSON. Pour un acte humain, `agent` défaut = l'agent courant.
    """
    if agent_type == "humain" and agent is None:
        agent = agent_courant.get()
    cur = conn.execute(
        "INSERT INTO evenement (activite_id, type, agent, agent_type, cible_table, "
        "cible_id, avant, apres) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (activite_id, type, agent, agent_type, cible_table, cible_id,
         _js(avant), _js(apres)))
    return cur.lastrowid


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
    + ses enfants (mêmes règles). C'est l'état AVANT capturé à la suppression : le CASCADE
    SQL détruit tout le sous-arbre, mais le journal en garde la trace → substrat de l'undo
    (D1). L'`id` est inclus ici (indispensable pour restaurer la hiérarchie)."""
    base = snapshot_region(conn, region_id)
    if base is None:
        return None
    base["id"] = region_id
    annot = snapshot_annotation(conn, region_id)
    if annot is not None:
        base["annotation"] = annot
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
                           cibles=None) -> dict:
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
    """
    if album_ids:
        ph = ",".join("?" * len(album_ids))
        join = f" JOIN planches p ON p.id = r.planche_id WHERE p.album_id IN ({ph})"
        params = list(album_ids)
    else:
        join, params = "", []

    def cnt(extra: str = "") -> int:
        sql = f"SELECT COUNT(*) FROM regions r{join}"
        if extra:
            sql += (" AND " if join else " WHERE ") + extra
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
    aid = ouvrir_activite(conn, type, agent=agent, agent_type="moteur", version=version,
                          params=params, portee={"planche_id": planche_id})
    try:
        yield aid
    except Exception:
        cloturer_activite(conn, aid, comptes={"echec": True})   # run raté (souvent rollback)
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
