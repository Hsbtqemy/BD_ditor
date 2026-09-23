"""AUTH-12, étape 2 — « 👥 Comptes et groupes » joué dans un vrai navigateur.

La réponse de `GET /api/comptes-et-groupes` est ici INTERCEPTÉE (`page.route`) et rendue
par le test, sur la forme du contrat accordé avec le serveur. Ce n'est pas une doublure de
l'annuaire — celle-là vit côté serveur, et l'audit d'accessibilité comme le reflow passent
par elle — mais un test du CONTRAT côté écran : les trois états de l'annuaire, un « À
regarder » de rentrée, un compte à l'identité changée, se fabriquent ici en une ligne, là où
la vraie route demanderait un annuaire en panne ou treize arrivants semés en base.

Chaque test vise ce qu'aucun test d'API ne verrait : le serveur peut répondre juste et
l'écran perdre le tri en changeant d'axe, dire « non vérifié » là où il n'y a rien à
vérifier, ou laisser trente arrivants pousser la liste sous l'écran.

Les gestes qui ÉCRIVENT ou qui sortent du bloc — la nature d'un compte, et les liens vers
« Qui entre » dans la Bibliothèque — passent, eux, par le vrai serveur ; et un test d'intégration joue la
vraie route avec la doublure de l'annuaire, sans rien intercepter.
"""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

from conftest import ADMIN, ECRITURE  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/administration",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier annote une planche ; aucun compte ni groupe ne s'y consulte",
    "/recherche": "la Recherche interroge le corpus, pas les comptes de l'instance",
    "/corpus": "la Bibliothèque n'y est atteinte que par les liens du bloc ; « Qui entre » "
               "s'y éprouve dans test_e2e_qui_entre",
    "/exploration": "l'Exploration mesure la langue du corpus, pas ceux qui l'annotent",
}

ROUTE = "**/api/comptes-et-groupes"
MAINTENANT = datetime.now(timezone.utc)


def _iso(jours):
    return (MAINTENANT - timedelta(days=jours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compte(login, nom=None, *, jours=1, groupes=(), collections=(), usage="application",
            administrateur=False, reprises=0, derniere_reprise=None, signaux=(), actes=0,
            acces=0, nature="nominatif"):
    venu = jours is not None
    return {"login": login, "nom": nom, "courriel": None, "dans_annuaire": True,
            "usage": usage, "venu": venu,
            "premiere_vue": _iso(jours + 30) if venu else None,
            "derniere_vue": _iso(jours) if venu else None,
            "nature": nature if venu else None, "groupes": list(groupes),
            "administrateur": administrateur, "collections": list(collections),
            "collections_completes": True, "actes": actes, "acces_explicites": acces,
            "verdict": "rien à orpheliner" if not (actes or acces) else "laisse des actes",
            "reprises": reprises, "derniere_reprise": derniere_reprise,
            "signaux": list(signaux)}


def _groupe(nom, membres, *, gid=None, collections=(), derniere_venue=None,
            administrateur=False, role=False, signaux=()):
    return {"id": gid, "nom": nom, "dans_annuaire": True, "role_annuaire": role,
            "administrateur": administrateur, "nb_comptes": len(membres),
            "membres": list(membres), "derniere_venue": derniere_venue,
            "collections": list(collections), "signaux": list(signaux)}


ETUDIANTS = [f"e{i:02d}" for i in range(1, 13)]


def decor(cid=1, cid2=2):
    """Le décor des maquettes d'AUTH-12, sur un annuaire LU : un administrateur, une
    propriétaire, un groupe d'étudiants de douze comptes jamais venus, un arrivant sans
    groupe, un stagiaire à l'identité changée, un groupe disparu de l'annuaire, une
    collection sans propriétaire et le compte d'amorçage de l'annuaire."""
    test = {"id": cid, "nom": "Collection Test"}
    comptes = [
        _compte("admin-bd", "Camille Admin", jours=0, groupes=["bd-admins", "lldap_admin"],
                administrateur=True),
        _compte("proprio", "Paule Propriétaire", jours=2, groupes=["annotateurs"],
                actes=214, acces=1,
                collections=[{**test, "niveau": "proprietaire", "exporter": True,
                              "par": "compte", "groupe": None},
                             {**test, "niveau": "lecture", "exporter": True,
                              "par": "groupe", "groupe": "annotateurs"}]),
        _compte("lectrice", "Léa Lectrice", jours=5, groupes=["annotateurs"],
                collections=[{**test, "niveau": "lecture", "exporter": True,
                              "par": "groupe", "groupe": "annotateurs"}]),
        _compte("arrivant", "Sacha Benali", jours=None, signaux=["jamais_venu"]),
        _compte("stagiaire", "Théo Marchand", jours=20, reprises=2,
                derniere_reprise=_iso(3), signaux=["identite_changee"]),
        _compte("admin", "Administrateur de l'annuaire", jours=None, usage="annuaire",
                groupes=["lldap_admin"]),
    ] + [_compte(e, f"Étudiant {e[1:]}", jours=None, groupes=["etudiants-bd-2026"],
                 signaux=["jamais_venu"]) for e in ETUDIANTS]
    ancien = _groupe("ancien-cours", [], collections=[{**test, "niveau": "lecture",
                                                        "exporter": False}],
                     signaux=["groupe_absent"])
    ancien.update({"dans_annuaire": False, "nb_comptes": None, "membres": None})
    groupes = [
        _groupe("annotateurs", ["proprio", "lectrice"], gid=5, derniere_venue=_iso(2),
                collections=[{**test, "niveau": "lecture", "exporter": True}]),
        _groupe("etudiants-bd-2026", ETUDIANTS, gid=6),
        _groupe("bd-admins", ["admin-bd"], gid=4, derniere_venue=_iso(0),
                administrateur=True),
        _groupe("lldap_admin", ["admin", "admin-bd"], gid=1, derniere_venue=_iso(0),
                role=True),
        ancien,
    ]
    collections = [
        {**test, "nb_albums": 3, "statut_diffusion": "restreint", "repli": False,
         "derniere_modification": _iso(1),
         "proprietaires": [{"par": "compte", "login": "proprio", "groupe": None,
                            "vivant": True}],
         "nb_acces": 3,
         "acces": [{"par": "compte", "login": "proprio", "groupe": None,
                    "niveau": "proprietaire", "exporter": True},
                   {"par": "groupe", "login": None, "groupe": "annotateurs",
                    "niveau": "lecture", "exporter": True},
                   {"par": "groupe", "login": None, "groupe": "ancien-cours",
                    "niveau": "lecture", "exporter": False}],
         "signaux": []},
        {"id": cid2, "nom": "Étude B", "nb_albums": 1, "statut_diffusion": "prive",
         "repli": False, "derniere_modification": None, "proprietaires": [], "nb_acces": 0,
         "acces": [], "signaux": ["sans_proprietaire"]},
    ]
    a_regarder = ([{"signal": "groupe_absent", "groupe": "ancien-cours", "collection": cid},
                   {"signal": "sans_proprietaire", "collection": cid2},
                   {"signal": "identite_changee", "login": "stagiaire"}]
                  + [{"signal": "jamais_venu", "login": l}
                     for l in sorted(["arrivant"] + ETUDIANTS)])
    return {"annuaire": {"etat": "lu", "source": "lldap", "lu_le": _iso(0), "duree_ms": 80,
                         "motif": None, "lien": "https://annuaire.example.fr/"},
            "comptes": comptes, "groupes": groupes, "collections": collections,
            "a_regarder": a_regarder,
            "limite": "Les groupes et leurs membres sont lus dans l'annuaire à l'ouverture "
                      "de cette vue."}


def sans_lecture(d, etat):
    """Le même décor quand l'annuaire n'a rien pu dire : ce que le contrat met à `null`, et
    les signaux qui supposent l'annuaire retirés — aucun n'est remplacé par une supposition."""
    d = json.loads(json.dumps(d))
    d["annuaire"].update({"etat": etat, "lu_le": None, "duree_ms": None, "lien": None,
                          "source": None if etat == "sans_annuaire" else "lldap",
                          "motif": "delai" if etat == "non_verifie" else None})
    for c in d["comptes"]:
        c.update({"dans_annuaire": None, "usage": None, "groupes": None,
                  "administrateur": None, "collections_completes": False})
        c["collections"] = [x for x in c["collections"] if x["par"] == "compte"]
        c["signaux"] = [s for s in c["signaux"] if s == "identite_changee"]
    for g in d["groupes"]:
        g.update({"id": None, "dans_annuaire": None, "nb_comptes": None, "membres": None,
                  "derniere_venue": None, "signaux": []})
    d["a_regarder"] = [s for s in d["a_regarder"]
                       if s["signal"] in ("sans_proprietaire", "identite_changee")]
    d["limite"] = "Les accès accordés par groupe n'apparaissent pas."
    return d


def _servir(page, donnees, statut=200):
    page.route(ROUTE, lambda route: route.fulfill(
        status=statut, content_type="application/json",
        body=json.dumps(donnees if statut == 200 else {"detail": "refusé pour le test"})))


def _ouvrir(page, base, donnees, chemin="/administration"):
    _servir(page, donnees)
    page.goto(base + chemin, wait_until="networkidle")
    expect(page.locator("#cg-bloc")).to_be_visible()


def _noms(page):
    return page.locator("#cg-objets > li > .cg-objet .cg-nom").all_inner_texts()


def _creer_collection(base, nom):
    with httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ECRITURE) as c:
        r = c.post("/api/collections", json={"nom": nom})
        assert r.status_code == 201, r.text
        return r.json()["id"]


# ── La liste, la fiche, l'adresse ──────────────────────────────────────────────────────


def test_la_liste_s_ouvre_trie_a_z_et_une_fiche_se_nomme_dans_l_adresse(page, live_server):
    """Les comptes ordinaires par nom LU, les comptes de l'annuaire repliés à la fin, et un
    clic qui ouvre la fiche en l'écrivant dans l'adresse."""
    _ouvrir(page, live_server, decor())
    noms = _noms(page)
    assert noms[:4] == ["Camille Admin", "Étudiant 01", "Étudiant 02", "Étudiant 03"], noms
    assert "Administrateur de l'annuaire" not in noms, (
        "le compte d'amorçage de l'annuaire se lit dans la liste ordinaire : il devait se "
        "replier en fin de liste avec les comptes qui ne servent que l'annuaire")
    expect(page.locator("#cg-objets .cg-a-parte summary")).to_have_text("1 compte de l'annuaire")

    page.locator("#cg-objets .cg-objet", has_text="Paule Propriétaire").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Paule Propriétaire")
    assert "compte=proprio" in page.url
    courant = page.locator('#cg-objets .cg-objet[aria-current="true"]')
    expect(courant).to_have_count(1)
    # Au large, choisir dans la liste y LAISSE le clavier — la ligne a été redessinée, et le
    # focus la retrouve — pour parcourir la suivante sans revenir.
    expect(courant).to_be_focused()
    # La fiche dit PAR QUOI on entre : à son nom, ou par un groupe — deux lignes pour la
    # même collection, jamais un niveau fusionné. Et elle le dit en ACTES, lus dans
    # `/api/droits` (AUTH-12, étape 3) : le dernier cran se dit « tous les actes ».
    lignes = page.locator("#cg-fiche .cg-section", has_text="Collections").locator("li")
    expect(lignes).to_have_count(2)
    expect(lignes.nth(0)).to_contain_text("tous les actes, dont décider qui entre — à son nom")
    expect(lignes.nth(1)).to_contain_text("lire, exporter — par le groupe annotateurs")
    expect(page.locator("#cg-fiche")).not_to_contain_text("propriétaire · peut exporter")

    # « + Dans l'annuaire » crée un compte ou un groupe ; une collection se crée ailleurs.
    expect(page.locator("#cg-annuaire-lien")).to_be_visible()
    page.locator('#cg [data-axe="collections"]').click()
    expect(page.locator("#cg-annuaire-lien")).to_be_hidden()


def test_le_tri_survit_au_changement_d_axe_et_au_rechargement(page, live_server):
    _ouvrir(page, live_server, decor())
    page.locator('#cg [data-tri="recents"]').click()
    noms = _noms(page)
    # Le plus récent en tête ; les jamais venus, sans date, à la FIN.
    assert noms[0] == "Camille Admin", noms
    assert noms.index("Théo Marchand") < noms.index("Sacha Benali"), noms

    page.locator('#cg [data-axe="groupes"]').click()
    expect(page.locator('#cg [data-tri="recents"]')).to_have_attribute("aria-pressed", "true")
    assert "axe=groupes" in page.url and "tri=recents" in page.url, page.url
    groupes = _noms(page)
    assert groupes.index("bd-admins") < groupes.index("annotateurs"), groupes
    # Sans venue (aucun membre venu, ou groupe absent de l'annuaire) : en fin de liste.
    assert groupes.index("annotateurs") < groupes.index("etudiants-bd-2026"), groupes

    page.reload(wait_until="networkidle")
    expect(page.locator('#cg [data-axe="groupes"]')).to_have_attribute("aria-pressed", "true")
    expect(page.locator('#cg [data-tri="recents"]')).to_have_attribute("aria-pressed", "true")
    assert _noms(page) == groupes


def test_un_lien_de_fiche_change_d_axe_et_retour_defait_le_saut(page, live_server):
    _ouvrir(page, live_server, decor(), "/administration?compte=proprio")
    expect(page.locator("#cg-fiche-titre")).to_have_text("Paule Propriétaire")

    page.locator("#cg-fiche .cg-lien", has_text="annotateurs").first.click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("annotateurs")
    expect(page.locator('#cg [data-axe="groupes"]')).to_have_attribute("aria-pressed", "true")
    # Le focus suit la fiche quand on vient d'un lien : le clavier ne reste pas sur un
    # bouton qui vient d'être détruit.
    expect(page.locator("#cg-fiche-titre")).to_be_focused()
    # Le propriétaire ne verrait pas les membres ; l'administrateur, si.
    expect(page.locator("#cg-fiche .cg-section", has_text="Membres").locator("li")).to_have_count(2)

    page.go_back()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Paule Propriétaire")
    expect(page.locator('#cg [data-axe="comptes"]')).to_have_attribute("aria-pressed", "true")


def test_le_filtre_ignore_casse_et_accents_et_ouvre_le_repli_qui_contient_la_reponse(
        page, live_server):
    _ouvrir(page, live_server, decor())
    page.locator("#cg-filtre").fill("LEA")
    assert _noms(page) == ["Léa Lectrice"]
    page.locator("#cg-filtre").fill("amorçage")
    expect(page.locator("#cg-objets .cg-vide")).to_contain_text("Aucun compte ne correspond")
    page.locator("#cg-filtre").fill("annuaire")
    # Le seul compte trouvé vit dans le repli : un filtre qui le laisserait fermé dirait
    # « trouvé » sans le montrer.
    expect(page.locator("#cg-objets .cg-a-parte")).to_have_attribute("open", "")
    expect(page.locator("#cg-objets .cg-a-parte .cg-objet")).to_be_visible()


def test_la_liste_se_parcourt_aux_fleches(page, live_server):
    _ouvrir(page, live_server, decor())
    lignes = page.locator("#cg-objets > li > .cg-objet")
    lignes.first.focus()
    page.keyboard.press("ArrowDown")
    expect(lignes.nth(1)).to_be_focused()
    page.keyboard.press("End")
    # Le repli fermé des comptes de l'annuaire ne vole pas le focus.
    expect(lignes.last).to_be_focused()
    page.keyboard.press("Home")
    expect(lignes.first).to_be_focused()


# ── « À regarder » ─────────────────────────────────────────────────────────────────────


def test_a_zero_signal_l_alerte_est_eteinte_et_se_rallume_au_premier(page, live_server):
    """À ZÉRO, « À regarder » n'est plus une alerte : ni ⚠, ni ambre, ni cadre, et repliée.

    Le seul élément de la page conçu pour attraper l'œil était allumé en permanence — cadre
    ambre, ⚠, `open` —, y compris quand il n'annonçait rien (relevé par Hugo le 2026-09-18
    sur une capture). C'est le mode d'échec le plus coûteux, parce qu'il ne se remarque
    jamais : qui ouvre cette page chaque semaine et voit toujours le même cadre finit par ne
    plus le lire, et le jour où il y a vraiment un accès mort, le cadre a exactement la même
    apparence qu'un mois de rien. Même règle que le bandeau de portée vide (AUTH-2), qui
    nomme les quatre situations mais ne se déplie d'office que pour la panne CERTAINE.

    Le COMPTE reste affiché dans les deux cas : « (0) » n'est pas le problème, c'est le décor
    d'alerte autour de lui. Et les DEUX états sont joués — une garde qui ne verrait que le
    zéro laisserait éteindre l'alerte pour de bon.
    """
    vide = decor()
    vide["a_regarder"] = []
    _ouvrir(page, live_server, vide)
    regarder = page.locator("#cg-regarder")
    expect(page.locator("#cg-regarder-titre")).to_have_text("À regarder (0)")
    assert regarder.evaluate("el => el.open") is False, "l'alerte vide s'ouvre d'office"
    # Les valeurs CALCULÉES, et non la classe seule : une classe posée sans règle dans la
    # feuille laisserait le cadre ambre allumé, et le test approuverait un écran inchangé.
    fond, bordure = page.evaluate(
        "(el) => { const s = getComputedStyle(el); return [s.backgroundColor, s.borderTopWidth]; }",
        regarder.element_handle())
    assert fond in ("rgba(0, 0, 0, 0)", "transparent"), f"fond encore teinté : {fond}"
    assert bordure == "0px", f"cadre encore tracé : {bordure}"
    expect(page.locator("#cg-signaux > li")).to_have_text("Rien à regarder.")

    # Dès qu'il y a UN signal, l'alerte revient — c'est là qu'elle vaut quelque chose.
    _servir(page, decor())
    page.reload(wait_until="networkidle")
    expect(page.locator("#cg-regarder-titre")).to_have_text("⚠ À regarder (16)")
    assert page.locator("#cg-regarder").evaluate("el => el.open") is True
    bordure = page.evaluate("(el) => getComputedStyle(el).borderTopWidth",
                            page.locator("#cg-regarder").element_handle())
    assert bordure != "0px", "l'alerte ne se rallume pas quand il y a quelque chose à voir"


def test_a_regarder_replie_un_code_au_dela_de_cinq_et_mene_a_la_fiche(page, live_server):
    """Décision de Hugo du 2026-09-17 : au-delà de cinq signaux du même code, une ligne
    dépliable ; les codes rares restent ligne à ligne, dans l'ordre du serveur."""
    _ouvrir(page, live_server, decor())
    regarder = page.locator("#cg-regarder")
    expect(page.locator("#cg-regarder-titre")).to_have_text("⚠ À regarder (16)")
    expect(regarder).to_have_attribute("open", "")
    lignes = page.locator("#cg-signaux > li")
    expect(lignes).to_have_count(4)
    expect(lignes.nth(0)).to_contain_text("Le groupe ancien-cours n'est pas dans l'annuaire")
    expect(lignes.nth(1)).to_contain_text("« Étude B » n'a pas de propriétaire")
    expect(lignes.nth(2)).to_contain_text("Théo Marchand (stagiaire) : identité changée")
    expect(lignes.nth(3).locator("summary")).to_have_text("13 comptes jamais venus")

    lignes.nth(3).locator("summary").click()
    lignes.nth(3).locator(".cg-lien", has_text="Sacha Benali").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Sacha Benali")
    expect(page.locator("#cg-fiche .cg-explique")).to_contain_text("corpus vide")
    # Le repli déplié ne se referme pas sous la main quand la fiche change.
    expect(lignes.nth(3).locator("details")).to_have_attribute("open", "")
    # Ni quand les données se RECHARGENT — ce qui suit tout geste sur la nature, refus
    # compris (ici un 404 : ce compte n'existe que dans la réponse interceptée). Le mutant
    # « le repli se referme au rendu » survivait aux assertions précédentes, qui ne
    # rechargeaient rien (2026-09-17).
    lignes.nth(2).locator(".cg-lien").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Théo Marchand")
    page.locator("#cg-nature").select_option("collectif")
    expect(page.locator("#cg-nature-msg")).to_contain_text("Aucun compte connu")
    expect(lignes.nth(3).locator("details")).to_have_attribute("open", "")


def test_la_marque_d_identite_changee_et_le_depart_disent_une_consequence(page, live_server):
    _ouvrir(page, live_server, decor(), "/administration?compte=stagiaire")
    expect(page.locator("#cg-fiche .cg-sous")).to_contain_text("identité changée 2")

    _ouvrir(page, live_server, decor(), "/administration?compte=proprio")
    depart = page.locator("#cg-fiche .cg-depart")
    expect(depart).not_to_have_attribute("open", "")
    depart.locator("summary").click()
    texte = depart.inner_text()
    assert "214 actes et 1 accès resteraient à ce login" in texte, texte
    # La doctrine d'AUTH-7 : une CONSÉQUENCE, jamais une recommandation — et rien sur une
    # règle `archives` qui n'existe pas.
    for interdit in ("recommand", "possible", "archives", "ne peut plus se connecter"):
        assert interdit not in texte, (interdit, texte)


# ── Les trois états de l'annuaire ──────────────────────────────────────────────────────


@pytest.mark.parametrize("etat,annonce,interdit", [
    ("lu", "Annuaire lu", "Non vérifié"),
    ("non_verifie", "Non vérifié : l'annuaire n'a pas répondu (délai dépassé)",
     "Aucun annuaire n'est configuré"),
    ("sans_annuaire", "Aucun annuaire n'est configuré", "Non vérifié"),
])
def test_chaque_etat_de_l_annuaire_se_dit_et_ne_bloque_rien(page, live_server, etat,
                                                             annonce, interdit):
    """Sans annuaire, rien n'est « non vérifié » : il n'y a rien à vérifier, et le dire
    ferait chercher une panne qui n'existe pas. En panne, l'écran le dit — et continue de
    montrer ce que l'application sait seule."""
    d = decor() if etat == "lu" else sans_lecture(decor(), etat)
    _ouvrir(page, live_server, d, "/administration?compte=proprio")
    expect(page.locator("#cg-annuaire")).to_contain_text(annonce)
    expect(page.locator("#cg-fiche-titre")).to_have_text("Paule Propriétaire")
    fiche = page.locator("#cg-fiche").inner_text()
    assert interdit not in fiche + page.locator("#cg-annuaire").inner_text()
    if etat == "lu":
        expect(page.locator("#cg-annuaire-lien")).to_be_visible()
    else:
        # Ce que l'application sait seule reste là : l'accès à son nom.
        expect(page.locator("#cg-fiche .cg-section", has_text="Collections").locator("li")
               ).to_have_count(1)
        expect(page.locator("#cg-annuaire-lien")).to_be_hidden()
        page.locator('#cg [data-axe="groupes"]').click()
        # Les lignes de premier niveau : celles du repli fermé se lisent vides.
        etats = page.locator("#cg-objets > li > .cg-objet .cg-etat").all_inner_texts()
        if etat == "non_verifie":
            assert set(etats) == {"non vérifié"}, etats
        else:
            assert "non vérifié" not in etats, etats


def test_un_refus_cache_le_bloc_une_panne_le_dit(page, live_server):
    _servir(page, decor(), statut=403)
    page.goto(live_server + "/administration", wait_until="networkidle")
    expect(page.locator("#cg-bloc")).to_be_hidden()

    page.unroute(ROUTE)
    _servir(page, decor(), statut=500)
    page.goto(live_server + "/administration", wait_until="networkidle")
    expect(page.locator("#cg-bloc")).to_be_visible()
    expect(page.locator("#cg-annuaire")).to_contain_text("n'a pas pu être lue")


# ── Les gestes qui passent par le serveur ──────────────────────────────────────────────


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_la_nature_se_declare_dans_la_fiche_et_le_serveur_l_enregistre(page, live_server,
                                                                       tmp_path):
    """Le seul geste d'écriture du bloc. Il passe par la VRAIE route, et l'état relu est
    celui de la base : c'est cette valeur qui décide si une mesure d'accord peut répondre."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30) as c:
        assert c.get("/api/moi", headers={"Remote-User": "salle-204"}).status_code == 200

    def nature_en_base():
        with sqlite3.connect(tmp_path / "live.sqlite") as base:
            return base.execute("SELECT nature FROM utilisateur WHERE login = ?",
                                ("salle-204",)).fetchone()[0]

    # La réponse interceptée relit la BASE à chaque chargement : l'écran recharge après le
    # geste, et doit alors montrer ce que le serveur a enregistré, pas ce qu'on a cliqué.
    def servir(route):
        d = decor()
        d["comptes"].append(_compte("salle-204", "Poste de la salle 204", jours=0,
                                    nature=nature_en_base()))
        route.fulfill(status=200, content_type="application/json", body=json.dumps(d))

    page.set_extra_http_headers(ADMIN)
    page.route(ROUTE, servir)
    page.goto(live_server + "/administration?compte=salle-204", wait_until="networkidle")
    expect(page.locator("#cg-fiche-titre")).to_have_text("Poste de la salle 204")

    select = page.locator("#cg-nature")
    with page.expect_request(lambda r: r.method == "PATCH") as envoi:
        select.select_option("collectif")
    assert json.loads(envoi.value.post_data) == {"nature": "collectif"}
    expect(page.locator("#cg-nature-msg")).to_have_text("Nature enregistrée.")
    expect(page.locator("#cg-nature")).to_be_focused()
    expect(page.locator("#cg-nature")).to_have_value("collectif")
    assert nature_en_base() == "collectif"

    # Un refus se lit sous le sélecteur, en rouge, n'est pas avalé — et le sélecteur revient
    # à ce que la base porte encore.
    page.route("**/api/comptes/*/nature", lambda route: route.fulfill(
        status=422, content_type="application/json",
        body=json.dumps({"detail": "Nature invalide pour le test."})))
    page.locator("#cg-nature").select_option("nominatif")
    expect(page.locator("#cg-nature-msg")).to_have_text("Nature invalide pour le test.")
    expect(page.locator("#cg-nature-msg")).to_have_class(re.compile(r"\berreur\b"))
    expect(page.locator("#cg-nature")).to_have_value("collectif")
    assert nature_en_base() == "collectif"


def test_regler_qui_entre_mene_a_la_fiche_de_la_collection(page, live_server):
    """« Régler qui entre » ouvrait le panneau voisin, sur la même page ; depuis l'étape 3
    d'AUTH-12, il mène à la collection dans la Bibliothèque, dépliée sur « Qui entre », le
    focus sur son titre. Seul le lien a changé : la fiche d'ici reste en lecture seule."""
    cid = _creer_collection(live_server, "Collection Test")
    _ouvrir(page, live_server, decor(cid=cid, cid2=cid + 1000),
            f"/administration?axe=collections&collection={cid}")
    expect(page.locator("#cg-fiche-titre")).to_have_text("Collection Test")
    qui = page.locator("#cg-fiche .cg-section", has_text="Qui entre")
    expect(qui.locator("li")).to_have_count(3)
    expect(qui.locator("input, select")).to_have_count(0)
    lien = page.locator("#cg-fiche a.cg-regler")
    expect(lien).to_have_attribute("href", f"/corpus?collection={cid}")
    lien.click()
    page.wait_for_url(f"**/corpus?collection={cid}")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    expect(item).to_have_attribute("open", "")
    expect(item.locator(".qe-titre")).to_be_focused()


def test_ouvrir_une_collection_a_ce_groupe_le_preselectionne(page, live_server):
    """« Ouvrir une collection à ce groupe… » attendait l'étape 3 : la collection choisie
    s'ouvre dans la Bibliothèque, le groupe déjà choisi dans la ligne d'ajout. Le geste se
    FAIT là-bas ; rien n'est accordé depuis cette fiche."""
    cid = _creer_collection(live_server, "Collection Test")
    _ouvrir(page, live_server, decor(cid=cid, cid2=cid + 1000),
            "/administration?axe=groupes&groupe=annotateurs")
    expect(page.locator("#cg-fiche-titre")).to_have_text("annotateurs")
    envois = []
    page.on("request", lambda r: envois.append(r.url) if r.method != "GET" else None)
    page.locator("#cg-ouvrir-a").select_option(str(cid))
    page.locator("#cg-fiche [data-cg-ouvrir]").click()
    page.wait_for_url(f"**/corpus?collection={cid}&groupe=annotateurs")
    item = page.locator(f'#col-body .col-item[data-id="{cid}"]')
    # `annotateurs` est dans la doublure de l'annuaire : il est CHOISI dans la liste, pas tapé.
    expect(item.locator(".qe-choix")).to_have_value("groupe:annotateurs")
    expect(item.locator(".qe-libre")).to_be_hidden()
    assert envois == [], f"une écriture est partie sans geste : {envois}"


# ── Sur la vraie route ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_sur_la_vraie_route_un_acces_mort_se_signale_et_mene_a_ses_fiches(page, live_server):
    """Sans interception : la route d'AUTH-6 et la doublure de l'annuaire que `live_server`
    charge. Un accès accordé à un groupe que l'annuaire ne connaît pas est le cas que la
    lecture de l'annuaire existe pour montrer — il n'ouvre rien, et rien ne le disait."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        r = c.post("/api/collections", json={"nom": "Étude B"})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        r = c.put(f"/api/collections/{cid}/acces",
                  json={"genre": "groupe", "principal": "ancien-cours", "niveau": "lecture"})
        assert r.status_code in (200, 201, 204), r.text

    page.set_extra_http_headers(ADMIN)
    page.goto(live_server + "/administration", wait_until="networkidle")
    expect(page.locator("#cg-annuaire")).to_contain_text("Annuaire lu")
    # Une doublure qui ne se dirait pas passerait pour l'annuaire de l'instance.
    expect(page.locator("#cg-annuaire")).to_contain_text("Doublure de test")
    signal = page.locator("#cg-signaux > li").first
    expect(signal).to_contain_text(
        "Le groupe ancien-cours n'est pas dans l'annuaire (accès à « Étude B »)")
    expect(page.locator("#cg-signaux details.cg-replie > summary")).to_contain_text(
        re.compile(r"^\d+ comptes jamais venus$"))

    signal.locator(".cg-lien").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("ancien-cours")
    expect(page.locator("#cg-fiche .cg-puce.rouge")).to_have_text("absent de l'annuaire")
    expect(page.locator("#cg-fiche .cg-explique")).to_contain_text("n'ouvrent rien")

    page.locator("#cg-fiche .cg-lien", has_text="Étude B").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Étude B")
    expect(page.locator("#cg-fiche .cg-sous")).to_contain_text("sans propriétaire")
    qui = page.locator("#cg-fiche .cg-section", has_text="Qui entre").locator("li")
    expect(qui).to_have_count(1)
    expect(qui).to_contain_text("ancien-cours")
    expect(qui).to_contain_text("absent de l'annuaire")


# ── Au large : un cadre de taille connue ───────────────────────────────────────────────


def test_au_large_le_cadre_ne_suit_pas_le_nombre_d_entrees(page, live_server):
    """La hauteur est FIXE (2026-09-22) : dix-sept comptes ou deux collections, le cadre ne
    bouge pas, et c'est la liste qui défile dedans. Jusque-là, le cadre suivait la liste, et
    tout ce qui venait après lui se déplaçait à chaque changement d'axe."""
    page.set_viewport_size({"width": 1400, "height": 600})
    _ouvrir(page, live_server, decor())
    cadre, liste = page.locator("#cg"), page.locator(".cg-liste")
    hauteur = cadre.bounding_box()["height"]
    assert liste.evaluate("e => e.scrollHeight > e.clientHeight"), \
        "dix-sept comptes dans une fenêtre de 600 px : la liste doit défiler dans le cadre"
    page.locator('.cg-axes button[data-axe="collections"]').click()
    expect(page.locator("#cg-objets .cg-objet")).to_have_count(2)
    assert cadre.bounding_box()["height"] == hauteur
    assert liste.evaluate("e => e.scrollHeight <= e.clientHeight")


def test_le_bloc_entier_tient_dans_une_fenetre_courte(page, live_server):
    """Le cadre se compte depuis SON haut, pas depuis celui de la page : titre, phrase et
    ligne de l'annuaire pris, le bloc amené en tête de la zone qui défile tient dans la
    fenêtre. Trouvé par Hugo le 2026-09-23 en jouant la passe à 1280 × 500 : le cadre
    dépassait, la PAGE défilait à sa place, et la liste — à qui il restait plus de place
    qu'elle n'en demandait — ne défilait plus du tout. Un cadre de taille fixe qui déborde
    ne sert plus à rien."""
    page.set_viewport_size({"width": 1280, "height": 500})
    _ouvrir(page, live_server, decor())
    page.evaluate("document.querySelector('#cg-bloc').scrollIntoView({block: 'start'})")
    bas = page.locator("#cg").evaluate("e => e.getBoundingClientRect().bottom")
    assert bas <= page.evaluate("window.innerHeight")
    liste = page.locator(".cg-liste")
    assert liste.evaluate("e => e.scrollHeight > e.clientHeight")


def test_au_large_la_fiche_met_ses_deux_sections_cote_a_cote(page, live_server):
    """La largeur ne sert que si la fiche s'en sert : ses deux sections côte à côte, et une
    section seule — la collection n'a que « Qui entre » — sur toute la largeur de la carte."""
    page.set_viewport_size({"width": 1400, "height": 800})
    _ouvrir(page, live_server, decor())
    page.locator("#cg-objets .cg-objet", has_text="Léa Lectrice").click()
    sections = page.locator("#cg-fiche .cg-section")
    groupes, collections = sections.nth(0).bounding_box(), sections.nth(1).bounding_box()
    assert abs(groupes["y"] - collections["y"]) < 1
    assert collections["x"] >= groupes["x"] + groupes["width"]

    page.locator('.cg-axes button[data-axe="collections"]').click()
    page.locator("#cg-objets .cg-objet", has_text="Collection Test").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("Collection Test")
    carte = page.locator("#cg-fiche .cg-carte").bounding_box()
    assert abs(page.locator("#cg-fiche .cg-section").bounding_box()["width"]
               - carte["width"]) < 1


def test_une_fiche_neuve_s_ouvre_en_haut(page, live_server):
    """La fiche défile seule, donc elle garde sa position d'un rendu à l'autre. Deux groupes
    de même longueur, exprès : vers une fiche COURTE, le navigateur ramènerait de lui-même
    la position à zéro, et le test passerait sans que l'écran y soit pour rien."""
    d = decor()
    d["groupes"].append(_groupe("etudiants-bd-2025", ETUDIANTS, gid=7))
    page.set_viewport_size({"width": 1400, "height": 500})
    _ouvrir(page, live_server, d)
    page.locator('.cg-axes button[data-axe="groupes"]').click()
    page.locator("#cg-objets .cg-objet", has_text="etudiants-bd-2026").click()
    fiche = page.locator("#cg-fiche")
    assert fiche.evaluate("e => e.scrollHeight > e.clientHeight"), \
        "douze membres dans une fenêtre de 500 px : la fiche doit défiler"
    fiche.evaluate("e => { e.scrollTop = e.scrollHeight; }")
    assert fiche.evaluate("e => e.scrollTop") > 0
    page.locator("#cg-objets .cg-objet", has_text="etudiants-bd-2025").click()
    expect(page.locator("#cg-fiche-titre")).to_have_text("etudiants-bd-2025")
    assert fiche.evaluate("e => e.scrollTop") == 0


# ── Seuil étroit ───────────────────────────────────────────────────────────────────────


def test_a_375_px_la_fiche_remplace_la_liste_et_revient(page, live_server):
    page.set_viewport_size({"width": 375, "height": 800})
    _ouvrir(page, live_server, decor())
    page.locator("#cg-objets .cg-objet", has_text="Léa Lectrice").click()
    expect(page.locator(".cg-liste")).to_be_hidden()
    expect(page.locator("#cg-fiche-titre")).to_be_focused()
    page.locator("#cg-fiche .cg-retour").click()
    expect(page.locator(".cg-liste")).to_be_visible()
    expect(page.locator("#cg-fiche")).to_be_hidden()
    expect(page.locator('#cg-objets .cg-objet[aria-current="true"]')).to_be_focused()
