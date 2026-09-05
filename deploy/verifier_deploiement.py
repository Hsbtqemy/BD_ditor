"""Prouve qu'une instance déployée tient ses promesses — contrôle d'INFRA-1.

Trois des cinq cases d'INFRA-1 sont des affirmations vérifiables par machine ; ce script
les vérifie au lieu de les constater à l'œil. Il ne remplace pas le déploiement, il dit
si le déploiement a fait ce qu'on croit.

**Il se lance depuis le VPS**, après `docker compose up -d` :

    python deploy/verifier_deploiement.py --url https://bd.exemple.fr
    python deploy/verifier_deploiement.py --url https://bd.exemple.fr --tls-non-verifie

Deux familles de contrôles, et elles ne regardent pas au même endroit.

**DEHORS, en anonyme** : rien ne doit répondre 200. C'est la case « une requête non
authentifiée est refusée par Authelia AVANT d'atteindre l'application ». La liste des
chemins n'est pas décorative : le `Caddyfile` promet que le `forward_auth` couvre AUSSI
`/static`, `/derivatives` et `/api/sauvegarde`, et cette dernière déverse la base entière.
Un `forward_auth` posé au mauvais endroit dans le bloc laisserait passer les fichiers
statiques sans que rien ne le signale — la page d'accueil redirigerait correctement, et
l'instance aurait l'air protégée.

**DEDANS, par le conteneur** : `/api/sante?profond=1`, et surtout PAS la voie rapide.
`sante.rapide()` ne fait que constater la présence des modules ; le 2026-08-27, sur cette
pile même, elle a annoncé `bulles: true` alors que le premier `import ultralytics` levait
une exception. La voie profonde importe réellement chaque moteur et dit pourquoi quand ça
échoue. C'est exactement ce que la case d'INFRA-1 demande du NLP : « le seul contrôle qui
prouve que le modèle a bien suivi jusqu'en production ».

Ce que ce script NE vérifie pas, et qui reste à faire à la main : la déconnexion de bout
en bout depuis l'UI (elle passe par le navigateur et le cookie de session), et la
restauration d'une sauvegarde sur une machine de dev.
"""
import argparse
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ce qui ne doit JAMAIS répondre 200 à un anonyme. `/static` et `/derivatives` y sont
# parce que le Caddyfile promet de les couvrir : ce sont les pages d'un scan, et le
# cloisonnement d'AUTH-2 ne sert à rien si l'image se sert sans session.
CHEMINS_PROTEGES = [
    ("/", "la Visionneuse"),
    ("/corpus", "la Bibliothèque"),
    ("/recherche", "la Recherche"),
    ("/exploration", "l'Exploration"),
    ("/api/moi", "l'identité courante"),
    ("/api/sante", "l'état des moteurs"),
    ("/api/albums", "la liste des albums"),
    ("/api/sauvegarde", "LA BASE ENTIÈRE"),
    ("/static/style.css", "les feuilles de style"),
    ("/docs", "la documentation OpenAPI"),
]

# Le contrôle interne, exécuté DANS le conteneur : il n'a pas de session à présenter, et
# l'app n'est pas exposée hors du réseau Docker. On passe donc par `compose exec`.
SONDE_INTERNE = (
    "import json,urllib.request;"
    "r=urllib.request.urlopen('http://127.0.0.1:8000/api/sante?profond=1',timeout=120);"
    "print(r.read().decode())"
)


# Un refus d'AUTHENTIFICATION, et rien d'autre. Une panne d'infrastructure — 502 d'un
# proxy, 503 d'un conteneur mort, connexion refusée — ne prouve RIEN et ne doit surtout
# pas se lire comme une protection : c'est le mode d'échec qu'on a fabriqué en écrivant
# ce script, où une instance ÉTEINTE passait pour « parfaitement protégée ».
CODES_DE_REFUS = {401, 403}
CODES_DE_REDIRECTION = {301, 302, 303, 307, 308}


def ouvrir(url, verifier_tls, sans_proxy):
    """Une requête anonyme qui NE SUIT PAS les redirections.

    Suivre la redirection vers le portail rendrait le contrôle muet : on finirait sur une
    page de connexion en 200, et « 200 » est précisément ce qu'on cherche à interdire.
    """
    ctx = None if verifier_tls else ssl._create_unverified_context()

    class SansRedirection(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    handlers = [SansRedirection, urllib.request.HTTPSHandler(context=ctx)]
    if sans_proxy:                                    # un proxy sortant répond 502 à sa
        handlers.append(urllib.request.ProxyHandler({}))   # place et fausse le verdict
    op = urllib.request.build_opener(*handlers)
    try:
        rep = op.open(url, timeout=30)
        return rep.status, rep.headers.get("Location"), None
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location"), None
    except Exception as exc:                          # DNS, TLS, connexion refusée…
        return None, None, f"{type(exc).__name__}: {exc}"[:120]


def controle_externe(base, verifier_tls, sans_proxy):
    """Chaque chemin est classé en TROIS états, et « indéterminé » est un ÉCHEC.

    Un contrôle de sécurité qui ne distingue pas « refusé » de « injoignable » ment dans
    le sens le plus dangereux : il déclare sûre une instance qu'il n'a jamais atteinte.
    """
    print("\n  DEHORS — ce qu'un anonyme obtient")
    fuites, indetermines = [], []
    for chemin, quoi in CHEMINS_PROTEGES:
        code, dest, erreur = ouvrir(base.rstrip("/") + chemin, verifier_tls, sans_proxy)
        if erreur is not None:
            print(f"    ?? {chemin:22} INJOIGNABLE — {erreur}")
            indetermines.append((chemin, quoi, erreur))
        elif code == 200:
            print(f"    !! {chemin:22} 200 — {quoi} SERVI SANS AUTHENTIFICATION")
            fuites.append((chemin, quoi, "200"))
        elif code in CODES_DE_REFUS:
            print(f"    ok {chemin:22} {code} — refusé")
        elif code in CODES_DE_REDIRECTION and dest:
            print(f"    ok {chemin:22} {code} → {dest[:60]}")
        else:
            print(f"    ?? {chemin:22} {code} — ni refus ni redirection vers un portail")
            indetermines.append((chemin, quoi, f"code {code}"))
    return fuites, indetermines


def controle_interne(service):
    """Les moteurs répondent VRAIMENT, vus depuis le conteneur."""
    print("\n  DEDANS — les moteurs, importés pour de bon (?profond=1)")
    try:
        res = subprocess.run(
            ["docker", "compose", "exec", "-T", service, "python", "-c", SONDE_INTERNE],
            capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        print("    ?  `docker` introuvable — ce contrôle se lance DEPUIS le VPS")
        return ["docker absent"]
    if res.returncode != 0:
        print(f"    !! `compose exec` a échoué : {(res.stderr or '').strip()[:300]}")
        return ["compose exec"]
    try:
        rep = json.loads(res.stdout.strip().splitlines()[-1])
    except Exception:
        print(f"    !! réponse illisible : {res.stdout.strip()[:200]}")
        return ["réponse illisible"]

    profond = rep.get("profond") or {}
    manques = []
    for moteur in ("kumiko", "bulles", "ocr", "lemmes"):
        present = rep.get(moteur)
        detail = profond.get(moteur) or {}
        ok = detail.get("ok")
        if ok:
            print(f"    ok {moteur:8} présent et importé")
        else:
            raison = detail.get("erreur") or "aucun rapport profond"
            print(f"    !! {moteur:8} rapide={present} mais profond={ok} — {raison}")
            manques.append(moteur)
    return manques


def controle_config(chemin_env):
    """AVANT de démarrer : les trois domaines de `.env` sont-ils cohérents ?

    Le cas qu'on ferme ici est silencieux et grave. Authelia pose le cookie de session sur
    `COOKIE_DOMAINE` ; s'il est trop HAUT, le cookie part à tout ce domaine. Avec
    `sslip.io`, écrire `sslip.io` au lieu de `<ip>.sslip.io` enverrait la session de cette
    instance à toutes les instances du service. Rien ne le signalerait : la connexion
    fonctionne, et c'est bien le problème.

    Aucun des outils du déploiement ne voit ce cas — `compose config` valide la syntaxe,
    Caddy son fichier, Authelia le sien, mais aucun ne connaît les deux autres.
    """
    print(f"\n  AVANT — les domaines de {chemin_env}")
    vals = {}
    try:
        for ligne in open(chemin_env, encoding="utf-8"):
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, _, val = ligne.partition("=")
                vals[cle.strip()] = val.strip()
    except OSError as exc:
        print(f"    !! illisible : {exc}")
        return ["fichier .env illisible"]

    manquants = [c for c in ("BD_DOMAINE", "AUTH_DOMAINE", "COOKIE_DOMAINE")
                 if not vals.get(c)]
    if manquants:
        print(f"    !! absent(s) de .env : {', '.join(manquants)}")
        return manquants

    app, portail, parent = (vals["BD_DOMAINE"], vals["AUTH_DOMAINE"],
                            vals["COOKIE_DOMAINE"])
    pbs = []
    for nom, hote in (("BD_DOMAINE", app), ("AUTH_DOMAINE", portail)):
        if not hote.endswith("." + parent):
            print(f"    !! {nom}={hote} n'est PAS sous {parent} — session perdue")
            pbs.append(nom)
        else:
            print(f"    ok {nom:14} {hote}")
    if app == portail:
        print("    !! l'app et le portail portent le même nom")
        pbs.append("noms identiques")
    if parent.count(".") < 2:
        print(f"    !! COOKIE_DOMAINE={parent} est un domaine de TROP HAUT NIVEAU :")
        print("       le cookie de session partirait vers tout ce domaine, pas vers")
        print("       cette seule instance.")
        pbs.append("COOKIE_DOMAINE trop haut")
    else:
        print(f"    ok {'COOKIE_DOMAINE':14} {parent} (parent immédiat des deux)")
    return pbs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", help="URL publique de l'app (https://bd.…)")
    ap.add_argument("--config", metavar="ENV", nargs="?", const="deploy/.env",
                    help="vérifier la COHÉRENCE des domaines de .env, avant de démarrer")
    ap.add_argument("--service", default="app", help="nom du service compose (défaut : app)")
    ap.add_argument("--tls-non-verifie", action="store_true",
                    help="certificat auto-signé (Caddy `tls internal`), avant le vrai DNS")
    ap.add_argument("--sans-interne", action="store_true",
                    help="ne pas tenter `docker compose exec` (contrôle depuis un poste)")
    ap.add_argument("--sans-proxy", action="store_true",
                    help="ignorer le proxy de l'environnement (il répond 502 à sa place)")
    a = ap.parse_args()
    if not a.url and not a.config:
        ap.error("rien à vérifier : donner --url (instance en marche) et/ou --config")

    incoherences = controle_config(a.config) if a.config else []
    if not a.url:
        print("\n  ── Bilan ──")
        print("  Configuration incohérente." if incoherences
              else "  Les trois domaines sont cohérents.")
        return 1 if incoherences else 0

    print(f"\n  Instance : {a.url}")
    fuites, indetermines = controle_externe(a.url, verifier_tls=not a.tls_non_verifie,
                                            sans_proxy=a.sans_proxy)
    manques = [] if a.sans_interne else controle_interne(a.service)

    print("\n  ── Bilan ──")
    if fuites:
        print(f"  ÉCHEC — {len(fuites)} chemin(s) SERVI(s) sans authentification :")
        for chemin, quoi, etat in fuites:
            print(f"      {chemin}  ({quoi}) : {etat}")
    if indetermines:
        print(f"  ÉCHEC — {len(indetermines)} chemin(s) dont on ne SAIT RIEN :")
        for chemin, quoi, etat in indetermines:
            print(f"      {chemin}  ({quoi}) : {etat}")
        print("      Une instance éteinte, une URL fautive ou un proxy qui répond à sa")
        print("      place donnent tous ce résultat. Ne pas le lire comme une protection.")
    if not fuites and not indetermines:
        print(f"  Les {len(CHEMINS_PROTEGES)} chemins sont refusés ou redirigés vers le portail.")
    if manques:
        print(f"  ÉCHEC — moteur(s) absents ou cassés : {', '.join(manques)}")
        print("      Le NLP est le plus coûteux et le plus SILENCIEUX : sans lui,")
        print("      l'Exploration, la relecture (ANN-4) et les deux rapports d'accord")
        print("      sortent vides, sans qu'aucun message ne le dise.")
    elif not a.sans_interne:
        print("  Les quatre moteurs répondent réellement.")

    print("\n  Restent à vérifier à la main (hors de portée d'un script) :")
    print("    · la déconnexion depuis l'UI, pas seulement via /api/moi")
    print("    · une sauvegarde prise ici, restaurée sur une machine de dev")
    return 1 if (fuites or indetermines or manques or incoherences) else 0


if __name__ == "__main__":
    sys.exit(main())
