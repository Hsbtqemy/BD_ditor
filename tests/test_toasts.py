"""Un toast ne porte qu'une classe que `style.css` définit.

`toast(msg, kind)` (static/lib/common.js) pose `class="toast " + kind`, et rien ne vérifie que
`kind` existe. Cinq appels d'`exploration.js` passaient `"err"` quand la feuille ne définit
que `.toast.error` : leurs échecs s'affichaient avec le liseré bleu d'une information, sans
qu'aucun test ni aucune console ne le dise (trouvé le 2026-09-24, AUTH-11 — la fiche parlait
même d'un « toast rouge » qui ne l'avait jamais été).

Même patron que `test_csrf.py` pour les `fetch` : on balaie le SOURCE de `static/**/*.js`.
Une classe écrite en littéral doit être définie ; une classe CALCULÉE se déclare dans
`CLASSES_CALCULEES` avec l'endroit qui en garantit les valeurs.

**Angles morts connus.** Le balayage reconnaît `toast(` nu, le nom que `common.js` publie en
global. Il ne voit PAS un alias (`const t = toast; t(msg, "err")`), ni un appel passé par
une variable (`[msg, kind]` étalés, `toast.apply`), ni une classe posée après coup sur
l'élément. `window.toast(…)` et tout `x.toast(…)`, eux, ne sont pas lus par l'analyseur
mais sont COMPTÉS par le décompte naïf de `test_le_balayage_voit_les_appels` : l'écart
entre les deux fait tomber la suite plutôt que de les laisser passer en silence.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
STATIC = RACINE / "static"

# Appels dont la classe n'est pas un littéral : (fichier, expression) → où ses valeurs
# sont garanties. Une expression neuve échoue tant qu'elle n'est pas déclarée ici.
CLASSES_CALCULEES = {
    ("exploration.js", "b.ton"):
        "BDBilanImport.bilan ne rend que \"success\", \"\" ou \"error\" — "
        "tests/js/bilan-import.test.js",
}


def _classes_definies():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    return {""} | set(re.findall(r"\.toast\.([a-zA-Z0-9_-]+)", css))


def _arguments(source, debut):
    """Les arguments de premier niveau d'un appel dont `(` est en `debut`, tels qu'écrits.
    Suit les chaînes ("…", '…', `…` avec ${…}) et les parenthèses/crochets/accolades."""
    args, courant, pile, i = [], [], [], debut + 1
    while i < len(source):
        c = source[i]
        if c in "\"'`":
            fin = i + 1
            while fin < len(source) and source[fin] != c:
                if source[fin] == "\\":
                    fin += 1
                elif c == "`" and source.startswith("${", fin):
                    prof, fin = 1, fin + 2
                    while prof and fin < len(source):
                        prof += {"{": 1, "}": -1}.get(source[fin], 0)
                        fin += 1
                    continue
                fin += 1
            courant.append(source[i:fin + 1])
            i = fin + 1
            continue
        if c in "([{":
            pile.append(c)
        elif c in ")]}":
            if not pile:
                args.append("".join(courant).strip())
                return args
            pile.pop()
        elif c == "," and not pile:
            args.append("".join(courant).strip())
            courant = []
            i += 1
            continue
        courant.append(c)
        i += 1
    raise AssertionError("appel non refermé")


_CHAINE = r"""(["'])([^"'`\\]*)\1"""


def _litteraux(expr):
    """Les valeurs possibles d'une classe écrite en littéral — `"error"` — ou en ternaire
    dont TOUTES les branches sont des littéraux — `ok ? "" : "error"`, la condition pouvant
    être quelconque. None si une valeur n'est pas lisible dans le source."""
    m = re.fullmatch(_CHAINE, expr)
    if m:
        return [m.group(2)]
    if "?" not in expr:
        return None
    # Chaque branche (ce qui suit un `?` ou un `:`) est un littéral, ou un ternaire
    # parenthésé dont les branches le sont à leur tour ; les conditions sont libres.
    sans_chaines = re.sub(_CHAINE, '""', expr)
    if not all(re.match(r"\s*[(\"]", sans_chaines[m.end():])
               for m in re.finditer(r"[?:]", sans_chaines)):
        return None
    branche = r"""[?:]\s*\(?\s*(["'])([^"'`\\]*)\1"""
    return [m.group(2) for m in re.finditer(branche, expr)] or None


def _appels():
    """(fichier, ligne, arguments) de chaque `toast(` de static/**/*.js, sa définition exceptée."""
    for f in sorted(STATIC.rglob("*.js")):
        if "vendor" in f.parts:
            continue
        source = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w.$])toast\(", source):
            if re.search(r"function\s+$", source[:m.start()]):
                continue                                   # `function toast(` : la définition
            ligne = source.count("\n", 0, m.start()) + 1
            yield f.relative_to(STATIC).as_posix(), ligne, _arguments(source, m.end() - 1)


def _decompte_naif():
    """Une SECONDE façon de compter, aussi bête que possible et écrite à part : parcours
    par `os.walk` (et non `rglob`), et simple `str.count("toast(")` par fichier, moins la
    définition. Elle ne partage avec `_appels` ni l'énumération ni l'expression régulière."""
    import os
    compte = {}
    for dossier, sous, fichiers in os.walk(STATIC):
        sous[:] = [d for d in sous if d != "vendor"]
        for nom in fichiers:
            if nom.endswith(".js"):
                chemin = Path(dossier) / nom
                texte = chemin.read_text(encoding="utf-8")
                n = texte.count("toast(") - texte.count("function toast(")
                if n:
                    compte[chemin.relative_to(STATIC).as_posix()] = n
    return compte


def test_le_balayage_voit_les_appels():
    """ARCH-2 appliqué ici : un balayage qui ne verrait plus rien rendrait la garde verte.
    Pas de plancher recopié — il vieillit dans le sens permissif (cf. `test_surfaces`) :
    deux façons indépendantes de compter doivent donner le MÊME compte, fichier par
    fichier. Perdre la lecture d'un fichier entier, ou un appel que l'analyseur ne
    reconnaît pas (`window.toast(`), crée un écart qui crie."""
    par_fichier = {}
    for fichier, _, _ in _appels():
        par_fichier[fichier] = par_fichier.get(fichier, 0) + 1
    naif = _decompte_naif()
    assert naif, "le décompte naïf ne voit aucun appel : il ne prouve plus rien"
    assert par_fichier == naif, (
        "l'analyseur et le décompte naïf ne voient pas les mêmes appels : "
        f"analyseur={par_fichier}, naïf={naif}")
    assert any(len(a) >= 2 and a[1] == '"error"' for _, _, a in _appels())


def test_la_lecture_des_arguments_suit_chaines_et_parentheses():
    src = 'toast(`a, ${f(1, 2)}`, "error", 8000); toast(g("x, y"), c.k);'
    assert _arguments(src, src.index("(")) == ['`a, ${f(1, 2)}`', '"error"', "8000"]
    j = src.index("toast(", 5) + 5
    assert _arguments(src, j) == ['g("x, y")', "c.k"]


def test_la_lecture_des_classes_voit_les_ternaires():
    assert _litteraux('"error"') == ["error"]
    assert _litteraux('ok ? (ko ? "" : "success") : "error"') == ["", "success", "error"]
    assert _litteraux('/x/i.test(m) ? "" : "err"') == ["", "err"]
    assert _litteraux("b.ton") is None
    assert _litteraux('ok ? kind : "error"') is None       # une branche calculée


def test_tout_toast_porte_une_classe_definie():
    definies = _classes_definies()
    assert {"error", "success"} <= definies, definies
    fautifs, non_declares = [], []
    for fichier, ligne, args in _appels():
        if len(args) < 2:
            continue
        kind = args[1]
        litteraux = _litteraux(kind)
        if litteraux is not None:
            fautifs += [f"{fichier}:{ligne} → {kind}" for v in litteraux if v not in definies]
        elif (Path(fichier).name, kind) not in CLASSES_CALCULEES:
            non_declares.append(f"{fichier}:{ligne} → {kind}")
    assert not fautifs, (
        "classe de toast que style.css ne définit pas (le toast s'affiche comme une "
        f"simple information) : {fautifs}. Classes définies : {sorted(definies)}")
    assert not non_declares, (
        f"classe de toast calculée et non déclarée : {non_declares}. La déclarer dans "
        "CLASSES_CALCULEES avec l'endroit qui en garantit les valeurs")


def test_les_classes_calculees_declarees_existent_encore():
    vues = {(Path(f).name, a[1]) for f, _, a in _appels() if len(a) >= 2}
    fantomes = sorted(set(CLASSES_CALCULEES) - vues)
    assert not fantomes, f"déclarations sans appel correspondant : {fantomes}"
