"""Comparaison A/B : la mesure de classement se choisit, voyage dans l'URL et part avec
l'export (ANA-4).

Ce qu'aucun test d'API ne voit : que le sélecteur n'apparaît qu'en comparaison, que la
BARRE suit la mesure choisie — sans quoi un classement par keyness s'afficherait avec
les longueurs de l'autre mesure, et l'écran contredirait son propre ordre —, que l'URL
restaure le choix au rechargement, et que le fichier exporté trie comme l'écran.

Les tokens sont semés EN DIRECT dans la base du serveur live : la couche spaCy est
optionnelle, et un classement ne se vérifie que sur des comptes qu'on a choisis.
"""
import sqlite3

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

from conftest import ECRITURE, make_png  # noqa: E402

pytestmark = pytest.mark.e2e

SURFACES_AUDITEES = ("/exploration",)
SURFACES_HORS_PERIMETRE = {
    "/": "l'Atelier n'a pas de comparaison de sous-corpus : elle ne vit que dans l'Exploration",
    "/recherche": "la Recherche ne compare pas deux sous-corpus",
    "/corpus": "la Bibliothèque ne compare pas deux sous-corpus",
    "/administration": "l'Administration ne compare pas deux sous-corpus",
}

# A et B, de même taille (32 tokens) : l'écart relatif met « le » en tête de A, la
# log-vraisemblance y met « otage » — le jeu de `tests/test_vraisemblance.py`.
MOTS = {"colère": ["le"] * 30 + ["otage"] * 2, "joie": ["le"] * 24 + ["chat"] * 8}


@pytest.fixture
def corpus_compare(live_server, tmp_path):
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ECRITURE)
    try:
        aid = c.post("/api/albums", json={"titre": "Comparaison"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        regions = {}
        for tag in MOTS:
            rid = c.post(f"/api/planches/{pid}/regions",
                         json={"type": "bulle", "x": 10, "y": 10, "w": 50, "h": 40}).json()["id"]
            c.put(f"/api/regions/{rid}/annotation", json={"note": "", "tags": [tag]})
            regions[rid] = MOTS[tag]
    finally:
        c.close()
    # APRÈS l'annotation, qui réindexe : même base que le serveur (`live_server`).
    conn = sqlite3.connect(tmp_path / "live.sqlite")
    try:
        conn.executemany(
            "INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
            "VALUES (?, ?, ?, ?, 'X', '')",
            [(rid, o, m.upper(), m) for rid, liste in regions.items()
             for o, m in enumerate(liste)])
        conn.commit()
    finally:
        conn.close()
    return live_server


def _tete_de_a(page):
    return page.locator("#comparaison .col-a .dist-label").first.inner_text()


def test_la_keyness_se_choisit_voyage_dans_l_url_et_part_avec_l_export(page, corpus_compare):
    from test_e2e_a11y import _audit, _fmt      # axe absent : ce module-là se saute entier
    page.goto(f"{corpus_compare}/exploration?vue=comparaison&champ=lemme"
              "&tags=col%C3%A8re&b_tags=joie", wait_until="networkidle")
    page.wait_for_selector("#comparaison .col-a .dist-row")
    assert page.locator("#wrap-metrique").is_visible()
    assert _tete_de_a(page) == "le"                    # le défaut n'a pas changé
    assert "metrique" not in page.url

    page.select_option("#f-metrique", "ll")
    page.wait_for_function(
        "() => document.querySelector('#comparaison .col-a .dist-label')?.textContent === 'otage'",
        timeout=8000)
    assert "metrique=ll" in page.url
    assert "log-vraisemblance" in page.locator("#dist-info").inner_text()
    # La barre suit la mesure : en keyness, la tête a la plus longue. Mesurées à l'écart,
    # « otage » n'aurait qu'un tiers de celle de « le » (0,0625 contre 0,1875). Lues en
    # NOMBRES : le navigateur normalise « 100.0% » en « 100% » en relisant le style.
    largeurs = page.locator("#comparaison .col-a .bar-a").evaluate_all(
        "els => els.map(e => parseFloat(e.style.width))")
    assert largeurs[0] == 100 and largeurs[1] < 50, largeurs

    page.reload(wait_until="networkidle")
    page.wait_for_selector("#comparaison .col-a .dist-row")
    assert page.locator("#f-metrique").input_value() == "ll"
    assert _tete_de_a(page) == "otage"

    with page.expect_download() as telechargement:
        page.click("#btn-export-analyse")
    assert "metrique=ll" in telechargement.value.url

    viol = _audit(page)
    assert not viol, f"Comparaison classée par keyness :\n{_fmt(viol)}"


def test_le_selecteur_de_mesure_n_apparait_qu_en_comparaison(page, corpus_compare):
    """« Classer par » n'a de sens que pour la comparaison : ailleurs, il proposerait un
    réglage qui ne change rien à l'écran."""
    page.goto(f"{corpus_compare}/exploration?vue=distribution", wait_until="networkidle")
    assert page.locator("#wrap-metrique").is_hidden()
    page.select_option("#f-vue", "comparaison")
    assert page.locator("#wrap-metrique").is_visible()
    page.select_option("#f-vue", "concordance")
    assert page.locator("#wrap-metrique").is_hidden()
