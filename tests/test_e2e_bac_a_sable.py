"""COL-4 — l'écran du bac à sable, joué dans un vrai navigateur, sous chaque identité.

La forme a été tranchée par Hugo sur maquette le 2026-10-24 (`pilotage/COL-4.md`, zone
« L'écran »). Chaque test joue un geste de la fiche sous l'identité qui le VOIT, et vérifie
ce qu'elle NE voit PAS sous les autres :

- `camille`, une arrivante SANS AUCUN accès : « Mon bac à sable » dans la bande, dans le
  bandeau de portée vide (visible sans déplier) et dans la page vide ; le premier clic ;
  la ligne, inviter, remettre à neuf, le plafond, l'effacement du lundi ;
- `lea`, qui a déjà un projet : la bande seule l'offre, ni la page vide ni le menu du
  compte ; recliquer ramène ;
- `dominique`, invitée chez camille : « Bac · camille » dans le sélecteur, « Bac à sable de
  camille » et « Quitter… » seul dans la ligne ;
- `hugo`, administrateur : l'axe « Bacs à sable » de l'Administration, la fiche d'un bac
  où il n'entre pas — et dans le sien, un arrivant.

**Les requêtes PARTIES sont mesurées**, pas seulement l'état final : un clic qui ouvrirait
un second bac à sable, une invitation qui partirait comme responsable ou lirait l'annuaire,
passeraient une relecture de l'écran.

Un serveur derrière le proxy (`live_server` à `True`), et un JEU synthétique préparé par
l'outil de production (`tools/preparer_jeu.py`, en sous-processus sur la base du serveur) :
le parcours d'abord, puis un exemple et un stock.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from playwright.sync_api import expect  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import database  # noqa: E402
import main  # noqa: E402
from conftest import make_png  # noqa: E402
from test_jeu import ecrire_jeu  # noqa: E402
from tools.mesurer_reflow import ECRASEMENT, SONDE, decrire_ecrasement  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — la déclaration que `tests/test_surfaces.py` confronte aux surfaces servies : la
# ligne du bac à sable vit sur les CINQ, et c'est ce qu'on mesure.
SURFACES_AUDITEES = {
    "/": "Atelier",
    "/recherche": "Recherche",
    "/corpus": "Bibliothèque",
    "/exploration": "Exploration",
    "/administration": "Administration",
}
SURFACES_HORS_PERIMETRE = {}

CAMILLE = {"Remote-User": "camille"}
LEA = {"Remote-User": "lea"}
DOMINIQUE = {"Remote-User": "dominique"}
HUGO = {"Remote-User": "hugo", "Remote-Groups": "bd-admins"}
ECRIRE = {main.EN_TETE_REQUETE: "1"}

POLICES = (16, 20, 24)
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

# Le jeu : un document par rôle, le parcours en DEUX planches (la première est celle où
# l'on arrive), un exemple, un stock.
JEU = [
    {"cle": "parcours", "titre": "Le parcours", "role": "pas-a-pas", "rang": 1,
     "planches": [{"fichier": "p1.png"}, {"fichier": "p2.png"}]},
    {"cle": "exemple", "titre": "Un exemple", "role": "exemple",
     "planches": [{"fichier": "p3.png"}]},
    {"cle": "stock", "titre": "Le stock", "role": "stock",
     "planches": [{"fichier": "p1.png"}]},
]


# ── Outils ─────────────────────────────────────────────────────────────────────────────

def _api(base, qui, methode, chemin, corps=None, fichier=None):
    with httpx.Client(base_url=base, trust_env=False, timeout=60,
                      headers={**qui, **ECRIRE}) as c:
        if fichier is not None:
            r = c.request(methode, chemin, files={"file": fichier})
        else:
            r = c.request(methode, chemin, json=corps)
        assert r.status_code < 300, f"{methode} {chemin} → {r.status_code} {r.text}"
        return r.json() if r.content else None


def _env_serveur(tmp_path):
    return {**os.environ, "BD_DATA_DIR": str(tmp_path),
            "BD_DB_PATH": str(tmp_path / "live.sqlite")}


def _outil(tmp_path, *args):
    r = subprocess.run([sys.executable, *args], cwd=str(RACINE), env=_env_serveur(tmp_path),
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0, f"{args} → {r.returncode}\n{r.stdout}\n{r.stderr}"
    return r.stdout


def _date_attendue(efface_le):
    """« lundi 26 octobre à 4 h », calculé à part de l'écran : la règle de Paris du serveur
    (`database.decalage_de_paris`) et des noms écrits ici."""
    t = datetime.strptime(efface_le, "%Y-%m-%d %H:%M:%S")
    p = t + database.decalage_de_paris(t)
    heure = f"{p.hour} h" if p.minute == 0 else f"{p.hour} h {p.minute:02d}"
    return f"{JOURS[p.weekday()]} {p.day} {MOIS[p.month - 1]} à {heure}"


def _preference_police(page, police):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Page.setFontSizes", {"fontSizes": {"standard": police, "fixed": police}})


def _requetes(page):
    """Les requêtes d'API PARTIES de la page, (méthode, chemin, corps)."""
    vues = []

    def noter(req):
        if "/api/" in req.url:
            chemin = re.sub(r"^https?://[^/]+", "", req.url)
            vues.append((req.method, chemin, req.post_data))
    page.on("request", noter)
    return vues


def _sous(page, qui):
    page.set_extra_http_headers(qui)


@pytest.fixture
def jeu(live_server, tmp_path):
    """Le serveur derrière le proxy, et le jeu préparé par l'outil de production."""
    depot = ecrire_jeu(tmp_path / "jeu-depot", JEU, images=("p1.png", "p2.png", "p3.png"))
    _outil(tmp_path, "tools/preparer_jeu.py", "--depot", str(depot), "--appliquer")
    for qui in (CAMILLE, LEA, DOMINIQUE, HUGO):
        _api(live_server, qui, "GET", "/api/moi")
    return {"base": live_server, "tmp": tmp_path}


def _ouvrir(jeu, qui):
    """Le bac à sable de `qui`, ouvert par l'API (le geste de l'écran se joue ailleurs)."""
    return _api(jeu["base"], qui, "POST", "/api/bac-a-sable")


def _inviter(jeu, proprio, bac_id, login):
    _api(jeu["base"], proprio, "PUT", f"/api/projets/{bac_id}/membres",
         {"genre": "utilisateur", "principal": login, "role": "membre"})


def _projet_de_lea(jeu):
    pid = _api(jeu["base"], HUGO, "POST", "/api/projets", {"nom": "Corpus test"})["id"]
    _api(jeu["base"], HUGO, "PUT", f"/api/projets/{pid}/membres",
         {"genre": "utilisateur", "principal": "lea", "role": "membre"})
    return pid


def _ligne(page):
    loc = page.locator("#bac-ligne")
    expect(loc).to_be_visible()
    return loc


def _dialogue(page):
    loc = page.locator("#bac-modal")
    expect(loc).to_be_visible()
    return loc


pytestmark_proxy = pytest.mark.parametrize("live_server", [True], indirect=True)


# ── Le premier clic ────────────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_premier_clic_depuis_le_bandeau(page, jeu):
    """camille, sans aucun accès : le bandeau porte « Mon bac à sable » à droite, visible
    SANS déplier ; un clic ouvre UN bac à sable et mène à l'Atelier, sur la planche du
    parcours ; la bande dit « Mon bac à sable », la ligne paraît, le bandeau se masque."""
    _sous(page, CAMILLE)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    bandeau = page.locator("#portee-vide")
    expect(bandeau).to_be_visible()
    assert page.evaluate("() => document.querySelector('#portee-vide details').open") is False
    geste = bandeau.locator(".portee-vide-geste button")
    expect(geste).to_be_visible()
    expect(geste).to_have_text("Mon bac à sable")
    expect(bandeau.locator(".portee-vide-geste")).to_contain_text("En attendant :")
    geste.click()
    page.wait_for_url(re.compile(r"/\?album=\d+&planche=\d+$"))
    page.wait_for_load_state("networkidle")
    ouverts = [v for v in vues if v[0] == "POST" and v[1] == "/api/bac-a-sable"]
    assert len(ouverts) == 1, ouverts
    vue = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    parcours = next(j for j in vue["jeu"] if j["role"] == "pas-a-pas")
    assert page.url.endswith(f"/?album={parcours['album_id']}&planche={parcours['planche_ids'][0]}")
    expect(page.locator("#projet-nom")).to_have_text("Mon bac à sable")
    expect(page.locator("#planche-info")).to_contain_text("Le parcours")
    expect(page.locator("#planche-list li.active")).to_have_count(1)
    _ligne(page)
    expect(page.locator("#portee-vide")).to_be_hidden()
    expect(page.locator(".bac-ouvrir-bande")).to_have_count(0)


@pytestmark_proxy
def test_premier_clic_offert_par_la_bande_et_la_page_vide(page, jeu):
    """Avant tout bac à sable, sous camille : la bande et la page vide de l'Atelier l'offrent,
    la fiche de la Bibliothèque en carte ; le menu du compte ne l'offre pas. Le bouton de la
    bande est À CÔTÉ du projet — ici, sans projet, avant la pastille."""
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    bande = page.locator("#site-nav .bac-ouvrir-bande")
    expect(bande).to_be_visible()
    expect(page.locator("#stage-empty .bac-vide-geste button")).to_be_visible()
    expect(page.locator("#stage-empty")).to_contain_text("Sélectionnez ou importez une planche")
    page.locator(".user-chip button.user-who").click()
    expect(page.locator(".compte-panel")).to_be_visible()
    expect(page.locator(".compte-panel")).not_to_contain_text("bac à sable")
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    carte = page.locator("#bi-bac-carte .bac-vide-carte")
    expect(carte).to_be_visible()
    expect(carte.locator("button")).to_have_text("Mon bac à sable")
    # Depuis la bande : un clic, le même chemin.
    page.locator("#site-nav .bac-ouvrir-bande").click()
    page.wait_for_url(re.compile(r"/\?album=\d+&planche=\d+$"))
    _ligne(page)


@pytestmark_proxy
def test_un_compte_partage_se_voit_offrir_le_sien(page, jeu):
    """Hugo, 2026-10-24, qui renverse S1 : un compte PARTAGÉ a son bac à sable. Déclaré
    `collectif` par l'administrateur, `groupe-tp` voit « Mon bac à sable » dans la bande et
    dans le bandeau ; un clic l'ouvre, et sa ligne porte les gestes du propriétaire,
    « Remettre à neuf… » compris."""
    tp = {"Remote-User": "groupe-tp"}
    _api(jeu["base"], tp, "GET", "/api/moi")
    _api(jeu["base"], HUGO, "PATCH", "/api/comptes/groupe-tp/nature", {"nature": "collectif"})
    _sous(page, tp)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    expect(page.locator("#site-nav .bac-ouvrir-bande")).to_be_visible()
    expect(page.locator("#portee-vide .portee-vide-geste button")).to_be_visible()
    page.locator("#site-nav .bac-ouvrir-bande").click()
    page.wait_for_url(re.compile(r"/\?album=\d+&planche=\d+$"))
    page.wait_for_load_state("networkidle")
    assert len([v for v in vues if v[0] == "POST" and v[1] == "/api/bac-a-sable"]) == 1
    ligne = _ligne(page)
    expect(ligne.locator(".bac-nom")).to_have_text("Bac à sable")
    expect(ligne.locator("#bac-inviter")).to_be_visible()
    expect(ligne.locator("#bac-remettre")).to_have_text("Remettre à neuf…")


@pytestmark_proxy
def test_qui_a_deja_un_projet_le_trouve_dans_la_bande_seulement(page, jeu):
    """lea a un projet : la bande l'offre, à côté du projet ; ni la page vide, ni la carte
    de la Bibliothèque, ni le menu du compte ; aucun bandeau de portée vide."""
    _projet_de_lea(jeu)
    _sous(page, LEA)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    bande = page.locator("#site-nav .bac-ouvrir-bande")
    expect(bande).to_be_visible()
    # À côté du projet : juste après lui dans la bande.
    assert page.evaluate("""() => {
      const p = document.querySelector('#site-nav .projet-courant');
      return !!p && p.nextElementSibling === document.querySelector('.bac-ouvrir-bande'); }""")
    expect(page.locator(".bac-vide-geste")).to_have_count(0)
    expect(page.locator("#portee-vide")).to_have_count(0)
    page.locator(".user-chip button.user-who").click()
    expect(page.locator(".compte-panel")).not_to_contain_text("bac à sable")
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    expect(page.locator("#bi-accueil-titre")).to_be_visible()
    expect(page.locator(".bac-vide-carte")).to_have_count(0)


@pytestmark_proxy
def test_recliquer_ramene_au_meme_bac_a_sable(page, jeu):
    """lea ouvre le sien depuis la bande, repasse sur son projet par le sélecteur, puis
    choisit « Mon bac à sable » : le même, sans en ouvrir un second ; la bande ne porte plus
    le bouton."""
    pid = _projet_de_lea(jeu)
    _sous(page, LEA)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    page.locator("#site-nav .bac-ouvrir-bande").click()
    page.wait_for_url(re.compile(r"/\?album=\d+&planche=\d+$"))
    page.wait_for_load_state("networkidle")
    mien = _api(jeu["base"], LEA, "GET", "/api/bac-a-sable")["id"]
    choix = page.locator("#projet-choix")
    expect(choix).to_be_visible()
    expect(page.locator(".bac-ouvrir-bande")).to_have_count(0)
    choix.select_option(str(pid))
    expect(page.locator("#bac-ligne")).to_have_count(0)
    expect(page.locator(".bac-ouvrir-bande")).to_have_count(0)
    choix.select_option(str(mien))
    _ligne(page)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    expect(page.locator("#projet-choix")).to_have_value(str(mien))
    assert len([v for v in vues if v[0] == "POST" and v[1] == "/api/bac-a-sable"]) == 1
    assert len([p for p in _api(jeu["base"], LEA, "GET", "/api/projets")
                if p.get("bac_a_sable")]) == 1


# ── La ligne ───────────────────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_la_ligne_du_proprietaire_sur_les_cinq_surfaces(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, CAMILLE)
    date = _date_attendue(bac["efface_le"])
    for surface in SURFACES_AUDITEES:
        page.goto(jeu["base"] + surface, wait_until="networkidle")
        ligne = _ligne(page)
        expect(ligne.locator(".bac-nom")).to_have_text("Bac à sable")
        expect(ligne.locator(".bac-date")).to_have_text(f"s'efface {date}")
        expect(ligne.locator(".bac-plafond")).to_have_text("0 / 50 planches importées")
        expect(ligne.locator("#bac-inviter")).to_have_text("Inviter… (1)")
        expect(ligne.locator("#bac-remettre")).to_have_text("Remettre à neuf…")
        expect(ligne.locator("#bac-quitter")).to_have_count(0)
        expect(ligne.locator("text=Par où commencer")).to_have_count(0)
        assert "chaque lundi à 4 h" in ligne.locator(".bac-nom").get_attribute("title")
        # Le bandeau « Aucune collection » n'y paraît pas — il existe, masqué.
        expect(page.locator("#portee-vide")).to_be_hidden()
    # La ligne est la DERNIÈRE rangée de la bande, et la bande 1 ne recouvre pas la 2.
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    # Le bandeau MASQUÉ ne prend plus de rangée dans la grille de l'Atelier : le canevas a
    # toute la hauteur du corps (sans quoi il tomberait dans une rangée haute de son seul
    # contenu).
    g = page.evaluate("""() => { const b = document.getElementById('body').getBoundingClientRect(),
      v = document.getElementById('viewer').getBoundingClientRect();
      return { corps: b.height, canevas: v.height, haut: v.top - b.top }; }""")
    assert g["haut"] <= 1 and g["canevas"] >= g["corps"] - 1, g
    assert page.evaluate("""() => {
      const n = document.getElementById('site-nav'), l = document.getElementById('bac-ligne');
      const h = document.getElementById('header');
      return n.lastElementChild === l
        && l.getBoundingClientRect().bottom <= h.getBoundingClientRect().top + 1; }""")


@pytestmark_proxy
def test_hors_du_bac_a_sable_la_ligne_part_et_le_bandeau_revient(page, jeu):
    """dominique, invitée chez camille et sans autre accès : dans le bac la ligne, hors de
    lui (Bac à sable quitté, rien d'autre) le bandeau. Ici on change de projet en l'ouvrant
    elle-même : son bac à elle et celui de camille."""
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    sien = _ouvrir(jeu, DOMINIQUE)
    _sous(page, DOMINIQUE)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    choix = page.locator("#projet-choix")
    choix.select_option(str(bac["id"]))
    expect(_ligne(page).locator(".bac-nom")).to_have_text("Bac à sable de camille")
    choix.select_option(str(sien["id"]))
    expect(_ligne(page).locator(".bac-nom")).to_have_text("Bac à sable")
    expect(page.locator("#portee-vide")).to_be_hidden()


@pytestmark_proxy
def test_l_invitee_lit_bac_point_login_et_ne_peut_que_quitter(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, DOMINIQUE)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    # Elle n'a que lui : le nom seul, entier.
    expect(page.locator("#projet-nom")).to_have_text("Bac · camille")
    ligne = _ligne(page)
    expect(ligne.locator(".bac-nom")).to_have_text("Bac à sable de camille")
    expect(ligne.locator(".bac-date")).to_have_text(f"s'efface {_date_attendue(bac['efface_le'])}")
    expect(ligne.locator("#bac-quitter")).to_have_text("Quitter…")
    for absent in ("#bac-inviter", "#bac-remettre", ".bac-plafond"):
        expect(ligne.locator(absent)).to_have_count(0)
    # Elle peut encore ouvrir le sien.
    expect(page.locator(".bac-ouvrir-bande")).to_be_visible()
    ligne.locator("#bac-quitter").click()
    d = _dialogue(page)
    expect(d.locator("h3")).to_have_text("Quitter le bac à sable de camille ?")
    expect(d).to_contain_text("camille pourra vous inviter à nouveau.")
    d.get_by_role("button", name="Quitter").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#toasts")).to_contain_text("Vous avez quitté le bac à sable de camille.")
    expect(page.locator("#bac-ligne")).to_have_count(0)
    expect(page.locator("#projet-nom")).to_have_count(0)
    expect(page.locator("#portee-vide")).to_be_visible()
    assert ("POST", f"/api/bac-a-sable/{bac['id']}/quitter", None) in vues
    assert bac["id"] not in {p["id"] for p in _api(jeu["base"], DOMINIQUE, "GET", "/api/projets")}


# ── Remettre à neuf ────────────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_remettre_a_neuf_dit_ce_qui_part_et_ce_qui_revient(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, CAMILLE)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    _ligne(page).locator("#bac-remettre").click()
    d = _dialogue(page)
    expect(d.locator("h3")).to_have_text("Remettre votre bac à sable à neuf ?")
    cols = d.locator(".bac-deux-col > div")
    expect(cols).to_have_count(2)
    expect(cols.nth(0).locator("strong")).to_have_text("Ce qui part")
    expect(cols.nth(0)).to_contain_text("l'invitation de dominique")
    expect(cols.nth(0)).to_contain_text("le travail de dominique")
    expect(cols.nth(1).locator("strong")).to_have_text("Ce qui revient")
    expect(cols.nth(1)).to_contain_text("les 3 albums du jeu, vierges")
    # « Annuler » ne change rien : le dialogue se cache, aucune remise ne part.
    d.get_by_role("button", name="Annuler").click()
    expect(page.locator("#bac-modal")).to_be_hidden()
    assert not [v for v in vues if v[1] == "/api/bac-a-sable/remise-a-neuf"]
    assert _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")["id"] == bac["id"]
    # Pour de bon : un bac neuf, la page repart sur lui — la même surface, sans adresse —,
    # le dit, et « Inviter… » ne compte personne.
    page.goto(jeu["base"] + f"/corpus?collection={bac['base']['id']}", wait_until="networkidle")
    _ligne(page).locator("#bac-remettre").click()
    _dialogue(page).get_by_role("button", name="Remettre à neuf").click()
    page.wait_for_url(re.compile(r"/corpus$"))
    page.wait_for_load_state("networkidle")
    expect(page.locator("#toasts")).to_contain_text("Bac à sable remis à neuf.")
    neuf = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    assert neuf["id"] != bac["id"]
    expect(_ligne(page).locator("#bac-inviter")).to_have_text("Inviter…")
    expect(page.locator("#projet-nom")).to_have_text("Mon bac à sable")
    assert len([v for v in vues if v[1] == "/api/bac-a-sable/remise-a-neuf"]) == 1
    # Dans l'Atelier, la planche du parcours, comme au premier clic, et le message (Hugo,
    # 2026-10-24).
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    _ligne(page).locator("#bac-remettre").click()
    # L'Atelier récrit déjà son adresse sur l'album ouvert : on attend la NAVIGATION.
    with page.expect_navigation() as nav:
        _dialogue(page).get_by_role("button", name="Remettre à neuf").click()
    page.wait_for_load_state("networkidle")
    encore = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")
    parcours = next(j for j in encore["jeu"] if j["role"] == "pas-a-pas")
    assert encore["id"] != neuf["id"]
    # L'adresse DEMANDÉE, et non celle que l'Atelier récrit ensuite sur l'album ouvert —
    # qui peut être le parcours par défaut et masquer un retour sur « / ».
    cible = f"/?album={parcours['album_id']}&planche={parcours['planche_ids'][0]}"
    assert nav.value.url.endswith(cible), nav.value.url
    assert page.url.endswith(cible)
    expect(page.locator("#toasts")).to_contain_text("Bac à sable remis à neuf.")
    expect(page.locator("#planche-info")).to_contain_text("Le parcours")


# ── Inviter ────────────────────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_inviter_fait_entrer_un_compte_comme_membre(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    _ligne(page).locator("#bac-inviter").click()
    d = _dialogue(page)
    expect(d.locator("h3")).to_have_text("Qui y entre")
    expect(d.locator(".mp-ligne")).to_have_count(1)
    expect(d.locator(".mp-ligne").first).to_contain_text("camille")
    expect(d.locator(".mp-ligne").first).to_contain_text("responsable")
    expect(d.locator(".mp-ligne").first.locator(".mp-sortir")).to_have_count(0)
    # Ni rôle à choisir, ni groupe, ni annuaire.
    for absent in (".mp-role", ".mp-choix", ".mp-genre", ".col-note-admin"):
        expect(d.locator(absent)).to_have_count(0)
    champ = d.locator(".mp-nom")
    expect(champ).to_be_focused()
    champ.fill("dominique")
    d.get_by_role("button", name="+ Faire entrer").click()
    expect(d.locator(".mp-ligne")).to_have_count(2)
    expect(d.locator(".mp-ligne").nth(1)).to_contain_text("dominique")
    expect(d.locator(".mp-ligne").nth(1)).to_contain_text("membre")
    expect(d.locator(".mp-msg")).to_contain_text("dominique entre dans votre bac à sable, comme membre.")
    puts = [v for v in vues if v[0] == "PUT" and v[1] == f"/api/projets/{bac['id']}/membres"]
    assert len(puts) == 1 and '"role":"membre"' in puts[0][2].replace(" ", "") \
        and '"genre":"utilisateur"' in puts[0][2].replace(" ", ""), puts
    assert not [v for v in vues if v[1].endswith("/membres/choix")], "l'annuaire a été lu"
    d.get_by_role("button", name="Fermer").click()
    expect(page.locator("#bac-modal")).to_be_hidden()
    expect(page.locator("#bac-inviter")).to_have_text("Inviter… (1)")
    expect(page.locator("#bac-inviter")).to_be_focused()
    # ✕ le fait sortir.
    page.locator("#bac-inviter").click()
    d = _dialogue(page)
    d.get_by_role("button", name="Faire sortir dominique du bac à sable").click()
    expect(d.locator(".mp-ligne")).to_have_count(1)
    d.get_by_role("button", name="Fermer").click()
    expect(page.locator("#bac-inviter")).to_have_text("Inviter…")


# ── Le plafond ─────────────────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_le_plafond_eteint_l_import_la_raison_en_infobulle(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    album = _api(jeu["base"], CAMILLE, "POST", "/api/albums",
                 {"titre": "Mes essais", "collection_id": bac["base"]["id"]})["id"]
    _sous(page, CAMILLE)
    # À 49, l'import reste offert.
    for i in range(49):
        _api(jeu["base"], CAMILLE, "POST", f"/api/albums/{album}/import",
             fichier=(f"p{i:02d}.png", make_png(60, 80), "image/png"))
    page.goto(jeu["base"] + f"/corpus?album={album}", wait_until="networkidle")
    expect(_ligne(page).locator(".bac-plafond")).to_have_text("49 / 50 planches importées")
    bouton = page.locator("#bi-importer")
    expect(bouton).to_be_visible()
    assert bouton.get_attribute("aria-disabled") is None
    _api(jeu["base"], CAMILLE, "POST", f"/api/albums/{album}/import",
         fichier=("p49.png", make_png(60, 80), "image/png"))
    page.goto(jeu["base"] + f"/corpus?album={album}", wait_until="networkidle")
    compte = _ligne(page).locator(".bac-plafond")
    expect(compte).to_have_text("50 / 50 planches importées")
    expect(compte).to_have_class(re.compile(r"\best-plein\b"))
    # L'encre d'alerte : la couleur calculée du compte est celle de `--ink-red`.
    encre = page.evaluate("""() => {
      const s = document.createElement('span'); s.style.color = 'var(--ink-red)';
      document.body.appendChild(s); const attendu = getComputedStyle(s).color; s.remove();
      return [getComputedStyle(document.querySelector('.bac-plafond')).color, attendu]; }""")
    assert encre[0] == encre[1], encre
    bouton = page.locator("#bi-importer")
    expect(bouton).to_have_attribute("aria-disabled", "true")
    assert bouton.get_attribute("title").startswith("Plafond atteint : 50 planches importées sur 50")
    # Le clic ne fait rien : le sélecteur de fichiers ne s'ouvre pas. (Un clic DOM :
    # Playwright refuse de cliquer un élément `aria-disabled`, qu'un humain atteint.)
    ouverts = []
    page.on("filechooser", lambda fc: ouverts.append(fc))
    bouton.dispatch_event("click")
    page.wait_for_timeout(400)
    assert not ouverts, "le sélecteur de fichiers s'est ouvert au plafond"
    # L'Atelier, « au même endroit du geste » : le menu « Import / Export » et le ⤓ de la
    # liste des planches.
    page.goto(jeu["base"] + f"/?album={album}", wait_until="networkidle")
    for sel in ("#btn-import-menu", "#btn-import"):
        b = page.locator(sel)
        # Éteint et non désactivé : il garde le focus, et sa raison est sa DESCRIPTION.
        expect(b).to_have_attribute("aria-disabled", "true")
        assert b.get_attribute("disabled") is None, sel
        assert b.get_attribute("title").startswith("Plafond atteint"), sel
        expect(b).to_have_accessible_description(re.compile(r"^Plafond atteint : 50 planches"))
        # Une description ÉCRITE, joignable au clavier — pas la seule infobulle, que le
        # navigateur lit aussi en description et qui disparaîtrait avec elle.
        desc = b.get_attribute("aria-describedby")
        assert desc, sel
        expect(page.locator(f"#{desc}")).to_have_text(re.compile(r"^Plafond atteint : 50 planches"))
        b.dispatch_event("click")
    expect(page.locator("#btn-import")).to_have_accessible_name("Importer une planche")
    page.locator("#btn-import").focus()
    expect(page.locator("#btn-import")).to_be_focused()
    page.wait_for_timeout(300)
    assert not ouverts, "le sélecteur de fichiers s'est ouvert depuis l'Atelier au plafond"
    # Le serveur, lui, refuse de toute façon.
    with httpx.Client(base_url=jeu["base"], trust_env=False, timeout=30,
                      headers={**CAMILLE, **ECRIRE}) as c:
        r = c.post(f"/api/albums/{album}/import",
                   files={"file": ("p50.png", make_png(60, 80), "image/png")})
    assert r.status_code == 409


@pytestmark_proxy
def test_sous_le_plafond_l_import_de_l_atelier_reste_offert(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    for sel in ("#btn-import-menu", "#btn-import"):
        expect(page.locator(sel)).to_be_enabled()
    assert bac["planches_importees"] == 0


# ── L'effacement du lundi ──────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_l_effacement_se_dit_a_la_requete_suivante(page, jeu):
    """Bac à sable ouvert dans l'Atelier ; l'outil d'effacement passe ; on agit : le
    message paraît, la page retombe vide, et les places de « Mon bac à sable » reviennent."""
    bac = _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    # Le navigateur vit APRÈS l'échéance, comme le lundi à 4 h : l'horloge de la page est
    # posée une seconde après `efface_le` (le serveur, lui, efface quand l'outil le dit).
    page.clock.set_fixed_time(datetime.strptime(bac["efface_le"], "%Y-%m-%d %H:%M:%S")
                              .replace(second=1, tzinfo=timezone.utc))
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    _ligne(page)
    planches = page.locator("#planche-list li")
    expect(planches.first).to_be_visible()
    _outil(jeu["tmp"], "tools/effacer_bacs_a_sable.py", "--appliquer",
           "--maintenant", "2099-01-01 00:00:00")
    assert _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable") is None
    # Agir : choisir une planche — la requête suivante reçoit un 404.
    planches.nth(1).click()
    expect(page.locator("#toasts")).to_contain_text(
        "Votre bac à sable a été effacé lundi à 4 h.", timeout=15000)
    page.wait_for_load_state("networkidle")
    # La page est repartie sans l'adresse de l'album effacé.
    assert page.url.rstrip("/") == jeu["base"]
    expect(page.locator("#toasts")).not_to_contain_text("introuvable")
    expect(page.locator("#bac-ligne")).to_have_count(0)
    expect(page.locator("#site-nav .bac-ouvrir-bande")).to_be_visible()
    expect(page.locator("#portee-vide .portee-vide-geste button")).to_be_visible()
    expect(page.locator("#stage-empty .bac-vide-geste button")).to_be_visible()
    # Le message ne revient pas à la page suivante.
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    page.wait_for_timeout(300)
    expect(page.locator("#toasts")).not_to_contain_text("effacé")


@pytestmark_proxy
def test_l_effacement_se_dit_aussi_a_la_page_suivante_chez_l_invitee(page, jeu):
    """Sans requête en page : la page suivante le dit, une fois — chez l'invitée, « Le bac à
    sable de camille a été effacé… »."""
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, DOMINIQUE)
    page.clock.set_fixed_time(datetime.strptime(bac["efface_le"], "%Y-%m-%d %H:%M:%S")
                              .replace(second=1, tzinfo=timezone.utc))
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    _ligne(page)
    _outil(jeu["tmp"], "tools/effacer_bacs_a_sable.py", "--appliquer",
           "--maintenant", "2099-01-01 00:00:00")
    page.goto(jeu["base"] + "/recherche", wait_until="networkidle")
    expect(page.locator("#toasts")).to_contain_text(
        "Le bac à sable de camille a été effacé lundi à 4 h.")
    expect(page.locator("#bac-ligne")).to_have_count(0)
    page.goto(jeu["base"] + "/exploration", wait_until="networkidle")
    page.wait_for_timeout(300)
    expect(page.locator("#toasts")).not_to_contain_text("effacé")



@pytestmark_proxy
def test_hors_du_lundi_l_effacement_se_dit_sans_date_et_le_retrait_autrement(page, jeu):
    """Avant l'échéance : le sien effacé par l'outil (`--tous`) se dit sans date ; une invitée
    que le propriétaire fait sortir lit qu'elle n'y est plus — l'écran ne prétend pas savoir
    pourquoi."""
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, DOMINIQUE)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    _ligne(page)
    _api(jeu["base"], CAMILLE, "DELETE", f"/api/projets/{bac['id']}/membres/utilisateur/dominique")
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    expect(page.locator("#toasts")).to_contain_text(
        "Vous n'êtes plus dans le bac à sable de camille.")
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    _ligne(page)
    _outil(jeu["tmp"], "tools/effacer_bacs_a_sable.py", "--appliquer", "--tous")
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    expect(page.locator("#toasts")).to_contain_text("Votre bac à sable a été effacé.")
    expect(page.locator("#toasts")).not_to_contain_text("lundi")

# ── La Bibliothèque d'un bac à sable ───────────────────────────────────────────────────

@pytestmark_proxy
def test_la_bibliotheque_d_un_bac_compte_ses_albums_et_n_offre_pas_le_fonds(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    n_albums = len(bac["jeu"])
    n_planches = sum(len(j["planche_ids"]) for j in bac["jeu"])
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    stats = page.locator("#corpus-stats")
    expect(stats).to_contain_text(f"{n_albums} albums")
    expect(stats).to_contain_text(f"{n_planches} planches")
    synth = page.locator("#corpus-synthese")
    expect(synth).to_be_visible()
    expect(synth).to_contain_text(f"{n_albums} album(s) · {n_planches} planche(s)")
    expect(page.locator("#bi-prendre-fonds")).to_have_count(0)
    # Dans l'onglet Albums de la base aussi.
    page.goto(jeu["base"] + f"/corpus?collection={bac['base']['id']}&onglet=albums",
              wait_until="networkidle")
    expect(page.locator("#bi-dans-projet")).to_be_visible()
    expect(page.locator("#bi-prendre-fonds")).to_have_count(0)


@pytestmark_proxy
def test_hors_du_bac_les_chiffres_restent_ceux_du_corpus(page, jeu):
    """Les surfaces transverses restent aveugles : la Recherche ne demande jamais les
    chiffres d'un bac à sable."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/recherche", wait_until="networkidle")
    page.goto(jeu["base"] + "/exploration", wait_until="networkidle")
    assert [v for v in vues if v[1].startswith("/api/corpus")], "aucun compte lu : sans objet"
    assert not [v for v in vues if "bac_a_sable=" in v[1]], vues


# ── L'Administration ───────────────────────────────────────────────────────────────────

@pytestmark_proxy
def test_l_administrateur_voit_les_bacs_derriere_un_axe(page, jeu):
    for qui in (CAMILLE, DOMINIQUE, LEA):
        _ouvrir(jeu, qui)
    _sous(page, HUGO)
    page.goto(jeu["base"] + "/administration?vue=projets", wait_until="networkidle")
    axes = page.locator("#pj-axes")
    expect(axes).to_be_visible()
    projets = [p for p in _api(jeu["base"], HUGO, "GET", "/api/projets")
               if not p.get("bac_a_sable")]
    expect(axes.locator('[data-pj-axe="projets"]')).to_have_text(f"Projets · {len(projets)}")
    expect(axes.locator('[data-pj-axe="bacs"]')).to_have_text("Bacs à sable · 3")
    expect(axes.locator('[data-pj-axe="projets"]')).to_have_attribute("aria-pressed", "true")
    # « Projets » d'abord, sans aucun bac à sable.
    expect(page.locator("#pj-objets")).not_to_contain_text("bac")
    expect(page.locator("#pj-creer-ouvrir")).to_be_visible()
    axes.locator('[data-pj-axe="bacs"]').click()
    expect(page).to_have_url(re.compile(r"[?&]bacs"))
    compte = page.locator("#pj-liste-compte")
    efface = _api(jeu["base"], CAMILLE, "GET", "/api/bac-a-sable")["efface_le"]
    t = datetime.strptime(efface, "%Y-%m-%d %H:%M:%S")
    paris = t + database.decalage_de_paris(t)
    expect(compte).to_have_text(re.compile(
        rf"^3 bacs à sable · tous s'effacent lun\. {paris.day} \w+\., {paris.hour} h$"))
    expect(page.locator("#pj-creer-ouvrir")).to_be_hidden()
    lignes = page.locator("#pj-objets .pj-objet")
    expect(lignes).to_have_count(3)
    expect(lignes.nth(0).locator(".pj-nom")).to_have_text("camille")
    expect(lignes.nth(1).locator(".pj-nom")).to_have_text("dominique")
    expect(lignes.nth(2).locator(".pj-nom")).to_have_text("lea")
    expect(lignes.nth(0).locator(".pj-etat")).to_have_text(re.compile(r"^ouvert le \d\d/\d\d$"))
    # Filtre par login ; tri récents d'abord (lea, ouvert le dernier).
    page.locator("#pj-filtre").fill("dom")
    expect(lignes).to_have_count(1)
    expect(compte).to_contain_text("1 sur 3")
    page.locator("#pj-filtre").fill("")
    page.locator('#pj-tri [data-pj-tri="recents"]').click()
    expect(lignes.nth(0).locator(".pj-nom")).to_have_text("lea")
    # La fiche : propriétaire, ouverture, effacement, la phrase ; aucun geste.
    lignes.filter(has_text="camille").click()
    fiche = page.locator("#pj-fiche")
    expect(fiche.locator("#pj-fiche-titre")).to_have_text("Bac à sable de camille")
    expect(fiche.locator(".pj-puce")).to_have_text("bac à sable")
    expect(fiche.locator("h4")).to_have_text(["Propriétaire", "Ouvert", "S'efface"])
    expect(fiche).to_contain_text(_date_attendue(efface))
    expect(fiche.locator(".pj-bac-phrase")).to_have_text(
        "Vous n'y entrez pas. Pour aider camille, faites-vous inviter.")
    expect(fiche.get_by_role("button").filter(has_not_text="Liste")).to_have_count(0)
    # Le propriétaire mène à sa fiche de « Comptes et groupes ».
    fiche.locator("a[data-pj-compte]").click()
    expect(page.locator("#cg-fiche-titre")).to_contain_text("camille")
    expect(page).to_have_url(re.compile(r"compte=camille"))


@pytestmark_proxy
def test_l_administrateur_qui_a_le_sien_y_est_un_arrivant(page, jeu):
    """hugo a son bac à sable : dans la bande, « Mon bac à sable » avec la ligne du
    propriétaire ; dans la liste des bacs, sa fiche ne lui dit pas de se faire inviter. Le
    bac de camille n'est pas dans son sélecteur."""
    bac_c = _ouvrir(jeu, CAMILLE)
    sien = _ouvrir(jeu, HUGO)
    _sous(page, HUGO)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    choix = page.locator("#projet-choix")
    expect(choix).to_be_visible()
    valeurs = choix.locator("option").evaluate_all("(o) => o.map((x) => x.value)")
    assert str(sien["id"]) in valeurs and str(bac_c["id"]) not in valeurs
    choix.select_option(str(sien["id"]))
    expect(_ligne(page).locator("#bac-remettre")).to_be_visible()
    expect(page.locator(".bac-ouvrir-bande")).to_have_count(0)
    page.goto(jeu["base"] + f"/administration?vue=projets&bacs&bac={sien['id']}",
              wait_until="networkidle")
    fiche = page.locator("#pj-fiche")
    expect(fiche.locator("#pj-fiche-titre")).to_have_text("Votre bac à sable")
    expect(fiche.locator(".pj-bac-phrase")).to_contain_text("C'est le vôtre")
    # Il n'est pas dans la liste des PROJETS qu'il règle.
    page.locator('#pj-axes [data-pj-axe="projets"]').click()
    expect(page.locator("#pj-objets")).not_to_contain_text("bac à sable")


@pytestmark_proxy
def test_qui_ne_decide_pas_des_projets_n_a_pas_l_axe(page, jeu):
    """lea, responsable de son seul bac à sable : la vue Projets ne s'ouvre pas pour lui — son
    bac à sable se règle depuis sa ligne —, et l'axe des bacs à sable n'est pas demandé."""
    _ouvrir(jeu, LEA)
    _ouvrir(jeu, CAMILLE)
    _sous(page, LEA)
    vues = _requetes(page)
    page.goto(jeu["base"] + "/administration?vue=projets", wait_until="networkidle")
    expect(page.locator("#pj-axes")).to_be_hidden()
    expect(page.locator("#vue-lien-projets")).to_be_hidden()
    assert [v for v in vues if v[1].startswith("/api/projets")], "liste non lue : sans objet"
    assert not [v for v in vues if "bacs_a_sable=1" in v[1]]


# ── 320 px et grande police ─────────────────────────────────────────────────────────────

def _perdus(page):
    return [c for c in page.evaluate(SONDE)["coupables"] if not c["cadre"]]


_RECOUVRE = """() => {
  const n = document.getElementById('site-nav'), h = document.getElementById('header');
  if (!n || !h) return null;
  const bas = [...n.children].map((c) => c.getBoundingClientRect())
    .filter((b) => b.width > 0 && b.height > 0)
    .reduce((m, b) => Math.max(m, b.bottom), n.getBoundingClientRect().bottom);
  return { bas, haut: h.getBoundingClientRect().top };
}"""


@pytestmark_proxy
def test_la_ligne_et_ses_dialogues_tiennent_a_320_px_sous_grande_police(page, jeu):
    """À 320 px, sous des préférences de 16, 20 et 24, sur les cinq surfaces : la ligne ne
    perd rien, ne s'écrase pas, et la bande 1 ne recouvre pas la bande 2 ; ses dialogues non
    plus. Le login le plus long que « Bac · » garde entier (quinze) chez l'invitée. Sous
    Chromium seulement : la préférence se pose par CDP."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    long = {"Remote-User": "hsemil01-abcdef"}
    _api(jeu["base"], long, "GET", "/api/moi")
    bac = _ouvrir(jeu, long)
    for i in range(3):
        _inviter(jeu, long, bac["id"], f"invite-{i}")
    _inviter(jeu, long, bac["id"], "dominique")
    echecs = []
    for qui, nom in ((long, "propriétaire"), (DOMINIQUE, "invitée")):
        _sous(page, qui)
        for police in POLICES:
            _preference_police(page, police)
            page.set_viewport_size({"width": 320, "height": 800})
            for surface in SURFACES_AUDITEES:
                page.goto(jeu["base"] + surface, wait_until="networkidle")
                _ligne(page)
                cas = f"{nom}, {surface}, police {police}"
                if qui is DOMINIQUE:
                    expect(page.locator("#projet-nom")).to_have_text("Bac · hsemil01-abcdef")
                perdus = _perdus(page)
                if perdus:
                    echecs.append(f"{cas} : {perdus[:3]}")
                ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, "#site-nav"))
                if ecrase:
                    echecs.append(f"{cas} : bande ÉCRASÉE\n" + "\n".join(ecrase))
                v = page.evaluate(_RECOUVRE)
                if v and v["bas"] > v["haut"] + 1:
                    echecs.append(f"{cas} : la bande 1 recouvre la bande 2")
            # Les dialogues, sur l'Atelier.
            page.goto(jeu["base"] + "/", wait_until="networkidle")
            gestes = ["#bac-remettre", "#bac-inviter"] if qui is long else ["#bac-quitter"]
            for g in gestes:
                page.locator(g).click()
                _dialogue(page)
                page.wait_for_timeout(250)
                perdus = _perdus(page)
                if perdus:
                    echecs.append(f"{nom}, dialogue {g}, police {police} : {perdus[:3]}")
                ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, ".bac-boite"))
                if ecrase:
                    echecs.append(f"{nom}, dialogue {g}, police {police} : ÉCRASÉ\n"
                                  + "\n".join(ecrase))
                page.keyboard.press("Escape")
                expect(page.locator("#bac-modal")).to_be_hidden()
    assert not echecs, "\n".join(echecs)


@pytestmark_proxy
def test_le_bandeau_et_son_geste_tiennent_a_320_px(page, jeu):
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    _sous(page, CAMILLE)
    echecs = []
    for police in POLICES:
        _preference_police(page, police)
        page.set_viewport_size({"width": 320, "height": 800})
        for surface in SURFACES_AUDITEES:
            page.goto(jeu["base"] + surface, wait_until="networkidle")
            expect(page.locator("#portee-vide .portee-vide-geste button")).to_be_visible()
            for ouvert in (False, True):
                page.evaluate("(o) => { document.querySelector('#portee-vide details').open = o; }",
                              ouvert)
                page.wait_for_timeout(80)
                perdus = _perdus(page)
                if perdus:
                    echecs.append(f"{surface}, police {police}, "
                                  f"{'déplié' if ouvert else 'replié'} : {perdus[:3]}")
            for racine in ("#site-nav", "#portee-vide"):
                ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, racine))
                if ecrase:
                    echecs.append(f"{surface}, police {police} : {racine} ÉCRASÉ\n"
                                  + "\n".join(ecrase))
    assert not echecs, "\n".join(echecs)


# ── Accessibilité (axe, deux thèmes) ────────────────────────────────────────────────────

_AXE = Path(__file__).parent / "js" / "vendor" / "axe.min.js"


def _audit_axe(page):
    if not _AXE.exists():
        pytest.skip("axe-core absent (cf. tests/js/vendor/README.md)")
    from test_e2e_a11y import _audit, _fmt
    v = _audit(page)
    return v, _fmt(v)


@pytestmark_proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_la_ligne_ses_dialogues_et_l_administration(page, jeu, theme):
    page.add_init_script(f"localStorage.setItem('bd-theme','{theme}')")
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    rapports = []

    def auditer(quoi):
        v, f = _audit_axe(page)
        if v:
            rapports.append(f"{quoi} :\n{f}")

    _sous(page, CAMILLE)
    for surface in SURFACES_AUDITEES:
        page.goto(jeu["base"] + surface, wait_until="networkidle")
        _ligne(page)
        auditer(f"{surface}, ligne du propriétaire")
    for g in ("#bac-remettre", "#bac-inviter"):
        page.locator(g).click()
        _dialogue(page)
        page.wait_for_timeout(300)
        auditer(f"dialogue {g}")
        page.keyboard.press("Escape")
    _sous(page, DOMINIQUE)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    _ligne(page)
    auditer("ligne de l'invitée")
    page.locator("#bac-quitter").click()
    _dialogue(page)
    auditer("dialogue « Quitter… »")
    page.keyboard.press("Escape")
    # Avant le clic : la bande, le bandeau et son geste, la page vide.
    _projet_de_lea(jeu)
    _sous(page, LEA)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    expect(page.locator(".bac-ouvrir-bande")).to_be_visible()
    auditer("bande avec « Mon bac à sable »")
    _sous(page, {"Remote-User": "arrivant"})
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    expect(page.locator("#portee-vide .portee-vide-geste button")).to_be_visible()
    auditer("bandeau et page vide")
    # L'Administration, axe des bacs à sable et fiche.
    _sous(page, HUGO)
    page.goto(jeu["base"] + f"/administration?vue=projets&bacs&bac={bac['id']}",
              wait_until="networkidle")
    expect(page.locator(".pj-bac-phrase")).to_be_visible()
    auditer("Administration, bacs à sable")
    assert not rapports, "\n".join(rapports)



# ── Relecture de l'écran (2026-10-24) ──────────────────────────────────────────────────

def _messages(page):
    page.wait_for_timeout(500)
    return page.locator("#toasts").inner_text() if page.locator("#toasts").count() else ""


@pytestmark_proxy
def test_un_autre_compte_sur_le_meme_navigateur_ne_lit_pas_un_faux_effacement(page, jeu):
    """Le souvenir des bacs à sable est rangé par login : camille ouvre le sien, puis lea se
    connecte sur le même navigateur — rien ne lui est dit. Et camille, revenue, ne lit rien
    non plus : son bac à sable est toujours là."""
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    _ligne(page)
    _projet_de_lea(jeu)
    _sous(page, LEA)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    assert "effacé" not in _messages(page)
    _sous(page, CAMILLE)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    _ligne(page)
    assert "effacé" not in _messages(page)


@pytestmark_proxy
def test_un_autre_compte_ne_lit_pas_le_lien_d_invitation_d_un_autre(page, jeu):
    """dominique, invitée chez camille, puis lea sur le même navigateur : lea ne lit rien
    d'une relation entre deux autres comptes."""
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    _sous(page, DOMINIQUE)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    _ligne(page)
    _projet_de_lea(jeu)
    _sous(page, LEA)
    page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
    assert "camille" not in _messages(page)


# Le bandeau de portée vide, à sa naissance : jamais affiché dans un bac à sable, pas même
# un instant. Un observateur posé AVANT les scripts de la page note chaque état visible.
_GUET_BANDEAU = """
window.__bandeauVu = false;
new MutationObserver(() => {
  const b = document.getElementById('portee-vide');
  if (b && !b.hidden && getComputedStyle(b).display !== 'none') window.__bandeauVu = true;
}).observe(document, { childList: true, subtree: true, attributes: true,
                       attributeFilter: ['hidden'] });
"""


@pytestmark_proxy
def test_le_bandeau_ne_parait_pas_un_instant_dans_un_bac(page, jeu):
    _ouvrir(jeu, CAMILLE)
    _sous(page, CAMILLE)
    page.add_init_script(_GUET_BANDEAU)
    for surface in SURFACES_AUDITEES:
        page.goto(jeu["base"] + surface, wait_until="networkidle")
        _ligne(page)
        expect(page.locator("#portee-vide")).to_be_hidden()
        assert page.evaluate("() => window.__bandeauVu") is False, surface
    # Hors du bac à sable, il paraît : la garde ne le cache pas pour tout le monde.
    _sous(page, {"Remote-User": "arrivant"})
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    expect(page.locator("#portee-vide")).to_be_visible()


@pytest.mark.parametrize("live_server", [False], indirect=True)
def test_en_mono_poste_l_administration_n_a_pas_d_axe_des_bacs(page, live_server):
    """Aucun bac à sable n'existe en mono-poste : l'axe ne paraît pas, la liste des projets
    est celle d'avant."""
    page.goto(live_server + "/administration?vue=projets", wait_until="networkidle")
    expect(page.locator("#pj-objets .pj-objet").first).to_be_visible()
    expect(page.locator("#pj-axes")).to_be_hidden()
    expect(page.locator("#pj-creer-ouvrir")).to_be_visible()


@pytestmark_proxy
def test_le_bac_de_l_administrateur_se_trie_et_se_filtre_par_son_login(page, jeu):
    for qui in (CAMILLE, LEA):
        _ouvrir(jeu, qui)
    _ouvrir(jeu, HUGO)
    _sous(page, HUGO)
    page.goto(jeu["base"] + "/administration?vue=projets&bacs", wait_until="networkidle")
    noms = page.locator("#pj-objets .pj-objet .pj-nom")
    expect(noms).to_have_text(["camille", "hugo", "lea"])
    page.locator("#pj-filtre").fill("hug")
    expect(noms).to_have_text(["hugo"])
    page.locator("#pj-objets .pj-objet").first.click()
    expect(page.locator("#pj-fiche-titre")).to_have_text("Votre bac à sable")
    expect(page.locator("#pj-fiche a[data-pj-compte]")).to_have_text("hugo")


# Le contraste de la ligne sur SA rayure, que axe ne mesure pas (un fond en dégradé lui
# est « incomplet ») : chaque encre de la ligne contre les DEUX teintes de la rayure, dans
# les quatre thèmes — le plafond atteint compris, en encre d'alerte.
_CONTRASTES = """() => {
  const rgb = (c) => { const m = c.match(/rgba?\(([^)]+)\)/)[1].split(',').map(Number);
                       return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
  const sonde = (prop, val) => { const s = document.createElement('span'); s.style[prop] = val;
    document.body.appendChild(s); const v = getComputedStyle(s)[prop]; s.remove(); return rgb(v); };
  const fond = sonde('color', 'var(--bg-panel)');
  const voile = sonde('color', 'var(--bac-rayure, var(--hover))');
  const sur = { r: voile.r * voile.a + fond.r * (1 - voile.a), g: voile.g * voile.a + fond.g * (1 - voile.a),
                b: voile.b * voile.a + fond.b * (1 - voile.a) };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
                       return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  return [...document.querySelectorAll('#bac-ligne .bac-nom, #bac-ligne .bac-date, #bac-ligne .bac-plafond, #bac-ligne .bac-sep')]
    .map((e) => { const c = rgb(getComputedStyle(e).color);
                  return { quoi: e.className, fond: ratio(c, fond), rayure: ratio(c, sur) }; });
}"""


@pytestmark_proxy
def test_les_encres_de_la_ligne_passent_l_aa_sur_la_rayure_dans_les_quatre_themes(page, jeu):
    bac = _ouvrir(jeu, CAMILLE)
    album = _api(jeu["base"], CAMILLE, "POST", "/api/albums",
                 {"titre": "Mes essais", "collection_id": bac["base"]["id"]})["id"]
    for i in range(50):
        _api(jeu["base"], CAMILLE, "POST", f"/api/albums/{album}/import",
             fichier=(f"p{i:02d}.png", make_png(60, 80), "image/png"))
    _sous(page, CAMILLE)
    echecs = []
    for theme in ("dark", "light"):
        for contraste in ("normal", "high"):
            page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
            page.evaluate(f"() => {{ localStorage.setItem('bd-theme', '{theme}'); "
                          f"localStorage.setItem('bd-contrast', '{contraste}'); }}")
            page.goto(jeu["base"] + "/corpus", wait_until="networkidle")
            expect(_ligne(page).locator(".bac-plafond.est-plein")).to_be_visible()
            for m in page.evaluate(_CONTRASTES):
                # Le séparateur « · » est décoratif (`aria-hidden`) : le seuil graphique.
                seuil = 3 if "bac-sep" in m["quoi"] else 4.5
                if min(m["fond"], m["rayure"]) < seuil:
                    echecs.append(f"{theme}/{contraste} {m['quoi']} : fond {m['fond']:.2f}, "
                                  f"rayure {m['rayure']:.2f} (seuil {seuil})")
    assert not echecs, "\n".join(echecs)


# ── La relectrice : la bande à 320 px avec un projet, un sélecteur, un login long ────────

def _mesurer_320(page, base, cas_nom, echecs, attendre=".bac-ouvrir-bande"):
    for police in POLICES:
        _preference_police(page, police)
        page.set_viewport_size({"width": 320, "height": 800})
        for surface in SURFACES_AUDITEES:
            page.goto(base + surface, wait_until="networkidle")
            if attendre:
                expect(page.locator(attendre).first).to_be_visible()
            cas = f"{cas_nom}, {surface}, police {police}"
            perdus = _perdus(page)
            if perdus:
                echecs.append(f"{cas} : {perdus[:3]}")
            ecrase = decrire_ecrasement(page.evaluate(ECRASEMENT, "#site-nav"))
            if ecrase:
                echecs.append(f"{cas} : bande ÉCRASÉE\n" + "\n".join(ecrase))
            v = page.evaluate(_RECOUVRE)
            if v and v["bas"] > v["haut"] + 1:
                echecs.append(f"{cas} : la bande 1 recouvre la bande 2")
            large = page.evaluate("() => document.documentElement.scrollWidth")
            if large > 321:
                echecs.append(f"{cas} : défilement horizontal ({large} px)")


@pytestmark_proxy
def test_bande_projet_long_et_bouton_a_320_px(page, jeu):
    """Le bouton « Mon bac à sable » à côté d'un projet au nom de 21 caractères."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("CDP")
    pid = _api(jeu["base"], HUGO, "POST", "/api/projets", {"nom": "Corpus franco-belge X"})["id"]
    _api(jeu["base"], HUGO, "PUT", f"/api/projets/{pid}/membres",
         {"genre": "utilisateur", "principal": "lea", "role": "membre"})
    _sous(page, LEA)
    echecs = []
    _mesurer_320(page, jeu["base"], "lea (un projet)", echecs)
    assert not echecs, "\n".join(echecs)


@pytestmark_proxy
def test_bande_selecteur_et_bouton_a_320_px(page, jeu):
    """Deux projets (donc le <select>) ET le bouton."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("CDP")
    for nom in ("Corpus franco-belge X", "Incubateur des stagi"):
        pid = _api(jeu["base"], HUGO, "POST", "/api/projets", {"nom": nom})["id"]
        _api(jeu["base"], HUGO, "PUT", f"/api/projets/{pid}/membres",
             {"genre": "utilisateur", "principal": "lea", "role": "membre"})
    _sous(page, LEA)
    echecs = []
    _mesurer_320(page, jeu["base"], "lea (deux projets)", echecs)
    assert not echecs, "\n".join(echecs)


@pytestmark_proxy
def test_ligne_d_un_login_long_avec_selecteur_a_320_px(page, jeu):
    """Propriétaire au login long, ligne avec sélecteur (deux projets), « Inviter… (3) »."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("CDP")
    long = {"Remote-User": "hsemil01-abcdef"}
    _api(jeu["base"], long, "GET", "/api/moi")
    pid = _api(jeu["base"], HUGO, "POST", "/api/projets", {"nom": "Corpus franco-belge X"})["id"]
    _api(jeu["base"], HUGO, "PUT", f"/api/projets/{pid}/membres",
         {"genre": "utilisateur", "principal": "hsemil01-abcdef", "role": "membre"})
    bac = _ouvrir(jeu, long)
    for i in range(3):
        _inviter(jeu, long, bac["id"], f"invite-{i}")
    _sous(page, long)
    page.goto(jeu["base"] + "/", wait_until="networkidle")
    page.evaluate(f"localStorage.setItem('bd-projet', '{bac['id']}')")
    echecs = []
    _mesurer_320(page, jeu["base"], "propriétaire long + sélecteur", echecs, attendre="#bac-ligne")
    assert not echecs, "\n".join(echecs)


@pytestmark_proxy
def test_un_404_ordinaire_ne_fait_rien_hors_d_un_bac(page, jeu):
    """Hors d'un bac à sable, un 404 ordinaire ne relit rien et ne navigue pas ; dans un bac
    à sable encore là, il relit la liste UNE fois et ne navigue pas. Sur les cinq surfaces."""
    _projet_de_lea(jeu)
    _sous(page, LEA)
    vues = _requetes(page)
    for surface in SURFACES_AUDITEES:
        page.goto(jeu["base"] + surface + "?x=1", wait_until="networkidle")
        url, n = page.url, len(vues)
        page.evaluate("() => apiGet('/api/albums/999999/planches').catch(() => null)")
        page.wait_for_timeout(600)
        assert page.url == url, surface
        assert not [v for v in vues[n:] if v[1] == "/api/projets"], (surface, vues[n:])
    bac = _ouvrir(jeu, LEA)
    page.evaluate(f"localStorage.setItem('bd-projet', '{bac['id']}')")
    for surface in SURFACES_AUDITEES:
        page.goto(jeu["base"] + surface + "?x=1", wait_until="networkidle")
        _ligne(page)
        url, n = page.url, len(vues)
        page.evaluate("() => apiGet('/api/albums/999999/planches').catch(() => null)")
        page.wait_for_timeout(600)
        assert page.url == url, surface
        assert len([v for v in vues[n:] if v[1] == "/api/projets"]) == 1, (surface, vues[n:])


# ── La Recherche et l'Exploration, dans un bac à sable (Hugo, 2026-10-24) ──────────────

# Les deux surfaces qui ne voient pas le bac à sable, et l'élément au-dessus duquel la
# phrase se pose : au-dessus de leurs RÉSULTATS. DÉRIVÉES de `SURFACES_AUDITEES` par leur
# nom (`test_surfaces.test_aucune_seconde_liste_de_surfaces`).
_ANCRE_DES_RESULTATS = {"Recherche": ".results-head", "Exploration": ".dist-barre"}
HORS_RECHERCHE = {s: _ANCRE_DES_RESULTATS[nom] for s, nom in SURFACES_AUDITEES.items()
                  if nom in _ANCRE_DES_RESULTATS}
PHRASE_MIENNE = ("Votre bac à sable n'est ni cherché ni exploré : on y voit le corpus de "
                 "vos autres projets.")
PHRASE_INVITEE = ("Ce bac à sable n'est ni cherché ni exploré : on y voit le corpus de vos "
                  "autres projets.")


def _phrase(page, surface, texte):
    """La phrase est VISIBLE (pas seulement présente : `to_have_text` lit aussi un élément
    caché), porte le texte, et se pose juste au-dessus des résultats."""
    loc = page.locator("#bac-hors-recherche")
    expect(loc).to_be_visible()
    expect(loc).to_have_text(texte)
    assert page.evaluate("(s) => document.getElementById('bac-hors-recherche')"
                         ".nextElementSibling === document.querySelector(s)",
                         HORS_RECHERCHE[surface]), surface
    return loc


@pytestmark_proxy
def test_la_recherche_et_l_exploration_disent_qu_elles_ne_voient_pas_le_bac(page, jeu):
    """camille, qui n'a que son bac à sable : la phrase « Votre bac à sable… » au-dessus des
    résultats, sans geste — elle tient lieu de liste vide. dominique, invitée : « Ce bac à
    sable… ». Ni masquée, ni repliable : aucun bouton, aucun `<details>` en elle."""
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    for qui, texte in ((CAMILLE, PHRASE_MIENNE), (DOMINIQUE, PHRASE_INVITEE)):
        _sous(page, qui)
        for surface in HORS_RECHERCHE:
            page.goto(jeu["base"] + surface, wait_until="networkidle")
            loc = _phrase(page, surface, texte)
            assert loc.locator("button, details, summary, a").count() == 0
            # Une seule, et elle ne bouge pas quand la bande se redessine.
            page.evaluate("() => document.dispatchEvent(new CustomEvent('bd:projets-maj'))")
            page.wait_for_load_state("networkidle")
            expect(page.locator("#bac-hors-recherche")).to_have_count(1)
            _phrase(page, surface, texte)
    # Sur les trois autres surfaces, elle n'existe pas.
    _sous(page, CAMILLE)
    for surface in (s for s in SURFACES_AUDITEES if s not in HORS_RECHERCHE):
        page.goto(jeu["base"] + surface, wait_until="networkidle")
        _ligne(page)
        expect(page.locator("#bac-hors-recherche")).to_have_count(0)


@pytestmark_proxy
def test_hors_d_un_bac_la_phrase_n_existe_pas(page, jeu):
    """lea, sur son vrai projet : rien. Elle passe sur son bac à sable par le sélecteur, la
    phrase paraît ; elle revient sur son projet, la phrase part — sans recharger."""
    pid = _projet_de_lea(jeu)
    bac = _ouvrir(jeu, LEA)
    _sous(page, LEA)
    page.goto(jeu["base"] + "/recherche", wait_until="networkidle")
    page.locator("#projet-choix").select_option(str(pid))
    for surface in HORS_RECHERCHE:
        page.goto(jeu["base"] + surface, wait_until="networkidle")
        expect(page.locator("#bac-ligne")).to_have_count(0)
        expect(page.locator("#bac-hors-recherche")).to_have_count(0)
        page.locator("#projet-choix").select_option(str(bac["id"]))
        _phrase(page, surface, PHRASE_MIENNE)
        page.locator("#projet-choix").select_option(str(pid))
        expect(page.locator("#bac-hors-recherche")).to_have_count(0)


@pytestmark_proxy
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a11y_la_phrase_de_la_recherche_et_de_l_exploration(page, jeu, theme):
    """axe, sur les deux surfaces où la phrase vit, en contraste normal ET élevé : elle se lit
    en AA. Le contraste élevé est vérifié POSÉ avant l'audit, et la phrase visible."""
    bac = _ouvrir(jeu, CAMILLE)
    _inviter(jeu, CAMILLE, bac["id"], "dominique")
    rapports = []
    for contraste in ("normal", "high"):
        for qui, texte in ((CAMILLE, PHRASE_MIENNE), (DOMINIQUE, PHRASE_INVITEE)):
            _sous(page, qui)
            for surface in HORS_RECHERCHE:
                page.goto(jeu["base"] + surface, wait_until="networkidle")
                page.evaluate(f"() => {{ localStorage.setItem('bd-theme', '{theme}'); "
                              f"localStorage.setItem('bd-contrast', '{contraste}'); }}")
                page.goto(jeu["base"] + surface, wait_until="networkidle")
                etat = page.evaluate("() => ({c: document.documentElement.dataset.contrast"
                                     " || 'normal', t: document.documentElement.dataset.theme})")
                assert etat == {"c": contraste, "t": theme}, etat
                _phrase(page, surface, texte)
                v, f = _audit_axe(page)
                if v:
                    rapports.append(f"{surface} [{theme}/{contraste}] :\n{f}")
    assert not rapports, "\n".join(rapports)


@pytestmark_proxy
def test_la_phrase_tient_a_320_px_sous_grande_police(page, jeu):
    """À 320 px, sous des préférences de 16, 20 et 24 : la phrase passe à la ligne, ne perd
    rien, et la page ne défile pas de côté — chez le propriétaire au login long et chez
    l'invitée."""
    if page.context.browser.browser_type.name != "chromium":
        pytest.skip("la préférence de police se pose par CDP")
    long = {"Remote-User": "hsemil01-abcdef"}
    _api(jeu["base"], long, "GET", "/api/moi")
    bac = _ouvrir(jeu, long)
    _inviter(jeu, long, bac["id"], "dominique")
    echecs = []
    for qui, texte in ((long, PHRASE_MIENNE), (DOMINIQUE, PHRASE_INVITEE)):
        _sous(page, qui)
        for police in POLICES:
            _preference_police(page, police)
            page.set_viewport_size({"width": 320, "height": 800})
            for surface in HORS_RECHERCHE:
                page.goto(jeu["base"] + surface, wait_until="networkidle")
                loc = _phrase(page, surface, texte)
                cas = f"{qui['Remote-User']}, {surface}, police {police}"
                perdus = _perdus(page)
                if perdus:
                    echecs.append(f"{cas} : {perdus[:3]}")
                b = loc.bounding_box()
                if b["x"] < 0 or b["x"] + b["width"] > 321:
                    echecs.append(f"{cas} : la phrase sort de la fenêtre ({b})")
                large = page.evaluate("() => document.documentElement.scrollWidth")
                if large > 321:
                    echecs.append(f"{cas} : défilement horizontal ({large} px)")
    assert not echecs, "\n".join(echecs)
