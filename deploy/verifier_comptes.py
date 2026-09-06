#!/usr/bin/env python3
"""INFRA-11 — le fichier des comptes Authelia, contrôlé AVANT de redémarrer.

    python3 deploy/verifier_comptes.py [chemin]

Ce fichier a eu deux gardes, et aucune n'a vu la panne du 2026-09-06.

  * `authelia validate-config` ne le lit pas du tout — mesuré en y glissant une
    tabulation illégale : « successfully », code 0. Il valide `configuration.yml`.
  * Le contrôle `yaml.safe_load` ajouté par INFRA-8 pour combler ce trou a répondu
    « YAML valide » sur le fichier qui empêchait Authelia de démarrer. Il l'était : la
    syntaxe était parfaite, c'est la VALEUR d'un champ qui ne l'était pas — un condensé
    portant le préfixe `Digest: ` que rend `authelia crypto hash generate`.

Le portail est resté coupé six minutes, pour tout le monde, et le seul contrôle qui
voyait quelque chose était le démarrage d'Authelia lui-même — c'est-à-dire trop tard.

CE QUE CE SCRIPT NE FAIT PAS, et c'est écrit ici pour qu'on cesse de l'espérer.

Il ne valide RIEN cryptographiquement et ne sait pas si un condensé est déchiffrable :
seule Authelia le sait. Reproduire son analyseur fabriquerait une troisième garde à
faux, c'est-à-dire exactement le défaut qu'on répare. Il attrape la CLASSE de faute qui
s'est produite — une valeur qui n'est pas un condensé du tout — et il s'arrête là.

Il ne connaît pas non plus les algorithmes : Authelia accepte argon2, bcrypt, scrypt,
pbkdf2 et les variantes crypt(3), qui n'ont ni le même nombre de champs ni les mêmes
paramètres. Exiger `$argon2id$` refuserait un fichier légitime, et une garde qui crie
sur du correct finit désarmée. La seule propriété commune à TOUS ces formats est le `$`
initial — et c'est précisément elle que le préfixe `Digest: ` brisait.
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:                                    # pragma: no cover
    sys.exit("PyYAML est requis (présent par défaut sur Ubuntu) : pip install pyyaml")

RACINE = Path(__file__).resolve().parent.parent
DEFAUT = RACINE / "deploy" / "authelia" / "users_database.yml"

# Les marqueurs de gabarit. `users_database.example.yml` pose REMPLACER_PAR_UN_VRAI_HASH,
# et une valeur recopiée d'une documentation garde souvent ses points de suspension.
MARQUEURS = ("REMPLACER", "...", "…", "VOTRE", "CHANGEME")


def defauts(chemin) -> list[str]:
    """Rend la liste des défauts trouvés, vide si le fichier est acceptable.

    Le YAML est analysé ici aussi : deux commandes pour un seul fichier, c'est une
    occasion de n'en lancer qu'une, et l'erreur de syntaxe est le cas le plus banal.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        return [f"{chemin} : fichier introuvable"]
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        premiere = str(e).strip().splitlines()[0]
        return [f"YAML invalide : {premiere}"]

    if not isinstance(donnees, dict) or not isinstance(donnees.get("users"), dict):
        return ["le fichier ne porte pas de bloc `users:` — Authelia refusera de démarrer"]

    trouves = []
    for compte, champs in donnees["users"].items():
        if not isinstance(champs, dict):
            trouves.append(f"{compte} : le compte n'est pas un bloc de champs")
            continue
        h = champs.get("password")
        if not isinstance(h, str) or not h.strip():
            trouves.append(f"{compte} : `password` absent ou vide")
            continue
        # L'ordre des contrôles suit leur PRÉCISION : on nomme la faute la plus
        # probable en premier, pour que le message serve à réparer et pas seulement
        # à refuser.
        if not h.startswith("$"):
            debut = h[:24]
            indice = " (le préfixe `Digest: ` de `crypto hash generate` ?)" \
                if h.lower().startswith("digest") else ""
            trouves.append(
                f"{compte} : le condensé ne commence pas par `$` — {debut!r}{indice}")
        elif any(c.isspace() for c in h):
            trouves.append(
                f"{compte} : le condensé contient une espace — copie tronquée ou repliée ?")
        elif any(m in h.upper() for m in MARQUEURS):
            trouves.append(f"{compte} : le condensé est resté celui du gabarit — {h[:32]!r}")
        elif h.count("$") < 3:
            trouves.append(
                f"{compte} : le condensé n'a que {h.count('$')} champ(s) — tronqué ?")
    return trouves


def main(argv) -> int:
    chemin = Path(argv[1]) if len(argv) > 1 else DEFAUT
    trouves = defauts(chemin)
    if trouves:
        print(f"REFUS — {chemin} n'est pas en état d'être servi :")
        for d in trouves:
            print(f"   !! {d}")
        print("\n   NE PAS redémarrer Authelia : elle refuserait de démarrer, et le")
        print("   portail serait coupé pour TOUT LE MONDE jusqu'au retour arrière.")
        return 1
    try:
        n = len(yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))["users"])
    except Exception:                                   # pragma: no cover
        n = 0
    print(f"ok   {chemin.name} : {n} compte(s), aucun condensé manifestement invalide")
    print("     (ce contrôle ne PROUVE pas qu'Authelia démarrera — il écarte la faute")
    print("      qui l'en a empêchée le 2026-09-06, et rien de plus.)")
    return 0


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main(sys.argv))
