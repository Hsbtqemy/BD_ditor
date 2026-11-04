"""UX-6 — chaque étape de « Par où commencer » a sa section dans le guide d'utilisation.

L'écran et `docs/guide-utilisateur.md` ont un contrat commun : la liste des étapes et leur
ordre, figés avant l'écran pour que les deux ne divergent pas (`pilotage/UX-6.md`,
« Arbitrages »). Hugo y a ajouté « Tracer une zone » le 2026-11-02 — neuf étapes et non
huit —, et le guide en disait encore huit : c'est la divergence que ce test ferme. Il exige
que les titres des étapes de l'écran (`ETAPES` de `static/lib/wizard.js`) soient, dans le
même ordre et numérotés de 1 à N, les sections « Étape N — … » du §3 du guide, et que le
titre du §3 dise leur nombre.

Le guide n'est pas servi par l'application : l'écran ne peut pas y mener par un lien, et
c'est le TITRE qui fait le renvoi. Un titre changé d'un seul côté fait échouer la suite.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LIB = RACINE / "static" / "lib" / "wizard.js"
GUIDE = RACINE / "docs" / "guide-utilisateur.md"
NOMBRES = {8: "huit", 9: "neuf", 10: "dix"}


def titres_de_l_ecran():
    """Les `titre` du bloc `ETAPES`, dans l'ordre, lus dans le source."""
    source = LIB.read_text(encoding="utf-8")
    debut = source.index("const ETAPES = [")
    bloc = source[debut:source.index("\n  ];", debut)]
    return re.findall(r'\{\s*k:\s*"[a-z]+",\s*titre:\s*"([^"]+)"', bloc)


def sections_du_guide():
    """`[(numéro, titre)]` des sections « ### Étape N — Titre » du guide, sans la marque
    en italique qui suit un titre (« *(optionnel)* »)."""
    texte = GUIDE.read_text(encoding="utf-8")
    return [(int(n), re.sub(r"\s*\*\([^)]*\)\*\s*$", "", t).strip())
            for n, t in re.findall(r"(?m)^### Étape (\d+) — (.+?)\s*$", texte)]


def test_l_extraction_voit_les_neuf_etapes():
    # Une extraction qui rétrécirait en silence approuverait tout.
    assert titres_de_l_ecran() == [
        "Constituer le corpus", "Décrire l'album", "Pré-remplir", "Tracer une zone",
        "Corriger le découpage", "Transcrire et relire", "Annoter", "Chercher et explorer",
        "Exporter"]


def test_chaque_etape_de_l_ecran_a_sa_section_dans_le_guide():
    ecran = titres_de_l_ecran()
    guide = sections_du_guide()
    assert [n for n, _ in guide] == list(range(1, len(guide) + 1)), guide
    assert [t for _, t in guide] == ecran


def test_le_parcours_du_guide_dit_le_nombre_d_etapes():
    n = len(titres_de_l_ecran())
    texte = GUIDE.read_text(encoding="utf-8")
    assert re.search(rf"(?m)^## 3\. Le parcours en {NOMBRES[n]} étapes\s*$", texte)
    assert "huit étapes" not in texte or n == 8
