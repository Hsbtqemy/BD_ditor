"""UX-6 — chaque zone que la visite NOMME a sa marque sur sa surface.

La visite guidée surlignée a été RETENUE par Hugo le 2026-11-02, contre le refus que la
fiche tenait depuis le 2026-08-27 : elle se couple au balisage des six surfaces, que les
chantiers d'interface déplacent. Ce couplage devient une dépendance à tenir, et ce test la
tient (`pilotage/UX-6.md`, « Chaque zone de la visite a une marque stable ») : un écran
remanié qui perd l'élément d'une zone fait échouer la suite, au lieu de faire disparaître
la zone du guide sans bruit.

La marque est un attribut, `data-parcours="<marque>"`, posé soit dans le GABARIT de la
surface, soit par un SCRIPT que ce gabarit charge (la bande du haut : `theme.js` pour le
projet, le compte et « Aa », `bac-a-sable.js` pour la ligne du bac à sable). Les marques de
la barre du haut valent sur les six surfaces.

**La liste vient de `static/lib/wizard.js`, lue DEUX fois** : par une extraction Python du
source, qui tourne partout — l'image de test n'a pas Node —, et par Node quand il est là.
Les deux doivent rendre la même liste : une extraction qui rétrécirait en silence
approuverait tout (la leçon d'ARCH-2), et c'est l'écart entre deux façons de compter qui le
dit. Ce test ne dit PAS que la zone est visible ni où elle se dessine : c'est l'affaire du
navigateur (`tests/test_e2e_wizard.py`).
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
LIB = RACINE / "static" / "lib" / "wizard.js"
GABARITS = {"/": "index.html", "/annotation": "annotation.html", "/corpus": "corpus.html",
            "/recherche": "recherche.html", "/exploration": "exploration.html",
            "/administration": "administration.html"}

SCRIPT = re.compile(r'<script src="/static/([^"]+)"')
MARQUE_HTML = re.compile(r'data-parcours="([^"]+)"')
MARQUE_JS = re.compile(r'(?:dataset\.parcours\s*=\s*|setAttribute\(\s*"data-parcours"\s*,\s*)'
                       r'"([^"]+)"')


def _sans_commentaires(source: str) -> str:
    """Le source sans ses commentaires : une marque citée dans un commentaire ne pose rien."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|(?<=[;,{}()\]])\s*//.*$", "", source)


def marques_extraites():
    """`[(surface, bande, marque)]`, lues dans le bloc `VISITE` du source, sans Node."""
    source = _sans_commentaires(LIB.read_text(encoding="utf-8"))
    debut = source.index("const VISITE = [")
    fin = source.index("\n  ];", debut)
    bloc = source[debut:fin]
    out = []
    # Une page de la visite commence par `{ surface: "…"` ; ses zones sont des listes dont
    # le premier élément est la marque.
    pages = re.split(r'\n\s*\{\s*surface:\s*', bloc)[1:]
    for page in pages:
        surface = re.match(r'"([^"]*)"', page).group(1)
        bande = re.match(r'"[^"]*",\s*bande:\s*true', page) is not None
        for m in re.finditer(r'\[\s*"([a-z]+(?:-[a-z]+)+)",', page):
            out.append((surface, bande, m.group(1)))
    return out


def marques_de_node():
    r = subprocess.run(
        ["node", "-e", "process.stdout.write(JSON.stringify(require(process.argv[1]).marques()))",
         str(LIB)], cwd=str(RACINE), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return [(m["surface"], m["bande"], m["marque"]) for m in json.loads(r.stdout)]


def poseurs(gabarit: str):
    """Ce qui peut poser une marque sur la surface : son gabarit, et les scripts qu'il
    charge. `{marque: [lieu, …]}`."""
    html = (RACINE / "templates" / gabarit).read_text(encoding="utf-8")
    trouvees = {}
    for m in MARQUE_HTML.findall(_sans_commentaires_html(html)):
        trouvees.setdefault(m, []).append(gabarit)
    for src in SCRIPT.findall(html):
        chemin = RACINE / "static" / src
        if not chemin.exists():
            continue
        for m in MARQUE_JS.findall(_sans_commentaires(chemin.read_text(encoding="utf-8"))):
            trouvees.setdefault(m, []).append(src)
    return trouvees


def _sans_commentaires_html(html: str) -> str:
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def test_la_liste_des_marques_n_est_pas_vide():
    """Le plancher : une liste vide rendrait tous les contrôles suivants vacants."""
    m = marques_extraites()
    surfaces = {s for s, bande, _ in m if not bande}
    assert set(GABARITS) <= surfaces, (
        f"l'extraction ne voit des zones que sur {sorted(surfaces)} : soit la visite a "
        "perdu une surface, soit le motif ne lit plus le source")
    assert any(bande for _, bande, _ in m), "aucune zone de la barre du haut extraite"
    assert len(m) >= 25, f"seulement {len(m)} zones extraites : {m}"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js non installé")
def test_l_extraction_dit_ce_que_dit_le_module():
    """Deux énumérations indépendantes du même source, et la même liste."""
    assert marques_extraites() == marques_de_node()


@pytest.mark.parametrize("surface", sorted(GABARITS))
def test_chaque_zone_nommee_par_la_visite_a_sa_marque_sur_sa_surface(surface):
    gabarit = GABARITS[surface]
    posees = poseurs(gabarit)
    attendues = [mq for s, bande, mq in marques_extraites() if bande or s == surface]
    manquent = [mq for mq in attendues if mq not in posees]
    assert not manquent, (
        f"{surface} ({gabarit}) : la visite nomme {manquent}, et aucun élément ne porte "
        "leur `data-parcours` — ni le gabarit, ni un script qu'il charge. Une zone du guide "
        "disparaîtrait sans bruit : reposer la marque sur l'élément qui a pris la place de "
        "l'ancien, ou retirer la zone de `VISITE` dans `static/lib/wizard.js`.")


def test_aucune_marque_n_est_morte():
    """L'autre sens : une marque posée que la visite ne nomme pas est un reste, qu'un écran
    remanié laissera croire tenu. Elle se retire, ou la visite la nomme."""
    nommees = {mq for _, _, mq in marques_extraites()}
    mortes = {}
    for gabarit in GABARITS.values():
        for mq, lieux in poseurs(gabarit).items():
            if mq not in nommees:
                mortes.setdefault(mq, set()).update(lieux)
    assert not mortes, f"marques posées que la visite ne nomme pas : {mortes}"


def test_le_motif_mord():
    """Les motifs de ce fichier reconnaissent les trois formes qu'il prétend lire — sans
    quoi une garde qui ne trouve rien approuverait tout."""
    assert MARQUE_HTML.findall('<div data-parcours="a-b">') == ["a-b"]
    assert MARQUE_JS.findall('w.dataset.parcours = "a-b";') == ["a-b"]
    assert MARQUE_JS.findall('e.setAttribute("data-parcours", "c-d")') == ["c-d"]
    assert MARQUE_JS.findall(_sans_commentaires('/* w.dataset.parcours = "a-b"; */')) == []
    assert MARQUE_HTML.findall(_sans_commentaires_html('<!-- data-parcours="a-b" -->')) == []
    # Et la bande : `theme.js` pose bien les trois marques qu'on lui prête.
    posees = poseurs("index.html")
    for mq, lieu in (("bande-projet", "theme.js"), ("bande-compte", "theme.js"),
                     ("bande-affichage", "theme.js"), ("bande-bac", "bac-a-sable.js"),
                     ("bande-pages", "index.html")):
        assert lieu in posees.get(mq, []), (mq, posees.get(mq))
