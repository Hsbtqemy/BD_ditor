"""COL-3 — ce que l'ÉCRAN tient du serveur sans le lui demander, et ce qui les garde d'accord.

Le projet se voit sur les cinq surfaces, et trois choses de cet écran reposent sur le
serveur sans passer par une route. Chacune vieillirait en silence ; aucune ne casserait un
test navigateur avant longtemps.

1. **Deux valeurs RECOPIÉES.** Le plafond d'un nom et la liste des rôles ne sont publiés par
   aucune route ; `static/lib/projet.js` en tient une copie, pour dire le plafond sous le
   champ de saisie et proposer les rôles. Une copie qui s'écarte annoncerait un plafond que
   le serveur ne tient pas, ou poserait un rôle qu'il refuse.
2. **Une question LUE AILLEURS.** Créer, renommer, supprimer un projet : le serveur répond
   par `Portee.peut_decider_des_projets()`, et l'écran lit `acces.total` dans
   `GET /api/moi`. Les deux disent aujourd'hui la même chose ; rien ne l'impose.
3. **Un filtre qui SUPPOSE.** La Bibliothèque ne montre que les collections du projet
   courant, choisi parmi ceux de `GET /api/projets`. Une collection qu'on lit et dont le
   projet n'y figurerait pas ne serait d'aucun projet à l'écran : elle disparaîtrait, sans
   erreur, d'une liste où le serveur vient de la rendre.

Ce fichier lit des SOURCES pour le premier point — on y compare deux énumérations de
données, ce que le source dit exactement (le patron de `REGIMES_DIFFUSION`, dans
`test_collections_admin.py`) — et JOUE les deux autres. Il tourne dans la suite par défaut.
"""
import re
from pathlib import Path

import pytest

import autorisation
import database
from conftest import ADMIN

RACINE = Path(__file__).resolve().parent.parent
PROJET_JS = RACINE / "static" / "lib" / "projet.js"

ALICE = {"Remote-User": "alice"}
BOB = {"Remote-User": "bob"}


def _source():
    return PROJET_JS.read_text(encoding="utf-8")


def test_le_plafond_du_nom_est_le_meme_des_deux_cotes():
    """L'écran DIT le plafond sous le champ (« N caractères au plus ») : c'est une promesse,
    et c'est le serveur qui la tient."""
    m = re.search(r"const LONGUEUR_NOM = (\d+);", _source())
    assert m, "LONGUEUR_NOM introuvable dans static/lib/projet.js"
    assert int(m.group(1)) == database.LONGUEUR_NOM_PROJET, (
        f"l'écran annonce {m.group(1)} caractères, le serveur en admet "
        f"{database.LONGUEUR_NOM_PROJET}")


def test_les_roles_sont_les_memes_des_deux_cotes_et_dans_le_meme_ordre():
    """« + Faire entrer » pose le PREMIER rôle de la liste : l'ordre compte autant que les
    valeurs. Inversé, entrer dans un projet en nommerait le responsable."""
    m = re.search(r"const ROLES = \[(.*?)\];", _source(), re.S)
    assert m, "ROLES introuvable dans static/lib/projet.js"
    roles = re.findall(r'"([^"]*)"', m.group(1))
    assert roles == list(autorisation.ROLES_PROJET), (
        f"l'écran propose {roles}, le serveur accepte {list(autorisation.ROLES_PROJET)}")
    assert roles[0] == autorisation.MEMBRE, "le premier rôle n'est plus celui d'un membre"


def test_les_cinq_surfaces_chargent_le_projet_courant():
    """La bande du haut est dessinée par `theme.js`, qui lit la règle du projet courant dans
    `lib/projet.js`. Un gabarit qui ne le chargerait pas n'afficherait AUCUN projet, sans
    erreur : `theme.js` se tait quand le module manque, pour ne pas casser la page."""
    gabarits = sorted(p for p in (RACINE / "templates").glob("*.html")
                      if "/static/theme.js" in p.read_text(encoding="utf-8"))
    assert len(gabarits) >= 5, f"gabarits de surface trouvés : {[g.name for g in gabarits]}"
    sans = [g.name for g in gabarits
            if '<script src="/static/lib/projet.js"></script>' not in g.read_text(encoding="utf-8")]
    assert not sans, f"gabarits qui ne chargent pas lib/projet.js : {sans}"


def _membre(client, projet_id, principal, role):
    r = client.put(f"/api/projets/{projet_id}/membres", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": principal, "role": role})
    assert r.status_code == 200, r.text


@pytest.fixture
def deux_projets(client, derriere_proxy):
    """Le projet de repli et « Séminaire » ; alice en est responsable, bob simple membre."""
    r = client.post("/api/projets", json={"nom": "Séminaire"}, headers=ADMIN)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    _membre(client, pid, "alice", autorisation.RESPONSABLE)
    _membre(client, pid, "bob", autorisation.MEMBRE)
    return pid


@pytest.mark.parametrize("qui, entetes", [("administrateur", ADMIN), ("responsable", ALICE),
                                          ("simple membre", BOB)])
def test_decider_des_projets_se_lit_bien_dans_acces_total(client, deux_projets, qui, entetes):
    """L'écran offre « + Créer le projet », « Renommer » et « Supprimer » à qui `GET /api/moi`
    dit `acces.total`. Ce que le SERVEUR accepte doit dire la même chose, pour chacun : sinon
    l'écran offre un bouton qui répond 403, ou cache un geste permis."""
    total = client.get("/api/moi", headers=entetes).json()["acces"]["total"]
    r = client.post("/api/projets", json={"nom": f"Essai {qui}"[:database.LONGUEUR_NOM_PROJET]},
                    headers=entetes)
    assert (r.status_code == 201) == total, (
        f"{qui} : acces.total={total}, création d'un projet → {r.status_code} {r.text}")
    r = client.patch(f"/api/projets/{deux_projets}", json={"nom": f"Renommé {qui}"[:database.LONGUEUR_NOM_PROJET]},
                     headers=entetes)
    assert (r.status_code == 200) == total, (
        f"{qui} : acces.total={total}, renommer → {r.status_code} {r.text}")


def test_en_mono_poste_on_decide_des_projets_et_l_ecran_le_lit(client):
    """Sans proxy : une portée totale, donc les trois gestes — et `acces.total` le dit."""
    assert client.get("/api/moi").json()["acces"]["total"] is True
    assert client.post("/api/projets", json={"nom": "Second"}).status_code == 201


def test_toute_collection_lue_a_son_projet_parmi_ceux_qu_on_peut_nommer(client, deux_projets):
    """Le filtre de la Bibliothèque range chaque collection lue sous UN des projets de
    `GET /api/projets`. Qui lit une collection sans être du projet doit donc pouvoir le
    nommer — sans quoi elle ne serait listée sous aucun, donc nulle part."""
    c = client.post("/api/collections", headers=ADMIN,
                    json={"nom": "Étude", "projet_id": deux_projets})
    assert c.status_code == 201, c.text
    carol = {"Remote-User": "carol"}                      # ni membre, ni rien d'autre
    r = client.put(f"/api/collections/{c.json()['id']}/acces", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": "carol", "niveau": "lecture"})
    assert r.status_code in (200, 201), r.text
    for entetes in (ADMIN, ALICE, BOB, carol):
        projets = {p["id"] for p in client.get("/api/projets", headers=entetes).json()}
        cols = client.get("/api/collections", headers=entetes).json()
        hors = [(x["nom"], x["projet_id"]) for x in cols if x["projet_id"] not in projets]
        assert not hors, (
            f"{entetes.get('Remote-User')} lit des collections dont le projet ne lui est pas "
            f"nommé : {hors} — la Bibliothèque ne les montrerait sous aucun projet")
    assert [x["nom"] for x in client.get("/api/collections", headers=carol).json()] == ["Étude"]
