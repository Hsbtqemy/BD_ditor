"""Ce que l'Atelier ANNONCE comme touche, déclaré ici — et RATTACHÉ à ce qui l'éprouve (UX-15).

**Pourquoi ce module vit hors de l'audit navigateur.** La déclaration et ses deux
contrôles ne demandent ni Chromium ni serveur : ils lisent un source. Laissés dans
`test_e2e_transcription_promesses.py`, ils héritaient de son `pytestmark = e2e` et ne
tournaient QUE dans la passe navigateur — un renommage de test y laissait une promesse
orpheline pendant les vingt-trois minutes qui séparent une suite par défaut d'une passe
e2e. Leur jumeau doctrinal, `test_surfaces`, est dans la suite par défaut ; celui-ci doit
l'être aussi. Poser le marqueur test par test n'aurait pas suffi : le module d'audit
commence par un `importorskip` de Playwright, si bien que là où il n'est pas installé —
l'étape `test` de l'image, qui pèse un giga de moins que l'étape `e2e` — le contrôle
serait sauté pour une raison ÉTRANGÈRE à ce qu'il contrôle.

**Et c'est pourquoi il lit par AST plutôt qu'en important.** Même argument que
`tests/surfaces.py`, à l'identique : importer le module joueur ferait entrer Playwright
par la porte de derrière et rendrait ce contrôle indisponible précisément là où il coûte
le moins.

**Ce que ferme le second contrôle, et il a été mesuré manquant.** La première version se
contentait d'exiger que le test nommé EXISTE. Une revue a alors déclaré qu'un couple était
joué par un test qui ne presse jamais cette touche : la garde a approuvé. C'est
exactement ce que `test_surfaces.test_la_declaration_est_RATTACHEE_a_ce_que_le_module_fait`
ferme un étage plus haut — une déclaration qu'aucun mécanisme ne confronte à son objet est
une intention, et une intention vieillit.
"""
import ast
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
# Le module qui PRESSE les touches. Nommé une fois, ici : deux copies de ce chemin
# finiraient par désigner deux fichiers.
MODULE_JOUEUR = DOSSIER / "test_e2e_transcription_promesses.py"

RAISON_MINIMALE = 30   # « à voir » et « hors sujet » ne sont pas des raisons
JOUEE = "jouée par "

# Les quatre modes de l'Atelier. Une annonce ne vaut pas forcément dans tous, et depuis le
# 2026-09-24 c'est même le sujet : les badges de raccourci s'ÉTEIGNENT pendant la
# Transcription, où la touche ne peut pas marcher. Le recensement compare donc MODE PAR
# MODE — une union aurait gardé les badges au tableau et n'aurait rien vu s'éteindre.
MODES = ("navigation", "edition", "annotation", "transcription")
PARTOUT = MODES
# Éteints pendant la Transcription : cf. `.modes.sans-raccourcis` dans `style.css`.
HORS_TRANSCRIPTION = ("navigation", "edition", "annotation")
# Les libellés qui vivent DANS le panneau : `#transcription[hidden]` les retire ailleurs.
PANNEAU = ("transcription",)
# `#panel-edition` est `hidden` hors du mode Édition.
EDITION = ("edition",)

BADGES = JOUEE + "test_les_badges_de_mode_tiennent_leur_promesse"
FLECHES = JOUEE + "test_les_fleches_de_l_arbre_tiennent_leur_promesse"
BARRE_D_AIDE = JOUEE + "test_la_barre_d_aide_tient_ses_promesses_de_navigation"

# Ce que redit le texte indicatif de la zone de saisie. UNE chaîne, parce que deux copies
# au caractère près sont deux occasions de diverger sans que rien ne le signale.
REDIT_LA_BARRE_D_AIDE = (
    "même touche et même effet que la barre d'aide juste au-dessous, jouée là — la "
    "rejouer ici mesurerait deux fois le même écouteur, celui de `#tr-text`")


# ---------------------------------------------------------------------------
# Ce que l'Atelier ANNONCE, et ce que la garde en fait.
#
# La clé est `(porteur, touche)` : le porteur est l'élément qui affiche le libellé, désigné
# par son `id` s'il en a un, sinon par son tag et sa première classe. La valeur dit DEUX
# choses — dans quels modes l'annonce est FAITE, et comment la promesse est tenue :
# « jouée par <test> », ou la raison de ne pas la jouer.
#
# Six porteurs, douze touches distinctes, quatorze couples.
# ---------------------------------------------------------------------------
PROMESSES = {
    # Les quatre badges de mode : un `<kbd>` VISIBLE dans le bouton, et lui SEUL depuis
    # le 2026-09-24 — le `title` ne porte plus que le nom. Une promesse à deux endroits
    # est un endroit qu'on oublie d'éteindre.
    ("button.mode-btn", "N"): (HORS_TRANSCRIPTION, BADGES),
    ("button.mode-btn", "E"): (HORS_TRANSCRIPTION, BADGES),
    ("button.mode-btn", "A"): (HORS_TRANSCRIPTION, BADGES),
    ("button.mode-btn", "T"): (HORS_TRANSCRIPTION, BADGES),

    # Déplacement d'une région dans l'arbre de structure (nœud courant seulement).
    ("button.tn-mv", "Alt+↑"): (PARTOUT, FLECHES),
    ("button.tn-mv", "Alt+↓"): (PARTOUT, FLECHES),

    # Le seul libellé qui n'annonce PAS un raccourci clavier.
    ("p.edit-hint", "Maj"): (
        EDITION,
        "ce n'est pas un raccourci mais un geste de SOURIS — « Maj+glisser dans une case » "
        "— et la touche seule ne promet rien qu'on puisse presser : la jouer au clavier "
        "mesurerait autre chose que ce que la phrase annonce"),

    # Le panneau de Transcription : la famille d'où vient le défaut, le focus y vivant
    # TOUJOURS dans la zone de saisie (`renderTranscription()` la focalise à chaque rendu).
    ("#tr-exit", "Échap"): (PANNEAU, JOUEE + "test_le_bouton_de_sortie_tient_la_touche_qu_il_affiche"),
    ("div.tr-hint", "Tab"): (PANNEAU, BARRE_D_AIDE),
    ("div.tr-hint", "Maj+Tab"): (PANNEAU, BARRE_D_AIDE),
    ("div.tr-hint", "Ctrl+Entrée"): (PANNEAU, BARRE_D_AIDE),
    ("div.tr-hint", "Entrée"): (PANNEAU, JOUEE + "test_entree_reste_un_retour_a_la_ligne"),
    # Le texte indicatif de la zone de saisie REDIT deux touches de la barre d'aide.
    ("#tr-text", "Tab"): (PANNEAU, REDIT_LA_BARRE_D_AIDE),
    ("#tr-text", "Ctrl+Entrée"): (PANNEAU, REDIT_LA_BARRE_D_AIDE),
}

# Traduction des noms français affichés vers les touches de Playwright. Elle sert à JOUER
# ce qu'on a lu : une annonce intraduisible est une annonce qu'on ne peut pas éprouver,
# et le module joueur le dit plutôt que de la sauter.
CLAVIER = {
    "Échap": "Escape", "Tab": "Tab", "Entrée": "Enter", "Espace": "Space",
    "Maj+Tab": "Shift+Tab", "Ctrl+Entrée": "Control+Enter",
    "Alt+↑": "Alt+ArrowUp", "Alt+↓": "Alt+ArrowDown",
    "N": "n", "E": "e", "A": "a", "T": "t",
}


# ---------------------------------------------------------------------------
# Lecture du module joueur
# ---------------------------------------------------------------------------
def fonctions_du_joueur():
    """`{nom: nœud}` des fonctions définies dans le module qui presse les touches."""
    arbre = ast.parse(MODULE_JOUEUR.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(arbre)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def constantes_du_corps(fonction):
    """Les chaînes littérales du CORPS d'une fonction, DOCSTRING EXCLUE.

    L'exclusion est le cœur du contrôle : une docstring qui nomme une touche l'a citée,
    pas pressée. Les laisser entrer rendrait le rattachement satisfaisable en écrivant
    une phrase — c'est-à-dire par le geste même qu'on veut rendre insuffisant.

    `ast.walk` traverse les f-strings : la partie littérale d'un `f"#{s['premiere']}"`
    est bien `"#"`, et le sélecteur qu'on cherche y apparaît quand il est écrit en clair.
    """
    corps = fonction.body
    if (corps and isinstance(corps[0], ast.Expr)
            and isinstance(corps[0].value, ast.Constant)
            and isinstance(corps[0].value.value, str)):
        corps = corps[1:]
    return [n.value for instruction in corps for n in ast.walk(instruction)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def joue_bien(constantes, porteur, touche):
    """La touche est PRESSÉE, ou le porteur est INTERROGÉ — l'un des deux suffit.

    Il faut les deux branches, et la seconde n'est pas une facilité : le test de la
    sortie ne contient pas le littéral « Échap », et c'est sa VERTU — il demande au
    bouton ce qu'il annonce et presse ce qu'il a lu, si bien qu'un retour à
    « Quitter (N) » le ferait tomber. Exiger la touche en dur là récompenserait le test
    en miroir et punirait le test qui mesure.

    Le sens de l'imprécision est choisi, comme dans `surfaces.chemins_cites` : une
    constante `"N"` incidente rendrait le contrôle plus PERMISSIF, jamais plus bruyant.
    """
    return any(c == touche or porteur in c for c in constantes)


# ---------------------------------------------------------------------------
# Les deux contrôles
# ---------------------------------------------------------------------------
def test_chaque_promesse_est_jouee_ou_ecartee_avec_sa_raison():
    """Une déclaration n'est pas un classement : elle dit ce qu'on FAIT de l'annonce.

    Sans ce contrôle, `PROMESSES` deviendrait la case où ranger ce qu'on ne veut pas
    éprouver — le risque propre à toute liste d'exceptions, qui rend l'omission visible
    puis offre l'endroit où la faire taire.
    """
    fonctions = fonctions_du_joueur()
    assert fonctions, (
        f"aucune fonction lue dans {MODULE_JOUEUR.name} : le module a été renommé ou "
        "déplacé, et les deux contrôles de ce fichier sont devenus vacants sans échouer")

    for (porteur, touche), (modes, quoi) in PROMESSES.items():
        # Les modes d'abord : une liste vide, ou un mode qui n'existe pas, rendrait la
        # comparaison du recensement vacante SUR CETTE LIGNE sans rien faire tomber.
        assert modes and set(modes) <= set(MODES), (
            f"({porteur}, {touche!r}) déclare les modes {modes!r} : vides, ou hors de "
            f"{MODES}. Le recensement ne comparerait plus rien pour cette annonce")
        if quoi.startswith(JOUEE):
            nom = quoi[len(JOUEE):].strip()
            assert nom in fonctions, (
                f"({porteur}, {touche!r}) se dit jouée par `{nom}`, qui n'existe pas dans "
                f"{MODULE_JOUEUR.name} : la promesse n'est éprouvée par personne")
        else:
            assert len(quoi.strip()) >= RAISON_MINIMALE, (
                f"({porteur}, {touche!r}) est écartée sans raison lisible : {quoi!r}")


def test_la_promesse_jouee_est_RATTACHEE_au_test_qui_la_joue():
    """« Jouée par X » ne doit pas tenir au seul NOM de X.

    Mesuré manquant le 2026-09-23 : une revue a déclaré un couple joué par un test qui
    ne presse jamais cette touche, et la garde d'à côté — qui vérifiait l'existence du
    nom — a approuvé. Le nom est un lien vers un fichier, pas vers un geste.

    On exige donc que le corps du test NOMME la chose : la touche telle qu'elle est
    pressée (`CLAVIER["Tab"]`), ou le sélecteur du porteur qu'il interroge
    (`querySelector('#tr-exit')`). Ce n'est pas la preuve qu'il la presse bien — rien ne
    le serait, hors du navigateur — mais c'est ce qui rend le rattachement FAUX
    détectable, et c'est le seul mode d'échec qu'on ait vu se produire.
    """
    fonctions = fonctions_du_joueur()
    orphelines = []
    for (porteur, touche), (_modes, quoi) in PROMESSES.items():
        if not quoi.startswith(JOUEE):
            continue
        nom = quoi[len(JOUEE):].strip()
        fonction = fonctions.get(nom)
        if fonction is None:
            continue          # dit par le contrôle voisin, avec sa propre phrase
        if not joue_bien(constantes_du_corps(fonction), porteur, touche):
            orphelines.append(f"({porteur}, {touche!r}) → `{nom}`")

    assert not orphelines, (
        "des promesses se disent jouées par un test dont le corps ne nomme ni leur touche "
        "ni leur porteur : " + " ; ".join(orphelines)
        + ". Soit la déclaration désigne le mauvais test — et la touche n'est alors "
        "pressée par personne, ce qu'un nom juste dissimulait —, soit le test a cessé de "
        "la presser et la déclaration ne l'a pas suivi")
