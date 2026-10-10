"""UX-16 — « Qui entre » est un module, et il n'est écrit qu'UNE fois.

Le panneau a déménagé deux fois en treize jours, et chaque déménagement a recopié cinq cents
lignes d'un fichier de surface dans un autre. Il est désormais monté — dans la Bibliothèque,
pour le propriétaire, et dans l'Administration, pour l'administrateur — depuis
`static/lib/qui-entre.js`. Ce fichier garde la COUTURE : ce que rien d'autre n'empêcherait
de revenir.

**La faute visée n'échoue pas.** Un hôte qui se remettrait à dessiner une ligne d'accès, ou
à appeler `…/acces` lui-même « juste pour ce cas », fonctionnerait parfaitement : les deux
écrans divergeraient d'un libellé, puis d'une règle, et le premier à s'en apercevoir serait
quelqu'un qui règle un accès. C'est le même mode d'échec que les deux portes vers la même
pièce d'UX-10 — celle qu'on ne regarde plus vieillit.

Il ne lit que des SOURCES et tourne dans la suite par défaut. Les gestes, eux, se jouent
dans un navigateur, un fichier par montage : `tests/test_e2e_qui_entre.py` pour la
Bibliothèque, `tests/test_e2e_qui_entre_administration.py` pour l'Administration.
"""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
STATIC = RACINE / "static"
MODULE = STATIC / "lib" / "qui-entre.js"

# Les hôtes : les scripts de surface qui montent le module, avec le gabarit qui les sert.
HOTES = {
    "corpus.js": "corpus.html",
    "administration.js": "administration.html",
}

# Les hôtes qui ont une FICHE à ouvrir pour un compte ou un groupe, et passent donc
# `surOuvrir` au montage. La Bibliothèque n'en est pas : un propriétaire n'y a aucune fiche
# de compte, et un nom cliquable n'y mènerait nulle part.
OUVRENT_UNE_FICHE = {"administration.js"}

# Ce qui appartient au module et à lui seul. Le balisage : toute classe ou tout identifiant
# `qe-…` ; la classe `qe` nue dans un sélecteur (`.qe`, mais pas la propriété `x.qe`) ; et
# `class="… qe …"`. Les routes : les deux lectures et les deux écritures d'un accès.
BALISAGE = re.compile(r"""(?<![\w-])qe-[a-z]|(?<![\w.-])\.qe(?![\w-])|class=["'][^"']*\bqe\b""")
ROUTES = re.compile(r"/acces\b|/annuaire\b")


def _sans_commentaires(source: str) -> str:
    """Le code, sans ses commentaires : un hôte a le droit de RACONTER le panneau.

    Retirés par blocs `/* … */` puis par fins de ligne `// …`. La seconde passe épargne
    `://` — sans quoi une adresse écrite dans le code serait amputée, et la garde lirait
    autre chose que le fichier.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", source)


def test_le_module_porte_bien_ce_que_la_garde_cherche():
    """Le plancher. Une garde qui cherche des motifs absents de PARTOUT passe au vert.

    Si le module renommait ses classes ou ses routes, les deux motifs ci-dessus ne
    trouveraient plus rien nulle part — ni dans les hôtes, ni ailleurs — et le test suivant
    approuverait un hôte qui recopie le panneau sous son nouveau nom. Ils doivent donc
    MORDRE sur le module lui-même.
    """
    code = _sans_commentaires(MODULE.read_text(encoding="utf-8"))
    assert len(BALISAGE.findall(code)) >= 20, (
        "le motif du balisage ne reconnaît plus le module : la garde des hôtes est vacante")
    assert len(ROUTES.findall(code)) >= 2, (
        "le motif des routes ne reconnaît plus le module : la garde des hôtes est vacante")


@pytest.mark.parametrize("script", sorted(HOTES))
def test_aucun_hote_n_ecrit_le_panneau_ni_n_appelle_ses_routes(script):
    """Un hôte MONTE le module ; il ne dessine rien du panneau et ne lit pas ses données.

    Lu hors commentaires : le code seul compte. Une mention dans une chaîne compte aussi, et
    c'est voulu — un sélecteur `.qe-titre` dans un hôte, c'est déjà l'hôte qui sait comment
    le module est fait (d'où `focaliser()`, que la poignée expose pour qu'il n'ait pas à le
    savoir).
    """
    code = _sans_commentaires((STATIC / script).read_text(encoding="utf-8"))
    balisage = sorted(set(m.group(0).strip() for m in BALISAGE.finditer(code)))
    assert not balisage, (
        f"{script} écrit ou vise du balisage du panneau « Qui entre » : {balisage}. Il vit "
        "dans static/lib/qui-entre.js ; un hôte n'en connaît que `monter()` et sa poignée.")
    routes = sorted(set(ROUTES.findall(code)))
    assert not routes, (
        f"{script} appelle les routes d'accès d'une collection ({routes}) : le module lit et "
        "écrit SES données, sans quoi le contrat du serveur vivrait dans deux écrans.")


@pytest.mark.parametrize("script, gabarit", sorted(HOTES.items()))
def test_chaque_hote_monte_le_module_et_le_charge_a_temps(client, script, gabarit):
    """Un hôte listé ici monte réellement le module, et le gabarit le sert AVANT lui.

    Les deux moitiés tiennent ensemble : sans le montage, `HOTES` nommerait un fichier qui
    n'a plus rien à voir avec le panneau, et la garde ci-dessus tournerait sur lui pour
    rien ; sans la balise, `BDQuiEntre` n'existe pas et la page lève une `ReferenceError`
    au premier dépliage — pas au chargement, donc pas dans un test qui ouvre seulement la
    page.
    """
    code = _sans_commentaires((STATIC / script).read_text(encoding="utf-8"))
    assert "BDQuiEntre.monter(" in code, f"{script} ne monte plus le module"

    html = (RACINE / "templates" / gabarit).read_text(encoding="utf-8")
    module, page = "/static/lib/qui-entre.js", f"/static/{script}"
    assert module in html, f"{gabarit} ne charge pas le module"
    for avant in ("/static/lib/common.js", "/static/lib/droits.js"):
        assert html.index(avant) < html.index(module), (
            f"{gabarit} : {avant} doit précéder le module, qui s'en sert")
    assert html.index(module) < html.index(page), (
        f"{gabarit} : le module doit précéder {script}, qui le monte")

    servi = client.get(module)
    assert servi.status_code == 200
    assert "BDQuiEntre" in servi.text


@pytest.mark.parametrize("script", sorted(HOTES))
def test_seul_un_hote_qui_a_des_fiches_fait_des_noms_des_liens(script):
    """`surOuvrir` change ce que le panneau MONTRE : chaque nom y devient un bouton.

    La Bibliothèque est le témoin de l'extraction — son montage ne change pas à l'écran —,
    et rien d'autre ne l'empêcherait de recevoir l'option « pour faire pareil » : les noms y
    deviendraient des boutons vers des fiches qu'un propriétaire ne peut pas ouvrir. Le
    navigateur le mesure aussi (`test_e2e_qui_entre_administration`) ; ici, c'est la
    déclaration qui est tenue, dans la suite par défaut.
    """
    code = _sans_commentaires((STATIC / script).read_text(encoding="utf-8"))
    assert ("surOuvrir" in code) == (script in OUVRENT_UNE_FICHE), (
        f"{script} : `surOuvrir` {'manque' if script in OUVRENT_UNE_FICHE else 'est passé'} "
        "au montage, à l'inverse de ce que `OUVRENT_UNE_FICHE` déclare")
    assert OUVRENT_UNE_FICHE <= set(HOTES), "un hôte qui ouvre des fiches est d'abord un hôte"


def test_le_module_ne_fait_un_lien_d_un_nom_que_sur_demande():
    """Le plancher de la garde ci-dessus : le module lit bien une option de ce nom.

    S'il la renommait, les hôtes continueraient de passer `surOuvrir` dans le vide, les noms
    redeviendraient du texte partout, et le test précédent resterait vert."""
    code = _sans_commentaires(MODULE.read_text(encoding="utf-8"))
    assert code.count("options.surOuvrir") >= 2, (
        "le module ne lit plus `options.surOuvrir` : la déclaration des hôtes ne garde rien")


def test_tout_script_de_surface_qui_monte_le_module_est_un_hote_declare():
    """La porte de l'OUBLI : un montage ajouté ailleurs entre dans `HOTES`, ou échoue ici.

    Sans cela, la troisième surface à monter le panneau échapperait aux deux gardes
    ci-dessus en n'étant simplement pas dans la liste — et une liste écrite à la main oublie
    ce qu'on ajoute (leçon de `test_csp`, ARCH-2).
    """
    monteurs = sorted(
        p.name for p in STATIC.glob("*.js")
        if "BDQuiEntre" in _sans_commentaires(p.read_text(encoding="utf-8")))
    assert monteurs == sorted(HOTES), (
        f"scripts qui emploient BDQuiEntre : {monteurs} ; hôtes déclarés : {sorted(HOTES)}")
