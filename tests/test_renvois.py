"""Les renvois au code depuis `pilotage/` — une case OUVERTE ne cite pas un numéro de ligne.

Un numéro de ligne ne meurt pas : il VIEILLIT, et vers une ligne qui a du sens. Relevé le
2026-09-08 sur les documents vivants du dépôt : trente renvois, dont un pointant sur
`failed += 1` au milieu d'une autre fonction — du code réel, plausible, sans rien qui
signale qu'on ne regarde pas ce que la phrase annonce. Trois d'entre eux avaient dérivé le
matin même, déplacés par un commit de la veille.

**La règle générale n'est PAS testable, et c'est pourquoi ce cliquet est étroit.** « Une
adresse n'est pas une affirmation » : la repointer ne change aucune phrase, donc on la
repointe — SAUF quand l'adresse EST l'affirmation. Le dépôt en compte deux familles, et
aucune n'est reconnaissable par une machine :

- l'adresse citée comme PREUVE de dérive (`AUDIT-1`, `COL-1`, `INFRA-3` citent chacun un
  renvoi faux pour montrer qu'il l'est — le corriger détruirait le propos) ;
- l'adresse figée dans un constat DATÉ, qui décrit le code d'un jour donné et non celui
  d'aujourd'hui (les `*Constat :*` d'`AUDIT-2`, les mesures rejouées d'`UX-7`).

Ce qui SE décide mécaniquement, en revanche : **une case ouverte est actionnable
aujourd'hui**. Quelqu'un va la lire pour agir, suivre son renvoi, et tomber ailleurs. Son
adresse doit donc être vivante — un symbole, pas un rang dans un fichier qui bouge.

Les deux cas trouvés le 2026-09-08 (`AUTH-1`, `AUTH-7`) étaient encore JUSTES par chance :
c'est exactement l'état où un cliquet a de la valeur, et où une relecture n'en a aucune.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Une adresse de la forme `chemin.ext:12` ou `chemin.ext:12-34`.
RENVOI = re.compile(r"[\w/\.-]+\.(?:py|js|css|html|yml|yaml|sh|mjs):\d+(?:-\d+)?")

# Exceptions DÉCLARÉES, avec leur raison — vide à dessein. Une case ouverte qui devrait
# vraiment citer un rang plutôt qu'un nom se déclare ici ; qu'aucune n'y soit après le
# balayage du 2026-09-08 est une mesure, pas un optimisme.
RENVOIS_ADMIS: dict[str, str] = {}


def _fiches():
    return sorted(RACINE.glob("pilotage/*.md")) + sorted(RACINE.glob("pilotage/qa/*.md"))


def test_aucune_case_ouverte_ne_cite_un_numero_de_ligne():
    fautifs = []
    for f in _fiches():
        for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not ligne.lstrip().startswith("- [ ]"):
                continue
            for m in RENVOI.finditer(ligne):
                cle = f"{f.relative_to(RACINE).as_posix()}:{n}"
                if cle in RENVOIS_ADMIS:
                    continue
                fautifs.append(f"{cle}  cite  {m.group(0)}")
    assert not fautifs, (
        "une case OUVERTE est actionnable aujourd'hui : quelqu'un suivra son renvoi.\n"
        "Citer par SYMBOLE (fonction, route, constante), pas par rang dans un fichier —\n"
        "le rang dérive au premier commit et pointe alors sur du code plausible.\n  "
        + "\n  ".join(fautifs))


def test_le_balayage_voit_bien_les_cases_ouvertes():
    """Le mode d'échec du test ci-dessus est de ne RIEN regarder.

    S'il cessait de reconnaître les cases ouvertes — un changement de gabarit, une puce
    écrite autrement —, il deviendrait vert en n'ayant rien vu. C'est la forme d'échec
    qu'ARCH-2 a payée trois jours : une garde qui approuve sans avoir regardé.
    """
    ouvertes = sum(1 for f in _fiches()
                   for l in f.read_text(encoding="utf-8").splitlines()
                   if l.lstrip().startswith("- [ ]"))
    assert ouvertes > 100, f"le balayage ne voit que {ouvertes} case(s) ouverte(s)"
