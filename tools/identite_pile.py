#!/usr/bin/env python
"""Sur quoi cette pile tourne-t-elle, et en quoi diffère-t-elle de l'image ?  QA-5.

Deux questions que le dépôt ne savait pas poser, et qui sont la même vue des deux bouts.

**« Sur quelle version des dépendances ? »** Un échec de suite dans l'image ne disait ni
quel commit, ni quelle pile — il fallait reconstruire pour le savoir. Lancé par le `CMD`
de l'étape `test`, ce script pose l'identité AVANT la première ligne de pytest, si bien
qu'un journal de construction gardé trois semaines reste lisible.

**« En quoi mon venv diffère-t-il de ce qui sera livré ? »** C'est la thèse de QA-5 prise
au mot. Mesuré le 2026-09-09 : 51 paquets communs portent une version différente entre ce
poste et l'image — dont `numpy` en **1.26 contre 2.4**, un saut de version MAJEURE sous
OpenCV, torch, scipy et scikit-image. La suite passe donc au vert sur numpy 1.x et livre
sur numpy 2.x. C'est la forme exacte du défaut d'ARCH-2 : l'environnement qui MESURE
n'est pas celui qui SERT, et l'écart ne se découvrait qu'en production.

Ce script RAPPORTE, il n'interdit rien : c'est `tests/test_ecart_venv_image.py` qui fait
échouer la suite, et sur les seuls paquets DÉLIBÉRÉMENT épinglés — les autres flottent
par construction, exiger leur égalité sur un poste de travail partagé serait une demande
qu'on ne peut pas satisfaire.

    python tools/identite_pile.py              # identité + écart
    python tools/identite_pile.py --json       # sortie machine
    python tools/identite_pile.py --identite   # identité seule (ce que fait l'image)
"""
import argparse
import hashlib
import importlib.metadata as md
import json
import platform
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from _commun import forcer_utf8  # noqa: E402

# Les verrous d'IMAGE (QA-4) : ce que l'artefact installe réellement.
VERROUS_IMAGE = ("verrou-torch.lock", "verrou-image.lock", "verrou-test.lock")
# Les verrous CHOISIS : les dépendances que le dépôt a décidées, avec leur raison.
VERROUS_CHOISIS = ("requirements.lock", "requirements-dev.lock")


def canon(nom: str) -> str:
    """Le nom canonique d'un paquet (PEP 503) — `Pillow` et `pillow` sont le même."""
    return re.sub(r"[-_.]+", "-", nom).lower()


def _pins(fichier: str) -> dict:
    """{paquet: version} d'un fichier de verrou. Les lignes `nom @ URL` sont écartées :
    elles épinglent par empreinte et n'ont pas de version à comparer."""
    chemin = RACINE / fichier
    if not chemin.exists():
        return {}
    pins = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#"):
            m = re.match(r"^([A-Za-z0-9._-]+)\s*==\s*([^\s;]+)", ligne)
            if m:
                pins[canon(m.group(1))] = m.group(2)
    return pins


def pins_image() -> dict:
    d = {}
    for f in VERROUS_IMAGE:
        d.update(_pins(f))
    return d


def pins_choisis() -> dict:
    d = {}
    for f in VERROUS_CHOISIS:
        d.update(_pins(f))
    return d


def installes() -> dict:
    """{paquet: version} de ce qui est RÉELLEMENT importable ici."""
    vus = {}
    for dist in md.distributions():
        nom = dist.metadata["Name"]
        if nom:
            vus[canon(nom)] = dist.version
    return vus


def ecarts(reference: dict, presents: dict | None = None) -> dict:
    """{paquet: (ici, référence)} pour les paquets PRÉSENTS DES DEUX CÔTÉS.

    L'absence n'est PAS un écart, et c'est délibéré : `uvloop` ne s'installe pas sous
    Windows et `iiif-prezi3` n'est qu'un outil de test. Confondre « je ne l'ai pas » avec
    « je n'ai pas la même version » ferait crier la garde là où rien n'est réparable, et
    l'on apprendrait à ne plus la lire.
    """
    presents = installes() if presents is None else presents
    return {p: (presents[p], v) for p, v in reference.items()
            if p in presents and presents[p] != v}


def absents(reference: dict, presents: dict | None = None) -> list:
    presents = installes() if presents is None else presents
    return sorted(p for p in reference if p not in presents)


def _empreinte(fichier: str) -> str:
    """Les 12 premiers caractères du sha256 d'un verrou — un jeton qui l'identifie.

    Sur son CONTENU NORMALISÉ (lignes utiles, fins de ligne unifiées) : deux machines qui
    régénèrent le même jeu de versions doivent obtenir la même empreinte, or l'une écrit
    en CRLF et l'autre en LF.
    """
    chemin = RACINE / fichier
    if not chemin.exists():
        return "absent"
    utiles = [l.strip() for l in chemin.read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.strip().startswith("#")]
    return hashlib.sha256("\n".join(utiles).encode()).hexdigest()[:12]


def identite() -> dict:
    """Ce qui identifie CETTE pile, en une poignée de valeurs."""
    import config
    import sante

    vus = installes()
    return {
        "commit": config.COMMIT_SERVI or "inconnu",
        "python": platform.python_version(),
        "plateforme": f"{platform.system()} {platform.machine()}",
        "verrous": {f: _empreinte(f) for f in VERROUS_IMAGE},
        "paquets": len(vus),
        "cles": {p: vus.get(p, "—") for p in
                 ("fastapi", "starlette", "pydantic", "numpy", "pillow", "torch",
                  "spacy", "opencv-python", "ultralytics", "easyocr")},
        # Les clés de `rapide()` telles quelles, sans correspondance inventée :
        # `sante.MOTEURS` dit « nlp » là où `rapide()` dit « lemmes », et traduire
        # l'un dans l'autre ici m'a fait afficher `nlp ✗` sur une machine où spaCy
        # ET son modèle sont installés. Un bandeau d'identité qui ment sur ce qu'il
        # décrit est pire que pas de bandeau.
        "moteurs": dict(sante.rapide()),
    }


def _afficher_identite(ident: dict) -> None:
    print("┌─ IDENTITÉ DE LA PILE " + "─" * 46)
    print(f"│  commit      {ident['commit']}")
    print(f"│  python      {ident['python']}   ({ident['plateforme']})")
    print(f"│  paquets     {ident['paquets']} installés")
    for f, e in ident["verrous"].items():
        print(f"│  {f:22} {e}")
    print("│  versions clés")
    for p, v in ident["cles"].items():
        print(f"│      {p:18} {v}")
    print("│  moteurs     " + "  ".join(
        f"{m} {'✓' if ok else '✗'}" for m, ok in ident["moteurs"].items()))
    print("└" + "─" * 68)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="sortie machine")
    ap.add_argument("--identite", action="store_true",
                    help="identité seule, sans l'écart (ce que fait l'image)")
    args = ap.parse_args()
    forcer_utf8()

    vus = installes()
    ident = identite()
    ecart_image = ecarts(pins_image(), vus)
    ecart_choisi = ecarts(pins_choisis(), vus)
    manquants = absents(pins_choisis(), vus)

    if args.json:
        print(json.dumps({"identite": ident,
                          "ecart_image": ecart_image,
                          "ecart_choisi": ecart_choisi,
                          "choisis_absents": manquants},
                         ensure_ascii=False, indent=2))
        return 0

    _afficher_identite(ident)
    if args.identite:
        return 0

    print()
    print(f"ÉCART AVEC L'IMAGE — {len(ecart_image)} paquet(s) commun(s) de version "
          f"différente")
    if ecart_choisi:
        print(f"  dont {len(ecart_choisi)} portant une épingle DÉLIBÉRÉE "
              f"(c'est celles-là que la suite garde) :")
        for p, (ici, ref) in sorted(ecart_choisi.items()):
            print(f"      {p:22} ici {ici:16} verrou {ref}")
    if manquants:
        print(f"  et {len(manquants)} épinglé(s) ABSENT(s) ici : {', '.join(manquants)}")
        print("      (un test qui en dépend se SKIPPE, donc se lit comme un succès)")
    autres = sorted(set(ecart_image) - set(ecart_choisi))
    if autres:
        print(f"  les {len(autres)} autres flottent par construction : "
              f"{', '.join(autres[:12])}{' …' if len(autres) > 12 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
