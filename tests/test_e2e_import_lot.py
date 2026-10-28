"""UX-11 — importer des planches EN LOT depuis la fiche d'un album, dans un vrai navigateur.

La Bibliothèque est le lieu où l'on CONSTITUE un corpus : ses planches y entrent par
dizaines, là où l'Atelier en ajoute une à l'unité. Ce que ce fichier mesure, sous des
identités derrière le proxy :

- le bouton ouvre un sélecteur à choix MULTIPLE ;
- les fichiers partent UN PAR UN, dans l'ordre de leurs noms — pas dans celui que rend le
  sélecteur —, chacun par la route de l'Atelier, avec l'en-tête anti-CSRF ;
- la progression dit « n sur N » et le nom en cours, puis un bilan ;
- un fichier refusé se NOMME, et les suivants partent quand même ;
- la liste et la fiche se mettent à jour sans recharger la page, les planches numérotées
  dans l'ordre des noms ;
- aucun bouton pour qui ne fait que lire l'album.

Les images sont fabriquées ici, de largeurs distinctes : c'est la largeur relue au serveur
qui dit quelle image est devenue quelle planche.
"""
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
    "/annotation": "l'import en lot vit dans la fiche d'un album, dans la Bibliothèque",
    "/": "l'Atelier garde son import à l'unité, inchangé par ce chantier ; ses entrées sont "
         "mesurées par test_e2e_atelier_album.py",
    "/recherche": "aucun import : la Recherche lit le corpus",
    "/exploration": "aucun import : l'Exploration compte le corpus",
    "/administration": "« Importer au fonds » y est un geste d'administrateur à part, "
                       "mesuré par test_e2e_fonds.py",
}

# Le journal de la ligne d'état : chaque texte qu'elle a porté, dans l'ordre. La ligne est
# redessinée avec la fiche ; on lit donc les nœuds AJOUTÉS, chacun avec sa valeur du moment.
_JOURNAL = """() => {
  window.__etats = [];
  const noter = (t) => { const v = (t || '').trim(); const l = window.__etats;
                         if (v && l[l.length - 1] !== v) l.push(v); };
  new MutationObserver((recs) => {
    for (const r of recs) {
      for (const n of r.addedNodes) {
        if (n.nodeType === 3 && n.parentElement && n.parentElement.id === 'bi-import-etat')
          noter(n.data);
        else if (n.nodeType === 1) {
          const e = n.id === 'bi-import-etat' ? n : n.querySelector && n.querySelector('#bi-import-etat');
          if (e) noter(e.textContent);
        }
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
}"""


def _decor(base):
    """« Étude », où sam écrit, et « Lecture », que sam et lina ne font que lire ; un album
    vide dans chacune."""
    with httpx.Client(base_url=base, trust_env=False, timeout=60, headers=ECRITURE) as c:
        ids = {}
        for nom in ("Étude", "Lecture"):
            ids[nom] = c.post("/api/collections", json={"nom": nom}).json()["id"]
        for cid, qui, niveau in ((ids["Étude"], "sam", "ecriture"),
                                 (ids["Lecture"], "sam", "lecture"),
                                 (ids["Lecture"], "lina", "lecture")):
            du_projet(c, cid, "utilisateur", qui, headers=ECRITURE)
            r = c.put(f"/api/collections/{cid}/acces",
                      json={"genre": "utilisateur", "principal": qui, "niveau": niveau})
            assert r.status_code == 200, r.text
        albums = {}
        for titre, nom in (("Ecrit", "Étude"), ("Lu", "Lecture")):
            r = c.post("/api/albums", json={"titre": titre, "collection_id": ids[nom]})
            assert r.status_code == 201, r.text
            albums[titre] = r.json()["id"]
    return albums


def _ouvrir(page, base, qui, titre):
    page.set_extra_http_headers({"Remote-User": qui})
    page.goto(base + "/corpus", wait_until="networkidle")
    page.locator(".album-row", has_text=titre).first.click()
    expect(page.locator("#album-titre")).to_contain_text(titre)


def _png(nom, largeur):
    return {"name": nom, "mimeType": "image/png", "buffer": make_png(largeur, 300)}


def test_importer_quatre_fichiers_depuis_la_fiche_d_un_album(page, live_server):
    albums = _decor(live_server)
    _ouvrir(page, live_server, "sam", "Ecrit")
    page.evaluate("() => { window.__sans_rechargement = 1; }")
    page.evaluate(_JOURNAL)
    # Le nom de chaque fichier envoyé, lu dans le corps au départ : Playwright ne rend pas le
    # corps d'une requête qui porte un fichier (`post_data_buffer` vaut None).
    page.evaluate("""() => { window.__envois = []; const f = window.fetch;
      window.fetch = (u, o) => { if (o && o.body instanceof FormData)
        window.__envois.push(o.body.get('file').name); return f(u, o); }; }""")
    envois = []
    page.on("request", lambda r: envois.append(r)
            if r.method == "POST" and r.url.endswith(f"/api/albums/{albums['Ecrit']}/import")
            else None)

    bouton = page.locator("#bi-importer")
    expect(bouton).to_be_visible()
    expect(bouton).to_have_text("⤓ Importer des planches…")
    with page.expect_file_chooser() as choix:
        bouton.click()
    assert choix.value.is_multiple(), "le sélecteur ne laisse choisir qu'un fichier"
    # L'ordre du SÉLECTEUR, volontairement mélangé ; p2 n'est pas une image.
    choix.value.set_files([
        _png("p10.png", 310),
        _png("p3.png", 330),
        {"name": "p2.png", "mimeType": "image/png", "buffer": b"ceci n'est pas une image"},
        _png("p1.png", 340),
    ])

    etat = page.locator("#bi-import-etat")
    expect(etat).to_have_text("3 planches importées, 1 échec", timeout=30000)
    echecs = page.locator(".bi-import-echecs li")
    expect(echecs).to_have_count(1)
    # Le refus se dit en mots et nomme son fichier, une fois (UX-11, 2026-10-22).
    expect(echecs.first).to_have_text("p2.png n'est pas une image lisible : son format n'est "
                                      "pas reconnu, ou le fichier est abîmé.")
    # Quel fichier est devenu quelle planche, dans l'ordre d'envoi.
    expect(page.locator(".bi-import-planches li")).to_have_text(
        ["p1.png → planche 1", "p3.png → planche 2", "p10.png → planche 3"])
    expect(bouton).to_be_enabled()

    # La progression a dit chaque fichier, dans l'ordre des noms, puis le bilan.
    assert page.evaluate("() => window.__etats") == [
        "Import : 1 sur 4 — p1.png",
        "Import : 2 sur 4 — p2.png",
        "Import : 3 sur 4 — p3.png · 1 échec",
        "Import : 4 sur 4 — p10.png · 1 échec",
        "3 planches importées, 1 échec",
    ]

    # Quatre requêtes, une par fichier, dans l'ordre des noms, chacune avec l'en-tête.
    noms = page.evaluate("() => window.__envois")
    assert noms == ["p1.png", "p2.png", "p3.png", "p10.png"], noms
    assert len(envois) == 4, [r.url for r in envois]
    assert all(r.headers.get("x-bd-requete") == "1" for r in envois)

    # La fiche et la liste ont suivi, sans rechargement.
    assert page.evaluate("() => window.__sans_rechargement") == 1
    expect(page.locator("#album-detail input[data-pid]")).to_have_count(3)
    expect(page.locator(".album-row", has_text="Ecrit").locator(".lf-etat")).to_have_text("3 pl.")
    expect(page.locator("#corpus-stats")).to_contain_text("3 planches")

    # Au serveur : trois planches, numérotées dans l'ordre des noms (p1, p3, p10).
    with httpx.Client(base_url=live_server, trust_env=False, timeout=30,
                      headers=ECRITURE) as c:
        planches = c.get(f"/api/albums/{albums['Ecrit']}/planches").json()
    assert [(p["numero"], p["largeur_px"]) for p in planches] == [(1, 340), (2, 330), (3, 310)]


@pytest.mark.parametrize("qui", ["lina", "sam"])
def test_aucun_bouton_d_import_pour_qui_ne_fait_que_lire(page, live_server, qui):
    """lina ne fait que lire ; sam écrit ailleurs, mais ne fait que LIRE cet album. Le
    bouton suit `ecrivable` de l'album, pas un droit d'écrire quelque part."""
    _decor(live_server)
    _ouvrir(page, live_server, qui, "Lu")
    expect(page.locator("#album-detail")).to_be_visible()
    expect(page.locator("#bi-importer")).to_have_count(0)
    expect(page.locator("#bi-import")).to_have_count(0)
