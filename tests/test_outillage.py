"""Le verrou de l'outillage Node tient-il ?  (`pilote`, le journal de bord.)

Ce fichier existe parce que le gel a sauté TROIS fois, dont deux après avoir été
« corrigé ». La cause a fini par être reproduite plutôt que supposée : **`npm install`
réécrit `git+https://github.com/O/R.git#<sha>` en `github:O/R` et JETTE la référence.**
Le lockfile résout alors le HEAD amont, et la révision installée change sans que personne
ne l'ait demandé — ni le contrat lu par `npm run verifier`, ni `pilotage/_TEMPLATE.md`,
n'ayant été vérifiés pour cette révision-là.

La forme qui SURVIT (mesurée, deux `npm install` de suite) est la forme courte de npm avec
sa référence : `github:O/R#<sha>`. C'est celle qu'exige le premier test.

Geler l'aval — le lockfile — d'une résolution qu'on laisse libre en amont revient à
écrire la conclusion en rouvrant la prémisse. Le premier commit de gel a fait exactement
cela, et le suivant a corrigé la prémisse sans savoir que npm la réécrirait encore.
"""
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SHA = re.compile(r"#([0-9a-f]{40})$")


def _manifeste() -> dict:
    return json.loads((RACINE / "package.json").read_text(encoding="utf-8"))


def _verrou() -> dict:
    return json.loads((RACINE / "package-lock.json").read_text(encoding="utf-8"))


def test_pilote_est_epingle_sur_un_commit():
    """Sans référence dans `package.json`, npm re-résout sur le HEAD amont à chaque
    installation — et le dépôt se met à dépendre d'une révision que personne n'a lue."""
    spec = _manifeste()["devDependencies"]["pilote"]
    assert SHA.search(spec), (
        f"`pilote` n'est pas épinglé sur un commit : {spec!r}.\n"
        "Forme attendue : `github:Hsbtqemy/pilote#<40 caractères hex>`. La forme longue "
        "`git+https://…#<sha>` NE TIENT PAS — `npm install` la normalise en `github:O/R` "
        "et jette la référence (mesuré). Changer de révision est un ACTE : on vérifie "
        "d'abord que `pilotage/_TEMPLATE.md` est identique à celui du paquet et que les "
        "statuts de `journal-contrat.mjs` sont ceux de CLAUDE.md.")


def test_le_verrou_et_le_manifeste_designent_le_meme_commit():
    """Deux fichiers qui se contredisent, c'est une installation dont le résultat dépend
    de la commande employée — et donc de la machine."""
    spec = _manifeste()["devDependencies"]["pilote"]
    m = SHA.search(spec)
    # Sans ce garde-fou, l'absence de référence ferait planter le test en
    # `AttributeError` au lieu de nommer ce qu'il a trouvé — un cliquet qui s'écroule
    # au lieu de parler coûte plus qu'il ne rapporte.
    assert m, f"pas de commit épinglé dans le manifeste : {spec!r} (cf. le test ci-dessus)"
    attendu = m.group(1)
    verrou = _verrou()
    resolu = verrou["packages"]["node_modules/pilote"]["resolved"]
    assert attendu in resolu, (
        f"le manifeste épingle {attendu[:12]} mais le verrou résout {resolu[-45:]} — "
        "lancez `npm install` pour les réaccorder.")
    racine = verrou["packages"][""]["devDependencies"]["pilote"]
    assert attendu in racine, (
        f"le verrou enregistre une autre exigence que le manifeste : {racine!r}")
