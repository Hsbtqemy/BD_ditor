"""UX-11 (Hugo, 2026-10-22) — l'ordre des planches et le nom du fichier d'origine, dans la
fiche d'un album de la Bibliothèque, dans un vrai navigateur.

Ce que ce fichier mesure, sous des identités derrière le proxy :

- le nom du fichier d'origine se lit au SURVOL de la ligne d'une planche — « Fichier :
  p10.png » —, et une planche d'avant la v34 n'a pas d'infobulle ;
- « ⇅ Ranger par nom de fichier » confirme d'abord, en disant ce qui change, puis range ;
- ↑ ↓ déplacent une planche d'un cran, au clavier comme à la souris, et le focus suit la
  planche déplacée ;
- un ordre changé par quelqu'un d'autre pendant qu'on regarde : le geste est refusé, la
  fiche le dit et montre l'ordre actuel ;
- aucun de ces gestes pour qui ne fait que lire l'album.

Les images sont fabriquées ici, de largeurs distinctes : c'est la largeur relue au serveur
qui dit quelle image est à quel rang.
"""
import re
import sqlite3

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
from playwright.sync_api import expect  # noqa: E402

from conftest import du_projet
from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
    "/annotation": "l'ordre des planches se change dans la Bibliothèque seule",
    "/": "l'Atelier ne change pas l'ordre des planches : ses listes suivent le numéro que "
         "la Bibliothèque pose",
    "/recherche": "aucun geste sur les planches : la Recherche lit le corpus",
    "/exploration": "aucun geste sur les planches : l'Exploration compte le corpus",
    "/administration": "l'ordre des planches est un geste de la fiche d'un album, que "
                       "l'Administration n'ouvre pas",
}

SAM = {"Remote-User": "sam"}


def _decor(base, noms=("p10.png", "p2.png", "p1.png")):
    """« Étude », où sam écrit et lina ne fait que lire ; un album « Ecrit » dont les
    planches sont importées dans l'ordre de `noms` — un dossier mal nommé."""
    with httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE) as c:
        cid = c.post("/api/collections", json={"nom": "Étude"}).json()["id"]
        for qui, niveau in (("sam", "ecriture"), ("lina", "lecture")):
            du_projet(c, cid, "utilisateur", qui, headers=ECRITURE)
            r = c.put(f"/api/collections/{cid}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau})
            assert r.status_code == 200, r.text
        r = c.post("/api/albums", json={"titre": "Ecrit", "collection_id": cid})
        assert r.status_code == 201, r.text
        aid = r.json()["id"]
        ids = []
        for i, nom in enumerate(noms):
            r = c.post(f"/api/albums/{aid}/import",
                       files={"file": (nom, make_png(300 + 10 * i, 200), "image/png")})
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
    return aid, ids


def _ouvrir(page, base, qui="sam"):
    page.set_extra_http_headers({"Remote-User": qui})
    page.goto(base + "/corpus", wait_until="networkidle")
    page.locator(".album-row", has_text="Ecrit").first.click()
    expect(page.locator("#album-titre")).to_contain_text("Ecrit")


def _lignes(page):
    return page.locator("#album-detail tr[data-ligne-planche]")


def _ordre_serveur(base, aid):
    with httpx.Client(base_url=base, trust_env=False, timeout=30, headers=ECRITURE) as c:
        return [p["id"] for p in c.get(f"/api/albums/{aid}/planches").json()]


def test_le_nom_du_fichier_se_lit_au_survol_de_la_ligne(page, live_server, tmp_path):
    aid, ids = _decor(live_server)
    # La troisième date d'avant la v34 : rien n'a été noté de son fichier.
    conn = sqlite3.connect(tmp_path / "live.sqlite")
    conn.execute("UPDATE planches SET master_origine = NULL WHERE id = ?", (ids[2],))
    conn.execute("UPDATE planches SET master_origine = 'sharedocs:BD/Espace de sam/p2.png' "
                 "WHERE id = ?", (ids[1],))
    conn.commit()
    conn.close()
    _ouvrir(page, live_server)
    lignes = _lignes(page)
    expect(lignes).to_have_count(3)
    expect(lignes.nth(0)).to_have_attribute("title", "Fichier : p10.png")
    expect(lignes.nth(1)).to_have_attribute("title", "Fichier : p2.png")   # le nom seul
    assert lignes.nth(2).get_attribute("title") is None
    # Le survol de la vignette montre l'infobulle de sa ligne : rien ne la recouvre.
    assert lignes.nth(0).locator("img.pl-thumb").get_attribute("title") is None
    expect(page.locator("#album-detail")).not_to_contain_text("Espace de sam")


def test_ranger_par_nom_de_fichier_confirme_puis_range(page, live_server):
    aid, ids = _decor(live_server)               # importées : p10, p2, p1
    _ouvrir(page, live_server)
    questions = []

    def repondre(d):
        questions.append(d.message)
        d.accept()
    page.on("dialog", repondre)
    bouton = page.locator("#bi-ranger-nom")
    expect(bouton).to_have_text("⇅ Ranger par nom de fichier")
    bouton.click()
    ligne = page.locator("#bi-ordre-msg")
    expect(ligne).to_have_text("Planches rangées dans l'ordre des noms de fichier : 2 "
                               "planches ont changé de place.")
    assert len(questions) == 1, questions
    assert questions[0].startswith("Ranger les planches dans l'ordre des noms de fichier ?")
    assert "2 planches changent de place." in questions[0]
    assert "citations « pl·c·b »" in questions[0]
    titres = [_lignes(page).nth(i).get_attribute("title") for i in range(3)]
    assert titres == ["Fichier : p1.png", "Fichier : p2.png", "Fichier : p10.png"], titres
    assert _ordre_serveur(live_server, aid) == ids[::-1]
    expect(bouton).to_be_focused()
    # Déjà rangé : la fiche le dit, sans rien demander.
    bouton.click()
    expect(ligne).to_have_text("Les planches sont déjà dans l'ordre des noms de fichier.")
    assert len(questions) == 1


def test_ranger_par_nom_refuse_ne_change_rien(page, live_server):
    aid, ids = _decor(live_server)
    _ouvrir(page, live_server)
    page.on("dialog", lambda d: d.dismiss())
    envois = []
    page.on("request", lambda r: envois.append(r) if r.method == "PUT" else None)
    page.locator("#bi-ranger-nom").click()
    page.wait_for_timeout(300)
    assert envois == []
    assert _ordre_serveur(live_server, aid) == ids


def test_monter_et_descendre_au_clavier_puis_a_la_souris(page, live_server):
    aid, ids = _decor(live_server, noms=("a.png", "b.png", "c.png"))
    _ouvrir(page, live_server)
    lignes = _lignes(page)
    expect(lignes.nth(0).locator("[data-monter]")).to_be_disabled()
    expect(lignes.nth(2).locator("[data-descendre]")).to_be_disabled()

    # Au clavier : la première descend d'un cran, le focus la suit, elle descend encore.
    descendre = page.locator(f"[data-descendre='{ids[0]}']")
    descendre.focus()
    page.keyboard.press("Enter")
    ligne = page.locator("#bi-ordre-msg")
    expect(ligne).to_have_text("Déplacée : c'est maintenant la planche 2 (i.002).")
    expect(lignes.nth(1)).to_have_attribute("data-ligne-planche", str(ids[0]))
    expect(page.locator(f"[data-descendre='{ids[0]}']")).to_be_focused()
    page.keyboard.press("Enter")
    expect(ligne).to_have_text("Déplacée : c'est maintenant la planche 3 (i.003).")
    expect(lignes.nth(2)).to_have_attribute("data-ligne-planche", str(ids[0]))
    # Au bord, ↓ s'éteint : le focus passe à ↑ de la même planche.
    expect(page.locator(f"[data-descendre='{ids[0]}']")).to_be_disabled()
    expect(page.locator(f"[data-monter='{ids[0]}']")).to_be_focused()
    assert _ordre_serveur(live_server, aid) == [ids[1], ids[2], ids[0]]

    # À la souris : la dernière remonte d'un cran.
    page.locator(f"[data-monter='{ids[0]}']").click()
    expect(lignes.nth(1)).to_have_attribute("data-ligne-planche", str(ids[0]))
    assert _ordre_serveur(live_server, aid) == [ids[1], ids[0], ids[2]]
    # Les fichiers n'ont pas suivi : la largeur de chaque planche est celle de son image.
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        planches = c.get(f"/api/albums/{aid}/planches").json()
    assert [(p["id"], p["largeur_px"], p["numero"]) for p in planches] == [
        (ids[1], 310, 1), (ids[0], 300, 2), (ids[2], 320, 3)]


def test_un_ordre_change_ailleurs_est_refuse_et_la_fiche_montre_l_ordre_actuel(page,
                                                                            live_server):
    aid, ids = _decor(live_server, noms=("a.png", "b.png", "c.png"))
    _ouvrir(page, live_server)
    # Pendant que sam regarde, quelqu'un d'autre inverse l'album.
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers={**ECRITURE, "Remote-User": "alice"}) as c:
        r = c.put(f"/api/albums/{aid}/ordre-des-planches",
                  json={"ordre": ids[::-1], "vu": ids})
        assert r.status_code == 200, r.text
    page.locator(f"[data-descendre='{ids[0]}']").click()
    ligne = page.locator("#bi-ordre-msg")
    expect(ligne).to_contain_text("Conflit : l'ordre des planches a été changé par alice")
    expect(ligne).to_contain_text("Votre modification n'est pas enregistrée.")
    expect(ligne).to_have_class(re.compile(r"\berreur\b"))
    expect(_lignes(page).nth(0)).to_have_attribute("data-ligne-planche", str(ids[2]))
    assert _ordre_serveur(live_server, aid) == ids[::-1]


def test_aucun_geste_d_ordre_pour_qui_ne_fait_que_lire(page, live_server):
    _decor(live_server)
    _ouvrir(page, live_server, "lina")
    expect(_lignes(page)).to_have_count(3)
    expect(page.locator("#bi-ranger-nom")).to_have_count(0)
    expect(page.locator("#album-detail [data-monter], #album-detail [data-descendre]")) \
        .to_have_count(0)
    # L'infobulle, elle, est pour tous ceux qui lisent l'album.
    expect(_lignes(page).nth(0)).to_have_attribute("title", "Fichier : p10.png")


def test_les_fleches_s_eteignent_sous_un_filtre_de_relecture(page, live_server):
    """Le filtre CACHE des planches, et un cran se compte dans l'album entier : ↑ échangerait
    la planche avec une voisine qu'on ne voit pas (relecture croisée). Éteintes, elles disent
    pourquoi — au CLAVIER aussi (contre-relecture) : `aria-disabled` et non `disabled`, la
    tabulation les atteint, leur description est la raison, et les toucher la dit dans la
    ligne d'état sans rien envoyer. Le filtre retiré, elles reviennent."""
    aid, ids = _decor(live_server, noms=("a.png", "b.png", "c.png"))
    _ouvrir(page, live_server)
    envois = []
    page.on("request", lambda r: envois.append(r) if r.method == "PUT" else None)
    page.select_option("#rel-filter", "a_faire")
    raison = re.compile(r"^Retirez le filtre de relecture pour changer l'ordre")
    monter = page.locator(f"[data-monter='{ids[0]}']")
    descendre = page.locator(f"[data-descendre='{ids[0]}']")
    for bouton in (monter, descendre, page.locator(f"[data-monter='{ids[1]}']")):
        expect(bouton).to_have_attribute("aria-disabled", "true")
        assert bouton.get_attribute("disabled") is None
        expect(bouton).to_have_accessible_description(raison)
        expect(bouton).to_have_attribute("title", raison)
    # L'audit axe de la fiche, flèches éteintes (A11Y : description, contraste, nom).
    from test_e2e_a11y import _audit, _fmt
    viol = _audit(page)
    assert not viol, f"Fiche d'un album, flèches éteintes :\n{_fmt(viol)}"
    # Au clavier : la case de la ligne, puis Tab — le bouton éteint reçoit le focus.
    page.locator(f"input[data-pid='{ids[0]}']").focus()
    page.keyboard.press("Tab")
    expect(monter).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#bi-ordre-msg")).to_have_text(raison)
    # À la souris, sur ↓ — qui, filtre retiré, déplacerait vraiment : rien ne part.
    page.locator("#bi-ordre-msg").evaluate("el => { el.textContent = ''; }")
    # `force` : Playwright tient un `aria-disabled` pour inactif, le navigateur non — il
    # livre le clic, et c'est l'écran qui doit le refuser en disant pourquoi.
    descendre.click(force=True)
    expect(page.locator("#bi-ordre-msg")).to_have_text(raison)
    page.wait_for_timeout(300)
    assert envois == []
    page.select_option("#rel-filter", "")
    expect(page.locator(f"[data-descendre='{ids[0]}']")).to_be_enabled()
    expect(page.locator(f"[data-descendre='{ids[0]}']")).to_have_attribute(
        "title", "Descendre d'un cran dans l'album")


def test_les_fleches_s_eteignent_pendant_un_import_dans_l_album(page, live_server):
    """Un import en lot ajoute des planches pendant qu'on les déplacerait : ↑ ↓ et « Ranger »
    s'éteignent tant qu'il court dans CET album. La requête d'import est retenue le temps
    de regarder."""
    aid, ids = _decor(live_server, noms=("a.png", "b.png"))
    _ouvrir(page, live_server)
    retenues = []
    page.route(f"**/api/albums/{aid}/import", lambda route: retenues.append(route))
    with page.expect_file_chooser() as choix:
        page.locator("#bi-importer").click()
    choix.value.set_files([{"name": "c.png", "mimeType": "image/png",
                            "buffer": make_png(330, 200)}])
    expect(page.locator("#bi-import-arreter")).to_be_visible()
    descendre = page.locator(f"[data-descendre='{ids[0]}']")
    expect(descendre).to_have_attribute("aria-disabled", "true")
    expect(descendre).to_have_accessible_description(re.compile(r"^Un import est en cours "
                                                                r"dans cet album"))
    expect(page.locator("#bi-ranger-nom")).to_be_disabled()
    for _ in range(100):                      # la route est interceptée pendant l'attente
        if retenues:
            break
        page.wait_for_timeout(50)
    assert retenues, "la requête d'import n'a pas été retenue"
    retenues[0].continue_()
    expect(page.locator("#bi-import-etat")).to_have_text("1 planche importée", timeout=30000)
    expect(page.locator(f"[data-descendre='{ids[0]}']")).to_be_enabled()
    assert page.locator(f"[data-descendre='{ids[0]}']").get_attribute("aria-disabled") is None
    expect(page.locator("#bi-ranger-nom")).to_be_enabled()
