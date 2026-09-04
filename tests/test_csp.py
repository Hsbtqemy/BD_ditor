"""Content-Security-Policy (SEC-2) — la politique est SERVIE, et rien ne la viole.

Trois natures de tests, et il faut les trois. Le premier lit l'EN-TÊTE : il dit que la
politique existe et qu'elle interdit ce qu'elle prétend interdire. Le deuxième confronte
les tolérances déclarées aux surfaces réellement chargées — une tolérance qui vise un
chemin que personne ne charge dormirait en donnant l'impression d'avoir été pesée. Le
troisième EXÉCUTE la politique dans un vrai Chromium et écoute `securitypolicyviolation` :
lui seul dit que l'application VIT dessous.

Une CSP qu'on n'a pas exécutée n'est pas une protection, c'est une déclaration. Les deux
premières violations trouvées en écrivant ceci le montrent : le `<link rel="icon"
href="data:,">` des quatre gabarits, et le logo que ReDoc charge depuis l'INTÉRIEUR de son
bundle — deux choses qu'aucune relecture de source ne pouvait voir.
"""
import httpx
import pytest

from conftest import make_png

ADMIN = {"Remote-User": "csp", "Remote-Groups": "bd-admins"}

SURFACES_HTML = ("/", "/corpus", "/recherche", "/exploration")


def _csp(client, chemin):
    r = client.get(chemin)
    entete = r.headers.get("Content-Security-Policy")
    assert entete, f"{chemin} ne porte aucune CSP"
    return {d.split()[0]: d.split()[1:] for d in
            (x.strip() for x in entete.split(";")) if d}


@pytest.mark.parametrize("chemin", SURFACES_HTML)
def test_la_politique_stricte_couvre_les_quatre_surfaces(client, chemin):
    """Aucun script inline sur les surfaces de l'application, et c'est vérifiable.

    C'est LA directive qui compte : `script-src 'self'` sans `'unsafe-inline'` ni
    `'unsafe-eval'`. Les gabarits ne portent aucun `<script>` inline ni `onclick=`, donc
    elle ne coûte rien — mais rien ne l'aurait empêchée de se dégrader en silence le jour
    où quelqu'un ajoute un handler dans le HTML.
    """
    d = _csp(client, chemin)
    assert d["script-src"] == ["'self'"], d["script-src"]
    assert d["object-src"] == ["'none'"]
    assert d["frame-ancestors"] == ["'none'"]      # anti-clickjacking
    assert d["base-uri"] == ["'none'"]             # une <base> injectée détournerait tout
    # `style-src` tolère l'attribut (dix largeurs CALCULÉES) ; le canal ÉLÉMENT, lui,
    # reste strict — il n'existe aucun `<style>`, donc la sévérité y est gratuite.
    assert "'unsafe-inline'" in d["style-src"]
    assert d["style-src-elem"] == ["'self'"]
    assert "data:" in d["img-src"]                 # <link rel="icon" href="data:,">


def test_l_api_porte_la_politique_elle_aussi(client):
    """L'en-tête est posé sur TOUTE réponse, pas seulement sur les pages.

    Une route qui renverrait un jour du HTML hériterait alors de la politique par DÉFAUT
    plutôt que d'en être exemptée par oubli — même raisonnement que l'export qui nomme ses
    colonnes (AUTH-1) : ce qu'on ajoute est couvert par décision, jamais par défaut.
    """
    assert _csp(client, "/api/sante")["script-src"] == ["'self'"]


@pytest.mark.parametrize("chemin", ["/docs", "/redoc"])
def test_les_docs_ont_leur_politique_et_pas_une_exemption(client, chemin):
    """`/docs` est engendré par FastAPI depuis un CDN : la politique stricte le casserait.

    Il en reçoit une AUTRE, pas aucune. Ce qui ne bouge pas d'une politique à l'autre est
    ce qui compte — un chemin sans en-tête est un chemin qu'il faudrait se rappeler d'avoir
    exempté.
    """
    d = _csp(client, chemin)
    assert "https://cdn.jsdelivr.net" in d["script-src"]
    assert d["object-src"] == ["'none'"]           # relâché pour vivre, pas sur le principe
    assert d["frame-ancestors"] == ["'none'"]
    assert d["base-uri"] == ["'none'"]
    # Et surtout : cette tolérance ne DÉBORDE pas sur l'application.
    assert "'unsafe-inline'" not in _csp(client, "/")["script-src"]


# --------------------------------------------------------------------------- #
# Le seul test qui prouve quelque chose : la politique EXÉCUTÉE
# --------------------------------------------------------------------------- #
_ECOUTE = """
  window.__csp = [];
  document.addEventListener('securitypolicyviolation', function (e) {
    window.__csp.push(e.violatedDirective + ' bloque ' + (e.blockedURI || '(inline)')
                      + ' — ' + (e.sourceFile || '') + ':' + (e.lineNumber || ''));
  });
"""


@pytest.fixture
def corpus_csp(live_server):
    """Un album, une planche, une région annotée : de quoi faire RENDRE les barres et la
    heatmap, c'est-à-dire précisément les dix `style="width:…"` que la politique tolère.

    Le `timeout` de 30 s lâche par INTERMITTENCE : une `ReadTimeout` au MONTAGE du décor,
    donc une ERREUR et non un échec — le test n'a alors jamais mesuré la politique. Relevé
    le 2026-09-04 : une fois dans un run E2E complet de 26 min, puis une fois sur trois
    relances du seul fichier, les deux autres passant en 60 et 75 s. La charge du run n'est
    donc PAS l'explication, contrairement à ce qu'on a d'abord écrit ici, et la cause reste
    non établie. Même symptôme que celui consigné dans `test_e2e_a11y.py`. On ne remonte pas
    le chiffre pour autant : une marge plus large masquerait la question sans y répondre, et
    l'ERREUR est un signal honnête — elle dit « je n'ai rien mesuré », là où un test lent
    aurait dit « tout va bien ».
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "CSP"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"})
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# Ce qu'on accepte de voir bloqué, et pourquoi. Un blocage DÉCLARÉ n'est pas un échec,
# c'est une décision : ReDoc va chercher son propre logo sur `cdn.redoc.ly` depuis
# l'INTÉRIEUR de son bundle — l'URL n'apparaît nulle part dans le HTML servi, et aucune
# lecture de la source ne pouvait la trouver ; c'est ce test qui l'a dite. On ne rouvre pas
# un hôte tiers pour une image décorative : la page rend parfaitement sans, et un hôte
# ouvert le reste pour tout ce que ce CDN servira un jour. Même forme que les déclarations
# d'AUTH-5 — ce qui n'est pas déclaré ici fait échouer la suite.
BLOCAGES_ADMIS = {
    "/redoc": [("img-src", "https://cdn.redoc.ly/redoc/logo-mini.svg",
                "logo décoratif de ReDoc, chargé par son bundle. Purement cosmétique : "
                "ouvrir un CDN tiers en `img-src` coûte plus que le logo ne vaut.")],
}


# Les surfaces effectivement CHARGÉES par le navigateur. Nommées ici plutôt qu'en ligne
# dans le décorateur : `BLOCAGES_ADMIS` doit pouvoir être confronté à cette liste, sans
# quoi une entrée visant un chemin qu'aucun test ne charge ne serait JAMAIS regardée — ni
# honorée, ni démentie. C'est le troisième mensonge possible d'un cliquet, et celui qui a
# coûté le plus cher ailleurs aujourd'hui (AUTH-5, `0ff38c7`).
SURFACES_BALAYEES = [
    "/?album={album}&planche={planche}&region={region}",
    "/recherche?q=pouvoir",
    "/corpus",
    "/exploration?champ=lemme",
    "/docs",
    "/redoc",
]


def test_tout_blocage_admis_vise_une_surface_reellement_chargee():
    """Une tolérance qui vise un chemin non balayé est une tolérance que rien ne contrôle.

    Elle ne serait ni honorée ni démentie : elle dormirait dans la liste en donnant
    l'impression d'avoir été pesée. Test RAPIDE à dessein — il n'a pas besoin d'un
    navigateur pour dire qu'une déclaration ne pointe nulle part.
    """
    for chemin in BLOCAGES_ADMIS:
        assert chemin in SURFACES_BALAYEES, (
            f"{chemin} est déclaré dans BLOCAGES_ADMIS mais n'est chargé par aucun test : "
            "sa tolérance n'est jamais vérifiée. L'ajouter à SURFACES_BALAYEES, ou la "
            "retirer.")


@pytest.mark.e2e
@pytest.mark.parametrize("live_server", [True], indirect=True)
@pytest.mark.parametrize("chemin", SURFACES_BALAYEES)
def test_aucune_violation_de_csp_au_chargement(page, corpus_csp, chemin):
    """« Console navigateur vide » — la case du chantier, rendue exécutable.

    On écoute l'événement DOM plutôt que la console : il porte la directive violée, la
    ressource bloquée et la ligne, là où un message de console est une chaîne à relire.
    """
    page.add_init_script(_ECOUTE)
    page.goto(corpus_csp["base"] + chemin.format(**corpus_csp), wait_until="networkidle")
    page.wait_for_timeout(800)
    violations = page.evaluate("window.__csp || []")
    admis = BLOCAGES_ADMIS.get(chemin, [])
    surprises = [v for v in violations
                 if not any(d in v and uri in v for d, uri, _ in admis)]
    assert not surprises, (
        f"{chemin} viole sa propre CSP :\n  " + "\n  ".join(surprises)
        + "\n\nSoit la page cesse de le faire, soit la politique l'autorise EXPLICITEMENT "
          "dans `main.py` avec sa raison écrite. Desserrer sans écrire pourquoi rendrait "
          "la politique indistinguable d'une absence de politique. Et un blocage "
          "ASSUMÉ entre dans BLOCAGES_ADMIS, avec la sienne.")
    # L'inverse compte autant : un blocage déclaré qui ne se produit plus est une liste
    # qui pourrit, et une liste qui pourrit rassure au lieu de protéger.
    for directive, uri, raison in admis:
        assert raison, chemin + " : blocage admis sans raison écrite"
        assert any(directive in v and uri in v for v in violations), (
            chemin + " déclare admettre le blocage de " + uri + " (" + directive
            + "), qui ne se produit plus — à retirer de BLOCAGES_ADMIS.")
