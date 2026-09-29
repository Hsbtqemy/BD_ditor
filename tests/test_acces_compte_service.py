"""Le compte de SERVICE de l'annuaire n'ouvre aucune session derrière le portail.  AUTH-6.

**Le défaut qu'il ferme, constaté le 2026-09-18 sur la recette.** Connecté au portail comme
`bd-application` — le compte avec lequel l'application LIT l'annuaire —, on arrivait sur BD,
bandeau de portée vide, « Groupes reçus : lldap_strict_readonly ». La règle qui ouvre le
domaine BD en `one_factor` ne nomme personne : elle vaut pour TOUT compte de l'annuaire, et
elle avait raison tant que l'annuaire ne contenait que des personnes. AUTH-6 y a mis un
identifiant de service dont le mot de passe vit dans le `.env` de l'hôte ; sans règle, il
est aussi un identifiant de portail. L'effet observé était nul — portée vide, fermeture par
défaut d'AUTH-2 —, mais nul par ABSENCE d'accès, pas par règle.

**Ce que ce test exige** : une règle `deny` qui nomme ce compte, sans restriction de chemin,
de méthode ni de réseau, et qui est la PREMIÈRE de `access_control`. L'ordre est le cœur de
la chose : Authelia applique la première règle qui correspond
(`authorization.Authorizer.GetRequiredLevel`, v4.39.22), donc un refus précédé d'une règle
qui correspond aussi à ce compte ne serait jamais atteint — et le fichier se lirait pourtant
très bien. « Avant la règle qui nomme BD » ne suffisait pas : un joker sur le domaine de
cookie ou un `domain_regex` correspond à BD sans le nommer (deux mutants l'ont montré).

**Ce qu'il ne prouve pas.** Qu'Authelia DÉMARRE sur ce fichier (`authelia validate-config`
le dit, dans le conteneur), ni que le nom écrit ici est celui du compte réellement créé dans
LLDAP : le nom est un réglage de l'`.env` (`BD_ANNUAIRE_COMPTE`), et c'est
`verifier_deploiement.py` qui AVERTIT quand les deux divergent.
"""
import re
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parent.parent
CONF = RACINE / "deploy" / "authelia" / "configuration.yml"
ENV_EXEMPLE = RACINE / "deploy" / ".env.example"

if not CONF.exists():
    pytest.skip(
        "deploy/ est exclu du contexte de build (.dockerignore) : ce module ne tourne QUE "
        "sur la machine de développement — cf. QA-6", allow_module_level=True)

COMPTE_SERVICE = "bd-application"
DOMAINE_BD = '{{ env "BD_DOMAINE" }}'
DOMAINE_ANNUAIRE = '{{ env "ANNUAIRE_DOMAINE" }}'


def _regles(texte):
    """Les règles d'`access_control`, lues en YAML.

    Le fichier ENTIER ne se lit pas en YAML (`{{- if env "SMTP_ADRESSE" }}` n'en est pas) ;
    la section, elle, l'est — les `{{ env "…" }}` y sont entre apostrophes, donc des chaînes.
    Même découpe que `test_repli_annuaire._backend`.
    """
    lignes = texte.splitlines()
    assert "access_control:" in lignes, "la section access_control a disparu"
    i = lignes.index("access_control:")
    fin = next((j for j in range(i + 1, len(lignes)) if re.match(r"[A-Za-z_]", lignes[j])),
               len(lignes))
    regles = yaml.safe_load("\n".join(lignes[i:fin]))["access_control"]["rules"]
    assert regles, "access_control ne porte plus aucune règle : la garde ne garde rien"
    return regles


def _domaines(regle):
    d = regle.get("domain", [])
    return [d] if isinstance(d, str) else list(d)


def _nomme(regle, compte):
    """Vrai si la règle vise ce compte À ELLE SEULE.

    `subject` a trois formes : une chaîne, une liste (OU), une liste de listes (ET). Un
    `user:` noyé dans un ET avec un groupe ne viserait le compte que s'il était AUSSI dans
    ce groupe : seule une conjonction à un terme compte.
    """
    sujet = regle.get("subject")
    cible = f"user:{compte}"
    if isinstance(sujet, str):
        return sujet == cible
    for terme in sujet or []:
        if terme == cible or (isinstance(terme, list) and terme == [cible]):
            return True
    return False


def _refus_du_compte(regles):
    return [i for i, r in enumerate(regles)
            if r.get("policy") == "deny" and _nomme(r, COMPTE_SERVICE)]


def _manquements(texte):
    """Ce qui manque au fichier pour que le compte de service soit refusé ; vide si rien."""
    regles = _regles(texte)
    refus = _refus_du_compte(regles)
    if not refus:
        return [f"aucune règle `deny` ne nomme `user:{COMPTE_SERVICE}` : le compte avec lequel "
                "l'application lit l'annuaire ouvre une session sur BD par la règle générale"]
    i = refus[0]
    regle = regles[i]
    manques = [f"le refus du compte de service ne couvre pas {d} ({regle})"
               for d in (DOMAINE_BD, DOMAINE_ANNUAIRE) if d not in _domaines(regle)]
    # Une restriction de chemin, de méthode, de réseau ou de requête ferait du refus un
    # refus PARTIEL : le reste du domaine retomberait sur la règle générale.
    restes = sorted(k for k in ("resources", "methods", "networks", "query") if k in regle)
    if restes:
        manques.append(f"le refus du compte de service est borné par {restes} : il fuit ailleurs")
    # PREMIÈRE, et non « avant la règle qui nomme BD » : une règle qui le précède peut
    # correspondre à BD sans le nommer — un joker `*.{{ env "COOKIE_DOMAINE" }}`, un
    # `domain_regex` — et savoir si elle y correspond demanderait de réécrire l'appariement
    # d'Authelia ici. Exiger la première place ne demande rien.
    if i != 0:
        manques.append(
            f"le refus du compte de service est en position {i + 1}, et non en tête : "
            f"la règle en position 1 ({regles[0]}) est examinée avant lui, et si elle "
            "correspond à ce compte, c'est elle qui décide")
    return manques


def test_le_compte_de_service_est_refuse_avant_que_bd_ne_s_ouvre():
    manques = _manquements(CONF.read_text(encoding="utf-8"))
    assert not manques, "\n".join(manques)


def test_le_nom_du_refus_est_celui_que_l_env_exemple_retient():
    """Le nom vit à deux endroits — la règle d'Authelia et le commentaire qui dit quel compte
    créer dans LLDAP. Un nom changé d'un seul côté ferait créer un compte que la règle ne
    nomme pas, sans qu'aucun des deux fichiers ne paraisse faux."""
    retenu = re.search(r"Nom (?:retenu|imposé)\s*:\s*([\w\-]+(?:\.[\w\-]+)*)",
                       ENV_EXEMPLE.read_text(encoding="utf-8"))
    assert retenu, ".env.example ne dit plus quel nom donner au compte de service"
    assert retenu.group(1) == COMPTE_SERVICE, (
        f".env.example retient `{retenu.group(1)}`, la règle d'Authelia refuse `{COMPTE_SERVICE}`")


# La garde se nourrit de sa propre lecture : on l'éprouve sur des fichiers FABRIQUÉS, pour
# qu'une lecture qui ne trouverait plus rien ne se lise pas comme un fichier conforme.
_OUVRE_BD = f"    - domain: '{DOMAINE_BD}'\n      policy: 'one_factor'\n"
_REFUS = (f"    - domain:\n        - '{DOMAINE_BD}'\n        - '{DOMAINE_ANNUAIRE}'\n"
          f"      subject: 'user:{COMPTE_SERVICE}'\n      policy: 'deny'\n")


@pytest.mark.parametrize("regles,conforme", [
    (_REFUS + _OUVRE_BD, True),
    (_REFUS.replace(f"'user:{COMPTE_SERVICE}'", f"['group:x', 'user:{COMPTE_SERVICE}']")
     + _OUVRE_BD, True),
    (_OUVRE_BD, False),
    (_OUVRE_BD + _REFUS, False),
    (_REFUS.replace(COMPTE_SERVICE, "bd-applicatio") + _OUVRE_BD, False),
    (_REFUS.replace("'deny'", "'one_factor'") + _OUVRE_BD, False),
    (_REFUS.replace(f"'user:{COMPTE_SERVICE}'", f"[['user:{COMPTE_SERVICE}', 'group:x']]")
     + _OUVRE_BD, False),
    (_REFUS.replace(f"        - '{DOMAINE_ANNUAIRE}'\n", "") + _OUVRE_BD, False),
    (_REFUS + "      resources: ['^/api/']\n" + _OUVRE_BD, False),
    ("    - domain: '*.{{ env \"COOKIE_DOMAINE\" }}'\n      policy: 'one_factor'\n"
     + _REFUS + _OUVRE_BD, False),
    ("    - domain_regex: '^bd\\..*$'\n      policy: 'one_factor'\n" + _REFUS + _OUVRE_BD, False),
    ("    - domain: 'autre.exemple.fr'\n      subject: 'group:bd-admins'\n"
     "      policy: 'two_factor'\n" + _REFUS + _OUVRE_BD, False),
], ids=["conforme", "ou", "absent", "apres", "mauvais-nom", "pas-deny", "conjonction",
        "sans-annuaire", "borne", "joker-avant", "regex-avant", "groupe-avant"])
def test_la_garde_distingue_les_formes(regles, conforme):
    texte = "access_control:\n  default_policy: 'deny'\n  rules:\n" + regles + "session:\n"
    assert (not _manquements(texte)) == conforme, _manquements(texte)
