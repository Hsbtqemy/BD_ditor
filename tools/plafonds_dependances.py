"""Quels paquets épinglés subissent un PLAFOND imposé par un tiers ? (SEC-3)

Ce qui a retenu le dépôt sous `CVE-2026-25990` n'est pas d'avoir épinglé Pillow — tout est
épinglé dans un verrou, c'est le principe — mais qu'`iiif-prezi3` lui INTERDISE de monter.
C'est cette forme-là qui peut nous laisser sous un correctif de sécurité, et le constat
d'un endroit ne dit rien des autres.

L'outil répond à la question pour tout le verrou, hors ligne : les métadonnées des paquets
installés déclarent leurs contraintes, il suffit de les croiser avec ce qu'on épingle.

**Il ne mesure QUE ce qui est installé.** Lancé dans un environnement où `iiif-prezi3` est
absent, il ne peut rien dire du plafond qui a motivé ce chantier — d'où la doctrine de
QA-5 : le venv local n'est pas l'artefact livré, et ce balayage vaut d'abord dans l'image.

    docker build -f deploy/Dockerfile --target test -t bdediteur:suite .
    docker run --rm bdediteur:suite python tools/plafonds_dependances.py

**Il ne dit pas si une version est vulnérable** : il n'interroge aucun avis. Il nomme les
endroits où l'on ne pourrait PAS monter si un avis tombait, ce qui est la question qu'on ne
peut pas se poser après coup dans l'urgence.

Sortie : code 0 toujours. Ce n'est pas un cliquet — un plafond de version majeure est la
convention ordinaire, pas un défaut, et faire échouer une suite là-dessus apprendrait à
ignorer le signal.
"""
from __future__ import annotations

import argparse
import re
from importlib import metadata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
VERROUS = ("requirements.lock", "requirements-dev.lock")

# `<` et `<=` seulement. `!=` exclut une version isolée sans empêcher de monter, et `~=`
# est une borne que l'on s'impose à soi-même, pas un tiers qui nous retient.
PLAFOND = re.compile(r"(<=|<)\s*([0-9][\w.!+*-]*)")

# Une version de forme MAJEURE : « 2 », « 2.0 », « 1.0.0 ». Ne sert QU'À TRAVERS
# `est_convention` — seule, elle ne décide de rien, et c'était le défaut (cf. ci-dessous).
MAJEUR = re.compile(r"^\d+(\.0)*$")

# Un plafond posé par un tiers : (qui, op, version, marqueur). Le marqueur est ce qui suit
# le `;` de la ligne `Requires-Dist` ; VIDE = exigence obligatoire, et c'est la seule qui
# retienne à coup sûr.
Borne = tuple[str, str, str, str]


def _norm(nom: str) -> str:
    return re.sub(r"[-_.]+", "-", nom).lower()


def est_convention(op: str, version: str) -> bool:
    """« Je ne promets rien au-delà de la prochaine majeure », ou un vrai plafond ?

    **C'est l'OPÉRATEUR qui décide**, et ne regarder que le numéro était le défaut de la
    première version (trouvé le 2026-09-08 en rejouant le balayage dans l'image) :

    - `<2.0` EXCLUT toute la majeure suivante. C'est la convention de l'écosystème, elle
      ne retient personne sous un correctif — un correctif paraît en mineure ou en
      corrective, sous la borne.
    - `<=12.0.0` ADMET cette version-là et rien au-dessus. C'est le plafond le plus serré
      qui existe : il fige une release précise. Et il porte pourtant un numéro de forme
      majeure, ce qui le faisait ranger parmi les conventions — donc masquer par défaut.

    Le cas masqué était `Pillow<=12.0.0` imposé par `iiif-prezi3`, c'est-à-dire le seul
    plafond qui ait jamais motivé cet outil. Un balayage qui cache ce qu'il est venu
    chercher ne rapporte rien, et il le fait sans jamais échouer.
    """
    return op == "<" and bool(MAJEUR.match(version))


def epingles() -> dict[str, str]:
    """Ce que les verrous figent : {paquet normalisé: version}."""
    out: dict[str, str] = {}
    for nom in VERROUS:
        chemin = RACINE / nom
        if not chemin.exists():
            continue
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.split("#")[0].strip()
            m = re.match(r"^([A-Za-z0-9._-]+)\s*==\s*(.+)$", ligne)
            if m:
                out.setdefault(_norm(m.group(1)), m.group(2).strip())
    return out


def lire_exigence(exigence: str) -> tuple[str, list[tuple[str, str]], str]:
    """Une ligne de `Requires-Dist` → (cible, [(op, version)…], marqueur).

    Le marqueur est ce qui suit le `;` — `extra == "dev"`, `python_version < "3.11"`.
    Il est RENDU au lieu d'être jeté : une contrainte derrière `extra` ne s'applique
    qu'à qui installe cet extra, et la confondre avec une obligatoire ferait annoncer
    un plafond qui ne retient personne.

    Les extras de la CIBLE (`requests[security]>=2.0`) sont sautés sans emporter la
    spécification qui les suit — les couper au premier `[` faisait perdre le plafond
    en silence.
    """
    base, _, marqueur = exigence.partition(";")
    m = re.match(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*(.*)$", base)
    if not m:
        return "", [], ""
    return _norm(m.group(1)), PLAFOND.findall(m.group(2)), marqueur.strip()


def plafonds() -> dict[str, set[Borne]]:
    """Qui plafonne qui, d'après les métadonnées INSTALLÉES."""
    out: dict[str, set[Borne]] = {}
    for dist in metadata.distributions():
        nom = dist.metadata["Name"]
        if not nom:
            continue
        for exigence in (dist.requires or []):
            cible, bornes, marqueur = lire_exigence(exigence)
            for op, version in bornes:
                out.setdefault(cible, set()).add((_norm(nom), op, version, marqueur))
    return out


def sans_redites(entrees: set[Borne]) -> list[Borne]:
    """La même borne redite sous un extra ne s'affiche qu'une fois, en obligatoire.

    `iiif-prezi3` déclare `Pillow<=12.0.0` deux fois — une obligatoire, une sous
    `extra == "dev"`. Les afficher toutes deux ferait passer une redite pour deux
    plafonds ; ne garder que la variante marquée ferait passer une obligation pour
    une option.
    """
    obligatoires = {(qui, op, v) for qui, op, v, marq in entrees if not marq}
    return sorted(e for e in entrees
                  if not e[3] or (e[0], e[1], e[2]) not in obligatoires)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tous", action="store_true",
                    help="montre aussi les plafonds de version majeure (convention)")
    args = ap.parse_args(argv)

    fige, impose = epingles(), plafonds()
    installes = {_norm(d.metadata["Name"]) for d in metadata.distributions()
                 if d.metadata["Name"]}
    absents = sorted(p for p in fige if p not in installes)

    serres, conventions = [], []
    for paquet in sorted(fige):
        for qui, op, version, marqueur in sans_redites(impose.get(paquet, set())):
            ligne = (paquet, fige[paquet], qui, f"{op}{version}", marqueur)
            (conventions if est_convention(op, version) else serres).append(ligne)

    def rendre(lignes, verbe):
        # Le VERBE change avec la section : écrire « retenu par » sous un titre qui dit
        # « ils ne retiennent personne » ferait se contredire le rapport en deux lignes.
        for paquet, v, qui, spec, marqueur in lignes:
            # Un plafond derrière un marqueur ne mord que si l'on installe cet extra.
            sous = f"  [sous « {marqueur} »]" if marqueur else ""
            print(f"  {paquet:<22} {v:<12} {verbe} {qui} ({spec}){sous}")

    print(f"{len(fige)} paquets épinglés · {len(absents)} non installés ici\n")
    print("PLAFONDS SERRÉS — on ne pourrait pas monter si un avis tombait")
    if serres:
        rendre(serres, "retenu par")
    else:
        print("  aucun")

    if args.tous:
        print("\nPLAFONDS DE VERSION MAJEURE — convention, ils ne retiennent personne")
        rendre(conventions, "plafonné par")
    else:
        print(f"\n({len(conventions)} plafonds de version majeure masqués — `--tous`)")

    if absents:
        # La limite, dite à chaque exécution plutôt qu'en note de bas de page : c'est
        # précisément un paquet absent qui a motivé ce chantier.
        print("\nATTENTION — épinglés mais NON INSTALLÉS ici, donc invisibles à ce"
              " balayage :")
        print("  " + ", ".join(absents))
        print("  Un plafond qu'ils imposeraient ne peut pas être vu. Rejouez dans"
              " l'image (QA-5).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
