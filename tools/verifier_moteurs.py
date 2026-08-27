#!/usr/bin/env python
"""Contrat d'IMAGE : les moteurs exigés sont-ils réellement utilisables ?  SANTE-1 / QA-5.

Lancé À LA CONSTRUCTION de l'image (cf. `deploy/Dockerfile`, étape `runtime`), il fait
échouer le build si un moteur exigé manque ou est cassé. Utilisable aussi à la main sur
une instance en place :  `docker exec bd-app python tools/verifier_moteurs.py`.

Pourquoi un contrôle SÉPARÉ de la suite de tests, alors qu'on vient d'apprendre à faire
tourner celle-ci dans l'image (QA-5) ? Parce qu'elle ne peut pas répondre à cette
question-là. Mesuré le 2026-08-27 sur une image dont le modèle spaCy avait été retiré :
451 tests, **zéro échec**. La couche NLP est conçue pour dégrader proprement et les tests
encodent la même hypothèse — « moteur absent » est un état qu'ils sont écrits pour
accepter, ce qui est CORRECT en développement local, où l'on travaille couramment sans
spaCy.

Un contrat d'image dit autre chose : non pas « le code se comporte bien quand un moteur
manque », mais « cet artefact-ci DOIT porter ces moteurs-là ». Les deux sont nécessaires
et aucun ne remplace l'autre.

Sans `--exiger`, le script se contente de rapporter (code de retour 0) : c'est le mode
diagnostic. Avec `--exiger`, il refuse (code 1) dès qu'un moteur nommé n'est pas utilisable.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sante  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--exiger", default="",
                   help="moteurs OBLIGATOIRES, séparés par des virgules "
                        f"(parmi : {', '.join(sante.MOTEURS)}). "
                        "Vide = rapport seul, sans échec.")
    p.add_argument("--json", action="store_true", help="sortie machine")
    args = p.parse_args()

    exiges = [m.strip() for m in args.exiger.split(",") if m.strip()]
    inconnus = [m for m in exiges if m not in sante.MOTEURS]
    if inconnus:
        print(f"moteur(s) inconnu(s) : {', '.join(inconnus)} "
              f"— attendus parmi {', '.join(sante.MOTEURS)}", file=sys.stderr)
        return 2

    rapport = sante.rapport()

    if args.json:
        import json
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
    else:
        for moteur, r in rapport.items():
            marque = "OK  " if r["ok"] else "PANNE"
            exige = " (exigé)" if moteur in exiges else ""
            print(f"  {marque} {moteur}{exige}")
            if not r["ok"]:
                print(f"        {r['erreur']}")

    manquants = [m for m in exiges if not rapport[m]["ok"]]
    if manquants:
        print(f"\nÉCHEC — moteur(s) exigé(s) inutilisable(s) : {', '.join(manquants)}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
