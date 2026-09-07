"""UX-10 — aucune surface de l'application n'échappe aux audits sans qu'on l'ait DÉCIDÉ.

Écrit AVANT la cinquième page `/administration`, et c'est la moitié de sa valeur : une
garde écrite après serait née en constatant l'omission qu'elle devait empêcher.

Le défaut visé est mesuré, pas redouté. Huit fichiers énumèrent les quatre surfaces — les
sept audits E2E et `test_csp` —, et un seul était gardé contre l'oubli. Ajouter une page
sans penser à `test_e2e_a11y.SURFACES` donne une surface jamais auditée pour
l'accessibilité, avec une suite entièrement verte : la page marche, l'audit approuve, et
il approuve en ne regardant pas là.

**Ce test n'exige pas l'exhaustivité, et c'est délibéré.** Les sept audits n'ont pas tous
vocation à couvrir toutes les pages : le défilement n'a rien à dire d'un canevas de
pan/zoom, et l'audit de santé suit un PANNEAU qui ne vit que dans la Bibliothèque. Forcer
la couverture fabriquerait des tests sans objet — et un test sans objet finit par être
écrit pour passer. Ce qu'on exige est plus faible et plus utile : que chaque surface soit
soit AUDITÉE, soit ÉCARTÉE AVEC SA RAISON. Le patron est celui de `HORS_PERIMETRE` dans
`test_autorisation` et de `SORTIES_DECLAREES` dans `test_sorties_identite` — on ne ferme
pas la porte de l'erreur, on ferme celle de l'OUBLI.
"""
import pytest

import surfaces

RAISON_MINIMALE = 20   # « n/a » et « voir plus haut » ne sont pas des raisons


def test_le_recensement_des_audits_n_est_pas_vide():
    """Le plancher, et il vient d'ARCH-2 : une garde qui n'inspecte rien passe au vert.

    `modules_d_audit()` dérive d'un `glob`. Un renommage de fichiers, un déplacement de
    dossier, et la boucle des tests suivants tournerait à vide en les rendant tous verts —
    plus verts à mesure qu'ils voient moins. C'est exactement ce qui est arrivé le
    2026-09-07 à une garde écrite le matin même : `assert not fautifs` est trivialement
    vrai sur une liste vide.
    """
    # NEUF, et le chiffre a été MESURÉ par cette garde même : le recensement à la main
    # qui a précédé en comptait sept, et `test_e2e_audit2` comme `test_e2e_tiroirs` lui
    # avaient échappé — ils ne citaient aucun des chemins que la recherche interrogeait.
    # C'est un CLIQUET : il monte quand on ajoute un audit, et le baisser doit être un
    # geste délibéré, jamais la façon de faire passer une suite devenue rouge.
    trouves = surfaces.modules_d_audit()
    assert len(trouves) >= 9, (
        f"seulement {len(trouves)} module(s) d'audit E2E recensé(s) : {[f.name for f in trouves]}. "
        "Le motif de `modules_d_audit` ne les atteint plus, et tous les contrôles de ce "
        "fichier deviennent vacants sans échouer")


@pytest.mark.parametrize("fichier", surfaces.modules_d_audit(), ids=lambda f: f.name)
def test_chaque_audit_declare_son_perimetre(fichier):
    """Un audit doit DIRE ce qu'il regarde. Le déduire de son code serait le deviner."""
    auditees, hors = surfaces.declarations(fichier)
    assert auditees is not None, (
        f"{fichier.name} n'expose pas `{surfaces.NOM_AUDITEES}` : impossible de savoir ce "
        "qu'il couvre, donc impossible de dire qu'une surface neuve lui a échappé")
    assert hors is not None, (
        f"{fichier.name} n'expose pas `{surfaces.NOM_HORS}`. Un dictionnaire VIDE est une "
        "réponse parfaitement valable — « je couvre tout » — mais elle doit être écrite : "
        "l'absence de déclaration et la couverture totale ne se ressemblent pas assez")


@pytest.mark.parametrize("fichier", surfaces.modules_d_audit(), ids=lambda f: f.name)
def test_aucune_surface_n_echappe_a_un_audit_sans_raison(fichier, client):
    """LE test de ce fichier : toute surface servie est auditée, ou écartée avec sa raison.

    Le jour où `/administration` existera, les sept audits échoueront ensemble tant que
    chacun n'aura pas dit ce qu'il en fait. C'est bruyant, et c'est le but : le mode
    d'échec qu'on remplace était silencieux.
    """
    servies = surfaces.surfaces_servies(client)
    assert servies, (
        "aucune surface HTML détectée : le contrôle ne prouve plus rien. Voir "
        "`inventaire_routes` — la forme de `app.routes` a peut-être changé (ARCH-2)")

    auditees, hors = surfaces.declarations(fichier)
    # Sans ceci, un module non déclaré rend un `TypeError` au lieu d'une phrase. Le test
    # voisin le dit correctement, mais on ne lit pas toujours les deux : une garde qui
    # échoue mal se fait ranger dans « bizarrerie du harnais » plutôt que corriger.
    assert auditees is not None and hors is not None, (
        f"{fichier.name} ne déclare pas son périmètre — voir "
        "`test_chaque_audit_declare_son_perimetre`, qui dit quoi ajouter")
    declarees = set(auditees) | set(hors)

    oubliees = sorted(servies - declarees)
    assert not oubliees, (
        f"{fichier.name} ne dit rien de {oubliees}. Cette ou ces surfaces sont servies par "
        f"l'application et cet audit ne les regarde pas — ce qui est peut-être juste, mais "
        f"doit être ÉCRIT : les ajouter à `{surfaces.NOM_AUDITEES}`, ou à "
        f"`{surfaces.NOM_HORS}` avec la raison de les écarter")

    fantomes = sorted(declarees - servies)
    assert not fantomes, (
        f"{fichier.name} déclare {fantomes}, que l'application ne sert plus. Une liste "
        "périmée rassure, et les tests paramétrés dessus deviennent vacants")


@pytest.mark.parametrize("fichier", surfaces.modules_d_audit(), ids=lambda f: f.name)
def test_la_declaration_est_RATTACHEE_a_ce_que_le_module_fait(fichier, client):
    """Une déclaration doit décrire son module, pas vivre à côté de lui.

    Trouvé en relisant, le 2026-09-07, quelques minutes après avoir écrit le reste de ce
    fichier. `SURFACES_AUDITEES` était une SECONDE COPIE posée près de la vraie liste de
    chaque audit, et rien ne les reliait. Mesuré plutôt que redouté : en retirant
    `"corpus"` du `SURFACES` de `test_e2e_a11y` et en laissant la déclaration intacte, la
    Bibliothèque cessait d'être auditée pour l'accessibilité — le scénario même qu'`UX-10`
    décrit — et tous les contrôles de ce fichier restaient VERTS.

    C'est la forme que la journée entière a rencontrée sept fois, cette fois dans le
    remède : un dispositif qui affirme au lieu de mesurer. Une déclaration qu'aucun
    mécanisme ne confronte à son objet est une intention, et une intention vieillit.
    """
    servies = surfaces.surfaces_servies(client)
    auditees, hors = surfaces.declarations(fichier)
    assert auditees is not None, "voir `test_chaque_audit_declare_son_perimetre`"

    cites = surfaces.chemins_cites(fichier, servies)

    promises = sorted(set(auditees) - cites)
    assert not promises, (
        f"{fichier.name} déclare auditer {promises}, mais son source ne nomme ce ou ces "
        "chemins nulle part. Soit la surface a été retirée de la liste réelle de l'audit "
        "sans que la déclaration suive — et cet audit ne la couvre plus, en silence —, "
        "soit la déclaration a été écrite d'avance. Les deux se réparent au même endroit")

    tues = sorted(cites - set(auditees) - set(hors or {}))
    assert not tues, (
        f"{fichier.name} va sur {tues} sans le déclarer : la surface est visitée par cet "
        f"audit et absente de `{surfaces.NOM_AUDITEES}` comme de `{surfaces.NOM_HORS}`")


@pytest.mark.parametrize("fichier", surfaces.modules_d_audit(), ids=lambda f: f.name)
def test_une_exemption_porte_une_vraie_raison(fichier):
    """Sans ceci, l'exemption devient un moyen de faire taire le test plutôt que de décider.

    C'est le risque propre à toute liste d'exceptions déclarées : elle rend l'omission
    visible, puis elle offre la case où la ranger. Exiger une phrase ne garantit pas
    qu'elle soit vraie — rien ne le peut — mais elle oblige à formuler, et une raison
    qu'on doit écrire est une raison qu'on relit.
    """
    _, hors = surfaces.declarations(fichier)
    for chemin, raison in (hors or {}).items():
        assert isinstance(raison, str) and len(raison.strip()) >= RAISON_MINIMALE, (
            f"{fichier.name} écarte {chemin} sans raison lisible : {raison!r}. "
            "Écrire pourquoi cet audit n'a rien à y dire")
