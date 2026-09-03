"""Faux proxy d'authentification — pour ESSAYER le mode connecté dans l'interface.

  ⚠  OUTIL DE DÉVELOPPEMENT. Il n'authentifie PERSONNE et ne vérifie aucun mot de
     passe : il pose l'identité qu'on lui demande. Devant une instance réelle, il
     donnerait à quiconque l'identité de son choix, `bd-admins` compris. Il n'écoute
     que sur 127.0.0.1, et cela ne suffit pas à le rendre inoffensif ailleurs.

BD_ditor n'authentifie personne — c'est la doctrine AUTH-1 : il fait confiance aux
en-têtes `Remote-User`, `Remote-Groups`, `Remote-Name` et `Remote-Email` posés par un
proxy, et seulement si `BD_AUTH_PROXY` déclare que ce proxy est bien devant.

D'où un angle mort d'OBSERVATION, et il est large : un navigateur n'envoie pas ces
en-têtes. Sans quelque chose devant, on ne peut voir qu'UN des états d'AUTH-2 — celui où
aucune identité ne parvient — et tout le reste (cloisonnement par collection, trois
niveaux d'AUTH-3, pouvoir déclaré de l'administrateur en AUTH-4, 404-jamais-403) reste
invisible bien qu'entièrement écrit et testé. Monter Authelia pour le regarder demande le
VPS, c'est-à-dire INFRA-1, bloqué.

Ce script tient ce rôle et rien d'autre : il choisit une IDENTITÉ (cookie), pose les
quatre en-têtes, et relaie. C'est exactement le partage des rôles qu'AUTH-1 décrit — le
proxy dit QUI, l'application décide QUOI. Cinq identités, choisies pour montrer chacune un
état différent, dont les trois pannes que le bandeau de portée vide distingue.

    # 1. une base JETABLE, semée
    BD_DATA_DIR=/tmp/demo BD_DB_PATH=/tmp/demo/demo.sqlite python tools/semer_demo.py
    # 2. l'application derrière le drapeau, sur 8003
    BD_DATA_DIR=/tmp/demo BD_DB_PATH=/tmp/demo/demo.sqlite BD_AUTH_PROXY=1         BD_AUTH_LOGOUT_URL=http://127.0.0.1:8002/_connexion         python -m uvicorn main:app --port 8003
    # 3. le proxy devant, sur 8002
    python tools/faux_proxy_auth.py     # puis http://127.0.0.1:8002/_connexion

Accorder un accès se fait ensuite par l'API, sous l'identité `admin` — ce qui montre au
passage qu'un administrateur qui crée une collection n'en devient PAS propriétaire (AUTH-4).
"""
import http.cookies
import http.server
import urllib.error
import urllib.request

ECOUTE = ("127.0.0.1", 8002)
AMONT = "http://127.0.0.1:8003"
COOKIE = "bd_demo_identite"

# Cette machine a un proxy HTTP sortant, et `urllib` l'honore : sans cet opener,
# la requete vers 127.0.0.1 part chez le proxy, qui repond « Could Not Connect ».
# Le meme piege avait donne un 502 a `curl` (d'ou son --noproxy).
OUVREUR = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# login | nom lisible | courriel | groupes — et chacun montre un ÉTAT différent.
PERSONNAGES = {
    "": ("", "", "", "", "Personne — aucune identité ne parvient (le proxy est muet)"),
    "alice": ("alice", "Alice Duval", "alice@exemple.fr", "",
              "Identité SANS groupe — le proxy pose Remote-User, pas Remote-Groups"),
    "bob": ("bob", "Bob Marchand", "bob@exemple.fr", "chercheurs",
            "Identité AVEC groupes, dont aucun n'a d'accès — la panne qui ne se répare pas"),
    "claire": ("claire", "Claire Ferrand", "claire@exemple.fr", "chercheurs",
               "Comme bob, mais un accès lui a été accordé — elle voit son sous-corpus"),
    "admin": ("admin", "Ada Superviseur", "admin@exemple.fr", "chercheurs,bd-admins",
              "Membre de bd-admins — voit TOUT sans figurer dans collection_acces (AUTH-4)"),
}

PAGE = """<!doctype html><html lang="fr"><meta charset="utf-8">
<title>Faux proxy d'authentification</title>
<style>
 body{{font:15px/1.55 system-ui,sans-serif;max-width:52rem;margin:3rem auto;padding:0 1.2rem;
      background:#12141a;color:#e6e8ee}}
 h1{{font-size:1.35rem;margin-bottom:.2rem}} p.sous{{color:#9aa3b2;margin-top:0}}
 ul{{list-style:none;padding:0}}
 li{{border:1px solid #2a2f3a;border-radius:.5rem;margin:.55rem 0;padding:.75rem .95rem;
     background:#181b22}}
 li.actif{{border-color:#4c8bf5;background:#1b2333}}
 a{{color:#8ab4ff;text-decoration:none;font-weight:600}} a:hover{{text-decoration:underline}}
 code{{background:#22262f;padding:.1rem .35rem;border-radius:.25rem;font-size:.9em}}
 .quoi{{color:#9aa3b2;font-size:.92em;margin-top:.25rem}}
 .barre{{margin-top:1.6rem;padding-top:1rem;border-top:1px solid #2a2f3a;color:#9aa3b2;
         font-size:.92em}}
</style>
<h1>Faux proxy d'authentification</h1>
<p class="sous">Choisir qui l'on est. Le proxy pose les en-têtes, l'application décide
ce qu'on voit — c'est tout le partage des rôles d'AUTH-1/AUTH-2.</p>
<ul>{items}</ul>
<p class="barre">Identité courante : <code>{courant}</code> ·
 l'application est sur <a href="/">/</a> — revenir ici par
 <a href="/_connexion">/_connexion</a>.</p>
</html>"""


def page(courant):
    items = []
    for cle, (login, nom, _, groupes, quoi) in PERSONNAGES.items():
        actif = " class=\"actif\"" if cle == courant else ""
        titre = nom or "Personne"
        detail = f"<code>{login or '—'}</code>"
        if groupes:
            detail += f" · groupes <code>{groupes}</code>"
        elif login:
            detail += " · <code>Remote-Groups</code> absent"
        items.append(f"<li{actif}><a href=\"/_connexion?qui={cle}\">{titre}</a> — {detail}"
                     f"<div class=\"quoi\">{quoi}</div></li>")
    return PAGE.format(items="".join(items), courant=courant or "(personne)")


class Relais(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):        # silence : la sortie sert à voir l'amont
        pass

    def _qui(self):
        brut = self.headers.get("Cookie") or ""
        c = http.cookies.SimpleCookie()
        c.load(brut)
        v = c[COOKIE].value if COOKIE in c else ""
        return v if v in PERSONNAGES else ""

    def _repondre(self, code, corps, ctype="text/html; charset=utf-8", cookie=None):
        corps = corps.encode("utf-8") if isinstance(corps, str) else corps
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corps)))
        if cookie is not None:
            self.send_header("Set-Cookie", f"{COOKIE}={cookie}; Path=/; SameSite=Lax")
        self.end_headers()
        self.wfile.write(corps)

    def _traiter(self):
        chemin = self.path
        if chemin.startswith("/_connexion"):
            qui = ""
            if "?" in chemin:
                for p in chemin.split("?", 1)[1].split("&"):
                    if p.startswith("qui="):
                        qui = p[4:]
            if "qui=" in chemin:
                qui = qui if qui in PERSONNAGES else ""
                # On ENTRE dans l'application. Se recharger soi-meme laissait le seul
                # chemin vers l'app dans un lien de pied de page : on choisissait une
                # identite sans que rien ne se passe.
                corps = b"<!doctype html><meta charset=utf-8><title>...</title>"
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie",
                                 f"{COOKIE}={qui}; Path=/; SameSite=Lax")
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)
                return
            return self._repondre(200, page(self._qui()))

        corps = None
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            corps = self.rfile.read(n)

        req = urllib.request.Request(AMONT + chemin, data=corps, method=self.command)
        for h, v in self.headers.items():
            if h.lower() in ("host", "content-length", "connection", "accept-encoding",
                             "remote-user", "remote-groups", "remote-name", "remote-email"):
                continue
            req.add_header(h, v)

        login, nom, email, groupes, _ = PERSONNAGES[self._qui()]
        if login:
            req.add_header("Remote-User", login)
            req.add_header("Remote-Name", nom)
            req.add_header("Remote-Email", email)
            # Une identité SANS groupe est un état à part entière : on n'envoie pas
            # l'en-tête du tout, comme un proxy mal configuré.
            if groupes:
                req.add_header("Remote-Groups", groupes)

        try:
            with OUVREUR.open(req) as r:
                donnees, code, entetes = r.read(), r.status, r.headers
        except urllib.error.HTTPError as e:
            donnees, code, entetes = e.read(), e.code, e.headers
        except urllib.error.URLError as e:
            return self._repondre(502, f"<h1>Amont injoignable</h1><p>{AMONT} — {e}</p>")

        ctype = entetes.get("Content-Type", "")
        if "text/html" in ctype and b"</body>" in donnees:
            login, nom, _, groupes, _ = PERSONNAGES[self._qui()]
            qui = nom or "personne connectee"
            grp = groupes or ("aucun groupe" if login else "")
            donnees = donnees.replace(b"</body>", self._bandeau(qui, grp) + b"</body>")

        self.send_response(code)
        for h, v in entetes.items():
            if h.lower() in ("transfer-encoding", "content-length", "connection",
                             "content-security-policy"):
                continue
            self.send_header(h, v)
        # La CSP de l'app interdit `style` en attribut ? Non : `style-src 'unsafe-inline'`
        # est tolere (dix largeurs calculees, cf. SEC-2). Mais le bandeau est du DECOR de
        # demonstration : on la reemet telle quelle, sans rien desserrer.
        csp = entetes.get("Content-Security-Policy")
        if csp:
            self.send_header("Content-Security-Policy", csp)
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    @staticmethod
    def _bandeau(qui, groupes):
        detail = f" &middot; {groupes}" if groupes else ""
        return (
            '<div style="position:fixed;left:0;right:0;bottom:0;z-index:99999;'
            'background:#1b2333;color:#e6e8ee;border-top:2px solid #4c8bf5;'
            'font:13px system-ui,sans-serif;padding:.45rem .9rem;display:flex;'
            'gap:.8rem;align-items:center;justify-content:space-between">'
            f'<span>Proxy de demonstration &mdash; vous etes <b>{qui}</b>{detail}</span>'
            '<a href="/_connexion" style="color:#8ab4ff;font-weight:600">'
            "changer d&rsquo;identite</a></div>").encode("utf-8")

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _traiter


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(ECOUTE, Relais)
    print(f"Faux proxy sur http://{ECOUTE[0]}:{ECOUTE[1]}/_connexion (amont {AMONT})")
    srv.serve_forever()
