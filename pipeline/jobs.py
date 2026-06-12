"""Traitement par lot en arrière-plan (segmentation / bulles / OCR).

Un « job » traite un ensemble de planches — potentiellement réparties sur
plusieurs albums — en enchaînant les passes demandées. Registre en mémoire +
worker thread (application locale mono-utilisateur ; rien n'est persisté).

Le worker ouvre SA propre connexion SQLite (WAL + busy_timeout gèrent les
écritures concurrentes avec les requêtes du serveur) et committe planche par
planche ; une erreur sur une passe est collectée et n'interrompt pas le lot.
"""
from __future__ import annotations

import threading

from database import get_connection

PASSES = ("segmenter", "bulles", "ocr")   # ordre canonique d'exécution

_jobs: dict = {}
_lock = threading.Lock()        # protège le registre + le compteur
_run_lock = threading.Lock()    # un seul job s'exécute à la fois (modèles ML non thread-safe)
_counter = 0


def _apply_pass(conn, passe: str, planche_id: int) -> None:
    # Import paresseux + via le module → mockable en test, et n'impose pas les
    # moteurs ML au chargement.
    if passe == "segmenter":
        import pipeline.segmentation as m
        m.segment_planche(conn, planche_id)
    elif passe == "bulles":
        import pipeline.bulles as m
        m.detect_bulles(conn, planche_id)
    elif passe == "ocr":
        import pipeline.ocr as m
        m.ocr_planche(conn, planche_id)


def _run(job_id: int) -> None:
    job = _jobs[job_id]
    conn = None
    with _run_lock:                       # jobs traités en file (un à la fois)
        try:
            conn = get_connection()
            for pid in job["planche_ids"]:
                if job["cancel"]:
                    break
                job["current"] = pid
                for passe in job["passes"]:
                    if job["cancel"]:
                        break
                    try:
                        _apply_pass(conn, passe, pid)
                        conn.commit()
                    except Exception as exc:              # une passe ratée n'arrête pas le lot
                        conn.rollback()
                        job["errors"].append(
                            {"planche_id": pid, "passe": passe, "erreur": str(exc)})
                job["done"] += 1
        finally:                          # statut TOUJOURS positionné (même si get_connection lève)
            if conn is not None:
                conn.close()
            job["current"] = None
            job["status"] = "annule" if job["cancel"] else "termine"


def snapshot(job_id: int):
    j = _jobs.get(job_id)
    if j is None:
        return None
    return {k: j[k] for k in
            ("id", "passes", "total", "done", "current", "errors", "status")}


def all_jobs() -> list:
    return [snapshot(jid) for jid in sorted(_jobs, reverse=True)]


def start_job(passes, planche_ids) -> dict:
    global _counter
    with _lock:
        _counter += 1
        jid = _counter
        _jobs[jid] = {
            "id": jid, "passes": list(passes), "planche_ids": list(planche_ids),
            "total": len(planche_ids), "done": 0, "current": None,
            "errors": [], "status": "en_cours", "cancel": False,
        }
    threading.Thread(target=_run, args=(jid,), daemon=True).start()
    return snapshot(jid)


def cancel_job(job_id: int) -> bool:
    j = _jobs.get(job_id)
    if j is None:
        return False
    if j["status"] == "en_cours":
        j["cancel"] = True
    return True
