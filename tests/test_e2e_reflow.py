"""WCAG 2.1 AA — 1.4.10 « Reflow » : la garde qu'axe ne peut pas poser (UX-7).

Le dépôt revendique AA et l'audite avec axe (`test_e2e_a11y.py`). Or **axe ne teste pas
le 1.4.10**, qui n'est pas automatisable en général : il faut décider ce que « utilisable »
veut dire. La suite était donc verte sans rien dire à ce sujet — pas un échec signalé, un
silence pris pour un succès, ce qui est le pire des deux cas. Ce fichier comble ce
silence-là, et rien d'autre.

**Ce test ne regarde PAS `documentElement.scrollWidth`**, et c'est le point qui l'a fait
exister. La fiche UX-7 spécifiait au départ une garde écrite dessus ; elle aurait été
VACANTE. `static/style.css` pose `html, body { overflow: hidden }` — nécessaire à quatre
coques pleine hauteur —, si bien que le débordement est CLIPPÉ et que `scrollWidth` reste
égal à `clientWidth` pendant que 431 px de contenu sont hors champ. Mesuré le 2026-09-04 :
les quatre surfaces passaient cette garde-là au vert dans un état où un tiers de l'écran
de la Visionneuse était inatteignable. `test_la_garde_sur_scrollwidth_serait_vacante`
ci-dessous en fait une DÉMONSTRATION plutôt qu'une affirmation de docstring.

On compare donc le RECTANGLE de chaque élément à la largeur de la fenêtre, et on distingue
trois états que le rectangle seul confond :

- **encadré** — un ancêtre défile horizontalement et tient dans l'écran. Le 1.4.10 TOLÈRE
  explicitement ce cas pour un contenu à deux dimensions (un tableau). Conforme.
- **escamoté** — entièrement hors champ ET référencé par un `aria-controls`. C'est un
  tiroir fermé, et le contrôle EST le chemin de retour. Conforme.
- **perdu** — tout le reste. C'est ce que le test refuse.

La sonde est IMPORTÉE de `tools/mesurer_reflow.py` et non recopiée : c'est la même règle,
et deux exemplaires d'une même règle divergent au premier correctif — un seul serait
corrigé le jour où l'on apprend quelque chose. L'outil balaie sept largeurs pour
l'exploration ; le test en garde deux, les deux canoniques du critère.
"""
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ADMIN, make_png            # noqa: E402
from tools.mesurer_reflow import SONDE          # noqa: E402

pytestmark = pytest.mark.e2e

# Les deux largeurs du critère. 320 px est celle qu'il NOMME (une fenêtre de 1280 px à
# 400 % de zoom) ; 768 px est la tablette, où le chantier avait cru n'avoir rien à faire
# — à tort, la Visionneuse n'y laissant que 228 px de canevas avant les tiroirs.
LARGEURS = [320, 768]


@pytest.fixture
def decor(live_server):
    """Album + planche + bulle annotée, pour que les surfaces aient quelque chose à rendre.

    Volontairement NON partagé avec `test_e2e_a11y.seeded`, qui lui ressemble : ce
    module-là se skippe entier quand axe est absent du dossier vendu, et en importer une
    fixture ferait dépendre la mesure du reflow de la présence d'axe-core — deux
    conditions sans aucun rapport. Ce qu'il ne fallait pas dupliquer, c'est la RÈGLE
    (`SONDE`), pas huit lignes de décor.
    """
    c = httpx.Client(base_url=live_server, trust_env=False, timeout=30, headers=ADMIN)
    try:
        aid = c.post("/api/albums", json={"titre": "Reflow", "auteur": "X"}).json()["id"]
        pid = c.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", make_png(), "image/png")}).json()["id"]
        rid = c.post(f"/api/planches/{pid}/regions",
                     json={"type": "bulle", "x": 10, "y": 10, "w": 120, "h": 80}).json()["id"]
        # Même délai généreux que le décor d'a11y, et pour la même raison : écrire l'OCR
        # déclenche la réindexation, donc le chargement à froid de spaCy (~10 s).
        c.put(f"/api/regions/{rid}", json={"ocr_texte": "POUVOIR ABSOLU"}, timeout=180)
        c.put(f"/api/regions/{rid}/annotation", json={"note": "colère", "tags": ["emotion"]})
    finally:
        c.close()
    return {"base": live_server, "album": aid, "planche": pid, "region": rid}


# La Recherche est visée AVEC une requête, et ce n'est pas un détail : au repos elle ne
# rend aucun résultat, donc ni `.r-thumb` ni `.result`. Trois largeurs figées ont vécu des
# mois sans être mesurées pour exactement cette raison — ce que la page ne rend pas,
# l'instrument ne le voit pas (UX-7, 2026-09-05).
SURFACES = {
    "visionneuse": lambda d: f"/?album={d['album']}&planche={d['planche']}&region={d['region']}",
    "recherche":   lambda d: "/recherche?q=pouvoir",
    "corpus":      lambda d: "/corpus",
    "exploration": lambda d: "/exploration?champ=lemme",
}


# Une exemption NOMMÉE, sur le modèle de `HORS_PERIMETRE` (test_autorisation) et de
# `BLOCAGES_ADMIS` (test_csp) : ce qui sort du périmètre le fait par DÉCISION ÉCRITE, pas
# parce qu'une règle astucieuse l'a avalé au passage. Une règle générale « surface de
# pan » excuserait n'importe quel conteneur en `overflow: hidden`, c'est-à-dire les quatre
# coques de l'application.
EXEMPTIONS = {
    "canvas": (
        "surface de PAN/ZOOM de la Visionneuse. Le 1.4.10 exempte explicitement le contenu "
        "qui exige une disposition à deux dimensions — une image en fait partie, et un scan "
        "de planche est l'image même qu'on est venu regarder. Son atteignabilité ne vient "
        "pas d'un cadre défilant mais du GESTE : glisser dans `#stage`, plus quatre commandes "
        "de zoom dont « Ajuster ». `test_la_surface_de_pan_reste_bornee_et_commandee` "
        "vérifie que ces deux conditions tiennent, sans quoi l'exemption deviendrait "
        "une excuse."),
}

# Les commandes qui rendent le canevas atteignable sans souris. Le glisser ne suffirait
# pas — le 1.4.10 se lit avec le 2.1.1 (tout au clavier) —, et c'est `#zoom-fit`
# (« Ajuster ») qui porte la charge : les trois autres déplacent l'échelle, lui seul
# garantit que la planche ENTIÈRE rentre. On exige les quatre parce que retirer Ajuster
# en laissant les autres passerait autrement inaperçu.
COMMANDES_CANEVAS = ["#zoom-out", "#zoom-in", "#zoom-fit", "#zoom-reset"]


def _sonder(page, decor, surface, largeur):
    page.set_viewport_size({"width": largeur, "height": 900})
    page.goto(decor["base"] + SURFACES[surface](decor), wait_until="networkidle")
    page.wait_for_timeout(400)          # les surfaces peuplent leur DOM après le chargement
    return page.evaluate(SONDE)


def _decrire(coupables):
    lignes = []
    for c in coupables:
        ident = (f"#{c['id']}" if c["id"] else (f".{c['cls']}" if c["cls"] else ""))
        lignes.append(f"  <{c['tag']}>{ident} — {c['largeur']} px, dépasse de {c['depasse']} px")
    return "\n".join(lignes)


@pytest.mark.parametrize("largeur", LARGEURS)
@pytest.mark.parametrize("surface", list(SURFACES))
def test_aucune_surface_ne_perd_de_contenu(page, decor, surface, largeur):
    """À 320 et 768 px, aucun élément n'est hors champ sans cadre ni bascule."""
    r = _sonder(page, decor, surface, largeur)
    perdus = [c for c in r["coupables"]
              if not c["cadre"] and c["id"] not in EXEMPTIONS]
    assert not perdus, (
        f"{surface} à {largeur} px — contenu INATTEIGNABLE (1.4.10) :\n{_decrire(perdus)}")


def test_la_surface_de_pan_reste_bornee_et_commandee(page, decor):
    """Ce que l'exemption de `#canvas` doit continuer de mériter.

    Deux conditions, et elles ne se recouvrent pas. Le conteneur qui CLIPPE doit tenir
    dans la fenêtre — sinon ce n'est plus un cadre de pan, c'est la page qui déborde. Et
    le déplacement doit être COMMANDABLE, faute de quoi l'exemption reposerait sur un
    geste de souris que le 2.1.1 n'accepte pas.

    Trouvé en écrivant le test : le balayage de `tools/mesurer_reflow.py` charge `/` SANS
    album, donc sans image, donc avec un canevas minuscule — il n'a jamais vu ce cas. Le
    test, lui, charge une planche, et `#canvas` y fait 800 px pour 768 de fenêtre.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + SURFACES["visionneuse"](decor), wait_until="networkidle")
    page.wait_for_timeout(400)
    r = page.evaluate("""(commandes) => {
      const st = document.querySelector('#stage');
      const b = st.getBoundingClientRect(), large = document.documentElement.clientWidth;
      return {
        clippe: getComputedStyle(st).overflowX === 'hidden',
        borne: b.left >= -1 && b.right <= large + 1,
        rect: [Math.round(b.left), Math.round(b.right)], large,
        manquantes: commandes.filter(s => !document.querySelector(s)),
      };
    }""", COMMANDES_CANEVAS)
    assert r["clippe"], (
        "`#stage` ne clippe plus : `#canvas` n'est donc plus une surface de pan, et son "
        "exemption dans EXEMPTIONS ne décrit plus la réalité")
    assert r["borne"], (
        f"le conteneur de pan déborde lui-même ({r['rect']} pour {r['large']} px) : ce "
        "n'est plus le canevas qui dépasse dans son cadre, c'est le cadre qui dépasse")
    assert not r["manquantes"], (
        f"commandes de déplacement absentes : {r['manquantes']} — l'exemption de "
        "`#canvas` reposerait alors sur le seul glisser-déposer à la souris")


def test_la_garde_sur_scrollwidth_serait_vacante(page, decor):
    """La garde que la fiche spécifiait d'abord aurait approuvé une page amputée.

    Démonstration et non affirmation : on plante un bloc de 900 px dans une fenêtre de
    320, sous `overflow: hidden`. `scrollWidth` reste égal à `clientWidth` — la garde
    naïve passe — pendant que la sonde, elle, le signale comme perdu. Sans ce test, la
    docstring ci-dessus serait une croyance, et le jour où quelqu'un « simplifierait » la
    sonde en revenant à `scrollWidth`, la suite resterait verte.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.evaluate("""() => {
      const d = document.createElement('div');
      d.id = 'temoin-large';
      d.style.cssText = 'width:900px;height:40px;background:#f00';
      document.body.appendChild(d);
    }""")
    r = page.evaluate(SONDE)
    assert r["scrollWidth"] == r["clientWidth"], (
        "prémisse fausse : `overflow: hidden` ne clippe plus, et la garde naïve "
        "verrait peut-être quelque chose — ce test doit alors être repensé, pas supprimé")
    assert any(c["id"] == "temoin-large" for c in r["coupables"]), (
        "la sonde n'a pas vu un bloc de 900 px dans une fenêtre de 320 : elle ne mesure "
        f"plus ce qu'elle prétend.\n{_decrire(r['coupables'])}")


def test_un_panneau_escamote_n_est_pas_compte_comme_perdu(page, decor):
    """Contrôle POSITIF de l'exemption : un tiroir fermé est conforme.

    Sans lui, `test_aucune_surface_ne_perd_de_contenu` pourrait passer au vert parce que
    l'exemption avale TOUT, et non parce que les surfaces sont saines.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.evaluate("""() => {
      const d = document.createElement('div');
      d.id = 'faux-tiroir';
      d.style.cssText = 'position:fixed;top:0;left:-400px;width:300px;height:40px';
      document.body.appendChild(d);
      const b = document.createElement('button');
      b.setAttribute('aria-controls', 'faux-tiroir');
      document.body.appendChild(b);
    }""")
    r = page.evaluate(SONDE)
    assert not any(c["id"] == "faux-tiroir" for c in r["coupables"])


def test_un_panneau_hors_champ_sans_bascule_est_signale(page, decor):
    """Contrôle NÉGATIF, et c'est le vrai : l'exemption exige le CHEMIN DE RETOUR.

    Écrite sur la seule position — « entièrement hors de la fenêtre, donc escamoté » —,
    elle excusait n'importe quel panneau qu'aucun geste ne ramène, c'est-à-dire exactement
    la violation cherchée. Trouvé dans une passe de revue le 2026-09-05, sur l'instrument
    lui-même. Le même bloc que le test précédent, privé de son `aria-controls`, doit être
    SIGNALÉ.
    """
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(decor["base"] + "/corpus", wait_until="networkidle")
    page.evaluate("""() => {
      const d = document.createElement('div');
      d.id = 'tiroir-sans-bascule';
      d.style.cssText = 'position:fixed;top:0;left:-400px;width:300px;height:40px';
      document.body.appendChild(d);
    }""")
    r = page.evaluate(SONDE)
    assert any(c["id"] == "tiroir-sans-bascule" for c in r["coupables"]), (
        "un panneau hors champ qu'aucun contrôle ne référence a été EXEMPTÉ : "
        "l'exemption est redevenue positionnelle")
