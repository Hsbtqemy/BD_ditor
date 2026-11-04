"""ANN-7 — le FORMULAIRE de construction d'une grille (Administration › Projets › Grilles ;
l'option HYBRIDE tranchée par Hugo sur maquette le 2026-11-03).

Dans un vrai navigateur, sur les vraies routes :

- construire au formulaire une grille de deux rubriques — la forme attendue (« une
  variante » sans variante) marquée ● et « Publier… » éteint tant qu'elle attend —, la
  publier, l'activer ;
- une entrée EMPLOYÉE s'offre à retirer, jamais à supprimer ; « Fusionner dans… » sur une
  grille ouverte seulement ;
- un 409 de valeur vue ouvre le bandeau de l'application, et la saisie reste dans son champ ;
- « Corriger dans le formulaire ↗ » du bilan d'un réimport mène à l'entrée en faute.

Chaque fois, l'état est RELU par l'API : un écran ne prouve pas ce qui s'est écrit. Les
grilles sont FICTIVES (`tools/grille-modele.csv`)."""
import io
import re
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")
openpyxl = pytest.importorskip("openpyxl")

from playwright.sync_api import expect  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import grille_tableur  # noqa: E402
from conftest import ECRITURE, make_png  # noqa: E402
from grilles_decor import grille_active_vivante  # noqa: E402

pytestmark = pytest.mark.e2e

# UX-10 — le périmètre de cet audit (`tests/test_surfaces.py`).
SURFACES_AUDITEES = ("/administration",)
SURFACES_HORS_PERIMETRE = {
    "/": "le formulaire d'une grille ne vit que dans la fiche d'un projet de l'Administration",
    "/annotation": "la page Annotation pose des relevés ; l'aperçu du formulaire n'en pose pas",
    "/recherche": "le formulaire d'une grille ne vit que dans la fiche d'un projet",
    "/corpus": "le masquage d'une grille par collection, dans la Bibliothèque, n'est pas ici",
    "/exploration": "le formulaire d'une grille ne vit que dans la fiche d'un projet",
}

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _http(base):
    return httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE)


def _ouvrir(page, base, projet, grille=None):
    suite = f"&grille={grille}" if grille else ""
    page.goto(f"{base}/administration?vue=projets&projet={projet}{suite}",
              wait_until="networkidle")
    if grille:
        expect(page.locator(".fm-ed")).to_be_visible(timeout=10000)
    else:
        expect(page.locator("#pg-liste-zone")).not_to_contain_text("Chargement", timeout=10000)


def _noeud(page, nom):
    return page.locator(".fm-plan .fm-noeud").filter(
        has=page.locator(".lf-nom", has_text=re.compile(rf"^{re.escape(nom)}$")))


def _plan(base, gid):
    with _http(base) as c:
        g = c.get(f"/api/grilles/{gid}").json()
        n = max(v["numero"] for v in g["versions"])
        return g, c.get(f"/api/grilles/{gid}/versions/{n}").json()


def _avec_un_releve(c, entree="cri", ouverte=True):
    """La grille fictive active dans le projet de repli, et un relevé sur `entree`."""
    g = grille_active_vivante(c, nom="Libre" if ouverte else "Signaux", ouverte=ouverte)
    aid = c.post("/api/albums", json={"titre": "E2E formulaire"}).json()["id"]
    pid = c.post(f"/api/albums/{aid}/import",
                 files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
    bulle = c.post(f"/api/planches/{pid}/regions",
                   json={"type": "bulle", "x": 10, "y": 10, "w": 100, "h": 60}).json()["id"]
    c.put(f"/api/regions/{bulle}", json={"ocr_texte": "AAAH ! OUILLE"})
    r = c.post("/api/releves", json={"grille_id": g["grille_id"], "version": 1,
                                     "region_id": bulle, "entree_cle": entree, "mots": [0]})
    assert r.status_code == 201, r.text
    return g


def test_construire_une_grille_de_deux_rubriques_la_publier_l_activer(page, live_server):
    base = live_server
    with _http(base) as c:
        projet = c.post("/api/projets", json={"nom": "Étude lieux"}).json()["id"]
    _ouvrir(page, base, projet)
    page.get_by_role("button", name="+ Construire une grille").click()
    expect(page.locator("#fm-g-nom")).to_be_focused()
    creer = page.get_by_role("button", name="Créer la grille")
    expect(creer).to_have_attribute("aria-disabled", "true")
    page.fill("#fm-g-nom", "Lieux")
    page.keyboard.press("Tab")
    page.get_by_label("La case").check()
    expect(creer).not_to_have_attribute("aria-disabled", "true")
    creer.click()
    expect(page.locator("#fm-titre")).to_have_text("Lieux")
    expect(page).to_have_url(re.compile(r"[?&]grille=\d+"))
    with _http(base) as c:
        (g,) = c.get(f"/api/projets/{projet}/grilles").json()["grilles"]
    gid = g["id"]
    assert [(v["numero"], v["etat"]) for v in g["versions"]] == [(1, "brouillon")]

    # Deux rubriques, une entrée dans chacune — chaque nom part quand on quitte son champ.
    page.get_by_role("button", name="+ Rubrique").click()
    page.fill("#fm-r-libelle", "Intérieur")
    page.keyboard.press("Tab")
    expect(_noeud(page, "Intérieur")).to_have_attribute("aria-current", "true")
    page.get_by_role("button", name="+ Entrée").click()
    page.fill("#fm-e-libelle", "domicile")
    page.keyboard.press("Tab")
    expect(_noeud(page, "domicile")).to_have_attribute("aria-current", "true")
    expect(page.locator(".fm-genre")).to_have_text("Entrée · Intérieur")
    # « Une variante » sans variante attend chez le formulaire : ●, et « Publier… » éteint.
    page.get_by_label("Une variante parmi plusieurs").check()
    expect(page.locator(".fm-manque-msg")).to_have_text("● Ajoutez au moins une variante.")
    expect(_noeud(page, "domicile")).to_contain_text("● à compléter")
    publier = page.get_by_role("button", name="Publier la v1…")
    expect(publier).to_have_attribute("aria-disabled", "true")
    with _http(base) as c:                     # rien n'est parti
        dom = next(e for e in c.get(f"/api/grilles/{gid}/versions/1").json()["entrees"])
    assert dom["forme"] == "simple"
    page.fill("#fm-var-neuve", "cuisine")
    page.keyboard.press("Tab")
    expect(page.locator("#fm-var-0-libelle")).to_have_value("cuisine")
    expect(page.locator(".fm-manque-msg")).to_have_count(0)
    page.fill("#fm-var-neuve", "chambre")
    page.keyboard.press("Tab")
    expect(page.locator("#fm-var-1-libelle")).to_have_value("chambre")

    page.get_by_role("button", name="+ Rubrique").click()
    page.fill("#fm-r-libelle", "Extérieur")
    page.keyboard.press("Tab")
    expect(_noeud(page, "Extérieur")).to_have_attribute("aria-current", "true")
    page.get_by_role("button", name="+ Entrée").click()
    page.fill("#fm-e-libelle", "rue")
    page.keyboard.press("Tab")
    expect(_noeud(page, "rue")).to_have_attribute("aria-current", "true")
    page.fill("#fm-e-definition", "une voie de la ville")
    page.keyboard.press("Tab")
    # L'aperçu : la grille telle que la page Annotation la montre, et le guide de l'entrée.
    apercu = page.locator(".fm-apercu")
    expect(apercu.locator(".an-rub-lib")).to_have_text(["Intérieur", "Extérieur"])
    expect(apercu.locator(".an-var")).to_have_text(["cuisine", "chambre"])
    expect(apercu.locator(".fm-ap-guide")).to_contain_text("une voie de la ville")
    expect(page.locator("#fm-enreg")).to_have_text("✓ enregistré")

    expect(publier).not_to_have_attribute("aria-disabled", "true")
    publier.click()
    page.locator("#fm-publier-ok").click()
    expect(page.locator("#pj-formulaire-msg")).to_contain_text("La version 1 est publiée")
    activer = page.get_by_role("button", name="Activer la v1")
    activer.click()
    expect(page.locator("#pj-formulaire-msg")).to_contain_text("active dans le projet")
    g, plan = _plan(base, gid)
    assert g["active"] == {"numero": 1, "etat": "publiee"}
    assert [r["libelle"] for r in plan["rubriques"]] == ["Intérieur", "Extérieur"]
    assert [(e["libelle"], e["rubriques"], e["forme"]) for e in plan["entrees"]] == [
        ("domicile", [plan["rubriques"][0]["cle"]], "variantes"),
        ("rue", [plan["rubriques"][1]["cle"]], "simple")]
    assert [v["libelle"] for v in plan["entrees"][0]["variantes"]] == ["cuisine", "chambre"]
    assert plan["porte_sur"] == ["case"]

    # Réordonner, à la souris (↓) puis au clavier (Alt + ↑ sur la ligne du plan) : sur une
    # grille fermée publiée, l'ordre s'écrit dans un brouillon neuf.
    _noeud(page, "Intérieur").click()
    page.get_by_role("button", name="Descendre Intérieur").click()
    expect(page.locator(".fm-apercu .an-rub-lib")).to_have_text(["Extérieur", "Intérieur"])
    with _http(base) as c:
        v2 = c.get(f"/api/grilles/{gid}/versions/2").json()
    assert v2["etat"] == "brouillon"
    assert [r["libelle"] for r in v2["rubriques"]] == ["Extérieur", "Intérieur"]
    _noeud(page, "Intérieur").focus()
    page.keyboard.press("Alt+ArrowUp")
    expect(page.locator(".fm-apercu .an-rub-lib")).to_have_text(["Intérieur", "Extérieur"])
    expect(_noeud(page, "Intérieur")).to_be_focused()
    with _http(base) as c:
        v2 = c.get(f"/api/grilles/{gid}/versions/2").json()
    assert [r["libelle"] for r in v2["rubriques"]] == ["Intérieur", "Extérieur"]

    # « ← » ramène à la fiche du projet, sur « Modifier… » de la grille.
    page.get_by_role("button", name="← Étude lieux").click()
    expect(page.locator(f'[data-gr-modifier="{gid}"]')).to_be_focused()
    expect(page).not_to_have_url(re.compile(r"[?&]grille="))


def test_une_entree_employee_se_retire_et_ne_s_offre_jamais_a_supprimer(page, live_server):
    base = live_server
    with _http(base) as c:
        g = _avec_un_releve(c)
    gid, projet = g["grille_id"], g["projet_id"]
    _ouvrir(page, base, projet, gid)
    _noeud(page, "cri").click()
    expect(page.locator("#fm-e-libelle")).to_have_value("cri")
    expect(page.locator(".fm-note")).to_have_text("1 relevé la porte.")
    gestes = page.locator(".fm-gestes-objet")
    expect(gestes.get_by_role("button", name="Supprimer l'entrée…")).to_have_count(0)
    expect(gestes.get_by_role("button", name="Retirer")).to_be_visible()
    expect(gestes.get_by_role("button", name="Fusionner dans…")).to_be_visible()
    # Sous son relevé, sur une ouverte, sa forme ne change pas : la réponse est éteinte.
    expect(page.locator("#fm-forme-variantes")).to_be_disabled()
    # Une entrée que personne n'emploie, elle, se supprime.
    _noeud(page, "regard caméra").click()
    expect(page.locator(".fm-gestes-objet").get_by_role("button", name="Supprimer l'entrée…")
           ).to_be_visible()
    _noeud(page, "cri").click()
    page.locator(".fm-gestes-objet").get_by_role("button", name="Retirer").click()
    expect(page.locator(".fm-note")).to_have_text(
        "Retirée : elle ne se pose plus ; 1 relevé la porte, à revoir.")
    expect(page.locator(".fm-gestes-objet").get_by_role("button", name="Remettre en usage")
           ).to_be_visible()
    expect(page.locator(".fm-gestes-objet").get_by_role("button", name="Supprimer l'entrée…")
           ).to_have_count(0)
    _, plan = _plan(base, gid)
    assert next(e for e in plan["entrees"] if e["cle"] == "cri")["retiree"] is True


def test_sur_une_fermee_fusionner_ne_s_offre_pas(page, live_server):
    base = live_server
    with _http(base) as c:
        g = _avec_un_releve(c, ouverte=False)
    _ouvrir(page, base, g["projet_id"], g["grille_id"])
    expect(page.locator(".fm-tete .pj-puce").first).to_have_text(
        "v1 publiée · un brouillon v2 naîtra au premier changement")
    _noeud(page, "cri").click()
    gestes = page.locator(".fm-gestes-objet")
    expect(gestes.get_by_role("button", name="Retirer")).to_be_visible()
    expect(gestes.get_by_role("button", name="Fusionner dans…")).to_have_count(0)
    expect(gestes.get_by_role("button", name="Supprimer l'entrée…")).to_have_count(0)
    gestes.get_by_role("button", name="Retirer").click()
    expect(page.locator(".fm-tete .pj-puce").first).to_have_text("brouillon v2")
    with _http(base) as c:
        v2 = c.get(f"/api/grilles/{g['grille_id']}/versions/2").json()
    assert next(e for e in v2["entrees"] if e["cle"] == "cri")["retiree"] is True


def test_un_409_de_valeur_vue_garde_la_saisie(page, live_server):
    base = live_server
    with _http(base) as c:
        g = grille_active_vivante(c, nom="Libre", ouverte=True)
    gid = g["grille_id"]
    _ouvrir(page, base, g["projet_id"], gid)
    _noeud(page, "cri").click()
    expect(page.locator("#fm-e-libelle")).to_have_value("cri")
    # Un autre écran change la définition après que celui-ci l'a lue.
    with _http(base) as c:
        r = c.patch(f"/api/grilles/{gid}/entrees/cri", json={"definition": "l'autre"})
        assert r.status_code == 200, r.text
    page.fill("#fm-e-definition", "la mienne")
    page.keyboard.press("Tab")
    titre = page.locator("#fm-conflit-titre")
    expect(titre).to_be_visible()
    expect(titre).to_contain_text("Définition modifiée")
    expect(page.locator(".fm-conflit")).to_contain_text("Version enregistrée : l'autre")
    expect(page.locator("#fm-e-definition")).to_have_value("la mienne")
    _, plan = _plan(base, gid)
    assert next(e for e in plan["entrees"] if e["cle"] == "cri")["definition"] == "l'autre"
    page.get_by_role("button", name="Remplacer par la mienne").click()
    expect(page.locator(".fm-conflit")).to_have_count(0)
    expect(page.locator("#fm-e-definition")).to_have_value("la mienne")
    _, plan = _plan(base, gid)
    assert next(e for e in plan["entrees"] if e["cle"] == "cri")["definition"] == "la mienne"


def _retouche(data: bytes, retouche) -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(data))
    retouche(wb[grille_tableur.FEUILLE_ENTREES])
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def test_corriger_dans_le_formulaire_mene_a_l_entree_en_faute(page, live_server):
    base = live_server
    with _http(base) as c:
        g = grille_active_vivante(c, nom="Libre", ouverte=True)
        classeur = c.get(f"/api/grilles/{g['grille_id']}/versions/1/tableur").content

    def libre(ws):
        titres = None
        for ligne in ws.iter_rows():
            valeurs = [x.value for x in ligne]
            if titres is None and "Entrée" in valeurs:
                titres = {v: i for i, v in enumerate(valeurs) if v}
                continue
            if titres is not None and valeurs[titres["Entrée"]] == "cri":
                ws.cell(row=ligne[0].row, column=titres["4. Ce qu'on choisit"] + 1, value="libre")
                return
        raise AssertionError("« cri » introuvable")
    fautif = _retouche(classeur, libre)
    _ouvrir(page, base, g["projet_id"])
    ligne = page.locator(".pg-grille", has_text="Libre")
    ligne.get_by_role("button", name="⤒ Réimporter…").click()
    page.set_input_files("#pg-fichier", {"name": "libre.xlsx", "mimeType": XLSX,
                                         "buffer": fautif})
    page.get_by_role("button", name="Vérifier").click()
    faute = page.locator(".pg-faute")
    expect(faute).to_have_count(1)
    faute.get_by_role("button", name="Corriger dans le formulaire ↗").click()
    expect(page.locator(".fm-ed")).to_be_visible()
    expect(_noeud(page, "cri")).to_have_attribute("aria-current", "true")
    expect(page.locator("#fm-e-libelle")).to_have_value("cri")
    expect(page).to_have_url(re.compile(rf"[?&]grille={g['grille_id']}(?!\d)"))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_le_formulaire_se_lit_sans_violation_et_dit_quand_il_est_trop_etroit(page, live_server,
                                                                          theme):
    """Le formulaire ouvert sur une entrée à variantes, sous axe (WCAG 2.1 AA), dans les deux
    thèmes ; puis à 700 px, où il le DIT au lieu de se tasser, sans défilement de côté."""
    from test_e2e_a11y import _audit, _fmt, _theme
    base = live_server
    with _http(base) as c:
        g = grille_active_vivante(c, nom="Libre", ouverte=True)
    _theme(page, theme)
    _ouvrir(page, base, g["projet_id"], g["grille_id"])
    _noeud(page, "onomatopée de choc").click()
    expect(page.locator("#fm-var-0-libelle")).to_be_visible()
    viol = _audit(page)
    assert not viol, f"Administration, formulaire d'une grille [{theme}] :\n{_fmt(viol)}"
    page.set_viewport_size({"width": 700, "height": 800})
    expect(page.locator(".fm-etroit")).to_be_visible()
    expect(page.locator(".fm-ed")).to_be_hidden()
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), \
        "le formulaire fait défiler la page de côté à 700 px"
