"""Ce qu'on déclare caché est vraiment caché — la garde de la famille `[hidden]`.

Les scripts de surface masquent par la PROPRIÉTÉ DOM (`el.hidden = true`), qui n'agit
qu'à travers la règle du navigateur `[hidden] { display: none }`. Toute règle de la
feuille qui pose un `display` sur le même élément l'emporte, par simple spécificité — et
l'élément reste à l'écran alors que le code le croit caché.

Le dépôt connaît le piège et le garde par une dizaine de règles, l'une avec le commentaire
« sinon le display:flex écrase [hidden] ». Il en manquait CINQ, trouvées le 2026-09-04 :
`.dist` — la distribution restait affichée sous le tableau de croisement après une bascule
de vue —, les trois filtres `#wrap-champ`, `#wrap-lemme`, `#wrap-kwic`, visibles dans des
vues qui ne les emploient pas, et `.corpus-synthese`, dont le cadre bordé s'affichait vide.

**Le cinquième a été trouvé par la RELECTURE de ce test, pas par ce test.** Sa première
version ne captait que la forme `$("#id").hidden` et affirmait dans son en-tête que c'était
la seule employée dans le dépôt. Mesuré : 35 des 88 affectations `.hidden` des quatre
scripts passaient par une variable, et lui échappaient — dont `.corpus-synthese`. Pire, la
garde censée détecter ce cas (« aucune cible trouvée ») ne pouvait jamais se déclencher,
puisqu'il restait toujours des formes directes. Une garde écrite pour surveiller un angle
mort en avait un.

**La résolution des variables est POSITIONNELLE**, et ce n'est pas un raffinement : une
résolution globale associait `box` à sa dernière définition du fichier, alors que
`corpus.js` s'en sert pour TROIS éléments différents selon la fonction. Elle désignait donc
`#jobs`, jamais masqué, et manquait `#album-detail`, qui l'est.

**Ce que le test ne sait pas lire, il le DIT** : toute affectation `.hidden` dont la
variable ne remonte à aucun `$("#…")` doit figurer dans `NON_RESOLUS` avec sa raison. C'est
le patron de `test_autorisation.py` et de `test_sorties_identite.py` — soit c'est couvert,
soit c'est déclaré. Sans cette liste, une forme nouvelle sortirait du périmètre en silence,
et le vert deviendrait un mensonge.

Le défaut dormait depuis longtemps sur l'Exploration : `overflow: hidden` clippait ce qui
dépassait, donc la distribution en trop était présente mais INATTEIGNABLE. Poser un cadre
de défilement l'a rendue visible, et une passe de QA l'a vue le jour même.

Le marqueur `e2e` est posé PAR TEST : celui qui ouvre un navigateur en est, la garde
du périmètre non — elle ne lit que des sources et tourne dans la suite par défaut.
"""
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="pytest-playwright non installé")

# Le marqueur `e2e` se pose PAR TEST et non sur le module : la garde du périmètre ne lit
# que des sources et n'ouvre aucun navigateur. La marquer `e2e` la sortait de la suite par
# défaut, donc de la boucle courte — or c'est elle qui dit quand le balayage cesse de
# couvrir quelque chose, et cette information n'a aucune raison d'attendre un run long.

RACINE = Path(__file__).resolve().parent.parent
# UX-10 — LA liste de cet audit, et elle sert de déclaration : `tests/test_surfaces.py`
# la confronte aux surfaces réellement servies. C'est la MÊME structure que le test
# parcourt, pas une copie posée à côté — une déclaration jumelle dériverait de sa liste
# sans que rien ne le dise, ce qui a été mesuré le 2026-09-07 sur un premier jet.
SURFACES_AUDITEES = {"/": "viewer.js", "/recherche": "recherche.js",
                     "/corpus": "corpus.js", "/exploration": "exploration.js",
                     "/administration": "administration.js"}
SURFACES_HORS_PERIMETRE = {}

# UX-16 — un module MONTÉ masque pour le compte de la surface qui le monte. Le balayage ne
# lisait que les scripts de surface : en sortant de `corpus.js`, le masquage de « Qui entre »
# quittait donc le périmètre SANS QUE RIEN NE TOMBE, et sa déclaration dans `NON_RESOLUS`
# restait là, à désigner un fichier qui ne contenait plus la ligne. Les modules qui touchent
# `hidden` sont donc lus eux aussi — par la garde de périmètre, qui ne demande aucun
# navigateur. Une clé par module, sa valeur dit qui le monte.
MODULES_MONTES = {
    "lib/qui-entre.js": "monté par la Bibliothèque, dans chaque collection dépliée (UX-16)",
    "lib/membres-projet.js": "monté par l'Administration, dans la fiche d'un projet (COL-3)",
}

DIRECT =re.compile(r'\$\(\s*"#([a-z0-9-]+)"\s*\)\.hidden\s*=')
AFFECT = re.compile(r'(\w+)\s*=\s*(?:\$\(\s*"#([a-z0-9-]+)"\s*\)'
                    r'|document\.getElementById\(\s*"([a-z0-9-]+)"\s*\))')
VAR = re.compile(r'(?<![.\w])(\w+)\.hidden\s*=')

# Les affectations dont la cible ne remonte à aucun `$("#…")`, avec la raison de les
# laisser hors du balayage. Une entrée par (fichier, nom de variable).
NON_RESOLUS = {
    ("exploration.js", "el"): (
        "Le paramètre d'un `forEach` sur `.sub-title` : la cible est une CLASSE, pas un "
        "identifiant, donc `getElementById` ne l'atteint pas. Vérifié à la main le "
        "2026-09-04 — `.sub-title` ne pose aucun `display`, l'attribut agit. Le jour où "
        "le balayage saura viser un sélecteur, cette entrée disparaît."),
    ("lib/qui-entre.js", "libre"): (
        "La saisie libre de « Qui entre » (AUTH-12, étape 3), une par panneau monté : "
        "la cible est la CLASSE `.qe-libre`, cherchée dans sa section, pas un identifiant. "
        "Elle pose `display: inline-flex`, d'où le garde `.qe-libre[hidden] { display: none; }` "
        "dans la feuille — vérifié le 2026-09-17 dans les deux sens par deux tests e2e : "
        "`test_ouvrir_une_collection_a_ce_groupe_le_preselectionne` l'exige CACHÉE, "
        "`test_un_annuaire_en_panne_n_empeche_rien` VISIBLE."),
    ("lib/membres-projet.js", "libre"): (
        "La saisie libre de « Qui y entre » d'un projet (COL-3), une par partie montée, sur "
        "le patron de celle de « Qui entre » : la cible est la CLASSE `.mp-libre`, cherchée "
        "dans sa section, pas un identifiant. Elle pose `display: inline-flex`, d'où le garde "
        "`.mp-libre[hidden] { display: none; }` dans la feuille — vérifié le 2026-10-10 dans "
        "les deux sens par deux tests e2e : "
        "`test_faire_entrer_un_groupe_part_avec_le_role_de_membre` l'exige CACHÉE, "
        "`test_faire_entrer_un_compte_demande_de_dire_ce_qu_il_est` VISIBLE."),
}


def cibles(source: str):
    """Les identifiants dont le script bascule le `hidden`, et ce qu'il n'a pas su lire.

    Chaque `X.hidden` remonte à la définition de `X` la plus proche EN AMONT — la portée
    réelle du code, et non la dernière définition du fichier.
    """
    defs = [(m.start(), m.group(1), m.group(2) or m.group(3))
            for m in AFFECT.finditer(source)]
    ids, orphelins = set(DIRECT.findall(source)), []
    for m in VAR.finditer(source):
        amont = [i for (pos, nom, i) in defs if nom == m.group(1) and pos < m.start()]
        if amont:
            ids.add(amont[-1])
        else:
            orphelins.append((source[:m.start()].count("\n") + 1, m.group(1)))
    return sorted(ids), orphelins


SONDE = """(ids) => {
  const out = [];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;                       // injecté à la demande : rien à mesurer
    const avant = el.hidden;
    el.hidden = true;
    const d = getComputedStyle(el).display;
    el.hidden = avant;
    if (d !== 'none') out.push(`#${id} → display:${d}`);
  }
  return out;
}"""


@pytest.mark.e2e
@pytest.mark.parametrize("chemin, script", SURFACES_AUDITEES.items())
def test_un_element_declare_cache_l_est_vraiment(page, live_server, chemin, script):
    """Pour CHAQUE élément que la surface masque, poser `hidden` doit donner `display:none`.

    On demande au navigateur plutôt qu'à la feuille de style : la question est celle du
    style CALCULÉ, où se joue la spécificité, et une lecture du CSS ne saurait pas dire
    laquelle des deux règles gagne.
    """
    ids, _ = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
    assert ids, (
        f"aucune cible `.hidden` trouvée dans {script} : soit le masquage a changé de "
        "forme, soit ce test ne couvre plus rien — les deux demandent une relecture")

    page.goto(live_server + chemin, wait_until="networkidle")
    coupables = page.evaluate(SONDE, ids)
    assert not coupables, (
        f"Sur {chemin}, ces éléments restent AFFICHÉS malgré `hidden` — une règle de la "
        f"feuille écrase `[hidden] {{ display: none }}` : {', '.join(coupables)}. "
        "Ajouter le garde `<sélecteur>[hidden] { display: none; }` à côté de la règle "
        "fautive, comme la dizaine qui existent déjà.")


@pytest.mark.parametrize("chemin, script", SURFACES_AUDITEES.items())
def test_toute_cible_illisible_est_declaree(chemin, script):
    """Le périmètre du balayage ne rétrécit pas en silence.

    C'est la garde qui manquait à la première version, et son absence a coûté un défaut :
    une affectation que l'extraction ne sait pas résoudre sortait du test sans que rien
    ne le dise. Elle doit maintenant être déclarée avec sa raison, ou faire échouer.
    """
    _, orphelins = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
    non_declares = [(ligne, nom) for ligne, nom in orphelins
                    if (script, nom) not in NON_RESOLUS]
    assert not non_declares, (
        f"{script} : ces affectations `.hidden` ne remontent à aucun `$(\"#…\")`, donc le "
        "balayage ne les couvre pas — "
        + ", ".join(f"`{nom}.hidden` ligne {ligne}" for ligne, nom in non_declares)
        + ". Soit la cible reçoit un identifiant, soit l'entrée rejoint `NON_RESOLUS` "
          "avec la raison de l'y laisser ET la vérification faite à la main.")


@pytest.mark.parametrize("script", sorted(MODULES_MONTES))
def test_toute_cible_illisible_d_un_module_monte_est_declaree(script):
    """La même garde, pour ce qu'une surface MONTE au lieu de l'écrire (UX-16).

    Un module n'a pas de page à lui : le balayage navigateur ne peut pas le viser par une
    adresse. Mais ce qu'il masque sans identifiant doit être déclaré comme le reste — sans
    quoi extraire un panneau d'un script de surface suffirait à sortir ses masquages du
    périmètre, ce qui est exactement ce qui a failli arriver.
    """
    _, orphelins = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
    non_declares = [(ligne, nom) for ligne, nom in orphelins
                    if (script, nom) not in NON_RESOLUS]
    assert not non_declares, (
        f"{script} : ces affectations `.hidden` ne remontent à aucun `$(\"#…\")` — "
        + ", ".join(f"`{nom}.hidden` ligne {ligne}" for ligne, nom in non_declares)
        + ". L'entrée rejoint `NON_RESOLUS` avec sa raison ET la vérification faite.")


def test_tout_module_qui_masque_est_lu():
    """La porte de l'OUBLI, du côté des modules : `MODULES_MONTES` est écrite à la main.

    Tout fichier de `static/lib/` qui AFFECTE `hidden` doit y figurer. `dialog.js` n'y est
    pas, et c'est juste : il OBSERVE l'attribut et délègue la fermeture à l'appelant — sa
    seule affectation vit dans une fonction de repli que ce motif reconnaît, d'où
    l'exception nommée plutôt qu'un motif rétréci pour l'épargner.
    """
    exceptes = {"lib/dialog.js": "repli `toggleEl.hidden = true` sur l'élément que l'appelant "
                                 "lui confie ; la cible est celle de la surface, déjà balayée"}
    masquent = sorted(
        f"lib/{p.name}" for p in (RACINE / "static" / "lib").glob("*.js")
        if VAR.search(p.read_text(encoding="utf-8")) or DIRECT.search(p.read_text(encoding="utf-8")))
    attendus = sorted(set(MODULES_MONTES) | set(exceptes))
    assert masquent == attendus, (
        f"modules qui affectent `hidden` : {masquent} ; lus ou exceptés : {attendus}")


def test_aucune_declaration_n_est_morte():
    """Une entrée de `NON_RESOLUS` désigne une affectation qui EXISTE encore.

    C'est le défaut qu'UX-16 a rendu visible : la déclaration `("corpus.js", "libre")` aurait
    survécu au déménagement de sa ligne, en excusant d'avance la prochaine variable `libre`
    de ce fichier — une exception sans objet est un passe-droit. Une déclaration morte se
    retire, ou suit sa ligne.
    """
    scripts = set(SURFACES_AUDITEES.values()) | set(MODULES_MONTES)
    mortes = []
    for (script, nom) in NON_RESOLUS:
        if script not in scripts:
            mortes.append((script, nom, "fichier hors du balayage"))
            continue
        _, orphelins = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
        if nom not in {n for _, n in orphelins}:
            mortes.append((script, nom, "plus aucune affectation de ce nom"))
    assert not mortes, f"déclarations sans objet dans NON_RESOLUS : {mortes}"
