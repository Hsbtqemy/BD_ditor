"""ShareDocs Huma-Num : téléchargement WebDAV + OCR via watch-folder.

⚠️ NON TESTÉ (nécessite des identifiants ShareDocs). Code prêt à brancher,
écrit d'après la doc Huma-Num + le pattern éprouvé de `madbot_webdav`.

Deux usages :
  1. download_dir() : récupérer des planches depuis ton espace ShareDocs.
  2. ocr_via_watchfolder() : déposer un fichier dans hnTools_watchFolder/OCR/...
     et récupérer le résultat `_hnOCR` (ABBYY ou Tesseract côté Huma-Num).

CONTRAINTES IMPORTANTES (doc Huma-Num) — à garder en tête :
  * Quota ABBYY : 900 pages / utilisateur / an. INUTILISABLE pour l'OCR de
    masse d'un corpus de milliers de planches. Réservé à un échantillon.
  * Contrat ABBYY « valable jusqu'à juin 2026 » — vérifier qu'il est encore actif.
  * Latence : traitement asynchrone (1–24 h), email à la fin.
  * Watch-folder = PAS du stockage : fichiers supprimés après 21 jours.
  * Nom de fichier unique sur 23 jours glissants (anti-boucle) — préfixer d'un
    horodatage si on resoumet.
  * AbbyyCloud envoie sur Azure (externe, 24 h) -> à éviter pour des scans sous
    droits ; préférer AbbyyServer (interne Huma-Num). Sortie suffixée `_hnOCR`.

Identifiants ShareDocs :
  base_url = "https://sharedocs.huma-num.fr/dav.php/"   (endpoint SabreDAV)
  username = "<id>@webdav"   password = "<mot de passe d'application>"
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx
from webdav4.client import Client

IMG_EXT = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
WATCHFOLDER = "hnTools_watchFolder"


def connect(base_url: str, username: str, password: str,
            timeout: float = 60.0) -> Client:
    """Client WebDAV ShareDocs (Basic auth, suivi de redirection)."""
    http = httpx.Client(auth=(username, password), timeout=timeout,
                        follow_redirects=True)
    return Client(base_url.rstrip("/") + "/", http_client=http)


def discover_tools(client: Client) -> list[str]:
    """Liste hnTools_watchFolder/OCR/ pour révéler les noms EXACTS des
    dossiers (engine/preset/langue) — à faire en premier, la casse compte."""
    out = []
    for tool in client.ls(WATCHFOLDER, detail=False):
        out.append(tool)
    return out


def download_dir(client: Client, remote_dir: str, local_dir: Path,
                 exts=IMG_EXT) -> list[Path]:
    """Télécharge toutes les images d'un répertoire ShareDocs."""
    local_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for entry in client.ls(remote_dir, detail=True):
        name = entry["name"].rstrip("/").split("/")[-1]
        if Path(name).suffix.lower() in exts and entry.get("type") != "directory":
            dest = local_dir / name
            client.download_file(entry["name"], str(dest))
            saved.append(dest)
    return saved


def ocr_via_watchfolder(client: Client, local_file: Path,
                        engine: str = "AbbyyServer", preset: str = "toText",
                        lang: str = "French", *, wait: bool = False,
                        timeout_s: int = 3600, interval_s: int = 60) -> str | None:
    """Dépose `local_file` dans hnTools_watchFolder/OCR/<engine>/<preset>/<lang>/
    et (optionnellement) attend puis renvoie le chemin distant du résultat
    `<stem>_hnOCR.<ext>`. Sans `wait`, renvoie None (récupérer plus tard).

    NB : vérifier les noms de dossiers exacts avec discover_tools() — la doc
    montre p.ex. `abbyyServer/toWord/German`. La casse peut compter.
    """
    folder = f"{WATCHFOLDER}/OCR/{engine}/{preset}/{lang}"
    remote = f"{folder}/{local_file.name}"
    client.upload_file(str(local_file), remote, overwrite=False)

    if not wait:
        return None
    deadline = time.time() + timeout_s
    stem = local_file.stem
    while time.time() < deadline:
        for entry in client.ls(folder, detail=False):
            leaf = entry.rstrip("/").split("/")[-1]
            if leaf.startswith(f"{stem}_hnOCR"):
                return entry
        time.sleep(interval_s)
    return None  # dépassé : récupérer manuellement plus tard (latence 1–24 h)


if __name__ == "__main__":  # pragma: no cover - utilitaire manuel
    import argparse
    ap = argparse.ArgumentParser(description="Diagnostic ShareDocs (ls watch-folder OCR)")
    ap.add_argument("--url", default="https://sharedocs.huma-num.fr/dav.php/")
    ap.add_argument("--user", required=True, help="<id>@webdav")
    ap.add_argument("--password", required=True)
    a = ap.parse_args()
    c = connect(a.url, a.user, a.password)
    print("hnTools_watchFolder/OCR :")
    try:
        for t in c.ls(f"{WATCHFOLDER}/OCR", detail=False):
            print("  ", t)
    except Exception as exc:
        print("  (échec :", exc, ")")
