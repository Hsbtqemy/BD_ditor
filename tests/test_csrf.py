"""SEC-2 — la garde contre les requêtes forgées (CSRF).

Ce qu'elle ferme, mesuré le 2026-09-08 : sur 72 routes mutantes, 61 étaient déjà hors
d'atteinte — leur méthode ou leur Content-Type en fait des requêtes « non simples », donc
préflightées, et l'application ne sert aucun en-tête CORS. **Onze restaient forgeables par
un simple `<form>`**, dont `POST /api/undo`, les trois lancements de passe ML et les deux
imports de fichier.

Ce qu'Authelia ne pouvait pas fermer : son cookie porte `SameSite=Lax` — l'inter-sites est
mort — mais aussi `domain=edito-revue.fr`, le domaine PARENT, nécessaire au partage de
session entre `auth.` et `bd.`. `SameSite` raisonnant par domaine ENREGISTRABLE, tout
`*.edito-revue.fr` est *same-site* et reçoit le cookie. La protection dépendait donc de
l'hygiène d'un voisin que le projet n'héberge pas.

Le client de `conftest` porte l'en-tête, comme un navigateur. Ces tests-ci construisent
donc le leur, sans rien : autrement ils ne pourraient jamais faire échouer la garde.
"""
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

import main

MUTANTES = ("POST", "PUT", "PATCH", "DELETE")


@pytest.fixture
def nu(data_dir):
    """Un client SANS en-tête ni `Sec-Fetch-Site` — ce qu'un `<form>` forgé produit."""
    return TestClient(main.app)


@pytest.mark.parametrize("methode", MUTANTES)
def test_une_ecriture_sans_preuve_d_origine_est_refusee(nu, methode):
    """Les QUATRE méthodes mutantes, et pas seulement POST.

    POST est la seule que le mesurage désignait comme forgeable par un `<form>` — les
    autres sont déjà préflightées. Les couvrir quand même coûte une ligne et ferme une
    hypothèse : la garde ne doit pas dépendre de ce que les navigateurs d'aujourd'hui
    refusent d'émettre. Ce qui protège les trois autres est un comportement de navigateur,
    pas une règle de l'application.
    """
    r = nu.request(methode, "/api/undo")
    assert r.status_code == 403, f"{methode} passe sans preuve d'origine"
    assert "X-BD-Requete" in r.json()["detail"], (
        "le refus doit NOMMER l'en-tête manquant : un 403 muet se diagnostique en tâtonnant")


def test_une_lecture_n_est_pas_genee(nu):
    """La garde ne borde QUE les écritures.

    Une lecture forgée ne peut rien changer, et son résultat n'est de toute façon pas
    lisible par le site attaquant faute de CORS. L'y soumettre casserait les liens
    d'export — `window.location` vers un `.csv` est une navigation, sans en-tête possible.
    """
    assert nu.get("/api/sante").status_code == 200


def test_l_application_elle_meme_passe_par_sec_fetch_site(nu):
    """`Sec-Fetch-Site: same-origin` suffit, et c'est ce qui laisse vivre `/docs`.

    Le « Try it out » de Swagger émet ses requêtes depuis la page elle-même et n'a aucune
    raison de connaître notre en-tête. Cet en-tête-ci est posé par le NAVIGATEUR seul : son
    nom est interdit aux scripts, donc un site tiers ne peut pas le contrefaire.
    """
    r = nu.post("/api/undo", headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code != 403, r.text


@pytest.mark.parametrize("site", ["same-site", "cross-site"])
def test_un_voisin_de_sous_domaine_est_refuse(nu, site):
    """**`same-site` est le cas qui motive tout le chantier, et il est REFUSÉ.**

    Un `bd.edito-revue.fr` attaqué depuis un `autre.edito-revue.fr` produit exactement
    `Sec-Fetch-Site: same-site`, et le cookie Authelia part avec la requête — c'est le trou
    que `SameSite=Lax` ne bouche pas. Accepter `same-site` aurait donné une garde qui
    refuse ce qui était déjà refusé et laisse passer ce qui ne l'était pas.
    """
    r = nu.post("/api/undo", headers={"Sec-Fetch-Site": site})
    assert r.status_code == 403, f"une écriture {site} doit être refusée"


def test_l_en_tete_seul_suffit_meme_sans_sec_fetch_site(nu):
    """Un navigateur ancien n'envoie pas `Sec-Fetch-Site` — l'en-tête doit alors suffire.

    C'est la raison d'être des DEUX mécanismes. `Sec-Fetch-Site` est absent avant
    Firefox 90 ou Safari 16.4 ; s'en remettre à lui seul aurait fait dépendre la protection
    de la version du navigateur de la victime, c'est-à-dire de rien qu'on maîtrise.
    """
    r = nu.post("/api/undo", headers={main.EN_TETE_REQUETE: "1"})
    assert r.status_code != 403, r.text


def test_le_refus_porte_quand_meme_la_politique_de_securite(nu):
    """La garde est déclarée AVANT `_csp`, donc elle est la plus INTERNE.

    Starlette applique les middlewares dans l'ordre inverse de leur déclaration : le
    dernier déclaré enveloppe les autres. Déclarer celui-ci en dernier l'aurait rendu
    externe, et son 403 serait ressorti SANS politique de sécurité — la promesse de `_csp`,
    « sur TOUTE réponse », serait devenue fausse pour les seules réponses qu'on refuse.

    C'est un ordre que rien ne rend visible à la lecture : il se lit dans la position des
    deux fonctions dans le fichier, ce qu'un déplacement anodin change sans le dire.
    """
    r = nu.post("/api/undo")
    assert r.status_code == 403
    assert "Content-Security-Policy" in r.headers, (
        "le 403 de la garde CSRF sort sans CSP : elle a été déclarée APRÈS `_csp`")


def test_les_imports_de_fichier_sont_bordes(nu, album, png_bytes):
    """Les deux routes multipart, qui sont les plus franchement forgeables.

    Un `<form enctype="multipart/form-data">` d'un site voisin les atteignait sans le
    moindre script : c'est la forme la plus ancienne et la plus simple d'une CSRF, et la
    seule que ni `SameSite=Lax` ni le préflight ne gênaient.
    """
    r = nu.post(f"/api/albums/{album['id']}/import",
                files={"file": ("p.png", png_bytes, "image/png")})
    assert r.status_code == 403, "l'import de planche accepte encore un multipart forgé"

    r = nu.post("/api/lexique/importer",
                files={"file": ("v.csv", b"domaine;dimension\n", "text/csv")})
    assert r.status_code == 403, "l'import de vocabulaire accepte encore un multipart forgé"


def test_le_frontend_pose_exactement_l_en_tete_que_la_garde_attend():
    """Le nom de l'en-tête est écrit des DEUX côtés, et rien ne les relie.

    **C'est le seul défaut de ce chantier qui laisserait la suite par défaut VERTE.** Un
    renommage côté Python laisserait le frontend poser l'ancien nom : chaque écriture de
    chaque surface repartirait en 403, et rien ne le dirait — tous les clients de la suite
    passent par la fixture `client`, qui lit la constante et suivrait le renommage. Seul
    un navigateur verrait la panne, douze minutes plus tard, et le marqueur `e2e` est
    exclu par défaut.

    Ce test lit le SOURCE. C'est faible en général — un test qui lit une surface au lieu
    de l'exécuter déclare couvert ce qu'il n'éprouve pas — et c'est exact ici, parce que
    ce qu'on vérifie EST une graphie. Il ne prouve pas que chaque écriture porte
    l'en-tête : cela, seuls les e2e le voient.
    """
    racine = pathlib.Path(main.__file__).resolve().parent / "static"
    sources = {p.relative_to(racine).as_posix(): p.read_text(encoding="utf-8")
               for p in racine.rglob("*.js")}
    assert sources, "aucun source JS lu : le test ne mesure rien"

    assert main.EN_TETE_REQUETE in sources.get("lib/common.js", ""), (
        f"`common.js` ne pose plus {main.EN_TETE_REQUETE} : `apiSend` sert les CINQ "
        "surfaces, donc toute écriture de l'application repartirait en 403")

    # Les deux envois multipart et le zip de figures n'utilisent pas `apiSend` : ils
    # construisent leur `fetch`, et doivent poser l'en-tête eux-mêmes. On les reconnaît à
    # leur `method:` LITTÉRALE — celle d'`apiSend` est une variable, et c'est bien ce qui
    # la distingue : elle est déjà couverte par l'assertion ci-dessus.
    mutants = [(c, m.start()) for c, s in sources.items()
               for m in re.finditer(r'method:\s*["\']?(POST|PUT|PATCH|DELETE)', s)]
    assert len(mutants) >= 3, (
        f"seulement {len(mutants)} appel(s) `fetch` à méthode LITTÉRALE trouvé(s) : le "
        "balayage ne voit plus ce qu'il garde, et deviendrait vert en ne mesurant rien")
    for chemin, pos in mutants:
        # L'en-tête peut précéder ou suivre `method:` dans l'objet d'options ; la fenêtre
        # couvre l'appel, pas le fichier — sans quoi un en-tête posé ailleurs suffirait.
        voisinage = sources[chemin][max(0, pos - 200):pos + 400]
        assert main.EN_TETE_REQUETE in voisinage, (
            f"{chemin} : un `fetch` mutant hors `apiSend` ne pose pas "
            f"{main.EN_TETE_REQUETE} — il repartira en 403")
