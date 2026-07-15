r"""Diagnostic ShareDocs : vérifie LECTURE et ÉCRITURE sur un dossier WebDAV.

Réutilise le client de l'app (`pipeline/sharedocs.py`) — le test est donc fidèle
au comportement réel de BéDéditeur, et valide accessoirement le client contre
le vrai ShareDocs (jusqu'ici testé seulement sur WebDAV simulé).

Les identifiants viennent de l'ENVIRONNEMENT — jamais de la ligne de commande,
jamais affichés.

    # Windows PowerShell :
    $env:BD_SHAREDOCS_URL = "https://sharedocs.huma-num.fr/remote.php/dav/files/MONUSER"
    $env:BD_SHAREDOCS_USER = "monuser"
    $env:BD_SHAREDOCS_PASS = "..."          # sinon demandé en interactif (masqué)
    .\.venv\Scripts\python.exe tools\sharedocs_check.py "Mon dossier/sous-dossier"

    # Linux / VPS :
    export BD_SHAREDOCS_URL="..."; export BD_SHAREDOCS_USER="..."; export BD_SHAREDOCS_PASS="..."
    python tools/sharedocs_check.py "Mon dossier/sous-dossier"

Étapes : connexion (PROPFIND) → liste le dossier → y dépose un fichier test →
le relit → le supprime. À lancer une fois par dossier à tester (perso, partagé).
"""
from __future__ import annotations

import os
import sys
from getpass import getpass

import httpx

# Rend le paquet `pipeline` importable quand on lance depuis la racine du dépôt.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.sharedocs as sd  # noqa: E402


def raw_probe(url: str, user: str, password: str) -> None:
    """Sonde brute : montre le code HTTP exact, une redirection éventuelle et
    le schéma d'auth attendu. Sert à distinguer 401 (auth) de 403 (permission)
    et à détecter un SSO (redirection vers une page de login)."""
    target = url.rstrip("/") + "/"
    print(f"→ Sonde brute : PROPFIND {target} (sans suivre les redirections) …")

    # (1) Sans redirection : révèle un éventuel 302 vers un portail SSO.
    try:
        with httpx.Client(auth=(user, password), timeout=30.0,
                          follow_redirects=False) as c:
            r = c.request("PROPFIND", target,
                          headers={"Depth": "0", "Content-Type": "application/xml"},
                          content=sd._PROPFIND_BODY)
    except httpx.HTTPError as exc:
        print(f"   ✗ erreur réseau : {exc}")
        return

    print(f"   → HTTP {r.status_code}")
    if r.status_code in (301, 302, 303, 307, 308):
        print(f"   ↪ Redirection vers : {r.headers.get('location')!r}")
        print("     (une redirection vers une page de login = SSO/formulaire,")
        print("      le Basic Auth seul ne suffira pas)")
    if r.status_code == 401:
        print(f"   ↪ WWW-Authenticate : {r.headers.get('www-authenticate')!r}")
        print("     (si ce n'est pas 'Basic ...', le serveur attend un autre schéma)")
    snippet = " ".join(r.text[:300].split())
    if snippet:
        print(f"   ↪ début du corps : {snippet!r}")
    print()


def main() -> int:
    url = os.environ.get("BD_SHAREDOCS_URL", "").strip()
    user = os.environ.get("BD_SHAREDOCS_USER", "").strip()
    password = os.environ.get("BD_SHAREDOCS_PASS") or getpass("Mot de passe ShareDocs : ")
    folder = (sys.argv[1] if len(sys.argv) > 1 else "").strip("/")

    if not url or not user:
        print("✗ Définis d'abord BD_SHAREDOCS_URL et BD_SHAREDOCS_USER "
              "(voir l'en-tête du script).")
        return 2

    raw_probe(url, user, password)

    print(f"→ Connexion à {url} en tant que {user!r} …")
    try:
        sd.configure(url, user, password)
    except sd.ShareDocsError as exc:
        print(f"✗ Connexion refusée : {exc}")
        return 1
    print("✓ Connexion OK (lecture authentifiée à la racine).")

    label = f"/{folder}" if folder else "/ (racine)"
    print(f"\n→ Lecture du dossier {label} …")
    try:
        entries = sd.list_dir(folder)
    except sd.ShareDocsError as exc:
        print(f"✗ Lecture impossible : {exc}")
        return 1
    print(f"✓ Lecture OK — {len(entries)} entrée(s) :")
    for e in entries[:10]:
        print(f"    [{'dir ' if e['is_dir'] else 'file'}] {e['name']}")
    if len(entries) > 10:
        print(f"    … (+{len(entries) - 10} autres)")

    # --- Test d'écriture ---
    test_name = "bd_annotator_write_test.txt"
    test_path = f"{folder}/{test_name}" if folder else test_name
    payload = ("BéDéditeur - test d'écriture WebDAV (fichier temporaire à supprimer).\n"
               ).encode("utf-8")
    print(f"\n→ Test d'écriture : dépôt de {test_name!r} …")
    try:
        sd.upload(test_path, payload)
    except sd.ShareDocsError as exc:
        print(f"✗ Écriture REFUSÉE : {exc}")
        print("  → Dossier en LECTURE SEULE : utilisable comme SOURCE d'import,")
        print("    mais PAS comme cible de sauvegarde.")
        return 0
    print("✓ Écriture OK.")

    try:
        back = sd.download(test_path)
        conforme = back == payload
    except sd.ShareDocsError:
        conforme = False
    print(f"{'✓' if conforme else '✗'} Relecture du fichier déposé "
          f"{'conforme' if conforme else 'NON conforme'}.")

    # --- Nettoyage (DELETE — pas de helper dédié dans le client, requête directe) ---
    target = sd._join(sd._session["url"], test_path)
    try:
        with sd._client(user, password) as c:
            r = c.request("DELETE", target)
        if r.status_code < 400 or r.status_code == 404:
            print("✓ Nettoyage OK (fichier test supprimé).")
        else:
            print(f"⚠ Fichier test non supprimé (HTTP {r.status_code}) "
                  f"— à retirer à la main : {test_path}")
    except httpx.HTTPError as exc:
        print(f"⚠ Suppression échouée ({exc}) — à retirer à la main : {test_path}")

    print(f"\n✅ Dossier {label} : LECTURE + ÉCRITURE OK "
          "→ utilisable comme stockage / cible de sauvegarde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
