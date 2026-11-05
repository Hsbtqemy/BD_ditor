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

**Toute affectation `.hidden = …` compte, pas seulement celles que l'extraction reconnaît**
(ANN-7, 2026-11-05). Les deux motifs ne voyaient que `$("#id").hidden` et `nom.hidden` ;
tout ce qui précédait `.hidden` d'une parenthèse ou d'un crochet — `$(id).hidden` dans une
fonction d'aide, `$(idLien(lieu, "liste")).hidden`, `sel.closest("label").hidden` — sortait
du balayage SANS ÊTRE COMPTÉ, donc sans tomber dans `NON_RESOLUS`. La garde des orphelins
avait le même angle mort que celle de la première version : elle ne voyait que ce que
l'extraction voyait. Désormais chaque `.hidden =` du fichier est l'une de deux choses :
résolu en identifiant (les deux formes d'avant ; un appel à une fonction d'aide MASQUEUSE
— `function montrer(id, oui) { $(id).hidden = !oui; }` — dont le premier argument est un
littéral `"#…"` ; un `$(id)` dans le corps d'un `for (const id of ["#…", …])`), ou un
orphelin nommé par son EXPRESSION, à déclarer. Rien n'est interprété au-delà : un appel à la
fonction d'aide dont l'argument se calcule est un orphelin comme un autre. Et une
déclaration peut nommer les identifiants qu'elle désigne (`IDS_DECLARES`) : la sonde les
mesure alors comme les autres, au lieu de les excuser.

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
SURFACES_AUDITEES = {"/": "viewer.js", "/annotation": "annotation.js",
                     "/recherche": "recherche.js",
                     "/corpus": "corpus.js", "/exploration": "exploration.js",
                     "/administration": "administration.js"}
SURFACES_HORS_PERIMETRE = {}

# UX-16 — un module MONTÉ masque pour le compte de la surface qui le monte. Le balayage ne
# lisait que les scripts de surface : en sortant de `corpus.js`, le masquage de « Qui entre »
# quittait donc le périmètre SANS QUE RIEN NE TOMBE, et sa déclaration dans `NON_RESOLUS`
# restait là, à désigner un fichier qui ne contenait plus la ligne. Les modules qui touchent
# `hidden` sont donc lus eux aussi — par la garde de périmètre, qui ne demande aucun
# navigateur. Une clé par module, sa valeur dit qui le monte. `lib/qui-entre.js` en est
# sorti avec sa saisie libre (COL-3, tranche 3c, F2) : il ne masque plus rien, et s'il y
# revenait, `test_tout_module_qui_masque_est_lu` le dirait.
MODULES_MONTES = {
    "lib/membres-projet.js": "monté par l'Administration, dans la fiche d'un projet (COL-3), "
                             "et par la ligne du bac à sable, dans « Inviter… » (COL-4)",
    "lib/champ-personnage.js": "monté par l'Atelier, pour le locuteur et l'identité d'une "
                               "boîte, et par la page Annotation, pour le locuteur du Contexte "
                               "(ANN-7, tranche 2, commit 8) et l'identité d'une boîte",
    "lib/alignements.js": "monté par l'Atelier, deux fois dans le panneau Personnage (par le "
                          "locuteur, par la boîte), et par la page Annotation, dans la fiche "
                          "d'un personnage (ANN-7)",
}

# COL-4 — un script de surface PARTAGÉ par les cinq pages : la ligne du bac à sable, son
# bouton et ses dialogues. Il n'appartient à aucune surface, donc à aucune entrée de
# `SURFACES_AUDITEES` ; lu ici comme un module monté, et joué sur l'Atelier par la sonde.
SCRIPTS_PARTAGES = {
    "bac-a-sable.js": "chargé par les cinq gabarits, avant le script de la surface (COL-4)",
    "wizard.js": "chargé par les six gabarits, après `bac-a-sable.js` (UX-6)",
}

DIRECT =re.compile(r'\$\(\s*"#([a-z0-9-]+)"\s*\)\.hidden\s*=')
AFFECT = re.compile(r'(\w+)\s*=\s*(?:\$\(\s*"#([a-z0-9-]+)"\s*\)'
                    r'|document\.getElementById\(\s*"([a-z0-9-]+)"\s*\))')
VAR = re.compile(r'(?<![.\w])(\w+)\.hidden\s*=')
# ANN-7 — TOUTE affectation de la propriété, quelle que soit l'expression qui la précède :
# c'est l'inventaire que les formes résolues doivent épuiser, le reste étant un orphelin.
TOUT = re.compile(r'\.hidden\s*=(?!=)')
# Une fonction d'aide MASQUEUSE : son premier paramètre passe tel quel à `$(…)`, dont elle
# bascule le `hidden`. Ses appels à littéral se résolvent ; les autres sont des orphelins.
MASQUEUSE = re.compile(r'function\s+(\w+)\s*\(\s*(\w+)[^)]*\)\s*\{\s*'
                       r'\$\(\s*\2\s*\)\.hidden\s*=')
# Un `for … of` sur un tableau ÉCRIT de littéraux `"#…"` : un `$(nom)` dans son corps vise
# chacun d'eux.
POUR = re.compile(r'for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s+\[([^\]]*)\]\s*\)')
LITTERAL = re.compile(r'\s*"#([a-z0-9-]+)"\s*')

# Les affectations dont la cible ne remonte à aucun `$("#…")`, avec la raison de les
# laisser hors du balayage. Une entrée par (fichier, nom de variable).
NON_RESOLUS = {
    ("exploration.js", "el"): (
        "Le paramètre d'un `forEach` sur `.sub-title` : la cible est une CLASSE, pas un "
        "identifiant, donc `getElementById` ne l'atteint pas. Vérifié à la main le "
        "2026-09-04 — `.sub-title` ne pose aucun `display`, l'attribut agit. Le jour où "
        "le balayage saura viser un sélecteur, cette entrée disparaît."),
    ("corpus.js", "partie"): (
        "Les quatre panneaux de la fiche d'une collection (UX-18) — Albums, Qui entre, "
        "Description, Diffusion et dépôt —, parcourus par `querySelectorAll('[role=tabpanel]')` "
        "quand on change d'onglet : la cible est un RÔLE, pas un identifiant écrit dans un "
        "`$(\"#…\")`. `.bi-panneau` ne pose aucun `display`, l'attribut agit ; vérifié le "
        "2026-10-17 par `test_e2e_bibliotheque.test_la_fiche_d_une_collection_a_quatre_onglets`, "
        "qui exige un seul panneau VISIBLE à la fois."),
    ("bac-a-sable.js", "voile"): (
        "Le voile des dialogues de la ligne du bac à sable (COL-4), créé au premier dialogue "
        "par `el(\"div\", \"bac-modal\")` : la cible a un identifiant (`#bac-modal`) mais naît "
        "d'un `createElement`, que la résolution ne remonte pas. Elle pose `display: flex`, "
        "d'où le garde `.bac-modal[hidden] { display: none; }` dans la feuille — vérifié le "
        "2026-10-24 par `tests/test_e2e_bac_a_sable.py`, qui exige le dialogue VISIBLE à "
        "l'ouverture et CACHÉ après « Annuler »."),
    ("wizard.js", "voile"): (
        "Le voile de l'album et de la carte de « Par où commencer » (UX-6), créé à la "
        "première ouverture par `el(\"div\", \"wizard-modal\")` : la cible a un identifiant "
        "(`#wizard-modal`) mais naît d'un `createElement`, que la résolution ne remonte pas. "
        "Elle pose `display: flex`, d'où le garde `.wizard-modal[hidden] { display: none; }` "
        "dans la feuille — vérifié le 2026-11-03 par `tests/test_e2e_wizard.py`, qui exige "
        "l'album VISIBLE à l'ouverture et CACHÉ après « Fermer ✕ »."),
    ("wizard.js", "foyer"): (
        "Le conteneur de la fenêtre sur la zone et de son assombri (UX-6, la visite des "
        "pages et le « ? »), créé à la première ouverture par `el(\"div\", \"wizard-foyer\")` : "
        "même cas que le voile de l'album. Il ne pose aucun `display`, et le garde "
        "`.wizard-foyer[hidden] { display: none; }` est dans la feuille quand même — vérifié "
        "le 2026-11-04 par `tests/test_e2e_wizard.py`, qui exige la fenêtre VISIBLE à "
        "l'ouverture et CACHÉE après Échap."),
    ("lib/champ-personnage.js", "sug"): (
        "La liste des propositions du champ « personnage », que l'hôte CONFIE au montage "
        "(`#loc-suggest` et `#perso-suggest` dans l'Atelier, `#an-loc-liste` et "
        "`#an-perso-liste` sur la page Annotation) : la cible est un paramètre, pas un "
        "identifiant écrit ici. `.tag-suggest` "
        "ne pose aucun `display`, l'attribut agit — vérifié le 2026-10-30 par "
        "`test_e2e_annotation_page.test_le_locuteur_se_choisit_et_se_retire_dans_le_contexte`, "
        "qui exige la liste VISIBLE pendant la saisie et CACHÉE après le choix. Dans "
        "`viewer.js`, `sug.hidden` se rattachait jusque-là, par la définition la plus proche en "
        "amont, à un autre `sug` du fichier : un hasard de la résolution, pas une couverture."),
    ("annotation.js", "retirer"): (
        "Le « × » d'un lien du Contexte, `#an-loc-retirer` ou `#an-perso-retirer` : la page "
        "traite le locuteur et le personnage d'une boîte par une même fonction "
        "(`montrerLien`), qui compose l'identifiant (`idLien`). Un bouton `.ghost.small."
        "an-loc-x` ne pose aucun `display`, l'attribut agit — vérifié le 2026-11-05 dans les "
        "deux sens par `test_e2e_annotation_page."
        "test_le_personnage_d_une_boite_se_choisit_et_se_retire_dans_le_contexte`, qui l'exige "
        "CACHÉ une fois le personnage retiré, et `test_une_lectrice_lit_les_doutes_sans_aucun_"
        "geste`, CACHÉ chez une lectrice ; `test_le_locuteur_se_choisit_et_se_retire_dans_le_"
        "contexte` le clique, donc VISIBLE."),
    ("annotation.js", '$(idLien(lieu, "liste"))'): (
        "La liste des propositions d'un lien du Contexte, `#an-loc-liste` ou "
        "`#an-perso-liste`, vidée au changement de zone : même composition que le « × » "
        "(`idLien`). Mesurée par la sonde, ses deux identifiants déclarés dans `IDS_DECLARES`."),
    ("annotation.js", 'montrer(idLien(lieu, "saisie"))'): (
        "Le champ d'un lien du Contexte, `#an-loc-saisie` ou `#an-perso-saisie`, montré à "
        "qui écrit : la fonction d'aide `montrer` reçoit un identifiant COMPOSÉ (`idLien`), "
        "que la résolution des appels à littéral ne lit pas. Mesuré par la sonde, ses deux "
        "identifiants déclarés dans `IDS_DECLARES`."),
    ("exploration.js", 'sel.closest("label")'): (
        "Le libellé « Importer dans » de la modale du 📖 Lexique, l'ancêtre `<label>` de "
        "`#lex-import-portee`, retiré à qui n'écrit nulle part : la cible est atteinte par "
        "`closest`, et n'a pas d'identifiant. `.lex-import-portee` pose `display: "
        "inline-flex`, d'où le garde `.modal-box label[hidden] { display: none; }` dans la "
        "feuille — vérifié le 2026-11-05 par `test_e2e_import_vocabulaire."
        "test_qui_n_ecrit_nulle_part_lit_pourquoi_le_menu_est_ferme`, qui exige le menu CACHÉ "
        "chez une lectrice, et `test_le_menu_importer_dans_n_offre_que_les_collections_ou_l_"
        "on_ecrit`, VISIBLE chez qui écrit."),
    ("annotation.js", "fiche"): (
        "« Fiche » d'un lien du Contexte, `#an-loc-fiche` ou `#an-perso-fiche` : même "
        "composition que le « × ». `.ghost.small.an-loc-fiche` ne pose aucun `display` — "
        "vérifié le 2026-11-05 dans les deux sens par `test_e2e_annotation_page."
        "test_la_fiche_d_un_personnage_s_ouvre_du_locuteur_et_de_la_boite`, qui l'exige "
        "VISIBLE avec un personnage et CACHÉ une fois le personnage retiré."),
    ("lib/alignements.js", "sec"): (
        "La section de l'alignement d'autorité, que l'hôte CONFIE au montage "
        "(`#loc-align-section` et `#perso-align-section` dans l'Atelier, `#an-align` dans la "
        "fiche d'un personnage de la page Annotation) : un paramètre, pas un identifiant écrit "
        "ici. Aucune des trois ne pose de `display`, l'attribut agit — vérifié le 2026-11-05 "
        "par `test_e2e_annotation_page.test_la_fiche_d_un_personnage_s_ouvre_du_locuteur_et_"
        "de_la_boite`, qui exige `#an-align` VISIBLE une fois la fiche ouverte. Dans "
        "`viewer.js`, `sec.hidden` se rattachait jusque-là, par la définition la plus proche "
        "en amont, à `#perso-section` : un hasard de la résolution."),
    ("lib/alignements.js", "saisie"): (
        "Ce qui porte le champ d'une URI, confié au montage — le champ lui-même par défaut "
        "(`#loc-align-input`, `#perso-align-input` dans l'Atelier, qui écrit toujours), "
        "`#an-align-saisie` dans la page Annotation. `.tag-input-wrap` et le champ ne posent "
        "aucun `display` — vérifié le 2026-11-05 dans les deux sens par "
        "`test_e2e_annotation_page`, qui l'exige VISIBLE sur un album où l'on écrit et CACHÉ "
        "chez une lectrice (`test_une_lectrice_lit_les_doutes_sans_aucun_geste`)."),
    ("lib/membres-projet.js", "libre"): (
        "La saisie libre de « Qui y entre » d'un projet (COL-3), une par partie montée, sur "
        "le patron de celle de « Qui entre » : la cible est la CLASSE `.mp-libre`, cherchée "
        "dans sa section, pas un identifiant. Elle pose `display: inline-flex`, d'où le garde "
        "`.mp-libre[hidden] { display: none; }` dans la feuille — vérifié le 2026-10-10 dans "
        "les deux sens par deux tests e2e : "
        "`test_faire_entrer_un_groupe_part_avec_le_role_de_membre` l'exige CACHÉE, "
        "`test_faire_entrer_un_compte_demande_de_dire_ce_qu_il_est` VISIBLE."),
}

# Les identifiants que désigne une déclaration de `NON_RESOLUS`, quand on sait les nommer
# sans interpréter le script (une composition fermée, comme `idLien` : `loc` ou `perso`).
# La sonde les mesure sur la surface du script, comme les cibles résolues : déclarer n'est
# alors plus excuser. `test_les_identifiants_declares_existent` vérifie qu'ils sont dans un
# gabarit, et que leur déclaration existe.
IDS_DECLARES = {
    ("annotation.js", "retirer"): ("an-loc-retirer", "an-perso-retirer"),
    ("annotation.js", "fiche"): ("an-loc-fiche", "an-perso-fiche"),
    ("annotation.js", '$(idLien(lieu, "liste"))'): ("an-loc-liste", "an-perso-liste"),
    ("annotation.js", 'montrer(idLien(lieu, "saisie"))'): ("an-loc-saisie", "an-perso-saisie"),
}


def _sauter_chaine_a_reculons(source: str, j: int) -> int:
    """`source[j]` ferme une chaîne : l'indice juste avant son ouverture."""
    q, k = source[j], j - 1
    while k >= 0 and not (source[k] == q and (k == 0 or source[k - 1] != "\\")):
        k -= 1
    return k - 1


def _expression_avant(source: str, fin: int) -> str:
    """L'expression qui précède `.hidden` en `fin` : une chaîne de noms, de points, d'appels
    et d'indices, lue à reculons en sautant les parenthèses, les crochets et les chaînes.
    Elle NOMME l'orphelin dans `NON_RESOLUS` ; rien n'en est interprété."""
    i = fin
    while i > 0:
        c = source[i - 1]
        if c in ")]":
            profondeur, j = 0, i - 1
            while j >= 0:
                d = source[j]
                if d in "\"'`":
                    j = _sauter_chaine_a_reculons(source, j)
                    continue
                if d in ")]":
                    profondeur += 1
                elif d in "([":
                    profondeur -= 1
                    if profondeur == 0:
                        break
                j -= 1
            i = max(j, 0)
        elif c.isalnum() or c in "_$.":
            i -= 1
        else:
            break
    return re.sub(r"\s+", " ", source[i:fin]).strip()


def _premier_argument(source: str, ouvrante: int) -> str:
    """Le texte du premier argument d'un appel dont la parenthèse ouvrante est en
    `ouvrante`, jusqu'à la virgule ou la parenthèse de même profondeur."""
    profondeur, j = 0, ouvrante + 1
    while j < len(source):
        c = source[j]
        if c in "([{":
            profondeur += 1
        elif c in ")]}":
            if profondeur == 0:
                break
            profondeur -= 1
        elif c == "," and profondeur == 0:
            break
        elif c in "\"'`":
            k = j + 1
            while k < len(source) and not (source[k] == c and source[k - 1] != "\\"):
                k += 1
            j = k
        j += 1
    return re.sub(r"\s+", " ", source[ouvrante + 1:j]).strip()


def _corps_du_pour(source: str, fin: int) -> tuple:
    """L'étendue du corps d'un `for (…)` qui se ferme en `fin` : un bloc `{…}`, ou
    l'instruction seule jusqu'à son `;`."""
    i = fin
    while i < len(source) and source[i].isspace():
        i += 1
    if i < len(source) and source[i] == "{":
        profondeur = 0
        for j in range(i, len(source)):
            if source[j] == "{":
                profondeur += 1
            elif source[j] == "}":
                profondeur -= 1
                if profondeur == 0:
                    return i, j
        return i, len(source)
    j = source.find(";", i)
    return i, (j if j >= 0 else len(source))


def cibles(source: str):
    """Les identifiants dont le script bascule le `hidden`, et ce qu'il n'a pas su lire.

    Chaque `X.hidden` remonte à la définition de `X` la plus proche EN AMONT — la portée
    réelle du code, et non la dernière définition du fichier.

    ANN-7 — puis chaque `.hidden =` qu'aucune forme n'a résolu devient un orphelin, nommé par
    son expression (`$(idLien(lieu, "liste"))`) : l'inventaire part de TOUTES les
    affectations, jamais de ce que les motifs savent lire. Une fonction d'aide masqueuse est
    résolue par ses appels : à littéral, l'identifiant ; sinon un orphelin nommé
    `montrer(<argument>)`.
    """
    def ligne(pos):
        return source[:pos].count("\n") + 1

    defs = [(m.start(), m.group(1), m.group(2) or m.group(3))
            for m in AFFECT.finditer(source)]
    ids, orphelins, vus = set(DIRECT.findall(source)), [], set()
    for m in DIRECT.finditer(source):
        vus.add(m.start() + m.group(0).rindex(".hidden"))
    for m in VAR.finditer(source):
        vus.add(m.end(1))
        amont = [i for (pos, nom, i) in defs if nom == m.group(1) and pos < m.start()]
        if amont:
            ids.add(amont[-1])
        else:
            orphelins.append((ligne(m.start()), m.group(1)))
    # Les fonctions d'aide masqueuses : leur propre affectation est résolue par leurs appels.
    for m in MASQUEUSE.finditer(source):
        vus.add(m.start() + m.group(0).rindex(".hidden"))
        definition = m.start(1)
        for appel in re.finditer(r'(?<![.\w])' + re.escape(m.group(1)) + r'(?![\w])', source):
            if appel.start() == definition:
                continue
            parenthese = re.compile(r'\s*\(').match(source, appel.end())
            if not parenthese:
                # Passée en valeur, `ids.forEach(montrer)` : entre `(` ou `,` et `)` ou `,`.
                # Le nom seul ne suffit pas — « montrer » est aussi un mot des commentaires.
                if (re.compile(r'[(,]\s*$').search(source, 0, appel.start())
                        and re.compile(r'\s*[,)]').match(source, appel.end())):
                    orphelins.append((ligne(appel.start()), m.group(1)))
                continue
            arg = _premier_argument(source, parenthese.end() - 1)
            lit = LITTERAL.fullmatch(arg)
            if lit:
                ids.add(lit.group(1))
            else:
                orphelins.append((ligne(appel.start()), f"{m.group(1)}({arg})"))
    # Un `$(nom)` dans le corps d'un `for (const nom of ["#a", "#b"])`.
    for m in POUR.finditer(source):
        elements = [e for e in m.group(2).split(",") if e.strip()]
        lits = [LITTERAL.fullmatch(e) for e in elements]
        if not elements or not all(lits):
            continue
        debut, fin = _corps_du_pour(source, m.end())
        motif = re.compile(r'\$\(\s*' + re.escape(m.group(1)) + r'\s*\)\.hidden\s*=')
        for a in motif.finditer(source, debut, fin + 1):
            vus.add(a.start() + a.group(0).rindex(".hidden"))
            ids.update(x.group(1) for x in lits)
    # Tout le reste est un orphelin, quelle qu'en soit la forme.
    for m in TOUT.finditer(source):
        if m.start() not in vus:
            orphelins.append((ligne(m.start()), _expression_avant(source, m.start())))
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
    # ANN-7 — ce qu'une déclaration sait nommer se mesure comme le reste.
    ids = sorted(set(ids) | {i for (s, _n), declares in IDS_DECLARES.items() if s == script
                             for i in declares})
    # COL-4 — les cibles du script partagé valent sur chaque surface : il y est chargé.
    for partage in SCRIPTS_PARTAGES:
        ids = sorted(set(ids) | set(cibles((RACINE / "static" / partage).read_text(
            encoding="utf-8"))[0]))
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
        + ", ".join(f"`{nom}` ligne {ligne}" for ligne, nom in non_declares)
        + ". Soit la cible reçoit un identifiant, soit l'entrée rejoint `NON_RESOLUS` "
          "avec la raison de l'y laisser ET la vérification faite à la main.")


@pytest.mark.parametrize("script", sorted(MODULES_MONTES) + sorted(SCRIPTS_PARTAGES))
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
        + ", ".join(f"`{nom}` ligne {ligne}" for ligne, nom in non_declares)
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
        if TOUT.search(p.read_text(encoding="utf-8")))
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
    scripts = set(SURFACES_AUDITEES.values()) | set(MODULES_MONTES) | set(SCRIPTS_PARTAGES)
    mortes = []
    for (script, nom) in NON_RESOLUS:
        if script not in scripts:
            mortes.append((script, nom, "fichier hors du balayage"))
            continue
        _, orphelins = cibles((RACINE / "static" / script).read_text(encoding="utf-8"))
        if nom not in {n for _, n in orphelins}:
            mortes.append((script, nom, "plus aucune affectation de ce nom"))
    assert not mortes, f"déclarations sans objet dans NON_RESOLUS : {mortes}"


def test_les_identifiants_declares_existent():
    """Une déclaration qui nomme ses identifiants les fait mesurer : il faut qu'elle existe
    (sans quoi l'entrée de `IDS_DECLARES` ne désignerait rien de déclaré), et que chacun soit
    un `id="…"` d'un gabarit — un identifiant perdu sortirait de la sonde sans rien dire,
    puisqu'elle passe ce qu'elle ne trouve pas."""
    gabarits = "".join(p.read_text(encoding="utf-8")
                       for p in (RACINE / "templates").glob("*.html"))
    sans_declaration = [k for k in IDS_DECLARES if k not in NON_RESOLUS]
    perdus = [i for declares in IDS_DECLARES.values() for i in declares
              if f'id="{i}"' not in gabarits]
    assert not sans_declaration, f"IDS_DECLARES hors de NON_RESOLUS : {sans_declaration}"
    assert not perdus, f"identifiants déclarés absents de tout gabarit : {perdus}"


def test_les_motifs_mordent_sur_chaque_forme():
    """La garde de la garde : chaque forme est jouée sur une source écrite exprès. Une forme
    que l'extraction cesserait de résoudre doit tomber en orphelin, jamais disparaître — c'est
    l'angle mort fermé le 2026-11-05 : `$(idLien(…)).hidden` et `montrer(id, oui)` sortaient
    du balayage sans être comptés."""
    source = """
const a = $("#direct-par-variable");
a.hidden = true;
$("#direct").hidden = false;
function montrer(id, oui) { $(id).hidden = !oui; }
montrer("#par-l-aide", true);
montrer(idLien(lieu, "x"), false);
[1, 2].forEach(montrer);
for (const id of ["#boucle-1", "#boucle-2"]) $(id).hidden = true;
for (const id of ["#bloc"]) { faire(); $(id).hidden = false; }
$(id).hidden = true;
$(idLien(lieu, "liste")).hidden = true;
sel.closest("label").hidden = !ouvert;
lignes[i].hidden = false;
if (x.hidden === true) {}
orphelin.hidden = true;
"""
    ids, orphelins = cibles(source)
    assert ids == sorted(["direct-par-variable", "direct", "par-l-aide",
                          "boucle-1", "boucle-2", "bloc"]), ids
    assert sorted(n for _, n in orphelins) == sorted([
        "orphelin",                       # VAR sans définition : comme avant
        "x",                              # une comparaison que VAR prend : comme avant
        'montrer(idLien(lieu, "x"))',     # l'aide, appelée sans littéral
        "montrer",                        # l'aide, passée en valeur
        "$(id)",                          # hors du corps des boucles : pas résolu par elles
        '$(idLien(lieu, "liste"))',
        'sel.closest("label")',
        "lignes[i]",
    ]), orphelins
