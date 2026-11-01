"""ANN-7, tranche 2 (commit 1) — la page Annotation, jouée dans un vrai navigateur.

La page, sans grille ni pose : on y choisit une planche du projet courant, une CASE sur la
minicarte, une zone DANS la case agrandie (ou le fond, la case elle-même), et l'on lit le
Contexte — locuteur, personnage, note — sans geste. La logique (le rangement en cases, les
étiquettes, l'adresse) est verrouillée sous Node (`tests/js/annotation.test.js`) ; ce fichier
vérifie que la page s'en sert, et qu'elle tient ce que la note de cadrage lui demande dès ce
commit :

- l'ADRESSE ouvre la planche et la zone qu'elle nomme, et suit chaque choix ;
- la disposition NE BOUGE PAS quand on passe d'une case ou d'une zone à l'autre (Hugo,
  2026-10-14) — mesurée sur la boîte de la case, la rangée des zones et le bloc du texte ;
- chaque choix a son chemin au CLAVIER ;
- « Ouvrir dans l'Atelier ↗ » mène à la même zone, et l'Atelier y revient.

Les audits transverses (axe dans les deux thèmes, contraste élevé, reflow à 320 px, grande
police, zoom, masquage, CSP, bande du projet, bac à sable) déclarent la page dans leurs
propres modules.
"""
import re

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import ECRITURE, du_projet, make_png  # noqa: E402
from grilles_decor import grille_active_vivante  # noqa: E402

pytestmark = pytest.mark.e2e

SURFACES_AUDITEES = ("/annotation",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier n'est visité que par le lien « Ouvrir dans l'Atelier ↗ », pour son retour",
    "/recherche": "la Recherche n'a rien de la page Annotation : elle lit le corpus",
    "/corpus": "la Bibliothèque range des albums ; elle ne mène pas encore à cette page",
    "/exploration": "l'Exploration compte le corpus ; les relevés y viendront en tranche 4",
    "/administration": "rien n'y porte sur une planche ; les grilles s'y régleront plus tard",
}


@pytest.fixture
def decor(live_server):
    """Une planche à deux cases : la première porte une bulle (texte, locuteur, note) et une
    boîte personnage ; la seconde, un cartouche."""
    with httpx.Client(base_url=live_server, trust_env=False, timeout=180,
                      headers=ECRITURE) as c:
        aid = c.post("/api/albums", json={"titre": "E2E annotation"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]

        def region(**corps):
            rep = c.post(f"/api/planches/{pid}/regions", json=corps)
            assert rep.status_code in (200, 201), rep.text
            return rep.json()["id"]

        c1 = region(type="case", x=20, y=20, w=360, h=900)
        c2 = region(type="case", x=420, y=20, w=360, h=500)
        bulle = region(type="bulle", x=60, y=60, w=200, h=120, parent_id=c1)
        boite = region(type="personnage", x=80, y=400, w=150, h=300, parent_id=c1)
        cartouche = region(type="cartouche", x=440, y=40, w=300, h=80, parent_id=c2)
        c.put(f"/api/regions/{bulle}", json={"ocr_texte": "MILLE SABORDS !"})
        c.put(f"/api/regions/{cartouche}", json={"ocr_texte": "PENDANT CE TEMPS…"})
        perso = c.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]
        assert c.put(f"/api/regions/{bulle}/locuteur",
                     json={"personnage_id": perso}).status_code == 200
        assert c.put(f"/api/regions/{boite}/personnage",
                     json={"personnage_id": perso}).status_code == 200
        c.put(f"/api/regions/{bulle}/annotation", json={"note": "il jure"})
        # La grille FICTIVE du dépôt, active sur le projet de l'album, et un relevé sur le
        # premier mot de la bulle — de quoi lire « n ici » (commit 2).
        g = grille_active_vivante(c)
        r = c.post("/api/releves", json={"region_id": bulle, "grille_id": g["grille_id"],
                                         "version": 1, "entree_cle": "cri", "mots": [0]})
        assert r.status_code == 201, r.text
    return {"base": live_server, "album": aid, "planche": pid, "c1": c1, "c2": c2,
            "bulle": bulle, "boite": boite, "cartouche": cartouche,
            "grille": g["grille_id"], "projet": g["projet_id"]}


def _ouvrir(page, d, region=None):
    qs = f"album={d['album']}&planche={d['planche']}"
    if region is not None:
        qs += f"&region={region}"
    page.goto(f"{d['base']}/annotation?{qs}", wait_until="networkidle")
    expect(page.locator("#an-mini .an-mz")).to_have_count(2, timeout=15000)


def _boites(page):
    """Les boîtes dont la hauteur ne doit pas bouger pendant le travail."""
    return page.evaluate("""() => ['#an-vue-case', '#an-zones', '#an-porte', '#an-mots', '.an-tete', '#an-pied']
      .map((s) => Math.round(document.querySelector(s).getBoundingClientRect().height))""")


def test_l_adresse_ouvre_la_zone_et_le_contexte_se_lit(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-album")).to_have_value(str(decor["album"]))
    expect(page.locator("#an-planche-choix")).to_have_value(str(decor["planche"]))
    expect(page.locator("#an-tete-case")).to_have_text("Case c1")
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    expect(page.locator("#an-mots")).to_have_text("MILLE SABORDS !")
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    # Sur un album où l'on écrit, le Contexte s'écrit ici (commit 8) : le champ du locuteur,
    # la note dans son champ.
    expect(page.locator("#an-loc-input")).to_be_visible()
    expect(page.locator("#an-note")).to_have_value("il jure")
    expect(page.locator("#an-note-lu")).to_be_hidden()
    expect(page.locator("#an-preparee")).to_contain_text("2 zones de texte")


def test_choisir_une_case_puis_une_zone_ne_change_la_taille_de_rien(page, decor):
    _ouvrir(page, decor)
    expect(page.locator("#an-tete-case")).to_have_text("Case c1")
    avant = _boites(page)
    # La seconde case, sur la minicarte : sa zone se lit, l'adresse suit.
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    expect(page.locator('#an-mini .an-mz[data-case="1"]')).to_have_attribute("aria-pressed",
                                                                            "true")
    assert _boites(page) == avant
    # Le cartouche, dans la case agrandie.
    page.locator(f'#an-vue-case rect[data-zone="{decor["cartouche"]}"]').click()
    expect(page.locator("#an-tete-zone")).to_have_text("cartouche b1")
    expect(page.locator("#an-mots")).to_have_text("PENDANT CE TEMPS…")
    assert _boites(page) == avant
    assert f"region={decor['cartouche']}" in page.url
    # Le fond de la case : la case elle-même, et l'adresse nomme la case.
    page.locator("#an-vue-case rect.an-fond").click(position={"x": 5, "y": 200})
    expect(page.locator("#an-tete-zone")).to_have_text("")
    expect(page.locator("#an-mots")).to_have_text("—")
    assert f"region={decor['c2']}" in page.url
    assert _boites(page) == avant


def test_la_boite_personnage_dit_son_personnage_sur_l_image(page, decor):
    _ouvrir(page, decor, decor["boite"])
    expect(page.locator("#an-vue-case text.an-vz-lbl", has_text="Haddock")).to_have_count(1)
    expect(page.locator('#an-ctx-corps dd[data-ctx="personnage"]')).to_have_text("Haddock")
    # Une étiquette lue à taille d'ÉCRAN constante, quelle que soit la case.
    taille = page.evaluate("""() => {
      const t = [...document.querySelectorAll('#an-vue-case text.an-vz-lbl')]
        .find((x) => x.textContent === 'Haddock');
      return t.getBoundingClientRect().height; }""")
    assert 8 <= taille <= 22, taille


def test_chaque_choix_a_son_chemin_au_clavier(page, decor):
    _ouvrir(page, decor)
    case2 = page.locator('#an-mini .an-mz[data-case="1"]')
    case2.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    # Les zones de la case, une rangée de boutons.
    bouton = page.locator("#an-zones .an-zone-btn", has_text="cartouche")
    bouton.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#an-tete-zone")).to_have_text("cartouche b1")
    expect(bouton).to_have_attribute("aria-pressed", "true")


def test_ouvrir_dans_l_atelier_mene_a_la_meme_zone_et_en_revient(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    lien = page.locator("#an-atelier")
    href = lien.get_attribute("href")
    assert f"region={decor['bulle']}" in href and f"planche={decor['planche']}" in href
    assert "retour=" in href
    lien.click()
    page.wait_for_url("**/?*", timeout=15000)
    expect(page.locator("#region-type")).to_be_visible(timeout=15000)
    retour = page.locator("#back-link")
    expect(retour).to_be_visible()
    retour.click()
    page.wait_for_url("**/annotation?*", timeout=15000)
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1", timeout=15000)


def test_annoter_depuis_l_atelier_mene_a_la_meme_zone_et_en_revient(page, decor):
    """H2 : le pendant d'« Ouvrir dans l'Atelier ↗ » — la zone que l'on vient de choisir, pas
    celle de l'arrivée : le lien suit la sélection."""
    page.goto(f"{decor['base']}/?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor['c1']}", wait_until="networkidle")
    lien = page.locator("#btn-annoter")
    expect(lien).to_have_attribute("href", re.compile(rf"region={decor['c1']}&"))
    page.evaluate("id => selectRegion(id)", decor["bulle"])
    expect(lien).to_have_attribute("href", re.compile(rf"region={decor['bulle']}&"))
    assert f"planche={decor['planche']}" in lien.get_attribute("href")
    assert "retour=" in lien.get_attribute("href")
    lien.click()
    page.wait_for_url("**/annotation?*", timeout=15000)
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1", timeout=15000)
    retour = page.locator("#back-link")
    expect(retour).to_be_visible()
    retour.click()
    page.wait_for_url(re.compile(r"/\?album="), timeout=15000)
    expect(page.locator("#region-type")).to_be_visible(timeout=15000)


def test_la_page_est_dans_la_navigation_entre_l_atelier_et_la_bibliotheque(page, decor):
    _ouvrir(page, decor)
    liens = page.locator("#site-nav .surf-nav a.surf-link")
    noms = [liens.nth(i).get_attribute("href") for i in range(liens.count())]
    assert noms.index("/annotation") == noms.index("/") + 1
    assert noms.index("/corpus") == noms.index("/annotation") + 1
    expect(page.locator('#site-nav a[href="/annotation"]')).to_have_attribute("aria-current",
                                                                             "page")


def test_sans_planche_la_page_s_ouvre_vide_sans_erreur(page, live_server):
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.goto(f"{live_server}/annotation", wait_until="networkidle")
    expect(page.locator("#an-album option")).to_have_count(1)
    expect(page.locator("#an-tete-case")).to_have_text("—")
    assert not erreurs, erreurs


# --------------------------------------------------------------------------- #
# La grille, en lecture (commit 2)
# --------------------------------------------------------------------------- #
def test_la_grille_se_lit_avec_ses_onglets_ses_rubriques_et_n_ici(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    onglet = page.locator(f"#an-onglet-{decor['grille']}")
    expect(onglet).to_have_attribute("aria-selected", "true")
    expect(onglet).to_contain_text("Signaux")
    expect(onglet).to_contain_text("(1)")
    expect(onglet).to_have_attribute("title", "Signaux · version 1 (publiée) — modèle fictif")
    assert f"grille={decor['grille']}" in page.url
    rub = page.locator("#an-plan .an-rub-btn", has_text="A. Sons").first
    expect(rub).to_contain_text("1 ici")
    # Les trois formes, et les marques d'une cible propre et de « plusieurs ».
    expect(page.locator("#an-plan .an-var", has_text="crac")).to_have_count(1)
    expect(page.locator("#an-plan .an-ent-btn", has_text="origine du son")) \
        .to_contain_text("+ source du son")
    expect(page.locator("#an-plan .an-ent-btn", has_text="ton de voix")) \
        .to_contain_text("toute la zone")
    regard = page.locator("#an-plan .an-ent-btn", has_text="regard caméra")
    expect(regard).to_contain_text("la case")
    expect(regard).not_to_contain_text("plusieurs")          # une case, une fois
    expect(page.locator("#an-plan .an-ent-btn", has_text="réponse à une autre bulle")) \
        .to_contain_text("plusieurs")
    # Aucun mot désigné : rien n'est coché, même le « cri » posé sur « MILLE » (commit 3).
    expect(page.locator('#an-plan [role=checkbox][aria-checked="true"]')).to_have_count(0)


def test_la_ligne_du_guide_garde_sa_hauteur(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    hauteur = lambda: page.evaluate(  # noqa: E731
        "() => Math.round(document.querySelector('#an-guide').getBoundingClientRect().height)")
    vide = hauteur()
    page.locator("#an-plan .an-ent-btn", has_text="cri").first.hover()
    contenu = page.locator("#an-guide-contenu")
    expect(contenu).to_contain_text("un cri poussé par un personnage")
    expect(contenu).to_contain_text("AAAH !")
    expect(contenu.locator(".an-g-piege")).to_contain_text("pas une onomatopée")
    assert hauteur() == vide
    # Le pointeur reste où il est : le focus fait défiler le plan et amène une autre entrée
    # sous lui, et le navigateur émet un mouseover — qui ne reprend pas la ligne du guide.
    page.locator("#an-plan .an-var", has_text="splash").focus()
    expect(contenu).to_contain_text("[liquide] + [chute]")
    expect(contenu.locator(".an-g-chemin")).to_contain_text("onomatopée de choc")
    assert hauteur() == vide


def test_le_filtre_accents_par_et_clavier(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    champ = page.locator("#an-filtre")
    page.keyboard.press("/")
    expect(champ).to_be_focused()
    champ.fill("CHUCHOTÉ")
    expect(page.locator("#an-resultats")).to_be_visible()
    expect(page.locator("#an-resultats [role=option]")).to_have_count(1)
    expect(page.locator("#an-resultats .an-res-lib")).to_have_text("chuchoté")
    page.keyboard.press("Enter")
    expect(page.locator("#an-guide-contenu .an-g-lib")).to_have_text("chuchoté")
    champ.fill("origine par hors")
    expect(page.locator("#an-resultats .an-res-lib")).to_have_text(
        ["origine du son par hors champ"])
    champ.fill("cri")
    expect(page.locator("#an-resultats .an-res.actif .an-res-lib")).to_have_text("cri")
    page.keyboard.press("ArrowDown")
    expect(page.locator("#an-resultats .an-res.actif .an-res-lib")).to_have_text("crié")
    expect(champ).to_have_attribute("aria-activedescendant", "an-res-1")
    page.keyboard.press("Escape")
    expect(champ).to_have_value("")
    expect(page.locator("#an-resultats")).to_be_hidden()
    expect(page.locator("#an-plan")).to_be_visible()


def test_rubriques_repliables_et_afficher(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    rub = page.locator("#an-plan .an-rub-btn", has_text="B. Provenance")
    rub.click()
    rub = page.locator("#an-plan .an-rub-btn", has_text="B. Provenance")
    expect(rub).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#an-plan .an-ent-btn", has_text="origine du son")).to_have_count(0)
    expect(rub).to_be_focused()
    page.locator("#an-afficher").select_option(label="E. Image")
    expect(page.locator("#an-plan .an-rub-btn")).to_have_count(1)
    expect(page.locator("#an-plan .an-rub-btn")).to_contain_text("E. Image")


def test_le_guide_complet_se_produit_depuis_la_grille(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    bouton = page.locator("#an-guide-complet")
    bouton.click()
    modale = page.locator("#an-guide-modal")
    expect(modale).to_be_visible()
    expect(page.locator("#an-guide-titre")).to_have_text("Guide — Signaux (version 1)")
    expect(modale.locator("table tbody tr")).to_have_count(10)
    expect(modale).to_contain_text("source du son")
    expect(modale).to_contain_text("Pièges")
    page.keyboard.press("Escape")
    expect(modale).to_be_hidden()
    expect(bouton).to_be_focused()


def test_la_collection_qui_masque_cache_l_onglet(page, decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        col = c.post("/api/collections", json={"nom": "Étude masquée",
                                               "projet_id": decor["projet"]}).json()["id"]
        assert c.put(f"/api/albums/{decor['album']}/collections/{col}").status_code in (200, 201)
        assert c.put(f"/api/collections/{col}/grilles-masquees/{decor['grille']}") \
            .status_code == 200
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-collection").select_option(str(col))
    expect(page.locator(f"#an-onglet-{decor['grille']}")).to_have_count(0)
    expect(page.locator("#an-collection")).to_have_attribute(
        "title", "Cette collection masque 1 grille du projet. "
                 "Leurs relevés restent visibles, en lecture.")
    page.locator("#an-collection").select_option("toutes")
    expect(page.locator(f"#an-onglet-{decor['grille']}")).to_have_count(1)


# --------------------------------------------------------------------------- #
# Désigner et poser (commit 3)
# --------------------------------------------------------------------------- #
# La bulle du décor, « MILLE SABORDS ! », se découpe en MILLE (0) · SABORDS (1) · ! (2) ; le
# décor y a posé « cri » sur MILLE.
def _http(d):
    return httpx.Client(base_url=d["base"], trust_env=False, timeout=30, headers=ECRITURE)


def _releves(d):
    with _http(d) as c:
        return c.get(f"/api/planches/{d['planche']}/releves").json()["releves"]


def _mot(page, rang):
    return page.locator(f"#an-mot-{rang}")


def test_designer_des_mots_et_poser_puis_retirer(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    expect(_mot(page, 2)).to_be_visible()
    # Un glissé de SABORDS à « ! » : le passage continu, sans rien poser.
    _mot(page, 1).hover()
    page.mouse.down()
    _mot(page, 2).hover()
    page.mouse.up()
    expect(_mot(page, 1)).to_have_attribute("aria-selected", "true")
    expect(_mot(page, 2)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#an-poses-titre")).to_have_text("Sur « SABORDS ! »")
    expect(page.locator('#an-porte [data-porte="mots"]')).to_have_attribute("aria-pressed", "true")
    cri = page.locator("#an-plan [role=checkbox]", has_text="cri").first
    expect(cri).to_have_attribute("aria-checked", "false")
    cri.click()
    expect(cri).to_have_attribute("aria-checked", "true")
    poses = [r for r in _releves(decor) if r["entree_cle"] == "cri"]
    assert sorted(tuple(m["rang"] for m in r["mots"]) for r in poses) == [(0,), (1, 2)]
    # Les traits : deux relevés se chevauchent sur MILLE … SABORDS ? Non — deux couloirs
    # tout de même, puisqu'ils se touchent bord à bord ; chaque mot porte un trait coloré.
    expect(_mot(page, 1).locator(".an-trait.an-teinte-0")).to_have_count(1)
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(1)
    expect(page.locator("#an-annonce")).to_have_text("Posé : cri")
    # Recocher sur le même passage retire.
    cri.click()
    expect(cri).to_have_attribute("aria-checked", "false")
    poses = [r for r in _releves(decor) if r["entree_cle"] == "cri"]
    assert [tuple(m["rang"] for m in r["mots"]) for r in poses] == [(0,)]


def test_maj_ctrl_et_clavier_designent_un_passage(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, 0).click()
    _mot(page, 2).click(modifiers=["Control"])
    expect(page.locator("#an-poses-titre")).to_have_text("Sur « MILLE … ! »")
    _mot(page, 0).click()
    _mot(page, 2).click(modifiers=["Shift"])
    expect(page.locator("#an-poses-titre")).to_have_text("Sur « MILLE SABORDS ! »")
    # Au clavier : la liste des mots, les flèches, Maj+flèche, Entrée vers le filtre, et
    # Entrée sur le résultat POSE.
    mots = page.locator("#an-mots")
    mots.focus()
    page.keyboard.press("Escape")
    expect(page.locator("#an-poses-titre")).to_have_text("Dans la bulle b1")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    expect(mots).to_have_attribute("aria-activedescendant", "an-mot-1")
    page.keyboard.press("Shift+ArrowRight")
    expect(page.locator("#an-poses-titre")).to_have_text("Sur « SABORDS ! »")
    page.keyboard.press("Enter")
    expect(page.locator("#an-filtre")).to_be_focused()
    page.keyboard.type("cri")
    page.keyboard.press("Enter")
    expect(page.locator("#an-annonce")).to_have_text("Posé : cri")
    assert any([m["rang"] for m in r["mots"]] == [1, 2]
               for r in _releves(decor) if r["entree_cle"] == "cri")


def test_une_variante_se_pose_sur_la_zone_et_se_remplace_en_place(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-plan .an-var", has_text="crié").click()
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "true")
    ton = [r for r in _releves(decor) if r["entree_cle"] == "ton-de-voix"]
    assert len(ton) == 1 and ton[0]["variante_cle"] == "crie" and ton[0]["mots"] == []
    page.locator("#an-plan .an-var", has_text="chuchoté").click()
    expect(page.locator("#an-plan .an-var", has_text="chuchoté")).to_have_attribute("aria-pressed", "true")
    ton2 = [r for r in _releves(decor) if r["entree_cle"] == "ton-de-voix"]
    assert [(r["id"], r["variante_cle"]) for r in ton2] == [(ton[0]["id"], "chuchote")]
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="ton de voix · chuchoté")) \
        .to_have_count(1)


def test_des_qualificatifs_et_une_precision(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, 1).click()
    origine = page.locator("#an-plan .an-ent", has=page.locator("text=origine du son"))
    origine.locator(".an-var", has_text="objet").click()
    expect(origine.locator(".an-var", has_text="objet")).to_have_attribute("aria-pressed", "true")
    origine.locator(".an-var", has_text="hors champ").click()
    expect(origine.locator(".an-var", has_text="hors champ")).to_have_attribute("aria-pressed", "true")
    r = [x for x in _releves(decor) if x["entree_cle"] == "origine-du-son"]
    assert len(r) == 1 and sorted(r[0]["qualificatifs"]) == ["hors-champ", "objet"]
    assert r[0]["etat"] == "a_completer"
    # La précision attendue (« lieu ») se tape dans la liste.
    champ = page.locator("#an-poses-liste .an-prec")
    champ.fill("le salon")
    champ.press("Enter")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="« le salon »")).to_have_count(1)
    r = [x for x in _releves(decor) if x["entree_cle"] == "origine-du-son"]
    assert r[0]["precision"] == "le salon" and r[0]["etat"] == "normal"


def test_le_lien_se_designe_sur_la_planche(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-plan [role=checkbox]", has_text="réponse à une autre bulle").click()
    expect(page.locator("#an-poses-liste .an-etat", has_text="à compléter")).to_have_count(1)
    page.locator("#an-poses-liste .an-lien-btn").click()
    # L'autre zone vit dans la seconde case : on y va, puis on la touche.
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    with _reponse_de(page, RELEVE):
        page.locator(f'#an-vue-case rect[data-zone="{decor["cartouche"]}"]').click()
    r = [x for x in _releves(decor) if x["entree_cle"] == "reponse-a"]
    assert r[0]["lien"]["region_id"] == decor["cartouche"] and r[0]["etat"] == "normal"


def test_un_retrait_sur_une_valeur_perimee_ouvre_le_bandeau(page, decor):
    with _http(decor) as c:
        r = c.post("/api/releves", json={"region_id": decor["bulle"], "grille_id": decor["grille"],
                                         "version": 1, "entree_cle": "ton-de-voix",
                                         "variante_cle": "crie"}).json()
    _ouvrir(page, decor, decor["bulle"])
    hauteur = lambda: page.evaluate(  # noqa: E731
        "() => Math.round(document.querySelector('#an-grille').getBoundingClientRect().height)")
    avant = hauteur()
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "true")
    with _http(decor) as c:                        # un autre écran change la variante
        assert c.put(f"/api/releves/{r['id']}", json={"variante_cle": "chuchote"}).status_code == 200
    page.locator("#an-plan .an-var", has_text="crié").click()     # l'écran croit retirer
    expect(page.locator("#an-cf-titre")).to_contain_text("Variante modifiée")
    expect(page.locator("#an-guide-contenu")).to_contain_text("Votre retrait n'est pas enregistré.")
    expect(page.locator("#an-guide-contenu")).to_contain_text("chuchoté")
    assert hauteur() == avant
    assert [x["variante_cle"] for x in _releves(decor) if x["id"] == r["id"]] == ["chuchote"]
    # Tant qu'il est ouvert, un autre geste ne part pas (une entrée qui se poserait sur la
    # bulle entière, sans rien désigner).
    page.locator("#an-plan [role=checkbox]", has_text="réponse à une autre bulle").click()
    expect(page.locator("#an-cf-mienne")).to_be_focused()
    assert not [x for x in _releves(decor) if x["entree_cle"] == "reponse-a"]
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-plan .an-var", has_text="chuchoté")).to_have_attribute("aria-pressed", "true")


def test_la_cardinalite_propose_de_remplacer_le_releve_existant(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "false")
    with _http(decor) as c:                        # posé ailleurs, après l'ouverture
        r = c.post("/api/releves", json={"region_id": decor["bulle"], "grille_id": decor["grille"],
                                         "version": 1, "entree_cle": "ton-de-voix",
                                         "variante_cle": "crie"}).json()
    page.locator("#an-plan .an-var", has_text="chuchoté").click()
    expect(page.locator("#an-cf-titre")).to_contain_text("est déjà posé ici")
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    ton = [x for x in _releves(decor) if x["entree_cle"] == "ton-de-voix"]
    assert [(x["id"], x["variante_cle"]) for x in ton] == [(r["id"], "chuchote")]


def test_creer_une_entree_dans_une_grille_ouverte_et_releves(page, decor):
    with _http(decor) as c:
        g = grille_active_vivante(c, nom="Lieux", ouverte=True, projet_id=decor["projet"])
    _ouvrir(page, decor, decor["bulle"])
    page.locator(f"#an-onglet-{g['grille_id']}").click()
    _mot(page, 1).click()
    page.locator("#an-filtre").fill("Moulinsart")
    expect(page.locator("#an-resultats .an-res-creer")).to_have_text(
        re.compile("Créer « Moulinsart »"))
    page.locator("#an-filtre").press("Enter")
    expect(page.locator("#an-annonce")).to_have_text("Posé : Moulinsart")
    expect(page.locator("#an-plan .an-ent-btn", has_text="Moulinsart")).to_have_attribute(
        "aria-checked", "true")
    # Une entrée sans rubrique : « Sans rubrique » porte le gris de ses relevés.
    sans = page.locator("#an-plan .an-rub-tete", has_text="Sans rubrique")
    expect(sans.locator(".an-rub-filet.an-trait-autre")).to_have_count(1)
    expect(sans.locator(".an-rub-titre .an-pastille.an-trait-autre")).to_have_count(1)
    # « Relevés : ▾ » : la grille ouverte seule, puis aussi « Signaux » — retenu au rechargement.
    page.keyboard.press("Escape")
    page.locator("#an-mots").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(0)
    page.locator("#an-releves-btn").click()
    page.locator(f'#an-releves-pop [data-voir="{decor["grille"]}"]').check()
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(1)
    page.reload(wait_until="networkidle")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(1,
                                                                                    timeout=15000)


# --------------------------------------------------------------------------- #
# « Terminée », le parcours, Ctrl+Z (commit 4)
# --------------------------------------------------------------------------- #
# La grille fictive vise des mots, des zones de texte, la case et la planche : son parcours
# du décor est c1, sa bulle, c2, son cartouche, puis la planche (la boîte n'y est pas).
def _passes(d):
    with _http(d) as c:
        return c.get(f"/api/planches/{d['planche']}/releves").json()["passes"]


def test_terminee_suivante_le_parcours_et_rouvrir(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    etat = page.locator("#an-passe-etat")
    rang = page.locator("#an-tete-rang")
    expect(rang).to_have_text("zone 2 / 5 de « Signaux »")
    expect(etat).to_have_text("Signaux : à faire")
    avant = _boites(page)
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and f"/api/regions/{decor['bulle']}/passes/" in r.url) as rep:
        page.locator("#an-terminee-suiv").click()
    assert rep.value.status == 200
    assert rep.value.request.post_data_json == {"rubrique_cle": "", "vu": {"passe": False}}
    assert [(p["region_id"], p["rubrique_cle"]) for p in _passes(decor)] == [(decor["bulle"], "")]
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    expect(rang).to_have_text("zone 3 / 5 de « Signaux »")
    assert _boites(page) == avant
    page.locator("#an-prec").click()
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    expect(etat).to_contain_text("✓ Signaux : terminée")
    expect(page.locator(f"#an-onglet-{decor['grille']} .an-fini")).to_have_count(1)
    # « À faire seulement » saute la bulle terminée.
    page.locator("#an-prec").click()
    expect(rang).to_have_text("zone 1 / 5 de « Signaux »")
    page.locator("#an-parcours-sel").select_option("afaire")
    page.locator("#an-suiv").click()
    expect(rang).to_have_text("zone 3 / 5 de « Signaux »")
    # Les raccourcis : Ctrl+Entrée la suivante, Ctrl+Maj+Entrée la précédente.
    page.locator("#an-mots").focus()
    page.keyboard.press("Control+Enter")
    expect(rang).to_have_text("zone 4 / 5 de « Signaux »")
    page.keyboard.press("Control+Shift+Enter")
    expect(rang).to_have_text("zone 3 / 5 de « Signaux »")
    page.keyboard.press("Control+Shift+Enter")
    expect(rang).to_have_text("zone 1 / 5 de « Signaux »")
    # La planche : la dernière étape, sur une case pseudo que le parcours ajoute.
    page.locator("#an-parcours-sel").select_option("tout")
    page.locator("#an-prec").click()
    expect(page.locator("#an-tete-case")).to_have_text("La planche")
    expect(rang).to_have_text("zone 5 / 5 de « Signaux »")
    # Rouvrir.
    page.locator("#an-suiv").click()
    page.locator("#an-suiv").click()
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    with page.expect_response(lambda r: r.request.method == "DELETE" and "/passes/" in r.url) as rep:
        page.locator("#an-rouvrir").click()
    assert rep.value.status == 204 and "vu_marquee=true" in rep.value.url
    expect(etat).to_have_text("Signaux : à faire")
    expect(page.locator("#an-rouvrir")).to_be_hidden()
    assert _passes(decor) == []
    expect(page.locator(f"#an-onglet-{decor['grille']} .an-fini")).to_have_count(0)


def test_terminee_par_rubrique_et_les_marques_de_la_minicarte(page, decor):
    _ouvrir(page, decor, decor["c2"])
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    page.locator("#an-afficher").select_option("image")
    page.locator("#an-terminee-suiv").click()
    expect(page.locator("#an-tete-zone")).to_have_text("cartouche b1")
    assert [(p["region_id"], p["rubrique_cle"]) for p in _passes(decor)] == [(decor["c2"], "image")]
    page.locator("#an-prec").click()
    expect(page.locator("#an-passe-etat")).to_contain_text("✓ Signaux › E. Image : terminée")
    # Pour toute la grille, une rubrique ne suffit pas.
    page.locator("#an-afficher").select_option("*")
    expect(page.locator("#an-passe-etat")).to_have_text("Signaux : à faire")
    case2 = page.locator('#an-mini .an-mz[data-case="1"]')
    expect(case2).not_to_have_class(re.compile(r"\bfaite\b"))
    # Les deux étapes de c2 terminées : la case l'est, et son nom le dit.
    page.locator("#an-terminee-suiv").click()
    expect(page.locator("#an-tete-zone")).to_have_text("cartouche b1")
    page.locator("#an-terminee-suiv").click()
    expect(case2).to_have_class(re.compile(r"\bfaite\b"))
    expect(case2).to_have_attribute("aria-label", "Case c2 · terminée")
    # Un doute ouvert sur un relevé de la première case la marque.
    rid = next(r["id"] for r in _releves(decor) if r["entree_cle"] == "cri")
    with _http(decor) as c:
        assert c.post(f"/api/releves/{rid}/doutes", json={"texte": "un juron ?"}).status_code == 201
    page.reload(wait_until="networkidle")
    case1 = page.locator('#an-mini .an-mz[data-case="0"]')
    expect(case1).to_have_class(re.compile(r"\bdoute\b"))
    expect(case1).to_have_attribute("aria-label", re.compile("doute ouvert"))


def test_ctrl_z_annule_une_pose(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, 1).click()
    cri = page.locator("#an-plan [role=checkbox]", has_text="cri").first
    cri.click()
    expect(cri).to_have_attribute("aria-checked", "true")
    assert len([r for r in _releves(decor) if r["entree_cle"] == "cri"]) == 2
    page.locator("#an-mots").focus()
    with page.expect_response(lambda r: r.url.endswith("/api/undo")) as rep:
        page.keyboard.press("Control+z")
    assert rep.value.status == 200
    expect(page.locator("#toasts")).to_contain_text("Annulé :")
    assert [[m["rang"] for m in r["mots"]] for r in _releves(decor)
            if r["entree_cle"] == "cri"] == [[0]]
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    # La planche est RELUE : le trait de SABORDS est parti, celui de MILLE reste.
    expect(_mot(page, 1).locator(".an-trait.an-teinte-0")).to_have_count(0)
    expect(_mot(page, 0).locator(".an-trait.an-teinte-0")).to_have_count(1)
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(1)
    # Dans un champ de saisie, Ctrl+Z reste l'annulation native : rien ne part.
    page.locator("#an-filtre").fill("cri")
    envois = []
    page.on("request", lambda r: envois.append(r.url) if r.url.endswith("/api/undo") else None)
    page.locator("#an-filtre").press("Control+z")
    page.wait_for_timeout(300)
    assert envois == []


# --------------------------------------------------------------------------- #
# Le doute et la Synthèse (commit 5)
# --------------------------------------------------------------------------- #
def _poser(d, **corps):
    with _http(d) as c:
        r = c.post("/api/releves", json={"grille_id": d["grille"], "version": 1, **corps})
        assert r.status_code == 201, r.text
        return r.json()


def _douter_api(d, releve_id, texte):
    with _http(d) as c:
        r = c.post(f"/api/releves/{releve_id}/doutes", json={"texte": texte})
        assert r.status_code == 201, r.text
        return r.json()


def _cri(d):
    return next(r for r in _releves(d) if r["entree_cle"] == "cri")


def _synthese(page, vue):
    page.locator("#an-ong-synthese").click()
    expect(page.locator("#an-p-synthese")).to_be_visible()
    page.locator(f'#an-syn-vues [data-syn="{vue}"]').click()
    expect(page.locator(f'#an-syn-vues [data-syn="{vue}"]')).to_have_attribute("aria-pressed", "true")


def test_douter_dans_la_boite_du_guide_puis_ajouter_au_fil(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    hauteur = lambda: page.evaluate(  # noqa: E731
        "() => Math.round(document.querySelector('#an-guide').getBoundingClientRect().height)")
    avant = hauteur()
    rid = _cri(decor)["id"]
    douter = page.locator(f'#an-poses-liste [data-douter="{rid}"]')
    expect(douter).to_be_visible()
    douter.click()
    champ = page.locator("#an-dt-texte")
    expect(champ).to_be_focused()
    expect(page.locator("#an-dt-titre")).to_have_text("? Douter de « cri »")
    assert hauteur() == avant
    # Sans commentaire, rien ne part.
    envois = []
    page.on("request", lambda r: envois.append(r.url) if "/doutes" in r.url else None)
    page.locator("#an-dt-envoyer").click()
    expect(champ).to_have_attribute("aria-invalid", "true")
    assert envois == []
    # Le survol d'une entrée ne reprend pas la boîte tant que le formulaire est ouvert : la
    # saisie garde son champ ET son focus.
    champ.type("Un juron")
    page.locator("#an-plan .an-ent-btn", has_text="origine du son").hover()
    page.locator("#an-plan .an-ent-btn", has_text="cri").first.hover()
    expect(champ).to_be_focused()
    expect(champ).to_have_value("Un juron")
    champ.fill("Un juron, plutôt ?")
    with page.expect_response(lambda r: r.request.method == "POST"
                              and r.url.endswith(f"/api/releves/{rid}/doutes")) as rep:
        champ.press("Control+Enter")
    assert rep.value.status == 201
    assert rep.value.request.post_data_json == {"texte": "Un juron, plutôt ?"}
    expect(page.locator("#an-dt-texte")).to_have_count(0)
    expect(page.locator("#an-poses-liste .an-etat-doute")).to_have_count(1)
    expect(page.locator('#an-mini .an-mz[data-case="0"]')).to_have_class(re.compile(r"\bdoute\b"))
    expect(page.locator("#an-n-revoir")).to_have_text(" · 1")
    # Un second « ? » ajoute au fil du doute ouvert.
    douter.click()
    expect(page.locator("#an-dt-titre")).to_have_text("? Ajouter au doute sur « cri »")
    page.locator("#an-dt-texte").fill("Je penche pour le cri.")
    page.locator("#an-dt-envoyer").click()
    expect(page.locator("#an-dt-texte")).to_have_count(0)
    assert [m["texte"] for m in _cri(decor)["doute"]["messages"]] == [
        "Un juron, plutôt ?", "Je penche pour le cri."]
    # Échap referme un formulaire vide, et rend le focus au « ? ».
    douter.click()
    page.keyboard.press("Escape")
    expect(page.locator("#an-dt-texte")).to_have_count(0)
    expect(douter).to_be_focused()


def test_un_doute_a_moitie_ecrit_garde_la_planche(page, decor):
    with _http(decor) as c:                       # une seconde planche dans l'album
        p2 = c.post(f"/api/albums/{decor['album']}/import",
                    files={"file": ("p2.png", make_png(), "image/png")}).json()["id"]
    _ouvrir(page, decor, decor["bulle"])
    page.locator(f'#an-poses-liste [data-douter="{_cri(decor)["id"]}"]').click()
    page.locator("#an-dt-texte").fill("à moitié")
    page.locator("#an-planche-choix").select_option(str(p2))
    expect(page.locator("#toasts")).to_contain_text("en cours d'écriture")
    expect(page.locator("#an-planche-choix")).to_have_value(str(decor["planche"]))
    expect(page.locator("#an-dt-texte")).to_have_value("à moitié")


def test_a_revoir_repondre_puis_lever_en_gardant(page, decor):
    rid = _cri(decor)["id"]
    d = _douter_api(decor, rid, "Un juron ?")
    _ouvrir(page, decor, decor["bulle"])
    _synthese(page, "revoir")
    expect(page.locator("#an-syn-n")).to_have_text(" (1)")
    corps = page.locator("#an-syn-corps")
    expect(corps.locator(".an-syn-g-titre", has_text="Doutes ouverts · 1")).to_be_visible()
    expect(corps.locator(".an-fil-texte")).to_have_text(["Un juron ?"])
    reponse = page.locator(f"#an-rep-{d['id']}")
    reponse.fill("Non, un cri.")
    with page.expect_response(lambda r: r.request.method == "POST"
                              and r.url.endswith(f"/api/doutes/{d['id']}/messages")) as rep:
        page.locator(f'[data-repondre="{d["id"]}"]').click()
    assert rep.value.status == 201
    expect(corps.locator(".an-fil-texte")).to_have_text(["Un juron ?", "Non, un cri."])
    expect(page.locator(f"#an-rep-{d['id']}")).to_have_value("")
    with page.expect_response(lambda r: r.url.endswith(f"/api/doutes/{d['id']}/levee")) as rep:
        corps.locator('[data-lever="garde"]').click()
    assert rep.value.status == 200
    assert rep.value.request.post_data_json == {"issue": "garde", "vu": {"doute": "ouvert"}}
    expect(corps.locator(".an-syn-g-titre", has_text="Doutes ouverts")).to_have_count(0)
    leves = corps.locator(".an-syn-g", has=page.locator(".an-syn-g-titre", has_text="Doutes levés · 1"))
    expect(leves).to_be_visible()
    expect(leves.locator(".an-rv-ligne")).to_contain_text("— gardé")
    expect(leves.locator(".an-fil-texte")).to_have_text(["Un juron ?", "Non, un cri."])
    expect(page.locator("#an-n-revoir")).to_have_text("")
    r = _cri(decor)
    assert r["doute"] is None and [x["issue"] for x in r["doutes_leves"]] == ["garde"]


def test_changer_en_place_pour_une_variante_sinon_retirer(page, decor):
    ton = _poser(decor, region_id=decor["bulle"], entree_cle="ton-de-voix", variante_cle="crie")
    _douter_api(decor, ton["id"], "Plutôt chuchoté ?")
    _douter_api(decor, _cri(decor)["id"], "Vraiment un cri ?")
    _ouvrir(page, decor, decor["bulle"])
    _synthese(page, "revoir")
    corps = page.locator("#an-syn-corps")
    item_ton = corps.locator(".an-rv", has=page.locator(f'[data-syn-releve="{ton["id"]}"]'))
    item_ton.locator("[data-changer]").click()
    choix = item_ton.locator(".an-rv-changer")
    expect(choix.locator('[data-changer-v="crie"]')).to_have_attribute("aria-pressed", "true")
    with page.expect_response(lambda r: r.url.endswith("/levee")) as rep:
        choix.locator('[data-changer-v="chuchote"]').click()
    assert rep.value.request.post_data_json["issue"] == "change"
    apres = next(r for r in _releves(decor) if r["id"] == ton["id"])
    assert apres["variante_cle"] == "chuchote" and apres["doute"] is None
    assert [x["issue"] for x in apres["doutes_leves"]] == ["change"]
    expect(corps.locator(".an-syn-g-titre", has_text="Doutes levés · 1")).to_be_visible()
    # Une autre entrée ne se change pas en place : « retirez, puis posez l'autre ».
    rid = _cri(decor)["id"]
    item_cri = corps.locator(".an-rv", has=page.locator(f'[data-syn-releve="{rid}"]')).first
    changer = item_cri.locator("[data-changer]")
    expect(changer).to_have_attribute("aria-disabled", "true")
    changer.focus()                               # éteint, il reste focalisable et le dit
    page.keyboard.press("Enter")
    expect(page.locator("#an-annonce")).to_have_text(re.compile("retirez ce relevé, puis posez l'autre"))
    item_cri.locator('[data-lever="retire"]').click()
    expect(corps.locator(f'[data-syn-releve="{rid}"]')).to_have_count(0)
    assert not [r for r in _releves(decor) if r["entree_cle"] == "cri"]


def test_a_revoir_rattacher_aux_mots_designes(page, decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=180,
                      headers=ECRITURE) as c:     # MILLE disparaît du texte : le cri le perd
        assert c.put(f"/api/regions/{decor['bulle']}",
                     json={"ocr_texte": "CENT SABORDS !"}).status_code == 200
    r = _cri(decor)            # le rang 0 a changé de mot : le texte a changé depuis la pose
    assert r["etat"] == "a_revoir" and "texte_change" in r["causes"]
    _ouvrir(page, decor, decor["bulle"])
    _synthese(page, "revoir")
    item = page.locator("#an-syn-corps .an-rv", has=page.locator(f'[data-syn-releve="{r["id"]}"]'))
    expect(item.locator(".an-causes")).to_contain_text("le texte a changé depuis la pose")
    expect(item).to_contain_text("désignait « MILLE »")
    _mot(page, 0).click()
    with page.expect_response(lambda x: x.request.method == "PUT"
                              and x.url.endswith(f"/api/releves/{r['id']}")) as rep:
        item.locator("[data-rattacher]").click()
    assert rep.value.status == 200
    assert rep.value.request.post_data_json == {"mots": [0], "vu": {"mots": [0]}}
    r = _cri(decor)
    assert r["etat"] == "normal" and [m["forme"] for m in r["mots"]] == ["CENT"]
    expect(page.locator("#an-syn-corps")).to_contain_text("Rien à revoir sur cette planche.")


def test_a_completer_la_precision_s_ecrit_dans_a_revoir(page, decor):
    o = _poser(decor, region_id=decor["bulle"], entree_cle="origine-du-son", mots=[1],
               qualificatifs=["objet"])
    _ouvrir(page, decor, decor["bulle"])
    _synthese(page, "revoir")
    corps = page.locator("#an-syn-corps")
    expect(corps.locator(".an-syn-g-titre", has_text="À compléter · 1")).to_be_visible()
    expect(corps.locator(".an-causes")).to_have_text("précision attendue")
    champ = page.locator(f"#an-rv-prec-{o['id']}")
    champ.fill("le salon")
    champ.press("Enter")
    expect(corps).to_contain_text("Rien à revoir sur cette planche.")
    apres = next(r for r in _releves(decor) if r["id"] == o["id"])
    assert apres["precision"] == "le salon" and apres["etat"] == "normal"


def test_synthese_releves_par_case_puis_decompte(page, decor):
    regard = _poser(decor, region_id=decor["c2"], entree_cle="regard-camera")
    _poser(decor, planche_id=decor["planche"], entree_cle="ambiance")
    _poser(decor, region_id=decor["bulle"], entree_cle="ton-de-voix", variante_cle="crie")
    _ouvrir(page, decor, decor["bulle"])
    avant = _boites(page)
    _synthese(page, "releves")
    corps = page.locator("#an-syn-corps")
    expect(corps.locator(".an-syn-g-titre")).to_have_text(
        ["Case c1 · 2", "Case c2 · 1", "La planche · 1"])
    expect(corps.locator('[data-syn-case="0"]')).to_have_attribute("aria-current", "true")
    # Un clic ouvre le relevé : sa case, sa zone ; la case en cours suit.
    corps.locator(f'[data-syn-releve="{regard["id"]}"]').click()
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    expect(page.locator("#an-tete-zone")).to_have_text("")
    expect(corps.locator('[data-syn-case="1"]')).to_have_attribute("aria-current", "true")
    expect(page.locator("#an-guide-contenu .an-g-lib")).to_have_text("regard caméra")
    assert _boites(page) == avant
    # Le mot du cri, ouvert depuis la Synthèse, est désigné.
    corps.locator(f'[data-syn-releve="{_cri(decor)["id"]}"]').click()
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    expect(_mot(page, 0)).to_have_attribute("aria-selected", "true")
    # Le Décompte : toute la planche, par rubrique, entrée, variante ; zones terminées.
    page.locator('#an-syn-vues [data-syn="decompte"]').click()
    expect(corps.locator(".an-dc-titre")).to_contain_text("Signaux · 4")
    expect(corps.locator(".an-dc-titre")).to_contain_text("zones terminées 0 / 5")
    lignes = corps.locator(".an-dc-l")
    expect(lignes.filter(has_text="crié")).to_contain_text("1")
    expect(lignes.filter(has_text="A. Sons")).to_contain_text("2")
    # Cette zone : la bulle, sa case et la planche — le regard de c2 n'y est pas.
    corps.locator('[data-portee="zone"]').click()
    expect(corps.locator(".an-dc-titre")).to_contain_text("Signaux · 3")
    expect(corps.locator(".an-dc-titre")).to_contain_text("zones terminées 0 / 3")
    expect(lignes.filter(has_text="regard caméra")).to_have_count(0)
    # Le retour à la planche : la minicarte est là, la Synthèse cachée.
    page.locator("#an-ong-planche").click()
    expect(page.locator("#an-mini")).to_be_visible()
    expect(page.locator("#an-p-synthese")).to_be_hidden()


def test_les_onglets_de_gauche_au_clavier(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-ong-planche").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#an-ong-synthese")).to_be_focused()
    expect(page.locator("#an-ong-synthese")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#an-p-synthese")).to_be_visible()
    page.keyboard.press("Home")
    expect(page.locator("#an-ong-planche")).to_be_focused()
    expect(page.locator("#an-p-planche")).to_be_visible()


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_une_lectrice_lit_les_doutes_sans_aucun_geste(page, live_server):
    """Hugo, 2026-10-26 : les lecteurs voient les auteurs et le fil des doutes, gestes en
    moins — ni « ? », ni « ✕ », ni réponse, ni levée."""
    admin = {"Remote-User": "decor", "Remote-Name": "Decor Admin", "Remote-Groups": "bd-admins"}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=180,
                      headers={**ECRITURE, **admin}) as c:
        c.get("/api/moi")                         # le nom lisible s'enregistre là
        cid = c.post("/api/collections", json={"nom": "Étude lue"}).json()["id"]
        du_projet(c, cid, "utilisateur", "lectrice", headers={**ECRITURE, **admin})
        assert c.put(f"/api/collections/{cid}/acces", json={
            "genre": "utilisateur", "principal": "lectrice", "niveau": "lecture"}).status_code == 200
        aid = c.post("/api/albums", json={"titre": "Lu", "collection_id": cid}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]
        case = c.post(f"/api/planches/{pid}/regions",
                      json={"type": "case", "x": 20, "y": 20, "w": 700, "h": 900}).json()["id"]
        bulle = c.post(f"/api/planches/{pid}/regions",
                       json={"type": "bulle", "x": 60, "y": 60, "w": 200, "h": 120,
                             "parent_id": case}).json()["id"]
        c.put(f"/api/regions/{bulle}", json={"ocr_texte": "MILLE SABORDS !"})
        g = grille_active_vivante(c)
        r = c.post("/api/releves", json={"region_id": bulle, "grille_id": g["grille_id"],
                                         "version": 1, "entree_cle": "cri", "mots": [0]})
        assert r.status_code == 201, r.text
        assert c.post(f"/api/releves/{r.json()['id']}/doutes",
                      json={"texte": "Un juron ?"}).status_code == 201
        perso = c.post("/api/personnages", json={"nom": "Haddock"}).json()["id"]
        assert c.put(f"/api/regions/{bulle}/locuteur",
                     json={"personnage_id": perso}).status_code == 200
    page.set_extra_http_headers({"Remote-User": "lectrice"})
    page.goto(f"{live_server}/annotation?album={aid}&planche={pid}&region={bulle}",
              wait_until="networkidle")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_be_visible(timeout=15000)
    expect(page.locator("#an-poses-liste .an-etat-doute")).to_be_visible()
    expect(page.locator("#an-poses-liste [data-douter]")).to_have_count(0)
    expect(page.locator("#an-poses-liste [data-retirer]")).to_have_count(0)
    _synthese(page, "revoir")
    corps = page.locator("#an-syn-corps")
    expect(corps.locator(".an-fil-texte")).to_have_text(["Un juron ?"])
    expect(corps.locator(".an-fil-qui")).to_have_text(["Decor Admin"])
    expect(corps.locator("textarea, [data-lever], [data-changer], [data-repondre]")).to_have_count(0)
    # La grille se voit ÉTEINTE et le dit au clic, à l'écran et au lecteur d'écran (commit 7 :
    # le clic sautait l'annonce). Playwright ne clique pas un élément éteint : on
    # envoie le clic comme le navigateur le ferait.
    cri = page.locator("#an-plan [role=checkbox]", has_text="cri").first
    expect(cri).to_have_attribute("aria-disabled", "true")
    assert cri.evaluate("(b) => getComputedStyle(b).cursor") != "pointer"
    cri.dispatch_event("click")
    expect(page.locator("#toasts")).to_contain_text("Vous lisez cet album")
    expect(page.locator("#an-annonce")).to_have_text("Vous lisez cet album : rien ne s'y pose.")
    # Le TITRE d'une entrée à variantes s'éteint comme le reste (passe des correctifs) ; le
    # survol y montre encore le guide.
    tete = page.locator("#an-plan .an-ent-tete", has_text="onomatopée de choc")
    expect(tete).to_have_attribute("aria-disabled", "true")
    assert tete.evaluate("(b) => getComputedStyle(b).cursor") != "pointer"
    tete.hover()
    expect(page.locator("#an-guide-contenu")).to_contain_text("le bruit d'un choc")
    # Éteinte, la grille garde ses couleurs : elles nomment les parties, pas un geste.
    expect(page.locator("#an-plan .an-rub-tete > .an-rub-filet.an-teinte-0").first).to_be_visible()
    # Le Contexte se LIT, sans aucun champ (commit 8).
    page.locator("#an-ong-planche").click()
    expect(page.locator("#an-note-lu")).to_have_text("—")
    expect(page.locator("#an-note")).to_be_hidden()
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    expect(page.locator("#an-loc-saisie")).to_be_hidden()
    expect(page.locator("#an-loc-retirer")).to_be_hidden()
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers={**ECRITURE, **admin}) as c:
        assert len(c.get(f"/api/planches/{pid}/releves").json()["releves"]) == 1


def test_la_synthese_tient_a_320_px(page, decor):
    """La sonde du reflow mesure la page au repos, Synthèse cachée : ce test l'ouvre, sur
    « À revoir » qui porte le plus de gestes, et exige qu'aucun élément ne déborde de côté."""
    _douter_api(decor, _cri(decor)["id"], "Un juron, ou un cri qu'on n'entend pas ?")
    page.set_viewport_size({"width": 320, "height": 900})
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-tiroir-planche").click()         # sous 75em, le tiroir la porte
    _synthese(page, "revoir")
    expect(page.locator("#an-syn-corps [data-lever=garde]")).to_be_visible()
    dehors = page.evaluate("""() => [...document.querySelectorAll('#an-gauche *')]
      .filter((x) => { const r = x.getBoundingClientRect();
                       return r.width && (r.right > innerWidth + 1 || r.left < -1); })
      .map((x) => x.id || x.className)""")
    assert not dehors, dehors
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")


def test_le_decompte_compte_toutes_les_grilles(page, decor):
    """« Relevés : ▾ » vaut pour la Synthèse, pas pour le Décompte (ANN-6, 2026-10-22) : un
    relevé d'une autre grille, absent des Relevés par case, est compté."""
    with _http(decor) as c:
        g = grille_active_vivante(c, nom="Lieux", ouverte=True, projet_id=decor["projet"])
        r = c.post("/api/releves", json={"grille_id": g["grille_id"], "version": 1,
                                         "region_id": decor["bulle"], "mots": [1],
                                         "nouvelle_entree": {"libelle": "Moulinsart"}})
        assert r.status_code == 201, r.text
    _ouvrir(page, decor, decor["bulle"])
    page.locator(f"#an-onglet-{decor['grille']}").click()          # Signaux, pas Lieux
    expect(page.locator(f"#an-onglet-{decor['grille']}")).to_have_attribute("aria-selected", "true")
    _synthese(page, "releves")
    corps = page.locator("#an-syn-corps")
    expect(corps.locator(".an-syn-g-titre")).to_have_text(["Case c1 · 1"])
    expect(corps.locator(".an-pose-lib", has_text="Moulinsart")).to_have_count(0)
    page.locator('#an-syn-vues [data-syn="decompte"]').click()
    expect(corps.locator(".an-dc-titre", has_text="Lieux · 1")).to_be_visible()
    expect(corps.locator(".an-dc-titre", has_text="Signaux · 1")).to_be_visible()
    expect(corps.locator(".an-dc-l", has_text="Moulinsart")).to_have_count(1)


# --------------------------------------------------------------------------- #
# Deux écrans (commit 6)
# --------------------------------------------------------------------------- #
# « L'autre écran » est un client HTTP : ce que la page n'a pas écrit elle-même lui vient
# d'ailleurs. Le signal se demande au retour sur l'onglet (`visibilitychange`), comme dans
# l'Atelier (`tests/test_e2e_planche_changee.py`).
def _retour_sur_l_onglet(page):
    with page.expect_response(lambda r: r.url.endswith("/empreinte")):
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")


def test_un_releve_pose_ailleurs_propose_actualiser_qui_garde_la_saisie(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    bouton = page.locator("#an-actualiser")
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_hidden()
    # Ce que la page écrit elle-même ne se signale pas : un doute, une passe.
    page.locator(f'#an-poses-liste [data-douter="{_cri(decor)["id"]}"]').click()
    page.locator("#an-dt-texte").fill("Un juron ?")
    page.locator("#an-dt-envoyer").click()
    expect(page.locator("#an-dt-texte")).to_have_count(0)
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_hidden()
    # Un brouillon de doute, des mots désignés, puis un relevé posé AILLEURS sur la bulle.
    _mot(page, 0).click()                          # le mot du cri : sa ligne reste
    page.locator(f'#an-poses-liste [data-douter="{_cri(decor)["id"]}"]').click()
    page.locator("#an-dt-texte").fill("Et ce second mot ?")
    _poser(decor, region_id=decor["bulle"], entree_cle="ton-de-voix", variante_cle="crie")
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_visible()
    expect(bouton).to_have_attribute(
        "title", "La planche a changé ailleurs : des relevés sur 1 zone. "
                 "Actualiser la recharge, sans perdre votre saisie.")
    # Rien ne se recharge d'office.
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "false")
    with page.expect_response(lambda r: r.url.endswith(f"/api/planches/{decor['planche']}/releves")):
        bouton.click()
    expect(bouton).to_be_hidden()
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "true")
    # La saisie est restée : la zone, le mot désigné, le doute à moitié écrit.
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    expect(_mot(page, 0)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#an-dt-texte")).to_have_value("Et ce second mot ?")
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_hidden()


def test_une_passe_ou_un_doute_d_ailleurs_se_signalent_aussi(page, decor):
    _ouvrir(page, decor, decor["c2"])
    bouton = page.locator("#an-actualiser")
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_hidden()
    with _http(decor) as c:
        assert c.put(f"/api/planches/{decor['planche']}/passes/{decor['grille']}",
                     json={}).status_code == 200
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_visible()
    bouton.click()
    expect(bouton).to_be_hidden()
    _douter_api(decor, _cri(decor)["id"], "Vu d'ailleurs ?")
    _retour_sur_l_onglet(page)
    expect(bouton).to_be_visible()


def test_un_releve_retire_ailleurs_quitte_la_page_sans_rien_relancer(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    rid = _cri(decor)["id"]
    expect(page.locator(f'#an-poses-liste [data-retirer="{rid}"]')).to_be_visible()
    with _http(decor) as c:
        assert c.request("DELETE", f"/api/releves/{rid}").status_code == 204
    envois = []
    page.on("request", lambda r: envois.append((r.method, r.url))
            if "/api/releves" in r.url and r.method != "GET" else None)
    page.locator(f'#an-poses-liste [data-retirer="{rid}"]').click()
    expect(page.locator("#toasts")).to_contain_text("retiré depuis, par un autre écran")
    expect(page.locator(f'#an-poses-liste [data-retirer="{rid}"]')).to_have_count(0)
    assert envois == [("DELETE", f"{decor['base']}/api/releves/{rid}")]


def test_un_doute_dont_le_releve_est_retire_ailleurs_rend_son_texte(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    rid = _cri(decor)["id"]
    page.locator(f'#an-poses-liste [data-douter="{rid}"]').click()
    page.locator("#an-dt-texte").fill("Mon doute écrit pour rien")
    with _http(decor) as c:
        assert c.request("DELETE", f"/api/releves/{rid}").status_code == 204
    page.locator("#an-dt-envoyer").click()
    expect(page.locator("#toasts")).to_contain_text("« Mon doute écrit pour rien »")
    expect(page.locator("#an-dt-texte")).to_have_count(0)


def test_actualiser_attend_un_conflit_ouvert(page, decor):
    with _http(decor) as c:
        r = c.post("/api/releves", json={"region_id": decor["bulle"], "grille_id": decor["grille"],
                                         "version": 1, "entree_cle": "ton-de-voix",
                                         "variante_cle": "crie"}).json()
    _ouvrir(page, decor, decor["bulle"])
    with _http(decor) as c:
        assert c.put(f"/api/releves/{r['id']}", json={"variante_cle": "chuchote"}).status_code == 200
    page.locator("#an-plan .an-var", has_text="crié").click()        # ouvre le bandeau
    expect(page.locator("#an-cf-titre")).to_be_visible()
    # Un autre changement, sur une autre zone (la bulle, touchée par le retrait refusé, a
    # adopté sa nouvelle empreinte : c'est la limite écrite de `lib/signal-planche.js`).
    _poser(decor, region_id=decor["c2"], entree_cle="regard-camera")
    _retour_sur_l_onglet(page)
    bouton = page.locator("#an-actualiser")
    expect(bouton).to_be_visible()
    bouton.click()
    expect(page.locator("#an-cf-mienne")).to_be_focused()            # le conflit attend son choix
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(bouton).to_be_visible()


# --------------------------------------------------------------------------- #
# Les correctifs de la passe du jalon 1 (commit 7)
# --------------------------------------------------------------------------- #
def test_la_precision_et_le_retrait_tiennent_sur_une_ligne(page, decor):
    """À la largeur de Hugo (~1 400 px), ✕ passait sous le champ de la précision."""
    page.set_viewport_size({"width": 1400, "height": 900})
    o = _poser(decor, region_id=decor["bulle"], entree_cle="origine-du-son", mots=[1],
               qualificatifs=["objet"])
    _ouvrir(page, decor, decor["bulle"])
    champ = page.locator("#an-poses-liste .an-prec")
    retrait = page.locator(f'#an-poses-liste [data-retirer="{o["id"]}"]')
    expect(champ).to_be_visible()
    c, x = champ.bounding_box(), retrait.bounding_box()
    assert abs((c["y"] + c["height"] / 2) - (x["y"] + x["height"] / 2)) < 6, (c, x)
    assert x["x"] >= c["x"] + c["width"] - 1, (c, x)


def test_le_lien_se_designe_sur_la_minicarte_et_dit_sa_zone(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-plan [role=checkbox]", has_text="réponse à une autre bulle").click()
    page.locator("#an-poses-liste .an-lien-btn").click()
    mode = page.locator("#an-mini-mode")
    expect(mode).to_be_visible()                     # la minicarte a changé de rôle, et le dit
    expect(page.locator("#an-mini")).to_have_attribute("title", re.compile("zone liée"))
    # Le cartouche de la seconde case, sur la MINICARTE : le cadre de la case ne prend plus
    # le clic (Playwright refuserait de cliquer un élément recouvert).
    with _reponse_de(page, RELEVE):
        page.locator(f'#an-mini rect[data-region="{decor["cartouche"]}"]').click()
    expect(mode).to_be_hidden()
    expect(page.locator("#an-tete-case")).to_have_text("Case c1")      # la case n'a pas changé
    r = [x for x in _releves(decor) if x["entree_cle"] == "reponse-a"]
    assert r[0]["lien"]["region_id"] == decor["cartouche"]
    # Le cartouche est dans une AUTRE case : le lien la nomme (passe des correctifs).
    expect(page.locator("#an-poses-liste .an-pose-lien")).to_have_text("↔ c2 · b1 « PENDANT CE TEMPS… »")
    # Après la désignation, la minicarte rechoisit des cases.
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")


def test_la_boite_du_guide_se_replie_et_la_liste_prend_sa_place(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    bouton = page.locator("#an-guide-replier")
    expect(bouton).to_have_attribute("aria-expanded", "true")
    hauteur = lambda s: page.evaluate(  # noqa: E731
        "(s) => Math.round(document.querySelector(s).getBoundingClientRect().height)", s)
    colonne, poses = hauteur("#an-grille"), hauteur("#an-poses")
    bouton.click()
    expect(bouton).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#an-guide-contenu")).to_be_hidden()
    assert hauteur("#an-poses") > poses + 60
    assert hauteur("#an-grille") == colonne
    # Retenu au rechargement.
    page.reload(wait_until="networkidle")
    expect(page.locator("#an-guide-replier")).to_have_attribute("aria-expanded", "false", timeout=15000)
    # Le formulaire d'un doute la déplie d'office ; refermé, elle se replie de nouveau.
    page.locator(f'#an-poses-liste [data-douter="{_cri(decor)["id"]}"]').click()
    expect(page.locator("#an-dt-texte")).to_be_visible()
    expect(page.locator("#an-guide-replier")).to_have_attribute("aria-expanded", "true")
    page.locator("#an-dt-annuler").click()
    expect(page.locator("#an-guide-replier")).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#an-guide-contenu")).to_be_hidden()


def test_le_releve_de_la_planche_se_lit_partout_et_la_case_se_dit_la_case(page, decor):
    _poser(decor, planche_id=decor["planche"], entree_cle="ambiance")
    _poser(decor, region_id=decor["c1"], entree_cle="regard-camera")
    _ouvrir(page, decor, decor["bulle"])
    liste = page.locator("#an-poses-liste")
    expect(liste.locator("#an-poses-planche")).to_have_text("Sur la planche")
    # En bas, à part : après le groupe, le relevé de la surface.
    textes = liste.locator("li").all_inner_texts()
    i = textes.index("Sur la planche")
    assert any("ambiance" in t for t in textes[i + 1:]) and not any("ambiance" in t for t in textes[:i])
    regard = liste.locator(".an-pose", has_text="regard caméra")
    expect(regard.locator(".an-pose-pass")).to_have_text("la case")
    page.locator("#an-vue-case rect.an-fond").click(position={"x": 5, "y": 200})
    expect(page.locator("#an-tete-zone")).to_have_text("")
    expect(liste.locator(".an-pose", has_text="regard caméra").locator(".an-pose-pass")).to_have_text("la case")


def test_porte_sur_repart_de_la_zone_et_la_liste_le_suit(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, 1).click()                                  # SABORDS : le cri sur MILLE sort
    expect(page.locator("#an-poses-titre")).to_have_text("Sur « SABORDS »")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(0)
    # « toute la bulle » : la liste suit « Porte sur », le mot restant désigné.
    page.locator('#an-porte [data-porte="zone"]').click()
    expect(page.locator("#an-poses-titre")).to_have_text("Dans la bulle b1")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_have_count(1)
    # Un choix d'une autre zone ne suit pas : « la planche », puis le cartouche.
    page.locator('#an-porte [data-porte="planche"]').click()
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    page.locator(f'#an-vue-case rect[data-zone="{decor["cartouche"]}"]').click()
    expect(page.locator('#an-porte [aria-pressed="true"]')).to_have_attribute("data-porte", "mots")


def test_le_titre_d_un_passage_suit_le_texte_transcrit(page, decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=180,
                      headers=ECRITURE) as c:
        assert c.put(f"/api/regions/{decor['bulle']}",
                     json={"ocr_texte": "L' CUL !"}).status_code == 200
        decoupe = c.get(f"/api/regions/{decor['bulle']}/mots").json()["mots"]
    rangs = [m["rang"] for m in decoupe if m["forme"] != "!"]
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, rangs[0]).click()
    _mot(page, rangs[-1]).click(modifiers=["Shift"])
    expect(page.locator("#an-poses-titre")).to_have_text("Sur « L' CUL »")


def test_l_atelier_et_la_page_annotation_partagent_le_lieu(page, decor):
    """Hugo, 2026-10-30 : par la navigation, l'une et l'autre gardent l'album, la planche
    et la zone ; une adresse explicite l'emporte toujours."""
    _ouvrir(page, decor, decor["cartouche"])
    page.locator('#site-nav a[href="/"]').click()
    page.wait_for_url(re.compile(rf"region={decor['cartouche']}"), timeout=15000)
    assert f"planche={decor['planche']}" in page.url and f"album={decor['album']}" in page.url
    # L'Atelier, sur une autre zone par son adresse : la page Annotation la reprend, par-dessus
    # sa propre mémoire (qui disait le cartouche).
    page.goto(f"{decor['base']}/?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor['bulle']}", wait_until="networkidle")
    expect(page.locator("#region-type")).to_be_visible(timeout=15000)
    page.locator('#site-nav a[href="/annotation"]').click()
    page.wait_for_url("**/annotation?*", timeout=15000)
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1", timeout=15000)
    # Une adresse explicite l'emporte.
    page.goto(f"{decor['base']}/annotation?album={decor['album']}&planche={decor['planche']}"
              f"&region={decor['c2']}", wait_until="networkidle")
    expect(page.locator("#an-tete-case")).to_have_text("Case c2", timeout=15000)


# --------------------------------------------------------------------------- #
# Jalon 3, commit 8 — les restes de la passe, le Contexte modifiable
# --------------------------------------------------------------------------- #
def test_un_lien_vers_une_autre_case_nomme_sa_case(page, decor):
    """« ↔ b1 « Pédé ! » » ne disait pas laquelle des deux b1 (passe des correctifs)."""
    with _http(decor) as c:                        # une bulle dans la case c2 : c2 a sa b1
        b2 = c.post(f"/api/planches/{decor['planche']}/regions",
                    json={"type": "bulle", "x": 450, "y": 200, "w": 200, "h": 80,
                          "parent_id": decor["c2"]}).json()["id"]
        c.put(f"/api/regions/{b2}", json={"ocr_texte": "PÉDÉ !"})
    loin = _poser(decor, region_id=decor["bulle"], entree_cle="reponse-a")
    with _http(decor) as c:
        assert c.put(f"/api/releves/{loin['id']}",
                     json={"lien_region_id": b2}).status_code == 200
    _ouvrir(page, decor, decor["bulle"])
    lien = page.locator("#an-poses-liste .an-pose-lien")
    expect(lien).to_have_text(re.compile(r"^↔ c2 · b\d « PÉDÉ ! »$"))
    # Dans la même case, la forme courte : une seconde bulle de c1.
    with _http(decor) as c:
        b3 = c.post(f"/api/planches/{decor['planche']}/regions",
                    json={"type": "bulle", "x": 60, "y": 760, "w": 200, "h": 80,
                          "parent_id": decor["c1"]}).json()["id"]
        c.put(f"/api/regions/{b3}", json={"ocr_texte": "OUI"})
        pres = _poser(decor, region_id=decor["bulle"], entree_cle="reponse-a")
        assert c.put(f"/api/releves/{pres['id']}",
                     json={"lien_region_id": b3}).status_code == 200
    page.reload(wait_until="networkidle")
    expect(page.locator("#an-poses-liste .an-pose-lien", has_text="OUI")).to_have_text(
        re.compile(r"^↔ b\d « OUI »$"), timeout=15000)


def test_une_ligne_tient_sur_sa_hauteur_pendant_la_designation(page, decor):
    """Mesuré le 2026-10-30 : « réponse à une autre bulle » s'étalait sur 91 px pendant
    « Désigner sur la planche » — la pastille seule, le libellé coupé, les marques empilées."""
    page.set_viewport_size({"width": 1400, "height": 900})
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-plan [role=checkbox]", has_text="réponse à une autre bulle").click()
    ligne = page.locator("#an-poses-liste .an-pose", has_text="réponse à une autre bulle")
    bouton = ligne.locator(".an-lien-btn")
    expect(bouton).to_be_visible()
    hors = ligne.bounding_box()["height"]
    bouton.click()
    expect(bouton).to_have_attribute("aria-pressed", "true")
    pendant = ligne.bounding_box()["height"]
    lib = ligne.locator(".an-pose-lib")
    # Le libellé tient sur UNE ligne, la pastille à sa hauteur, et la ligne ne grandit pas.
    assert lib.bounding_box()["height"] < 26, lib.bounding_box()
    pastille, l = ligne.locator(".an-pastille").bounding_box(), lib.bounding_box()
    assert abs((pastille["y"] + pastille["height"] / 2) - (l["y"] + l["height"] / 2)) < 8
    # Trois rangées au plus, le geste de la ligne pour mesure : une borne en pixels supposait une
    # chasse. Sous DejaVu Sans, « à compléter » passe à la ligne : 71 px, et une ligne saine. Le
    # défaut d'origine, 91 px, en demandait quatre.
    rangee = bouton.bounding_box()["height"]
    assert pendant <= hors + 1 and pendant < 3 * rangee, (hors, pendant, rangee)


def test_le_locuteur_se_choisit_et_se_retire_dans_le_contexte(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    champ = page.locator("#an-loc-input")
    champ.fill("Tournesol")
    expect(page.locator("#an-loc-liste")).to_contain_text("Créer « Tournesol »")
    with page.expect_response(lambda r: "/locuteur" in r.url and r.request.method == "PUT") as rep:
        champ.press("Enter")
    corps = rep.value.request.post_data_json
    assert corps["personnage_vu"] is not None      # la valeur VUE part avec le choix
    expect(page.locator("#an-loc-nom")).to_have_text("Tournesol")
    expect(page.locator("#an-loc-liste")).to_be_hidden()
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["nom"] == "Tournesol"
    page.locator("#an-loc-retirer").click()
    expect(page.locator("#an-loc-nom")).to_have_text("—")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"] is None
    # Le CARTOUCHE a un locuteur ; la boîte personnage n'en a pas, son personnage se lit.
    page.locator('#an-mini .an-mz[data-case="1"]').click()
    page.locator(f'#an-vue-case rect[data-zone="{decor["cartouche"]}"]').click()
    expect(page.locator("#an-loc-input")).to_have_attribute("aria-label", "Attribuer un locuteur au cartouche")
    page.locator('#an-mini .an-mz[data-case="0"]').click()
    page.locator(f'#an-vue-case rect[data-zone="{decor["boite"]}"]').click()
    expect(page.locator("#an-ctx-loc")).to_be_hidden()
    expect(page.locator("#an-ctx-perso")).to_have_text("Haddock")


def test_deux_personnages_du_meme_nom_se_departagent_dans_le_contexte(page, decor):
    """Le champ est celui de l'Atelier : Entrée ne prend pas un homonyme au hasard."""
    with _http(decor) as c:
        for serie in ("Spirou", "Gaston"):
            assert c.post("/api/personnages", json={"nom": "Zed", "serie": serie}).status_code in (200, 201)
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-loc-input").fill("Zed")
    page.locator("#an-loc-input").press("Enter")
    liste = page.locator("#an-loc-liste")
    expect(liste.locator("div")).to_have_count(2)
    expect(liste).to_contain_text("Gaston")
    with _http(decor) as c:                        # rien n'est pris
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["nom"] == "Haddock"
    liste.locator("div", has_text="Spirou").dispatch_event("mousedown")
    expect(page.locator("#an-loc-nom")).to_have_text("Zed · Spirou")


def test_un_locuteur_change_ailleurs_ouvre_le_bandeau(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    with _http(decor) as c:                        # un autre écran attribue Milou
        milou = c.post("/api/personnages", json={"nom": "Milou"}).json()["id"]
        assert c.put(f"/api/regions/{decor['bulle']}/locuteur",
                     json={"personnage_id": milou}).status_code == 200
        tournesol = c.post("/api/personnages", json={"nom": "Tournesol"}).json()["id"]
    hauteur = lambda: page.evaluate(  # noqa: E731
        "() => Math.round(document.querySelector('#an-grille').getBoundingClientRect().height)")
    avant = hauteur()
    page.locator("#an-loc-input").fill("Tournesol")
    expect(page.locator("#an-loc-liste")).to_contain_text("Tournesol")
    page.locator("#an-loc-input").press("Enter")
    expect(page.locator("#an-cf-titre")).to_contain_text("Locuteur modifié")
    expect(page.locator("#an-guide-contenu")).to_contain_text("Votre choix, Tournesol, n'est pas enregistré.")
    expect(page.locator("#an-guide-contenu")).to_contain_text("Milou")
    assert hauteur() == avant
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["id"] == milou
    # Tant que le bandeau attend, la note ne part pas non plus.
    page.locator("#an-note").fill("il jure encore")
    page.locator("#an-note").blur()
    page.wait_for_timeout(800)
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il jure"
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-loc-nom")).to_have_text("Tournesol")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["id"] == tournesol
    # La note retenue part une fois le conflit réglé.
    expect(page.locator("#an-note-etat")).to_have_text("Enregistrée")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il jure encore"


def test_la_note_s_ecrit_et_un_conflit_garde_la_saisie(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    note = page.locator("#an-note")
    expect(note).to_have_value("il jure")
    with page.expect_response(lambda r: r.url.endswith(f"/regions/{decor['bulle']}/annotation")
                              and r.request.method == "PUT") as rep:
        note.fill("il jure comme un charretier")
    assert rep.value.request.post_data_json == {"note": "il jure comme un charretier",
                                                "note_vue": "il jure"}
    expect(page.locator("#an-note-etat")).to_have_text("Enregistrée")
    with _http(decor) as c:                        # un autre écran récrit la note
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "il crie"}).status_code == 200
    note.fill("il jure, et fort")
    expect(page.locator("#an-cf-titre")).to_contain_text("Note modifiée")
    expect(page.locator("#an-guide-contenu")).to_contain_text("il crie")
    expect(note).to_have_value("il jure, et fort")          # la saisie reste
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-note-etat")).to_have_text("Enregistrée")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il jure, et fort"
    # « Garder l'autre » : la version de l'autre revient dans le champ.
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "il hurle"}).status_code == 200
    note.fill("il jure, encore")
    expect(page.locator("#an-cf-titre")).to_contain_text("Note modifiée")
    page.locator("#an-cf-autre").click()
    expect(note).to_have_value("il hurle")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il hurle"


def test_une_note_tapee_puis_une_autre_zone_part_sur_la_sienne(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-note").fill("il jure, vite")
    # Aussitôt une autre zone, avant le délai de frappe : la note part sur la BULLE.
    with _reponse_de(page, f"/regions/{decor['bulle']}/annotation"):
        page.locator(f'#an-vue-case rect[data-zone="{decor["boite"]}"]').click()
    expect(page.locator("#an-tete-zone")).to_have_text(re.compile("boîte"))
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il jure, vite"
        assert c.get(f"/api/regions/{decor['boite']}/annotation").json()["note"] in (None, "")
    expect(page.locator("#an-note")).to_have_value("")


def test_ctrl_z_defait_le_locuteur_et_la_note(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-note").fill("il jure, puis non")
    page.locator("#an-loc-input").fill("Tournesol")
    expect(page.locator("#an-loc-liste")).to_contain_text("Créer « Tournesol »")
    page.locator("#an-loc-input").press("Enter")
    expect(page.locator("#an-loc-nom")).to_have_text("Tournesol")
    page.locator("#an-mots").focus()
    page.keyboard.press("Control+z")
    expect(page.locator("#toasts")).to_contain_text("Annulé :")
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["nom"] == "Haddock"
    page.locator("#an-mots").focus()
    page.keyboard.press("Control+z")
    expect(page.locator("#an-note")).to_have_value("il jure")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il jure"


def test_ctrl_z_attend_la_note_partie(page, decor):
    """Ctrl+Z défait le DERNIER geste : une note partie juste avant, dont la réponse n'est pas
    revenue, en est un. Sans attendre son retour, Ctrl+Z défaisait le geste d'AVANT — ici le
    relevé du décor — et la note restait."""
    avant = len(_releves(decor))
    retenues = []
    page.route("**/api/regions/*/annotation",
               lambda route: retenues.append(route) if route.request.method == "PUT"
               else route.continue_())
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-note").fill("il jure, puis non")
    page.locator("#an-mots").focus()                # la sortie du champ envoie la note
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues, "la note n'est pas partie"
    annulations = []
    page.on("request", lambda r: annulations.append(r.url) if r.url.endswith("/api/undo") else None)
    page.keyboard.press("Control+z")
    page.wait_for_timeout(800)
    assert annulations == [], "Ctrl+Z est parti avant le retour de la note"
    retenues[0].continue_()
    expect(page.locator("#toasts")).to_contain_text("Annulé :")
    expect(page.locator("#an-note")).to_have_value("il jure")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il jure"
    assert len(_releves(decor)) == avant


def test_un_409_pendant_la_frappe_laisse_le_focus_dans_le_champ(page, decor):
    """La note part après le délai de frappe : le 409 revient sous les doigts. S'il prenait le
    focus, l'espace suivante activerait « Remplacer par la mienne » et écraserait l'autre sans
    décision — trouvé au rejeu de la passe des correctifs du jalon 3, au clavier réel."""
    _ouvrir(page, decor, decor["bulle"])
    note = page.locator("#an-note")
    expect(note).to_have_value("il jure")
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "il crie"}).status_code == 200
    note.click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" vite")
    expect(page.locator("#an-cf-titre")).to_be_visible()     # la pause : le 409 est revenu
    expect(note).to_be_focused()
    page.keyboard.type(" et encore")                         # commence par une espace
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(note).to_have_value("il jure vite et encore")
    expect(page.locator("#an-note-etat")).to_have_text("En attente de votre choix")
    page.wait_for_timeout(700)                     # une absence : le délai de frappe passé
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il crie"
    page.locator("#an-cf-mienne").click()                    # le choix part avec TOUTE la frappe
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-note-etat")).to_have_text("Enregistrée")
    with _http(decor) as c:
        assert (c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"]
                == "il jure vite et encore")


def test_quitter_la_planche_attend_la_note_et_son_conflit(page, decor):
    """Un départ de la planche passe par ses gardes : la note pas encore partie part d'abord,
    et si elle reçoit un 409, le bandeau s'ouvre et la planche RESTE."""
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=180,
                      headers=ECRITURE) as c:
        p2 = c.post(f"/api/albums/{decor['album']}/import",
                    files={"file": ("p2.png", make_png(800, 1000), "image/png")}).json()["id"]
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    with _http(decor) as c:                        # un autre écran récrit la note
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "il crie"}).status_code == 200
    page.locator("#an-note").fill("il jure, je pars")
    page.locator("#an-planche-choix").select_option(str(p2))
    expect(page.locator("#an-cf-titre")).to_contain_text("Note modifiée")
    expect(page.locator("#an-planche-choix")).to_have_value(str(decor["planche"]))
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/annotation").json()["note"] == "il crie"


# --------------------------------------------------------------------------- #
# Jalon 3, commit 9 — tracer une zone : un détail d'image, un texte hors bulle
# --------------------------------------------------------------------------- #
def _glisser(page, fx1, fy1, fx2, fy2):
    """Un glissé dans la case agrandie, en fractions de sa boîte à l'écran."""
    b = page.locator("#an-vue-case svg.an-case-svg").bounding_box()
    page.mouse.move(b["x"] + b["width"] * fx1, b["y"] + b["height"] * fy1)
    page.mouse.down()
    page.mouse.move(b["x"] + b["width"] * (fx1 + fx2) / 2, b["y"] + b["height"] * (fy1 + fy2) / 2,
                    steps=4)
    page.mouse.move(b["x"] + b["width"] * fx2, b["y"] + b["height"] * fy2, steps=4)
    page.mouse.up()


def _regions(d):
    with _http(d) as c:
        return {r["id"]: r for r in c.get(f"/api/planches/{d['planche']}/regions").json()}


def test_tracer_un_detail_le_nommer_et_le_lire_sur_l_image(page, decor):
    _ouvrir(page, decor)                                     # la case c1, sans zone
    avant = set(_regions(decor))
    # Un détail DANS la boîte personnage (80, 400)–(230, 700) de la case (20, 20, 360, 900) :
    # le glissé commence et finit sur la boîte, et le clic qui le termine ne la choisit pas.
    _glisser(page, 0.25, 0.47, 0.5, 0.7)
    choix = page.locator("#an-trace")
    expect(choix).to_be_visible()
    expect(page.locator("#an-vue-case .an-trace-rect")).to_have_count(1)
    expect(page.locator("#an-tete-case")).to_have_text("Case c1")
    expect(page.locator("#an-tete-zone")).to_have_text("")            # le glissé n'a rien choisi
    with page.expect_response(lambda r: r.request.method == "POST"
                              and r.url.endswith(f"/planches/{decor['planche']}/regions")) as rep:
        choix.locator('[data-trace="detail"]').click()
    corps = rep.value.request.post_data_json
    assert corps["type"] == "detail" and corps["parent_id"] == decor["c1"]
    assert corps["w"] > 50 and corps["h"] > 50                         # des pixels master
    nouvelles = set(_regions(decor)) - avant
    assert len(nouvelles) == 1
    d = nouvelles.pop()
    expect(choix).to_be_hidden()
    expect(page.locator("#an-tete-zone")).to_have_text(re.compile(r"^détail d\d$"))
    nom = page.locator("#an-nom")
    expect(nom).to_be_focused()
    nom.fill("le téléphone")
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(f"/api/regions/{d}")) as rep:
        nom.press("Enter")
    assert rep.value.request.post_data_json == {"nom": "le téléphone", "vu": {"nom": None}}
    assert _regions(decor)[d]["nom"] == "le téléphone"
    expect(page.locator("#an-vue-case text.an-vz-lbl", has_text="le téléphone")).to_have_count(1)
    # Ni locuteur ni transcription : un détail a un nom et une note.
    expect(page.locator("#an-ctx-loc")).to_be_hidden()
    expect(page.locator("#an-ctx-tr")).to_be_hidden()
    expect(page.locator("#an-note")).to_be_visible()
    # Échap annule un tracé, sans rien créer.
    _glisser(page, 0.1, 0.6, 0.4, 0.75)
    expect(choix).to_be_visible()
    page.keyboard.press("Escape")
    expect(choix).to_be_hidden()
    expect(page.locator("#an-vue-case .an-trace-rect")).to_have_count(0)
    assert len(_regions(decor)) == len(avant) + 1


def test_un_nom_change_ailleurs_ouvre_le_bandeau(page, decor):
    with _http(decor) as c:
        d = c.post(f"/api/planches/{decor['planche']}/regions",
                   json={"type": "detail", "x": 200, "y": 100, "w": 100, "h": 100,
                         "parent_id": decor["c1"], "nom": "la lampe"}).json()["id"]
    _ouvrir(page, decor, d)
    nom = page.locator("#an-nom")
    expect(nom).to_have_value("la lampe")
    with _http(decor) as c:
        assert c.put(f"/api/regions/{d}", json={"nom": "le phare"}).status_code == 200
    nom.fill("la lampe de poche")
    nom.press("Enter")
    expect(page.locator("#an-cf-titre")).to_contain_text("Nom modifié")
    expect(page.locator("#an-guide-contenu")).to_contain_text("le phare")
    expect(nom).to_have_value("la lampe de poche")
    page.locator("#an-cf-autre").click()
    expect(nom).to_have_value("le phare")
    expect(page.locator("#an-vue-case text.an-vz-lbl", has_text="le phare")).to_have_count(1)
    assert _regions(decor)[d]["nom"] == "le phare"
    # « Remplacer par la mienne », sur un nouveau conflit.
    with _http(decor) as c:
        assert c.put(f"/api/regions/{d}", json={"nom": "la torche"}).status_code == 200
    nom.fill("la lanterne")
    nom.press("Enter")
    expect(page.locator("#an-cf-titre")).to_contain_text("Nom modifié")
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-vue-case text.an-vz-lbl", has_text="la lanterne")).to_have_count(1)
    assert _regions(decor)[d]["nom"] == "la lanterne"


def test_tracer_un_texte_hors_bulle_le_transcrire_puis_l_annoter(page, decor):
    _ouvrir(page, decor)
    avant = set(_regions(decor))
    _glisser(page, 0.1, 0.55, 0.5, 0.7)
    page.locator('#an-trace [data-trace="texte"]').click()
    expect(page.locator("#an-transcription")).to_be_focused()
    t = (set(_regions(decor)) - avant).pop()
    assert _regions(decor)[t]["type"] == "texte" and _regions(decor)[t]["parent_id"] == decor["c1"]
    page.locator("#an-transcription").fill("PSST, PAR ICI")
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(f"/api/regions/{t}")) as rep:
        page.locator("#an-transcription").blur()
    assert rep.value.request.post_data_json == {"ocr_texte": "PSST, PAR ICI",
                                                "vu": {"ocr_texte": None}}
    expect(page.locator("#an-mots")).to_have_text("PSST, PAR ICI")
    assert _regions(decor)[t]["ocr_texte"] == "PSST, PAR ICI"
    # Un texte se transcrit puis s'ANNOTE : ses mots se désignent, le cri s'y pose.
    _mot(page, 0).click()
    with _reponse_de(page, "/api/releves", "POST"):
        page.locator("#an-plan [role=checkbox]", has_text="cri").first.click()
    assert any(r["region_id"] == t and [m["rang"] for m in r["mots"]] == [0]
               for r in _releves(decor))
    # Il a un locuteur, comme toute zone de texte.
    expect(page.locator("#an-loc-input")).to_be_visible()


def test_supprimer_une_zone_tracee_puis_ctrl_z_la_rend(page, decor):
    with _http(decor) as c:
        d = c.post(f"/api/planches/{decor['planche']}/regions",
                   json={"type": "detail", "x": 200, "y": 100, "w": 100, "h": 100,
                         "parent_id": decor["c1"], "nom": "la lampe"}).json()["id"]
    # Une bulle ne se supprime pas d'ici : elle n'est pas tracée par la page.
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-zone-supprimer")).to_be_hidden()
    _ouvrir(page, decor, d)
    bouton = page.locator("#an-zone-supprimer")
    expect(bouton).to_be_visible()
    messages = []
    page.once("dialog", lambda dlg: (messages.append(dlg.message), dlg.dismiss()))
    bouton.click()
    assert messages and "le détail" in messages[0] and "Ctrl+Z" in messages[0]
    assert d in _regions(decor)                                  # refusé : rien ne part
    page.once("dialog", lambda dlg: dlg.accept())
    bouton.click()
    expect(page.locator("#an-tete-zone")).to_have_text("")
    expect(page.locator(f'#an-vue-case rect[data-zone="{d}"]')).to_have_count(0)
    assert d not in _regions(decor)
    page.locator("#an-mots").focus()
    page.keyboard.press("Control+z")
    expect(page.locator("#toasts")).to_contain_text("Annulé :")
    expect(page.locator(f'#an-vue-case rect[data-zone="{d}"]')).to_have_count(1)
    assert _regions(decor)[d]["nom"] == "la lampe"


@pytest.mark.parametrize("live_server", [True], indirect=True)   # proxy déclaré
def test_une_lectrice_ne_trace_rien(page, live_server):
    admin = {"Remote-User": "decor", "Remote-Name": "Decor Admin", "Remote-Groups": "bd-admins"}
    with httpx.Client(base_url=live_server, trust_env=False, timeout=180,
                      headers={**ECRITURE, **admin}) as c:
        cid = c.post("/api/collections", json={"nom": "Étude lue"}).json()["id"]
        du_projet(c, cid, "utilisateur", "lectrice", headers={**ECRITURE, **admin})
        assert c.put(f"/api/collections/{cid}/acces", json={
            "genre": "utilisateur", "principal": "lectrice", "niveau": "lecture"}).status_code == 200
        aid = c.post("/api/albums", json={"titre": "Lu", "collection_id": cid}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(800, 1000), "image/png")}).json()["id"]
        case = c.post(f"/api/planches/{pid}/regions",
                      json={"type": "case", "x": 20, "y": 20, "w": 700, "h": 900}).json()["id"]
        d = c.post(f"/api/planches/{pid}/regions",
                   json={"type": "detail", "x": 60, "y": 60, "w": 200, "h": 120,
                         "parent_id": case, "nom": "la lampe"}).json()["id"]
    page.set_extra_http_headers({"Remote-User": "lectrice"})
    page.goto(f"{live_server}/annotation?album={aid}&planche={pid}&region={d}",
              wait_until="networkidle")
    expect(page.locator("#an-nom-lu")).to_have_text("la lampe", timeout=15000)
    expect(page.locator("#an-nom")).to_be_hidden()
    expect(page.locator("#an-zone-supprimer")).to_be_hidden()
    _glisser(page, 0.5, 0.5, 0.9, 0.9)
    expect(page.locator("#an-trace")).to_be_hidden()
    expect(page.locator("#an-vue-case .an-trace-rect")).to_have_count(0)


# --------------------------------------------------------------------------- #
# Les correctifs de la passe du jalon 3 (commit 14)
# --------------------------------------------------------------------------- #
_RECTS = """() => ['#an-gauche', '#an-zone', '#an-grille', '.an-ctx', '#an-ctx-corps', '#an-guide',
                   '#an-note', '#an-nom', '#an-transcription', '#an-loc-input']
  .map((s) => { const r = document.querySelector(s).getBoundingClientRect();
                return [s, Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })"""
_JETON = """(nom) => { const s = document.createElement('span'); s.style.color = `var(${nom})`;
  document.body.appendChild(s); const v = getComputedStyle(s).color; s.remove(); return v; }"""


def _detail(d, **corps):
    with _http(d) as c:
        return c.post(f"/api/planches/{d['planche']}/regions",
                      json={"type": "detail", "x": 200, "y": 100, "w": 100, "h": 100,
                            "parent_id": d["c1"], **corps}).json()["id"]


def _texte_hors_bulle(d):
    with _http(d) as c:
        t = c.post(f"/api/planches/{d['planche']}/regions",
                   json={"type": "texte", "x": 60, "y": 750, "w": 200, "h": 80,
                         "parent_id": d["c1"]}).json()["id"]
        assert c.put(f"/api/regions/{t}", json={"ocr_texte": "PSST"}).status_code == 200
    return t


def _conflit_de_note(page, d, ailleurs, mienne):
    with _http(d) as c:
        assert c.put(f"/api/regions/{d['bulle']}/annotation",
                     json={"note": ailleurs}).status_code == 200
    page.locator("#an-note").fill(mienne)
    page.locator("#an-note").blur()


def _conflit_de_locuteur(page, d, ailleurs, mienne):
    with _http(d) as c:
        pid = c.post("/api/personnages", json={"nom": ailleurs}).json()["id"]
        c.post("/api/personnages", json={"nom": mienne})
        assert c.put(f"/api/regions/{d['bulle']}/locuteur",
                     json={"personnage_id": pid}).status_code == 200
    page.locator("#an-loc-input").fill(mienne)
    expect(page.locator("#an-loc-liste")).to_contain_text(mienne)
    page.locator("#an-loc-input").press("Enter")


def _conflit_de_nom(page, d, rid, ailleurs, mienne):
    with _http(d) as c:
        assert c.put(f"/api/regions/{rid}", json={"nom": ailleurs}).status_code == 200
    page.locator("#an-nom").fill(mienne)
    page.locator("#an-nom").press("Enter")


def _conflit_de_transcription(page, d, rid, ailleurs, mienne):
    with _http(d) as c:
        assert c.put(f"/api/regions/{rid}", json={"ocr_texte": ailleurs}).status_code == 200
    page.locator("#an-transcription").fill(mienne)
    page.locator("#an-transcription").blur()


def _plus_de_mention(mention, champ):
    if champ == "note":                # sa ligne d'état reste, et passe à autre chose
        expect(mention).not_to_have_text("En attente de votre choix")
    else:
        expect(mention).to_be_hidden()


@pytest.mark.parametrize("champ", ["note", "locuteur", "nom", "transcription"])
def test_un_conflit_du_contexte_se_voit_depuis_le_champ(page, decor, champ):
    """Hugo, sur la passe : le bandeau naît en bas à droite alors qu'on regarde à gauche. Le
    champ prend l'alerte, le bandeau la même couleur, la mention le dit en mots, RIEN ne
    bouge — et la marque part avec le conflit, par les deux réponses."""
    page.set_viewport_size({"width": 1600, "height": 900})
    # Le thème sombre : en clair, `--ink-red` EST l'accent, et l'écart ne se verrait pas.
    page.add_init_script("localStorage.setItem('bd-theme', 'dark')")
    if champ in ("note", "locuteur"):
        region, ligne, saisie = decor["bulle"], f"#an-ctx-{'note' if champ == 'note' else 'loc'}", \
            "#an-note" if champ == "note" else "#an-loc-input"
        provoquer = (lambda a, m: _conflit_de_note(page, decor, a, m)) if champ == "note" \
            else (lambda a, m: _conflit_de_locuteur(page, decor, a, m))
    elif champ == "nom":
        region, ligne, saisie = _detail(decor, nom="la lampe"), "#an-ctx-nom", "#an-nom"
        provoquer = lambda a, m: _conflit_de_nom(page, decor, region, a, m)  # noqa: E731
    else:
        region, ligne, saisie = _texte_hors_bulle(decor), "#an-ctx-tr", "#an-transcription"
        provoquer = lambda a, m: _conflit_de_transcription(page, decor, region, a, m)  # noqa: E731
    _ouvrir(page, decor, region)
    expect(page.locator(saisie)).to_be_enabled()
    expect(page.locator(saisie)).to_be_visible()
    page.wait_for_function("() => !document.querySelector('#an-note').disabled")
    avant = page.evaluate(_RECTS)
    mention = page.locator("#an-note-etat" if champ == "note" else "#an-ctx-attente")

    provoquer("Version A", "Ma version A")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(page.locator(f"{ligne}.an-en-conflit")).to_have_count(1)
    expect(page.locator(".an-en-conflit")).to_have_count(1)
    expect(mention).to_be_visible()
    expect(mention).to_have_text("En attente de votre choix")
    ligne_mention = mention.evaluate("(m) => m.closest('dd').id")
    assert f"#{ligne_mention}" == ligne, "la mention n'est pas sur le champ en conflit"
    if champ == "note":                # sa ligne d'état dit déjà l'attente, une seule fois
        expect(page.locator("#an-ctx-attente")).to_be_hidden()
    alerte = page.evaluate(_JETON, "--ink-red")
    assert page.locator(saisie).evaluate("(c) => getComputedStyle(c).borderTopColor") == alerte
    assert mention.evaluate("(m) => getComputedStyle(m).color") == alerte
    assert page.locator("#an-guide-contenu").evaluate(
        "(c) => getComputedStyle(c).borderLeftColor") == alerte
    assert page.locator("#an-cf-titre").evaluate("(c) => getComputedStyle(c).color") == alerte
    assert page.evaluate(_RECTS) == avant, "le conflit a fait bouger quelque chose"
    # La mention ne recouvre pas le champ ni son libellé.
    m, s = mention.bounding_box(), page.locator(saisie).bounding_box()
    assert m["y"] + m["height"] <= s["y"] + 1 or m["y"] >= s["y"] + s["height"] - 1

    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator(".an-en-conflit")).to_have_count(0)
    _plus_de_mention(mention, champ)

    provoquer("Version B", "Ma version B")
    expect(page.locator(f"{ligne}.an-en-conflit")).to_have_count(1)
    expect(mention).to_have_text("En attente de votre choix")
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator(".an-en-conflit")).to_have_count(0)
    _plus_de_mention(mention, champ)
    assert page.evaluate(_RECTS) == avant


def test_la_marque_d_un_conflit_suit_la_zone_ou_il_attend(page, decor):
    d = _detail(decor, nom="la lampe")
    _ouvrir(page, decor, d)
    expect(page.locator("#an-nom")).to_have_value("la lampe")
    _conflit_de_nom(page, decor, d, "le phare", "la lanterne")
    expect(page.locator("#an-ctx-nom.an-en-conflit")).to_have_count(1)
    page.locator("#an-zones .an-zone-btn", has_text="bulle").click()
    expect(page.locator("#an-tete-zone")).to_have_text(re.compile("bulle"))
    expect(page.locator(".an-en-conflit")).to_have_count(0)
    expect(page.locator("#an-ctx-attente")).to_be_hidden()
    expect(page.locator("#an-cf-titre")).to_be_visible()             # il attend toujours
    page.locator("#an-zones .an-zone-btn", has_text="détail").click()
    expect(page.locator("#an-ctx-nom.an-en-conflit")).to_have_count(1)
    expect(page.locator("#an-ctx-attente")).to_be_visible()
    # La note aussi, sur sa ligne d'état.
    page.locator("#an-cf-autre").click()
    expect(page.locator(".an-en-conflit")).to_have_count(0)
    page.locator("#an-zones .an-zone-btn", has_text="bulle").click()
    expect(page.locator("#an-note")).to_have_value("il jure")
    _conflit_de_note(page, decor, "il crie", "il jure fort")
    expect(page.locator("#an-ctx-note.an-en-conflit")).to_have_count(1)
    page.locator("#an-zones .an-zone-btn", has_text="détail").click()
    expect(page.locator(".an-en-conflit")).to_have_count(0)
    expect(page.locator("#an-note-etat")).not_to_have_text("En attente de votre choix")
    page.locator("#an-zones .an-zone-btn", has_text="bulle").click()
    expect(page.locator("#an-ctx-note.an-en-conflit")).to_have_count(1)
    expect(page.locator("#an-note-etat")).to_have_text("En attente de votre choix")


def test_les_encres_du_conflit_et_la_palette_tiennent_dans_les_quatre_themes(page, decor):
    """axe ne mesure ni un filet de 3 px ni un état qu'il n'a pas vu : l'encre d'alerte (texte,
    4,5:1, sur le panneau et sur la boîte du guide ; bordure, 3:1), et chaque teinte de la
    palette contre le fond du plan et des mots (3:1), dans les quatre thèmes."""
    mesure = """() => {
      const rgb = (c) => c.match(/rgba?\\(([^)]+)\\)/)[1].split(',').map(Number);
      const jeton = (n) => { const s = document.createElement('span'); s.style.color = `var(${n})`;
        document.body.appendChild(s); const v = rgb(getComputedStyle(s).color); s.remove(); return v; };
      const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
        return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const plan = document.querySelector('#an-plan');
      const fondPlan = rgb(getComputedStyle(document.querySelector('#an-grille')).backgroundColor);
      const fondMots = rgb(getComputedStyle(document.querySelector('#an-mots')).backgroundColor);
      const teintes = {};
      for (const c of [0, 1, 2, 3, 4, 5, 6].map((i) => `an-teinte-${i}`).concat('an-trait-autre')) {
        const i = document.createElement('i'); i.className = c; plan.appendChild(i);
        const v = rgb(getComputedStyle(i).backgroundColor); i.remove();
        teintes[c] = Math.min(ratio(v, fondPlan), ratio(v, fondMots));
      }
      const encre = jeton('--ink-red');
      return { teintes, panneau: ratio(encre, jeton('--bg-panel')), guide: ratio(encre, jeton('--bg-deep')),
               champ: ratio(encre, jeton('--bg-panel')) };
    }"""
    echecs = []
    for theme in ("dark", "light"):
        for contraste in ("normal", "high"):
            page.goto(decor["base"] + "/annotation", wait_until="domcontentloaded")
            page.evaluate(f"() => {{ localStorage.setItem('bd-theme', '{theme}'); "
                          f"localStorage.setItem('bd-contrast', '{contraste}'); }}")
            _ouvrir(page, decor, decor["bulle"])
            expect(page.locator("#an-plan .an-rub-filet").first).to_be_visible()
            m = page.evaluate(mesure)
            assert len(m["teintes"]) == 8
            for cle, r in m["teintes"].items():
                if r < 3:
                    echecs.append(f"{theme}/{contraste} {cle} : {r:.2f} (seuil 3)")
            for cle in ("panneau", "guide"):
                if m[cle] < 4.5:
                    echecs.append(f"{theme}/{contraste} encre sur {cle} : {m[cle]:.2f} (seuil 4,5)")
    assert not echecs, "\n".join(echecs)


def _fond(locator):
    return locator.evaluate("(e) => getComputedStyle(e).backgroundColor")


def test_le_plan_porte_la_teinte_de_ses_rubriques_et_de_leurs_releves(page, decor):
    """Hugo : on ne repère pas les parties de la grille. Le filet sur toute la hauteur de la
    rubrique de tête, sous-rubriques comprises, la pastille dans son titre, la teinte des
    relevés — et le nom reste."""
    _poser(decor, region_id=decor["bulle"], entree_cle="origine-du-son", mots=[1])
    _ouvrir(page, decor, decor["bulle"])
    tetes = page.locator("#an-plan .an-rub-tete")
    expect(tetes).to_have_count(5)
    expect(page.locator("#an-plan .an-rub-filet")).to_have_count(5)    # les têtes, seules
    sons = tetes.filter(has_text="A. Sons")
    prov = tetes.filter(has_text="B. Provenance")
    expect(sons.locator(".an-rub-tete")).to_have_count(0)
    expect(sons.locator(".an-rub")).not_to_have_count(0)               # il a des sous-rubriques
    # Le filet couvre la rubrique, sous-rubriques comprises ; le titre garde sa pastille.
    filet = sons.locator("> .an-rub-filet")
    expect(filet).to_be_visible()
    hauteur = sons.evaluate("(s) => s.getBoundingClientRect().height")
    assert abs(filet.bounding_box()["height"] - hauteur) <= 1
    dernier = sons.locator(".an-ent-btn").last.bounding_box()
    assert filet.bounding_box()["y"] + filet.bounding_box()["height"] >= dernier["y"] + dernier["height"] - 1
    # La teinte d'une rubrique est celle de ses traits et de ses pastilles.
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="cri")).to_be_visible()
    trait_cri = page.locator("#an-mots .an-mot .an-trait.an-teinte-0").first
    assert _fond(filet) == _fond(sons.locator(".an-rub-titre .an-pastille")) == _fond(trait_cri)
    pastille_cri = page.locator("#an-poses-liste li", has_text="cri").locator(".an-pastille")
    assert _fond(filet) == _fond(pastille_cri)
    pastille_or = page.locator("#an-poses-liste li", has_text="origine du son").locator(".an-pastille")
    assert _fond(prov.locator("> .an-rub-filet")) == _fond(pastille_or)
    assert _fond(prov.locator("> .an-rub-filet")) != _fond(filet)
    # Le nom reste, et la couleur ne se lit pas au lecteur d'écran.
    expect(sons.locator(".an-rub-titre .an-rub-lib").first).to_have_text("A. Sons")
    expect(sons.locator("> .an-rub-filet")).to_have_attribute("aria-hidden", "true")
    # Repliée, réduite à son titre, elle garde sa couleur.
    prov.locator(".an-rub-btn").click()
    prov = page.locator("#an-plan .an-rub-tete", has_text="B. Provenance")
    expect(prov.locator(".an-rub-btn")).to_have_attribute("aria-expanded", "false")
    expect(prov.locator(".an-rub-titre .an-pastille")).to_be_visible()
    assert _fond(prov.locator(".an-rub-titre .an-pastille")) == _fond(pastille_or)
    # « Afficher » n'en montre qu'une : elle garde son rang dans la grille, donc sa teinte.
    rang_e = _fond(tetes.filter(has_text="E. Image").locator("> .an-rub-filet"))
    page.locator("#an-afficher").select_option(label="E. Image")
    expect(page.locator("#an-plan .an-rub-tete")).to_have_count(1)
    assert _fond(page.locator("#an-plan .an-rub-filet")) == rang_e


def test_porte_sur_et_la_rangee_des_zones_gardent_le_focus_clavier(page, decor):
    """Le bouton est redessiné : retiré du document, il laissait le focus sur `body`, et le
    contour du clavier disparaissait."""
    _ouvrir(page, decor, decor["bulle"])
    actif = "() => [document.activeElement.dataset.porte ?? document.activeElement.dataset.zone ?? " \
            "document.activeElement.tagName, document.activeElement.matches(':focus-visible')]"
    zone = page.locator('#an-porte [data-porte="zone"]')
    page.locator('#an-porte [data-porte="mots"]').focus()
    page.keyboard.press("Tab")                     # le contour du clavier, comme à la main
    for touche in ("Enter", " "):
        expect(zone).to_be_focused()
        page.keyboard.press(touche)
        expect(zone).to_have_attribute("aria-pressed", "true")
        expect(zone).to_be_focused()
        assert page.evaluate(actif) == ["zone", True]
        page.keyboard.press("Shift+Tab")
        page.keyboard.press(touche)
        mots = page.locator('#an-porte [data-porte="mots"]')
        expect(mots).to_have_attribute("aria-pressed", "true")
        expect(mots).to_be_focused()
        assert page.evaluate(actif) == ["mots", True]
        page.keyboard.press("Tab")
    # La rangée des zones : la case, puis la bulle, à Entrée puis à Espace.
    boite = page.locator("#an-zones .an-zone-btn", has_text="personnage")
    bulle = page.locator("#an-zones .an-zone-btn", has_text="bulle")
    bulle.focus()
    page.keyboard.press("Tab")
    expect(boite).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#an-tete-zone")).to_have_text(re.compile("personnage"))
    expect(boite).to_be_focused()
    assert page.evaluate(actif)[1] is True
    page.keyboard.press("Shift+Tab")
    expect(bulle).to_be_focused()
    page.keyboard.press(" ")
    expect(page.locator("#an-tete-zone")).to_have_text(re.compile("bulle"))
    expect(bulle).to_be_focused()
    assert page.evaluate(actif)[1] is True


def test_le_contexte_ne_s_etire_pas_et_une_note_garde_ses_lignes(page, decor):
    """`white-space: pre-line` sur la ligne entière faisait des blancs du gabarit des lignes
    vides (235 px contre 108 sur une bulle). Les retours à la ligne d'une NOTE sont du contenu."""
    with _http(decor) as c:
        c.put(f"/api/regions/{decor['bulle']}/annotation", json={"note": "il jure\npuis se tait"})
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure\npuis se tait")
    # Chaque ligne fait exactement la hauteur de ce qu'elle porte.
    lignes = page.evaluate("""() => ['#an-ctx-loc', '#an-ctx-note'].map((s) => {
      const dd = document.querySelector(s);
      const vus = [...dd.children].filter((e) => e.getBoundingClientRect().height > 0);
      const haut = Math.min(...vus.map((e) => e.getBoundingClientRect().top));
      const bas = Math.max(...vus.map((e) => e.getBoundingClientRect().bottom));
      return [s, dd.getBoundingClientRect().height, bas - haut]; })""")
    for s, hauteur, contenu in lignes:
        assert abs(hauteur - contenu) <= 1, f"{s} : {hauteur} px pour {contenu} px de contenu"
    # Un retour à la ligne se lit, en écriture comme en lecture.
    page.route(re.compile(r"/api/albums(\?.*)?$"), lambda route: route.fulfill(
        response=(r := route.fetch()),
        json=[{**a, "ecrivable": False} for a in r.json()]))
    _ouvrir(page, decor, decor["bulle"])
    lu = page.locator("#an-note-lu")
    expect(lu).to_be_visible()
    expect(lu).to_have_text(re.compile("il jure"))
    assert lu.evaluate("(e) => e.innerText") == "il jure\npuis se tait"


def _atelier_sur(page, d, region):
    page.goto(f"{d['base']}/?album={d['album']}&planche={d['planche']}&region={region}",
              wait_until="networkidle")
    expect(page.locator("#region-type")).to_be_visible(timeout=15000)


def test_un_type_refuse_revient_au_type_de_la_region(page, decor):
    """Passe du jalon 3 : la case qui porte un détail ne change pas de type, et la liste
    restait sur le type refusé, à l'écran d'une région qui ne l'avait pas pris."""
    _detail(decor)
    _atelier_sur(page, decor, decor["c1"])
    sel = page.locator("#region-type")
    expect(sel).to_have_value("case")
    with page.expect_response(lambda r: r.request.method == "PUT"
                              and r.url.endswith(f"/api/regions/{decor['c1']}")) as rep:
        sel.select_option("bulle")
    assert rep.value.status == 422
    expect(page.locator("#toasts")).to_contain_text("Échec mise à jour")
    expect(sel).to_have_value("case")
    assert _regions(decor)[decor["c1"]]["type"] == "case"


def test_un_rattachement_ou_des_coordonnees_refuses_reviennent_aussi(page, decor):
    """Les autres champs du même chemin ; le serveur n'a pas de refus à portée de ces gestes
    sur ce décor, on lui en fait dire un."""
    _atelier_sur(page, decor, decor["bulle"])
    page.route(re.compile(rf"/api/regions/{decor['bulle']}$"), lambda route: route.fulfill(
        status=422, content_type="application/json", body='{"detail": "Refusé pour le test."}'))
    parent = page.locator("#region-parent")
    expect(parent).to_have_value(str(decor["c1"]))
    parent.select_option("")
    expect(page.locator("#toasts")).to_contain_text("Refusé pour le test.")
    expect(parent).to_have_value(str(decor["c1"]))
    page.click('.mode-btn[data-mode="edition"]')
    w = page.locator("#coord-w")
    expect(w).to_have_value("200")
    w.fill("999")
    w.blur()
    expect(w).to_have_value("200")
    # Un autre champ à moitié écrit ne bouge pas : seul le panneau de la région revient.
    expect(page.locator("#region-type")).to_have_value("bulle")


def test_l_arbre_de_l_atelier_ecrit_detail_avec_son_accent(page, decor):
    d = _detail(decor, nom="la lampe")
    _atelier_sur(page, decor, d)
    expect(page.locator(".tnode-detail .tn-label")).to_have_text("détail")
    assert page.locator(".tnode-detail .tn-label").inner_text() == "Détail"     # la capitale du CSS
    # Les valeurs ne changent pas : le serveur lit toujours « detail ».
    expect(page.locator("#region-type")).to_have_value("detail")
    assert _regions(decor)[d]["type"] == "detail"


# --------------------------------------------------------------------------- #
# Tranche 2, commit 15 — une saisie en conflit survit, et le focus reste où l'on agit
# --------------------------------------------------------------------------- #
def _zone(page, texte):
    page.locator("#an-zones .an-zone-btn", has_text=texte).click()
    expect(page.locator("#an-tete-zone")).to_contain_text(texte)


def _lire_note(d, rid):
    with _http(d) as c:
        return c.get(f"/api/regions/{rid}/annotation").json()["note"]


def _reponse_de(page, chemin, methode="PUT"):
    """Le geste rendu à sa RÉPONSE. Ce que le bandeau, le champ ou la base disent juste après un
    clic n'en dit rien : le bandeau se ferme au clic, avant que le serveur ait écrit, et
    `wait_for_load_state("networkidle")` rend tout de suite sur une page déjà chargée. Un test
    qui lisait la base derrière lui gagnait sa course sur le poste et la perdait dans l'image :
    quinze rouges, reproduits sur le poste en retardant le serveur. `chemin` : la fin de
    l'adresse, ou `RELEVE` pour une écriture de relevé."""
    return page.expect_response(lambda r: r.request.method == methode
                                and (r.url.endswith(chemin) if chemin is not RELEVE
                                     else "/api/releves/" in r.url))


RELEVE = object()


def _retenir_les_envois(page, motif, methode="PUT"):
    """Retient les écritures vers `motif` jusqu'à `lacher()` ; les lectures passent, et les
    écritures d'après aussi."""
    retenues, actif = [], [True]

    def gerer(route):
        if actif[0] and route.request.method == methode:
            retenues.append(route)
        else:
            route.continue_()

    def lacher():
        actif[0] = False
        retenues[0].continue_()

    page.route(motif, gerer)
    return retenues, lacher


def _attendre_retenue(page, retenues):
    for _ in range(50):
        if retenues:
            return
        page.wait_for_timeout(100)
    assert retenues


def _prepare_conflit(page, d, champ):
    """Ouvre `champ` et son conflit. Rend ce que chaque test en lit : le champ, sa zone, et de
    quoi lire la base."""
    if champ == "note":
        rid, zone, sel, autre_zone = d["bulle"], "bulle", "#an-note", "personnage"
        _ouvrir(page, d, rid)
        expect(page.locator(sel)).to_have_value("il jure")
        _conflit_de_note(page, d, "Version autre", "Ma version")
        lire = lambda: _lire_note(d, rid)  # noqa: E731
        chemin, cle = f"/regions/{rid}/annotation", "note"
    elif champ == "nom":
        rid, zone, sel, autre_zone = _detail(d, nom="la lampe"), "détail", "#an-nom", "bulle"
        _ouvrir(page, d, rid)
        expect(page.locator(sel)).to_have_value("la lampe")
        _conflit_de_nom(page, d, rid, "Version autre", "Ma version")
        lire = lambda: _regions(d)[rid]["nom"]  # noqa: E731
        chemin, cle = f"/regions/{rid}", "nom"
    else:
        rid, zone, sel, autre_zone = _texte_hors_bulle(d), "texte", "#an-transcription", "bulle"
        _ouvrir(page, d, rid)
        expect(page.locator(sel)).to_have_value("PSST")
        _conflit_de_transcription(page, d, rid, "Version autre", "Ma version")
        lire = lambda: _regions(d)[rid]["ocr_texte"]  # noqa: E731
        chemin, cle = f"/regions/{rid}", "ocr_texte"
    expect(page.locator("#an-cf-titre")).to_be_visible()
    return {"champ": champ, "rid": rid, "zone": zone, "sel": sel, "autre": autre_zone,
            "lire": lire, "chemin": chemin, "cle": cle}


def _part_en(page, cf, attendu):
    """« Remplacer par la mienne » : mesure LA requête partie, avec la valeur vue."""
    with _reponse_de(page, cf["chemin"]) as q:
        page.locator("#an-cf-mienne").click()
    corps = q.value.request.post_data_json
    assert corps[cf["cle"]] == attendu
    assert (corps["note_vue"] if cf["champ"] == "note" else corps["vu"][cf["cle"]]) == "Version autre"
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert cf["lire"]() == attendu


@pytest.mark.parametrize("champ", ["note", "nom", "transcription"])
@pytest.mark.parametrize("retouche", [False, True], ids=["telle-quelle", "retouchee"])
def test_une_saisie_en_conflit_survit_a_un_aller_retour(page, decor, champ, retouche):
    """Conflit ouvert, on change de zone, on revient : le champ montre MA saisie — la dernière,
    retouchée après le 409 s'il le faut —, et « Remplacer par la mienne » l'écrit. Le champ
    repartait sur la version de l'autre (ou l'ancienne), et le bouton n'écrivait rien de neuf."""
    cf = _prepare_conflit(page, decor, champ)
    mienne = "Ma version"
    if retouche:
        mienne = "Ma version, retouchée"
        page.locator(cf["sel"]).fill(mienne)
    _zone(page, cf["autre"])
    _zone(page, cf["zone"])
    expect(page.locator(cf["sel"])).to_have_value(mienne)
    expect(page.locator(".an-en-conflit")).to_have_count(1)
    _part_en(page, cf, mienne)
    expect(page.locator(cf["sel"])).to_have_value(mienne)


@pytest.mark.parametrize("champ", ["note", "nom", "transcription"])
def test_une_saisie_en_conflit_part_aussi_depuis_une_autre_zone(page, decor, champ):
    """Le bandeau reste ouvert d'une zone à l'autre : y répondre d'ailleurs écrit la saisie
    retouchée, pas celle du premier refus."""
    cf = _prepare_conflit(page, decor, champ)
    page.locator(cf["sel"]).fill("Ma version, retouchée")
    _zone(page, cf["autre"])
    _part_en(page, cf, "Ma version, retouchée")


@pytest.mark.parametrize("champ", ["note", "nom", "transcription"])
def test_garder_l_autre_jette_la_saisie_apres_un_aller_retour(page, decor, champ):
    cf = _prepare_conflit(page, decor, champ)
    _zone(page, cf["autre"])
    _zone(page, cf["zone"])
    envois = []
    page.on("request", lambda r: envois.append(r.url) if r.method == "PUT" else None)
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator(cf["sel"])).to_have_value("Version autre")
    page.locator(cf["sel"]).blur()
    page.wait_for_timeout(700)
    assert envois == []
    assert cf["lire"]() == "Version autre"


def test_un_choix_de_locuteur_en_conflit_survit_et_declare_la_version_vue(page, decor):
    """Le choix vit dans le conflit. Répondu DEPUIS UNE AUTRE ZONE, il déclare quand même ce
    que le bandeau a montré : sans quoi un troisième serait écrasé sans le dire."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    _conflit_de_locuteur(page, decor, "Zed", "Yann")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    with _http(decor) as c:
        zed = c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["id"]
    _zone(page, "personnage")
    with _reponse_de(page, "/locuteur") as q:
        page.locator("#an-cf-mienne").click()
    assert q.value.request.post_data_json["personnage_vu"] == zed
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["nom"] == "Yann"
    # Retour sur la zone, un autre conflit : le choix survit de même.
    _zone(page, "bulle")
    expect(page.locator("#an-loc-nom")).to_have_text("Yann")
    _conflit_de_locuteur(page, decor, "Xavier", "Willy")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    _zone(page, "personnage")
    _zone(page, "bulle")
    expect(page.locator("#an-loc-nom")).to_have_text("Xavier")
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(page.locator("#an-loc-nom")).to_have_text("Willy")
    with _http(decor) as c:
        assert c.get(f"/api/regions/{decor['bulle']}/locuteur").json()["locuteur"]["nom"] == "Willy"


def test_une_autre_planche_attend_le_conflit_meme_depuis_une_autre_zone(page, decor):
    with httpx.Client(base_url=decor["base"], trust_env=False, timeout=180,
                      headers=ECRITURE) as c:
        p2 = c.post(f"/api/albums/{decor['album']}/import",
                    files={"file": ("p2.png", make_png(800, 1000), "image/png")}).json()["id"]
    cf = _prepare_conflit(page, decor, "nom")
    page.locator(cf["sel"]).fill("Ma version, retouchée")
    _zone(page, "bulle")
    page.locator("#an-planche-choix").select_option(str(p2))
    expect(page.locator("#an-cf-mienne")).to_be_focused()
    expect(page.locator("#an-planche-choix")).to_have_value(str(decor["planche"]))
    _zone(page, "détail")
    expect(page.locator(cf["sel"])).to_have_value("Ma version, retouchée")
    _part_en(page, cf, "Ma version, retouchée")


@pytest.mark.parametrize("champ", ["note", "nom", "transcription"])
def test_actualiser_ne_perd_rien_d_une_saisie_en_conflit(page, decor, champ):
    cf = _prepare_conflit(page, decor, champ)
    page.locator(cf["sel"]).fill("Ma version, retouchée")
    _poser(decor, region_id=decor["c2"], entree_cle="regard-camera")
    _retour_sur_l_onglet(page)
    bouton = page.locator("#an-actualiser")
    expect(bouton).to_be_visible()
    bouton.click()
    expect(page.locator("#an-cf-mienne")).to_be_focused()
    expect(page.locator(cf["sel"])).to_have_value("Ma version, retouchée")
    _part_en(page, cf, "Ma version, retouchée")


@pytest.mark.parametrize("champ", ["note", "nom", "transcription"])
def test_une_saisie_retenue_par_un_autre_conflit_survit_et_part(page, decor, champ):
    """Un AUTRE conflit attend (sur le locuteur de la bulle) : le champ ne part pas. Changer de
    zone l'effaçait sans un mot ; il revient au retour, et part quand le conflit est réglé."""
    if champ == "note":
        rid, sel, zone = decor["boite"], "#an-note", "personnage"
        lire, chemin = (lambda: _lire_note(decor, rid)), f"/regions/{rid}/annotation"  # noqa: E731
    elif champ == "nom":
        rid, sel, zone = _detail(decor, nom="la lampe"), "#an-nom", "détail"
        lire, chemin = (lambda: _regions(decor)[rid]["nom"]), f"/regions/{rid}"  # noqa: E731
    else:
        rid, sel, zone = _texte_hors_bulle(decor), "#an-transcription", "texte"
        lire, chemin = (lambda: _regions(decor)[rid]["ocr_texte"]), f"/regions/{rid}"  # noqa: E731
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    _conflit_de_locuteur(page, decor, "Zed", "Yann")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    _zone(page, zone)
    page.locator(sel).fill("Ma saisie")
    page.locator(sel).blur()
    _zone(page, "bulle")
    _zone(page, zone)
    expect(page.locator(sel)).to_have_value("Ma saisie")
    with _reponse_de(page, chemin):
        page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert lire() == "Ma saisie"


def test_un_refus_arrive_apres_le_depart_de_la_zone_ouvre_le_bandeau(page, decor):
    """La note part à la sortie du champ, et le 409 revient quand on est déjà ailleurs : un
    toast disait « la vôtre n'a pas été enregistrée », et le texte était perdu. Le conflit
    s'ouvre, sans prendre le focus de ce qu'on fait maintenant, et la note attend sur sa zone."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "Version autre"}).status_code == 200
    retenues, lacher = _retenir_les_envois(page, "**/api/regions/*/annotation")
    page.locator("#an-note").fill("Ma version")
    bouton = page.locator("#an-zones .an-zone-btn", has_text="personnage")
    bouton.click()
    expect(page.locator("#an-tete-zone")).to_contain_text("personnage")
    assert len(retenues) == 1
    lacher()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(page.locator("#an-guide-contenu")).to_contain_text("bulle b1")
    expect(bouton).to_be_focused()
    expect(page.locator(".an-en-conflit")).to_have_count(0)
    _zone(page, "bulle")
    expect(page.locator("#an-note")).to_have_value("Ma version")
    expect(page.locator("#an-ctx-note.an-en-conflit")).to_have_count(1)
    with _reponse_de(page, "/annotation"):
        page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _lire_note(decor, decor["bulle"]) == "Ma version"


def test_un_refus_revenu_sur_la_meme_zone_rend_la_saisie_au_champ(page, decor):
    """Un clic sur la zone où l'on est relit le Contexte pendant que la note est en vol : le
    champ reprenait la version de l'autre sous le bandeau qui promet « elle reste »."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "Version autre"}).status_code == 200
    retenues, lacher = _retenir_les_envois(page, "**/api/regions/*/annotation")
    page.locator("#an-note").fill("Ma version")
    page.locator("#an-zones .an-zone-btn", has_text="bulle").click()
    _attendre_retenue(page, retenues)
    assert len(retenues) == 1
    lacher()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(page.locator("#an-note")).to_have_value("Ma version")
    with _reponse_de(page, "/annotation"):
        page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _lire_note(decor, decor["bulle"]) == "Ma version"


def test_une_note_sur_une_zone_supprimee_ailleurs_se_dit_avec_son_texte(page, decor):
    """« Remplacer par la mienne » sur une zone supprimée entre-temps : il n'y a plus où
    l'écrire, et le message rend le texte, comme pour un doute dont le relevé a été retiré."""
    t = _texte_hors_bulle(decor)
    _ouvrir(page, decor, t)
    expect(page.locator("#an-transcription")).to_have_value("PSST")
    with _http(decor) as c:
        assert c.put(f"/api/regions/{t}/annotation", json={"note": "Version autre"}).status_code == 200
    page.locator("#an-note").fill("Ma note perdue")
    page.locator("#an-note").blur()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    with _http(decor) as c:
        assert c.delete(f"/api/regions/{t}").status_code in (200, 204)
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#toasts")).to_contain_text("Ma note perdue")


# Le focus au clavier. Le contour se lit : `:focus-visible` et un trait réel, à Entrée comme à
# Espace ; une souris n'en gagne pas.
_CONTOUR = """() => { const a = document.activeElement; const s = getComputedStyle(a);
  return { tag: a.tagName, visible: a.matches(':focus-visible'),
           trait: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 }; }"""


def _au_clavier(page, cible):
    """Le focus arrive sur `cible` par une touche, comme à la main : c'est ce qui donne le
    contour du clavier."""
    cible.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(cible).to_be_focused()


def _focus_tenu(page, cible):
    expect(cible).to_be_focused()
    expect(cible).to_be_focused()
    c = page.evaluate(_CONTOUR)
    assert c["visible"] and c["trait"], c


TOUCHES = pytest.mark.parametrize("touche", ["Enter", " "], ids=["entree", "espace"])


@TOUCHES
def test_poser_au_clavier_garde_le_focus_sur_l_entree_ou_la_variante(page, decor, touche):
    """Le geste principal au clavier : l'entrée redessinée garde le contour, et l'on enchaîne
    sans repartir du haut de la page."""
    _ouvrir(page, decor, decor["c2"])
    regard = page.locator("#an-ent-regard-camera")
    _au_clavier(page, regard)
    page.keyboard.press(touche)
    expect(regard).to_have_attribute("aria-checked", "true")
    _focus_tenu(page, regard)
    page.keyboard.press(touche)
    expect(regard).to_have_attribute("aria-checked", "false")
    _focus_tenu(page, regard)
    # Une variante, sur la bulle ; puis sa voisine, par Tab, sans revenir au début.
    page.locator('#an-zones .an-zone-btn', has_text="La case").first.click()
    _ouvrir(page, decor, decor["bulle"])
    crie = page.locator("#an-plan .an-var", has_text="crié")
    _au_clavier(page, crie)
    page.keyboard.press(touche)
    expect(crie).to_have_attribute("aria-pressed", "true")
    _focus_tenu(page, crie)
    page.keyboard.press("Tab")
    assert page.evaluate("() => !!document.activeElement.closest('#an-plan')")
    chuchote = page.locator("#an-plan .an-var", has_text="chuchoté")
    _au_clavier(page, chuchote)
    page.keyboard.press(touche)
    expect(chuchote).to_have_attribute("aria-pressed", "true")
    _focus_tenu(page, chuchote)
    # Un qualificatif, sur un mot désigné.
    _mot(page, 1).click()
    objet = page.locator("#an-plan .an-ent", has=page.locator("text=origine du son")) \
        .locator(".an-var", has_text="objet")
    _au_clavier(page, objet)
    page.keyboard.press(touche)
    expect(objet).to_have_attribute("aria-pressed", "true")
    _focus_tenu(page, objet)


def test_un_clic_sur_le_signe_du_filtre_donne_le_focus_au_filtre(page, decor):
    _ouvrir(page, decor, decor["c2"])
    page.locator(".an-filtre-wrap kbd").click()
    expect(page.locator("#an-filtre")).to_be_focused()


def test_le_focus_ne_quitte_pas_le_filtre_ni_un_champ_qu_on_vient_de_remplir(page, decor):
    _ouvrir(page, decor, decor["c2"])
    page.keyboard.press("/")
    filtre = page.locator("#an-filtre")
    expect(filtre).to_be_focused()
    filtre.fill("regard")
    expect(page.locator("#an-resultats .an-res").first).to_be_visible()
    page.keyboard.press("Enter")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="regard caméra")).to_have_count(1)
    expect(filtre).to_be_focused()
    filtre.fill("")
    # Une pose dont la réponse revient quand on écrit déjà la note : le redessin n'y touche pas.
    retenues, lacher = _retenir_les_envois(page, "**/api/releves", "POST")
    entree = page.locator("#an-plan .an-var", has_text="crié")
    _ouvrir(page, decor, decor["bulle"])
    entree.click()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues
    note = page.locator("#an-note")
    note.focus()
    note.fill("il jure encore")
    lacher()
    expect(entree).to_have_attribute("aria-pressed", "true")
    expect(note).to_be_focused()


def test_la_souris_ne_gagne_pas_de_contour(page, decor):
    _poser(decor, region_id=decor["c2"], entree_cle="regard-camera")
    _ouvrir(page, decor, decor["bulle"])
    crie = page.locator("#an-plan .an-var", has_text="crié")
    crie.click()
    expect(crie).to_have_attribute("aria-pressed", "true")
    assert page.evaluate(_CONTOUR)["visible"] is False
    page.locator('#an-porte [data-porte="zone"]').click()
    assert page.evaluate(_CONTOUR)["visible"] is False
    _synthese(page, "releves")
    page.locator('#an-syn-corps [data-syn-case="1"]').click()
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    assert page.evaluate(_CONTOUR)["visible"] is False


def _deuxieme_grille(d, nom="Lexique"):
    with _http(d) as c:
        return grille_active_vivante(c, nom=nom, projet_id=d["projet"])["grille_id"]


@TOUCHES
def test_un_onglet_de_grille_non_ouvert_garde_le_focus(page, decor, touche):
    _deuxieme_grille(decor)
    _ouvrir(page, decor, decor["bulle"])
    fermee = page.locator('#an-onglets [aria-selected="false"]').get_attribute("data-grille")
    onglet = page.locator(f"#an-onglet-{fermee}")
    _au_clavier(page, page.locator('#an-onglets [aria-selected="true"]'))
    onglet.focus()                                 # tabindex="-1" : un non-ouvert n'a pas de Tab
    page.keyboard.press(touche)
    expect(onglet).to_have_attribute("aria-selected", "true")
    _focus_tenu(page, onglet)
    # « Aussi dans » disparaît avec son geste : le focus revient au filtre.
    page.locator("#an-filtre").fill("cri")
    aussi = page.locator("#an-ailleurs [data-grille]")
    expect(aussi).to_be_visible()
    _au_clavier(page, aussi)
    page.keyboard.press(touche)
    _focus_tenu(page, page.locator("#an-filtre"))


@TOUCHES
def test_les_cases_de_releves_gardent_le_focus(page, decor, touche):
    _deuxieme_grille(decor)
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-releves-btn").click()
    autre = page.locator("#an-releves-pop [data-voir]:not([disabled])").get_attribute("data-voir")
    case = page.locator(f'#an-releves-pop [data-voir="{autre}"]')
    expect(case).to_be_visible()
    _au_clavier(page, case)
    page.keyboard.press(" ")
    expect(case).to_be_checked()
    _focus_tenu(page, case)
    page.keyboard.press(" ")
    expect(case).not_to_be_checked()
    _focus_tenu(page, case)
    # Les deux boutons du panneau.
    toutes = page.locator("#an-releves-pop [data-voir-tout]")
    _au_clavier(page, toutes)
    page.keyboard.press(touche)
    expect(case).to_be_checked()
    _focus_tenu(page, toutes)
    seule = page.locator("#an-releves-pop [data-voir-seule]")
    _au_clavier(page, seule)
    page.keyboard.press(touche)
    expect(case).not_to_be_checked()
    _focus_tenu(page, seule)


@TOUCHES
def test_les_boutons_de_la_synthese_gardent_le_focus(page, decor, touche):
    regard = _poser(decor, region_id=decor["c2"], entree_cle="regard-camera")
    _ouvrir(page, decor, decor["bulle"])
    _synthese(page, "releves")
    corps = page.locator("#an-syn-corps")
    # « Case c2 · 1 » : le geste change de zone, et le bouton reste là, marqué courant.
    c2 = corps.locator('[data-syn-case="1"]')
    _au_clavier(page, c2)
    page.keyboard.press(touche)
    expect(page.locator("#an-tete-case")).to_have_text("Case c2")
    expect(c2).to_have_attribute("aria-current", "true")
    _focus_tenu(page, c2)
    # Une ligne : elle ouvre son relevé, et reste.
    ligne = corps.locator(f'[data-syn-releve="{_cri(decor)["id"]}"]')
    _au_clavier(page, ligne)
    page.keyboard.press(touche)
    expect(page.locator("#an-tete-zone")).to_have_text("bulle b1")
    _focus_tenu(page, ligne)
    assert regard
    # Le Décompte : « cette zone », « la planche ».
    page.locator('#an-syn-vues [data-syn="decompte"]').click()
    zone = corps.locator('[data-portee="zone"]')
    _au_clavier(page, zone)
    page.keyboard.press(touche)
    expect(zone).to_have_attribute("aria-pressed", "true")
    _focus_tenu(page, zone)


@TOUCHES
def test_un_bouton_qui_disparait_avec_son_geste_rend_le_focus_a_cote(page, decor, touche):
    r = _poser(decor, region_id=decor["bulle"], entree_cle="ton-de-voix", variante_cle="crie")
    _douter_api(decor, r["id"], "crié ?")
    _ouvrir(page, decor, decor["bulle"])
    # « Changer… » reste, et ses variantes aussi.
    _synthese(page, "revoir")
    corps = page.locator("#an-syn-corps")
    changer = corps.locator(f'[data-changer="{r["id"]}"]')
    _au_clavier(page, changer)
    page.keyboard.press(touche)
    expect(changer).to_have_attribute("aria-pressed", "true")
    _focus_tenu(page, changer)
    # « Garder » lève le doute : son bouton part, le focus va au bouton de la vue.
    garder = corps.locator(f'[data-lever="garde"][data-pour="{r["id"]}"]')
    _au_clavier(page, garder)
    page.keyboard.press(touche)
    expect(garder).to_have_count(0)
    _focus_tenu(page, page.locator('#an-syn-vues [data-syn="revoir"]'))
    # ✕ dans la liste : le suivant de la liste, sinon « Relevés ▾ ».
    page.locator("#an-ong-planche").click()
    _ouvrir(page, decor, decor["bulle"])
    retirer = page.locator(f'#an-poses-liste [data-retirer="{r["id"]}"]')
    _au_clavier(page, retirer)
    page.keyboard.press(touche)
    expect(retirer).to_have_count(0)
    _focus_tenu(page, page.locator("#an-poses-liste [data-retirer]").first)
    page.keyboard.press(touche)
    expect(page.locator("#an-poses-liste [data-retirer]")).to_have_count(0)
    _focus_tenu(page, page.locator("#an-releves-btn"))


@TOUCHES
def test_les_gestes_d_une_ligne_de_ce_qui_est_pose_gardent_le_focus(page, decor, touche):
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, 1).click()
    origine = page.locator("#an-plan .an-ent", has=page.locator("text=origine du son"))
    origine.locator(".an-var", has_text="objet").click()
    expect(page.locator("#an-poses-liste .an-prec")).to_be_visible()
    r = [x for x in _releves(decor) if x["entree_cle"] == "origine-du-son"][0]
    # La précision : Entrée l'enregistre, et le champ reste, avec son texte.
    champ = page.locator("#an-poses-liste .an-prec")
    _au_clavier(page, champ)
    page.keyboard.type("le salon")
    page.keyboard.press("Enter")
    expect(page.locator("#an-poses-liste .an-pose-lib", has_text="« le salon »")).to_have_count(1)
    _focus_tenu(page, champ)
    expect(champ).to_have_value("le salon")
    # La ligne elle-même.
    ligne = page.locator(f'#an-poses-liste .an-pose-btn[data-releve="{r["id"]}"]')
    _au_clavier(page, ligne)
    page.keyboard.press(touche)
    _focus_tenu(page, ligne)


@TOUCHES
def test_repondre_a_un_conflit_de_valeur_rend_le_focus_a_son_entree(page, decor, touche):
    with _http(decor) as c:
        r = c.post("/api/releves", json={"region_id": decor["bulle"], "grille_id": decor["grille"],
                                         "version": 1, "entree_cle": "ton-de-voix",
                                         "variante_cle": "crie"}).json()
    _ouvrir(page, decor, decor["bulle"])
    with _http(decor) as c:
        assert c.put(f"/api/releves/{r['id']}", json={"variante_cle": "chuchote"}).status_code == 200
    crie = page.locator("#an-plan .an-var", has_text="crié")
    _au_clavier(page, crie)
    page.keyboard.press(touche)                    # le retrait, refusé
    autre = page.locator("#an-cf-autre")
    expect(autre).to_be_visible()
    expect(page.locator("#an-cf-mienne")).to_be_focused()
    page.keyboard.press("Tab")
    expect(autre).to_be_focused()
    page.keyboard.press(touche)
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    _focus_tenu(page, page.locator("#an-ent-ton-de-voix"))


@TOUCHES
def test_un_conflit_du_contexte_repondu_d_ailleurs_rend_le_focus_a_la_zone(page, decor, touche):
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    _conflit_de_note(page, decor, "il crie", "il jure fort")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    _zone(page, "personnage")
    autre = page.locator("#an-cf-autre")
    _au_clavier(page, autre)
    page.keyboard.press(touche)
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    _focus_tenu(page, page.locator("#an-zones .an-zone-btn", has_text="personnage"))


@TOUCHES
def test_actualiser_au_clavier_rend_le_focus_a_la_zone(page, decor, touche):
    _ouvrir(page, decor, decor["bulle"])
    _poser(decor, region_id=decor["c2"], entree_cle="regard-camera")
    _retour_sur_l_onglet(page)
    bouton = page.locator("#an-actualiser")
    expect(bouton).to_be_visible()
    _au_clavier(page, bouton)
    page.keyboard.press(touche)
    expect(bouton).to_be_hidden()
    _focus_tenu(page, page.locator("#an-zones .an-zone-btn", has_text="bulle"))


def test_ctrl_entree_d_un_champ_qui_disparait_rend_le_focus_a_la_zone(page, decor):
    """Le locuteur n'existe pas sur une boîte : Ctrl+Entrée depuis son champ mène à une zone où
    il se cache, et le focus tombait."""
    _ouvrir(page, decor, decor["bulle"])
    _au_clavier(page, page.locator("#an-loc-input"))
    page.keyboard.press("Control+Enter")
    expect(page.locator("#an-tete-zone")).not_to_have_text("bulle b1")
    expect(page.locator("#an-loc-input")).to_be_hidden()
    assert page.evaluate("() => document.activeElement.tagName") != "BODY"
    # Les mots de la bulle : leur boîte cesse d'être focalisable le temps de lire les suivants.
    _ouvrir(page, decor, decor["bulle"])
    expect(_mot(page, 2)).to_be_visible()
    _au_clavier(page, page.locator("#an-mots"))
    page.keyboard.press("Control+Enter")
    expect(page.locator("#an-tete-zone")).not_to_have_text("bulle b1")
    assert page.evaluate("() => document.activeElement.tagName") != "BODY"


def test_un_trace_au_clavier_rend_le_focus_a_son_bouton(page, decor):
    _ouvrir(page, decor, decor["c2"])
    tracer = page.locator("#an-tracer")
    # Annuler, puis Échap, une fois la sorte proposée : les boutons partent avec le choix.
    for geste in ("annuler", "echap"):
        _au_clavier(page, tracer)
        page.keyboard.press("Enter")
        expect(page.locator("#an-vue-case")).to_be_focused()
        page.keyboard.press("Enter")
        sorte = page.locator('#an-trace [data-trace="detail"]')
        expect(sorte).to_be_focused()
        if geste == "annuler":
            page.locator('#an-trace [data-trace=""]').focus()
            page.keyboard.press("Enter")
        else:
            page.keyboard.press("Escape")
        expect(page.locator("#an-trace")).to_be_hidden()
        _focus_tenu(page, tracer)


def test_supprimer_une_zone_au_clavier_rend_le_focus_a_la_case(page, decor):
    t = _texte_hors_bulle(decor)
    _ouvrir(page, decor, t)
    page.on("dialog", lambda d: d.accept())
    bouton = page.locator("#an-zone-supprimer")
    expect(bouton).to_be_visible()
    _au_clavier(page, bouton)
    page.keyboard.press("Enter")
    expect(page.locator("#an-tete-zone")).to_have_text("")
    _focus_tenu(page, page.locator('#an-zones .an-zone-btn[aria-pressed="true"]'))


def test_terminee_sur_la_derniere_zone_garde_le_focus_dans_le_pied(page, decor):
    """« Terminée, suivante » s'éteint quand il n'y a plus de suivante à marquer : le bouton
    éteint perdait le focus."""
    _ouvrir(page, decor, decor["bulle"])
    page.locator("#an-parcours-sel").select_option("afaire")
    fin = page.locator("#an-terminee-suiv")
    total = 0
    _au_clavier(page, fin)
    annonce = page.locator("#an-annonce")
    while total < 12 and fin.is_enabled():
        total += 1
        avant = annonce.text_content()
        page.keyboard.press("Enter")
        expect(annonce).not_to_have_text(avant)    # la réponse est là, la zone a suivi
        tag = page.evaluate("() => document.activeElement.tagName")
        assert tag != "BODY", f"focus perdu au passage {total}"
    assert total
    _focus_tenu(page, page.locator("#an-pied :focus"))


def test_la_minicarte_garde_son_focus_a_ctrl_z(page, decor):
    """Ctrl+Z relit la planche, et la minicarte se redessine sous le focus."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    page.locator("#an-note").fill("il jure, puis non")
    with page.expect_response(lambda r: r.url.endswith("/annotation") and r.request.method == "PUT"):
        page.locator("#an-note").blur()
    expect(page.locator("#an-note-etat")).to_have_text("Enregistrée")
    case = page.locator('#an-mini .an-mz[data-case="1"]')
    _au_clavier(page, case)
    page.keyboard.press("Control+z")
    expect(page.locator("#toasts")).to_contain_text("Annulé :")
    expect(page.locator("#an-note")).to_have_value("il jure")
    expect(case).to_be_focused()


def _detail_ouvert(page, d):
    rid = _detail(d, nom="la lampe")
    _ouvrir(page, d, rid)
    expect(page.locator("#an-nom")).to_have_value("la lampe")
    return rid


@pytest.mark.parametrize("doigts", ["sous-les-doigts", "champ-quitte"])
def test_un_nom_retouche_pendant_l_aller_retour_est_ce_qui_attend(page, decor, doigts):
    """Le 409 revient sur un champ retouché entre-temps : c'est la dernière version qui attend.
    Champ quitté, elle part derrière le premier envoi, trouve le bandeau ouvert, et s'arrêtait là."""
    rid = _detail_ouvert(page, decor)
    with _http(decor) as c:
        assert c.put(f"/api/regions/{rid}", json={"nom": "Version autre"}).status_code == 200
    retenues, lacher = _retenir_les_envois(page, f"**/api/regions/{rid}")
    nom = page.locator("#an-nom")
    nom.fill("Première")
    nom.press("Enter")
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues
    nom.fill("Seconde")
    if doigts == "champ-quitte":
        page.locator("#an-filtre").focus()
        page.wait_for_timeout(100)
    lacher()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(nom).to_have_value("Seconde")
    with _reponse_de(page, f"/regions/{rid}") as q:
        page.locator("#an-cf-mienne").click()
    assert q.value.request.post_data_json == {"nom": "Seconde", "vu": {"nom": "Version autre"}}
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _regions(decor)[rid]["nom"] == "Seconde"


def test_un_champ_relu_pendant_l_aller_retour_suit_la_reponse(page, decor):
    """Un clic sur la zone où l'on est relit le Contexte pendant que le nom est en vol : le champ
    reprenait l'ancien nom, et le gardait une fois le nouveau enregistré."""
    rid = _detail_ouvert(page, decor)
    retenues, lacher = _retenir_les_envois(page, f"**/api/regions/{rid}")
    nom = page.locator("#an-nom")
    nom.fill("la lanterne")
    page.locator("#an-zones .an-zone-btn", has_text="détail").click()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues
    expect(nom).to_have_value("la lampe")
    lacher()
    expect(nom).to_have_value("la lanterne")
    assert _regions(decor)[rid]["nom"] == "la lanterne"


def test_un_refus_arrive_pendant_un_autre_conflit_attend_son_tour(page, decor):
    """La note est en vol quand un autre conflit s'ouvre : son 409 ne perd pas le texte, il
    ouvre son bandeau une fois le premier réglé."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    with _http(decor) as c:
        assert c.put(f"/api/regions/{decor['bulle']}/annotation",
                     json={"note": "Version autre"}).status_code == 200
    retenues, lacher = _retenir_les_envois(page, "**/api/regions/*/annotation")
    page.locator("#an-note").fill("Ma version")
    page.locator("#an-note").blur()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues
    _conflit_de_locuteur(page, decor, "Zed", "Yann")
    expect(page.locator("#an-cf-titre")).to_contain_text("Locuteur")
    _zone(page, "personnage")                      # plus de champ où la note survivrait seule
    lacher()
    expect(page.locator("#an-cf-titre")).to_contain_text("Locuteur")
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_contain_text("Note modifiée")
    _zone(page, "bulle")
    expect(page.locator("#an-note")).to_have_value("Ma version")
    with _reponse_de(page, "/annotation"):
        page.locator("#an-cf-mienne").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _lire_note(decor, decor["bulle"]) == "Ma version"


def test_le_focus_remis_ne_reprend_pas_la_ligne_du_guide(page, decor):
    """Le redessin remet le focus sur l'entrée posée ; le guide, lui, suit le pointeur parti sur
    une autre entrée : un focus remis n'est pas un geste."""
    _ouvrir(page, decor, decor["bulle"])
    retenues, lacher = _retenir_les_envois(page, "**/api/releves", "POST")
    crie = page.locator("#an-plan .an-var", has_text="crié")
    crie.click()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues
    page.locator("#an-ent-regard-camera").hover()
    expect(page.locator("#an-guide-contenu .an-g-lib")).to_have_text("regard caméra")
    lacher()
    expect(crie).to_have_attribute("aria-pressed", "true")
    expect(crie).to_be_focused()
    expect(page.locator("#an-guide-contenu .an-g-lib")).to_have_text("regard caméra")


def test_une_precision_en_cours_survit_a_un_redessin_de_la_liste(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    _mot(page, 1).click()
    origine = page.locator("#an-plan .an-ent", has=page.locator("text=origine du son"))
    origine.locator(".an-var", has_text="objet").click()
    champ = page.locator("#an-poses-liste .an-prec")
    expect(champ).to_be_visible()
    retenues, lacher = _retenir_les_envois(page, "**/api/releves", "POST")
    # Le champ retiré du document émet sa sortie (`focusout`) : elle ne vaut pas départ, et
    # rien ne doit partir de ce qui est à moitié tapé.
    ecrites = []
    page.on("request", lambda r: ecrites.append(r.url)
            if r.method == "PUT" and "/api/releves/" in r.url else None)
    page.locator("#an-plan .an-var", has_text="crié").click()
    for _ in range(50):
        if retenues:
            break
        page.wait_for_timeout(100)
    assert retenues
    champ.focus()
    page.keyboard.type("le sal")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    lacher()
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "true")
    expect(champ).to_be_focused()
    expect(champ).to_have_value("le sal")
    page.keyboard.type("L")                        # la place dans le champ reste
    expect(champ).to_have_value("le Lsal")
    page.wait_for_timeout(200)
    assert not ecrites, "le dessin a enregistré une précision à moitié tapée"
    with _reponse_de(page, RELEVE):
        champ.blur()                            # c'est la sortie du champ qui l'envoie
    assert [r for r in _releves(decor)
            if r["entree_cle"] == "origine-du-son"][0]["precision"] == "le Lsal"


def test_le_guide_complet_rend_le_focus_a_son_bouton(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    bouton = page.locator("#an-guide-complet")
    for sortie in ("Escape", "fermer"):
        _au_clavier(page, bouton)
        page.keyboard.press("Enter")
        expect(page.locator("#an-guide-modal")).to_be_visible()
        if sortie == "Escape":
            page.keyboard.press("Escape")
        else:
            page.locator("#an-guide-fermer").focus()
            page.keyboard.press("Enter")
        expect(page.locator("#an-guide-modal")).to_be_hidden()
        expect(bouton).to_be_focused()


def test_une_note_retenue_par_un_conflit_de_releve_part_quand_il_est_regle(page, decor):
    """La grille attend son choix, on écrit la note d'une autre zone, on en repart : elle part
    quand le bandeau est réglé, d'où qu'on y réponde."""
    with _http(decor) as c:
        r = c.post("/api/releves", json={"region_id": decor["bulle"], "grille_id": decor["grille"],
                                         "version": 1, "entree_cle": "ton-de-voix",
                                         "variante_cle": "crie"}).json()
    _ouvrir(page, decor, decor["bulle"])
    with _http(decor) as c:
        assert c.put(f"/api/releves/{r['id']}", json={"variante_cle": "chuchote"}).status_code == 200
    page.locator("#an-plan .an-var", has_text="crié").click()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    _zone(page, "personnage")
    page.locator("#an-note").fill("Ma note")
    page.locator("#an-note").blur()
    _zone(page, "bulle")
    with _reponse_de(page, "/annotation"):
        page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _lire_note(decor, decor["boite"]) == "Ma note"


# ── Les voies de perte de saisie (tranche 2, commit 17) ──
# Chacune mesurée avant d'être corrigée : ces tests échouaient sur le code d'avant.

def _second_projet(d):
    """Un autre projet, avec un album : la bande du haut passe à un sélecteur."""
    with _http(d) as c:
        p = c.post("/api/projets", json={"nom": "Second", "acces_membres": "ecriture"}).json()["id"]
        col = c.post("/api/collections", json={"nom": "Étude", "projet_id": p}).json()["id"]
        a = c.post("/api/albums", json={"titre": "Autre album", "collection_id": col}).json()["id"]
        c.post(f"/api/albums/{a}/import", files={"file": ("p.png", make_png(), "image/png")})
    return p


def _ouvrir_brouillon(page, d, sorte):
    """La page ouverte, un doute ou une réponse à moitié écrits. Rend le champ."""
    if sorte == "doute":
        _ouvrir(page, d, d["bulle"])
        page.locator(f'#an-poses-liste [data-douter="{_cri(d)["id"]}"]').click()
        champ = page.locator("#an-dt-texte")
    else:
        doute = _douter_api(d, _cri(d)["id"], "Un juron ?")
        _ouvrir(page, d, d["bulle"])
        _synthese(page, "revoir")
        champ = page.locator(f"#an-rep-{doute['id']}")
    expect(champ).to_be_visible()
    champ.click()
    page.keyboard.type("à moitié")
    return champ


@pytest.mark.parametrize("sorte", ["doute", "reponse"])
def test_changer_de_projet_attend_un_brouillon(page, decor, sorte):
    """Un brouillon de doute se disait « relevé retiré ailleurs » et partait, une réponse partait
    sans un mot. Le changement est refusé AVANT d'écrire : rien ne bouge, ni la page, ni le
    sélecteur, ni le projet retenu, que d'autres onglets liraient."""
    autre = _second_projet(decor)
    champ = _ouvrir_brouillon(page, decor, sorte)
    choix = page.locator("#projet-choix")
    choix.select_option(str(autre))
    expect(page.locator("#toasts")).to_contain_text("en cours d'écriture")
    expect(page.locator("#toasts")).not_to_contain_text("ailleurs")
    expect(choix).to_have_value(str(decor["projet"]))
    assert page.evaluate("() => BDProjet.lire()") != autre
    expect(champ).to_be_visible()
    expect(champ).to_have_value("à moitié")
    expect(page.locator("#an-album")).to_have_value(str(decor["album"]))
    # Sans brouillon, le même geste passe, et le projet choisi est retenu.
    champ.fill("")
    choix.select_option(str(autre))
    expect(choix).to_have_value(str(autre))
    expect(page.locator("#an-album option")).to_have_text(["Autre album"])
    assert page.evaluate("() => BDProjet.lire()") == autre


def test_un_changement_refuse_revient_au_projet_ou_l_on_est(page, decor):
    """Le sélecteur revient au projet COURANT, pas à celui de l'arrivée sur la page."""
    autre = _second_projet(decor)
    page.add_init_script(f"localStorage.setItem('bd-projet', '{autre}')")
    page.goto(f"{decor['base']}/annotation", wait_until="networkidle")
    choix = page.locator("#projet-choix")
    expect(choix).to_have_value(str(autre))
    choix.select_option(str(decor["projet"]))
    expect(page.locator("#an-album")).to_have_value(str(decor["album"]))
    expect(page.locator("#an-mini .an-mz")).to_have_count(2)
    _zone(page, "bulle")
    page.locator(f'#an-poses-liste [data-douter="{_cri(decor)["id"]}"]').click()
    page.locator("#an-dt-texte").fill("à moitié")
    choix.select_option(str(autre))
    expect(page.locator("#toasts")).to_contain_text("en cours d'écriture")
    expect(choix).to_have_value(str(decor["projet"]))


def test_changer_de_projet_attend_un_conflit_ouvert(page, decor):
    """Le bandeau restait ouvert sur le projet d'arrivée, la note effacée de son champ, pour
    une zone que la page ne montrait plus."""
    autre = _second_projet(decor)
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    _conflit_de_note(page, decor, "Version autre", "Ma version")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    choix = page.locator("#projet-choix")
    choix.select_option(str(autre))
    expect(page.locator("#toasts")).to_contain_text("Réglez d'abord le conflit")
    expect(choix).to_have_value(str(decor["projet"]))
    expect(page.locator("#an-note")).to_have_value("Ma version")
    expect(page.locator("#an-album")).to_have_value(str(decor["album"]))
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    choix.select_option(str(autre))
    expect(page.locator("#an-album option")).to_have_text(["Autre album"])


def _sorties(page):
    """Répond aux demandes du navigateur à la sortie. Rend `(vues, reponse)` : `reponse["partir"]`
    faux, on reste."""
    vues, reponse = [], {"partir": False}

    def repondre(dialogue):
        vues.append(dialogue.type)
        if reponse["partir"]:
            dialogue.accept()
        else:
            dialogue.dismiss()

    page.on("dialog", repondre)
    return vues, reponse


def _vers_la_bibliotheque(page):
    page.locator('#site-nav a[href="/corpus"]').first.click()


@pytest.mark.parametrize("sorte", ["conflit", "doute", "reponse"])
def test_quitter_par_la_navigation_demande_quand_une_saisie_se_perdrait(page, decor, sorte):
    """Le lien de la navigation partait sans rien dire : la saisie du bandeau, le brouillon, la
    réponse disparaissaient avec la page. Le navigateur demande ; rester garde tout."""
    if sorte == "conflit":
        _ouvrir(page, decor, decor["bulle"])
        expect(page.locator("#an-note")).to_have_value("il jure")
        _conflit_de_note(page, decor, "Version autre", "Ma version")
        expect(page.locator("#an-cf-titre")).to_be_visible()
        champ, valeur = page.locator("#an-note"), "Ma version"
    else:
        champ, valeur = _ouvrir_brouillon(page, decor, sorte), "à moitié"
    vues, reponse = _sorties(page)
    _vers_la_bibliotheque(page)
    expect(champ).to_have_value(valeur)
    page.wait_for_timeout(300)
    assert vues == ["beforeunload"]
    assert "/annotation" in page.url
    expect(champ).to_have_value(valeur)
    reponse["partir"] = True                       # « Quitter » : on part vraiment
    _vers_la_bibliotheque(page)
    page.wait_for_url("**/corpus*")
    assert vues == ["beforeunload", "beforeunload"]


def test_un_conflit_sans_rien_dans_les_champs_retient_aussi_la_page(page, decor):
    """Un choix de locuteur en conflit n'est dans aucun champ : la saisie vit dans le bandeau."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    _conflit_de_locuteur(page, decor, "Zed", "Yann")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    vues, _ = _sorties(page)
    _vers_la_bibliotheque(page)
    page.wait_for_timeout(300)
    assert vues == ["beforeunload"]
    expect(page.locator("#an-cf-titre")).to_be_visible()


@pytest.mark.parametrize("champ", ["precision", "nom", "transcription"])
def test_recharger_demande_quand_un_champ_n_est_pas_parti(page, decor, champ):
    """Recharger ne fait pas sortir du champ : ce qui y est tapé n'est parti nulle part."""
    if champ == "precision":
        _ouvrir(page, decor, decor["bulle"])
        cible = _avec_une_precision(page)
    elif champ == "nom":
        _ouvrir(page, decor, _detail(decor, nom="la lampe"))
        cible = page.locator("#an-nom")
    else:
        _ouvrir(page, decor, _texte_hors_bulle(decor))
        cible = page.locator("#an-transcription")
    cible.click()
    page.keyboard.type("x")
    vues, _ = _sorties(page)
    page.evaluate("() => { setTimeout(() => location.reload(), 0); }")
    expect(cible).to_be_focused()
    page.wait_for_timeout(400)
    assert vues == ["beforeunload"]
    expect(cible).to_be_focused()


def test_recharger_demande_quand_la_note_n_est_pas_partie(page, decor):
    """La note part après le délai de frappe : recharger avant le perdait (mesuré)."""
    _ouvrir(page, decor, decor["bulle"])
    note = page.locator("#an-note")
    expect(note).to_have_value("il jure")
    note.click()
    vues, _ = _sorties(page)
    # Dans la même tâche : le délai de frappe ne doit pas avoir le temps de passer.
    page.evaluate("""() => {
      const c = document.querySelector('#an-note');
      c.value += ' encore';
      c.dispatchEvent(new Event('input', { bubbles: true }));
      setTimeout(() => location.reload(), 0);
    }""")
    page.wait_for_timeout(300)
    assert vues == ["beforeunload"]
    expect(note).to_have_value("il jure encore")


def test_quitter_une_page_sans_enjeu_ne_demande_rien(page, decor):
    """Un formulaire de doute vide, un champ cliqué sans rien y changer : rien à perdre."""
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    page.locator(f'#an-poses-liste [data-douter="{_cri(decor)["id"]}"]').click()
    expect(page.locator("#an-dt-texte")).to_be_visible()
    page.locator("#an-note").click()
    vues, _ = _sorties(page)
    _vers_la_bibliotheque(page)
    page.wait_for_url("**/corpus*")
    assert vues == []


def test_une_note_enregistree_ne_retient_plus_la_page(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    note = page.locator("#an-note")
    expect(note).to_have_value("il jure")
    note.click()
    page.keyboard.type(" encore")
    expect(page.locator("#an-note-etat")).to_have_text("Enregistrée")
    vues, _ = _sorties(page)
    _vers_la_bibliotheque(page)
    page.wait_for_url("**/corpus*")
    assert vues == []


def test_un_conflit_regle_ne_retient_plus_la_page(page, decor):
    _ouvrir(page, decor, decor["bulle"])
    expect(page.locator("#an-note")).to_have_value("il jure")
    _conflit_de_note(page, decor, "Version autre", "Ma version")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    vues, _ = _sorties(page)
    _vers_la_bibliotheque(page)
    page.wait_for_url("**/corpus*")
    assert vues == []


def _avec_une_precision(page):
    """Un relevé « origine du son » sur le second mot : sa ligne attend une précision."""
    _mot(page, 1).click()
    origine = page.locator("#an-plan .an-ent", has=page.locator("text=origine du son"))
    origine.locator(".an-var", has_text="objet").click()
    champ = page.locator("#an-poses-liste .an-prec")
    expect(champ).to_be_visible()
    return champ


def _origine(d):
    return next(r for r in _releves(d) if r["entree_cle"] == "origine-du-son")


def _precision_sous_conflit(page, d):
    """Un champ de précision, et un conflit de locuteur qui attend."""
    _ouvrir(page, d, d["bulle"])
    expect(page.locator("#an-loc-nom")).to_have_text("Haddock")
    champ = _avec_une_precision(page)
    _conflit_de_locuteur(page, d, "Zed", "Yann")
    expect(page.locator("#an-cf-titre")).to_be_visible()
    return champ


def test_une_precision_ecrite_pendant_un_autre_conflit_survit_et_part(page, decor):
    """Elle n'attendait nulle part : la sortie du champ disait « réglez d'abord le conflit » et
    prenait le focus, et le premier dessin de la liste l'effaçait."""
    champ = _precision_sous_conflit(page, decor)
    champ.fill("le salon")
    champ.blur()
    page.wait_for_timeout(200)
    expect(page.locator("#toasts")).not_to_contain_text("Réglez d'abord")
    expect(page.locator("#an-cf-mienne")).not_to_be_focused()
    expect(champ).to_have_attribute("title", "En attente de votre choix")
    assert _origine(decor)["precision"] is None
    _zone(page, "personnage")
    _zone(page, "bulle")
    _mot(page, 1).click()
    expect(champ).to_be_visible()
    expect(champ).to_have_value("le salon")
    expect(champ).to_have_attribute("title", "En attente de votre choix")
    with _reponse_de(page, RELEVE) as q:
        page.locator("#an-cf-autre").click()
    assert q.value.request.post_data_json == {"precision": "le salon", "vu": {"precision": None}}
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _origine(decor)["precision"] == "le salon"
    expect(champ).to_have_value("le salon")
    expect(champ).not_to_have_attribute("title", "En attente de votre choix")


def test_quitter_le_champ_d_une_precision_pour_le_bandeau_ne_vole_pas_le_clic(page, decor):
    """Le piège du commit 16 : la sortie du champ reprenait le focus, et le clic sur le bandeau
    tombait dans le vide (mesuré : le bandeau restait ouvert)."""
    champ = _precision_sous_conflit(page, decor)
    champ.click()
    page.keyboard.type("le salon")
    with _reponse_de(page, RELEVE):
        page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _origine(decor)["precision"] == "le salon"


def test_une_retenue_pas_encore_repartie_retient_la_page(page, decor):
    """Le conflit est réglé, et les saisies qu'il retenait partent l'une après l'autre : tant que
    la dernière attend son tour, quitter la perdrait."""
    champ = _precision_sous_conflit(page, decor)
    _zone(page, "personnage")
    page.locator("#an-note").fill("Ma note")
    page.locator("#an-note").blur()
    _zone(page, "bulle")
    _mot(page, 1).click()
    champ.fill("le salon")
    champ.blur()
    notes, lacher = _retenir_les_envois(page, "**/api/regions/*/annotation")
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    for _ in range(50):
        if notes:
            break
        page.wait_for_timeout(100)
    assert notes
    vues, _ = _sorties(page)
    _vers_la_bibliotheque(page)
    page.wait_for_timeout(300)
    assert vues == ["beforeunload"]
    with _reponse_de(page, RELEVE):
        lacher()
    assert _origine(decor)["precision"] == "le salon"


def test_une_precision_retenue_deja_ecrite_ailleurs_ne_repart_pas(page, decor):
    """« Garder l'autre » relit le relevé, et l'autre a écrit le même texte : rien à envoyer."""
    _ouvrir(page, decor, decor["bulle"])
    champ = _avec_une_precision(page)
    rid = _origine(decor)["id"]
    origine = page.locator("#an-plan .an-ent", has=page.locator("text=origine du son"))
    with _http(decor) as c:
        assert c.put(f"/api/releves/{rid}",
                     json={"qualificatifs": ["objet", "personnage"]}).status_code == 200
    origine.locator(".an-var", has_text="hors champ").click()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    champ.fill("le salon")
    champ.blur()
    with _http(decor) as c:
        assert c.put(f"/api/releves/{rid}", json={"precision": "le salon"}).status_code == 200
    ecrites = []
    page.on("request", lambda r: ecrites.append(r.url)
            if r.method == "PUT" and "/api/releves/" in r.url else None)
    with _reponse_de(page, "/releves", "GET"):     # « Garder l'autre » relit ; la reprise suit
        page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    page.wait_for_timeout(300)                     # une absence : rien à attendre d'autre
    assert ecrites == []
    expect(champ).to_have_value("le salon")


def test_une_precision_ramenee_a_sa_valeur_n_attend_plus_rien(page, decor):
    champ = _precision_sous_conflit(page, decor)
    champ.fill("le salon")
    champ.blur()
    champ.fill("")
    champ.blur()
    expect(champ).not_to_have_attribute("title", "En attente de votre choix")
    page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    page.wait_for_timeout(300)                     # une absence : rien à attendre d'autre
    assert _origine(decor)["precision"] is None


def test_les_deux_champs_d_une_precision_retenue_disent_la_meme_chose(page, decor):
    """La liste et « À compléter » montrent le même relevé : l'autre champ, resté sur l'ancienne
    valeur, aurait repris la retenue à sa sortie."""
    champ = _precision_sous_conflit(page, decor)
    _synthese(page, "revoir")
    jumeau = page.locator("#an-syn-corps .an-prec")
    expect(jumeau).to_be_visible()
    champ.fill("le salon")
    champ.blur()
    expect(jumeau).to_have_value("le salon")
    jumeau.focus()
    jumeau.blur()
    _zone(page, "personnage")                      # « À compléter » se redessine, et la redit
    expect(jumeau).to_have_value("le salon")
    with _reponse_de(page, RELEVE):
        page.locator("#an-cf-autre").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    assert _origine(decor)["precision"] == "le salon"


@pytest.mark.parametrize("reponse", ["mienne", "autre"])
def test_une_precision_retouchee_pendant_son_propre_conflit(page, decor, reponse):
    """Sa retouche suit le conflit : « Remplacer » écrit la dernière version, « Garder l'autre »
    ne laisse rien partir derrière lui."""
    _ouvrir(page, decor, decor["bulle"])
    champ = _avec_une_precision(page)
    rid = _origine(decor)["id"]
    with _http(decor) as c:
        assert c.put(f"/api/releves/{rid}", json={"precision": "de l'autre"}).status_code == 200
    champ.fill("la mienne")
    champ.blur()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    expect(champ).to_have_value("la mienne")
    champ.fill("la mienne, retouchée")
    champ.blur()
    expect(page.locator("#toasts")).not_to_contain_text("Réglez d'abord")
    # « Garder l'autre » relit la planche : c'est la seule réponse à attendre de ce côté-là.
    attendu = "la mienne, retouchée" if reponse == "mienne" else "de l'autre"
    with _reponse_de(page, RELEVE if reponse == "mienne" else "/releves", "PUT" if reponse == "mienne" else "GET"):
        page.locator(f"#an-cf-{reponse}").click()
    expect(page.locator("#an-cf-titre")).to_have_count(0)
    expect(champ).to_have_value(attendu)
    assert _origine(decor)["precision"] == attendu


def test_une_precision_retenue_sur_un_releve_retire_rend_son_texte(page, decor):
    """Le conflit était sur le retrait de ce relevé : « Remplacer » le retire, et la précision
    retenue n'a plus où s'écrire. Elle se dit, plutôt que de se perdre."""
    _ouvrir(page, decor, decor["bulle"])
    champ = _avec_une_precision(page)
    r = _origine(decor)
    with _http(decor) as c:
        assert c.put(f"/api/releves/{r['id']}",
                     json={"qualificatifs": ["hors-champ"]}).status_code == 200
    page.locator(f'#an-poses-liste [data-retirer="{r["id"]}"]').click()
    expect(page.locator("#an-cf-titre")).to_be_visible()
    champ.fill("le salon")
    champ.blur()
    page.locator("#an-cf-mienne").click()
    expect(page.locator("#toasts")).to_contain_text("« le salon »")
    assert not [x for x in _releves(decor) if x["id"] == r["id"]]


def test_une_precision_a_moitie_tapee_survit_a_actualiser(page, decor):
    """« Actualiser » relit la planche pendant qu'on est revenu dans le champ : le dessin qui
    suit n'envoie rien, et la frappe continue à sa place."""
    _ouvrir(page, decor, decor["bulle"])
    champ = _avec_une_precision(page)
    _retour_sur_l_onglet(page)
    _poser(decor, region_id=decor["bulle"], entree_cle="ton-de-voix", variante_cle="crie")
    _retour_sur_l_onglet(page)
    bouton = page.locator("#an-actualiser")
    expect(bouton).to_be_visible()
    lues, lacher = _retenir_les_envois(page, "**/api/planches/*/releves", "GET")
    ecrites = []
    page.on("request", lambda r: ecrites.append(r.url)
            if r.method == "PUT" and "/api/releves/" in r.url else None)
    bouton.click()
    for _ in range(50):
        if lues:
            break
        page.wait_for_timeout(100)
    assert lues
    champ.click()
    page.keyboard.type("le sal")
    page.keyboard.press("ArrowLeft")
    lacher()
    expect(page.locator("#an-plan .an-var", has_text="crié")).to_have_attribute("aria-pressed", "true")
    expect(bouton).to_be_hidden()
    expect(champ).to_be_focused()
    page.keyboard.type("L")
    expect(champ).to_have_value("le saLl")
    assert ecrites == []
    assert _origine(decor)["precision"] is None


def test_une_precision_dont_la_ligne_s_en_va_s_enregistre(page, decor):
    """Le champ part avec sa ligne sans qu'on l'ait quitté, et la frappe n'a plus de suite : le
    texte part, il ne se perd pas."""
    _ouvrir(page, decor, decor["bulle"])
    champ = _avec_une_precision(page)
    champ.click()
    page.keyboard.type("le salon")
    # Un clic sans sortie du champ, comme un raccourci.
    with _reponse_de(page, RELEVE):
        page.evaluate("() => document.querySelector('#an-zones .an-zone-btn:last-child').click()")
    expect(page.locator("#an-tete-zone")).to_contain_text("personnage")
    assert _origine(decor)["precision"] == "le salon"
