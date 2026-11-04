"""UX-6 — l'écran dit « Atelier », jamais « Visionneuse ».

Les deux mots désignent la MÊME page, `/` (cf. `CLAUDE.md`) ; l'écran dit Atelier, et le
guide pas à pas l'enseigne sous ce nom. La Recherche nommait encore « Visionneuse » le lien
de son aperçu, et son infobulle, et le panneau 🎯 Accord de l'Exploration y renvoyait : un
arrivant cherchait une page qui n'existe pas dans la navigation.

Ce test lit ce que l'écran peut MONTRER — les gabarits hors commentaires, et les littéraux de
chaîne des scripts hors commentaires — et non les notes : le code, les commentaires, `docs/`
et `pilotage/` gardent le mot, ce sont des traces datées. Il vérifie d'abord que sa lecture
mord : une garde qui ne trouve rien nulle part approuve tout."""
import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOT = re.compile(r"visionneuse", re.IGNORECASE)


def chaines_js(source: str) -> list[tuple[int, str]]:
    """Les littéraux de chaîne et de gabarit d'un script, hors commentaires, avec leur ligne.
    Une lecture à la main et non un analyseur : elle ignore l'imbrication des `${…}`, ce qui
    suffit à repérer un mot écrit dans un texte."""
    sortie, i, n = [], 0, len(source)
    while i < n:
        c = source[i]
        if source.startswith("//", i):
            j = source.find("\n", i)
            i = n if j < 0 else j
            continue
        if source.startswith("/*", i):
            j = source.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and source[j] != c:
                if source[j] == "\\":
                    j += 1
                elif c != "`" and source[j] == "\n":
                    break
                j += 1
            sortie.append((source.count("\n", 0, i) + 1, source[i + 1:j]))
            i = j + 1
            continue
        i += 1
    return sortie


def html_sans_commentaires(source: str) -> str:
    return re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)


def _scripts():
    return [f for f in sorted(RACINE.glob("static/**/*.js")) if "vendor" not in f.parts]


def test_la_lecture_mord():
    """La garde distingue un texte d'une note : sans quoi elle passerait en ne lisant rien."""
    src = ('// la Visionneuse, en commentaire\n/* Visionneuse */\n'
           'const a = "Ouvrir la visionneuse";\nconst b = `dans la Visionneuse ${x}`;\n'
           "const c = 'l\\'Atelier';\n")
    trouves = [(ligne, s) for ligne, s in chaines_js(src) if MOT.search(s)]
    assert [ligne for ligne, _ in trouves] == [3, 4], trouves
    assert MOT.search(html_sans_commentaires('<a title="la visionneuse">x</a>'))
    assert not MOT.search(html_sans_commentaires("<!-- Visionneuse -->"))
    # Le balayage porte sur de vrais fichiers, en nombre.
    assert len(_scripts()) > 20
    assert len(list(RACINE.glob("templates/*.html"))) >= 6


def test_aucun_texte_de_l_ecran_ne_dit_visionneuse():
    fautes = []
    for f in _scripts():
        for ligne, s in chaines_js(f.read_text(encoding="utf-8")):
            if MOT.search(s):
                fautes.append(f"{f.relative_to(RACINE)}:{ligne} : {s[:70]!r}")
    for f in sorted(RACINE.glob("templates/*.html")):
        texte = html_sans_commentaires(f.read_text(encoding="utf-8"))
        for m in MOT.finditer(texte):
            ligne = texte.count("\n", 0, m.start()) + 1
            fautes.append(f"{f.relative_to(RACINE)}:{ligne} (hors commentaires)")
    assert not fautes, "l'écran dit encore « Visionneuse » : " + " ; ".join(fautes)


def test_le_lien_de_l_apercu_dit_atelier():
    """La case de la fiche : le bouton de l'aperçu et son infobulle."""
    html = (RACINE / "templates" / "recherche.html").read_text(encoding="utf-8")
    lien = re.search(r'<a id="preview-edit"[^>]*>[^<]*</a>', html).group(0)
    assert "Atelier" in lien and "title=\"Ouvrir dans l'Atelier" in lien, lien
