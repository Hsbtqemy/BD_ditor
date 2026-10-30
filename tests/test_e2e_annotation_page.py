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
    expect(page.locator('#an-ctx-corps dd[data-ctx="locuteur"]')).to_have_text("Haddock")
    expect(page.locator('#an-ctx-corps dd[data-ctx="note"]')).to_have_text("il jure")
    # Aucun champ dans le Contexte : il se lit ici, il s'écrit dans l'Atelier.
    expect(page.locator(".an-ctx input, .an-ctx textarea, .an-ctx select")).to_have_count(0)
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
    page.locator("#an-vue-case rect.an-fond").click(position={"x": 5, "y": 300})
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


def test_la_synthese_tient_a_320_px(page, decor):
    """La sonde du reflow mesure la page au repos, Synthèse cachée : ce test l'ouvre, sur
    « À revoir » qui porte le plus de gestes, et exige qu'aucun élément ne déborde de côté."""
    _douter_api(decor, _cri(decor)["id"], "Un juron, ou un cri qu'on n'entend pas ?")
    page.set_viewport_size({"width": 320, "height": 900})
    _ouvrir(page, decor, decor["bulle"])
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
    page.wait_for_load_state("networkidle")


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
