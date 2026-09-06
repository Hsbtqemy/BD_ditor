"""INFRA-11 — le contrôle du fichier des comptes, éprouvé DANS LES DEUX SENS.

Ce module existe à cause d'une panne, et sa forme vient de ce que la panne a appris.

Le 2026-09-06 à 22:43, ajouter un compte de test a coupé le portail six minutes. Le
fichier avait alors deux gardes : `validate-config`, qui ne le lit pas, et le contrôle
`yaml.safe_load` d'INFRA-8, qui a répondu « YAML valide » — il l'était. La syntaxe était
parfaite, c'est la valeur d'un `password` qui ne l'était pas.

**Aucune des deux n'avait jamais été vue ÉCHOUER.** C'est le fil de la journée entière :
l'inventaire de routes d'ARCH-2 approuvait en ne voyant plus que 53 routes sur 122, et la
garde géométrique du bandeau est devenue aveugle à 1440 px le jour de sa naissance. Une
garde qu'on n'éprouve que dans le sens du succès ne prouve rien du tout — d'où le
`test_refuse_*` pour chaque `test_accepte_*` ci-dessous.

**Le second devoir de ces tests est de borner ce que le contrôle PRÉTEND.** Il ne valide
rien cryptographiquement, et il ne doit refuser aucun format légitime : Authelia accepte
argon2, bcrypt, scrypt, pbkdf2 et les variantes crypt(3). `test_accepte_les_autres_
formats` est là pour ça, et il vaut autant que les refus — une garde qui crie sur du
correct finit désarmée, et on aura reproduit le défaut qu'on répare.
"""
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SCRIPT = RACINE / "deploy" / "verifier_comptes.py"

if not SCRIPT.exists():
    pytest.skip(
        "deploy/ est exclu du contexte de build (.dockerignore) : ce module ne tourne QUE "
        "sur la machine de développement. Son skip dans l'image N'EST PAS une couverture "
        "— cf. QA-6, « un skip se lit comme un succès »", allow_module_level=True)

sys.path.insert(0, str(RACINE / "deploy"))
import verifier_comptes  # noqa: E402

# Un condensé argon2id réel, de forme complète — le sel et l'empreinte sont inventés,
# ce qui n'a aucune importance : le contrôle ne déchiffre rien, et c'est écrit.
BON = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaaJObG"

GABARIT = """users:
  chercheur:
    disabled: false
    displayname: 'Chercheur'
    password: '{h}'
    email: 'chercheur@labo.fr'
    groups:
      - 'bd-admins'
"""


def _fichier(tmp_path, contenu):
    p = tmp_path / "users_database.yml"
    p.write_text(contenu, encoding="utf-8")
    return p


# ── Le sens du succès ────────────────────────────────────────────────────────────

def test_accepte_un_fichier_correct(tmp_path):
    assert verifier_comptes.defauts(_fichier(tmp_path, GABARIT.format(h=BON))) == []


@pytest.mark.parametrize("condense", [
    "$2b$12$LongueChaineDeSelEtEmpreinteQuiFaitLeCompteIci123456",   # bcrypt
    "$6$rounds=100000$sel$empreinte",                                # sha512-crypt
    "$scrypt$ln=16,r=8,p=1$c2VsCg$ZW1wcmVpbnRlCg",                   # scrypt
    "$pbkdf2-sha512$310000$c2VsCg$ZW1wcmVpbnRlCg",                   # pbkdf2
])
def test_accepte_les_autres_formats_qu_authelia_admet(tmp_path, condense):
    """Le contrôle ne connaît pas les algorithmes, et ne DOIT pas les connaître.

    Exiger `$argon2id$` refuserait un fichier parfaitement valide. Ce test vaut autant
    que les refus : il borne ce que la garde prétend, et l'empêche de devenir la
    troisième garde à faux de ce fichier.
    """
    assert verifier_comptes.defauts(_fichier(tmp_path, GABARIT.format(h=condense))) == []


# ── Le sens de l'échec, celui qui manquait aux deux gardes précédentes ───────────

def test_refuse_le_prefixe_digest_qui_a_coupe_le_portail(tmp_path):
    """La faute EXACTE du 2026-09-06, rejouée telle quelle.

    `authelia crypto hash generate` rend une ligne préfixée `Digest: `. Collée entière,
    elle passe le YAML sans broncher et fait boucler Authelia au démarrage.
    """
    d = verifier_comptes.defauts(_fichier(tmp_path, GABARIT.format(h="Digest: " + BON)))
    assert len(d) == 1
    assert "chercheur" in d[0]
    # Le message ne se contente pas de refuser : il NOMME la cause probable, parce
    # qu'à 22:43 la question n'était pas « est-ce cassé » mais « pourquoi ».
    assert "Digest" in d[0]


def test_refuse_le_hash_du_gabarit(tmp_path):
    """`users_database.example.yml` pose REMPLACER_PAR_UN_VRAI_HASH. Recopié tel quel,
    il commence bien par `$` — la garde ne peut donc pas s'en remettre au seul `$`."""
    faux = "$argon2id$v=19$m=65536,t=3,p=4$REMPLACER_PAR_UN_VRAI_HASH"
    d = verifier_comptes.defauts(_fichier(tmp_path, GABARIT.format(h=faux)))
    assert len(d) == 1 and "gabarit" in d[0]


def test_refuse_un_condense_coupe_en_deux(tmp_path):
    """Un copier-coller replié par le terminal insère une espace au milieu."""
    coupe = BON[:30] + " " + BON[30:]
    d = verifier_comptes.defauts(_fichier(tmp_path, GABARIT.format(h=coupe)))
    assert len(d) == 1 and "espace" in d[0]


def test_refuse_un_condense_tronque(tmp_path):
    d = verifier_comptes.defauts(_fichier(tmp_path, GABARIT.format(h="$argon2id$v=19")))
    assert len(d) == 1 and "champ" in d[0]


def test_refuse_un_password_absent(tmp_path):
    sans = "users:\n  chercheur:\n    displayname: 'Chercheur'\n"
    d = verifier_comptes.defauts(_fichier(tmp_path, sans))
    assert len(d) == 1 and "absent" in d[0]


def test_refuse_un_yaml_invalide(tmp_path):
    """La tabulation illégale : le cas sur lequel `validate-config` répondait
    « successfully », code 0, le 2026-09-06."""
    d = verifier_comptes.defauts(_fichier(tmp_path, "users:\n\tchercheur: {}\n"))
    assert len(d) == 1 and "YAML" in d[0]


def test_refuse_un_fichier_sans_bloc_users(tmp_path):
    d = verifier_comptes.defauts(_fichier(tmp_path, "autre_chose: 1\n"))
    assert len(d) == 1 and "users" in d[0]


def test_refuse_un_fichier_absent(tmp_path):
    d = verifier_comptes.defauts(tmp_path / "pas-la.yml")
    assert len(d) == 1 and "introuvable" in d[0]


# ── Il regarde TOUS les comptes, pas seulement celui qu'on vient d'ajouter ───────

def test_balaie_tous_les_comptes(tmp_path):
    """Le semis d'AUTH-5 en petit : une garde qui ne regarde qu'un endroit rend un vert
    sincère sur un fichier cassé ailleurs. Ici le compte fautif est le SECOND, et c'est
    le premier qu'on aurait vérifié à l'œil en ajoutant quelqu'un à la fin."""
    deux = GABARIT.format(h=BON) + f"""  stagiaire:
    disabled: false
    displayname: 'Stagiaire'
    password: 'Digest: {BON}'
    email: 'stagiaire@labo.fr'
"""
    d = verifier_comptes.defauts(_fichier(tmp_path, deux))
    assert len(d) == 1 and "stagiaire" in d[0]


# ── Le code de retour, puisque c'est lui qu'un script d'exploitation lit ─────────

def test_le_code_de_retour_distingue_les_deux_cas(tmp_path):
    bon = _fichier(tmp_path, GABARIT.format(h=BON))
    assert verifier_comptes.main(["verifier_comptes.py", str(bon)]) == 0
    mauvais = _fichier(tmp_path, GABARIT.format(h="Digest: " + BON))
    assert verifier_comptes.main(["verifier_comptes.py", str(mauvais)]) == 1


def test_le_fichier_reel_du_depot_est_acceptable():
    """Le GABARIT versionné doit passer le contrôle, sinon la procédure documentée
    échouerait dès sa première étape. Son hash placeholder est refusé — c'est voulu —
    mais on vérifie ici que le fichier est au moins LISIBLE et bien structuré."""
    gabarit = RACINE / "deploy" / "authelia" / "users_database.example.yml"
    d = verifier_comptes.defauts(gabarit)
    assert all("YAML" not in x and "users" not in x for x in d), \
        f"le gabarit versionné n'est pas structurellement lisible : {d}"
