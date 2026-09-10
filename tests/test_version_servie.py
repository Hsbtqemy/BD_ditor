"""INFRA-10 — quel commit sert cette instance, et qui a le droit de le savoir.

La donnée existait depuis INFRA-12 et ne quittait jamais `deployer.sh` : elle n'était
lisible qu'au cours d'un déploiement, c'est-à-dire au seul instant où quelqu'un regardait
déjà. Le 2026-09-07, l'instance a servi six commits de retard — dont une fonctionnalité
livrée, testée et annoncée — sans que rien ne le dise, parce que l'écart n'avait aucun
endroit où apparaître.

`GET /api/version` est cet endroit. Elle est SÉPARÉE de `GET /api/sante`, qui doit
répondre sans identité (sonde de conteneur, déclarée telle dans `test_autorisation.py`) :
y ajouter une branche dépendant de l'appelant aurait rendu cette déclaration fausse.

Et elle est RÉSERVÉE, arbitré le 2026-09-07 : le dépôt est public, donc connaître le
commit servi revient à savoir exactement quels correctifs sont en place.
"""
import re
from pathlib import Path

import pytest

import main
from conftest import ADMIN

DOCKERFILE = Path(__file__).resolve().parent.parent / "deploy" / "Dockerfile"


# --------------------------------------------------------------------------- #
# La règle de forme, seule logique du chantier
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("brut, attendu", [
    ("a" * 40,                     "a" * 40),      # un commit
    ("  " + "0" * 40 + "\n",       "0" * 40),      # le même, avec ce qu'un shell y laisse
    ("inconnu",                    None),          # le défaut de l'`ARG` du Dockerfile
    ("",                           None),          # hors conteneur : variable absente
    (None,                         None),
    ("a" * 39,                     None),          # tronqué
    ("a" * 41,                     None),
    ("A" * 40,                     None),          # majuscules : cf. la docstring de la règle
    ("g" * 40,                     None),          # 40 caractères, pas hexadécimaux
    ("025b0d9",                    None),          # forme courte : `deployer.sh` compare du long
])
def test_on_reconnait_un_commit_a_sa_forme(brut, attendu):
    """Jamais en énumérant ce qui n'en est pas.

    La leçon vient de l'étape 2 bis de `deployer.sh` : sa première version listait `""`,
    `inconnu` et `<no value>`, cette dernière d'après ce qu'un gabarit Go rend sur une clé
    absente. Mesuré, la sortie réelle était une ligne VIDE — la liste noire aurait donc
    fermé le bon cas pour la mauvaise raison, et se serait tue le jour d'une quatrième
    valeur. Ici, tout ce qui n'est pas un SHA-1 complet vaut « je ne sais pas ».
    """
    from config import commit_valide
    assert commit_valide(brut) == attendu


# --------------------------------------------------------------------------- #
# La route
# --------------------------------------------------------------------------- #
def test_la_version_servie_est_reservee_aux_administrateurs(client, derriere_proxy):
    """Pas un pouvoir, un RENSEIGNEMENT — et c'est ce qui le rend réservé.

    Sur un dépôt public, le commit servi dit quels correctifs sont en place et lesquels ne
    le sont pas. Il n'est utile qu'à qui exploite l'instance.
    """
    r = client.get("/api/version", headers={"Remote-User": "simple"})
    assert r.status_code == 403
    assert "administrateurs" in r.json()["detail"]


def test_un_administrateur_lit_le_commit_servi(client, derriere_proxy, monkeypatch):
    """Le cas nominal, et il ÉPINGLE la route dans `main.py`.

    Le remplacement porte sur `main.COMMIT_SERVI` parce que `main.py` importe la constante
    par valeur, comme toutes les autres de `config`. C'est le second critère d'ARCH-1 —
    un bloc que les tests remplacent PAR `main` ne peut pas déménager sans que le
    remplacement cesse d'agir EN SILENCE. On l'écrit ici plutôt que de le laisser
    découvrir : cette route reste dans `main.py`, à côté de `/api/sante` qui y est déjà
    épinglée pour la même raison.
    """
    monkeypatch.setattr(main, "COMMIT_SERVI", "b" * 40)
    d = client.get("/api/version", headers=ADMIN).json()
    assert d["commit"] == "b" * 40
    assert d["note"] is None, "rien à expliquer quand la réponse est là"


def test_sans_commit_la_route_DIT_pourquoi(client, derriere_proxy, monkeypatch):
    """Un `null` seul enverrait chercher la mauvaise panne.

    Trois causes mènent au même `null` — image construite sans l'argument, serveur lancé
    hors conteneur, variable retirée du Dockerfile — et l'écran ne peut en deviner aucune.
    C'est le travers que le bandeau de portée vide a dû désapprendre (AUTH-1) : il
    annonçait une cause qu'il n'avait pas établie, et un test verrouillait la formule.
    """
    monkeypatch.setattr(main, "COMMIT_SERVI", None)
    d = client.get("/api/version", headers=ADMIN).json()
    assert d["commit"] is None
    assert d["note"] and "deployer.sh" in d["note"]


def test_en_mono_poste_la_version_se_lit_sans_en_tete(client):
    """Sans `BD_AUTH_PROXY`, la portée est TOTALE : il n'y a personne à qui la cacher.

    Même raison qui rend `acces.groupes_admin` vide en mono-poste (AUTH-4) — nommer un
    rôle d'administrateur là où l'on est seul distinguerait deux rôles qui n'en font qu'un.
    """
    assert client.get("/api/version").status_code == 200


# --------------------------------------------------------------------------- #
# Le Dockerfile, et la panne qui ressemblerait à un environnement de développement
# --------------------------------------------------------------------------- #
def test_le_dockerfile_declare_le_commit_pour_les_DEUX_lecteurs():
    """`LABEL` et `ENV` portent la même valeur, et aucun ne remplace l'autre.

    Le `LABEL` se lit de l'EXTÉRIEUR (`docker inspect`) : c'est ce que `deployer.sh`
    interroge pour décider s'il y a à déployer. L'`ENV` se lit de l'INTÉRIEUR : un `ARG`
    ne survit pas au build, donc sans lui le processus ignore quel commit il sert.

    Ce test existe pour le MODE D'ÉCHEC, pas pour la symétrie. Retirer l'`ENV` ne casse
    rien de visible : la page d'Administration affiche « l'image ne déclare pas le commit
    qu'elle sert », ce qui est exactement ce qu'elle affiche, légitimement, sur une machine
    de développement. La panne se déguise donc en fonctionnement normal, et sur la seule
    surface qui aurait pu la signaler.
    """
    texte = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^ARG BD_COMMIT=", texte, re.M), "l'argument de build a disparu"
    assert re.search(r"^LABEL bd\.commit=\$BD_COMMIT\s*$", texte, re.M), (
        "sans le LABEL, `deployer.sh` ne peut plus comparer et redéploie à chaque passage")
    assert re.search(r"^ENV BD_COMMIT=\$BD_COMMIT\s*$", texte, re.M), (
        "sans l'ENV, le processus qui tourne ignore quel commit il sert, et la page "
        "d'Administration dit « inconnu » pour toujours — indistinguable d'un poste de "
        "développement, donc silencieux")
