"""ANN-7 — le bloc « Grilles » de la fiche d'un projet (Administration › Projets), et l'écran
d'import (tranchés par Hugo sur maquette le 2026-11-03).

Trois parcours, dans un vrai navigateur, sur la vraie route :

- un classeur FAUTIF : le bilan dit où (la feuille, la ligne, l'entrée, la question), ce qui
  ne va pas et ce qu'il faut faire, « Importer » reste éteint et rien ne s'écrit ;
- le classeur JUSTE : la grille naît, puis se publie et s'active depuis sa ligne ;
- le RÉIMPORT d'une grille ouverte qui perd une entrée employée : le bilan demande « retirer »
  ou « fusionner dans… », « Importer » attend la réponse, et l'entrée est retirée.

Chaque fois, l'état est RELU par l'API : un bilan affiché ne prouve pas ce qui s'est écrit.
La grille est FICTIVE (`tools/grille-modele.csv`)."""
import io
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
openpyxl = pytest.importorskip("openpyxl")

from playwright.sync_api import expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import grille_import  # noqa: E402
import grille_tableur  # noqa: E402
from conftest import ECRITURE, make_png  # noqa: E402
from grilles_decor import MODELE, MODELE_LISTES, flux, grille_active_vivante  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — le périmètre de cet audit (`tests/test_surfaces.py`).
SURFACES_AUDITEES = ("/administration",)
SURFACES_HORS_PERIMETRE = {
    "/": "le bloc « Grilles » ne vit que dans la fiche d'un projet de l'Administration",
    "/annotation": "la page Annotation pose des relevés ; elle n'importe pas de grille",
    "/recherche": "le bloc « Grilles » ne vit que dans la fiche d'un projet de l'Administration",
    "/corpus": "le masquage d'une grille par collection, dans la Bibliothèque, n'est pas ici",
    "/exploration": "le bloc « Grilles » ne vit que dans la fiche d'un projet de l'Administration",
}

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _http(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


def _classeur() -> bytes:
    contenu = grille_import.lire(flux(MODELE), flux(MODELE_LISTES), porte_sur="mots")["contenu"]
    return grille_tableur.ecrire_classeur(contenu, nom="Signaux", ouverte=False,
                                          porte_sur="mots", note=None)


def _retouche(data: bytes, retouche) -> bytes:
    """Le classeur, sa feuille des entrées retouchée par openpyxl — comme un tableur."""
    wb = openpyxl.load_workbook(io.BytesIO(data))
    retouche(wb[grille_tableur.FEUILLE_ENTREES])
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def _ligne_de(ws, entree):
    """(numéro de ligne, colonne de chaque titre) de la ligne de l'entrée `entree`."""
    titres = None
    for ligne in ws.iter_rows():
        valeurs = [c.value for c in ligne]
        if titres is None and "Entrée" in valeurs:
            titres = {v: i for i, v in enumerate(valeurs) if v}
            continue
        if titres is not None and valeurs[titres["Entrée"]] == entree:
            return ligne[0].row, titres
    raise AssertionError(f"« {entree} » introuvable dans la feuille")


def _fichier(nom, data):
    return {"name": nom, "mimeType": XLSX, "buffer": data}


def _ouvrir(page, base, projet):
    page.goto(f"{base}/administration?vue=projets&projet={projet}", wait_until="networkidle")
    expect(page.locator("#pj-grilles-titre")).to_be_visible()
    expect(page.locator("#pg-liste-zone")).not_to_contain_text("Chargement", timeout=10000)


def test_un_classeur_fautif_dit_ou_et_quoi_puis_le_juste_fait_naitre_la_grille(page,
                                                                               live_server):
    base = live_server
    with _http(base) as c:
        projet = c.post("/api/projets", json={"nom": "Étude grilles"}).json()["id"]
    juste = _classeur()

    def libre(ws):
        n, titres = _ligne_de(ws, "cri")
        ws.cell(row=n, column=titres["4. Ce qu'on choisit"] + 1, value="libre")
    fautif = _retouche(juste, libre)

    _ouvrir(page, base, projet)
    expect(page.locator("#pg-liste-zone")).to_contain_text("Aucune grille")
    page.get_by_role("button", name="⤒ Importer un classeur…").click()
    expect(page.locator("#pg-fichier")).to_be_focused()
    page.set_input_files("#pg-fichier", _fichier("signaux.xlsx", fautif))
    page.get_by_role("button", name="Vérifier").click()
    verdict = page.locator("#pg-verdict")
    expect(verdict).to_be_visible()
    expect(verdict).to_have_text("1 faute à corriger : rien n'est importé tant qu'il en reste une.")
    faute = page.locator(".pg-faute")
    expect(faute).to_have_count(1)
    expect(faute.locator(".pg-faute-ou")).to_contain_text("feuille « 2. Les entrées », ligne")
    expect(faute.locator(".pg-faute-ou")).to_contain_text("« cri » · 4. Ce qu'on choisit")
    expect(faute).to_contain_text("« libre » n'est pas une forme")
    expect(faute.locator(".pg-faute-faire")).to_contain_text("une variante")
    importer = page.locator("#pg-importer")
    expect(importer).to_have_attribute("aria-disabled", "true")
    importer.click(force=True)                 # éteint : rien ne part
    expect(page.locator("#pj-grilles-msg")).to_contain_text("à corriger")
    with _http(base) as c:
        assert c.get(f"/api/projets/{projet}/grilles").json()["grilles"] == []

    # Le classeur juste : le bilan d'avant s'efface, le nouveau dit ce qui va naître.
    page.set_input_files("#pg-fichier", _fichier("signaux.xlsx", juste))
    expect(verdict).to_have_count(0)
    page.get_by_role("button", name="Vérifier").click()
    expect(verdict).to_have_text("Le fichier est juste : l'import peut se faire.")
    expect(page.locator(".pg-declaration")).to_have_text(
        "La grille : « Signaux », fermée, porte sur des mots")
    expect(page.locator(".pg-bilan")).to_contain_text("10 entrées")
    with _http(base) as c:                     # vérifier n'écrit rien
        assert c.get(f"/api/projets/{projet}/grilles").json()["grilles"] == []
    expect(importer).not_to_have_attribute("aria-disabled", "true")
    importer.click()
    expect(verdict).to_have_text("Le fichier est juste, et la grille est importée.")
    expect(page.locator("#pj-grilles-msg")).to_have_text("« Signaux » est importée.")
    ligne = page.locator(".pg-grille", has_text="Signaux")
    expect(ligne.locator(".pj-puce")).to_have_text("brouillon v1")
    expect(page.locator("#pj-grilles-titre")).to_have_text("Grilles · 1")
    with _http(base) as c:
        (g,) = c.get(f"/api/projets/{projet}/grilles").json()["grilles"]
    assert [(v["numero"], v["etat"]) for v in g["versions"]] == [(1, "brouillon")]
    assert ligne.locator(".pg-telecharger").get_attribute("href") == \
        f"/api/grilles/{g['id']}/versions/1/tableur"

    # Publier (confirmé), puis activer, depuis la ligne.
    ligne.get_by_role("button", name="Publier la v1…").click()
    ligne.get_by_role("button", name="Publier la v1", exact=True).click()
    expect(page.locator("#pj-grilles-msg")).to_have_text("La version 1 de « Signaux » est publiée.")
    expect(ligne.locator(".pj-puce")).to_have_text("v1 publiée · pas active")
    expect(ligne.locator(".pg-nom")).to_be_focused()
    ligne.get_by_role("button", name="Activer la v1").click()
    expect(ligne.locator(".pj-puce")).to_have_text("v1 publiée · active")
    with _http(base) as c:
        assert c.get(f"/api/grilles/{g['id']}").json()["active"] == {"numero": 1,
                                                                      "etat": "publiee"}


def test_reimporter_une_ouverte_qui_perd_une_entree_employee_demande_retirer(page,
                                                                            live_server):
    base = live_server
    with _http(base) as c:
        g = grille_active_vivante(c, nom="Libre", ouverte=True)
        gid, projet = g["grille_id"], g["projet_id"]
        aid = c.post("/api/albums", json={"titre": "E2E grilles"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        bulle = c.post(f"/api/planches/{pid}/regions",
                       json={"type": "bulle", "x": 10, "y": 10, "w": 100, "h": 60}).json()["id"]
        c.put(f"/api/regions/{bulle}", json={"ocr_texte": "AAAH ! OUILLE"})
        r = c.post("/api/releves", json={"grille_id": gid, "version": 1, "region_id": bulle,
                                         "entree_cle": "cri", "mots": [0]})
        assert r.status_code == 201, r.text
        classeur = c.get(f"/api/grilles/{gid}/versions/1/tableur").content
    sans_cri = _retouche(classeur, lambda ws: ws.delete_rows(_ligne_de(ws, "cri")[0]))

    _ouvrir(page, base, projet)
    ligne = page.locator(".pg-grille", has_text="Libre")
    expect(ligne.locator(".pj-puce")).to_have_text("ouverte · active")
    ligne.get_by_role("button", name="⤒ Réimporter…").click()
    expect(page.locator("#pg-import-titre")).to_have_text("Réimporter « Libre »")
    page.set_input_files("#pg-fichier", _fichier("libre.xlsx", sans_cri))
    page.get_by_role("button", name="Vérifier").click()
    verdict = page.locator("#pg-verdict")
    expect(verdict).to_contain_text("« retirer » ou « fusionner dans… »")
    choix = page.get_by_label("« cri » disparaît du classeur · 1 relevé posé")
    expect(choix).to_be_visible()
    expect(page.locator(".pg-changements")).to_contain_text("1 relevé posé · à répondre plus bas")
    importer = page.locator("#pg-importer")
    expect(importer).to_have_attribute("aria-disabled", "true")
    expect(page.locator("#pg-importer-raison")).to_have_text(
        "1 entrée à répondre : dites pour chacune « retirer » ou « fusionner dans… ».")
    from test_e2e_a11y import _audit, _fmt     # la liste « À répondre » et « Ce qui change »
    viol = _audit(page)
    assert not viol, f"Administration, bilan d'un réimport :\n{_fmt(viol)}"
    choix.select_option("retirer")
    expect(choix).to_be_focused()
    expect(importer).not_to_have_attribute("aria-disabled", "true")
    importer.click()
    expect(verdict).to_have_text("Le fichier est juste, et la grille est importée.")
    with _http(base) as c:
        plan = c.get(f"/api/grilles/{gid}/versions/1").json()
    cri = next(e for e in plan["entrees"] if e["cle"] == "cri")
    assert cri["retiree"] is True


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_le_bilan_se_lit_sans_violation_ni_defilement_de_cote(page, live_server, theme):
    """Le bilan d'un classeur fautif, et la ligne d'une grille, sous axe (WCAG 2.1 AA) dans
    les deux thèmes ; puis à 320 px, où rien ne défile de côté. Les audits des vues de
    l'Administration ne voient ni grille ni bilan : leur décor n'en a pas."""
    from test_e2e_a11y import _audit, _fmt, _theme
    base = live_server
    with _http(base) as c:
        projet = c.post("/api/projets", json={"nom": "Étude grilles"}).json()["id"]
        grille_active_vivante(c, nom="Libre", ouverte=True, projet_id=projet)

    def libre(ws):
        n, titres = _ligne_de(ws, "cri")
        ws.cell(row=n, column=titres["4. Ce qu'on choisit"] + 1, value="libre")
    _theme(page, theme)
    _ouvrir(page, base, projet)
    expect(page.locator(".pg-grille")).to_have_count(1)
    page.get_by_role("button", name="⤒ Importer un classeur…").click()
    page.set_input_files("#pg-fichier", _fichier("signaux.xlsx", _retouche(_classeur(), libre)))
    page.get_by_role("button", name="Vérifier").click()
    expect(page.locator(".pg-faute")).to_have_count(1)
    viol = _audit(page)
    assert not viol, f"Administration, bloc « Grilles » et bilan [{theme}] :\n{_fmt(viol)}"
    page.set_viewport_size({"width": 320, "height": 800})
    expect(page.locator(".pg-faute")).to_be_visible()
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), \
        "le bloc « Grilles » fait défiler la page de côté à 320 px"
