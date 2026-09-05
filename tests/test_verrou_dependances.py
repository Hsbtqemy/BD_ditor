"""La spec et le verrou disent-ils la même chose ?  ARCH-2.

Le dépôt tient ses dépendances en DEUX temps, et c'est un bon modèle : les
`requirements*.txt` sont la spec lisible (des planchers, une intention), les
`requirements*.lock` sont le verrou de reproductibilité (des versions exactes, QA-1).
L'image de déploiement installe le verrou ; une personne qui développe installe, presque
toujours, la spec.

Rien ne rapprochait les deux. Le 2026-09-05 on a mesuré l'écart : la spec disait
`fastapi>=0.110`, le verrou `fastapi==0.133.0`, et le venv local avait dérivé jusqu'à
0.137 — une version où `app.routes` change de forme. Les deux cliquets qui énumèrent les
routes de l'application y sont devenus aveugles à 56 % du contrat, sans échouer.

L'écart lui-même est ce que ce fichier ferme. QA-5 l'avait dénoncé dans l'autre sens
(« 451 tests verts en local, trois moteurs morts dans l'image ») ; ici c'est le local qui
voyait juste, et ce qu'il voyait, c'est que la garde ne gardait plus rien. Dans les deux
sens la faute est la même : l'environnement qui MESURE n'est pas celui qui SERT, et rien ne
le dit.

Ce que ces tests ne font PAS : ils ne résolvent aucune dépendance. Ils ne peuvent donc pas
promettre qu'un `pip install` neuf rendra la version du verrou — cela demanderait le réseau
et l'index. Ils promettent l'invariant qui reste vérifiable hors ligne, et qui est celui
qui a manqué : la spec et le verrou ne se CONTREDISENT pas.
"""
import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

RACINE = Path(__file__).resolve().parent.parent

SPECS = ("requirements.txt", "requirements-dev.txt", "requirements-export.txt",
         "requirements-ocr.txt", "requirements-nlp.txt", "requirements-kumiko.txt")
VERROUS = ("requirements.lock", "requirements-dev.lock")

# Les paquets dont le dépôt lit un détail que le paquet ne PROMET pas. Ceux-là portent un
# plafond, et la raison s'écrit à côté du plafond, dans la spec.
#
# La liste n'est pas une précaution générale : plafonner tout mettrait le dépôt en dette de
# montée permanente, pour un gain nul là où l'on n'utilise que l'API publique. Ce qui la
# justifie ici est précis — `app.routes` est un attribut interne que trois fichiers de test
# ÉNUMÈRENT, et dont la forme a déjà changé une fois sous eux.
PLAFONNES = {
    "fastapi": "ARCH-2 — `app.routes` change de forme entre 0.133 et 0.137, et deux "
               "cliquets en tirent leur inventaire de routes",
}


def _lignes(nom: str) -> list[str]:
    """Les lignes utiles d'un fichier de dépendances, `-r` et commentaires écartés."""
    texte = (RACINE / nom).read_text(encoding="utf-8")
    return [l.strip() for l in texte.splitlines()
            if l.strip() and not l.strip().startswith(("#", "-r ", "--"))]


def _exigences(noms) -> dict:
    """{paquet: [Requirement, …]} sur un jeu de fichiers, extras compris."""
    out = {}
    for nom in noms:
        for ligne in _lignes(nom):
            exig = Requirement(re.sub(r"\s+#.*$", "", ligne))
            out.setdefault(exig.name.lower(), []).append((nom, exig))
    return out


def test_le_verrou_ne_contredit_jamais_la_spec():
    """Une version épinglée doit SATISFAIRE la spec qui la décrit.

    C'est l'invariant qui manquait, et sa violation est silencieuse dans les deux sens : un
    verrou qui sort de la spec fait installer autre chose selon le fichier employé, et une
    spec resserrée sous son verrou rend le verrou non installable. Ni l'un ni l'autre ne se
    remarque avant que deux environnements ne mesurent des choses différentes.
    """
    specs = _exigences(SPECS)
    fautes = []
    for nom in VERROUS:
        for paquet, paires in _exigences([nom]).items():
            for _, exig in paires:
                epingles = [s.version for s in exig.specifier if s.operator == "=="]
                if not epingles:
                    fautes.append(f"{nom} : `{exig}` n'épingle pas de version — un verrou "
                                  "qui ne verrouille pas est un fichier de plus à lire")
                    continue
                version = Version(epingles[0])
                for src, spec in specs.get(paquet, []):
                    if version not in spec.specifier:
                        fautes.append(
                            f"{paquet} : {nom} épingle {version}, que {src} exclut "
                            f"(`{spec}`). Un `pip install -r {src}` n'installera JAMAIS la "
                            f"version que {nom} — et l'image — utilisent.")
    assert not fautes, (
        "La spec et le verrou se contredisent :\n  " + "\n  ".join(fautes))


def _raison_declaree(nom: str, paquet: str) -> str:
    """Le bloc de commentaires contigus posé JUSTE AU-DESSUS d'un pin, s'il y en a un.

    Le test lit la déclaration au lieu de tenir une liste d'exemptions — même patron que
    les `# noqa: F401` du ré-export, dans `test_decoupage_api`. Une liste d'exemptions vit
    loin du cas qu'elle exempte, et elle survit à sa raison ; un commentaire posé sur la
    ligne part avec elle.
    """
    lignes = (RACINE / nom).read_text(encoding="utf-8").splitlines()
    for i, ligne in enumerate(lignes):
        nu = re.sub(r"\s+#.*$", "", ligne.strip())
        if not nu or nu.startswith(("#", "-r ", "--")):
            continue
        if Requirement(nu).name.lower() != paquet:
            continue
        bloc = []
        for precedente in reversed(lignes[:i]):
            if not precedente.strip().startswith("#"):
                break
            bloc.insert(0, precedente.strip().lstrip("# ").rstrip())
        return " ".join(bloc)
    return ""


def test_tout_paquet_du_verrou_a_une_spec_lisible_ou_une_raison_ecrite():
    """Un pin sans spec est une version qui ne vit qu'à un endroit, et sans intention.

    Le verrou dit QUOI installer, la spec dit POURQUOI cette borne. Un paquet qui n'existe
    que dans le verrou se monte à l'aveugle : personne ne sait quelle plage le dépôt tolère,
    donc personne ne sait si la prochaine montée est un choix ou un accident.

    L'exception est PRÉVUE et elle existe déjà : `opencv-python` est épinglé sans spec
    exprès — `ultralytics` le tire en transitif non épinglé, les deux paquets s'installent
    dans le même `cv2/`, et le non-épinglé gagne à l'import. Épingler le jumeau est le seul
    moyen de rendre le pin effectif. C'est une décision, et elle est écrite au-dessus du
    pin ; ce test la LIT au lieu de la connaître par cœur, faute de quoi il faudrait tenir
    une seconde liste, ailleurs, qui survivrait à sa raison.
    """
    specs = set(_exigences(SPECS))
    fautes = []
    for nom in VERROUS:
        for paquet in _exigences([nom]):
            if paquet in specs:
                continue
            raison = _raison_declaree(nom, paquet)
            if len(raison) < 120:
                fautes.append(
                    f"{nom} : `{paquet}` est épinglé sans figurer dans aucun "
                    f"requirements*.txt, et sans raison écrite au-dessus du pin "
                    f"({len(raison)} caractères de commentaire). Ajoutez la borne lisible "
                    "dans la spec, ou la raison ici — un pin muet est une version que "
                    "personne ne saura monter.")
    assert not fautes, "\n  " + "\n  ".join(fautes)


def test_les_paquets_dont_on_lit_les_entrailles_portent_un_plafond():
    """`fastapi` ne peut plus s'ouvrir jusqu'à une version qui change `app.routes`.

    Le plafond ne remplace pas le plancher dérivé d'`inventaire_routes` : celui-ci fait
    ÉCHOUER un inventaire qui rétrécit, quelle qu'en soit la cause, y compris une cause
    qu'on n'a pas prévue. Le plafond fait autre chose — il empêche l'environnement qui
    mesure de s'éloigner de l'image qui sert. Retirer l'un parce que l'autre existe
    reproduirait exactement la situation du 2026-09-05, par l'un des deux bouts.
    """
    specs = _exigences(["requirements.txt"])
    for paquet, raison in PLAFONNES.items():
        paires = specs.get(paquet)
        assert paires, f"{paquet} a disparu de requirements.txt"
        for src, exig in paires:
            plafonds = [s for s in exig.specifier if s.operator in ("<", "<=", "==", "~=")]
            assert plafonds, (
                f"{src} : `{exig}` n'a plus de plafond. Raison du plafond — {raison}. "
                "Le retirer rouvre la dérive entre le venv de développement et l'image "
                "livrée ; si la raison a cessé de valoir, retirez l'entrée de PLAFONNES "
                "en écrivant pourquoi.")
