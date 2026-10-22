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

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("live_server", [True], indirect=True)]

# UX-10 — ce que `tests/test_surfaces.py` confronte au source.
SURFACES_AUDITEES = ("/corpus",)
SURFACES_HORS_PERIMETRE = {
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
