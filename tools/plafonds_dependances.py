"""Quels paquets épinglés subissent un PLAFOND imposé par un tiers ? (SEC-3)

Ce qui a retenu le dépôt sous `CVE-2026-25990` n'est pas d'avoir épinglé Pillow — tout est
épinglé dans un verrou, c'est le principe — mais qu'`iiif-prezi3` lui INTERDISE de monter.
C'est cette forme-là qui peut nous laisser sous un correctif de sécurité, et le constat
d'un endroit ne dit rien des autres.

L'outil répond à la question pour tout le verrou, hors ligne : les métadonnées des paquets
installés déclarent leurs contraintes, il suffit de les croiser avec ce qu'on épingle.

**Il ne mesure QUE ce qui est installé, et c'est sa limite principale.** Lancé dans un
environnement où `iiif-prezi3` est absent, il ne voit pas le plafond qui a motivé ce
chantier — mesuré le 2026-09-08. La conclusion suit la doctrine de QA-5 : le venv local
n'est pas l'artefact livré, et ce balayage vaut d'abord dans l'image.

    docker build -f deploy/Dockerfile --target test -t bdediteur:suite .
    docker run --rm bdediteur:suite python tools/plafonds_dependances.py

**Il ne dit pas non plus si une version est vulnérable** : il n'interroge aucun avis. Il
nomme les endroits où l'on ne pourrait PAS monter si un avis tombait, ce qui est la
question qu'on ne peut pas se poser après coup dans l'urgence.

Sortie : code 0 toujours. Ce n'est pas un cliquet — un plafond de version majeure est la
convention ordinaire, pas un défaut, et faire échouer une suite là-dessus apprendrait à
ignorer le signal.
"""
from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
VERROUS = ("requirements.lock", "requirements-dev.lock")

# `<` et `<=` seulement. `!=` exclut une version isolée sans empêcher de monter, et `~=`
# est une borne que l'on s'impose à soi-même, pas un tiers qui nous retient.
PLAFOND = re.compile(r"(<=|<)\s*([0-9][\w.!+*-]*)")

# Un plafond de version MAJEURE (« <2.0 », « <1.0.0 », « <13 ») dit « je ne promets rien
# au-delà de la prochaine majeure » — la convention de tout l'écosystème. Il ne retient
# personne sous un correctif, qui paraît en version mineure ou corrective. Ce sont les
# AUTRES qu'on vient chercher, comme `Pillow<=12.0.0`.
MAJEUR = re.compile(r"^\d+(\.0)*$")


def _norm(nom: str) -> str:
    return re.sub(r"[-_.]+", "-", nom).lower()


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


def plafonds() -> dict[str, list[tuple[str, str]]]:
    """Qui plafonne qui, d'après les métadonnées INSTALLÉES."""
    out: dict[str, list[tuple[str, str]]] = {}
    for dist in metadata.distributions():
        nom = dist.metadata["Name"]
        if not nom:
            continue
        for exigence in (dist.requires or []):
            base = re.split(r"[;\[]", exigence)[0]
            m = re.match(r"^\s*([A-Za-z0-9._-]+)\s*(.*)$", base)
            if not m:
                continue
            cible = _norm(m.group(1))
            for op, version in PLAFOND.findall(m.group(2)):
                out.setdefault(cible, []).append((_norm(nom), op, version))
    return out


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
        for qui, op, version in sorted(set(impose.get(paquet, []))):
            ligne = (paquet, fige[paquet], qui, f"{op}{version}")
            (conventions if MAJEUR.match(version) else serres).append(ligne)

    print(f"{len(fige)} paquets épinglés · {len(absents)} non installés ici\n")
    print("PLAFONDS SERRÉS — on ne pourrait pas monter si un avis tombait")
    if serres:
        for paquet, v, qui, spec in serres:
            print(f"  {paquet:<22} {v:<12} retenu par {qui} ({spec})")
    else:
        print("  aucun")

    if args.tous:
        print("\nPLAFONDS DE VERSION MAJEURE — convention, ils ne retiennent personne")
        for paquet, v, qui, spec in conventions:
            print(f"  {paquet:<22} {v:<12} {qui} ({spec})")
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
