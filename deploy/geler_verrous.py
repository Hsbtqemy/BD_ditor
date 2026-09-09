#!/usr/bin/env python3
"""Régénère les verrous d'IMAGE depuis l'image construite (QA-4).

**Pourquoi depuis l'image et non depuis la machine de dev.** `requirements.lock` épingle
les dépendances DIRECTES — 13 paquets, chacun avec sa spec ou sa raison écrite, ce que
`tests/test_verrou_dependances.py` exige. C'est une liste d'INTENTIONS, et elle doit le
rester : y verser quatre-vingt-dix lignes transitives noierait les treize décisions dans
du bruit et tuerait ce cliquet.

Mais une liste d'intentions ne dit rien de ce qui les suit. Mesuré le 2026-09-09 dans
l'image : **91 paquets à l'exécution pour 13 épinglés**, donc 78 qui flottent — et ce ne
sont pas des feuilles, il y a là `uvicorn`, `starlette` et `pydantic`. Deux constructions
à un mois d'écart ne donnaient pas la même image.

D'où trois verrous SÉPARÉS, et la séparation n'est pas cosmétique : chacun s'installe
avec son propre index ou à sa propre étape.

  · `verrou-torch.lock`   — la fermeture de `torch`/`torchvision` (13 paquets), servie
    par l'index CPU de PyTorch. Elle est à part parce que ses versions portent un
    identifiant LOCAL (`+cpu`) qui n'existe que là. Elle contient aussi `numpy` et
    `pillow` : sans eux, l'installation de torch les résout librement et l'étape
    suivante les RÉTROGRADE — le double travail que QA-4 relevait.
  · `verrou-image.lock`   — le reste de l'exécution, depuis PyPI. Il porte le modèle
    spaCy sous sa forme `fr_core_news_sm @ https://…#sha256=…`, ce qui l'épingle par
    version ET par empreinte. `python -m spacy download` prenait le plus récent
    compatible, et le modèle est ce qui produit les lemmes : l'index de recherche et le
    statut de relecture en dépendent.
  · `verrou-test.lock`    — ce que l'étape `test` ajoute, et rien d'autre.

`pip` est ÉCARTÉ des trois : l'épingler ferait se mettre à jour l'outil au milieu de sa
propre installation.

Usage :

    python deploy/geler_verrous.py            # régénère les trois fichiers
    python deploy/geler_verrous.py --verifier # ne réécrit rien, dit si l'image a dérivé

**Quand le refaire** : après tout changement de `requirements*.lock`, de la ligne torch
du Dockerfile ou de la version de base Python — et jamais autrement. Un gel régénéré
« pour voir » ramasse silencieusement les publications du jour, ce qui est exactement ce
qu'on vient de fermer. Après régénération : reconstruire avec `--no-cache` et lancer la
suite DANS l'image (QA-5), le venv local n'étant pas l'artefact livré.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
from datetime import date

RACINE = pathlib.Path(__file__).resolve().parent.parent
# Les verrous vivent à la RACINE et non dans `deploy/`, où ils seraient pourtant chez
# eux : `.dockerignore` exclut ce dossier ENTIER — `deploy/authelia/users_database.yml`
# porte un hash de mot de passe, et `COPY . .` le déposerait dans une image qui n'a
# aucune raison de connaître les comptes. Y rouvrir une exception ferait de la règle
# « tout sauf X et Y », exactement la forme que son commentaire dénonce comme se
# périmant au premier fichier ajouté. La racine est de toute façon là où vivent déjà
# `requirements.lock` et `requirements-dev.lock`.
DOSSIER = RACINE

# La console Windows est en cp1252 : un « → » y lève `UnicodeEncodeError`. Le dépôt a
# déjà UNE réponse à ça, et la recopier serait la faute qu'elle répare.
sys.path.insert(0, str(RACINE / "tools"))
from _commun import forcer_utf8  # noqa: E402

# Les images intermédiaires de la mesure. Suffixées pour ne jamais écraser une image
# que quelqu'un utilise (`bdediteur:test`, `bdediteur:suite`…).
IMG_BASE = "bdediteur:gel-base"
IMG_TEST = "bdediteur:gel-test"

# `pip` n'entre dans aucun verrou : cf. l'en-tête du module.
EXCLUS = {"pip"}

# Calcule la fermeture de torch DANS l'image — les métadonnées installées sont la seule
# source qui dise ce que CETTE résolution a réellement tiré.
_FERMETURE_TORCH = """
import importlib.metadata as md
from packaging.requirements import Requirement

def deps(nom, vus):
    n = nom.lower().replace("_", "-")
    if n in vus:
        return vus
    vus.add(n)
    try:
        reqs = md.requires(n) or []
    except md.PackageNotFoundError:
        return vus
    for r in reqs:
        req = Requirement(r)
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue          # extras et marqueurs non satisfaits : pas installés
        deps(req.name, vus)
    return vus

vus = set()
deps("torch", vus)
deps("torchvision", vus)
print("\\n".join(sorted(vus)))
"""


def _docker(*args: str, capture: bool = True) -> str:
    """Lance docker, en relevant une erreur PARLANTE plutôt qu'un code de retour nu."""
    r = subprocess.run(["docker", *args], capture_output=capture, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()[-2000:] if capture else ""
        raise SystemExit(f"✗ docker {' '.join(args[:2])} a échoué ({r.returncode})\n{detail}")
    return r.stdout if capture else ""


def _nom(ligne: str) -> str:
    """Le nom normalisé d'une ligne de gel — `x==1.2` comme `x @ https://…`."""
    m = re.match(r"^\s*([A-Za-z0-9._-]+)\s*(?:==|@)", ligne)
    return m.group(1).lower().replace("_", "-") if m else ""


def _geler(image: str) -> dict[str, str]:
    """{nom normalisé: ligne verbatim} — la ligne est gardée TELLE QUELLE.

    Verbatim parce qu'une ligne de gel n'est pas toujours `nom==version` : le modèle
    spaCy sort en `nom @ URL#sha256=…`, et c'est cette forme qui l'épingle par empreinte.
    La reconstruire à partir du nom et de la version perdrait le hash.
    """
    sortie = _docker("run", "--rm", image, "python", "-m", "pip", "freeze", "--all")
    lignes = {}
    for l in sortie.splitlines():
        l = l.strip()
        n = _nom(l)
        if n and n not in EXCLUS:
            lignes[n] = l
    return lignes


def _ecrire(chemin: pathlib.Path, entete: str, lignes: dict[str, str],
            noms: list[str]) -> None:
    corps = "\n".join(lignes[n] for n in sorted(noms))
    # `newline=""` : sans lui, Python traduit `\n` en `\r\n` sur Windows, et un
    # collègue sous Linux qui régénérerait obtiendrait un diff de fichier ENTIER pour
    # rien. Ces fichiers partent dans une image Linux ; ils s'écrivent en LF partout.
    chemin.write_text(entete.rstrip() + "\n\n" + corps + "\n",
                      encoding="utf-8", newline="")


def _entete(titre: str, source: str, quoi: str) -> str:
    return f"""# {titre}
#
# ENGENDRÉ — ne pas éditer à la main. Régénérer par :
#     python deploy/geler_verrous.py
#
# Produit le {date.today().isoformat()} par `pip freeze` DANS l'image `{source}`, et non
# depuis un environnement de développement : le venv local n'est pas l'artefact livré
# (QA-5, mesuré le 2026-08-27 — 451 tests verts en local, trois moteurs morts dans
# l'image le même jour).
#
# {quoi}
#
# Ce fichier ne remplace pas `requirements.lock`, qui reste la liste des dépendances
# CHOISIES, chacune avec sa spec ou sa raison écrite. Celui-ci dit ce qui SUIT de ces
# choix — `tests/test_verrou_dependances.py` vérifie que les deux ne se contredisent
# jamais."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verifier", action="store_true",
                    help="ne réécrit rien ; sort en 1 si l'image a dérivé des verrous")
    args = ap.parse_args()
    forcer_utf8()

    print("→ construction des deux étapes…")
    _docker("build", "-f", "deploy/Dockerfile", "--target", "base", "-t", IMG_BASE, ".",
            capture=False)
    _docker("build", "-f", "deploy/Dockerfile", "--target", "test", "-t", IMG_TEST, ".",
            capture=False)

    print("→ gel des deux fermetures…")
    base, test = _geler(IMG_BASE), _geler(IMG_TEST)
    fermeture_torch = {n for n in
                       _docker("run", "--rm", IMG_BASE, "python", "-c",
                               _FERMETURE_TORCH).split()
                       if n in base}

    noms_torch = sorted(fermeture_torch)
    noms_image = sorted(set(base) - fermeture_torch)
    noms_test = sorted(set(test) - set(base))

    cibles = [
        (DOSSIER / "verrou-torch.lock", noms_torch, base,
         _entete("Verrou TORCH — servi par l'index CPU de PyTorch", IMG_BASE,
                 "Fermeture de `torch` + `torchvision`. À part des autres parce que ses\n"
                 "# versions portent un identifiant LOCAL (`+cpu`) absent de PyPI, et parce\n"
                 "# qu'y inclure `numpy` et `pillow` évite que l'étape suivante ne les\n"
                 "# rétrograde — le double travail que QA-4 relevait.")),
        (DOSSIER / "verrou-image.lock", noms_image, base,
         _entete("Verrou d'EXÉCUTION — le reste de l'image, depuis PyPI", IMG_BASE,
                 "Tout ce dont l'application a besoin pour tourner, hors fermeture torch.\n"
                 "# Porte le modèle spaCy sous sa forme `@ URL#sha256=…` : c'est ce qui\n"
                 "# l'épingle par version ET par empreinte, là où `python -m spacy download`\n"
                 "# prenait le plus récent compatible.")),
        (DOSSIER / "verrou-test.lock", noms_test, test,
         _entete("Verrou de TEST — ce que l'étape `test` ajoute", IMG_TEST,
                 "La différence entre les deux étapes, et rien d'autre : `runtime` reste\n"
                 "# indemne de tout outil de test (QA-5).")),
    ]

    if args.verifier:
        derive = False
        for chemin, noms, lignes, _ in cibles:
            attendu = {lignes[n] for n in noms}
            actuel = {l for l in chemin.read_text(encoding="utf-8").splitlines()
                      if l.strip() and not l.startswith("#")}
            if attendu != actuel:
                derive = True
                print(f"✗ {chemin.name} a dérivé de l'image")
                for l in sorted(attendu - actuel):
                    print(f"    image seule  : {l}")
                for l in sorted(actuel - attendu):
                    print(f"    verrou seul  : {l}")
        if derive:
            return 1
        print("✓ les trois verrous décrivent exactement l'image construite.")
        return 0

    for chemin, noms, lignes, entete in cibles:
        _ecrire(chemin, entete, lignes, noms)
        print(f"✓ {chemin.relative_to(RACINE).as_posix():34} {len(noms):3} paquets")
    print(f"\n  Total gelé : {len(noms_torch) + len(noms_image) + len(noms_test)} paquets "
          f"({len(base)} à l'exécution, +{len(noms_test)} pour les tests).")
    print("  Reconstruire ensuite avec `--no-cache`, puis lancer la suite DANS l'image.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
