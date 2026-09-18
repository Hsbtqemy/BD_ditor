"""AUTH-12, étape 3 — « Qui entre » : les accès d'une collection, dans SA fiche.

Les accès vivaient dans l'Administration, panneau « 👥 Accès aux collections ». Ils vivent en
tête de la collection dépliée, dans la Bibliothèque, et se règlent en ACTES lus dans
`GET /api/droits`. Ce module joue les gestes du propriétaire sur la vraie route, avec la
doublure de l'annuaire que charge `live_server` (`annotateurs` y est ; `ancien-cours` non).

Chaque test vise ce qu'aucun test d'API ne verrait : des actes liés qui se cocheraient
séparément ; un nom déjà présent que « Faire entrer » rétrograderait en lecture sans rien
dire ; un annuaire en panne qui bloquerait le geste ; un mot du modèle — « principal »,
« genre », « utilisateur » — revenu dans un texte d'écran.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/corpus", "/administration")
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier annote une planche ; aucun accès ne s'y règle",
    "/recherche": "la Recherche interroge le corpus ; aucun accès ne s'y règle",
    "/exploration": "l'Exploration mesure la langue du corpus ; aucun accès ne s'y règle",
}


def _client(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ECRITURE)


@pytest.fixture
def collection(live_server):
    """Une collection neuve, en mono-poste (portée totale : on l'administre)."""
    with _client(live_server) as c:
        cid = c.post("/api/collections", json={"nom": "Étude qui entre"}).json()["id"]
    return {"base": live_server, "id": cid}


def _accorder(base, cid, genre, principal, niveau, exporter=False):
    with _client(base) as c:
        r = c.put(f"/api/collections/{cid}/acces", json={
            "genre": genre, "principal": principal, "niveau": niveau, "exporter": exporter})
        assert r.status_code == 200, r.text


def _acces(base, cid):
    with _client(base) as c:
        return {(a["genre"], a["principal"]): a
                for a in c.get(f"/api/collections/{cid}/acces").json()}


def _droits(base):
    with _client(base) as c:
        return c.get("/api/droits").json()


def _ouvrir(page, base, cid, suite=""):
    page.goto(base + f"/corpus?collection={cid}{suite}", wait_until="networkidle")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    item.locator(".qe-choix").wait_for(timeout=5000)
    return item


def _ligne(item, principal):
    return item.locator(".qe-table tbody tr", has=item.page.locator("th", has_text=principal))


# ── L'adresse ──────────────────────────────────────────────────────────────────────────


def test_l_adresse_ouvre_la_collection_sur_qui_entre(page, collection):
    """`/corpus?collection=<id>` est la cible de « Régler qui entre » : la collection s'ouvre,
    « Qui entre » EN PREMIER, le focus sur son titre. Une collection qu'on ne lit pas n'ouvre
    rien, et une ligne le dit sans dire si elle existe (règle du 404, AUTH-2)."""
    item = _ouvrir(page, collection["base"], collection["id"])
    expect(item).to_have_attribute("open", "")
    expect(item.locator(".qe-titre")).to_be_focused()
    premiere = item.locator(".col-detail > *").first
    expect(premiere).to_have_class(re.compile(r"\bqe\b"))

    page.goto(collection["base"] + "/corpus?collection=987654", wait_until="networkidle")
    expect(page.locator("#col-body .col-msg.erreur")).to_contain_text(
        "n'est pas dans la liste")


# ── Faire entrer, puis cocher ─────────────────────────────────────────────────────────


def test_faire_entrer_un_groupe_puis_cocher_l_ecriture_d_un_seul_geste(page, collection):
    """Décision 4 (2) et deux gestes retenus par Hugo : un groupe CHOISI dans la liste entre
    en lecture, puis un cran se coche. Les actes que le serveur accorde ensemble n'ont
    qu'UNE case, dont la cellule couvre leurs colonnes, et dont le nom accessible les nomme
    tous — la liaison dite en clair, jamais une finesse promise."""
    base, cid = collection["base"], collection["id"]
    item = _ouvrir(page, base, cid)
    item.locator(".qe-choix").select_option("groupe:annotateurs")
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        item.locator(".qe-faire-entrer").click()
    expect(item.locator(".qe-msg")).to_contain_text(
        "Le groupe annotateurs entre dans « Étude qui entre », en lecture. Cochez les autres actes.")
    assert _acces(base, cid)[("groupe", "annotateurs")]["niveau"] == "lecture"

    droits = _droits(base)
    ecriture = [a for a in droits["actes"] if a["niveau"] == "ecriture"]
    assert len(ecriture) > 1, "prémisse : plusieurs actes liés en écriture"
    ligne = _ligne(item, "annotateurs")
    cases = ligne.locator('.qe-case[data-cran="ecriture"]')
    expect(cases).to_have_count(1)
    expect(ligne.locator("td.qe-cran.qe-lie")).to_have_attribute("colspan", str(len(ecriture)))
    nom = page.evaluate("""(el) => (el.getAttribute('aria-labelledby') || '').split(' ')
      .map((id) => document.getElementById(id)?.textContent.trim()).join(' | ')""",
                        cases.element_handle())
    for a in ecriture:
        assert a["libelle"] in nom, (a["libelle"], nom)
    assert "annotateurs" in nom, nom

    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        cases.check()
    expect(_ligne(item, "annotateurs").locator('.qe-case[data-cran="ecriture"]')).to_be_checked()
    assert _acces(base, cid)[("groupe", "annotateurs")]["niveau"] == "ecriture"
    # Le premier cran ne se décoche pas : un accès lit toujours, et se retire par ✕.
    expect(_ligne(item, "annotateurs").locator('.qe-case[data-cran="lecture"]')).to_be_disabled()


def test_un_nom_tape_inconnu_de_l_annuaire_est_accorde_et_signale(page, collection):
    """Décision 4 (2) : une saisie libre est SIGNALÉE, jamais refusée. Le texte est celui que
    Hugo a retenu, et la ligne porte « inconnu de l'annuaire »."""
    base, cid = collection["base"], collection["id"]
    item = _ouvrir(page, base, cid)
    item.locator(".qe-choix").select_option("autre")
    item.locator(".qe-nom").fill("ancien-cours")
    item.locator(".qe-genre").select_option("groupe")
    item.locator(".qe-faire-entrer").click()
    expect(item.locator(".qe-msg.alerte")).to_have_text(
        "Le groupe ancien-cours n'est pas dans l'annuaire : l'accès est accordé, en lecture, "
        "mais n'ouvrira rien tant que ce nom n'y existe pas.")
    expect(_ligne(item, "ancien-cours").locator(".qe-signal")).to_contain_text(
        "inconnu de l'annuaire")
    assert ("groupe", "ancien-cours") in _acces(base, cid)


def test_faire_entrer_un_nom_deja_present_ne_le_retrograde_pas(page, collection):
    """Le `PUT` d'un accès RE-POSE un niveau : « faire entrer » un nom déjà présent le
    rétrograderait en lecture. L'écran le refuse sans rien envoyer — sur le COUPLE (compte ou
    groupe, nom exact) : un compte qui porte le nom d'un groupe est un autre accès, et passe.
    Limite écrite dans AUTH-12 : un autre onglet peut encore rétrograder."""
    base, cid = collection["base"], collection["id"]
    _accorder(base, cid, "groupe", "annotateurs", "ecriture")
    item = _ouvrir(page, base, cid)
    envois = []
    page.on("request", lambda r: envois.append(r.url)
            if r.method == "PUT" and "/acces" in r.url else None)
    item.locator(".qe-choix").select_option("groupe:annotateurs")
    item.locator(".qe-faire-entrer").click()
    expect(item.locator(".qe-msg.erreur")).to_contain_text("entre déjà")
    assert envois == [], f"le PUT est parti, et aurait rétrogradé : {envois}"
    assert _acces(base, cid)[("groupe", "annotateurs")]["niveau"] == "ecriture"

    item.locator(".qe-choix").select_option("autre")
    item.locator(".qe-nom").fill("annotateurs")
    item.locator(".qe-genre").select_option("utilisateur")
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        item.locator(".qe-faire-entrer").click()
    acces = _acces(base, cid)
    assert acces[("utilisateur", "annotateurs")]["niveau"] == "lecture"
    assert acces[("groupe", "annotateurs")]["niveau"] == "ecriture"


def test_un_annuaire_en_panne_n_empeche_rien(page, collection):
    """L'annuaire ne répond pas : la liste des groupes manque, la note le dit (texte de Hugo,
    sans « et ses comptes »), et le geste passe quand même, marqué « non vérifié ». Le
    tableau, lui, n'a pas attendu l'annuaire. La réponse de `…/annuaire` est interceptée :
    `live_server` charge une doublure qui répond."""
    base, cid = collection["base"], collection["id"]

    def panne(route):
        route.fulfill(status=200, content_type="application/json", body=(
            '{"annuaire": {"etat": "non_verifie", "motif": "delai"}, "groupes": null, '
            '"acces": [{"par": "groupe", "login": null, "groupe": "nouveau-cours", '
            '"verification": "non_verifie"}]}'))
    page.route("**/api/collections/*/annuaire", panne)
    item = _ouvrir(page, base, cid)
    # Une chaîne et non une expression : Playwright normalise alors les blancs, et le texte
    # du gabarit passe à la ligne.
    expect(item.locator(".qe-annuaire-note")).to_have_text(
        "L'annuaire ne répond pas : impossible de proposer ses groupes, ni de vérifier le nom "
        "que vous tapez. L'accès sera accordé tel quel, et marqué « non vérifié ».")
    expect(item.locator(".qe-choix optgroup")).to_have_count(0)
    # Sans liste, la saisie libre s'offre d'emblée.
    expect(item.locator(".qe-libre")).to_be_visible()
    item.locator(".qe-nom").fill("nouveau-cours")
    item.locator(".qe-genre").select_option("groupe")
    item.locator(".qe-faire-entrer").click()
    expect(item.locator(".qe-msg.alerte")).to_contain_text("non vérifié")
    expect(_ligne(item, "nouveau-cours").locator(".qe-signal")).to_contain_text("non vérifié")
    assert ("groupe", "nouveau-cours") in _acces(base, cid)


# ── Les cases ──────────────────────────────────────────────────────────────────────────


def test_la_case_hors_rang_vient_d_office_au_dernier_cran(page, collection):
    """« exporter » vient d'office au propriétaire : cochée, désactivée, et dite. Chez une
    lectrice, elle se coche et le serveur l'enregistre."""
    base, cid = collection["base"], collection["id"]
    _accorder(base, cid, "utilisateur", "proprio", "proprietaire")
    _accorder(base, cid, "utilisateur", "lectrice", "lecture")
    item = _ouvrir(page, base, cid)
    office = _ligne(item, "proprio").locator('.qe-case[data-hors-rang="exporter"]')
    expect(office).to_be_checked()
    expect(office).to_be_disabled()
    expect(_ligne(item, "proprio")).to_contain_text("(d'office)")

    case = _ligne(item, "lectrice").locator('.qe-case[data-hors-rang="exporter"]')
    expect(case).not_to_be_checked()
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        case.check()
    expect(_ligne(item, "lectrice").locator('.qe-case[data-hors-rang="exporter"]')).to_be_checked()
    lectrice = _acces(base, cid)[("utilisateur", "lectrice")]
    assert (lectrice["niveau"], lectrice["exporter"]) == ("lecture", True)


def test_decocher_decider_rend_l_ecriture_et_le_retrait_rend_le_focus(page, collection):
    """Décocher « décider qui entre » rend le cran du DESSOUS — l'écriture, pas la lecture —
    quand un autre propriétaire reste. Puis « ✕ » retire l'accès, et le focus, dont le
    bouton disparaît avec la ligne, va au titre de « Qui entre » plutôt que nulle part."""
    base, cid = collection["base"], collection["id"]
    _accorder(base, cid, "utilisateur", "proprio", "proprietaire")
    _accorder(base, cid, "groupe", "enseignants", "proprietaire")
    item = _ouvrir(page, base, cid)
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        _ligne(item, "enseignants").locator('.qe-case[data-cran="proprietaire"]').uncheck()
    expect(_ligne(item, "enseignants").locator('.qe-case[data-cran="proprietaire"]')).not_to_be_checked()
    assert _acces(base, cid)[("groupe", "enseignants")]["niveau"] == "ecriture"

    with page.expect_response(lambda r: r.request.method == "DELETE"):
        _ligne(item, "enseignants").locator(".qe-retirer").click()
    expect(item.locator(".qe-table th[scope=row]", has_text="enseignants")).to_have_count(0)
    expect(item.locator(".qe-titre")).to_be_focused()
    assert ("groupe", "enseignants") not in _acces(base, cid)


def test_a_375_px_une_carte_par_acces_et_le_meme_geste(page, collection):
    """Sous 48em, le tableau devient une carte par accès (tranché par Hugo le 2026-09-17) :
    une case par cran, libellée des actes qu'elle accorde. Le geste y est le même."""
    base, cid = collection["base"], collection["id"]
    _accorder(base, cid, "groupe", "annotateurs", "lecture")
    _accorder(base, cid, "utilisateur", "proprio", "proprietaire")
    page.set_viewport_size({"width": 375, "height": 900})
    item = _ouvrir(page, base, cid)
    expect(item.locator(".qe-table")).to_have_count(0)
    expect(item.locator(".qe-carte")).to_have_count(2)
    carte = item.locator(".qe-carte", has=page.locator(".qe-qui", has_text="annotateurs"))
    ecriture = carte.locator('.qe-case[data-cran="ecriture"]')
    with page.expect_response(lambda r: r.request.method == "PUT" and r.url.endswith("/acces")):
        ecriture.check()
    assert _acces(base, cid)[("groupe", "annotateurs")]["niveau"] == "ecriture"
    expect(item.locator(".qe-carte", has=page.locator(".qe-qui", has_text="annotateurs"))
           .locator('.qe-case[data-cran="ecriture"]')).to_be_checked()


# ── Le lexique ─────────────────────────────────────────────────────────────────────────

_MOTS_DU_MODELE = re.compile(r"\b(principal|principaux|genre|utilisateurs?)\b", re.I)

_TEXTES_D_UN_BLOC = """(sel) => {
  const bloc = document.querySelector(sel);
  if (!bloc) return null;
  const attributs = [...bloc.querySelectorAll('[placeholder], [aria-label], [title]')]
    .flatMap((el) => ['placeholder', 'aria-label', 'title'].map((a) => el.getAttribute(a)))
    .filter(Boolean);
  return [bloc.innerText, ...attributs].join('\\n');
}"""


def test_aucun_texte_d_ecran_ne_dit_principal_genre_ni_utilisateur(page, collection):
    """AUTH-12, décision 7 : compte, personne, groupe, accès, propriétaire, administrateur —
    jamais « principal », « genre » ni « utilisateur ». Mesuré sur ce que l'écran MONTRE, texte
    et attributs lisibles compris, et non sur le source, où ces mots restent des valeurs
    d'API. Les deux blocs qui parlent d'accès : « Qui entre », saisie libre ouverte, et les
    trois fiches de « 👥 Comptes et groupes »."""
    base, cid = collection["base"], collection["id"]
    _accorder(base, cid, "groupe", "annotateurs", "ecriture")
    _accorder(base, cid, "utilisateur", "arrivant", "lecture")
    item = _ouvrir(page, base, cid)
    item.locator(".qe-choix").select_option("autre")
    item.locator(".qe-faire-entrer").click()          # un refus affiché, lui aussi relu
    item.locator(".qe-msg.erreur").wait_for(timeout=3000)
    texte = page.evaluate(_TEXTES_D_UN_BLOC, "#collections-bloc")
    assert texte and "Qui entre" in texte
    trouves = sorted({m.group(0) for m in _MOTS_DU_MODELE.finditer(texte)})
    assert not trouves, f"la Bibliothèque dit {trouves}"

    for suite in ("?compte=arrivant", "?axe=groupes&groupe=annotateurs",
                  f"?axe=collections&collection={cid}"):
        page.goto(base + "/administration" + suite, wait_until="networkidle")
        page.locator("#cg-fiche-titre").wait_for(timeout=5000)
        texte = page.evaluate(_TEXTES_D_UN_BLOC, "#cg-bloc")
        trouves = sorted({m.group(0) for m in _MOTS_DU_MODELE.finditer(texte)})
        assert not trouves, f"« Comptes et groupes » ({suite}) dit {trouves}"


# ── Ce qui a déménagé avec le panneau ──────────────────────────────────────────────────


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_le_resume_dit_proprietaire_ou_administrateur(page, live_server):
    """La pastille qui vivait dans l'Administration a suivi les accès : le résumé d'une
    collection dit « propriétaire » à qui l'est, « administrateur » à qui l'administre sans
    figurer dans les accès — un pouvoir qu'on déclare (AUTH-4) —, et rien à qui ne fait que
    participer."""
    admin = {"Remote-User": "decor", "Remote-Groups": "bd-admins"}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers={**ECRITURE, **admin}) as c:
        cid = c.post("/api/collections", json={"nom": "Étude résumée"}).json()["id"]
        for principal, niveau in (("proprio", "proprietaire"), ("lectrice", "lecture")):
            r = c.put(f"/api/collections/{cid}/acces", json={
                "genre": "utilisateur", "principal": principal, "niveau": niveau})
            assert r.status_code == 200, r.text

    attendus = (({"Remote-User": "proprio"}, "propriétaire"), (admin, "administrateur"),
                ({"Remote-User": "lectrice"}, None))
    for entetes, pastille in attendus:
        page.set_extra_http_headers(entetes)
        page.goto(live_server + "/corpus", wait_until="networkidle")
        resume = page.locator(f'#col-body .col-item[data-id="{cid}"] summary')
        resume.wait_for(timeout=5000)
        if pastille:
            expect(resume.locator(".col-niveau")).to_have_text(pastille)
        else:
            expect(resume.locator(".col-niveau")).to_have_count(0)


def test_le_resume_ne_dit_rien_en_mono_poste(page, collection):
    """En mono-poste, on administre tout sans être « administrateur » : il n'y a qu'un rôle,
    et nommer un pouvoir qui ne distingue personne serait faux (AUTH-4). Le résumé ne porte
    donc aucune pastille — le mutant qui l'affichait à quiconque administre survivait au
    test voisin, joué derrière le proxy seulement."""
    page.goto(collection["base"] + "/corpus", wait_until="networkidle")
    resume = page.locator(f'#col-body .col-item[data-id="{collection["id"]}"] summary')
    resume.wait_for(timeout=5000)
    expect(resume.locator(".col-niveau")).to_have_count(0)
