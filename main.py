"""BéDéditeur — application FastAPI (routes albums, planches, régions,
annotations, recherche, export).

Lancer :  uvicorn main:app --reload
"""
from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
import time
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Request,
                     UploadFile)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from config import (AUTH_ADMIN_GROUPS, AUTH_LOGOUT_URL, AUTH_PROXY, DATA_DIR,
                    REFERENT_CONTACT, REFERENT_NOM, RELECTURE, ROLES_PLANCHE,
                    STATIC_DIR, STATUTS, TEMPLATES_DIR, TYPES_REGION)
from database import (citations_regions, collection_par_defaut, contributions_album,
                      dimensions_cm, init_db, noms_lisibles, numeros_editoriaux,
                      relecture_planches, reindex_region, unindex_region)
import autorisation
import journal
import sante as sante_moteurs

# ARCH-1 — le socle partagé vit dans `socle.py` ; on le ré-exporte ici parce que deux
# cliquets (autorisation, sorties d'identité) interrogent ces noms SUR `main`, et que
# le découpage ne doit réécrire aucun test.
#
# La liste est TOUT ce que `socle.py` définit, et non ce que ce fichier utilise encore.
# Les deux ensembles coïncidaient, et c'était une coïncidence : dérivée de l'usage, la
# liste rétrécit d'elle-même à chaque bloc extrait, si bien qu'un nom cesserait d'être
# joignable sur `main` le jour où sa dernière route d'ici déménage — sans que rien ne le
# dise. La règle écrite (« main ré-exporte tout ce qui a déménagé ») devient donc la règle
# appliquée. Un nom défini des DEUX côtés serait écrasé en silence par cet import : il n'y
# en a aucun, et l'outil de recalcul s'arrête s'il en apparaît un.
from socle import (  # noqa: F401  (ré-export : `main.X` reste un nom valide)
    AccesIn, AlbumIn, AlbumUpdate, AlignementIn, AnnotationIn, AttributIn, CollectionIn,
    CollectionUpdate, ContributionIn, ContributionRoleIn, DeposerIn, DimensionDomaineIn,
    DimensionIn, DomaineIn, FigureIn, FusionIn, JobIn, LexiqueIn, LocuteurIn, MoveIn,
    PersonnageIn, PersonnageUpdate, PresenceIn, RegionIn, RegionUpdate, RelectureIn,
    RoleIn, SharedocsConnIn, SharedocsImportIn, StatutIn, TagIn, TokenCorrectionIn,
    ValeurIn, ValidationIn, VerrouIn, _BOM, _ETATS_LEXIQUE, _LIBELLE, _NOM_TERME,
    _PARENT_TERME, _ancetres_terme, _annotation_for_region, _attributs_de, _auteur,
    _clause_personnage, _csv_response, _csv_safe, _descendre_portee, _ensure_tags,
    _get_album, _get_dimension, _get_personnage, _get_planche, _get_region, _get_valeur,
    _groupes, _norm_tag, _patch_lexique, _refuser_si_verrouillee, _row, _rows,
    _sans_accents, _validate_parent, db, portee_courante,
)
# ARCH-1 — les domaines sortis de ce fichier. `include_router`, plus bas, les rend
# indiscernables de routes déclarées ici : mêmes chemins, même place dans
# `app.routes`, donc les trois cliquets (autorisation, sorties d'identité, CSP)
# continuent de les voir.
from routes import analyse as _routes_analyse
from routes import annulation as _routes_annulation
from routes import collections as _routes_collections
from routes import figures as _routes_figures
from routes import lexique as _routes_lexique
from routes import personnages as _routes_personnages
from routes import recherche as _routes_recherche

from pipeline.backup import make_backup
from pipeline import jobs
from pipeline import nlp
from pipeline.bulles import BullesError, bulles_available, detect_bulles
from pipeline.ingest import (ingest_image, remove_album_files,
                             remove_planche_files, store_upload)
from pipeline.ocr import OCRError, ocr_available, ocr_planche, region_crop_png
from pipeline.ordering import move_region, reorder_planche
from pipeline.segmentation import KumikoError, kumiko_available, segment_planche
from pipeline import sharedocs
from pipeline.sharedocs import ShareDocsError

# Extensions image acceptées à l'import (Pillow ; PDF non géré pour l'instant).
IMG_EXTS = (".tif", ".tiff", ".jpg", ".jpeg",
            ".jp2", ".j2k", ".jpf", ".jpx", ".jpc", ".j2c",   # JPEG2000 (Pillow/OpenJPEG)
            ".png", ".bmp", ".gif", ".webp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Pré-chauffage NLP optionnel (déconseillé en consultation pure) : évite le
    # gel de la 1re écriture/recherche sur le chargement à froid de spaCy.
    if os.environ.get("BD_NLP_PREWARM", "").lower() in ("1", "true", "yes", "on"):
        nlp.prewarm()
    yield


app = FastAPI(title="BéDéditeur", version="1.0", lifespan=lifespan)


async def _capter_agent(request: Request) -> None:
    """Dépendance GLOBALE (une par requête) : capte l'utilisateur connecté dans le
    contextvar du journal, pour attribuer les actes humains SANS threader `request` dans
    chaque route. ASYNC → s'exécute dans la tâche de la requête, dont le contexte est copié
    vers l'endpoint sync (threadpool) → la valeur y est visible. Cf. journal.agent_courant,
    INFRA-2 (`_auteur`)."""
    journal.agent_courant.set(_auteur(request))


# Appliquée à toutes les routes du routeur principal (les montages StaticFiles sont hors
# routeur → non concernés, ce qui est voulu). `_auteur` est résolu à l'appel (défini plus bas).
app.router.dependencies.append(Depends(_capter_agent))

# APRÈS la ligne ci-dessus, et ce n'est pas un détail de mise en page : `include_router`
# FIGE les dépendances de chaque route au moment de l'inclusion. Inclus plus haut, les
# domaines sortis de ce fichier n'auraient jamais reçu `_capter_agent` — le journal de
# provenance leur attribuerait `NULL`, sans qu'aucun test unitaire ne bronche. C'est un
# audit E2E qui l'a trouvé (accord inter-annotateurs : alice et bob devenaient tous
# deux anonymes, donc zéro re-touche entre auteurs distincts).
#
# Une route incluse est par ailleurs INDISCERNABLE d'une route déclarée plus bas :
# mêmes chemins, même place dans `app.routes` — ce dont dépendent les trois cliquets.
app.include_router(_routes_recherche.router)
app.include_router(_routes_analyse.router)
app.include_router(_routes_figures.router)
app.include_router(_routes_personnages.router)
app.include_router(_routes_annulation.router)
app.include_router(_routes_collections.router)
app.include_router(_routes_lexique.router)


# --------------------------------------------------------------------------- #
# Content-Security-Policy (SEC-2)
# --------------------------------------------------------------------------- #
# DEUX politiques, et c'est une décision : une garde se pose sur la SURFACE qu'elle
# protège, pas sur le serveur entier. Les quatre pages de l'application n'ont aucun script
# inline, aucun `<style>`, aucun `onclick=`, aucune ressource externe — elles peuvent donc
# porter une politique stricte SANS qu'on touche une ligne d'application. `/docs` et
# `/redoc` sont engendrés par FastAPI depuis un CDN : leur imposer la même politique ne les
# sécuriserait pas, ça les casserait. Leur donner la leur, ÉCRITE, vaut mieux que les
# exempter — un chemin sans politique est un chemin qu'il faut se rappeler d'avoir exempté.
#
# `style-src` garde `'unsafe-inline'` pour une raison unique et bornée : dix attributs
# `style="width:…%"` portent des valeurs CALCULÉES (barres, heatmap, jauges d'accord) qui
# ne peuvent pas rejoindre la feuille de style. `style-src-elem` reprend d'une main ce que
# `style-src` donne de l'autre : aucun `<style>` n'existe, donc le canal ÉLÉMENT devient
# strict gratuitement, et seul l'attribut reste ouvert. Un navigateur qui ignore `-elem`
# retombe sur `style-src` : plus permissif, jamais cassé.
#
# `data:` est indispensable dans `img-src` — les gabarits posent `<link rel="icon"
# href="data:,">` pour éviter un 404 sur /favicon.ico.
_CSP_APP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "style-src-elem 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

# Relevé sur les pages ENGENDRÉES, pas supposé (2026-08-31) : Swagger charge son bundle et
# sa CSS depuis jsdelivr plus un `<script>` inline d'amorçage ; ReDoc charge son bundle,
# un `<style>` inline et Google Fonts ; les deux prennent leur favicon sur
# fastapi.tiangolo.com. Ce qui NE bouge pas d'une politique à l'autre est ce qui compte :
# `object-src`, `base-uri` et `frame-ancestors` restent fermés — on relâche ce qu'il faut
# pour que la page vive, pas le principe.
_CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    # MESURÉ, pas supposé : sans lui, `worker-src bloque blob:` depuis
    # redoc.standalone.js:8 — ReDoc rend son schéma dans un worker construit à partir d'un
    # blob. Il a d'abord été posé par intuition ; le retirer pour voir est ce qui l'a
    # justifié. Une directive qu'on ne sait pas justifier n'a rien à faire dans une
    # politique de sécurité, fût-elle inoffensive.
    "worker-src 'self' blob:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

# DÉRIVÉ de l'application, jamais recopié : ces quatre chemins sont configurables au
# constructeur de FastAPI. Une liste en dur ne casserait rien le jour où l'un change —
# `/docs` recevrait simplement la politique stricte et cesserait de s'afficher, sans que
# personne relie la panne à cette ligne. C'est le défaut qu'AUTH-4 avait corrigé ailleurs
# en lisant les groupes d'administration depuis `/api/moi` plutôt qu'une constante jumelle.
_CHEMINS_DOCS = frozenset(
    c for c in (app.docs_url, app.redoc_url, app.openapi_url,
                app.swagger_ui_oauth2_redirect_url) if c)


@app.middleware("http")
async def _csp(request, call_next):
    """Pose la CSP sur TOUTE réponse, pas seulement sur les pages HTML.

    Un en-tête posé partout ne coûte rien sur du JSON et ferme la question de savoir
    quelles réponses sont « des documents » : une route qui renverrait un jour du HTML
    hériterait de la politique par DÉFAUT, au lieu d'en être exemptée par oubli. C'est le
    même raisonnement que l'export qui NOMME ses colonnes (AUTH-1) : ce qu'on ajoute doit
    être couvert par décision, jamais par défaut.
    """
    response = await call_next(request)
    docs = request.url.path in _CHEMINS_DOCS
    response.headers["Content-Security-Policy"] = _CSP_DOCS if docs else _CSP_APP
    return response


@app.middleware("http")
async def _no_cache_assets(request, call_next):
    """Force la revalidation des assets (CSS/JS) et des pages HTML. Sans ça, le
    navigateur intégré d'un IDE (Cursor/VS Code, basé Chromium) peut servir un
    style.css / theme.js PÉRIMÉ tout en chargeant le HTML neuf → bandes non stylées,
    layout cassé, alors que le disque est à jour. ETag/Last-Modified de StaticFiles
    restent honorés (réponse 304 si rien n'a changé) : coût négligeable."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static") or path in ("/", "/recherche", "/corpus", "/exploration"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(sqlite3.OperationalError)
async def _sqlite_operational_handler(request, exc: sqlite3.OperationalError):
    """Contention SQLite (« database is locked », p.ex. une écriture pendant un
    lot ML) → 409 explicite plutôt qu'un 500 brut, pour inviter à réessayer.
    Les autres OperationalError → 500 générique (message interne non divulgué)."""
    msg = str(exc).lower()
    if "lock" in msg or "busy" in msg:
        return JSONResponse(
            status_code=409,
            content={"detail": "Base de données momentanément occupée, réessayez."})
    # Inattendue (ex. SQL malformé) : on masque le détail au client mais on la
    # TRACE côté serveur (sinon ce handler la rendrait silencieuse → indébogable).
    logging.getLogger("bd_annotator").error(
        "OperationalError SQLite inattendue", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Erreur base de données."})


# =========================================================================== #
# Albums & planches
# =========================================================================== #
@app.get("/api/albums")
def list_albums(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    ou, params = portee.clause_album("a.id")
    return _rows(conn.execute(
        f"""SELECT a.*,
                  (SELECT COUNT(*) FROM planches p WHERE p.album_id = a.id)
                      AS nb_planches,
                  (SELECT COUNT(*) FROM regions r JOIN planches p ON p.id = r.planche_id
                     WHERE p.album_id = a.id) AS nb_regions,
                  (SELECT COUNT(*) FROM regions r JOIN planches p ON p.id = r.planche_id
                     WHERE p.album_id = a.id
                       AND TRIM(COALESCE(r.ocr_texte, '')) <> '') AS nb_transcrites,
                  (SELECT COUNT(*) FROM planches p
                     WHERE p.album_id = a.id AND p.validee IS NOT NULL) AS nb_validees
           FROM albums a
           WHERE {ou}
           ORDER BY a.serie IS NULL, a.serie, a.annee, a.titre""", params
    ))


@app.post("/api/albums", status_code=201)
def create_album(album: AlbumIn, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    data = album.model_dump()                       # toutes les colonnes descriptives (dont N0)
    data["titre"] = (data.get("titre") or "").strip()   # B9 : titre requis (comme un tag)
    if not data["titre"]:
        raise HTTPException(422, "Le titre de l'album est requis.")
    # AUTH-2 — un album appartient TOUJOURS à une collection : c'est elle qui porte les
    # droits. Un orphelin ne correspondrait à aucune règle, et il faudrait alors inventer
    # une politique dans le code. Le champ est facultatif à l'API (32 appels existants
    # l'ignorent, et une instance neuve n'a pas encore de collection) mais l'appartenance,
    # elle, n'est jamais facultative : à défaut, la collection de repli.
    cid = data.pop("collection_id", None)
    if cid is not None:
        # Introuvable ET interdite donnent la MÊME réponse : dire « elle existe mais pas
        # pour vous » révélerait l'existence d'études voisines.
        if not portee.peut_ecrire(cid) or conn.execute(
                "SELECT 1 FROM collection WHERE id = ?", (cid,)).fetchone() is None:
            raise HTTPException(404, f"Collection {cid} introuvable")
    else:
        cid = collection_par_defaut(conn)
        # Ici un 403 ne fuit rien : il parle des droits de l'appelant, pas du corpus.
        if not portee.peut_ecrire(cid):
            raise HTTPException(
                403, "Aucune collection ouverte en écriture : précisez `collection_id`, "
                     "ou demandez un accès en écriture.")
    cols = list(data)
    cur = conn.execute(
        f"INSERT INTO albums ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        tuple(data.values()),
    )
    conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                 (cid, cur.lastrowid))
    conn.commit()
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (cur.lastrowid,)))


@app.put("/api/albums/{album_id}")
def update_album(album_id: int, patch: AlbumUpdate,
                 conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id, ecriture=True)
    fields = patch.model_dump(exclude_unset=True)
    if "titre" in fields:                               # B9 : ne pas vider un titre par édition
        fields["titre"] = (fields["titre"] or "").strip()
        if not fields["titre"]:
            raise HTTPException(422, "Le titre de l'album est requis.")
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE albums SET {cols} WHERE id = ?",
                     (*fields.values(), album_id))
        conn.commit()
    return _row(conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)))


@app.delete("/api/albums/{album_id}", status_code=204)
def delete_album(album_id: int, conn: sqlite3.Connection = Depends(db),
                 portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id, ecriture=True)
    # Désindexe les régions du FTS (le CASCADE SQL ne touche pas la table FTS).
    for r in conn.execute(
        "SELECT r.id FROM regions r JOIN planches p ON p.id = r.planche_id "
        "WHERE p.album_id = ?", (album_id,)).fetchall():
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))   # CASCADE planches/regions
    conn.commit()
    remove_album_files(album_id)
    return Response(status_code=204)


@app.delete("/api/planches/{planche_id}", status_code=204)
def delete_planche(planche_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    p = _get_planche(conn, portee, planche_id, ecriture=True)
    for r in conn.execute(
        "SELECT id FROM regions WHERE planche_id = ?", (planche_id,)).fetchall():
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM planches WHERE id = ?", (planche_id,))   # CASCADE regions
    conn.commit()
    remove_planche_files(p["chemin_tiff"], p["chemin_web"])
    return Response(status_code=204)


@app.get("/api/albums/{album_id}/planches")
def album_planches(album_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id)
    planches = _rows(conn.execute(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM regions r WHERE r.planche_id = p.id)
                      AS nb_regions,
                  (SELECT COUNT(*) FROM regions r
                     JOIN annotations an ON an.region_id = r.id
                   WHERE r.planche_id = p.id) AS nb_annotees
           FROM planches p WHERE p.album_id = ? ORDER BY p.numero""",
        (album_id,),
    ))
    nums = numeros_editoriaux(conn, album_id)
    rel = relecture_planches(conn, [p["id"] for p in planches])   # ANN-4 : statut dérivé/forcé
    # AUTH-1 — le NOM de qui détient un verrou. `verrou_par` est consigné depuis la v22 et
    # aucun écran ne le lisait : on voyait « verrouillée le … » sans savoir à qui demander
    # la levée, ce qui est précisément l'information dont on a besoin. Le login reste dans
    # la charge utile : il est stable, et lui seul permet à l'écran de dire « par vous ».
    noms = noms_lisibles(conn, [p["verrou_par"] for p in planches])
    for p in planches:
        p["verrou_par_nom"] = noms.get(p["verrou_par"])
        p["url_web"] = "/" + p["chemin_web"] if p["chemin_web"] else None
        p["numero_editorial"] = nums.get(p["id"])   # None si paratexte (cf. role)
        # Matériel (A6) : dimensions physiques dérivées (px÷dpi), None si résolution absente.
        p["dimensions_cm"] = dimensions_cm(p["largeur_px"], p["hauteur_px"],
                                           p["dpi_x"], p["dpi_y"])
        p["relecture_statut"] = rel.get(p["id"])     # {statut, derive, force, tokens, relus}
    return planches


# Route synchrone (def) : FastAPI l'exécute dans un threadpool, ce qui évite
# de bloquer la boucle d'événements pendant le redimensionnement PIL (lourd
# sur un TIFF 400 dpi). On lit donc l'upload via file.file (API synchrone).
def _allouer_numero(conn, album_id: int, numero: Optional[int]) -> int:
    """Alloue le numéro d'une nouvelle planche AVANT toute écriture de fichier (DB-1).
    Les fichiers master/dérivé sont nommés d'après le numéro : on vérifie donc l'unicité
    en amont, sinon l'écriture écraserait SILENCIEUSEMENT la planche existante de même
    numéro. `numero` explicite déjà pris → 409 ; absent → MAX+1 de l'album. L'index unique
    (album_id, numero) reste le filet en cas de course concurrente résiduelle."""
    if numero is None:
        return conn.execute(
            "SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM planches WHERE album_id = ?",
            (album_id,)).fetchone()["n"]
    if conn.execute("SELECT 1 FROM planches WHERE album_id = ? AND numero = ?",
                    (album_id, numero)).fetchone():
        raise HTTPException(409, f"Le numéro {numero} est déjà pris dans cet album.")
    return numero


@app.post("/api/albums/{album_id}/import", status_code=201)
def import_planche(
    album_id: int,
    file: UploadFile = File(...),
    numero: Optional[int] = Form(None, ge=1),
    conn: sqlite3.Connection = Depends(db),
    portee: autorisation.Portee = Depends(portee_courante),
):
    _get_album(conn, portee, album_id, ecriture=True)
    data = file.file.read()
    if not data:
        raise HTTPException(400, "Fichier vide")
    # Numéro alloué AVANT écriture (DB-1) : un numéro explicite déjà pris → 409, sans
    # écraser les fichiers (master/dérivé nommés d'après lui) de la planche existante.
    numero = _allouer_numero(conn, album_id, numero)
    master = store_upload(album_id, file.filename or "planche.tif", data, numero)
    try:
        planche = ingest_image(conn, album_id, master, numero=numero)
    except sqlite3.IntegrityError:
        master.unlink(missing_ok=True)   # course rare : un concurrent a pris ce numéro
        raise HTTPException(409, f"Numéro {numero} déjà pris (course d'import) — réessayez.")
    except Exception as exc:
        # Pas de master orphelin sur disque si l'ingestion échoue après écriture.
        master.unlink(missing_ok=True)
        raise HTTPException(400, f"Échec de l'ingestion : {exc}")
    conn.commit()
    planche["url_web"] = "/" + planche["chemin_web"]
    return planche


# =========================================================================== #
# Segmentation & régions
# =========================================================================== #
@app.post("/api/planches/{planche_id}/segmenter")
def segmenter(planche_id: int, use_master: bool = False,
              conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    _refuser_si_verrouillee(_get_planche(conn, portee, planche_id, ecriture=True))
    if not kumiko_available():
        raise HTTPException(
            503,
            "Kumiko n'est pas installé. Clonez-le dans lib/kumiko "
            "(git clone https://github.com/njean42/kumiko.git lib/kumiko).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            with journal.passe_ml(conn, "segmentation", planche_id, agent="kumiko",
                                  params={"use_master": use_master}):
                res = segment_planche(conn, planche_id, use_master=use_master)
    except KumikoError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/planches/{planche_id}/detecter-bulles")
def detecter_bulles(planche_id: int, conf: float = 0.3,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    _refuser_si_verrouillee(_get_planche(conn, portee, planche_id, ecriture=True))
    if not bulles_available():
        raise HTTPException(
            503,
            "Détecteur de bulles indisponible. "
            "pip install -r requirements-ocr.txt (ultralytics + huggingface_hub).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            from pipeline.modeles import liberer_modeles_ml
            liberer_modeles_ml(sauf=("bulles", "nlp"))   # CONC-2 : libère l'autre modèle torch (OCR)
            with journal.passe_ml(conn, "bulles", planche_id, agent="yolov8-bulles",
                                  version=journal.version_moteur("ultralytics"),
                                  params={"conf": conf}):
                res = detect_bulles(conn, planche_id, conf=conf)
    except BullesError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/planches/{planche_id}/ocr")
def ocr_route(planche_id: int, only_empty: bool = True,
              conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    _refuser_si_verrouillee(_get_planche(conn, portee, planche_id, ecriture=True))
    if not ocr_available():
        raise HTTPException(
            503,
            "OCR indisponible. pip install -r requirements-ocr.txt (easyocr).",
        )
    try:
        with jobs.ML_LOCK:                       # pas d'inférence ML concurrente (mémoire)
            from pipeline.modeles import liberer_modeles_ml
            liberer_modeles_ml(sauf=("ocr", "nlp"))      # CONC-2 : libère l'autre modèle torch (bulles)
            with journal.passe_ml(conn, "ocr", planche_id, agent="easyocr",
                                  version=journal.version_moteur("easyocr"),
                                  params={"only_empty": only_empty}):
                res = ocr_planche(conn, planche_id, only_empty=only_empty)
    except OCRError as exc:
        raise HTTPException(500, str(exc))
    conn.commit()
    return res


@app.post("/api/ml/liberer")
def liberer_ml(portee: autorisation.Portee = Depends(portee_courante)):
    """Décharge les modèles ML résidents (rend la RAM) — CONC-2. Utile entre deux
    grosses passes sur machine contrainte. Sérialisé par ML_LOCK (jamais pendant une
    inférence). Renvoie la liste des moteurs libérés.

    AUTH-2 — réservé aux ADMINISTRATEURS : le verrou et les modèles sont globaux, et
    décharger pendant qu'une autre équipe travaille rallonge sa passe suivante de plusieurs
    secondes. Ici un 403 ne fuit rien : il parle des droits de l'appelant, pas du corpus.
    En mono-poste (`BD_AUTH_PROXY` absent), la portée est totale — rien ne change.
    """
    if not portee.admin:
        raise HTTPException(403, "Décharger les modèles est un acte d'exploitation, "
                                 "réservé aux administrateurs.")
    from pipeline.modeles import etat_modeles, liberer_modeles_ml
    with jobs.ML_LOCK:
        liberes = liberer_modeles_ml()
    return {"liberes": liberes, "modeles_charges": etat_modeles()}


@app.get("/api/planches/{planche_id}/regions")
def planche_regions(planche_id: int, conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    _get_planche(conn, portee, planche_id)
    regions = _rows(conn.execute(
        """SELECT r.*,
                  EXISTS(SELECT 1 FROM annotations a WHERE a.region_id = r.id)
                      AS annotee,
                  (SELECT COUNT(*) FROM regions c WHERE c.parent_id = r.id)
                      AS nb_enfants
           FROM regions r WHERE r.planche_id = ?
           ORDER BY r.parent_id IS NOT NULL, r.ordre, r.id""",
        (planche_id,),
    ))
    cits = citations_regions(conn, [r["id"] for r in regions])
    for r in regions:
        r["citation"] = cits.get(r["id"])   # {texte, planche, case[, bulle], global, total}
    return regions


@app.post("/api/planches/{planche_id}/regions", status_code=201)
def create_region(planche_id: int, region: RegionIn,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_planche(conn, portee, planche_id, ecriture=True)
    if region.type not in TYPES_REGION:
        raise HTTPException(422, f"Type invalide : {region.type}")
    _validate_parent(conn, planche_id, region.parent_id)
    ordre = region.ordre
    if ordre is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(ordre), 0) + 1 AS n FROM regions "
            "WHERE planche_id = ? AND parent_id IS ?",
            (planche_id, region.parent_id),
        ).fetchone()
        ordre = row["n"]
    cur = conn.execute(
        """INSERT INTO regions
              (planche_id, parent_id, type, x, y, w, h, ordre, ocr_texte, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (planche_id, region.parent_id, region.type, region.x, region.y,
         region.w, region.h, ordre, region.ocr_texte, region.source),
    )
    new_id = cur.lastrowid
    if region.ocr_texte:
        reindex_region(conn, new_id)
    journal.journaliser(conn, "creation", "regions", new_id,
                        apres=journal.snapshot_region(conn, new_id))
    conn.commit()
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (new_id,)))


@app.get("/api/regions/{region_id}/crop")
def region_crop(region_id: int, taille: int = 1600,
                conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """PNG net de la région recadré dans le master.

    `taille` borne la largeur (vignettes de recherche : ~240 ; transcription :
    1600 par défaut). Bornée à [40, 2000].
    """
    _get_region(conn, portee, region_id)
    png = region_crop_png(conn, region_id, max_dim=max(40, min(taille, 2000)))
    if png is None:
        raise HTTPException(404, f"Région {region_id} introuvable")
    return Response(png, media_type="image/png")


@app.put("/api/regions/{region_id}")
def update_region(region_id: int, patch: RegionUpdate,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    existing = _get_region(conn, portee, region_id, ecriture=True)
    fields = patch.model_dump(exclude_unset=True)
    if "type" in fields and fields["type"] not in TYPES_REGION:
        raise HTTPException(422, f"Type invalide : {fields['type']}")
    if "parent_id" in fields:
        _validate_parent(conn, existing["planche_id"], fields["parent_id"], region_id)
    if fields:
        avant = journal.snapshot_region(conn, region_id)
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE regions SET {cols} WHERE id = ?",
                     (*fields.values(), region_id))
        if "ocr_texte" in fields:
            reindex_region(conn, region_id)
        # Retouche humaine d'une zone (souvent un pré-remplissage machine) : événement +
        # surface dénormalisée `touche` (lue par l'indicateur de dérive). marquer_touche
        # après le snapshot `apres` (touche n'est pas une colonne métier → hors instantané).
        journal.journaliser(conn, "modification", "regions", region_id,
                            avant=avant, apres=journal.snapshot_region(conn, region_id))
        journal.marquer_touche(conn, region_id)
        conn.commit()
    return _row(conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)))


@app.delete("/api/regions/{region_id}", status_code=204)
def delete_region(region_id: int, conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)
    # Désindexe la région ET tous ses descendants (le CASCADE SQL les supprime,
    # mais l'index FTS, lui, doit être nettoyé explicitement).
    descendants = conn.execute(
        """WITH RECURSIVE d(id) AS (
               SELECT id FROM regions WHERE id = ?
               UNION
               SELECT r.id FROM regions r JOIN d ON r.parent_id = d.id
           ) SELECT id FROM d""",
        (region_id,),
    ).fetchall()
    # Instantané PROFOND avant destruction (le CASCADE emporte annotation + sous-arbre) :
    # c'est le substrat de l'undo (D1). Le journal survit à la suppression (cible non-FK).
    avant = journal.snapshot_region_profond(conn, region_id)
    for r in descendants:
        unindex_region(conn, r["id"])
    conn.execute("DELETE FROM regions WHERE id = ?", (region_id,))
    journal.journaliser(conn, "suppression", "regions", region_id, avant=avant)
    conn.commit()
    return Response(status_code=204)


@app.post("/api/planches/{planche_id}/reordonner")
def reordonner(planche_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Recalcule l'ordre de lecture (rang per-niveau) de toute la planche."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    res = reorder_planche(conn, planche_id)
    conn.commit()
    return res


@app.post("/api/regions/{region_id}/deplacer")
def deplacer_region(region_id: int, payload: MoveIn,
                    conn: sqlite3.Connection = Depends(db),
                    portee: autorisation.Portee = Depends(portee_courante)):
    """Déplace une région d'un cran parmi ses frères ('haut' ou 'bas')."""
    _get_region(conn, portee, region_id, ecriture=True)
    avant = journal.snapshot_region(conn, region_id)
    try:
        res = move_region(conn, region_id, payload.sens)
    except ValueError as exc:
        raise HTTPException(404 if "introuvable" in str(exc) else 422, str(exc))
    journal.journaliser(conn, "modification", "regions", region_id,
                        avant=avant, apres=journal.snapshot_region(conn, region_id))
    conn.commit()
    return res


# =========================================================================== #
# ShareDocs (WebDAV Huma-Num) — explorateur & import
# =========================================================================== #
# Emplacement unique du mono-poste (SHARE-1). Une chaîne VIDE ne peut jamais être un
# login : `autorisation.auteur` strip et rend None sur vide.
_MONO = ""


def _principal_sharedocs(portee: autorisation.Portee) -> Optional[str]:
    """Sous quelle clé ranger la session ShareDocs de cette requête (SHARE-1).

    · **Mono-poste** (`BD_AUTH_PROXY` faux) : un emplacement unique. Il n'y a qu'une
      personne devant la machine, et le comportement d'avant SHARE-1 est conservé à
      l'identique — c'est une case du chantier, prouvée par un test.
    · **Derrière le proxy** : le login.
    · **Derrière le proxy SANS identité** : `None`, donc AUCUNE session personnelle
      possible. Les ranger toutes sous une même clé y ferait partager un compte Huma-Num
      entre inconnus — précisément le défaut que ce chantier corrige. Il reste le compte
      de l'instance, ou rien : fermeture par défaut, comme la portée vide d'AUTH-2.

    Ce module tranche la question ; `pipeline/sharedocs.py` ne sait rien du proxy et range
    ce qu'on lui donne. Deux implémentations de « qui est là » finiraient par diverger.
    """
    return _MONO if not AUTH_PROXY else portee.utilisateur


def _exiger_admin_instance(portee: autorisation.Portee, geste: str) -> None:
    """Le compte de l'instance n'appartient à personne en particulier (SHARE-1).

    Sans cette garde, la première personne qui clique « déconnexion » en prive tout le
    monde — le même défaut qu'AUTH-2 avait trouvé ailleurs : une action personnelle aux
    effets collectifs, qui marche parfaitement et casse pour les autres.
    """
    if not portee.admin:
        raise HTTPException(
            403, f"{geste} le compte ShareDocs de l'instance est réservé aux "
                 "administrateurs : il sert de repli à tout le monde.")


def _compte_demande(compte: Optional[str]) -> Optional[str]:
    """Valide le compte demandé, ou 422 qui le nomme (SHARE-1).

    Trouvé en relisant : les routes d'écriture testaient `== INSTANCE` et retombaient
    SILENCIEUSEMENT sur le compte personnel pour tout le reste. Un administrateur qui
    écrivait « instace » n'obtenait pas un refus — il ouvrait sa propre session, et
    recevait `{"connecte": true}`, ce qui se lit comme un succès. Il croyait avoir remplacé
    le compte de l'instance, le repli de tout le monde restait inchangé, et rien ne le
    disait. C'était en outre incohérent avec la LECTURE, où `resoudre` refuse déjà un
    compte inconnu : la même faute de frappe donnait un message clair sur `liste` et un
    effet silencieux sur `connexion`.
    """
    if compte is not None and compte not in sharedocs.COMPTES:
        raise HTTPException(
            422, f"Compte ShareDocs inconnu : {compte} "
                 f"({' | '.join(sharedocs.COMPTES)}).")
    return compte


@app.get("/api/sharedocs/etat")
def sharedocs_etat(portee: autorisation.Portee = Depends(portee_courante)):
    """État des sessions (jamais de mot de passe) + pré-remplissage depuis l'env.

    Dit LEQUEL des deux comptes répondrait (`actif`) : sans cela on dépose sans savoir où,
    et la question n'a plus de réponse évidente dès que les deux existent.
    """
    return sharedocs.status(principal=_principal_sharedocs(portee))


@app.post("/api/sharedocs/connexion")
def sharedocs_connexion(payload: SharedocsConnIn,
                        portee: autorisation.Portee = Depends(portee_courante)):
    """Ouvre MA session ShareDocs — ou remplace celle de l'instance (administrateurs)."""
    pwd = payload.password or os.environ.get("BD_SHAREDOCS_PASS", "")
    if _compte_demande(payload.compte) == sharedocs.INSTANCE:
        _exiger_admin_instance(portee, "Remplacer")
        try:
            return {"connecte": True, "compte": sharedocs.INSTANCE,
                    **sharedocs.configurer_instance(payload.url, payload.user, pwd)}
        except ShareDocsError as exc:
            raise HTTPException(400, str(exc))
    try:
        return sharedocs.configurer(payload.url, payload.user, pwd,
                                    principal=_principal_sharedocs(portee))
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/sharedocs/deconnexion")
def sharedocs_deconnexion(compte: Optional[str] = None,
                          portee: autorisation.Portee = Depends(portee_courante)):
    """Ferme MA session. `compte=instance` coupe celle de l'instance (administrateurs)."""
    if _compte_demande(compte) == sharedocs.INSTANCE:
        _exiger_admin_instance(portee, "Couper")
        sharedocs.couper_instance()
        return {"connecte": False, "compte": sharedocs.INSTANCE}
    sharedocs.deconnecter(principal=_principal_sharedocs(portee))
    return {"connecte": False, "compte": sharedocs.PERSO}


@app.get("/api/sharedocs/liste")
def sharedocs_liste(chemin: str = "", compte: Optional[str] = None,
                    portee: autorisation.Portee = Depends(portee_courante)):
    _compte_demande(compte)          # 422 nommé, plutôt que le 400 générique de `resoudre`
    try:
        return sharedocs.list_dir(chemin, principal=_principal_sharedocs(portee),
                                  compte=compte)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/sharedocs/importer")
def sharedocs_importer(payload: SharedocsImportIn,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Télécharge des fichiers ShareDocs et les ingère comme planches.

    Album cible : `album_id` (existant) OU `nouvel_album` (créé). Les fichiers
    non-image sont ignorés (collectés dans `erreurs`) ; un échec sur un fichier
    n'interrompt pas le lot.
    """
    if not payload.chemins:
        raise HTTPException(422, "Aucun fichier sélectionné.")
    # Avant de créer quoi que ce soit : un compte inconnu échouerait sinon FICHIER PAR
    # FICHIER, en autant d'erreurs de téléchargement qu'il y a de chemins — et la vraie
    # cause, un mot mal orthographié, ne paraîtrait nulle part.
    _compte_demande(payload.compte)
    created_album = False
    if payload.album_id is not None:
        # AUTH-2 : importer des planches, c'est écrire dans l'album.
        _get_album(conn, portee, payload.album_id, ecriture=True)
        album_id = payload.album_id
    elif payload.nouvel_album and payload.nouvel_album.strip():
        # Même invariant qu'à la création d'album : jamais d'orphelin, et il faut le droit
        # d'écrire dans la collection qui l'accueille.
        cid = collection_par_defaut(conn)
        if not portee.peut_ecrire(cid):
            raise HTTPException(
                403, "Aucune collection ouverte en écriture : créez l'album depuis la "
                     "Bibliothèque en précisant sa collection, puis importez dedans.")
        cur = conn.execute("INSERT INTO albums (titre) VALUES (?)",
                           (payload.nouvel_album.strip(),))
        album_id = cur.lastrowid
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (cid, album_id))
        created_album = True
    else:
        raise HTTPException(422, "Album cible manquant (album_id ou nouvel_album).")

    importes, erreurs = [], []
    for chemin in payload.chemins:
        nom = chemin.rsplit("/", 1)[-1]
        if os.path.splitext(nom)[1].lower() not in IMG_EXTS:
            erreurs.append({"chemin": chemin, "erreur": "type non géré (image attendue)"})
            continue
        master = None
        try:
            t0 = time.perf_counter()
            data = sharedocs.download(
                chemin, principal=_principal_sharedocs(portee), compte=payload.compte)
            if not data:
                raise ShareDocsError("fichier vide")
            t_dl = time.perf_counter() - t0
            numero = _allouer_numero(conn, album_id, None)   # auto (MAX+1) ; index unique = filet
            master = store_upload(album_id, nom, data, numero)
            t1 = time.perf_counter()
            planche = ingest_image(conn, album_id, master, numero=numero)
            t_ing = time.perf_counter() - t1
            planche["url_web"] = "/" + planche["chemin_web"]
            importes.append(planche)
            # Segmentation best-effort : un échec ici ne doit JAMAIS invalider
            # un import déjà réussi (la planche est déjà ingérée et comptée).
            t_seg = 0.0
            if payload.segmenter and kumiko_available():
                t2 = time.perf_counter()
                try:
                    with jobs.ML_LOCK:               # cohérent : pas de ML concurrent
                        res_seg = segment_planche(conn, planche["id"])
                    # L'EFFECTIF, pas « segmentee » en dur : depuis B6 la segmentation ne
                    # fait plus reculer le statut, si bien qu'écrire la constante ferait
                    # mentir la réponse d'import sur une planche déjà avancée. Le mensonge
                    # serait invisible — la base, elle, aurait raison.
                    planche["statut"] = res_seg["statut"]
                except Exception as exc:
                    # Best-effort, mais PAS muet. Ce `pass` a avalé, le 2026-08-31, un
                    # `TypeError` introduit par ce commit même : la seule trace était un
                    # statut resté `importee`, qu'on attribue naturellement à la
                    # segmentation plutôt qu'à un bug. Un import qui perd sa segmentation
                    # sans rien dire est la même faute que le lot qui s'annonçait terminé
                    # (CONC-2) — se taire n'est pas être robuste.
                    print(f"[import] segmentation ignorée pour {nom} : "
                          f"{type(exc).__name__}: {exc}")
                t_seg = time.perf_counter() - t2
            # Chronométrage par phase (diagnostic de la vitesse d'import).
            print(f"[import-timing] {nom} : download={t_dl:.2f}s "
                  f"derive={t_ing:.2f}s segment={t_seg:.2f}s "
                  f"total={t_dl + t_ing + t_seg:.2f}s "
                  f"taille={len(data) / 1e6:.1f}Mo", flush=True)
        except Exception as exc:   # un fichier en échec ne stoppe pas le lot
            # Pas de master orphelin sur disque si l'ingestion a échoué après écriture.
            if master is not None:
                master.unlink(missing_ok=True)
            erreurs.append({"chemin": chemin, "erreur": str(exc)})
    if created_album and not importes:
        # rien d'importé : ne pas laisser un album vide orphelin
        conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
    conn.commit()
    return {"album_id": album_id, "importes": importes, "erreurs": erreurs}


# =========================================================================== #
# Sauvegarde / archivage de la base
# =========================================================================== #
def _faire_sauvegarde():
    """`make_backup` avec garde (B8) : une OperationalError (base occupée) file au handler
    global (→ 409 « réessayez ») ; toute autre erreur (disque plein, chemin…) → 503 propre
    + trace serveur, au lieu d'un 500 brut."""
    try:
        return make_backup()
    except sqlite3.OperationalError:
        raise                                        # handler global : 409 si « locked/busy »
    except Exception as exc:
        logging.getLogger("bd_annotator").error("Échec de sauvegarde", exc_info=exc)
        raise HTTPException(503, "Sauvegarde impossible pour le moment (réessayez).")


def _exiger_admin_sauvegarde(portee: autorisation.Portee) -> None:
    """La sauvegarde déverse la base ENTIÈRE — tout le texte, toutes collections
    confondues. Elle est réservée aux administrateurs depuis DROIT-1.

    L'arbitrage du 2026-08-27 la laissait ouverte à tout compte, et portait sa propre
    CONDITION DE RÉOUVERTURE : « dès que l'instance accueille quelqu'un qui n'a pas le
    droit de tout voir — un partenaire extérieur, un tiering de droits effectif (DROIT-1),
    un corpus sous embargo — cette décision se rejoue. » Elle vient de se déclencher.

    L'argument d'origine tient toujours : une sauvegarde partielle ne restaure pas une
    instance, et le nom deviendrait trompeur. On ne la scope donc PAS — elle reste
    entière, et change de public. Sauvegarder est un geste d'exploitation, pas de
    recherche : le restreindre ne retire rien à personne qui en avait l'usage.

    Le mono-poste garde la sienne (`portee.tout`) : sans proxy, il n'y a personne à qui
    la refuser.
    """
    if not portee.admin:
        raise HTTPException(403, "La sauvegarde déverse la base entière, toutes "
                                 "collections confondues : elle est réservée aux "
                                 "administrateurs de l'instance.")


@app.get("/api/sauvegarde")
def telecharger_sauvegarde(portee: autorisation.Portee = Depends(portee_courante)):
    """Télécharge un snapshot cohérent de la base (zip horodaté). Administrateurs seuls."""
    _exiger_admin_sauvegarde(portee)
    name, data = _faire_sauvegarde()
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/sharedocs/deposer-sauvegarde")
def deposer_sauvegarde(payload: DeposerIn,
                       conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    """Dépose une sauvegarde de la base dans un dossier ShareDocs (PUT WebDAV).

    Même garde que le téléchargement, et pour une raison de plus : l'application ne
    contrôle pas le partage du dossier d'arrivée.

    Ce n'est PAS le régime de diffusion qui l'impose (précision du 2026-08-28) : ShareDocs
    est du stockage, pas une audience — les ressources y vivent sans question de droits, et
    y déposer n'est pas publier. La frontière de DROIT-1 passe entre l'instance et le
    DÉPÔT (Nakala), pas entre l'instance et son disque distant. La garde reste, mais elle
    tient à ce que sauvegarder est un geste d'exploitation, et à qui peut lire le dossier
    d'arrivée."""
    _exiger_admin_sauvegarde(portee)
    name, data = _faire_sauvegarde()
    folder = payload.dossier.strip("/")
    chemin = f"{folder}/{name}" if folder else name
    try:
        depot = sharedocs.upload(chemin, data,
                                 principal=_principal_sharedocs(portee),
                                 compte=payload.compte)
    except ShareDocsError as exc:
        raise HTTPException(400, str(exc))

    # SHARE-1 — le dépôt est un ACTE, et il ne laissait aucune trace : rien ne disait qui
    # avait déposé quoi, ni sous quel compte. L'événement distingue les DEUX faits — la
    # personne qui a cliqué (l'agent, capté par la dépendance globale) et le compte
    # Huma-Num employé — parce qu'ils cessent d'être le même dès qu'il y a deux comptes
    # possibles. `cible_table='sharedocs'` n'est pas une table du schéma, et c'est déjà le
    # contrat du journal (`cible_id` n'est pas une FK) ; l'undo ne le voit pas, sa liste
    # blanche de tables ne le contient pas.
    journal.journaliser(conn, "creation", "sharedocs", None,
                        apres={"chemin": chemin, "taille": len(data),
                               "compte": depot["compte"], "compte_user": depot["user"]})
    conn.commit()
    return {"depose": chemin, "taille": len(data),
            "compte": depot["compte"], "compte_user": depot["user"]}


@app.patch("/api/planches/{planche_id}/statut")
def update_statut(planche_id: int, payload: StatutIn,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    _get_planche(conn, portee, planche_id, ecriture=True)
    # AUCUN ordre de transition n'est validé ici, et c'est une DÉCISION (B6, AUDIT-1) :
    # la machine ne recule jamais (`database.avancer_statut`), l'humain le peut. Une passe
    # automatique n'a pas d'intention ; quelqu'un qui appelle cette route en a une, y
    # compris pour réparer une erreur — et `statut` ne commande RIEN dans l'application,
    # il nourrit la barre d'avancement. Interdire le retour coincerait une planche mal
    # marquée sans rien protéger. On ne valide donc que l'APPARTENANCE à `STATUTS`.
    if payload.statut not in STATUTS:
        raise HTTPException(422, f"Statut invalide : {payload.statut}")
    conn.execute("UPDATE planches SET statut = ? WHERE id = ?",
                 (payload.statut, planche_id))
    conn.commit()
    return _get_planche(conn, portee, planche_id, ecriture=True)


@app.patch("/api/planches/{planche_id}/relecture")
def update_relecture(planche_id: int, payload: RelectureIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    """Force (ou libère) le statut de RELECTURE grammaticale d'une planche (ANN-4).
    `relecture=null` → revient au DÉRIVÉ (provenances de tokens) ; sinon override contrôlé.
    Cf. database.relecture_planches / docs/relecture.md."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.relecture is not None and payload.relecture not in RELECTURE:
        raise HTTPException(422, f"Statut de relecture invalide : {payload.relecture} "
                                 f"({' | '.join(RELECTURE)} | null).")
    conn.execute("UPDATE planches SET relecture = ? WHERE id = ?",
                 (payload.relecture, planche_id))
    conn.commit()
    return {"id": planche_id, "relecture": payload.relecture,
            "relecture_statut": relecture_planches(conn, [planche_id])[planche_id]}


@app.patch("/api/planches/{planche_id}/validation")
def update_validation(planche_id: int, payload: ValidationIn,
                      conn: sqlite3.Connection = Depends(db),
                      portee: autorisation.Portee = Depends(portee_courante)):
    """Marque une planche comme validée (relue/finalisée) ou retire la validation.
    Drapeau humain orthogonal au `statut` du pipeline ; `validee` = horodatage."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.validee:
        conn.execute("UPDATE planches SET validee = datetime('now') WHERE id = ?",
                     (planche_id,))
    else:
        conn.execute("UPDATE planches SET validee = NULL WHERE id = ?", (planche_id,))
    journal.journaliser(conn, "validation", "planches", planche_id,
                        apres={"validee": bool(payload.validee)})
    conn.commit()
    return _get_planche(conn, portee, planche_id, ecriture=True)


@app.patch("/api/planches/{planche_id}/verrou")
def update_verrou(planche_id: int, payload: VerrouIn, request: Request,
                  conn: sqlite3.Connection = Depends(db),
                  portee: autorisation.Portee = Depends(portee_courante)):
    """Verrouille une planche (la protège des passes automatiques en lot) ou la
    déverrouille. Distinct de `validee` (verrou = protection ≠ validation = qualité) ;
    `verrouillee` = horodatage. Cf. docs/correction-grammaticale.md §6."""
    _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.verrouillee:
        # AUTH-1 : on consigne QUI verrouille. À un seul utilisateur la question ne se
        # posait pas ; à plusieurs, un verrou anonyme n'est pas levable en connaissance
        # de cause. Purement informatif — n'importe qui peut toujours déverrouiller.
        conn.execute("UPDATE planches SET verrouillee = datetime('now'), verrou_par = ? "
                     "WHERE id = ?", (_auteur(request), planche_id))
    else:
        conn.execute("UPDATE planches SET verrouillee = NULL, verrou_par = NULL "
                     "WHERE id = ?", (planche_id,))
    conn.commit()
    p = _get_planche(conn, portee, planche_id, ecriture=True)
    # Le nom accompagne le retour, sinon l'écran qui vient de poser le verrou afficherait
    # un login jusqu'au prochain rechargement — une incohérence d'une seconde, mais qui
    # ferait douter du reste.
    p["verrou_par_nom"] = noms_lisibles(conn, [p["verrou_par"]]).get(p["verrou_par"])
    return p


@app.patch("/api/planches/{planche_id}/role")
def update_role(planche_id: int, payload: RoleIn,
                conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Définit le rôle éditorial d'une planche : 'recit' (narrative, numérotée) ou
    'paratexte' (couverture, liminaire, pub… — écartée de la numérotation et du
    décompte de cases citables). Le numéro éditorial est DÉRIVÉ, jamais stocké ;
    on le renvoie ici (recalculé sur tout l'album) car basculer une planche décale
    les suivantes. Cf. docs/numerotation-et-citation.md."""
    planche = _get_planche(conn, portee, planche_id, ecriture=True)
    if payload.role not in ROLES_PLANCHE:
        raise HTTPException(422, f"Rôle invalide : {payload.role}")
    conn.execute("UPDATE planches SET role = ? WHERE id = ?", (payload.role, planche_id))
    conn.commit()
    out = _get_planche(conn, portee, planche_id, ecriture=True)
    out["numero_editorial"] = numeros_editoriaux(conn, planche["album_id"]).get(planche_id)
    return out


# =========================================================================== #
# Annotations & tags
# =========================================================================== #
@app.get("/api/regions/{region_id}/annotation")
def get_annotation(region_id: int, conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id)
    return _annotation_for_region(conn, region_id)


@app.put("/api/regions/{region_id}/annotation")
def put_annotation(region_id: int, payload: AnnotationIn,
                   conn: sqlite3.Connection = Depends(db),
                   portee: autorisation.Portee = Depends(portee_courante)):
    _get_region(conn, portee, region_id, ecriture=True)

    # État avant (note + tags) pour journaliser création / modification / suppression.
    avant_annot = journal.snapshot_annotation(conn, region_id)

    tag_rows = _ensure_tags(conn, payload.tags)
    # Vider une annotation (note vide ET aucun tag) = SUPPRIMER la ligne, pas
    # laisser une coquille vide : sinon elle fausserait le compteur d'annotées,
    # ne serait pas cherchable, et ferait conserver à tort la case à la
    # re-segmentation (préservation du travail humain).
    if not (payload.note or "").strip() and not tag_rows:
        conn.execute("DELETE FROM annotations WHERE region_id = ?", (region_id,))
        reindex_region(conn, region_id)
        if avant_annot is not None:
            # Cible = region_id (STABLE), pas l'id d'annotation (détruit ici) : une annotation
            # supprimée doit rester restaurable par l'undo (D1), comme locuteur/présence.
            journal.journaliser(conn, "suppression", "annotations", region_id,
                                avant=avant_annot)
        conn.commit()
        return _annotation_for_region(conn, region_id)

    # Upsert de l'annotation (region_id est UNIQUE).
    conn.execute(
        """INSERT INTO annotations (region_id, note) VALUES (?, ?)
           ON CONFLICT(region_id) DO UPDATE SET
               note = excluded.note,
               date_modification = datetime('now')""",
        (region_id, payload.note),
    )
    ann_id = conn.execute(
        "SELECT id FROM annotations WHERE region_id = ?", (region_id,)
    ).fetchone()["id"]

    # Remplace l'ensemble des tags.
    conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (ann_id,))
    for t in tag_rows:
        conn.execute(
            "INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) "
            "VALUES (?, ?)", (ann_id, t["id"]),
        )

    # Cible = region_id (stable), pas ann_id (éphémère) → undo (D1) uniforme avec locuteur/présence.
    journal.journaliser(conn, "creation" if avant_annot is None else "modification",
                        "annotations", region_id, avant=avant_annot,
                        apres=journal.snapshot_annotation(conn, region_id))
    reindex_region(conn, region_id)
    conn.commit()
    return _annotation_for_region(conn, region_id)


@app.get("/api/tags")
def list_tags(conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    """Le vocabulaire de tags, avec sa fréquence d'emploi.

    AUTH-2 — deux filtres, pas un. Le premier borne les TERMES visibles (global, ou
    appartenant à une collection qu'on lit : cf. `clause_terme`). Le second borne le
    COMPTE : `frequence` était calculée sur tout le corpus, si bien que le nuage de tags
    disait le volume de travail des autres. Le compter sur les seules régions lisibles est
    du même coup plus JUSTE analytiquement — un nuage doit refléter le sous-corpus qu'on
    regarde, pas la base entière.
    """
    ou_terme, p_terme = portee.clause_terme("t.collection_id")
    ou_album, p_album = portee.clause_album("pl.album_id")
    return _rows(conn.execute(
        f"""SELECT t.id, t.label, t.couleur, t.description,
                  (SELECT COUNT(*)
                     FROM annotation_tags at
                     JOIN annotations an ON an.id = at.annotation_id
                     JOIN regions r      ON r.id = an.region_id
                     JOIN planches pl    ON pl.id = r.planche_id
                    WHERE at.tag_id = t.id AND {ou_album}) AS frequence
           FROM tags t
           WHERE {ou_terme}
           ORDER BY frequence DESC, t.label""", [*p_album, *p_terme]
    ))


@app.post("/api/tags", status_code=201)
def create_tag(tag: TagIn, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — enrichir le vocabulaire suppose de pouvoir écrire QUELQUE PART. Le tag
    créé reste global (`collection_id` NULL, comme avant) : c'est le comportement
    historique, et le rattacher d'office à une collection demanderait de choisir laquelle,
    question sans réponse quand on écrit dans plusieurs. Sans cette garde, une personne en
    lecture seule pourrait polluer un vocabulaire que tout le monde partage."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un terme du vocabulaire demande un droit "
                                 "d'écriture sur au moins une collection.")
    label = _norm_tag(tag.label)
    if not label:
        raise HTTPException(422, "Label de tag vide")
    conn.execute(
        """INSERT INTO tags (label, couleur, description) VALUES (?, ?, ?)
           ON CONFLICT(label) DO UPDATE SET
               couleur = COALESCE(excluded.couleur, tags.couleur),
               description = COALESCE(excluded.description, tags.description)""",
        (label, tag.couleur, tag.description),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM tags WHERE label = ?", (label,)))


# =========================================================================== #
# Contributions & vocabulaire de rôles (N0, v15) — paternité Zotero-like
# =========================================================================== #
_CONTRIB_SQL = ("SELECT c.id, c.nom, c.rang, c.role_id, r.label AS role, "
                "r.bucket, r.marc FROM contribution c "
                "LEFT JOIN contribution_role r ON r.id = c.role_id WHERE c.id = ?")


def _album_existe(conn, portee: autorisation.Portee, album_id, *, ecriture=False):
    """Existence + VISIBILITÉ. Le nom reste, mais depuis AUTH-2 « existe » veut dire
    « existe pour cet appelant » — un album hors portée est introuvable, pas interdit."""
    _get_album(conn, portee, album_id, ecriture=ecriture)


def _role_id(conn, label):
    """Résout un label de rôle → id, en le CRÉANT au besoin (vocabulaire contrôlé-ouvert,
    bucket défaut 'contributor'). None si label vide."""
    label = (label or "").strip()
    if not label:
        return None
    conn.execute("INSERT OR IGNORE INTO contribution_role (label) VALUES (?)", (label,))
    return conn.execute(
        "SELECT id FROM contribution_role WHERE label = ?", (label,)).fetchone()["id"]


@app.get("/api/contribution-roles")
def list_contribution_roles(conn: sqlite3.Connection = Depends(db),
                            portee: autorisation.Portee = Depends(portee_courante)):
    """Vocabulaire de rôles (avec fréquence d'emploi), pour la datalist de saisie.

    AUTH-2 — les LABELS restent visibles de tous : ce vocabulaire est curé depuis les MARC
    Relators (« scénariste », « coloriste »…), il ne dit rien du corpus. La `frequence`,
    elle, compte des contributions d'albums : elle est donc filtrée, sinon elle trahirait
    le volume de catalogage des autres."""
    ou, params = portee.clause_album("c.album_id")
    return _rows(conn.execute(
        f"""SELECT r.id, r.label, r.bucket, r.marc,
                  (SELECT COUNT(*) FROM contribution c
                    WHERE c.role_id = r.id AND {ou}) AS frequence
           FROM contribution_role r
           ORDER BY frequence DESC, r.label""", params))


@app.post("/api/contribution-roles", status_code=201)
def create_contribution_role(role: ContributionRoleIn,
                             conn: sqlite3.Connection = Depends(db),
                             portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — même garde que les tags et les domaines : enrichir un vocabulaire que tout
    le monde partage suppose de pouvoir écrire quelque part."""
    if not portee.peut_ecrire_quelque_part():
        raise HTTPException(403, "Créer un rôle demande un droit d'écriture sur au moins "
                                 "une collection.")
    label = role.label.strip()
    if not label:
        raise HTTPException(422, "Label de rôle vide")
    # bucket None si non/ mal fourni → défaut 'contributor' à la CRÉATION seulement ;
    # sur conflit, on ne clobbe PAS un bucket existant (COALESCE), symétrique de `marc`.
    bucket = role.bucket if role.bucket in ("creator", "contributor") else None
    conn.execute(
        """INSERT INTO contribution_role (label, bucket, marc)
           VALUES (?, COALESCE(?, 'contributor'), ?)
           ON CONFLICT(label) DO UPDATE SET
               bucket = COALESCE(?, contribution_role.bucket),
               marc = COALESCE(excluded.marc, contribution_role.marc)""",
        (label, bucket, role.marc, bucket))
    conn.commit()
    return _row(conn.execute("SELECT * FROM contribution_role WHERE label = ?", (label,)))


@app.get("/api/albums/{album_id}/contributions")
def list_contributions(album_id: int, conn: sqlite3.Connection = Depends(db),
                       portee: autorisation.Portee = Depends(portee_courante)):
    _album_existe(conn, portee, album_id)
    return contributions_album(conn, album_id)


@app.post("/api/albums/{album_id}/contributions", status_code=201)
def add_contribution(album_id: int, contrib: ContributionIn,
                     conn: sqlite3.Connection = Depends(db),
                     portee: autorisation.Portee = Depends(portee_courante)):
    _album_existe(conn, portee, album_id, ecriture=True)
    nom = contrib.nom.strip()
    if not nom:
        raise HTTPException(422, "Nom de contributeur vide")
    role_id = _role_id(conn, contrib.role)
    rang = conn.execute("SELECT COALESCE(MAX(rang), 0) + 1 AS n FROM contribution "
                        "WHERE album_id = ?", (album_id,)).fetchone()["n"]
    cur = conn.execute(
        "INSERT INTO contribution (album_id, nom, role_id, rang) VALUES (?, ?, ?, ?)",
        (album_id, nom, role_id, rang))
    conn.commit()
    return _row(conn.execute(_CONTRIB_SQL, (cur.lastrowid,)))


@app.delete("/api/contributions/{contribution_id}", status_code=204)
def delete_contribution(contribution_id: int, conn: sqlite3.Connection = Depends(db),
                        portee: autorisation.Portee = Depends(portee_courante)):
    """AUTH-2 — une contribution est la paternité d'un ALBUM : elle s'autorise par lui.
    La route ne recevant que l'id de la contribution, on remonte à son album."""
    ou, params = portee.clause_album("c.album_id", ecriture=True)
    if conn.execute(f"SELECT 1 FROM contribution c WHERE c.id = ? AND {ou}",
                    (contribution_id, *params)).fetchone() is None:
        raise HTTPException(404, f"Contribution {contribution_id} introuvable")
    conn.execute("DELETE FROM contribution WHERE id = ?", (contribution_id,))
    conn.commit()
    return Response(status_code=204)


# =========================================================================== #
# Jobs : traitement par lot en arrière-plan (segmentation / bulles / OCR)
# =========================================================================== #
@app.post("/api/jobs", status_code=201)
def creer_job(payload: JobIn, conn: sqlite3.Connection = Depends(db),
              portee: autorisation.Portee = Depends(portee_courante)):
    """Lance un lot sur l'ensemble des planches d'albums et/ou planches données."""
    passes = [p for p in jobs.PASSES if p in payload.passes]   # ordre canonique
    if not passes:
        raise HTTPException(422, "Aucune passe valide (segmenter / bulles / ocr).")
    avail = {"segmenter": kumiko_available(), "bulles": bulles_available(),
             "ocr": ocr_available()}
    manquants = [p for p in passes if not avail[p]]
    if manquants:
        raise HTTPException(503, f"Moteur(s) indisponible(s) : {', '.join(manquants)}.")

    # AUTH-2 — un lot MODIFIE les régions : il faut le droit d'écrire sur chaque planche.
    # On filtre plutôt que de refuser en bloc : demander « tout l'album 3 » quand on n'en
    # voit qu'une partie doit traiter cette partie, pas échouer en révélant le reste.
    ou, pparams = portee.clause_album("planches.album_id", ecriture=True)
    pids = set()
    if payload.planche_ids:
        inscriptibles = {r[0] for r in conn.execute(
            f"SELECT id FROM planches WHERE {ou}", pparams)}
        pids = inscriptibles & set(payload.planche_ids)
    for aid in payload.album_ids:
        pids.update(r["id"] for r in conn.execute(
            f"SELECT id FROM planches WHERE album_id = ? AND {ou}",
            (aid, *pparams)).fetchall())
    valid, verrouillees = [], 0
    if pids:
        ph = ",".join("?" * len(pids))
        rows = conn.execute(
            f"SELECT id, verrouillee FROM planches WHERE id IN ({ph}) "
            f"ORDER BY album_id, numero", tuple(pids)).fetchall()
        valid = [r["id"] for r in rows if not r["verrouillee"]]      # 🔒 ignorées
        verrouillees = sum(1 for r in rows if r["verrouillee"])
    if not valid:
        raise HTTPException(422, "Aucune planche à traiter"
                            + (f" ({verrouillees} verrouillée(s))." if verrouillees else "."))
    job = jobs.start_job(passes, valid)
    job["verrouillees_ignorees"] = verrouillees   # signalé, jamais en silence
    return job


def _planches_autorisees(conn, portee: autorisation.Portee,
                         *, ecriture: bool = False) -> Optional[set]:
    """Ids des planches visibles (ou modifiables si `ecriture`). None = toutes (portée
    totale), pour ne pas matérialiser un corpus entier à chaque appel."""
    if portee.tout:
        return None
    ou, params = portee.clause_album("p.album_id", ecriture=ecriture)
    return {r[0] for r in conn.execute(f"SELECT p.id FROM planches p WHERE {ou}", params)}


def _job_visible(conn, portee: autorisation.Portee, job_id: int,
                 *, ecriture: bool = False) -> bool:
    """Un job n'est visible que si TOUTES ses planches le sont.

    Le sous-ensemble strict, et pas l'intersection : un lot à cheval sur une collection
    autorisée et une autre révélerait, par son total et sa progression, qu'un travail
    existe ailleurs. Conséquence assumée : un lot lancé par un administrateur sur tout
    le corpus n'apparaît qu'à lui.
    """
    autorisees = _planches_autorisees(conn, portee, ecriture=ecriture)
    if autorisees is None:
        return True
    return set(jobs.planches_du_job(job_id)) <= autorisees


@app.get("/api/jobs")
def lister_jobs(conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    """Les lots en cours — filtrés : la progression d'un lot cite des planches, donc
    des albums, donc l'existence d'études qu'on ne devrait pas connaître."""
    return [s for s in jobs.all_jobs() if _job_visible(conn, portee, s["id"])]


@app.get("/api/jobs/{job_id}")
def etat_job(job_id: int, conn: sqlite3.Connection = Depends(db),
             portee: autorisation.Portee = Depends(portee_courante)):
    snap = jobs.snapshot(job_id)
    if snap is None or not _job_visible(conn, portee, job_id):
        raise HTTPException(404, f"Job {job_id} introuvable")
    return snap


@app.post("/api/jobs/{job_id}/annuler")
def annuler_job(job_id: int, conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    # Annuler un lot INTERROMPT un traitement : c'est une écriture, pas une lecture.
    # Un droit de lecture seule permettrait sinon de saborder la passe d'un collègue.
    if not _job_visible(conn, portee, job_id, ecriture=True):
        raise HTTPException(404, f"Job {job_id} introuvable")
    if not jobs.cancel_job(job_id):
        raise HTTPException(404, f"Job {job_id} introuvable")
    return jobs.snapshot(job_id)


# =========================================================================== #
# Export
# =========================================================================== #
def _region_tree(regions: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """Reconstruit l'arbre des régions (par parent_id) avec annotations."""
    by_parent: dict = {}
    for r in regions:
        by_parent.setdefault(r["parent_id"], []).append(r)

    cits = citations_regions(conn, [r["id"] for r in regions])

    def build(parent_id):
        nodes = []
        for r in sorted(by_parent.get(parent_id, []),
                        key=lambda x: (x["ordre"] or 0, x["id"])):
            ann = _annotation_for_region(conn, r["id"])
            nodes.append({
                "id": r["id"], "type": r["type"],
                "citation": cits.get(r["id"]),
                "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"],
                "ordre": r["ordre"], "source": r["source"],
                "ocr_texte": r["ocr_texte"],
                "annotation": {
                    "note": ann["note"],
                    "tags": [t["label"] for t in ann["tags"]],
                } if (ann["note"] or ann["tags"]) else None,
                "enfants": build(r["id"]),
            })
        return nodes

    return build(None)


# Ce que l'export JSON publie, NOMMÉ colonne par colonne (AUTH-1, 2026-08-31).
#
# Il faisait `SELECT *` sur `albums` et `planches`, donc 34 colonnes dont personne n'avait
# décidé la publication : `verrou_par` (qui tient un verrou d'édition, un état de travail
# transitoire, dans un artefact destiné à un entrepôt qui garde ses versions),
# `verrouillee`, et les chemins de fichiers du SERVEUR. Le défaut n'est pas la fuite mais
# le MÉCANISME : une colonne ajoutée à `planches` se publiait toute seule — par défaut et
# non par décision, comme la garde d'interface d'AUTH-4.
#
# `regions` n'y figure pas : `_region_tree` nomme déjà ses champs un à un.
_EXPORT_ALBUM_COLS = (
    "id", "titre", "auteur", "annee", "editeur", "serie", "description", "date_edition",
    "date_originale", "langue", "type_oeuvre", "lieu_edition", "edition_tirage", "isbn",
    "format_physique", "source_numerisation", "date_import")
_EXPORT_PLANCHE_COLS = (
    "id", "album_id", "numero", "role", "largeur_px", "hauteur_px", "dpi_x", "dpi_y",
    "mode", "statut", "date_segmentation", "validee", "relecture")
# Retenues, et pourquoi — le test `test_toute_colonne_exportable_est_classee` exige que
# toute colonne de la table figure ici OU dans la liste publiée : une colonne neuve fait
# échouer la suite au lieu de partir au dépôt.
_EXPORT_PLANCHE_RETENUES = {
    "chemin_tiff": "chemin de fichier sur le SERVEUR — interne, sans valeur descriptive",
    "chemin_web": "idem ; le dérivé se publie par IIIF, pas par un chemin de disque",
    "verrouillee": "état de travail TRANSITOIRE, faux dès la seconde suivante",
    "verrou_par": "qui tient le verrou : une identité, et transitoire de surcroît",
}


def _album_payload(conn: sqlite3.Connection, album_id: int) -> dict:
    album = _row(conn.execute(
        f"SELECT {', '.join(_EXPORT_ALBUM_COLS)} FROM albums WHERE id = ?", (album_id,)))
    if album is None:
        raise HTTPException(404, f"Album {album_id} introuvable")
    planches = _rows(conn.execute(
        f"SELECT {', '.join(_EXPORT_PLANCHE_COLS)} FROM planches "
        "WHERE album_id = ? ORDER BY numero", (album_id,)))
    nums = numeros_editoriaux(conn, album_id)
    for p in planches:
        p["numero_editorial"] = nums.get(p["id"])   # None si paratexte ; `role` déjà présent
        p["dimensions_cm"] = dimensions_cm(p["largeur_px"], p["hauteur_px"],   # matériel (A6)
                                           p["dpi_x"], p["dpi_y"])
        regions = _rows(conn.execute(
            "SELECT * FROM regions WHERE planche_id = ?", (p["id"],)))
        p["regions"] = _region_tree(regions, conn)
    album["planches"] = planches
    return album


@app.get("/api/export/json")
def export_json(album_id: int, conn: sqlite3.Connection = Depends(db),
                portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id)
    album = _album_payload(conn, album_id)
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "regions": "hasPart",
            "enfants": "hasPart",
            "ocr_texte": "text",
            "annotation": "comment",
        },
        "@type": "Book",
        "@id": f"album:{album['id']}",
        **album,
    }


@app.get("/api/export/csv")
def export_csv(album_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    _get_album(conn, portee, album_id)
    rows = _rows(conn.execute(
        """SELECT a.titre AS album, p.numero AS ordre_import, r.id AS region_id,
                  r.type, r.parent_id, r.x, r.y, r.w, r.h, r.ordre, r.source,
                  r.ocr_texte,
                  an.note,
                  (SELECT GROUP_CONCAT(tg.label, '|')
                     FROM annotation_tags at JOIN tags tg ON tg.id = at.tag_id
                    WHERE at.annotation_id = an.id) AS tags
           FROM regions r
           JOIN planches p ON p.id = r.planche_id
           JOIN albums a ON a.id = p.album_id
           LEFT JOIN annotations an ON an.region_id = r.id
           WHERE a.id = ?
           ORDER BY p.numero, r.parent_id IS NOT NULL, r.ordre, r.id""",
        (album_id,),
    ))
    # Deux rôles distincts : `ordre_import` = page PHYSIQUE (position d'import, garde
    # le paratexte groupable) ; `planche` = numéro ÉDITORIAL cité (vide pour le
    # paratexte) ; `citation` = repère « pl·c(·b) ». Cf. docs/numerotation-et-citation.md.
    cits = citations_regions(conn, [r["region_id"] for r in rows])
    for r in rows:
        c = cits.get(r["region_id"]) or {}
        r["planche"] = c["planche"] if c.get("planche") is not None else ""
        r["citation"] = c.get("texte", "")
        for k in ("album", "ocr_texte", "note", "tags"):      # B7 : anti-injection de formule
            r[k] = _csv_safe(r.get(k))
    buf = io.StringIO()
    cols = ["album", "ordre_import", "planche", "citation", "region_id", "type",
            "parent_id", "x", "y", "w", "h", "ordre", "source", "ocr_texte",
            "note", "tags"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return _csv_response(buf.getvalue(), f"album_{album_id}.csv")


TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _tei_el(parent, tag, **attrs):
    el = ET.SubElement(parent, f"{{{TEI_NS}}}{tag}")
    for k, v in attrs.items():
        if v is not None:
            el.set(k, str(v))
    return el


# Caractères interdits par XML 1.0 (hors \t \n \r) : ElementTree les émet bruts,
# produisant un fichier non re-parsable. On les retire du texte libre (OCR / note
# / métadonnées) avant insertion — sinon l'export TEI est silencieusement corrompu.
def _xml_safe(text) -> str:
    """Retire les caracteres interdits par XML 1.0 (garde tab/LF/CR) du
    texte libre : sinon ElementTree produit un export TEI non re-parsable."""
    if not text:
        return ""
    return "".join(
        c for c in text
        if ord(c) in (0x09, 0x0A, 0x0D)
        or 0x20 <= ord(c) <= 0xD7FF
        or 0xE000 <= ord(c) <= 0xFFFD
        or ord(c) >= 0x10000)


@app.get("/api/export/tei")
def export_tei(album_id: int, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    album = _get_album(conn, portee, album_id)

    ET.register_namespace("", TEI_NS)
    root = ET.Element(f"{{{TEI_NS}}}TEI")

    # teiHeader minimal
    header = _tei_el(root, "teiHeader")
    file_desc = _tei_el(header, "fileDesc")
    title_stmt = _tei_el(file_desc, "titleStmt")
    _tei_el(title_stmt, "title").text = _xml_safe(album["titre"])
    if album["auteur"]:
        _tei_el(title_stmt, "author").text = _xml_safe(album["auteur"])
    pub = _tei_el(file_desc, "publicationStmt")
    _tei_el(pub, "publisher").text = _xml_safe(album["editeur"] or "BéDéditeur")
    src = _tei_el(file_desc, "sourceDesc")
    _tei_el(src, "p").text = _xml_safe(
        f"{album['titre']}"
        + (f", {album['serie']}" if album["serie"] else "")
        + (f" ({album['annee']})" if album["annee"] else "")
    )

    facsimile = _tei_el(root, "facsimile")
    planches = _rows(conn.execute(
        "SELECT * FROM planches WHERE album_id = ? ORDER BY numero", (album_id,)))
    nums = numeros_editoriaux(conn, album_id)

    for p in planches:
        surface = _tei_el(facsimile, "surface", ulx="0", uly="0",
                          lrx=p["largeur_px"], lry=p["hauteur_px"])
        surface.set(f"{{{XML_NS}}}id", f"planche_{p['id']}")   # ancre technique stable
        ed = nums.get(p["id"])
        if ed is not None:                 # planche de récit → @n = numéro éditorial cité
            surface.set("n", str(ed))
        else:                              # paratexte (couverture, liminaire…) : hors numérotation
            surface.set("type", "paratexte")
        if p["chemin_web"]:
            _tei_el(surface, "graphic", url="/" + p["chemin_web"])

        regions = _rows(conn.execute(
            "SELECT * FROM regions WHERE planche_id = ?", (p["id"],)))
        by_parent: dict = {}
        for r in regions:
            by_parent.setdefault(r["parent_id"], []).append(r)
        zone_cits = citations_regions(conn, [r["id"] for r in regions])

        def add_zones(container, parent_id):
            for r in sorted(by_parent.get(parent_id, []),
                            key=lambda x: (x["ordre"] or 0, x["id"])):
                zone = _tei_el(container, "zone",
                               ulx=r["x"], uly=r["y"],
                               lrx=(r["x"] or 0) + (r["w"] or 0),
                               lry=(r["y"] or 0) + (r["h"] or 0))
                zone.set(f"{{{XML_NS}}}id", f"zone_{r['id']}")
                zone.set("type", r["type"])
                _c = zone_cits.get(r["id"]) or {}
                if _c.get("bulle") is not None:        # zone citable : c2·b1
                    zone.set("n", f"c{_c['case']}·b{_c['bulle']}")
                elif _c.get("case") is not None:
                    zone.set("n", f"c{_c['case']}")
                if r["ocr_texte"]:
                    _tei_el(zone, "line").text = _xml_safe(r["ocr_texte"])
                ann = _annotation_for_region(conn, r["id"])
                if ann["note"] or ann["tags"]:
                    note = _tei_el(zone, "note")
                    if ann["tags"]:
                        note.set("type", "tags")
                        note.set("ana", _xml_safe(" ".join(t["label"] for t in ann["tags"])))
                    note.text = _xml_safe(ann["note"])
                add_zones(zone, r["id"])

        add_zones(surface, None)

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(
        xml_bytes, media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="album_{album_id}_tei.xml"'},
    )


# =========================================================================== #
# Statut Kumiko + frontend
# =========================================================================== #
@app.get("/api/sante")
def sante(profond: bool = False):
    """État des moteurs. RAPIDE par défaut, PROFOND sur demande (SANTE-1).

    Sans `?profond=1`, on répond comme avant : présence des modules, sans rien importer.
    C'est la voie des SONDES — celle d'un conteneur, celle d'une supervision — et celle
    qu'appelle le panneau 🩺 Moteurs à son ouverture. Elle doit rester instantanée. (Ce
    docstring a longtemps dit « ce que l'UI appelle à chaque chargement de page » : c'était
    faux depuis longtemps, aucun fichier de `static/` ne l'appelait.)

    Avec `?profond=1`, chaque moteur est RÉELLEMENT importé et le rapport dit pourquoi
    quand ça échoue. Coûteux au premier appel (torch se charge, plusieurs secondes et
    quelques centaines de Mo), puis mémorisé. À utiliser pour diagnostiquer une instance
    déployée, où l'on n'a plus d'accès shell — c'est précisément là que le contrôle rapide
    ment : le 2026-08-27 il a annoncé `bulles: true` sur une pile dont le premier
    `import ultralytics` levait une exception. Cf. `sante.py`."""
    from pipeline.modeles import etat_modeles
    rep = dict(sante_moteurs.rapide())
    rep["modeles_charges"] = etat_modeles()          # CONC-2 : modèles résidents en RAM
    if profond:
        rep["profond"] = sante_moteurs.rapport()
    return rep


_VUS_TTL = 3600.0
_vus: dict = {}


def _identite_reprise(ancien_nom, ancien_email, nom, email) -> Optional[tuple]:
    """Les champs d'identité qui ont changé sous un login DÉJÀ connu, ou None (AUTH-7).

    Ne compte qu'un passage d'une valeur renseignée à une AUTRE valeur renseignée. Une
    valeur qui apparaît ou qui disparaît est une variation d'EN-TÊTE — un proxy qui cesse
    d'envoyer `Remote-Name`, ou qui se met à l'envoyer — et non un indice sur la personne ;
    les compter ferait battre la trace à chaque alternance, dans une table append-only.

    Ce que la fonction constate est un CHANGEMENT D'ATTRIBUTS, jamais un changement de
    personne : quelqu'un qui se marie déclenche la même chose que quelqu'un qui succède.
    C'est la vue des comptes qui interprète, et c'est pourquoi l'événement porte les deux
    valeurs plutôt qu'un verdict.
    """
    champs = [(cle, a, b) for cle, a, b in (("nom", ancien_nom, nom),
                                            ("email", ancien_email, email))
              if a and b and a != b]
    if not champs:
        return None
    return ({cle: a for cle, a, _ in champs}, {cle: b for cle, _, b in champs})


def _enregistrer_utilisateur(conn: sqlite3.Connection, request: Request) -> Optional[str]:
    """Crée ou rafraîchit la ligne `utilisateur` de la personne connectée (AUTH-1).

    Renvoie son login, ou None hors proxy. Appelé depuis `/api/moi`, que l'UI sollicite à
    chaque chargement de page : la ligne apparaît donc dès la première visite. Un client
    purement API qui n'appellerait jamais `/api/moi` ne serait pas enregistré — assumé,
    et sans conséquence tant que rien n'exige la ligne."""
    login = _auteur(request)
    if not login:
        return None
    nom = (request.headers.get("Remote-Name") or "").strip() or None
    email = (request.headers.get("Remote-Email") or "").strip() or None
    connu = _vus.get(login)
    if connu is None or connu[:2] != (nom, email) or time.monotonic() - connu[2] > _VUS_TTL:
        # La comparaison se fait contre la BASE et non contre `_vus` : le cache est vide
        # au démarrage du processus, et c'est précisément là qu'un login repris se présente
        # pour la première fois. Un SELECT sur le chemin lent seulement — au plus un par
        # heure et par login (`_VUS_TTL`), la ligne étant ensuite servie par le cache.
        ancien = conn.execute(
            "SELECT nom, email FROM utilisateur WHERE login = ?", (login,)).fetchone()
        reprise = (_identite_reprise(ancien["nom"], ancien["email"], nom, email)
                   if ancien else None)
        conn.execute(
            "INSERT INTO utilisateur (login, nom, email, derniere_vue) "
            "VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(login) DO UPDATE SET nom = excluded.nom, email = excluded.email, "
            "derniere_vue = datetime('now')",
            (login, nom, email))
        if reprise:
            # AUTH-7 — `utilisateur` est un MIROIR : l'UPSERT ci-dessus écrase l'ancien
            # nom, et rien ne disait qu'il avait existé. Or un login se réutilise (tranché
            # le 2026-09-06 : il ne portera pas l'année), et alors `premiere_vue` date le
            # nouvel arrivant de l'arrivée de son prédécesseur — dans l'instrument même
            # dont la règle de suppression dépend.
            #
            # La trace ne peut pas être RECONSTRUITE plus tard : sans elle, l'ancienne
            # valeur est perdue à l'instant de l'écrasement. C'est ce qui la rend urgente
            # alors que la vue qui la lira n'existe pas encore.
            #
            # Elle vaut au-delà de l'administration. Le journal A3 attribue les actes au
            # LOGIN ; si deux personnes l'ont porté, l'export les fond en un seul
            # `annotateur-N` et la chaîne de révision devient fausse. L'événement étant
            # DATÉ, la coupe reste reconstructible — on ne l'applique pas, on cesse de la
            # perdre.
            #
            # `cible_table='utilisateur'`, `cible_id` NULL : `login` est du texte, donc
            # l'identifiant vit dans la charge. Même contrat que `sharedocs` plus haut, et
            # l'undo ne le voit pas — sa liste blanche de tables ne le contient pas.
            journal.journaliser(conn, "modification", "utilisateur", None,
                                avant={"login": login, **reprise[0]},
                                apres={"login": login, **reprise[1]})
        conn.commit()
        _vus[login] = (nom, email, time.monotonic())
    return login


def _referent_instance():
    """Le référent d'instance (AUTH-4), ou None s'il n'est pas déclaré.

    DÉCLARATIF, et c'est écrit plutôt que laissé à découvrir : l'application ne connaît les
    groupes que de la personne qui frappe, à l'instant de sa requête (AUTH-1). Que ce nom
    appartienne encore à `bd-admins` lui est structurellement invérifiable — un référent
    qui a quitté l'équipe reste donc affiché. Le savoir vaut mieux que le constater.
    """
    if not (REFERENT_NOM or REFERENT_CONTACT):
        return None
    return {"nom": REFERENT_NOM or None, "contact": REFERENT_CONTACT or None}


@app.get("/api/moi")
def moi(request: Request, conn: sqlite3.Connection = Depends(db),
        portee: autorisation.Portee = Depends(portee_courante)):
    """Identité de l'utilisateur connecté, sa PORTÉE, et l'URL de déconnexion.

    En local, sans proxy, l'en-tête est absent → `utilisateur` vaut None et l'UI
    n'affiche ni nom ni déconnexion.

    AUTH-2 — le bloc `acces` existe pour une raison d'ergonomie, pas de sécurité : une
    portée vide rend l'application VISUELLEMENT indistinguable d'un corpus vide, et c'est
    la bonne réponse de sécurité (404 partout, rien ne fuit) mais la pire réponse d'usage.
    La personne se croit devant un outil cassé alors qu'il lui manque un droit. On ne
    révèle rien en le disant : le compte est le SIEN, pas celui du corpus.

    Cette route ne consultait pas la portée jusqu'au 2026-08-28, et sa raison écrite était
    qu'elle serait « circulaire » — elle ne l'est pas : `portee_courante` ne dépend que de
    la requête et de la base. Rapporter sa propre portée n'est pas se soumettre à elle.
    """
    utilisateur = _enregistrer_utilisateur(conn, request)
    nom = (request.headers.get("Remote-Name") or "").strip() or utilisateur
    return {"utilisateur": utilisateur, "nom": nom,
            "groupes": _groupes(request),
            "acces": {"total": portee.tout, "admin": portee.admin,
                      "collections": None if portee.tout else len(portee.lecture),
                      "ecriture": None if portee.tout else len(portee.ecriture),
                      # AUTH-4 — les noms des groupes d'administration. Ce ne sont pas des
                      # secrets : ils sont en clair dans `deploy/docker-compose.yml`. Mais
                      # aucune route ne les disait, si bien qu'une personne admise ne
                      # pouvait pas même déduire que le groupe existe — et le savoir ne le
                      # donne pas, l'appartenance venant d'Authelia.
                      #
                      # VIDE en mono-poste, et ce n'est pas une pudeur : sans proxy, aucun
                      # groupe n'est lu (AUTH-1) et personne ne peut appartenir à
                      # `bd-admins`. Le nommer ferait dire à l'écran des accès que « les
                      # administrateurs de l'instance lisent toute collection, sans y
                      # figurer » — en distinguant deux rôles là où il n'y a qu'une
                      # personne, qui a déjà tout. Un nom exact au service d'une phrase
                      # fausse.
                      "groupes_admin": sorted(AUTH_ADMIN_GROUPS) if AUTH_PROXY else [],
                      # Le référent d'INSTANCE : le seul lisible par une portée VIDE, donc
                      # le seul qui serve la personne que le bandeau envoie « demander un
                      # accès » sans dire à qui.
                      "referent": _referent_instance()},
            "deconnexion_url": AUTH_LOGOUT_URL or None}


# Fichiers statiques + images dérivées + shell HTML.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/derivatives/{chemin:path}")
def derivative(chemin: str, conn: sqlite3.Connection = Depends(db),
               portee: autorisation.Portee = Depends(portee_courante)):
    """Image web d'une planche, CLOISONNÉE (AUTH-2).

    C'était un `app.mount("/derivatives", StaticFiles(...))` — et la plus large fuite du
    dépôt, trouvée en relisant plutôt que par un test : un montage n'est pas une route,
    le cliquet de `tests/test_autorisation.py` ne le voyait donc pas. Les chemins sont
    parfaitement devinables (`/derivatives/album_2/planche_0001.jpg`), si bien que tout le
    corpus restait lisible en image quelle que soit la rigueur des routes JSON. Le test
    regarde désormais aussi les montages.

    La base sert d'ALLOWLIST : on ne sert que des fichiers dont le chemin figure dans
    `planches.chemin_web`. Cela autorise et, du même coup, rend toute traversée de
    répertoire impossible — un `..` ne correspond à aucune ligne.
    """
    ou, params = portee.clause_album("planches.album_id")
    row = _row(conn.execute(
        f"SELECT chemin_web FROM planches WHERE chemin_web = ? AND {ou}",
        (f"derivatives/{chemin}", *params)))
    if row is None:
        raise HTTPException(404, "Image introuvable")
    fichier = DATA_DIR / row["chemin_web"]
    if not fichier.is_file():
        raise HTTPException(404, "Image introuvable")
    return FileResponse(str(fichier))


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(str(TEMPLATES_DIR / "index.html"))


@app.get("/recherche", response_class=HTMLResponse)
def recherche_page():
    return FileResponse(str(TEMPLATES_DIR / "recherche.html"))


@app.get("/corpus", response_class=HTMLResponse)
def corpus_page():
    return FileResponse(str(TEMPLATES_DIR / "corpus.html"))


@app.get("/exploration", response_class=HTMLResponse)
def exploration_page():
    return FileResponse(str(TEMPLATES_DIR / "exploration.html"))
