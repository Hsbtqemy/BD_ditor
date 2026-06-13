# Hébergement & sécurité — notes d'analyse

> Analyse réalisée le 2026-06-13 sur la branche `main` (commit `ede51ad`).
> **État actuel : aucune authentification n'est en place.** C'est un choix
> assumé — l'app a été conçue pour un usage **local, mono-utilisateur**. Une
> couche d'**authentification (accès gated à tout)** est prévue *avant* toute
> exposition sur un VPS. Ce document liste ce qu'il faut savoir, dimensionner et
> corriger avant cette mise en ligne.

## 1. Modèle de concurrence (à comprendre avant tout)

Les routes sont des `def` **synchrones** → FastAPI les exécute dans un
threadpool (~40 threads). Donc, **même en un seul process uvicorn, plusieurs
requêtes s'exécutent réellement en parallèle**, chacune avec sa propre connexion
SQLite (`check_same_thread=False`, `main.py:51-65`).

- **État global au process** : `_jobs` (`pipeline/jobs.py:19`), `_session`
  ShareDocs (`pipeline/sharedocs.py:33`), `_model` YOLO (`pipeline/bulles.py:23`),
  `_reader` EasyOCR (`pipeline/ocr.py:24`), `_crop_cache` (`pipeline/ocr.py:123`).
  → **Mono-process obligatoire.** Interdit de lancer `uvicorn --workers N` /
  gunicorn multi-workers : l'état divergerait (jobs, session, modèles).

- **Faille de thread-safety sur les routes ML directes.** Le worker de lot se
  protège avec `_run_lock` *parce que* « les modèles ML ne sont pas thread-safe »
  (`pipeline/jobs.py:21`). Mais les routes par planche `/ocr`, `/detecter-bulles`,
  `/segmenter` **n'ont aucun verrou** : deux appels concurrents partagent le même
  `_reader`/`_model`. De plus `_get_reader`/`_load_model` font un *check-then-set*
  non atomique (`pipeline/ocr.py:41`, `pipeline/bulles.py:35`) → deux premières
  requêtes simultanées peuvent construire deux Readers (double téléchargement +
  double pic mémoire). Le cache de crop, lui, **est** correctement verrouillé
  (`_crop_lock`, `pipeline/ocr.py:124`).

- **Les inférences ML bloquent des threads du pool** pendant toute leur durée
  (lentes, CPU) → quelques appels ML concurrents peuvent affamer les requêtes
  normales (annotation, recherche).

- **Contention d'écriture SQLite pendant un job.** WAL = N lecteurs + 1 rédacteur.
  Le worker écrit (commit par passe) pendant que l'utilisateur écrit → au-delà de
  `busy_timeout=5000`, `database is locked` → `OperationalError`. La route
  `recherche` l'attrape (`main.py:815`), **pas les routes d'écriture** → une
  sauvegarde d'annotation peut **500 par intermittence** en collision avec un lot.

## 2. Sécurité — failles à corriger AVANT exposition

Toutes amplifiées par l'absence d'authentification.

| Sévérité | Faille | Référence | Détail |
|---|---|---|---|
| 🔴 Élevé | **SSRF via ShareDocs** | `pipeline/sharedocs.py:43-45,124-130` | `configure(url,…)` prend une URL **contrôlée par le client** ; le serveur émet PROPFIND/GET/PUT dessus avec `follow_redirects=True`, timeout 30 s. Un inconnu peut viser `http://169.254.169.254/…` (**métadonnées cloud → vol d'identifiants IAM**), services internes, `localhost`. |
| 🔴 Élevé | **Exfiltration totale non authentifiée** | `main.py:647`, `main.py:1103` | `GET /api/sauvegarde` → snapshot **complet** de la base en un GET. `/derivatives/...` (StaticFiles) → toutes les images, énumérables. Tout le corpus (données + images) téléchargeable par n'importe qui. |
| 🟠 Moyen | **OOM upload + bombe de décompression** | `pipeline/ingest.py:25,97-101,158` | `file.file.read()` charge tout en RAM ; image **ouverte deux fois** + `convert/resize` ; `Image.MAX_IMAGE_PIXELS = None` (`ingest.py:25`, `ocr.py:55`) **supprime la garde Pillow**. Aucune limite de taille → un seul upload suffit à OOM. |
| 🟠 Moyen | **Pic RAM de la sauvegarde** | `pipeline/backup.py:28-34` | `raw = snap.read_bytes()` + zip en `io.BytesIO()` → base chargée 2× en RAM (pic 2–3× la taille de la base). |
| 🟡 Faible | **Fuite d'info par messages d'erreur** | divers `HTTPException(…, str(exc))` | Chemins disque, erreurs SQL, URLs internes renvoyés au client. |

### Points confirmés SAINS (ne pas sur-corriger)
- **Pas d'injection SQL** : recherche FTS5 avec tokens échappés + `MATCH` paramétré
  (`main.py:783-787`) ; ailleurs, valeurs liées et noms de colonnes statiques.
- **Pas de traversée de chemin** : fichiers nommés `planche_{numero:04d}`, seul le
  suffixe vient du client et ne peut contenir de `/` (`pipeline/ingest.py:153-157`) ;
  `_rel_posix` via `relative_to(DATA_DIR)`.
- Course écriture→lecture déjà traitée (commit explicite, `main.py:51-57`).
- Préservation du travail humain à la re-détection (CTE `doomed`, `bulles.py:107-122`).

## 3. Capacités VPS recommandées

| Usage | vCPU | RAM | Disque |
|---|---|---|---|
| Annotation + recherche seules (ML désactivé) | 1–2 | 1–2 Go | dominé par les TIFF |
| Avec les 3 passes ML (segmentation / bulles / OCR) | 4 | **8 Go** (4 Go = risque OOM) | + cache modèles ~1–2 Go |

- **Pilote mémoire = images décodées + modèles torch résidents** (`_model`/`_reader`
  restent chargés après le 1er appel). La base reste modeste (texte/métadonnées).
- **Disque dominé par les masters TIFF** (`corpus/`) : dizaines–centaines de Go.
- **Disque local uniquement** pour la base (WAL casse sur NFS/CIFS).
- **Modèles téléchargés au 1er appel** (`hf_hub_download`, `easyocr.Reader()`) →
  sur VPS sans egress, pré-charger au provisioning. Repo HF **non épinglé** à une
  révision → à fixer (reproductibilité / supply-chain).

## 4. Plan d'action (par priorité)

1. **Authentification + isolement réseau** (reverse proxy auth/TLS, ou VPN/firewall).
   Neutralise d'un coup l'exfiltration `/api/sauvegarde` + `/derivatives` et réduit
   SSRF/DoS. ← *la couche prévue.*
2. **Anti-SSRF ShareDocs** : allowlist du host (domaine Huma-Num), refus IP
   privées/loopback/link-local, `follow_redirects=False`.
3. **Garde-fous upload** : limite de taille (proxy + appli), `MAX_IMAGE_PIXELS`
   raisonnable, streaming vers disque, ouvrir l'image une seule fois.
4. **Verrouiller les routes ML directes** (Lock partagé avec le worker, ou les
   router vers la file de jobs) + rendre `_get_reader`/`_load_model` atomiques.
5. **1 worker uvicorn + systemd** (sans `--reload`), modèles pré-chargés,
   `/api/sante` en liveness probe.
6. **Figer les dépendances** (lockfile) + **épingler la révision du modèle HF** ;
   sauvegarde automatisée hors-site (en tenant compte du pic RAM de `make_backup`).
7. Attraper `OperationalError` sur les routes d'écriture (409/retry) et
   **assainir les messages d'erreur**.

## 5. Rappels d'exploitation

- Lancement prod : `uvicorn main:app --workers 1` (jamais `--reload`).
- Données configurables : `BD_DATA_DIR` (racine corpus/derivatives/base),
  `BD_DB_PATH` (base). ShareDocs : `BD_SHAREDOCS_URL/USER/PASS` (le mot de passe
  n'est jamais persisté ni renvoyé).
- Les jobs sont **éphémères** (threads daemon, registre RAM) : un redémarrage les
  perd. Le travail DB déjà committé par passe survit ; le suivi de job non.
