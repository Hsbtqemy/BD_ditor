"""COL-3 — « Qui y entre » d'un projet est un module, et il n'est écrit qu'UNE fois.

Le frère de `test_qui_entre_module.py`, pour le frère de `qui-entre.js` : les membres d'un
projet se règlent par `static/lib/membres-projet.js`, monté dans la fiche du projet par
l'Administration. Ce fichier garde la COUTURE, avant qu'un second écran ne le monte — la
passe du projet, la fiche d'une collection — et pour la même raison que son aîné.

**La faute visée n'échoue pas.** Un hôte qui dessinerait lui-même une ligne de membre, ou
appellerait `…/membres` « juste pour ce cas », fonctionnerait parfaitement : deux écrans
divergeraient d'un libellé, puis d'une règle — entrer comme membre ici, comme responsable
là —, et le premier à s'en apercevoir serait quelqu'un qui règle un projet.

Il ne lit que des SOURCES et tourne dans la suite par défaut. Les gestes se jouent dans un
navigateur : `tests/test_e2e_projets.py`.
"""
import re
from pathlib import Path

import pytest

# Importé, pas recopié : la même lecture « hors commentaires » que la garde du module aîné,
# pour que les deux ne finissent pas par ne plus lire un fichier de la même façon.
from test_qui_entre_module import _sans_commentaires

RACINE = Path(__file__).resolve().parent.parent
STATIC = RACINE / "static"
MODULE = STATIC / "lib" / "membres-projet.js"

# Les hôtes : les scripts de surface qui montent le module, avec les gabarits qui les servent.
# COL-4 — `bac-a-sable.js` le monte dans le dialogue « Inviter… » de la ligne du bac à sable,
# sur les CINQ surfaces, réduit à ce qu'un bac à sable permet (`bacASable`).
HOTES = {
    "administration.js": ("administration.html",),
    "bac-a-sable.js": ("index.html", "recherche.html", "corpus.html", "exploration.html",
                       "administration.html"),
}
# Les hôtes qui passent le mode RÉDUIT d'un bac à sable : un hôte déclaré ici et nulle part
# ailleurs. Le mode retire l'annuaire, les groupes et le choix du rôle — passé par erreur
# dans la fiche d'un projet ordinaire, il y cacherait ce que son responsable doit régler.
HOTES_BAC_A_SABLE = {"bac-a-sable.js"}

# Ce qui appartient au module et à lui seul. Le balisage : toute classe ou tout identifiant
# `mp-…` ; la classe `mp` nue dans un sélecteur ; et `class="… mp …"`. Les routes : la
# lecture des membres, celle de l'annuaire (`…/membres/choix`) et les deux écritures — toutes
# passent par `/membres`.
BALISAGE = re.compile(r"""(?<![\w-])mp-[a-z]|(?<![\w.-])\.mp(?![\w-])|class=["'][^"']*\bmp\b""")
ROUTES = re.compile(r"/membres\b")


def test_le_module_porte_bien_ce_que_la_garde_cherche():
    """Le plancher. Une garde qui cherche des motifs absents de PARTOUT passe au vert : si le
    module renommait ses classes ou ses routes, le test suivant approuverait un hôte qui le
    recopie sous son nouveau nom. Les deux motifs doivent donc MORDRE sur le module."""
    code = _sans_commentaires(MODULE.read_text(encoding="utf-8"))
    assert len(BALISAGE.findall(code)) >= 20, (
        "le motif du balisage ne reconnaît plus le module : la garde des hôtes est vacante")
    assert len(ROUTES.findall(code)) >= 1, (
        "le motif des routes ne reconnaît plus le module : la garde des hôtes est vacante")


@pytest.mark.parametrize("script", sorted(HOTES))
def test_aucun_hote_n_ecrit_la_partie_ni_n_appelle_ses_routes(script):
    """Un hôte MONTE le module ; il ne dessine rien de la partie et ne lit pas ses données.

    Lu hors commentaires. Une mention dans une chaîne compte, et c'est voulu : un sélecteur
    `.mp-titre` dans un hôte, c'est déjà l'hôte qui sait comment le module est fait (d'où
    `focaliser()`, que la poignée expose pour qu'il n'ait pas à le savoir)."""
    code = _sans_commentaires((STATIC / script).read_text(encoding="utf-8"))
    balisage = sorted(set(m.group(0).strip() for m in BALISAGE.finditer(code)))
    assert not balisage, (
        f"{script} écrit ou vise du balisage de « Qui y entre » : {balisage}. Il vit dans "
        "static/lib/membres-projet.js ; un hôte n'en connaît que `monter()` et sa poignée.")
    routes = sorted(set(ROUTES.findall(code)))
    assert not routes, (
        f"{script} appelle les routes des membres d'un projet ({routes}) : le module lit et "
        "écrit SES données, sans quoi le contrat du serveur vivrait dans deux écrans.")


@pytest.mark.parametrize("script, gabarit",
                         sorted((s, g) for s, gs in HOTES.items() for g in gs))
def test_chaque_hote_monte_le_module_et_le_charge_a_temps(client, script, gabarit):
    """Un hôte listé ici monte réellement le module, et le gabarit le sert AVANT lui — après
    `common.js` et `projet.js`, dont il se sert. Sans la balise, `BDMembresProjet` n'existe
    pas et la page lève une `ReferenceError` à l'ouverture de la première fiche."""
    code = _sans_commentaires((STATIC / script).read_text(encoding="utf-8"))
    assert "BDMembresProjet.monter(" in code, f"{script} ne monte plus le module"

    html = (RACINE / "templates" / gabarit).read_text(encoding="utf-8")
    module, page = "/static/lib/membres-projet.js", f"/static/{script}"
    assert module in html, f"{gabarit} ne charge pas le module"
    for avant in ("/static/lib/common.js", "/static/lib/projet.js"):
        assert html.index(avant) < html.index(module), (
            f"{gabarit} : {avant} doit précéder le module, qui s'en sert")
    assert html.index(module) < html.index(page), (
        f"{gabarit} : le module doit précéder {script}, qui le monte")

    servi = client.get(module)
    assert servi.status_code == 200
    assert "BDMembresProjet" in servi.text


def test_tout_script_de_surface_qui_monte_le_module_est_un_hote_declare():
    """La porte de l'OUBLI : un montage ajouté ailleurs entre dans `HOTES`, ou échoue ici —
    sans quoi le deuxième écran à monter la partie échapperait aux gardes ci-dessus en
    n'étant simplement pas dans la liste."""
    monteurs = sorted(
        p.name for p in STATIC.glob("*.js")
        if "BDMembresProjet" in _sans_commentaires(p.read_text(encoding="utf-8")))
    assert monteurs == sorted(HOTES), (
        f"scripts qui emploient BDMembresProjet : {monteurs} ; hôtes déclarés : {sorted(HOTES)}")


@pytest.mark.parametrize("script", sorted(HOTES))
def test_seul_un_hote_declare_passe_le_mode_du_bac_a_sable(script):
    """`bacASable` réduit la partie : ni annuaire, ni groupe, ni rôle à choisir. Un hôte qui
    le passerait sans être déclaré le ferait pour un projet ordinaire — et son responsable
    ne pourrait plus y nommer un autre responsable ni y faire entrer un groupe."""
    code = _sans_commentaires((STATIC / script).read_text(encoding="utf-8"))
    passe = "bacASable" in code
    assert passe == (script in HOTES_BAC_A_SABLE), (
        f"{script} {'passe' if passe else 'ne passe pas'} `bacASable` : "
        "déclarez-le dans HOTES_BAC_A_SABLE, ou retirez l'option")


def test_le_mode_du_bac_a_sable_ne_lit_pas_l_annuaire():
    """Le plancher de la garde ci-dessus : le mode existe dans le module, et il coupe la
    lecture de l'annuaire — sans quoi une invitation dans un bac à sable lirait les groupes
    de l'instance, l'oracle que S2 ferme pour chaque arrivant."""
    code = _sans_commentaires(MODULE.read_text(encoding="utf-8"))
    assert "options.bacASable" in code, "le module n'a plus de mode « bac à sable »"
    corps = code[code.index("async function lireAnnuaire"):]
    corps = corps[:corps.index("\n  }\n")]
    assert "bacASable" in corps, "lireAnnuaire ne s'arrête plus dans un bac à sable"


def test_le_module_ne_recopie_ni_les_roles_ni_leurs_libelles():
    """Les rôles vivent dans `lib/projet.js`, où leur accord avec le serveur est MESURÉ
    (`tests/test_projet_ecran.py`). Écrits en clair dans le module, ils formeraient une
    troisième copie, que rien ne tiendrait d'accord : entrer poserait un rôle, et la liste
    en proposerait d'autres."""
    code = _sans_commentaires(MODULE.read_text(encoding="utf-8"))
    for mot in ('"membre"', '"responsable"', "'membre'", "'responsable'"):
        assert mot not in code, (
            f"membres-projet.js écrit le rôle {mot} : il se lit dans `BDProjet.ROLES`")
    assert "ROLES[0]" in code and "libelleRole(" in code, (
        "le module ne lit plus les rôles dans `lib/projet.js`")
