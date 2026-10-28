"""UX-19 — l'Atelier choisit sa COLLECTION avant son album (Hugo, 2026-10-21).

Une liste *Collection* précède la liste *Album* : la base du projet en tête, puis les autres
collections qu'on lit (A → Z), puis « Toutes les collections du projet » ; la liste *Album*
ne montre que les albums rangés dans la collection choisie. Rien de choisi : la base — ou
« Toutes » tant qu'elle ne contient aucun album qu'on lit. Le
choix est un filtre de l'Atelier seul, retenu projet par projet. Un lien vers un album
absent de la collection choisie la change ; un lien de la Bibliothèque pose la sienne.

Joué sous une identité derrière le proxy qui LIT plusieurs collections du projet sans
portée totale — la lectrice, membre des deux projets, dont la base lui est ouverte en
lecture —, pour que la liste soit celle que le serveur borne, et non celle d'un
administrateur qui lit tout. La règle elle-même est verrouillée par
`tests/js/atelier.test.js` ; ce fichier mesure que l'écran s'en sert, sur les gestes.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": (
        "le filtre de collection est le MÊME module (`lib/atelier.js`), partagé "
        "et testé sous Node ; la page Annotation le réemploie sans en changer la "
        "règle, et le mesure dans son propre audit (`test_e2e_annotation_page`)"),
    "/corpus": "la Bibliothèque n'a pas de liste *Album* à filtrer ; on n'y joue que le lien "
               "de la fiche d'un album vers l'Atelier, et ce qu'elle ne retient pas",
    "/recherche": "aucune liste d'albums à filtrer par collection : la Recherche traverse",
    "/exploration": "aucune liste d'albums à filtrer par collection : l'Exploration compte",
    "/administration": "l'Administration traverse les projets et ne lit pas ce filtre",
}

LECTRICE = {"Remote-User": "lea", "Remote-Name": "Léa Lectrice"}
TOUTES = "toutes"


def _api(base, methode, chemin, corps=None):
    with httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ECRITURE) as c:
        r = c.request(methode, chemin, json=corps)
        assert r.status_code < 300, f"{methode} {chemin} → {r.status_code} {r.text}"
        return r.json() if r.content else None


def _base_de(base, projet_id):
    return next(c["id"] for c in _api(base, "GET", "/api/collections")
                if c["base"] and c["projet_id"] == projet_id)


def _planche(base, album_id):
    with httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ECRITURE) as c:
        r = c.post(f"/api/albums/{album_id}/import",
                   files={"file": ("p.png", make_png(), "image/png")})
        assert r.status_code < 300, r.text
        return r.json()["id"]


@pytest.fixture
def decor(live_server):
    """Dans le projet de repli : sa base, « Étude A », « Étude B » et « Vide », que la
    lectrice lit toutes ; un album dans la base, un dans A, un dans B, un dans A ET B. Un
    second projet, « Séminaire », dont elle lit la base, qui porte un album."""
    b = live_server
    repli = next(p for p in _api(b, "GET", "/api/projets") if p["repli"])["id"]
    seminaire = _api(b, "POST", "/api/projets", {"nom": "Séminaire",
                                                 "acces_membres": "lecture"})["id"]
    _api(b, "PUT", f"/api/projets/{repli}/acces-membres", {"acces_membres": "lecture"})
    for pid in (repli, seminaire):
        _api(b, "PUT", f"/api/projets/{pid}/membres",
             {"genre": "utilisateur", "principal": "lea", "role": "membre"})
    cols = {"base": _base_de(b, repli), "sem": _base_de(b, seminaire)}
    for nom, cle in (("Étude A", "A"), ("Étude B", "B"), ("Vide", "vide")):
        cols[cle] = _api(b, "POST", "/api/collections", {"nom": nom})["id"]
        _api(b, "PUT", f"/api/collections/{cols[cle]}/acces",
             {"genre": "utilisateur", "principal": "lea", "niveau": "lecture"})
    albums = {}
    for titre, cle in (("De la base", "base"), ("De A", "A"), ("De A et de B", "A"),
                       ("De B", "B"), ("Du séminaire", "sem")):
        albums[titre] = _api(b, "POST", "/api/albums",
                             {"titre": titre, "collection_id": cols[cle]})["id"]
    _api(b, "PUT", f"/api/albums/{albums['De A et de B']}/collections/{cols['B']}")
    noms = [c["nom"] for c in _api(b, "GET", "/api/collections") if c["id"] == cols["base"]]
    return {"base": b, "repli": repli, "seminaire": seminaire, "cols": cols,
            "albums": albums, "nom_base": noms[0]}


def _ouvrir(page, d, chemin="/"):
    page.set_extra_http_headers(LECTRICE)
    page.goto(d["base"] + chemin, wait_until="networkidle")
    expect(page.locator("#collection-select option")).not_to_have_count(0)


def _collection(page):
    return page.locator("#collection-select")


def _albums(page):
    return page.locator("#album-select option")


def test_la_collection_precede_l_album_et_le_filtre(page, decor):
    """La liste *Collection* : la base en tête, les autres A → Z, puis « Toutes » ; rien de
    choisi, la base. La liste *Album* ne montre que les albums de la collection choisie, et
    un album rangé dans deux collections paraît dans chacune."""
    d = decor
    _ouvrir(page, d)
    # Le libellé précède la liste, et la liste *Collection* précède *Album* dans le document.
    expect(page.get_by_label("Collection", exact=True)).to_have_id("collection-select")
    ordre = page.evaluate("""() => {
      const c = document.getElementById('collection-select');
      const a = document.getElementById('album-select');
      return !!(c.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING);
    }""")
    assert ordre, "la liste Collection doit précéder la liste Album"
    expect(page.locator("#collection-select option")).to_have_text(
        [d["nom_base"], "Étude A", "Étude B", "Vide", "Toutes les collections du projet"])
    expect(_collection(page)).to_have_value(str(d["cols"]["base"]))
    expect(_albums(page)).to_have_text(["De la base (0)"])
    expect(page.locator("#album-select")).to_have_value(str(d["albums"]["De la base"]))

    _collection(page).select_option(str(d["cols"]["B"]))
    expect(_albums(page)).to_have_text(["De A et de B (0)", "De B (0)"])
    expect(page.locator("#album-select")).to_have_value(str(d["albums"]["De A et de B"]))
    _collection(page).select_option(str(d["cols"]["A"]))
    expect(_albums(page)).to_have_text(["De A (0)", "De A et de B (0)"])
    # L'album ouvert, rangé aussi dans A, le reste.
    expect(page.locator("#album-select")).to_have_value(str(d["albums"]["De A et de B"]))


def test_une_base_vide_ouvre_toutes_les_collections_puis_la_base_quand_elle_se_remplit(
        page, decor):
    """Rien de choisi, une base qu'on lit mais qui ne contient aucun album lu : l'Atelier
    s'ouvre sur « Toutes les collections du projet » (Hugo, 2026-10-21), sans le retenir.
    Dès que la base contient un album lu, c'est elle."""
    d = decor
    b = d["base"]
    pid = _api(b, "POST", "/api/projets", {"nom": "Base vide",
                                           "acces_membres": "lecture"})["id"]
    _api(b, "PUT", f"/api/projets/{pid}/membres",
         {"genre": "utilisateur", "principal": "lea", "role": "membre"})
    base_vide = _base_de(b, pid)
    etude = _api(b, "POST", "/api/collections", {"nom": "Étude C", "projet_id": pid})["id"]
    _api(b, "PUT", f"/api/collections/{etude}/acces",
         {"genre": "utilisateur", "principal": "lea", "niveau": "lecture"})
    du_c = _api(b, "POST", "/api/albums", {"titre": "Du C", "collection_id": etude})["id"]

    _ouvrir(page, d)
    page.locator("#projet-choix").select_option(str(pid))
    # La base est proposée — on la lit —, mais l'Atelier ne s'ouvre pas sur elle, vide.
    expect(page.locator("#collection-select option")).to_have_text(
        ["Base vide", "Étude C", "Toutes les collections du projet"])
    expect(_collection(page)).to_have_value(TOUTES)
    expect(_albums(page)).to_have_text(["Du C (0)"])
    expect(page.locator("#album-select")).to_have_value(str(du_c))
    assert page.evaluate(f"() => BDAtelier.lire({pid})") is None, (
        "un défaut déduit ne se retient pas")

    # La base reçoit un album : rouverte sans lien, l'Atelier s'ouvre sur elle.
    _api(b, "PUT", f"/api/albums/{du_c}/collections/{base_vide}")
    page.goto(b + "/", wait_until="networkidle")
    expect(_collection(page)).to_have_value(str(base_vide))
    expect(_albums(page)).to_have_text(["Du C (0)"])


def test_toutes_les_collections_rend_la_liste_du_projet(page, decor):
    d = decor
    _ouvrir(page, d)
    _collection(page).select_option(TOUTES)
    # Dans l'ordre où le serveur les rend, comme avant UX-19.
    expect(_albums(page)).to_have_text(
        ["De A (0)", "De A et de B (0)", "De B (0)", "De la base (0)"])
    # Le projet, et lui seul : l'album du séminaire n'y est pas.
    expect(_albums(page).filter(has_text="Du séminaire")).to_have_count(0)


def test_le_choix_est_retenu_par_l_atelier_projet_par_projet(page, decor):
    """Choisir « Étude B », recharger : « Étude B » revient. Changer de projet : la base du
    nouveau. Revenir : « Étude B ». La Bibliothèque n'en est pas changée."""
    d = decor
    _ouvrir(page, d)
    _collection(page).select_option(str(d["cols"]["B"]))
    expect(_albums(page)).to_have_text(["De A et de B (0)", "De B (0)"])
    # L'adresse a suivi l'album ouvert : recharger avant rouvrirait l'album d'AVANT, que
    # la règle du lien ferait sortir de « Étude B ».
    expect(page).to_have_url(re.compile(rf"album={d['albums']['De A et de B']}(?:&|$)"))
    page.reload(wait_until="networkidle")
    expect(_collection(page)).to_have_value(str(d["cols"]["B"]))
    expect(_albums(page)).to_have_text(["De A et de B (0)", "De B (0)"])

    page.locator("#projet-choix").select_option(str(d["seminaire"]))
    expect(_collection(page)).to_have_value(str(d["cols"]["sem"]))
    expect(_albums(page)).to_have_text(["Du séminaire (0)"])
    page.locator("#projet-choix").select_option(str(d["repli"]))
    expect(_collection(page)).to_have_value(str(d["cols"]["B"]))
    expect(_albums(page)).to_have_text(["De A et de B (0)", "De B (0)"])

    # La Bibliothèque : aucun calque posé, et la liste de ses albums est celle du projet.
    page.goto(d["base"] + "/corpus", wait_until="networkidle")
    page.locator("#col-body .col-item").first.wait_for(timeout=5000)
    expect(page.locator("#col-body [data-calque]:checked")).to_have_count(0)
    expect(page.locator("#albums-body .album-row")).to_have_count(4)


def test_sans_stockage_l_atelier_s_ouvre_sur_la_base_sans_erreur(page, decor):
    d = decor
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.add_init_script("""Object.defineProperty(window, 'localStorage', {
      configurable: true, get() { throw new Error('stockage bloqué'); } });""")
    _ouvrir(page, d)
    expect(_collection(page)).to_have_value(str(d["cols"]["base"]))
    expect(_albums(page)).to_have_text(["De la base (0)"])
    _collection(page).select_option(str(d["cols"]["A"]))
    expect(_albums(page)).to_have_text(["De A (0)", "De A et de B (0)"])
    expect(page.locator(".toast.error")).to_have_count(0)
    # Le choix n'a tenu que le temps de la page : rouvert sans lien, l'Atelier revient sur
    # la base. (Recharger rouvrirait l'album de l'adresse, que la règle du lien suit.)
    page.goto(d["base"] + "/", wait_until="networkidle")
    expect(_collection(page)).to_have_value(str(d["cols"]["base"]))
    expect(_albums(page)).to_have_text(["De la base (0)"])
    assert not erreurs, erreurs


def test_une_collection_vide_le_dit_sans_garder_l_album_d_avant(page, decor):
    d = decor
    pl = _planche(d["base"], d["albums"]["De A"])
    _ouvrir(page, d, f"/?album={d['albums']['De A']}&planche={pl}")
    expect(page.locator(f"#planche-list li[data-id='{pl}']")).to_have_class(re.compile("active"))
    _collection(page).select_option(str(d["cols"]["vide"]))
    expect(_albums(page)).to_have_text(["— aucun album dans cette collection —"])
    expect(page.locator("#planche-list li")).to_have_count(0)
    expect(page.locator("#stage-empty")).to_be_visible()
    expect(page.locator("#planche-info")).to_have_text("—")
    assert page.evaluate("() => state.albumId") is None


def test_un_lien_vers_un_album_hors_de_la_collection_la_change(page, decor):
    """« Étude B » retenue ; un lien vers « De A » — qui n'est pas dans B — l'ouvre, et la
    liste le contient : la collection est passée à « Étude A »."""
    d = decor
    pl = _planche(d["base"], d["albums"]["De A"])
    _ouvrir(page, d)
    _collection(page).select_option(str(d["cols"]["B"]))
    expect(_albums(page)).to_have_text(["De A et de B (0)", "De B (0)"])

    page.goto(f"{d['base']}/?album={d['albums']['De A']}&planche={pl}", wait_until="networkidle")
    expect(_collection(page)).to_have_value(str(d["cols"]["A"]))
    expect(page.locator("#album-select")).to_have_value(str(d["albums"]["De A"]))
    expect(_albums(page)).to_have_text(["De A (1)", "De A et de B (0)"])
    expect(page.locator(f"#planche-list li[data-id='{pl}']")).to_have_class(re.compile("active"))


def test_un_lien_sans_planche_ouvre_l_album_du_lien(page, decor):
    """`/?album=<id>` seul : l'album du lien s'ouvre, et non le premier de la liste."""
    d = decor
    _ouvrir(page, d, f"/?album={d['albums']['De B']}")
    expect(_collection(page)).to_have_value(str(d["cols"]["B"]))
    expect(page.locator("#album-select")).to_have_value(str(d["albums"]["De B"]))


def test_depuis_une_collection_de_la_bibliotheque_l_atelier_la_pose(page, decor):
    """Depuis « Étude B », l'album « De A et de B » — qui vit aussi dans « Étude A » —
    s'ouvre dans l'Atelier avec *Collection* = « Étude B »."""
    d = decor
    aid = d["albums"]["De A et de B"]
    pl = _planche(d["base"], aid)
    _ouvrir(page, d)
    _collection(page).select_option(str(d["cols"]["A"]))   # retenue : A
    page.goto(f"{d['base']}/corpus?collection={d['cols']['B']}&album={aid}",
              wait_until="networkidle")
    lien = page.locator("#album-detail a[href^='/?album=']").first
    expect(lien).to_have_attribute("href", re.compile(rf"collection={d['cols']['B']}\b"))
    lien.click()
    page.wait_for_load_state("networkidle")
    expect(_collection(page)).to_have_value(str(d["cols"]["B"]))
    expect(page.locator("#album-select")).to_have_value(str(aid))
    expect(page.locator(f"#planche-list li[data-id='{pl}']")).to_have_class(re.compile("active"))


def test_un_conflit_ouvert_bloque_le_changement_de_collection(page, decor):
    """Un changement de collection qui change d'album passe par les gardes d'un changement
    d'album : un conflit ouvert le bloque, la liste revient sur la collection d'avant."""
    d = decor
    _ouvrir(page, d)
    page.evaluate("() => { state.conflit = { lieu: 'note', regionId: -1, conflit: {} }; }")
    _collection(page).select_option(str(d["cols"]["B"]))
    expect(page.locator(".toast", has_text="Choisissez d'abord une version")).to_be_visible()
    expect(_collection(page)).to_have_value(str(d["cols"]["base"]))
    expect(_albums(page)).to_have_text(["De la base (0)"])
    assert page.evaluate("() => state.albumId") == d["albums"]["De la base"]


def test_un_enregistrement_en_cours_retient_le_changement_puis_le_rejoue(page, decor):
    """Un enregistrement pas encore revenu RETIENT le geste ; à la réponse il se rejoue, sans
    clic à refaire."""
    d = decor
    _ouvrir(page, d)
    page.evaluate("() => { state.envoiNote = new Promise((r) => { window.__lacher = r; }); }")
    _collection(page).select_option(str(d["cols"]["B"]))
    expect(_collection(page)).to_have_value(str(d["cols"]["base"]))
    assert page.evaluate("() => state.albumId") == d["albums"]["De la base"]
    page.evaluate("() => { state.envoiNote = null; window.__lacher(['ok']); }")
    expect(_collection(page)).to_have_value(str(d["cols"]["B"]))
    expect(_albums(page)).to_have_text(["De A et de B (0)", "De B (0)"])
    expect(page.locator("#album-select")).to_have_value(str(d["albums"]["De A et de B"]))
