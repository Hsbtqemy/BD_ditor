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

# CONC-1 — le registre vit en RAM et ne perdait jamais rien. Invisible en session courte,
# sensible sur une instance qui tourne des jours (INFRA-1) : chaque lot y laissait une
# entrée pour toujours.
#
# On borne le NOMBRE et non l'ÂGE, et c'est le seul des deux qui tienne la promesse « sa
# taille ne croît plus indéfiniment » : une purge par ancienneté laisse grossir une rafale
# de lots lancés coup sur coup, un plafond non.
#
# Le plafond est LARGE exprès. Ce qu'on borde est une fuite lente, pas une empreinte : cent
# entrées de quelques centaines d'octets ne pèsent rien, et un plafond serré ferait
# disparaître sous les yeux de quelqu'un le lot qu'il vient de regarder.
JOBS_CONSERVES = 100
_STATUTS_TERMINAUX = frozenset(("termine", "echec", "annule"))

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
    """Instantané de tous les lots, du plus récent au plus ancien.

    **Sous `_lock`, et c'est la purge qui l'a rendu nécessaire** (CONC-1). Cette fonction
    lisait le registre sans verrou : elle en tirait la liste des identifiants, puis
    demandait leur instantané un par un. Tant que `_jobs` ne faisait que GRANDIR, seule
    l'insertion pouvait s'y glisser — un `RuntimeError: dictionary changed size during
    iteration`, déjà possible et jamais vu. La purge y ajoute le RETRAIT, et avec lui un
    mode de panne neuf : un identifiant listé, purgé, puis interrogé, dont `snapshot`
    rend `None`. `GET /api/jobs` fait alors `s["id"]` dessus et répond 500.

    Ce n'est pas une course d'école. La Bibliothèque interroge cette route CHAQUE SECONDE
    pendant un lot, et c'est le lancement d'un autre lot — depuis le même écran — qui
    purge. Le poll avale ses erreurs (`catch { return; }`) : rien ne s'afficherait, la
    progression se figerait sans un mot.

    `_purger_registre` n'est appelée que par `start_job`, sous CE verrou. Le tenir ici
    rend le retrait concurrent IMPOSSIBLE plutôt que rattrapé — filtrer les `None` en
    plus serait du code que rien ne peut faire rougir. Corollaire pour la suite :
    `snapshot` ne prend pas `_lock`, et le lui faire prendre suffirait à bloquer ici.
    """
    with _lock:
        return [snapshot(jid) for jid in sorted(_jobs, reverse=True)]


def planches_du_job(job_id: int) -> list | None:
    """Planches couvertes par un job — `None` si le job n'existe pas.

    Hors de `snapshot` À DESSEIN : c'est une donnée d'AUTORISATION (AUTH-2 : à qui ce job
    appartient-il ?), pas de progression — la renvoyer dans le snapshot reviendrait à
    publier ce qu'on cherche justement à filtrer.

    **Le `None` n'est pas une commodité, c'est ce qui ferme un fail-open** (CONC-1). Cette
    fonction rendait `[]` pour un identifiant inconnu, et l'ensemble vide est inclus dans
    n'importe quel autre : un appelant qui teste « planches ⊆ autorisées » approuvait donc
    un job qui n'existe pas. Un job RÉEL porte toujours au moins une planche — la route de
    création refuse par 422 une sélection vide —, si bien que la liste vide ne désignait
    QUE l'inconnu. Les deux cas étaient distinguables et rendus identiques.
    """
    j = _jobs.get(job_id)
    return list(j["planche_ids"]) if j else None


def _purger_registre() -> None:
    """Retire les lots TERMINÉS les plus anciens au-delà de `JOBS_CONSERVES` (CONC-1).

    Appelée sous `_lock`, à la CRÉATION d'un lot : c'est le seul instant où le registre
    grandit, donc le seul où une purge ait quelque chose à faire. Pas de fil de fond pour
    ça — un objet vivant de plus se justifie quand il faut agir en l'absence d'appel, ce
    qui n'est pas le cas ici et l'est pour le TTL du cache de crop.

    **Un lot non terminé n'est JAMAIS purgé**, quel que soit son rang : `en_cours` couvre
    aussi les lots en file derrière `_run_lock`, qui n'ont encore rien fait et dont un
    écran attend la progression.

    Ce que la purge rend routinier — un identifiant qui ne désigne plus rien — était un cas
    rare avant elle. C'est pourquoi `_job_visible` a été durci D'ABORD : il approuvait tout
    job inconnu, la liste vide étant incluse dans n'importe quelle portée.
    """
    finis = [jid for jid in sorted(_jobs) if _jobs[jid]["status"] in _STATUTS_TERMINAUX]
    for jid in finis[:max(0, len(finis) - JOBS_CONSERVES)]:
        del _jobs[jid]


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
        _purger_registre()
    threading.Thread(target=_run, args=(jid,), daemon=True).start()
    return snapshot(jid)


def cancel_job(job_id: int) -> bool:
    j = _jobs.get(job_id)
    if j is None:
        return False
    if j["status"] == "en_cours":
        j["cancel"] = True
    return True
