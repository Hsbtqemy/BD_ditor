"""Traitement par lot en arrière-plan (segmentation / bulles / OCR).

Un « job » traite un ensemble de planches — potentiellement réparties sur
plusieurs albums — en enchaînant les passes demandées. Registre en mémoire +
worker thread (application locale mono-utilisateur ; rien n'est persisté).

Le worker ouvre SA propre connexion SQLite (WAL + busy_timeout gèrent les
écritures concurrentes avec les requêtes du serveur) et committe planche par
planche ; une erreur sur une passe est collectée et n'interrompt pas le lot.

Deux échecs de natures différentes, donc : une PASSE qui rate est collectée et le lot
continue (`termine`, avec des erreurs) ; le LOT qui meurt — les deux lectures SQLite hors
du `try` par passe — s'arrête et le dit (`echec`). Sans cette seconde branche le lot mort
s'annonçait « terminé », ce qu'aucun écran ne pouvait démentir.
"""
from __future__ import annotations

import threading
import traceback

from database import get_connection

PASSES = ("segmenter", "bulles", "ocr")   # ordre canonique d'exécution

_jobs: dict = {}
_lock = threading.Lock()        # protège le registre + le compteur
_run_lock = threading.Lock()    # un seul job s'exécute à la fois
_counter = 0

# Sérialise TOUTE inférence ML — worker de lot ET routes directes (/segmenter,
# /detecter-bulles, /ocr). Les modèles (torch) ne sont pas thread-safe et deux
# inférences simultanées doubleraient la mémoire → risque d'OOM sur petit VPS.
# Sérialise aussi le chargement paresseux des modèles (évite un double-load).
ML_LOCK = threading.Lock()


def _est_verrouillee(conn, planche_id: int) -> bool:
    """Verrou de planche (protège des passes auto). Re-vérifié dans le worker au cas
    où le verrou serait posé APRÈS le lancement du lot (le filtrage principal se fait
    à la création du job)."""
    row = conn.execute("SELECT verrouillee FROM planches WHERE id = ?",
                       (planche_id,)).fetchone()
    return bool(row and row["verrouillee"])


def _apply_pass(conn, passe: str, planche_id: int) -> None:
    # Import paresseux + via le module → mockable en test, et n'impose pas les
    # moteurs ML au chargement. Chaque passe est enveloppée par `journal.passe_ml`
    # (A3) : activité tracée (moteur + version + portée + bilan), régions générées
    # rattachées à leur run (wasGeneratedBy) et événements de création/OCR journalisés.
    import journal
    if passe == "segmenter":
        import pipeline.segmentation as m
        with journal.passe_ml(conn, "segmentation", planche_id, agent="kumiko"):
            m.segment_planche(conn, planche_id)
    elif passe == "bulles":
        import pipeline.bulles as m
        with journal.passe_ml(conn, "bulles", planche_id, agent="yolov8-bulles",
                              version=journal.version_moteur("ultralytics")):
            m.detect_bulles(conn, planche_id)
    elif passe == "ocr":
        import pipeline.ocr as m
        with journal.passe_ml(conn, "ocr", planche_id, agent="easyocr",
                              version=journal.version_moteur("easyocr")):
            m.ocr_planche(conn, planche_id)


def _run(job_id: int) -> None:
    job = _jobs[job_id]
    conn = None
    echec = None
    with _run_lock:                       # jobs traités en file (un à la fois)
        try:
            conn = get_connection()
            for pid in job["planche_ids"]:
                if job["cancel"]:
                    break
                job["current"] = pid
                if _est_verrouillee(conn, pid):     # verrou posé après le lancement
                    job["done"] += 1
                    continue
                for passe in job["passes"]:
                    if job["cancel"]:
                        break
                    try:
                        with ML_LOCK:                    # pas d'inférence ML concurrente
                            _apply_pass(conn, passe, pid)
                        conn.commit()
                    except Exception as exc:              # une passe ratée n'arrête pas le lot
                        conn.rollback()
                        job["errors"].append(
                            {"planche_id": pid, "passe": passe, "erreur": str(exc)})
                job["done"] += 1
        except Exception as exc:
            # Le lot MEURT ici, et c'est le seul endroit qui puisse le dire. Deux lignes
            # échappent au `try` par passe : l'ouverture de la connexion et la relecture du
            # verrou — deux lectures SQLite, donc deux « database is locked » possibles,
            # exactement ce que le WAL et le 409 d'`OperationalError` existent pour gérer
            # ailleurs. Sans cette branche, le `finally` posait « terminé » sur un lot mort
            # à la première planche : 0/3, aucune erreur, une réussite AFFIRMÉE. Un statut
            # bloqué se remarque ; un succès faux ne se remarque jamais.
            echec = exc
            job["errors"].append({"planche_id": job["current"], "passe": None,
                                  "erreur": str(exc)})
            # La trace part sur stderr ICI plutôt qu'en relevant l'exception : « database
            # is locked » ne dit pas OÙ, et l'écran n'affiche que ce message. Relever
            # laisserait mourir un thread daemon sur une exception non traitée — même
            # sortie, plus du bruit dans la suite.
            traceback.print_exc()
        finally:                          # statut TOUJOURS positionné (même si get_connection lève)
            if conn is not None:
                conn.close()
            from pipeline.modeles import liberer_modeles_ml
            with ML_LOCK:                 # CONC-2 : libère HORS inférence (pas de course avec une route ML)
                liberer_modeles_ml()      # rendre la RAM après le lot (modèles déchargés)
            job["current"] = None
            # L'ANNULATION prime : demandée avant la panne, c'est elle qui explique l'arrêt.
            job["status"] = ("annule" if job["cancel"]
                             else "echec" if echec is not None else "termine")


def snapshot(job_id: int):
    j = _jobs.get(job_id)
    if j is None:
        return None
    return {k: j[k] for k in
            ("id", "passes", "total", "done", "current", "errors", "status")}


def all_jobs() -> list:
    return [snapshot(jid) for jid in sorted(_jobs, reverse=True)]


def planches_du_job(job_id: int) -> list:
    """Planches couvertes par un job. Hors de `snapshot` À DESSEIN : c'est une donnée
    d'AUTORISATION (AUTH-2 : à qui ce job appartient-il ?), pas de progression — la
    renvoyer dans le snapshot reviendrait à publier ce qu'on cherche justement à filtrer."""
    j = _jobs.get(job_id)
    return list(j["planche_ids"]) if j else []


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
